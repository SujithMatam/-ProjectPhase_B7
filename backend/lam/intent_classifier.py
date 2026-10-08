""""
LAM Intent Classifier.

Phase 2/3 implementation using:
1. Deterministic high-confidence rules.
2. Explicit patient-intake/context detection.
3. Sentence-BERT semantic similarity.
4. Keyword fallback.

Important:
This classifier NEVER returns:
    - EMERGENCY
    - OUT_OF_SCOPE

Those are handled upstream by:
    - SafetyTriageEngine
    - ScopeValidator

The classifier only returns routable intents.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

from lam.schemas import IntentLabel, LAMContext


# ============================================================================
# CONFIGURATION
# ============================================================================

SEMANTIC_MIN_SCORE = 0.35
SEMANTIC_MIN_MARGIN = 0.04

# EXPERIMENT, not shipped (eval/routing/REPORT.md step 4). When True,
# Sentence-BERT ranks the intents first and the keyword rules only act as a
# tiebreaker (thin margin) or as the fallback (low confidence / model
# offline). Off by default: the shipped order is keyword rules first, then
# semantic. Set LAM_SEMANTIC_FIRST=1 in the environment to switch it on.
SEMANTIC_FIRST = os.environ.get("LAM_SEMANTIC_FIRST", "").strip().lower() in {"1", "true", "yes", "on"}

_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_DEFAULT_ROUTABLE_INTENT = IntentLabel.RECOVERY_PROGRESS


# ============================================================================
# ROUTABLE INTENTS
# ============================================================================

ROUTABLE_INTENTS = (
    IntentLabel.RECOVERY_PROGRESS,
    IntentLabel.PAIN_SYMPTOMS,
    IntentLabel.REHABILITATION,
    IntentLabel.MEDICATION,
    IntentLabel.WOUND_CARE,
    IntentLabel.DAILY_ACTIVITY,
    IntentLabel.NUTRITION,
    IntentLabel.MENTAL_WELLBEING,
    IntentLabel.INTAKE_CONTEXT,
)


# ============================================================================
# SEMANTIC PROTOTYPES
# ============================================================================

_PROTOTYPE_SENTENCES = {

    IntentLabel.RECOVERY_PROGRESS: [
        "When will I reach recovery milestones after my surgery?",
        "What is the expected recovery timeline for my procedure?",
        "When can I expect to return to normal activities?",
        "How is my healing progressing so far?",
        "Is my recovery on track for this stage after surgery?",
        "How long before I can move around like I used to?",
        "Am I recovering normally?",
        "Is my recovery going well?",
    ],

    IntentLabel.PAIN_SYMPTOMS: [
        "I am experiencing pain in the operated area.",
        "My joint feels swollen and tender.",
        "I have stiffness and numbness in my leg.",
        "There is tingling and throbbing pain near the incision.",
        "The pain has become sharper and more intense today.",
        "My joint seems more inflamed than yesterday and it is painful.",
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

    # IMPORTANT:
    # Intake examples are about PROVIDING information, not asking
    # a clinical question.
    IntentLabel.INTAKE_CONTEXT: [
        "I want to provide my baseline information.",
        "Let's set up my recovery profile.",
        "Here are my surgery details and history.",
        "I need to complete the initial intake.",
        "I am checking in for the first time.",
        "Here is my medical background.",
        "My name is John and I want to provide my details.",
        "Hi, I am a new patient.",
        "I want to give my patient information.",
        "I want to register my postoperative information.",
        "I need to tell you about my surgery.",
        "I want to provide information about my operation.",
        "I am John and I had knee surgery two days ago.",
        "My name is John and my surgery was two days ago.",
        "I had knee surgery two days ago.",
        "I had a knee replacement yesterday.",
        "My surgery was yesterday and I am providing my details.",
    ],
}


# ============================================================================
# INTAKE / INTRODUCTION DETECTION
# ============================================================================

# Simple greetings.
_GREETING_PATTERNS = [
    r"^\s*hi\s*[!.]?\s*$",
    r"^\s*hello\s*[!.]?\s*$",
    r"^\s*hey\s*[!.]?\s*$",
    r"^\s*good morning\s*[!.]?\s*$",
    r"^\s*good afternoon\s*[!.]?\s*$",
    r"^\s*good evening\s*[!.]?\s*$",
]


# Introduction anywhere in the message.
# The old classifier incorrectly required the introduction to be
# the ENTIRE message.
_INTRODUCTION_PATTERNS = [
    r"\bmy name is\s+[a-z][a-z\s'-]{1,40}",
]

# "I am X" / "I'm X" on its own is NOT an introduction any more: "I am
# feeling okay today", "I'm walking with a walker now" and "I am anxious
# about my visit" all start that way (eval/routing/REPORT.md). Such a message
# is intake only when it also carries one of the cues in _has_intake_cue().

# A greeting at the START of a longer message ("Hi, I am Rishi").
_LEADING_GREETING_PATTERN = (
    r"^\s*(?:hi|hello|hey|namaste|good morning|good afternoon|good evening)\b"
)

# A capitalised word right after "I am" / "I'm" in the ORIGINAL (un-lowercased)
# message reads as a name: "I am Rishi", "I'm Anjali Nair". Common
# sentence-initial capitalisations that are not names are excluded.
_NAME_AFTER_PRONOUN_PATTERN = re.compile(
    r"\bI(?:\s+am|'m)\s+([A-Z][a-z]+)\b"
)
_NOT_A_NAME = {
    "ok", "okay", "fine", "good", "not", "feeling", "having", "done", "back",
    "still", "very", "also", "able", "so", "now", "on", "in", "at", "a", "an",
    "the", "just", "really", "worried", "scared", "anxious", "afraid", "tired",
    "sure", "sorry", "here", "new", "from", "day", "getting", "going", "doing",
    "taking", "walking", "trying", "unable", "already", "almost", "always",
}


# Explicit intake language.
_INTAKE_PATTERNS = [
    r"\bnew patient\b",
    r"\bfirst time\b",
    r"\bfirst visit\b",
    r"\bregister\b",
    r"\bregistration\b",
    r"\bonboard\b",
    r"\bonboarding\b",
    r"\bcheck[- ]?in\b",
    r"\binitial intake\b",
    r"\bpatient intake\b",
    r"\bcomplete my intake\b",
    r"\bmy details\b",
    r"\bmy information\b",
    r"\bpatient information\b",
    r"\bprovide my details\b",
    r"\bprovide my information\b",
    r"\bprovide my history\b",
    r"\bmedical history\b",
    r"\bmedical background\b",
    r"\bbaseline information\b",
    r"\brecovery profile\b",
    r"\bsurgery details\b",
    r"\boperation details\b",
    r"\bsurgery date\b",
    r"\bdate of surgery\b",
    r"\bwhen was my surgery\b",
    r"\bmy surgery was\b",
    r"\bmy operation was\b",
    r"\bi had .* surgery\b",
    r"\bi had (?:a |an |my )?(?:\w+ ){0,3}(?:replacement|arthroplasty|operation)\b",
    r"\bi underwent\b",
]


# ============================================================================
# KEYWORDS
# ============================================================================

_MEDICATION_KEYWORDS = {
    "medication",
    "medications",
    "medicine",
    "medicines",
    "drug",
    "drugs",
    "pill",
    "pills",
    "tablet",
    "tablets",
    "dose",
    "dosage",
    "paracetamol",
    "ibuprofen",
    "opioid",
    "painkiller",
    "aspirin",
    "anticoagulant",
    "anticoagulants",
    "anticaogulant",
    "anticaogulants",
    "blood thinner",
    "warfarin",
    "rivaroxaban",
    "antibiotic",
    "prescription",
    "missed dose",
    "side effect",
    "purpose",
    "precaution",
}
# "safe", "safety", "schedule", "timing" and "warning" used to be in this
# list. On their own they are not about medication ("Is it safe to climb
# stairs?", "What is the schedule for my exercises?") and, because the
# medication rule is checked first, they stole those turns from Daily
# Activity, Rehabilitation and Recovery (eval/routing/REPORT.md). A message
# that pairs them with a drug word still matches through the drug word.


def _contains_word(text: str, marker: str) -> bool:
    """Whole-word / whole-phrase match (no substring hits such as "no" in
    "nothing", "ok" in "took" or "pill" in "pillow")."""
    return re.search(r"\b" + re.escape(marker) + r"\b", text) is not None


def _looks_like_medication_follow_up(
    text: str,
    chat_history: list[dict[str, str]],
) -> bool:
    """Identify medication follow-ups whose current turn uses pronouns."""
    medication_context = (
        "medication", "medications", "medicine", "medicines", "dose", "doses",
        "dosage", "tablet", "tablets", "pill", "pills",
        "paracetamol", "enoxaparin", "aspirin", "antibiotic", "antibiotics",
        "painkiller", "painkillers", "blood thinner", "prescription",
    )
    follow_up = (
        "take it", "taking it", "took it", "next dose", "dose", "doses", "dosage",
        "how often", "when should i take", "when do i take",
        "timing", "schedule", "what time",
        "hours late", "hour late", "pain level", "pain is",
        "yes", "yeah", "yep", "no", "nope", "okay", "ok",
    )
    history_text = " ".join(
        str(turn.get("content", "")).lower()
        for turn in chat_history
        if isinstance(turn, dict)
    )
    return (
        any(_contains_word(text, marker) for marker in follow_up)
        and any(_contains_word(history_text, marker) for marker in medication_context)
    )


def _matches_recorded_medication(text: str, medication_names: list[str]) -> bool:
    return any(
        name and re.search(r"\b" + re.escape(name.lower()) + r"\b", text)
        for name in medication_names
    )


_PAIN_KEYWORDS = {
    "pain",
    "hurt",
    "hurts",
    "hurting",
    "ache",
    "aching",
    "sore",
    "soreness",
    "sharp pain",
    "burning pain",
    "swelling",
    "swollen",
    "puffiness",
    "tender",
    "tenderness",
    "numb",
    "numbness",
    "tingling",
    "stiffness",
    "stiff",
    "throbbing",
}


_WOUND_KEYWORDS = {
    "wound",
    "incision",
    "scar",
    "stitches",
    "staples",
    "suture",
    "drainage",
    "draining",
    "leaking",
    "discharge",
    "bandage",
    "dressing",
    "redness around wound",
    "pus",
    "yellow fluid",
    "wound care",
    "clean wound",
}


_REHAB_KEYWORDS = {
    "exercise",
    "exercises",
    "physical therapy",
    "physio",
    "physiotherapy",
    "heel slide",
    "heel slides",
    "rehab",
    "rehabilitation",
    "stretch",
    "stretching",
    "range of motion",
    "rom",
    "flexion",
    "extension",
    "bend",
    "straighten",
    "quad set",
    "heel slide",
    "leg raise",
    "ankle pump",
    "crutches",
    "walker",
    "walking aid",
    "weight bearing",
    "mobility",
    "strength",
    "strengthening",
}


_DAILY_ACTIVITY_KEYWORDS = {
    "stairs",
    "stair",
    "shower",
    "showering",
    "bath",
    "bathing",
    "sleep",
    "sleeping",
    "sleep position",
    "sleeping position",
    "drive",
    "driving",
    "bed",
    "chair",
    "sitting",
    "sit",
    "stand",
    "standing",
    "toilet",
    "bathroom",
    "walking around",
    "daily activity",
    "daily activities",
    "activities",
    "chores",
    "housework",
    "transfer",
    "getting out of bed",
}


_NUTRITION_KEYWORDS = {
    "eat",
    "eating",
    "diet",
    "food",
    "foods",
    "nutrition",
    "nutritional",
    "protein",
    "calories",
    "vitamin",
    "supplement",
    "hydration",
    "water",
    "drink",
    "drinking",
    "alcohol",
    "constipation",
    "bowel",
    "appetite",
}


_MENTAL_KEYWORDS = {
    "anxious",
    "anxiety",
    "depressed",
    "depression",
    "worried",
    "worry",
    "scared",
    "fear",
    "frustrated",
    "mental health",
    "mood",
    "emotional",
    "stress",
    "stressed",
    "overwhelmed",
    "sad",
    "hopeless",
    "lonely",
}


_RECOVERY_KEYWORDS = {
    "recovery",
    "healing",
    "progress",
    "how am i doing",
    "milestones",
    "timeline",
    "postop day",
    "post-op day",
    "weeks",
    "going home",
    "return to work",
    "getting better",
    "improve",
    "improvement",
}


# ============================================================================
# DETERMINISTIC RULES
# ============================================================================

# Clinical question intents come before generic intake words.
#
# Why?
#
# "I had knee surgery 2 days ago and my knee hurts"
#
# contains surgery/introduction language AND a symptom.
# That should be PAIN_SYMPTOMS.
#
# But:
#
# "I had knee surgery 2 days ago"
#
# has no actual clinical question/symptom and should be INTAKE_CONTEXT.
_DETERMINISTIC_RULES = [
    (IntentLabel.MEDICATION, _MEDICATION_KEYWORDS),
    (IntentLabel.PAIN_SYMPTOMS, _PAIN_KEYWORDS),
    (IntentLabel.WOUND_CARE, _WOUND_KEYWORDS),
    (IntentLabel.REHABILITATION, _REHAB_KEYWORDS),
    (IntentLabel.DAILY_ACTIVITY, _DAILY_ACTIVITY_KEYWORDS),
    (IntentLabel.NUTRITION, _NUTRITION_KEYWORDS),
    (IntentLabel.MENTAL_WELLBEING, _MENTAL_KEYWORDS),
    (IntentLabel.RECOVERY_PROGRESS, _RECOVERY_KEYWORDS),
]


# ============================================================================
# MODEL STATE
# ============================================================================

_model = None
_np = None

_model_load_attempted = False
_model_available = False

_prototype_embeddings = None


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def _normalise_query(query: str) -> str:
    if not query:
        return ""

    text = str(query).lower().strip()
    text = text.replace("’", "'")
    text = re.sub(r"\s+", " ", text)

    return text


def _has_question_signal(text: str) -> bool:
    """
    Detect whether the user is actually asking for clinical guidance.

    This prevents patient-information statements from being interpreted
    as recovery questions.
    """

    if "?" in text:
        return True

    question_patterns = [
        r"\bhow\b",
        r"\bwhen\b",
        r"\bwhat\b",
        r"\bwhy\b",
        r"\bcan i\b",
        r"\bshould i\b",
        r"\bis it\b",
        r"\bam i\b",
        r"\bwill i\b",
        r"\bdo i\b",
        r"\bcan\b",
        r"\bshould\b",
    ]

    return any(re.search(pattern, text) for pattern in question_patterns)


def _has_clinical_symptom_signal(text: str) -> bool:
    """
    True when the message contains a symptom that should override
    generic introduction/intake language.
    """

    symptom_sets = (
        _PAIN_KEYWORDS,
        _WOUND_KEYWORDS,
        _MEDICATION_KEYWORDS,
        _MENTAL_KEYWORDS,
    )

    for keywords in symptom_sets:
        for keyword in keywords:
            if re.search(r"\b" + re.escape(keyword) + r"\b", text):
                return True

    return False


def _is_simple_greeting(text: str) -> bool:
    for pattern in _GREETING_PATTERNS:
        if re.search(pattern, text):
            return True

    return False


def _has_intake_cue(text: str, raw_text: Optional[str] = None) -> bool:
    """
    True when the message carries something that marks it as onboarding /
    identity information rather than a clinical statement that merely
    starts with "I am": a greeting, "my name is", one of the explicit
    intake phrases, or a capitalised name right after "I am" / "I'm" in
    the original message.
    """

    if not text:
        return False

    if _is_simple_greeting(text):
        return True

    if re.search(_LEADING_GREETING_PATTERN, text):
        return True

    for pattern in _INTRODUCTION_PATTERNS:
        if re.search(pattern, text):
            return True

    for pattern in _INTAKE_PATTERNS:
        if re.search(pattern, text):
            return True

    if raw_text:
        match = _NAME_AFTER_PRONOUN_PATTERN.search(str(raw_text).replace("’", "'"))
        if match and match.group(1).lower() not in _NOT_A_NAME:
            return True

    return False


def _is_introduction(text: str, raw_text: Optional[str] = None) -> bool:
    """
    Detect patient introductions and profile/surgery information.

    Important:
    The introduction does NOT have to be the whole message.

    Examples:
        "Hi, I am Rishi"
        "I am Rishi and I had knee surgery 2 days ago"
        "My name is John. My surgery was yesterday."

    "I am <something>" alone is not enough; the message needs an intake cue
    (greeting, "my name is", an intake phrase, or a capitalised name).
    """

    if not text:
        return False

    return _has_intake_cue(text, raw_text)


def _looks_like_intake_statement(text: str, raw_text: Optional[str] = None) -> bool:
    """
    Determine whether the message is primarily patient onboarding/context.

    Intake wins when the user is supplying identity/surgery information
    without asking an actual clinical question and without reporting
    a clinical symptom.
    """

    if not text:
        return False

    if _is_simple_greeting(text):
        return True

    has_intro = _is_introduction(text, raw_text)

    if not has_intro:
        return False

    has_question = _has_question_signal(text)
    has_symptom = _has_clinical_symptom_signal(text)

    # A clinical symptom or actual question overrides generic intake.
    if has_symptom or has_question:
        return False

    return True


# ============================================================================
# DETERMINISTIC CLASSIFICATION
# ============================================================================

def _deterministic_intent(query: str) -> Optional[IntentLabel]:

    text = _normalise_query(query)

    if not text:
        return None

    # ------------------------------------------------------------
    # STEP 1
    # Pure greeting / patient introduction / context
    # ------------------------------------------------------------

    if _looks_like_intake_statement(text, query):
        return IntentLabel.INTAKE_CONTEXT

    # ------------------------------------------------------------
    # STEP 2
    # Strong clinical intent
    # ------------------------------------------------------------

    for intent, keywords in _DETERMINISTIC_RULES:

        for keyword in keywords:

            if re.search(r"\b" + re.escape(keyword) + r"\b", text):
                return intent

    return None


# ============================================================================
# SENTENCE-BERT MODEL
# ============================================================================

def _load_model() -> bool:

    global _model
    global _np
    global _model_load_attempted
    global _model_available

    if _model_load_attempted:
        return _model_available

    _model_load_attempted = True

    try:

        import numpy as np
        from sentence_transformers import SentenceTransformer

        _np = np
        _model = SentenceTransformer(_MODEL_NAME)

        _model_available = True

    except Exception as exc:

        print(f"[LAM] Sentence-BERT unavailable: {exc}")

        _model = None
        _np = None
        _model_available = False

    return _model_available


def _get_prototype_embeddings():

    global _prototype_embeddings

    if _prototype_embeddings is not None:
        return _prototype_embeddings

    if not _load_model():
        return None

    try:

        sentences = []
        owners = []

        for intent in ROUTABLE_INTENTS:

            for sentence in _PROTOTYPE_SENTENCES[intent]:

                sentences.append(sentence)
                owners.append(intent)

        embeddings = _model.encode(
            sentences,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        by_intent = {}

        for intent, sentence, embedding in zip(
            owners,
            sentences,
            embeddings,
        ):

            if intent not in by_intent:
                by_intent[intent] = []

            by_intent[intent].append(
                (sentence, embedding)
            )

        _prototype_embeddings = by_intent

        return _prototype_embeddings

    except Exception as exc:

        print(f"[LAM] Prototype embedding failure: {exc}")

        _prototype_embeddings = None

        return None


def _semantic_scores(
    query: str,
) -> Optional[dict[IntentLabel, tuple[float, str]]]:

    prototypes = _get_prototype_embeddings()

    if prototypes is None:
        return None

    try:

        query_embedding = _model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )[0]

    except Exception as exc:

        print(f"[LAM] Query embedding failure: {exc}")

        return None

    scores = {}

    for intent, entries in prototypes.items():

        best_score = float("-inf")
        best_sentence = ""

        for sentence, embedding in entries:

            similarity = float(
                _np.dot(
                    query_embedding,
                    embedding,
                )
            )

            if similarity > best_score:

                best_score = similarity
                best_sentence = sentence

        scores[intent] = (
            best_score,
            best_sentence,
        )

    return scores


# ============================================================================
# DIAGNOSTICS
# ============================================================================

@dataclass
class ClassificationDetail:

    intent: IntentLabel

    top1_intent: Optional[IntentLabel]
    top1_score: float

    top2_intent: Optional[IntentLabel]
    top2_score: float

    margin: float

    matched_prototype: Optional[str]

    decision_path: str


# ============================================================================
# INTENT CLASSIFIER
# ============================================================================

class IntentClassifier:

    @classmethod
    def detect_applicable_intents(
        cls,
        query: str,
        context: LAMContext,
    ) -> tuple[IntentLabel, ...]:
        """
        Detect every domain explicitly present in one turn.

        This is deliberately deterministic and keyword-based.  The normal
        classifier remains the source of truth for single-domain semantic
        routing, while this method prevents a combined clinical statement
        from being reduced to its first matching intent.
        """
        text = _normalise_query(query)
        detected: list[IntentLabel] = []

        if _matches_recorded_medication(text, context.medication_names) or (
            context.chat_history and _looks_like_medication_follow_up(
                text, context.chat_history
            )
        ):
            detected.append(IntentLabel.MEDICATION)

        for intent, keywords in _DETERMINISTIC_RULES:
            if intent in detected:
                continue
            matches = [
                keyword for keyword in keywords
                if re.search(r"\b" + re.escape(keyword) + r"\b", text)
            ]
            # "pain tablet/medicine/pill" identifies the medication, not a
            # second pain-assessment request.  Retain pain when the turn also
            # contains an independent symptom (for example "pain is worse").
            if (
                intent == IntentLabel.PAIN_SYMPTOMS
                and IntentLabel.MEDICATION in detected
                and matches
                and all(keyword in {"pain", "hurt", "hurts", "sore", "soreness"}
                        for keyword in matches)
                and all(
                    re.search(
                        r"\b" + re.escape(keyword)
                        + r"\s+(?:tablet|tablets|pill|pills|medicine|medication|killer)\b",
                        text,
                    )
                    for keyword in matches
                )
            ):
                matches = []
            if matches:
                detected.append(intent)

        # Active wound follow-ups can be terse, so retain wound ownership.
        if (
            context.chat_history
            and any(
                marker in " ".join(
                    str(turn.get("content", "")).lower()
                    for turn in context.chat_history
                    if isinstance(turn, dict)
                )
                for marker in ("wound care", "wound", "incision", "drainage")
            )
            and not any(intent == IntentLabel.WOUND_CARE for intent in detected)
            and len(text.split()) <= 8
        ):
            detected.append(IntentLabel.WOUND_CARE)

        if not detected:
            detected.append(cls.classify(query, context))

        return tuple(detected)

    @classmethod
    def classify(
        cls,
        query: str,
        context: LAMContext,
    ) -> IntentLabel:

        result = cls.classify_detailed(
            query,
            context,
        )

        return result.intent

    @classmethod
    def classify_detailed(
        cls,
        query: str,
        context: LAMContext,
    ) -> ClassificationDetail:

        text = _normalise_query(query)

        if _matches_recorded_medication(text, context.medication_names):
            return ClassificationDetail(
                intent=IntentLabel.MEDICATION,
                top1_intent=IntentLabel.MEDICATION,
                top1_score=1.0,
                top2_intent=None,
                top2_score=0.0,
                margin=1.0,
                matched_prototype=None,
                decision_path="deterministic_patient_record",
            )

        # Short follow-ups often omit the medication noun ("when should I
        # take it?"). Preserve the medication route when the conversation
        # already established medication context.
        if (
            context.chat_history
            and _looks_like_medication_follow_up(text, context.chat_history)
        ):
            return ClassificationDetail(
                intent=IntentLabel.MEDICATION,
                top1_intent=IntentLabel.MEDICATION,
                top1_score=1.0,
                top2_intent=None,
                top2_score=0.0,
                margin=1.0,
                matched_prototype=None,
                decision_path="deterministic_context",
            )

        if SEMANTIC_FIRST:
            return cls._classify_semantic_first(query, text)

        # ============================================================
        # STEP 1
        # Deterministic classification
        # ============================================================

        # The raw query goes along so the intake check can see the original
        # capitalisation ("I am Rishi" vs "I am fine").
        deterministic = _deterministic_intent(query)

        if deterministic is not None:

            return ClassificationDetail(
                intent=deterministic,
                top1_intent=deterministic,
                top1_score=1.0,
                top2_intent=None,
                top2_score=0.0,
                margin=1.0,
                matched_prototype=None,
                decision_path="deterministic",
            )

        # ============================================================
        # STEP 2
        # Semantic classification
        # ============================================================

        scores = _semantic_scores(text)

        if scores is None:

            fallback = cls._classify_by_keywords(query)

            return ClassificationDetail(
                intent=fallback,
                top1_intent=None,
                top1_score=0.0,
                top2_intent=None,
                top2_score=0.0,
                margin=0.0,
                matched_prototype=None,
                decision_path="fallback_offline",
            )

        # The intake prototypes ("I had a knee replacement yesterday.", "I
        # need to tell you about my surgery.") sit close to ANY sentence that
        # mentions the knee or the surgery, so "Am I on track with my knee?"
        # and "Which exercises should I do today for my knee?" used to win as
        # INTAKE_CONTEXT semantically (eval/routing/REPORT.md). Intake is an
        # onboarding statement, which the deterministic step already
        # recognises by its cues; without such a cue the semantic ranking
        # does not get to pick intake, and the next-best intent competes
        # against the usual thresholds instead.
        if (
            IntentLabel.INTAKE_CONTEXT in scores
            and not _has_intake_cue(text, query)
        ):
            scores = {
                intent: value
                for intent, value in scores.items()
                if intent != IntentLabel.INTAKE_CONTEXT
            }

        ranked = sorted(
            scores.items(),
            key=lambda item: item[1][0],
            reverse=True,
        )

        top1_intent = ranked[0][0]
        top1_score = ranked[0][1][0]
        top1_prototype = ranked[0][1][1]

        if len(ranked) > 1:

            top2_intent = ranked[1][0]
            top2_score = ranked[1][1][0]

        else:

            top2_intent = None
            top2_score = 0.0

        margin = top1_score - top2_score

        # ============================================================
        # STEP 3
        # Low confidence -> deterministic fallback
        # ============================================================

        if top1_score < SEMANTIC_MIN_SCORE:

            fallback = cls._classify_by_keywords(query)

            return ClassificationDetail(
                intent=fallback,
                top1_intent=top1_intent,
                top1_score=top1_score,
                top2_intent=top2_intent,
                top2_score=top2_score,
                margin=margin,
                matched_prototype=top1_prototype,
                decision_path="fallback_low_confidence",
            )

        # ============================================================
        # STEP 4
        # Low semantic margin -> deterministic fallback
        # ============================================================

        if margin < SEMANTIC_MIN_MARGIN:

            fallback = cls._classify_by_keywords(query)

            return ClassificationDetail(
                intent=fallback,
                top1_intent=top1_intent,
                top1_score=top1_score,
                top2_intent=top2_intent,
                top2_score=top2_score,
                margin=margin,
                matched_prototype=top1_prototype,
                decision_path="fallback_low_margin",
            )

        # ============================================================
        # STEP 5
        # Trusted semantic result
        # ============================================================

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

    # ========================================================================
    # EXPERIMENT: SEMANTIC FIRST, KEYWORDS AS TIEBREAKER (SEMANTIC_FIRST)
    # ========================================================================

    @classmethod
    def _classify_semantic_first(
        cls,
        query: str,
        text: str,
    ) -> ClassificationDetail:
        """
        Order used only when SEMANTIC_FIRST is True:

          1. Sentence-BERT scores (with the same intake-cue gate as the
             shipped path).
          2. Confident and clear (score >= SEMANTIC_MIN_SCORE, margin >=
             SEMANTIC_MIN_MARGIN) -> the semantic winner.
          3. Confident but thin margin -> the keyword rules break the tie
             between the top two; a keyword hit outside the top two wins
             over both (it is the stronger evidence); no keyword at all ->
             keep the semantic winner.
          4. Low confidence or model offline -> the keyword rules, then the
             default routable intent (exactly the shipped fallback).
        """

        def _detail(intent, path, ranked=None):
            if ranked:
                top1_intent, (top1_score, top1_prototype) = ranked[0]
                top2_intent, top2_score = (ranked[1][0], ranked[1][1][0]) if len(ranked) > 1 else (None, 0.0)
                return ClassificationDetail(
                    intent=intent, top1_intent=top1_intent, top1_score=top1_score,
                    top2_intent=top2_intent, top2_score=top2_score,
                    margin=top1_score - top2_score, matched_prototype=top1_prototype,
                    decision_path=path,
                )
            return ClassificationDetail(
                intent=intent, top1_intent=None, top1_score=0.0, top2_intent=None,
                top2_score=0.0, margin=0.0, matched_prototype=None, decision_path=path,
            )

        scores = _semantic_scores(text)

        if scores is None:
            return _detail(cls._classify_by_keywords(query), "fallback_offline")

        if (
            IntentLabel.INTAKE_CONTEXT in scores
            and not _has_intake_cue(text, query)
        ):
            scores = {
                intent: value for intent, value in scores.items()
                if intent != IntentLabel.INTAKE_CONTEXT
            }

        ranked = sorted(scores.items(), key=lambda item: item[1][0], reverse=True)
        top1_intent, top1_score = ranked[0][0], ranked[0][1][0]
        top2_intent = ranked[1][0] if len(ranked) > 1 else None
        top2_score = ranked[1][1][0] if len(ranked) > 1 else 0.0
        margin = top1_score - top2_score

        if top1_score >= SEMANTIC_MIN_SCORE and margin >= SEMANTIC_MIN_MARGIN:
            return _detail(top1_intent, "semantic_first", ranked)

        deterministic = _deterministic_intent(query)

        if top1_score >= SEMANTIC_MIN_SCORE:
            # Thin margin: let the keyword rules break the tie.
            if deterministic in (top1_intent, top2_intent):
                return _detail(deterministic, "semfirst_tiebreak_keywords", ranked)
            if deterministic is not None:
                return _detail(deterministic, "semfirst_tiebreak_deterministic", ranked)
            return _detail(top1_intent, "semfirst_tiebreak_top1", ranked)

        # Low confidence: keyword rules, then the default.
        return _detail(cls._classify_by_keywords(query), "semfirst_low_confidence", ranked)

    # ========================================================================
    # KEYWORD FALLBACK
    # ========================================================================

    @classmethod
    def _classify_by_keywords(
        cls,
        query: str,
    ) -> IntentLabel:

        text = _normalise_query(query)

        if not text:
            return _DEFAULT_ROUTABLE_INTENT

        # Intake first only when it is actually an intake statement.
        if _looks_like_intake_statement(text, query):
            return IntentLabel.INTAKE_CONTEXT

        # Clinical intents.
        for intent, keywords in _DETERMINISTIC_RULES:

            for keyword in keywords:

                if re.search(r"\b" + re.escape(keyword) + r"\b", text):
                    return intent

        return _DEFAULT_ROUTABLE_INTENT