"""
Rehabilitation & Exercise Agent test suite -- Milestone Sec 2.7.

Covers the enhancement in agents/specialized_agents.py::RehabilitationAgent
(the EXISTING LAM agent evolved to fulfil the Milestone's Rehabilitation &
Exercise role -- no second, competing rehab pipeline was added) on top of
the shared Phase 1-4 pipeline (safety triage -> scope validation -> intent
classification -> AgentRouter -> specialized agent -> RAG -> LLM /
deterministic fallback), which this suite must never weaken.

Plain-Python script (no pytest dependency), consistent with
test_phase2_intent.py / test_phase3_rag.py / test_phase4_agents.py /
test_recovery_progress_agent.py / test_symptom_assessment_agent.py.

Run directly:
    .venv/Scripts/python.exe test_rehabilitation_agent.py
"""

from __future__ import annotations

import sys
from typing import Any, Dict, Optional
from unittest.mock import patch

from lam.orchestrator import LAMOrchestrator
from lam.schemas import IntentLabel, WeightBearingStatus, resolve_procedure_code
from agents.agent_router import AgentRouter, _AGENT_BY_INTENT
from agents.specialized_agents import RehabilitationAgent

_FAILURES: list[str] = []


def _check(condition: bool, message: str) -> None:
    if not condition:
        _FAILURES.append(message)
        print(f"    !! FAILED: {message}")


def _stub_answer_question(reply: str = "stub reply", sources: Optional[list] = None):
    calls: list[Dict[str, Any]] = []

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


# ---------------------------------------------------------------------------
# 1. Correct routing to RehabilitationAgent
# ---------------------------------------------------------------------------

def test_routing() -> None:
    print("=" * 78)
    print("1 -- REHABILITATION routes to RehabilitationAgent")
    print("=" * 78)
    fn, calls = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        result = LAMOrchestrator.process(
            patient_id="TEST-PT",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=7,
            user_message="How many heel slides should I do today?",
        )
    print(f"    intent={result['intent']} target_agent={result['target_agent']} action={result['action']}")
    _check(result["intent"] == IntentLabel.REHABILITATION.value, "query did not classify as rehabilitation")
    _check(
        result["target_agent"] == RehabilitationAgent.TARGET_AGENT.value,
        f"expected target_agent {RehabilitationAgent.TARGET_AGENT.value}, got {result['target_agent']}",
    )
    _check(len(calls) == 1, f"expected exactly 1 response-generation call, got {len(calls)}")
    _check(
        _AGENT_BY_INTENT.get(IntentLabel.REHABILITATION) is RehabilitationAgent,
        "agent_router mapping for rehabilitation is not RehabilitationAgent",
    )
    print()


# ---------------------------------------------------------------------------
# 2. postop day / stage reaches the agent
# ---------------------------------------------------------------------------

def test_postop_day_reaches_agent() -> None:
    print("=" * 78)
    print("2 -- postop_day (stage) reaches the agent")
    print("=" * 78)
    fn, calls = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        RehabilitationAgent.handle(
            patient_id="TEST-PT",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=14,
            user_message="What exercises should I be doing now?",
            procedure="TKA",
        )
    _check(len(calls) == 1, f"expected 1 call, got {len(calls)}")
    _check(calls and calls[0].get("postop_day") == 14, "postop_day not forwarded")
    print("    CONFIRMED: postop_day reaches the response-generation pipeline.")
    print()


# ---------------------------------------------------------------------------
# 3. NWB / PWB / WBAT / FWB input handling
# ---------------------------------------------------------------------------

def test_weight_bearing_status_handling() -> None:
    print("=" * 78)
    print("3 -- NWB / PWB / WBAT / FWB weight-bearing status handling")
    print("=" * 78)
    expected_labels = {
        WeightBearingStatus.NWB: "Non-Weight-Bearing (NWB)",
        WeightBearingStatus.PWB: "Partial Weight-Bearing (PWB)",
        WeightBearingStatus.WBAT: "Weight-Bearing As Tolerated (WBAT)",
        WeightBearingStatus.FWB: "Full Weight-Bearing (FWB)",
    }
    for status, expected_label in expected_labels.items():
        fn, calls = _stub_answer_question()
        with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
            RehabilitationAgent.handle(
                patient_id="TEST-PT",
                surgery_type="Total Knee Arthroplasty (TKA)",
                affected_limb="Right",
                postop_day=5,
                user_message="What exercises can I do today?",
                procedure="TKA",
                weight_bearing_status=status,
            )
        instruction = calls[0].get("domain_instruction", "") if calls else ""
        print(f"    {status.value:5s} -> label present: {expected_label in instruction}")
        _check(expected_label in instruction, f"{status.value}: expected label {expected_label!r} not found")
        _check(
            "NEVER recommend an exercise, activity, or progression that "
            "would violate it" in instruction,
            f"{status.value}: missing the no-advancement-beyond-restriction safety instruction",
        )
    print()


# ---------------------------------------------------------------------------
# 4. ROM context handling
# ---------------------------------------------------------------------------

def test_rom_context_handling() -> None:
    print("=" * 78)
    print("4 -- Current ROM context handling")
    print("=" * 78)
    fn, calls = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        RehabilitationAgent.handle(
            patient_id="TEST-PT",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=7,
            user_message="Am I bending my knee enough?",
            procedure="TKA",
            current_rom="Flexion to about 80 degrees, extension to 5 degrees",
        )
    instruction = calls[0].get("domain_instruction", "") if calls else ""
    print(f"    domain_instruction contains ROM: {'Flexion to about 80 degrees' in instruction}")
    _check(
        "Flexion to about 80 degrees, extension to 5 degrees" in instruction,
        "reported current_rom was not incorporated verbatim",
    )
    _check(
        "Give repetition targets ONLY when the retrieved clinical context" in instruction,
        "missing the no-invented-repetition-count instruction",
    )
    print()


# ---------------------------------------------------------------------------
# 5. Exercise-history context handling
# ---------------------------------------------------------------------------

def test_exercise_history_handling() -> None:
    print("=" * 78)
    print("5 -- Exercise-history context handling")
    print("=" * 78)
    fn, calls = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        RehabilitationAgent.handle(
            patient_id="TEST-PT",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=7,
            user_message="Should I progress to standing exercises?",
            procedure="TKA",
            exercise_history="Completed heel slides and quad sets today; missed yesterday's session",
        )
    instruction = calls[0].get("domain_instruction", "") if calls else ""
    _check(
        "Completed heel slides and quad sets today; missed yesterday's session" in instruction,
        "reported exercise_history was not incorporated verbatim",
    )
    print("    CONFIRMED: exercise history reaches the response-generation pipeline verbatim.")
    print()


# ---------------------------------------------------------------------------
# 6. Optional fields preserve backward compatibility
# ---------------------------------------------------------------------------

def test_backward_compatibility() -> None:
    print("=" * 78)
    print("6 -- Missing optional rehab fields does not break old clients")
    print("=" * 78)

    fn, calls = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        result = AgentRouter.dispatch(
            intent_label=IntentLabel.REHABILITATION,
            patient_id="TEST-PT",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=5,
            user_message="How many heel slides should I do?",
            procedure="TKA",
        )
    _check(len(calls) == 1, "old-style AgentRouter.dispatch() call (no rehab kwargs) failed")
    _check(
        set(result.keys()) == {"reply", "triage_level", "is_escalated", "engine", "sources"},
        f"response shape changed for old-style call: {sorted(result.keys())}",
    )
    _check(
        calls and calls[0].get("domain_instruction") == RehabilitationAgent.DOMAIN_FOCUS,
        "old-style call (no rehab fields) must produce the plain, unmodified DOMAIN_FOCUS",
    )

    fn2, calls2 = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn2):
        LAMOrchestrator.process(
            patient_id="TEST-PT",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=5,
            user_message="How many heel slides should I do?",
        )
    _check(len(calls2) == 1, "old-style LAMOrchestrator.process() call (no rehab kwargs) failed")
    _check(
        calls2 and calls2[0].get("domain_instruction") == RehabilitationAgent.DOMAIN_FOCUS,
        "old-style LAMOrchestrator.process() call must produce the plain, unmodified DOMAIN_FOCUS",
    )
    print("    CONFIRMED: omitting all new rehab fields reproduces prior behavior exactly.")
    print()


# ---------------------------------------------------------------------------
# 7. RED bypasses RehabilitationAgent entirely
# ---------------------------------------------------------------------------

def test_red_bypasses_agent() -> None:
    print("=" * 78)
    print("7 -- RED safety short-circuit before RehabilitationAgent executes")
    print("=" * 78)
    fn, calls = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        result = LAMOrchestrator.process(
            patient_id="TEST-PT",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=5,
            user_message="I have severe calf pain and swelling, can I still do my exercises?",
            weight_bearing_status=WeightBearingStatus.FWB,
        )
    print(f"    intent={result['intent']} triage_level={result['triage_level']} chat_calls={len(calls)}")
    _check(result["triage_level"] == "RED", "text red-flag rehab query did not produce RED")
    _check(result["intent"] == IntentLabel.EMERGENCY.value, "RED query did not return EMERGENCY intent")
    _check(len(calls) == 0, "RED query must never reach RehabilitationAgent / ChatAgent.answer_question")
    print()


# ---------------------------------------------------------------------------
# 8. Procedure-specific RAG isolation (TKA / THA / GEN)
# ---------------------------------------------------------------------------

def test_procedure_isolation() -> None:
    print("=" * 78)
    print("8 -- TKA / THA / GEN procedure isolation")
    print("=" * 78)
    cases = [
        ("Total Knee Arthroplasty (TKA)", "How many heel slides should I do?", "TKA"),
        ("Total Hip Arthroplasty (THA)", "What hip exercises are safe for me?", "THA"),
        ("Ankle ORIF", "What ankle exercises should I do?", "GEN"),
    ]
    for surgery_type, query, expected_procedure in cases:
        resolved = resolve_procedure_code(surgery_type)
        _check(resolved == expected_procedure, f"{surgery_type!r} expected procedure {expected_procedure}, got {resolved}")
        _check(
            not (expected_procedure == "GEN" and resolved == "TKA"),
            f"REGRESSION: {surgery_type!r} silently resolved to TKA instead of GEN",
        )
        fn, calls = _stub_answer_question()
        with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
            LAMOrchestrator.process(
                patient_id="TEST-PT", surgery_type=surgery_type, affected_limb="Right",
                postop_day=7, user_message=query,
            )
        procedure_passed = calls[0].get("procedure") if calls else None
        print(f"    {surgery_type!r} -> resolved={resolved!r} dispatched procedure={procedure_passed!r}")
        _check(
            procedure_passed == expected_procedure,
            f"{surgery_type!r}: expected procedure {expected_procedure} passed to RehabilitationAgent, got {procedure_passed!r}",
        )
    print()


# ---------------------------------------------------------------------------
# 9. No unsupported advancement when restrictions are supplied -- the
# domain instruction must explicitly forbid advancement beyond a supplied
# weight-bearing restriction, and must forbid inventing rep counts even
# when a restriction is combined with an advancement-seeking query.
# ---------------------------------------------------------------------------

def test_no_unsupported_advancement_with_restriction() -> None:
    print("=" * 78)
    print("9 -- No unsupported advancement when a restriction is supplied")
    print("=" * 78)
    fn, calls = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        RehabilitationAgent.handle(
            patient_id="TEST-PT",
            surgery_type="Total Hip Arthroplasty (THA)",
            affected_limb="Left",
            postop_day=10,
            user_message="Can I start doing weight-bearing squats now?",
            procedure="THA",
            weight_bearing_status=WeightBearingStatus.NWB,
        )
    instruction = calls[0].get("domain_instruction", "") if calls else ""
    print(f"    domain_instruction = {instruction!r}")
    _check("Non-Weight-Bearing (NWB)" in instruction, "NWB restriction not present in instruction")
    _check(
        "do not advance the exercise plan beyond what the retrieved clinical "
        "context and this reported context support" in instruction,
        "missing explicit no-advancement-beyond-support instruction",
    )
    _check(
        "acknowledge the inconsistency rather than inventing a resolution" in instruction,
        "missing conflict-acknowledgement instruction for a query that seeks advancement despite a restriction",
    )
    print("    CONFIRMED: a supplied restriction is paired with an explicit no-advancement instruction.")
    print()


def main() -> int:
    test_routing()
    test_postop_day_reaches_agent()
    test_weight_bearing_status_handling()
    test_rom_context_handling()
    test_exercise_history_handling()
    test_backward_compatibility()
    test_red_bypasses_agent()
    test_procedure_isolation()
    test_no_unsupported_advancement_with_restriction()

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
