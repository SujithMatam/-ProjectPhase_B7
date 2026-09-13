"""
Recovery Logic -- Pass 1: deterministic fact extraction, milestone/verdict
evaluation, and action decision. Pure logic only.

This module owns everything that can be decided WITHOUT calling RAG, an LLM,
the orchestrator, or IntentClassifier. It operates exclusively through the
approved public API of RecoverySessionState (backend/agents/recovery_state.py)
-- get_fact/status_of/is_current/ask_count_of/pending_field/
effective_postop_day/postop_day_verified for reads, and set_fact/mark_pending/
mark_unknown/mark_unavailable/clear_pending/apply_verified_day/
clear_verified_day for writes. It never reaches into that module's private
internals (_facts, _field_status, _ask_counts, _pending_field,
_effective_postop_day, _postop_day_verified) and never assigns a verification
flag directly.

Explicitly OUT of scope for this pass (see the Pass-1 instructions):
    - orchestrator / continuation routing
    - RecoveryProgressAgent / specialized_agents.py changes
    - ChatAgent changes
    - RAG retrieval calls (evaluate_checkpoint() accepts a small, dependency-
      light RecoveryEvidence VIEW instead -- see its docstring)
    - LLM calls
    - patient-facing response text (everything here returns structured data:
      enums, dataclasses, reason codes -- never prose)

No new persistent state concept (e.g. an "AMBIGUOUS" status) was added to
RecoverySessionState for this pass, per the Section-2 approval boundary.
Extraction ambiguity is represented ONLY as a return value from this module
(AmbiguousField) -- it never mutates RecoverySessionState, and the field
being ambiguous this turn does not touch whatever fact/status was already on
record for it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from agents.recovery_state import FieldStatus, RecoverySessionState


# ============================================================================
# FIELD NAME CONSTANTS -- use these, not ad-hoc strings, for consistency.
# ============================================================================

MOBILITY_STATUS = "mobility_status"
ROM_FLEXION_DEGREES = "rom_flexion_degrees"
ROM_EXTENSION_DEGREES = "rom_extension_degrees"
PAIN_SCORE = "pain_score"


# ============================================================================
# RECOVERY WORKFLOW CONSTANTS -- session/workflow policy, NOT clinical.
# ============================================================================

# Maximum number of times a single field may be asked before the decision
# layer treats it as exhausted (DECLINE_TO_ASSESS for that metric). This is
# the already-agreed retry budget for this branch, not a clinical parameter.
MAX_ASKS_PER_FIELD = 2

# ENGINEERING INPUT-VALIDATION GUARD (NOT a clinical threshold): a single
# hinge joint's angular measurement, represented as one plain degree number
# in this simplified project, cannot structurally exceed roughly a half
# revolution (180 degrees) -- this is a generic geometric sanity ceiling for
# ANY one-joint rotational figure, chosen purely to catch obviously
# corrupted/mistyped input (e.g. "800 degrees"). It is NOT sourced from any
# clinical guideline and does NOT assert a "normal" or "expected" knee ROM
# range -- that would be a clinical threshold, and none exists in the vetted
# corpus for this purpose. Values above this are rejected structurally,
# before ever reaching the checkpoint comparison.
_ROM_STRUCTURAL_MAX_DEGREES = 180.0


# ============================================================================
# EXTRACTION RESULT TYPES
# ============================================================================

@dataclass(frozen=True)
class ExtractedFact:
    field_name: str
    value: Any


@dataclass(frozen=True)
class AmbiguousField:
    """
    One field where the message contained genuinely conflicting current
    values with no basis to prefer one over the other. This is an
    EXTRACTION-LAYER result only -- it is never written into
    RecoverySessionState (there is no AMBIGUOUS FieldStatus), and the prior
    fact/status already on record for this field is left completely
    untouched when this is produced.
    """
    field_name: str
    candidates: Tuple[Any, ...]
    raw_text: str


@dataclass(frozen=True)
class ExtractionResult:
    applied_facts: Tuple[ExtractedFact, ...]
    ambiguous_fields: Tuple[AmbiguousField, ...]
    marked_unknown_fields: Tuple[str, ...]


# ============================================================================
# FACT EXTRACTION -- deterministic, regex-based. No NLP library, no LLM, no
# embeddings. Deliberately narrow: see module docstring.
# ============================================================================

_MOBILITY_DEVICES: Tuple[str, ...] = ("walker", "cane", "crutches")

_INDEPENDENT_PHRASES: Tuple[str, ...] = (
    "walk independently", "walking independently", "walking on my own",
    "without a walker", "without any aid", "without assistance",
    "without help", "on my own now",
)

_PAST_CUES: Tuple[str, ...] = ("before", "used to", "previously", "last week", "was using")
_CURRENT_CUES: Tuple[str, ...] = ("now", "currently", "these days", "today")

_NEGATION_ANYMORE_RE = re.compile(
    r"\bnot\s+using\s+(?:the|a|my)?\s*(walker|cane|crutches)\b[^.]*\b(any\s*more|anymore)\b"
    r"|\bno\s+longer\s+(?:using|use|need)\s+(?:the|a|my)?\s*(walker|cane|crutches)\b"
    r"|\bdon'?t\s+need\s+(?:the|a|my)?\s*(walker|cane|crutches)\b[^.]*\b(any\s*more|anymore)?\b",
    re.IGNORECASE,
)

# Splits a message into rough clauses on commas/semicolons/"but"/"however" --
# just enough to let "I used a walker before, but now I use a cane." attach
# "before" to the walker clause and "now" to the cane clause independently.
# Deliberately NOT a general parser; does not split on "and" (see the
# ambiguity case below, which relies on "and" NOT splitting the clause).
_CLAUSE_SPLIT_RE = re.compile(r"\s*(?:,|;|\bbut\b|\bhowever\b)\s*", re.IGNORECASE)


def _split_clauses(lower: str) -> List[str]:
    parts = [p.strip() for p in _CLAUSE_SPLIT_RE.split(lower) if p.strip()]
    return parts or [lower]


def _extract_mobility(text: str, lower: str) -> Tuple[Optional[ExtractedFact], Optional[AmbiguousField]]:
    clauses = _split_clauses(lower)
    current_candidates: List[str] = []

    for clause in clauses:
        clause_devices = [d for d in _MOBILITY_DEVICES if re.search(r"\b" + d + r"\b", clause)]
        clause_independent = any(p in clause for p in _INDEPENDENT_PHRASES)
        clause_negated_anymore = bool(_NEGATION_ANYMORE_RE.search(clause))
        clause_past = any(c in clause for c in _PAST_CUES)
        clause_current = any(c in clause for c in _CURRENT_CUES)

        if clause_negated_anymore and len(clause_devices) == 1 and not clause_independent:
            # "I'm not using the walker anymore" -- the negation itself is
            # the positive signal for independence, only when no other
            # device is named in the same clause. Do not guess beyond this.
            current_candidates.append("independent")
            continue

        if clause_independent:
            current_candidates.append("independent")
            continue

        if not clause_devices:
            continue

        if clause_past and not clause_current:
            # Purely historical mention in this clause -- nothing current
            # to extract from it.
            continue

        # Default: a clause with no tense cue at all reads as an ordinary
        # present-tense statement ("I'm using a walker."), and a clause with
        # an explicit current cue obviously does too.
        current_candidates.extend(clause_devices)

    if not current_candidates:
        return None, None

    unique_current: List[str] = []
    for c in current_candidates:
        if c not in unique_current:
            unique_current.append(c)

    if len(unique_current) == 1:
        return ExtractedFact(MOBILITY_STATUS, unique_current[0]), None

    # More than one distinct CURRENT candidate ("I'm using a walker and a
    # cane.") with nothing in the message to prefer one over the other --
    # report ambiguity, do not guess based on regex/mention order.
    return None, AmbiguousField(MOBILITY_STATUS, tuple(sorted(unique_current)), text)


_FLEXION_CUES: Tuple[str, ...] = ("bend", "flex", "flexion", "bent")
_EXTENSION_CUES: Tuple[str, ...] = ("straighten", "extend", "extension", "straight")

_DEGREE_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:degrees|deg|°)")
_CORRECTION_RE = re.compile(
    r"\bactually,?\s+(?:it'?s\s+)?(\d+(?:\.\d+)?)\s*(?:degrees|deg|°)?\s*,?\s*not\s+"
    r"(\d+(?:\.\d+)?)\s*(?:degrees|deg|°)?",
    re.IGNORECASE,
)


def _classify_rom_target(lower: str, pending_field: Optional[str]) -> Optional[str]:
    has_flexion_cue = any(c in lower for c in _FLEXION_CUES)
    has_extension_cue = any(c in lower for c in _EXTENSION_CUES)
    if has_flexion_cue and not has_extension_cue:
        return ROM_FLEXION_DEGREES
    if has_extension_cue and not has_flexion_cue:
        return ROM_EXTENSION_DEGREES
    if pending_field in (ROM_FLEXION_DEGREES, ROM_EXTENSION_DEGREES):
        # No cue word in the message itself (e.g. a bare "Actually it's 70,
        # not 80.") -- attribute it to whichever ROM field the agent is
        # actually waiting on, never guessed independently of that context.
        return pending_field
    return None


def _extract_rom(
    text: str, lower: str, pending_field: Optional[str]
) -> Tuple[List[ExtractedFact], List[AmbiguousField]]:
    facts: List[ExtractedFact] = []
    ambiguous: List[AmbiguousField] = []

    correction = _CORRECTION_RE.search(lower)
    if correction:
        corrected_value = float(correction.group(1))
        target = _classify_rom_target(lower, pending_field)
        if target is not None:
            facts.append(ExtractedFact(target, corrected_value))
        else:
            # Cannot attribute the correction to flexion or extension --
            # do not guess.
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
            target = _classify_rom_target(lower, pending_field)
            if target is not None:
                facts.append(ExtractedFact(target, value))
            # else: no attributable metric and no relevant pending field --
            # silently skip this number rather than guess.

    return facts, ambiguous


_PAIN_RE = re.compile(r"\bpain\b[^.\d]{0,15}?(\d{1,2})\s*(?:/\s*10|out of\s*10)?", re.IGNORECASE)

_DONT_KNOW_RE = re.compile(r"\b(i\s+don'?t\s+know|not\s+sure|no\s+idea)\b", re.IGNORECASE)
_BARE_DONT_KNOW_NORMALIZED = {"i dont know", "not sure", "no idea"}
_SAME_AS_YESTERDAY_RE = re.compile(r"^same as yesterday$", re.IGNORECASE)


def _detect_field_specific_unknown(lower: str) -> Optional[str]:
    """A message that BOTH expresses "don't know" AND names a specific
    metric (e.g. "I don't know my bend angle.") targets that field directly
    -- independent of whatever field happens to be pending."""
    if not _DONT_KNOW_RE.search(lower):
        return None
    has_flexion_cue = any(c in lower for c in _FLEXION_CUES)
    has_extension_cue = any(c in lower for c in _EXTENSION_CUES)
    if has_flexion_cue and not has_extension_cue:
        return ROM_FLEXION_DEGREES
    if has_extension_cue and not has_flexion_cue:
        return ROM_EXTENSION_DEGREES
    has_mobility_cue = (
        any(d in lower for d in _MOBILITY_DEVICES)
        or "walking" in lower or "mobility" in lower or "getting around" in lower
    )
    if has_mobility_cue:
        return MOBILITY_STATUS
    if "pain" in lower:
        return PAIN_SCORE
    return None


def extract_and_apply(message: str, state: RecoverySessionState) -> ExtractionResult:
    """
    Deterministically extract supported Recovery facts from `message` and
    apply them to `state` THROUGH ITS APPROVED PUBLIC API ONLY (set_fact /
    mark_unknown). Returns a structured ExtractionResult describing what was
    applied, what was ambiguous (never applied), and which fields were
    marked UNKNOWN this turn.

    Order of checks (most specific first):
      1. "Same as yesterday." (Section 5's one narrow helper)
      2. field-specific "don't know" ("I don't know my bend angle.")
      3. bare context-free "I don't know" / "not sure" / "no idea",
         resolved only against state.pending_field
      4. ordinary multi-field extraction (mobility, ROM, pain)
    """
    text = message.strip()
    lower = text.lower()

    applied: List[ExtractedFact] = []
    ambiguous: List[AmbiguousField] = []
    marked_unknown: List[str] = []

    # 1. "Same as yesterday." -- narrow rule only, per Section 5.
    if _SAME_AS_YESTERDAY_RE.match(lower.strip(" .!")):
        pending = state.pending_field
        if pending is None:
            # EXPLICIT GUARD: with no pending field there is nothing to
            # resolve "same as yesterday" against -- must NOT copy any fact
            # forward and must NOT guess a target field. No-op.
            return ExtractionResult(tuple(applied), tuple(ambiguous), tuple(marked_unknown))

        resolved = False
        if state.postop_day_verified and state.effective_postop_day is not None:
            prior = state.get_fact(pending)
            if prior is not None and prior.effective_postop_day == state.effective_postop_day - 1:
                state.set_fact(pending, prior.value, effective_postop_day=state.effective_postop_day)
                applied.append(ExtractedFact(pending, prior.value))
                resolved = True
        if not resolved:
            # Cannot safely resolve "same as yesterday" (no prior value, no
            # verified day, or the prior value isn't tagged exactly
            # current_day - 1) -- treated as a non-answer to the pending
            # field, consuming a retry via the approved API, rather than
            # guessing a value.
            state.mark_unknown(pending)
            marked_unknown.append(pending)
        return ExtractionResult(tuple(applied), tuple(ambiguous), tuple(marked_unknown))

    # 2. Field-specific "don't know".
    specific_unknown_field = _detect_field_specific_unknown(lower)
    if specific_unknown_field is not None:
        state.mark_unknown(specific_unknown_field)
        marked_unknown.append(specific_unknown_field)
        return ExtractionResult(tuple(applied), tuple(ambiguous), tuple(marked_unknown))

    # 3. Bare context-free "don't know" -- only resolvable against a
    # pending field; never guessed against every field.
    stripped = re.sub(r"[^\w\s]", "", lower).strip()
    stripped = re.sub(r"\s+", " ", stripped)
    if stripped in _BARE_DONT_KNOW_NORMALIZED:
        pending = state.pending_field
        if pending is not None:
            # Capture pending BEFORE calling mark_unknown() -- mark_unknown
            # clears state.pending_field as part of its own atomic
            # transition, so re-reading state.pending_field afterward would
            # incorrectly observe None here.
            state.mark_unknown(pending)
            marked_unknown.append(pending)
        return ExtractionResult(tuple(applied), tuple(ambiguous), tuple(marked_unknown))

    # 4. Ordinary fact extraction -- a single message may supply several
    # fields at once.
    mobility_fact, mobility_ambiguous = _extract_mobility(text, lower)
    if mobility_fact is not None:
        applied.append(mobility_fact)
    if mobility_ambiguous is not None:
        ambiguous.append(mobility_ambiguous)

    rom_facts, rom_ambiguous = _extract_rom(text, lower, state.pending_field)
    applied.extend(rom_facts)
    ambiguous.extend(rom_ambiguous)

    pain_match = _PAIN_RE.search(lower)
    if pain_match:
        applied.append(ExtractedFact(PAIN_SCORE, int(pain_match.group(1))))

    # Tag every applied fact with the state's own VERIFIED day, or None --
    # NEVER a client-supplied day (see module docstring / Section 4).
    tag_day = state.effective_postop_day if state.postop_day_verified else None
    for fact in applied:
        state.set_fact(fact.field_name, fact.value, effective_postop_day=tag_day)

    return ExtractionResult(tuple(applied), tuple(ambiguous), tuple(marked_unknown))


# ============================================================================
# PROCEDURE / METRIC REQUIREMENTS
# ============================================================================

@dataclass(frozen=True)
class MetricRequirement:
    procedure: str
    metric: str


# Metric-specific, not procedure-wide: TKA has two INDEPENDENT requirement
# rows (flexion, extension), each requiring only its own field -- there is
# no single "TKA requires flexion+extension+mobility+pain" gate. Mobility
# and pain are optional context (see OPTIONAL_CONTEXT_FIELDS below); they
# are not required by either row because the corpus provides no comparable
# quantitative threshold for them.
REQUIRED_FOR_PROGRESS_ASSESSMENT: Dict[Tuple[str, str], MetricRequirement] = {
    ("TKA", ROM_FLEXION_DEGREES): MetricRequirement("TKA", ROM_FLEXION_DEGREES),
    ("TKA", ROM_EXTENSION_DEGREES): MetricRequirement("TKA", ROM_EXTENSION_DEGREES),
}

# THA and GEN deliberately have NO rows: no sourced quantitative progress
# milestone exists for either in the current corpus (THA-01 is precautions-
# only; no GEN-specific document exists at all).
SUPPORTED_METRICS_BY_PROCEDURE: Dict[str, Tuple[str, ...]] = {
    "TKA": (ROM_FLEXION_DEGREES, ROM_EXTENSION_DEGREES),
    "THA": (),
    "GEN": (),
}

OPTIONAL_CONTEXT_FIELDS: Tuple[str, ...] = (MOBILITY_STATUS, PAIN_SCORE)


# ============================================================================
# MILESTONE TABLE -- exactly the currently supported source-backed evidence.
# ============================================================================

@dataclass(frozen=True)
class MilestoneDefinition:
    procedure: str
    metric: str
    source_id: str
    checkpoint_day: int
    applicability_days_raw: str
    range_low: float
    range_high: float


# Source (verbatim, backend/rag/data/seed_knowledge.json, id="TKA-03",
# topic "Range of Motion & Extension Milestones", procedure="TKA",
# days="1-21", verified directly against the current repository HEAD before
# writing this table):
#
#   "Target milestones for Total Knee Arthroplasty: By Post-Op Day 7,
#   patients should aim for 70°-90° of passive flexion and
#   near-full extension (0°-5°). Full terminal extension is
#   critical; patients should avoid putting pillows directly under the knee
#   joint, placing pillows under the ankle/calf instead to promote gravity
#   extension."
MILESTONE_TABLE: Dict[Tuple[str, str], MilestoneDefinition] = {
    ("TKA", ROM_FLEXION_DEGREES): MilestoneDefinition(
        procedure="TKA", metric=ROM_FLEXION_DEGREES, source_id="TKA-03",
        checkpoint_day=7, applicability_days_raw="1-21",
        range_low=70.0, range_high=90.0,
    ),
    ("TKA", ROM_EXTENSION_DEGREES): MilestoneDefinition(
        procedure="TKA", metric=ROM_EXTENSION_DEGREES, source_id="TKA-03",
        checkpoint_day=7, applicability_days_raw="1-21",
        range_low=0.0, range_high=5.0,
    ),
}
# No THA rows, no GEN rows, no Day-14/Day-21 rows, no trajectory/interpolation
# entries, no invented safety ceilings -- only what TKA-03 itself states.


# ============================================================================
# EVIDENCE VIEW -- deliberately NOT the real RAG RetrievedChunk type.
# ============================================================================

@dataclass(frozen=True)
class RecoveryEvidence:
    """
    A small, dependency-light VIEW of the metadata evaluate_checkpoint()
    actually needs from a retrieved clinical chunk. Deliberately a standalone
    dataclass here rather than importing rag.knowledge_base.RetrievedChunk,
    to keep this module free of any import-time coupling to the RAG package
    (even though that package's heavy dependencies -- chromadb,
    sentence-transformers -- are themselves lazily loaded, not imported at
    module scope). A later integration pass adapts a real retrieved chunk
    into this small view; no RAG call happens in this pass.
    """
    source_id: str
    procedure: str
    days_raw: str


_DAY_RANGE_RE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")


def parse_days_window(days_raw: str) -> Optional[Tuple[int, int]]:
    """Deterministic parser for the source's own 'days' applicability
    metadata (e.g. "1-21"). Returns (start_day, end_day), or None if
    malformed/unusable -- callers must then treat evidence as insufficient
    rather than inventing a default window."""
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
# trajectory claim. See module docstring / Pass-1 instructions Section 9.
# ============================================================================

class CheckpointVerdict:
    TARGET_NOT_YET_DUE = "target_not_yet_due"
    MEETS_STATED_CHECKPOINT = "meets_stated_checkpoint"
    BELOW_STATED_CHECKPOINT = "below_stated_checkpoint"
    EXCEEDS_STATED_RANGE = "exceeds_stated_range"
    OUTSIDE_STATED_RANGE = "outside_stated_range"


class ReasonCode:
    UNSUPPORTED_PROCEDURE_METRIC = "unsupported_procedure_metric"
    DAY_NOT_VERIFIED = "day_not_verified"
    EVIDENCE_MISSING = "evidence_missing"
    EVIDENCE_SOURCE_MISMATCH = "evidence_source_mismatch"
    EVIDENCE_PROCEDURE_MISMATCH = "evidence_procedure_mismatch"
    MALFORMED_APPLICABILITY_WINDOW = "malformed_applicability_window"
    DAY_OUTSIDE_APPLICABILITY_WINDOW = "day_outside_applicability_window"
    VALUE_NOT_CURRENT = "value_not_current"
    INVALID_METRIC_VALUE = "invalid_metric_value"


@dataclass(frozen=True)
class CheckpointResult:
    supported: bool
    verdict: Optional[str]
    procedure: str
    metric: str
    patient_value: Optional[float]
    effective_postop_day: Optional[int]
    checkpoint_day: Optional[int]
    source_id: Optional[str]
    applicability_window: Optional[Tuple[int, int]]
    reason_code: Optional[str]


def _is_structurally_valid_rom_value(value: Any) -> bool:
    """ENGINEERING input-validity check -- see _ROM_STRUCTURAL_MAX_DEGREES
    docstring above. Not a clinical plausibility range."""
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    f = float(value)
    if f != f:  # NaN
        return False
    if f in (float("inf"), float("-inf")):
        return False
    if f < 0:
        return False
    if f > _ROM_STRUCTURAL_MAX_DEGREES:
        return False
    return True


def _compare_flexion(value: float, low: float, high: float) -> str:
    if value < low:
        return CheckpointVerdict.BELOW_STATED_CHECKPOINT
    if value > high:
        return CheckpointVerdict.EXCEEDS_STATED_RANGE
    return CheckpointVerdict.MEETS_STATED_CHECKPOINT


def _compare_extension(value: float, low: float, high: float) -> str:
    # Deliberately NEUTRAL / non-directional: extension does NOT share
    # flexion's "higher good, lower bad" semantics in this source. Only
    # WITHIN vs OUTSIDE the stated range is ever reported -- never a
    # direction, and never "better"/"worse"/"ahead"/"behind".
    if low <= value <= high:
        return CheckpointVerdict.MEETS_STATED_CHECKPOINT
    return CheckpointVerdict.OUTSIDE_STATED_RANGE


def _evaluate_evidence_gate(
    state: RecoverySessionState,
    *,
    procedure: str,
    metric: str,
    evidence: Optional[RecoveryEvidence],
) -> Optional[CheckpointResult]:
    """
    Checks every gate that does NOT require the metric's own patient value:
    supported procedure/metric, verified day, evidence presence, source/
    procedure match, applicability-window parse, and day-inside-window.

    Returns a populated (failure) CheckpointResult the moment any of these
    gates fails, or None if every evidence/day gate passed (meaning the
    caller may proceed to value-dependent checks). Shared by
    evaluate_checkpoint() and decide_progress_verdict_action() so there is
    exactly ONE implementation of this logic, never two competing copies.
    """
    milestone = MILESTONE_TABLE.get((procedure, metric))
    if milestone is None:
        return CheckpointResult(
            supported=False, verdict=None, procedure=procedure, metric=metric,
            patient_value=None, effective_postop_day=state.effective_postop_day,
            checkpoint_day=None, source_id=evidence.source_id if evidence else None,
            applicability_window=None, reason_code=ReasonCode.UNSUPPORTED_PROCEDURE_METRIC,
        )

    if not state.postop_day_verified or state.effective_postop_day is None:
        return CheckpointResult(
            supported=False, verdict=None, procedure=procedure, metric=metric,
            patient_value=None, effective_postop_day=state.effective_postop_day,
            checkpoint_day=milestone.checkpoint_day, source_id=evidence.source_id if evidence else None,
            applicability_window=None, reason_code=ReasonCode.DAY_NOT_VERIFIED,
        )

    if evidence is None:
        return CheckpointResult(
            supported=False, verdict=None, procedure=procedure, metric=metric,
            patient_value=None, effective_postop_day=state.effective_postop_day,
            checkpoint_day=milestone.checkpoint_day, source_id=None,
            applicability_window=None, reason_code=ReasonCode.EVIDENCE_MISSING,
        )

    if evidence.source_id != milestone.source_id:
        return CheckpointResult(
            supported=False, verdict=None, procedure=procedure, metric=metric,
            patient_value=None, effective_postop_day=state.effective_postop_day,
            checkpoint_day=milestone.checkpoint_day, source_id=evidence.source_id,
            applicability_window=None, reason_code=ReasonCode.EVIDENCE_SOURCE_MISMATCH,
        )

    if evidence.procedure != milestone.procedure:
        return CheckpointResult(
            supported=False, verdict=None, procedure=procedure, metric=metric,
            patient_value=None, effective_postop_day=state.effective_postop_day,
            checkpoint_day=milestone.checkpoint_day, source_id=evidence.source_id,
            applicability_window=None, reason_code=ReasonCode.EVIDENCE_PROCEDURE_MISMATCH,
        )

    window = parse_days_window(evidence.days_raw)
    if window is None:
        return CheckpointResult(
            supported=False, verdict=None, procedure=procedure, metric=metric,
            patient_value=None, effective_postop_day=state.effective_postop_day,
            checkpoint_day=milestone.checkpoint_day, source_id=evidence.source_id,
            applicability_window=None, reason_code=ReasonCode.MALFORMED_APPLICABILITY_WINDOW,
        )

    start_day, end_day = window
    if not (start_day <= state.effective_postop_day <= end_day):
        return CheckpointResult(
            supported=False, verdict=None, procedure=procedure, metric=metric,
            patient_value=None, effective_postop_day=state.effective_postop_day,
            checkpoint_day=milestone.checkpoint_day, source_id=evidence.source_id,
            applicability_window=window, reason_code=ReasonCode.DAY_OUTSIDE_APPLICABILITY_WINDOW,
        )

    return None


def evaluate_checkpoint(
    state: RecoverySessionState,
    *,
    procedure: str,
    metric: str,
    evidence: Optional[RecoveryEvidence],
) -> CheckpointResult:
    """
    Deterministic, source-gated checkpoint comparison. Gates BEFORE any
    numeric comparison, in this exact order (see Pass-1 instructions
    Section 11/12):

        1-6. evidence/day gates -- see _evaluate_evidence_gate() docstring
             (supported procedure/metric, day verified, evidence present,
             source match, procedure match, window parses, day in window)
        7. field value is CURRENT (state.is_current(metric) -- not merely
           "a fact exists")
        8. the stored value is structurally valid (not negative / not
           absurd / numeric -- see _is_structurally_valid_rom_value)
        9. checkpoint actually due yet (effective_postop_day >= checkpoint_day)
       10. only now compare the value against the stated range

    Reads state ONLY through its approved public API (is_current, get_fact,
    postop_day_verified, effective_postop_day) -- never touches private
    internals.
    """
    gate_failure = _evaluate_evidence_gate(state, procedure=procedure, metric=metric, evidence=evidence)
    if gate_failure is not None:
        return gate_failure

    milestone = MILESTONE_TABLE[(procedure, metric)]
    # evidence is guaranteed non-None and window is guaranteed parseable --
    # both already verified by _evaluate_evidence_gate() above.
    window = parse_days_window(evidence.days_raw)

    if not state.is_current(metric):
        return CheckpointResult(
            supported=False, verdict=None, procedure=procedure, metric=metric,
            patient_value=None, effective_postop_day=state.effective_postop_day,
            checkpoint_day=milestone.checkpoint_day, source_id=evidence.source_id,
            applicability_window=window, reason_code=ReasonCode.VALUE_NOT_CURRENT,
        )

    fact = state.get_fact(metric)
    raw_value = fact.value if fact is not None else None

    if not _is_structurally_valid_rom_value(raw_value):
        return CheckpointResult(
            supported=False, verdict=None, procedure=procedure, metric=metric,
            patient_value=None, effective_postop_day=state.effective_postop_day,
            checkpoint_day=milestone.checkpoint_day, source_id=evidence.source_id,
            applicability_window=window, reason_code=ReasonCode.INVALID_METRIC_VALUE,
        )

    value = float(raw_value)

    if state.effective_postop_day < milestone.checkpoint_day:
        return CheckpointResult(
            supported=True, verdict=CheckpointVerdict.TARGET_NOT_YET_DUE,
            procedure=procedure, metric=metric, patient_value=value,
            effective_postop_day=state.effective_postop_day,
            checkpoint_day=milestone.checkpoint_day, source_id=evidence.source_id,
            applicability_window=window, reason_code=None,
        )

    if metric == ROM_EXTENSION_DEGREES:
        verdict = _compare_extension(value, milestone.range_low, milestone.range_high)
    else:
        verdict = _compare_flexion(value, milestone.range_low, milestone.range_high)

    return CheckpointResult(
        supported=True, verdict=verdict, procedure=procedure, metric=metric,
        patient_value=value, effective_postop_day=state.effective_postop_day,
        checkpoint_day=milestone.checkpoint_day, source_id=evidence.source_id,
        applicability_window=window, reason_code=None,
    )


# ============================================================================
# RECOVERY ACTION MODEL
# ============================================================================

class RecoveryAction:
    ASK_FOR_INFORMATION = "ask_for_information"
    AWAIT_INFORMATION = "await_information"
    ASSESS_SUPPORTED_METRIC = "assess_supported_metric"
    # Not produced by decide_progress_verdict_action() in this pass -- it
    # belongs to a separate, later decision path that classifies whether a
    # message is a progress-VERDICT request at all vs. an ordinary guidance
    # question. Included here only so the action model is complete.
    PROVIDE_GROUNDED_GUIDANCE = "provide_grounded_guidance"
    DECLINE_TO_ASSESS = "decline_to_assess"


class DecisionReasonCode:
    DAY_UNVERIFIED = "day_unverified"
    NO_SUPPORTED_METRIC_FOR_PROCEDURE = "no_supported_metric_for_procedure"
    EVIDENCE_MISSING = "evidence_missing"
    EVIDENCE_SOURCE_MISMATCH = "evidence_source_mismatch"
    EVIDENCE_PROCEDURE_MISMATCH = "evidence_procedure_mismatch"
    MALFORMED_APPLICABILITY_WINDOW = "malformed_applicability_window"
    DAY_OUTSIDE_APPLICABILITY_WINDOW = "day_outside_applicability_window"
    FIELD_NEVER_ASKED = "field_never_asked"
    FIELD_PENDING = "field_pending"
    FIELD_UNKNOWN_RETRY_REMAINING = "field_unknown_retry_remaining"
    FIELD_UNAVAILABLE = "field_unavailable"
    RETRY_EXHAUSTED = "retry_exhausted"
    FIELD_AMBIGUOUS = "field_ambiguous"
    INVALID_METRIC_VALUE = "invalid_metric_value"
    ALL_GATES_PASSED = "all_gates_passed"


# Explicit mapping from evaluate_checkpoint()'s ReasonCode vocabulary to
# DecisionReasonCode, used ONLY when decide_progress_verdict_action() must
# propagate a checkpoint-layer failure into its own DecisionResult. Kept as
# an explicit table (not string reuse) so the two vocabularies -- "why the
# decision layer won't act" vs. "why the checkpoint comparison itself is
# unsupported" -- stay reviewable as separate, named concepts even where
# they describe the same underlying gate failure.
_CHECKPOINT_REASON_TO_DECISION_REASON: Dict[str, str] = {
    ReasonCode.UNSUPPORTED_PROCEDURE_METRIC: DecisionReasonCode.NO_SUPPORTED_METRIC_FOR_PROCEDURE,
    ReasonCode.DAY_NOT_VERIFIED: DecisionReasonCode.DAY_UNVERIFIED,
    ReasonCode.EVIDENCE_MISSING: DecisionReasonCode.EVIDENCE_MISSING,
    ReasonCode.EVIDENCE_SOURCE_MISMATCH: DecisionReasonCode.EVIDENCE_SOURCE_MISMATCH,
    ReasonCode.EVIDENCE_PROCEDURE_MISMATCH: DecisionReasonCode.EVIDENCE_PROCEDURE_MISMATCH,
    ReasonCode.MALFORMED_APPLICABILITY_WINDOW: DecisionReasonCode.MALFORMED_APPLICABILITY_WINDOW,
    ReasonCode.DAY_OUTSIDE_APPLICABILITY_WINDOW: DecisionReasonCode.DAY_OUTSIDE_APPLICABILITY_WINDOW,
    # VALUE_NOT_CURRENT should not actually be reachable from the decision
    # function (it already gates on is_current() itself before ever calling
    # evaluate_checkpoint), but mapped defensively rather than left to KeyError.
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
) -> DecisionResult:
    """
    Decide the next Recovery action for a PROGRESS-VERDICT request about one
    (procedure, metric) pair. PURE function: reads RecoverySessionState only
    through its approved public API and NEVER mutates it -- calling this
    twice with identical inputs always returns an identical DecisionResult.
    (Previously this function called state.mark_unavailable() itself when
    retries were exhausted; that state transition is now the responsibility
    of the future agent/action executor, not this decision function.)

    Every DecisionResult this function returns is truthful/actionable by
    itself: it never returns ASSESS_SUPPORTED_METRIC unless
    evaluate_checkpoint() has already confirmed supported=True for the exact
    same state/procedure/metric/evidence.

    Gate order (do not ask for a metric the evidence already proves cannot
    be used):
        1. procedure/metric support
        2. verified day
        3. evidence/source/procedure/applicability-window validity for the
           CURRENT verified day (via the same _evaluate_evidence_gate()
           evaluate_checkpoint() itself uses -- no duplicated gate logic).
           This does NOT require a current patient metric value; it is
           evaluated before any interview-state inspection.
        4. interview/field state (ambiguous / pending / unknown / never
           asked) -- ask/retry/await as needed
        5. once a current value exists, run the FULL evaluate_checkpoint()
           (value validity + comparison) and only return
           ASSESS_SUPPORTED_METRIC when it reports supported=True.

    Does NOT call IntentClassifier, the orchestrator, RAG, or an LLM.
    """
    supported_metrics = SUPPORTED_METRICS_BY_PROCEDURE.get(procedure, ())
    if metric not in supported_metrics:
        # THA/GEN (or an unsupported TKA metric): no sourced deterministic
        # progress verdict exists. This declines ONLY the verdict decision
        # for this (procedure, metric) pair -- it does not make the
        # procedure "unsupported forever"; ordinary grounded guidance is a
        # separate path, untouched here.
        return DecisionResult(
            action=RecoveryAction.DECLINE_TO_ASSESS, procedure=procedure,
            metric=metric, reason_code=DecisionReasonCode.NO_SUPPORTED_METRIC_FOR_PROCEDURE,
        )

    if not state.postop_day_verified or state.effective_postop_day is None:
        return DecisionResult(
            action=RecoveryAction.DECLINE_TO_ASSESS, procedure=procedure,
            metric=metric, reason_code=DecisionReasonCode.DAY_UNVERIFIED,
        )

    # Evidence/source/procedure/window gate -- checked BEFORE interview
    # state, and BEFORE requiring any current patient metric value, so the
    # patient is never asked for a value the evidence already proves cannot
    # be used deterministically.
    evidence_gate_failure = _evaluate_evidence_gate(state, procedure=procedure, metric=metric, evidence=evidence)
    if evidence_gate_failure is not None:
        return DecisionResult(
            action=RecoveryAction.DECLINE_TO_ASSESS, procedure=procedure,
            metric=metric, reason_code=_map_checkpoint_reason_to_decision_reason(evidence_gate_failure.reason_code),
        )

    if metric in ambiguous_fields:
        return DecisionResult(
            action=RecoveryAction.ASK_FOR_INFORMATION, procedure=procedure,
            metric=metric, reason_code=DecisionReasonCode.FIELD_AMBIGUOUS,
        )

    status = state.status_of(metric)

    if status == FieldStatus.PENDING:
        return DecisionResult(
            action=RecoveryAction.AWAIT_INFORMATION, procedure=procedure,
            metric=metric, reason_code=DecisionReasonCode.FIELD_PENDING,
        )

    if status == FieldStatus.UNAVAILABLE:
        return DecisionResult(
            action=RecoveryAction.DECLINE_TO_ASSESS, procedure=procedure,
            metric=metric, reason_code=DecisionReasonCode.FIELD_UNAVAILABLE,
        )

    if status == FieldStatus.UNKNOWN:
        if state.ask_count_of(metric) < MAX_ASKS_PER_FIELD:
            return DecisionResult(
                action=RecoveryAction.ASK_FOR_INFORMATION, procedure=procedure,
                metric=metric, reason_code=DecisionReasonCode.FIELD_UNKNOWN_RETRY_REMAINING,
            )
        # PURE: retries exhausted, but this function does NOT call
        # state.mark_unavailable() itself -- the executor applies that
        # transition. The DecisionResult still names the outcome plainly.
        return DecisionResult(
            action=RecoveryAction.DECLINE_TO_ASSESS, procedure=procedure,
            metric=metric, reason_code=DecisionReasonCode.RETRY_EXHAUSTED,
        )

    # status is NEVER_ASKED here.
    if not state.is_current(metric):
        return DecisionResult(
            action=RecoveryAction.ASK_FOR_INFORMATION, procedure=procedure,
            metric=metric, reason_code=DecisionReasonCode.FIELD_NEVER_ASKED,
        )

    # A current value exists and the evidence gate already passed -- run the
    # FULL checkpoint (value validity + comparison) before ever promising
    # ASSESS_SUPPORTED_METRIC.
    checkpoint = evaluate_checkpoint(state, procedure=procedure, metric=metric, evidence=evidence)
    if not checkpoint.supported:
        return DecisionResult(
            action=RecoveryAction.DECLINE_TO_ASSESS, procedure=procedure,
            metric=metric, reason_code=_map_checkpoint_reason_to_decision_reason(checkpoint.reason_code),
        )

    return DecisionResult(
        action=RecoveryAction.ASSESS_SUPPORTED_METRIC, procedure=procedure,
        metric=metric, reason_code=DecisionReasonCode.ALL_GATES_PASSED,
    )
