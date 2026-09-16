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
    STIFFNESS: "does the joint feel stiff",
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
    normalised = _normalise(text)
    if normalised in ("no", "nope", "none", "not really", "nothing", "never"):
        return True
    return normalised.startswith(("no ", "nope ", "not really ", "none ", "nothing "))


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
    return None


def _is_alt_question(text: str) -> bool:
    normalised = _normalise(text)
    return any(marker in normalised for marker in _ALT_MARKERS.values())


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
    """
    if pending_field is None:
        return False
    return _most_recent_assistant_message_field(chat_history) == pending_field


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
)

_CALF_TERMS = ("calf", "lower leg", "shin")

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
_LOCATION_PHRASE_RE = re.compile(
    r"\b((?:behind|in front of|around|near|in|on|at|toward|towards|below|above)"
    r"\s+(?:the|my)\s+(?:lower\s+)?\w+"
    r"|(?:the|my)\s+(?:calf|lower leg|shin|knee|thigh|ankle|hip|incision|surgical site))\b",
    re.IGNORECASE,
)

_LOCATION_ANCHOR_WORDS = _LOCATION_TERMS + ("knee", "thigh", "ankle", "hip")


def _extract_location_phrase(text: str) -> str:
    match = _LOCATION_PHRASE_RE.search(text)
    if match:
        return match.group(1).strip()
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


def classify_location_branch(location_text: str) -> str:
    """
    Which follow-up branch a stored `location` value implies. "calf" is the
    only currently-implemented specialised branch (DVT-adjacent associated
    symptoms) -- everything else (knee, thigh, hip, "somewhere else", ...)
    uses the standard joint-pain branch. Never returns a diagnosis label.
    """
    normalised = _normalise(location_text)
    if any(term in normalised for term in _CALF_TERMS):
        return "calf"
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
# PENDING-FIELD ATTRIBUTION (question/answer pairs) -- mirrors
# wound_care_agent.py::_extract_answer_pairs. A short reply like "8" or
# "suddenly" is attributed to whatever field the PRECEDING assistant
# question was about, regardless of whether the reply's own wording would
# have matched direct-extraction keywords.
# ============================================================================

def _attribute_pending_answer(field_name: str, text: str) -> Optional[str]:
    """Convert a raw reply into a stored value for `field_name`, once we
    already know (from the preceding assistant question) which field this
    reply answers. Falls back to the raw trimmed text when no
    field-specific parser applies -- the point of pending-field attribution
    is that we don't need the reply to contain a recognisable keyword."""
    stripped = text.strip()
    if not stripped:
        return None

    if field_name == PAIN_SCORE:
        match = _PAIN_SCALE_RE.search(_normalise(text)) or _BARE_NUMBER_RE.search(_normalise(text))
        if match:
            value = int(match.group(1))
            if 0 <= value <= 10:
                return str(value)
        # No exact number given -- accept a rough category ("mild"/
        # "moderate"/"severe") instead of looping on the same question.
        # Never invented as a fabricated exact score (see severity_bucket
        # and pain_integration._readable_value for how this is rendered).
        category = _extract_pain_score_category(text)
        if category is not None:
            return category
        return None

    if field_name == ONSET:
        direct = _extract_onset_direct(text)
        return direct if direct is not None else stripped

    if field_name == LOCATION:
        return _extract_location_phrase(text)

    if field_name == WORSENING_OR_IMPROVING:
        direct = _extract_worsening_direct(text)
        return direct if direct is not None else stripped

    # Every remaining field: accept the raw answer verbatim (still subject
    # to the negative-answer/uncertainty handling one level up).
    return stripped


def _extract_answer_pairs(
    chat_history: Optional[List[Dict[str, str]]],
    current_message: str,
) -> Tuple[Dict[str, Any], Set[str]]:
    """
    Returns (paired_facts, needs_alt) -- see wound_care_agent.py's identical
    contract. needs_alt holds fields where the patient answered "I don't
    know" to the FIRST-phrasing question; those are left OUT of
    paired_facts so the caller re-asks with ALT_QUESTIONS instead of
    accepting uncertainty as a real value. A SECOND uncertain answer (to the
    alt phrasing) is recorded as the literal string "unknown".
    """
    history = list(chat_history or [])
    if current_message.strip():
        history = history + [{"role": "user", "content": current_message.strip()}]

    paired: Dict[str, Any] = {}
    needs_alt: Set[str] = set()

    pending_field: Optional[str] = None
    pending_is_alt = False

    for item in history:
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
                pending_is_alt = _is_alt_question(content)
            continue

        if role == "user" and pending_field:
            if _is_uncertain_answer(content):
                if pending_is_alt:
                    paired[pending_field] = "unknown"
                    needs_alt.discard(pending_field)
                else:
                    needs_alt.add(pending_field)
            else:
                correction = _detect_correction(content)
                if correction is not None and correction[0] != pending_field:
                    # This message is a cue-gated correction to a DIFFERENT,
                    # already-established field (e.g. correcting pain_score
                    # while onset is what's actually pending) -- do NOT
                    # consume the pending question with it. The correction
                    # itself is applied in build_assessment()'s corrections
                    # pass; leaving pending_field unresolved here means the
                    # SAME question is naturally re-asked, since the field
                    # never appears in `paired`.
                    pass
                else:
                    value = _attribute_pending_answer(pending_field, content)
                    if value is not None:
                        paired[pending_field] = value
                        needs_alt.discard(pending_field)
            pending_field = None
            pending_is_alt = False

    return paired, needs_alt


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

def build_assessment(
    chat_history: Optional[List[Dict[str, str]]],
    current_message: str,
    *,
    seed_facts: Optional[Dict[str, Any]] = None,
    cached_facts: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Set[str]]:
    """
    Reconstruct everything currently known for this Pain conversation:
        1. opportunistic direct extraction from every user message in the
           conversation (catches facts volunteered without being asked)
        2. pending-field (question/answer pair) attribution, which takes
           priority over (1) for whichever field it resolves
        3. cue-gated corrections (see _detect_correction), applied in
           chronological order so a LATER correction always overrides an
           earlier value -- this is what lets "Actually wait, it's more
           like a 7 than a 5." fix an already-resolved pain_score even
           though a different field is the one actually pending
        4. `cached_facts` -- a FALLBACK BASELINE only, filling ONLY the
           fields steps 1-3 left unresolved (see pain_state.py's
           structured-fact cache). This is what lets an earlier turn's
           structured pain_score/swelling_description survive onto a LATER
           turn that doesn't resupply it, WITHOUT letting a stale cached
           value override a genuine free-text correction from steps 1-3 --
           a field already set by conversation/correction is never
           overwritten by the cache.
        5. `seed_facts` -- the CURRENT request's own structured API fields,
           which always take top priority, unconditionally overriding
           everything above -- explicit structured input supplied THIS
           turn is trusted over inferred text parsing AND over the cache
           (existing, unchanged API behaviour).

    Returns (assessment, needs_alt).
    """
    history = list(chat_history or [])
    if current_message.strip():
        history = history + [{"role": "user", "content": current_message.strip()}]

    assessment: Dict[str, Any] = {}
    for item in history:
        if not isinstance(item, dict):
            continue
        if str(item.get("role", "")).lower().strip() != "user":
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        for field_name, value in _direct_extraction_for_message(content).items():
            assessment[field_name] = value

    paired, needs_alt = _extract_answer_pairs(chat_history, current_message)
    assessment.update(paired)

    for field_name in list(needs_alt):
        if field_name in assessment:
            needs_alt.discard(field_name)

    for item in history:
        if not isinstance(item, dict):
            continue
        if str(item.get("role", "")).lower().strip() != "user":
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        correction = _detect_correction(content)
        if correction is not None:
            field_name, value = correction
            assessment[field_name] = value
            needs_alt.discard(field_name)

    if cached_facts:
        for field_name, value in cached_facts.items():
            # setdefault: fills ONLY a field still missing after direct
            # extraction/pending-answer/corrections -- a value already
            # established from the conversation itself is never overwritten
            # by a cached (possibly stale) structured fact.
            if field_name not in assessment:
                assessment[field_name] = value
                needs_alt.discard(field_name)

    if seed_facts:
        assessment.update(seed_facts)
        for field_name in list(needs_alt):
            if field_name in assessment:
                needs_alt.discard(field_name)

    if PAIN_SCORE in assessment and assessment[PAIN_SCORE] != "unknown":
        try:
            assessment[PAIN_SCORE] = int(assessment[PAIN_SCORE])
        except (TypeError, ValueError):
            pass

    return assessment, needs_alt


# ============================================================================
# NEXT-INFORMATION DECISION (pure, deterministic, genuinely adaptive)
# ============================================================================

def select_next_field(
    assessment: Dict[str, Any],
    *,
    medication_mentioned: bool = False,
) -> Optional[str]:
    """
    Decide the single most useful next field to ask about, given what is
    already known. NOT a fixed linear order past the three core fields --
    branches on location and severity, and stops as soon as the current
    branch has enough information rather than marching through every
    possible field.
    """
    for field_name in REQUIRED_FIELDS:
        if field_name not in assessment:
            return field_name

    branch = classify_location_branch(str(assessment.get(LOCATION, "")))
    severity = severity_bucket(assessment.get(PAIN_SCORE))

    if branch == "calf":
        for field_name in _CALF_BRANCH_FIELDS:
            if field_name not in assessment:
                return field_name
        if severity in ("moderate", "severe") and FEVER_OR_TEMPERATURE not in assessment:
            return FEVER_OR_TEMPERATURE
    else:
        # Standard joint-pain branch -- deliberately does NOT launch the
        # calf-specific swelling/warmth/numbness sequence for ordinary
        # knee/thigh/hip pain.
        if severity == "severe":
            if WORSENING_OR_IMPROVING not in assessment:
                return WORSENING_OR_IMPROVING
            if STIFFNESS not in assessment:
                return STIFFNESS
        elif severity == "moderate":
            if WORSENING_OR_IMPROVING not in assessment:
                return WORSENING_OR_IMPROVING
        # mild severity: the three core fields are enough on their own --
        # do not add extra questions for ordinary, low-severity pain.

    if medication_mentioned and MEDICATION_EFFECT not in assessment:
        return MEDICATION_EFFECT

    return None


def is_complete(assessment: Dict[str, Any], *, medication_mentioned: bool = False) -> bool:
    return select_next_field(assessment, medication_mentioned=medication_mentioned) is None


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
