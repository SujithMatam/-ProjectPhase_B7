"""
Phase 4 test suite -- executable specialized clinical agents.

Run directly:
    .venv/Scripts/python.exe test_phase4_agents.py

Plain-Python script (no pytest dependency), consistent with
test_phase2_intent.py / test_phase3_rag.py. Mocks the shared
ChatAgent.answer_question() response-generation layer so routing/dispatch
can be verified without Ollama -- the mock records exactly which
domain_instruction (i.e. which specialized agent) was actually invoked,
proving dispatch is real rather than cosmetic.
"""

from __future__ import annotations

import sys
from typing import Any, Dict, Optional
from unittest.mock import patch

from lam.orchestrator import LAMOrchestrator
from lam.schemas import IntentLabel, ScopeStatus, resolve_procedure_code
from agents.agent_router import AgentRouter, _AGENT_BY_INTENT
from agents.chat_agent import ChatAgent
from agents.specialized_agents import (
    DailyActivityAgent,
    MedicationAgent,
    MentalWellbeingAgent,
    NutritionAgent,
    PainSymptomsAgent,
    RecoveryProgressAgent,
    RehabilitationAgent,
    WoundCareAgent,
)
from triage.safety_triage import SafetyTriageEngine

_FAILURES: list[str] = []


def _check(condition: bool, message: str) -> None:
    if not condition:
        _FAILURES.append(message)
        print(f"    !! FAILED: {message}")


def _counting_safety_evaluate():
    """
    Wraps the REAL SafetyTriageEngine.evaluate() (not a stub -- we need
    genuine RED/GREEN/YELLOW classification for these tests) so calls to it
    can be counted, to prove it runs exactly once per request through the
    LAM, not once in the orchestrator and again inside ChatAgent.
    """
    real_evaluate = SafetyTriageEngine.evaluate.__func__
    calls: list[Dict[str, Any]] = []

    def _fn(cls, **kwargs):
        calls.append(kwargs)
        return real_evaluate(cls, **kwargs)

    return classmethod(_fn), calls


def _stub_answer_question(reply: str = "stub reply", sources: Optional[list] = None):
    """A ChatAgent.answer_question() stand-in that records its kwargs and
    returns a normal-shaped response, without touching Ollama/RAG/embeddings."""
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
# 1. All 8 agents -- representative query per routable intent
# ---------------------------------------------------------------------------

_AGENT_CASES: list[tuple[str, str, IntentLabel, type, str]] = [
    # (query, surgery_type, expected_intent, expected_agent_class, expected_action)
    ("When should I expect to walk normally again?", "Total Knee Arthroplasty (TKA)",
     IntentLabel.RECOVERY_PROGRESS, RecoveryProgressAgent, "inform"),
    ("My knee is more swollen today and hurts.", "Total Knee Arthroplasty (TKA)",
     IntentLabel.PAIN_SYMPTOMS, PainSymptomsAgent, "assess"),
    ("How many heel slides should I do?", "Total Knee Arthroplasty (TKA)",
     IntentLabel.REHABILITATION, RehabilitationAgent, "advise"),
    ("I forgot my evening pain tablet.", "Total Knee Arthroplasty (TKA)",
     IntentLabel.MEDICATION, MedicationAgent, "inform"),
    ("Can I change my incision dressing today?", "Total Knee Arthroplasty (TKA)",
     IntentLabel.WOUND_CARE, WoundCareAgent, "advise"),
    ("When can I climb stairs and drive again?", "Total Knee Arthroplasty (TKA)",
     IntentLabel.DAILY_ACTIVITY, DailyActivityAgent, "inform"),
    ("What foods and protein should I eat while recovering?", "Total Knee Arthroplasty (TKA)",
     IntentLabel.NUTRITION, NutritionAgent, "inform"),
    ("I am anxious about moving my operated leg.", "Total Knee Arthroplasty (TKA)",
     IntentLabel.MENTAL_WELLBEING, MentalWellbeingAgent, "advise"),
]


def run_all_agents_test() -> None:
    print("=" * 78)
    print("SECTION 1 -- All 8 specialized agents (representative query each)")
    print("=" * 78)
    for query, surgery_type, expected_intent, expected_agent_cls, expected_action in _AGENT_CASES:
        fn, calls = _stub_answer_question()
        with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
            result = LAMOrchestrator.process(
                patient_id="TEST-PT",
                surgery_type=surgery_type,
                affected_limb="Right",
                postop_day=5,
                user_message=query,
            )

        captured_domain_instruction = calls[0].get("domain_instruction") if calls else None
        print(f"[{expected_agent_cls.__name__}] \"{query}\"")
        print(f"    intent          = {result['intent']}")
        print(f"    target_agent    = {result['target_agent']}")
        print(f"    action          = {result['action']}")
        print(f"    dispatch calls  = {len(calls)}")
        print(f"    domain_instruction = {captured_domain_instruction!r}")
        print()

        _check(
            result["intent"] == expected_intent.value,
            f"{query!r} expected intent {expected_intent.value}, got {result['intent']}",
        )
        _check(
            result["target_agent"] == expected_agent_cls.TARGET_AGENT.value,
            f"{query!r} expected target_agent {expected_agent_cls.TARGET_AGENT.value}, got {result['target_agent']}",
        )
        _check(
            result["action"] == expected_action,
            f"{query!r} expected action {expected_action}, got {result['action']}",
        )
        _check(
            len(calls) == 1,
            f"{query!r} expected exactly 1 response-generation call, got {len(calls)}",
        )
        _check(
            captured_domain_instruction == expected_agent_cls.DOMAIN_FOCUS,
            f"{query!r} expected {expected_agent_cls.__name__}.DOMAIN_FOCUS to be passed through, "
            f"got {captured_domain_instruction!r}",
        )
        # Cross-check against the orchestrator's own routing table so metadata
        # (target_agent) and actual dispatch never drift apart.
        _check(
            _AGENT_BY_INTENT.get(expected_intent) is expected_agent_cls,
            f"agent_router mapping for {expected_intent.value} is not {expected_agent_cls.__name__}",
        )


# ---------------------------------------------------------------------------
# 2. Safety precedence -- RED must never invoke a specialized agent
# ---------------------------------------------------------------------------

def run_safety_precedence_test() -> None:
    print("=" * 78)
    print("SECTION 2 -- Safety precedence (RED)")
    print("=" * 78)
    fn, calls = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        result = LAMOrchestrator.process(
            patient_id="TEST-PT",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=5,
            user_message="I can't breathe and have severe chest pain",
        )
    print(f"    intent = {result['intent']}, engine = {result['engine']}, "
          f"dispatch calls = {len(calls)}")

    _check(result["intent"] == IntentLabel.EMERGENCY.value, "RED query did not return EMERGENCY intent")
    _check(result["engine"] == "Deterministic Safety Triage", "RED query did not use the deterministic safety engine")
    _check(result["triage_level"] == "RED", "RED query did not report triage_level RED")
    _check(len(calls) == 0, f"RED query invoked the specialized-agent dispatcher ({len(calls)} call(s)) -- must be 0")
    print()


# ---------------------------------------------------------------------------
# 3. Scope precedence -- OUT_OF_SCOPE must never invoke a specialized agent
# ---------------------------------------------------------------------------

def run_scope_precedence_test() -> None:
    print("=" * 78)
    print("SECTION 3 -- Scope precedence (OUT_OF_SCOPE)")
    print("=" * 78)
    fn, calls = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        result = LAMOrchestrator.process(
            patient_id="TEST-PT",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=5,
            user_message="What is the capital of France?",
        )
    print(f"    intent = {result['intent']}, engine = {result['engine']}, "
          f"dispatch calls = {len(calls)}")

    _check(result["intent"] == IntentLabel.OUT_OF_SCOPE.value, "query did not return OUT_OF_SCOPE intent")
    _check(result["engine"] == "Scope Validator", "query did not use Scope Validator")
    _check(len(calls) == 0, f"OUT_OF_SCOPE query invoked the specialized-agent dispatcher ({len(calls)} call(s)) -- must be 0")
    print()


# ---------------------------------------------------------------------------
# 4. Procedure correctness -- TKA / THA / GEN, GEN never silently becomes TKA
# ---------------------------------------------------------------------------

def run_procedure_correctness_test() -> None:
    print("=" * 78)
    print("SECTION 4 -- Procedure correctness (TKA / THA / GEN)")
    print("=" * 78)
    cases = [
        ("Total Knee Arthroplasty (TKA)", "What exercises should I do after my knee replacement?", "TKA"),
        ("Total Hip Arthroplasty (THA)", "What movements should I avoid after my hip replacement?", "THA"),
        ("Ankle ORIF", "What general postoperative precautions should I follow?", "GEN"),
    ]
    for surgery_type, query, expected_procedure in cases:
        resolved = resolve_procedure_code(surgery_type)
        print(f"    resolve_procedure_code({surgery_type!r}) = {resolved!r}")
        _check(resolved == expected_procedure, f"{surgery_type!r} expected procedure {expected_procedure}, got {resolved}")
        _check(not (expected_procedure == "GEN" and resolved == "TKA"),
               f"REGRESSION: {surgery_type!r} silently resolved to TKA instead of GEN")

        fn, calls = _stub_answer_question()
        with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
            LAMOrchestrator.process(
                patient_id="TEST-PT", surgery_type=surgery_type, affected_limb="Right",
                postop_day=5, user_message=query,
            )
        procedure_passed = calls[0].get("procedure") if calls else None
        print(f"    dispatched procedure = {procedure_passed!r}")
        _check(
            procedure_passed == expected_procedure,
            f"{surgery_type!r}: expected procedure {expected_procedure} passed to the agent, got {procedure_passed!r}",
        )
    print()


# ---------------------------------------------------------------------------
# 5. Backward compatibility -- direct ChatAgent.answer_question() usage
# without the new specialized-agent parameters must still work.
# ---------------------------------------------------------------------------

def run_backward_compatibility_test() -> None:
    print("=" * 78)
    print("SECTION 5 -- Backward compatibility (direct ChatAgent usage)")
    print("=" * 78)
    result = ChatAgent.answer_question(
        patient_id="TEST-PT",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=5,
        user_message="What exercises should I do after my knee replacement?",
    )
    print(f"    engine  = {result['engine']}")
    print(f"    sources = {result['sources']}")
    _check(
        set(result.keys()) == {"reply", "triage_level", "is_escalated", "engine", "sources"},
        f"direct ChatAgent.answer_question() response shape changed: {sorted(result.keys())}",
    )
    _check(len(result["sources"]) > 0, "direct ChatAgent call returned no sources")
    print("    CONFIRMED: existing direct ChatAgent.answer_question() callers still work unmodified.")
    print()


# ---------------------------------------------------------------------------
# 6. Failure behavior -- unmapped intent must degrade safely, never crash,
# never fabricate EMERGENCY/OUT_OF_SCOPE.
# ---------------------------------------------------------------------------

def run_dispatch_failure_behavior_test() -> None:
    print("=" * 78)
    print("SECTION 6 -- Dispatch failure behavior (unmapped intent)")
    print("=" * 78)
    fn, calls = _stub_answer_question()
    # EMERGENCY is intentionally NOT a key in _AGENT_BY_INTENT (it never
    # legitimately reaches AgentRouter in normal operation -- the
    # orchestrator short-circuits before Step 5). Calling dispatch() with it
    # directly simulates the "intent unexpectedly unmapped" defensive path.
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        try:
            result = AgentRouter.dispatch(
                intent_label=IntentLabel.EMERGENCY,
                patient_id="TEST-PT",
                surgery_type="Total Knee Arthroplasty (TKA)",
                affected_limb="Right",
                postop_day=5,
                user_message="irrelevant for this test",
                procedure="TKA",
            )
            crashed = False
        except Exception as exc:  # noqa: BLE001
            result = None
            crashed = True
            print(f"    !! dispatch raised: {exc!r}")

    _check(not crashed, "AgentRouter.dispatch() raised on an unmapped intent instead of degrading safely")
    if result is not None:
        print(f"    result keys = {sorted(result.keys())}")
        _check(
            set(result.keys()) == {"reply", "triage_level", "is_escalated", "engine", "sources"},
            f"unmapped-intent fallback response shape changed: {sorted(result.keys())}",
        )
        _check(
            len(calls) == 1 and calls[0].get("domain_instruction") is None,
            "unmapped-intent fallback should call the plain generic ChatAgent path (no domain_instruction)",
        )
        _check(
            "EMERGENCY" not in str(result.get("reply", "")).upper()
            and result.get("triage_level") != "RED",
            "unmapped-intent fallback must not fabricate an EMERGENCY/RED result",
        )
    print("    CONFIRMED: unmapped intent degrades to the generic response path without crashing.")
    print()


# ---------------------------------------------------------------------------
# 7. Single-evaluation guarantee -- SafetyTriageEngine.evaluate() must run
# exactly once per LAM request, not once in the orchestrator and again
# inside ChatAgent when a specialized agent is dispatched.
# ---------------------------------------------------------------------------

def run_single_safety_evaluation_test() -> None:
    print("=" * 78)
    print("SECTION 7 -- SafetyTriageEngine evaluated exactly once per LAM request")
    print("=" * 78)

    # 7a. Normal in-scope request: evaluate() exactly once, specialized
    # agent dispatched exactly once, and it received the precomputed triage.
    patched_evaluate, triage_calls = _counting_safety_evaluate()
    chat_fn, chat_calls = _stub_answer_question()
    with patch.object(SafetyTriageEngine, "evaluate", patched_evaluate), \
         patch("agents.chat_agent.ChatAgent.answer_question", side_effect=chat_fn):
        result = LAMOrchestrator.process(
            patient_id="TEST-PT", surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right", postop_day=5,
            user_message="How many heel slides should I do?",
        )
    print(f"    [normal query] triage evaluate() calls = {len(triage_calls)}, "
          f"specialized-agent dispatch calls = {len(chat_calls)}")
    _check(len(triage_calls) == 1, f"expected exactly 1 SafetyTriageEngine.evaluate() call, got {len(triage_calls)}")
    _check(len(chat_calls) == 1, f"expected exactly 1 specialized-agent dispatch, got {len(chat_calls)}")
    if chat_calls:
        _check(
            chat_calls[0].get("precomputed_triage") is not None,
            "specialized agent did not receive the LAM's precomputed_triage",
        )
    _check(result["intent"] == IntentLabel.REHABILITATION.value, "normal query did not classify as REHABILITATION")

    # 7b. RED request: evaluate() exactly once (Step 1 only), zero specialized-agent dispatches.
    patched_evaluate, triage_calls = _counting_safety_evaluate()
    chat_fn, chat_calls = _stub_answer_question()
    with patch.object(SafetyTriageEngine, "evaluate", patched_evaluate), \
         patch("agents.chat_agent.ChatAgent.answer_question", side_effect=chat_fn):
        red_result = LAMOrchestrator.process(
            patient_id="TEST-PT", surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right", postop_day=5,
            user_message="I can't breathe and have severe chest pain",
        )
    print(f"    [RED query] triage evaluate() calls = {len(triage_calls)}, "
          f"specialized-agent dispatch calls = {len(chat_calls)}")
    _check(len(triage_calls) == 1, f"RED query: expected exactly 1 evaluate() call, got {len(triage_calls)}")
    _check(len(chat_calls) == 0, f"RED query: expected 0 specialized-agent dispatches, got {len(chat_calls)}")
    _check(red_result["intent"] == IntentLabel.EMERGENCY.value, "RED query did not return EMERGENCY intent")

    # 7c. OUT_OF_SCOPE request: zero specialized-agent dispatches.
    chat_fn, chat_calls = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=chat_fn):
        oos_result = LAMOrchestrator.process(
            patient_id="TEST-PT", surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right", postop_day=5,
            user_message="What is the capital of France?",
        )
    print(f"    [OUT_OF_SCOPE query] specialized-agent dispatch calls = {len(chat_calls)}")
    _check(len(chat_calls) == 0, f"OUT_OF_SCOPE query: expected 0 specialized-agent dispatches, got {len(chat_calls)}")
    _check(oos_result["intent"] == IntentLabel.OUT_OF_SCOPE.value, "query did not return OUT_OF_SCOPE intent")

    # 7d. Direct legacy ChatAgent.answer_question() call, no precomputed_triage
    # supplied: it must still run its own internal safety check exactly once.
    patched_evaluate, triage_calls = _counting_safety_evaluate()
    with patch.object(SafetyTriageEngine, "evaluate", patched_evaluate):
        legacy_result = ChatAgent.answer_question(
            patient_id="TEST-PT", surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right", postop_day=5,
            user_message="What exercises should I do after my knee replacement?",
        )
    print(f"    [direct legacy ChatAgent call, no precomputed_triage] "
          f"triage evaluate() calls = {len(triage_calls)}")
    _check(
        len(triage_calls) == 1,
        f"direct legacy ChatAgent call (no precomputed_triage) expected its own 1 evaluate() call, got {len(triage_calls)}",
    )
    _check(legacy_result["triage_level"] == "GREEN", "direct legacy ChatAgent call did not produce a normal GREEN result")

    print("    CONFIRMED: safety triage runs exactly once per LAM request; direct legacy "
          "ChatAgent calls without precomputed_triage still run their own check.")
    print()


def main() -> int:
    run_all_agents_test()
    run_safety_precedence_test()
    run_scope_precedence_test()
    run_procedure_correctness_test()
    run_backward_compatibility_test()
    run_dispatch_failure_behavior_test()
    run_single_safety_evaluation_test()

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
