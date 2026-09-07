"""
Regression suite for the ChatAgent deterministic (Ollama-unavailable)
fallback -- procedure isolation for exercise/rehab replies.

Root cause fixed here: agents/chat_agent.py::_generate_smart_reply()'s
"exercise"/"workout"/"physio" branch used to return hardcoded,
TKA/knee-specific exercise text (flexion degrees, quad sets, heel slides,
calf raises) regardless of the patient's actual procedure or the ALREADY
procedure-filtered rag_docs it was passed. A THA (or GEN/ankle) patient
could receive knee-specific fallback advice whenever Ollama was
unreachable. See agents/chat_agent.py::_rehab_fallback_reply() for the fix:
it grounds itself in the already procedure-filtered rag_docs, or falls back
to conservative non-specific wording -- it never hardcodes exercise content
of its own, so cross-procedure leakage is structurally impossible.

A second, related root cause is also covered here: the swelling fallback
branch used `('knee' if 'knee' in surgery_type.lower() else 'hip')`, which
mapped EVERY non-knee procedure -- including GEN/ankle/foot/lower-leg -- to
"hip". Fixed via _SWELLING_BODY_REGION_BY_PROCEDURE (TKA->knee, THA->hip,
deliberately no GEN entry) with neutral "operative area" wording for any
procedure not in that map, so nothing is guessed.

Plain-Python script (no pytest dependency), consistent with the other
test_*.py files in this directory.

Run directly:
    .venv/Scripts/python.exe test_fallback_procedure_isolation.py
"""

from __future__ import annotations

import sys
from typing import Any, Dict
from unittest.mock import patch

from agents.chat_agent import ChatAgent
from lam.orchestrator import LAMOrchestrator
from lam.schemas import WeightBearingStatus

_FAILURES: list[str] = []


def _check(condition: bool, message: str) -> None:
    if not condition:
        _FAILURES.append(message)
        print(f"    !! FAILED: {message}")


# Phrases unique to the OLD hardcoded TKA/knee fallback text (not generic
# joint terminology like bare "flexion", which legitimately also appears in
# the real THA RAG content -- these are the specific knee-exercise phrases
# that must never appear for a THA/GEN patient).
_TKA_ONLY_PHRASES = ["passive flexion", "quad set", "heel slide", "calf raise", "knee flat", "seated knee extension", "straight leg raise"]
# Phrases that only ever make sense for a HIP (THA) patient.
_THA_ONLY_PHRASES = ["hip flexion", "abduction wedge", "crossing legs", "dislocation"]


def _force_ollama_unavailable():
    """Patch ChatAgent._query_llama to behave exactly as it does when Ollama
    is unreachable (returns None), so answer_question() falls through to
    the deterministic _generate_smart_reply() path under test."""
    return patch.object(ChatAgent, "_query_llama", classmethod(lambda cls, **kwargs: None))


# ---------------------------------------------------------------------------
# 1. THA exercise query with Ollama unavailable must NOT get knee/TKA advice
# ---------------------------------------------------------------------------

def test_tha_fallback_has_no_tka_language() -> None:
    print("=" * 78)
    print("1 -- THA exercise fallback contains no TKA/knee-specific language")
    print("=" * 78)
    with _force_ollama_unavailable():
        result = LAMOrchestrator.process(
            patient_id="TEST-PT",
            surgery_type="Total Hip Arthroplasty (THA)",
            affected_limb="Left",
            postop_day=10,
            user_message="What exercises are safe for me right now?",
        )
    reply_lower = result["reply"].lower()
    print(f"    engine={result['engine']}")
    print(f"    reply={result['reply']!r}")
    _check(result["engine"] == "Clinical Synthesis Engine", "expected the deterministic fallback engine to have been used")
    for phrase in _TKA_ONLY_PHRASES:
        _check(phrase not in reply_lower, f"REGRESSION: THA fallback reply contains TKA-only phrase {phrase!r}")
    print()


# ---------------------------------------------------------------------------
# 2. TKA exercise fallback must NOT get THA-only advice
# ---------------------------------------------------------------------------

def test_tka_fallback_has_no_tha_language() -> None:
    print("=" * 78)
    print("2 -- TKA exercise fallback contains no THA-only language")
    print("=" * 78)
    with _force_ollama_unavailable():
        result = LAMOrchestrator.process(
            patient_id="TEST-PT",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=10,
            user_message="What exercises should I do for my knee?",
        )
    reply_lower = result["reply"].lower()
    print(f"    engine={result['engine']}")
    print(f"    reply={result['reply']!r}")
    _check(result["engine"] == "Clinical Synthesis Engine", "expected the deterministic fallback engine to have been used")
    for phrase in _THA_ONLY_PHRASES:
        _check(phrase not in reply_lower, f"REGRESSION: TKA fallback reply contains THA-only phrase {phrase!r}")
    print()


# ---------------------------------------------------------------------------
# 3. GEN/ankle fallback must not silently become TKA, and must not invent
# exercises/reps/ROM when no relevant protocol is retrieved.
# ---------------------------------------------------------------------------

def test_gen_fallback_does_not_become_tka() -> None:
    print("=" * 78)
    print("3 -- GEN/ankle exercise fallback does not silently become TKA")
    print("=" * 78)
    with _force_ollama_unavailable():
        result = LAMOrchestrator.process(
            patient_id="TEST-PT",
            surgery_type="Ankle ORIF",
            affected_limb="Right",
            postop_day=10,
            user_message="What exercises should I do for my ankle?",
        )
    reply_lower = result["reply"].lower()
    print(f"    engine={result['engine']} sources={result['sources']}")
    print(f"    reply={result['reply']!r}")
    _check(result["engine"] == "Clinical Synthesis Engine", "expected the deterministic fallback engine to have been used")
    for phrase in _TKA_ONLY_PHRASES + _THA_ONLY_PHRASES:
        _check(phrase not in reply_lower, f"REGRESSION: GEN fallback reply contains procedure-specific phrase {phrase!r}")
    _check(
        result["sources"] == [],
        f"GEN query unexpectedly matched retrieved sources {result['sources']!r} -- verify this test still exercises the no-match path",
    )
    _check(
        "check with your physical therapist" in reply_lower or "surgical team" in reply_lower,
        "GEN fallback with no retrieved protocol should give conservative, deferring wording",
    )
    print()


# ---------------------------------------------------------------------------
# 4. Weight-bearing / restriction context is not contradicted by the
# fallback, in both the RAG-grounded and no-match cases.
# ---------------------------------------------------------------------------

def test_restriction_not_contradicted() -> None:
    print("=" * 78)
    print("4 -- Weight-bearing restriction context is not contradicted by the fallback")
    print("=" * 78)
    restriction_instruction = (
        "Focus on physiotherapy, exercises, range of motion, and mobility progression. "
        "Reported rehabilitation context: Prescribed weight-bearing status: Non-Weight-Bearing (NWB)."
    )

    # 4a. No matching retrieved protocol -- must defer to the restriction,
    # never invent an exercise that could contradict it.
    reply_no_match = ChatAgent._generate_smart_reply(
        user_message="What exercises can I do today?",
        patient_id="TEST-PT",
        surgery_type="Total Hip Arthroplasty (THA)",
        affected_limb="Left",
        postop_day=10,
        rag_docs=[],
        domain_instruction=restriction_instruction,
    )
    print(f"    no-match reply = {reply_no_match!r}")
    _check(
        "prescribed restriction" in reply_no_match.lower() or "weight-bearing restriction" in reply_no_match.lower(),
        "no-match fallback with a recorded restriction did not reference the restriction",
    )
    for phrase in _TKA_ONLY_PHRASES + ["squat", "lunge", "standing"]:
        _check(phrase not in reply_no_match.lower(), f"REGRESSION: restricted no-match fallback suggested {phrase!r}")

    # 4b. A matching retrieved protocol exists -- the restriction note must
    # be appended, not silently dropped.
    reply_with_match = ChatAgent._generate_smart_reply(
        user_message="What exercises can I do today?",
        patient_id="TEST-PT",
        surgery_type="Total Hip Arthroplasty (THA)",
        affected_limb="Left",
        postop_day=10,
        rag_docs=[{"topic": "Hip Precautions & Dislocation Prevention", "content": "Avoid hip flexion greater than 90 degrees."}],
        domain_instruction=restriction_instruction,
    )
    print(f"    with-match reply = {reply_with_match!r}")
    _check(
        "weight-bearing restriction is on record" in reply_with_match.lower(),
        "RAG-grounded fallback with a recorded restriction did not append the restriction note",
    )
    _check(
        "Avoid hip flexion greater than 90 degrees" in reply_with_match,
        "RAG-grounded fallback did not cite the retrieved content",
    )

    # 4c. No restriction supplied at all -- behavior must be unaffected
    # (no restriction note fabricated out of nowhere).
    reply_unrestricted = ChatAgent._generate_smart_reply(
        user_message="What exercises can I do today?",
        patient_id="TEST-PT",
        surgery_type="Total Hip Arthroplasty (THA)",
        affected_limb="Left",
        postop_day=10,
        rag_docs=[{"topic": "Hip Precautions & Dislocation Prevention", "content": "Avoid hip flexion greater than 90 degrees."}],
        domain_instruction=None,
    )
    print(f"    unrestricted reply = {reply_unrestricted!r}")
    _check(
        "weight-bearing restriction is on record" not in reply_unrestricted.lower(),
        "fallback fabricated a restriction note when none was supplied",
    )
    print("    CONFIRMED: fallback never contradicts a recorded weight-bearing restriction.")
    print()


# ---------------------------------------------------------------------------
# 5. Generic (non-symptom, non-rehab) fallback: the RAG-grounded branch is
# unaffected; the no-rag_docs branch was ALSO invented ungrounded advice
# ("elevate your leg", "stay hydrated") and is fixed here to match the
# conservative no-invention pattern already used by the swelling/pain
# branches (tests 8/9) -- see agents/chat_agent.py::_generate_smart_reply().
# ---------------------------------------------------------------------------

def test_non_rehab_fallback_unaffected() -> None:
    print("=" * 78)
    print("5 -- Generic (non-symptom, non-rehab) fallback behavior")
    print("=" * 78)

    generic_with_docs = ChatAgent._generate_smart_reply(
        user_message="How is my recovery going overall?",
        patient_id="TEST-PT", surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right", postop_day=5,
        rag_docs=[{"topic": "Some Topic", "content": "Some retrieved content."}],
    )
    print(f"    generic (with rag_docs) reply = {generic_with_docs!r}")
    _check("Based on your Day 5 protocol for" in generic_with_docs, "generic-with-rag_docs fallback branch changed unexpectedly")

    generic_no_docs = ChatAgent._generate_smart_reply(
        user_message="How is my recovery going overall?",
        patient_id="TEST-PT", surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right", postop_day=5, rag_docs=[],
    )
    print(f"    generic (no rag_docs) reply   = {generic_no_docs!r}")
    lower_no_docs = generic_no_docs.lower()
    _check(
        "don't have enough retrieved protocol information" in lower_no_docs,
        "generic-no-rag_docs fallback no longer states that no protocol was retrieved",
    )
    for phrase in ["your progress is on track", "doing great", "typically", "elevate your leg", "stay hydrated"]:
        _check(
            phrase not in lower_no_docs,
            f"REGRESSION: generic-no-rag_docs fallback invented unsupported claim {phrase!r}",
        )

    print("    CONFIRMED: generic (non-symptom) fallback branch no longer invents ungrounded recovery/advice claims.")
    print()


# ---------------------------------------------------------------------------
# 6. Swelling fallback body-region wording -- TKA/THA/GEN isolation.
# Root cause: `('knee' if 'knee' in surgery_type.lower() else 'hip')` mapped
# EVERY non-knee procedure (including ankle/foot/lower-leg/GEN) to "hip".
# Fixed via _SWELLING_BODY_REGION_BY_PROCEDURE (TKA->knee, THA->hip, no
# entry for GEN) + neutral "operative area" fallback wording.
# ---------------------------------------------------------------------------

def test_swelling_fallback_body_region_isolation() -> None:
    print("=" * 78)
    print("6 -- Swelling fallback body-region wording (TKA/THA/GEN isolation)")
    print("=" * 78)

    tka_reply = ChatAgent._generate_smart_reply(
        user_message="I have some swelling today",
        patient_id="TEST-PT", surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right", postop_day=5, rag_docs=[], procedure="TKA",
    )
    print(f"    TKA reply = {tka_reply!r}")
    _check("knee" in tka_reply.lower(), "TKA swelling fallback did not mention knee")
    _check("hip" not in tka_reply.lower(), "REGRESSION: TKA swelling fallback says hip")

    tha_reply = ChatAgent._generate_smart_reply(
        user_message="I have some swelling today",
        patient_id="TEST-PT", surgery_type="Total Hip Arthroplasty (THA)",
        affected_limb="Left", postop_day=5, rag_docs=[], procedure="THA",
    )
    print(f"    THA reply = {tha_reply!r}")
    _check("hip" in tha_reply.lower(), "THA swelling fallback did not mention hip")
    _check("knee" not in tha_reply.lower(), "REGRESSION: THA swelling fallback says knee")

    gen_reply = ChatAgent._generate_smart_reply(
        user_message="I have some swelling today",
        patient_id="TEST-PT", surgery_type="Ankle ORIF",
        affected_limb="Right", postop_day=5, rag_docs=[], procedure="GEN",
    )
    print(f"    GEN reply = {gen_reply!r}")
    _check("knee" not in gen_reply.lower(), "REGRESSION: GEN/ankle swelling fallback incorrectly says knee")
    _check("hip" not in gen_reply.lower(), "REGRESSION: GEN/ankle swelling fallback incorrectly says hip (the original bug)")
    _check(
        "operative area" in gen_reply.lower() or "affected" in gen_reply.lower(),
        "GEN/ankle swelling fallback did not use neutral wording",
    )

    # procedure omitted entirely (defensive: an older/direct caller that
    # doesn't yet pass procedure) must ALSO never guess "hip".
    omitted_reply = ChatAgent._generate_smart_reply(
        user_message="I have some swelling today",
        patient_id="TEST-PT", surgery_type="Ankle ORIF",
        affected_limb="Right", postop_day=5, rag_docs=[],
    )
    print(f"    procedure-omitted reply = {omitted_reply!r}")
    _check("hip" not in omitted_reply.lower(), "REGRESSION: omitted-procedure swelling fallback defaults to hip")
    _check("knee" not in omitted_reply.lower(), "omitted-procedure swelling fallback incorrectly guessed knee")

    print("    CONFIRMED: swelling fallback never maps a non-knee procedure to hip, and never guesses for GEN.")
    print()


# ---------------------------------------------------------------------------
# 7. RED safety precedence is unaffected by the fallback fixes -- a red-flag
# query must short-circuit in the orchestrator BEFORE _generate_smart_reply
# (or any fallback code) ever runs, exactly as before.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 8. Swelling fallback no longer invents a "normal" classification or a
# hardcoded icing duration when no RAG support exists; it CAN cite retrieved
# content verbatim (including retrieved wording like "is normal") when a
# matching protocol exists.
# ---------------------------------------------------------------------------

def test_swelling_fallback_no_invented_claims() -> None:
    print("=" * 78)
    print("8 -- Swelling fallback: no invented clinical claims without RAG support")
    print("=" * 78)

    no_match_reply = ChatAgent._generate_smart_reply(
        user_message="I have some swelling today",
        patient_id="TEST-PT", surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right", postop_day=5, rag_docs=[], procedure="TKA",
    )
    print(f"    no-match reply = {no_match_reply!r}")
    lower = no_match_reply.lower()
    _check("is normal" not in lower, "REGRESSION: swelling fallback invented a 'normal' classification with no RAG support")
    _check("increased circulation" not in lower, "REGRESSION: swelling fallback invented an unsupported clinical explanation")
    _check("ice pack" not in lower and "20 minutes" not in lower, "REGRESSION: swelling fallback invented a hardcoded icing duration")
    _check("elevated above heart level" not in lower, "REGRESSION: swelling fallback invented unsupported elevation advice")
    _check(
        "you reported" in lower and "swelling" in lower,
        "swelling fallback did not acknowledge the reported symptom",
    )
    _check(
        "don't have a matching retrieved protocol" in lower,
        "swelling fallback did not state that no matching protocol was retrieved",
    )
    _check(
        "care-team" in lower or "care team" in lower or "discharge instructions" in lower,
        "swelling fallback did not defer to existing care-team/discharge instructions",
    )

    # A matching retrieved protocol DOES exist -- the fallback may cite it
    # verbatim (including if the retrieved text itself says "normal"), since
    # that classification is now grounded in real retrieved content, not
    # invented by this code.
    match_reply = ChatAgent._generate_smart_reply(
        user_message="I have some swelling today",
        patient_id="TEST-PT", surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right", postop_day=5,
        rag_docs=[{
            "topic": "Normal Post-Op Edema vs DVT",
            "content": "Mild to moderate swelling of the operative knee and ankle is normal and expected up to 3 months post-op.",
        }],
        procedure="TKA",
    )
    print(f"    RAG-grounded reply = {match_reply!r}")
    _check(
        "Mild to moderate swelling of the operative knee and ankle is normal and expected" in match_reply,
        "RAG-grounded swelling fallback did not cite the retrieved content",
    )
    print("    CONFIRMED: swelling fallback never invents claims, but may cite grounded retrieved content.")
    print()


# ---------------------------------------------------------------------------
# 9. Pain fallback no longer invents medication timing or a "typical"
# soreness classification when no RAG support exists; it CAN use retrieved
# content when a matching protocol exists.
# ---------------------------------------------------------------------------

def test_pain_fallback_no_invented_claims() -> None:
    print("=" * 78)
    print("9 -- Pain fallback: no invented clinical claims without RAG support")
    print("=" * 78)

    no_match_reply = ChatAgent._generate_smart_reply(
        user_message="My knee really hurts",
        patient_id="TEST-PT", surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right", postop_day=5, rag_docs=[], procedure="TKA",
    )
    print(f"    no-match reply = {no_match_reply!r}")
    lower = no_match_reply.lower()
    _check("typical" not in lower, "REGRESSION: pain fallback invented a 'typical' soreness classification")
    _check("30-45 minutes" not in lower, "REGRESSION: pain fallback invented hardcoded medication timing")
    _check("mild to moderate soreness" not in lower, "REGRESSION: pain fallback invented an unsupported clinical judgment")
    _check(
        "you reported" in lower and "pain" in lower,
        "pain fallback did not acknowledge the reported symptom",
    )
    _check(
        "don't have a matching retrieved protocol" in lower,
        "pain fallback did not state that no matching protocol was retrieved",
    )

    match_reply = ChatAgent._generate_smart_reply(
        user_message="My knee really hurts",
        patient_id="TEST-PT", surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right", postop_day=5,
        rag_docs=[{
            "topic": "Pain Management & Analgesic Titration",
            "content": "Scheduled acetaminophen and prescribed NSAIDs if indicated, with short-acting opioids strictly reserved for breakthrough pain.",
        }],
        procedure="TKA",
    )
    print(f"    RAG-grounded reply = {match_reply!r}")
    _check(
        "Scheduled acetaminophen and prescribed NSAIDs" in match_reply,
        "RAG-grounded pain fallback did not cite the retrieved content",
    )
    print("    CONFIRMED: pain fallback never invents claims, but may cite grounded retrieved content.")
    print()


# ---------------------------------------------------------------------------
# 10. TKA/THA/GEN isolation holds for the pain branch too (mirrors test 6,
# which already covers the swelling branch).
# ---------------------------------------------------------------------------

def test_pain_fallback_procedure_isolation() -> None:
    print("=" * 78)
    print("10 -- Pain fallback procedure isolation (TKA/THA/GEN)")
    print("=" * 78)
    cases = [
        ("Total Knee Arthroplasty (TKA)", "TKA", [{"topic": "TKA Pain Doc", "content": "TKA-specific pain content."}]),
        ("Total Hip Arthroplasty (THA)", "THA", [{"topic": "THA Pain Doc", "content": "THA-specific pain content."}]),
        ("Ankle ORIF", "GEN", []),
    ]
    for surgery_type, procedure, rag_docs in cases:
        reply = ChatAgent._generate_smart_reply(
            user_message="It hurts today",
            patient_id="TEST-PT", surgery_type=surgery_type,
            affected_limb="Right", postop_day=5, rag_docs=rag_docs, procedure=procedure,
        )
        print(f"    {procedure} -> {reply!r}")
        if rag_docs:
            _check(rag_docs[0]["content"] in reply, f"{procedure}: expected reply to cite its own procedure-filtered content")
        else:
            _check("don't have a matching retrieved protocol" in reply.lower(), f"{procedure}: expected conservative no-match wording")
    print()


def test_red_precedence_unaffected() -> None:
    print("=" * 78)
    print("11 -- RED safety precedence unaffected by the fallback fixes")
    print("=" * 78)
    with _force_ollama_unavailable(), \
         patch.object(ChatAgent, "_generate_smart_reply", side_effect=AssertionError("fallback must never run for a RED query")) as fallback_mock:
        result = LAMOrchestrator.process(
            patient_id="TEST-PT",
            surgery_type="Total Hip Arthroplasty (THA)",
            affected_limb="Left",
            postop_day=5,
            user_message="I have severe calf pain and swelling in my calf.",
        )
    print(f"    intent={result['intent']} triage_level={result['triage_level']} fallback_calls={fallback_mock.call_count}")
    _check(result["triage_level"] == "RED", "red-flag query did not produce RED")
    _check(result["intent"] == "emergency", "RED query did not return EMERGENCY intent")
    _check(fallback_mock.call_count == 0, "RED query must never reach _generate_smart_reply()")
    print()


def main() -> int:
    test_tha_fallback_has_no_tka_language()
    test_tka_fallback_has_no_tha_language()
    test_gen_fallback_does_not_become_tka()
    test_restriction_not_contradicted()
    test_non_rehab_fallback_unaffected()
    test_swelling_fallback_body_region_isolation()
    test_swelling_fallback_no_invented_claims()
    test_pain_fallback_no_invented_claims()
    test_pain_fallback_procedure_isolation()
    test_red_precedence_unaffected()

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
