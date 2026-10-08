"""
Recovery Progress Agent test suite.

Architecture under test (feature/agents-proactive rework, see
agents/RECOVERY_AGENT_CHANGES.md): TKA and THA run a deterministic
OBSERVE -> PLAN -> ACT -> UPDATE interview (recovery_state.py /
recovery_logic.py / recovery_integration.py, wired together in
agents.specialized_agents.RecoveryProgressAgent). Milestones come from
agents/data/recovery_milestones.json (every entry sourced from a passage of
eval/eval_corpus.json, plus the retained TKA-03 day-7 ROM entries); memory
comes from agents/patient_memory.py. Each mid-interview turn gives
immediate feedback on what was just supplied and asks exactly ONE question;
the final turn compares every collected value with the nearest checkpoint
at or before the current day, names the next milestone, offers a 'recovery
check', optionally adds an LLM explanation (ChatAgent) and persists the
collected ROM into today's metrics row. GEN (no sourced checkpoint) keeps
the unmodified ChatAgent grounded-guidance path.

Every test function is labeled MOCKED-BOUNDARY or REAL-INTEGRATION:

    MOCKED-BOUNDARY -- mocks ClinicalKnowledgeBase.retrieve_detailed and/or
        ChatAgent.answer_question to prove ONE exact invariant without
        depending on which optional RAG backend happens to be installed.
    REAL-INTEGRATION -- exercises the actual recovery_state / recovery_logic
        / recovery_integration / orchestrator / classifier code, including
        (where noted) the real RAG retrieval, on whichever path (semantic
        chroma or keyword fallback) this environment provides.

Plain-Python script (no pytest dependency), also runnable under pytest via
backend/run_agent_tests.py.

Run directly (from backend/):
    python test_recovery_progress_agent.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch

from lam.orchestrator import LAMOrchestrator
from lam import orchestrator as orchestrator_module
from lam.schemas import IntentLabel, TargetAgent, resolve_procedure_code
from agents.agent_router import AgentRouter, _AGENT_BY_INTENT
from agents.specialized_agents import RecoveryProgressAgent
from agents import recovery_state
from agents import recovery_logic as rl
from agents import recovery_integration as ri
from rag.knowledge_base import ClinicalKnowledgeBase

_FAILURES: List[str] = []


def _check(condition: bool, message: str) -> None:
    """A failed check is a REAL failure: it is recorded in _FAILURES (for the
    main() summary) and raises AssertionError, so pytest marks the test as
    failed instead of silently passing it. main() catches the AssertionError
    per test so the script runner still runs every test and prints a summary."""
    if not condition:
        _FAILURES.append(message)
        print(f"    !! FAILED: {message}")
        raise AssertionError(message)


def _run(test_fn) -> None:
    """main()-only wrapper: keeps the plain-script runner going past a failed
    test (the failure is already recorded in _FAILURES by _check)."""
    try:
        test_fn()
    except AssertionError as exc:
        if str(exc) not in _FAILURES:
            _FAILURES.append(str(exc))
            print(f"    !! FAILED: {exc}")
        print()


def _section(title: str) -> None:
    print("=" * 78)
    print(title)
    print("=" * 78)


# ============================================================================
# SHARED TEST HELPERS
# ============================================================================

def _reset_recovery_store() -> None:
    """Every test that touches recovery_state must reset the process-scoped
    in-memory store first -- it is a module-level global, not per-test."""
    recovery_state._clear_all_state_for_tests()


def _dynamic_surgery_date(days_ago: int) -> str:
    """
    Build a surgery_date_raw string whose derive_effective_postop_day()
    result is deterministic REGARDLESS of what day this test actually runs
    on: (today - days_ago) as surgery date gives effective day (days_ago+1),
    since Day-1 convention makes the surgery date itself Day 1. Uses the
    naive-local ISO shape actually sent by the Flutter client (see
    recovery_integration.py's own convention notes).
    """
    d = date.today() - timedelta(days=days_ago)
    return f"{d.isoformat()}T00:00:00.000"


class _FakeChunk:
    """Minimal stand-in for rag.knowledge_base.RetrievedChunk -- only the
    attributes build_recovery_evidence_from_chunk() actually reads."""
    def __init__(self, doc_id: str, procedure: str, days: str):
        self.doc_id = doc_id
        self.procedure = procedure
        self.days = days


class _FakeDetail:
    def __init__(self, results: List[_FakeChunk]):
        self.results = results


TKA03_CHUNK = _FakeChunk(doc_id="TKA-03", procedure="TKA", days="1-21")
TKA03_EVIDENCE = rl.RecoveryEvidence(source_id="TKA-03", procedure="TKA", days_raw="1-21")


class _RetrievalSpy:
    """MOCKED-BOUNDARY helper: replaces ClinicalKnowledgeBase.retrieve_detailed
    with a canned TKA-03 result while recording every call for count/argument
    assertions. Used ONLY in tests explicitly labeled MOCKED-BOUNDARY."""
    def __init__(self, results: Optional[List[_FakeChunk]] = None):
        self.calls: List[Dict[str, Any]] = []
        self._results = results if results is not None else [TKA03_CHUNK]

    def __call__(self, query_text, procedure="TKA", limit=2):
        self.calls.append({"query_text": query_text, "procedure": procedure, "limit": limit})
        return _FakeDetail(list(self._results))

    @property
    def call_count(self) -> int:
        return len(self.calls)


def _stub_answer_question(reply: str = "stub reply", sources: Optional[list] = None):
    calls: List[Dict[str, Any]] = []

    def _fn(**kwargs) -> Dict[str, Any]:
        calls.append(kwargs)
        return {
            "reply": reply,
            "triage_level": "GREEN",
            "is_escalated": False,
            "engine": "Clinical Synthesis Engine",
            "sources": sources or ["Stub Source"],
        }

    return _fn, calls


_FORBIDDEN_TRAJECTORY_PHRASES = ("on track", "above expected", "ahead of schedule", "normal recovery")
_FORBIDDEN_DIRECTIONAL_PHRASES = ("better", "worse", "ahead", "behind")

# Style-pass regression guard: the report-style phrasing the conversational
# rewrite was specifically meant to eliminate (see recovery_integration.py's
# format_assess_message / format_decline_message / format_ask_question).
# None of these should ever appear in a Recovery reply again.
_FORBIDDEN_ROBOTIC_PHRASES = (
    "has been noted",
    "reported metric",
    "supplied value",
    "there isn't a stated target to compare against yet",
    "your reported",
    "noted",
)


def _assert_no_forbidden_trajectory_language(reply: str, label: str) -> None:
    lower = reply.lower()
    for phrase in _FORBIDDEN_TRAJECTORY_PHRASES:
        _check(phrase not in lower, f"{label}: forbidden trajectory phrase {phrase!r} leaked into reply: {reply!r}")


def _assert_no_forbidden_directional_language(reply: str, label: str) -> None:
    lower = reply.lower()
    for phrase in _FORBIDDEN_DIRECTIONAL_PHRASES:
        _check(phrase not in lower, f"{label}: forbidden directional phrase {phrase!r} leaked into reply: {reply!r}")


def _assert_no_forbidden_robotic_language(reply: str, label: str) -> None:
    lower = reply.lower()
    for phrase in _FORBIDDEN_ROBOTIC_PHRASES:
        _check(phrase not in lower, f"{label}: robotic report-style phrase {phrase!r} leaked into reply: {reply!r}")


# ============================================================================
# 1. POSTOPERATIVE-DAY DERIVATION -- REAL-INTEGRATION (pure function,
#    injectable today=, no mocks). Pass-3 Section 4.
# ============================================================================

def test_postop_day_derivation() -> None:
    _section("1 -- derive_effective_postop_day() [REAL-INTEGRATION, today= pinned]")

    surgery = "2026-09-02T00:00:00.000"
    cases = [
        (date(2026, 9, 2), 1, "same date -> Day 1"),
        (date(2026, 9, 3), 2, "one calendar day later -> Day 2"),
        (date(2026, 9, 7), 6, "Day 6"),
        (date(2026, 9, 8), 7, "Day 7"),
        (date(2026, 9, 9), 8, "Day 8"),
    ]
    for today, expected, label in cases:
        got = ri.derive_effective_postop_day(surgery, today=today)
        _check(got == expected, f"{label}: expected {expected}, got {got}")

    # Missing / malformed surgery_date -> None (never guessed).
    _check(ri.derive_effective_postop_day(None, today=date(2026, 9, 8)) is None, "missing surgery_date must return None")
    _check(ri.derive_effective_postop_day("not-a-date", today=date(2026, 9, 8)) is None, "malformed surgery_date must return None")
    _check(ri.derive_effective_postop_day("", today=date(2026, 9, 8)) is None, "empty surgery_date must return None")

    # Integration: missing/malformed surgery_date clears the verified day
    # through RecoverySessionState.clear_verified_day() (not just the raw
    # helper) -- this is what handle() actually relies on.
    _reset_recovery_store()
    state = recovery_state.get_or_create_state(patient_id="PD-1", surgery_date_raw=None, procedure="TKA")
    effective = ri.derive_effective_postop_day(None)
    if effective is not None:
        state.apply_verified_day(effective)
    else:
        state.clear_verified_day()
    _check(state.postop_day_verified is False, "missing surgery_date must leave postop_day_verified False")
    _check(state.effective_postop_day is None, "missing surgery_date must leave effective_postop_day None")

    # Literal calendar-digit preservation across all three input shapes
    # (naive local, 'Z', offset) -- the CHOSEN convention deliberately
    # ignores time-of-day/timezone markers and reads only YYYY-MM-DD.
    pinned_today = date(2026, 9, 12)
    naive = ri.derive_effective_postop_day("2026-09-02T23:30:00.000", today=pinned_today)
    z_form = ri.derive_effective_postop_day("2026-09-02T23:30:00.000Z", today=pinned_today)
    offset_form = ri.derive_effective_postop_day("2026-09-02T23:30:00.000+05:30", today=pinned_today)
    _check(naive == 11, f"naive ISO: expected literal calendar date preserved (Day 11), got {naive}")
    _check(z_form == 11, f"'Z' ISO: expected literal WRITTEN calendar date preserved (Day 11), got {z_form}")
    _check(offset_form == 11, f"offset ISO: expected literal WRITTEN calendar date preserved (Day 11), got {offset_form}")
    _check(naive == z_form == offset_form, "all three input shapes must resolve to the identical calendar date")

    # Accepted limitation (Pass-2 correction, documented in
    # recovery_integration.py): default `today` is the BACKEND HOST's local
    # calendar date, not a patient/app timezone -- there is no such field in
    # this repo. This is NOT asserted as timezone-independent; only that the
    # injectable `today=` keeps the deterministic tests pinned regardless.
    print("    NOTE: default today= is backend-host local date; surgery_date digits are")
    print("    client-written calendar digits. Host/patient timezone agreement is an")
    print("    accepted assumption, not asserted as timezone-independent here.")
    print()


# ============================================================================
# 2. DAY 6/7/8 CHECKPOINT BOUNDARY -- REAL-INTEGRATION (pure recovery_logic,
#    no mocks). Pass-3 Section 5.
# ============================================================================

def test_checkpoint_day_6_7_8_boundary() -> None:
    _section("2 -- Day 6/7/8 checkpoint boundary, flexion=60 [REAL-INTEGRATION]")

    def state_at_day(day: int) -> recovery_state.RecoverySessionState:
        _reset_recovery_store()
        s = recovery_state.get_or_create_state(patient_id=f"CB-{day}", surgery_date_raw="2026-09-02T00:00:00.000", procedure="TKA")
        s.apply_verified_day(day)
        s.set_fact(rl.ROM_FLEXION_DEGREES, 60, effective_postop_day=day)
        return s

    s6 = state_at_day(6)
    cp6 = rl.evaluate_checkpoint(s6, procedure="TKA", metric=rl.ROM_FLEXION_DEGREES, evidence=TKA03_EVIDENCE)
    _check(cp6.supported, "Day 6: expected supported=True")
    _check(cp6.verdict == rl.CheckpointVerdict.TARGET_NOT_YET_DUE, f"Day 6: expected TARGET_NOT_YET_DUE, got {cp6.verdict}")

    s7 = state_at_day(7)
    cp7 = rl.evaluate_checkpoint(s7, procedure="TKA", metric=rl.ROM_FLEXION_DEGREES, evidence=TKA03_EVIDENCE)
    _check(cp7.verdict == rl.CheckpointVerdict.BELOW_STATED_CHECKPOINT, f"Day 7: expected BELOW_STATED_CHECKPOINT, got {cp7.verdict}")

    s8 = state_at_day(8)
    cp8 = rl.evaluate_checkpoint(s8, procedure="TKA", metric=rl.ROM_FLEXION_DEGREES, evidence=TKA03_EVIDENCE)
    _check(cp8.verdict == rl.CheckpointVerdict.BELOW_STATED_CHECKPOINT, f"Day 8: expected BELOW_STATED_CHECKPOINT, got {cp8.verdict}")
    _check(cp8.checkpoint_day == 7, f"Day 8: checkpoint_day must stay 7 (TKA-03's own stated day), got {cp8.checkpoint_day}")
    _check(cp8.effective_postop_day == 8, f"Day 8: effective_postop_day must be 8, got {cp8.effective_postop_day}")

    reply8 = ri.format_assess_message(cp8)
    print(f"    Day 8 reply: {reply8!r}")
    # UPDATED (readability pass): the checkpoint is named in plain words ("the day-7
    # range"), never as "the earlier Post-Op Day 7 checkpoint", and no passage id
    # appears in patient text.
    _check("day-7" in reply8, "Day 8 reply must refer to the day-7 checkpoint, not a Day-8 target")
    _check("earlier Post-Op Day" not in reply8 and "TKA-03" not in reply8, "no checkpoint jargon or passage id in patient text")
    _check("Day 8 checkpoint" not in reply8 and "day-8" not in reply8, "Day 8 reply must not invent a Day-8 checkpoint")
    print()


# ============================================================================
# 3. ASSESSMENT WORDING + NEGATIVE ASSERTIONS -- REAL-INTEGRATION (pure
#    recovery_logic + recovery_integration formatters). Pass-3 Section 10.
# ============================================================================

def test_assessment_wording_and_negative_assertions() -> None:
    _section("3 -- Assessment wording: required phrasing + forbidden trajectory language [REAL-INTEGRATION]")

    def checkpoint_for(day: int, metric: str, value: float) -> rl.CheckpointResult:
        _reset_recovery_store()
        s = recovery_state.get_or_create_state(patient_id=f"W-{day}-{metric}-{value}", surgery_date_raw="2026-09-02T00:00:00.000", procedure="TKA")
        s.apply_verified_day(day)
        s.set_fact(metric, value, effective_postop_day=day)
        return rl.evaluate_checkpoint(s, procedure="TKA", metric=metric, evidence=TKA03_EVIDENCE)

    # Day 6 + flexion 60 -> not yet due, must NOT say "below checkpoint".
    # UPDATED (rework item 4): before day 7 the agent now GIVES the day-7
    # target as the thing to work towards instead of "too early", so the
    # 70-90 range IS stated -- explicitly as the day-7 checkpoint's range,
    # with its source, never as a day-6 target.
    cp = checkpoint_for(6, rl.ROM_FLEXION_DEGREES, 60)
    reply = ri.format_assess_message(cp)
    print(f"    Day6 flex60: {reply!r}")
    _check(cp.verdict == rl.CheckpointVerdict.TARGET_NOT_YET_DUE, "Day6 flex60 must be TARGET_NOT_YET_DUE")
    _check("below" not in reply.lower(), "Day6 flex60 (not yet due) must not say 'below'")
    _check("70" in reply and "90" in reply and "day 7" in reply, "Day6 flex60 must state the DAY-7 target to work towards")
    # UPDATED (readability pass): the source passage id is metadata, never patient text.
    _check("work towards" in reply and "TKA-03" not in reply, "Day6 flex60 must frame the range as the target to work towards without naming a passage id")
    _check("Day 6 checkpoint" not in reply and "day 6 target" not in reply.lower(), "Day6 flex60 must not invent a day-6 checkpoint")
    _assert_no_forbidden_trajectory_language(reply, "Day6 flex60")
    _assert_no_forbidden_robotic_language(reply, "Day6 flex60")

    # Day 7 + flexion 80 -> within 70-90 stated for Post-Op Day 7.
    cp = checkpoint_for(7, rl.ROM_FLEXION_DEGREES, 80)
    reply = ri.format_assess_message(cp)
    print(f"    Day7 flex80: {reply!r}")
    _check(cp.verdict == rl.CheckpointVerdict.MEETS_STATED_CHECKPOINT, "Day7 flex80 must MEET the checkpoint")
    _check("70" in reply and "90" in reply, "Day7 flex80 must state the 70-90 range")
    # UPDATED (readability pass): "the day-7 range", never "Post-Op Day 7" / "earlier".
    _check("day-7" in reply and "earlier" not in reply and "Post-Op Day" not in reply, "Day7 flex80: the checkpoint is named in plain words, never 'earlier'")
    _assert_no_forbidden_trajectory_language(reply, "Day7 flex80")

    # Day 8 + flexion 80 -> within range stated for the EARLIER Day-7 checkpoint.
    cp = checkpoint_for(8, rl.ROM_FLEXION_DEGREES, 80)
    reply = ri.format_assess_message(cp)
    print(f"    Day8 flex80: {reply!r}")
    _check("day-7" in reply and "earlier Post-Op Day" not in reply, "Day8 flex80 must reference the day-7 checkpoint in plain words")
    _assert_no_forbidden_trajectory_language(reply, "Day8 flex80")

    # Day 10 + flexion 80 -> same earlier-Day-7 wording.
    cp = checkpoint_for(10, rl.ROM_FLEXION_DEGREES, 80)
    reply = ri.format_assess_message(cp)
    print(f"    Day10 flex80: {reply!r}")
    _check("day-7" in reply and "earlier Post-Op Day" not in reply, "Day10 flex80 must reference the day-7 checkpoint in plain words")
    _assert_no_forbidden_trajectory_language(reply, "Day10 flex80")

    # Day 10 + flexion 60 -> below the EARLIER Day-7 checkpoint, never "behind recovery".
    cp = checkpoint_for(10, rl.ROM_FLEXION_DEGREES, 60)
    reply = ri.format_assess_message(cp)
    print(f"    Day10 flex60: {reply!r}")
    _check(cp.verdict == rl.CheckpointVerdict.BELOW_STATED_CHECKPOINT, "Day10 flex60 must be BELOW_STATED_CHECKPOINT")
    _check("day-7" in reply and "earlier Post-Op Day" not in reply, "Day10 flex60 must reference the day-7 checkpoint in plain words")
    _check("behind recovery" not in reply.lower(), "Day10 flex60 must not say 'behind recovery'")
    _assert_no_forbidden_trajectory_language(reply, "Day10 flex60")

    # Day 7 + flexion 95 -> exceeds stated range; never "above expected"/"better"/"ahead".
    cp = checkpoint_for(7, rl.ROM_FLEXION_DEGREES, 95)
    reply = ri.format_assess_message(cp)
    print(f"    Day7 flex95: {reply!r}")
    _check(cp.verdict == rl.CheckpointVerdict.EXCEEDS_STATED_RANGE, "Day7 flex95 must EXCEED the stated range")
    _assert_no_forbidden_trajectory_language(reply, "Day7 flex95")
    _assert_no_forbidden_directional_language(reply, "Day7 flex95")

    # Extension 3 -> within stated 0-5 range.
    cp = checkpoint_for(7, rl.ROM_EXTENSION_DEGREES, 3)
    reply = ri.format_assess_message(cp)
    print(f"    Day7 ext3: {reply!r}")
    _check(cp.verdict == rl.CheckpointVerdict.MEETS_STATED_CHECKPOINT, "Day7 ext3 must MEET the checkpoint")
    _check("0" in reply and "5" in reply, "Day7 ext3 must state the 0-5 range")
    _assert_no_forbidden_directional_language(reply, "Day7 ext3")

    # Extension 8 -> outside stated 0-5 range; no directional interpretation.
    cp = checkpoint_for(7, rl.ROM_EXTENSION_DEGREES, 8)
    reply = ri.format_assess_message(cp)
    print(f"    Day7 ext8: {reply!r}")
    _check(cp.verdict == rl.CheckpointVerdict.OUTSIDE_STATED_RANGE, "Day7 ext8 must be OUTSIDE_STATED_RANGE")
    _assert_no_forbidden_directional_language(reply, "Day7 ext8")
    _assert_no_forbidden_trajectory_language(reply, "Day7 ext8")

    for label, r in (
        ("Day6 flex60", ri.format_assess_message(checkpoint_for(6, rl.ROM_FLEXION_DEGREES, 60))),
        ("Day7 flex80", ri.format_assess_message(checkpoint_for(7, rl.ROM_FLEXION_DEGREES, 80))),
        ("Day8 flex80", ri.format_assess_message(checkpoint_for(8, rl.ROM_FLEXION_DEGREES, 80))),
    ):
        _assert_no_forbidden_robotic_language(r, label)
    print()


# ============================================================================
# 4. DECLINE TESTS -- REAL-INTEGRATION (pure recovery_logic +
#    recovery_integration.format_decline_message). Pass-3 Section 11.
# ============================================================================

def test_decline_reasons() -> None:
    _section("4 -- Decline reasons never read as a clinical abnormality [REAL-INTEGRATION]")

    def fresh_verified(patient: str, day: int = 10) -> recovery_state.RecoverySessionState:
        _reset_recovery_store()
        s = recovery_state.get_or_create_state(patient_id=patient, surgery_date_raw="2026-09-02T00:00:00.000", procedure="TKA")
        s.apply_verified_day(day)
        return s

    # Unverified day.
    _reset_recovery_store()
    s = recovery_state.get_or_create_state(patient_id="D-unverified", surgery_date_raw=None, procedure="TKA")
    s.clear_verified_day()
    d = rl.decide_progress_verdict_action(s, procedure="TKA", metric=rl.ROM_FLEXION_DEGREES, evidence=TKA03_EVIDENCE)
    _check(d.action == rl.RecoveryAction.DECLINE_TO_ASSESS and d.reason_code == rl.DecisionReasonCode.DAY_UNVERIFIED, f"unverified day: {d}")

    # UPDATED (rework item 4): the milestone FILE is now the comparison
    # source, so the retrieval-evidence gates (missing / wrong source /
    # wrong procedure / malformed window / day outside window) no longer
    # exist -- inside day 1-365 the agent never declines to assess. A
    # retrieved chunk passed as `evidence` is attribution only and never
    # changes the decision.
    s = fresh_verified("D-no-evidence-still-asks")
    d = rl.decide_progress_verdict_action(s, procedure="TKA", metric=rl.ROM_FLEXION_DEGREES, evidence=None)
    _check(d.action == rl.RecoveryAction.ASK_FOR_INFORMATION, f"no evidence must not block the interview: {d}")
    wrong_source = rl.RecoveryEvidence(source_id="TKA-99", procedure="THA", days_raw="not-a-range")
    s.set_fact(rl.ROM_FLEXION_DEGREES, 80, effective_postop_day=10)
    d = rl.decide_progress_verdict_action(s, procedure="TKA", metric=rl.ROM_FLEXION_DEGREES, evidence=wrong_source)
    _check(d.action == rl.RecoveryAction.ASSESS_SUPPORTED_METRIC, f"a mismatched retrieved chunk must not block the assessment: {d}")

    # Day 22 was outside TKA-03's 1-21 window and used to decline; it now
    # compares against the nearest checkpoint at or before day 22 (day 21,
    # EV-TKA-REC-02 -- words only, no number, so the verdict is STATE_ONLY).
    _reset_recovery_store()
    s = recovery_state.get_or_create_state(patient_id="D-day22", surgery_date_raw="2026-08-01T00:00:00.000", procedure="TKA")
    s.apply_verified_day(22)
    s.set_fact(rl.ROM_FLEXION_DEGREES, 95, effective_postop_day=22)
    d = rl.decide_progress_verdict_action(s, procedure="TKA", metric=rl.ROM_FLEXION_DEGREES, evidence=TKA03_EVIDENCE)
    _check(d.action == rl.RecoveryAction.ASSESS_SUPPORTED_METRIC, f"day 22 must be assessed, not declined: {d}")
    cp22 = rl.evaluate_checkpoint(s, procedure="TKA", metric=rl.ROM_FLEXION_DEGREES)
    _check(cp22.checkpoint_day == 21 and cp22.source_id == "EV-TKA-REC-02", f"day 22 must use the day-21 checkpoint: {cp22}")
    _check(cp22.verdict == rl.CheckpointVerdict.STATE_ONLY, f"day-21 flexion entry carries no number -> STATE_ONLY, got {cp22.verdict}")
    reply22 = ri.format_assess_message(cp22)
    print(f"    Day22 flex95: {reply22!r}")
    # UPDATED (readability pass): the source id stays in CheckpointResult.source_id (metadata), never in the text.
    _check("gives no number" in reply22 and "EV-TKA-REC-02" not in reply22 and "day-21" in reply22, "a words-only checkpoint says so in plain words, no passage id")
    _assert_no_forbidden_trajectory_language(reply22, "Day22 flex95")

    # A metric with no entry for the procedure (knee ROM for THA) is the
    # only "unsupported" decline left.
    _reset_recovery_store()
    s = recovery_state.get_or_create_state(patient_id="D-tha-rom", surgery_date_raw="2026-09-02T00:00:00.000", procedure="THA")
    s.apply_verified_day(10)
    d = rl.decide_progress_verdict_action(s, procedure="THA", metric=rl.ROM_FLEXION_DEGREES)
    _check(d.reason_code == rl.DecisionReasonCode.NO_SUPPORTED_METRIC_FOR_PROCEDURE, f"THA knee ROM: {d}")

    # Invalid metric values: negative, absurdly large, non-numeric.
    for bad_value, label in ((-5, "negative"), (999, "absurdly large"), ("not-a-number", "non-numeric")):
        s = fresh_verified(f"D-invalid-{label}")
        s.set_fact(rl.ROM_FLEXION_DEGREES, bad_value, effective_postop_day=10)
        cp = rl.evaluate_checkpoint(s, procedure="TKA", metric=rl.ROM_FLEXION_DEGREES, evidence=TKA03_EVIDENCE)
        _check(not cp.supported and cp.reason_code == rl.ReasonCode.INVALID_METRIC_VALUE, f"{label} value {bad_value!r}: {cp}")
        reply = ri.format_decline_message(rl.DecisionReasonCode.INVALID_METRIC_VALUE, metric=rl.ROM_FLEXION_DEGREES, evidence=TKA03_EVIDENCE)
        _check("doesn't look usable" in reply, f"{label} value decline text must not claim a clinical abnormality")
        _assert_no_forbidden_robotic_language(reply, f"{label} value decline")
    print()


# ============================================================================
# 5. EXTRACTION REGRESSION TESTS -- REAL-INTEGRATION (pure
#    recovery_logic.extract_and_apply). Pass-3 Section 12.
# ============================================================================

def test_extraction_regressions() -> None:
    _section("5 -- Extraction regressions [REAL-INTEGRATION]")

    def fresh(patient: str) -> recovery_state.RecoverySessionState:
        _reset_recovery_store()
        return recovery_state.get_or_create_state(patient_id=patient, surgery_date_raw="2026-09-02T00:00:00.000", procedure="TKA")

    # walker -> cane, latest wins.
    s = fresh("E1")
    r = rl.extract_and_apply("I used a walker before, but now I use a cane.", s)
    _check(len(r.applied_facts) == 1 and r.applied_facts[0].value == "cane", f"walker->cane latest-wins: {r.applied_facts}")

    # past walker + current cane (different phrasing).
    s = fresh("E2")
    r = rl.extract_and_apply("I was using a walker previously; now I use a cane.", s)
    _check(len(r.applied_facts) == 1 and r.applied_facts[0].value == "cane", f"past walker + current cane: {r.applied_facts}")

    # walker negation ("not using the walker anymore" -> independent).
    s = fresh("E3")
    r = rl.extract_and_apply("I'm not using the walker anymore.", s)
    _check(len(r.applied_facts) == 1 and r.applied_facts[0].value == "independent", f"walker negation: {r.applied_facts}")

    # "Actually it's 70, not 80." with pending flexion -> applies 70 to flexion.
    s = fresh("E4")
    s.mark_pending(rl.ROM_FLEXION_DEGREES)
    r = rl.extract_and_apply("Actually it's 70, not 80.", s)
    _check(
        r.applied_facts == (rl.ExtractedFact(rl.ROM_FLEXION_DEGREES, 70.0),),
        f"correction attributed to pending flexion: {r.applied_facts}",
    )

    # "Actually it's 70, not 80." with pending extension -> applies 70 to extension.
    s = fresh("E4b")
    s.mark_pending(rl.ROM_EXTENSION_DEGREES)
    r = rl.extract_and_apply("Actually it's 70, not 80.", s)
    _check(
        r.applied_facts == (rl.ExtractedFact(rl.ROM_EXTENSION_DEGREES, 70.0),),
        f"correction attributed to pending extension: {r.applied_facts}",
    )

    # Multiple facts in one message.
    s = fresh("E5")
    r = rl.extract_and_apply("I can bend to 80 degrees, my pain is 3/10, and I am walking independently.", s)
    applied = {f.field_name: f.value for f in r.applied_facts}
    _check(
        applied == {rl.MOBILITY_STATUS: "independent", rl.ROM_FLEXION_DEGREES: 80.0, rl.PAIN_SCORE: 3},
        f"multi-fact single message: {applied}",
    )

    # Bare "I don't know" only applies to the pending field.
    s = fresh("E6a")
    r = rl.extract_and_apply("I dont know", s)
    _check(r.marked_unknown_fields == (), "bare 'I don't know' with NO pending field must be a no-op")
    s2 = fresh("E6b")
    s2.mark_pending(rl.ROM_FLEXION_DEGREES)
    r2 = rl.extract_and_apply("I dont know", s2)
    _check(r2.marked_unknown_fields == (rl.ROM_FLEXION_DEGREES,), f"bare 'I don't know' with pending flexion: {r2.marked_unknown_fields}")

    # Field-specific "don't know" targets that field regardless of pending.
    s = fresh("E7")
    r = rl.extract_and_apply("I don't know my bend angle.", s)
    _check(r.marked_unknown_fields == (rl.ROM_FLEXION_DEGREES,), f"field-specific unknown: {r.marked_unknown_fields}")

    # Ambiguous walker + cane -> no arbitrary overwrite, prior fact untouched.
    s = fresh("E8")
    s.set_fact(rl.MOBILITY_STATUS, "walker", effective_postop_day=None)
    r = rl.extract_and_apply("I am using a walker and a cane.", s)
    _check(len(r.applied_facts) == 0, "ambiguous walker+cane must not apply any fact")
    _check(len(r.ambiguous_fields) == 1 and r.ambiguous_fields[0].field_name == rl.MOBILITY_STATUS, f"ambiguous field reported: {r.ambiguous_fields}")
    _check(s.get_fact(rl.MOBILITY_STATUS).value == "walker", "ambiguity must not overwrite the prior stored fact")

    # "Same as yesterday." -- only resolves with a pending field AND a prior
    # value tagged exactly current_day - 1.
    s = fresh("E9")
    s.apply_verified_day(6)
    s.set_fact(rl.ROM_FLEXION_DEGREES, 65, effective_postop_day=6)
    s.apply_verified_day(7)
    s.mark_pending(rl.ROM_FLEXION_DEGREES)
    r = rl.extract_and_apply("Same as yesterday.", s)
    _check(r.applied_facts == (rl.ExtractedFact(rl.ROM_FLEXION_DEGREES, 65),), f"same-as-yesterday resolved: {r.applied_facts}")
    _check(s.get_fact(rl.ROM_FLEXION_DEGREES).effective_postop_day == 7, "same-as-yesterday must retag the carried-forward value to TODAY's day")

    # "Same as yesterday." with no pending field -> true no-op.
    s = fresh("E10")
    r = rl.extract_and_apply("Same as yesterday.", s)
    _check(r.applied_facts == () and r.marked_unknown_fields == (), "same-as-yesterday with no pending field must be a true no-op")
    _check(s.pending_field is None, "same-as-yesterday no-op must not invent a pending field")
    print("    CONFIRMED: extraction regressions match the approved recovery_logic.py behavior.")
    print()


# ============================================================================
# 6. EXECUTOR STATE-TRANSITION TESTS -- MOCKED-BOUNDARY (retrieval mocked to
#    a canned TKA-03 chunk so decisions are deterministic). Pass-3 Section 7.
# ============================================================================

def test_executor_state_transitions() -> None:
    _section("6 -- Executor state transitions (ASK / AWAIT / retry / ASSESS / decline) [MOCKED-BOUNDARY: retrieval]")

    surgery_date = _dynamic_surgery_date(9)  # Day 10

    # ASK_FOR_INFORMATION -> mark_pending(metric), status PENDING, pending_field == metric.
    _reset_recovery_store()
    spy = _RetrievalSpy()
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy):
        result = RecoveryProgressAgent.handle(
            patient_id="EX-1", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="How is my recovery going?", procedure="TKA", surgery_date=surgery_date,
        )
    state = recovery_state.peek_state(patient_id="EX-1", surgery_date_raw=surgery_date, procedure="TKA")
    _check(state is not None, "ASK turn must create Recovery state")
    _check(state.pending_field == rl.ROM_FLEXION_DEGREES, f"ASK turn must set pending_field to flexion, got {state.pending_field}")
    _check(state.status_of(rl.ROM_FLEXION_DEGREES) == recovery_state.FieldStatus.PENDING, "ASK turn must set flexion status to PENDING")
    _check(result["engine"] == RecoveryProgressAgent.ENGINE_NAME, f"ASK turn engine: {result['engine']}")

    # AWAIT_INFORMATION -> pending state unchanged, no duplicate transition.
    ask_count_before = state.ask_count_of(rl.ROM_FLEXION_DEGREES)
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy):
        RecoveryProgressAgent.handle(
            patient_id="EX-1", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="What's the weather like today?", procedure="TKA", surgery_date=surgery_date,
        )
    _check(state.pending_field == rl.ROM_FLEXION_DEGREES, "AWAIT turn must not change pending_field")
    _check(state.ask_count_of(rl.ROM_FLEXION_DEGREES) == ask_count_before, "AWAIT turn must not touch ask_count")

    # RETRY SEQUENCE: two "I don't know" answers -> RETRY_EXHAUSTED -> UNAVAILABLE.
    _reset_recovery_store()
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy):
        RecoveryProgressAgent.handle(  # Turn 1: asks flexion
            patient_id="EX-2", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="How is my recovery going?", procedure="TKA", surgery_date=surgery_date,
        )
        RecoveryProgressAgent.handle(  # Turn 2: "I don't know." -> retry remaining
            patient_id="EX-2", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="I don't know.", procedure="TKA", surgery_date=surgery_date,
        )
    state2 = recovery_state.peek_state(patient_id="EX-2", surgery_date_raw=surgery_date, procedure="TKA")
    # NOTE: within ONE turn, extract_and_apply()'s mark_unknown() sets UNKNOWN
    # first, but since a retry remains, decide_progress_verdict_action()
    # returns ASK_FOR_INFORMATION and the executor immediately calls
    # mark_pending() again to re-ask in that SAME response -- so by the time
    # handle() returns, status is legitimately back to PENDING (awaiting the
    # just-re-asked question), not UNKNOWN. ask_count_of() is the persistent
    # signal that one non-answer has already been recorded; UNKNOWN is only
    # ever observable mid-turn, between extraction and the executor's own
    # re-ask, never in state a caller reads after handle() returns.
    _check(state2.pending_field == rl.ROM_FLEXION_DEGREES, "after 1 'I don't know': field must be re-asked (pending_field == flexion)")
    _check(state2.status_of(rl.ROM_FLEXION_DEGREES) == recovery_state.FieldStatus.PENDING, "after 1 'I don't know': status must be PENDING again (this turn re-asked)")
    _check(state2.ask_count_of(rl.ROM_FLEXION_DEGREES) == 1, "after 1 'I don't know': ask_count must be 1 (the persistent retry signal)")

    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy):
        RecoveryProgressAgent.handle(  # Turn 3: agent re-asks (AWAIT/ASK again since UNKNOWN w/ retry remaining) -> supply another "don't know"
            patient_id="EX-2", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="I don't know.", procedure="TKA", surgery_date=surgery_date,
        )
    _check(state2.status_of(rl.ROM_FLEXION_DEGREES) == recovery_state.FieldStatus.UNAVAILABLE, f"after 2nd 'I don't know': expected UNAVAILABLE, got {state2.status_of(rl.ROM_FLEXION_DEGREES)}")

    # Next decision for the same metric must be FIELD_UNAVAILABLE, not RETRY_EXHAUSTED again.
    d = rl.decide_progress_verdict_action(state2, procedure="TKA", metric=rl.ROM_FLEXION_DEGREES, evidence=TKA03_EVIDENCE)
    _check(d.reason_code == rl.DecisionReasonCode.FIELD_UNAVAILABLE, f"post-exhaustion decision must be FIELD_UNAVAILABLE, got {d.reason_code}")

    # UPDATED (rework items 3/4): an assessed metric is fed back AND the next
    # missing metric is asked in the SAME turn, so after a flexion-only
    # message extension is now PENDING (asked), while every metric that was
    # neither supplied nor asked stays untouched.
    _reset_recovery_store()
    s3 = recovery_state.get_or_create_state(patient_id="EX-3", surgery_date_raw=surgery_date, procedure="TKA")
    s3.apply_verified_day(10)
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy):
        RecoveryProgressAgent.handle(
            patient_id="EX-3", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="I can bend to about 80 degrees.", procedure="TKA", surgery_date=surgery_date,
        )
    _check(s3.status_of(rl.ROM_EXTENSION_DEGREES) == recovery_state.FieldStatus.PENDING, "flexion assessed -> extension is asked next (PENDING)")
    _check(s3.pending_field == rl.ROM_EXTENSION_DEGREES, "exactly one pending question after the flexion turn")
    for untouched in (rl.MOBILITY_STATUS, rl.WALKING_DURATION_MINUTES, rl.STAIRS):
        _check(s3.status_of(untouched) == recovery_state.FieldStatus.NEVER_ASKED, f"ASSESS on flexion must not mutate {untouched}")

    # Evidence/day decline must perform NO interview mutation.
    _reset_recovery_store()
    s4 = recovery_state.get_or_create_state(patient_id="EX-4", surgery_date_raw=None, procedure="TKA")
    s4.clear_verified_day()  # unverified day -> DAY_UNVERIFIED decline
    pending_before = s4.pending_field
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy):
        RecoveryProgressAgent.handle(
            patient_id="EX-4", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="How is my recovery going?", procedure="TKA", surgery_date=None,
        )
    _check(s4.pending_field == pending_before, "evidence/day decline must not set a pending_field")
    _check(s4.status_of(rl.ROM_FLEXION_DEGREES) == recovery_state.FieldStatus.NEVER_ASKED, "evidence/day decline must leave flexion status NEVER_ASKED")
    print()


# ============================================================================
# 7. IMMEDIATE METRIC ASSESSMENT (end-to-end) -- MOCKED-BOUNDARY (retrieval
#    mocked). Pass-3 Section 6 -- the primary acceptance test.
# ============================================================================

def test_immediate_metric_assessment_end_to_end() -> None:
    _section("7 -- Immediate metric assessment: flexion supplied must be assessed, not skipped [MOCKED-BOUNDARY: retrieval]")

    surgery_date = _dynamic_surgery_date(9)  # Day 10, inside TKA-03's 1-21 window, past Day-7 checkpoint
    spy = _RetrievalSpy()

    _reset_recovery_store()
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy):
        RecoveryProgressAgent.handle(  # Turn 1: generic opener -> asks flexion
            patient_id="IM-1", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="How is my recovery going?", procedure="TKA", surgery_date=surgery_date,
        )
        state = recovery_state.peek_state(patient_id="IM-1", surgery_date_raw=surgery_date, procedure="TKA")
        _check(state.pending_field == rl.ROM_FLEXION_DEGREES, "Turn 1 must ask flexion")
        _check(state.status_of(rl.ROM_EXTENSION_DEGREES) == recovery_state.FieldStatus.NEVER_ASKED, "extension must start NEVER_ASKED")

        result2 = RecoveryProgressAgent.handle(  # Turn 2: patient supplies flexion
            patient_id="IM-1", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="I can bend to around 80 degrees.", procedure="TKA", surgery_date=surgery_date,
        )

    reply2 = result2["reply"]
    print(f"    Turn 2 reply: {reply2!r}")
    _check(state.is_current(rl.ROM_FLEXION_DEGREES), "flexion must become current after Turn 2")
    _check("day-7" in reply2 and "earlier Post-Op Day" not in reply2, "Turn 2 reply must reference the day-7 checkpoint in plain words")
    # UPDATED (rework items 3/4): the flexion verdict is given immediately
    # AND the next missing metric (extension) is asked in the same reply --
    # one tracked question per turn, never a second verdict.
    _check(reply2.count("?") == 1, f"Turn 2 must ask exactly ONE question, got {reply2!r}")
    _check(state.pending_field == rl.ROM_EXTENSION_DEGREES, "Turn 2 must leave extension as the one pending question")
    _check(state.status_of(rl.ROM_EXTENSION_DEGREES) == recovery_state.FieldStatus.PENDING, "extension must be PENDING after Turn 2")
    _assert_no_forbidden_trajectory_language(reply2, "Turn 2 (flexion assess)")

    # A LATER appropriate progress-verdict turn (nothing new supplied) may
    # now ask extension.
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy):
        result3 = RecoveryProgressAgent.handle(
            patient_id="IM-1", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="How is my recovery going overall?", procedure="TKA", surgery_date=surgery_date,
        )
    _check(state.pending_field == rl.ROM_EXTENSION_DEGREES, f"Turn 3 (no new metric) must now ask extension, pending_field={state.pending_field}")
    print(f"    Turn 3 reply: {result3['reply']!r}")

    # SYMMETRIC CASE: extension supplied this turn, flexion missing ->
    # extension is assessed, flexion is not asked in the same response.
    _reset_recovery_store()
    s_sym = recovery_state.get_or_create_state(patient_id="IM-2", surgery_date_raw=surgery_date, procedure="TKA")
    s_sym.apply_verified_day(10)
    s_sym.mark_pending(rl.ROM_EXTENSION_DEGREES)
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy):
        result_sym = RecoveryProgressAgent.handle(
            patient_id="IM-2", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="I can straighten to about 3 degrees.", procedure="TKA", surgery_date=surgery_date,
        )
    reply_sym = result_sym["reply"]
    print(f"    Extension-symmetry reply: {reply_sym!r}")
    _check(s_sym.is_current(rl.ROM_EXTENSION_DEGREES), "extension must become current")
    # UPDATED (rework items 3/4): the extension verdict comes first, then
    # the one missing ROM metric (flexion) is asked -- a verdict for
    # extension, a QUESTION for flexion, never a flexion verdict.
    _check("extension of 3°" in reply_sym and "0°-5°" in reply_sym, "extension-assess reply must state the extension verdict")
    _check(reply_sym.count("?") == 1 and s_sym.pending_field == rl.ROM_FLEXION_DEGREES, "then exactly one question, about flexion")
    _check("flexion of" not in reply_sym.lower(), "no flexion verdict may be invented from nothing")
    print()


# ============================================================================
# 8. MULTI-FACT / ONE-ACTION -- MOCKED-BOUNDARY (retrieval mocked).
#    Pass-3 Section 17.
# ============================================================================

def test_multi_fact_one_action() -> None:
    _section("8 -- One message supplies both flexion and extension: both stored, ONE verdict [MOCKED-BOUNDARY: retrieval]")

    surgery_date = _dynamic_surgery_date(9)  # Day 10
    spy = _RetrievalSpy()

    _reset_recovery_store()
    state = recovery_state.get_or_create_state(patient_id="MF-1", surgery_date_raw=surgery_date, procedure="TKA")
    state.apply_verified_day(10)
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy):
        result = RecoveryProgressAgent.handle(
            patient_id="MF-1", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="I can bend to 80 degrees and straighten to 3 degrees.",
            procedure="TKA", surgery_date=surgery_date,
        )
    reply = result["reply"]
    print(f"    Multi-fact reply: {reply!r}")
    _check(state.is_current(rl.ROM_FLEXION_DEGREES), "flexion fact must be stored and current")
    _check(state.is_current(rl.ROM_EXTENSION_DEGREES), "extension fact must ALSO be stored and current (not lost)")
    _check("day-7" in reply and "earlier Post-Op Day" not in reply, "single response must assess against the day-7 checkpoint")
    # UPDATED (rework item 3 -- multi-slot): several values VOLUNTEERED in
    # one message are all accepted and all fed back (flexion first, in
    # canonical order), and only what is still missing is asked -- ONE
    # question (walking aid), never a question about either ROM value.
    _check(reply.index("flexion of 80°") < reply.index("extension of 3°"), "both values are fed back, flexion first")
    _check(reply.count("?") == 1 and state.pending_field == rl.MOBILITY_STATUS, f"exactly one question, about the next missing metric: {state.pending_field}")
    _check("how many degrees" not in reply.lower(), "neither ROM value may be asked again")
    print("    CONFIRMED: both volunteered values accepted and compared in one reply; one question about what is still missing.")
    print()


# ============================================================================
# 9. SINGLE RETRIEVAL PER PROGRESS-VERDICT TURN -- MOCKED-BOUNDARY (call-count
#    spy). Pass-3 Section 8.
# ============================================================================

def test_single_retrieval_per_turn() -> None:
    _section("9 -- Retrieval budget: no Recovery-owned retrieval on interview turns; ONE ChatAgent call on the final turn [MOCKED-BOUNDARY]")

    # UPDATED (rework item 1): the milestone FILE is the comparison source,
    # so interview turns no longer retrieve anything themselves -- sources
    # on an assess turn come from the file's entries. The only retrieval
    # happens inside ChatAgent on the FINAL turn (exactly one call), where
    # the model may add an explanation above the deterministic block.
    surgery_date = _dynamic_surgery_date(9)  # Day 10

    # A. ASK turn: no retrieval, no LLM.
    _reset_recovery_store()
    spy_a = _RetrievalSpy()
    chat_fn, chat_calls = _stub_answer_question()
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy_a), \
         patch("agents.chat_agent.ChatAgent.answer_question", side_effect=chat_fn):
        RecoveryProgressAgent.handle(
            patient_id="RC-A", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="How is my recovery going?", procedure="TKA", surgery_date=surgery_date,
        )
    _check(spy_a.call_count == 0, f"ASK turn: expected no Recovery-owned retrieve_detailed() call, got {spy_a.call_count}")
    _check(len(chat_calls) == 0, "ASK turn: no ChatAgent call")

    # B. ASSESS turn: sources come from the milestone file (TKA-03 for day-7 flexion).
    _reset_recovery_store()
    state = recovery_state.get_or_create_state(patient_id="RC-B", surgery_date_raw=surgery_date, procedure="TKA")
    state.apply_verified_day(10)
    state.mark_pending(rl.ROM_FLEXION_DEGREES)
    spy_b = _RetrievalSpy()
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy_b), \
         patch("agents.chat_agent.ChatAgent.answer_question", side_effect=chat_fn):
        result_b = RecoveryProgressAgent.handle(
            patient_id="RC-B", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="I can bend to around 80 degrees.", procedure="TKA", surgery_date=surgery_date,
        )
    _check(spy_b.call_count == 0, f"ASSESS turn: expected no Recovery-owned retrieval, got {spy_b.call_count}")
    _check(result_b["sources"] == ["TKA-03"], f"ASSESS turn: the milestone entry's source must be attributed, got {result_b['sources']}")

    # C. FINAL turn: every asked metric already current -> exactly one ChatAgent call.
    _reset_recovery_store()
    state_c = recovery_state.get_or_create_state(patient_id="RC-C", surgery_date_raw=surgery_date, procedure="TKA")
    state_c.apply_verified_day(10)
    for metric, value in ((rl.ROM_FLEXION_DEGREES, 80), (rl.ROM_EXTENSION_DEGREES, 3), (rl.MOBILITY_STATUS, "cane"),
                          (rl.WALKING_DURATION_MINUTES, 15.0), (rl.STAIRS, "one_at_a_time")):
        state_c.set_fact(metric, value, effective_postop_day=10)
    chat_fn_c, chat_calls_c = _stub_answer_question(reply="")
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy_b), \
         patch("agents.chat_agent.ChatAgent.answer_question", side_effect=chat_fn_c):
        result_c = RecoveryProgressAgent.handle(
            patient_id="RC-C", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="How is my recovery going?", procedure="TKA", surgery_date=surgery_date,
        )
    _check(len(chat_calls_c) == 1, f"FINAL turn: exactly one ChatAgent call, got {len(chat_calls_c)}")
    _check("Here's how things compare" in result_c["reply"], "FINAL turn must carry the deterministic comparison block")
    _check("TKA-03" in result_c["sources"] and "EV-TKA-REC-01" in result_c["sources"], f"FINAL turn sources come from the milestone entries used: {result_c['sources']}")
    print()


# ============================================================================
# 10. REAL KEYWORD-FALLBACK RETRIEVAL -- REAL-INTEGRATION (no mock of
#    retrieve_detailed). Pass-3 Section 9.
# ============================================================================

def test_real_keyword_fallback_retrieval() -> None:
    _section("10 -- Real retrieval for a bare continuation reply, on whichever path this environment provides [REAL-INTEGRATION]")

    # UPDATED: this test used to require retrieval_path == "keyword_fallback"
    # and failed as soon as chromadb/sentence-transformers were installed
    # (the path became "semantic_chroma"). The CONTRACT it guards is about
    # the RESULT, not the path: the hint-augmented query must retrieve
    # TKA-03 on the real knowledge base. The path is printed as a
    # disclosure only, so the test passes on both retrieval paths.
    bare_query = "80 degrees"
    bare_detail = ClinicalKnowledgeBase.retrieve_detailed(bare_query, procedure="TKA", limit=2)
    print(f"    bare query {bare_query!r} -> path={bare_detail.retrieval_path} n_results={len(bare_detail.results)}")
    _check(bare_detail.retrieval_path in ("keyword_fallback", "semantic_chroma"), f"unexpected retrieval path {bare_detail.retrieval_path!r}")
    if bare_detail.retrieval_path == "keyword_fallback":
        # Only the keyword path is guaranteed to return nothing for a bare
        # number; the semantic path may legitimately return nearest chunks.
        _check(len(bare_detail.results) == 0, "bare '80 degrees' must retrieve NOTHING via keyword fallback (motivates the hint augmentation)")

    # recovery_integration's hint: augment with a metric-specific phrase
    # built from the corpus's OWN vocabulary before the real retrieval.
    augmented_query = ri.build_retrieval_query(bare_query, rl.ROM_FLEXION_DEGREES)
    print(f"    augmented query -> {augmented_query!r}")
    augmented_detail = ClinicalKnowledgeBase.retrieve_detailed(augmented_query, procedure="TKA", limit=2)
    print(f"    augmented -> path={augmented_detail.retrieval_path} n_results={len(augmented_detail.results)}")
    _check(len(augmented_detail.results) >= 1, "augmented query must retrieve at least one chunk")
    _check(
        any(r.doc_id == "TKA-03" for r in augmented_detail.results),
        f"augmented query must retrieve TKA-03, got {[r.doc_id for r in augmented_detail.results]}",
    )
    _check(all(r.procedure in ("TKA", "All") for r in augmented_detail.results), "procedure isolation must hold on this path too")
    print(f"    DISCLOSURE: retrieval path exercised here was {augmented_detail.retrieval_path!r}; the assertions are path-independent.")
    print()


# ============================================================================
# 11. CONTINUATION HELPER TESTS -- REAL-INTEGRATION (recovery_state +
#    recovery_integration, no mocks). Pass-3 Section 13.
# ============================================================================

def test_continuation_helper() -> None:
    _section("11 -- check_recovery_continuation() [REAL-INTEGRATION]")

    surgery_date = "2026-09-02T00:00:00.000"

    def state_with_pending_flexion(patient: str) -> None:
        _reset_recovery_store()
        s = recovery_state.get_or_create_state(patient_id=patient, surgery_date_raw=surgery_date, procedure="TKA")
        s.mark_pending(rl.ROM_FLEXION_DEGREES)

    for msg in ("80 degrees", "I can bend my knee to around 80 degrees.", "I don't know.", "Same as yesterday."):
        state_with_pending_flexion("CT-1")
        matched = ri.check_recovery_continuation(patient_id="CT-1", surgery_date_raw=surgery_date, procedure="TKA", user_message=msg)
        _check(matched is True, f"pending flexion + {msg!r} must be a Recovery continuation")

    for msg in ("My wound is red and leaking.", "I forgot to take my medication."):
        state_with_pending_flexion("CT-2")
        matched = ri.check_recovery_continuation(patient_id="CT-2", surgery_date_raw=surgery_date, procedure="TKA", user_message=msg)
        _check(matched is False, f"pending flexion + off-topic {msg!r} must NOT force Recovery continuation")

    # No Recovery state at all -> continuation False, and it must never CREATE state.
    _reset_recovery_store()
    matched_no_state = ri.check_recovery_continuation(
        patient_id="CT-3-NO-STATE", surgery_date_raw=surgery_date, procedure="TKA", user_message="80 degrees",
    )
    _check(matched_no_state is False, "no existing Recovery state must return False")
    proof = recovery_state.peek_state(patient_id="CT-3-NO-STATE", surgery_date_raw=surgery_date, procedure="TKA")
    _check(proof is None, "check_recovery_continuation must NEVER create Recovery state as a side effect (peek_state must still be None)")
    print()


# ============================================================================
# 12. REAL CLASSIFIER MISROUTE REGRESSION -- REAL-INTEGRATION (real
#    IntentClassifier + real orchestrator continuation hook + real keyword-
#    fallback retrieval). Pass-3 Section 14.
# ============================================================================

def test_real_classifier_bend_misroute_regression() -> None:
    _section("12 -- Real classifier 'bend' misroute regression: continuation must intercept BEFORE classification [REAL-INTEGRATION]")

    from lam.intent_classifier import IntentClassifier
    from lam.schemas import LAMContext

    message = "I can bend my knee to around 80 degrees."

    # First prove the underlying misroute risk is real: a FRESH classification
    # (no Recovery continuation context at all) maps "bend" to REHABILITATION.
    ctx = LAMContext(
        patient_id="MR-PROBE", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
        postop_day=10, user_message=message, surgery_date=None, chat_history=[],
    )
    fresh_classification = IntentClassifier.classify_detailed(query=message, context=ctx)
    print(f"    fresh classification (no continuation context): intent={fresh_classification.intent} path={fresh_classification.decision_path}")
    _check(
        fresh_classification.intent == IntentLabel.REHABILITATION,
        f"PRECONDITION: expected a fresh classification of {message!r} to be REHABILITATION (the misroute this hook must prevent), got {fresh_classification.intent}",
    )

    # Now set up an existing Recovery episode with flexion pending and run the
    # REAL orchestrator (real SafetyTriageEngine, real ScopeValidator, real
    # check_recovery_continuation, real IntentClassifier -- only
    # ClinicalKnowledgeBase.retrieve_detailed is exercised via the REAL
    # keyword-fallback corpus, no mocking).
    surgery_date = _dynamic_surgery_date(9)  # Day 10
    _reset_recovery_store()
    state = recovery_state.get_or_create_state(patient_id="MR-1", surgery_date_raw=surgery_date, procedure="TKA")
    state.apply_verified_day(10)
    state.mark_pending(rl.ROM_FLEXION_DEGREES)

    result = LAMOrchestrator.process(
        patient_id="MR-1", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
        postop_day=10, user_message=message, surgery_date=surgery_date,
    )
    print(f"    orchestrator result: intent={result['intent']} target_agent={result['target_agent']} engine={result['engine']}")
    _check(result["intent"] == IntentLabel.RECOVERY_PROGRESS.value, f"continuation must route as recovery_progress, got {result['intent']}")
    _check(result["target_agent"] == TargetAgent.RECOVERY_AGENT.value, f"continuation must dispatch to RecoveryProgressAgent, got {result['target_agent']}")
    _check(state.is_current(rl.ROM_FLEXION_DEGREES), "flexion=80 must actually be stored and current after this real end-to-end turn")
    _check("day-7" in result["reply"], f"reply must assess flexion against the day-7 checkpoint: {result['reply']!r}")
    print("    CONFIRMED: the real classifier's own 'bend'->REHABILITATION rule was correctly PREEMPTED by the continuation hook.")
    print()


# ============================================================================
# 13. SAFETY / SCOPE ORDER PRECEDENCE -- REAL-INTEGRATION (real
#    LAMOrchestrator.process(), continuation call-count spy). Pass-3 Section 15.
# (Also folds in and updates the OLD suite's tests 6/7 -- RED / OUT_OF_SCOPE
# short-circuit before RecoveryProgressAgent -- which remain fully valid.)
# ============================================================================

def test_safety_and_scope_precedence() -> None:
    _section("13 -- Safety RED / Scope precedence over Recovery continuation [REAL-INTEGRATION + continuation call-count spy]")

    surgery_date = "2026-09-02T00:00:00.000"
    _reset_recovery_store()
    state = recovery_state.get_or_create_state(patient_id="SP-1", surgery_date_raw=surgery_date, procedure="TKA")
    state.mark_pending(rl.ROM_FLEXION_DEGREES)

    chat_fn, chat_calls = _stub_answer_question()

    # RED must win; continuation helper must never even be reached.
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=chat_fn), \
         patch.object(ClinicalKnowledgeBase, "retrieve_detailed") as rag_mock, \
         patch("lam.orchestrator.check_recovery_continuation", wraps=ri.check_recovery_continuation) as cont_spy:
        result = LAMOrchestrator.process(
            patient_id="SP-1", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="I can't breathe and have severe chest pain", surgery_date=surgery_date,
        )
    print(f"    RED+pending-flexion: intent={result['intent']} triage={result['triage_level']} continuation_calls={cont_spy.call_count} rag_calls={rag_mock.call_count}")
    _check(result["intent"] == IntentLabel.EMERGENCY.value, "RED query did not return EMERGENCY intent")
    _check(result["triage_level"] == "RED", "RED query did not report triage_level RED")
    _check(len(chat_calls) == 0, "RED query must never reach ChatAgent.answer_question")
    _check(rag_mock.call_count == 0, "RED query must never reach RecoveryProgressAgent's retrieval")
    _check(cont_spy.call_count == 0, "RED short-circuit must happen BEFORE the continuation check is ever reached")
    _check(state.pending_field == rl.ROM_FLEXION_DEGREES, "RED short-circuit must not mutate the pending Recovery field")

    # OUT_OF_SCOPE must win; continuation helper must never be reached.
    chat_fn2, chat_calls2 = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=chat_fn2), \
         patch.object(ClinicalKnowledgeBase, "retrieve_detailed") as rag_mock2, \
         patch("lam.orchestrator.check_recovery_continuation", wraps=ri.check_recovery_continuation) as cont_spy2:
        result2 = LAMOrchestrator.process(
            patient_id="SP-1", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="What is the capital of France?", surgery_date=surgery_date,
        )
    print(f"    OUT_OF_SCOPE+pending-flexion: intent={result2['intent']} continuation_calls={cont_spy2.call_count} rag_calls={rag_mock2.call_count}")
    _check(result2["intent"] == IntentLabel.OUT_OF_SCOPE.value, "query did not return OUT_OF_SCOPE intent")
    _check(len(chat_calls2) == 0, "OUT_OF_SCOPE query must never reach ChatAgent.answer_question")
    _check(rag_mock2.call_count == 0, "OUT_OF_SCOPE query must never reach RecoveryProgressAgent's retrieval")
    _check(cont_spy2.call_count == 0, "Scope short-circuit must happen BEFORE the continuation check is ever reached")
    _check(state.pending_field == rl.ROM_FLEXION_DEGREES, "Scope short-circuit must not mutate the pending Recovery field")

    # Sanity: with neither RED nor OUT_OF_SCOPE, the continuation check IS reached.
    spy = _RetrievalSpy()
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy), \
         patch("lam.orchestrator.check_recovery_continuation", wraps=ri.check_recovery_continuation) as cont_spy3:
        LAMOrchestrator.process(
            patient_id="SP-1", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="80 degrees", surgery_date=surgery_date,
        )
    _check(cont_spy3.call_count == 1, f"an ordinary in-scope, non-RED turn must reach the continuation check exactly once, got {cont_spy3.call_count}")
    print()


# ============================================================================
# 14. PROCEDURE ISOLATION (TKA / THA / GEN) -- MOCKED-BOUNDARY for THA/GEN's
#    ChatAgent call; MOCKED-BOUNDARY retrieval for TKA. Pass-3 Section 16.
#    (Rewrite of the OLD suite's test 8, whose "domain_instruction milestone
#    note" concept no longer exists -- see Pass-3 migration report.)
# ============================================================================

def test_procedure_isolation() -> None:
    _section("14 -- TKA / THA / GEN procedure isolation [MOCKED-BOUNDARY]")

    surgery_date = _dynamic_surgery_date(9)  # Day 10

    # TKA: deterministic milestone flow IS supported -- creates Recovery
    # state and produces a checkpoint-relative verdict, no ChatAgent call.
    _reset_recovery_store()
    state = recovery_state.get_or_create_state(patient_id="PI-TKA", surgery_date_raw=surgery_date, procedure="TKA")
    state.apply_verified_day(10)
    chat_fn, chat_calls = _stub_answer_question()
    spy = _RetrievalSpy()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=chat_fn), \
         patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy):
        result_tka = RecoveryProgressAgent.handle(
            patient_id="PI-TKA", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="I can bend to 80 degrees.", procedure="TKA", surgery_date=surgery_date,
        )
    _check(len(chat_calls) == 0, "TKA must never call ChatAgent.answer_question (fully deterministic)")
    _check(result_tka["engine"] == RecoveryProgressAgent.ENGINE_NAME, f"TKA engine: {result_tka['engine']}")
    _check("day-7" in result_tka["reply"], "TKA must produce a checkpoint-relative verdict")

    # UPDATED (rework items 1/3): THA now HAS sourced checkpoints
    # (EV-THA-REC-*, EV-THA-REHAB-04) and runs the interview loop -- walking
    # and precaution questions, never knee ROM, no ChatAgent call on an
    # interview turn, and its own RecoverySessionState.
    _reset_recovery_store()
    fn_tha, calls_tha = _stub_answer_question(reply="THA grounded reply")
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn_tha):
        result_tha = RecoveryProgressAgent.handle(
            patient_id="PI-THA", surgery_type="Total Hip Arthroplasty (THA)", affected_limb="Left",
            postop_day=10, user_message="Am I on track for my hip recovery?", procedure="THA", surgery_date=surgery_date,
        )
    _check(len(calls_tha) == 0, f"THA interview turn must not call ChatAgent, got {len(calls_tha)}")
    _check(result_tha["engine"] == RecoveryProgressAgent.ENGINE_NAME, f"THA engine: {result_tha['engine']}")
    proof_tha = recovery_state.peek_state(patient_id="PI-THA", surgery_date_raw=surgery_date, procedure="THA")
    _check(proof_tha is not None and proof_tha.pending_field == rl.MOBILITY_STATUS, "THA must create state and open with the walking-aid question")
    _check(not any(w in result_tha["reply"].lower() for w in ("knee", "flexion", "extension", "degrees")), f"THA must never ask knee ROM: {result_tha['reply']!r}")

    # GEN: same as THA.
    _reset_recovery_store()
    fn_gen, calls_gen = _stub_answer_question(reply="GEN grounded reply")
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn_gen):
        RecoveryProgressAgent.handle(
            patient_id="PI-GEN", surgery_type="Ankle ORIF", affected_limb="Right",
            postop_day=10, user_message="How is my ankle recovery progressing?", procedure="GEN", surgery_date=surgery_date,
        )
    _check(len(calls_gen) == 1, f"GEN must reach the grounded-guidance ChatAgent path exactly once, got {len(calls_gen)}")
    _check(calls_gen[0].get("domain_instruction") == RecoveryProgressAgent.DOMAIN_FOCUS, "GEN domain_instruction must be the plain, unmodified DOMAIN_FOCUS")
    proof_gen = recovery_state.peek_state(patient_id="PI-GEN", surgery_date_raw=surgery_date, procedure="GEN")
    _check(proof_gen is None, "GEN must NOT create a RecoverySessionState")

    print("    DOCUMENTED: GEN skips the interview loop because no sourced checkpoint exists for it in the milestone file;")
    print("    TKA and THA both run the loop (THA: walking aid, walking duration, stairs, hip precautions).")
    print()


# ============================================================================
# 15. CLIENT-REPORTED POSTOP-DAY -- diagnostic-only, never authoritative.
#    REAL-INTEGRATION. Pass-3 Section 19.
# ============================================================================

def test_client_reported_postop_day_is_diagnostic_only() -> None:
    _section("15 -- client_reported_postop_day is diagnostic-only, never overrides effective_postop_day [REAL-INTEGRATION]")

    surgery_date = _dynamic_surgery_date(9)  # server-derived effective day = 10
    _reset_recovery_store()
    spy = _RetrievalSpy()
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy):
        RecoveryProgressAgent.handle(
            patient_id="CD-1", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=999,  # deliberately conflicting client-supplied value
            user_message="I can bend to 80 degrees.", procedure="TKA", surgery_date=surgery_date,
        )
    state = recovery_state.peek_state(patient_id="CD-1", surgery_date_raw=surgery_date, procedure="TKA")
    _check(state.client_reported_postop_day == 999, "client_reported_postop_day must still be recorded for diagnostics")
    _check(state.effective_postop_day == 10, f"effective_postop_day must stay server-derived (10), got {state.effective_postop_day}")
    _check(state.is_current(rl.ROM_FLEXION_DEGREES), "the clinical comparison must have proceeded using the server-derived day")
    print("    CONFIRMED: conflicting client postop_day=999 has no authority; effective_postop_day stayed 10.")
    print("    NOTE (Pass-2 correction, unchanged): state.client_reported_postop_day = postop_day in")
    print("    specialized_agents.py is the one intentional diagnostic-only direct public field assignment.")
    print("    A dedicated RecoverySessionState mutator for it is a documented Pass-3+ API-consistency cleanup")
    print("    candidate, not a functional blocker -- not changed in this pass (no test revealed a functional bug).")
    print()


# ============================================================================
# 16. ROUTING + RESPONSE SHAPE -- rewrite of OLD test 1. MOCKED-BOUNDARY
#    (retrieval mocked for TKA determinism).
# ============================================================================

def test_routing_and_response_shape() -> None:
    _section("16 -- Correct routing to RecoveryProgressAgent + new response shape [MOCKED-BOUNDARY: retrieval]")

    surgery_date = _dynamic_surgery_date(9)
    _reset_recovery_store()
    spy = _RetrievalSpy()
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy):
        result = LAMOrchestrator.process(
            patient_id="RT-1", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="How is my recovery progressing compared to a normal timeline?",
            surgery_date=surgery_date,
        )
    print(f"    intent={result['intent']} target_agent={result['target_agent']} action={result['action']} engine={result['engine']}")
    _check(result["intent"] == IntentLabel.RECOVERY_PROGRESS.value, "query did not classify as recovery_progress")
    _check(result["target_agent"] == RecoveryProgressAgent.TARGET_AGENT.value, f"expected target_agent {RecoveryProgressAgent.TARGET_AGENT.value}, got {result['target_agent']}")
    _check(
        _AGENT_BY_INTENT.get(IntentLabel.RECOVERY_PROGRESS) is RecoveryProgressAgent,
        "agent_router mapping for recovery_progress is not RecoveryProgressAgent",
    )
    # TKA interview turns are fully deterministic -- no ChatAgent call, and
    # (UPDATED, rework item 1) no Recovery-owned retrieval either: the
    # milestone file is the source.
    _check(result["engine"] == RecoveryProgressAgent.ENGINE_NAME, f"TKA route must use the deterministic engine, got {result['engine']}")
    _check(spy.call_count == 0, f"no Recovery-owned retrieval on an interview turn, got {spy.call_count}")
    _check(result["reply"].count("?") == 1, "the routed opener asks exactly one question")
    print()


# ============================================================================
# 17. postop_day / procedure / chat_history REACH THE AGENT -- rewrite of OLD
#    tests 2/3/4. These now specifically exercise the THA grounded-guidance
#    path (the only Recovery path that still calls ChatAgent.answer_question
#    and forwards chat_history). MOCKED-BOUNDARY.
# ============================================================================

def test_postop_day_procedure_and_chat_history_reach_grounded_guidance() -> None:
    _section("17 -- postop_day / procedure / chat_history reach ChatAgent for the GEN grounded-guidance path [MOCKED-BOUNDARY]")

    # UPDATED (rework items 1/3): THA now runs the interview loop, so the
    # grounded-guidance forwarding contract is exercised with GEN (the one
    # procedure that still takes that path). A THA request WITHOUT a
    # surgery_date cannot be placed on a day: it gets the deterministic
    # "can't verify your surgery date" reply and never reaches ChatAgent.
    fn, calls = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        RecoveryProgressAgent.handle(
            patient_id="GG-1", surgery_type="Ankle ORIF", affected_limb="Left",
            postop_day=13, user_message="Am I on track for my ankle recovery?", procedure="GEN",
        )
    _check(len(calls) == 1, f"expected 1 call, got {len(calls)}")
    if calls:
        _check(calls[0].get("postop_day") == 13, f"postop_day not forwarded, got {calls[0].get('postop_day')}")
        _check(calls[0].get("procedure") == "GEN", f"procedure not forwarded, got {calls[0].get('procedure')}")
        _check(calls[0].get("surgery_type") == "Ankle ORIF", "surgery_type not forwarded")

    history = [
        {"role": "user", "content": "I had my ankle fixed five days ago."},
        {"role": "assistant", "content": "Great, how does it feel today?"},
    ]
    fn2, calls2 = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn2):
        RecoveryProgressAgent.handle(
            patient_id="GG-2", surgery_type="Ankle ORIF", affected_limb="Left",
            postop_day=5, user_message="Is this normal for my ankle?", procedure="GEN", chat_history=history,
        )
    _check(len(calls2) == 1, f"expected 1 call, got {len(calls2)}")
    _check(calls2 and calls2[0].get("chat_history") == history, "chat_history was not forwarded unmodified")

    _reset_recovery_store()
    fn3, calls3 = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn3):
        result_tha = RecoveryProgressAgent.handle(
            patient_id="GG-THA", surgery_type="Total Hip Arthroplasty (THA)", affected_limb="Left",
            postop_day=13, user_message="Am I on track for my hip recovery?", procedure="THA",
        )
    _check(len(calls3) == 0, "THA without a surgery_date must not reach ChatAgent")
    _check("can't verify your surgery date" in result_tha["reply"], f"THA without a surgery_date gets the day-unverified reply: {result_tha['reply']!r}")

    # By contrast: TKA's deterministic loop does NOT depend on chat_history
    # at all (state, not chat_history, is Recovery's source of truth) --
    # confirm it accepts None safely without crashing.
    surgery_date = _dynamic_surgery_date(9)
    _reset_recovery_store()
    spy = _RetrievalSpy()
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy):
        result = RecoveryProgressAgent.handle(
            patient_id="GG-3", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="How is my recovery going?", procedure="TKA",
            surgery_date=surgery_date, chat_history=None,
        )
    _check(result["reply"], "TKA path must produce a reply even with chat_history=None")
    print("    CONFIRMED: THA/GEN forward postop_day/procedure/chat_history to ChatAgent unmodified; TKA's")
    print("    deterministic state-driven loop does not require chat_history at all.")
    print()


# ============================================================================
# 18. CONVERSATIONAL STYLE -- MOCKED-BOUNDARY (retrieval mocked) /
#    REAL-INTEGRATION (orchestrator wound-priority). Verifies the Pass-4
#    style-only rewrite: natural acknowledgment + grounded explanation +
#    at most one question, with no report-style wording and no invented
#    targets -- WITHOUT pinning to one exact full sentence. State-machine
#    behavior (ASK/AWAIT/ASSESS, pending-field handling, RED/wound
#    priority) is untouched and re-verified here only to confirm the style
#    pass didn't disturb it.
# ============================================================================

def test_conversational_style_and_grounding() -> None:
    _section("18 -- Conversational style: natural wording + preserved grounding [MOCKED-BOUNDARY: retrieval / REAL-INTEGRATION: wound priority]")

    spy = _RetrievalSpy()

    # ------------------------------------------------------------------
    # A + D: "60 degrees" answered BEFORE the first milestone (Day 4 <
    # checkpoint Day 7) -- must sound conversational, mention 60 degrees,
    # explain (grounded in the patient's own day and the checkpoint day)
    # that it's too early to compare, and must NOT invent a Day-4 target
    # (no 70/90 range leaking in).
    # ------------------------------------------------------------------
    surgery_date_day4 = _dynamic_surgery_date(3)  # Day 4
    _reset_recovery_store()
    state_a = recovery_state.get_or_create_state(patient_id="CS-A", surgery_date_raw=surgery_date_day4, procedure="TKA")
    state_a.apply_verified_day(4)
    state_a.mark_pending(rl.ROM_FLEXION_DEGREES)
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy):
        result_a = RecoveryProgressAgent.handle(
            patient_id="CS-A", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=4, user_message="60 degrees", procedure="TKA", surgery_date=surgery_date_day4,
        )
    reply_a = result_a["reply"]
    print(f"    A/D (Day4, '60 degrees'): {reply_a!r}")
    _check(state_a.is_current(rl.ROM_FLEXION_DEGREES), "A: 60 degrees must be stored as the current flexion value")
    _check(state_a.get_fact(rl.ROM_FLEXION_DEGREES).value == 60.0, "A: stored value must be 60")
    _check("60" in reply_a, "A: reply must mention the reported 60 degrees")
    _check("day 4" in reply_a and "day 7" in reply_a, "A/D: reply must ground the explanation in both the patient's day (4) and the checkpoint day (7)")
    # UPDATED (rework item 4): before day 7 the day-7 range IS given, as the
    # target to work towards (with its source), never as a day-4 target.
    _check("70" in reply_a and "90" in reply_a and "work towards" in reply_a, "A/D: reply must give the day-7 target to work towards")
    # UPDATED (readability pass): the source is metadata (result["sources"]), never patient text.
    _check("TKA-03" not in reply_a and result_a["sources"] == ["TKA-03"], "A/D: the target is sourced in metadata, not in the text")
    _assert_no_forbidden_trajectory_language(reply_a, "A/D Day4 60-degrees")
    _assert_no_forbidden_robotic_language(reply_a, "A/D Day4 60-degrees")
    _check("noted" not in reply_a.lower(), "A/D: acknowledgment must not sound like a database entry ('noted')")
    # UPDATED (rework item 3): the ONE follow-up question (the next missing
    # metric, extension) is now asked in the same reply and IS tracked --
    # pending_field is set to it, so the answer can be attributed.
    _check(reply_a.count("?") == 1 and state_a.pending_field == rl.ROM_EXTENSION_DEGREES, f"A/D: exactly one tracked question follows the feedback, got {reply_a!r}")

    # ------------------------------------------------------------------
    # B: "Same as yesterday." must still be interpreted as an answer to
    # the pending field (unchanged extraction/continuation logic) and
    # produce a natural, grounded reply once the checkpoint is due.
    # ------------------------------------------------------------------
    surgery_date_day7 = _dynamic_surgery_date(6)  # Day 7 today
    _reset_recovery_store()
    state_b = recovery_state.get_or_create_state(patient_id="CS-B", surgery_date_raw=surgery_date_day7, procedure="TKA")
    state_b.apply_verified_day(6)
    state_b.set_fact(rl.ROM_FLEXION_DEGREES, 75, effective_postop_day=6)
    state_b.apply_verified_day(7)
    state_b.mark_pending(rl.ROM_FLEXION_DEGREES)
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy):
        result_b = RecoveryProgressAgent.handle(
            patient_id="CS-B", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=7, user_message="Same as yesterday.", procedure="TKA", surgery_date=surgery_date_day7,
        )
    reply_b = result_b["reply"]
    print(f"    B ('Same as yesterday.'): {reply_b!r}")
    _check(state_b.is_current(rl.ROM_FLEXION_DEGREES), "B: 'same as yesterday' must still be applied as the current flexion value")
    _check(state_b.get_fact(rl.ROM_FLEXION_DEGREES).value == 75, "B: carried-forward value must stay 75")
    _check("75" in reply_b, "B: reply must reflect the carried-forward value (75)")
    _assert_no_forbidden_robotic_language(reply_b, "B same-as-yesterday")

    # ------------------------------------------------------------------
    # C: "I don't know." must be handled naturally -- a short, varied
    # acknowledgment ahead of the re-ask, not a bare repeated question.
    # ------------------------------------------------------------------
    surgery_date_day10 = _dynamic_surgery_date(9)  # Day 10
    _reset_recovery_store()
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy):
        RecoveryProgressAgent.handle(  # Turn 1: opener -> asks flexion (no ack -- nothing to acknowledge yet)
            patient_id="CS-C", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="How is my recovery going?", procedure="TKA", surgery_date=surgery_date_day10,
        )
        result_c = RecoveryProgressAgent.handle(  # Turn 2: "I don't know."
            patient_id="CS-C", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="I don't know.", procedure="TKA", surgery_date=surgery_date_day10,
        )
    reply_c = result_c["reply"]
    print(f"    C (\"I don't know.\"): {reply_c!r}")
    state_c = recovery_state.peek_state(patient_id="CS-C", surgery_date_raw=surgery_date_day10, procedure="TKA")
    _check(state_c.ask_count_of(rl.ROM_FLEXION_DEGREES) == 1, "C: 'I don't know' must still be recorded as a retry (state machine untouched)")
    # UPDATED (rework item 3): after an uncertain answer the SIMPLER
    # rephrase is asked (not the identical question), with a short
    # acknowledgment in front and the progress indicator after it.
    alt_question = ri._ALT_QUESTIONS[rl.ROM_FLEXION_DEGREES]
    _check(alt_question in reply_c and not reply_c.startswith(alt_question), f"C: reply must open with a short acknowledgment before the simpler rephrase, got {reply_c!r}")
    _check(ri._ASK_QUESTIONS[rl.ROM_FLEXION_DEGREES] not in reply_c, "C: the identical question must not simply be repeated")
    _check("degrees" in reply_c.lower() or "bend" in reply_c.lower(), "C: reply must still ask about flexion")
    _check(state_c.pending_variant == "alt", "C: the rephrase is tracked as the 'alt' variant")
    _assert_no_forbidden_robotic_language(reply_c, "C don't-know retry")

    # ------------------------------------------------------------------
    # E: day WITH an available milestone (Day 10, past checkpoint Day 7,
    # flexion 80 within 70-90) -- natural grounded comparison, still
    # stating the real range and the real (earlier) checkpoint day.
    # ------------------------------------------------------------------
    _reset_recovery_store()
    state_e = recovery_state.get_or_create_state(patient_id="CS-E", surgery_date_raw=surgery_date_day10, procedure="TKA")
    state_e.apply_verified_day(10)
    state_e.mark_pending(rl.ROM_FLEXION_DEGREES)
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy):
        result_e = RecoveryProgressAgent.handle(
            patient_id="CS-E", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="I can bend to about 80 degrees.", procedure="TKA", surgery_date=surgery_date_day10,
        )
    reply_e = result_e["reply"]
    print(f"    E (Day10, flexion 80): {reply_e!r}")
    _check("80" in reply_e, "E: reply must mention the reported 80 degrees")
    _check("70" in reply_e and "90" in reply_e, "E: reply must state the real 70-90 checkpoint range")
    _check("day-7" in reply_e and "earlier Post-Op Day" not in reply_e, "E: reply must reference the real day-7 checkpoint in plain words, grounded not invented")
    _assert_no_forbidden_trajectory_language(reply_e, "E Day10 flexion80")
    _assert_no_forbidden_directional_language(reply_e, "E Day10 flexion80")
    _assert_no_forbidden_robotic_language(reply_e, "E Day10 flexion80")

    # ------------------------------------------------------------------
    # F: RED safety still overrides Recovery entirely -- re-verified here
    # (already proven in test_safety_and_scope_precedence) purely as a
    # style-pass regression guard: the conversational rewrite must not
    # have touched orchestrator-level precedence.
    # ------------------------------------------------------------------
    surgery_date_flat = "2026-09-02T00:00:00.000"
    _reset_recovery_store()
    state_f = recovery_state.get_or_create_state(patient_id="CS-F", surgery_date_raw=surgery_date_flat, procedure="TKA")
    state_f.mark_pending(rl.ROM_FLEXION_DEGREES)
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed") as rag_mock_f:
        result_f = LAMOrchestrator.process(
            patient_id="CS-F", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="I can't breathe and have severe chest pain", surgery_date=surgery_date_flat,
        )
    _check(result_f["intent"] == IntentLabel.EMERGENCY.value, "F: RED query must still return EMERGENCY, unaffected by the style pass")
    _check(rag_mock_f.call_count == 0, "F: RED must still short-circuit before Recovery's retrieval is ever reached")
    _check(state_f.pending_field == rl.ROM_FLEXION_DEGREES, "F: RED short-circuit must still leave the pending Recovery field untouched")

    # ------------------------------------------------------------------
    # G: an explicit wound issue still overrides an outstanding Recovery
    # question -- re-verified here as a style-pass regression guard on
    # orchestrator-level wound priority (untouched by this pass).
    # ------------------------------------------------------------------
    _reset_recovery_store()
    state_g = recovery_state.get_or_create_state(patient_id="CS-G", surgery_date_raw=surgery_date_flat, procedure="TKA")
    state_g.mark_pending(rl.ROM_FLEXION_DEGREES)
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed") as rag_mock_g:
        result_g = LAMOrchestrator.process(
            patient_id="CS-G", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="My wound looks more red today and it's leaking some fluid.", surgery_date=surgery_date_flat,
        )
    print(f"    G (explicit wound issue): intent={result_g['intent']} target_agent={result_g['target_agent']}")
    _check(result_g["target_agent"] == TargetAgent.WOUND_CARE_AGENT.value, f"G: explicit wound issue must route to WoundCareAgent, got {result_g['target_agent']}")
    _check(rag_mock_g.call_count == 0, "G: wound priority must short-circuit before Recovery's own retrieval is ever reached")
    _check(state_g.pending_field == rl.ROM_FLEXION_DEGREES, "G: wound priority must not mutate the still-outstanding Recovery field")
    print()


# ============================================================================
# REWORK TESTS (feature/agents-proactive) -- one per item of the rework.
# ============================================================================

import json as _json
import logging as _logging
import re as _re
import os as _os
import sqlite3 as _sqlite3
import tempfile as _tempfile
from pathlib import Path as _Path

from agents import patient_memory as pm


def _seed_recovery_patient(patient_id: str, *, surgery_type: str, surgery_date: str, metrics=None) -> None:
    """A real `patients`/`surgeries` row (plus optional metrics rows) in
    the isolated test DB so memory reads and persistence actually work."""
    from patient_database import create_patient, delete_patient

    try:
        delete_patient(patient_id)
    except Exception:
        pass
    try:
        create_patient({
            "patient_id": patient_id, "full_name": f"Recovery {patient_id}", "surgery_type": surgery_type,
            "affected_limb": "Right", "surgery_date": surgery_date[:10], "postop_day": 1,
            "weight_bearing_status": "Weight Bearing as Tolerated (WBAT)", "metrics_history": metrics or [],
        })
    except _sqlite3.IntegrityError:
        pass


def _days_ago_iso(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def _handle_tka(patient_id: str, message: str, *, surgery_date: str, day: int, history=None, **extra):
    return RecoveryProgressAgent.handle(
        patient_id=patient_id, surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
        postop_day=day, user_message=message, procedure="TKA", surgery_date=surgery_date,
        chat_history=history, **extra,
    )


def _handle_tha(patient_id: str, message: str, *, surgery_date: str, day: int, history=None, **extra):
    return RecoveryProgressAgent.handle(
        patient_id=patient_id, surgery_type="Total Hip Arthroplasty (THA)", affected_limb="Left",
        postop_day=day, user_message=message, procedure="THA", surgery_date=surgery_date,
        chat_history=history, **extra,
    )


def _run_interview(handle_fn, patient_id: str, messages, *, surgery_date: str, day: int, stub_reply: str = "", **extra):
    """Drive a whole interview with a stubbed LLM; returns (results, chat_fn calls)."""
    fn, calls = _stub_answer_question(reply=stub_reply)
    results = []
    history: List[Dict[str, str]] = []
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        for message in messages:
            result = handle_fn(patient_id, message, surgery_date=surgery_date, day=day, history=list(history), **extra)
            results.append(result)
            history += [{"role": "user", "content": message}, {"role": "assistant", "content": result["reply"]}]
    return results, calls


_TKA_FULL_INTERVIEW = [
    "How is my recovery going?", "I can bend to about 85 degrees", "yes, fully flat",
    "I'm using a cane", "about 15 minutes", "one step at a time holding the rail",
]
_THA_FULL_INTERVIEW = [
    "How is my hip recovery going?", "I'm still using one crutch", "about 20 minutes",
    "foot over foot now", "yes, still following them",
]


# ----------------------------------------------------------------------------
# 19. Milestone data file: every entry's passage id exists in its corpus,
#     structure is complete, and the loader rejects malformed data.
# ----------------------------------------------------------------------------

def test_milestone_file_sources_exist_in_corpus() -> None:
    _section("19 -- recovery_milestones.json: every entry sourced from the eval corpus (or the retained TKA-03) [REAL-INTEGRATION]")

    table = rl.parse_milestone_file(validate_sources=True)
    backend_dir = _Path(rl.__file__).resolve().parent.parent
    eval_corpus = {p["id"]: p for p in _json.loads((backend_dir / "eval" / "eval_corpus.json").read_text(encoding="utf-8"))}
    seed_corpus = {p["id"]: p for p in _json.loads((backend_dir / "rag" / "data" / "seed_knowledge.json").read_text(encoding="utf-8"))}
    allowed_eval_prefixes = ("EV-TKA-REC-", "EV-THA-REC-")
    allowed_eval_exact = {"EV-TKA-REHAB-02", "EV-TKA-REHAB-03", "EV-THA-REHAB-04"}

    print(f"    {len(table.entries)} entries; checkpoint days {table.checkpoint_days}; procedures {table.procedures()}")
    _check(table.checkpoint_days == (7, 14, 21, 42, 84), f"checkpoint days must be 7/14/21/42/84, got {table.checkpoint_days}")
    for entry in table.entries:
        if entry.source_id == "TKA-03":
            _check(entry.source_corpus == "rag/data/seed_knowledge.json" and "TKA-03" in seed_corpus, "the retained TKA-03 entries cite the seed corpus")
            _check(entry.checkpoint == 7 and entry.metric in rl.ROM_FIELDS, "TKA-03 is kept ONLY for the day-7 ROM entries")
            continue
        _check(entry.source_id in eval_corpus, f"{entry.source_id} must exist in eval/eval_corpus.json")
        _check(
            entry.source_id.startswith(allowed_eval_prefixes) or entry.source_id in allowed_eval_exact,
            f"{entry.source_id} is outside the allowed passage set",
        )
        passage = eval_corpus[entry.source_id]
        _check(passage["procedure"] == entry.procedure, f"{entry.source_id}: passage procedure {passage['procedure']} vs entry {entry.procedure}")
        _check(entry.source_url == passage["metadata"]["source_url"], f"{entry.source_id}: source_url must be the passage's own URL")
        for fragment in entry.quote.split(" ... "):
            _check(fragment in passage["content"], f"{entry.source_id} {entry.metric} day {entry.checkpoint}: quote fragment not in passage: {fragment!r}")
        if entry.kind == "numeric":
            # No invented numbers: every bound must appear in the quoted passage text.
            for bound in (entry.range_low, entry.range_high):
                if bound is None:
                    continue
                token = str(int(bound)) if float(bound).is_integer() else str(bound)
                words = {"0": ("fully straight", "fully flat", "0"), "10": ("10", "ten")}
                _check(
                    any(w in passage["content"] for w in words.get(token, (token,))),
                    f"{entry.source_id} {entry.metric} day {entry.checkpoint}: bound {bound} not stated by the passage",
                )

    # Required coverage: both procedures, every checkpoint day + long-term,
    # the eight metrics of the brief represented, THA without knee ROM.
    for procedure in ("TKA", "THA"):
        for day in (7, 14, 21, 42, 84):
            _check(table.at_checkpoint(procedure, day), f"{procedure} needs entries at day {day}")
        _check(table.at_checkpoint(procedure, rl.LONG_TERM), f"{procedure} needs a long-term entry")
    tka_metrics = {e.metric for e in table.entries if e.procedure == "TKA"}
    _check(tka_metrics >= {rl.ROM_FLEXION_DEGREES, rl.ROM_EXTENSION_DEGREES, rl.MOBILITY_STATUS, rl.WALKING_DURATION_MINUTES,
                           rl.STAIRS, rl.DAILY_ACTIVITIES, rl.DRIVING, rl.RETURN_TO_WORK}, f"TKA metrics: {tka_metrics}")
    tha_metrics = {e.metric for e in table.entries if e.procedure == "THA"}
    _check(not (tha_metrics & set(rl.ROM_FIELDS)), "THA must carry no knee ROM entries")
    _check({rl.MOBILITY_STATUS, rl.WALKING_DURATION_MINUTES, rl.STAIRS, rl.HIP_PRECAUTIONS, rl.DRIVING, rl.RETURN_TO_WORK} <= tha_metrics, f"THA metrics: {tha_metrics}")
    _check(rl.load_milestones().entries == table.entries, "the cached production loader returns the same table")

    # Loader validation: tampered copies are rejected with a clear error.
    raw = _json.loads(_Path(table.source_path).read_text(encoding="utf-8"))

    def _expect_rejection(mutate, label: str) -> None:
        bad = _json.loads(_json.dumps(raw))
        mutate(bad)
        tmp = _Path(_tempfile.mkdtemp(prefix="milestones_")) / "bad.json"
        tmp.write_text(_json.dumps(bad), encoding="utf-8")
        try:
            rl.parse_milestone_file(tmp, validate_sources=True)
        except rl.MilestoneDataError as exc:
            print(f"    rejected ({label}): {exc}")
            return
        _check(False, f"loader must reject: {label}")

    _expect_rejection(lambda b: b["entries"][0].__setitem__("checkpoint", 9), "a checkpoint day outside 7/14/21/42/84")
    _expect_rejection(lambda b: b["entries"].append({**b["entries"][0], "procedure": "THA"}), "a THA knee-ROM entry")
    _expect_rejection(lambda b: b["entries"][0].__setitem__("source_id", "EV-NOPE-99"), "a source id missing from the corpus")
    _expect_rejection(lambda b: b["entries"][0].pop("unit"), "a numeric entry without a unit")
    _expect_rejection(
        lambda b: b.__setitem__("entries", [e for e in b["entries"] if not (e["procedure"] == "TKA" and e["checkpoint"] == "long_term")]),
        "a procedure without a long-term entry",
    )
    _expect_rejection(lambda b: b["entries"].append(dict(b["entries"][0])), "a duplicate (procedure, checkpoint, metric)")
    print()


# ----------------------------------------------------------------------------
# 20. Nearest checkpoint at or before the day; long-term after day 84; the
#     first checkpoint before day 7; next milestone.
# ----------------------------------------------------------------------------

def test_select_checkpoint_nearest_at_or_before_and_long_term() -> None:
    _section("20 -- select_checkpoint(): nearest at-or-before day, first checkpoint before day 7, long-term after 84 [REAL-INTEGRATION]")

    flex = rl.ROM_FLEXION_DEGREES
    cases = [(1, 7), (4, 7), (7, 7), (10, 7), (14, 14), (20, 14), (21, 21), (30, 21), (42, 42), (60, 42), (84, 84)]
    for day, expected in cases:
        entry = rl.select_checkpoint("TKA", flex, day)
        _check(entry is not None and entry.checkpoint == expected, f"TKA flexion day {day}: expected checkpoint {expected}, got {entry.checkpoint if entry else None}")
    for day in (85, 100, 200, 365):
        entry = rl.select_checkpoint("TKA", flex, day)
        _check(entry is not None and entry.is_long_term and entry.source_id == "EV-TKA-REC-06", f"TKA flexion day {day}: expected the long-term entry, got {entry}")
    # Extension has no long-term entry -> the nearest dated checkpoint (84) is used after day 84.
    ext_late = rl.select_checkpoint("TKA", rl.ROM_EXTENSION_DEGREES, 120)
    _check(ext_late is not None and ext_late.checkpoint == 84, f"TKA extension day 120 falls back to day 84, got {ext_late}")
    tha_late = rl.select_checkpoint("THA", rl.HIP_PRECAUTIONS, 200)
    _check(tha_late is not None and tha_late.is_long_term and tha_late.source_id == "EV-THA-REC-06", f"THA precautions day 200: {tha_late}")
    _check(rl.select_checkpoint("THA", flex, 10) is None, "THA has no knee-ROM checkpoint at all")

    # Never None for a sourced metric anywhere in day 1-365.
    table = rl.load_milestones()
    for procedure in ("TKA", "THA"):
        metrics = {e.metric for e in table.entries if e.procedure == procedure}
        for metric in metrics:
            for day in (1, 6, 7, 13, 22, 41, 42, 83, 84, 85, 365):
                _check(rl.select_checkpoint(procedure, metric, day) is not None, f"{procedure} {metric} day {day} must resolve to an entry")

    _check(rl.next_milestone("TKA", 4)[0] == 7 and rl.next_milestone("TKA", 10)[0] == 14 and rl.next_milestone("TKA", 42)[0] == 84, "next_milestone picks the next checkpoint day")
    nxt, entries = rl.next_milestone("TKA", 84)
    _check(nxt == rl.LONG_TERM and entries and all(e.is_long_term for e in entries), "after the last checkpoint the next milestone is the long-term entry")
    print()


# ----------------------------------------------------------------------------
# 21. Memory: a value logged today/yesterday is confirmed rather than asked;
#     a trend is shown when at least two values exist.
# ----------------------------------------------------------------------------

def test_memory_confirms_logged_flexion_and_shows_trend() -> None:
    _section("21 -- Memory before asking: confirm yesterday's flexion, show the 7-day trend [REAL-INTEGRATION + stubbed LLM]")

    surgery_date = _dynamic_surgery_date(9)  # Day 10
    metrics = [
        {"day": 7, "date": _days_ago_iso(3), "rom_flexion": 70, "rom_extension": 8},
        {"day": 9, "date": _days_ago_iso(1), "rom_flexion": 80, "rom_extension": 5},
    ]
    _seed_recovery_patient("MEM-TKA", surgery_type="Total Knee Arthroplasty (TKA)", surgery_date=surgery_date, metrics=metrics)

    memory = pm.load_patient_memory("MEM-TKA")
    series = memory.metric_series("rom_flexion", days=7)
    _check([v for _, v in series] == [70.0, 80.0], f"metric_series must return the last-7-day values oldest first, got {series}")
    latest = memory.latest_metric("rom_flexion", within_days=1)
    _check(latest is not None and latest[1] == 80.0 and latest[2] == 1, f"latest_metric must find yesterday's 80, got {latest}")
    _check(ri.confirmation_offer(rl.ROM_FLEXION_DEGREES, memory) == (80.0, 1), "confirmation_offer uses the value logged yesterday")
    # UPDATED (readability pass): the trend is one short phrase with a direction word.
    _check(ri.trend_line(rl.ROM_FLEXION_DEGREES, memory, 85.0) == "improving: 70 -> 80 -> 85", f"trend line wording: {ri.trend_line(rl.ROM_FLEXION_DEGREES, memory, 85.0)!r}")
    _check(ri.trend_line(rl.ROM_FLEXION_DEGREES, memory, 80.0) == "improving: 70 -> 80 -> 80", "direction compares the first and last values")
    _check(ri.trend_direction(rl.ROM_EXTENSION_DEGREES, [8, 5]) == "improving" and ri.trend_direction(rl.ROM_FLEXION_DEGREES, [80, 80]) == "steady"
           and ri.trend_direction(rl.ROM_FLEXION_DEGREES, [85, 80]) == "over the week", "extension improves towards zero; unchanged is steady; the other way is neutral")
    _check(ri.trend_line(rl.WALKING_DURATION_MINUTES, memory, 15.0) is None, "no trend for a metric without a metrics column")

    # "yes" keeps the logged value.
    _reset_recovery_store()
    results, _ = _run_interview(_handle_tka, "MEM-TKA", ["How is my recovery going?", "yes"], surgery_date=surgery_date, day=10)
    opener, confirmed = results[0]["reply"], results[1]["reply"]
    print(f"    opener: {opener!r}")
    print(f"    after 'yes': {confirmed!r}")
    _check("Your log from yesterday says you could bend to 80°" in opener and "still about that?" in opener, "the opener confirms yesterday's flexion instead of asking")
    _check(ri._ASK_QUESTIONS[rl.ROM_FLEXION_DEGREES] not in opener, "the plain flexion question is NOT asked when a logged value exists")
    state = recovery_state.peek_state(patient_id="MEM-TKA", surgery_date_raw=surgery_date, procedure="TKA")
    _check(state.is_current(rl.ROM_FLEXION_DEGREES) and state.get_fact(rl.ROM_FLEXION_DEGREES).value == 80.0, "'yes' stores the logged 80")
    _check("flexion of 80°" in confirmed and "improving: 70 -> 80 -> 80" in confirmed, f"the confirmed value is compared and the trend shown: {confirmed!r}")
    _check("Your log from yesterday says your extension was 5°" in confirmed, "the next ROM metric logged yesterday is confirmed too")

    # A number overrides the logged value; "no" falls back to the plain question.
    _reset_recovery_store()
    results, _ = _run_interview(_handle_tka, "MEM-TKA", ["How is my recovery going?", "it's about 85 now"], surgery_date=surgery_date, day=10)
    state = recovery_state.peek_state(patient_id="MEM-TKA", surgery_date_raw=surgery_date, procedure="TKA")
    _check(state.get_fact(rl.ROM_FLEXION_DEGREES).value == 85.0, "a number overrides the logged value")
    _check("improving: 70 -> 80 -> 85" in results[1]["reply"], f"trend uses today's number: {results[1]['reply']!r}")
    _reset_recovery_store()
    results, _ = _run_interview(_handle_tka, "MEM-TKA", ["How is my recovery going?", "no"], surgery_date=surgery_date, day=10)
    print(f"    after 'no': {results[1]['reply']!r}")
    _check(ri._ASK_QUESTIONS[rl.ROM_FLEXION_DEGREES] in results[1]["reply"], "'no' leads to the plain flexion question")
    state = recovery_state.peek_state(patient_id="MEM-TKA", surgery_date_raw=surgery_date, procedure="TKA")
    _check(not state.is_current(rl.ROM_FLEXION_DEGREES) and state.pending_field == rl.ROM_FLEXION_DEGREES, "'no' stores nothing and keeps flexion pending")

    # A value logged THREE days ago is not offered for confirmation.
    _seed_recovery_patient("MEM-OLD", surgery_type="Total Knee Arthroplasty (TKA)", surgery_date=surgery_date,
                           metrics=[{"day": 7, "date": _days_ago_iso(3), "rom_flexion": 70}])
    _reset_recovery_store()
    results, _ = _run_interview(_handle_tka, "MEM-OLD", ["How is my recovery going?"], surgery_date=surgery_date, day=10)
    _check(ri._ASK_QUESTIONS[rl.ROM_FLEXION_DEGREES] in results[0]["reply"] and "still about that" not in results[0]["reply"], "a 3-day-old value is asked afresh, not confirmed")
    print()


# ----------------------------------------------------------------------------
# 22. The request's current_rom is read via patient_memory and never asked.
# ----------------------------------------------------------------------------

def test_request_current_rom_seeded_and_never_asked() -> None:
    _section("22 -- current_rom from the request is parsed via patient_memory and never asked again [REAL-INTEGRATION + stubbed LLM]")

    _check(pm.parse_current_rom("flexion 85, extension 3") == {"rom_flexion": 85.0, "rom_extension": 3.0}, "labelled pair")
    _check(pm.parse_current_rom("85/5") == {"rom_flexion": 85.0, "rom_extension": 5.0}, "slash pair")
    _check(pm.parse_current_rom("I can bend to 90 degrees") == {"rom_flexion": 90.0}, "bend wording -> flexion only")
    _check(pm.parse_current_rom("") == {} and pm.parse_current_rom(None) == {}, "empty -> nothing")

    surgery_date = _dynamic_surgery_date(9)
    _reset_recovery_store()
    results, _ = _run_interview(_handle_tka, "ROM-REQ", ["How is my recovery going?"], surgery_date=surgery_date, day=10,
                                current_rom="flexion 85, extension 3")
    reply = results[0]["reply"]
    print(f"    with current_rom: {reply!r}")
    state = recovery_state.peek_state(patient_id="ROM-REQ", surgery_date_raw=surgery_date, procedure="TKA")
    _check(state.is_current(rl.ROM_FLEXION_DEGREES) and state.get_fact(rl.ROM_FLEXION_DEGREES).value == 85.0, "request flexion is seeded as today's fact")
    _check(state.is_current(rl.ROM_EXTENSION_DEGREES) and state.get_fact(rl.ROM_EXTENSION_DEGREES).value == 3.0, "request extension is seeded as today's fact")
    _check("flexion of 85°" in reply and "extension of 3°" in reply, "seeded values are compared on the opener")
    _check(state.pending_field == rl.MOBILITY_STATUS and "how many degrees" not in reply.lower(), f"neither ROM value is asked; the walking-aid question comes first: {state.pending_field}")
    print()


# ----------------------------------------------------------------------------
# 23. The simpler extension question maps to degree ranges from TKA-03.
# ----------------------------------------------------------------------------

def test_simpler_extension_question_maps_to_range() -> None:
    _section("23 -- 'Can you get the knee fully flat on the bed?' -> degree ranges (TKA-03's 0-5 near-full) [REAL-INTEGRATION + stubbed LLM]")

    surgery_date = _dynamic_surgery_date(9)  # Day 10

    def _answer_flat(patient: str, answer: str):
        _reset_recovery_store()
        results, _ = _run_interview(_handle_tka, patient, ["I can bend to 85 degrees", "I don't know", answer], surgery_date=surgery_date, day=10)
        state = recovery_state.peek_state(patient_id=patient, surgery_date_raw=surgery_date, procedure="TKA")
        return results, state

    results, state = _answer_flat("FLAT-YES", "yes")
    print(f"    after 'I don't know': {results[1]['reply']!r}")
    _check(ri._ALT_QUESTIONS[rl.ROM_EXTENSION_DEGREES] in results[1]["reply"], "the simpler flat-on-the-bed question follows an uncertain answer")
    _check("can you get the knee fully flat on the bed?" in results[1]["reply"].lower(), "wording as specified")
    value = state.get_fact(rl.ROM_EXTENSION_DEGREES).value
    _check(isinstance(value, rl.ValueRange) and value.is_point and value.low == 0.0, f"'yes' -> fully flat = 0°, got {value}")
    # UPDATED (readability pass): the comparison is one short clause ("..., within the day-7 range of 0°-5°").
    _check("extension (fully flat on the bed), within the day-7 range of 0°-5°" in results[2]["reply"], f"'yes' compares within 0-5: {results[2]['reply']!r}")

    results, state = _answer_flat("FLAT-ALMOST", "almost, there's a small gap")
    value = state.get_fact(rl.ROM_EXTENSION_DEGREES).value
    _check(value == rl.EXTENSION_FLAT_ANSWERS["near_full"], f"'almost' -> near-full 0-5 range, got {value}")
    _check("(nearly flat), within the day-7 range of 0°-5°" in results[2]["reply"], f"'almost' compares within 0-5: {results[2]['reply']!r}")

    results, state = _answer_flat("FLAT-NO", "no")
    value = state.get_fact(rl.ROM_EXTENSION_DEGREES).value
    _check(value == rl.EXTENSION_FLAT_ANSWERS["not_full"], f"'no' -> more than near-full, got {value}")
    _check("(not yet flat), outside the day-7 range of 0°-5°" in results[2]["reply"], f"'no' compares outside 0-5, neutrally: {results[2]['reply']!r}")
    _assert_no_forbidden_directional_language(results[2]["reply"].split("\n\n")[0], "flat 'no'")

    # Day 14 (range 0-10): "nearly flat" (0-5) is fully inside; "not yet
    # flat" (5-open) straddles 0-10 -> OVERLAPS, phrased as uncertain.
    _reset_recovery_store()
    s = recovery_state.get_or_create_state(patient_id="FLAT-14", surgery_date_raw=surgery_date, procedure="TKA")
    s.apply_verified_day(14)
    s.set_fact(rl.ROM_EXTENSION_DEGREES, rl.EXTENSION_FLAT_ANSWERS["not_full"], effective_postop_day=14)
    cp = rl.evaluate_checkpoint(s, procedure="TKA", metric=rl.ROM_EXTENSION_DEGREES)
    _check(cp.verdict == rl.CheckpointVerdict.OVERLAPS_STATED_RANGE and cp.checkpoint_day == 14, f"day-14 'not yet flat' overlaps 0-10: {cp.verdict}")
    _check("a measured number would settle it" in ri.format_assess_message(cp), "overlap wording asks for a number instead of guessing")
    print()


# ----------------------------------------------------------------------------
# 24. Walking-aid, walking-duration and stairs questions for both
#     procedures; THA gets walking + precautions, never knee ROM.
# ----------------------------------------------------------------------------

def test_walking_duration_stairs_precaution_questions_both_procedures() -> None:
    _section("24 -- Walking aid / duration / stairs questions for TKA and THA; THA precautions, no knee ROM [REAL-INTEGRATION + stubbed LLM]")

    _check(rl.asked_metrics_for("TKA") == (rl.ROM_FLEXION_DEGREES, rl.ROM_EXTENSION_DEGREES, rl.MOBILITY_STATUS, rl.WALKING_DURATION_MINUTES, rl.STAIRS), "TKA question order")
    _check(rl.asked_metrics_for("THA") == (rl.MOBILITY_STATUS, rl.WALKING_DURATION_MINUTES, rl.STAIRS, rl.HIP_PRECAUTIONS), "THA question order")
    _check(rl.asked_metrics_for("GEN") == (), "GEN asks nothing (grounded guidance)")

    surgery_date = _dynamic_surgery_date(29)  # Day 30
    _reset_recovery_store()
    results, _ = _run_interview(_handle_tha, "Q-THA", _THA_FULL_INTERVIEW, surgery_date=surgery_date, day=30)
    questions = [r["reply"] for r in results[:-1]]
    for q in questions:
        print(f"    THA: {q!r}")
    _check(ri._ASK_QUESTIONS[rl.MOBILITY_STATUS] in questions[0], "THA opens with the walking-aid question")
    _check(ri._ASK_QUESTIONS[rl.WALKING_DURATION_MINUTES] in questions[1], "then walking duration")
    _check(ri._ASK_QUESTIONS[rl.STAIRS] in questions[2], "then stairs")
    _check(ri._ASK_QUESTIONS[rl.HIP_PRECAUTIONS] in questions[3], "then hip precautions")
    all_text = " ".join(r["reply"].lower() for r in results)
    # ("bending the hip past a right angle" is a hip precaution, so the
    # knee-ROM check looks for knee/flexion/extension/degree wording.)
    _check(not any(w in all_text for w in ("knee", "flexion", "extension", "degrees")), f"THA never mentions knee ROM: {all_text[:300]!r}")
    _check(all(q.count("?") == 1 for q in questions), "one tracked question per THA turn")
    state = recovery_state.peek_state(patient_id="Q-THA", surgery_date_raw=surgery_date, procedure="THA")
    _check(state.get_fact(rl.MOBILITY_STATUS).value == "crutches", "'one crutch' -> crutches")
    _check(state.get_fact(rl.WALKING_DURATION_MINUTES).value == 20.0, "'about 20 minutes' -> 20")
    _check(state.get_fact(rl.STAIRS).value == "foot_over_foot", "'foot over foot now' -> foot_over_foot")
    _check(state.get_fact(rl.HIP_PRECAUTIONS).value == "following", "'yes, still following them' -> following")
    _check("hip precautions: keeping to your hip precautions" in results[-1]["reply"], "precautions are compared in the THA assessment")
    # UPDATED (readability pass): THA day 30 -> next milestone day 42 names hip
    # precautions and the walking aid (the two most relevant), nothing else.
    tha_milestone = [p for p in results[-1]["reply"].split("\n\n") if p.startswith("Next milestone")][0]
    _check("hip precautions:" in tha_milestone and "walking aid:" in tha_milestone and "stairs:" not in tha_milestone, f"THA next milestone lists precautions + walking aid only: {tha_milestone!r}")

    # TKA asks the same three walking questions after ROM.
    surgery_date_tka = _dynamic_surgery_date(9)
    _reset_recovery_store()
    results, _ = _run_interview(_handle_tka, "Q-TKA", _TKA_FULL_INTERVIEW, surgery_date=surgery_date_tka, day=10)
    joined = [r["reply"] for r in results]
    _check(ri._ASK_QUESTIONS[rl.MOBILITY_STATUS] in joined[2] and ri._ASK_QUESTIONS[rl.WALKING_DURATION_MINUTES] in joined[3]
           and ri._ASK_QUESTIONS[rl.STAIRS] in joined[4], "TKA asks walking aid, walking duration, stairs after ROM")

    # Extraction shapes for the new fields.
    def _extract(text: str, pending=None):
        _reset_recovery_store()
        s = recovery_state.get_or_create_state(patient_id="EXTR", surgery_date_raw=surgery_date_tka, procedure="TKA")
        s.apply_verified_day(10)
        if pending:
            s.mark_pending(pending)
        r = rl.extract_and_apply(text, s)
        return {f.field_name: f.value for f in r.applied_facts}

    _check(_extract("I can walk for half an hour") == {rl.WALKING_DURATION_MINUTES: 30.0}, "half an hour -> 30")
    _check(_extract("walking more than ten minutes now")[rl.WALKING_DURATION_MINUTES] == rl.WALKING_DURATION_ANSWERS["more"], "'more than ten minutes' -> range (10, open)")
    _check(_extract("15", pending=rl.WALKING_DURATION_MINUTES) == {rl.WALKING_DURATION_MINUTES: 15.0}, "bare number answers the pending duration")
    _check(_extract("I'm doing the stairs one at a time with the rail") == {rl.STAIRS: "one_at_a_time"}, "stairs one at a time")
    _check(_extract("I go up the stairs foot over foot") == {rl.STAIRS: "foot_over_foot"}, "foot over foot")
    _check(_extract("haven't tried stairs yet") == {rl.STAIRS: "not_yet"}, "not yet")
    _check(_extract("I'm using a frame") == {rl.MOBILITY_STATUS: "walker"}, "frame -> walker")
    _check(_extract("I use a stick now") == {rl.MOBILITY_STATUS: "cane"}, "stick -> cane")
    _check(_extract("no", pending=rl.HIP_PRECAUTIONS) == {rl.HIP_PRECAUTIONS: "not_following"}, "'no' to the precautions question")
    _check(_extract("I did my exercises this morning") == {rl.EXERCISE_COMPLETED: True}, "exercises done")
    _check(_extract("I started driving again and I'm back at work") == {rl.DRIVING: "driving", rl.RETURN_TO_WORK: "returned"}, "driving + work volunteered")
    print()


# ----------------------------------------------------------------------------
# 25. Multi-slot: several values volunteered at once are all accepted; only
#     what is missing is asked, one question per turn.
# ----------------------------------------------------------------------------

def test_multi_slot_volunteered_values_ask_only_missing() -> None:
    _section("25 -- Multi-slot: volunteered values all accepted, only the missing metric is asked [REAL-INTEGRATION + stubbed LLM]")

    surgery_date = _dynamic_surgery_date(9)
    _reset_recovery_store()
    results, _ = _run_interview(
        _handle_tka, "MULTI",
        ["I can bend to 85 degrees, I'm using a cane, I can walk 15 minutes and I do stairs one at a time"],
        surgery_date=surgery_date, day=10,
    )
    reply = results[0]["reply"]
    print(f"    reply: {reply!r}")
    state = recovery_state.peek_state(patient_id="MULTI", surgery_date_raw=surgery_date, procedure="TKA")
    for metric in (rl.ROM_FLEXION_DEGREES, rl.MOBILITY_STATUS, rl.WALKING_DURATION_MINUTES, rl.STAIRS):
        _check(state.is_current(metric), f"{metric} must be stored from the one message")
    _check(state.pending_field == rl.ROM_EXTENSION_DEGREES, f"only extension is missing -> it is the one question, got {state.pending_field}")
    _check(reply.count("?") == 1, "exactly one question")
    _check("flexion of 85°" in reply and "walking aid: a cane" in reply and "walking duration: 15 minutes" in reply and "stairs: one step at a time" in reply, "all four values are fed back")
    _check("(last question)" in reply, "the indicator reflects that only one metric remains")
    print()


# ----------------------------------------------------------------------------
# 26. Assessment names the checkpoint and the source at every checkpoint;
#     categorical verdicts; precautions needing review.
# ----------------------------------------------------------------------------

def test_assessment_names_checkpoint_and_source() -> None:
    _section("26 -- Every comparison names the nearest checkpoint and its source passage [REAL-INTEGRATION]")

    def _cp(procedure: str, metric: str, day: int, value):
        _reset_recovery_store()
        s = recovery_state.get_or_create_state(patient_id=f"CPS-{procedure}-{metric}-{day}", surgery_date_raw="2026-01-01T00:00:00.000", procedure=procedure)
        s.apply_verified_day(day)
        s.set_fact(metric, value, effective_postop_day=day)
        return rl.evaluate_checkpoint(s, procedure=procedure, metric=metric)

    # UPDATED (readability pass): the checkpoint is named "day-N" in plain words; the source
    # id lives ONLY in CheckpointResult.source_id (-> result["sources"]), never in the text.
    expectations = [
        (10, 7, "TKA-03", "day-7"),
        (14, 14, "EV-TKA-REHAB-02", "day-14"),
        (30, 21, "EV-TKA-REC-02", "day-21"),
        (42, 42, "EV-TKA-REC-03", "day-42"),
        (60, 42, "EV-TKA-REC-03", "day-42"),
        (84, 84, "EV-TKA-REC-05", "day-84"),
        (100, None, "EV-TKA-REC-06", "the long-term guidance"),
    ]
    for day, checkpoint_day, source, phrase in expectations:
        cp = _cp("TKA", rl.ROM_FLEXION_DEGREES, day, 95)
        text = ri.format_assess_message(cp)
        print(f"    TKA flexion day {day}: {text!r}")
        _check(cp.checkpoint_day == checkpoint_day and cp.source_id == source, f"day {day}: expected checkpoint {checkpoint_day}/{source}, got {cp.checkpoint_day}/{cp.source_id}")
        _check(phrase in text and source not in text and "earlier Post-Op Day" not in text, f"day {day}: reply names the checkpoint in plain words and no passage id: {text!r}")
        _check(ri.final_comparison_line(cp) != ri.comparison_clause(cp) and source not in ri.final_comparison_line(cp), f"day {day}: the final line never repeats the acknowledgement clause verbatim")
        _assert_no_forbidden_trajectory_language(text, f"TKA flexion day {day}")
        _assert_no_forbidden_robotic_language(text, f"TKA flexion day {day}")

    cp = _cp("TKA", rl.ROM_FLEXION_DEGREES, 42, 95)
    _check(cp.verdict == rl.CheckpointVerdict.BELOW_STATED_CHECKPOINT and "below the day-42 mark of more than 110°" in ri.format_assess_message(cp), f"day 42 flexion 95 is below the >110 mark: {ri.format_assess_message(cp)!r}")
    cp = _cp("TKA", rl.ROM_FLEXION_DEGREES, 42, 115)
    _check(cp.verdict == rl.CheckpointVerdict.MEETS_STATED_CHECKPOINT, "day 42 flexion 115 meets the >110 mark")
    cp = _cp("TKA", rl.ROM_EXTENSION_DEGREES, 42, 2)
    _check(cp.verdict == rl.CheckpointVerdict.OUTSIDE_STATED_RANGE and "outside the day-42 target of 0°" in ri.format_assess_message(cp), "day 42 extension 2 is outside 'fully straight', phrased neutrally")

    # Categorical verdicts: match / not yet / beyond; precautions review.
    cp = _cp("TKA", rl.MOBILITY_STATUS, 21, "cane")
    _check(cp.verdict == rl.CheckpointVerdict.MATCHES_STATED_STATE and cp.source_id == "EV-TKA-REHAB-03" and "EV-TKA-REHAB-03" not in ri.format_assess_message(cp), "cane at day 21 matches; source in metadata only")
    cp = _cp("TKA", rl.MOBILITY_STATUS, 21, "walker")
    text = ri.format_assess_message(cp)
    # UPDATED (readability pass): "not yet at the day-21 checkpoint: ..." is the one-clause form.
    _check(cp.verdict == rl.CheckpointVerdict.NOT_YET_AT_STATED_STATE and "not yet at the day-21 checkpoint" in text, f"walker at day 21 is 'not yet': {text!r}")
    _assert_no_forbidden_directional_language(text, "walker day 21")
    cp = _cp("TKA", rl.MOBILITY_STATUS, 21, "independent")
    # UPDATED (readability pass): "beyond the day-21 checkpoint: ..." is the one-clause form.
    _check(cp.verdict == rl.CheckpointVerdict.BEYOND_STATED_STATE and "beyond the day-21 checkpoint" in ri.format_assess_message(cp), "independent at day 21 is 'beyond'")
    cp = _cp("THA", rl.HIP_PRECAUTIONS, 14, "not_following")
    text = ri.format_assess_message(cp)
    _check(cp.verdict == rl.CheckpointVerdict.NEEDS_REVIEW and "check with your surgical team" in text and cp.source_id == "EV-THA-REC-02" and "EV-THA-REC-02" not in text, f"precautions not followed -> review: {text!r}")
    cp = _cp("THA", rl.MOBILITY_STATUS, 30, "crutches")
    _check(cp.checkpoint_day == 21 and cp.source_id == "EV-THA-REHAB-04", f"THA day 30 uses the day-21 THA entry: {cp}")
    print()


# ----------------------------------------------------------------------------
# 27. Never declines inside day 1-365; a metric with no data is named and
#     the interview moves on to another question.
# ----------------------------------------------------------------------------

def test_never_declines_inside_day_range_and_names_missing_data() -> None:
    _section("27 -- Never declines inside day 1-365; 'no data' is said and another metric is asked [REAL-INTEGRATION + stubbed LLM]")

    for day in (1, 7, 22, 84, 200, 365):
        surgery_date = _dynamic_surgery_date(day - 1)
        _reset_recovery_store()
        results, calls = _run_interview(_handle_tka, f"ND-{day}", _TKA_FULL_INTERVIEW, surgery_date=surgery_date, day=day)
        final = results[-1]["reply"]
        _check("Here's how things compare on post-op day" in final, f"day {day}: a full assessment is produced, got {final[:80]!r}")
        _check("can't give a supported verdict" not in final and "not able to compare" not in final, f"day {day}: never declines")
        _check(len(calls) == 1, f"day {day}: the final turn calls the LLM exactly once")
        if day == 1:
            _check("target to work towards" in final, "day 1 gives the day-7 target to work towards")
        if day > 84:
            # UPDATED (readability pass): the long-term passage id is in the sources metadata, not the text.
            # UPDATED (eval REPORT.md, c18): the long-term entry is the close's one next step.
            _check("EV-TKA-REC-06" in results[-1]["sources"] and "EV-TKA-REC-06" not in final and "Next milestone: longer term --" in final, f"day {day}: the long-term entry is used and offered")

    # Two misses on flexion: the agent says so, moves on, and the final
    # assessment names the missing metric instead of declining.
    surgery_date = _dynamic_surgery_date(9)
    _reset_recovery_store()
    results, _ = _run_interview(
        _handle_tka, "ND-MISS",
        ["How is my recovery going?", "I don't know", "no idea", "3 degrees", "a walker", "10 minutes", "not yet"],
        surgery_date=surgery_date, day=10,
    )
    moved_on = results[2]["reply"]
    print(f"    after two misses: {moved_on!r}")
    _check("I'll leave flexion for now" in moved_on, "the agent says it has no data for flexion")
    _check(ri._ASK_QUESTIONS[rl.ROM_EXTENSION_DEGREES] in moved_on and moved_on.count("?") == 1, "...and asks about another metric")
    state = recovery_state.peek_state(patient_id="ND-MISS", surgery_date_raw=surgery_date, procedure="TKA")
    _check(state.status_of(rl.ROM_FLEXION_DEGREES) == recovery_state.FieldStatus.UNAVAILABLE, "flexion is UNAVAILABLE after two misses")
    final = results[-1]["reply"]
    print(f"    final: {final!r}")
    _check("flexion: I don't have a value from you for this one" in final, "the final assessment names the metric with no data")
    _check("extension: 3°" in final and "walking aid: a walker/frame" in final, "the other metrics are still compared")
    print()


# ----------------------------------------------------------------------------
# 28. Server-derived day kept; a warning is logged when the client's
#     postop_day disagrees -- once per episode.
# ----------------------------------------------------------------------------

def test_server_day_kept_and_mismatch_warning_logged() -> None:
    _section("28 -- Server-derived post-op day is kept; client disagreement logs a WARNING once [REAL-INTEGRATION]")

    class _Capture(_logging.Handler):
        def __init__(self):
            super().__init__(level=_logging.WARNING)
            self.records = []

        def emit(self, record):
            self.records.append(record)

    logger = _logging.getLogger("agents.recovery")
    handler = _Capture()
    logger.addHandler(handler)
    try:
        surgery_date = _dynamic_surgery_date(9)  # server day 10
        _reset_recovery_store()
        fn, _ = _stub_answer_question()
        with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
            _handle_tka("MISMATCH", "How is my recovery going?", surgery_date=surgery_date, day=999)
            _handle_tka("MISMATCH", "80 degrees", surgery_date=surgery_date, day=999)
        state = recovery_state.peek_state(patient_id="MISMATCH", surgery_date_raw=surgery_date, procedure="TKA")
        _check(state.effective_postop_day == 10 and state.client_reported_postop_day == 999, "server day 10 kept; client 999 recorded as diagnostic only")
        warnings = [r for r in handler.records if "postop_day mismatch" in r.getMessage()]
        _check(len(warnings) == 1, f"exactly one WARNING per distinct disagreement, got {len(warnings)}")
        _check(warnings and warnings[0].levelno == _logging.WARNING and "client sent 999" in warnings[0].getMessage() and "server derived 10" in warnings[0].getMessage(), f"warning text: {warnings[0].getMessage() if warnings else None}")

        handler.records.clear()
        _reset_recovery_store()
        with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
            _handle_tka("AGREE", "How is my recovery going?", surgery_date=surgery_date, day=10)
        _check(not [r for r in handler.records if "postop_day mismatch" in r.getMessage()], "no warning when client and server agree")
    finally:
        logger.removeHandler(handler)
    print()


# ----------------------------------------------------------------------------
# 29. Persistence: the close writes flexion/extension/exercise into today's
#     metrics row; an abandoned interview persists nothing.
# ----------------------------------------------------------------------------

def test_final_turn_persists_metrics_and_abandoned_persists_nothing() -> None:
    _section("29 -- Close persists flexion/extension/exercise_completed into today's metrics; abandoned interviews persist nothing [REAL-INTEGRATION]")
    from patient_database import get_patient

    surgery_date = _dynamic_surgery_date(9)
    _seed_recovery_patient("PERSIST", surgery_type="Total Knee Arthroplasty (TKA)", surgery_date=surgery_date)
    _reset_recovery_store()
    messages = ["How is my recovery going?", "I can bend to 85 degrees and I did my exercises", "yes, fully flat",
                "I'm using a cane", "about 15 minutes", "one step at a time"]
    _run_interview(_handle_tka, "PERSIST", messages, surgery_date=surgery_date, day=10)
    rows = [r for r in get_patient("PERSIST")["metrics_history"] if r.get("date") == pm.today_iso()]
    print(f"    today's rows: {rows}")
    _check(len(rows) == 1, "exactly one row for today")
    _check(rows and rows[0]["rom_flexion"] == 85.0 and rows[0]["rom_extension"] == 0.0 and rows[0]["exercise_completed"] == 1 and rows[0]["day"] == 10,
           f"collected values written: {rows}")

    # A range-only extension ("nearly flat") writes nothing for that column.
    _seed_recovery_patient("PERSIST-RANGE", surgery_type="Total Knee Arthroplasty (TKA)", surgery_date=surgery_date)
    _reset_recovery_store()
    _run_interview(_handle_tka, "PERSIST-RANGE", ["I can bend to 85 degrees", "I don't know", "almost", "a cane", "15 minutes", "one at a time"], surgery_date=surgery_date, day=10)
    rows = [r for r in get_patient("PERSIST-RANGE")["metrics_history"] if r.get("date") == pm.today_iso()]
    _check(rows and rows[0]["rom_flexion"] == 85.0 and rows[0]["rom_extension"] is None, f"a range answer never fabricates a number: {rows}")

    # Abandoned after two answers: nothing written.
    _seed_recovery_patient("ABANDON", surgery_type="Total Knee Arthroplasty (TKA)", surgery_date=surgery_date)
    _reset_recovery_store()
    _run_interview(_handle_tka, "ABANDON", ["How is my recovery going?", "I can bend to 85 degrees"], surgery_date=surgery_date, day=10)
    rows = [r for r in get_patient("ABANDON")["metrics_history"] if r.get("date") == pm.today_iso()]
    _check(rows == [], f"an abandoned interview must persist nothing, got {rows}")

    # write_today_metrics round trip for the new columns, unknown patient fails softly.
    _check(pm.write_today_metrics("PERSIST", rom_flexion=90.0, exercise_completed=False) is True, "update of today's row with ROM columns")
    row = [r for r in get_patient("PERSIST")["metrics_history"] if r.get("date") == pm.today_iso()][0]
    _check(row["rom_flexion"] == 90.0 and row["exercise_completed"] == 0 and row["rom_extension"] == 0.0, f"update touches only supplied columns: {row}")
    _check(pm.write_today_metrics("NOBODY-REC", rom_flexion=80.0) is False, "unknown patient fails softly")
    print()


# ----------------------------------------------------------------------------
# 30. The close ends with the next milestone and a 'recovery check' offer;
#     the LLM explanation is optional, guarded, and never sets triage.
# ----------------------------------------------------------------------------

def test_final_turn_next_milestone_offer_and_llm_guard() -> None:
    _section("30 -- Close: next milestone + 'recovery check' offer; LLM explanation guarded; triage authoritative [REAL-INTEGRATION + stubbed LLM]")

    surgery_date = _dynamic_surgery_date(9)
    yellow = {"triage_level": "YELLOW", "is_escalated": True, "action_protocol": "Contact the orthopedic nursing hotline."}

    _reset_recovery_store()
    results, calls = _run_interview(_handle_tka, "CLOSE-DET", _TKA_FULL_INTERVIEW, surgery_date=surgery_date, day=10, precomputed_triage=yellow)
    final = results[-1]
    print(f"    deterministic close: {final['reply']!r}")
    _check("Next milestone: day 14 --" in final["reply"], "the close names the next milestone and its day")
    # UPDATED (readability pass): the next-milestone paragraph lists at most the two
    # metrics most relevant to the procedure and day; the guidance is cited once, in
    # plain words; no passage id and no "earlier Post-Op Day" wording anywhere.
    milestone_paragraph = [p for p in final["reply"].split("\n\n") if p.startswith("Next milestone")][0]
    _check(milestone_paragraph.split("Say 'recovery check'")[0].count(";") <= 1, f"at most two metrics in the next-milestone paragraph: {milestone_paragraph!r}")
    _check("flexion:" in milestone_paragraph and "extension:" in milestone_paragraph, "TKA day 14: knee bend and straightening are the two most relevant metrics")
    _check(final["reply"].count(ri.CITATION) == 1, f"the discharge guidance is cited exactly once: {final['reply']!r}")
    _check(not _re.search(r"\b(?:EV-[A-Z]+-[A-Z]+-\d+|TKA-\d+|THA-\d+)\b", final["reply"]) and "earlier Post-Op Day" not in final["reply"], "no passage id or checkpoint jargon in the close")
    _check(all(s in final["sources"] for s in ("TKA-03", "EV-TKA-REC-01", "EV-TKA-REHAB-02")), f"passage ids travel in sources: {final['sources']}")
    for mid in results[:-1]:
        _check(mid["reply"].count(ri.CITATION) <= 1 and not _re.search(r"\b(?:EV-[A-Z]+-[A-Z]+-\d+|TKA-\d+)\b", mid["reply"]), f"mid-interview: at most one citation, no passage id: {mid['reply']!r}")
    _check(final["reply"].rstrip().endswith("Say 'recovery check' at day 14 and I'll compare."), "the close ends with the follow-up offer")
    _check(final["engine"] == RecoveryProgressAgent.ENGINE_NAME, "empty LLM reply -> deterministic engine")
    _check(final["triage_level"] == "YELLOW" and final["is_escalated"] is True, "triage copied from the upstream result")
    _check(len(calls) == 1 and "RECOVERY COMPARISON (untrusted data" in calls[0]["domain_instruction"], "the deterministic block travels fenced in the LLM instruction")
    _check("say you don't have that information" in calls[0]["domain_instruction"], "the abstention sentence is in the instruction")
    _check(calls[0]["postop_day"] == 10 and "day 10" in calls[0]["user_message"], "the LLM is given the server day and a retrieval query")

    # Accepted LLM explanation: appears ABOVE the unchanged deterministic block.
    _reset_recovery_store()
    good = "Your bend and straightening are both inside the week-one guide, so keep working on the exercises your physiotherapist set."
    results, _ = _run_interview(_handle_tka, "CLOSE-LLM", _TKA_FULL_INTERVIEW, surgery_date=surgery_date, day=10, stub_reply=good, precomputed_triage=yellow)
    final = results[-1]
    _check(final["reply"].startswith(good) and "Here's how things compare on post-op day 10" in final["reply"], "accepted explanation sits above the deterministic block")
    _check(final["engine"] == RecoveryProgressAgent.ENGINE_FINAL, "engine reflects the accepted explanation")
    _check(final["triage_level"] == "YELLOW", "the LLM path never changes the triage level")

    # Rejected: an unsourced number / trajectory language -> deterministic only.
    for bad in ("You are on track and should reach 130 degrees by next week.", "You are well ahead of schedule."):
        _reset_recovery_store()
        results, _ = _run_interview(_handle_tka, "CLOSE-BAD", _TKA_FULL_INTERVIEW, surgery_date=surgery_date, day=10, stub_reply=bad)
        final = results[-1]
        _check(bad not in final["reply"] and final["engine"] == RecoveryProgressAgent.ENGINE_NAME, f"rejected explanation never reaches the patient: {bad!r}")
    _check(ri.llm_body_is_acceptable("Keep going with the heel slides; 85 degrees is inside the guide.", allowed_numbers=["85"]), "numbers present in the block are allowed")
    _check(not ri.llm_body_is_acceptable("Aim for 130 degrees.", allowed_numbers=["85"]), "numbers absent from the block are rejected")

    # Long-term close.
    surgery_date_long = _dynamic_surgery_date(99)
    _reset_recovery_store()
    results, _ = _run_interview(_handle_tka, "CLOSE-LONG", _TKA_FULL_INTERVIEW, surgery_date=surgery_date_long, day=100)
    # UPDATED (eval REPORT.md, c18): past day 84 the close still names ONE next step.
    _check("Next milestone: longer term --" in results[-1]["reply"] and "Say 'recovery check' any time and I'll compare with today." in results[-1]["reply"], f"long-term close: {results[-1]['reply'][-200:]!r}")

    # 'recovery check' routes to the Recovery agent.
    _reset_recovery_store()
    fn, _ = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        routed = LAMOrchestrator.process(
            patient_id="RECHECK", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="recovery check", surgery_date=surgery_date,
        )
    _check(routed["intent"] == IntentLabel.RECOVERY_PROGRESS.value and routed["target_agent"] == TargetAgent.RECOVERY_AGENT.value, f"'recovery check' routes to RecoveryProgressAgent: {routed['intent']}")
    _check(routed["reply"].count("?") == 1, "...and opens the interview with one question")
    print()


# ----------------------------------------------------------------------------
# 31. Continuation hook accepts the new answer shapes, still rejects
#     off-topic messages.
# ----------------------------------------------------------------------------

def test_continuation_accepts_new_answer_shapes() -> None:
    _section("31 -- check_recovery_continuation(): new fields and yes/no-shaped answers [REAL-INTEGRATION]")

    surgery_date = "2026-09-02T00:00:00.000"

    def _pending(metric: str, *, variant: str = "primary", confirm_value=None, procedure: str = "TKA") -> None:
        _reset_recovery_store()
        s = recovery_state.get_or_create_state(patient_id="CT-NEW", surgery_date_raw=surgery_date, procedure=procedure)
        s.mark_pending(metric, variant=variant, confirm_value=confirm_value)

    def _matches(message: str, procedure: str = "TKA") -> bool:
        return ri.check_recovery_continuation(patient_id="CT-NEW", surgery_date_raw=surgery_date, procedure=procedure, user_message=message)

    positive = [
        (rl.MOBILITY_STATUS, "primary", None, "I'm using a stick"),
        (rl.WALKING_DURATION_MINUTES, "primary", None, "about 20 minutes"),
        (rl.WALKING_DURATION_MINUTES, "primary", None, "20"),
        (rl.WALKING_DURATION_MINUTES, "alt", None, "more than that"),
        (rl.STAIRS, "primary", None, "one at a time"),
        (rl.STAIRS, "primary", None, "not yet"),
        (rl.HIP_PRECAUTIONS, "primary", None, "yes"),
        (rl.ROM_EXTENSION_DEGREES, "alt", None, "no"),
        (rl.ROM_FLEXION_DEGREES, "confirm", 80.0, "yes"),
        (rl.ROM_FLEXION_DEGREES, "confirm", 80.0, "it's about 85 now"),
        (rl.ROM_FLEXION_DEGREES, "primary", None, "85"),
    ]
    for metric, variant, confirm_value, message in positive:
        _pending(metric, variant=variant, confirm_value=confirm_value, procedure="THA" if metric == rl.HIP_PRECAUTIONS else "TKA")
        _check(_matches(message, "THA" if metric == rl.HIP_PRECAUTIONS else "TKA") is True, f"pending {metric}/{variant} + {message!r} must continue")

    for metric in (rl.MOBILITY_STATUS, rl.WALKING_DURATION_MINUTES, rl.STAIRS, rl.ROM_FLEXION_DEGREES):
        for message in ("My wound is red and leaking.", "I forgot to take my medication.", "What should I eat tonight?"):
            _pending(metric)
            _check(_matches(message) is False, f"pending {metric} + off-topic {message!r} must NOT continue")

    # A bare "yes" to the PRIMARY flexion question (not yes/no shaped) is not a continuation.
    _pending(rl.ROM_FLEXION_DEGREES)
    _check(_matches("yes") is False, "'yes' does not answer 'how many degrees' -- classification runs instead")
    # A number inside an unrelated sentence is NOT a loose measurement.
    _pending(rl.ROM_FLEXION_DEGREES)
    _check(_matches("I took 2 tablets this morning") is False, "a medication message with a number must not be stolen as a measurement")
    _check(rl.loose_number("i took 2 tablets this morning") is None and rl.loose_number("it's about 85 now") == 85.0, "loose_number accepts filler-only replies")
    print()


# ----------------------------------------------------------------------------
# 32. Regressions from the conversation eval (eval/agents/REPORT.md):
#     a number in another unit is not an angle, an opening value is kept,
#     and the long-term close still ends with one next step.
# ----------------------------------------------------------------------------

def test_eval_report_regressions() -> None:
    _section("32 -- Eval regressions: 'about 5 minutes' is not flexion; opening 'about 60 degrees' kept; long-term next step [REAL-INTEGRATION + stubbed LLM]")

    surgery_date = _dynamic_surgery_date(3)

    # (a) "about 5 minutes" while waiting for flexion: a non-fit, nothing
    # stored, and the clarifying question -- never "flexion of 5°".
    _reset_recovery_store()
    results, _ = _run_interview(_handle_tka, "EVAL-UNIT", ["Am I on track with my knee?", "about 5 minutes"], surgery_date=surgery_date, day=4)
    opening, unfit = results
    _check("how many degrees can you currently bend" in opening["reply"], f"the opening asks for flexion: {opening['reply']!r}")
    state = recovery_state.get_or_create_state(patient_id="EVAL-UNIT", surgery_date_raw=surgery_date, procedure="TKA")
    _check(not state.is_current(rl.ROM_FLEXION_DEGREES), f"'about 5 minutes' is not stored as flexion: {state.get_fact(rl.ROM_FLEXION_DEGREES)}")
    _check(not state.is_current(rl.WALKING_DURATION_MINUTES), "...nor as a walking duration nobody asked about")
    _check("5°" not in unfit["reply"] and "flexion: 5" not in unfit["reply"], f"no 5-degree comparison: {unfit['reply']!r}")
    _check(unfit["reply"].startswith("Sorry, I didn't quite catch that as an angle.") and "in degrees" in unfit["reply"], f"the clarifying question follows: {unfit['reply']!r}")
    _check(state.pending_field == rl.ROM_FLEXION_DEGREES, "flexion is still the open question")

    # What the pending flexion question accepts: a degrees unit, a bare
    # number in 0-150, or a cued phrase; nothing else.
    accepted = {"about 60 degrees": 60.0, "75": 75.0, "it's about 85 now": 85.0, "I can bend to 95": 95.0, "120 deg": 120.0}
    for message, expected in accepted.items():
        _reset_recovery_store()
        s = recovery_state.get_or_create_state(patient_id="EVAL-UNIT", surgery_date_raw=surgery_date, procedure="TKA")
        s.mark_pending(rl.ROM_FLEXION_DEGREES)
        result = rl.extract_and_apply(message, s)
        _check(s.get_fact(rl.ROM_FLEXION_DEGREES) is not None and s.get_fact(rl.ROM_FLEXION_DEGREES).value == expected and not result.unfit_fields, f"pending flexion + {message!r} -> {expected}")
    for message in ("about 5 minutes", "5 mins", "200", "about 3 hours", "10 steps"):
        _reset_recovery_store()
        s = recovery_state.get_or_create_state(patient_id="EVAL-UNIT", surgery_date_raw=surgery_date, procedure="TKA")
        s.mark_pending(rl.ROM_FLEXION_DEGREES)
        result = rl.extract_and_apply(message, s)
        _check(s.get_fact(rl.ROM_FLEXION_DEGREES) is None and result.unfit_fields == (rl.ROM_FLEXION_DEGREES,), f"pending flexion + {message!r} is a non-fit")
    _reset_recovery_store()
    s = recovery_state.get_or_create_state(patient_id="EVAL-UNIT", surgery_date_raw=surgery_date, procedure="TKA")
    s.mark_pending(rl.ROM_EXTENSION_DEGREES)
    rl.extract_and_apply("about 5 minutes", s)
    _check(s.get_fact(rl.ROM_EXTENSION_DEGREES) is None, "the same rule holds for extension")
    _reset_recovery_store()
    s = recovery_state.get_or_create_state(patient_id="EVAL-UNIT", surgery_date_raw=surgery_date, procedure="TKA")
    s.mark_pending(rl.WALKING_DURATION_MINUTES)
    rl.extract_and_apply("about 15 minutes", s)
    _check(s.get_fact(rl.WALKING_DURATION_MINUTES) is not None and s.get_fact(rl.WALKING_DURATION_MINUTES).value == 15.0, "a minutes answer still fits the walking question")
    _reset_recovery_store()
    s = recovery_state.get_or_create_state(patient_id="EVAL-UNIT", surgery_date_raw=surgery_date, procedure="TKA")
    s.mark_pending(rl.WALKING_DURATION_MINUTES)
    rl.extract_and_apply("about 60 degrees", s)
    _check(s.get_fact(rl.WALKING_DURATION_MINUTES) is None, "...and a degrees answer does not fit it")
    _pending_reset = recovery_state.get_or_create_state(patient_id="CT-UNIT", surgery_date_raw=surgery_date, procedure="TKA")
    _pending_reset.mark_pending(rl.ROM_FLEXION_DEGREES)
    _check(ri.check_recovery_continuation(patient_id="CT-UNIT", surgery_date_raw=surgery_date, procedure="TKA", user_message="about 5 minutes") is True, "the continuation hook still keeps the reply with Recovery, so the clarifying question is asked")

    # (b) A value volunteered in the opening message is extracted and
    # confirmed back, not re-asked.
    _reset_recovery_store()
    results, _ = _run_interview(_handle_tka, "EVAL-OPEN", ["about 60 degrees"], surgery_date=surgery_date, day=4)
    reply = results[0]["reply"]
    state = recovery_state.get_or_create_state(patient_id="EVAL-OPEN", surgery_date_raw=surgery_date, procedure="TKA")
    _check(state.is_current(rl.ROM_FLEXION_DEGREES) and state.get_fact(rl.ROM_FLEXION_DEGREES).value == 60.0, f"opening 'about 60 degrees' is stored as flexion: {state.get_fact(rl.ROM_FLEXION_DEGREES)}")
    _check("flexion of 60°" in reply, f"the value is confirmed back: {reply!r}")
    _check("how many degrees can you currently bend" not in reply and state.pending_field != rl.ROM_FLEXION_DEGREES, f"flexion is not re-asked: {reply!r}")
    _reset_recovery_store()
    results, _ = _run_interview(_handle_tha, "EVAL-OPEN-THA", ["I keep it under 90 degrees"], surgery_date=surgery_date, day=4)
    tha_state = recovery_state.get_or_create_state(patient_id="EVAL-OPEN-THA", surgery_date_raw=surgery_date, procedure="THA")
    _check(tha_state.get_fact(rl.ROM_FLEXION_DEGREES) is None, "a THA opening with degrees is never read as knee flexion")

    # (c) After day 84: one concrete next step from the long-term entry,
    # then the check-in offer.
    _reset_recovery_store()
    _seed_recovery_patient("EVAL-LONG", surgery_type="Total Knee Arthroplasty (TKA)", surgery_date=_dynamic_surgery_date(89))
    results, _ = _run_interview(
        _handle_tka, "EVAL-LONG",
        ["Is my recovery on track now?", "115 degrees", "0 degrees, it goes fully straight", "walking without any aid now", "about 60 minutes", "foot over foot"],
        surgery_date=_dynamic_surgery_date(89), day=90,
    )
    final = results[-1]["reply"]
    paragraph = [p for p in final.split("\n\n") if p.startswith("Next milestone")]
    _check(len(paragraph) == 1, f"the long-term close has a next-milestone paragraph: {final!r}")
    if paragraph:
        step = paragraph[0].split("Say 'recovery check'")[0]
        _check(step.startswith("Next milestone: longer term -- daily activities: back to many previous activities"), f"built from the TKA long-term entry: {step!r}")
        _check(";" not in step, f"exactly one next step: {step!r}")
    _check(final.rstrip().endswith("Say 'recovery check' any time and I'll compare with today."), "the close ends with the check-in offer")
    _check("Longer term, the guidance describes" not in final, "the old step-less wording is gone")
    print()


# ----------------------------------------------------------------------------
# 33. Prompt boilerplate the model echoes is stripped before the patient
#     sees the explanation (live-run fixtures, eval/agents/LIVE_REPORT.md).
# ----------------------------------------------------------------------------

# Verbatim llama3.2 replies that were accepted and shipped with the echo.
LIVE_C04_DIRECT = (
    "Here's a friendly answer to the user's question:\n\nYou're making great progress on day 30 after your Total Hip "
    "Arthroplasty (THA)! You're doing a great job of following your hip precautions, which is helping your hip heal "
    "properly. Now that you're walking for 20 minutes at a stretch, your next goal is to work on reducing your walking "
    "aid, which your physiotherapist will advise on. In the meantime, don't forget to take care of your hip by icing "
    "it after activities and elevating your leg to reduce swelling."
)
LIVE_C04_ORCH = (
    "Here's a friendly answer to the user's question:\n\nYou're doing great on day 30 after your Total Hip Arthroplasty "
    "(THA)! You're meeting all the milestones, including walking for 20 minutes without any issues and using a crutch "
    "as needed. For your next step, your surgeon will confirm when the hip precautions have ended, but in the meantime, "
    "keep up the good work with your physiotherapy, icing, and elevating your leg to help with healing."
)
LIVE_C19_DIRECT = (
    "Here's a friendly answer to the user's question:\n\n\"Hi! On day 20 after your Total Knee Arthroplasty (TKA), your "
    "knee is making good progress. You're doing great with your walking aid - using a walker is right where you should "
    "be at this stage. For next steps, focus on bending your knee a bit more each day, aiming to get closer to 110 "
    "degrees by the end of week six. Don't forget to take care of your knee by icing it after activities and elevating "
    "your leg to reduce swelling. Keep up the good work!\""
)
LIVE_C19_ORCH = (
    "Here's a friendly answer directly addressing the user's question:\n\nYour knee is making good progress on day 20 "
    "after Total Knee Arthroplasty (TKA). You're doing great with your walking aid, using a walker, and your walking "
    "duration is meeting the expected mark. For next steps, focus on improving your knee's range of motion, especially "
    "flexion, and try to incorporate icing and elevating your leg to help with recovery."
)


def test_llm_prompt_boilerplate_stripped() -> None:
    _section("33 -- LLM explanation: prompt boilerplate ('Here's a friendly answer...') stripped; nothing left -> block alone [REAL-INTEGRATION + stubbed LLM]")

    block = "Here's how things compare on post-op day 30, according to the discharge guidance:\n- walking duration: 20 minutes"
    for name, raw, opening in (
        ("c04 direct", LIVE_C04_DIRECT, "You're making great progress on day 30"),
        ("c04 orchestrator", LIVE_C04_ORCH, "You're doing great on day 30"),
        ("c19 direct", LIVE_C19_DIRECT, "Hi! On day 20 after your Total Knee Arthroplasty"),
        ("c19 orchestrator", LIVE_C19_ORCH, "Your knee is making good progress on day 20"),
    ):
        stripped = ri.strip_prompt_boilerplate(raw)
        _check(stripped.startswith(opening), f"{name}: the answer starts at its first real sentence: {stripped[:60]!r}")
        _check("friendly answer" not in stripped.lower() and "user's question" not in stripped.lower(), f"{name}: no prompt echo left")
        _check(not stripped.startswith('"') and not stripped.endswith('"'), f"{name}: quotes around the whole answer removed")
        composed = ri.compose_final_reply(raw, block)
        _check(composed.startswith(opening) and composed.endswith(block) and "Here's a friendly" not in composed, f"{name}: the composed reply carries no echo")
    _check(ri.strip_prompt_boilerplate(LIVE_C19_DIRECT).endswith("Keep up the good work!"), "c19: the closing quote is removed with the opening one")

    # Lead-in variants and instruction restatements.
    _check(ri.strip_prompt_boilerplate("Here is a friendly, 2-3 sentence answer:\nKeep walking little and often.") == "Keep walking little and often.", "'Here is a friendly...' lead-in")
    _check(ri.strip_prompt_boilerplate("Sure! Here's a plain-language explanation: Keep walking little and often.") == "Keep walking little and often.", "inline lead-in on the answer's own line")
    _check(ri.strip_prompt_boilerplate("Keep walking little and often.\nI've written this in plain, everyday language for the user's question.") == "Keep walking little and often.", "a line restating the instruction is dropped")
    _check(ri.strip_prompt_boilerplate("Here is how your walking compares: it meets the guide.") == "Here is how your walking compares: it meets the guide.", "an ordinary sentence with a colon is kept")

    # Nothing but boilerplate: rejected, and the deterministic block goes alone.
    echo_only = "Here's a friendly answer to the user's question:\n\n\"\""
    _check(ri.strip_prompt_boilerplate(echo_only) == "", "an echo with no answer strips to nothing")
    _check(ri.compose_final_reply(echo_only, block) == block, "nothing left -> the deterministic block alone")
    _check(not ri.llm_body_is_acceptable(echo_only, allowed_numbers=[]), "an echo-only reply is not accepted")

    # End to end through the agent.
    surgery_date = _dynamic_surgery_date(9)
    good = "Your bend and straightening are both inside the week-one guide, so keep working on the exercises your physiotherapist set."
    _reset_recovery_store()
    results, _ = _run_interview(_handle_tka, "ECHO-LLM", _TKA_FULL_INTERVIEW, surgery_date=surgery_date, day=10,
                                stub_reply=f"Here's a friendly answer to the user's question:\n\n\"{good}\"")
    final = results[-1]
    _check(final["reply"].startswith(good) and "friendly answer" not in final["reply"], f"the patient sees the answer without the echo: {final['reply'][:80]!r}")
    _check(final["engine"] == RecoveryProgressAgent.ENGINE_FINAL, "the stripped explanation is still the LLM's")
    _reset_recovery_store()
    results, _ = _run_interview(_handle_tka, "ECHO-ONLY", _TKA_FULL_INTERVIEW, surgery_date=surgery_date, day=10, stub_reply=echo_only)
    final = results[-1]
    # UPDATED (summary line, test 34): the deterministic block now opens with its one-line summary.
    _check(final["reply"].startswith("All five things we checked") and "\nHere's how things compare on post-op day 10" in final["reply"]
           and final["engine"] == RecoveryProgressAgent.ENGINE_NAME,
           f"echo only -> the deterministic block alone: {final['reply'][:80]!r}")
    print()


# ----------------------------------------------------------------------------
# 34. Summary line at the top of the close: counts and direction only, built
#     from the checkpoint comparisons already made.
# ----------------------------------------------------------------------------

def test_final_block_summary_line() -> None:
    _section("34 -- Close summary line: counts + direction, no judgement words, no new numbers [REAL-INTEGRATION]")

    def _cp(procedure: str, metric: str, day: int, value):
        _reset_recovery_store()
        s = recovery_state.get_or_create_state(patient_id=f"SUM-{procedure}-{metric}-{day}-{value}", surgery_date_raw="2026-01-01T00:00:00.000", procedure=procedure)
        s.apply_verified_day(day)
        s.set_fact(metric, value, effective_postop_day=day)
        return rl.evaluate_checkpoint(s, procedure=procedure, metric=metric)

    def _improving(series: str):
        return ri.TrendNote(f"improving: {series}", series=series, direction="improving")

    def _block(procedure: str, day: int, comparisons) -> str:
        next_checkpoint, next_entries = rl.next_milestone(procedure, day)
        return ri.format_final_assessment(
            procedure=procedure, postop_day=day, comparisons=comparisons, missing_metrics=[],
            next_checkpoint=next_checkpoint, next_entries=next_entries, metrics_of_interest=[c.metric for c, _ in comparisons],
        )

    def _check_rules(block: str, label: str) -> str:
        first, rest = block.split("\n", 1)
        lower = first.lower()
        for word in ("on track", "behind", "slow", "normal", "doing well", "ahead", "better", "worse"):
            _check(word not in lower, f"{label}: judgement word {word!r} in the summary: {first!r}")
        for number in _re.findall(r"\d+", first):
            _check(number in rest, f"{label}: summary number {number} is not elsewhere in the block: {first!r}")
        _check(rest.startswith("Here's how things compare on post-op day"), f"{label}: the header follows the summary: {rest[:80]!r}")
        return first

    # All in range (two with an improving trend).
    tka = [
        (_cp("TKA", rl.ROM_FLEXION_DEGREES, 10, 85), _improving("70 -> 80 -> 85")),
        (_cp("TKA", rl.ROM_EXTENSION_DEGREES, 10, 5), _improving("8 -> 5")),
        (_cp("TKA", rl.MOBILITY_STATUS, 10, "cane"), None),
        (_cp("TKA", rl.STAIRS, 10, "one_at_a_time"), None),
    ]
    block = _block("TKA", 10, tka)
    first = _check_rules(block, "all-in-range")
    print(f"    all-in-range: {first!r}")
    _check(first == "All four things we checked are within the expected range for your stage, and flexion and extension are improving over the week.", f"all-in-range summary: {first!r}")
    for checkpoint, trend in tka:
        _check(f"- {ri.final_comparison_line(checkpoint, trend=trend)}" in block, "per-metric lines unchanged")
    _check("Next milestone: day 14 --" in block, "next-milestone sentence unchanged")

    # One below range.
    tha = [
        (_cp("THA", rl.MOBILITY_STATUS, 30, "crutches"), None),
        (_cp("THA", rl.WALKING_DURATION_MINUTES, 30, 5), None),
        (_cp("THA", rl.STAIRS, 30, "foot_over_foot"), None),
        (_cp("THA", rl.HIP_PRECAUTIONS, 30, "following"), None),
    ]
    _check(tha[1][0].verdict == rl.CheckpointVerdict.BELOW_STATED_CHECKPOINT, f"fixture: 5 minutes is below the day-21 mark: {tha[1][0].verdict}")
    first = _check_rules(_block("THA", 30, tha), "one-below")
    print(f"    one-below: {first!r}")
    _check(first == "Three of four are within the expected range for your stage; walking duration is below the day-21 guide, so that's the one to work on.", f"one-below summary: {first!r}")

    # State-only items only: "as described", never below range.
    state_only = [
        (_cp("TKA", rl.ROM_FLEXION_DEGREES, 25, 60), None),
        (_cp("TKA", rl.ROM_EXTENSION_DEGREES, 25, 20), None),
    ]
    _check(all(c.verdict == rl.CheckpointVerdict.STATE_ONLY for c, _ in state_only), "fixture: TKA day-21 ROM entries carry no number")
    first = _check_rules(_block("TKA", 25, state_only), "state-only")
    print(f"    state-only: {first!r}")
    _check(first == "Both things we checked are as the guidance describes for your stage.", f"state-only summary: {first!r}")
    _check("below" not in first and "work on" not in first, "a state-only item is never called below range")
    mixed = tka[:1] + [(_cp("TKA", rl.WALKING_DURATION_MINUTES, 10, 15), None)]
    first = ri.format_summary_line(mixed)
    _check(first == "Both things we checked are within the expected range or as described for your stage, and flexion is improving over the week.", f"within + state-only summary: {first!r}")

    # Single item, phrased singly.
    first = _check_rules(_block("TKA", 10, tka[:1]), "single-within")
    print(f"    single-within: {first!r}")
    _check(first == "Flexion, the one thing we checked, is within the expected range for your stage, and it is improving over the week.", f"single-item summary: {first!r}")
    first = _check_rules(_block("THA", 30, tha[1:2]), "single-below")
    print(f"    single-below: {first!r}")
    _check(first == "Walking duration is below the day-21 guide, so that's the one to work on.", f"single below summary: {first!r}")

    # Nothing measured: no summary line.
    _check(ri.format_summary_line([]) is None, "no comparisons -> no summary")
    _check(_block("TKA", 10, []).startswith("Here's how things compare on post-op day 10"), "no comparisons -> block starts with the header")
    print()


def main() -> int:
    _run(test_postop_day_derivation)
    _run(test_checkpoint_day_6_7_8_boundary)
    _run(test_assessment_wording_and_negative_assertions)
    _run(test_decline_reasons)
    _run(test_extraction_regressions)
    _run(test_executor_state_transitions)
    _run(test_immediate_metric_assessment_end_to_end)
    _run(test_multi_fact_one_action)
    _run(test_single_retrieval_per_turn)
    _run(test_real_keyword_fallback_retrieval)
    _run(test_continuation_helper)
    _run(test_real_classifier_bend_misroute_regression)
    _run(test_safety_and_scope_precedence)
    _run(test_procedure_isolation)
    _run(test_client_reported_postop_day_is_diagnostic_only)
    _run(test_routing_and_response_shape)
    _run(test_postop_day_procedure_and_chat_history_reach_grounded_guidance)
    _run(test_conversational_style_and_grounding)
    _run(test_milestone_file_sources_exist_in_corpus)
    _run(test_select_checkpoint_nearest_at_or_before_and_long_term)
    _run(test_memory_confirms_logged_flexion_and_shows_trend)
    _run(test_request_current_rom_seeded_and_never_asked)
    _run(test_simpler_extension_question_maps_to_range)
    _run(test_walking_duration_stairs_precaution_questions_both_procedures)
    _run(test_multi_slot_volunteered_values_ask_only_missing)
    _run(test_assessment_names_checkpoint_and_source)
    _run(test_never_declines_inside_day_range_and_names_missing_data)
    _run(test_server_day_kept_and_mismatch_warning_logged)
    _run(test_final_turn_persists_metrics_and_abandoned_persists_nothing)
    _run(test_final_turn_next_milestone_offer_and_llm_guard)
    _run(test_continuation_accepts_new_answer_shapes)
    _run(test_eval_report_regressions)
    _run(test_llm_prompt_boilerplate_stripped)
    _run(test_final_block_summary_line)

    print("=" * 78)
    if _FAILURES:
        print(f"RESULT: {len(_FAILURES)} FAILURE(S)")
        for f in _FAILURES:
            print(f"  - {f}")
        return 1
    print("RESULT: ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
