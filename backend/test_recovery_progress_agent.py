"""
Recovery Progress Agent test suite -- Milestone Sec 2.5.

Covers the enhancement in agents/specialized_agents.py::RecoveryProgressAgent
on top of the shared Phase 1-4 pipeline (safety triage -> scope validation ->
intent classification -> AgentRouter -> specialized agent -> RAG -> LLM /
deterministic fallback), which this suite must never weaken.

Plain-Python script (no pytest dependency), consistent with
test_phase2_intent.py / test_phase3_rag.py / test_phase4_agents.py.

Run directly:
    .venv/Scripts/python.exe test_recovery_progress_agent.py
"""

from __future__ import annotations

import sys
from typing import Any, Dict, Optional
from unittest.mock import patch

from lam.orchestrator import LAMOrchestrator
from lam.schemas import IntentLabel
from agents.agent_router import AgentRouter, _AGENT_BY_INTENT
from agents.specialized_agents import RecoveryProgressAgent
from rag.knowledge_base import ClinicalKnowledgeBase

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
# 1. Correct routing to RecoveryProgressAgent
# ---------------------------------------------------------------------------

def test_routing() -> None:
    print("=" * 78)
    print("1 -- Correct routing to RecoveryProgressAgent")
    print("=" * 78)
    fn, calls = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        result = LAMOrchestrator.process(
            patient_id="TEST-PT",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=10,
            user_message="How is my recovery progressing compared to a normal timeline?",
        )
    print(f"    intent={result['intent']} target_agent={result['target_agent']} action={result['action']}")
    _check(result["intent"] == IntentLabel.RECOVERY_PROGRESS.value, "query did not classify as recovery_progress")
    _check(
        result["target_agent"] == RecoveryProgressAgent.TARGET_AGENT.value,
        f"expected target_agent {RecoveryProgressAgent.TARGET_AGENT.value}, got {result['target_agent']}",
    )
    _check(len(calls) == 1, f"expected exactly 1 response-generation call, got {len(calls)}")
    _check(
        _AGENT_BY_INTENT.get(IntentLabel.RECOVERY_PROGRESS) is RecoveryProgressAgent,
        "agent_router mapping for recovery_progress is not RecoveryProgressAgent",
    )
    print()


# ---------------------------------------------------------------------------
# 2. postop_day and 3. procedure type reach the agent's response pipeline
# ---------------------------------------------------------------------------

def test_postop_day_and_procedure_reach_agent() -> None:
    print("=" * 78)
    print("2/3 -- postop_day and procedure type reach the agent")
    print("=" * 78)
    fn, calls = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        RecoveryProgressAgent.handle(
            patient_id="TEST-PT",
            surgery_type="Total Hip Arthroplasty (THA)",
            affected_limb="Left",
            postop_day=13,
            user_message="Am I on track for my hip recovery?",
            procedure="THA",
        )
    _check(len(calls) == 1, f"expected 1 call, got {len(calls)}")
    if calls:
        _check(calls[0].get("postop_day") == 13, f"postop_day not forwarded, got {calls[0].get('postop_day')}")
        _check(calls[0].get("procedure") == "THA", f"procedure not forwarded, got {calls[0].get('procedure')}")
        _check(calls[0].get("surgery_type") == "Total Hip Arthroplasty (THA)", "surgery_type not forwarded")
    print("    CONFIRMED: postop_day and procedure reach the response-generation pipeline.")
    print()


# ---------------------------------------------------------------------------
# 4. Recovery / conversation history reaches the agent
# ---------------------------------------------------------------------------

def test_chat_history_reaches_agent() -> None:
    print("=" * 78)
    print("4 -- Conversation / recovery history reaches the agent")
    print("=" * 78)
    history = [
        {"role": "user", "content": "I had my TKA five days ago."},
        {"role": "assistant", "content": "Great, how does your knee feel today?"},
    ]
    fn, calls = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        RecoveryProgressAgent.handle(
            patient_id="TEST-PT",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=5,
            user_message="Is my flexion where it should be by now?",
            procedure="TKA",
            chat_history=history,
        )
    _check(len(calls) == 1, f"expected 1 call, got {len(calls)}")
    _check(calls and calls[0].get("chat_history") == history, "chat_history was not forwarded unmodified")
    print("    CONFIRMED: chat_history reaches ChatAgent.answer_question unmodified.")
    print()


# ---------------------------------------------------------------------------
# 5. RAG-grounded response path -- real ClinicalKnowledgeBase, no invented
# milestone data, and graceful degradation when retrieval fails or yields
# nothing relevant.
# ---------------------------------------------------------------------------

def test_rag_grounded_stage_note() -> None:
    print("=" * 78)
    print("5 -- RAG-grounded stage-specific milestone note (real RAG, no invention)")
    print("=" * 78)
    fn, calls = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        RecoveryProgressAgent.handle(
            patient_id="TEST-PT",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=10,
            user_message="When should I expect to walk normally again?",
            procedure="TKA",
        )
    instruction = calls[0].get("domain_instruction") if calls else None
    print(f"    domain_instruction = {instruction!r}")
    _check(instruction is not None, "no domain_instruction captured")
    if instruction:
        _check(
            instruction.startswith(RecoveryProgressAgent.DOMAIN_FOCUS),
            "enriched domain_instruction must still start with the unmodified DOMAIN_FOCUS",
        )
        _check(
            "Range of Motion & Extension Milestones" in instruction,
            "expected the real retrieved chunk title to appear in the milestone note",
        )
        _check(
            "Day 1-21" in instruction or "1-21" in instruction,
            "expected the chunk's OWN 'days' metadata (1-21), not an invented value",
        )
        _check("Day 10" in instruction, "expected the patient's actual postop_day (10) in the note")

    # Graceful degradation: RAG lookup failure must not crash, and must not
    # fabricate a milestone note -- falls back to plain DOMAIN_FOCUS.
    fn2, calls2 = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn2), \
         patch.object(ClinicalKnowledgeBase, "retrieve_detailed", side_effect=RuntimeError("vector store down")):
        RecoveryProgressAgent.handle(
            patient_id="TEST-PT",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=10,
            user_message="When should I expect to walk normally again?",
            procedure="TKA",
        )
    _check(len(calls2) == 1, "RAG failure must not prevent the underlying answer from being generated")
    _check(
        calls2 and calls2[0].get("domain_instruction") == RecoveryProgressAgent.DOMAIN_FOCUS,
        "RAG failure must degrade to the plain DOMAIN_FOCUS, never fabricate a milestone note",
    )
    print("    CONFIRMED: RAG-failure path degrades safely without inventing milestone data.")
    print()


# ---------------------------------------------------------------------------
# 6. RED safety short-circuit -- must never reach RecoveryProgressAgent at all
# ---------------------------------------------------------------------------

def test_red_short_circuit() -> None:
    print("=" * 78)
    print("6 -- RED safety short-circuit before RecoveryProgressAgent executes")
    print("=" * 78)
    chat_fn, chat_calls = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=chat_fn), \
         patch.object(ClinicalKnowledgeBase, "retrieve_detailed") as rag_mock:
        result = LAMOrchestrator.process(
            patient_id="TEST-PT",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=10,
            user_message="I can't breathe and have severe chest pain",
        )
    print(f"    intent={result['intent']} engine={result['engine']} chat_calls={len(chat_calls)} rag_calls={rag_mock.call_count}")
    _check(result["intent"] == IntentLabel.EMERGENCY.value, "RED query did not return EMERGENCY intent")
    _check(result["triage_level"] == "RED", "RED query did not report triage_level RED")
    _check(len(chat_calls) == 0, "RED query must never reach ChatAgent.answer_question")
    _check(rag_mock.call_count == 0, "RED query must never reach RecoveryProgressAgent's RAG milestone lookup")
    print()


# ---------------------------------------------------------------------------
# 7. Out-of-scope short-circuit -- must never reach RecoveryProgressAgent
# ---------------------------------------------------------------------------

def test_out_of_scope_short_circuit() -> None:
    print("=" * 78)
    print("7 -- Out-of-scope short-circuit before RecoveryProgressAgent executes")
    print("=" * 78)
    chat_fn, chat_calls = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=chat_fn), \
         patch.object(ClinicalKnowledgeBase, "retrieve_detailed") as rag_mock:
        result = LAMOrchestrator.process(
            patient_id="TEST-PT",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=10,
            user_message="What is the capital of France?",
        )
    print(f"    intent={result['intent']} engine={result['engine']} chat_calls={len(chat_calls)} rag_calls={rag_mock.call_count}")
    _check(result["intent"] == IntentLabel.OUT_OF_SCOPE.value, "query did not return OUT_OF_SCOPE intent")
    _check(len(chat_calls) == 0, "OUT_OF_SCOPE query must never reach ChatAgent.answer_question")
    _check(rag_mock.call_count == 0, "OUT_OF_SCOPE query must never reach RecoveryProgressAgent's RAG milestone lookup")
    print()


# ---------------------------------------------------------------------------
# 8. TKA / THA / GEN procedure isolation in the milestone note itself
# ---------------------------------------------------------------------------

def test_procedure_isolation() -> None:
    print("=" * 78)
    print("8 -- TKA / THA / GEN procedure isolation in milestone notes")
    print("=" * 78)

    # TKA: must surface TKA-tagged benchmarks only.
    fn, calls = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        RecoveryProgressAgent.handle(
            patient_id="TEST-PT", surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right", postop_day=10,
            user_message="How is my knee recovery progressing?", procedure="TKA",
        )
    tka_instruction = calls[0].get("domain_instruction", "") if calls else ""
    print(f"    TKA  -> {tka_instruction!r}")
    _check("Range of Motion" in tka_instruction, "TKA query did not surface a TKA-tagged benchmark")
    _check("Hip Precautions" not in tka_instruction, "REGRESSION: TKA query leaked THA-only guidance")

    # THA: must surface THA-tagged benchmarks only.
    fn, calls = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        RecoveryProgressAgent.handle(
            patient_id="TEST-PT", surgery_type="Total Hip Arthroplasty (THA)",
            affected_limb="Left", postop_day=10,
            user_message="When can I bend my hip and cross my legs again?", procedure="THA",
        )
    tha_instruction = calls[0].get("domain_instruction", "") if calls else ""
    print(f"    THA  -> {tha_instruction!r}")
    _check("Hip Precautions" in tha_instruction, "THA query did not surface a THA-tagged benchmark")
    _check(
        "Range of Motion & Extension Milestones" not in tha_instruction,
        "REGRESSION: THA query leaked TKA-only guidance",
    )

    # GEN (ankle -- below-hip, non-arthroplasty): resolve_procedure_code must
    # never silently become TKA, and with nothing procedure/"All"-relevant
    # retrieved, the agent must NOT fabricate a milestone note.
    fn, calls = _stub_answer_question()
    with patch("agents.chat_agent.ChatAgent.answer_question", side_effect=fn):
        RecoveryProgressAgent.handle(
            patient_id="TEST-PT", surgery_type="Ankle ORIF",
            affected_limb="Right", postop_day=10,
            user_message="How is my ankle recovery progressing?", procedure="GEN",
        )
    gen_instruction = calls[0].get("domain_instruction", "") if calls else ""
    print(f"    GEN  -> {gen_instruction!r}")
    _check("Range of Motion" not in gen_instruction, "REGRESSION: GEN query leaked TKA-only guidance")
    _check("Hip Precautions" not in gen_instruction, "REGRESSION: GEN query leaked THA-only guidance")
    _check(
        gen_instruction == RecoveryProgressAgent.DOMAIN_FOCUS,
        "GEN query with no relevant retrieved benchmark must not fabricate a milestone note",
    )
    print()


def main() -> int:
    test_routing()
    test_postop_day_and_procedure_reach_agent()
    test_chat_history_reaches_agent()
    test_rag_grounded_stage_note()
    test_red_short_circuit()
    test_out_of_scope_short_circuit()
    test_procedure_isolation()

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
