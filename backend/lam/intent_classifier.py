"""
LAM Intent Classifier -- Phase 1 keyword/rule-based implementation.

Public interface:
    IntentClassifier.classify(query: str, context: LAMContext) -> IntentLabel

Phase 1 strategy: deterministic keyword matching.
  - No external dependencies.
  - Fully predictable and testable.
  - Ordered by clinical priority (EMERGENCY checked first).

Phase 2 upgrade path:
  Replace _classify_by_keywords() internals with Sentence-BERT cosine-
  similarity against intent prototype sentences.  The public classify()
  signature and the orchestrator call-site remain unchanged.
"""

from __future__ import annotations

from lam.schemas import IntentLabel, LAMContext

# ---------------------------------------------------------------------------
# Intent keyword tables
# Ordered from highest to lowest clinical priority within each group.
# Each entry is (IntentLabel, frozenset_of_trigger_keywords).
# The classifier walks this list in order and returns on first match.
# ---------------------------------------------------------------------------

_INTENT_RULES: list[tuple[IntentLabel, frozenset[str]]] = [
    # --- EMERGENCY (always checked first after triage, as a second signal) ---
    (IntentLabel.EMERGENCY, frozenset({
        "emergency", "can't breathe", "cannot breathe", "chest pain",
        "shortness of breath", "collapse", "collapsed", "unconscious",
        "call ambulance", "heart attack", "stroke", "severe bleeding",
        "coughing blood", "blood clot", "dvt", "pulmonary embolism",
        "drop foot", "toes blue", "toes pale", "foot cold",
        "pus coming out", "high fever", "foul smell", "wound gaping",
        "wound opening",
    })),

    # --- PAIN_SYMPTOMS ---
    (IntentLabel.PAIN_SYMPTOMS, frozenset({
        "pain", "hurt", "hurts", "hurting", "ache", "aching",
        "sore", "soreness", "sharp pain", "burning pain",
        "swelling", "swollen", "puffiness", "tender", "tenderness",
        "numb", "numbness", "tingling", "stiffness", "stiff",
        "throbbing",
    })),

    # --- WOUND_CARE ---
    (IntentLabel.WOUND_CARE, frozenset({
        "wound", "incision", "cut", "scar", "stitches", "staples",
        "suture", "drainage", "draining", "leaking", "discharge",
        "bandage", "dressing", "redness around wound", "infection",
        "pus", "yellow fluid", "wound care", "clean wound",
    })),

    # --- MEDICATION ---
    (IntentLabel.MEDICATION, frozenset({
        "medication", "medicine", "drug", "drugs", "pill", "pills",
        "tablet", "dose", "dosage", "paracetamol", "ibuprofen",
        "opioid", "painkiller", "aspirin", "anticoagulant",
        "blood thinner", "warfarin", "rivaroxaban", "antibiotic",
        "prescription", "take my medication", "when to take",
        "missed dose", "side effect",
    })),

    # --- REHABILITATION ---
    (IntentLabel.REHABILITATION, frozenset({
        "exercise", "exercises", "physical therapy", "physio",
        "physiotherapy", "rehab", "rehabilitation", "stretch",
        "stretching", "range of motion", "rom", "flexion", "extension",
        "bend", "straighten", "quad set", "heel slide", "leg raise",
        "ankle pump", "crutches", "walker", "walking aid",
        "weight bearing", "mobility", "strength", "strengthening",
    })),

    # --- MENTAL_WELLBEING --- (Moved up to prevent 'recovery' generic match)
    (IntentLabel.MENTAL_WELLBEING, frozenset({
        "anxious", "anxiety", "depressed", "depression",
        "worried", "worry", "scared", "fear", "frustrated",
        "mental health", "mood", "emotional", "stress", "stressed",
        "overwhelmed", "sad", "hopeless", "motivation", "bored",
        "lonely", "isolation",
    })),

    # --- RECOVERY_PROGRESS ---
    (IntentLabel.RECOVERY_PROGRESS, frozenset({
        "recovery", "healing", "progress", "how am i doing",
        "normal", "expected", "milestones", "timeline",
        "postop day", "post-op day", "week", "weeks",
        "discharge", "going home", "return to work",
        "getting better", "improve", "improvement",
    })),

    # --- DAILY_ACTIVITY ---
    (IntentLabel.DAILY_ACTIVITY, frozenset({
        "shower", "showering", "bath", "bathing", "wash",
        "sleep", "sleeping", "lying down", "position",
        "drive", "driving", "car", "stairs", "climbing",
        "toilet", "chair", "sitting", "stand", "standing",
        "daily activity", "activities", "chores",
    })),

    # --- NUTRITION ---
    (IntentLabel.NUTRITION, frozenset({
        "eat", "eating", "diet", "food", "nutrition", "nutritional",
        "protein", "calories", "vitamin", "supplement", "hydration",
        "water", "drink", "alcohol", "constipation", "bowel",
        "appetite", "weight", "lose weight",
    })),
]


class IntentClassifier:
    """
    Classifies patient query into one of the 10 supported IntentLabels.

    Phase 1 implementation: keyword/rule-based, deterministic, zero dependencies.
    Phase 2: replace _classify_by_keywords() with Sentence-BERT cosine-similarity.
    The public classify() method signature is unchanged between phases.
    """

    @classmethod
    def classify(cls, query: str, context: LAMContext) -> IntentLabel:
        """
        Classify query into an IntentLabel.

        Args:
            query:   The patient's message text.
            context: LAMContext with patient metadata (used for tie-breaking
                     and future embedding enrichment in Phase 2).

        Returns:
            IntentLabel matching the most likely intent.
        """
        return cls._classify_by_keywords(query)

    # ------------------------------------------------------------------
    # Phase 1 internals (replaceable in Phase 2 without touching above)
    # ------------------------------------------------------------------

    @classmethod
    def _classify_by_keywords(cls, query: str) -> IntentLabel:
        """
        Keyword scan in clinical-priority order.
        Returns the first matching IntentLabel, or OUT_OF_SCOPE if none match.

        NOTE: This method is the ONLY thing that changes in Phase 2.
        """
        lower = query.lower()
        for intent_label, keywords in _INTENT_RULES:
            if any(kw in lower for kw in keywords):
                return intent_label
        return IntentLabel.OUT_OF_SCOPE
