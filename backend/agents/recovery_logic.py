"""
Recovery Logic -- deterministic fact extraction, milestone lookup, checkpoint
comparison and the per-turn plan. Pure logic only.

This module owns everything that can be decided WITHOUT calling RAG, an LLM,
the orchestrator, or IntentClassifier. It operates exclusively through the
approved public API of RecoverySessionState (backend/agents/recovery_state.py)
-- get_fact/status_of/is_current/ask_count_of/pending_field/
pending_variant/pending_confirm_value/effective_postop_day/
postop_day_verified for reads, and set_fact/mark_pending/mark_unknown/
mark_unavailable/clear_pending/note_confirm_declined/apply_verified_day/
clear_verified_day for writes. It never reaches into that module's private
internals.

Milestone data lives in agents/data/recovery_milestones.json (see
load_milestones()). Every entry there is taken from one passage of
backend/eval/eval_corpus.json (or the retained TKA-03 seed passage) and
carries its passage id and source URL; nothing in this module invents a
number, a range or a trajectory claim -- it only compares what the patient
reported with what the chosen passage states.

Explicitly OUT of scope here:
    - orchestrator / continuation routing
    - RecoveryProgressAgent / specialized_agents.py behaviour
    - ChatAgent / RAG / LLM calls
    - patient-facing response text (everything here returns structured
      data: enums, dataclasses, reason codes -- never prose; wording is
      owned by recovery_integration.py)

Extraction ambiguity is represented ONLY as a return value from this module
(AmbiguousField) -- it never mutates RecoverySessionState.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from agents.recovery_state import FieldStatus, RecoverySessionState


# ============================================================================
# FIELD NAME CONSTANTS -- use these, not ad-hoc strings, for consistency.
# ============================================================================

MOBILITY_STATUS = "mobility_status"            # walking aid
ROM_FLEXION_DEGREES = "rom_flexion_degrees"
ROM_EXTENSION_DEGREES = "rom_extension_degrees"
PAIN_SCORE = "pain_score"
WALKING_DURATION_MINUTES = "walking_duration_minutes"
STAIRS = "stairs"
DAILY_ACTIVITIES = "daily_activities"
DRIVING = "driving"
RETURN_TO_WORK = "return_to_work"
HIP_PRECAUTIONS = "hip_precautions"
EXERCISE_COMPLETED = "exercise_completed"

ROM_FIELDS: Tuple[str, ...] = (ROM_FLEXION_DEGREES, ROM_EXTENSION_DEGREES)
NUMERIC_FIELDS: Tuple[str, ...] = ROM_FIELDS + (WALKING_DURATION_MINUTES,)

# Metrics the interview ASKS about, per procedure, in canonical order. THA
# gets walking and precaution questions, never knee ROM. Everything else in
# the milestone file (daily activities, driving, return to work) is
# collected only when the patient volunteers it, and is then assessed too.
ASKED_METRICS_BY_PROCEDURE: Dict[str, Tuple[str, ...]] = {
    "TKA": (ROM_FLEXION_DEGREES, ROM_EXTENSION_DEGREES, MOBILITY_STATUS, WALKING_DURATION_MINUTES, STAIRS),
    "THA": (MOBILITY_STATUS, WALKING_DURATION_MINUTES, STAIRS, HIP_PRECAUTIONS),
}
VOLUNTEERED_ONLY_METRICS: Tuple[str, ...] = (DAILY_ACTIVITIES, DRIVING, RETURN_TO_WORK, EXERCISE_COMPLETED)


def asked_metrics_for(procedure: Optional[str]) -> Tuple[str, ...]:
    return ASKED_METRICS_BY_PROCEDURE.get((procedure or "").upper(), ())


# Kept for callers/tests that still read it: the metrics with a sourced
# checkpoint per procedure (derived from the milestone file at import).
def _supported_metrics_from_file() -> Dict[str, Tuple[str, ...]]:
    table: Dict[str, List[str]] = {"TKA": [], "THA": [], "GEN": []}
    try:
        for entry in load_milestones().entries:
            bucket = table.setdefault(entry.procedure, [])
            if entry.metric not in bucket:
                bucket.append(entry.metric)
    except Exception:
        pass
    return {proc: tuple(metrics) for proc, metrics in table.items()}


# ============================================================================
# RECOVERY WORKFLOW CONSTANTS -- session/workflow policy, NOT clinical.
# ============================================================================

# Maximum number of times a single field may be asked before the interview
# treats it as exhausted ("no data for this one -- moving on"). This is the
# agreed retry budget, not a clinical parameter.
MAX_ASKS_PER_FIELD = 2

# ENGINEERING INPUT-VALIDATION GUARD (NOT a clinical threshold): a single
# hinge joint's angular measurement cannot structurally exceed roughly a
# half revolution (180 degrees) -- a generic geometric sanity ceiling used
# purely to catch obviously corrupted/mistyped input (e.g. "800 degrees").
_ROM_STRUCTURAL_MAX_DEGREES = 180.0
# Same idea for a walking duration in minutes: a day has 1440.
_MINUTES_STRUCTURAL_MAX = 1440.0
# ENGINEERING INPUT-PLAUSIBILITY GUARD (NOT a clinical threshold): a reply
# to the flexion/extension question that carries NO degrees unit is only
# read as an angle when the number is in 0-150. Anything else ("about 5
# minutes", "200") is a non-fit and gets the clarifying question.
_ROM_UNITLESS_MAX_DEGREES = 150.0

# The milestone file covers post-op days 1-365 (its long-term passages are
# tagged 43-365). Inside that window the agent never declines to assess.
SUPPORTED_DAY_RANGE: Tuple[int, int] = (1, 365)


# ============================================================================
# VALUE TYPES
# ============================================================================

@dataclass(frozen=True)
class ValueRange:
    """A reported value known only as a range -- e.g. the simpler extension
    question ("can you get the knee fully flat?") maps "nearly" to the
    0-5 degree near-full range TKA-03 itself names, and the walking
    rephrase maps "more than ten minutes" to (10, None). `label` is the
    patient-facing wording for the answer; `low`/`high` may be None for an
    open end."""
    low: Optional[float]
    high: Optional[float]
    label: str
    # True when the range starts strictly ABOVE `low` ("more than the 0-5
    # near-full range" starts beyond 5, not at 5).
    low_exclusive: bool = False

    @property
    def is_point(self) -> bool:
        return self.low is not None and self.high is not None and self.low == self.high


# Answers to the simpler extension question, mapped to degree ranges. The
# only numbers used are TKA-03's own "near-full extension (0-5 degrees)";
# "fully flat" is 0 degrees by definition and "not flat" is anything
# beyond the near-full range -- nothing else is invented.
EXTENSION_FLAT_ANSWERS: Dict[str, ValueRange] = {
    "full": ValueRange(0.0, 0.0, "fully flat on the bed"),
    "near_full": ValueRange(0.0, 5.0, "nearly flat"),
    "not_full": ValueRange(5.0, None, "not yet flat", low_exclusive=True),
}

# Answers to the simpler walking-duration question ("more than ten minutes
# at a time, or less?") -- the ten-minute mark is the corpus's own
# criterion for moving to a single crutch or cane.
WALKING_DURATION_ANSWERS: Dict[str, ValueRange] = {
    "more": ValueRange(10.0, None, "more than ten minutes at a time", low_exclusive=True),
    "less": ValueRange(0.0, 10.0, "less than ten minutes at a time"),
}


# ============================================================================
# EXTRACTION RESULT TYPES
# ============================================================================

@dataclass(frozen=True)
class ExtractedFact:
    field_name: str
    value: Any


@dataclass(frozen=True)
class AmbiguousField:
    """One field where the message contained genuinely conflicting current
    values with no basis to prefer one. Extraction-layer result only --
    never written into RecoverySessionState."""
    field_name: str
    candidates: Tuple[Any, ...]
    raw_text: str


@dataclass(frozen=True)
class ExtractionResult:
    applied_facts: Tuple[ExtractedFact, ...]
    ambiguous_fields: Tuple[AmbiguousField, ...]
    marked_unknown_fields: Tuple[str, ...]
    # Fields whose confirmation offer was declined this turn ("no" to
    # "still about 80 degrees?") -- the plain question follows.
    confirm_declined_fields: Tuple[str, ...] = ()
    # The pending field got a reply carrying a number that does not fit it
    # ("about 5 minutes" while waiting for flexion). Nothing is stored; the
    # agent asks the clarifying question instead of the plain re-ask.
    unfit_fields: Tuple[str, ...] = ()


# ============================================================================
# FACT EXTRACTION -- deterministic, regex-based. No NLP library, no LLM.
# ============================================================================

_MOBILITY_DEVICES: Tuple[str, ...] = ("walker", "cane", "crutches")
_MOBILITY_SYNONYMS: Dict[str, str] = {
    "frame": "walker", "walking frame": "walker", "zimmer": "walker", "rollator": "walker",
    "stick": "cane", "walking stick": "cane",
    "crutch": "crutches",
}

_INDEPENDENT_PHRASES: Tuple[str, ...] = (
    "walk independently", "walking independently", "walking on my own",
    "without a walker", "without any aid", "without assistance",
    "without help", "on my own now", "no aid", "nothing to help me walk",
    "not using anything", "without a stick", "without the frame",
)

_PAST_CUES: Tuple[str, ...] = ("before", "used to", "previously", "last week", "was using")
_CURRENT_CUES: Tuple[str, ...] = ("now", "currently", "these days", "today")

_NEGATION_ANYMORE_RE = re.compile(
    r"\bnot\s+using\s+(?:the|a|my)?\s*(walker|cane|crutches)\b[^.]*\b(any\s*more|anymore)\b"
    r"|\bno\s+longer\s+(?:using|use|need)\s+(?:the|a|my)?\s*(walker|cane|crutches)\b"
    r"|\bdon'?t\s+need\s+(?:the|a|my)?\s*(walker|cane|crutches)\b[^.]*\b(any\s*more|anymore)?\b",
    re.IGNORECASE,
)

_CLAUSE_SPLIT_RE = re.compile(r"\s*(?:,|;|\bbut\b|\bhowever\b)\s*", re.IGNORECASE)


def _split_clauses(lower: str) -> List[str]:
    parts = [p.strip() for p in _CLAUSE_SPLIT_RE.split(lower) if p.strip()]
    return parts or [lower]


def _canonical_mobility_text(lower: str) -> str:
    """Map walking-aid synonyms (frame/stick/crutch) onto the canonical
    device words before the clause scan."""
    text = lower
    for phrase, canonical in sorted(_MOBILITY_SYNONYMS.items(), key=lambda kv: -len(kv[0])):
        text = re.sub(r"\b" + re.escape(phrase) + r"\b", canonical, text)
    return text


def _extract_mobility(text: str, lower: str) -> Tuple[Optional[ExtractedFact], Optional[AmbiguousField]]:
    clauses = _split_clauses(_canonical_mobility_text(lower))
    current_candidates: List[str] = []

    for clause in clauses:
        clause_devices = [d for d in _MOBILITY_DEVICES if re.search(r"\b" + d + r"\b", clause)]
        clause_independent = any(p in clause for p in _INDEPENDENT_PHRASES)
        clause_negated_anymore = bool(_NEGATION_ANYMORE_RE.search(clause))
        clause_past = any(c in clause for c in _PAST_CUES)
        clause_current = any(c in clause for c in _CURRENT_CUES)

        if clause_negated_anymore and len(clause_devices) == 1 and not clause_independent:
            current_candidates.append("independent")
            continue

        if clause_independent:
            current_candidates.append("independent")
            continue

        if not clause_devices:
            continue

        if clause_past and not clause_current:
            continue

        current_candidates.extend(clause_devices)

    if not current_candidates:
        return None, None

    unique_current: List[str] = []
    for c in current_candidates:
        if c not in unique_current:
            unique_current.append(c)

    if len(unique_current) == 1:
        return ExtractedFact(MOBILITY_STATUS, unique_current[0]), None

    return None, AmbiguousField(MOBILITY_STATUS, tuple(sorted(unique_current)), text)


_FLEXION_CUES: Tuple[str, ...] = ("bend", "flex", "flexion", "bent")
_EXTENSION_CUES: Tuple[str, ...] = ("straighten", "extend", "extension", "straight", "flat")

_DEGREE_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:degrees|degree|deg|°)")
_CORRECTION_RE = re.compile(
    r"\bactually,?\s+(?:it'?s\s+)?(\d+(?:\.\d+)?)\s*(?:degrees|deg|°)?\s*,?\s*not\s+"
    r"(\d+(?:\.\d+)?)\s*(?:degrees|deg|°)?",
    re.IGNORECASE,
)
# A reply that is nothing but a number ("80", "about 80", "roughly 15.") --
# attributable only to the pending numeric field.
_BARE_NUMBER_RE = re.compile(r"^\s*(?:about|around|roughly|approximately|maybe|~)?\s*(\d+(?:\.\d+)?)\s*[.!]?\s*$", re.IGNORECASE)
# A short reply carrying exactly one number and no unit ("it's about 85
# now", "more like 90 I think") -- also attributable only to the pending
# numeric field, never to anything else.
_LOOSE_NUMBER_RE = re.compile(r"(?<![\d./])(\d{1,3}(?:\.\d+)?)(?![\d./%])")


_LOOSE_FILLER_WORDS = frozenset((
    "it's", "its", "it", "is", "about", "around", "roughly", "maybe", "more", "like", "now", "i", "think",
    "probably", "say", "i'd", "d", "or", "so",
    "still", "today", "currently", "the", "number", "a", "bit", "over", "under", "just", "nearly", "almost",
    "yes", "no", "well", "hmm", "um", "closer", "to", "than", "that", "this", "morning", "at", "moment",
))
_DEGREE_UNIT_WORDS = frozenset(("degrees", "degree", "deg"))
_MINUTE_UNIT_WORDS = frozenset(("minutes", "minute", "mins", "min"))
# The few words of an angle answer that carry no unit ("I can bend to 95",
# "it gets up to 100").
_ROM_PHRASE_WORDS = frozenset((
    "can", "could", "bend", "bends", "bent", "bending", "straighten", "straightens", "straight",
    "flexion", "extension", "get", "gets", "go", "goes", "up", "my", "knee", "off", "from",
))


def _unit_words_for(field_name: Optional[str]) -> frozenset:
    """The one unit a loose number may carry for `field_name`: degrees for
    flexion/extension, minutes for walking duration. Any other unit word
    makes the reply a non-fit for that field. With no field (the
    continuation hook: "is this a short numeric answer at all?") either
    unit is allowed and the agent decides whether it fits."""
    if field_name in ROM_FIELDS:
        return _DEGREE_UNIT_WORDS | _ROM_PHRASE_WORDS
    if field_name == WALKING_DURATION_MINUTES:
        return _MINUTE_UNIT_WORDS
    return _DEGREE_UNIT_WORDS | _MINUTE_UNIT_WORDS


def loose_number(lower: str, field_name: Optional[str] = None) -> Optional[float]:
    """A short reply whose only content is ONE number plus filler words
    ("it's about 85 now", "more like 90 I think"), optionally with the
    unit of `field_name`. Anything carrying other words ("I took 2
    tablets") or another unit ("about 5 minutes" for flexion) is NOT a
    loose number -- it may belong to another domain and must never be read
    as the pending measurement."""
    if "/10" in lower or "out of 10" in lower:
        return None
    tokens = re.findall(r"[a-z']+|\d+(?:\.\d+)?", lower)
    if not tokens or len(tokens) > 8:
        return None
    numbers = [t for t in tokens if re.fullmatch(r"\d+(?:\.\d+)?", t)]
    if len(numbers) != 1:
        return None
    allowed = _LOOSE_FILLER_WORDS | _unit_words_for(field_name)
    if any(t not in allowed for t in tokens if t not in numbers):
        return None
    return float(numbers[0])


def pending_number(lower: str, field_name: str) -> Optional[float]:
    """A bare or loose number attributable to the pending numeric field.
    For flexion/extension a unit-less number must also be in the plausible
    0-150 range; with a degrees unit the structural check downstream
    applies instead."""
    bare = _BARE_NUMBER_RE.match(lower)
    value = float(bare.group(1)) if bare is not None else loose_number(lower, field_name)
    if value is None:
        return None
    if field_name in ROM_FIELDS and not _DEGREE_NUM_RE.search(lower) and not (0.0 <= value <= _ROM_UNITLESS_MAX_DEGREES):
        return None
    return value


def _classify_rom_target(lower: str, pending_field: Optional[str], default_target: Optional[str] = None) -> Optional[str]:
    has_flexion_cue = any(c in lower for c in _FLEXION_CUES)
    has_extension_cue = any(c in lower for c in _EXTENSION_CUES)
    if has_flexion_cue and not has_extension_cue:
        return ROM_FLEXION_DEGREES
    if has_extension_cue and not has_flexion_cue:
        return ROM_EXTENSION_DEGREES
    if pending_field in ROM_FIELDS:
        return pending_field
    if pending_field is None and not (has_flexion_cue or has_extension_cue):
        return default_target
    return None


def _extract_rom(
    text: str, lower: str, pending_field: Optional[str], default_target: Optional[str] = None,
) -> Tuple[List[ExtractedFact], List[AmbiguousField]]:
    facts: List[ExtractedFact] = []
    ambiguous: List[AmbiguousField] = []

    correction = _CORRECTION_RE.search(lower)
    if correction:
        corrected_value = float(correction.group(1))
        target = _classify_rom_target(lower, pending_field, default_target)
        if target is not None:
            facts.append(ExtractedFact(target, corrected_value))
        else:
            ambiguous.append(AmbiguousField("rom_degrees", (corrected_value,), text))
        return facts, ambiguous

    for m in _DEGREE_NUM_RE.finditer(lower):
        value = float(m.group(1))
        window_start = max(0, m.start() - 25)
        local = lower[window_start:m.start()]
        local_flexion = any(c in local for c in _FLEXION_CUES)
        local_extension = any(c in local for c in _EXTENSION_CUES)
        if local_flexion and not local_extension:
            facts.append(ExtractedFact(ROM_FLEXION_DEGREES, value))
        elif local_extension and not local_flexion:
            facts.append(ExtractedFact(ROM_EXTENSION_DEGREES, value))
        else:
            target = _classify_rom_target(lower, pending_field, default_target)
            if target is not None:
                facts.append(ExtractedFact(target, value))

    return facts, ambiguous


_PAIN_RE = re.compile(r"\bpain\b[^.\d]{0,15}?(\d{1,2})\s*(?:/\s*10|out of\s*10)?", re.IGNORECASE)

_DONT_KNOW_RE = re.compile(r"\b(i\s+don'?t\s+know|not\s+sure|no\s+idea|haven'?t\s+measured|never\s+measured)\b", re.IGNORECASE)
_BARE_DONT_KNOW_NORMALIZED = {"i dont know", "not sure", "no idea", "dont know", "i have no idea", "i am not sure", "im not sure"}
_SAME_AS_YESTERDAY_RE = re.compile(r"^same as yesterday$", re.IGNORECASE)

_AFFIRMATIVE_RE = re.compile(
    r"^\s*(?:yes|yeah|yep|yup|correct|right|that'?s right|still(?: about)? that|about that|same|the same|"
    r"still the same|roughly|pretty much|i think so|i can|yes i can)\b[\s.!,]*(?:still|about|that|same|the same)?[\s.!]*$",
    re.IGNORECASE,
)
_NEGATIVE_RE = re.compile(r"^\s*(?:no|nope|not really|no not really|not quite|not yet|i can'?t|no i can'?t|can'?t)\b[\s.!,]*$", re.IGNORECASE)

_FLAT_FULL_RE = re.compile(
    r"\b(fully flat|completely flat|flat on the bed|fully straight|completely straight|all the way straight|"
    r"knee (?:is|goes|gets) flat|get it flat|lies flat|straight(?:en)? (?:it )?fully|goes (?:fully )?flat)\b",
    re.IGNORECASE,
)
_FLAT_NEAR_RE = re.compile(
    r"\b(almost|nearly|not quite|close to|just about|very nearly|a (?:tiny|small|little) gap|just short of)\b",
    re.IGNORECASE,
)
_FLAT_NOT_RE = re.compile(
    r"\b(can'?t (?:get it|get the knee|straighten|get my knee)[^.]*(?:flat|straight)|won'?t go flat|doesn'?t go flat|"
    r"not flat|still bent|stays bent|won'?t straighten|can'?t straighten|a big gap|big gap under)\b",
    re.IGNORECASE,
)

_MINUTES_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:-|to)?\s*(?:\d+(?:\.\d+)?\s*)?(?:min|mins|minutes|minute)\b", re.IGNORECASE)
_HOURS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b", re.IGNORECASE)
_HALF_HOUR_RE = re.compile(r"\bhalf an hour\b|\bhalf hour\b|\b30 ?min", re.IGNORECASE)
_AN_HOUR_RE = re.compile(r"\ban hour\b|\bone hour\b", re.IGNORECASE)
_MORE_THAN_TEN_RE = re.compile(r"\b(more than|over|longer than|above)\s+(?:ten|10)\s*(?:min|mins|minutes)?\b", re.IGNORECASE)
_LESS_THAN_TEN_RE = re.compile(r"\b(less than|under|not even|shorter than|below)\s+(?:ten|10)\s*(?:min|mins|minutes)?\b", re.IGNORECASE)
_WALKING_CONTEXT_RE = re.compile(r"\b(walk|walking|walks|stroll|on my feet)\b", re.IGNORECASE)

_STAIRS_CONTEXT_RE = re.compile(r"\b(stairs?|steps?|staircase|upstairs|downstairs)\b", re.IGNORECASE)
_STAIRS_FOOT_OVER_FOOT_RE = re.compile(r"\b(foot over foot|step over step|alternat\w+|normally|like normal|one foot on each|foot after foot)\b", re.IGNORECASE)
_STAIRS_ONE_AT_A_TIME_RE = re.compile(r"\b(one (?:step )?at a time|one step at a time|step by step|step at a time|hand ?rail|the rail|holding (?:on to )?the (?:rail|banister)|banister|one by one|two or three steps|a few steps)\b", re.IGNORECASE)
_STAIRS_NOT_YET_RE = re.compile(r"\b(not yet|haven'?t (?:tried|done|managed|been up)|can'?t (?:do|manage|climb)|no stairs|avoid(?:ing)? (?:the )?stairs|not (?:doing|managing|using) (?:the )?stairs|unable)\b", re.IGNORECASE)

_HELP_NEEDED_RE = re.compile(r"\b(need(?:s|ing)? help|needs? (?:a lot of )?help|someone helps|helps me with|rely on|relying on|can'?t manage (?:the )?(?:cooking|shopping|housework|laundry|bathing)|does (?:the|my) (?:cooking|shopping|laundry))\b", re.IGNORECASE)
_MOST_ACTIVITIES_RE = re.compile(r"\b(most of my (?:usual|normal|everyday|daily) (?:activities|routine|things|tasks)|back to most|back to normal|doing most things|most (?:of my )?(?:daily|everyday) (?:activities|tasks)|manag(?:e|ing) (?:almost )?everything|socks and (?:shoes|shoelaces)|tie my (?:shoes|shoelaces))\b", re.IGNORECASE)
_LIGHT_ACTIVITIES_RE = re.compile(r"\b(light (?:activities|tasks|housework|jobs|duties)|manag(?:e|ing) (?:my own|on my own|myself|my own care)|dress(?:ing)? myself|wash(?:ing)? myself|make (?:my own )?(?:meals|breakfast|tea)|looking after myself|my own care)\b", re.IGNORECASE)

_DRIVING_YES_RE = re.compile(r"\b(started driving|back to driving|back driving|i(?:'m| am) driving|driving again|drove|drive(?:n)? (?:again|to|myself)|allowed to drive now)\b", re.IGNORECASE)
_DRIVING_NO_RE = re.compile(r"\b(not driving|haven'?t (?:driven|started driving)|can'?t drive|not allowed to drive|no driving|not (?:yet )?(?:back )?driving|not drive yet|still not driving)\b", re.IGNORECASE)

_WORK_YES_RE = re.compile(r"\b(back at work|back to work|returned to work|started work again|working again|back in the office|went back to work)\b", re.IGNORECASE)
_WORK_NO_RE = re.compile(r"\b(not back at work|not back to work|off work|haven'?t (?:returned|gone back) to work|still off(?: work| sick)?|not working yet|signed off|not returned to work)\b", re.IGNORECASE)

_PRECAUTION_CONTEXT_RE = re.compile(r"\b(precaution|precautions|90 degrees|right angle|cross(?:ing)? (?:my )?legs|low chair|bend(?:ing)? (?:the|my) hip|hip rules)\b", re.IGNORECASE)
_PRECAUTION_ENDED_RE = re.compile(r"\b(ended|finished|over now|no longer need|lifted|been cleared|surgeon said (?:i can|they'?re (?:over|done|finished))|don'?t have to follow)\b", re.IGNORECASE)
_PRECAUTION_NOT_RE = re.compile(r"\b(not following|haven'?t been following|broke|forgot|slipped|bent past|crossed my legs|not keeping|struggl\w+ to (?:keep|follow)|ignored|not sticking)\b", re.IGNORECASE)
_PRECAUTION_YES_RE = re.compile(r"\b(following|keeping to|sticking to|still (?:doing|following|keeping)|being careful|haven'?t broken|not bending past|avoiding)\b", re.IGNORECASE)

_EXERCISE_CONTEXT_RE = re.compile(r"\b(exercises?|physio (?:programme|program|routine)|home programme|home program)\b", re.IGNORECASE)
_EXERCISE_DONE_RE = re.compile(r"\b(did|done|completed|finished|managed|got through)\b[^.]{0,25}\bexercises?\b|\bexercises?\b[^.]{0,20}\b(done|completed|finished)\b", re.IGNORECASE)
_EXERCISE_MISSED_RE = re.compile(r"\b(didn'?t|haven'?t|did not|have not|couldn'?t|skipped|missed|forgot)\b[^.]{0,25}\bexercises?\b", re.IGNORECASE)


def _detect_field_specific_unknown(lower: str) -> Optional[str]:
    """A message that BOTH expresses "don't know" AND names a specific
    metric ("I don't know my bend angle.") targets that field directly."""
    if not _DONT_KNOW_RE.search(lower):
        return None
    has_flexion_cue = any(c in lower for c in _FLEXION_CUES)
    has_extension_cue = any(c in lower for c in _EXTENSION_CUES)
    if has_flexion_cue and not has_extension_cue:
        return ROM_FLEXION_DEGREES
    if has_extension_cue and not has_flexion_cue:
        return ROM_EXTENSION_DEGREES
    if "minute" in lower or "how long" in lower or "how far" in lower:
        return WALKING_DURATION_MINUTES
    if _STAIRS_CONTEXT_RE.search(lower):
        return STAIRS
    if _PRECAUTION_CONTEXT_RE.search(lower):
        return HIP_PRECAUTIONS
    has_mobility_cue = (
        any(d in lower for d in _MOBILITY_DEVICES)
        or "walking" in lower or "mobility" in lower or "getting around" in lower
    )
    if has_mobility_cue:
        return MOBILITY_STATUS
    if "pain" in lower:
        return PAIN_SCORE
    return None


def _extract_extension_flat(lower: str, pending_field: Optional[str], pending_variant: Optional[str]) -> Optional[ValueRange]:
    """The simpler extension question and its unprompted equivalents."""
    if _FLAT_NOT_RE.search(lower):
        return EXTENSION_FLAT_ANSWERS["not_full"]
    if _FLAT_NEAR_RE.search(lower) and (
        _FLAT_FULL_RE.search(lower) or "flat" in lower or "straight" in lower or "gap" in lower
        or (pending_field == ROM_EXTENSION_DEGREES and pending_variant == "alt")
    ):
        return EXTENSION_FLAT_ANSWERS["near_full"]
    if _FLAT_FULL_RE.search(lower):
        return EXTENSION_FLAT_ANSWERS["full"]
    if pending_field == ROM_EXTENSION_DEGREES and pending_variant == "alt":
        if _AFFIRMATIVE_RE.match(lower):
            return EXTENSION_FLAT_ANSWERS["full"]
        if _NEGATIVE_RE.match(lower):
            return EXTENSION_FLAT_ANSWERS["not_full"]
    return None


_ALT_DURATION_MORE_RE = re.compile(r"^\s*(?:yes,?\s*)?(?:more|longer|over|above)\b", re.IGNORECASE)
_ALT_DURATION_LESS_RE = re.compile(r"^\s*(?:no,?\s*)?(?:less|shorter|under|below|not (?:that|even|yet))\b", re.IGNORECASE)


def _extract_walking_duration(lower: str, pending_field: Optional[str], pending_variant: Optional[str] = None) -> Optional[Any]:
    walking_context = bool(_WALKING_CONTEXT_RE.search(lower)) or pending_field == WALKING_DURATION_MINUTES
    if not walking_context:
        return None
    if _MORE_THAN_TEN_RE.search(lower):
        return WALKING_DURATION_ANSWERS["more"]
    if _LESS_THAN_TEN_RE.search(lower):
        return WALKING_DURATION_ANSWERS["less"]
    if pending_field == WALKING_DURATION_MINUTES and pending_variant == "alt" and not re.search(r"\d", lower):
        # The simpler rephrase asked "more than ten minutes, or less?"
        if _ALT_DURATION_MORE_RE.match(lower):
            return WALKING_DURATION_ANSWERS["more"]
        if _ALT_DURATION_LESS_RE.match(lower):
            return WALKING_DURATION_ANSWERS["less"]
    if _HALF_HOUR_RE.search(lower):
        return 30.0
    if _AN_HOUR_RE.search(lower):
        return 60.0
    hours = _HOURS_RE.search(lower)
    if hours:
        return float(hours.group(1)) * 60.0
    minutes = _MINUTES_RE.search(lower)
    if minutes:
        return float(minutes.group(1))
    return None


def _extract_stairs(lower: str, pending_field: Optional[str]) -> Optional[str]:
    in_context = bool(_STAIRS_CONTEXT_RE.search(lower)) or pending_field == STAIRS
    if not in_context:
        return None
    if _STAIRS_FOOT_OVER_FOOT_RE.search(lower):
        return "foot_over_foot"
    if _STAIRS_NOT_YET_RE.search(lower):
        return "not_yet"
    if _STAIRS_ONE_AT_A_TIME_RE.search(lower):
        return "one_at_a_time"
    if pending_field == STAIRS and _NEGATIVE_RE.match(lower):
        return "not_yet"
    return None


def _extract_daily_activities(lower: str) -> Optional[str]:
    if _MOST_ACTIVITIES_RE.search(lower):
        return "most_activities"
    if _HELP_NEEDED_RE.search(lower):
        return "need_help"
    if _LIGHT_ACTIVITIES_RE.search(lower):
        return "light_activities"
    return None


def _extract_driving(lower: str) -> Optional[str]:
    if _DRIVING_NO_RE.search(lower):
        return "not_driving"
    if _DRIVING_YES_RE.search(lower):
        return "driving"
    return None


def _extract_return_to_work(lower: str) -> Optional[str]:
    if _WORK_NO_RE.search(lower):
        return "not_yet"
    if _WORK_YES_RE.search(lower):
        return "returned"
    return None


def _extract_hip_precautions(lower: str, pending_field: Optional[str]) -> Optional[str]:
    in_context = bool(_PRECAUTION_CONTEXT_RE.search(lower)) or pending_field == HIP_PRECAUTIONS
    if not in_context:
        return None
    if _PRECAUTION_ENDED_RE.search(lower):
        return "ended"
    if _PRECAUTION_NOT_RE.search(lower):
        return "not_following"
    if _PRECAUTION_YES_RE.search(lower):
        return "following"
    if pending_field == HIP_PRECAUTIONS:
        if _AFFIRMATIVE_RE.match(lower):
            return "following"
        if _NEGATIVE_RE.match(lower):
            return "not_following"
    return None


def _extract_exercise_completed(lower: str) -> Optional[bool]:
    if not _EXERCISE_CONTEXT_RE.search(lower):
        return None
    if _EXERCISE_MISSED_RE.search(lower):
        return False
    if _EXERCISE_DONE_RE.search(lower):
        return True
    return None


def extract_and_apply(message: str, state: RecoverySessionState) -> ExtractionResult:
    """
    Deterministically extract supported Recovery facts from `message` and
    apply them to `state` THROUGH ITS APPROVED PUBLIC API ONLY. A single
    message may supply several fields at once (multi-slot); the agent then
    asks only what is still missing.

    Order of checks (most specific first):
      1. "Same as yesterday." (narrow helper)
      2. an answer to a pending CONFIRM question ("still about 80?")
      3. field-specific "don't know" ("I don't know my bend angle.")
      4. bare context-free "I don't know", resolved only against the
         pending field
      5. ordinary multi-field extraction
    """
    text = message.strip()
    lower = text.lower()
    pending = state.pending_field
    pending_variant = state.pending_variant

    applied: List[ExtractedFact] = []
    ambiguous: List[AmbiguousField] = []
    marked_unknown: List[str] = []
    confirm_declined: List[str] = []

    tag_day = state.effective_postop_day if state.postop_day_verified else None

    # 1. "Same as yesterday."
    if _SAME_AS_YESTERDAY_RE.match(lower.strip(" .!")):
        if pending is None:
            return ExtractionResult((), (), ())
        resolved = False
        if state.postop_day_verified and state.effective_postop_day is not None:
            prior = state.get_fact(pending)
            if prior is not None and prior.effective_postop_day == state.effective_postop_day - 1:
                state.set_fact(pending, prior.value, effective_postop_day=state.effective_postop_day)
                applied.append(ExtractedFact(pending, prior.value))
                resolved = True
        if not resolved:
            state.mark_unknown(pending)
            marked_unknown.append(pending)
        return ExtractionResult(tuple(applied), tuple(ambiguous), tuple(marked_unknown))

    # 2. Confirmation of a logged value ("still about 80 degrees?").
    confirm_value = state.pending_confirm_value
    if pending is not None and confirm_value is not None:
        has_number = bool(re.search(r"\d", lower))
        if not has_number:
            if _AFFIRMATIVE_RE.match(lower):
                state.set_fact(pending, confirm_value, effective_postop_day=tag_day)
                return ExtractionResult((ExtractedFact(pending, confirm_value),), (), ())
            if _DONT_KNOW_RE.search(lower):
                # Can't confirm AND doesn't know the number: the offer is
                # withdrawn and the field counts as one miss, so the
                # simpler rephrase is asked next.
                state.note_confirm_declined(pending)
                state.mark_unknown(pending)
                return ExtractionResult((), (), (pending,), (pending,))
            if _NEGATIVE_RE.match(lower):
                state.note_confirm_declined(pending)
                return ExtractionResult((), (), (), (pending,))
        else:
            # A number overrides the logged value -- the offer is withdrawn
            # so it is never re-offered if the number turns out unusable.
            state.note_confirm_declined(pending)
            confirm_declined.append(pending)
        # Anything else falls through to ordinary extraction.

    # 3. Field-specific "don't know" -- never when the message also carries
    # a number ("not sure, maybe 80 degrees" is an answer, not a non-answer).
    has_digit = bool(re.search(r"\d", lower))
    specific_unknown_field = None if has_digit else _detect_field_specific_unknown(lower)
    if specific_unknown_field is not None:
        state.mark_unknown(specific_unknown_field)
        marked_unknown.append(specific_unknown_field)
        return ExtractionResult(tuple(applied), tuple(ambiguous), tuple(marked_unknown))

    # 4. Bare "don't know" -- only resolvable against a pending field.
    stripped = re.sub(r"[^\w\s]", "", lower).strip()
    stripped = re.sub(r"\s+", " ", stripped)
    if stripped in _BARE_DONT_KNOW_NORMALIZED or (
        not has_digit and _DONT_KNOW_RE.search(lower) and len(stripped.split()) <= 6
    ):
        if pending is not None:
            state.mark_unknown(pending)
            marked_unknown.append(pending)
        return ExtractionResult(tuple(applied), tuple(ambiguous), tuple(marked_unknown))

    # 5. Ordinary multi-field extraction.
    mobility_fact, mobility_ambiguous = _extract_mobility(text, lower)
    if mobility_fact is not None:
        applied.append(mobility_fact)
    if mobility_ambiguous is not None:
        ambiguous.append(mobility_ambiguous)

    # A degrees value with no bend/straighten cue and nothing pending (the
    # opening message: "about 60 degrees") is the bend angle -- the first
    # thing the interview would ask -- as long as that is still open.
    default_rom_target = None
    if (
        pending is None
        and ROM_FLEXION_DEGREES in asked_metrics_for(state.procedure)
        and not state.is_current(ROM_FLEXION_DEGREES)
    ):
        default_rom_target = ROM_FLEXION_DEGREES
    rom_facts, rom_ambiguous = _extract_rom(text, lower, pending, default_rom_target)
    applied.extend(rom_facts)
    ambiguous.extend(rom_ambiguous)

    if not any(f.field_name == ROM_EXTENSION_DEGREES for f in rom_facts):
        flat = _extract_extension_flat(lower, pending, pending_variant)
        if flat is not None:
            applied.append(ExtractedFact(ROM_EXTENSION_DEGREES, flat))

    duration = _extract_walking_duration(lower, pending, pending_variant)
    if duration is not None:
        applied.append(ExtractedFact(WALKING_DURATION_MINUTES, duration))

    stairs = _extract_stairs(lower, pending)
    if stairs is not None:
        applied.append(ExtractedFact(STAIRS, stairs))

    daily = _extract_daily_activities(lower)
    if daily is not None:
        applied.append(ExtractedFact(DAILY_ACTIVITIES, daily))

    driving = _extract_driving(lower)
    if driving is not None:
        applied.append(ExtractedFact(DRIVING, driving))

    work = _extract_return_to_work(lower)
    if work is not None:
        applied.append(ExtractedFact(RETURN_TO_WORK, work))

    precautions = _extract_hip_precautions(lower, pending)
    if precautions is not None:
        applied.append(ExtractedFact(HIP_PRECAUTIONS, precautions))

    exercise = _extract_exercise_completed(lower)
    if exercise is not None:
        applied.append(ExtractedFact(EXERCISE_COMPLETED, exercise))

    # A bare (or short, single) number answers whichever numeric field is
    # pending -- and only that field, only in that field's own unit, and
    # for flexion/extension only in the plausible range. A number that does
    # not fit ("about 5 minutes" while waiting for flexion) is a non-fit:
    # nothing is stored and the clarifying question follows.
    unfit: List[str] = []
    if not applied and pending in NUMERIC_FIELDS:
        value = pending_number(lower, pending)
        if value is not None:
            applied.append(ExtractedFact(pending, value))
        elif pending in ROM_FIELDS and has_digit and not _PAIN_RE.search(lower):
            unfit.append(pending)

    pain_match = _PAIN_RE.search(lower)
    if pain_match:
        applied.append(ExtractedFact(PAIN_SCORE, int(pain_match.group(1))))

    # A yes/no to the PRIMARY (degrees) extension question is not a
    # number: treat it as "don't know the number" so the simpler flat-on-
    # the-bed rephrase is asked next.
    if (
        not applied and not unfit and pending == ROM_EXTENSION_DEGREES and pending_variant == "primary"
        and (_AFFIRMATIVE_RE.match(lower) or _NEGATIVE_RE.match(lower))
    ):
        state.mark_unknown(pending)
        marked_unknown.append(pending)
        return ExtractionResult((), tuple(ambiguous), tuple(marked_unknown))

    for fact in applied:
        state.set_fact(fact.field_name, fact.value, effective_postop_day=tag_day)

    return ExtractionResult(
        tuple(applied), tuple(ambiguous), tuple(marked_unknown), tuple(confirm_declined), tuple(unfit),
    )


# ============================================================================
# MILESTONE DATA -- loaded from agents/data/recovery_milestones.json
# ============================================================================

LONG_TERM = "long_term"
_DATA_PATH = Path(__file__).resolve().parent / "data" / "recovery_milestones.json"
_BACKEND_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class MilestoneEntry:
    procedure: str
    checkpoint: Any            # int day, or LONG_TERM
    metric: str
    kind: str                  # "numeric" | "categorical" | "state"
    expected_state: str
    source_id: str
    source_url: Optional[str]
    source_corpus: str
    quote: str
    range_low: Optional[float] = None
    range_high: Optional[float] = None
    unit: Optional[str] = None
    accepted_values: Tuple[str, ...] = ()

    @property
    def is_long_term(self) -> bool:
        return self.checkpoint == LONG_TERM

    @property
    def checkpoint_day(self) -> Optional[int]:
        return None if self.is_long_term else int(self.checkpoint)


@dataclass(frozen=True)
class MilestoneTable:
    entries: Tuple[MilestoneEntry, ...]
    checkpoint_days: Tuple[int, ...]
    long_term_after_day: int
    vocabularies: Dict[str, Tuple[str, ...]]
    source_path: str

    def for_metric(self, procedure: str, metric: str) -> List[MilestoneEntry]:
        return [e for e in self.entries if e.procedure == procedure and e.metric == metric]

    def at_checkpoint(self, procedure: str, checkpoint: Any) -> List[MilestoneEntry]:
        return [e for e in self.entries if e.procedure == procedure and e.checkpoint == checkpoint]

    def procedures(self) -> Tuple[str, ...]:
        seen: List[str] = []
        for e in self.entries:
            if e.procedure not in seen:
                seen.append(e.procedure)
        return tuple(seen)


class MilestoneDataError(ValueError):
    """The milestone file is missing, malformed or fails validation."""


_REQUIRED_KEYS = ("procedure", "checkpoint", "metric", "kind", "expected_state", "source_id", "source_corpus", "quote")
_KNOWN_METRICS = (
    ROM_FLEXION_DEGREES, ROM_EXTENSION_DEGREES, MOBILITY_STATUS, WALKING_DURATION_MINUTES, STAIRS,
    DAILY_ACTIVITIES, DRIVING, RETURN_TO_WORK, HIP_PRECAUTIONS,
)


def _validate_entry(raw: Dict[str, Any], index: int, vocabularies: Dict[str, Tuple[str, ...]], checkpoint_days: Sequence[int]) -> MilestoneEntry:
    for key in _REQUIRED_KEYS:
        if key not in raw:
            raise MilestoneDataError(f"entry {index}: missing key {key!r}")
    procedure = str(raw["procedure"]).upper()
    if procedure not in ("TKA", "THA"):
        raise MilestoneDataError(f"entry {index}: unknown procedure {raw['procedure']!r}")
    checkpoint = raw["checkpoint"]
    if checkpoint != LONG_TERM:
        if not isinstance(checkpoint, int) or isinstance(checkpoint, bool) or checkpoint not in checkpoint_days:
            raise MilestoneDataError(f"entry {index}: checkpoint {checkpoint!r} is not one of {list(checkpoint_days)} or {LONG_TERM!r}")
    metric = str(raw["metric"])
    if metric not in _KNOWN_METRICS:
        raise MilestoneDataError(f"entry {index}: unknown metric {metric!r}")
    if procedure == "THA" and metric in ROM_FIELDS:
        raise MilestoneDataError(f"entry {index}: THA must not carry knee ROM entries")
    kind = str(raw["kind"])
    if kind not in ("numeric", "categorical", "state"):
        raise MilestoneDataError(f"entry {index}: unknown kind {kind!r}")
    if not str(raw["expected_state"]).strip():
        raise MilestoneDataError(f"entry {index}: expected_state must be non-empty")
    if not str(raw["quote"]).strip():
        raise MilestoneDataError(f"entry {index}: quote must be non-empty")

    range_low = raw.get("range_low")
    range_high = raw.get("range_high")
    accepted = tuple(raw.get("accepted_values") or ())
    if kind == "numeric":
        if range_low is None and range_high is None:
            raise MilestoneDataError(f"entry {index}: numeric entry needs range_low and/or range_high")
        for bound in (range_low, range_high):
            if bound is not None and (isinstance(bound, bool) or not isinstance(bound, (int, float))):
                raise MilestoneDataError(f"entry {index}: range bound {bound!r} is not a number")
        if range_low is not None and range_high is not None and range_low > range_high:
            raise MilestoneDataError(f"entry {index}: range_low > range_high")
        if not raw.get("unit"):
            raise MilestoneDataError(f"entry {index}: numeric entry needs a unit")
    elif kind == "categorical":
        vocabulary = vocabularies.get(metric)
        if not vocabulary:
            raise MilestoneDataError(f"entry {index}: no vocabulary for categorical metric {metric!r}")
        if not accepted:
            raise MilestoneDataError(f"entry {index}: categorical entry needs accepted_values")
        for value in accepted:
            if value not in vocabulary:
                raise MilestoneDataError(f"entry {index}: accepted value {value!r} not in vocabulary for {metric!r}")
    else:
        if range_low is not None or range_high is not None:
            raise MilestoneDataError(f"entry {index}: a 'state' entry must not carry numbers")

    return MilestoneEntry(
        procedure=procedure, checkpoint=checkpoint, metric=metric, kind=kind,
        expected_state=str(raw["expected_state"]).strip(), source_id=str(raw["source_id"]),
        source_url=raw.get("source_url"), source_corpus=str(raw["source_corpus"]), quote=str(raw["quote"]).strip(),
        range_low=float(range_low) if range_low is not None else None,
        range_high=float(range_high) if range_high is not None else None,
        unit=raw.get("unit"), accepted_values=accepted,
    )


def load_corpus_ids(corpus_relative_path: str) -> set:
    """Passage ids of one of the corpora the milestone file may cite
    (paths are relative to backend/). Used by validation and tests."""
    path = _BACKEND_DIR / corpus_relative_path
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    items = data if isinstance(data, list) else data.get("documents") or data.get("passages") or []
    return {str(item.get("id")) for item in items if isinstance(item, dict)}


def parse_milestone_file(path: Optional[Path] = None, *, validate_sources: bool = False) -> MilestoneTable:
    """Read and validate the milestone file. `validate_sources=True`
    additionally checks every source_id against its named corpus file --
    the test suite does this; production loads skip the extra file reads."""
    data_path = Path(path) if path is not None else _DATA_PATH
    try:
        with data_path.open(encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError as exc:
        raise MilestoneDataError(f"milestone file not found: {data_path}") from exc
    except json.JSONDecodeError as exc:
        raise MilestoneDataError(f"milestone file is not valid JSON: {exc}") from exc

    checkpoint_days = tuple(int(d) for d in raw.get("checkpoint_days") or ())
    if not checkpoint_days or list(checkpoint_days) != sorted(set(checkpoint_days)):
        raise MilestoneDataError("checkpoint_days must be a sorted list of distinct days")
    long_term_after = int(raw.get("long_term_after_day") or checkpoint_days[-1])
    vocabularies = {k: tuple(v) for k, v in (raw.get("vocabularies") or {}).items()}
    entries_raw = raw.get("entries")
    if not isinstance(entries_raw, list) or not entries_raw:
        raise MilestoneDataError("entries must be a non-empty list")

    entries = [_validate_entry(item, idx, vocabularies, checkpoint_days) for idx, item in enumerate(entries_raw)]

    seen: set = set()
    for e in entries:
        key = (e.procedure, e.checkpoint, e.metric)
        if key in seen:
            raise MilestoneDataError(f"duplicate entry for {key}")
        seen.add(key)

    for procedure in ("TKA", "THA"):
        for day in checkpoint_days:
            if not any(e.procedure == procedure and e.checkpoint == day for e in entries):
                raise MilestoneDataError(f"{procedure} has no entry for checkpoint day {day}")
        if not any(e.procedure == procedure and e.is_long_term for e in entries):
            raise MilestoneDataError(f"{procedure} has no long-term entry")

    if validate_sources:
        ids_by_corpus: Dict[str, set] = {}
        for e in entries:
            if e.source_corpus not in ids_by_corpus:
                ids_by_corpus[e.source_corpus] = load_corpus_ids(e.source_corpus)
            if e.source_id not in ids_by_corpus[e.source_corpus]:
                raise MilestoneDataError(f"{e.procedure} {e.checkpoint} {e.metric}: source {e.source_id!r} not in {e.source_corpus}")

    return MilestoneTable(
        entries=tuple(entries), checkpoint_days=checkpoint_days, long_term_after_day=long_term_after,
        vocabularies=vocabularies, source_path=str(data_path),
    )


@lru_cache(maxsize=1)
def load_milestones() -> MilestoneTable:
    """Cached, validated milestone table for production use."""
    return parse_milestone_file()


def select_checkpoint(procedure: str, metric: str, day: int, table: Optional[MilestoneTable] = None) -> Optional[MilestoneEntry]:
    """
    The entry to compare `metric` against on post-op `day`:
      - after the last checkpoint day: the long-term entry when one exists
        for this metric, otherwise the nearest checkpoint at or before day;
      - otherwise the nearest checkpoint AT OR BEFORE `day`;
      - before the first checkpoint: the first checkpoint's entry (the
        caller reports it as the target to work towards, not as due).
    Returns None only when the metric has no entry at all for the procedure.
    """
    table = table or load_milestones()
    entries = table.for_metric(procedure, metric)
    if not entries:
        return None
    dated = sorted((e for e in entries if not e.is_long_term), key=lambda e: e.checkpoint_day)
    if day > table.long_term_after_day:
        long_term = [e for e in entries if e.is_long_term]
        if long_term:
            return long_term[0]
    at_or_before = [e for e in dated if e.checkpoint_day <= day]
    if at_or_before:
        return at_or_before[-1]
    return dated[0] if dated else None


def next_milestone(procedure: str, day: int, table: Optional[MilestoneTable] = None) -> Tuple[Any, List[MilestoneEntry]]:
    """The next checkpoint after `day` (its day and entries), or
    (LONG_TERM, entries) once every dated checkpoint is behind the patient."""
    table = table or load_milestones()
    for checkpoint_day in table.checkpoint_days:
        if checkpoint_day > day:
            return checkpoint_day, table.at_checkpoint(procedure, checkpoint_day)
    return LONG_TERM, table.at_checkpoint(procedure, LONG_TERM)


def ordinal_of(metric: str, value: str, table: Optional[MilestoneTable] = None) -> Optional[int]:
    table = table or load_milestones()
    vocabulary = table.vocabularies.get(metric) or ()
    return vocabulary.index(value) if value in vocabulary else None


# ============================================================================
# EVIDENCE VIEW -- retained for source attribution only.
# ============================================================================

@dataclass(frozen=True)
class RecoveryEvidence:
    """A small view of a retrieved chunk's metadata. The milestone file is
    now the comparison source; this type is kept so callers that adapt a
    retrieved chunk (recovery_integration.build_recovery_evidence_from_chunk)
    and existing tests keep working. It never gates an assessment."""
    source_id: str
    procedure: str
    days_raw: str


_DAY_RANGE_RE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")


def parse_days_window(days_raw: str) -> Optional[Tuple[int, int]]:
    if not days_raw:
        return None
    match = _DAY_RANGE_RE.match(days_raw)
    if not match:
        return None
    start, end = int(match.group(1)), int(match.group(2))
    if start > end:
        return None
    return start, end


# ============================================================================
# VERDICT / REASON-CODE VOCABULARY -- checkpoint-relative, never a global
# trajectory claim.
# ============================================================================

class CheckpointVerdict:
    TARGET_NOT_YET_DUE = "target_not_yet_due"            # before day 7: target to work towards
    MEETS_STATED_CHECKPOINT = "meets_stated_checkpoint"
    BELOW_STATED_CHECKPOINT = "below_stated_checkpoint"
    EXCEEDS_STATED_RANGE = "exceeds_stated_range"
    OUTSIDE_STATED_RANGE = "outside_stated_range"        # neutral (extension)
    OVERLAPS_STATED_RANGE = "overlaps_stated_range"      # a range answer straddles the stated range
    MATCHES_STATED_STATE = "matches_stated_state"        # categorical: in accepted values
    NOT_YET_AT_STATED_STATE = "not_yet_at_stated_state"
    BEYOND_STATED_STATE = "beyond_stated_state"
    NEEDS_REVIEW = "needs_review"                        # e.g. precautions not being followed
    STATE_ONLY = "state_only"                            # the source gives words, no comparable number


class ReasonCode:
    UNSUPPORTED_PROCEDURE_METRIC = "unsupported_procedure_metric"
    DAY_NOT_VERIFIED = "day_not_verified"
    NO_CHECKPOINT_FOR_METRIC = "no_checkpoint_for_metric"
    VALUE_NOT_CURRENT = "value_not_current"
    INVALID_METRIC_VALUE = "invalid_metric_value"


@dataclass(frozen=True)
class CheckpointResult:
    supported: bool
    verdict: Optional[str]
    procedure: str
    metric: str
    patient_value: Any
    effective_postop_day: Optional[int]
    checkpoint_day: Optional[int]
    source_id: Optional[str]
    reason_code: Optional[str]
    entry: Optional[MilestoneEntry] = None
    applicability_window: Optional[Tuple[int, int]] = None  # kept for older readers; unused

    @property
    def is_long_term(self) -> bool:
        return self.entry is not None and self.entry.is_long_term

    @property
    def source_url(self) -> Optional[str]:
        return self.entry.source_url if self.entry else None


def _is_structurally_valid_number(value: Any, maximum: float) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    f = float(value)
    if f != f or f in (float("inf"), float("-inf")):
        return False
    return 0 <= f <= maximum


def _is_structurally_valid_rom_value(value: Any) -> bool:
    return _is_structurally_valid_number(value, _ROM_STRUCTURAL_MAX_DEGREES)


def is_valid_value_for(metric: str, value: Any, table: Optional[MilestoneTable] = None) -> bool:
    if isinstance(value, ValueRange):
        return True
    if metric in ROM_FIELDS:
        return _is_structurally_valid_rom_value(value)
    if metric == WALKING_DURATION_MINUTES:
        return _is_structurally_valid_number(value, _MINUTES_STRUCTURAL_MAX)
    if metric == EXERCISE_COMPLETED:
        return isinstance(value, bool)
    table = table or load_milestones()
    vocabulary = table.vocabularies.get(metric)
    if vocabulary:
        return isinstance(value, str) and value in vocabulary
    return value is not None


def _compare_point(metric: str, value: float, low: Optional[float], high: Optional[float]) -> str:
    if metric == ROM_EXTENSION_DEGREES:
        # Deliberately NEUTRAL: only within/outside is reported for
        # extension, never a direction.
        within_low = low is None or value >= low
        within_high = high is None or value <= high
        return CheckpointVerdict.MEETS_STATED_CHECKPOINT if (within_low and within_high) else CheckpointVerdict.OUTSIDE_STATED_RANGE
    if low is not None and value < low:
        return CheckpointVerdict.BELOW_STATED_CHECKPOINT
    if high is not None and value > high:
        return CheckpointVerdict.EXCEEDS_STATED_RANGE
    return CheckpointVerdict.MEETS_STATED_CHECKPOINT


def _compare_range(metric: str, value: ValueRange, low: Optional[float], high: Optional[float]) -> str:
    if value.is_point:
        return _compare_point(metric, float(value.low), low, high)
    v_low = value.low if value.low is not None else float("-inf")
    v_high = value.high if value.high is not None else float("inf")
    s_low = low if low is not None else float("-inf")
    s_high = high if high is not None else float("inf")
    starts_above_stated_high = v_low >= s_high if value.low_exclusive else v_low > s_high
    if v_low >= s_low and v_high <= s_high:
        return CheckpointVerdict.MEETS_STATED_CHECKPOINT
    if v_high < s_low:
        return CheckpointVerdict.OUTSIDE_STATED_RANGE if metric == ROM_EXTENSION_DEGREES else CheckpointVerdict.BELOW_STATED_CHECKPOINT
    if starts_above_stated_high:
        return CheckpointVerdict.OUTSIDE_STATED_RANGE if metric == ROM_EXTENSION_DEGREES else CheckpointVerdict.EXCEEDS_STATED_RANGE
    return CheckpointVerdict.OVERLAPS_STATED_RANGE


def _compare_categorical(metric: str, value: str, entry: MilestoneEntry, table: MilestoneTable) -> str:
    if metric == HIP_PRECAUTIONS and value == "not_following":
        return CheckpointVerdict.NEEDS_REVIEW
    if value in entry.accepted_values:
        return CheckpointVerdict.MATCHES_STATED_STATE
    position = ordinal_of(metric, value, table)
    accepted_positions = [p for p in (ordinal_of(metric, v, table) for v in entry.accepted_values) if p is not None]
    if position is None or not accepted_positions:
        return CheckpointVerdict.STATE_ONLY
    if position < min(accepted_positions):
        return CheckpointVerdict.NOT_YET_AT_STATED_STATE
    return CheckpointVerdict.BEYOND_STATED_STATE


def evaluate_checkpoint(
    state: RecoverySessionState,
    *,
    procedure: str,
    metric: str,
    evidence: Optional[RecoveryEvidence] = None,
    table: Optional[MilestoneTable] = None,
) -> CheckpointResult:
    """
    Deterministic checkpoint comparison for one metric on the state's
    VERIFIED day. Gates, in order: metric has an entry for this procedure;
    day verified; a CURRENT value exists (is_current, not merely a fact);
    the value is structurally valid. Then the nearest checkpoint at or
    before the day is chosen (select_checkpoint) and the value compared.
    `evidence` is accepted for backward compatibility and never gates.
    """
    table = table or load_milestones()
    day = state.effective_postop_day

    def _fail(reason: str, entry: Optional[MilestoneEntry] = None) -> CheckpointResult:
        return CheckpointResult(
            supported=False, verdict=None, procedure=procedure, metric=metric, patient_value=None,
            effective_postop_day=day, checkpoint_day=entry.checkpoint_day if entry else None,
            source_id=entry.source_id if entry else None, reason_code=reason, entry=entry,
        )

    if not table.for_metric(procedure, metric):
        return _fail(ReasonCode.UNSUPPORTED_PROCEDURE_METRIC)
    if not state.postop_day_verified or day is None:
        return _fail(ReasonCode.DAY_NOT_VERIFIED)
    entry = select_checkpoint(procedure, metric, day, table)
    if entry is None:
        return _fail(ReasonCode.NO_CHECKPOINT_FOR_METRIC)
    if not state.is_current(metric):
        return _fail(ReasonCode.VALUE_NOT_CURRENT, entry)

    fact = state.get_fact(metric)
    raw_value = fact.value if fact is not None else None
    if not is_valid_value_for(metric, raw_value, table):
        return _fail(ReasonCode.INVALID_METRIC_VALUE, entry)

    value: Any = float(raw_value) if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool) else raw_value

    if entry.kind == "numeric":
        if isinstance(value, ValueRange):
            verdict = _compare_range(metric, value, entry.range_low, entry.range_high)
        else:
            verdict = _compare_point(metric, float(value), entry.range_low, entry.range_high)
    elif entry.kind == "categorical":
        verdict = _compare_categorical(metric, str(value), entry, table) if isinstance(value, str) else CheckpointVerdict.STATE_ONLY
    else:
        verdict = CheckpointVerdict.STATE_ONLY

    # Before the first checkpoint the entry is the target to work towards,
    # not something already due -- reported as such, WITH its target.
    if not entry.is_long_term and entry.checkpoint_day is not None and day < entry.checkpoint_day:
        verdict = CheckpointVerdict.TARGET_NOT_YET_DUE

    return CheckpointResult(
        supported=True, verdict=verdict, procedure=procedure, metric=metric, patient_value=value,
        effective_postop_day=day, checkpoint_day=entry.checkpoint_day, source_id=entry.source_id,
        reason_code=None, entry=entry,
    )


# ============================================================================
# RECOVERY ACTION MODEL
# ============================================================================

class RecoveryAction:
    ASK_FOR_INFORMATION = "ask_for_information"
    AWAIT_INFORMATION = "await_information"
    ASSESS_SUPPORTED_METRIC = "assess_supported_metric"
    PROVIDE_GROUNDED_GUIDANCE = "provide_grounded_guidance"
    DECLINE_TO_ASSESS = "decline_to_assess"


class DecisionReasonCode:
    DAY_UNVERIFIED = "day_unverified"
    NO_SUPPORTED_METRIC_FOR_PROCEDURE = "no_supported_metric_for_procedure"
    FIELD_NEVER_ASKED = "field_never_asked"
    FIELD_PENDING = "field_pending"
    FIELD_UNKNOWN_RETRY_REMAINING = "field_unknown_retry_remaining"
    FIELD_UNAVAILABLE = "field_unavailable"
    RETRY_EXHAUSTED = "retry_exhausted"
    FIELD_AMBIGUOUS = "field_ambiguous"
    CONFIRM_DECLINED = "confirm_declined"
    FIELD_UNFIT = "field_unfit"  # the pending field got a number that does not fit it
    INVALID_METRIC_VALUE = "invalid_metric_value"
    ALL_GATES_PASSED = "all_gates_passed"


_CHECKPOINT_REASON_TO_DECISION_REASON: Dict[str, str] = {
    ReasonCode.UNSUPPORTED_PROCEDURE_METRIC: DecisionReasonCode.NO_SUPPORTED_METRIC_FOR_PROCEDURE,
    ReasonCode.NO_CHECKPOINT_FOR_METRIC: DecisionReasonCode.NO_SUPPORTED_METRIC_FOR_PROCEDURE,
    ReasonCode.DAY_NOT_VERIFIED: DecisionReasonCode.DAY_UNVERIFIED,
    ReasonCode.VALUE_NOT_CURRENT: DecisionReasonCode.FIELD_NEVER_ASKED,
    ReasonCode.INVALID_METRIC_VALUE: DecisionReasonCode.INVALID_METRIC_VALUE,
}


def _map_checkpoint_reason_to_decision_reason(reason_code: Optional[str]) -> str:
    if reason_code is None:
        return DecisionReasonCode.ALL_GATES_PASSED
    return _CHECKPOINT_REASON_TO_DECISION_REASON.get(reason_code, reason_code)


@dataclass(frozen=True)
class DecisionResult:
    action: str
    procedure: str
    metric: str
    reason_code: str


def decide_progress_verdict_action(
    state: RecoverySessionState,
    *,
    procedure: str,
    metric: str,
    evidence: Optional[RecoveryEvidence] = None,
    ambiguous_fields: Tuple[str, ...] = (),
    table: Optional[MilestoneTable] = None,
) -> DecisionResult:
    """
    Decide the next action for ONE metric. PURE: never mutates state.
    Gate order: metric has a sourced entry for the procedure -> verified
    day -> interview state (ambiguous / pending / unavailable / unknown /
    never asked) -> full evaluate_checkpoint() once a current value exists.
    """
    table = table or load_milestones()
    if not table.for_metric(procedure, metric):
        return DecisionResult(RecoveryAction.DECLINE_TO_ASSESS, procedure, metric, DecisionReasonCode.NO_SUPPORTED_METRIC_FOR_PROCEDURE)

    if not state.postop_day_verified or state.effective_postop_day is None:
        return DecisionResult(RecoveryAction.DECLINE_TO_ASSESS, procedure, metric, DecisionReasonCode.DAY_UNVERIFIED)

    if metric in ambiguous_fields:
        return DecisionResult(RecoveryAction.ASK_FOR_INFORMATION, procedure, metric, DecisionReasonCode.FIELD_AMBIGUOUS)

    status = state.status_of(metric)

    if status == FieldStatus.PENDING:
        return DecisionResult(RecoveryAction.AWAIT_INFORMATION, procedure, metric, DecisionReasonCode.FIELD_PENDING)

    if status == FieldStatus.UNAVAILABLE:
        return DecisionResult(RecoveryAction.DECLINE_TO_ASSESS, procedure, metric, DecisionReasonCode.FIELD_UNAVAILABLE)

    if status == FieldStatus.UNKNOWN:
        if state.ask_count_of(metric) < MAX_ASKS_PER_FIELD:
            return DecisionResult(RecoveryAction.ASK_FOR_INFORMATION, procedure, metric, DecisionReasonCode.FIELD_UNKNOWN_RETRY_REMAINING)
        return DecisionResult(RecoveryAction.DECLINE_TO_ASSESS, procedure, metric, DecisionReasonCode.RETRY_EXHAUSTED)

    if not state.is_current(metric):
        reason = DecisionReasonCode.CONFIRM_DECLINED if state.confirm_declined(metric) else DecisionReasonCode.FIELD_NEVER_ASKED
        return DecisionResult(RecoveryAction.ASK_FOR_INFORMATION, procedure, metric, reason)

    checkpoint = evaluate_checkpoint(state, procedure=procedure, metric=metric, table=table)
    if not checkpoint.supported:
        return DecisionResult(RecoveryAction.DECLINE_TO_ASSESS, procedure, metric, _map_checkpoint_reason_to_decision_reason(checkpoint.reason_code))

    return DecisionResult(RecoveryAction.ASSESS_SUPPORTED_METRIC, procedure, metric, DecisionReasonCode.ALL_GATES_PASSED)


# ============================================================================
# TURN PLAN -- which metrics were just supplied, which one to ask next,
# which were exhausted this turn, and whether the interview is complete.
# ============================================================================

@dataclass(frozen=True)
class TurnPlan:
    just_supplied: Tuple[str, ...]          # asked-or-volunteered metrics supplied this turn and now current
    exhausted_this_turn: Tuple[str, ...]    # asked metrics whose retry budget ran out this turn
    next_metric: Optional[str]              # the ONE metric to ask about now (None when complete)
    next_reason: Optional[str]              # DecisionReasonCode for the ask
    remaining_after_next: int               # askable metrics still open after the next question
    complete: bool                          # nothing left to ask -> final assessment


def plan_turn(
    state: RecoverySessionState,
    *,
    procedure: str,
    extraction: ExtractionResult,
    ambiguous_fields: Tuple[str, ...] = (),
    table: Optional[MilestoneTable] = None,
) -> TurnPlan:
    """
    PURE: reads state only through its public API and never mutates it.
    The caller (executor) applies mark_unavailable() for
    `exhausted_this_turn` and mark_pending() for `next_metric`.
    """
    table = table or load_milestones()
    asked = asked_metrics_for(procedure)
    applied_names = tuple(f.field_name for f in extraction.applied_facts)

    just_supplied = tuple(
        m for m in applied_names
        if (m in asked or m in VOLUNTEERED_ONLY_METRICS) and state.is_current(m)
    )
    # De-duplicate while keeping order.
    seen: List[str] = []
    for m in just_supplied:
        if m not in seen:
            seen.append(m)
    just_supplied = tuple(seen)

    exhausted: List[str] = []
    for m in extraction.marked_unknown_fields:
        if m in asked and state.status_of(m) == FieldStatus.UNKNOWN and state.ask_count_of(m) >= MAX_ASKS_PER_FIELD:
            exhausted.append(m)

    def _open(metric: str) -> bool:
        if metric in exhausted:
            return False
        decision = decide_progress_verdict_action(state, procedure=procedure, metric=metric, ambiguous_fields=ambiguous_fields, table=table)
        return decision.action in (RecoveryAction.ASK_FOR_INFORMATION, RecoveryAction.AWAIT_INFORMATION)

    open_metrics = [m for m in asked if _open(m)]

    # Priority for the next question: a metric flagged ambiguous or marked
    # unknown this turn (with a retry left) keeps the floor; then the
    # existing pending field; then canonical order.
    next_metric: Optional[str] = None
    for m in asked:
        if m in ambiguous_fields and m in open_metrics:
            next_metric = m
            break
    if next_metric is None:
        for m in asked:
            if m in extraction.marked_unknown_fields and m in open_metrics:
                next_metric = m
                break
    if next_metric is None and state.pending_field in open_metrics:
        next_metric = state.pending_field
    if next_metric is None and open_metrics:
        next_metric = open_metrics[0]

    next_reason = None
    if next_metric is not None:
        next_reason = decide_progress_verdict_action(
            state, procedure=procedure, metric=next_metric, ambiguous_fields=ambiguous_fields, table=table,
        ).reason_code
        if next_reason == DecisionReasonCode.FIELD_PENDING and next_metric in extraction.unfit_fields:
            next_reason = DecisionReasonCode.FIELD_UNFIT

    remaining_after_next = max(len(open_metrics) - (1 if next_metric else 0), 0)
    return TurnPlan(
        just_supplied=just_supplied, exhausted_this_turn=tuple(exhausted), next_metric=next_metric,
        next_reason=next_reason, remaining_after_next=remaining_after_next, complete=next_metric is None,
    )


def assessable_metrics(state: RecoverySessionState, procedure: str, table: Optional[MilestoneTable] = None) -> List[str]:
    """Every metric with a CURRENT value and a sourced entry -- the asked
    ones in canonical order first, then anything volunteered."""
    table = table or load_milestones()
    ordered = list(asked_metrics_for(procedure)) + [m for m in VOLUNTEERED_ONLY_METRICS if m != EXERCISE_COMPLETED]
    return [m for m in ordered if state.is_current(m) and table.for_metric(procedure, m)]


def missing_asked_metrics(state: RecoverySessionState, procedure: str) -> List[str]:
    """Asked metrics with NO current value (unavailable / never answered)."""
    return [m for m in asked_metrics_for(procedure) if not state.is_current(m)]


# Backward-compatible names (derived from the file at import time).
SUPPORTED_METRICS_BY_PROCEDURE: Dict[str, Tuple[str, ...]] = _supported_metrics_from_file()
OPTIONAL_CONTEXT_FIELDS: Tuple[str, ...] = (PAIN_SCORE,)
