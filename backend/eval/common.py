"""Shared helpers for the local-LLM RAG comparison harness (stdlib only).

Nothing in this module imports backend application code.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

EVAL_DIR = Path(__file__).resolve().parent
BACKEND_DIR = EVAL_DIR.parent
QUERIES_PATH = EVAL_DIR / "eval_queries.jsonl"
CONTEXTS_PATH = EVAL_DIR / "eval_contexts.jsonl"
RESULTS_DIR = EVAL_DIR / "results"
SCORES_DIR = EVAL_DIR / "scores"

DOMAINS = ("recovery", "pain", "rehab")
PROCEDURES = ("TKA", "THA")
ANSWERABILITY = ("full", "partial", "none")
QUERY_FIELDS = ("id", "domain", "procedure", "postop_day", "answerability", "query", "reference_answer")
OPTIONAL_QUERY_FIELDS = ("affected_limb", "reference_passages")

# v2: num_predict 600, warm-up request, reasoning traces split out of `response`.
# Results written by an older version are treated as stale by run_models.py
# and skipped by score.py.
HARNESS_VERSION = "2"

# Wrappers some models put around a reasoning trace inside the answer text
# (name, start marker, end marker). Matched case-insensitively. MedGemma
# (Gemma 3 based) emits "<unused94>thought ... <unused95>".
REASONING_MARKERS: Tuple[Tuple[str, str, str], ...] = (
    ("medgemma_unused94", "<unused94>", "<unused95>"),
    ("think_tag", "<think>", "</think>"),
    ("thinking_tag", "<thinking>", "</thinking>"),
    ("reasoning_tag", "<reasoning>", "</reasoning>"),
    ("thought_markers", "<|begin_of_thought|>", "<|end_of_thought|>"),
    ("channel_analysis", "<|channel|>analysis", "<|end|>"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(obj: Any) -> str:
    return sha256_text(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def safe_name(value: str) -> str:
    """Filesystem-safe form of a model tag: 'medgemma1.5:4b-it-q8_0' -> 'medgemma1.5-4b-it-q8_0'."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "unnamed"


def split_reasoning(text: str) -> Dict[str, Any]:
    """Separate reasoning-trace blocks from the visible answer.

    Returns:
      visible        the answer text outside every trace block (stripped)
      visible_spans  (start, end) character spans of `text` that are visible
      trace          the trace blocks, markers included, joined by blank lines ("" if none)
      formats        marker names found, in order
      closed         False if a trace block was never closed (e.g. cut off by num_predict)

    An end marker that appears with no preceding start marker (some chat
    templates pre-fill the opening tag) makes everything up to it a trace.
    """
    text = text or ""
    lower = text.lower()
    spans: List[Tuple[int, int]] = []
    traces: List[str] = []
    formats: List[str] = []
    closed = True
    pos = 0

    orphan_end = None
    for name, start, end in REASONING_MARKERS:
        e = lower.find(end.lower())
        s = lower.find(start.lower())
        if e != -1 and (s == -1 or e < s) and (orphan_end is None or e < orphan_end[0]):
            orphan_end = (e, name, end)
    if orphan_end is not None:
        e, name, end = orphan_end
        traces.append(text[: e + len(end)])
        formats.append(f"{name}_orphan_end")
        pos = e + len(end)

    while pos < len(text):
        best = None
        for name, start, end in REASONING_MARKERS:
            i = lower.find(start.lower(), pos)
            if i != -1 and (best is None or i < best[0]):
                best = (i, name, start, end)
        if best is None:
            spans.append((pos, len(text)))
            break
        i, name, start, end = best
        if i > pos:
            spans.append((pos, i))
        j = lower.find(end.lower(), i + len(start))
        formats.append(name)
        if j == -1:
            traces.append(text[i:])
            closed = False
            break
        traces.append(text[i: j + len(end)])
        pos = j + len(end)

    visible = "".join(text[a:b] for a, b in spans).strip()
    return {
        "visible": visible,
        "visible_spans": spans,
        "trace": "\n\n".join(t.strip() for t in traces if t.strip()),
        "formats": formats,
        "closed": closed,
    }


def query_fingerprint(query: Dict[str, Any]) -> str:
    """Identifies the retrieval input; a context built from different query text is stale."""
    return sha256_json({"query": query["query"], "procedure": query["procedure"]})


def repair_partial_tail(path: Path) -> int:
    """Drop an incomplete final line left by an interrupted write. Returns bytes removed."""
    if not path.exists():
        return 0
    data = path.read_bytes()
    if not data or data.endswith(b"\n"):
        return 0
    cut = data.rfind(b"\n") + 1  # 0 when the only line is incomplete
    with open(path, "r+b") as handle:
        handle.truncate(cut)
    return len(data) - cut


def read_jsonl(path: Path, allow_partial_tail: bool = False) -> List[Tuple[int, Dict[str, Any]]]:
    """(line number, object) pairs. With allow_partial_tail, an unterminated last line is ignored."""
    if not path.exists():
        return []
    data = path.read_bytes()
    lines = data.split(b"\n")
    if allow_partial_tail and not data.endswith(b"\n"):
        lines = lines[:-1]
    records = []
    for lineno, raw in enumerate(lines, start=1):
        text = raw.decode("utf-8").strip()
        if not text:
            continue
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}:{lineno}: invalid JSON ({exc.msg})") from None
        if not isinstance(obj, dict):
            raise ValueError(f"{path.name}:{lineno}: expected a JSON object")
        records.append((lineno, obj))
    return records


def latest_by_id(records: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Index records by id; for append-only files the newest record per id wins."""
    latest: Dict[str, Dict[str, Any]] = {}
    for record in records:
        latest[str(record.get("id"))] = record
    return latest


def append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    """Append one record durably: a crash leaves at most one incomplete final line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def write_jsonl_atomic(path: Path, records: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def load_queries(path: Path = QUERIES_PATH) -> List[Dict[str, Any]]:
    """Load and validate eval queries. A row whose fields are all empty (the template) is ignored.

    postop_day is required on every row: there is deliberately no default, so a
    missing or null value is an error rather than a silent fallback.
    """
    queries: List[Dict[str, Any]] = []
    seen = set()
    errors = []
    for lineno, obj in read_jsonl(path):
        if all(obj.get(field) in ("", None) for field in QUERY_FIELDS):
            continue
        where = f"{path.name}:{lineno}"
        missing = [field for field in QUERY_FIELDS if field not in obj]
        if missing:
            hint = " (postop_day is required; no default is applied)" if "postop_day" in missing else ""
            errors.append(f"{where}: missing field(s) {missing}{hint}")
            continue
        day = obj["postop_day"]
        if not (isinstance(day, int) and not isinstance(day, bool) and day >= 0):
            errors.append(f"{where}: postop_day must be an integer >= 0 (no default is applied), got {day!r}")
        if "affected_limb" in obj and not (isinstance(obj["affected_limb"], str) and obj["affected_limb"].strip()):
            errors.append(f"{where}: affected_limb, when given, must be a non-empty string")
        passages = obj.get("reference_passages")
        if "reference_passages" in obj and not (
            isinstance(passages, list) and all(isinstance(p, str) and p.strip() for p in passages)
        ):
            errors.append(f"{where}: reference_passages, when given, must be a list of passage id strings")
        qid = str(obj["id"]).strip()
        if not qid:
            errors.append(f"{where}: empty id")
        elif qid in seen:
            errors.append(f"{where}: duplicate id {qid!r}")
        if obj["domain"] not in DOMAINS:
            errors.append(f"{where}: domain must be one of {DOMAINS}, got {obj['domain']!r}")
        if obj["procedure"] not in PROCEDURES:
            errors.append(f"{where}: procedure must be one of {PROCEDURES}, got {obj['procedure']!r}")
        if obj["answerability"] not in ANSWERABILITY:
            errors.append(f"{where}: answerability must be one of {ANSWERABILITY}, got {obj['answerability']!r}")
        if not isinstance(obj["query"], str) or not obj["query"].strip():
            errors.append(f"{where}: query must be a non-empty string")
        if not isinstance(obj["reference_answer"], str):
            errors.append(f"{where}: reference_answer must be a string (may be empty)")
        seen.add(qid)
        queries.append({**obj, "id": qid})
    if errors:
        raise ValueError("Invalid eval queries:\n  " + "\n  ".join(errors))
    return queries
