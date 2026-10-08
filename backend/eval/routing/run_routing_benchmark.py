"""
Routing benchmark runner.

    .venv/Scripts/python.exe eval/routing/run_routing_benchmark.py --label <name> [options]

Scores every case in eval/routing/cases.py twice:

  classifier     IntentClassifier.classify_detailed() on the bare message
                 (fresh LAMContext, no chat history, no recorded medications)
  orchestrator   LAMOrchestrator.process() on the same message for a brand-new
                 patient id (no history, no pending question), with
                 AgentRouter.dispatch stubbed so no agent or LLM runs.  The
                 orchestrator reads the patient record (the default template
                 lists Paracetamol and Enoxaparin), runs SafetyTriageEngine,
                 ScopeValidator, detect_applicable_intents and the
                 continuation hooks before the classifier, so its routing can
                 differ from the classifier's answer.

A prediction is correct when it is in the case's `acceptable` set.  For the
orchestrator two scores are kept: *lenient* (any dispatched agent is
acceptable; this is how eval/agents counts a misroute) and *strict* (every
dispatched agent is acceptable, i.e. the patient is not also sent to a
wrong agent).  Cases whose `orchestrator_expected` is emergency/out_of_scope
are scored on that outcome in the orchestrator run and skipped in the
classifier table.

Every miss is attributed to the rule that produced it (keyword order,
overbroad keyword, keyword gap, intake "I am" rule, semantic prototype pull,
semantic threshold -> keyword fallback -> default, patient-record
medication, ...), read from the classifier's own tables at run time.

Options:
  --label NAME        results go to eval/routing/results/NAME.json and .md,
                      and the markdown is copied to
                      eval/reports/<date>_routing-NAME.md
  --semantic-first    set intent_classifier.SEMANTIC_FIRST = True for the run
                      (the step-4 experiment flag; ignored with a warning when
                      the attribute does not exist)
  --no-orchestrator   classifier only
  --only SUBSTR       run only cases whose id, source or text contains SUBSTR
  --verbose           show the orchestrator's console output

Isolation: PATIENT_DATABASE_PATH points at a fresh temp sqlite file, every
SMTP*/DOCTOR_ALERT* variable is removed, and the RED doctor-alert hook is a
no-op, all before any backend module is imported.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1]
RESULTS_DIR = HERE / "results"
REPORTS_DIR = BACKEND / "eval" / "reports"

AGENT_ORDER = (
    "pain_symptoms", "recovery_progress", "rehabilitation", "wound_care", "medication",
    "daily_activity", "nutrition", "mental_wellbeing", "intake_context",
)
AGENT_NAME = {
    "pain_symptoms": "Pain & Symptoms", "recovery_progress": "Recovery Progress",
    "rehabilitation": "Rehabilitation", "wound_care": "Wound Care", "medication": "Medication",
    "daily_activity": "Daily Activity", "nutrition": "Nutrition",
    "mental_wellbeing": "Mental Wellbeing", "intake_context": "Intake / Context",
}
SURGERY = {"TKA": "Total Knee Arthroplasty (TKA)", "THA": "Total Hip Arthroplasty (THA)"}


# ---------------------------------------------------------------------------
# Isolation (before importing the backend)
# ---------------------------------------------------------------------------

def isolate_environment() -> str:
    for key in list(os.environ):
        upper = key.upper()
        if "SMTP" in upper or "DOCTOR_ALERT" in upper:
            del os.environ[key]
    temp_dir = tempfile.mkdtemp(prefix="routing_bench_")
    db_path = os.path.join(temp_dir, "patients.sqlite3")
    os.environ["PATIENT_DATABASE_PATH"] = db_path
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    return db_path


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(BACKEND),
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Rule attribution helpers (read the classifier's own tables)
# ---------------------------------------------------------------------------

def keyword_hits(ic, text: str) -> List[Dict[str, Any]]:
    """Keywords that match `text`, in rule order, as the classifier sees them."""
    hits = []
    for position, (intent, keywords) in enumerate(ic._DETERMINISTIC_RULES):
        matched = sorted(k for k in keywords if re.search(r"\b" + re.escape(k) + r"\b", text))
        if matched:
            hits.append({"intent": intent.value, "keywords": matched, "rule_position": position})
    return hits


def intake_signals(ic, text: str) -> Dict[str, Any]:
    intro = [p for p in getattr(ic, "_INTRODUCTION_PATTERNS", []) if re.search(p, text)]
    cues = [p for p in getattr(ic, "_INTAKE_PATTERNS", []) if re.search(p, text)]
    return {
        "greeting": bool(ic._is_simple_greeting(text)),
        "introduction_patterns": intro,
        "intake_cues": cues,
        "question": bool(ic._has_question_signal(text)),
        "symptom": bool(ic._has_clinical_symptom_signal(text)),
        "intake_statement": bool(ic._looks_like_intake_statement(text)),
    }


def attribute(case: Dict[str, Any], detail: Dict[str, Any], hits: List[Dict[str, Any]],
              intake: Dict[str, Any]) -> str:
    """Name the rule that produced a classifier miss."""
    predicted = detail["intent"]
    acceptable = set(case["acceptable"])
    path = detail["decision_path"]
    acceptable_hits = [h for h in hits if h["intent"] in acceptable]
    wrong_hits = [h for h in hits if h["intent"] == predicted]

    if path == "deterministic_patient_record":
        return "patient-record medication name"
    if path == "deterministic_context":
        return "medication follow-up context"
    if path in ("deterministic", "fallback_offline", "fallback_low_confidence", "fallback_low_margin",
                "semfirst_low_confidence", "semfirst_tiebreak_keywords", "semfirst_tiebreak_deterministic"):
        if predicted == "intake_context" and intake["intake_statement"]:
            if intake["greeting"]:
                return "intake rule: greeting"
            if intake["introduction_patterns"] and not intake["intake_cues"]:
                return "intake rule: 'I am / I'm' introduction regex"
            return f"intake rule: cue {intake['intake_cues']}"
        if wrong_hits and acceptable_hits:
            return (f"keyword order: {predicted} ({', '.join(wrong_hits[0]['keywords'])}) is checked before "
                    f"{acceptable_hits[0]['intent']} ({', '.join(acceptable_hits[0]['keywords'])})")
        if wrong_hits:
            return f"overbroad keyword: {predicted} matched {', '.join(wrong_hits[0]['keywords'])}"
        if path.startswith("fallback") or path.startswith("semfirst"):
            why = {"fallback_low_confidence": f"top1 {detail['top1_intent']} {detail['top1_score']:.2f} < {getattr_threshold('SEMANTIC_MIN_SCORE')}",
                   "fallback_low_margin": f"margin {detail['margin']:.2f} < {getattr_threshold('SEMANTIC_MIN_MARGIN')}",
                   "fallback_offline": "model offline"}.get(path, path)
            if hits:
                return f"semantic threshold ({why}) -> keyword fallback picked {predicted}"
            return f"semantic threshold ({why}) -> no keyword -> default {predicted}"
        return f"deterministic ({path}) without a keyword hit"
    if path in ("semantic", "semantic_first", "semfirst_tiebreak_top1"):
        return (f"semantic prototype pull: {predicted} {detail['top1_score']:.2f} via "
                f"{detail['matched_prototype']!r}, margin {detail['margin']:.2f}")
    return path


_THRESHOLDS: Dict[str, Any] = {}


def getattr_threshold(name: str) -> Any:
    return _THRESHOLDS.get(name, "?")


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------

def run(args) -> int:
    db_path = isolate_environment()
    sys.path.insert(0, str(BACKEND))
    sys.path.insert(0, str(HERE))
    os.chdir(str(BACKEND))

    from cases import CASES  # noqa: E402
    import lam.intent_classifier as ic  # noqa: E402
    from lam.schemas import LAMContext  # noqa: E402

    _THRESHOLDS["SEMANTIC_MIN_SCORE"] = getattr(ic, "SEMANTIC_MIN_SCORE", "?")
    _THRESHOLDS["SEMANTIC_MIN_MARGIN"] = getattr(ic, "SEMANTIC_MIN_MARGIN", "?")

    semantic_first = False
    if args.semantic_first:
        if hasattr(ic, "SEMANTIC_FIRST"):
            ic.SEMANTIC_FIRST = True
            semantic_first = True
        else:
            print("[routing] WARNING: intent_classifier has no SEMANTIC_FIRST flag; running the default order")

    cases = list(CASES)
    if args.only:
        needle = args.only.lower()
        cases = [c for c in cases if needle in c["id"].lower() or needle in c["source"].lower()
                 or needle in c["text"].lower()]

    print(f"[routing] commit={git_commit()} cases={len(cases)} semantic_first={semantic_first} "
          f"orchestrator={not args.no_orchestrator}")
    print(f"[routing] PATIENT_DATABASE_PATH={db_path}; SMTP*/DOCTOR_ALERT* cleared")

    # --- classifier -------------------------------------------------------
    t0 = time.time()
    rows: List[Dict[str, Any]] = []
    quiet = io.StringIO()
    for case in cases:
        ctx = LAMContext(patient_id="RB-CLS", surgery_type=SURGERY[case["surgery"]], affected_limb="Right",
                         postop_day=5, user_message=case["text"])
        with contextlib.redirect_stdout(quiet if not args.verbose else sys.stdout):
            d = ic.IntentClassifier.classify_detailed(case["text"], ctx)
        text = ic._normalise_query(case["text"])
        detail = {
            "intent": d.intent.value,
            "decision_path": d.decision_path,
            "top1_intent": getattr(d.top1_intent, "value", None),
            "top1_score": round(float(d.top1_score), 4),
            "top2_intent": getattr(d.top2_intent, "value", None),
            "top2_score": round(float(d.top2_score), 4),
            "margin": round(float(d.margin), 4),
            "matched_prototype": d.matched_prototype,
        }
        hits = keyword_hits(ic, text)
        intake = intake_signals(ic, text)
        correct = d.intent.value in case["acceptable"]
        rows.append({
            **case,
            "classifier": detail,
            "keyword_hits": hits,
            "intake_signals": intake,
            "classifier_correct": correct,
            "classifier_rule": None if correct else attribute(case, detail, hits, intake),
        })
    classifier_seconds = round(time.time() - t0, 1)

    # --- orchestrator -----------------------------------------------------
    orchestrator_seconds = None
    if not args.no_orchestrator:
        from unittest.mock import patch  # noqa: E402
        from agents.agent_router import AgentRouter  # noqa: E402
        from lam import orchestrator as orch  # noqa: E402

        def dispatch(**kwargs):
            intent = kwargs["intent_label"]
            return {"reply": f"{intent.value} response", "triage_level": "GREEN", "is_escalated": False,
                    "engine": "benchmark stub", "sources": []}

        notifier = getattr(orch, "doctor_alert_notifier", None)
        alert_patch = (patch.object(notifier, "notify_red_triage_background", return_value=None)
                       if notifier is not None else contextlib.nullcontext())
        t0 = time.time()
        with patch.object(AgentRouter, "dispatch", side_effect=dispatch), alert_patch:
            for index, row in enumerate(rows, start=1):
                pid = f"RB-{index:04d}"
                try:
                    with contextlib.redirect_stdout(quiet if not args.verbose else sys.stdout):
                        result = orch.LAMOrchestrator.process(
                            patient_id=pid, surgery_type=SURGERY[row["surgery"]], affected_limb="Right",
                            postop_day=5, user_message=row["text"], chat_history=[],
                        )
                    error = None
                except Exception as exc:  # recorded, never hidden
                    result, error = {}, f"{type(exc).__name__}: {exc}"
                intent_value = str(result.get("intent", "") or "")
                routed = [i for i in intent_value.split(",") if i]
                expected_special = row.get("orchestrator_expected")
                if expected_special:
                    correct_lenient = correct_strict = (routed == [expected_special])
                else:
                    acceptable = set(row["acceptable"])
                    dispatched = [i for i in routed if i not in ("emergency", "out_of_scope")]
                    correct_lenient = any(i in acceptable for i in dispatched)
                    correct_strict = bool(dispatched) and all(i in acceptable for i in dispatched)
                pre_empted = None
                if routed == ["emergency"]:
                    pre_empted = "red_triage"
                elif routed == ["out_of_scope"]:
                    pre_empted = "scope_validator"
                row["orchestrator"] = {
                    "intent": intent_value,
                    "routed_intents": routed,
                    "target_agent": result.get("target_agent"),
                    "triage_level": result.get("triage_level"),
                    "engine": result.get("engine"),
                    "pre_empted": pre_empted,
                    "multi_agent": len(routed) > 1,
                    "error": error,
                }
                row["orchestrator_correct"] = correct_lenient
                row["orchestrator_correct_strict"] = correct_strict
        orchestrator_seconds = round(time.time() - t0, 1)

    meta = {
        "label": args.label, "commit": git_commit(), "date": date.today().isoformat(),
        "semantic_first": semantic_first, "orchestrator": not args.no_orchestrator,
        "cases": len(rows), "classifier_seconds": classifier_seconds,
        "orchestrator_seconds": orchestrator_seconds,
        "thresholds": dict(_THRESHOLDS),
    }
    summary = summarise(rows, with_orchestrator=not args.no_orchestrator)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = {"meta": meta, "summary": summary, "rows": rows}
    (RESULTS_DIR / f"{args.label}.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    md = markdown(meta, summary, rows)
    (RESULTS_DIR / f"{args.label}.md").write_text(md, encoding="utf-8")
    (REPORTS_DIR / f"{meta['date']}_routing-{args.label}.md").write_text(md, encoding="utf-8")

    print_summary(summary, with_orchestrator=not args.no_orchestrator)
    print(f"[routing] results -> {RESULTS_DIR / (args.label + '.json')}")
    return 0


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _acc(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    return {"n": len(rows), "correct": sum(1 for r in rows if r.get(key))}


def summarise(rows: List[Dict[str, Any]], *, with_orchestrator: bool) -> Dict[str, Any]:
    classifier_rows = [r for r in rows if not r.get("orchestrator_expected")]
    per_agent: Dict[str, Dict[str, Any]] = {}
    for agent in AGENT_ORDER:
        mine = [r for r in classifier_rows if r["expected"] == agent]
        if not mine:
            continue
        entry = {
            "classifier": _acc(mine, "classifier_correct"),
            "classifier_clear": _acc([r for r in mine if r["confidence"] == "clear"], "classifier_correct"),
            "classifier_openings": _acc([r for r in mine if r["kind"] == "opening"], "classifier_correct"),
        }
        if with_orchestrator:
            entry["orchestrator"] = _acc(mine, "orchestrator_correct")
            entry["orchestrator_strict"] = _acc(mine, "orchestrator_correct_strict")
            entry["orchestrator_openings"] = _acc([r for r in mine if r["kind"] == "opening"], "orchestrator_correct")
        per_agent[agent] = entry

    overall = {
        "classifier": _acc(classifier_rows, "classifier_correct"),
        "classifier_clear": _acc([r for r in classifier_rows if r["confidence"] == "clear"], "classifier_correct"),
        "classifier_openings": _acc([r for r in classifier_rows if r["kind"] == "opening"], "classifier_correct"),
    }
    if with_orchestrator:
        overall["orchestrator"] = _acc(classifier_rows, "orchestrator_correct")
        overall["orchestrator_strict"] = _acc(classifier_rows, "orchestrator_correct_strict")
        overall["orchestrator_openings"] = _acc([r for r in classifier_rows if r["kind"] == "opening"], "orchestrator_correct")
        overall["orchestrator_special"] = _acc([r for r in rows if r.get("orchestrator_expected")], "orchestrator_correct")
        overall["multi_agent_turns"] = sum(1 for r in rows if r.get("orchestrator", {}).get("multi_agent"))
        overall["pre_empted"] = Counter(r["orchestrator"]["pre_empted"] for r in rows
                                        if r.get("orchestrator", {}).get("pre_empted"))

    rule_groups: Dict[str, List[str]] = defaultdict(list)
    for r in classifier_rows:
        if not r["classifier_correct"]:
            rule_groups[_group(r["classifier_rule"])].append(r["id"])
    decision_paths = Counter(r["classifier"]["decision_path"] for r in rows)

    return {
        "per_agent": per_agent, "overall": overall,
        "miss_groups": {k: sorted(v) for k, v in sorted(rule_groups.items())},
        "decision_paths": dict(decision_paths),
    }


def _group(rule: Optional[str]) -> str:
    if not rule:
        return "-"
    for prefix in ("keyword order", "overbroad keyword", "intake rule", "semantic prototype pull",
                   "semantic threshold", "patient-record", "medication follow-up"):
        if rule.startswith(prefix):
            return prefix
    return rule.split(":")[0]


def pct(acc: Dict[str, int]) -> str:
    return f"{acc['correct']}/{acc['n']} ({100 * acc['correct'] / acc['n']:.0f}%)" if acc["n"] else "-"


def print_summary(summary: Dict[str, Any], *, with_orchestrator: bool) -> None:
    print()
    head = f"{'agent':<18} {'classifier':>14} {'clear only':>14}"
    if with_orchestrator:
        head += f" {'orchestrator':>14} {'strict':>14}"
    print(head)
    for agent, entry in summary["per_agent"].items():
        line = f"{AGENT_NAME[agent]:<18} {pct(entry['classifier']):>14} {pct(entry['classifier_clear']):>14}"
        if with_orchestrator:
            line += f" {pct(entry['orchestrator']):>14} {pct(entry['orchestrator_strict']):>14}"
        print(line)
    o = summary["overall"]
    line = f"{'ALL':<18} {pct(o['classifier']):>14} {pct(o['classifier_clear']):>14}"
    if with_orchestrator:
        line += f" {pct(o['orchestrator']):>14} {pct(o['orchestrator_strict']):>14}"
    print(line)
    print()
    for group, ids in summary["miss_groups"].items():
        print(f"  misses by rule: {group:<28} {len(ids):>3}  {' '.join(ids)}")


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def markdown(meta: Dict[str, Any], summary: Dict[str, Any], rows: List[Dict[str, Any]]) -> str:
    with_orch = meta["orchestrator"]
    L: List[str] = []
    L.append(f"# Routing benchmark -- `{meta['label']}`")
    L.append("")
    L.append(f"- commit `{meta['commit']}`, {meta['date']}; {meta['cases']} cases; "
             f"semantic_first={meta['semantic_first']}; thresholds {meta['thresholds']}")
    L.append(f"- classifier run {meta['classifier_seconds']}s"
             + (f", orchestrator run {meta['orchestrator_seconds']}s" if with_orch else ""))
    L.append("- a prediction is correct when it is in the case's acceptable set; *clear only* excludes debatable cases; "
             "*openings* excludes the six answers-to-a-pending-question, which carry no routable signal on their own")
    if with_orch:
        L.append("- orchestrator *lenient*: at least one dispatched agent is acceptable (the eval/agents definition); "
                 "*strict*: every dispatched agent is acceptable")
    L.append("")
    L.append("## Per agent")
    L.append("")
    head = "| Agent | n | Classifier | Classifier, clear only | Classifier, openings |"
    sep = "|---|---|---|---|---|"
    if with_orch:
        head += " Orchestrator (lenient) | Orchestrator (strict) | Orchestrator, openings |"
        sep += "---|---|---|"
    L.append(head)
    L.append(sep)
    for agent, e in summary["per_agent"].items():
        line = (f"| {AGENT_NAME[agent]} | {e['classifier']['n']} | {pct(e['classifier'])} | "
                f"{pct(e['classifier_clear'])} | {pct(e['classifier_openings'])} |")
        if with_orch:
            line += f" {pct(e['orchestrator'])} | {pct(e['orchestrator_strict'])} | {pct(e['orchestrator_openings'])} |"
        L.append(line)
    o = summary["overall"]
    line = (f"| **All** | {o['classifier']['n']} | **{pct(o['classifier'])}** | {pct(o['classifier_clear'])} | "
            f"{pct(o['classifier_openings'])} |")
    if with_orch:
        line += f" **{pct(o['orchestrator'])}** | {pct(o['orchestrator_strict'])} | {pct(o['orchestrator_openings'])} |"
    L.append(line)
    L.append("")
    if with_orch:
        L.append(f"Orchestrator pre-emption cases (emergency / out_of_scope expected): {pct(o['orchestrator_special'])}; "
                 f"multi-agent turns: {o['multi_agent_turns']}; pre-empted: {dict(o['pre_empted'])}.")
        L.append("")
    L.append("Decision paths: " + ", ".join(f"`{k}` {v}" for k, v in sorted(summary["decision_paths"].items())))
    L.append("")

    L.append("## Classifier misses, grouped by rule")
    L.append("")
    misses = [r for r in rows if not r.get("orchestrator_expected") and not r["classifier_correct"]]
    if not misses:
        L.append("none")
    for group, ids in summary["miss_groups"].items():
        L.append(f"### {group} ({len(ids)})")
        L.append("")
        L.append("| Case | Message | Expected (acceptable) | Got | Path | Rule |")
        L.append("|---|---|---|---|---|---|")
        for r in misses:
            if _group(r["classifier_rule"]) != group:
                continue
            tag = f" *{r['kind']}*" if r["kind"] != "opening" else ""
            tag += " *debatable*" if r["confidence"] == "debatable" else ""
            L.append(f"| {r['id']} | \"{r['text']}\"{tag} | {r['expected']} ({', '.join(r['acceptable'])}) | "
                     f"{r['classifier']['intent']} | {r['classifier']['decision_path']} | {r['classifier_rule']} |")
        L.append("")

    if with_orch:
        L.append("## Orchestrator misses (lenient)")
        L.append("")
        omiss = [r for r in rows if not r.get("orchestrator_correct")]
        if not omiss:
            L.append("none")
        else:
            L.append("| Case | Message | Expected (acceptable) | Orchestrator intent | Target agent | Classifier said |")
            L.append("|---|---|---|---|---|---|")
            for r in omiss:
                oc = r["orchestrator"]
                exp = r.get("orchestrator_expected") or f"{r['expected']} ({', '.join(r['acceptable'])})"
                L.append(f"| {r['id']} | \"{r['text']}\" | {exp} | {oc['intent'] or oc['error']} | {oc['target_agent']} | "
                         f"{r['classifier']['intent']} ({r['classifier']['decision_path']}) |")
        L.append("")
        L.append("## Orchestrator differs from the classifier")
        L.append("")
        diff = [r for r in rows if r["orchestrator"]["routed_intents"] != [r["classifier"]["intent"]]]
        L.append("| Case | Message | Classifier | Orchestrator | Why |")
        L.append("|---|---|---|---|---|")
        for r in diff:
            oc = r["orchestrator"]
            why = oc["pre_empted"] or ("multi-agent: detect_applicable_intents" if oc["multi_agent"] else
                                       "recorded medication / context")
            L.append(f"| {r['id']} | \"{r['text']}\" | {r['classifier']['intent']} | {oc['intent']} | {why} |")
        L.append("")

    L.append("## Every case")
    L.append("")
    head = "| Case | Source | Message | Expected (acceptable) | Conf. | Classifier | Path |"
    sep = "|---|---|---|---|---|---|---|"
    if with_orch:
        head += " Orchestrator |"
        sep += "---|"
    L.append(head)
    L.append(sep)
    for r in rows:
        c = r["classifier"]
        mark = "" if r["classifier_correct"] else " **x**"
        line = (f"| {r['id']} | {r['source']} | \"{r['text']}\" | {r['expected']} ({', '.join(r['acceptable'])}) | "
                f"{r['confidence']}{'/' + r['kind'] if r['kind'] != 'opening' else ''} | {c['intent']}{mark} | {c['decision_path']} |")
        if with_orch:
            oc = r["orchestrator"]
            omark = "" if r.get("orchestrator_correct") else " **x**"
            line += f" {oc['intent'] or oc['error']}{omark} |"
        L.append(line)
    L.append("")
    return "\n".join(L)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", required=True)
    parser.add_argument("--semantic-first", action="store_true")
    parser.add_argument("--no-orchestrator", action="store_true")
    parser.add_argument("--only", default=None)
    parser.add_argument("--verbose", action="store_true")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
