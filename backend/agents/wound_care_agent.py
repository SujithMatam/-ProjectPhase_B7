"""
Wound Care Agent.

Conversational postoperative wound/incision assessment.

Flow:

    Patient concern
        ↓
    Acknowledge
        ↓
    Ask focused wound question
        ↓
    Patient answers
        ↓
    Reconstruct assessment from conversation history
        ↓
    Ask next relevant question
        ↓
    Enough wound information
        ↓
    Existing RAG + Qwen conclusion
        ↓
    Safe deterministic fallback if the generic LLM response is unhelpful

Safety:

    Emergency/red-flag classification is NEVER performed here.

    SafetyTriageEngine runs upstream in LAMOrchestrator on every turn.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from agents.base_clinical_agent import BaseClinicalAgent
from agents.chat_agent import ChatAgent
from lam.schemas import TargetAgent


# ============================================================================
# WOUND TERMS
# ============================================================================

_WOUND_TERMS = (
    "wound",
    "incision",
    "surgical cut",
    "scar",
    "stitch",
    "stitches",
    "suture",
    "sutures",
    "staple",
    "staples",
    "dressing",
    "bandage",
    "drainage",
    "draining",
    "discharge",
    "leaking",
    "leak",
    "pus",
    "fluid",
    "redness",
    "red",
    "warm",
    "warmer",
    "warmth",
    "hot",
    "swelling",
    "swollen",
    "separation",
    "opening",
    "opened",
    "gap",
    "gaping",
)


# ============================================================================
# OTHER DOMAINS
# ============================================================================

_OTHER_DOMAIN_TERMS = (
    "medication",
    "medicine",
    "tablet",
    "pill",
    "dose",
    "exercise",
    "exercises",
    "physio",
    "physiotherapy",
    "rehab",
    "rehabilitation",
    "stairs",
    "stair",
    "drive",
    "driving",
    "shower",
    "showering",
    "diet",
    "food",
    "nutrition",
    "protein",
    "sleeping position",
    "return to work",
)


# ============================================================================
# QUESTION BANK
# ============================================================================

_QUESTIONS: Dict[str, str] = {
    "onset": (
        "When did you first notice the change in the wound?"
    ),
    "progression": (
        "Since you first noticed it, has it been getting better, "
        "getting worse, or staying about the same?"
    ),
    "appearance": (
        "Please have a look at the skin around the incision. "
        "Does it look more red than usual, less red, or about the same?"
    ),
    "warmth": (
        "Does the area around the incision feel warmer than the "
        "surrounding skin, cooler, or about the same?"
    ),
    "drainage": (
        "Have you noticed any fluid coming from the incision? "
        "If so, what does it look like and roughly how much is there?"
    ),
    "separation": (
        "Does the incision still look closed, or do you notice "
        "any part of it opening or separating?"
    ),
    "pain": (
        "How does the area feel now? Is there pain or tenderness "
        "around the incision, and has that changed recently?"
    ),
    "fever": (
        "Have you checked your temperature, or have you felt "
        "feverish or unusually unwell?"
    ),
}


# ============================================================================
# SIMPLIFIED FOLLOW-UP QUESTIONS
#
# Used ONLY when the patient answered the normal question with something
# like "I don't know". Each one gives a concrete, easy way to check,
# instead of just repeating the same abstract question and getting the
# same "I don't know" again.
# ============================================================================

_ALT_QUESTIONS: Dict[str, str] = {
    "onset": (
        "No worries, even a rough idea is fine. Would you say it was "
        "today, yesterday, or a few days ago?"
    ),
    "progression": (
        "That's okay. Compared to when you first noticed it, does it "
        "feel any different now at all, or does it feel about the same?"
    ),
    "appearance": (
        "No problem. If you compare it to how it looked a day or two "
        "ago (or a photo if you have one), does it look any different "
        "at all, even slightly?"
    ),
    "warmth": (
        "That's fine, here's an easy way to check: gently touch the "
        "skin around the incision with the back of your hand, then "
        "touch the same spot on your other arm or leg. Does the "
        "incision area feel warmer, cooler, or about the same?"
    ),
    "drainage": (
        "No worries. Has your dressing, bandage, or clothing near the "
        "area gotten wet, stained, or needed changing more than usual?"
    ),
    "separation": (
        "That's okay. Can you tell if the two edges of the incision "
        "are still touching each other, or is there any gap or opening "
        "you can see or feel?"
    ),
    "pain": (
        "No problem, you don't need an exact number. On a scale of "
        "0 (no pain) to 10 (the worst pain you can imagine), roughly "
        "where would you put it right now?"
    ),
    "fever": (
        "That's fine. Even without a thermometer, have you felt "
        "unusually warm, chilly, sweaty, or generally unwell?"
    ),
}


# ============================================================================
# UNCERTAINTY DETECTION
# ============================================================================

_UNCERTAIN_PHRASES = (
    "i don't know",
    "i dont know",
    "idk",
    "don't know",
    "dont know",
    "not sure",
    "unsure",
    "no idea",
    "no clue",
    "can't tell",
    "cant tell",
    "hard to tell",
    "not certain",
    "not able to tell",
    "unable to tell",
)


def _is_uncertain_answer(text: str) -> bool:
    """
    True when the patient's answer expresses genuine uncertainty rather
    than an actual observation. This must NOT silently count as a normal
    answer -- see _extract_answer_pairs, which either re-asks an easier
    version of the question once, or (on a second uncertain answer)
    explicitly records the field as "unknown" rather than guessing.
    """

    normalised = _normalise(text)

    if not normalised:
        return False

    if normalised in ("dunno", "unknown", "not applicable", "n/a"):
        return True

    return any(
        phrase in normalised
        for phrase in _UNCERTAIN_PHRASES
    )


# ============================================================================
# NORMALISATION
# ============================================================================

def _normalise(text: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        (text or "").strip().lower(),
    )


# ============================================================================
# HISTORY
# ============================================================================

def _history_with_current_message(
    chat_history: Optional[List[Dict[str, str]]],
    current_message: str,
) -> List[Dict[str, str]]:

    history = list(chat_history or [])

    if current_message.strip():
        history.append(
            {
                "role": "user",
                "content": current_message.strip(),
            }
        )

    return history


# ============================================================================
# QUESTION IDENTIFICATION
# ============================================================================

def _alt_field_from_question(
    text: str,
) -> Optional[str]:
    """
    Identifies which field a SIMPLIFIED follow-up question (from
    _ALT_QUESTIONS) was about, using a short unique marker phrase from
    each one. Returns None if this isn't an alt question at all.
    """

    normalised = _normalise(text)

    markers: Dict[str, str] = {
        "onset": "even a rough idea is fine",
        "progression": "does it feel any different now at all",
        "appearance": "compare it to how it looked",
        "warmth": "back of your hand",
        "drainage": "gotten wet, stained",
        "separation": "edges of the incision",
        "pain": "0 (no pain) to 10",
        "fever": "unusually warm, chilly, sweaty",
    }

    for field, marker in markers.items():
        if marker in normalised:
            return field

    return None


def _primary_field_from_question(
    text: str,
) -> Optional[str]:

    normalised = _normalise(text)

    # Onset
    if (
        "when did you first notice" in normalised
        or "when did you notice" in normalised
        or "how long ago" in normalised
    ):
        return "onset"

    # Progression
    if (
        "getting better" in normalised
        or "getting worse" in normalised
        or "staying about the same" in normalised
    ):
        return "progression"

    # Appearance
    if (
        "more red than usual" in normalised
        or "less red" in normalised
        or (
            "around the incision" in normalised
            and "red" in normalised
        )
    ):
        return "appearance"

    # Warmth
    if (
        "feel warmer" in normalised
        or "warmer than the surrounding skin" in normalised
        or "feel hotter" in normalised
        or (
            "warm" in normalised
            and (
                "surrounding skin" in normalised
                or "area around the incision" in normalised
            )
        )
    ):
        return "warmth"

    # Drainage
    if (
        "fluid coming from" in normalised
        or "fluid from the incision" in normalised
        or "drainage" in normalised
    ):
        return "drainage"

    # Separation
    if (
        "incision still look closed" in normalised
        or "opening or separating" in normalised
        or "part of it opening" in normalised
        or "wound opening" in normalised
    ):
        return "separation"

    # Pain
    if (
        "pain or tenderness" in normalised
        or (
            "has that changed recently" in normalised
            and (
                "pain" in normalised
                or "tenderness" in normalised
            )
        )
    ):
        return "pain"

    # Fever
    if (
        "checked your temperature" in normalised
        or "felt feverish" in normalised
        or "unusually unwell" in normalised
    ):
        return "fever"

    return None


def _field_from_question(
    text: str,
) -> Optional[str]:
    """
    Which field is this assistant question about -- checking BOTH the
    normal question phrasing and the simplified alt phrasing. Used by
    helpers that only care "what topic was being asked", not whether it
    was the first or the simplified retry version.
    """

    alt_field = _alt_field_from_question(text)

    if alt_field:
        return alt_field

    return _primary_field_from_question(text)


def _previous_question_field(
    chat_history: Optional[List[Dict[str, str]]],
) -> Optional[str]:

    for item in reversed(chat_history or []):

        if not isinstance(item, dict):
            continue

        role = str(
            item.get("role", "")
        ).lower().strip()

        if role not in {"assistant", "bot"}:
            continue

        content = str(
            item.get("content", "")
        ).strip()

        if not content:
            continue

        field = _field_from_question(content)

        if field:
            return field

    return None


# ============================================================================
# ANSWER PAIR EXTRACTION
# ============================================================================

def _extract_answer_pairs(
    chat_history: Optional[List[Dict[str, str]]],
    current_message: str,
) -> Tuple[Dict[str, str], set]:
    """
    Returns (assessment, needs_alt).

    needs_alt is the set of fields where the patient answered "I don't
    know" (or similar) to the FIRST (normal-phrasing) question for that
    field. Those fields are deliberately left OUT of `assessment` here,
    so the caller knows to re-ask using the simpler _ALT_QUESTIONS
    version instead of accepting uncertainty as a real answer.

    If the patient is STILL uncertain after the alt (simplified)
    question, that field IS written into `assessment` as the literal
    string "unknown" -- explicit and visible, rather than silently
    treated as a normal/neutral answer.
    """

    history = _history_with_current_message(
        chat_history,
        current_message,
    )

    assessment: Dict[str, str] = {}
    needs_alt: set = set()

    pending_field: Optional[str] = None
    pending_is_alt: bool = False

    for item in history:

        if not isinstance(item, dict):
            continue

        role = str(
            item.get("role", "")
        ).lower().strip()

        content = str(
            item.get("content", "")
        ).strip()

        if not content:
            continue

        if role in {"assistant", "bot"}:

            alt_field = _alt_field_from_question(content)

            if alt_field:
                pending_field = alt_field
                pending_is_alt = True
            else:
                field = _primary_field_from_question(content)

                if field:
                    pending_field = field
                    pending_is_alt = False

            continue

        if role == "user" and pending_field:

            if _is_uncertain_answer(content):

                if pending_is_alt:
                    # Already asked the simpler version and STILL
                    # uncertain -- accept "unknown" explicitly rather
                    # than looping forever.
                    assessment[pending_field] = "unknown"
                    needs_alt.discard(pending_field)
                else:
                    # First time uncertain -- don't accept it as the
                    # answer. Flag for a simpler re-ask instead.
                    needs_alt.add(pending_field)

            else:
                assessment[pending_field] = content
                needs_alt.discard(pending_field)

            pending_field = None
            pending_is_alt = False

    return assessment, needs_alt


# ============================================================================
# DIRECT INFORMATION EXTRACTION
# ============================================================================

def _extract_direct_information(
    text: str,
) -> Dict[str, str]:

    normalised = _normalise(text)

    result: Dict[str, str] = {}

    # Pain
    if any(
        term in normalised
        for term in (
            "pain",
            "painful",
            "tender",
            "tenderness",
            "sore",
            "hurts",
            "hurt",
        )
    ):
        result["pain"] = text.strip()

    # Appearance
    if any(
        term in normalised
        for term in (
            "red",
            "redness",
            "less red",
            "more red",
            "bruising",
            "bruise",
        )
    ):
        result["appearance"] = text.strip()

    # Onset
    #
    # Do NOT treat "noticed" by itself as onset.
    # This prevents:
    #
    #     "I noticed less redness"
    #
    # from incorrectly becoming an onset answer.
    #
    if any(
        term in normalised
        for term in (
            "yesterday",
            "today",
            "this morning",
            "this afternoon",
            "this evening",
            "last night",
            "hours ago",
            "hour ago",
            "days ago",
            "day ago",
            "since yesterday",
            "since today",
            "started",
            "began",
        )
    ):
        result["onset"] = text.strip()

    # Progression
    if any(
        term in normalised
        for term in (
            "better",
            "worse",
            "getting better",
            "getting worse",
            "improving",
            "improved",
            "unchanged",
            "same",
            "about the same",
            "less red",
            "more red",
            "less warm",
            "more warm",
            "less swollen",
            "more swollen",
        )
    ):
        result["progression"] = text.strip()

    # Warmth
    if any(
        term in normalised
        for term in (
            "warm",
            "warmer",
            "warmth",
            "hot",
            "hotter",
            "less warm",
            "cooler",
            "less hot",
            "not warm",
        )
    ):
        result["warmth"] = text.strip()

    # Drainage
    if any(
        term in normalised
        for term in (
            "fluid",
            "drainage",
            "draining",
            "discharge",
            "leaking",
            "leak",
            "pus",
            "blood",
            "bleeding",
            "no fluid",
            "no drainage",
            "no discharge",
        )
    ):
        result["drainage"] = text.strip()

    # Separation
    if any(
        term in normalised
        for term in (
            "open",
            "opening",
            "opened",
            "separated",
            "separation",
            "gap",
            "gaping",
            "closed",
            "still closed",
        )
    ):
        result["separation"] = text.strip()

    # Fever
    if any(
        term in normalised
        for term in (
            "fever",
            "feverish",
            "temperature",
            "temp",
            "chills",
            "shivering",
            "unwell",
            "not feverish",
            "no fever",
        )
    ):
        result["fever"] = text.strip()

    return result


# ============================================================================
# COMPLETE ASSESSMENT
# ============================================================================

def _build_assessment(
    chat_history: Optional[List[Dict[str, str]]],
    current_message: str,
) -> Tuple[Dict[str, str], set]:
    """
    Returns (assessment, needs_alt) -- see _extract_answer_pairs for what
    needs_alt means.
    """

    history = _history_with_current_message(
        chat_history,
        current_message,
    )

    assessment: Dict[str, str] = {}

    # First collect direct information from every patient message.
    for item in history:

        if not isinstance(item, dict):
            continue

        role = str(
            item.get("role", "")
        ).lower().strip()

        if role != "user":
            continue

        content = str(
            item.get("content", "")
        ).strip()

        if not content:
            continue

        direct = _extract_direct_information(
            content
        )

        for field, value in direct.items():
            assessment[field] = value

    # Explicit question-answer pairs have priority.
    paired, needs_alt = _extract_answer_pairs(
        chat_history,
        current_message,
    )

    assessment.update(paired)

    # If the patient gave usable direct information for a field
    # elsewhere in the conversation, don't re-ask it just because they
    # separately said "I don't know" to the formal question about it.
    for field in list(needs_alt):
        if field in assessment:
            needs_alt.discard(field)

    return assessment, needs_alt


# ============================================================================
# WOUND CONVERSATION DETECTION
# ============================================================================

def _is_wound_conversation(
    user_message: str,
    chat_history: Optional[List[Dict[str, str]]],
) -> bool:

    current = _normalise(
        user_message
    )

    # Explicit wound terminology.
    if any(
        term in current
        for term in _WOUND_TERMS
    ):
        return True

    # Answer to an active wound question.
    if _previous_question_field(
        chat_history
    ):
        return True

    # Recent conversation is wound-focused.
    recent = (
        chat_history or []
    )[-10:]

    recent_text = " ".join(
        str(item.get("content", ""))
        for item in recent
        if isinstance(item, dict)
    )

    return any(
        term in _normalise(recent_text)
        for term in _WOUND_TERMS
    )


# ============================================================================
# TOPIC CHANGE
# ============================================================================

def _changed_to_other_topic(
    user_message: str,
) -> bool:

    text = _normalise(
        user_message
    )

    return any(
        term in text
        for term in _OTHER_DOMAIN_TERMS
    )


# ============================================================================
# INTERPRETATION HELPERS
# ============================================================================

def _is_improving(
    value: str,
) -> bool:

    text = _normalise(value)

    return any(
        term in text
        for term in (
            "better",
            "improving",
            "improved",
            "less red",
            "less redness",
            "less warm",
            "less swollen",
            "decreased",
            "decreasing",
            "smaller",
            "cooler",
        )
    )


def _is_worsening(
    value: str,
) -> bool:

    text = _normalise(value)

    return any(
        term in text
        for term in (
            "worse",
            "getting worse",
            "more red",
            "more redness",
            "warmer",
            "more warm",
            "hotter",
            "more swollen",
            "spreading",
            "increasing",
            "increased",
        )
    )


def _is_negative_answer(
    value: str,
) -> bool:

    text = _normalise(value)

    if text in (
        "no",
        "nope",
        "none",
        "not",
        "nothing",
        "never",
    ):
        return True

    return text.startswith(
        (
            "no ",
            "nope ",
            "not ",
            "none ",
            "nothing ",
        )
    )


def _field_is_negative(
    assessment: Dict[str, str],
    field: str,
) -> bool:

    value = _normalise(
        assessment.get(field, "")
    )

    if not value:
        return False

    return _is_negative_answer(value)


# ============================================================================
# QUESTION SELECTION
# ============================================================================

_QUESTION_ORDER: Tuple[str, ...] = (
    "onset",
    "progression",
    "appearance",
    "warmth",
    "drainage",
    "separation",
    "pain",
    "fever",
)


def _next_question(
    assessment: Dict[str, str],
    needs_alt: Optional[set] = None,
) -> Optional[Tuple[str, str]]:
    """
    Adaptive wound assessment.

    We intentionally collect the core wound findings before concluding.

    Required for a normal wound assessment:

        onset
        progression
        appearance
        warmth
        drainage
        separation

    Pain and fever are collected when they were not already supplied.

    This prevents the agent from concluding immediately after:

        onset + progression + appearance

    which was the previous bug.

    If `needs_alt` contains a field (the patient answered "I don't
    know" to its normal question), the SIMPLIFIED question from
    _ALT_QUESTIONS is asked instead of repeating the same question.
    """

    needs_alt = needs_alt or set()

    for field in _QUESTION_ORDER:

        if field not in assessment:

            if field in needs_alt:
                return (
                    field,
                    _ALT_QUESTIONS[field],
                )

            return (
                field,
                _QUESTIONS[field],
            )

    return None


# ============================================================================
# CONCLUSION CHECK
# ============================================================================

def _should_conclude(
    assessment: Dict[str, str],
) -> bool:
    """
    Only conclude once the important wound fields have been assessed.

    This is intentionally stricter than the previous implementation.

    The agent must have:

        onset
        progression
        appearance
        warmth
        drainage
        separation

    before it hands the case to RAG + Qwen.

    Pain and fever are optional if they were not relevant to the
    patient's initial complaint.
    """

    required_wound_fields = (
        "onset",
        "progression",
        "appearance",
        "warmth",
        "drainage",
        "separation",
    )

    return all(
        field in assessment
        for field in required_wound_fields
    )


# ============================================================================
# FRIENDLY ACKNOWLEDGEMENT
# ============================================================================

def _acknowledgement(
    assessment: Dict[str, str],
) -> str:

    if not assessment:
        return (
            "I understand. 🩹 Let's go through this together "
            "step by step."
        )

    latest = _normalise(
        list(assessment.values())[-1]
    )

    if (
        "better" in latest
        or "less red" in latest
        or "less redness" in latest
        or "less warm" in latest
        or "improving" in latest
    ):
        return (
            "Thanks, that's helpful. It's good to know that "
            "you've noticed some improvement."
        )

    if (
        _is_worsening(latest)
        and not _is_improving(latest)
    ):
        return (
            "Thanks for telling me. Since you've noticed a "
            "change, I'd like to check a little more carefully."
        )

    if any(
        term in latest
        for term in (
            "fluid",
            "drainage",
            "discharge",
            "leaking",
            "pus",
        )
    ):
        return (
            "Thanks, that's useful information. "
            "Let's clarify that a little further."
        )

    if _is_negative_answer(latest):
        return (
            "Thanks, that's helpful to know."
        )

    return (
        "Thanks, that helps me understand what you're noticing."
    )


# ============================================================================
# FOLLOW-UP RESPONSE
# ============================================================================

def _followup_response(
    question: str,
    assessment: Dict[str, str],
    precomputed_triage: Optional[Dict[str, Any]],
) -> Dict[str, Any]:

    triage_level = "GREEN"
    is_escalated = False

    if precomputed_triage:

        triage_level = precomputed_triage.get(
            "triage_level",
            "GREEN",
        )

        is_escalated = bool(
            precomputed_triage.get(
                "is_escalated",
                False,
            )
        )

    reply = (
        _acknowledgement(assessment)
        + "\n\n"
        + question
    )

    return {
        "reply": reply,
        "triage_level": triage_level,
        "is_escalated": is_escalated,
        "engine": "Wound Care Agent - Multi-turn Assessment",
        "sources": [],
    }


# ============================================================================
# LLM FALLBACK DETECTION
# ============================================================================

def _is_unhelpful_llm_reply(
    reply: str,
) -> bool:

    text = _normalise(reply)

    generic_phrases = (
        "i don't have enough specific information",
        "i do not have enough specific information",
        "please provide a little more detail about what you would like help with",
        "please provide more detail about what you would like help with",
        "i need more information about what you would like help with",
    )

    return any(
        phrase in text
        for phrase in generic_phrases
    )


# ============================================================================
# SAFE DETERMINISTIC CONCLUSION
# ============================================================================

def _deterministic_conclusion(
    assessment: Dict[str, str],
    precomputed_triage: Optional[Dict[str, Any]],
) -> Dict[str, Any]:

    triage_level = "GREEN"
    is_escalated = False

    if precomputed_triage:

        triage_level = precomputed_triage.get(
            "triage_level",
            "GREEN",
        )

        is_escalated = bool(
            precomputed_triage.get(
                "is_escalated",
                False,
            )
        )

    progression = _normalise(
        assessment.get("progression", "")
    )

    appearance = _normalise(
        assessment.get("appearance", "")
    )

    warmth = _normalise(
        assessment.get("warmth", "")
    )

    drainage = _normalise(
        assessment.get("drainage", "")
    )

    separation = _normalise(
        assessment.get("separation", "")
    )

    pain = assessment.get(
        "pain",
        "",
    ).strip()

    fever = _normalise(
        assessment.get("fever", "")
    )

    improving = (
        _is_improving(progression)
        or "less red" in appearance
        or "less redness" in appearance
        or "less warm" in warmth
    )

    no_drainage = (
        _is_negative_answer(drainage)
        or "no fluid" in drainage
        or "no drainage" in drainage
        or "no discharge" in drainage
    )

    closed = (
        "closed" in separation
        and not any(
            term in separation
            for term in (
                "open",
                "opening",
                "separated",
                "separation",
            )
        )
    )

    no_fever = (
        _is_negative_answer(fever)
        or "no fever" in fever
        or "not feverish" in fever
    )

    summary_bits: List[str] = []

    if improving:
        summary_bits.append(
            "you've described the wound as improving"
        )

    if "less red" in appearance:
        summary_bits.append(
            "the redness has decreased"
        )

    if "less warm" in warmth:
        summary_bits.append(
            "the area feels less warm"
        )

    if no_drainage:
        summary_bits.append(
            "you have not noticed fluid from the incision"
        )

    if closed:
        summary_bits.append(
            "the incision is still closed"
        )

    if no_fever:
        summary_bits.append(
            "you have not reported fever or feeling feverish"
        )

    summary = (
        "; ".join(summary_bits)
        if summary_bits
        else "the wound findings you described"
    )

    if triage_level == "RED":

        action = (
            "Because the safety triage result is RED, follow the "
            "emergency escalation instruction provided by the "
            "system and seek urgent clinical help."
        )

    elif triage_level == "YELLOW":

        action = (
            "Because the safety triage result is YELLOW, follow the "
            "clinical advice provided by your surgical team and "
            "contact them if the concern persists or worsens."
        )

    else:

        action = (
            "For now, continue following the wound-care instructions "
            "given by your surgical team. Monitor the incision for "
            "meaningful changes such as increasing redness, increasing "
            "warmth, new or worsening drainage, the incision opening, "
            "increasing pain, or feeling feverish or unwell. If these "
            "changes develop, contact your surgical team promptly."
        )

    pain_sentence = ""

    if pain and pain.strip().lower() != "unknown":

        if _is_improving(pain):
            pain_sentence = (
                " You also described improvement in the discomfort."
            )
        else:
            pain_sentence = (
                " You also reported pain or tenderness around the area."
            )

    # ============================================================
    # UNKNOWN / UNCERTAIN FIELDS
    #
    # A field left as "unknown" must never be silently treated as
    # neutral -- explicitly call it out so the patient (or whoever is
    # reading this) knows something still needs checking.
    # ============================================================

    unknown_fields = [
        field
        for field, value in assessment.items()
        if value == "unknown"
    ]

    uncertainty_sentence = ""

    if unknown_fields:

        readable_fields = ", ".join(
            field.replace("_", " ")
            for field in unknown_fields
        )

        uncertainty_sentence = (
            "\n\nYou weren't able to tell about the following: "
            f"{readable_fields}. Since that's not clear from what you "
            "described, it's a good idea to have someone else take a "
            "look at the area for you, or check with your surgical "
            "team, just to be safe."
        )

    reply = (
        "Thanks for going through that with me. "
        f"Based on what you've told me, {summary}."
        f"{pain_sentence}\n\n"
        f"{action}"
        f"{uncertainty_sentence}\n\n"
        "This is a preliminary assessment based on the information "
        "you provided and cannot confirm how the incision is healing."
    )

    return {
        "reply": reply,
        "triage_level": triage_level,
        "is_escalated": is_escalated,
        "engine": "Wound Care Agent - Safe Conclusion Fallback",
        "sources": [],
    }


# ============================================================================
# WOUND CARE AGENT
# ============================================================================

class WoundCareAgent(BaseClinicalAgent):

    TARGET_AGENT = TargetAgent.WOUND_CARE_AGENT

    DOMAIN_FOCUS = (
        "You are OrthoSync's Wound Care Agent for orthopedic "
        "postoperative recovery. "

        "Communicate like a calm, professional clinical support "
        "assistant. Be warm and conversational, but never pretend "
        "to be a human doctor. "

        "Briefly acknowledge what the patient has told you before "
        "responding. "

        "Use the entire conversation history and all previous "
        "patient answers. Never repeatedly ask for information "
        "that has already been provided. "

        "When important information is missing, ask one focused "
        "question at a time. Questions should be adaptive and "
        "relevant to the patient's answers. "

        "Once the wound assessment is complete, STOP asking "
        "follow-up questions. Give a clear preliminary conclusion, "
        "practical next steps, and what the patient should monitor. "

        "Use retrieved orthopedic clinical knowledge as the basis "
        "for specific medical guidance. Never invent clinical facts, "
        "treatment instructions, thresholds, doses, or timelines. "

        "The deterministic SafetyTriageEngine has already evaluated "
        "the current message upstream and its result is authoritative. "
        "Do not independently classify emergencies or override the "
        "triage result. "

        "If the patient reports improvement, acknowledge that "
        "improvement rather than treating the original symptom as "
        "unchanged. "

        "A small number of professional emojis such as 🩹 or ⚠️ "
        "may be used when helpful, but do not overuse emojis."
    )

    @classmethod
    def handle(
        cls,
        *,
        patient_id: str,
        surgery_type: str,
        affected_limb: str,
        postop_day: int,
        user_message: str,
        procedure: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        surgery_date: Optional[str] = None,
        precomputed_triage: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        history = chat_history or []

        # ============================================================
        # Explicit topic change
        # ============================================================

        if _changed_to_other_topic(
            user_message
        ):

            return ChatAgent.answer_question(
                patient_id=patient_id,
                surgery_type=surgery_type,
                affected_limb=affected_limb,
                postop_day=postop_day,
                user_message=user_message,
                chat_history=history,
                procedure=procedure,
                domain_instruction=cls.DOMAIN_FOCUS,
                precomputed_triage=precomputed_triage,
                surgery_date=surgery_date,
            )

        # ============================================================
        # Confirm wound conversation
        # ============================================================

        if not _is_wound_conversation(
            user_message,
            history,
        ):

            return ChatAgent.answer_question(
                patient_id=patient_id,
                surgery_type=surgery_type,
                affected_limb=affected_limb,
                postop_day=postop_day,
                user_message=user_message,
                chat_history=history,
                procedure=procedure,
                domain_instruction=cls.DOMAIN_FOCUS,
                precomputed_triage=precomputed_triage,
                surgery_date=surgery_date,
            )

        # ============================================================
        # Reconstruct COMPLETE assessment
        # ============================================================

        assessment, needs_alt = _build_assessment(
            history,
            user_message,
        )

        print(
            "[WOUND] "
            f"assessment={assessment} needs_alt={needs_alt}"
        )

        # ============================================================
        # Continue assessment until ALL CORE WOUND FIELDS exist
        #
        # If the patient was uncertain about a field, needs_alt makes
        # _next_question ask the SIMPLIFIED version instead of moving
        # on or repeating the same question.
        # ============================================================

        if not _should_conclude(
            assessment
        ):

            next_question = _next_question(
                assessment,
                needs_alt,
            )

            if next_question:

                _, question = next_question

                return _followup_response(
                    question=question,
                    assessment=assessment,
                    precomputed_triage=precomputed_triage,
                )

        # ============================================================
        # FINAL CONCLUSION
        #
        # Fields the patient was never able to answer (still "I don't
        # know" after the simplified question) show as "not sure"
        # rather than their raw internal marker, so both the LLM prompt
        # and the deterministic fallback treat them as explicitly
        # unresolved instead of a normal finding.
        # ============================================================

        assessment_summary = "\n".join(
            f"- {field}: {'not sure' if value == 'unknown' else value}"
            for field, value in assessment.items()
        )

        has_unknown_fields = any(
            value == "unknown"
            for value in assessment.values()
        )

        # ============================================================
        # FINAL CONCLUSION INSTRUCTION
        #
        # The assessment is complete.
        # The LLM is still used so that the existing RAG + Qwen
        # pipeline remains intact.
        #
        # The important change is that the FINAL response is explicitly
        # instructed to answer from the completed patient assessment
        # rather than falling back to generic information about one
        # symptom.
        # ============================================================

        conclusion_instruction = (
            f"{cls.DOMAIN_FOCUS}\n\n"

            "IMPORTANT: The conversational wound assessment is COMPLETE.\n"
            "This is the FINAL response to the patient.\n\n"

            "Use BOTH the complete previous conversation history and the "
            "structured wound assessment below. The patient's reported "
            "findings are the primary context for the answer.\n\n"

            "Do NOT restart the assessment.\n"
            "Do NOT ask another routine wound-care question.\n"
            "Do NOT ask the patient to provide information that is already "
            "present in the assessment.\n"
            "Do NOT respond with a generic explanation about only one "
            "symptom.\n"
            "Do NOT ignore improvement reported by the patient.\n\n"

            "Patient-reported wound assessment:\n"
            f"{assessment_summary}\n\n"

            "Generate a patient-specific final response.\n\n"

            "The response must:\n"
            "1. Briefly acknowledge what the patient reported.\n"
            "2. Summarise the important wound findings that were actually "
            "reported.\n"
            "3. Explicitly mention improvement or worsening when present.\n"
            "4. Give a clear preliminary interpretation based on the "
            "reported findings.\n"
            "5. Give practical next steps.\n"
            "6. Explain what changes should be monitored.\n"
            "7. Explain when the patient should contact the surgical team.\n\n"

            "Use the retrieved orthopedic knowledge from the existing RAG "
            "pipeline for specific clinical guidance. Apply that knowledge "
            "to the patient's actual findings instead of replacing the "
            "assessment with generic wound-care education.\n\n"

            "For example, if the assessment says that pain is improving, "
            "redness is decreasing, warmth is decreasing, there is no "
            "drainage, and the incision is closed, explicitly acknowledge "
            "those findings together in the final answer. Do not respond "
            "only with general information about drainage, pain, redness, "
            "or postoperative wounds.\n\n"

            "Write in plain, everyday language a patient without a medical "
            "background would understand. Avoid clinical jargon where a "
            "simpler word works, and briefly explain any medical term you "
            "do need to use.\n\n"

            + (
                "IMPORTANT: One or more fields in the assessment are "
                "marked 'not sure' -- the patient was genuinely unable "
                "to tell, even after being offered an easier way to "
                "check. Do NOT treat 'not sure' as a normal or "
                "reassuring finding and do NOT silently ignore it. "
                "Explicitly say which finding(s) are unclear, and "
                "recommend the patient ask someone to look at the area "
                "for them or check with their surgical team, so nothing "
                "gets missed.\n\n"
                if has_unknown_fields
                else ""
            )

            + "Do not independently perform emergency triage.\n"
            "The deterministic SafetyTriageEngine result is authoritative.\n"
            "Do not invent medical thresholds, treatment instructions, "
            "doses, or timelines.\n\n"

            "The assessment is complete. Give the final patient-facing "
            "answer now."
        )

        # ============================================================
        # EXISTING RAG + QWEN CONCLUSION
        #
        # FIX: final_wound_assessment and wound_assessment_summary were
        # previously NOT passed here. That meant ChatAgent.answer_question()
        # always treated this as a normal chat turn:
        #   - _query_llama() built the generic "2-3 sentence answer" prompt
        #     instead of the dedicated final-wound-assessment prompt.
        #   - If that generic LLM reply was empty/unhelpful, the fallback
        #     dropped into _generate_smart_reply(), which returns the
        #     static "Based on your Day X protocol..." RAG-dump text --
        #     the exact generic answer being reported. Passing these two
        #     fields routes both the prompt AND the fallback through the
        #     dedicated final-wound-assessment path instead.
        # ============================================================

        llm_result = ChatAgent.answer_question(
            patient_id=patient_id,
            surgery_type=surgery_type,
            affected_limb=affected_limb,
            postop_day=postop_day,
            user_message=(
                "FINAL WOUND-CARE RESPONSE.\n\n"
                "The multi-turn wound assessment is COMPLETE.\n"
                "Do not ask another question.\n\n"

                "Use the previous conversation and the completed "
                "patient-specific assessment below as the main context "
                "for your answer:\n\n"

                f"{assessment_summary}\n\n"

                "Generate a concise, patient-specific final conclusion. "
                "Explicitly reflect the patient's actual findings, "
                "including improvement or worsening. Do not replace "
                "these findings with generic wound-care information."
            ),
            chat_history=history,
            procedure=procedure,
            domain_instruction=conclusion_instruction,
            precomputed_triage=precomputed_triage,
            surgery_date=surgery_date,
            final_wound_assessment=True,
            wound_assessment_summary=assessment_summary,
        )

        # ============================================================
        # CHECK THE LLM RESPONSE
        # ============================================================

        llm_reply = str(
            llm_result.get(
                "reply",
                "",
            )
        ).strip()

        # ============================================================
        # IMPORTANT:
        #
        # A generic response is not acceptable after a completed
        # wound assessment.
        #
        # If Qwen returns a useful patient-specific response, preserve
        # the existing RAG + Qwen result.
        #
        # Otherwise use the deterministic conclusion, which explicitly
        # summarises the patient's actual wound findings.
        # ============================================================

        if (
            llm_reply
            and not _is_unhelpful_llm_reply(
                llm_reply
            )
        ):

            return llm_result

        return _deterministic_conclusion(
            assessment=assessment,
            precomputed_triage=precomputed_triage,
        )