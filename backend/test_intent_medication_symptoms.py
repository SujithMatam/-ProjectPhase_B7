"""
Medication side-effect words need a medication cue.

Main added side-effect descriptors (itching, bloated, dizzy, nausea, ...) to
the MEDICATION keywords. The medication rule is checked first, so on their
own these words took wound, nutrition, pain and daily-activity turns. They
now count for MEDICATION only when the message also carries a medication
cue (tablet, pill, medicine, dose, painkiller, a drug name, "since I
started", "side effect", ...). Both directions are tested here.

    .venv/Scripts/python.exe -m pytest test_intent_medication_symptoms.py -q
"""

from __future__ import annotations

import pytest

import lam.intent_classifier as ic
from lam.intent_classifier import IntentClassifier, _deterministic_intent
from lam.schemas import IntentLabel, LAMContext

MED = IntentLabel.MEDICATION
SYMPTOM_WORDS = sorted(ic._MEDICATION_SYMPTOM_KEYWORDS)


def _ctx(message: str) -> LAMContext:
    return LAMContext(
        patient_id="MED-SYMPTOM-TEST",
        surgery_type="Total Knee Arthroplasty (TKA)",
        affected_limb="Right",
        postop_day=5,
        user_message=message,
    )


# ---------------------------------------------------------------------------
# The words are kept
# ---------------------------------------------------------------------------

def test_symptom_words_stay_in_medication_keywords():
    assert ic._MEDICATION_SYMPTOM_KEYWORDS <= ic._MEDICATION_KEYWORDS
    for word in ("itching", "itchy", "bloated", "dizzy", "nausea", "nauseous",
                 "drowsy", "constipated", "light-headed", "queasy", "fatigued"):
        assert word in ic._MEDICATION_SYMPTOM_KEYWORDS


def test_symptom_words_still_override_intake():
    # They still count as a clinical symptom, so an introduction that
    # reports one is not treated as plain intake.
    assert ic._has_clinical_symptom_signal("hi, i am rishi and i feel dizzy")
    assert _deterministic_intent("Hi, I am Rishi and I feel dizzy") != IntentLabel.INTAKE_CONTEXT


# ---------------------------------------------------------------------------
# With a medication cue -> MEDICATION
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("word", SYMPTOM_WORDS)
def test_every_symptom_word_with_a_cue_is_medication(word):
    message = f"I have been {word} since the new tablets"
    assert _deterministic_intent(message) == MED


@pytest.mark.parametrize("message", [
    "I feel dizzy after my tablet",
    "Feeling dizzy after the pill",
    "Dizzy after the medicine this morning",
    "I get dizzy after every dose",
    "I feel dizzy after my painkiller",
    "I feel dizzy on tramadol",
    "Dizzy since I started the new course",
    "Is dizziness a side effect?",
    "Itching all over since the new tablets started",
    "Tummy feels bloated ever since I began these pills",
    "The blood thinner makes me light headed",
    "Nausea after the antibiotic, is that normal?",
    "Queasy in the mornings after my meds",
])
def test_each_cue_routes_symptom_to_medication(message):
    assert _deterministic_intent(message) == MED
    assert IntentClassifier.classify(message, _ctx(message)) == MED
    assert MED in IntentClassifier.detect_applicable_intents(message, _ctx(message))


# ---------------------------------------------------------------------------
# Without a medication cue -> NOT medication; the next rules decide
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("word", SYMPTOM_WORDS)
def test_symptom_word_alone_is_not_a_medication_keyword_hit(word):
    text = f"i feel {word} today"
    assert ic._rule_keyword_matches(MED, ic._MEDICATION_KEYWORDS, text) == []
    assert _deterministic_intent(text) != MED


@pytest.mark.parametrize("message, expected", [
    ("My incision is itching alot, is it normal?", IntentLabel.WOUND_CARE),
    ("The skin along my incision line is very itchy", IntentLabel.WOUND_CARE),
    ("I feel bloated after meals, any diet advice?", IntentLabel.NUTRITION),
    ("Constipated since the operation, which foods will help?", IntentLabel.NUTRITION),
])
def test_symptom_without_cue_goes_to_the_next_rule(message, expected):
    assert _deterministic_intent(message) == expected
    assert IntentClassifier.classify(message, _ctx(message)) == expected
    assert MED not in IntentClassifier.detect_applicable_intents(message, _ctx(message))


@pytest.mark.parametrize("message", [
    "I get dizzy when I stand up after physio",
    "Feeling light-headed when I get out of bed in the morning",
    "Very fatigued after walking to the gate and back",
    "So drowsy in the afternoons these days",
    "Feeling queasy and dizzy this evening",
])
def test_symptom_without_cue_is_never_medication(message):
    assert IntentClassifier.classify(message, _ctx(message)) != MED
    assert MED not in IntentClassifier.detect_applicable_intents(message, _ctx(message))


def test_non_symptom_medication_keywords_are_not_gated():
    # Only the side-effect words need a cue; a drug word is a cue by itself.
    assert _deterministic_intent("Can I take paracetamol now?") == MED
    assert _deterministic_intent("What is the purpose of this?") == MED  # unchanged teammate keyword
