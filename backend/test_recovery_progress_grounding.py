"""
Regression suite for a REAL live /api/chat bug against Ollama llama3.2.

Live request that exposed the bug:
    POST /api/chat
    {
      "patient_id": "TEST-001",
      "surgery_type": "Total Knee Arthroplasty (TKA)",
      "affected_limb": "Right",
      "postop_day": 10,
      "message": "How is my recovery progressing at this stage?",
      "chat_history": []
    }

Live (buggy) response:
    {
      "reply": "... you're doing great, and your progress is on track ...
                Typically, by Day 10 post-TKA ... icing and elevating your
                leg as needed will continue to be an important part ...",
      "triage_level": "GREEN",
      "engine": "Local LLM (llama3.2)",
      "sources": [],
      "intent": "recovery_progress",
      "target_agent": "RecoveryProgressAgent"
    }

Root cause: this exact query ("How is my recovery progressing at this
stage?") does not keyword/semantically match any seed RAG chunk (see
rag/data/seed_knowledge.json -- no chunk carries "recovery"/"progress"/
"stage" keywords), so ClinicalKnowledgeBase.query() legitimately returns
[]. ChatAgent.answer_question() nonetheless still called the free-generation
LLM prompt with an EMPTY rag_context, merely asking it nicely to answer
"based on the discharge notes" -- with no discharge notes present. A local
llama3.2 does not reliably refuse in that situation; it invented a recovery
assessment, a Day-10 timeline claim, and icing/elevation advice from prior
knowledge instead. `sources=[]` was truthful about what was retrieved, but
nothing enforced that the returned reply's CONTENT was actually limited to
what `sources` supports.

Fix (agents/chat_agent.py::ChatAgent.answer_question /
_generate_smart_reply): when ClinicalKnowledgeBase.query() returns no
chunks, the free-generation LLM call is skipped entirely (never invoked --
this is deterministic, not a prompt-engineering mitigation) and a
conservative, non-inventive fallback reply is used instead. When RAG DOES
return relevant chunks, the LLM/fallback path is unchanged and remains
grounded in -- and `sources` continues to report -- those retrieved chunks.

Plain-Python script (no pytest dependency), consistent with the other
test_*.py files in this directory.

Run directly:
    .venv/Scripts/python.exe test_recovery_progress_grounding.py
"""

from __future__ import annotations

import sys
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from agents.chat_agent import ChatAgent
from lam.orchestrator import LAMOrchestrator
from rag.knowledge_base import ClinicalKnowledgeBase

_FAILURES: list[str] = []


def _check(condition: bool, message: str) -> None:
    if not condition:
        _FAILURES.append(message)
        print(f"    !! FAILED: {message}")


# Exact live request payload from the bug report.
_LIVE_REQUEST: Dict[str, Any] = dict(
    patient_id="TEST-001",
    surgery_type="Total Knee Arthroplasty (TKA)",
    affected_limb="Right",
    postop_day=10,
    user_message="How is my recovery progressing at this stage?",
    chat_history=[],
)

# The exact invented reply llama3.2 produced live -- used to prove the fix
# structurally prevents the LLM from ever being consulted (and therefore
# from ever being able to return this) when nothing was retrieved, rather
# than merely hoping a smarter prompt would stop it.
_LIVE_HALLUCINATED_REPLY = (
    "I'm happy to help you with your recovery! At this stage, you're doing "
    "great, and your progress is on track. Typically, by Day 10 post-TKA, "
    "patients are starting to feel more comfortable with their new knee, "
    "and we're aiming to see improvements in range of motion, strength, "
    "and mobility - icing and elevating your leg as needed will continue "
    "to be an important part of your recovery routine."
)

# Affirmative assertions the live LLM made with no retrieved support --
# deliberately specific (not bare "on track"/"doing great") so this does not
# false-positive on the FIXED conservative reply's own negated wording
# ("...to judge whether you're on track...", i.e. explicitly NOT asserting
# it either way).
_UNSUPPORTED_PHRASES = [
    "you're doing great",
    "your progress is on track",
    "typically, by day 10",
    "typically by day 10",
]


def _assert_reply_makes_no_unsupported_claims(reply: str) -> None:
    lower = reply.lower()
    for phrase in _UNSUPPORTED_PHRASES:
        _check(phrase not in lower, f"REGRESSION: reply asserts unsupported claim {phrase!r} with no RAG grounding")
    _check("icing" not in lower and "elevat" not in lower, "REGRESSION: reply invents icing/elevation advice with no RAG grounding")


# ---------------------------------------------------------------------------
# 1. Reproduce the EXACT live request end-to-end (real RAG, LLM mocked to
# return exactly what llama3.2 returned live) -- must NOT surface the
# hallucinated content, and sources must stay empty/truthful.
# ---------------------------------------------------------------------------

def test_live_request_no_rag_match_does_not_invent() -> None:
    print("=" * 78)
    print("1 -- Exact live /api/chat request: no RAG match must not invent claims")
    print("=" * 78)

    # Sanity: confirm this exact query really does retrieve nothing relevant
    # from the real knowledge base -- otherwise this test would not be
    # reproducing the reported bug.
    real_docs = ClinicalKnowledgeBase.query(
        _LIVE_REQUEST["user_message"], procedure="TKA", limit=2
    )
    print(f"    real RAG retrieval for this query -> {real_docs!r}")
    _check(real_docs == [], "test setup assumption violated: this query now matches real RAG content -- update the test")

    llama_mock = MagicMock(return_value=_LIVE_HALLUCINATED_REPLY)
    with patch.object(ChatAgent, "_query_llama", llama_mock):
        result = LAMOrchestrator.process(**_LIVE_REQUEST)

    print(f"    intent={result['intent']} target_agent={result['target_agent']} engine={result['engine']}")
    print(f"    sources={result['sources']}")
    print(f"    reply={result['reply']!r}")

    _check(result["intent"] == "recovery_progress", "did not classify as recovery_progress")
    _check(result["target_agent"] == "RecoveryProgressAgent", "did not route to RecoveryProgressAgent")
    _check(result["triage_level"] == "GREEN", "expected GREEN triage for this benign question")
    _check(result["sources"] == [], "expected empty sources -- nothing relevant was retrieved")

    _check(
        llama_mock.call_count == 0,
        "REGRESSION: the free-generation LLM was called even though nothing was retrieved -- "
        "grounding gate did not engage",
    )
    _check(
        result["engine"] != f"Local LLM (llama3.2)",
        "REGRESSION: an LLM-attributed engine was returned despite empty sources",
    )
    _assert_reply_makes_no_unsupported_claims(result["reply"])
    _check(
        "don't have enough retrieved protocol information" in result["reply"].lower(),
        "expected the conservative no-RAG-support message",
    )
    print("    CONFIRMED: exact live request now returns a conservative, non-inventive response.")
    print()


# ---------------------------------------------------------------------------
# 2. General invariant: whenever sources come back empty, the reply must
# never assert on-track/ahead/behind/typical-timeline/reassurance language,
# regardless of intent/agent.
# ---------------------------------------------------------------------------

def test_empty_sources_never_pair_with_unsupported_claims() -> None:
    print("=" * 78)
    print("2 -- Empty sources must never pair with unsupported recovery claims")
    print("=" * 78)
    with patch.object(ChatAgent, "_query_llama", MagicMock(return_value=_LIVE_HALLUCINATED_REPLY)), \
         patch.object(ClinicalKnowledgeBase, "query", return_value=[]):
        result = LAMOrchestrator.process(
            patient_id="TEST-002",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=10,
            user_message="How is my recovery progressing at this stage?",
        )
    print(f"    sources={result['sources']} reply={result['reply']!r}")
    _check(result["sources"] == [], "expected empty sources when RAG returns nothing")
    _assert_reply_makes_no_unsupported_claims(result["reply"])
    print()


# ---------------------------------------------------------------------------
# 3. When RAG content IS available, recovery guidance stays grounded in it,
# the LLM path is used normally, and returned sources correspond to the
# content actually used for grounding.
# ---------------------------------------------------------------------------

def test_rag_grounded_recovery_response_uses_llm_and_cites_sources() -> None:
    print("=" * 78)
    print("3 -- RAG-grounded recovery question: LLM path runs, sources match retrieval")
    print("=" * 78)
    fake_docs = [
        {
            "topic": "Range of Motion & Extension Milestones",
            "content": "By Post-Op Day 7, patients should aim for 70-90 degrees of passive flexion.",
        }
    ]
    grounded_reply = "Based on your discharge notes, by Day 7 you should be reaching 70-90 degrees of flexion."

    llama_mock = MagicMock(return_value=grounded_reply)
    with patch.object(ClinicalKnowledgeBase, "query", return_value=fake_docs) as query_mock, \
         patch.object(ChatAgent, "_query_llama", llama_mock):
        result = LAMOrchestrator.process(
            patient_id="TEST-003",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=10,
            user_message="How is my recovery progressing at this stage?",
        )

    print(f"    sources={result['sources']} engine={result['engine']}")
    print(f"    reply={result['reply']!r}")
    _check(query_mock.called, "expected ClinicalKnowledgeBase.query to be called when testing the grounded path")
    _check(llama_mock.call_count == 1, "expected the LLM to be consulted exactly once when RAG content was retrieved")
    _check(result["reply"] == grounded_reply, "expected the grounded LLM reply to be returned verbatim")
    _check(
        result["sources"] == ["Range of Motion & Extension Milestones"],
        f"returned sources {result['sources']!r} do not correspond to the retrieved content used for grounding",
    )
    print("    CONFIRMED: with RAG content available, the LLM runs and sources match what was retrieved.")
    print()


def main() -> int:
    test_live_request_no_rag_match_does_not_invent()
    test_empty_sources_never_pair_with_unsupported_claims()
    test_rag_grounded_recovery_response_uses_llm_and_cites_sources()

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
