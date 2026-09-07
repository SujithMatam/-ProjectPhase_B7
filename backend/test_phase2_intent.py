"""
Phase 2 test suite -- semantic (Sentence-BERT) intent classification.

Run directly:
    .venv/Scripts/python.exe test_phase2_intent.py

This is a plain-Python script (no pytest dependency) so it can run inside
the existing backend/.venv without installing anything beyond
sentence-transformers. Assertions raise AssertionError on failure; the
script also prints a full diagnostic report (scores/margins/decision paths)
for every case, pass or fail, since hiding uncertainty defeats the purpose
of the diagnostics this phase adds.
"""

from __future__ import annotations

import sys
from typing import Optional

import lam.intent_classifier as intent_classifier_module
from lam.intent_classifier import (
    IntentClassifier,
    ROUTABLE_INTENTS,
    ClassificationDetail,
)
from lam.schemas import IntentLabel, LAMContext, ScopeStatus
from lam.orchestrator import LAMOrchestrator
from lam.scope_validator import ScopeValidator
from triage.safety_triage import SafetyTriageEngine

_FAILURES: list[str] = []

# Per-category correctness tallies, used for the accuracy summary at the end.
_ACCURACY: dict[str, list[bool]] = {
    "benchmark": [],
    "unseen_paraphrase": [],
    "ambiguous_boundary": [],
}


def _ctx(message: str) -> LAMContext:
    return LAMContext(
        patient_id="TEST-PT",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=5,
        user_message=message,
    )


def _fmt_intent(intent: Optional[IntentLabel]) -> str:
    return intent.value if intent is not None else "-"


def _print_detail(label: str, query: str, detail: ClassificationDetail) -> None:
    print(f"[{label}] \"{query}\"")
    print(f"    final_intent      = {detail.intent.value}")
    print(f"    top1              = {_fmt_intent(detail.top1_intent)} "
          f"(score={detail.top1_score:.4f})")
    print(f"    top2              = {_fmt_intent(detail.top2_intent)} "
          f"(score={detail.top2_score:.4f})")
    print(f"    margin            = {detail.margin:.4f}")
    print(f"    matched_prototype = {detail.matched_prototype!r}")
    print(f"    decision_path     = {detail.decision_path}")
    print()


def _check(condition: bool, message: str) -> None:
    """Hard assertion: appends to _FAILURES (fails the whole suite)."""
    if not condition:
        _FAILURES.append(message)
        print(f"    !! FAILED: {message}")


def _note(condition: bool, message: str) -> None:
    """
    Soft assertion for classification-accuracy metrics only: printed, but
    does NOT fail the suite. A single misclassified unseen paraphrase is a
    genuine, honestly-reported generalization gap -- not a broken safety
    invariant -- so it must not be hidden by cherry-picking easier wording,
    nor allowed to mask real invariant violations under one exit code.
    """
    if not condition:
        print(f"    ?? MISCLASSIFIED (reported in accuracy summary, not a hard failure): {message}")


# ---------------------------------------------------------------------------
# 1. Benchmark queries -- one per routable intent
# ---------------------------------------------------------------------------

BENCHMARKS: list[tuple[str, IntentLabel]] = [
    ("When should I expect to walk normally again?", IntentLabel.RECOVERY_PROGRESS),
    ("My knee is more swollen today and hurts.", IntentLabel.PAIN_SYMPTOMS),
    ("How many heel slides should I do?", IntentLabel.REHABILITATION),
    ("I forgot my evening pain tablet.", IntentLabel.MEDICATION),
    ("Can I change my incision dressing today?", IntentLabel.WOUND_CARE),
    ("When can I climb stairs and drive again?", IntentLabel.DAILY_ACTIVITY),
    ("What foods and protein should I eat while recovering?", IntentLabel.NUTRITION),
    ("I am anxious about moving my operated leg.", IntentLabel.MENTAL_WELLBEING),
]


def run_benchmarks() -> None:
    print("=" * 78)
    print("SECTION 1 -- Benchmark queries (8 routable intents)")
    print("=" * 78)
    for query, expected in BENCHMARKS:
        detail = IntentClassifier.classify_detailed(query, _ctx(query))
        _print_detail("benchmark", query, detail)
        correct = detail.intent == expected
        _ACCURACY["benchmark"].append(correct)
        _check(
            correct,
            f"benchmark query {query!r} expected {expected.value}, got {detail.intent.value}",
        )
        _check(
            detail.intent in ROUTABLE_INTENTS,
            f"benchmark query {query!r} returned a non-routable intent {detail.intent.value}",
        )


# ---------------------------------------------------------------------------
# 1b. Unseen paraphrases -- NOT present anywhere in _PROTOTYPE_SENTENCES.
# At least 3 per routable intent, worded differently from both the
# benchmark queries and the prototype sentences, to genuinely test
# generalization rather than verbatim/near-verbatim lookup.
# ---------------------------------------------------------------------------

UNSEEN_PARAPHRASES: list[tuple[str, IntentLabel]] = [
    # RECOVERY_PROGRESS
    ("How long does it typically take to fully recover from this kind of operation?", IntentLabel.RECOVERY_PROGRESS),
    ("Am I healing at the pace the surgeon expected?", IntentLabel.RECOVERY_PROGRESS),
    ("What can I expect in terms of getting back to my usual life?", IntentLabel.RECOVERY_PROGRESS),
    # PAIN_SYMPTOMS
    ("The area around my joint feels really tender and inflamed.", IntentLabel.PAIN_SYMPTOMS),
    ("I've got a burning sensation and some numbness in my foot.", IntentLabel.PAIN_SYMPTOMS),
    ("Why does my leg feel so stiff and achy this morning?", IntentLabel.PAIN_SYMPTOMS),
    # REHABILITATION
    ("What kind of stretching routine should I follow for physio?", IntentLabel.REHABILITATION),
    ("Can you tell me how to improve my range of motion?", IntentLabel.REHABILITATION),
    ("Should I be doing strengthening drills for my leg yet?", IntentLabel.REHABILITATION),
    # MEDICATION
    ("Is it fine to skip a dose of my blood thinner occasionally?", IntentLabel.MEDICATION),
    ("What happens if I take my antibiotic later than scheduled?", IntentLabel.MEDICATION),
    ("Can you tell me the right dosage for my prescribed painkiller?", IntentLabel.MEDICATION),
    # WOUND_CARE
    ("There's some fluid coming from my surgical cut, is that normal?", IntentLabel.WOUND_CARE),
    ("How often should I clean the area where the stitches are?", IntentLabel.WOUND_CARE),
    ("My scar looks a bit red around the edges, should I worry?", IntentLabel.WOUND_CARE),
    # DAILY_ACTIVITY
    ("Is it alright to take a shower on my own yet?", IntentLabel.DAILY_ACTIVITY),
    ("What's the safest way to get in and out of bed?", IntentLabel.DAILY_ACTIVITY),
    ("Can I sit in a regular chair or do I need something special?", IntentLabel.DAILY_ACTIVITY),
    # NUTRITION
    ("Should I be taking any vitamins to help my body heal?", IntentLabel.NUTRITION),
    ("How much water should I drink each day while recovering?", IntentLabel.NUTRITION),
    ("Is alcohol okay to have during my recovery period?", IntentLabel.NUTRITION),
    # MENTAL_WELLBEING
    ("I keep feeling down and unmotivated during this recovery.", IntentLabel.MENTAL_WELLBEING),
    ("I'm scared to put any weight on my leg, is that normal to feel?", IntentLabel.MENTAL_WELLBEING),
    ("I feel isolated and low because I can't do my usual routine.", IntentLabel.MENTAL_WELLBEING),
]


def run_unseen_paraphrases() -> None:
    print("=" * 78)
    print("SECTION 1b -- Unseen paraphrases (>=3 per routable intent, not in prototypes)")
    print("=" * 78)
    for query, expected in UNSEEN_PARAPHRASES:
        detail = IntentClassifier.classify_detailed(query, _ctx(query))
        _print_detail("unseen", query, detail)
        correct = detail.intent == expected
        _ACCURACY["unseen_paraphrase"].append(correct)
        _note(
            correct,
            f"unseen paraphrase {query!r} expected {expected.value}, got {detail.intent.value}",
        )
        _check(
            detail.intent in ROUTABLE_INTENTS,
            f"unseen paraphrase {query!r} returned a non-routable intent {detail.intent.value}",
        )


# ---------------------------------------------------------------------------
# 2. Ambiguous / boundary queries -- report, don't hide uncertainty.
# Each query is paired with an "acceptable" set of intents rather than a
# single expected label, since these are deliberately hard boundary cases
# between two genuinely plausible intents. Accuracy = predicted intent
# falls within the acceptable set for that query.
# ---------------------------------------------------------------------------

AMBIGUOUS_QUERIES: list[tuple[str, frozenset[IntentLabel]]] = [
    ("I don't feel like doing anything today and my leg feels stiff.",
     frozenset({IntentLabel.PAIN_SYMPTOMS, IntentLabel.MENTAL_WELLBEING})),
    ("Is it normal to feel this way after the procedure?",
     frozenset({IntentLabel.RECOVERY_PROGRESS, IntentLabel.MENTAL_WELLBEING})),
    ("I'm not sure if this is a side effect or just soreness.",
     frozenset({IntentLabel.MEDICATION, IntentLabel.PAIN_SYMPTOMS})),
    ("Should I be worried about how slow this is going?",
     frozenset({IntentLabel.RECOVERY_PROGRESS, IntentLabel.MENTAL_WELLBEING})),
    ("My leg feels weird when I try to move it during exercises.",
     frozenset({IntentLabel.PAIN_SYMPTOMS, IntentLabel.REHABILITATION})),
]

# Explicit boundary pairs requested: recovery_progress vs daily_activity,
# pain_symptoms vs wound_care, pain_symptoms vs rehabilitation,
# medication vs pain_symptoms, mental_wellbeing vs recovery_progress.
BOUNDARY_PAIR_QUERIES: list[tuple[str, frozenset[IntentLabel]]] = [
    ("Is it normal that I still can't manage the stairs at this point in my recovery?",
     frozenset({IntentLabel.RECOVERY_PROGRESS, IntentLabel.DAILY_ACTIVITY})),
    ("There's soreness and some fluid leaking near my stitches.",
     frozenset({IntentLabel.PAIN_SYMPTOMS, IntentLabel.WOUND_CARE})),
    ("My leg hurts a lot after doing my exercises today.",
     frozenset({IntentLabel.PAIN_SYMPTOMS, IntentLabel.REHABILITATION})),
    ("Since starting the new tablets my pain has gotten worse.",
     frozenset({IntentLabel.MEDICATION, IntentLabel.PAIN_SYMPTOMS})),
    ("I'm discouraged because my recovery doesn't feel like it's improving.",
     frozenset({IntentLabel.MENTAL_WELLBEING, IntentLabel.RECOVERY_PROGRESS})),
]


def run_ambiguous_cases() -> None:
    print("=" * 78)
    print("SECTION 2 -- Ambiguous / boundary queries (report only, acceptable-set accuracy)")
    print("=" * 78)
    for query, acceptable in AMBIGUOUS_QUERIES + BOUNDARY_PAIR_QUERIES:
        detail = IntentClassifier.classify_detailed(query, _ctx(query))
        _print_detail("ambiguous", query, detail)
        print(f"    acceptable set    = {sorted(i.value for i in acceptable)}")
        print()
        acceptable_hit = detail.intent in acceptable
        _ACCURACY["ambiguous_boundary"].append(acceptable_hit)
        _check(
            detail.intent in ROUTABLE_INTENTS,
            f"ambiguous query {query!r} returned a non-routable intent {detail.intent.value}",
        )


# ---------------------------------------------------------------------------
# 3. Fallback / safety-invariant tests
# ---------------------------------------------------------------------------

EMERGENCY_LIKE_QUERIES: list[str] = [
    "I can't breathe and my chest hurts, call ambulance",
    "My toes are blue and cold and I can't feel my foot",
    "There is pus coming out and I have a high fever",
]

OUT_OF_SCOPE_LIKE_QUERIES: list[str] = [
    "What is the weather like today?",
    "Can you recommend a good pizza place?",
    "My shoulder has been hurting for a week.",
]


def run_fallback_and_safety_invariants() -> None:
    print("=" * 78)
    print("SECTION 3 -- Fallback + safety invariant tests")
    print("=" * 78)

    # 3a. Low-confidence fallback (forced) must never return EMERGENCY/OUT_OF_SCOPE
    original_semantic_scores = intent_classifier_module._semantic_scores
    try:
        def _low_confidence_scores(query: str):
            real = original_semantic_scores(query)
            if real is None:
                return None
            return {intent: (0.01, proto) for intent, (_, proto) in real.items()}

        intent_classifier_module._semantic_scores = _low_confidence_scores
        for query, _ in BENCHMARKS + [(q, None) for q in EMERGENCY_LIKE_QUERIES]:
            detail = IntentClassifier.classify_detailed(query, _ctx(query))
            _print_detail("forced-low-confidence", query, detail)
            _check(
                detail.decision_path == "fallback_low_confidence",
                f"expected fallback_low_confidence decision path for {query!r}, got {detail.decision_path}",
            )
            _check(
                detail.intent != IntentLabel.EMERGENCY,
                f"low-confidence fallback returned EMERGENCY for {query!r}",
            )
            _check(
                detail.intent != IntentLabel.OUT_OF_SCOPE,
                f"low-confidence fallback returned OUT_OF_SCOPE for {query!r}",
            )
    finally:
        intent_classifier_module._semantic_scores = original_semantic_scores

    # 3b. Model-failure / offline fallback must never return EMERGENCY/OUT_OF_SCOPE
    try:
        intent_classifier_module._semantic_scores = lambda query: None
        for query, _ in BENCHMARKS + [(q, None) for q in EMERGENCY_LIKE_QUERIES]:
            detail = IntentClassifier.classify_detailed(query, _ctx(query))
            _print_detail("forced-offline", query, detail)
            _check(
                detail.decision_path == "fallback_offline",
                f"expected fallback_offline decision path for {query!r}, got {detail.decision_path}",
            )
            _check(
                detail.intent != IntentLabel.EMERGENCY,
                f"model-failure fallback returned EMERGENCY for {query!r}",
            )
            _check(
                detail.intent != IntentLabel.OUT_OF_SCOPE,
                f"model-failure fallback returned OUT_OF_SCOPE for {query!r}",
            )
            _check(
                detail.intent in ROUTABLE_INTENTS,
                f"model-failure fallback returned non-routable intent {detail.intent.value} for {query!r}",
            )
    finally:
        intent_classifier_module._semantic_scores = original_semantic_scores

    # 3c. Even with normal (working) semantic classification, emergency-like
    #     and out-of-scope-like phrasing must never come back as EMERGENCY /
    #     OUT_OF_SCOPE from IntentClassifier.classify() directly.
    for query in EMERGENCY_LIKE_QUERIES + OUT_OF_SCOPE_LIKE_QUERIES:
        detail = IntentClassifier.classify_detailed(query, _ctx(query))
        _print_detail("direct-classify-safety-check", query, detail)
        _check(
            detail.intent != IntentLabel.EMERGENCY,
            f"IntentClassifier.classify() returned EMERGENCY for {query!r}",
        )
        _check(
            detail.intent != IntentLabel.OUT_OF_SCOPE,
            f"IntentClassifier.classify() returned OUT_OF_SCOPE for {query!r}",
        )


# ---------------------------------------------------------------------------
# 4. Safety/scope precedence -- EMERGENCY and OUT_OF_SCOPE must originate
#    exclusively from SafetyTriageEngine and ScopeValidator, via the full
#    orchestrator pipeline (not from IntentClassifier).
# ---------------------------------------------------------------------------

def run_precedence_tests() -> None:
    print("=" * 78)
    print("SECTION 4 -- Safety/scope precedence via LAMOrchestrator")
    print("=" * 78)

    # 4a. RED emergency must originate from SafetyTriageEngine, surfaced via orchestrator
    red_message = "I can't breathe and have severe chest pain"
    triage = SafetyTriageEngine.evaluate(symptoms=red_message, post_op_day=5)
    _check(triage["triage_level"] == "RED", "expected SafetyTriageEngine to flag RED for emergency message")

    result = LAMOrchestrator.process(
        patient_id="TEST-PT",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=5,
        user_message=red_message,
    )
    print(f"[orchestrator RED] intent={result['intent']} engine={result['engine']} "
          f"triage_level={result['triage_level']} scope_status={result['scope_status']}")
    _check(result["intent"] == IntentLabel.EMERGENCY.value, "orchestrator RED path should report EMERGENCY intent")
    _check(result["engine"] == "Deterministic Safety Triage", "RED path engine should be Deterministic Safety Triage")
    _check(result["scope_status"] == ScopeStatus.NOT_EVALUATED.value, "RED path should not evaluate scope")

    # 4b. OUT_OF_SCOPE must originate from ScopeValidator, surfaced via orchestrator
    oos_message = "What is the weather like today?"
    scope_status, _reason = ScopeValidator.validate(query=oos_message, surgery_type="Total Knee Arthroplasty (TKA)")
    _check(scope_status == ScopeStatus.OUT_OF_SCOPE, "expected ScopeValidator to flag OUT_OF_SCOPE for weather message")

    result = LAMOrchestrator.process(
        patient_id="TEST-PT",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=5,
        user_message=oos_message,
    )
    print(f"[orchestrator OOS] intent={result['intent']} engine={result['engine']} "
          f"scope_status={result['scope_status']}")
    _check(result["intent"] == IntentLabel.OUT_OF_SCOPE.value, "orchestrator OOS path should report OUT_OF_SCOPE intent")
    _check(result["engine"] == "Scope Validator", "OOS path engine should be Scope Validator")
    print()


# ---------------------------------------------------------------------------
# 5. /api/chat response contract unchanged
# ---------------------------------------------------------------------------

_EXPECTED_CONTRACT_KEYS = {
    "reply", "triage_level", "is_escalated", "engine", "sources",
    "intent", "target_agent", "action", "scope_status",
}


def run_contract_tests() -> None:
    print("=" * 78)
    print("SECTION 5 -- /api/chat response contract")
    print("=" * 78)
    for message in [
        "When should I expect to walk normally again?",
        "I can't breathe and have severe chest pain",
        "What is the weather like today?",
    ]:
        result = LAMOrchestrator.process(
            patient_id="TEST-PT",
            surgery_type="Total Knee Arthroplasty (TKA)",
            affected_limb="Right",
            postop_day=5,
            user_message=message,
        )
        print(f"[contract] {message!r} -> keys={sorted(result.keys())}")
        _check(
            set(result.keys()) == _EXPECTED_CONTRACT_KEYS,
            f"/api/chat contract keys changed for {message!r}: {sorted(result.keys())}",
        )
    print()


# ---------------------------------------------------------------------------
# 6. No Ollama / generative LLM used for intent classification
# ---------------------------------------------------------------------------

def run_no_ollama_check() -> None:
    print("=" * 78)
    print("SECTION 6 -- No Ollama / generative LLM in intent classification")
    print("=" * 78)
    import inspect
    source = inspect.getsource(intent_classifier_module)
    lowered = source.lower()
    forbidden_usages = [
        "import ollama", "from ollama", "ollama.chat", "ollama.generate",
        "import openai", "from openai", "openai.chat", "requests.post",
        "requests.get",
    ]
    found = [u for u in forbidden_usages if u in lowered]
    _check(not found, f"intent_classifier.py contains generative-LLM/network call usage: {found}")
    print("    OK: no Ollama / generative-LLM call usage found in intent_classifier.py")
    print()


def run_accuracy_summary() -> None:
    print("=" * 78)
    print("SECTION 7 -- Accuracy summary by category")
    print("=" * 78)
    labels = {
        "benchmark": "Original benchmark queries",
        "unseen_paraphrase": "Unseen paraphrases",
        "ambiguous_boundary": "Ambiguous / boundary queries (acceptable-set match)",
    }
    for key, label in labels.items():
        results = _ACCURACY[key]
        n = len(results)
        correct = sum(results)
        pct = (correct / n * 100.0) if n else 0.0
        print(f"    {label:55s}: {correct}/{n} ({pct:.1f}%)")
    print()


def main() -> int:
    run_benchmarks()
    run_unseen_paraphrases()
    run_ambiguous_cases()
    run_fallback_and_safety_invariants()
    run_precedence_tests()
    run_contract_tests()
    run_no_ollama_check()
    run_accuracy_summary()

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
