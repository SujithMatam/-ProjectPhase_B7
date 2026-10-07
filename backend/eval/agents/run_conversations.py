"""
Conversation-level evaluation of the Pain, Recovery and Rehabilitation agents.

    .venv/Scripts/python.exe eval/agents/run_conversations.py [options]

Runs every scripted conversation in eval/agents/conversations/*.json turn by
turn and checks the expected properties on each turn and on the whole
conversation (see README section of eval/agents/REPORT.md for the list).

Isolation, always (set before any backend module is imported):
  * PATIENT_DATABASE_PATH points at a fresh temp sqlite file; each
    conversation seeds its own patient record there;
  * every environment variable containing SMTP or DOCTOR_ALERT is removed,
    and the RED doctor-alert hook is replaced by a no-op.

Modes:
  default             direct calls to the real agent classes (as the tests
                      do), with precomputed_triage taken from
                      SafetyTriageEngine on the same turn text; the LLM is
                      stubbed (Pain/Recovery: empty ChatAgent reply, so the
                      deterministic close is measured; Rehab: the local LLM
                      offline, so ChatAgent's real retrieval and fallback run).
  --live              no LLM stub: ChatAgent talks to the local Ollama server.
  --via-orchestrator  every turn goes through LAMOrchestrator.process();
                      turns the orchestrator sends to another agent are
                      recorded as misrouted (the agent then never sees them).

Options:
  --backend-dir DIR   import the agents from another checkout's backend/
                      (used to run the same conversations against the
                      baseline commit in a git worktree).
  --label NAME        name of the run; results go to
                      eval/agents/results/<label>.json and .md, and the
                      markdown is also copied to
                      eval/reports/<date>_agents-conversations-<label>.md.
  --only SUBSTR       run only conversations whose id contains SUBSTR.
  --verbose           show the agents' own console output.

The script is deliberately tolerant of older agent code (missing modules,
fewer handle() parameters), so the identical conversations and checks run
against the baseline.
"""

from __future__ import annotations

import argparse
import contextlib
import inspect
import io
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
DEFAULT_BACKEND = HERE.parents[1]
CONVERSATIONS_DIR = HERE / "conversations"
RESULTS_DIR = HERE / "results"
REPORTS_DIR = DEFAULT_BACKEND / "eval" / "reports"

AGENT_CLASS = {
    "pain": "PainSymptomsAgent",
    "recovery": "RecoveryProgressAgent",
    "rehab": "RehabilitationAgent",
}

# Default LLM stub per agent (matches how the *_CHANGES.md transcripts were made).
DEFAULT_STUB = {"pain": "empty_reply", "recovery": "empty_reply", "rehab": "offline"}

# Final-turn patterns, per agent. "Trend or checkpoint" means: Pain compares
# with the last assessment; Recovery names a checkpoint day / the long-term
# guidance; Rehab anchors the guidance to the post-op day (or abstains for
# that day). "Next step" is the agent's one explicit next action.
FINAL_TREND = {
    "pain": r"Compared with last time",
    "recovery": r"day-\d+ (range|checkpoint|mark|target|guidance)|long-term guidance|checkpoint is day \d+",
    "rehab": r"on day \d+ after your (knee|hip) replacement|for day \d+ after your",
}
FINAL_NEXT = {
    "pain": r"Next step:",
    "recovery": r"Next milestone:",
    "rehab": r"Next session:",
}

PASSAGE_ID = re.compile(r"\b(?:EV-)?(?:TKA|THA|GEN)-(?:[A-Z]+-)?\d{1,3}\b")
CONFIRM_MARKER = "still about that"
UNKNOWN_VALUES = {None, "", "unknown"}


# ---------------------------------------------------------------------------
# Environment isolation (must run before importing the backend)
# ---------------------------------------------------------------------------

def isolate_environment() -> str:
    for key in list(os.environ):
        upper = key.upper()
        if "SMTP" in upper or "DOCTOR_ALERT" in upper:
            del os.environ[key]
    temp_dir = tempfile.mkdtemp(prefix="agent_conv_eval_")
    db_path = os.path.join(temp_dir, "patients.sqlite3")
    os.environ["PATIENT_DATABASE_PATH"] = db_path
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    return db_path


def ollama_reachable() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as response:
            return response.status == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Backend handle (modules imported from --backend-dir)
# ---------------------------------------------------------------------------

class Backend:
    def __init__(self, backend_dir: Path, verbose: bool):
        sys.path.insert(0, str(backend_dir))
        os.chdir(str(backend_dir))
        self.verbose = verbose
        with self.quiet():
            import patient_database
            from agents import specialized_agents, pain_logic, pain_state, recovery_state
            from agents.chat_agent import ChatAgent
            from triage.safety_triage import SafetyTriageEngine
            from lam import orchestrator as orchestrator_module
            from lam import schemas

            try:
                from agents import rehab_state  # added by the rework
            except ImportError:
                rehab_state = None
        self.db = patient_database
        self.agents = specialized_agents
        self.pain_logic = pain_logic
        self.pain_state = pain_state
        self.recovery_state = recovery_state
        self.rehab_state = rehab_state
        self.ChatAgent = ChatAgent
        self.Triage = SafetyTriageEngine
        self.orch = orchestrator_module
        self.schemas = schemas

    @contextlib.contextmanager
    def quiet(self):
        if self.verbose:
            yield
            return
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            yield

    def agent_class(self, agent: str):
        return getattr(self.agents, AGENT_CLASS[agent])

    def clear_states(self) -> None:
        for module in (self.pain_state, self.recovery_state, self.rehab_state):
            if module is not None and hasattr(module, "_clear_all_state_for_tests"):
                module._clear_all_state_for_tests()

    def engine_triage(self, text: str, day: int) -> Dict[str, Any]:
        prepare = getattr(self.orch, "_prepare_triage_text", lambda value: value)
        return self.Triage.evaluate(symptoms=prepare(text), post_op_day=day)


# ---------------------------------------------------------------------------
# LLM stubs
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def llm_mode(backend: Backend, mode: str):
    """mode: empty_reply | offline | live."""
    from unittest.mock import patch

    if mode == "live":
        yield
        return
    if mode == "empty_reply":
        def _answer(*args, **kwargs):
            return {"reply": "", "triage_level": "GREEN", "is_escalated": False,
                    "engine": "Clinical Synthesis Engine", "sources": []}
        with patch.object(backend.ChatAgent, "answer_question", side_effect=_answer):
            yield
        return
    if mode == "offline":
        with patch.object(backend.ChatAgent, "_query_llama", return_value=None):
            yield
        return
    raise ValueError(f"unknown LLM mode {mode!r}")


@contextlib.contextmanager
def no_doctor_alert(backend: Backend):
    from unittest.mock import patch

    notifier = getattr(backend.orch, "doctor_alert_notifier", None)
    if notifier is None or not hasattr(notifier, "notify_red_triage_background"):
        yield
        return
    with patch.object(notifier, "notify_red_triage_background", return_value=None):
        yield


# ---------------------------------------------------------------------------
# Probes: what the agent has collected / is asking, read from its own state
# ---------------------------------------------------------------------------

class PainSpy:
    """Captures the assessment dict the Pain agent builds on each turn (works
    for the baseline's build_assessment and the rework's
    build_assessment_detailed)."""

    NAMES = ("build_assessment_detailed", "build_assessment")

    def __init__(self, backend: Backend):
        self.backend = backend
        self.captured: List[Dict[str, Any]] = []
        self._originals: Dict[str, Any] = {}

    def __enter__(self):
        logic = self.backend.pain_logic
        for name in self.NAMES:
            original = getattr(logic, name, None)
            if original is None:
                continue
            self._originals[name] = original

            def wrapper(*args, _orig=original, **kwargs):
                result = _orig(*args, **kwargs)
                assessment = None
                if isinstance(result, tuple) and result and isinstance(result[0], dict):
                    assessment = result[0]
                elif hasattr(result, "assessment"):
                    assessment = getattr(result, "assessment")
                elif isinstance(result, dict):
                    assessment = result
                if isinstance(assessment, dict):
                    self.captured.append(dict(assessment))
                return result

            setattr(logic, name, wrapper)
        return self

    def __exit__(self, *exc):
        for name, original in self._originals.items():
            setattr(self.backend.pain_logic, name, original)
        return False


def _clean(facts: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for key, value in facts.items():
        if isinstance(value, str) and value.strip().lower() in UNKNOWN_VALUES:
            continue
        if value in UNKNOWN_VALUES:
            continue
        out[key] = value
    return out


def recovery_session(backend: Backend, patient_id: str):
    store = getattr(backend.recovery_state, "_STORE", {})
    matches = [state for key, state in list(store.items()) if patient_id.upper() in str(key).upper()]
    if not matches:
        return None
    return max(matches, key=lambda state: getattr(state, "last_updated", 0))


def collected_facts(backend: Backend, agent: str, patient_id: str, pain_spy: Optional[PainSpy],
                    previous: Dict[str, Any]) -> Dict[str, Any]:
    if agent == "pain":
        if pain_spy is not None and pain_spy.captured:
            fields = set(getattr(backend.pain_logic, "QUESTIONS", {}).keys()) | {
                "pain_characteristics", "medication_effect"}
            assessment = pain_spy.captured[-1]
            return _clean({k: v for k, v in assessment.items() if k in fields})
        return dict(previous)
    if agent == "recovery":
        state = recovery_session(backend, patient_id)
        if state is None:
            return dict(previous)
        facts = getattr(state, "_facts", {}) or {}
        return _clean({k: getattr(v, "value", v) for k, v in facts.items()})
    if agent == "rehab":
        if backend.rehab_state is None:
            return {}
        state = backend.rehab_state.peek_state(patient_id)
        if state is None:
            return dict(previous)
        facts = state.facts() if callable(getattr(state, "facts", None)) else getattr(state, "facts", {})
        return _clean(dict(facts or {}))
    return {}


def pending_field(backend: Backend, agent: str, patient_id: str) -> Tuple[bool, Optional[str]]:
    """(agent has a state module, pending field after the turn)."""
    if agent == "pain":
        state = backend.pain_state.peek_state(patient_id)
        return True, (state.pending_field if state is not None else None)
    if agent == "recovery":
        state = recovery_session(backend, patient_id)
        return True, (state.pending_field if state is not None else None)
    if agent == "rehab":
        if backend.rehab_state is None:
            return False, None
        state = backend.rehab_state.peek_state(patient_id)
        return True, (state.pending_field if state is not None else None)
    return False, None


# ---------------------------------------------------------------------------
# Database seeding and snapshots
# ---------------------------------------------------------------------------

def iso_days_ago(days: int) -> str:
    return (date.today() - timedelta(days=int(days))).isoformat()


def seed_record(backend: Backend, record: Dict[str, Any]) -> None:
    surgery_days = int(record["surgery_days_ago"])
    today_day = surgery_days + 1  # the surgery day is post-op day 1
    metrics = []
    for row in record.get("metrics", []):
        days_ago = int(row.get("days_ago", 0))
        entry = {k: v for k, v in row.items() if k != "days_ago"}
        entry["date"] = iso_days_ago(days_ago)
        entry["day"] = today_day - days_ago
        metrics.append(entry)
    with backend.quiet():
        backend.db.create_patient({
            "patient_id": record["patient_id"],
            "full_name": f"Eval {record['patient_id']}",
            "surgery_type": record["surgery_type"],
            "affected_limb": record.get("affected_limb", "Right"),
            "surgery_date": iso_days_ago(surgery_days),
            "postop_day": today_day,
            "weight_bearing_status": record.get("weight_bearing_status"),
            "metrics_history": metrics,
        })
    priors = sorted(record.get("prior_assessments", []), key=lambda row: -int(row.get("days_ago", 0)))
    if priors:
        with sqlite3.connect(os.environ["PATIENT_DATABASE_PATH"]) as connection:
            for row in priors:
                days_ago = int(row.get("days_ago", 0))
                values = {k: v for k, v in row.items() if k != "days_ago"}
                values["postop_day"] = today_day - days_ago
                columns = ["patient_id", "created_at", *values.keys()]
                connection.execute(
                    f"INSERT INTO symptom_assessments ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
                    (record["patient_id"], f"{iso_days_ago(days_ago)} 09:00:00", *values.values()),
                )


def db_snapshot(patient_id: str) -> Dict[str, Any]:
    with sqlite3.connect(os.environ["PATIENT_DATABASE_PATH"]) as connection:
        assessments = [row[0] for row in connection.execute(
            "SELECT id FROM symptom_assessments WHERE patient_id = ?", (patient_id,))]
        metrics = {row[0]: tuple(row[1:]) for row in connection.execute(
            "SELECT id, day, date, pain_score, rom_flexion, rom_extension, exercise_completed, swelling, triage "
            "FROM metrics WHERE patient_id = ?", (patient_id,))}
        wb_row = connection.execute(
            "SELECT weight_bearing_status FROM surgeries WHERE patient_id = ?", (patient_id,)).fetchone()
    return {"assessments": set(assessments), "metrics": metrics, "wb": wb_row[0] if wb_row else None}


def rows_written(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, int]:
    new_assessments = len(after["assessments"] - before["assessments"])
    new_metrics = len(set(after["metrics"]) - set(before["metrics"]))
    changed_metrics = sum(1 for key, row in after["metrics"].items()
                          if key in before["metrics"] and before["metrics"][key] != row)
    return {"symptom_assessments": new_assessments, "metrics_inserted": new_metrics,
            "metrics_updated": changed_metrics,
            "total": new_assessments + new_metrics + changed_metrics}


# ---------------------------------------------------------------------------
# Running one conversation
# ---------------------------------------------------------------------------

def call_agent_direct(backend: Backend, conv: Dict[str, Any], text: str, history: List[Dict[str, str]],
                      triage: Dict[str, Any]) -> Dict[str, Any]:
    record, request = conv["record"], conv.get("request", {})
    agent_cls = backend.agent_class(conv["agent"])
    kwargs = dict(
        patient_id=record["patient_id"], surgery_type=record["surgery_type"],
        affected_limb=record.get("affected_limb", "Right"),
        postop_day=int(request.get("postop_day", record["surgery_days_ago"] + 1)),
        user_message=text, procedure=record["procedure"], chat_history=list(history),
        surgery_date=iso_days_ago(record["surgery_days_ago"]), precomputed_triage=triage,
        current_rom=request.get("current_rom"), exercise_history=request.get("exercise_history"),
        weight_bearing_status=_wb_enum(backend, request.get("weight_bearing_status")),
    )
    accepted = inspect.signature(agent_cls.handle).parameters
    kwargs = {k: v for k, v in kwargs.items() if k in accepted}
    return agent_cls.handle(**kwargs)


def call_orchestrator(backend: Backend, conv: Dict[str, Any], text: str,
                      history: List[Dict[str, str]]) -> Dict[str, Any]:
    record, request = conv["record"], conv.get("request", {})
    kwargs = dict(
        patient_id=record["patient_id"], surgery_type=record["surgery_type"],
        affected_limb=record.get("affected_limb", "Right"),
        postop_day=int(request.get("postop_day", record["surgery_days_ago"] + 1)),
        user_message=text, chat_history=list(history),
        surgery_date=iso_days_ago(record["surgery_days_ago"]),
        current_rom=request.get("current_rom"), exercise_history=request.get("exercise_history"),
        weight_bearing_status=_wb_enum(backend, request.get("weight_bearing_status")),
    )
    accepted = inspect.signature(backend.orch.LAMOrchestrator.process).parameters
    kwargs = {k: v for k, v in kwargs.items() if k in accepted}
    return backend.orch.LAMOrchestrator.process(**kwargs)


def _wb_enum(backend: Backend, value: Optional[str]):
    if not value:
        return None
    enum_cls = getattr(backend.schemas, "WeightBearingStatus", None)
    return enum_cls(value) if enum_cls is not None else value


def run_conversation(backend: Backend, conv: Dict[str, Any], *, live: bool, via_orchestrator: bool) -> Dict[str, Any]:
    agent = conv["agent"]
    record = conv["record"]
    patient_id = record["patient_id"]
    day = int(conv.get("request", {}).get("postop_day", record["surgery_days_ago"] + 1))
    mode = "live" if live else conv.get("llm_stub", DEFAULT_STUB[agent])
    expected_class = AGENT_CLASS[agent]

    backend.clear_states()
    seed_record(backend, record)
    start = db_snapshot(patient_id)

    history: List[Dict[str, str]] = []
    turns_out: List[Dict[str, Any]] = []
    collected: Dict[str, Any] = {}
    snapshot = start
    pending_before: Optional[str] = None  # our agent's open question going into the turn

    with llm_mode(backend, mode), no_doctor_alert(backend):
        for index, turn in enumerate(conv["turns"], start=1):
            text = turn["patient"]
            engine = backend.engine_triage(text, day)
            detour = turn.get("detour")
            before_collected = dict(collected)
            spy = PainSpy(backend) if agent == "pain" else None
            routed_to = None
            error = None
            result: Dict[str, Any] = {}
            started = time.time()
            try:
                with (spy or contextlib.nullcontext()), backend.quiet():
                    if via_orchestrator:
                        result = call_orchestrator(backend, conv, text, history)
                        routed_to = result.get("target_agent")
                    elif detour:
                        result = {"reply": detour["reply"], "triage_level": engine.get("triage_level"),
                                  "engine": "scripted detour", "sources": []}
                        routed_to = detour["agent"]
                    else:
                        result = call_agent_direct(backend, conv, text, history, engine)
                        routed_to = expected_class
            except Exception as exc:  # recorded as a failed turn, never hidden
                error = f"{type(exc).__name__}: {exc}"
                result = {"reply": "", "triage_level": None}
            elapsed = time.time() - started

            reply = str(result.get("reply") or "")
            if detour and not via_orchestrator:
                has_state, pending = False, None
            else:
                collected = collected_facts(backend, agent, patient_id, spy, collected)
                has_state, pending = pending_field(backend, agent, patient_id)
            after = db_snapshot(patient_id)
            written = rows_written(snapshot, after)
            snapshot = after

            expected_here = (detour or {}).get("agent") or turn.get("orchestrator_expected_agent") or expected_class
            ours = not detour
            misroute_kind = None
            if expected_here != "*" and expected_here not in str(routed_to or ""):
                if str(routed_to) == "SafetyTriageAgent":
                    misroute_kind = "red_preempted"
                elif pending_before:
                    misroute_kind = "continuation"
                else:
                    misroute_kind = "fresh_classification"
            if has_state:
                asked = pending is not None and "?" in reply
                questions = 1 if asked else 0
            else:
                asked = False
                questions = reply.count("?") if ours else 0
            new_fields = sorted(k for k in collected if k not in before_collected
                                or before_collected[k] != collected[k])

            turns_out.append({
                "index": index,
                "patient": text,
                "reply": reply,
                "engine": result.get("engine"),
                "sources": result.get("sources", []),
                "triage_level": result.get("triage_level"),
                "engine_triage_level": engine.get("triage_level"),
                "routed_to": routed_to,
                "expected_agent": expected_here,
                "misroute_kind": misroute_kind,
                "pending_before": pending_before,
                "is_agent_turn": ours,
                "asked_field": pending if asked else None,
                "is_confirm": bool(asked and CONFIRM_MARKER in reply.lower()),
                "questions": questions,
                "collected": {k: str(v) for k, v in collected.items()},
                "collected_before": {k: str(v) for k, v in before_collected.items()},
                "new_fields": new_fields,
                "rows_written": written,
                "error": error,
                "seconds": round(elapsed, 2),
            })
            history.append({"role": "user", "content": text})
            history.append({"role": "assistant", "content": reply})
            if ours and misroute_kind is None:
                pending_before = pending if asked else None
            elif ours and misroute_kind == "red_preempted":
                pending_before = None

    end = db_snapshot(patient_id)
    out = {
        "id": conv["id"], "agent": agent, "title": conv.get("title", ""), "tags": conv.get("tags", []),
        "llm_mode": mode, "turns": turns_out,
        "rows_persisted": rows_written(start, end),
        "wb_before": start["wb"], "wb_after": end["wb"],
    }
    out["properties"] = evaluate(conv, out, via_orchestrator=via_orchestrator)
    out["summary"] = summarise(conv, out)
    return out


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

def _prop(name: str, passed: bool, detail: str = "", turn: Optional[int] = None) -> Dict[str, Any]:
    return {"name": name, "turn": turn, "passed": bool(passed), "detail": detail}


def evaluate(conv: Dict[str, Any], run: Dict[str, Any], *, via_orchestrator: bool) -> List[Dict[str, Any]]:
    agent = conv["agent"]
    expect = conv.get("expect", {})
    props: List[Dict[str, Any]] = []
    turns = run["turns"]
    agent_turns = [t for t in turns if t["is_agent_turn"]]

    for spec, out in zip(conv["turns"], turns):
        i = out["index"]
        if out["error"]:
            props.append(_prop("turn_runs_without_error", False, out["error"], i))
        if not out["is_agent_turn"]:
            continue
        for field in spec.get("must_collect", []):
            props.append(_prop("collects_field", field in out["collected"],
                               f"{field} -> {out['collected'].get(field, 'not collected')}", i))
        for field in spec.get("must_not_collect", []):
            props.append(_prop("does_not_collect", field not in out["collected"],
                               f"{field} -> {out['collected'].get(field, 'not collected')}", i))
        for field, needle in spec.get("must_not_store", {}).items():
            value = out["collected"].get(field, "")
            props.append(_prop("does_not_store_unfitting_reply", needle.lower() not in value.lower(),
                               f"{field} = {value!r} must not contain {needle!r}", i))
        if spec.get("reply_must_match"):
            props.append(_prop("reply_matches", re.search(spec["reply_must_match"], out["reply"]) is not None,
                               f"/{spec['reply_must_match']}/", i))
        if spec.get("reply_must_not_match"):
            hit = re.search(spec["reply_must_not_match"], out["reply"])
            props.append(_prop("reply_does_not_match", hit is None,
                               f"/{spec['reply_must_not_match']}/" + (f" hit {hit.group(0)!r}" if hit else ""), i))

    # No question asks for data already in the record. Confirming the
    # recorded value is allowed, and so is asking afresh once the patient
    # has not confirmed it.
    record_fields = [f["field"] for f in conv.get("record_fields", []) if f.get("field")]
    if record_fields:
        bad = [f"turn {t['index']}: {t['asked_field']}" for t in record_field_asks(agent_turns, record_fields)]
        props.append(_prop("no_question_for_record_data", not bad,
                           "; ".join(bad) or f"never asked: {', '.join(record_fields)}"))

    # No question re-asks something already collected in this conversation.
    reasks = [f"turn {t['index']}: {t['asked_field']}" for t in agent_turns
              if t["asked_field"] and t["asked_field"] in t["collected_before"]
              and t["asked_field"] not in t["new_fields"]]
    props.append(_prop("no_reask_of_collected_field", not reasks, "; ".join(reasks)))

    total_questions = sum(t["questions"] for t in agent_turns)
    if "max_questions" in expect:
        props.append(_prop("max_questions", total_questions <= expect["max_questions"],
                           f"{total_questions} asked, max {expect['max_questions']}"))

    # Engine level on the turn's own text. Through the orchestrator, a turn
    # its cumulative Pain triage escalates to RED is answered by the safety
    # path instead; that is the engine's own (more severe) decision, so it is
    # reported in the detail but not counted as a mismatch.
    mismatches, preempted = [], []
    for t in agent_turns:
        if t["triage_level"] == t["engine_triage_level"]:
            continue
        if t["misroute_kind"] == "red_preempted" and t["triage_level"] == "RED":
            preempted.append(f"turn {t['index']}: RED from cumulative triage (engine on turn text {t['engine_triage_level']})")
        else:
            mismatches.append(f"turn {t['index']}: got {t['triage_level']}, engine {t['engine_triage_level']}")
    props.append(_prop("triage_equals_engine", not mismatches, "; ".join(mismatches + preempted)))

    leaks = [f"turn {t['index']}: {m}" for t in agent_turns for m in PASSAGE_ID.findall(t["reply"])]
    props.append(_prop("no_passage_id_in_text", not leaks, "; ".join(leaks)))

    final = agent_turns[-1] if agent_turns else None
    if expect.get("completes") and final is not None:
        props.append(_prop("final_turn_closes_interview", final["asked_field"] is None and final["questions"] == 0,
                           f"final turn still asks {final['asked_field'] or 'a question'}"
                           if final["questions"] else "no question pending"))
        trend = expect.get("final_trend", FINAL_TREND[agent]) if "final_trend" in expect else FINAL_TREND[agent]
        if trend:
            props.append(_prop("final_has_trend_or_checkpoint", re.search(trend, final["reply"]) is not None,
                               f"/{trend}/"))
        nxt = expect.get("final_next_step", FINAL_NEXT[agent])
        props.append(_prop("final_has_next_step", re.search(nxt, final["reply"]) is not None, f"/{nxt}/"))

    persisted = run["rows_persisted"]["total"]
    if expect.get("abandoned"):
        props.append(_prop("abandoned_persists_nothing", persisted == 0, f"{persisted} row(s) written"))
    elif expect.get("persist_min"):
        props.append(_prop("persists_on_completion", persisted >= expect["persist_min"],
                           f"{persisted} row(s) written, expected >= {expect['persist_min']}"))
    if expect.get("wb_record_unchanged"):
        props.append(_prop("weight_bearing_record_unchanged", run["wb_before"] == run["wb_after"],
                           f"{run['wb_before']!r} -> {run['wb_after']!r}"))

    if via_orchestrator:
        misrouted = [f"turn {t['index']}: {t['routed_to']} ({t['misroute_kind']}, expected {t['expected_agent']})"
                     for t in turns if t["misroute_kind"] in ("continuation", "fresh_classification")]
        props.append(_prop("routed_to_expected_agent", not misrouted, "; ".join(misrouted)))
    return props


def record_field_asks(agent_turns: List[Dict[str, Any]], record_fields: List[str]) -> List[Dict[str, Any]]:
    """Turns that ask for a record field from scratch, without having first
    offered the recorded value for confirmation."""
    confirmed: set = set()
    asks = []
    for t in agent_turns:
        field = t["asked_field"]
        if field not in record_fields:
            continue
        if t["is_confirm"]:
            confirmed.add(field)
        elif field not in confirmed:
            asks.append(t)
    return asks


def summarise(conv: Dict[str, Any], run: Dict[str, Any]) -> Dict[str, Any]:
    agent_turns = [t for t in run["turns"] if t["is_agent_turn"]]
    evidence = [f for f in conv.get("record_fields", []) if f.get("evidence")]
    replies = "\n".join(t["reply"] for t in agent_turns)
    reused = [f["source"] for f in evidence if re.search(f["evidence"], replies)]
    record_field_names = [f["field"] for f in conv.get("record_fields", []) if f.get("field")]
    asked_record = {t["asked_field"] for t in record_field_asks(agent_turns, record_field_names)}
    misrouted = [t["index"] for t in run["turns"] if t["misroute_kind"] in ("continuation", "fresh_classification")]
    continuation = [t["index"] for t in run["turns"] if t["misroute_kind"] == "continuation"]
    fresh = [t["index"] for t in run["turns"] if t["misroute_kind"] == "fresh_classification"]
    red_preempted = [t["index"] for t in run["turns"] if t["misroute_kind"] == "red_preempted"]
    props = run["properties"]
    return {
        "questions": sum(t["questions"] for t in agent_turns),
        "fields_per_turn": [len(t["new_fields"]) for t in agent_turns],
        "fields_total": len({field for t in agent_turns for field in t["collected"]}),
        "record_fields_reused": len(reused),
        "record_fields_offered": len(evidence),
        "record_fields_reused_sources": reused,
        "record_fields_asked": sorted(asked_record),
        "rows_persisted": run["rows_persisted"]["total"],
        "misrouted_turns": misrouted,
        "misrouted_continuation": continuation,
        "misrouted_fresh": fresh,
        "red_preempted_turns": red_preempted,
        "properties_passed": sum(1 for p in props if p["passed"]),
        "properties_total": len(props),
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def markdown(label: str, meta: Dict[str, Any], runs: List[Dict[str, Any]]) -> str:
    lines = [f"# Agent conversation eval -- {label}", ""]
    lines.append(f"- backend: {meta['backend_dir']} (commit `{meta['commit']}`)")
    lines.append(f"- mode: {'via LAMOrchestrator.process' if meta['via_orchestrator'] else 'direct agent calls'}; "
                 f"LLM: {'live (Ollama)' if meta['live'] else 'stubbed'}")
    lines.append(f"- run at {meta['started']}, {meta['seconds']}s")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    header = "| Conversation | Agent | Properties | Questions | Fields collected per turn | Record fields reused | Rows persisted |"
    if meta["via_orchestrator"]:
        header += " Misrouted turns |"
    lines.append(header)
    lines.append("|" + "---|" * (header.count("|") - 1))
    for run in runs:
        s = run["summary"]
        row = (f"| {run['id']} | {run['agent']} | {s['properties_passed']}/{s['properties_total']} | {s['questions']} | "
               f"{' · '.join(str(n) for n in s['fields_per_turn'])} (={s['fields_total']}) | "
               f"{s['record_fields_reused']}/{s['record_fields_offered']} | {s['rows_persisted']} |")
        if meta["via_orchestrator"]:
            kinds = [f"{i} (pending answer)" for i in s["misrouted_continuation"]]
            kinds += [f"{i} (fresh)" for i in s["misrouted_fresh"]]
            kinds += [f"{i} (RED pre-empted)" for i in s["red_preempted_turns"]]
            row += f" {', '.join(kinds) or '-'} |"
        lines.append(row)
    lines.append("")
    lines.append("## Properties")
    for run in runs:
        lines.append("")
        lines.append(f"### {run['id']} -- {run['title']}")
        lines.append("")
        lines.append("| Turn | Property | Result | Detail |")
        lines.append("|---|---|---|---|")
        for p in run["properties"]:
            detail = str(p["detail"]).replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {p['turn'] or '-'} | {p['name']} | {'PASS' if p['passed'] else '**FAIL**'} | {detail} |")
        lines.append("")
        lines.append("<details><summary>Transcript</summary>")
        lines.append("")
        for t in run["turns"]:
            lines.append(f"**Patient ({t['index']}):** {t['patient']}")
            lines.append("")
            routed = (f" [routed to {t['routed_to']}{', ' + t['misroute_kind'] if t['misroute_kind'] else ''}]"
                      if meta["via_orchestrator"] else "")
            reply = t["reply"].strip() or "*(empty reply)*"
            lines.extend("> " + line for line in reply.splitlines())
            lines.append("")
            lines.append(f"*engine {t['engine']}; triage {t['triage_level']} (engine {t['engine_triage_level']}); "
                         f"asked {t['asked_field'] or '-'}; new fields {', '.join(t['new_fields']) or '-'}{routed}*")
            lines.append("")
        lines.append("</details>")
    return "\n".join(lines) + "\n"


def git_commit(backend_dir: Path) -> str:
    try:
        import subprocess
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(backend_dir),
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend-dir", type=Path, default=DEFAULT_BACKEND)
    parser.add_argument("--label", default=None)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--via-orchestrator", action="store_true")
    parser.add_argument("--only", default=None)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    db_path = isolate_environment()
    backend_dir = args.backend_dir.resolve()
    if args.live and not ollama_reachable():
        print("--live needs a running Ollama server on localhost:11434", file=sys.stderr)
        return 2

    commit = git_commit(backend_dir)
    label = args.label or (f"{commit}{'_orchestrator' if args.via_orchestrator else ''}{'_live' if args.live else ''}")
    conversations = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(CONVERSATIONS_DIR.glob("*.json"))]
    if args.only:
        conversations = [c for c in conversations if args.only in c["id"]]

    print(f"[eval] backend={backend_dir} commit={commit}")
    print(f"[eval] PATIENT_DATABASE_PATH={db_path}; SMTP*/DOCTOR_ALERT* cleared")
    print(f"[eval] {len(conversations)} conversations; via_orchestrator={args.via_orchestrator} live={args.live}")

    backend = Backend(backend_dir, args.verbose)
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    t0 = time.time()
    runs = []
    for conv in conversations:
        run = run_conversation(backend, conv, live=args.live, via_orchestrator=args.via_orchestrator)
        s = run["summary"]
        print(f"  {conv['id']:<38} {s['properties_passed']:>2}/{s['properties_total']:<2} "
              f"q={s['questions']} fields={s['fields_per_turn']} reused={s['record_fields_reused']}/"
              f"{s['record_fields_offered']} rows={s['rows_persisted']}"
              + (f" misrouted={s['misrouted_turns']}" if args.via_orchestrator else ""))
        for p in run["properties"]:
            if not p["passed"]:
                print(f"      FAIL {p['name']}{' @' + str(p['turn']) if p['turn'] else ''}: {p['detail']}")
        runs.append(run)

    where = "this checkout" if backend_dir == DEFAULT_BACKEND.resolve() else f"git worktree at {commit}"
    meta = {"label": label, "backend_dir": where, "commit": commit, "live": args.live,
            "via_orchestrator": args.via_orchestrator, "started": started, "seconds": round(time.time() - t0, 1)}
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / f"{label}.json").write_text(json.dumps({"meta": meta, "runs": runs}, indent=2, default=str),
                                               encoding="utf-8")
    if args.via_orchestrator:
        totals = {key: sum(len(r["summary"][key]) for r in runs)
                  for key in ("misrouted_turns", "misrouted_continuation", "misrouted_fresh", "red_preempted_turns")}
        print(f"[eval] misrouted turns {totals['misrouted_turns']} "
              f"(answers to a pending question {totals['misrouted_continuation']}, "
              f"fresh classification {totals['misrouted_fresh']}); RED pre-empted {totals['red_preempted_turns']}")
    md = markdown(label, meta, runs)
    (RESULTS_DIR / f"{label}.md").write_text(md, encoding="utf-8")
    (REPORTS_DIR / f"{date.today().isoformat()}_agents-conversations-{label}.md").write_text(md, encoding="utf-8")

    passed = sum(r["summary"]["properties_passed"] for r in runs)
    total = sum(r["summary"]["properties_total"] for r in runs)
    print(f"[eval] properties passed {passed}/{total}; results -> {RESULTS_DIR / (label + '.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
