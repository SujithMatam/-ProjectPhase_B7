"""
Recovery Integration -- Pass 2: glue between the approved Recovery state
foundation (recovery_state.py), the approved pure Recovery decision/
milestone logic (recovery_logic.py), and the rest of the LAM pipeline.

This module owns:
    - server-side, trusted postoperative-day derivation from surgery_date
      (never trusting the client-supplied postop_day for a clinical
      comparison)
    - adapting a real RAG-retrieved clinical chunk into the small
      RecoveryEvidence view recovery_logic.py's evaluator expects
    - deterministic patient-facing templates for ASK / DECLINE / ASSESS
      (checkpoint-relative wording only -- see recovery_logic.CheckpointVerdict)
    - the narrow Recovery continuation check used by the orchestrator hook

It does NOT redefine any Recovery decision, extraction, or milestone logic
-- those remain owned exclusively by recovery_logic.py (Pass 1, approved).
This module only reads recovery_logic's PUBLIC constants/enums/dataclasses
(MILESTONE_TABLE, ROM_FLEXION_DEGREES, CheckpointVerdict, DecisionReasonCode,
RecoveryEvidence, etc.) and recovery_state's approved public API
(peek_state/get_or_create_state and RecoverySessionState's public methods).
It never touches either module's private internals.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Dict, Optional

from agents import recovery_logic
from agents import recovery_state


# ============================================================================
# POSTOPERATIVE-DAY DERIVATION
# ============================================================================
#
# CALENDAR-DATE / TIMEZONE CONVENTION (see Pass-2 report for full rationale):
#
# This project has no per-patient timezone metadata anywhere -- ChatRequest
# and PatientUser carry no timezone field, and the Flutter client has been
# observed sending naive local ISO strings (e.g. "2026-09-02T00:00:00.000",
# no 'Z', no offset). Without a real timezone to convert into, any attempt
# to "correctly" convert a UTC-labeled or offset-aware timestamp into "the
# patient's local calendar day" would require GUESSING a timezone this
# project does not have.
#
# CHOSEN CONVENTION: extract ONLY the literal YYYY-MM-DD calendar-date
# digits from surgery_date, for ALL THREE input shapes (naive local ISO, 'Z'
# ISO, offset ISO) -- deliberately ignoring time-of-day and any timezone/
# offset marker entirely. This is applied identically regardless of format,
# so there is exactly ONE rule, not three different ones. "Today" is then
# taken as the SERVER's own local calendar date (datetime.now().date()) --
# the closest available approximation to the app's calendar day without
# real per-patient timezone data, and consistent with how the naive-local
# format (the format actually sent today) is already meant to be read.
#
# This avoids ANY naive-vs-aware datetime arithmetic (the exact crash
# reproduced during investigation: subtracting an aware `Z`-parsed datetime
# from a naive datetime.now() raises TypeError) by construction -- we never
# build an aware datetime at all, only a plain `date`. It also avoids the
# worst-case off-by-one this kind of code commonly introduces: converting a
# 'Z' (UTC) timestamp near local midnight into a DIFFERENT calendar day than
# the one a clinician/patient actually entered, purely because of an
# unwarranted UTC<->local conversion. Whatever calendar date was written is
# the calendar date used -- verified explicitly in the boundary smoke tests
# (a timestamp at 23:30 local, and a 'Z' timestamp at 23:30, both still
# resolve to their own written calendar date, never shifted).
#
# WHAT THIS CONVENTION DOES *NOT* SOLVE -- read before relying on it:
#
# The two sides of the derive_effective_postop_day() subtraction are NOT
# proven timezone-independent, and this module does not claim they are:
#   - surgery_date's calendar digits are whatever the CLIENT wrote, in
#     whatever local convention the client used to produce them.
#   - "today" (the `today` parameter's default) is datetime.now().date() --
#     the BACKEND HOST's own local calendar date, per the Python/OS clock
#     the server process runs under. It is not the patient's or app's
#     timezone; this repo has no patient/app timezone field anywhere
#     (ChatRequest, PatientUser) to read one from, so none is invented and
#     none is guessed here -- specifically, this code does NOT assume or
#     hardcode Kerala/IST in production logic merely because that happens to
#     be this project's current development environment.
#   - Therefore this implementation only produces a correct postoperative
#     day when the backend host's local calendar date and the patient/app's
#     local calendar date AGREE at the moment of the request. That is the
#     explicit, accepted assumption for this branch.
#   - If ever deployed with the backend host and the patient/app in
#     different timezones, there is a genuine off-by-one risk during
#     whatever window their local calendar dates disagree. Concretely, for a
#     patient/app on India Standard Time (UTC+05:30) against a UTC-hosted
#     server, IST is 5 hours 30 minutes ahead of UTC, so the server's
#     calendar date has not yet advanced to the patient's for roughly the
#     first 5.5 hours after the patient's local midnight -- a request in
#     that window would be derived against the server's still-previous
#     calendar date.
#   - Converting naive timestamps to UTC (or any other normalization) does
#     NOT fix this -- there is no timezone attached to either side to
#     convert FROM, so any such conversion would just be guessing a
#     timezone and asserting it as fact. Do not do that.
#   - Proper deployment-grade resolution requires an explicit patient/app
#     timezone field carried through the API (ChatRequest / PatientUser),
#     which does not exist today. That is out of scope for this branch; the
#     literal-calendar-digit convention above is accepted as-is for now.
#
# The `today=` parameter stays injectable specifically so tests can pin a
# deterministic date regardless of this limitation -- see the Day 6/7/8
# tests, which must keep passing unchanged.

_DATE_ONLY_RE = re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})")


def parse_calendar_date(surgery_date_raw: Optional[str]) -> Optional[date]:
    """
    Extract the literal YYYY-MM-DD calendar date from a surgery_date
    string, per the convention above. Returns None for missing/malformed
    input -- never raises, never guesses a default date.
    """
    if not surgery_date_raw:
        return None
    match = _DATE_ONLY_RE.match(surgery_date_raw)
    if not match:
        return None
    year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def derive_effective_postop_day(
    surgery_date_raw: Optional[str],
    *,
    today: Optional[date] = None,
) -> Optional[int]:
    """
    Server-side, trusted postoperative-day derivation. Returns None for
    missing/malformed/unusable surgery_date -- callers must then call
    state.clear_verified_day(), never fall back to the client-supplied
    postop_day for a clinical comparison.

    Day-1 convention (existing project convention, confirmed in
    lib/models/patient_user.dart's `.clamp(1, 365)`): the surgery calendar
    date itself IS Post-Op Day 1, not Day 0.

    `today` is injectable (defaults to the server's own local calendar
    date) purely so callers/tests can pin a deterministic "today" without
    depending on the real clock.

    TIMEZONE CAVEAT (see the module-level comment block above): the default
    `today` is the BACKEND HOST's local calendar date, not a patient/app
    timezone -- this repo has none to read. This function is only correct
    when the host and patient/app agree on the calendar date; do not treat
    its result as timezone-independent.
    """
    surgery_date = parse_calendar_date(surgery_date_raw)
    if surgery_date is None:
        return None

    if today is None:
        today = datetime.now().date()

    day = (today - surgery_date).days + 1
    if day < 1:
        # Surgery date in the future relative to "today" -- nonsensical
        # input for this purpose. Treated as unusable rather than inventing
        # a zero/negative postoperative day.
        return None

    return day


# ============================================================================
# EVIDENCE ADAPTATION -- ONE retrieval per progress-verdict turn.
# ============================================================================

# A bare continuation reply ("80 degrees", "Same as yesterday.", "I don't
# know.") often carries none of TKA-03's own keywords ("flexion", "bend",
# "range of motion", ...), so the keyword-fallback retrieval path (the only
# path available whenever sentence-transformers/chromadb aren't installed --
# see the project's own investigation notes) can return an EMPTY result for
# such a message even though this is unambiguously an ongoing TKA
# ROM conversation. Rather than silently declining every terse continuation
# turn for want of a better query, the retrieval query for THIS turn's
# selected metric is augmented with a small, fixed, metric-specific phrase
# built from the corpus's own vocabulary (not invented clinical content --
# these exact words already appear in TKA-03's `keywords` list) before the
# single retrieve_detailed() call. This is still ONE retrieval, using the
# real patient message plus a fixed hint, never a second call and never
# fabricated evidence.
_RETRIEVAL_QUERY_HINTS: Dict[str, str] = {
    "rom_flexion_degrees": "knee flexion range of motion recovery milestone",
    "rom_extension_degrees": "knee extension range of motion recovery milestone",
}


def build_retrieval_query(user_message: str, metric: str) -> str:
    hint = _RETRIEVAL_QUERY_HINTS.get(metric)
    if not hint:
        return user_message
    return f"{user_message} {hint}"


def build_recovery_evidence_from_chunk(chunk) -> "recovery_logic.RecoveryEvidence":
    """
    Adapt a real rag.knowledge_base.RetrievedChunk (or anything exposing the
    same .doc_id / .procedure / .days attributes) into the small,
    dependency-light RecoveryEvidence view recovery_logic.py's evaluator
    expects. No RAG content is altered -- source_id/procedure/days_raw are
    taken verbatim from the retrieved chunk's own metadata.
    """
    return recovery_logic.RecoveryEvidence(
        source_id=chunk.doc_id,
        procedure=chunk.procedure,
        days_raw=chunk.days,
    )


# ============================================================================
# CONTINUATION CHECK -- used ONLY by the orchestrator hook.
# ============================================================================
#
# Deliberately a SEPARATE, small, narrow regex set from recovery_logic.py's
# extraction cue-word lists (some duplication) rather than importing
# recovery_logic's private (underscore) internals -- this keeps the
# approved Pass-1 module completely unmodified and unreached-into, at the
# cost of a small amount of duplicated cue vocabulary here.

_DEGREE_PATTERN = re.compile(r"\d+(\.\d+)?\s*(degrees|deg|°)", re.IGNORECASE)
_FLEXION_WORDS = ("bend", "flex", "flexion", "bent")
_EXTENSION_WORDS = ("straighten", "extend", "extension", "straight")
_MOBILITY_WORDS = ("walker", "cane", "crutches", "independent", "independently")
_DONT_KNOW_WORDS = ("don't know", "dont know", "not sure", "no idea")
_SAME_AS_YESTERDAY_PHRASE = "same as yesterday"
_PAIN_WORD_RE = re.compile(r"\bpain\b", re.IGNORECASE)
_PAIN_SCALE_RE = re.compile(r"\b\d{1,2}\s*(?:/|out of)\s*10\b", re.IGNORECASE)


def message_plausibly_answers_pending_field(message: str, pending_field: str) -> bool:
    """
    Narrow, deterministic check: does `message` plausibly answer the ONE
    SPECIFIC Recovery field currently pending? This is NOT a general intent
    classifier and must never be treated as one -- it only recognizes a
    small, field-scoped set of answer shapes (degree/angle mentions for ROM
    fields, mobility-aid/independence words for mobility, a pain-scale
    mention for pain, plus the universal "I don't know"/"same as yesterday"
    non-answers). Anything else (wound, medication, emergency, unrelated
    topics) correctly returns False so fresh intent classification runs.
    """
    lower = (message or "").strip().lower()
    if not lower:
        return False

    if _SAME_AS_YESTERDAY_PHRASE in lower:
        return True
    if any(phrase in lower for phrase in _DONT_KNOW_WORDS):
        return True

    if pending_field in (recovery_logic.ROM_FLEXION_DEGREES, recovery_logic.ROM_EXTENSION_DEGREES):
        if _DEGREE_PATTERN.search(lower):
            return True
        cue_words = (
            _FLEXION_WORDS if pending_field == recovery_logic.ROM_FLEXION_DEGREES else _EXTENSION_WORDS
        )
        return any(word in lower for word in cue_words)

    if pending_field == recovery_logic.MOBILITY_STATUS:
        return any(word in lower for word in _MOBILITY_WORDS)

    if pending_field == recovery_logic.PAIN_SCORE:
        return bool(_PAIN_WORD_RE.search(lower)) or bool(_PAIN_SCALE_RE.search(lower))

    return False


def check_recovery_continuation(
    *,
    patient_id: str,
    surgery_date_raw: Optional[str],
    procedure: str,
    user_message: str,
) -> bool:
    """
    The orchestrator's ONLY entry point for Recovery continuation. Returns
    True only when:
        - an EXISTING Recovery episode is found via peek_state() (exact-key
          lookup ONLY -- never get_or_create_state(), never NODATE->dated
          adoption; a message from a patient/episode with no existing
          Recovery state returns False immediately and creates nothing)
        - that episode has a real pending_field
        - the current message plausibly answers THAT SPECIFIC field

    Never uses "Recovery was the last active agent" as a signal. Never
    mutates state (peek_state is read-only).
    """
    state = recovery_state.peek_state(
        patient_id=patient_id, surgery_date_raw=surgery_date_raw, procedure=procedure,
    )
    if state is None:
        return False
    if state.pending_field is None:
        return False
    return message_plausibly_answers_pending_field(user_message, state.pending_field)


# ============================================================================
# DETERMINISTIC PATIENT-FACING TEMPLATES
# ============================================================================

def format_ask_question(metric: str) -> str:
    if metric == recovery_logic.ROM_FLEXION_DEGREES:
        return "About how many degrees can you currently bend your knee?"
    if metric == recovery_logic.ROM_EXTENSION_DEGREES:
        return "Do you know your current knee extension measurement in degrees (how close to fully straight)?"
    if metric == recovery_logic.MOBILITY_STATUS:
        return "How are you currently getting around -- walking independently, or using a walker, cane, or crutches?"
    if metric == recovery_logic.PAIN_SCORE:
        return "On a scale of 0 to 10, what is your current pain level?"
    return "Could you share more detail about your current recovery status?"


_DECLINE_REASON_TEXT: Dict[str, str] = {
    recovery_logic.DecisionReasonCode.DAY_UNVERIFIED:
        "I can't make a day-specific recovery comparison right now because your surgery date can't be verified.",
    recovery_logic.DecisionReasonCode.NO_SUPPORTED_METRIC_FOR_PROCEDURE:
        "I don't have supported evidence to give a specific progress-milestone verdict for this right now.",
    recovery_logic.DecisionReasonCode.EVIDENCE_MISSING:
        "I don't have supported evidence to give a specific progress-milestone verdict right now.",
    recovery_logic.DecisionReasonCode.EVIDENCE_SOURCE_MISMATCH:
        "The evidence I retrieved doesn't match the milestone I'd need to compare against, so I can't give a supported verdict right now.",
    recovery_logic.DecisionReasonCode.EVIDENCE_PROCEDURE_MISMATCH:
        "The evidence I retrieved is for a different procedure, so I can't give a supported verdict right now.",
    recovery_logic.DecisionReasonCode.MALFORMED_APPLICABILITY_WINDOW:
        "The retrieved guidance doesn't have a usable day range, so I can't give a supported verdict right now.",
    recovery_logic.DecisionReasonCode.DAY_OUTSIDE_APPLICABILITY_WINDOW:
        "The available source supports comparison only within its stated day range, and your current day falls outside "
        "that range, so I can't give a supported verdict right now.",
    recovery_logic.DecisionReasonCode.RETRY_EXHAUSTED:
        "I wasn't able to get a clear answer for this after a couple of tries, so I can't give a supported verdict right now.",
    recovery_logic.DecisionReasonCode.FIELD_UNAVAILABLE:
        "I don't have a confirmed current value for this, so I can't give a supported verdict right now.",
    recovery_logic.DecisionReasonCode.INVALID_METRIC_VALUE:
        "The reported measurement doesn't look usable, so I can't rely on it for a supported verdict -- "
        "could you clarify the number?",
}


def format_decline_message(
    reason_code: str,
    *,
    metric: str,
    evidence: Optional["recovery_logic.RecoveryEvidence"],
) -> str:
    """Reason-specific, concise decline wording. Never turns missing
    evidence into a claimed clinical abnormality."""
    return _DECLINE_REASON_TEXT.get(
        reason_code,
        "I don't have enough supported evidence to give a specific progress-milestone verdict right now.",
    )


def _fmt_num(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return str(value)


def _metric_label(metric: str) -> str:
    return "flexion" if metric == recovery_logic.ROM_FLEXION_DEGREES else "extension"


def format_assess_message(checkpoint: "recovery_logic.CheckpointResult") -> str:
    """
    Deterministic, checkpoint-relative ASSESS wording. Preserves the
    distinction between checkpoint_day (7, always TKA-03's own stated
    checkpoint) and effective_postop_day (whatever day the patient is
    actually on) explicitly in the sentence -- 70-90 deg is NEVER rewritten
    as though it were a target for the patient's current day. Never uses
    "on track" / "above expected" / "ahead of schedule" / "normal recovery"
    or any other unsupported trajectory language.
    """
    metric_label = _metric_label(checkpoint.metric)
    value_text = f"{_fmt_num(checkpoint.patient_value)}°" if checkpoint.patient_value is not None else "value"

    if checkpoint.verdict == recovery_logic.CheckpointVerdict.TARGET_NOT_YET_DUE:
        return (
            f"Your reported {metric_label} of {value_text} has been noted. "
            f"The Post-Op Day {checkpoint.checkpoint_day} checkpoint in {checkpoint.source_id} "
            f"hasn't been reached yet (you're currently at Day {checkpoint.effective_postop_day}), "
            "so there isn't a stated target to compare against yet."
        )

    milestone = recovery_logic.MILESTONE_TABLE.get((checkpoint.procedure, checkpoint.metric))
    if milestone is None:
        return "I don't have a supported way to phrase this result yet."
    range_text = f"{_fmt_num(milestone.range_low)}°-{_fmt_num(milestone.range_high)}°"

    if checkpoint.effective_postop_day == checkpoint.checkpoint_day:
        day_clause = f"Post-Op Day {checkpoint.checkpoint_day}"
    else:
        day_clause = f"the earlier Post-Op Day {checkpoint.checkpoint_day} checkpoint"

    if checkpoint.verdict == recovery_logic.CheckpointVerdict.MEETS_STATED_CHECKPOINT:
        relation = "is within"
    elif checkpoint.verdict == recovery_logic.CheckpointVerdict.BELOW_STATED_CHECKPOINT:
        relation = "is below"
    elif checkpoint.verdict == recovery_logic.CheckpointVerdict.EXCEEDS_STATED_RANGE:
        relation = "exceeds"
    elif checkpoint.verdict == recovery_logic.CheckpointVerdict.OUTSIDE_STATED_RANGE:
        relation = "is outside"
    else:
        return "I don't have a supported way to phrase this result yet."

    return (
        f"Your reported {metric_label} of {value_text} {relation} the {range_text} range "
        f"stated for {day_clause} in {checkpoint.source_id}."
    )
