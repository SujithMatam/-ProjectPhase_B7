"""
LAM Intent Classifier -- Phase 2 semantic (Sentence-BERT) implementation.

Public interface (unchanged from Phase 1):
    IntentClassifier.classify(query: str, context: LAMContext) -> IntentLabel

Phase 2 strategy:
  - Embed the query with a Sentence-BERT model
    (sentence-transformers/all-MiniLM-L6-v2) and compare it, via cosine
    similarity, against a small set of hand-written prototype sentences for
    each of the 8 ROUTABLE intents.
  - Score per intent is the MAX similarity among that intent's prototypes
    (max-pooling).  The top-1 / top-2 scores and their margin decide whether
    the semantic result is trusted.
  - If the semantic result is low-confidence, low-margin, or unavailable
    (import/model/inference failure), fall back to the Phase 1 deterministic
    keyword classifier.

Hard safety invariant (do not weaken):
  IntentClassifier.classify() NEVER returns EMERGENCY or OUT_OF_SCOPE, no
  matter what happens internally (semantic result, low confidence, low
  margin, or the model being completely unavailable).  Those two labels are
  reserved exclusively for the deterministic SafetyTriageEngine (RED path)
  and ScopeValidator, both of which run in the orchestrator BEFORE
  IntentClassifier.classify() is ever called.  This module has no knowledge
  of, and makes no attempt to reproduce, that logic.

No generative LLM (Ollama or otherwise) is used anywhere in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from lam.schemas import IntentLabel, LAMContext

# ---------------------------------------------------------------------------
# Configurable thresholds (provisional diagnostic values -- do not tune these
# merely to force tests to pass; they express a genuine confidence gate).
# ---------------------------------------------------------------------------

SEMANTIC_MIN_SCORE: float = 0.35
SEMANTIC_MIN_MARGIN: float = 0.04

_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Safe routable default used when neither semantic classification nor the
# keyword fallback identifies a specific intent. Never escalates, never
# deflects.
_DEFAULT_ROUTABLE_INTENT = IntentLabel.RECOVERY_PROGRESS

# The only 8 intents IntentClassifier.classify() may ever return.
ROUTABLE_INTENTS: tuple[IntentLabel, ...] = (
    IntentLabel.RECOVERY_PROGRESS,
    IntentLabel.PAIN_SYMPTOMS,
    IntentLabel.REHABILITATION,
    IntentLabel.MEDICATION,
    IntentLabel.WOUND_CARE,
    IntentLabel.DAILY_ACTIVITY,
    IntentLabel.NUTRITION,
    IntentLabel.MENTAL_WELLBEING,
)

# ---------------------------------------------------------------------------
# Prototype sentences -- multiple representative examples per routable
# intent, used to build the semantic reference embeddings.
# ---------------------------------------------------------------------------

_PROTOTYPE_SENTENCES: dict[IntentLabel, list[str]] = {
    IntentLabel.RECOVERY_PROGRESS: [
        "When will I reach recovery milestones after my surgery?",
        "What is the expected recovery timeline for my procedure?",
        "When can I expect to return to normal activities?",
        "How is my healing progressing so far?",
        "Is my recovery on track for this stage after surgery?",
        "How long before I can move around like I used to?",
    ],
    IntentLabel.PAIN_SYMPTOMS: [
        "I am experiencing pain in the operated area.",
        "My joint feels swollen and tender.",
        "I have stiffness and numbness in my leg.",
        "There is tingling and throbbing pain near the incision.",
        "The pain has become sharper and more intense today.",
        "My joint seems more inflamed than yesterday and it's painful.",
    ],
    IntentLabel.REHABILITATION: [
        "What exercises should I do for physiotherapy?",
        "How many heel slides should I perform daily?",
        "What is my range of motion goal this week?",
        "Can you guide me through strengthening exercises?",
        "How should I do my rehab stretches?",
        "Am I ready to progress my physical therapy exercises?",
    ],
    IntentLabel.MEDICATION: [
        "I forgot to take my prescribed medicine.",
        "What is the correct dose of my pain medication?",
        "I missed a dose of my anticoagulant.",
        "Are there side effects from my current medication?",
        "When should I take my next tablet?",
        "I skipped my nighttime dose of pain medicine.",
    ],
    IntentLabel.WOUND_CARE: [
        "How do I clean my surgical incision?",
        "Can I change my wound dressing today?",
        "There is drainage coming from my stitches.",
        "My wound has some redness around it.",
        "When should the staples be removed?",
        "Is it okay to redo the bandage over my surgical cut today?",
    ],
    IntentLabel.DAILY_ACTIVITY: [
        "When can I climb stairs again?",
        "Is it safe for me to drive yet?",
        "What is the best sleeping position after surgery?",
        "Can I take a bath or shower now?",
        "How do I safely transfer from bed to a chair?",
        "When am I allowed to go up steps and get behind the wheel?",
    ],
    IntentLabel.NUTRITION: [
        "What foods should I eat during recovery?",
        "How much protein do I need after surgery?",
        "Am I drinking enough water for healing?",
        "What is a good post-surgery diet?",
        "Should I take nutritional supplements while recovering?",
        "Which meals and protein sources are best during my recovery?",
    ],
    IntentLabel.MENTAL_WELLBEING: [
        "I feel anxious about moving my operated leg.",
        "I am worried and stressed about my recovery.",
        "I feel scared to put weight on my leg.",
        "My mood has been low since the surgery.",
        "I feel overwhelmed by the recovery process.",
        "I feel nervous about putting weight on my surgical leg.",
    ],
}

# ---------------------------------------------------------------------------
# Phase 1 keyword tables, restricted to the 8 routable intents only.
# EMERGENCY is intentionally excluded: the deterministic SafetyTriageEngine
# owns that decision exclusively. OUT_OF_SCOPE is intentionally excluded:
# the ScopeValidator owns that decision exclusively.
# ---------------------------------------------------------------------------

_ROUTABLE_KEYWORD_RULES: list[tuple[IntentLabel, frozenset[str]]] = [
    (IntentLabel.PAIN_SYMPTOMS, frozenset({
        "pain", "hurt", "hurts", "hurting", "ache", "aching",
        "sore", "soreness", "sharp pain", "burning pain",
        "swelling", "swollen", "puffiness", "tender", "tenderness",
        "numb", "numbness", "tingling", "stiffness", "stiff",
        "throbbing",
    })),
    (IntentLabel.WOUND_CARE, frozenset({
        "wound", "incision", "cut", "scar", "stitches", "staples",
        "suture", "drainage", "draining", "leaking", "discharge",
        "bandage", "dressing", "redness around wound", "infection",
        "pus", "yellow fluid", "wound care", "clean wound",
    })),
    (IntentLabel.MEDICATION, frozenset({
        "medication", "medicine", "drug", "drugs", "pill", "pills",
        "tablet", "dose", "dosage", "paracetamol", "ibuprofen",
        "opioid", "painkiller", "aspirin", "anticoagulant",
        "blood thinner", "warfarin", "rivaroxaban", "antibiotic",
        "prescription", "take my medication", "when to take",
        "missed dose", "side effect",
    })),
    (IntentLabel.REHABILITATION, frozenset({
        "exercise", "exercises", "physical therapy", "physio",
        "physiotherapy", "rehab", "rehabilitation", "stretch",
        "stretching", "range of motion", "rom", "flexion", "extension",
        "bend", "straighten", "quad set", "heel slide", "leg raise",
        "ankle pump", "crutches", "walker", "walking aid",
        "weight bearing", "mobility", "strength", "strengthening",
    })),
    (IntentLabel.MENTAL_WELLBEING, frozenset({
        "anxious", "anxiety", "depressed", "depression",
        "worried", "worry", "scared", "fear", "frustrated",
        "mental health", "mood", "emotional", "stress", "stressed",
        "overwhelmed", "sad", "hopeless", "motivation", "bored",
        "lonely", "isolation",
    })),
    (IntentLabel.RECOVERY_PROGRESS, frozenset({
        "recovery", "healing", "progress", "how am i doing",
        "normal", "expected", "milestones", "timeline",
        "postop day", "post-op day", "week", "weeks",
        "discharge", "going home", "return to work",
        "getting better", "improve", "improvement",
    })),
    (IntentLabel.DAILY_ACTIVITY, frozenset({
        "shower", "showering", "bath", "bathing", "wash",
        "sleep", "sleeping", "lying down", "position",
        "drive", "driving", "car", "stairs", "climbing",
        "toilet", "chair", "sitting", "stand", "standing",
        "daily activity", "activities", "chores",
    })),
    (IntentLabel.NUTRITION, frozenset({
        "eat", "eating", "diet", "food", "nutrition", "nutritional",
        "protein", "calories", "vitamin", "supplement", "hydration",
        "water", "drink", "alcohol", "constipation", "bowel",
        "appetite", "weight", "lose weight",
    })),
]

# ---------------------------------------------------------------------------
# Lazy, once-only model + prototype-embedding loading.
# ---------------------------------------------------------------------------

_model = None
_np = None
_model_load_attempted = False
_model_available = False
_prototype_embeddings: Optional[dict[IntentLabel, list[tuple[str, "object"]]]] = None


def _load_model() -> bool:
    """
    Load the SentenceTransformer model exactly once (lazily, on first use).
    Returns True if the model is available, False if it could not be loaded
    (missing dependency, download failure, corrupted weights, etc.).
    Subsequent calls do not retry -- a failed load is treated as a stable
    "offline" state for the remainder of the process lifetime.
    """
    global _model, _np, _model_load_attempted, _model_available
    if _model_load_attempted:
        return _model_available
    _model_load_attempted = True
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer

        _np = np
        _model = SentenceTransformer(_MODEL_NAME)
        _model_available = True
    except Exception:
        _model = None
        _np = None
        _model_available = False
    return _model_available


def _get_prototype_embeddings():
    """
    Batch-encode every prototype sentence exactly once and cache the
    normalized embeddings, keyed by intent. Returns None if the model is
    unavailable or encoding fails.
    """
    global _prototype_embeddings
    if _prototype_embeddings is not None:
        return _prototype_embeddings
    if not _load_model():
        return None

    try:
        flat_sentences: list[str] = []
        owners: list[IntentLabel] = []
        for intent, sentences in _PROTOTYPE_SENTENCES.items():
            for sentence in sentences:
                flat_sentences.append(sentence)
                owners.append(intent)

        embeddings = _model.encode(
            flat_sentences,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        by_intent: dict[IntentLabel, list[tuple[str, object]]] = {}
        for intent, sentence, embedding in zip(owners, flat_sentences, embeddings):
            by_intent.setdefault(intent, []).append((sentence, embedding))

        _prototype_embeddings = by_intent
        return _prototype_embeddings
    except Exception:
        _prototype_embeddings = None
        return None


def _semantic_scores(query: str) -> Optional[dict[IntentLabel, tuple[float, str]]]:
    """
    Encode `query` and return, for each routable intent, the max cosine
    similarity among that intent's prototypes plus the matched prototype
    sentence. Returns None on any failure (offline state).
    """
    prototypes = _get_prototype_embeddings()
    if prototypes is None:
        return None

    try:
        query_embedding = _model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )[0]
    except Exception:
        return None

    scores: dict[IntentLabel, tuple[float, str]] = {}
    for intent, entries in prototypes.items():
        best_score = float("-inf")
        best_sentence = entries[0][0]
        for sentence, embedding in entries:
            similarity = float(_np.dot(query_embedding, embedding))
            if similarity > best_score:
                best_score = similarity
                best_sentence = sentence
        scores[intent] = (best_score, best_sentence)
    return scores


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

@dataclass
class ClassificationDetail:
    """Diagnostic detail behind a single classify() decision."""
    intent: IntentLabel
    top1_intent: Optional[IntentLabel]
    top1_score: float
    top2_intent: Optional[IntentLabel]
    top2_score: float
    margin: float
    matched_prototype: Optional[str]
    decision_path: str  # "semantic" | "fallback_low_confidence" |
                         # "fallback_low_margin" | "fallback_offline"


class IntentClassifier:
    """
    Classifies a patient query into one of the 8 ROUTABLE IntentLabels.

    Phase 2 implementation: Sentence-BERT semantic similarity, with a
    deterministic keyword fallback (Phase 1 logic, restricted to routable
    intents) for low-confidence, low-margin, or offline cases.

    This classifier NEVER returns EMERGENCY or OUT_OF_SCOPE. Those remain
    reserved for SafetyTriageEngine and ScopeValidator respectively, both of
    which run upstream in the orchestrator.
    """

    @classmethod
    def classify(cls, query: str, context: LAMContext) -> IntentLabel:
        """
        Classify query into a routable IntentLabel.

        Args:
            query:   The patient's message text.
            context: LAMContext with patient metadata (unused by the current
                     semantic/keyword logic; kept for interface stability
                     and future context-aware enrichment).

        Returns:
            One of the 8 ROUTABLE_INTENTS. Never EMERGENCY or OUT_OF_SCOPE.
        """
        return cls.classify_detailed(query, context).intent

    @classmethod
    def classify_detailed(cls, query: str, context: LAMContext) -> ClassificationDetail:
        """
        Same decision as classify(), plus full diagnostic detail: top1/top2
        intents and scores, margin, matched prototype, and which decision
        path was taken.
        """
        scores = _semantic_scores(query)

        if scores is None:
            fallback_intent = cls._classify_by_keywords(query)
            return ClassificationDetail(
                intent=fallback_intent,
                top1_intent=None,
                top1_score=0.0,
                top2_intent=None,
                top2_score=0.0,
                margin=0.0,
                matched_prototype=None,
                decision_path="fallback_offline",
            )

        ranked = sorted(scores.items(), key=lambda kv: kv[1][0], reverse=True)
        top1_intent, (top1_score, top1_prototype) = ranked[0]
        if len(ranked) > 1:
            top2_intent, (top2_score, _) = ranked[1]
        else:
            top2_intent, top2_score = None, 0.0
        margin = top1_score - top2_score

        if top1_score < SEMANTIC_MIN_SCORE:
            fallback_intent = cls._classify_by_keywords(query)
            return ClassificationDetail(
                intent=fallback_intent,
                top1_intent=top1_intent,
                top1_score=top1_score,
                top2_intent=top2_intent,
                top2_score=top2_score,
                margin=margin,
                matched_prototype=top1_prototype,
                decision_path="fallback_low_confidence",
            )

        if margin < SEMANTIC_MIN_MARGIN:
            fallback_intent = cls._classify_by_keywords(query)
            return ClassificationDetail(
                intent=fallback_intent,
                top1_intent=top1_intent,
                top1_score=top1_score,
                top2_intent=top2_intent,
                top2_score=top2_score,
                margin=margin,
                matched_prototype=top1_prototype,
                decision_path="fallback_low_margin",
            )

        return ClassificationDetail(
            intent=top1_intent,
            top1_intent=top1_intent,
            top1_score=top1_score,
            top2_intent=top2_intent,
            top2_score=top2_score,
            margin=margin,
            matched_prototype=top1_prototype,
            decision_path="semantic",
        )

    # ------------------------------------------------------------------
    # Deterministic keyword fallback (Phase 1 logic, routable-only).
    # ------------------------------------------------------------------

    @classmethod
    def _classify_by_keywords(cls, query: str) -> IntentLabel:
        """
        Keyword scan restricted to the 8 routable intents.
        Returns the first matching IntentLabel, or the safe routable default
        (RECOVERY_PROGRESS) if nothing matches. Never returns EMERGENCY or
        OUT_OF_SCOPE.
        """
        lower = query.lower()
        for intent_label, keywords in _ROUTABLE_KEYWORD_RULES:
            if any(kw in lower for kw in keywords):
                return intent_label
        return _DEFAULT_ROUTABLE_INTENT
