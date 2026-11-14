"""
Run every model x prompt variant x query against a local Ollama server, using
the FROZEN retrieval context written by build_context.py (default
eval_contexts.jsonl; pass --contexts for another file, e.g. the pilot's
pilot/contexts.jsonl from the app's store or pilot/contexts_evalcorpus.jsonl
from eval_corpus.json). Prompt variants: project, project_abstain, minimal.

    python run_models.py --dry-run          # no Ollama contact: shows the plan
    python run_models.py                    # default model list, all three variants
    python run_models.py --models qwen3.5:4b --variants minimal
    python run_models.py --queries pilot_queries.jsonl --contexts pilot/contexts_evalcorpus.jsonl --results-dir pilot/results

Each request: POST /api/chat, stream=true, temperature 0, num_predict 600 (--num-predict),
fixed seed and num_ctx, and no client-side timeout. Recorded per request:

  response                     the VISIBLE answer only
  reasoning_trace              any reasoning block, split out: MedGemma's
                               <unused94>...<unused95>, <think> tags and similar
                               (common.REASONING_MARKERS), plus Ollama's
                               separate `thinking` field; has_reasoning_trace
                               flags it, raw_response keeps the untouched text
  raw_tokens / visible_tokens  all generated tokens (Ollama eval_count) vs the
                               tokens of the visible answer (streamed chunks)
  time_to_first_visible_token  seconds until the first visible-answer token
  latency_s, ollama_timings    first chunk / first raw token / total, and
                               Ollama's own counters
  memory                       sampled peak GPU memory (nvidia-smi,
                               system-wide), ollama process memory, and
                               /api/ps's GPU/CPU split

Models are run one at a time: loaded once (with the run's num_ctx), warmed up
with one short discarded chat request -- its duration is logged as
cold_start_seconds in results/_runs.jsonl and never enters latency statistics
-- then all their variants and queries run, then unloaded so the next model
gets the whole GPU. Missing models are skipped with a message; nothing is ever
pulled. Thinking is turned off (think=false) for models that report the
capability, unless --think is set. (MedGemma does not report it, so its trace
arrives inside the content and is split out as above.)

Resume: results/<model>_<variant>.jsonl is append-only, with one fsync'd line
per finished request. Re-running the same command skips ids that already have
an "ok" record from the same prompt, options and model digest, retries failed
ids, and discards an incomplete final line from an interrupted run. If the
harness version, prompts, contexts, options or the model build changed since
those records were written, the run stops instead of mixing results (see
--rerun-stale).

Standard library only (psutil is used for process memory if installed).
Never imports backend application code.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import prompts
from common import (
    CONTEXTS_PATH,
    HARNESS_VERSION,
    QUERIES_PATH,
    RESULTS_DIR,
    append_jsonl,
    latest_by_id,
    load_queries,
    query_fingerprint,
    read_jsonl,
    repair_partial_tail,
    safe_name,
    sha256_json,
    sha256_text,
    split_reasoning,
    utc_now,
)

try:
    import psutil  # optional
except ImportError:
    psutil = None

DEFAULT_OLLAMA_URL = os.getenv("EVAL_OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_MODELS = (
    "llama3.2:latest",            # installed; same digest (a80c4f17acd5) as llama3.2:3b
    "gemma3:4b",                  # = gemma3:4b-it-q4_K_M; base of MedGemma 1.5 4B (medical-tuning control)
    "qwen3.5:4b",
    "medgemma1.5:4b-it-q4_K_M",
    "medgemma1.5:4b-it-q8_0",
    "gemma4:e4b",                 # 9.6 GB: will not fit a 6 GB GPU, runs split GPU/CPU
)
TEMPERATURE = 0
NUM_PREDICT = 600
KEEP_ALIVE = "30m"
WARMUP_MESSAGES = [{"role": "user", "content": "Reply with the single word: ready"}]
WARMUP_NUM_PREDICT = 8
TOKEN_COUNT_METHOD = "streamed_chunks (Ollama streams one token per chunk; compare raw_chunks with raw_tokens)"
MAX_CONSECUTIVE_ERRORS = 3
RUNS_LOG_NAME = "_runs.jsonl"


# ============================================================================
# Ollama HTTP
# ============================================================================

class OllamaUnavailable(RuntimeError):
    """The server could not be reached at all: abort rather than record errors."""


def _open(url: str, payload: Optional[Dict[str, Any]] = None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        return urllib.request.urlopen(request)  # deliberately no timeout
    except urllib.error.HTTPError:
        raise
    except urllib.error.URLError as exc:
        raise OllamaUnavailable(f"cannot reach Ollama at {url}: {exc.reason}") from exc


def ollama_json(url: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    with _open(url, payload) as response:
        return json.loads(response.read().decode("utf-8"))


def http_error_message(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace")
    except Exception:
        body = ""
    try:
        detail = json.loads(body).get("error", body)
    except (ValueError, AttributeError):
        detail = body or exc.reason
    return f"HTTP {exc.code}: {detail}"


def _canonical_tag(model: str) -> str:
    return model if ":" in model else f"{model}:latest"


def model_info(base_url: str, model: str) -> Optional[Dict[str, Any]]:
    """Capabilities and digest of an installed model, or None if it isn't installed."""
    try:
        show = ollama_json(f"{base_url}/api/show", {"model": model})
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    digest = None
    for entry in ollama_json(f"{base_url}/api/tags").get("models", []):
        if _canonical_tag(model) in (entry.get("name"), entry.get("model")):
            digest = entry.get("digest")
    return {
        "capabilities": list(show.get("capabilities") or []),
        "digest": digest,
        "details": show.get("details") or {},
    }


def load_model(base_url: str, model: str, options: Dict[str, Any]) -> float:
    """Load weights with the run's num_ctx, so the first real request never triggers a reload."""
    started = time.perf_counter()
    ollama_json(f"{base_url}/api/generate", {
        "model": model, "keep_alive": KEEP_ALIVE, "stream": False,
        "options": {"num_ctx": options["num_ctx"]},
    })
    return time.perf_counter() - started


def warm_up(base_url: str, model: str, options: Dict[str, Any], think: Optional[bool]) -> Dict[str, Any]:
    """One short, discarded chat request with the run's own options (same num_ctx, so no reload).

    The first forward pass for an architecture pays one-off setup costs (6-15 s
    in the pilot). Spending them here keeps them out of every measured request;
    the time is recorded per model as cold_start_seconds.
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": WARMUP_MESSAGES,
        "stream": False,
        "options": {**options, "num_predict": WARMUP_NUM_PREDICT},
        "keep_alive": KEEP_ALIVE,
    }
    if think is not None:
        payload["think"] = think
    started = time.perf_counter()
    reply = ollama_json(f"{base_url}/api/chat", payload)
    return {"cold_start_seconds": round(time.perf_counter() - started, 3), "ollama_timings": _ollama_timings(reply)}


def unload_model(base_url: str, model: str) -> None:
    ollama_json(f"{base_url}/api/generate", {"model": model, "keep_alive": 0, "stream": False})


def loaded_model_memory(base_url: str, model: str) -> Optional[Dict[str, Any]]:
    """/api/ps view of the loaded model: total size and the part resident in VRAM."""
    try:
        running = ollama_json(f"{base_url}/api/ps").get("models", [])
    except (urllib.error.HTTPError, OllamaUnavailable):
        return None
    for entry in running:
        if _canonical_tag(model) in (entry.get("name"), entry.get("model")):
            return {"size_bytes": entry.get("size"), "size_vram_bytes": entry.get("size_vram")}
    return None


def stream_chat(base_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    started = time.perf_counter()
    first_chunk = first_token = first_thinking = None
    content: List[str] = []
    thinking: List[str] = []
    content_chunks: List[Tuple[int, int, float]] = []   # (start offset, end offset, seconds) per content chunk
    thinking_chunks = 0
    offset = 0
    final: Dict[str, Any] = {}
    with _open(f"{base_url}/api/chat", payload) as response:
        for raw in response:
            if not raw.strip():
                continue
            elapsed = time.perf_counter() - started
            chunk = json.loads(raw)
            if chunk.get("error"):
                raise RuntimeError(f"Ollama error: {chunk['error']}")
            if first_chunk is None:
                first_chunk = elapsed
            message = chunk.get("message") or {}
            if message.get("thinking"):
                thinking.append(message["thinking"])
                thinking_chunks += 1
                if first_thinking is None:
                    first_thinking = elapsed
            if message.get("content"):
                piece = message["content"]
                content.append(piece)
                content_chunks.append((offset, offset + len(piece), elapsed))
                offset += len(piece)
                if first_token is None:
                    first_token = elapsed
            if chunk.get("done"):
                final = chunk
                break
    total = time.perf_counter() - started
    if not final:
        raise RuntimeError("stream ended before Ollama sent its final 'done' message")
    return {
        "content": "".join(content),
        "thinking": "".join(thinking),
        "content_chunks": content_chunks,
        "thinking_chunks": thinking_chunks,
        "final": final,
        "first_chunk_s": first_chunk,
        "first_token_s": first_token,
        "first_thinking_s": first_thinking,
        "total_s": total,
    }


def visible_answer_metrics(out: Dict[str, Any]) -> Dict[str, Any]:
    """Split the reasoning trace out of the streamed content and measure the visible answer."""
    raw = out["content"]
    split = split_reasoning(raw)
    spans = split["visible_spans"]

    def chunk_is_visible(start: int, end: int) -> bool:
        return any(raw[max(start, a): min(end, b)].strip() for a, b in spans if start < b and end > a)

    visible_times = [t for start, end, t in out["content_chunks"] if chunk_is_visible(start, end)]
    sources = (["ollama_thinking_field"] if out["thinking"].strip() else []) + split["formats"]
    trace_parts = [part for part in (out["thinking"].strip(), split["trace"]) if part]
    return {
        "response": split["visible"],
        "raw_response": raw,
        "reasoning_trace": "\n\n".join(trace_parts) or None,
        "has_reasoning_trace": bool(trace_parts),
        "reasoning_trace_sources": sources or None,
        "reasoning_trace_closed": split["closed"] if split["formats"] else None,
        "raw_tokens": out["final"].get("eval_count"),
        "raw_chunks": len(out["content_chunks"]) + out["thinking_chunks"],
        "visible_tokens": len(visible_times),
        "time_to_first_visible_token": visible_times[0] if visible_times else None,
    }


def _ollama_timings(final: Dict[str, Any]) -> Dict[str, Any]:
    keys = ("total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration",
            "eval_count", "eval_duration")
    timings: Dict[str, Any] = {f"{key}_ns" if key.endswith("duration") else key: final.get(key) for key in keys}
    if final.get("eval_count") and final.get("eval_duration"):
        timings["eval_tokens_per_s"] = round(final["eval_count"] / (final["eval_duration"] / 1e9), 2)
    return timings


# ============================================================================
# Memory sampling
# ============================================================================

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run_quiet(cmd: List[str]) -> Optional[str]:
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=15, creationflags=_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def gpu_memory_used_mib() -> Optional[int]:
    """Used VRAM summed over NVIDIA GPUs -- system-wide, so it includes other processes."""
    if not shutil.which("nvidia-smi"):
        return None
    out = _run_quiet(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"])
    values = []
    for line in (out or "").splitlines():
        try:
            values.append(int(float(line.strip())))
        except ValueError:
            continue
    return sum(values) if values else None


def ollama_process_memory_mib() -> Tuple[Optional[float], str]:
    """Memory of all ollama* processes (server + model runner) and how it was measured."""
    if psutil is not None:
        total = 0
        for proc in psutil.process_iter(["name", "memory_info"]):
            name = (proc.info.get("name") or "").lower()
            mem = proc.info.get("memory_info")
            if name.startswith("ollama") and mem is not None:
                total += mem.rss
        return round(total / 2**20, 1), "psutil_rss"
    if os.name == "nt":
        out = _run_quiet(["tasklist", "/FO", "CSV", "/NH", "/FI", "IMAGENAME eq ollama*"])
        if out is None:
            return None, "tasklist_working_set"
        total_kib = 0
        for row in csv.reader(io.StringIO(out)):
            if len(row) >= 5:
                digits = "".join(ch for ch in row[4] if ch.isdigit())
                total_kib += int(digits) if digits else 0
        return round(total_kib / 1024, 1), "tasklist_working_set"
    out = _run_quiet(["ps", "-A", "-o", "rss=,comm="])
    if out is None:
        return None, "ps_rss"
    total_kib = 0
    for line in out.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and "ollama" in parts[1].lower() and parts[0].isdigit():
            total_kib += int(parts[0])
    return round(total_kib / 1024, 1), "ps_rss"


class MemorySampler:
    """Polls GPU and ollama-process memory in a background thread; keeps the peaks."""

    def __init__(self, interval_s: float, enabled: bool = True):
        self.interval_s = interval_s
        self.enabled = enabled
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.gpu_peak_mib: Optional[int] = None
        self.cpu_peak_mib: Optional[float] = None
        self.cpu_method: Optional[str] = None
        self.samples = 0

    def __enter__(self) -> "MemorySampler":
        if self.enabled:
            self._thread = threading.Thread(target=self._loop, name="memory-sampler", daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()

    def _loop(self) -> None:
        while True:
            gpu = gpu_memory_used_mib()
            cpu, method = ollama_process_memory_mib()
            if gpu is not None:
                self.gpu_peak_mib = gpu if self.gpu_peak_mib is None else max(self.gpu_peak_mib, gpu)
            if cpu is not None:
                self.cpu_peak_mib = cpu if self.cpu_peak_mib is None else max(self.cpu_peak_mib, cpu)
            self.cpu_method = method
            self.samples += 1
            if self._stop.wait(self.interval_s):
                return


def _total_ram_gib() -> Optional[float]:
    if os.name == "nt":
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return round(status.ullTotalPhys / 2**30, 2)
        return None
    try:
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 2)
    except (ValueError, OSError, AttributeError):
        return None


def hardware_snapshot() -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {
        "platform": sys.platform,
        "logical_cpus": os.cpu_count(),
        "ram_total_gib": _total_ram_gib(),
        "gpus": [],
    }
    if shutil.which("nvidia-smi"):
        out = _run_quiet(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                          "--format=csv,noheader,nounits"])
        for line in (out or "").splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) == 3:
                snapshot["gpus"].append({"name": parts[0], "vram_total_mib": int(float(parts[1])), "driver": parts[2]})
    return snapshot


# ============================================================================
# Planning and resume
# ============================================================================

def build_jobs(
    queries: List[Dict[str, Any]],
    contexts: Dict[str, Dict[str, Any]],
    variants: List[str],
    project_layout: str,
) -> Tuple[Dict[str, List[Dict[str, Any]]], List[str]]:
    """Rendered request for every (variant, query). Returns (jobs by variant, problems)."""
    problems = []
    jobs: Dict[str, List[Dict[str, Any]]] = {variant: [] for variant in variants}
    for query in queries:
        context = contexts.get(query["id"])
        if context is None:
            problems.append(f"{query['id']}: no frozen context -- run build_context.py")
            continue
        if context.get("query_sha256") != query_fingerprint(query):
            problems.append(f"{query['id']}: query text/procedure changed since contexts were built -- re-run build_context.py")
            continue
        if not context.get("context_sha256"):
            problems.append(f"{query['id']}: context has no context_sha256 (built by an older build_context.py) -- rebuild it")
            continue
        for variant in variants:
            messages = prompts.build_messages(variant, query, context, project_layout=project_layout)
            jobs[variant].append({
                "query": query,
                "context": context,
                "messages": messages,
                "prompt_sha256": sha256_json(messages),
                "context_sha256": context["context_sha256"],
            })
    return jobs, problems


def classify_existing(
    path: Path,
    jobs: List[Dict[str, Any]],
    options: Dict[str, Any],
    digest: Optional[str],
) -> Tuple[List[Dict[str, Any]], List[str], int]:
    """(jobs still to run, ids whose finished record is stale, number already done)."""
    existing = latest_by_id(record for _, record in read_jsonl(path, allow_partial_tail=True))
    todo, stale, done = [], [], 0
    for job in jobs:
        previous = existing.get(job["query"]["id"])
        if previous is None or previous.get("status") != "ok":
            todo.append(job)
            continue
        same = (
            previous.get("harness_version") == HARNESS_VERSION          # older harness output is stale
            and previous.get("prompt_sha256") == job["prompt_sha256"]
            and previous.get("context_sha256") == job["context_sha256"]   # catches a corpus change
            and previous.get("options") == options
            and (digest is None or previous.get("model_digest") == digest)
        )
        if same:
            done += 1
        else:
            stale.append(job["query"]["id"])
            todo.append(job)
    return todo, stale, done


def results_path(results_dir: Path, model: str, variant: str) -> Path:
    return results_dir / f"{safe_name(model)}_{variant}.jsonl"


# ============================================================================
# Execution
# ============================================================================

def run_variant(
    base_url: str,
    model: str,
    info: Dict[str, Any],
    variant: str,
    path: Path,
    todo: List[Dict[str, Any]],
    options: Dict[str, Any],
    think: Optional[bool],
    args: argparse.Namespace,
) -> bool:
    consecutive_errors = 0
    for index, job in enumerate(todo, start=1):
        query, context = job["query"], job["context"]
        payload: Dict[str, Any] = {
            "model": model,
            "messages": job["messages"],
            "stream": True,
            "options": options,
            "keep_alive": KEEP_ALIVE,
        }
        if think is not None:
            payload["think"] = think

        gpu_at_start = None if args.no_memory else gpu_memory_used_mib()
        started_at = utc_now()
        out: Optional[Dict[str, Any]] = None
        error: Optional[str] = None
        sampler = MemorySampler(args.sample_interval, enabled=not args.no_memory)
        try:
            with sampler:
                out = stream_chat(base_url, payload)
        except OllamaUnavailable:
            raise
        except urllib.error.HTTPError as exc:
            error = http_error_message(exc)
        except (RuntimeError, ValueError, OSError) as exc:
            error = f"{type(exc).__name__}: {exc}"

        visible = visible_answer_metrics(out) if out else {}
        response = visible.get("response")
        prompt_eval_count = out["final"].get("prompt_eval_count") if out else None
        record = {
            "id": query["id"],
            "domain": query["domain"],
            "procedure": query["procedure"],
            "answerability": query["answerability"],
            "model": model,
            "model_digest": info["digest"],
            "variant": variant,
            "project_layout": args.project_layout if variant.startswith("project") else None,
            "status": "ok" if error is None else "error",
            "error": error,
            # `response` is the VISIBLE answer only; any reasoning trace is in reasoning_trace.
            "response": response,
            "response_sha256": sha256_text(response) if response is not None else None,
            "empty_response": (response is not None and not response.strip()),
            "has_reasoning_trace": visible.get("has_reasoning_trace"),
            "reasoning_trace": visible.get("reasoning_trace"),
            "reasoning_trace_sources": visible.get("reasoning_trace_sources"),
            "reasoning_trace_closed": visible.get("reasoning_trace_closed"),
            "raw_response": visible.get("raw_response"),
            "raw_tokens": visible.get("raw_tokens"),
            "raw_chunks": visible.get("raw_chunks"),
            "visible_tokens": visible.get("visible_tokens"),
            "token_count_method": TOKEN_COUNT_METHOD if out else None,
            "time_to_first_visible_token": visible.get("time_to_first_visible_token"),
            "hit_token_limit": (out["final"].get("done_reason") == "length") if out else None,
            "done_reason": out["final"].get("done_reason") if out else None,
            "latency_s": {
                "first_chunk": out["first_chunk_s"],
                "first_token": out["first_token_s"],        # first content token, trace included
                "first_thinking": out["first_thinking_s"],
                "total": out["total_s"],
            } if out else None,
            "ollama_timings": _ollama_timings(out["final"]) if out else None,
            "memory": {
                "gpu_used_at_start_mib": gpu_at_start,
                "gpu_used_peak_mib": sampler.gpu_peak_mib,
                "ollama_process_peak_mib": sampler.cpu_peak_mib,
                "ollama_process_method": sampler.cpu_method,
                "sample_interval_s": args.sample_interval,
                "samples": sampler.samples,
                "loaded_model": loaded_model_memory(base_url, model),
            } if not args.no_memory else None,
            "options": options,
            "think": think,
            "prompt_sha256": job["prompt_sha256"],
            "context_sha256": job["context_sha256"],
            "corpus": {key: (context.get("corpus") or {}).get(key) for key in ("kind", "path", "sha256")},
            "query_sha256": context.get("query_sha256"),
            "postop_day": query["postop_day"],
            "n_context_chunks": len(context.get("chunks") or []),
            "prompt_chars": sum(len(message["content"]) for message in job["messages"]),
            # Lower bound only: Ollama reuses a cached shared prefix, so the count can be low.
            "context_may_be_truncated": (
                prompt_eval_count is not None and prompt_eval_count + options["num_predict"] >= options["num_ctx"]
            ),
            "started_at": started_at,
            "finished_at": utc_now(),
            "harness_version": HARNESS_VERSION,
        }
        append_jsonl(path, record)

        if error is None:
            latency = record["latency_s"]
            ttfv = record["time_to_first_visible_token"]
            first = f"{ttfv:.2f}s" if ttfv is not None else "n/a"
            flags = "".join([
                "  TRACE" if record["has_reasoning_trace"] else "",
                "  HIT-LIMIT" if record["hit_token_limit"] else "",
                "  NO VISIBLE ANSWER" if record["empty_response"] else "",
            ])
            print(f"  [{variant} {index}/{len(todo)}] {query['id']}: ok  first_visible={first}  "
                  f"total={latency['total']:.2f}s  tokens={record['visible_tokens']}/{record['raw_tokens']}{flags}")
            consecutive_errors = 0
        else:
            print(f"  [{variant} {index}/{len(todo)}] {query['id']}: ERROR {error}")
            consecutive_errors += 1
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                print(f"  {model}: stopping after {consecutive_errors} consecutive errors; re-run to retry them.")
                return False
    return True


def run(args: argparse.Namespace, jobs: Dict[str, List[Dict[str, Any]]], options: Dict[str, Any]) -> int:
    base_url = args.ollama_url.rstrip("/")
    version = ollama_json(f"{base_url}/api/version").get("version")
    print(f"Ollama {version} at {base_url}")

    available: Dict[str, Dict[str, Any]] = {}
    for model in dict.fromkeys(args.models):
        info = model_info(base_url, model)
        if info is None:
            print(f"SKIP {model}: not installed (this harness never pulls; run `ollama pull {model}` yourself if wanted)")
        else:
            available[model] = info
    if not available:
        print("None of the requested models are installed.")
        return 1

    plan = []
    stale_report = []
    for model, info in available.items():
        for variant in args.variants:
            path = results_path(args.results_dir, model, variant)
            todo, stale, done = classify_existing(path, jobs[variant], options, info["digest"])
            if stale:
                shown = ", ".join(stale[:5]) + (" ..." if len(stale) > 5 else "")
                stale_report.append(f"{path.name}: {len(stale)} finished record(s) came from a different "
                                    f"harness version/prompt/context (corpus)/options/model digest ({shown})")
            plan.append((model, variant, path, todo, done))
    if stale_report and not args.rerun_stale:
        print("Refusing to mix results produced under different settings:")
        for line in stale_report:
            print(f"  {line}")
        print("Use a fresh --results-dir, or --rerun-stale to redo those ids (the newest record per id wins).")
        return 2

    hardware = hardware_snapshot()
    runs_log = args.results_dir / RUNS_LOG_NAME
    exit_code = 0
    for model, info in available.items():
        model_plan = [entry for entry in plan if entry[0] == model]
        pending = sum(len(entry[3]) for entry in model_plan)
        if pending == 0:
            print(f"{model}: nothing to do ({sum(entry[4] for entry in model_plan)} already done)")
            continue
        think = args.think if "thinking" in info["capabilities"] else None
        gpu_before = gpu_memory_used_mib()
        print(f"{model}: loading ({pending} request(s) to run, think={think})")
        load_s = load_model(base_url, model, options)
        gpu_after_load = gpu_memory_used_mib()
        try:
            warm = warm_up(base_url, model, options, think)
            warm_error = None
        except urllib.error.HTTPError as exc:
            warm, warm_error = {"cold_start_seconds": None, "ollama_timings": None}, http_error_message(exc)
        # cold_start_seconds lives only here, never in per-request latency statistics.
        append_jsonl(runs_log, {
            "event": "model_loaded",
            "at": utc_now(),
            "model": model,
            "model_digest": info["digest"],
            "capabilities": info["capabilities"],
            "details": info["details"],
            "ollama_version": version,
            "load_s": round(load_s, 3),
            "cold_start_seconds": warm["cold_start_seconds"],
            "warmup_ollama_timings": warm["ollama_timings"],
            "warmup_error": warm_error,
            "gpu_used_before_load_mib": gpu_before,
            "gpu_used_after_load_mib": gpu_after_load,
            "loaded_model": loaded_model_memory(base_url, model),
            "options": options,
            "think": think,
            "hardware": hardware,
            "harness_version": HARNESS_VERSION,
        })
        if warm_error:
            print(f"  {model}: warm-up failed ({warm_error}); skipping this model.")
            exit_code = 1
            if not args.keep_loaded:
                try:
                    unload_model(base_url, model)
                except (urllib.error.HTTPError, OllamaUnavailable):
                    pass
            continue
        print(f"  load={load_s:.1f}s  cold_start (warm-up, discarded)={warm['cold_start_seconds']:.1f}s")
        try:
            for _, variant, path, todo, _ in model_plan:
                if not todo:
                    continue
                removed = repair_partial_tail(path)
                if removed:
                    print(f"  {path.name}: discarded an incomplete final line ({removed} bytes) from an interrupted run")
                if not run_variant(base_url, model, info, variant, path, todo, options, think, args):
                    exit_code = 1
                    break
        finally:
            if not args.keep_loaded:
                try:
                    unload_model(base_url, model)
                except (urllib.error.HTTPError, OllamaUnavailable):
                    pass
    return exit_code


def dry_run(args: argparse.Namespace, jobs: Dict[str, List[Dict[str, Any]]], options: Dict[str, Any]) -> int:
    print("DRY RUN -- Ollama is not contacted; model digests are not compared.")
    print(f"options={options}  project_layout={args.project_layout}  think={'on' if args.think else 'off'}")
    for model in dict.fromkeys(args.models):
        for variant in args.variants:
            path = results_path(args.results_dir, model, variant)
            todo, stale, done = classify_existing(path, jobs[variant], options, digest=None)
            print(f"  {path.name}: {done} done, {len(todo) - len(stale)} to run, {len(stale)} stale")
    for variant in args.variants:
        if jobs[variant]:
            example = jobs[variant][0]
            print(f"\n--- example {variant} request ({example['query']['id']}) ---")
            print(json.dumps(example["messages"], indent=2, ensure_ascii=False))
    return 0


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare local Ollama models on frozen RAG context.")
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument("--variants", nargs="+", choices=prompts.VARIANTS, default=list(prompts.VARIANTS))
    parser.add_argument("--project-layout", choices=prompts.PROJECT_LAYOUTS, default=prompts.DEFAULT_PROJECT_LAYOUT)
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--num-ctx", type=int, default=4096, help="fixed context window for every model (default 4096)")
    parser.add_argument("--num-predict", type=int, default=NUM_PREDICT,
                        help=f"generation budget per request (default {NUM_PREDICT}); part of the resume fingerprint")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--think", action="store_true", help="enable thinking on models that support it (default off)")
    parser.add_argument("--ids", nargs="+", help="only these query ids")
    parser.add_argument("--limit", type=int, help="only the first N queries")
    parser.add_argument("--rerun-stale", action="store_true", help="redo ids whose finished record used other settings")
    parser.add_argument("--keep-loaded", action="store_true", help="don't unload each model when it finishes")
    parser.add_argument("--no-memory", action="store_true", help="disable GPU/process memory sampling")
    parser.add_argument("--sample-interval", type=float, default=0.25, help="memory sampling interval in seconds")
    parser.add_argument("--queries", type=Path, default=QUERIES_PATH)
    parser.add_argument("--contexts", type=Path, default=CONTEXTS_PATH)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--dry-run", action="store_true", help="show the plan and an example request; no Ollama calls")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    try:
        queries = load_queries(args.queries)
        contexts = latest_by_id(record for _, record in read_jsonl(args.contexts))
    except (OSError, ValueError) as exc:
        print(exc)
        return 2
    if args.ids:
        wanted = set(args.ids)
        queries = [query for query in queries if query["id"] in wanted]
    if args.limit:
        queries = queries[: args.limit]
    if not queries:
        print("No queries to run: fill in eval_queries.jsonl, then run build_context.py.")
        return 1
    if not contexts:
        print(f"No frozen contexts in {args.contexts}: run build_context.py first.")
        return 1

    jobs, problems = build_jobs(queries, contexts, args.variants, args.project_layout)
    if problems:
        print("Cannot run:")
        for problem in problems:
            print(f"  {problem}")
        return 2

    options = {"temperature": TEMPERATURE, "num_predict": args.num_predict, "seed": args.seed, "num_ctx": args.num_ctx}
    if args.dry_run:
        return dry_run(args, jobs, options)
    try:
        return run(args, jobs, options)
    except OllamaUnavailable as exc:
        print(f"ERROR: {exc}\nStart Ollama and re-run; finished records are kept.")
        return 3
    except KeyboardInterrupt:
        print("\nInterrupted. Finished records are saved; re-run the same command to resume.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
