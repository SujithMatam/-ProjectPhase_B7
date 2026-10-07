"""
Pain & Symptoms extraction + pure next-information decision logic.

This module owns:
    - the Pain field vocabulary (module-level constants)
    - reconstructing what is already known from chat_history + the current
      message (the same robust "re-derive every turn" pattern
      agents/wound_care_agent.py already uses for Wound Care -- no server
      state is the single source of truth for a CLINICAL FACT; only the
      pending-field/ask-count BOOKKEEPING lives server-side, in
      agents/pain_state.py)
    - a pure, deterministic function that decides what single piece of
      information is most useful to ask for next, given what is already
      known -- genuinely adaptive (branches on location/severity/context),
      not a fixed linear questionnaire

Nothing in this module calls RAG, an LLM, or SafetyTriageEngine, and nothing
here performs emergency/red-flag classification -- that remains exclusively
the deterministic SafetyTriageEngine's job, upstream, before this module ever
runs (see lam/orchestrator.py Step 1).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple


# ============================================================================
# FIELD VOCABULARY
# ============================================================================

PAIN_SCORE = "pain_score"
ONSET = "onset"
LOCATION = "location"
WORSENING_OR_IMPROVING = "worsening_or_improving"
PAIN_CHARACTERISTICS = "pain_characteristics"
SWELLING = "swelling"
WARMTH_OR_REDNESS = "warmth_or_redness"
STIFFNESS = "stiffness"
NUMBNESS_OR_WEAKNESS = "numbness_or_weakness"
FEVER_OR_TEMPERATURE = "fever_or_temperature"
MEDICATION_EFFECT = "medication_effect"

REQUIRED_FIELDS: Tuple[str, ...] = (PAIN_SCORE, ONSET, LOCATION)

# Conditional/branch fields -- never asked unconditionally; see
# select_next_field() for exactly when each one becomes relevant.
_CALF_BRANCH_FIELDS: Tuple[str, ...] = (SWELLING, WARMTH_OR_REDNESS, NUMBNESS_OR_WEAKNESS)


# ============================================================================
# PATIENT-FACING QUESTIONS (ONE topic per question -- see module docstring
# and the "one question = one tracked answer" project requirement: a
# question must never bundle two different fields, e.g. never
# "swelling, numbness, or weakness?" as a single question).
# ============================================================================

QUESTIONS: Dict[str, str] = {
    PAIN_SCORE: "On a scale from 0 to 10, how bad is the pain right now?",
    ONSET: "Did it come on suddenly, or has it been building up gradually?",
    LOCATION: (
        "Where are you feeling it most -- in the knee itself, behind the "
        "knee, around the incision, in the calf, or somewhere else?"
    ),
    WORSENING_OR_IMPROVING: "Is it getting worse, getting better, or staying about the same?",
    PAIN_CHARACTERISTICS: "How would you describe the pain -- sharp, dull, throbbing, or something else?",
    SWELLING: "Have you noticed any swelling in that area?",
    WARMTH_OR_REDNESS: "Does the area feel warmer than usual, or look red?",
    STIFFNESS: "Does the joint feel stiff, especially when you try to move it?",
    NUMBNESS_OR_WEAKNESS: "Any numbness or weakness in that leg?",
    FEVER_OR_TEMPERATURE: "Have you felt feverish at all, or checked your temperature?",
    MEDICATION_EFFECT: "Did taking your pain medication help, or not really?",
}

# PROCEDURE-AWARE WORDING. QUESTIONS above is the TKA (knee) wording and the
# default. A hip replacement (THA) patient is offered hip-relevant places
# instead of knee ones. Only the fields whose wording actually depends on
# the joint are overridden; every other field falls back to QUESTIONS.
# The THA variants keep the SAME leading marker phrase ("where are you
# feeling it most" / "lower down toward the calf") so question
# identification (_PRIMARY_MARKERS/_ALT_MARKERS) works for both.
QUESTIONS_THA: Dict[str, str] = {
    LOCATION: (
        "Where are you feeling it most -- in the groin, the thigh, the "
        "buttock, the calf, or somewhere else?"
    ),
    STIFFNESS: "Does the hip feel stiff, especially when you try to move it?",
}

ALT_QUESTIONS_THA: Dict[str, str] = {
    LOCATION: (
        "That's okay -- just roughly, is it more in the groin, the thigh, "
        "the buttock, or lower down toward the calf?"
    ),
}


def question_text(field_name: str, *, procedure: Optional[str] = None, alt: bool = False) -> str:
    """The patient-facing question for `field_name`, in the wording for
    `procedure` ("TKA"/"THA"/"GEN"/None). Unknown or non-THA procedures use
    the default (knee) wording, exactly as before."""
    is_tha = str(procedure or "").strip().upper() == "THA"
    if alt:
        if is_tha and field_name in ALT_QUESTIONS_THA:
            return ALT_QUESTIONS_THA[field_name]
        return ALT_QUESTIONS[field_name]
    if is_tha and field_name in QUESTIONS_THA:
        return QUESTIONS_THA[field_name]
    return QUESTIONS[field_name]

# Simplified rephrase, used ONLY after a genuinely uncertain first answer
# ("I don't know") -- never the identical question repeated verbatim.
ALT_QUESTIONS: Dict[str, str] = {
    PAIN_SCORE: (
        "No worries if it's hard to pin down -- would you put it roughly "
        "in the mild range (1-3), moderate range (4-6), or severe range "
        "(7-10)?"
    ),
    ONSET: "No worries. Would you say the pain started all at once, or built up gradually?",
    LOCATION: "That's okay -- just roughly, is it more in the knee, behind it, or lower down toward the calf?",
    WORSENING_OR_IMPROVING: "That's fine -- compared to earlier, does it feel any different at all, or about the same?",
    PAIN_CHARACTERISTICS: "No problem -- would you call it more of a sharp pain or a dull ache?",
    SWELLING: "No worries -- does the area look any more puffy than the other side?",
    WARMTH_OR_REDNESS: "That's okay -- if you gently touch the area, does it feel warmer than the skin around it?",
    STIFFNESS: "No problem -- does it feel harder to bend or move than usual?",
    NUMBNESS_OR_WEAKNESS: "That's fine -- does the leg feel any different, like tingly or weaker than usual?",
    FEVER_OR_TEMPERATURE: "No worries -- have you felt chilly, sweaty, or generally unwell?",
    MEDICATION_EFFECT: "That's okay -- after taking it, did the pain feel any different at all?",
}

# CLARIFYING re-ask, used ONCE after a reply that did not plausibly answer
# the pending question at all (no number for the pain score, no onset/
# location/trend wording, no yes/no for a yes/no question, or clearly a
# different topic). Different lead-in from ALT_QUESTIONS ("I didn't catch
# ..." rather than "No worries if you're not sure"), because the patient
# was not uncertain -- the reply just did not fit the question. Each entry
# deliberately CONTAINS its field's _ALT_MARKERS phrase, so it is
# recognised as a SECOND ask of that field: a second reply that still does
# not fit (or an uncertain one) resolves the field as "unknown", exactly
# like the ALT path -- the agent never loops on the same question.
CLARIFY_QUESTIONS: Dict[str, str] = {
    PAIN_SCORE: (
        "Sorry, I didn't catch a number there. Would you put it roughly in "
        "the mild range (1-3), moderate range (4-6), or severe range (7-10)?"
    ),
    ONSET: (
        "Sorry, I didn't quite catch that. Would you say the pain started all "
        "at once, or built up gradually?"
    ),
    LOCATION: (
        "Sorry, I didn't catch where it is. Just roughly, is it more in the "
        "knee, behind it, or lower down toward the calf?"
    ),
    WORSENING_OR_IMPROVING: (
        "Sorry, I didn't quite catch that. Compared to earlier, does it feel "
        "any different at all, or about the same?"
    ),
    PAIN_CHARACTERISTICS: (
        "Sorry, I didn't quite catch that. Would you call it more of a sharp "
        "pain or a dull ache?"
    ),
    SWELLING: (
        "Sorry, I didn't quite catch that -- a simple yes or no is fine. Does "
        "the area look any more puffy than the other side?"
    ),
    WARMTH_OR_REDNESS: (
        "Sorry, I didn't quite catch that -- a simple yes or no is fine. If "
        "you gently touch the area, does it feel warmer than the skin around it?"
    ),
    STIFFNESS: (
        "Sorry, I didn't quite catch that -- a simple yes or no is fine. Does "
        "it feel harder to bend or move than usual?"
    ),
    NUMBNESS_OR_WEAKNESS: (
        "Sorry, I didn't quite catch that -- a simple yes or no is fine. Does "
        "the leg feel any different, like tingly or weaker than usual?"
    ),
    FEVER_OR_TEMPERATURE: (
        "Sorry, I didn't quite catch that -- a simple yes or no is fine. Have "
        "you felt chilly, sweaty, or generally unwell?"
    ),
    MEDICATION_EFFECT: (
        "Sorry, I didn't quite catch that -- a simple yes or no is fine. After "
        "taking it, did the pain feel any different at all?"
    ),
}

CLARIFY_QUESTIONS_THA: Dict[str, str] = {
    LOCATION: (
        "Sorry, I didn't catch where it is. Just roughly, is it more in the "
        "groin, the thigh, the buttock, or lower down toward the calf?"
    ),
}


def clarify_question_text(field_name: str, *, procedure: Optional[str] = None) -> str:
    if str(procedure or "").strip().upper() == "THA" and field_name in CLARIFY_QUESTIONS_THA:
        return CLARIFY_QUESTIONS_THA[field_name]
    return CLARIFY_QUESTIONS[field_name]


# MEMORY CONFIRMATION of today's already-logged pain score -- asked INSTEAD
# of the pain-score question when today's metrics row already has a score
# (see agents/patient_memory.py). The logged value is embedded in the
# question text ("{n}/10") so a bare "yes" reply can be resolved back to
# that number purely from chat_history (see _confirm_value_from_question).
_CONFIRM_MARKER = "still about that"
# Anchored on "log says N/10" -- the same assistant message may ALSO quote a
# previous assessment ("Last time you had 7/10 ..."), which must never be
# mistaken for today's logged value.
_CONFIRM_VALUE_RE = re.compile(r"log says\s+(10|[0-9])\s*/\s*10\b")


def confirm_pain_score_question(logged_score: int) -> str:
    return f"Your log says {int(logged_score)}/10 earlier today -- still about that?"


def _confirm_value_from_question(text: str) -> Optional[int]:
    normalised = _normalise(text)
    if _CONFIRM_MARKER not in normalised:
        return None
    match = _CONFIRM_VALUE_RE.search(normalised)
    if not match:
        return None
    value = int(match.group(1))
    return value if 0 <= value <= 10 else None


# Short, unique marker substrings used to recognise which field a PAST
# assistant message asked about (primary phrasing), so a short reply like
# "8" or "suddenly" can be attributed to the right field purely from
# chat_history -- same pattern as
# wound_care_agent.py::_primary_field_from_question.
_PRIMARY_MARKERS: Dict[str, str] = {
    PAIN_SCORE: "how bad is the pain right now",
    ONSET: "come on suddenly",
    LOCATION: "where are you feeling it most",
    WORSENING_OR_IMPROVING: "getting worse, getting better",
    PAIN_CHARACTERISTICS: "sharp, dull, throbbing",
    SWELLING: "any swelling in that area",
    WARMTH_OR_REDNESS: "feel warmer than usual",
    STIFFNESS: "feel stiff, especially when you try to move it",
    NUMBNESS_OR_WEAKNESS: "numbness or weakness in that leg",
    FEVER_OR_TEMPERATURE: "felt feverish at all",
    MEDICATION_EFFECT: "did taking your pain medication help",
}

_ALT_MARKERS: Dict[str, str] = {
    PAIN_SCORE: "mild range (1-3)",
    ONSET: "all at once, or built up gradually",
    LOCATION: "lower down toward the calf",
    WORSENING_OR_IMPROVING: "different at all, or about the same",
    PAIN_CHARACTERISTICS: "sharp pain or a dull ache",
    SWELLING: "puffy than the other side",
    WARMTH_OR_REDNESS: "gently touch the area",
    STIFFNESS: "harder to bend or move",
    NUMBNESS_OR_WEAKNESS: "tingly or weaker than usual",
    FEVER_OR_TEMPERATURE: "chilly, sweaty, or generally unwell",
    MEDICATION_EFFECT: "after taking it, did the pain feel any different",
}


# ============================================================================
# NORMALISATION / UNCERTAINTY (deliberately duplicated, small vocabulary --
# same project convention already used by wound_care_agent.py and
# specialized_agents.py::DailyActivityAgent to keep domain agents
# independent of each other rather than reaching into another agent's
# private helpers).
# ============================================================================

def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


_UNCERTAIN_PHRASES = (
    "i don't know", "i dont know", "idk", "don't know", "dont know",
    "not sure", "unsure", "no idea", "no clue", "can't tell", "cant tell",
    "hard to tell", "not certain", "not able to tell", "unable to tell",
)


def _is_uncertain_answer(text: str) -> bool:
    normalised = _normalise(text)
    if not normalised:
        return False
    if normalised in ("dunno", "unknown", "not applicable", "n/a"):
        return True
    return any(phrase in normalised for phrase in _UNCERTAIN_PHRASES)


def _is_negative_answer(text: str) -> bool:
    normalised = _normalise(text).strip(" .!")
    if normalised in (
        "no", "nope", "nah", "none", "not really", "nothing", "never", "not at all",
    ):
        return True
    if normalised in _NEGATIVE_ANSWERS:
        return True
    return normalised.startswith(("no ", "no,", "nope ", "nope,", "nah ", "not really ", "none ", "nothing "))


def _word_present(normalised_text: str, word: str) -> bool:
    """Word/phrase-aware presence check -- \\b-bounded, so "numb" does NOT
    match inside "numbness" (they are separate keyword-list entries with
    their own meaning), avoiding obvious partial-word false positives."""
    return re.search(rf"\b{re.escape(word)}\b", normalised_text) is not None


def _word_is_negated(normalised_text: str, word: str) -> bool:
    """
    True only when the negation is directly adjacent to THIS SPECIFIC word
    (e.g. "not swollen", "no fever", "isn't warm") -- never true merely
    because the message starts with "No". This is the LOCAL/adjacency
    check; _keyword_or_negative also applies a CLAUSE-level check (a
    clause opening with "no"/"not" covers every keyword found within that
    same clause, e.g. "No numbness or weakness" -- see
    _clause_is_negative_led) so a single leading negation can still cover a
    coordinated "A or B" list without needing "no" repeated before each
    word.
    """
    escaped = re.escape(word)
    for pattern in (
        rf"\bno\s+{escaped}\b",
        rf"\bnot\s+{escaped}\b",
        rf"\bisn'?t\s+{escaped}\b",
        rf"\bwasn'?t\s+{escaped}\b",
        rf"\bwithout\s+{escaped}\b",
    ):
        if re.search(pattern, normalised_text):
            return True
    return False


_NEGATION_LEAD_RE = re.compile(r"^\s*(no|not|isn'?t|wasn'?t|without)\b")


def _clause_is_negative_led(clause: str) -> bool:
    """True when a CLAUSE opens with a negation word ("no numbness or
    weakness", "not swollen") -- every field keyword found within THAT
    CLAUSE then shares the one negation, which is what correctly resolves
    a coordinated "no A or B" without requiring "no" immediately before
    each individual word."""
    return bool(_NEGATION_LEAD_RE.match(clause.strip()))


# ============================================================================
# QUESTION IDENTIFICATION (mirrors wound_care_agent.py's approach)
# ============================================================================

def _field_from_question(text: str) -> Optional[str]:
    normalised = _normalise(text)
    for field_name, marker in _ALT_MARKERS.items():
        if marker in normalised:
            return field_name
    for field_name, marker in _PRIMARY_MARKERS.items():
        if marker in normalised:
            return field_name
    if _CONFIRM_MARKER in normalised:
        return PAIN_SCORE
    return None


def _is_alt_question(text: str) -> bool:
    """True for any SECOND-ask phrasing of a field: the simplified ALT
    rephrase (after an uncertain answer) OR the CLARIFY re-ask (after a
    reply that did not fit the question). Both share the field's
    _ALT_MARKERS phrase by construction (see CLARIFY_QUESTIONS), so a reply
    to either that is still uncertain/unfitting resolves to "unknown"."""
    normalised = _normalise(text)
    return any(marker in normalised for marker in _ALT_MARKERS.values())


def _is_confirm_question(text: str) -> bool:
    return _CONFIRM_MARKER in _normalise(text)


def previous_pending_field(chat_history: Optional[List[Dict[str, str]]]) -> Optional[str]:
    """
    Which Pain field the most recent Pain QUESTION (if any) asked about --
    used both for natural acknowledgment wording (what did the patient just
    answer?) and by the LAM orchestrator's active-Pain-follow-up routing
    check. Mirrors wound_care_agent.py::_previous_question_field, INCLUDING
    its bridging behaviour: this walks backward past any intervening
    assistant message that does NOT match a Pain question (e.g. a reply
    from a different domain agent after an off-topic detour) rather than
    stopping at the very first assistant message found -- so an
    unfinished Pain question can still be recognised as pending after a
    brief detour, letting the patient resume it. That bridging is
    deliberately what THIS function is for (short-answer ROUTING, and
    acknowledgment wording once a turn IS already established as a
    continuation).

    It is intentionally NOT what decides whether a given turn should be
    treated as a continuation of the active assessment for the purposes of
    resetting/reusing pain_state.py's bookkeeping (pending_field/
    ask_counts/cached structured facts/active-history boundary) -- see
    is_active_assessment_continuation() below for that STRICTER check.
    """
    for item in reversed(chat_history or []):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).lower().strip()
        if role not in {"assistant", "bot"}:
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        field_name = _field_from_question(content)
        if field_name:
            return field_name
    return None


def _most_recent_assistant_message_field(
    chat_history: Optional[List[Dict[str, str]]],
) -> Optional[str]:
    """
    Which Pain field the LITERAL most recent assistant message asked about
    -- unlike previous_pending_field() above, this stops at the very FIRST
    assistant message found (scanning backward), whether or not it matches
    a Pain question, and returns None if it doesn't match (or if there is
    no assistant message at all). Private helper for
    is_active_assessment_continuation() below.
    """
    for item in reversed(chat_history or []):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).lower().strip()
        if role not in {"assistant", "bot"}:
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        return _field_from_question(content)
    return None


def is_active_assessment_continuation(
    chat_history: Optional[List[Dict[str, str]]],
    pending_field: Optional[str],
    user_message: Optional[str] = None,
) -> bool:
    """
    Whether THIS turn is a genuine continuation of `pending_field` (the
    server-side PainSessionState's currently pending field) for the
    purposes of reusing that session's bookkeeping -- see
    pain_state.PainSessionState.start_new_assessment() and its callers
    (specialized_agents.py::PainSymptomsAgent.handle(), and
    lam/orchestrator.py's cumulative-safety step, both of which must agree
    on this SAME decision so the active-history boundary they each use
    stays in sync).

    Deliberately STRICTER than previous_pending_field()'s bridging
    behaviour: true only when the conversation's LITERAL most recent
    assistant message (not one found by skipping backward past an
    intervening non-Pain reply) itself asked exactly `pending_field`. An
    off-topic detour in between (e.g. "Can I climb stairs?" answered by
    Daily Activity) means the most recent assistant message is NOT a Pain
    question, so this returns False even though `pending_field` itself is
    technically still set on the session -- a LATER, genuinely fresh Pain
    complaint must not silently inherit that abandoned interview's cached
    facts/boundary just because the old pending field was never formally
    resolved. Returns False outright when `pending_field` is None (nothing
    was pending to continue -- covers both "brand-new patient" and "the
    previous assessment already concluded", since clear_pending() clears
    pending_field to None on conclusion).

    DETOUR TOLERANCE (only when `user_message` is supplied): after an
    off-topic detour ("Can I climb stairs?" answered by Daily Activity),
    the literal most recent assistant message is not a Pain question, yet
    the patient may now be answering the still-pending one ("8", "my
    calf"). In that case this returns True when the BRIDGING check
    (previous_pending_field, the same signal the orchestrator's
    _has_active_pain_followup uses to route the turn to Pain in the first
    place) still points at `pending_field` AND the message does not read
    as a brand-new pain complaint (see looks_like_new_complaint) -- a fresh
    complaint after a detour still starts a fresh assessment. Callers that
    omit `user_message` (the orchestrator's cumulative-safety step today)
    get the original strict behaviour unchanged.
    """
    if pending_field is None:
        return False
    if _most_recent_assistant_message_field(chat_history) == pending_field:
        return True
    if user_message is None:
        return False
    if previous_pending_field(chat_history) != pending_field:
        return False
    return not looks_like_new_complaint(user_message)


# ============================================================================
# DIRECT (OPPORTUNISTIC) EXTRACTION -- scans any message regardless of
# whether it was asked for, so a fact volunteered up front is captured and
# never re-asked.
# ============================================================================

_SUDDEN_WORDS = ("suddenly", "sudden", "all at once", "out of nowhere", "abruptly")
_GRADUAL_WORDS = ("gradually", "gradual", "slowly", "over time", "little by little", "built up", "building up")

_PAIN_SCALE_RE = re.compile(r"\b(10|[0-9])\s*(?:/|out of)\s*10\b")
_PAIN_LEVEL_RE = re.compile(
    r"\b(?:pain(?:\s+(?:is|level|score))?|rate it|score of)\D{0,10}?\b(10|[0-9])\b"
)
_BARE_NUMBER_RE = re.compile(r"\b(10|[0-9])\b")

# Deliberately NARROW for DIRECT/opportunistic extraction: a bare "knee" (or
# other joint already implied by the surgery itself) mention is too generic
# to count as pinpointing WHERE the pain is -- that is exactly the
# distinction the branch logic needs (calf vs "somewhere around the knee"),
# so only genuinely specific location wording is captured opportunistically
# here. A bare "knee"/"my knee"/etc. IS still accepted as a location value
# when LOCATION is the field actually pending (see
# _attribute_pending_answer) -- only opportunistic, un-asked-for extraction
# excludes it.
_LOCATION_TERMS = (
    "calf", "lower leg", "shin",
    "behind the knee", "behind my knee", "back of the knee",
    "thigh", "ankle", "hip", "incision", "surgical site",
    "groin", "buttock", "glute",
)

_CALF_TERMS = ("calf", "lower leg", "shin")
# THA-only sub-branch: thigh pain after a hip replacement gets the
# swelling/warmth questions (the agent only COLLECTS these; what they mean
# is SafetyTriageEngine's call, upstream).
_THIGH_TERMS = ("thigh",)

_WORSE_WORDS = ("worse", "worsening", "increasing", "more intense", "increased", "intensifying")
_BETTER_WORDS = ("better", "improving", "improved", "decreasing", "easing", "settling")
_SAME_WORDS = ("same", "unchanged", "no different", "about the same")

# Shared clause-splitting markers -- used both to resolve a contrasting
# trend statement ("worse earlier but better now") and to scope negation
# per-clause for combined boolean-ish fields (see _keyword_or_negative).
# Deliberately a small, fixed list, not a general clause parser.
_CLAUSE_SPLIT_MARKERS: Tuple[str, ...] = (
    " but ", " however ", " although ", " though ", " yet ",
    ", i just meant ", ", i meant ", ", i mean ",
    " i just meant ", " i meant ", " i mean ",
)


def _split_clauses(normalised: str) -> List[str]:
    clauses = [normalised]
    for marker in _CLAUSE_SPLIT_MARKERS:
        next_clauses: List[str] = []
        for clause in clauses:
            next_clauses.extend(clause.split(marker))
        clauses = next_clauses
    return [clause for clause in clauses if clause.strip()]

_SWELLING_WORDS = ("swelling", "swollen", "puffy", "puffiness")
_WARMTH_WORDS = ("warm", "warmer", "warmth", "hot", "red", "redness")
_STIFFNESS_WORDS = ("stiff", "stiffness", "hard to bend", "hard to move", "tight")
_NUMBNESS_WORDS = ("numb", "numbness", "tingling", "tingly", "weak", "weakness")
_FEVER_WORDS = ("fever", "feverish", "temperature", "chills", "sweaty", "hot and cold")
_MEDICATION_WORDS = ("medication", "medicine", "tablet", "pill", "dose", "painkiller")
_PAIN_CHARACTER_WORDS = ("sharp", "dull", "throbbing", "burning", "aching", "shooting", "stabbing")


def _extract_pain_score_direct(text: str) -> Optional[int]:
    normalised = _normalise(text)
    match = _PAIN_SCALE_RE.search(normalised) or _PAIN_LEVEL_RE.search(normalised)
    if not match:
        return None
    value = int(match.group(1))
    return value if 0 <= value <= 10 else None


# Category-based pain_score answers ("mild"/"moderate"/"severe") -- used
# when the patient answers the ALT_QUESTIONS[PAIN_SCORE] rephrase (or the
# primary question) with a rough range instead of an exact 0-10 number.
# Stored as the literal category STRING, never converted to a fabricated
# exact number -- see severity_bucket() and pain_integration._readable_value
# for how a category value is handled downstream without inventing false
# precision.
_PAIN_SCORE_CATEGORY_WORDS: Tuple[str, ...] = ("mild", "moderate", "severe")


def _extract_pain_score_category(text: str) -> Optional[str]:
    normalised = _normalise(text)
    for word in _PAIN_SCORE_CATEGORY_WORDS:
        if re.search(rf"\b{word}\b", normalised):
            return word
    return None


def _extract_onset_direct(text: str) -> Optional[str]:
    normalised = _normalise(text)
    if any(word in normalised for word in _SUDDEN_WORDS):
        return "sudden"
    if any(word in normalised for word in _GRADUAL_WORDS):
        return "gradual"
    return None


# Short-phrase location extraction -- prefers a small window like "behind
# my knee" or "my knee" over dumping the entire raw sentence into the
# location field (which otherwise duplicates verbatim into the final
# summary whenever the same sentence also matches another field's keyword,
# e.g. "I've had mild 3/10 aching behind my knee..." matching both LOCATION
# and PAIN_CHARACTERISTICS). Deliberately simple pattern matching, not a
# general parser -- falls back to the bare anchor word, and finally to the
# original trimmed text, when no tighter phrase can be formed.
#
# SPECIFICITY: split into two patterns, checked in order, rather than one
# combined alternation searched left-to-right. A relational/directional
# phrase ("behind the knee", "around the incision", ...) pins down WHERE
# on/around the joint the pain is, which is strictly more specific than a
# bare region mention ("my knee") -- so it must win regardless of which one
# happens to appear EARLIER in the sentence. Without this split, a message
# like "My knee pain is 6/10, it started suddenly behind the knee..." would
# report the generic "My knee" match simply because it comes first, losing
# the more specific "behind the knee" the patient actually gave. A message
# with only a generic mention (no relational phrase at all) is unaffected
# -- it still falls through to _LOCATION_GENERIC_PHRASE_RE exactly as
# before.
_LOCATION_SPECIFIC_PHRASE_RE = re.compile(
    r"\b((?:behind|in front of|around|near|in|on|at|toward|towards|below|above)"
    r"\s+(?:the|my)\s+(?:lower\s+)?\w+)\b",
    re.IGNORECASE,
)

_LOCATION_GENERIC_PHRASE_RE = re.compile(
    r"\b((?:the|my)\s+(?:calf|lower leg|shin|knee|thigh|ankle|hip|incision|surgical site|groin|buttock|glute))\b",
    re.IGNORECASE,
)

_LOCATION_ANCHOR_WORDS = _LOCATION_TERMS + ("knee", "thigh", "ankle", "hip")

# Words that make a reply a PLAUSIBLE answer to the LOCATION question even
# when it is not specific enough for opportunistic extraction (a bare
# "knee", "my leg", "the side"). Used only by answer_plausibly_fits().
_LOCATION_ANSWER_WORDS = _LOCATION_ANCHOR_WORDS + (
    "knee", "leg", "joint", "side", "front", "back", "top", "inside", "outside",
    "behind", "around", "above", "below", "under", "kneecap", "foot", "toes",
    "all over", "everywhere", "whole leg", "scar", "stitches", "staples",
    "somewhere else", "elsewhere",
)


def _extract_location_phrase(text: str) -> str:
    specific_match = _LOCATION_SPECIFIC_PHRASE_RE.search(text)
    if specific_match:
        return specific_match.group(1).strip()
    generic_match = _LOCATION_GENERIC_PHRASE_RE.search(text)
    if generic_match:
        return generic_match.group(1).strip()
    normalised = _normalise(text)
    for term in _LOCATION_ANCHOR_WORDS:
        if term in normalised:
            return term
    return text.strip()


def _extract_location_direct(text: str) -> Optional[str]:
    normalised = _normalise(text)
    if any(term in normalised for term in _LOCATION_TERMS):
        return _extract_location_phrase(text)
    return None


def _resolve_contrasting_trend(normalised: str) -> Optional[str]:
    """
    Small contrast/last-signal heuristic for a message that mentions BOTH
    worsening and improving language in the same breath (e.g. "worse
    earlier but better now") -- prefers whichever signal is in the LATER
    clause, since that is normally the CURRENT state. Not a general NLP
    parser: splits on a small fixed set of contrast conjunctions
    (_CLAUSE_SPLIT_MARKERS); if no such marker is present, falls back to
    whichever word occurs LAST in the raw text. Returns None only when it
    genuinely can't tell (both signals in the same, unsplittable clause).
    """
    clauses = _split_clauses(normalised)

    if len(clauses) > 1:
        tail = clauses[-1]
        tail_has_worse = any(word in tail for word in _WORSE_WORDS)
        tail_has_better = any(word in tail for word in _BETTER_WORDS)
        if tail_has_better and not tail_has_worse:
            return "improving"
        if tail_has_worse and not tail_has_better:
            return "worsening"

    last_worse_idx = max((normalised.rfind(w) for w in _WORSE_WORDS if w in normalised), default=-1)
    last_better_idx = max((normalised.rfind(w) for w in _BETTER_WORDS if w in normalised), default=-1)
    if last_worse_idx == last_better_idx:
        return None
    return "improving" if last_better_idx > last_worse_idx else "worsening"


def _extract_worsening_direct(text: str) -> Optional[str]:
    normalised = _normalise(text)

    has_worse = any(word in normalised for word in _WORSE_WORDS)
    has_better = any(word in normalised for word in _BETTER_WORDS)

    if has_worse and has_better:
        resolved = _resolve_contrasting_trend(normalised)
        if resolved is not None:
            return resolved
        # Genuinely ambiguous even after the contrast heuristic -- fall
        # through to the existing default priority below.

    if has_worse:
        return "worsening"
    if has_better:
        return "improving"
    if any(word in normalised for word in _SAME_WORDS):
        return "stable"
    return None


def _keyword_or_negative(text: str, words: Tuple[str, ...]) -> Optional[str]:
    """
    OPPORTUNISTIC (un-asked-for) extraction for one boolean-ish field that
    may be described by SEVERAL keywords (e.g. WARMTH_OR_REDNESS covers
    both "warm" and "red"; NUMBNESS_OR_WEAKNESS covers both "numb" and
    "weak"). A field is only ever touched when at least one of its OWN
    keywords is actually present -- everything else is left alone (returns
    None, i.e. "still unknown"), never defaulted to "no".

    COMBINED-FIELD RULE: any CLEARLY POSITIVE member makes the whole field
    present -- checked per word (via _word_is_negated) AND per clause (via
    _clause_is_negative_led, so "No redness, but it feels warm." doesn't
    let the negated "redness" suppress the positively-mentioned "warm" in
    a later clause). The field only resolves to "no" when every keyword
    actually mentioned is negated and none is positive -- e.g. "No
    numbness or weakness." negates both via one shared clause-level "no",
    while "No numbness, but I feel weak." keeps "weak" positive because it
    sits in its own, non-negated clause.

    Returns the bare matched keyword (not the whole raw sentence) on a
    positive match, so an opportunistic mention doesn't dump an entire
    unrelated sentence into the final summary (see also
    _extract_location_phrase / _extract_pain_characteristics_direct).
    """
    normalised = _normalise(text)
    if not normalised:
        return None

    positive_word: Optional[str] = None
    negative_word: Optional[str] = None

    for clause in _split_clauses(normalised):
        clause_negative_led = _clause_is_negative_led(clause)
        for word in words:
            if not _word_present(clause, word):
                continue
            if clause_negative_led or _word_is_negated(clause, word):
                if negative_word is None:
                    negative_word = word
            else:
                positive_word = word

    if positive_word is not None:
        return positive_word
    if negative_word is not None:
        return "no"
    return None


def _extract_pain_characteristics_direct(text: str) -> Optional[str]:
    normalised = _normalise(text)
    for word in _PAIN_CHARACTER_WORDS:
        if word in normalised:
            return word
    return None


def classify_location_branch(location_text: str, procedure: Optional[str] = None) -> str:
    """
    Which follow-up branch a stored `location` value implies. "calf" is the
    specialised branch for every procedure (associated-symptom questions);
    "thigh" is a THA-only branch (swelling/warmth questions for thigh pain
    after a hip replacement); everything else (knee, groin, buttock, hip,
    "somewhere else", ...) uses the standard joint-pain branch. Never
    returns a diagnosis label -- it only decides which QUESTIONS to ask.
    """
    normalised = _normalise(location_text)
    if any(term in normalised for term in _CALF_TERMS):
        return "calf"
    if str(procedure or "").strip().upper() == "THA" and any(
        term in normalised for term in _THIGH_TERMS
    ):
        return "thigh"
    return "joint"


def severity_bucket(pain_score: Any) -> str:
    """mild (0-3) / moderate (4-6) / severe (7-10) / unknown.

    Also accepts an already-categorical pain_score value ("mild"/
    "moderate"/"severe" -- see _extract_pain_score_category) and returns it
    directly, unchanged, rather than trying to coerce it to a number."""
    if isinstance(pain_score, str) and pain_score.strip().lower() in _PAIN_SCORE_CATEGORY_WORDS:
        return pain_score.strip().lower()
    try:
        score = int(pain_score)
    except (TypeError, ValueError):
        return "unknown"
    if score <= 3:
        return "mild"
    if score <= 6:
        return "moderate"
    return "severe"


def _direct_extraction_for_message(text: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    score = _extract_pain_score_direct(text)
    if score is not None:
        result[PAIN_SCORE] = score

    onset = _extract_onset_direct(text)
    if onset is not None:
        result[ONSET] = onset

    location = _extract_location_direct(text)
    if location is not None:
        result[LOCATION] = location

    worsening = _extract_worsening_direct(text)
    if worsening is not None:
        result[WORSENING_OR_IMPROVING] = worsening

    characteristics = _extract_pain_characteristics_direct(text)
    if characteristics is not None:
        result[PAIN_CHARACTERISTICS] = characteristics

    swelling = _keyword_or_negative(text, _SWELLING_WORDS)
    if swelling is not None:
        result[SWELLING] = swelling

    warmth = _keyword_or_negative(text, _WARMTH_WORDS)
    if warmth is not None:
        result[WARMTH_OR_REDNESS] = warmth

    stiffness = _keyword_or_negative(text, _STIFFNESS_WORDS)
    if stiffness is not None:
        result[STIFFNESS] = stiffness

    numbness = _keyword_or_negative(text, _NUMBNESS_WORDS)
    if numbness is not None:
        result[NUMBNESS_OR_WEAKNESS] = numbness

    fever = _keyword_or_negative(text, _FEVER_WORDS)
    if fever is not None:
        result[FEVER_OR_TEMPERATURE] = fever

    return result


def mentions_medication(text: str) -> bool:
    normalised = _normalise(text)
    return any(word in normalised for word in _MEDICATION_WORDS)


# ============================================================================
# CORRECTIONS -- narrow, cue-gated re-targeting of an already-established
# field (pain_score / onset / location -- the fields a correction most
# commonly needs to touch). Fixes: "Agent asks onset. User corrects the
# EARLIER pain_score instead ('Actually wait, it's more like a 7 than a
# 5.')" -- previously that whole sentence was blindly attributed to onset
# (the field actually pending) and the pain_score correction was silently
# lost. Deliberately requires BOTH a correction cue word AND concrete,
# field-specific evidence in the SAME message -- a bare "actually" with
# nothing interpretable in it never overwrites anything. Not a general
# NLP parser: three small, deterministic patterns for the three fields
# that matter most for a correction.
# ============================================================================

_CORRECTION_CUES = (
    "actually", "wait", "i meant", "i mean", "more like", "correction",
    "rather", "i said",
)


def _has_correction_cue(text: str) -> bool:
    normalised = _normalise(text)
    return any(cue in normalised for cue in _CORRECTION_CUES)


_CORRECTION_SCORE_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(r"more like\s+(?:an?\s+)?(10|[0-9])\b"),
    re.compile(r"\b(10|[0-9])\s*,?\s*not\s+(?:an?\s+)?(?:10|[0-9])\b"),
    re.compile(r"\bactually\W{0,15}?\b(10|[0-9])\b"),
)

_ONSET_TEMPORAL_WORDS = (
    "yesterday", "today", "this morning", "this afternoon", "this evening",
    "last night", "days ago", "a day ago", "hours ago",
)

# Slightly broader than _LOCATION_TERMS -- correction detection is already
# gated behind a correction cue, so a few generic positional words (safe
# ONLY in that narrow context, not for ordinary opportunistic extraction)
# are included so "it's really more on the side" is recognised as a
# location correction.
_LOCATION_CORRECTION_WORDS = _LOCATION_TERMS + (
    "side", "front", "back of", "top", "middle", "inside", "outside",
    "knee",
)


def _correction_score_value(text: str) -> Optional[int]:
    normalised = _normalise(text)
    for pattern in _CORRECTION_SCORE_PATTERNS:
        match = pattern.search(normalised)
        if match:
            value = int(match.group(1))
            if 0 <= value <= 10:
                return value
    return None


def _split_correction_tail(text: str) -> str:
    """The part of a correction sentence that states the NEW value, e.g.
    "I said X but Y" -> "Y" -- so the stored value reflects the correction,
    not the old value being quoted back. Falls back to the whole text when
    no clear split point exists."""
    lowered = text.lower()
    for splitter in (" but ", " rather "):
        idx = lowered.rfind(splitter)
        if idx != -1:
            return text[idx + len(splitter):].strip(" .")
    return text.strip()


def _detect_correction(text: str) -> Optional[Tuple[str, Any]]:
    """Returns (field_name, new_value) when `text` is a cue-gated correction
    to pain_score, onset, or location -- None otherwise."""
    if not _has_correction_cue(text):
        return None

    score = _correction_score_value(text)
    if score is not None:
        return PAIN_SCORE, score

    onset = _extract_onset_direct(text)
    if onset is not None:
        return ONSET, onset
    normalised = _normalise(text)
    for word in _ONSET_TEMPORAL_WORDS:
        if word in normalised:
            return ONSET, word

    tail = _split_correction_tail(text)
    if any(term in _normalise(tail) for term in _LOCATION_CORRECTION_WORDS):
        return LOCATION, _extract_location_phrase(tail)

    return None


# ============================================================================
# ANSWER PLAUSIBILITY -- does a reply plausibly answer the pending question?
#
# A reply that does NOT fit (no number for the pain score, no onset/location/
# trend wording, no yes/no for a yes/no question, or clearly a different
# topic) is never stored as the field's value. The field is re-asked ONCE
# with CLARIFY_QUESTIONS; if the second reply still does not fit (or is
# uncertain), the field is recorded as "unknown" and the interview moves on.
# Anything the reply DID volunteer for OTHER fields is still captured by the
# opportunistic direct-extraction pass -- a volunteered answer is never
# discarded just because the pending question went unanswered.
# ============================================================================

_AFFIRMATIVE_ANSWERS: Tuple[str, ...] = (
    "yes", "yeah", "yep", "yup", "ya", "sure", "correct", "right", "that's right",
    "thats right", "definitely", "absolutely", "i think so", "a little", "a bit",
    "a little bit", "slightly", "somewhat", "some", "kind of", "sort of", "mildly",
    "quite a bit", "very", "a lot", "still", "same", "about the same", "about that",
    "yes about that", "unchanged", "it is", "it does", "it did", "i have", "i did",
    "it helped", "helped", "it worked", "worked", "yes it is", "yes it does",
)

_NEGATIVE_ANSWERS: Tuple[str, ...] = (
    "no", "nope", "nah", "none", "not really", "nothing", "never", "not at all",
    "no change", "not that i've noticed", "not that i noticed", "not that i have noticed",
    "i don't think so", "i dont think so", "don't think so", "dont think so",
    "not much", "it isn't", "it isnt", "it didn't", "it didnt", "it doesn't",
    "it doesnt", "i haven't", "i havent", "didn't help", "didnt help",
    "hasn't helped", "hasnt helped", "did not help", "not helping", "no it didn't",
)

_WORD_NUMBERS: Dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

_YES_NO_FIELDS: Tuple[str, ...] = (
    SWELLING, WARMTH_OR_REDNESS, STIFFNESS, NUMBNESS_OR_WEAKNESS,
    FEVER_OR_TEMPERATURE, MEDICATION_EFFECT,
)

# Extra words that make a reply a plausible answer to a given field even
# when it carries no extractable value (the stored value is then the raw
# reply, exactly as before -- these lists only gate WHETHER it is stored).
_ONSET_ANSWER_WORDS: Tuple[str, ...] = _ONSET_TEMPORAL_WORDS + (
    "ago", "since", "after", "when i", "started", "began", "overnight", "woke up",
    "all at once", "out of nowhere", "bit by bit", "creeping", "crept",
    "progressively", "steadily", "quick", "quickly", "fast", "slow", "sudden", "gradual",
)
_TREND_ANSWER_WORDS: Tuple[str, ...] = _WORSE_WORDS + _BETTER_WORDS + _SAME_WORDS + (
    "different", "no change", "steady", "stable", "fluctuat", "comes and goes",
    "up and down", "on and off", "varies", "depends",
)
_FIELD_ANSWER_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    SWELLING: _SWELLING_WORDS + ("puffier", "bigger", "larger", "tight skin", "normal size"),
    WARMTH_OR_REDNESS: _WARMTH_WORDS + ("cool", "cold", "normal temperature", "pink", "colour", "color"),
    STIFFNESS: _STIFFNESS_WORDS + ("loose", "moves fine", "bend", "move", "flexible", "locked"),
    NUMBNESS_OR_WEAKNESS: _NUMBNESS_WORDS + ("pins and needles", "normal feeling", "strength", "strong", "gives way", "giving way"),
    FEVER_OR_TEMPERATURE: _FEVER_WORDS + ("degrees", "thermometer", "unwell", "shivery", "normal temp", "afebrile"),
    MEDICATION_EFFECT: (
        "help", "helped", "helps", "work", "worked", "works", "relief", "relieve",
        "eased", "ease", "took the edge", "edge off", "difference", "better", "worse",
        "nothing", "no effect", "didn't", "did not", "not really", "a little", "bit",
        "took", "taken", "haven't taken", "havent taken",
    ),
    PAIN_CHARACTERISTICS: _PAIN_CHARACTER_WORDS + (
        "ache", "achy", "tender", "sore", "pressure", "cramp", "cramping", "pulling",
        "tight", "electric", "pins", "like a", "feels like", "constant", "intermittent",
    ),
}

# A reply that is itself a QUESTION on another topic ("Can I shower?",
# "When can I drive?") is "clearly another topic" when it carries no
# field evidence at all.
_OFF_TOPIC_QUESTION_CUES: Tuple[str, ...] = (
    "can i ", "could i ", "should i ", "when can", "how do i", "how should i",
    "what about", "is it ok", "is it okay", "am i allowed", "do i need",
    "what time", "when should", "how long", "may i ",
)

_TEMPERATURE_READING_RE = re.compile(
    r"\b3[5-9](?:\.\d)?\b|\b4[0-2](?:\.\d)?\b|\b9[6-9](?:\.\d)?\b|\b10[0-5](?:\.\d)?\b"
)


def _is_affirmative_answer(text: str) -> bool:
    normalised = _normalise(text).strip(" .!")
    if not normalised:
        return False
    if normalised in _AFFIRMATIVE_ANSWERS:
        return True
    return bool(re.match(r"^(yes|yeah|yep|yup)\b", normalised))


def _is_offtopic_question(normalised: str) -> bool:
    if normalised.endswith("?"):
        return True
    return any(normalised.startswith(cue) for cue in _OFF_TOPIC_QUESTION_CUES)


def _parse_pain_score_answer(text: str) -> Optional[Any]:
    """An exact 0-10 number (digits or a number word) or a category word
    from a reply to the pain-score question; None when there is neither."""
    normalised = _normalise(text)
    match = _PAIN_SCALE_RE.search(normalised) or _BARE_NUMBER_RE.search(normalised)
    if match:
        value = int(match.group(1))
        if 0 <= value <= 10:
            return value
    for word, value in _WORD_NUMBERS.items():
        if _word_present(normalised, word):
            return value
    category = _extract_pain_score_category(text)
    if category is not None:
        return category
    return None


def answer_plausibly_fits(field_name: str, text: str) -> bool:
    """
    True when `text` is a plausible answer to the question for `field_name`
    -- a parser match, a yes/no for a yes/no question, a number where a
    number is expected, or (for the open-ended "describe it" question)
    anything that is not an off-topic question. An uncertain answer ("I
    don't know") is handled by the caller before this is consulted.
    """
    normalised = _normalise(text).strip()
    if not normalised:
        return False

    if field_name == PAIN_SCORE:
        return _parse_pain_score_answer(text) is not None

    if field_name == ONSET:
        if _extract_onset_direct(text) is not None:
            return True
        return any(word in normalised for word in _ONSET_ANSWER_WORDS)

    if field_name == LOCATION:
        return any(word in normalised for word in _LOCATION_ANSWER_WORDS)

    if field_name == WORSENING_OR_IMPROVING:
        if _extract_worsening_direct(text) is not None:
            return True
        return any(word in normalised for word in _TREND_ANSWER_WORDS)

    if field_name == PAIN_CHARACTERISTICS:
        if any(word in normalised for word in _FIELD_ANSWER_KEYWORDS[PAIN_CHARACTERISTICS]):
            return True
        return not _is_offtopic_question(normalised)

    if field_name in _YES_NO_FIELDS:
        if _is_affirmative_answer(normalised) or _is_negative_answer(normalised):
            return True
        if any(word in normalised for word in _FIELD_ANSWER_KEYWORDS.get(field_name, ())):
            return True
        if field_name == FEVER_OR_TEMPERATURE and _TEMPERATURE_READING_RE.search(normalised):
            return True
        return False

    return not _is_offtopic_question(normalised)


def _concrete_value_if_any(field_name: str, text: str) -> Optional[Any]:
    """A concrete, parser-backed value hidden inside an otherwise UNCERTAIN
    reply ("not sure, maybe a 6" -> 6; "I think it's getting worse, not
    sure" -> "worsening"). None when the reply carries nothing concrete, in
    which case the caller treats it as genuinely uncertain."""
    if field_name == PAIN_SCORE:
        return _parse_pain_score_answer(text)
    if field_name == ONSET:
        return _extract_onset_direct(text)
    if field_name == WORSENING_OR_IMPROVING:
        return _extract_worsening_direct(text)
    if field_name == LOCATION:
        normalised = _normalise(text)
        if any(term in normalised for term in _LOCATION_ANCHOR_WORDS):
            return _extract_location_phrase(text)
        return None
    if field_name in _YES_NO_FIELDS:
        normalised = _normalise(text)
        # Only an UNAMBIGUOUS leading yes/no counts; "not sure if it's
        # swollen" must stay uncertain.
        if re.match(r"^(yes|yeah|yep|yup)\b", normalised):
            return "yes"
        if re.match(r"^(no|nope|nah)\b", normalised) and not _is_uncertain_answer(normalised[:12]):
            return "no"
        return None
    return None


# ============================================================================
# NEW-COMPLAINT DETECTION -- used ONLY to decide, after an off-topic detour,
# whether a message resumes the pending Pain question (a bare answer) or
# opens a fresh Pain complaint (a full sentence describing pain somewhere).
# ============================================================================

_COMPLAINT_CUES: Tuple[str, ...] = (
    "hurt", "hurts", "hurting", "ache", "aches", "aching", "sore", "soreness",
    "painful", "pain in", "pain is", "pain has", "pain started", "pain got",
    "started hurting", "has started", "flared", "flare", "throbbing in",
    "stabbing in", "burning in", "my pain",
)


def looks_like_new_complaint(text: str) -> bool:
    """A full sentence describing pain (location/pain word + complaint cue,
    four or more words), as opposed to a bare answer like "8", "my calf",
    "yes it's swollen" or "suddenly". Replies that OPEN with a yes/no are
    never treated as a new complaint."""
    normalised = _normalise(text).strip(" .!")
    if not normalised:
        return False
    if _is_affirmative_answer(normalised) or _is_negative_answer(normalised):
        return False
    if len(normalised.split()) < 4:
        return False
    if not any(cue in normalised for cue in _COMPLAINT_CUES):
        return False
    return "pain" in normalised or any(word in normalised for word in _LOCATION_ANSWER_WORDS)


# ============================================================================
# PENDING-FIELD ATTRIBUTION (question/answer pairs) -- mirrors
# wound_care_agent.py::_extract_answer_pairs. A short reply like "8" or
# "suddenly" is attributed to whatever field the PRECEDING assistant
# question was about, regardless of whether the reply's own wording would
# have matched direct-extraction keywords -- PROVIDED it plausibly answers
# that question at all (see answer_plausibly_fits).
# ============================================================================

def _attribute_pending_answer(field_name: str, text: str) -> Optional[Any]:
    """Convert a raw reply into a stored value for `field_name`, once we
    already know (from the preceding assistant question) which field this
    reply answers AND that it plausibly fits. Falls back to the raw trimmed
    text when no field-specific parser applies."""
    stripped = text.strip()
    if not stripped:
        return None

    if field_name == PAIN_SCORE:
        value = _parse_pain_score_answer(text)
        if value is None:
            return None
        return str(value) if isinstance(value, int) else value

    if field_name == ONSET:
        direct = _extract_onset_direct(text)
        return direct if direct is not None else stripped

    if field_name == LOCATION:
        return _extract_location_phrase(text)

    if field_name == WORSENING_OR_IMPROVING:
        direct = _extract_worsening_direct(text)
        return direct if direct is not None else stripped

    if field_name in _YES_NO_FIELDS:
        normalised = _normalise(text).strip(" .!")
        if normalised in _AFFIRMATIVE_ANSWERS and normalised not in (
            "still", "same", "about the same", "unchanged", "about that",
        ):
            return "yes"
        if normalised in _NEGATIVE_ANSWERS:
            return "no"
        return stripped

    # Every remaining field: accept the raw answer verbatim (still subject
    # to the negative-answer/uncertainty handling one level up).
    return stripped


def _detour_user_indices(history: List[Dict[str, str]]) -> Set[int]:
    """
    Indices of USER turns that belong to an off-topic DETOUR inside the
    active Pain assessment: a user message whose very next assistant reply
    is NOT a Pain question (another agent answered it -- e.g. "Can I climb
    stairs?" -> Daily Activity). Such a turn is skipped by BOTH the
    pending-answer attribution (it must not consume the pending Pain
    question) and the opportunistic direct-extraction pass (a wound/activity
    message must not seed Pain facts). The CURRENT message (last entry, no
    assistant reply after it yet) is never a detour.
    """
    detours: Set[int] = set()
    last_user_idx: Optional[int] = None
    for idx, item in enumerate(history):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).lower().strip()
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        if role == "user":
            last_user_idx = idx
            continue
        if role in {"assistant", "bot"}:
            if last_user_idx is not None and _field_from_question(content) is None:
                detours.add(last_user_idx)
            last_user_idx = None
    return detours


class AnswerPairs:
    """Result of _extract_answer_pairs_detailed() -- see that function."""

    __slots__ = (
        "paired", "needs_alt", "needs_clarify", "confirm_declined",
        "detour_indices", "confirm_reply_indices", "paired_by_index",
    )

    def __init__(self) -> None:
        self.paired: Dict[str, Any] = {}
        self.needs_alt: Set[str] = set()
        self.needs_clarify: Set[str] = set()
        self.confirm_declined: Set[str] = set()
        self.detour_indices: Set[int] = set()
        # The same attributions keyed by the USER-turn index they came from,
        # so build_assessment_detailed() can merge attributed answers and
        # opportunistic extraction in TURN ORDER (a later explicit "7 out of
        # 10" must beat an earlier confirmed 6, whichever pass produced it).
        self.paired_by_index: Dict[int, Dict[str, Any]] = {}
        # User turns that answered the memory CONFIRMATION question with a
        # plain yes/"about the same" -- "the same" there refers to the
        # logged SCORE, so it must not be read as a trend answer.
        self.confirm_reply_indices: Set[int] = set()

    def _resolve(self, field_name: str, value: Any, idx: Optional[int] = None) -> None:
        self.paired[field_name] = value
        self.needs_alt.discard(field_name)
        self.needs_clarify.discard(field_name)
        self.confirm_declined.discard(field_name)
        if idx is not None:
            self.paired_by_index.setdefault(idx, {})[field_name] = value


def _extract_answer_pairs_detailed(
    chat_history: Optional[List[Dict[str, str]]],
    current_message: str,
) -> AnswerPairs:
    """
    Walk the conversation as question/answer pairs:

      - an UNCERTAIN answer ("I don't know") to a FIRST-phrasing question
        puts the field in `needs_alt` (ask the simplified ALT rephrase);
        an uncertain answer to any SECOND ask records "unknown";
      - an answer that does NOT plausibly fit the question (see
        answer_plausibly_fits) is never stored: a first such answer puts
        the field in `needs_clarify` (ask CLARIFY_QUESTIONS once); a second
        records "unknown";
      - a reply to the memory CONFIRMATION question ("Your log says 6/10
        ... still about that?") resolves to the logged value on a yes, to
        the stated number/category when the patient gives one, and
        otherwise (no / anything else) to `confirm_declined` so the normal
        pain-score question is asked next;
      - user turns inside an off-topic detour are skipped entirely.
    """
    history = list(chat_history or [])
    if current_message.strip():
        history = history + [{"role": "user", "content": current_message.strip()}]

    result = AnswerPairs()
    result.detour_indices = _detour_user_indices(history)

    pending_field: Optional[str] = None
    pending_is_second = False
    pending_confirm_value: Optional[int] = None

    for idx, item in enumerate(history):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).lower().strip()
        content = str(item.get("content", "")).strip()
        if not content:
            continue

        if role in {"assistant", "bot"}:
            field_name = _field_from_question(content)
            if field_name:
                pending_field = field_name
                pending_is_second = _is_alt_question(content)
                pending_confirm_value = _confirm_value_from_question(content)
            continue

        if role != "user":
            continue
        if idx in result.detour_indices:
            # Detour turn (answered by another agent) -- leave the pending
            # Pain question open so a later bare answer still resumes it.
            continue
        if not pending_field:
            continue

        if pending_confirm_value is not None:
            concrete = _parse_pain_score_answer(content)
            if concrete is not None and not _is_uncertain_answer(content):
                result._resolve(pending_field, str(concrete) if isinstance(concrete, int) else concrete, idx)
            elif _is_affirmative_answer(content):
                result._resolve(pending_field, str(pending_confirm_value), idx)
                result.confirm_reply_indices.add(idx)
            else:
                result.confirm_declined.add(pending_field)
        elif _is_uncertain_answer(content):
            concrete = _concrete_value_if_any(pending_field, content)
            if concrete is not None:
                result._resolve(pending_field, str(concrete) if isinstance(concrete, int) else concrete, idx)
            elif pending_is_second:
                result._resolve(pending_field, "unknown", idx)
            else:
                result.needs_alt.add(pending_field)
        else:
            correction = _detect_correction(content)
            if correction is not None and correction[0] != pending_field:
                # A cue-gated correction to a DIFFERENT, already-established
                # field (e.g. correcting pain_score while onset is pending)
                # -- do NOT consume the pending question with it. The
                # correction itself is applied in build_assessment()'s
                # corrections pass; the pending question is re-asked.
                pass
            elif not answer_plausibly_fits(pending_field, content):
                if pending_is_second:
                    result._resolve(pending_field, "unknown", idx)
                else:
                    result.needs_clarify.add(pending_field)
            else:
                value = _attribute_pending_answer(pending_field, content)
                if value is not None:
                    result._resolve(pending_field, value, idx)
                elif pending_is_second:
                    result._resolve(pending_field, "unknown", idx)
                else:
                    result.needs_clarify.add(pending_field)

        pending_field = None
        pending_is_second = False
        pending_confirm_value = None

    return result


def _extract_answer_pairs(
    chat_history: Optional[List[Dict[str, str]]],
    current_message: str,
) -> Tuple[Dict[str, Any], Set[str]]:
    """Backward-compatible view: (paired_facts, needs_second_ask), where
    needs_second_ask is the union of the uncertain (ALT) and unfitting
    (CLARIFY) sets -- both mean "ask this field once more, differently"."""
    detailed = _extract_answer_pairs_detailed(chat_history, current_message)
    return detailed.paired, set(detailed.needs_alt) | set(detailed.needs_clarify)


# ============================================================================
# STRUCTURED FIELD SEEDING -- existing API-supplied fields (pain_score,
# pain_characteristics, swelling_description, temperature_c) must never be
# re-asked once supplied. Mapped onto this module's field names.
# ============================================================================

def seed_from_structured_fields(
    *,
    pain_score: Optional[int] = None,
    pain_characteristics: Optional[str] = None,
    swelling_description: Optional[str] = None,
    temperature_c: Optional[float] = None,
) -> Dict[str, Any]:
    seed: Dict[str, Any] = {}
    if pain_score is not None:
        seed[PAIN_SCORE] = pain_score
    if pain_characteristics:
        seed[PAIN_CHARACTERISTICS] = pain_characteristics.strip()
    if swelling_description:
        seed[SWELLING] = swelling_description.strip()
    if temperature_c is not None:
        seed[FEVER_OR_TEMPERATURE] = f"{temperature_c}°C reported"
    return seed


# ============================================================================
# BUILD ASSESSMENT
# ============================================================================

class AssessmentView:
    """Everything build_assessment_detailed() knows about the active Pain
    conversation. `needs_alt` / `needs_clarify` / `confirm_declined` are
    disjoint from the keys of `assessment` (a resolved field is never also
    pending a re-ask)."""

    __slots__ = ("assessment", "needs_alt", "needs_clarify", "confirm_declined", "detour_indices")

    def __init__(
        self,
        assessment: Dict[str, Any],
        needs_alt: Set[str],
        needs_clarify: Set[str],
        confirm_declined: Set[str],
        detour_indices: Optional[Set[int]] = None,
    ) -> None:
        self.assessment = assessment
        self.needs_alt = needs_alt
        self.needs_clarify = needs_clarify
        self.confirm_declined = confirm_declined
        # Indices (into chat_history + [current message]) of user turns that
        # belong to an off-topic detour -- see _detour_user_indices().
        self.detour_indices: Set[int] = set(detour_indices or ())

    @property
    def needs_second_ask(self) -> Set[str]:
        return set(self.needs_alt) | set(self.needs_clarify)


# The operated joint's bare name is too generic to count as pinpointing
# WHERE the pain is (for a TKA patient "knee" is already excluded from
# opportunistic extraction -- see _LOCATION_TERMS). "hip" stays in
# _LOCATION_TERMS because for a KNEE patient hip pain IS a specific place;
# for a HIP patient it is the operated joint, so an opportunistic bare
# "hip" is dropped and the location question (groin / thigh / buttock /
# calf / somewhere else) is asked. A bare "hip" given AS THE ANSWER to that
# question is still accepted (pending-answer attribution is unaffected).
_GENERIC_JOINT_LOCATIONS: Dict[str, Tuple[str, ...]] = {
    "THA": ("hip", "my hip", "the hip", "in my hip", "in the hip", "hip itself"),
    "TKA": ("knee", "my knee", "the knee", "in my knee", "in the knee", "knee itself"),
}


def _is_generic_joint_location(value: Any, procedure: Optional[str]) -> bool:
    generic = _GENERIC_JOINT_LOCATIONS.get(str(procedure or "").strip().upper())
    if not generic:
        return False
    return _normalise(str(value)) in generic


def build_assessment_detailed(
    chat_history: Optional[List[Dict[str, str]]],
    current_message: str,
    *,
    seed_facts: Optional[Dict[str, Any]] = None,
    cached_facts: Optional[Dict[str, Any]] = None,
    procedure: Optional[str] = None,
) -> AssessmentView:
    """
    Reconstruct everything currently known for this Pain conversation:
        1. opportunistic direct extraction from every user message in the
           conversation (catches facts volunteered without being asked --
           this is also what makes a MULTI-SLOT reply like "7 out of 10,
           started suddenly yesterday in the calf" fill three fields at
           once), skipping user turns inside an off-topic detour
        2. pending-field (question/answer pair) attribution, which takes
           priority over (1) for whichever field it resolves -- but only
           when the reply plausibly answers the pending question
        3. cue-gated corrections (see _detect_correction), applied in
           chronological order so a LATER correction always overrides an
           earlier value
        4. `cached_facts` -- a FALLBACK BASELINE only, filling ONLY the
           fields steps 1-3 left unresolved (see pain_state.py's
           structured-fact cache)
        5. `seed_facts` -- the CURRENT request's own structured API fields,
           which always take top priority
    """
    history = list(chat_history or [])
    if current_message.strip():
        history = history + [{"role": "user", "content": current_message.strip()}]

    pairs = _extract_answer_pairs_detailed(chat_history, current_message)

    assessment: Dict[str, Any] = {}
    for idx, item in enumerate(history):
        if not isinstance(item, dict):
            continue
        if str(item.get("role", "")).lower().strip() != "user":
            continue
        if idx in pairs.detour_indices:
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        for field_name, value in _direct_extraction_for_message(content).items():
            if field_name == WORSENING_OR_IMPROVING and idx in pairs.confirm_reply_indices:
                continue
            if field_name == LOCATION and _is_generic_joint_location(value, procedure):
                continue
            assessment[field_name] = value
        # Pending-answer attribution for THIS turn wins over the same
        # turn's opportunistic extraction -- but a LATER turn's explicit
        # statement still overrides an earlier attributed answer (turn
        # order, not pass order, decides).
        for field_name, value in pairs.paired_by_index.get(idx, {}).items():
            assessment[field_name] = value

    needs_alt = set(pairs.needs_alt)
    needs_clarify = set(pairs.needs_clarify)
    confirm_declined = set(pairs.confirm_declined)

    for idx, item in enumerate(history):
        if not isinstance(item, dict):
            continue
        if str(item.get("role", "")).lower().strip() != "user":
            continue
        if idx in pairs.detour_indices:
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        correction = _detect_correction(content)
        if correction is not None:
            field_name, value = correction
            assessment[field_name] = value

    if cached_facts:
        for field_name, value in cached_facts.items():
            # Fills ONLY a field still missing after direct extraction/
            # pending-answer/corrections -- a value already established
            # from the conversation itself is never overwritten by a cached
            # (possibly stale) structured fact.
            if field_name not in assessment:
                assessment[field_name] = value

    if seed_facts:
        assessment.update(seed_facts)

    for pending_set in (needs_alt, needs_clarify, confirm_declined):
        for field_name in list(pending_set):
            if field_name in assessment:
                pending_set.discard(field_name)

    if PAIN_SCORE in assessment and assessment[PAIN_SCORE] != "unknown":
        try:
            assessment[PAIN_SCORE] = int(assessment[PAIN_SCORE])
        except (TypeError, ValueError):
            pass

    return AssessmentView(assessment, needs_alt, needs_clarify, confirm_declined, pairs.detour_indices)


def build_assessment(
    chat_history: Optional[List[Dict[str, str]]],
    current_message: str,
    *,
    seed_facts: Optional[Dict[str, Any]] = None,
    cached_facts: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Set[str]]:
    """Backward-compatible (assessment, needs_second_ask) view of
    build_assessment_detailed() -- see that function for the precedence
    contract. The second element is the union of fields awaiting the ALT
    rephrase (uncertain answer) and fields awaiting the CLARIFY re-ask
    (reply did not fit the question)."""
    view = build_assessment_detailed(
        chat_history, current_message, seed_facts=seed_facts, cached_facts=cached_facts,
    )
    return view.assessment, view.needs_second_ask


# ============================================================================
# NEXT-INFORMATION DECISION (pure, deterministic, genuinely adaptive)
# ============================================================================

def select_next_field(
    assessment: Dict[str, Any],
    *,
    medication_mentioned: bool = False,
    procedure: Optional[str] = None,
) -> Optional[str]:
    """
    Decide the single most useful next field to ask about, given what is
    already known. NOT a fixed linear order past the three core fields --
    branches on location and severity, and stops as soon as the current
    branch has enough information rather than marching through every
    possible field.

    `procedure` ("TKA"/"THA"/"GEN"/None) only changes WHICH questions are
    collected after the three core fields; it never decides a triage level
    (SafetyTriageEngine does that, upstream, deterministically):

      - TKA / default: calf branch (swelling -> warmth -> numbness, + fever
        when moderate/severe); joint branch (trend, + stiffness when severe).
      - THA: calf branch as above; THIGH branch (swelling -> warmth, + trend
        when moderate/severe); hip-joint branch (groin/buttock/hip/other:
        trend when moderate/severe, + stiffness and numbness/weakness when
        severe -- the agent collects these so the record is complete; what
        they mean is upstream's call).
    """
    for field_name in REQUIRED_FIELDS:
        if field_name not in assessment:
            return field_name

    is_tha = str(procedure or "").strip().upper() == "THA"
    branch = classify_location_branch(str(assessment.get(LOCATION, "")), procedure)
    severity = severity_bucket(assessment.get(PAIN_SCORE))

    if branch == "calf":
        for field_name in _CALF_BRANCH_FIELDS:
            if field_name not in assessment:
                return field_name
        if severity in ("moderate", "severe") and FEVER_OR_TEMPERATURE not in assessment:
            return FEVER_OR_TEMPERATURE
    elif branch == "thigh":
        # THA-only thigh branch.
        for field_name in (SWELLING, WARMTH_OR_REDNESS):
            if field_name not in assessment:
                return field_name
        if severity in ("moderate", "severe") and WORSENING_OR_IMPROVING not in assessment:
            return WORSENING_OR_IMPROVING
    else:
        # Standard joint-pain branch -- deliberately does NOT launch the
        # calf-specific swelling/warmth/numbness sequence for ordinary
        # knee/thigh/hip pain.
        if severity == "severe":
            if WORSENING_OR_IMPROVING not in assessment:
                return WORSENING_OR_IMPROVING
            if STIFFNESS not in assessment:
                return STIFFNESS
            if is_tha and NUMBNESS_OR_WEAKNESS not in assessment:
                return NUMBNESS_OR_WEAKNESS
        elif severity == "moderate":
            if WORSENING_OR_IMPROVING not in assessment:
                return WORSENING_OR_IMPROVING
        # mild severity: the three core fields are enough on their own --
        # do not add extra questions for ordinary, low-severity pain.

    if medication_mentioned and MEDICATION_EFFECT not in assessment:
        return MEDICATION_EFFECT

    return None


def is_complete(
    assessment: Dict[str, Any],
    *,
    medication_mentioned: bool = False,
    procedure: Optional[str] = None,
) -> bool:
    return select_next_field(
        assessment, medication_mentioned=medication_mentioned, procedure=procedure,
    ) is None


def estimate_remaining_questions(
    assessment: Dict[str, Any],
    *,
    medication_mentioned: bool = False,
    procedure: Optional[str] = None,
) -> int:
    """
    How many more questions the interview needs from here, INCLUDING the
    one about to be asked, assuming every answer stays on the current
    branch. Computed by replaying select_next_field() with neutral
    placeholders, so it is a LOWER BOUND: an answer that opens a new branch
    (a calf location, a severe score) can add questions. Used only for the
    patient-facing progress indicator, never for any decision.
    """
    simulated = dict(assessment)
    count = 0
    while count < 20:
        field_name = select_next_field(
            simulated, medication_mentioned=medication_mentioned, procedure=procedure,
        )
        if field_name is None:
            break
        count += 1
        simulated[field_name] = "unknown"
    return count


# Fields whose ANSWER decides which branch the interview takes -- the
# progress indicator stays deliberately vague while one of these is open.
BRANCH_DECIDING_FIELDS: Tuple[str, ...] = (PAIN_SCORE, LOCATION)


# ============================================================================
# CUMULATIVE TRIAGE TEXT -- multi-turn safety support.
#
# IMPORTANT: this function only SYNTHESIZES TEXT from already-established
# patient-reported facts. It does NOT itself decide GREEN/YELLOW/RED, does
# NOT duplicate or approximate any SafetyTriageEngine rule (DVT/PE
# thresholds, compound escalation, etc.), and does NOT call
# SafetyTriageEngine. It exists solely so the orchestrator can hand
# SafetyTriageEngine -- the ONLY authority for a triage level -- a single
# string that combines facts the patient supplied across several turns,
# the same way it would already see them if the patient had said everything
# in one message. See lam/orchestrator.py's cumulative-safety step for the
# actual evaluate() call and severity comparison.
# ============================================================================

def build_cumulative_triage_text(
    chat_history: Optional[List[Dict[str, str]]],
    current_message: str,
    *,
    pain_score: Optional[int] = None,
    swelling_description: Optional[str] = None,
    cached_facts: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Reconstruct the accumulated Pain assessment -- chat_history + current
    message, PLUS the structured/API fields that are themselves genuine
    patient-reported facts and are otherwise invisible to cumulative safety
    (`pain_score`, `swelling_description`) -- and render it as a short,
    neutral fact list SafetyTriageEngine can evaluate exactly like a
    single consolidated message, e.g.:

        "pain 8/10; sudden onset; location my calf; swelling present"

    `pain_score`/`swelling_description` (the CURRENT request's own
    structured fields, if supplied) are seeded via the SAME
    seed_from_structured_fields()/build_assessment() path
    PainSymptomsAgent.handle() already uses, and always take top priority.

    `cached_facts` (typically pain_state.PainSessionState.
    cached_structured_facts() for this patient, read by the caller -- this
    function does not know about pain_state.py, keeping the
    supplemental-cache concern entirely in the orchestrator/pain_state
    layer, not duplicated here) is the FALLBACK BASELINE for a field
    neither the conversation NOR the current request resolves -- this is
    exactly what lets an EARLIER turn's structured pain_score survive onto
    a LATER turn that doesn't resupply it ("My pain suddenly got much
    worse today" + pain_score=8, then "my calf" with pain_score omitted --
    cumulative safety must still see the 8), while a later free-text
    correction ("Actually wait, it's more like a 5.") still overrides it
    (see build_assessment()'s precedence contract for the exact ordering).

    Deliberately EXCLUDES `temperature_c` and `pain_characteristics` (both
    from the current request AND from any cache): temperature_c already
    has its own direct, per-turn path straight into
    SafetyTriageEngine.evaluate() (see lam/orchestrator.py) -- unlike a
    text fact reconstructed from conversation, it can never "arrive in
    pieces" across turns, so folding it in here too would only risk
    double-applying the same threshold. pain_characteristics (sharp/dull/
    throbbing/...) has no bearing on any SafetyTriageEngine rule.

    Returns "" when nothing is known yet (caller should skip the extra
    evaluate() call in that case). A field whose value is "unknown" (the
    patient was genuinely unable to say, even after a simplified rephrase)
    or a negative answer ("no", "not really", ...) is never rendered as
    "present" -- this must never manufacture a symptom the patient did not
    actually report.
    """
    seed_facts = seed_from_structured_fields(
        pain_score=pain_score, swelling_description=swelling_description,
    )
    assessment, _ = build_assessment(
        chat_history, current_message,
        seed_facts=seed_facts or None,
        cached_facts=cached_facts,
    )

    if not assessment:
        return ""

    parts: List[str] = []

    def _present(field_name: str) -> bool:
        value = assessment.get(field_name)
        if value is None or value == "unknown":
            return False
        return not _is_negative_answer(str(value))

    if _present(PAIN_SCORE):
        score_value = assessment[PAIN_SCORE]
        if isinstance(score_value, (int, float)):
            parts.append(f"pain {score_value}/10")
        else:
            # Category value ("mild"/"moderate"/"severe") -- never state a
            # fabricated exact "/10" number the patient didn't give.
            parts.append(f"pain level {score_value}")

    if _present(ONSET):
        onset_value = assessment[ONSET]
        if onset_value == "sudden":
            parts.append("sudden onset")
        elif onset_value == "gradual":
            parts.append("gradual onset")
        else:
            parts.append(f"onset {onset_value}")

    if _present(LOCATION):
        parts.append(f"location {assessment[LOCATION]}")

    if _present(SWELLING):
        parts.append("swelling present")

    if _present(WARMTH_OR_REDNESS):
        parts.append("warmth/redness present")

    if _present(STIFFNESS):
        parts.append("stiffness present")

    if _present(NUMBNESS_OR_WEAKNESS):
        parts.append("numbness/weakness present")

    if _present(FEVER_OR_TEMPERATURE):
        parts.append("fever/temperature concern reported")

    if assessment.get(WORSENING_OR_IMPROVING) == "worsening":
        parts.append("worsening")

    return "; ".join(parts)
