"""
Recovery Progress Agent test suite -- Pass 3 (repository tests + regression
review) rewrite.

This file previously tested a SIMPLER RecoveryProgressAgent that always
called ChatAgent.answer_question() with a RAG-enriched domain_instruction.
That architecture no longer exists: TKA now runs a fully deterministic
OBSERVE -> DECIDE -> ACT -> UPDATE loop (recovery_state.py / recovery_logic.py
/ recovery_integration.py, wired together in
agents.specialized_agents.RecoveryProgressAgent) and never calls ChatAgent at
all. Only THA/GEN (no sourced quantitative milestone in the corpus) still
fall through to the original, unmodified ChatAgent/RAG grounded-guidance
path. Every test below was re-derived from that approved architecture, not
patched to "happen to pass" -- see the Pass-3 report for the full old-test
migration table.

Every test function is labeled MOCKED-BOUNDARY or REAL-INTEGRATION in its
docstring/print header (see Pass-3 instructions Section 3):

    MOCKED-BOUNDARY -- mocks ClinicalKnowledgeBase.retrieve_detailed and/or
        ChatAgent.answer_question to prove ONE exact invariant (call count,
        forced evidence shape, state transition) without depending on which
        optional RAG backend happens to be installed.
    REAL-INTEGRATION -- exercises the actual recovery_state / recovery_logic
        / recovery_integration / orchestrator / classifier code, including
        (where noted) the REAL keyword-fallback RAG corpus. This environment
        has no chromadb / sentence-transformers installed, so "REAL
        keyword-fallback retrieval" is the most of the RAG stack these tests
        can honestly claim to exercise -- semantic_chroma is never reached
        here, and no test claims otherwise.

Plain-Python script (no pytest dependency), consistent with
test_phase2_intent.py / test_phase3_rag.py / test_phase4_agents.py.

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
    if not condition:
        _FAILURES.append(message)
        print(f"    !! FAILED: {message}")


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


def _assert_no_forbidden_trajectory_language(reply: str, label: str) -> None:
    lower = reply.lower()
    for phrase in _FORBIDDEN_TRAJECTORY_PHRASES:
        _check(phrase not in lower, f"{label}: forbidden trajectory phrase {phrase!r} leaked into reply: {reply!r}")


def _assert_no_forbidden_directional_language(reply: str, label: str) -> None:
    lower = reply.lower()
    for phrase in _FORBIDDEN_DIRECTIONAL_PHRASES:
        _check(phrase not in lower, f"{label}: forbidden directional phrase {phrase!r} leaked into reply: {reply!r}")


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
    _check("earlier Post-Op Day 7" in reply8, "Day 8 reply must refer to the EARLIER Post-Op Day 7 checkpoint, not a Day-8 target")
    _check("Day 8 checkpoint" not in reply8, "Day 8 reply must not invent a Day-8 checkpoint")
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
    cp = checkpoint_for(6, rl.ROM_FLEXION_DEGREES, 60)
    reply = ri.format_assess_message(cp)
    print(f"    Day6 flex60: {reply!r}")
    _check(cp.verdict == rl.CheckpointVerdict.TARGET_NOT_YET_DUE, "Day6 flex60 must be TARGET_NOT_YET_DUE")
    _check("below" not in reply.lower(), "Day6 flex60 (not yet due) must not say 'below'")
    _assert_no_forbidden_trajectory_language(reply, "Day6 flex60")

    # Day 7 + flexion 80 -> within 70-90 stated for Post-Op Day 7.
    cp = checkpoint_for(7, rl.ROM_FLEXION_DEGREES, 80)
    reply = ri.format_assess_message(cp)
    print(f"    Day7 flex80: {reply!r}")
    _check(cp.verdict == rl.CheckpointVerdict.MEETS_STATED_CHECKPOINT, "Day7 flex80 must MEET the checkpoint")
    _check("70" in reply and "90" in reply, "Day7 flex80 must state the 70-90 range")
    _check("Post-Op Day 7" in reply and "earlier" not in reply, "Day7 flex80: day IS the checkpoint day, must not say 'earlier'")
    _assert_no_forbidden_trajectory_language(reply, "Day7 flex80")

    # Day 8 + flexion 80 -> within range stated for the EARLIER Day-7 checkpoint.
    cp = checkpoint_for(8, rl.ROM_FLEXION_DEGREES, 80)
    reply = ri.format_assess_message(cp)
    print(f"    Day8 flex80: {reply!r}")
    _check("earlier Post-Op Day 7" in reply, "Day8 flex80 must reference the earlier Post-Op Day 7 checkpoint")
    _assert_no_forbidden_trajectory_language(reply, "Day8 flex80")

    # Day 10 + flexion 80 -> same earlier-Day-7 wording.
    cp = checkpoint_for(10, rl.ROM_FLEXION_DEGREES, 80)
    reply = ri.format_assess_message(cp)
    print(f"    Day10 flex80: {reply!r}")
    _check("earlier Post-Op Day 7" in reply, "Day10 flex80 must reference the earlier Post-Op Day 7 checkpoint")
    _assert_no_forbidden_trajectory_language(reply, "Day10 flex80")

    # Day 10 + flexion 60 -> below the EARLIER Day-7 checkpoint, never "behind recovery".
    cp = checkpoint_for(10, rl.ROM_FLEXION_DEGREES, 60)
    reply = ri.format_assess_message(cp)
    print(f"    Day10 flex60: {reply!r}")
    _check(cp.verdict == rl.CheckpointVerdict.BELOW_STATED_CHECKPOINT, "Day10 flex60 must be BELOW_STATED_CHECKPOINT")
    _check("earlier Post-Op Day 7" in reply, "Day10 flex60 must reference the earlier Post-Op Day 7 checkpoint")
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

    # Missing evidence.
    s = fresh_verified("D-missing-evidence")
    d = rl.decide_progress_verdict_action(s, procedure="TKA", metric=rl.ROM_FLEXION_DEGREES, evidence=None)
    _check(d.reason_code == rl.DecisionReasonCode.EVIDENCE_MISSING, f"missing evidence: {d}")
    reply = ri.format_decline_message(d.reason_code, metric=rl.ROM_FLEXION_DEGREES, evidence=None)
    _check("supported evidence" in reply, "missing-evidence decline text must not claim a clinical abnormality")

    # Wrong evidence source.
    s = fresh_verified("D-wrong-source")
    wrong_source = rl.RecoveryEvidence(source_id="TKA-99", procedure="TKA", days_raw="1-21")
    d = rl.decide_progress_verdict_action(s, procedure="TKA", metric=rl.ROM_FLEXION_DEGREES, evidence=wrong_source)
    _check(d.reason_code == rl.DecisionReasonCode.EVIDENCE_SOURCE_MISMATCH, f"wrong source: {d}")

    # Wrong evidence procedure.
    s = fresh_verified("D-wrong-procedure")
    wrong_proc = rl.RecoveryEvidence(source_id="TKA-03", procedure="THA", days_raw="1-21")
    d = rl.decide_progress_verdict_action(s, procedure="TKA", metric=rl.ROM_FLEXION_DEGREES, evidence=wrong_proc)
    _check(d.reason_code == rl.DecisionReasonCode.EVIDENCE_PROCEDURE_MISMATCH, f"wrong procedure: {d}")

    # Malformed applicability window.
    s = fresh_verified("D-malformed-window")
    malformed = rl.RecoveryEvidence(source_id="TKA-03", procedure="TKA", days_raw="not-a-range")
    d = rl.decide_progress_verdict_action(s, procedure="TKA", metric=rl.ROM_FLEXION_DEGREES, evidence=malformed)
    _check(d.reason_code == rl.DecisionReasonCode.MALFORMED_APPLICABILITY_WINDOW, f"malformed window: {d}")

    # Day 22 outside TKA-03's 1-21 window.
    _reset_recovery_store()
    s = recovery_state.get_or_create_state(patient_id="D-day22", surgery_date_raw="2026-08-01T00:00:00.000", procedure="TKA")
    s.apply_verified_day(22)
    d = rl.decide_progress_verdict_action(s, procedure="TKA", metric=rl.ROM_FLEXION_DEGREES, evidence=TKA03_EVIDENCE)
    _check(d.reason_code == rl.DecisionReasonCode.DAY_OUTSIDE_APPLICABILITY_WINDOW, f"day 22: {d}")

    # Invalid metric values: negative, absurdly large, non-numeric.
    for bad_value, label in ((-5, "negative"), (999, "absurdly large"), ("not-a-number", "non-numeric")):
        s = fresh_verified(f"D-invalid-{label}")
        s.set_fact(rl.ROM_FLEXION_DEGREES, bad_value, effective_postop_day=10)
        cp = rl.evaluate_checkpoint(s, procedure="TKA", metric=rl.ROM_FLEXION_DEGREES, evidence=TKA03_EVIDENCE)
        _check(not cp.supported and cp.reason_code == rl.ReasonCode.INVALID_METRIC_VALUE, f"{label} value {bad_value!r}: {cp}")
        reply = ri.format_decline_message(rl.DecisionReasonCode.INVALID_METRIC_VALUE, metric=rl.ROM_FLEXION_DEGREES, evidence=TKA03_EVIDENCE)
        _check("doesn't look usable" in reply, f"{label} value decline text must not claim a clinical abnormality")
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

    # ASSESS_SUPPORTED_METRIC must not mutate an UNRELATED metric's state.
    _reset_recovery_store()
    s3 = recovery_state.get_or_create_state(patient_id="EX-3", surgery_date_raw=surgery_date, procedure="TKA")
    s3.apply_verified_day(10)
    extension_status_before = s3.status_of(rl.ROM_EXTENSION_DEGREES)
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy):
        RecoveryProgressAgent.handle(
            patient_id="EX-3", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="I can bend to about 80 degrees.", procedure="TKA", surgery_date=surgery_date,
        )
    _check(s3.status_of(rl.ROM_EXTENSION_DEGREES) == extension_status_before, "ASSESS on flexion must not mutate extension's status")

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
    _check("earlier Post-Op Day 7" in reply2, "Turn 2 reply must reference the earlier Day-7 checkpoint")
    _check("extension" not in reply2.lower(), "Turn 2 reply must NOT ask about extension in the same response")
    _check(state.status_of(rl.ROM_EXTENSION_DEGREES) == recovery_state.FieldStatus.NEVER_ASKED, "extension must remain NEVER_ASKED after Turn 2")
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
    _check("bend" not in reply_sym.lower() and "flexion" not in reply_sym.lower(), "extension-assess reply must not ask about flexion")
    _check(s_sym.status_of(rl.ROM_FLEXION_DEGREES) == recovery_state.FieldStatus.NEVER_ASKED, "flexion must remain NEVER_ASKED")
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
    _check("earlier Post-Op Day 7" in reply, "single response must assess flexion (canonical TKA order: flexion first)")
    _check("extension" not in reply.lower(), "response must not ALSO mix in an extension verdict/question")
    print("    CONFIRMED: canonical TKA order (flexion, then extension) selects exactly one verdict; the other fact is preserved for a later turn.")
    print()


# ============================================================================
# 9. SINGLE RETRIEVAL PER PROGRESS-VERDICT TURN -- MOCKED-BOUNDARY (call-count
#    spy). Pass-3 Section 8.
# ============================================================================

def test_single_retrieval_per_turn() -> None:
    _section("9 -- Exactly ONE retrieve_detailed() call per progress-verdict turn [MOCKED-BOUNDARY: call-count spy]")

    surgery_date = _dynamic_surgery_date(9)  # Day 10

    # A. ASK turn.
    _reset_recovery_store()
    spy_a = _RetrievalSpy()
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy_a):
        RecoveryProgressAgent.handle(
            patient_id="RC-A", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="How is my recovery going?", procedure="TKA", surgery_date=surgery_date,
        )
    _check(spy_a.call_count == 1, f"ASK turn: expected exactly 1 retrieve_detailed() call, got {spy_a.call_count}")

    # B. ASSESS turn.
    _reset_recovery_store()
    state = recovery_state.get_or_create_state(patient_id="RC-B", surgery_date_raw=surgery_date, procedure="TKA")
    state.apply_verified_day(10)
    state.mark_pending(rl.ROM_FLEXION_DEGREES)
    spy_b = _RetrievalSpy()
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy_b):
        result_b = RecoveryProgressAgent.handle(
            patient_id="RC-B", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="I can bend to around 80 degrees.", procedure="TKA", surgery_date=surgery_date,
        )
    _check(spy_b.call_count == 1, f"ASSESS turn: expected exactly 1 retrieve_detailed() call, got {spy_b.call_count}")
    _check(result_b["sources"] == ["TKA-03"], f"ASSESS turn: the SAME retrieved evidence must be threaded into source attribution, got {result_b['sources']}")

    # C. Evidence/window DECLINE turn (evidence present but wrong procedure -> declines without a second retrieval attempt).
    _reset_recovery_store()
    state_c = recovery_state.get_or_create_state(patient_id="RC-C", surgery_date_raw=surgery_date, procedure="TKA")
    state_c.apply_verified_day(10)
    spy_c = _RetrievalSpy(results=[_FakeChunk(doc_id="TKA-03", procedure="THA", days="1-21")])
    with patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=spy_c):
        result_c = RecoveryProgressAgent.handle(
            patient_id="RC-C", surgery_type="Total Knee Arthroplasty (TKA)", affected_limb="Right",
            postop_day=10, user_message="How is my recovery going?", procedure="TKA", surgery_date=surgery_date,
        )
    _check(spy_c.call_count == 1, f"DECLINE turn: expected exactly 1 retrieve_detailed() call, got {spy_c.call_count}")
    print()


# ============================================================================
# 10. REAL KEYWORD-FALLBACK RETRIEVAL -- REAL-INTEGRATION (no mock of
#    retrieve_detailed). Pass-3 Section 9.
# ============================================================================

def test_real_keyword_fallback_retrieval() -> None:
    _section("10 -- Real keyword-fallback retrieval for a bare continuation reply [REAL-INTEGRATION]")

    detail_probe = ClinicalKnowledgeBase.retrieve_detailed("probe", procedure="TKA", limit=1)
    if detail_probe.retrieval_path != "keyword_fallback":
        print(f"    SKIP-DISCLOSURE: environment has semantic_chroma available (path={detail_probe.retrieval_path}); "
              "this test only asserts the keyword-fallback contract and does not verify semantic_chroma here.")

    # Bare continuation message carries none of TKA-03's own keywords.
    bare_query = "80 degrees"
    bare_detail = ClinicalKnowledgeBase.retrieve_detailed(bare_query, procedure="TKA", limit=2)
    print(f"    bare query {bare_query!r} -> path={bare_detail.retrieval_path} n_results={len(bare_detail.results)}")
    _check(len(bare_detail.results) == 0, "bare '80 degrees' must retrieve NOTHING via keyword fallback (motivates the hint augmentation)")

    # recovery_integration's fix: augment with a metric-specific hint built
    # from the corpus's OWN vocabulary before the real retrieve_detailed() call.
    augmented_query = ri.build_retrieval_query(bare_query, rl.ROM_FLEXION_DEGREES)
    print(f"    augmented query -> {augmented_query!r}")
    augmented_detail = ClinicalKnowledgeBase.retrieve_detailed(augmented_query, procedure="TKA", limit=2)
    print(f"    augmented -> path={augmented_detail.retrieval_path} n_results={len(augmented_detail.results)}")
    _check(len(augmented_detail.results) >= 1, "augmented query must retrieve at least one chunk via keyword fallback")
    _check(
        any(r.doc_id == "TKA-03" for r in augmented_detail.results),
        f"augmented query must retrieve TKA-03, got {[r.doc_id for r in augmented_detail.results]}",
    )
    _check(
        augmented_detail.retrieval_path == "keyword_fallback",
        f"DISCLOSURE: this environment's retrieval path was {augmented_detail.retrieval_path!r}, not keyword_fallback -- "
        "chromadb/sentence-transformers may be installed here; re-verify this assertion is still the intended one.",
    )
    print("    DEPENDENCY DISCLOSURE: this environment has no chromadb/sentence-transformers installed; "
          "only the REAL keyword-fallback path was exercised. semantic_chroma was NOT exercised by this test.")
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
    _check("earlier Post-Op Day 7" in result["reply"], f"reply must assess flexion against the Day-7 checkpoint: {result['reply']!r}")
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
    _check("earlier Post-Op Day 7" in result_tka["reply"], "TKA must produce a checkpoint-relative verdict")

    # THA: no supported quantitative milestone -> grounded-guidance path
    # remains reachable, no Recovery state is created.
    _reset_recovery_store()
    fn_tha, calls_tha = _stub_answer_question(reply="THA grounded reply")
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn_tha):
        RecoveryProgressAgent.handle(
            patient_id="PI-THA", surgery_type="Total Hip Arthroplasty (THA)", affected_limb="Left",
            postop_day=10, user_message="Am I on track for my hip recovery?", procedure="THA", surgery_date=surgery_date,
        )
    _check(len(calls_tha) == 1, f"THA must reach the grounded-guidance ChatAgent path exactly once, got {len(calls_tha)}")
    _check(calls_tha[0].get("domain_instruction") == RecoveryProgressAgent.DOMAIN_FOCUS, "THA domain_instruction must be the plain, unmodified DOMAIN_FOCUS")
    proof_tha = recovery_state.peek_state(patient_id="PI-THA", surgery_date_raw=surgery_date, procedure="THA")
    _check(proof_tha is None, "THA must NOT create a RecoverySessionState (bypasses the deterministic interview loop entirely)")

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

    print("    DOCUMENTED (intentional, not a bug): THA/GEN skip the deterministic interview loop entirely because no")
    print("    sourced quantitative milestone exists for either in the current corpus. If a future pass adds one, this")
    print("    early return in RecoveryProgressAgent.handle() must be revisited so THA/GEN can join the state/interview loop.")
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
    # NEW architecture: TKA is fully deterministic -- no ChatAgent call at all.
    _check(result["engine"] == RecoveryProgressAgent.ENGINE_NAME, f"TKA route must use the deterministic engine, got {result['engine']}")
    _check(spy.call_count == 1, f"exactly one retrieval for this turn, got {spy.call_count}")
    print()


# ============================================================================
# 17. postop_day / procedure / chat_history REACH THE AGENT -- rewrite of OLD
#    tests 2/3/4. These now specifically exercise the THA grounded-guidance
#    path (the only Recovery path that still calls ChatAgent.answer_question
#    and forwards chat_history). MOCKED-BOUNDARY.
# ============================================================================

def test_postop_day_procedure_and_chat_history_reach_grounded_guidance() -> None:
    _section("17 -- postop_day / procedure / chat_history reach ChatAgent for the THA/GEN grounded-guidance path [MOCKED-BOUNDARY]")

    fn, calls = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        RecoveryProgressAgent.handle(
            patient_id="GG-1", surgery_type="Total Hip Arthroplasty (THA)", affected_limb="Left",
            postop_day=13, user_message="Am I on track for my hip recovery?", procedure="THA",
        )
    _check(len(calls) == 1, f"expected 1 call, got {len(calls)}")
    if calls:
        _check(calls[0].get("postop_day") == 13, f"postop_day not forwarded, got {calls[0].get('postop_day')}")
        _check(calls[0].get("procedure") == "THA", f"procedure not forwarded, got {calls[0].get('procedure')}")
        _check(calls[0].get("surgery_type") == "Total Hip Arthroplasty (THA)", "surgery_type not forwarded")

    history = [
        {"role": "user", "content": "I had my THA five days ago."},
        {"role": "assistant", "content": "Great, how does your hip feel today?"},
    ]
    fn2, calls2 = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn2):
        RecoveryProgressAgent.handle(
            patient_id="GG-2", surgery_type="Total Hip Arthroplasty (THA)", affected_limb="Left",
            postop_day=5, user_message="Is this normal for my hip?", procedure="THA", chat_history=history,
        )
    _check(len(calls2) == 1, f"expected 1 call, got {len(calls2)}")
    _check(calls2 and calls2[0].get("chat_history") == history, "chat_history was not forwarded unmodified")

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


def main() -> int:
    test_postop_day_derivation()
    test_checkpoint_day_6_7_8_boundary()
    test_assessment_wording_and_negative_assertions()
    test_decline_reasons()
    test_extraction_regressions()
    test_executor_state_transitions()
    test_immediate_metric_assessment_end_to_end()
    test_multi_fact_one_action()
    test_single_retrieval_per_turn()
    test_real_keyword_fallback_retrieval()
    test_continuation_helper()
    test_real_classifier_bend_misroute_regression()
    test_safety_and_scope_precedence()
    test_procedure_isolation()
    test_client_reported_postop_day_is_diagnostic_only()
    test_routing_and_response_shape()
    test_postop_day_procedure_and_chat_history_reach_grounded_guidance()

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
