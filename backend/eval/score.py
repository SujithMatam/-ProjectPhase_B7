"""
Rubric scoring for run_models.py results.

Two scoring sources, stored apart and reported apart -- never averaged together:

  manual   python score.py manual results/<model>_<variant>.jsonl [--rater NAME]
           -> scores/manual/<model>_<variant>.jsonl                score_source="manual"
  judge    python score.py judge results/<model>_<variant>.jsonl --judge-model TAG
           -> scores/judge/<judge-tag>/<model>_<variant>.jsonl     score_source="llm_judge"
  summary  python score.py summary [--results-dir DIR ...] [--by domain|procedure|answerability]
           performance table from the results dir(s), then one table per scoring source

Scores for a results file outside results/ go one level deeper, under that
directory's path relative to backend/eval/, e.g.
results_medgemma_2048/x.jsonl -> scores/judge/<judge-tag>/results_medgemma_2048/x.jsonl,
so files with the same name in two results dirs never share a score file.
Every table has a num_predict column (the generation budget of the results).

Rubric (one response at a time, judged against the FROZEN retrieved context):
  grounded               0-2   2 = every clinical statement is supported by the
                               retrieved context; 1 = mostly supported, with a
                               minor unsupported detail; 0 = the core answer is
                               unsupported by, or contradicts, the context
  claims                 list  every distinct factual/clinical claim in the
                               answer (instructions, numbers, durations,
                               timelines, thresholds, diagnoses, "this is
                               normal" reassurances), each as {"text", "label"}:
                                 supported   stated in the frozen context with
                                             the same meaning
                                 embellished in the context, but with added
                                             specifics (numbers, durations) or
                                             applied to a different purpose
                                 unsupported not in the context at all
                               A bare "I don't have that information, ask your
                               care team" is not a claim (unanswerable_handling
                               covers it). The list may be empty. The three
                               labels are counted and reported separately and
                               never summed.
  unanswerable_handling  correct | invented | n/a
                               answerability partial/none: "correct" if the
                               response says the missing part isn't covered (or
                               defers it to the care team) instead of supplying
                               it; "invented" if it fills the gap with
                               unsupported content. Always n/a for "full":
                               if the judge answers correct/invented there,
                               its value is kept as judge_raw_handling and
                               the field is set to n/a (also applied when
                               reading records written before this rule).
  followed_format        bool  meets prompts.FORMAT_EXPECTATIONS[variant]

Only the VISIBLE answer is scored: run_models.py already moves any reasoning
trace (e.g. MedGemma's <unused94> block) into reasoning_trace, and score.py
runs the same split again on `response` as a guard, so trace text can never
reach a rater or the judge. A response whose trace was cut off before any
answer is shown as "(no visible answer)".

Each score stores the sha256 of the exact visible answer it scored. If a
result is re-run and its answer changes, the old score is reported as stale
and excluded from the summary. Results written by an older HARNESS_VERSION are
skipped (re-run them). Scores written under an older SCORE_VERSION (the rubric
itself changed) are excluded from the summary and re-scored by manual/judge.

The judge mode calls a local Ollama model (never pulls). Everything else is
offline. No backend application code is imported.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import prompts
from common import (
    CONTEXTS_PATH,
    EVAL_DIR,
    HARNESS_VERSION,
    QUERIES_PATH,
    RESULTS_DIR,
    SCORES_DIR,
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

# Version of the score-record schema/rubric (results are versioned separately by
# HARNESS_VERSION). v2: a labelled claims list replaces the unsupported_claims count.
SCORE_VERSION = "2"

SCORE_FIELDS = ("grounded", "claims", "unanswerable_handling", "followed_format")
CLAIM_LABELS = ("supported", "embellished", "unsupported")
UNANSWERABLE_CHOICES = ("correct", "invented", "n/a")
RUNS_LOG_NAME = "_runs.jsonl"

ANSWERABILITY_MEANING = {
    "full": "the retrieved context contains everything needed to answer",
    "partial": "the retrieved context covers only part of the question",
    "none": "the retrieved context does not contain the answer",
}


# ============================================================================
# Shared
# ============================================================================

FULL_HANDLING_PROBLEM = "unanswerable_handling must be 'n/a' when answerability is 'full'"


def normalize_full_handling(fields: Dict[str, Any], answerability: str) -> Optional[str]:
    """For a "full" question the rubric fixes unanswerable_handling to "n/a" (manual mode sets it
    automatically). If a judge answered "correct"/"invented" there anyway, set it to "n/a" in place
    and return the judge's raw value (stored as judge_raw_handling); otherwise return None."""
    raw = fields.get("unanswerable_handling")
    if answerability == "full" and raw in ("correct", "invented"):
        fields["unanswerable_handling"] = "n/a"
        return raw
    return None


def normalized_judge_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Apply normalize_full_handling to a stored judge record, for records written before the rule
    existed. Only that one problem is dropped; a record with any other problem stays invalid."""
    fields = {"unanswerable_handling": record.get("unanswerable_handling")}
    raw = normalize_full_handling(fields, record.get("answerability"))
    if raw is None:
        return record
    remaining = [p for p in (record.get("problems") or []) if p != FULL_HANDLING_PROBLEM]
    return {**record, "unanswerable_handling": "n/a", "judge_raw_handling": raw,
            "valid": not remaining, "problems": remaining or None}


def validate_fields(fields: Dict[str, Any], answerability: str) -> List[str]:
    problems = []
    grounded = fields.get("grounded")
    if not (isinstance(grounded, int) and not isinstance(grounded, bool) and 0 <= grounded <= 2):
        problems.append("grounded must be an integer 0-2")
    claims = fields.get("claims")
    if not isinstance(claims, list):
        problems.append("claims must be a list")
    else:
        for n, claim in enumerate(claims, start=1):
            if not (isinstance(claim, dict) and isinstance(claim.get("text"), str) and claim["text"].strip()):
                problems.append(f"claim {n} must have non-empty text")
            elif claim.get("label") not in CLAIM_LABELS:
                problems.append(f"claim {n} label must be one of {CLAIM_LABELS}")
    handling = fields.get("unanswerable_handling")
    if handling not in UNANSWERABLE_CHOICES:
        problems.append(f"unanswerable_handling must be one of {UNANSWERABLE_CHOICES}")
    elif answerability == "full" and handling != "n/a":
        problems.append(FULL_HANDLING_PROBLEM)
    elif answerability in ("partial", "none") and handling == "n/a":
        problems.append("unanswerable_handling must be 'correct' or 'invented' when answerability is partial/none")
    if not isinstance(fields.get("followed_format"), bool):
        problems.append("followed_format must be true or false")
    return problems


def load_items(results: Path, queries_path: Path, contexts_path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Finished results joined with their query (reference answer) and frozen context."""
    latest = latest_by_id(record for _, record in read_jsonl(results, allow_partial_tail=True))
    queries = {query["id"]: query for query in load_queries(queries_path)}
    contexts = latest_by_id(record for _, record in read_jsonl(contexts_path))
    items, skipped = [], []
    for qid, result in latest.items():
        if result.get("status") != "ok":
            continue
        query = queries.get(qid)
        if result.get("harness_version") != HARNESS_VERSION:
            skipped.append(f"{qid}: produced by harness v{result.get('harness_version')} "
                           f"(current v{HARNESS_VERSION}) -- re-run run_models.py")
        elif query is None:
            skipped.append(f"{qid}: no longer in eval_queries.jsonl")
        elif result.get("query_sha256") != query_fingerprint(query):
            skipped.append(f"{qid}: query changed since this result was produced")
        else:
            items.append({"result": result, "query": query, "context": contexts.get(qid) or {}})
    return items, skipped


def visible_answer(result: Dict[str, Any]) -> str:
    """The text that gets scored: the response with any reasoning trace removed."""
    return split_reasoning(result.get("response") or "")["visible"]


def response_sha(result: Dict[str, Any]) -> str:
    return sha256_text(visible_answer(result))


def results_dir_key(results_dir: Path) -> str:
    """A results directory's path relative to backend/eval/ (e.g. "results", "results_medgemma_2048")."""
    resolved = results_dir.resolve()
    try:
        return resolved.relative_to(EVAL_DIR).as_posix()
    except ValueError:
        return resolved.as_posix()


DEFAULT_RESULTS_KEY = results_dir_key(RESULTS_DIR)


def score_subpath(results: Path) -> Path:
    """Where a results file's scores go, relative to scores/manual/ or scores/judge/<judge>/.

    results/ keeps the flat layout; any other results dir gets its own subdirectory, so two
    dirs holding the same <model>_<variant>.jsonl never write to one score file."""
    key = results_dir_key(results.parent)
    return Path(results.name) if key == DEFAULT_RESULTS_KEY else Path(key) / results.name


def num_predict_of(result: Dict[str, Any]) -> Any:
    return (result.get("options") or {}).get("num_predict")


def base_record(item: Dict[str, Any], results: Path, source: str) -> Dict[str, Any]:
    result, query = item["result"], item["query"]
    return {
        "id": result["id"],
        "results_file": results.name,
        "results_dir": results_dir_key(results.parent),
        "num_predict": num_predict_of(result),
        "model": result.get("model"),
        "variant": result.get("variant"),
        "domain": query["domain"],
        "procedure": query["procedure"],
        "answerability": query["answerability"],
        "response_sha256": response_sha(result),
        "score_source": source,
    }


def _context_lines(context: Dict[str, Any]) -> str:
    chunks = context.get("chunks") or []
    if not chunks:
        return "(no context was retrieved)"
    return "\n".join(f"[{chunk['rank']}] {chunk['topic']}: {chunk['content']}" for chunk in chunks)


def claim_counts(claims: List[Dict[str, Any]]) -> Dict[str, int]:
    """Number of claims per label; the labels are kept apart, never summed."""
    return {label: sum(1 for claim in claims if claim.get("label") == label) for label in CLAIM_LABELS}


def _approx_sentences(text: str) -> int:
    found = re.findall(r"[^.!?]+[.!?]+(?=\s|$)", text.strip())
    return len(found) or (1 if text.strip() else 0)


# ============================================================================
# Manual entry
# ============================================================================

class _Skip(Exception):
    pass


class _Quit(Exception):
    pass


def _ask(prompt: str, parse):
    while True:
        raw = input(prompt).strip()
        if raw.lower() == "s":
            raise _Skip
        if raw.lower() == "q":
            raise _Quit
        try:
            return parse(raw)
        except ValueError as exc:
            print(f"    {exc}")


def _parse_grounded(raw: str) -> int:
    if raw in ("0", "1", "2"):
        return int(raw)
    raise ValueError("enter 0, 1 or 2")


def _parse_claim_text(raw: str) -> str:
    return raw  # empty means "no more claims"


def _parse_claim_label(raw: str) -> str:
    # "s" alone is the skip command, so labels are entered as su / em / un (or in full).
    value = raw.lower()
    for label in CLAIM_LABELS:
        if len(value) >= 2 and label.startswith(value):
            return label
    if value in ("e", "u"):
        return {"e": "embellished", "u": "unsupported"}[value]
    raise ValueError("enter su (supported), em (embellished) or un (unsupported)")


def _ask_claims() -> List[Dict[str, str]]:
    print("claims: enter each factual/clinical claim in the answer, then its label.")
    print("  su = supported (in the context, same meaning)")
    print("  em = embellished (in the context, but with added numbers/durations or used for another purpose)")
    print("  un = unsupported (not in the context at all)")
    print("  Leave the claim text blank to finish (blank at once = no claims).")
    claims: List[Dict[str, str]] = []
    while True:
        text = _ask(f"  claim {len(claims) + 1} text: ", _parse_claim_text)
        if not text:
            break
        label = _ask(f"  claim {len(claims) + 1} label (su/em/un): ", _parse_claim_label)
        claims.append({"text": text, "label": label})
    counts = claim_counts(claims)
    print("  recorded: " + ", ".join(f"{counts[label]} {label}" for label in CLAIM_LABELS))
    return claims


def _parse_handling(raw: str) -> str:
    value = {"c": "correct", "i": "invented"}.get(raw.lower(), raw.lower())
    if value in ("correct", "invented"):
        return value
    raise ValueError("enter correct (c) or invented (i)")


def _parse_bool(raw: str) -> bool:
    if raw.lower() in ("y", "yes", "true", "1"):
        return True
    if raw.lower() in ("n", "no", "false", "0"):
        return False
    raise ValueError("enter y or n")


def _show(item: Dict[str, Any], index: int, total: int) -> None:
    result, query, context = item["result"], item["query"], item["context"]
    response = visible_answer(result)
    print("=" * 78)
    print(f"[{index}/{total}] {query['id']}   model={result.get('model')}   variant={result.get('variant')}")
    print(f"domain={query['domain']}   procedure={query['procedure']}   answerability={query['answerability']}")
    print(f"\nQUERY:\n  {query['query']}")
    print(f"\nREFERENCE ANSWER:\n  {query.get('reference_answer') or '(none given)'}")
    print(f"\nRETRIEVED CONTEXT ({len(context.get('chunks') or [])} chunk(s), path={context.get('retrieval_path')}):")
    print(_context_lines(context))
    print(f"\nFORMAT EXPECTATION: {prompts.FORMAT_EXPECTATIONS.get(result.get('variant'), '(unknown variant)')}")
    notes = []
    if result.get("has_reasoning_trace"):
        notes.append("the model also produced a reasoning trace, hidden here and not scored")
    if result.get("hit_token_limit"):
        notes.append("generation hit the token limit")
    if notes:
        print(f"\nNOTE: {'; '.join(notes)}.")
    shown = response or "(no visible answer)"
    print(f"\nRESPONSE (~{_approx_sentences(response)} sentence(s), {len(response.split())} words):\n{shown}\n")


def cmd_manual(args: argparse.Namespace) -> int:
    items, skipped = load_items(args.results, args.queries, args.contexts)
    for note in skipped:
        print(f"skip {note}")
    out_path = args.scores_dir / "manual" / score_subpath(args.results)
    repair_partial_tail(out_path)
    existing = latest_by_id(record for _, record in read_jsonl(out_path))
    todo = [
        item for item in items
        if args.rescore
        or existing.get(item["result"]["id"], {}).get("response_sha256") != response_sha(item["result"])
        or existing.get(item["result"]["id"], {}).get("score_version") != SCORE_VERSION
    ]
    rater = args.rater or os.getenv("USERNAME") or os.getenv("USER") or "manual"
    print(f"{len(todo)} response(s) to score, {len(items) - len(todo)} already scored.  "
          f"Enter s to skip one, q to quit.  Writing to {out_path}")
    for index, item in enumerate(todo, start=1):
        _show(item, index, len(todo))
        answerability = item["query"]["answerability"]
        try:
            fields: Dict[str, Any] = {
                "grounded": _ask("grounded (0-2): ", _parse_grounded),
                "claims": _ask_claims(),
            }
            if answerability == "full":
                fields["unanswerable_handling"] = "n/a"
                print("unanswerable_handling: n/a (answerability is full)")
            else:
                fields["unanswerable_handling"] = _ask("unanswerable_handling (correct/invented): ", _parse_handling)
            fields["followed_format"] = _ask("followed_format (y/n): ", _parse_bool)
            notes = input("notes (optional): ").strip()
        except _Skip:
            print("  skipped")
            continue
        except (_Quit, EOFError):
            print("\nStopped; scores entered so far are saved.")
            break
        problems = validate_fields(fields, answerability)
        if problems:  # the prompts above already enforce these; defensive only
            print(f"  not saved: {problems}")
            continue
        append_jsonl(out_path, {
            **base_record(item, args.results, "manual"),
            "scorer": rater,
            **fields,
            "notes": notes or None,
            "scored_at": utc_now(),
            "harness_version": HARNESS_VERSION,
            "score_version": SCORE_VERSION,
        })
    return 0


# ============================================================================
# LLM judge (optional)
# ============================================================================

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "rationale": {"type": "string"},
        "grounded": {"type": "integer", "enum": [0, 1, 2]},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "label": {"type": "string", "enum": list(CLAIM_LABELS)},
                },
                "required": ["text", "label"],
            },
        },
        "unanswerable_handling": {"type": "string", "enum": list(UNANSWERABLE_CHOICES)},
        "followed_format": {"type": "boolean"},
    },
    "required": ["rationale", "grounded", "claims", "unanswerable_handling", "followed_format"],
}

JUDGE_SYSTEM = """You are grading one answer written by a patient-education assistant for orthopedic post-operative recovery.

Judge the answer ONLY against the RETRIEVED CONTEXT. The REFERENCE ANSWER shows what a good answer should cover; it is not evidence, and neither is general medical knowledge.

Rubric:
- rationale: one or two sentences explaining the scores; name any embellished or unsupported claims.
- grounded (0-2): 2 = every clinical statement is supported by the retrieved context; 1 = mostly supported, with a minor unsupported detail; 0 = the core answer is unsupported by, or contradicts, the context.
- claims: list every distinct factual or clinical claim in the answer (instructions, numbers, durations, timelines, thresholds, diagnoses, reassurances such as "this is normal"), each with a short "text" and one "label":
  - "supported": stated in the retrieved context with the same meaning.
  - "embellished": in the retrieved context, but the answer adds specifics the context does not give (numbers, durations, frequencies) or applies it to a different purpose (e.g. context advice for swelling given as advice for pain).
  - "unsupported": not in the retrieved context at all.
  A bare statement that the information is unavailable, or a plain referral to the care team, is not a claim. Use an empty list if the answer makes no claims.
- unanswerable_handling: "n/a" if ANSWERABILITY is "full". Otherwise "correct" if the answer says the missing information is not available or defers it to the care team instead of supplying it, or "invented" if it fills the gap with unsupported content.
- followed_format (true/false): whether the answer meets the FORMAT EXPECTATION.

Respond with JSON only."""


def build_judge_messages(item: Dict[str, Any]) -> List[Dict[str, str]]:
    result, query, context = item["result"], item["query"], item["context"]
    user = (
        f"QUESTION:\n{query['query']}\n\n"
        f"ANSWERABILITY: {query['answerability']} ({ANSWERABILITY_MEANING[query['answerability']]})\n\n"
        f"RETRIEVED CONTEXT:\n{_context_lines(context)}\n\n"
        f"REFERENCE ANSWER:\n{query.get('reference_answer') or '(none given)'}\n\n"
        f"FORMAT EXPECTATION:\n{prompts.FORMAT_EXPECTATIONS.get(result.get('variant'), '(none)')}\n\n"
        f"ANSWER TO GRADE:\n{visible_answer(result) or '(no answer was given)'}"
    )
    return [{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": user}]


def cmd_judge(args: argparse.Namespace) -> int:
    # Stdlib-only HTTP helpers from this harness; still no backend code.
    from run_models import OllamaUnavailable, http_error_message, model_info, ollama_json

    items, skipped = load_items(args.results, args.queries, args.contexts)
    for note in skipped:
        print(f"skip {note}")
    evaluated = {item["result"].get("model") for item in items}
    if args.judge_model in evaluated and not args.allow_self_judge:
        print(f"Refusing: {args.judge_model} would grade its own answers (self-preference bias). "
              "Use another judge, or --allow-self-judge.")
        return 2

    base_url = args.ollama_url.rstrip("/")
    try:
        info = model_info(base_url, args.judge_model)
    except OllamaUnavailable as exc:
        print(f"ERROR: {exc}")
        return 3
    if info is None:
        print(f"Judge model {args.judge_model} is not installed (never pulled automatically).")
        return 1

    out_path = args.scores_dir / "judge" / safe_name(args.judge_model) / score_subpath(args.results)
    repair_partial_tail(out_path)
    existing = latest_by_id(record for _, record in read_jsonl(out_path))
    options = {"temperature": 0, "seed": args.seed, "num_predict": args.num_predict, "num_ctx": args.num_ctx}
    if args.num_gpu is not None:
        options["num_gpu"] = args.num_gpu
    think = False if "thinking" in info["capabilities"] else None
    print(f"Judging {len(items)} response(s) with {args.judge_model}; writing to {out_path}")

    for index, item in enumerate(items, start=1):
        messages = build_judge_messages(item)
        judge_prompt_sha = sha256_json({"messages": messages, "schema": JUDGE_SCHEMA, "options": options})
        previous = existing.get(item["result"]["id"])
        previous = normalized_judge_record(previous) if previous else None
        if (
            previous and not args.rescore and previous.get("valid")
            and previous.get("response_sha256") == response_sha(item["result"])
            and previous.get("judge_prompt_sha256") == judge_prompt_sha
            and previous.get("score_version") == SCORE_VERSION
        ):
            continue
        payload: Dict[str, Any] = {
            "model": args.judge_model,
            "messages": messages,
            "stream": False,
            "format": JUDGE_SCHEMA,
            "options": options,
            "keep_alive": "30m",
        }
        if think is not None:
            payload["think"] = think

        raw: Optional[str] = None
        parsed: Any = None
        problems: List[str] = []
        try:
            reply = ollama_json(f"{base_url}/api/chat", payload)
            raw = (reply.get("message") or {}).get("content", "")
            parsed = json.loads(raw)
        except OllamaUnavailable as exc:
            print(f"ERROR: {exc}")
            return 3
        except urllib.error.HTTPError as exc:
            problems.append(http_error_message(exc))
        except json.JSONDecodeError:
            problems.append("judge output is not valid JSON")
        if not problems and not isinstance(parsed, dict):
            problems.append("judge output is not a JSON object")
        fields = {field: parsed.get(field) for field in SCORE_FIELDS} if isinstance(parsed, dict) else {}
        raw_handling = normalize_full_handling(fields, item["query"]["answerability"])
        if not problems:
            problems = validate_fields(fields, item["query"]["answerability"])

        append_jsonl(out_path, {
            **base_record(item, args.results, "llm_judge"),
            "judge_model": args.judge_model,
            "judge_digest": info["digest"],
            "judge_options": options,
            "judge_prompt_sha256": judge_prompt_sha,
            **{field: fields.get(field) for field in SCORE_FIELDS},
            "judge_raw_handling": raw_handling,
            "rationale": parsed.get("rationale") if isinstance(parsed, dict) else None,
            "valid": not problems,
            "problems": problems or None,
            "raw_output": raw if problems else None,
            "scored_at": utc_now(),
            "harness_version": HARNESS_VERSION,
            "score_version": SCORE_VERSION,
        })
        status = "ok" if not problems else f"INVALID ({'; '.join(problems)})"
        print(f"  [{index}/{len(items)}] {item['result']['id']}: {status}")
    return 0


# ============================================================================
# Summary
# ============================================================================

def _table(headers: List[str], rows: List[List[Any]]) -> None:
    cells = [[("-" if value is None else str(value)) for value in row] for row in rows]
    widths = [max([len(header)] + [len(row[i]) for row in cells]) for i, header in enumerate(headers)]
    print("  " + "  ".join(header.ljust(widths[i]) for i, header in enumerate(headers)))
    print("  " + "  ".join("-" * width for width in widths))
    for row in cells:
        print("  " + "  ".join(value.ljust(widths[i]) for i, value in enumerate(row)))


def _median(values: List[float]) -> Optional[float]:
    values = [value for value in values if value is not None]
    return round(statistics.median(values), 2) if values else None


def _max(values: List[Any]) -> Any:
    values = [value for value in values if value is not None]
    return max(values) if values else None


def _cold_starts(results_dir: Path) -> Dict[str, Any]:
    """Latest cold_start_seconds per model from _runs.jsonl (reported separately, never in latency stats)."""
    cold: Dict[str, Any] = {}
    for _, event in read_jsonl(results_dir / RUNS_LOG_NAME, allow_partial_tail=True):
        if event.get("event") == "model_loaded" and event.get("harness_version") == HARNESS_VERSION:
            cold[event.get("model")] = event.get("cold_start_seconds")
    return cold


def _budget(records: List[Dict[str, Any]]) -> Any:
    """num_predict of a set of results; several values are joined with '/' so a mix is visible."""
    values = sorted({num_predict_of(r) for r in records if num_predict_of(r) is not None})
    return "/".join(str(v) for v in values) or None


# current: (results dir key, results file name) -> {id: latest result record}
Current = Dict[Tuple[str, str], Dict[str, Dict[str, Any]]]


def _print_performance(current: Current, results_dirs: List[Path]) -> None:
    multi = len(results_dirs) > 1
    print(f"PERFORMANCE (from {', '.join(results_dir_key(d) + '/' for d in results_dirs)}; "
          f"latest record per id, harness v{HARNESS_VERSION} only)")
    cold = {results_dir_key(d): _cold_starts(d) for d in results_dirs}
    rows = []
    old_version = 0
    for (dir_key, name), records in current.items():
        values = [r for r in records.values() if r.get("harness_version") == HARNESS_VERSION]
        old_version += len(records) - len(values)
        ok = [r for r in values if r.get("status") == "ok"]
        latency = [r.get("latency_s") or {} for r in ok]
        timings = [r.get("ollama_timings") or {} for r in ok]
        memory = [r.get("memory") or {} for r in ok]
        vram_share = []
        for entry in memory:
            loaded = entry.get("loaded_model") or {}
            if loaded.get("size_bytes"):
                vram_share.append(round(100 * (loaded.get("size_vram_bytes") or 0) / loaded["size_bytes"]))
        model = values[0].get("model") if values else name
        rows.append([
            *([dir_key] if multi else []),
            model, values[0].get("variant") if values else "", _budget(values),
            len(ok), len(values) - len(ok), sum(1 for r in ok if r.get("empty_response")),
            sum(1 for r in ok if r.get("has_reasoning_trace")), sum(1 for r in ok if r.get("hit_token_limit")),
            _median([r.get("time_to_first_visible_token") for r in ok]), _median([l.get("total") for l in latency]),
            _median([r.get("visible_tokens") for r in ok]), _median([r.get("raw_tokens") for r in ok]),
            _median([t.get("eval_tokens_per_s") for t in timings]),
            _max([m.get("gpu_used_peak_mib") for m in memory]), _max([m.get("ollama_process_peak_mib") for m in memory]),
            f"{min(vram_share)}%" if vram_share else None,
            cold[dir_key].get(model),
        ])
    _table([*(["results dir"] if multi else []), "model", "variant", "num_predict", "ok", "err", "no answer", "trace", "hit limit", "p50 first visible s",
            "p50 total s", "p50 visible tok", "p50 raw tok", "p50 tok/s", "peak GPU MiB", "peak ollama MiB",
            "min on GPU", "cold start s (excluded)"], rows)
    print("  (GPU MiB is system-wide; 'min on GPU' is the lowest share of the model in VRAM per /api/ps;")
    print("   cold start = discarded warm-up request, from _runs.jsonl, not part of any latency column)")
    if old_version:
        print(f"  excluded: {old_version} record(s) from an older harness version (re-run them)")
    print()


def _score_files(root: Path) -> List[Tuple[str, Path]]:
    """(results dir key, score file) under scores/manual/ or scores/judge/<judge>/ (see score_subpath)."""
    found = []
    for path in sorted(root.rglob("*.jsonl")):
        sub = path.parent.relative_to(root).as_posix()
        found.append((DEFAULT_RESULTS_KEY if sub == "." else sub, path))
    return found


def _print_scores(title: str, files: List[Tuple[str, Path]], current: Current,
                  by: Optional[str], is_judge: bool, multi: bool) -> None:
    print(title)
    loaded_dirs = {dir_key for dir_key, _ in current}
    other_dirs = sum(1 for dir_key, _ in files if dir_key not in loaded_dirs)
    files = [(dir_key, path) for dir_key, path in files if dir_key in loaded_dirs]
    if not files:
        print("  (none)" + (f"; {other_dirs} score file(s) belong to results dirs not listed" if other_dirs else "") + "\n")
        return
    groups: Dict[Tuple, List[Dict[str, Any]]] = {}
    stale = old_rubric = invalid = 0
    for dir_key, path in files:
        results = current.get((dir_key, path.name), {})
        for record in latest_by_id(r for _, r in read_jsonl(path, allow_partial_tail=True)).values():
            if is_judge:
                record = normalized_judge_record(record)
            result = results.get(str(record.get("id")))
            if (
                result is None
                or result.get("harness_version") != HARNESS_VERSION
                or response_sha(result) != record.get("response_sha256")
            ):
                stale += 1
                continue
            if record.get("score_version") != SCORE_VERSION:
                old_rubric += 1
                continue
            if is_judge and not record.get("valid"):
                invalid += 1
                continue
            if validate_fields({f: record.get(f) for f in SCORE_FIELDS}, record.get("answerability")):
                invalid += 1
                continue
            key = (((dir_key,) if multi else ()) + (record.get("model"), record.get("variant"),
                   num_predict_of(result)) + ((record.get(by),) if by else ()))
            groups.setdefault(key, []).append(record)
    rows = []
    for key, records in sorted(groups.items(), key=lambda pair: tuple(str(part) for part in pair[0])):
        gated = [r for r in records if r["answerability"] in ("partial", "none")]
        counts = [claim_counts(r["claims"]) for r in records]
        # One column per claim label: total, then mean per response. Never summed across labels.
        per_label = [
            f"{sum(c[label] for c in counts)} ({statistics.mean(c[label] for c in counts):.2f})"
            for label in CLAIM_LABELS
        ]
        rows.append([
            *key, len(records),
            round(statistics.mean(r["grounded"] for r in records), 2),
            *per_label,
            f"{round(100 * sum(r['followed_format'] for r in records) / len(records))}%",
            f"{sum(r['unanswerable_handling'] == 'correct' for r in gated)}/{len(gated)}",
            sum(r["unanswerable_handling"] == "invented" for r in gated),
        ])
    headers = (["results dir"] if multi else []) + ["model", "variant", "num_predict"] + ([by] if by else []) + [
        "n", "grounded (0-2)", *CLAIM_LABELS, "format ok", "unanswerable correct", "invented"]
    if rows:
        _table(headers, rows)
        print("  (claim columns: total claims with that label (mean per response); the three are never summed)")
    else:
        print("  (no current, valid scores)")
    print(f"  excluded: {stale} stale (response changed or missing), "
          f"{old_rubric} from an older rubric (score v{SCORE_VERSION} is current; re-score them), {invalid} invalid"
          + (f"; {other_dirs} score file(s) belong to results dirs not listed" if other_dirs else "") + "\n")


def cmd_summary(args: argparse.Namespace) -> int:
    results_dirs = list(dict.fromkeys(args.results_dir))
    current: Current = {}
    for results_dir in results_dirs:
        result_files = sorted(p for p in results_dir.glob("*.jsonl") if p.name != RUNS_LOG_NAME)
        if not result_files:
            print(f"No results in {results_dir} yet.")
        for p in result_files:
            current[(results_dir_key(results_dir), p.name)] = latest_by_id(
                r for _, r in read_jsonl(p, allow_partial_tail=True))
    if not current:
        return 0
    multi = len(results_dirs) > 1
    _print_performance(current, results_dirs)
    _print_scores("MANUAL SCORES  (score_source=manual)",
                  _score_files(args.scores_dir / "manual"), current, args.by, is_judge=False, multi=multi)
    judge_dirs = sorted(p for p in (args.scores_dir / "judge").glob("*") if p.is_dir())
    if not judge_dirs:
        print("LLM-JUDGE SCORES  (score_source=llm_judge)\n  (none)\n")
    for judge_dir in judge_dirs:
        _print_scores(f"LLM-JUDGE SCORES  (score_source=llm_judge, judge={judge_dir.name})",
                      _score_files(judge_dir), current, args.by, is_judge=True, multi=multi)
    return 0


# ============================================================================
# CLI
# ============================================================================

def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score run_models.py results (manual or LLM judge).")
    parser.add_argument("--queries", type=Path, default=QUERIES_PATH)
    parser.add_argument("--contexts", type=Path, default=CONTEXTS_PATH)
    parser.add_argument("--scores-dir", type=Path, default=SCORES_DIR)
    sub = parser.add_subparsers(dest="command", required=True)

    manual = sub.add_parser("manual", help="score responses interactively")
    manual.add_argument("results", type=Path, help="a results/<model>_<variant>.jsonl file")
    manual.add_argument("--rater", help="name recorded with each score (default: OS user name)")
    manual.add_argument("--rescore", action="store_true", help="re-score responses that already have a score")

    judge = sub.add_parser("judge", help="score responses with a local Ollama judge model")
    judge.add_argument("results", type=Path)
    judge.add_argument("--judge-model", required=True)
    judge.add_argument("--ollama-url", default=os.getenv("EVAL_OLLAMA_URL", "http://127.0.0.1:11434"))
    judge.add_argument("--num-ctx", type=int, default=8192)
    judge.add_argument("--num-predict", type=int, default=512)
    judge.add_argument("--num-gpu", type=int,
                       help="layers to offload to the GPU (Ollama num_gpu), e.g. 99 for all; overrides Ollama's "
                            "own fit, which keeps ~1 GiB VRAM free. Default: let Ollama decide")
    judge.add_argument("--seed", type=int, default=0)
    judge.add_argument("--rescore", action="store_true")
    judge.add_argument("--allow-self-judge", action="store_true")

    summary = sub.add_parser("summary", help="performance + score tables (manual and judge kept separate)")
    summary.add_argument("--results-dir", type=Path, nargs="+", default=[RESULTS_DIR],
                         help="one or more results dirs, read together (default: results/)")
    summary.add_argument("--by", choices=("domain", "procedure", "answerability"))
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    try:
        if args.command == "manual":
            return cmd_manual(args)
        if args.command == "judge":
            return cmd_judge(args)
        return cmd_summary(args)
    except (OSError, ValueError) as exc:
        print(exc)
        return 2
    except KeyboardInterrupt:
        print("\nInterrupted; scores saved so far are kept.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
