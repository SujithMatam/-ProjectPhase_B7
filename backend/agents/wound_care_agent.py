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
from patient_database import (
    save_wound_assessment,
    get_recent_wound_assessments,
    record_triage_event,
)
from doctor_alert import doctor_alert_notifier


# ============================================================================
# WOUND TERMS
#
# UNAMBIGUOUS WOUND ANCHORS ONLY -- kept in sync with lam/orchestrator.py's
# own _WOUND_TERMS (see that module's comment for the full rationale).
# Ambiguous, generic symptom words (swelling/swollen, redness/red,
# warm(th)/warmer/hot, fluid) are deliberately excluded here too: this
# module's _is_wound_conversation() must not disagree with the orchestrator
# about what counts as an unambiguous wound term, or the two layers could
# silently diverge on whether a bare "My knee is swollen." should be treated
# as wound-related.
# ============================================================================

_WOUND_TERMS = (
    "wound",
    "incision",
    "surgical site",
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
    "dressing_status": (
        "Since you are in early recovery, is your surgical dressing or bandage "
        "still clean, dry, and intact, or is there any fluid staining or strike-through soaking through it?"
    ),
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
    "dressing_status": (
        "That's okay! Just check the outside of the bandage: is it completely dry "
        "and firmly sticking, or is there any wetness, leaking, or staining?"
    ),
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
        "dressing_status": "outside of the bandage",
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

    # Dressing status
    if (
        "surgical dressing" in normalised
        or "clean, dry, and intact" in normalised
        or "strike-through" in normalised
        or "strikethrough" in normalised
        or "dressing or bandage still clean" in normalised
    ):
        return "dressing_status"

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

    # Dressing status
    if any(
        term in normalised
        for term in (
            "dressing",
            "bandage",
            "strike-through",
            "strikethrough",
            "gauze",
            "tape",
        )
    ):
        result["dressing_status"] = text.strip()

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
    elif any(
        term in normalised
        for term in (
            "covered by dressing",
            "under the dressing",
            "under the bandage",
            "dressing is on",
            "bandage is on",
            "can't see incision",
            "cannot see incision",
            "cant see incision",
        )
    ):
        result["separation"] = "Covered by intact dressing"

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
# DRAINAGE CLASSIFICATION
# ============================================================================

def classify_drainage_type(text: str) -> Tuple[str, str]:
    """
    Classify wound drainage characteristics into clinical categories:
      - 'none': Dry, no leakage
      - 'serous': Clear, straw-colored, thin (normal healing exudate)
      - 'serosanguineous': Pink, blood-tinged watery fluid (common early post-op)
      - 'sanguineous': Active red blood, bloody
      - 'purulent': Yellow, green, milky, thick, foul-smelling, pus (SSI indicator)
      - 'unknown': Fluid mentioned but character unspecified
    Returns: (category, description)
    """
    if not text:
        return "none", "No drainage reported"

    normalised = _normalise(text)
    if _is_negative_answer(normalised) or any(
        term in normalised for term in (
            "no fluid", "no drainage", "no discharge", "dry",
            "not leaking", "none", "no leak", "nothing leaking"
        )
    ):
        return "none", "No drainage observed (dry incision)"

    def _has_any(terms: Tuple[str, ...]) -> bool:
        return any(bool(re.search(r"\b" + re.escape(t) + r"\b", normalised)) for t in terms)

    # Purulent: Cardinal sign of Surgical Site Infection (SSI)
    if _has_any((
        "pus", "yellow", "green", "cloudy", "milky", "foul", "smelly",
        "stinky", "odor", "odour", "bad smell", "thick discharge", "opaque"
    )):
        return "purulent", "Purulent drainage (thick/yellow/green/foul odor - suspected surgical site infection)"

    # Serosanguineous: Pink, blood-tinged watery
    if _has_any((
        "pink", "blood-tinged", "blood tinged", "pinkish", "watery blood"
    )):
        return "serosanguineous", "Serosanguineous drainage (thin, pink, blood-tinged fluid)"

    # Sanguineous: Active blood
    if _has_any((
        "blood", "bloody", "red fluid", "bleeding"
    )):
        return "sanguineous", "Sanguineous drainage (fresh or dark red blood)"

    # Serous: Normal clear/pale yellow
    if _has_any((
        "clear", "straw", "watery", "pale yellow", "thin fluid", "amber"
    )):
        return "serous", "Serous drainage (clear or straw-colored normal post-op fluid)"

    if _has_any((
        "fluid", "drainage", "discharge", "leaking", "oozing", "leak", "wet"
    )):
        return "unknown", "Unspecified fluid drainage"

    return "none", "No drainage reported"


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


def _get_question_order(postop_day: Optional[int] = None) -> Tuple[str, ...]:
    if postop_day is not None and postop_day <= 3:
        return (
            "dressing_status",
            "onset",
            "progression",
            "appearance",
            "warmth",
            "drainage",
            "separation",
            "pain",
            "fever",
        )
    return (
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
    postop_day: Optional[int] = None,
) -> Optional[Tuple[str, str]]:
    """
    Adaptive wound assessment.

    We intentionally collect the core wound findings before concluding.
    If postop_day <= 3, dressing status (intact vs strike-through) is assessed
    before inspecting or asking about bare incision separation.

    If `needs_alt` contains a field (the patient answered "I don't
    know" to its normal question), the SIMPLIFIED question from
    _ALT_QUESTIONS is asked instead of repeating the same question.
    """

    needs_alt = needs_alt or set()
    order = _get_question_order(postop_day)

    for field in order:

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
    postop_day: Optional[int] = None,
) -> bool:
    """
    Only conclude once the important wound fields have been assessed.
    For early post-op (postop_day <= 3), dressing_status is also required.
    """

    required_wound_fields = [
        "onset",
        "progression",
        "appearance",
        "warmth",
        "drainage",
        "separation",
    ]
    if postop_day is not None and postop_day <= 3:
        required_wound_fields.insert(0, "dressing_status")

    return all(
        field in assessment
        for field in required_wound_fields
    )


# ============================================================================
# FRIENDLY ACKNOWLEDGEMENT
# ============================================================================

def _acknowledgement(
    assessment: Dict[str, str],
    has_photo: bool = False,
    photo_summary: str = "",
) -> str:

    prefix = ""
    if has_photo:
        if photo_summary:
            prefix = f"{photo_summary} 🩹 "
        else:
            prefix = "I've reviewed your uploaded incision photo. 🩹 "

    if not assessment:
        if prefix:
            return prefix + "Let's go through a few quick questions to assess how the area is doing."
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
        body = (
            "Thanks, that's helpful. It's good to know that "
            "you've noticed some improvement."
        )
        return f"{prefix}{body}" if prefix else body

    if (
        _is_worsening(latest)
        and not _is_improving(latest)
    ):
        body = (
            "Thanks for telling me. Since you've noticed a "
            "change, I'd like to check a little more carefully."
        )
        return f"{prefix}{body}" if prefix else body

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
        body = (
            "Thanks, that's useful information. "
            "Let's clarify that a little further."
        )
        return f"{prefix}{body}" if prefix else body

    if _is_negative_answer(latest):
        body = (
            "Thanks, that's helpful to know."
        )
        return f"{prefix}{body}" if prefix else body

    body = (
        "Thanks, that helps me understand what you're noticing."
    )
    return f"{prefix}{body}" if prefix else body


# ============================================================================
# FOLLOW-UP RESPONSE
# ============================================================================

def _followup_response(
    question: str,
    assessment: Dict[str, str],
    precomputed_triage: Optional[Dict[str, Any]],
    has_photo: bool = False,
    photo_summary: str = "",
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
        _acknowledgement(assessment, has_photo=has_photo, photo_summary=photo_summary)
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

# ============================================================================
# MULTIMODAL PHOTO ANALYSIS EXTRACTION
# ============================================================================

def _extract_photo_analysis(
    photo_analysis: Optional[Dict[str, Any]],
    chat_history: Optional[List[Dict[str, str]]],
    user_message: str,
) -> Optional[Dict[str, Any]]:
    """
    Extracts wound image CV analysis either from the direct API payload
    or by scanning recent conversation history / photo cards.
    """
    if photo_analysis and isinstance(photo_analysis, dict):
        return photo_analysis

    # Check user_message and chat_history for photo analysis outputs
    all_texts: List[str] = [user_message]
    for item in reversed(chat_history or []):
        if isinstance(item, dict):
            all_texts.append(str(item.get("content", "")))

    for text in all_texts:
        norm = text.lower()
        if "elevated_redness_detected" in norm or ("noticeable redness" in norm and ("photo" in norm or "image" in norm)):
            score = 0.08
            score_match = re.search(r"redness[_\s]score[:=\s]+([0-9.]+)", norm)
            if score_match:
                try:
                    score = float(score_match.group(1))
                except ValueError:
                    pass
            return {
                "visual_flag": "elevated_redness_detected",
                "redness_score": score,
                "redness_intensity": 0.50,
            }
        if "no_strong_indicators" in norm or ("don't see any strong signs of redness" in norm and ("photo" in norm or "image" in norm)):
            return {
                "visual_flag": "no_strong_indicators",
                "redness_score": 0.01,
                "redness_intensity": 0.10,
            }

    return None


# ============================================================================
# LONGITUDINAL COMPARISON
# ============================================================================

def _build_longitudinal_comparison(
    patient_id: str,
    current_assessment: Dict[str, str],
    current_postop_day: int,
) -> str:
    """
    Compares current wound assessment with prior visits recorded in SQLite
    to identify recovery trends (improving vs worsening vs stable).
    """
    try:
        past_records = get_recent_wound_assessments(patient_id, limit=3)
    except Exception as exc:
        print(f"[WOUND] Error retrieving prior assessments: {exc}")
        return ""

    if not past_records:
        return ""

    prior = past_records[0]
    prior_day = prior.get("postop_day")
    prior_app = str(prior.get("appearance", "")).lower()
    prior_drain = str(prior.get("drainage", "")).lower()
    prior_pain = str(prior.get("pain", "")).lower()

    curr_app = str(current_assessment.get("appearance", "")).lower()
    curr_drain = str(current_assessment.get("drainage", "")).lower()
    curr_pain = str(current_assessment.get("pain", "")).lower()

    comparison_points: List[str] = []

    # Redness comparison
    if "less red" in curr_app or ("red" in prior_app and ("normal" in curr_app or "not red" in curr_app or "less" in curr_app or "improving" in curr_app)):
        comparison_points.append("Incision redness has improved compared to your previous visit")
    elif "more red" in curr_app or ("elevated" in curr_app and "elevated" not in prior_app):
        comparison_points.append("Increased redness noted compared to your previous visit")

    # Drainage comparison
    curr_drain_type, _ = classify_drainage_type(curr_drain)
    prior_drain_type = prior.get("drainage_type") or classify_drainage_type(prior_drain)[0]
    if prior_drain_type in ("serous", "serosanguineous", "purulent", "sanguineous") and curr_drain_type == "none":
        comparison_points.append("Previous fluid drainage has now resolved")
    elif prior_drain_type == "none" and curr_drain_type in ("purulent", "sanguineous"):
        comparison_points.append(f"New {curr_drain_type} drainage developed since your previous visit")
    elif curr_drain_type == "purulent":
        comparison_points.append("Ongoing or new purulent drainage detected")

    # Pain comparison
    if _is_improving(curr_pain) or ("pain" in prior_pain and ("better" in curr_pain or "no pain" in curr_pain or "0" in curr_pain)):
        comparison_points.append("Incision site discomfort has decreased")
    elif _is_worsening(curr_pain):
        comparison_points.append("Incision pain or tenderness has increased compared to prior report")

    day_label = f"Day {prior_day}" if prior_day else "prior check-in"
    if not comparison_points:
        return f"\n\n**Recovery Trend:** Your wound findings remain consistent with {day_label}."

    bullets = "\n".join(f"• {pt}." for pt in comparison_points)
    return f"\n\n**Recovery Trend (vs. {day_label}):**\n{bullets}"


# ============================================================================
# PERSISTENCE & PHYSICIAN ALERT LINKAGE
# ============================================================================

def _finalize_assessment_persistence(
    patient_id: str,
    postop_day: int,
    assessment: Dict[str, str],
    precomputed_triage: Optional[Dict[str, Any]],
    photo_analysis: Optional[Dict[str, Any]],
    summary_text: str,
) -> Tuple[str, bool, str]:
    """
    Saves assessment to SQLite, escalates triage if purulent/infected,
    creates triage event record, and fires doctor alert if RED.
    """
    triage_level = "GREEN"
    is_escalated = False

    if precomputed_triage:
        triage_level = precomputed_triage.get("triage_level", "GREEN")
        is_escalated = bool(precomputed_triage.get("is_escalated", False))

    drainage_text = assessment.get("drainage", "")
    drainage_type, _ = classify_drainage_type(drainage_text)

    # SSI Escalation check
    fever_val = _normalise(assessment.get("fever", ""))
    has_fever = bool(fever_val and not _is_negative_answer(fever_val) and "no fever" not in fever_val and "not feverish" not in fever_val)

    if drainage_type == "purulent":
        if has_fever or _is_worsening(assessment.get("pain", "")):
            triage_level = "RED"
            is_escalated = True
        elif triage_level == "GREEN":
            triage_level = "YELLOW"
            is_escalated = True

    # Photo analysis values
    redness_score = None
    visual_flag = None
    if photo_analysis:
        redness_score = photo_analysis.get("redness_score")
        visual_flag = photo_analysis.get("visual_flag")

    # Longitudinal comparison
    trend_text = _build_longitudinal_comparison(
        patient_id=patient_id,
        current_assessment=assessment,
        current_postop_day=postop_day,
    )

    # Persist to SQLite
    record = {
        "postop_day": postop_day,
        "onset": assessment.get("onset"),
        "progression": assessment.get("progression"),
        "appearance": assessment.get("appearance"),
        "warmth": assessment.get("warmth"),
        "drainage": assessment.get("drainage"),
        "drainage_type": drainage_type,
        "separation": assessment.get("separation"),
        "pain": assessment.get("pain"),
        "fever": assessment.get("fever"),
        "dressing_status": assessment.get("dressing_status"),
        "redness_score": redness_score,
        "visual_flag": visual_flag,
        "triage_level": triage_level,
        "summary": summary_text,
    }
    try:
        save_wound_assessment(patient_id, record)
        print(f"[WOUND] Saved wound assessment for {patient_id} (Day {postop_day}, triage={triage_level}, drainage={drainage_type})")
    except Exception as exc:
        print(f"[WOUND] Failed to persist wound assessment: {exc}")

    # Record triage event if escalated or purulent
    if triage_level in ("RED", "YELLOW") or drainage_type == "purulent":
        try:
            record_triage_event(
                patient_id=patient_id,
                level=triage_level,
                symptom=f"Wound assessment: drainage={drainage_type}, appearance={assessment.get('appearance', 'unspecified')}",
                action="Emergency surgical site review advised" if triage_level == "RED" else "Clinical nurse wound review required",
            )
        except Exception as exc:
            print(f"[WOUND] Failed to record triage event: {exc}")

    # Doctor alert linkage if RED
    if triage_level == "RED":
        try:
            doctor_alert_notifier.notify_red_triage_background(
                patient_id=patient_id,
                user_message=f"Critical wound finding: drainage={drainage_type}, appearance={assessment.get('appearance', '')}",
                triage={
                    "triage_level": "RED",
                    "reasons": [f"Purulent drainage / wound infection risk ({drainage_type})"],
                    "action_protocol": "Immediate physician review required.",
                },
                postop_day=postop_day,
            )
        except Exception as exc:
            print(f"[WOUND] Failed to notify doctor alert: {exc}")

    return triage_level, is_escalated, trend_text


# ============================================================================
# SAFE DETERMINISTIC CONCLUSION
# ============================================================================

def _deterministic_conclusion(
    patient_id: str,
    postop_day: int,
    assessment: Dict[str, str],
    precomputed_triage: Optional[Dict[str, Any]],
    photo_analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

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
        ("closed" in separation or "covered by intact dressing" in separation)
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
            "the incision remains closed and protected"
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

    # Persistence, SQLite storage, triage escalation, and doctor alert
    triage_level, is_escalated, trend_text = _finalize_assessment_persistence(
        patient_id=patient_id,
        postop_day=postop_day,
        assessment=assessment,
        precomputed_triage=precomputed_triage,
        photo_analysis=photo_analysis,
        summary_text=summary,
    )

    drainage_type, _ = classify_drainage_type(drainage)

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

    ssi_warning = ""
    if drainage_type == "purulent":
        ssi_warning = (
            "\n\n⚠️ **CLINICAL NOTICE: Suspected Infection Signs (Purulent Drainage)**\n"
            "You reported drainage that appears thick, cloudy, yellow/green, or with an odor. "
            "In postoperative joint recovery, this can indicate a surgical site infection. "
            "Please notify your surgeon's clinic promptly for an urgent in-person evaluation."
        )

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
        f"{pain_sentence}"
        f"{ssi_warning}\n\n"
        f"{action}"
        f"{trend_text}"
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
        photo_analysis: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
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
        # Multimodal Photo Extraction & Fusion
        # ============================================================

        photo = _extract_photo_analysis(photo_analysis, history, user_message)

        # Confirm wound conversation (photo presence confirms wound domain)
        if not _is_wound_conversation(user_message, history) and not photo:

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

        # Auto-seed appearance from photo if not already explicitly stated
        photo_summary_phrase = ""
        if photo:
            flag = photo.get("visual_flag")
            score = photo.get("redness_score", 0.0)
            if flag == "elevated_redness_detected":
                if "appearance" not in assessment:
                    assessment["appearance"] = f"Elevated redness detected on uploaded photo (redness score: {score:.2f})"
                photo_summary_phrase = f"I reviewed your uploaded photo, which showed noticeable redness around the area (score: {score:.2f})."
            elif flag == "no_strong_indicators":
                if "appearance" not in assessment:
                    assessment["appearance"] = "Photo analyzed: no strong signs of elevated redness detected"
                photo_summary_phrase = "I reviewed your uploaded photo, which did not show strong signs of redness."

        print(
            "[WOUND] "
            f"assessment={assessment} needs_alt={needs_alt} photo={bool(photo)}"
        )

        # ============================================================
        # Continue assessment until ALL CORE WOUND FIELDS exist
        # ============================================================

        if not _should_conclude(
            assessment,
            postop_day=postop_day,
        ):

            next_question = _next_question(
                assessment,
                needs_alt,
                postop_day=postop_day,
            )

            if next_question:

                _, question = next_question

                return _followup_response(
                    question=question,
                    assessment=assessment,
                    precomputed_triage=precomputed_triage,
                    has_photo=bool(photo),
                    photo_summary=photo_summary_phrase,
                )

        # ============================================================
        # FINAL CONCLUSION
        # ============================================================

        assessment_summary = "\n".join(
            f"- {field}: {'not sure' if value == 'unknown' else value}"
            for field, value in assessment.items()
        )

        has_unknown_fields = any(
            value == "unknown"
            for value in assessment.values()
        )

        # RAG + Qwen conclusion
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
            "Do NOT respond with a generic explanation about only one symptom.\n"
            "Do NOT ignore improvement reported by the patient.\n\n"
            "Patient-reported wound assessment:\n"
            f"{assessment_summary}\n\n"
            "Generate a patient-specific final response.\n"
            "1. Briefly acknowledge what the patient reported.\n"
            "2. Summarise the important wound findings that were actually reported.\n"
            "3. Explicitly mention improvement or worsening when present.\n"
            "4. Give a clear preliminary interpretation based on the reported findings.\n"
            "5. Give practical next steps.\n"
            "6. Explain what changes should be monitored.\n"
            "7. Explain when the patient should contact the surgical team.\n\n"
            + (
                "IMPORTANT: One or more fields in the assessment are marked 'not sure'. "
                "Explicitly say which finding(s) are unclear and recommend surgical team check.\n\n"
                if has_unknown_fields else ""
            )
            + "The assessment is complete. Give the final patient-facing answer now."
        )

        llm_result = ChatAgent.answer_question(
            patient_id=patient_id,
            surgery_type=surgery_type,
            affected_limb=affected_limb,
            postop_day=postop_day,
            user_message=(
                "FINAL WOUND-CARE RESPONSE.\n\n"
                "The multi-turn wound assessment is COMPLETE.\n"
                "Do not ask another question.\n\n"
                f"{assessment_summary}\n\n"
                "Generate a concise, patient-specific final conclusion."
            ),
            chat_history=history,
            procedure=procedure,
            domain_instruction=conclusion_instruction,
            precomputed_triage=precomputed_triage,
            surgery_date=surgery_date,
            final_wound_assessment=True,
            wound_assessment_summary=assessment_summary,
        )

        llm_reply = str(llm_result.get("reply", "")).strip()

        if llm_reply and not _is_unhelpful_llm_reply(llm_reply):
            # Finalize persistence, triage escalation, and doctor alert
            triage_level, is_escalated, trend_text = _finalize_assessment_persistence(
                patient_id=patient_id,
                postop_day=postop_day,
                assessment=assessment,
                precomputed_triage=precomputed_triage,
                photo_analysis=photo,
                summary_text=llm_reply[:200],
            )
            drainage_type, _ = classify_drainage_type(assessment.get("drainage", ""))
            if drainage_type == "purulent" and "infection" not in llm_reply.lower():
                llm_reply += (
                    "\n\n⚠️ **CLINICAL NOTICE: Suspected Infection Signs (Purulent Drainage)**\n"
                    "You reported drainage that appears thick, cloudy, yellow/green, or with an odor. "
                    "In postoperative joint recovery, this can indicate a surgical site infection. "
                    "Please notify your surgeon's clinic promptly for an urgent in-person evaluation."
                )
            if trend_text and trend_text not in llm_reply:
                llm_reply += trend_text

            llm_result["reply"] = llm_reply
            llm_result["triage_level"] = triage_level
            llm_result["is_escalated"] = is_escalated
            return llm_result

        return _deterministic_conclusion(
            patient_id=patient_id,
            postop_day=postop_day,
            assessment=assessment,
            precomputed_triage=precomputed_triage,
            photo_analysis=photo,
        )