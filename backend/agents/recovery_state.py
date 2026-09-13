"""
Recovery Session State -- Design C (server-side, process-scoped state).

This module owns the SINGLE source of truth for an in-progress Recovery
interaction: known recovery facts (mobility, ROM, etc.), which field (if any)
the agent is waiting on an answer for, how many times each field has been
asked, and the server-derived postoperative day for the active recovery
episode.

Why this exists (see the prior investigation for the full evidence trail):
chat_history alone cannot safely carry this. The Flutter client caps
chat_history at the last 10 messages, and ChatAgent independently re-slices to
the last 10 again -- so retry counters, "already asked this", and "patient
said they don't know" all silently evaporate once the conversation runs past
~5-6 ask/answer cycles, because the only place that information lived was raw
message text that has since scrolled out of the window. A teammate's
Medication branch (origin/medication, unmerged) already converged on the same
answer independently for its own multi-turn adherence check
(ProactiveMedicationEngine._PATIENT_MED_STATES) -- this module is Recovery's
analogous, independently-owned equivalent, not a shared dependency on that
branch's code.

Explicit limitations (do not remove this notice when editing):
    - This is PROCESS-SCOPED, IN-MEMORY state. It does NOT survive:
        * a backend restart
        * multiple worker processes running without shared storage
          (e.g. `uvicorn --workers N>1`, or multiple machines behind a
          load balancer) -- each process would keep its own independent copy
        * the future longitudinal/daily-check-in feature, which will need
          real persistence (a database) -- that is explicitly out of scope
          for this branch.
    That limitation is accepted for this branch: the goal here is a
    genuinely agentic Recovery conversation within one sitting, not
    durable cross-session/day tracking.

CANONICAL FIELD-READ API -- future Recovery decision logic (next phase) MUST
use these three methods and must NOT reach into internal dictionaries
directly, assume fact existence implies currentness, or treat interview
status as clinical freshness:

    status_of(field_name)  -> interview/workflow status: NEVER_ASKED /
                               PENDING / UNKNOWN / UNAVAILABLE. This is
                               ask-workflow bookkeeping, not a clinical value.
    get_fact(field_name)   -> the latest stored RecoveryFact for this field,
                               if one exists -- may be HISTORICAL (from an
                               earlier postoperative day).
    is_current(field_name) -> whether that stored fact is usable as the
                               CURRENT verified-postop-day measurement.

To decide whether a field can be used in a current, day-gated assessment,
the canonical pair is:

    status_of(field_name) + is_current(field_name)

with get_fact(field_name) used only to retrieve the stored value itself.
HISTORICAL FACT EXISTENCE != CURRENT MEASUREMENT -- get_fact() returning a
value is not, by itself, permission to use it in a day-gated comparison;
is_current() is the only method that answers that question.

CANONICAL POSTOPERATIVE-DAY API -- the effective_postop_day/
postop_day_verified pair must NEVER be set independently (that recreates the
exact "caller must keep two fields in sync" problem this object exists to
prevent). Both are read-only properties; the only way to change them is:

    apply_verified_day(day) -> set a server-verified day. Atomically sets
                                effective_postop_day = day AND
                                postop_day_verified = True together.
    clear_verified_day()    -> record that no trustworthy day is currently
                                available (missing/malformed/unverifiable
                                surgery_date). Atomically sets
                                postop_day_verified = False AND
                                effective_postop_day = None together, so a
                                stale day value can never be read as if it
                                were still trustworthy.

Both route through one shared internal transition so the transient-interview
reset (pending_field / ask_counts / PENDING-UNKNOWN-UNAVAILABLE statuses)
fires consistently whenever the trustworthy day genuinely changes -- whether
it changes to a new day or to "no longer trustworthy".

This module intentionally does NOT:
    - parse or interpret chat_history (bootstrap-from-history is layered on
      top of this in the Recovery decision logic, not here)
    - decide what the next Recovery action should be
    - call RAG, an LLM, or any other agent
It is purely the state container plus the primitives to create, read, mutate,
expire, and bound it.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


# ============================================================================
# FIELD STATUS
# ============================================================================

class FieldStatus:
    """
    Stored INTERVIEW/WORKFLOW status for one recovery fact field --
    independent of chat_history and independent of whether a value is
    currently known.

    There is deliberately NO "KNOWN" member here. Whether a field has a
    usable current value is a DERIVED question -- answered by calling
    get_fact(field_name) together with is_current(field_name) on
    RecoverySessionState -- never a status stored redundantly alongside the
    fact itself.

    NEVER_ASKED -- no unresolved interview action is on record for this
                   field: either truly never asked, OR the field was
                   previously asked and has since been resolved (a value was
                   supplied, see set_fact()), OR it was demoted from PENDING
                   because a different field became the new pending field
                   (see mark_pending()). This is a workflow signal, not a
                   claim about whether a value exists -- use get_fact()/
                   is_current() for that.
    PENDING     -- the agent just asked about this field; awaiting the
                   patient's reply. At most one field is PENDING at a time
                   (enforced by mark_pending() -- see
                   RecoverySessionState.pending_field).
    UNKNOWN     -- the patient was asked and gave a non-answer ("I don't
                   know"), and at least one retry may still remain (whether
                   retries remain is a decision for the next-phase retry
                   policy, using ask_count_of()).
    UNAVAILABLE -- retries for this field are exhausted for the current
                   interview; do not ask again. A PRIOR fact may still be on
                   record (see get_fact()) -- UNAVAILABLE describes today's
                   interview outcome, not whether historical data exists.
    """

    NEVER_ASKED = "never_asked"
    PENDING = "pending"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


# ============================================================================
# ONE RECOVERY FACT
# ============================================================================

@dataclass(frozen=True)
class RecoveryFact:
    """
    One known recovery value, tagged with the effective postoperative day it
    was reported current for. The day tag is what lets
    RecoverySessionState.is_current() refuse to treat a stale, prior-day
    value as still current today, and is what the (future) "same as
    yesterday" rule will look up.

    Frozen (immutable) so that a caller holding a reference returned by
    get_fact() cannot mutate it in place and silently corrupt state that
    should only change through RecoverySessionState's own methods.
    """

    value: Any
    effective_postop_day: Optional[int]
    updated_at: datetime


# ============================================================================
# RECOVERY SESSION STATE
# ============================================================================

@dataclass
class RecoverySessionState:
    """
    The single source of truth for one active Recovery episode.

    One instance == one (patient, recovery episode) pair -- see
    make_episode_key() for exactly what identifies an "episode". Everything
    the Recovery decision layer needs to decide its next action lives here;
    chat_history is never consulted as a second, competing source of truth
    once this object exists for the episode.

    ALL mutation flows through this class's methods (set_fact, mark_pending,
    mark_unknown, mark_unavailable, clear_pending, apply_verified_day,
    clear_verified_day). Internal storage (_effective_postop_day,
    _postop_day_verified, _facts, _field_status, _ask_counts,
    _pending_field) is private specifically so callers cannot update one
    piece of bookkeeping while forgetting another -- each method below is
    one atomic, self-contained transition, never a set of pieces a caller
    must sequence correctly.
    """

    episode_key: str
    patient_id: str
    procedure: str

    # Raw surgery_date string as last supplied by a request, kept only for
    # diagnostics/debugging -- NOT parsed here (a later phase owns the
    # authoritative clinical derivation with full timezone/Day-1-convention
    # handling). This module only ever needs a best-effort, crash-proof
    # date-ish string to help build a stable key.
    surgery_date_raw: Optional[str] = None

    # Last client-supplied postop_day, retained ONLY for diagnostics/testing
    # comparison against effective_postop_day -- never authoritative on its
    # own.
    client_reported_postop_day: Optional[int] = None

    created_at: datetime = field(default_factory=lambda: _utcnow())
    last_updated: datetime = field(default_factory=lambda: _utcnow())

    # ------------------------------------------------------------------
    # PRIVATE internal storage. Do not read or write these from outside
    # this class -- use the methods/properties below instead. Making these
    # private is what prevents a caller from e.g. setting a status without
    # its accompanying fact, or the verified flag without the day (or vice
    # versa): there is no public handle to mutate one without going through
    # a method that keeps the related fields consistent.
    # ------------------------------------------------------------------
    _effective_postop_day: Optional[int] = None
    _postop_day_verified: bool = False
    _facts: Dict[str, RecoveryFact] = field(default_factory=dict)
    _field_status: Dict[str, str] = field(default_factory=dict)
    _ask_counts: Dict[str, int] = field(default_factory=dict)
    _pending_field: Optional[str] = None

    # ------------------------------------------------------------------
    # Read-only views. Mutate only via the methods below -- direct
    # assignment (e.g. `state.postop_day_verified = True`) raises
    # AttributeError, matching pending_field's existing pattern.
    # ------------------------------------------------------------------
    @property
    def effective_postop_day(self) -> Optional[int]:
        return self._effective_postop_day

    @property
    def postop_day_verified(self) -> bool:
        return self._postop_day_verified

    @property
    def pending_field(self) -> Optional[str]:
        return self._pending_field

    # ------------------------------------------------------------------
    # CANONICAL FIELD-READ API -- see module docstring.
    # ------------------------------------------------------------------

    def get_fact(self, field_name: str) -> Optional[RecoveryFact]:
        """Latest/historical stored fact for this field, if any. May be from
        a PRIOR postoperative day -- callers must check is_current() before
        treating this as usable in a current day-gated comparison."""
        return self._facts.get(field_name)

    def status_of(self, field_name: str) -> str:
        """Stored interview/workflow status (see FieldStatus). This is NOT
        a clinical-freshness signal and does NOT indicate whether a current
        value exists -- use is_current() for that."""
        return self._field_status.get(field_name, FieldStatus.NEVER_ASKED)

    def ask_count_of(self, field_name: str) -> int:
        return self._ask_counts.get(field_name, 0)

    def is_current(self, field_name: str) -> bool:
        """
        Whether the stored fact for `field_name` (if any) is usable as the
        CURRENT verified-postop-day measurement.

        True requires ALL of:
            - a fact exists for this field
            - this episode's postoperative day has actually been verified
              (postop_day_verified is True and effective_postop_day is set)
            - the fact's own effective_postop_day equals the episode's
              current effective_postop_day

        A fact recorded on a prior day remains stored (get_fact() still
        returns it) but this ALWAYS returns False once the day has moved on,
        AND ALWAYS returns False whenever postop_day_verified is False --
        regardless of what effective_postop_day happens to hold. HISTORICAL
        FACT EXISTENCE != CURRENT MEASUREMENT: future day-gated decision
        logic must call this instead of inferring currentness from
        status_of() or from "get_fact() is not None" alone.
        """
        fact = self._facts.get(field_name)
        if fact is None:
            return False
        if not self.postop_day_verified or self.effective_postop_day is None:
            return False
        return fact.effective_postop_day == self.effective_postop_day

    # ------------------------------------------------------------------
    # ATOMIC STATE TRANSITIONS -- each method performs every state change
    # that transition requires. Callers never need to remember to update a
    # second structure to keep invariants intact.
    # ------------------------------------------------------------------

    def set_fact(self, field_name: str, value: Any, *, effective_postop_day: Optional[int]) -> None:
        """
        Record a new value for `field_name`. This single call: stores the
        fact, resolves any pending/unknown/unavailable interview status for
        this field back to NEVER_ASKED (a value now exists; KNOWN is never
        stored -- see get_fact()/is_current()), RESETS this field's retry
        counter to 0 (a successfully supplied value means this interview
        attempt succeeded -- a future need to reconfirm the field should not
        start from an already-exhausted retry budget left over from earlier
        failed attempts; this is deliberate SESSION/WORKFLOW policy, not a
        clinical rule, and never touches any OTHER field's ask_count),
        clears pending_field if this was the field being waited on, and
        refreshes last_updated.
        """
        self._facts[field_name] = RecoveryFact(
            value=value,
            effective_postop_day=effective_postop_day,
            updated_at=_utcnow(),
        )
        self._field_status.pop(field_name, None)
        self._ask_counts.pop(field_name, None)
        if self._pending_field == field_name:
            self._pending_field = None
        self.last_updated = _utcnow()

    def mark_pending(self, field_name: str) -> None:
        """
        The agent is now asking about `field_name`. Enforces "at most one
        field is PENDING at a time" atomically: if a DIFFERENT field was
        previously pending, it is demoted back to NEVER_ASKED in this same
        call before the new field is marked -- two fields can never both
        show PENDING, and pending_field never disagrees with which field(s)
        carry the PENDING status.
        """
        previous = self._pending_field
        if previous is not None and previous != field_name and self._field_status.get(previous) == FieldStatus.PENDING:
            self._field_status[previous] = FieldStatus.NEVER_ASKED
        self._pending_field = field_name
        self._field_status[field_name] = FieldStatus.PENDING
        self.last_updated = _utcnow()

    def clear_pending(self) -> None:
        """
        Stop waiting on whatever field was pending, without recording an
        answer (e.g. the patient changed topics and Recovery is yielding to
        normal routing). If that field's status was PENDING, it is demoted
        back to NEVER_ASKED as part of this same call -- a field must never
        be left showing PENDING once it is no longer RecoverySessionState's
        tracked pending_field, or the two would silently disagree.
        """
        if self._pending_field is not None and self._field_status.get(self._pending_field) == FieldStatus.PENDING:
            self._field_status[self._pending_field] = FieldStatus.NEVER_ASKED
        self._pending_field = None
        self.last_updated = _utcnow()

    def mark_unknown(self, field_name: str) -> None:
        """
        The patient was asked about `field_name` and gave a non-answer
        ("I don't know"). One atomic transition: increments the retry
        counter, sets the interview status to UNKNOWN, clears pending_field
        (this turn's question has been resolved -- the caller decides
        separately, using ask_count_of(), whether to mark_pending() again
        or give up via mark_unavailable()), and refreshes last_updated.
        """
        self._ask_counts[field_name] = self._ask_counts.get(field_name, 0) + 1
        self._field_status[field_name] = FieldStatus.UNKNOWN
        if self._pending_field == field_name:
            self._pending_field = None
        self.last_updated = _utcnow()

    def mark_unavailable(self, field_name: str) -> None:
        """
        Retries for `field_name` are exhausted; stop asking for the rest of
        this interview. This does NOT delete any existing historical fact
        (get_fact() may still return a value reported on an earlier day) --
        a prior measurement remaining on record as historical context and
        today's field being UNAVAILABLE are two independent, intentionally
        compatible truths. is_current() is what stops that stale fact from
        being misread as a current answer; UNAVAILABLE only ever describes
        today's interview outcome.
        """
        self._field_status[field_name] = FieldStatus.UNAVAILABLE
        if self._pending_field == field_name:
            self._pending_field = None
        self.last_updated = _utcnow()

    # ------------------------------------------------------------------
    # CANONICAL POSTOPERATIVE-DAY API -- see module docstring. Both public
    # methods route through the one internal transition below so the
    # transient-interview reset fires consistently and effective_postop_day
    # / postop_day_verified can never be observed out of sync.
    # ------------------------------------------------------------------

    def _transition_day(self, *, day: Optional[int], verified: bool) -> bool:
        """
        Internal only. Atomically applies (effective_postop_day,
        postop_day_verified) together and runs the same transient-interview
        reset used for a genuine day change (pending_field clears,
        ask_counts fully wipes, PENDING/UNKNOWN/UNAVAILABLE statuses revert
        to NEVER_ASKED) whenever the previously-trustworthy day materially
        changes -- including the transition from "a verified day" to
        "no longer trustworthy". Facts are NEVER touched here. Returns True
        iff that reset occurred.
        """
        previously_trustworthy = self._postop_day_verified and self._effective_postop_day is not None
        day_changed = previously_trustworthy and (
            not verified or day is None or day != self._effective_postop_day
        )

        if day_changed:
            self._reset_transient_interview()

        self._effective_postop_day = day
        self._postop_day_verified = verified
        self.last_updated = _utcnow()
        return day_changed

    def apply_verified_day(self, day: int) -> bool:
        """
        Record a SERVER-VERIFIED effective postoperative day. Atomically
        sets effective_postop_day = day AND postop_day_verified = True
        together -- there is no way to set one without the other through
        this API. Returns True iff this represents a real change from a
        previously verified day (triggering the transient-interview reset;
        see FieldStatus and _transition_day docstrings). This full
        ask_counts reset on a genuine change is a deliberate SESSION/
        WORKFLOW policy choice, not a clinical rule: a new verified day
        starts a fresh interview retry budget for every field.
        """
        return self._transition_day(day=day, verified=True)

    def clear_verified_day(self) -> bool:
        """
        Record that NO trustworthy postoperative day is currently available
        (surgery_date missing, malformed, or otherwise unverifiable).
        Atomically sets postop_day_verified = False AND
        effective_postop_day = None together -- a stale day number is never
        left behind for a careless caller to read as if it were still
        trustworthy; postop_day_verified alone is sufficient for
        is_current() to always return False, and clearing the day value too
        removes any ambiguity for a caller that reads effective_postop_day
        directly. Returns True iff a previously-verified day was cleared
        (triggering the transient-interview reset).
        """
        return self._transition_day(day=None, verified=False)

    # ------------------------------------------------------------------
    # Shared internal reset, used both by a genuine day-state transition
    # above and by interview-TTL staleness (see module-level
    # _reset_transient_interview_state()) -- one place owns this logic.
    # ------------------------------------------------------------------
    def _reset_transient_interview(self) -> None:
        self._pending_field = None
        self._ask_counts = {}
        for name, status in list(self._field_status.items()):
            if status in (FieldStatus.PENDING, FieldStatus.UNKNOWN, FieldStatus.UNAVAILABLE):
                self._field_status[name] = FieldStatus.NEVER_ASKED


# ============================================================================
# TIME HELPER
# ============================================================================

def _utcnow() -> datetime:
    # Always timezone-aware UTC. Every datetime this module creates or
    # compares goes through this one function, so naive-vs-aware subtraction
    # errors (the exact landmine found for surgery_date parsing) cannot occur
    # inside this module's own TTL/expiry arithmetic.
    return datetime.now(timezone.utc)


# ============================================================================
# EPISODE KEY
# ============================================================================

_DATE_PREFIX_RE = re.compile(r"^\s*(\d{4}-\d{2}-\d{2})")
_NODATE_SENTINEL = "NODATE"


def _normalize_surgery_date_for_key(surgery_date_raw: Optional[str]) -> str:
    """
    Best-effort, crash-proof reduction of a surgery_date string to a stable
    YYYY-MM-DD key component. This is NOT the authoritative clinical day
    derivation (that is a separate, later step with full timezone/Day-1
    handling) -- it only needs to be stable and safe enough to keep two
    genuinely different surgery dates from colliding in the state-store key.

    Handles both formats seen in this repo's own investigation:
        "2026-09-02T00:00:00.000"   (Flutter's actual local, non-UTC format)
        "2026-08-15T00:00:00.000Z"  (the API doc's own example format)
    by just taking the leading YYYY-MM-DD, before any 'T'/time/zone part --
    which is identical for both formats and never requires constructing a
    datetime object (so it can never raise a naive/aware subtraction error).

    Anything that doesn't start with a recognizable YYYY-MM-DD is treated as
    absent -- returns the NODATE sentinel rather than guessing.
    """
    if not surgery_date_raw:
        return _NODATE_SENTINEL

    match = _DATE_PREFIX_RE.match(surgery_date_raw)
    if not match:
        return _NODATE_SENTINEL

    return match.group(1)


def _normalize_patient_id(patient_id: Optional[str]) -> str:
    return (patient_id or "UNKNOWN_PATIENT").strip().upper()


def _normalize_procedure(procedure: Optional[str]) -> str:
    return (procedure or "GEN").strip().upper()


def make_episode_key(patient_id: str, surgery_date_raw: Optional[str], procedure: str) -> str:
    """
    Build the recovery-episode key: (patient_id, surgery_date, procedure).

    Deliberately NOT keyed on patient_id alone -- the same patient having a
    second surgery later (a new procedure/date) must never silently reuse an
    older episode's stale facts/interview state. When surgery_date is
    missing/malformed, the date component degrades to a shared NODATE
    partition for that patient+procedure. See get_or_create_state() for how
    a NODATE episode is later adopted into a real dated key once a genuine
    surgery_date becomes available, rather than being permanently orphaned.
    """
    pid = _normalize_patient_id(patient_id)
    proc = _normalize_procedure(procedure)
    date_part = _normalize_surgery_date_for_key(surgery_date_raw)
    return f"{pid}::{date_part}::{proc}"


# ============================================================================
# STATE STORE
# ============================================================================
#
# SESSION_TTL / INTERVIEW_TTL / MAX_STORE_SIZE below are SESSION-MANAGEMENT
# ENGINEERING PARAMETERS -- reasonable defaults chosen for this branch, not
# clinical thresholds. No day-gated milestone comparison, verdict, or other
# clinical decision anywhere in this system depends on these numbers, and
# nothing about them is evidence-derived. They exist purely to bound this
# module's own memory footprint and to decide when interview bookkeeping
# should no longer be trusted as "still the same conversation". They are
# intentionally easy to tune later without touching any clinical logic.

# Whole-episode TTL: an episode untouched for this long is treated as stale
# and discarded outright on next access (fresh state is created instead).
SESSION_TTL = timedelta(hours=6)

# Interview TTL: shorter than SESSION_TTL. An episode untouched for this long
# (but less than SESSION_TTL) keeps its durable facts, but transient
# interview bookkeeping (pending_field / ask_counts / UNKNOWN / UNAVAILABLE /
# PENDING statuses) is cleared -- a patient returning after a real gap gets a
# fresh interview rather than resuming retry counts from a stale attempt.
INTERVIEW_TTL = timedelta(minutes=30)

# Simple bounded-store policy: if the store would exceed this many episodes,
# evict the least-recently-updated entries until back under the limit. This
# is a safety net against unbounded memory growth, not a precise LRU cache --
# appropriate for a process-scoped, single-purpose store like this one.
MAX_STORE_SIZE = 500

_STORE: Dict[str, RecoverySessionState] = {}
_LOCK = threading.Lock()
# FastAPI/Starlette runs synchronous path-operation functions in a
# threadpool (not strictly one-request-at-a-time), so this module guards
# every store read/mutate with a plain lock rather than assuming
# single-threaded access.


def _is_session_expired(state: RecoverySessionState, now: datetime) -> bool:
    return (now - state.last_updated) > SESSION_TTL


def _is_interview_stale(state: RecoverySessionState, now: datetime) -> bool:
    return (now - state.last_updated) > INTERVIEW_TTL


def _reset_transient_interview_state(state: RecoverySessionState) -> None:
    # Delegates to the instance's own reset so there is exactly one place
    # (RecoverySessionState._reset_transient_interview) that owns this
    # logic -- shared by interview-TTL staleness (here) and by a genuine
    # verified-day transition (RecoverySessionState._transition_day).
    state._reset_transient_interview()


def _evict_if_over_capacity(now: datetime, protected_key: Optional[str] = None) -> None:
    """
    Caller must hold _LOCK. Evicts oldest-by-last_updated entries when the
    store has grown past MAX_STORE_SIZE, EXCLUDING `protected_key` from
    eviction candidates.

    This is an ENGINEERING/CONCURRENCY invariant, not a clinical rule: it
    exists so the entry a request is about to return (just created, or just
    adopted from a NODATE episode) can never be the one evicted in the same
    call that produced it -- even though that is very unlikely to matter in
    this project's current single-process deployment. If protecting that
    entry means the store sits one entry above MAX_STORE_SIZE, that is
    accepted: the cap is a soft memory-bounding target, not a hard limit
    enforced at the cost of returning a request's own just-created state.
    """
    if len(_STORE) <= MAX_STORE_SIZE:
        return
    candidates = [k for k in _STORE if k != protected_key]
    overflow = len(_STORE) - MAX_STORE_SIZE
    oldest_keys = sorted(candidates, key=lambda k: _STORE[k].last_updated)[:overflow]
    for key in oldest_keys:
        del _STORE[key]


def get_or_create_state(
    *,
    patient_id: str,
    surgery_date_raw: Optional[str],
    procedure: str,
) -> RecoverySessionState:
    """
    Fetch the RecoverySessionState for this episode, creating a fresh one if
    none exists (subject to NODATE adoption below) or the existing one has
    fully expired (SESSION_TTL). If the existing entry is merely
    interview-stale (older than INTERVIEW_TTL but within SESSION_TTL),
    transient interview bookkeeping is cleared in place while durable facts
    are kept.

    NODATE -> DATED ADOPTION (one-directional only):
    If the caller supplies a REAL, parseable surgery_date and no live entry
    already exists under that exact dated key, this checks whether a
    matching, non-expired NODATE episode exists for the SAME patient_id and
    procedure. If so, that NODATE episode's entire state (facts, their
    original day tags, interview bookkeeping) is migrated onto the new dated
    key -- rather than starting a fresh, empty episode and silently
    orphaning everything collected before the surgery_date was known.

    This migration never happens in the other direction, and never merges
    two different real dates or two different procedures:
        - if a LIVE entry already exists under the exact requested key
          (dated or NODATE), it is returned as-is -- an existing dated
          episode always wins; no NODATE state is ever merged into it.
        - a NODATE lookup is only ever attempted when the caller asked for a
          REAL dated key and nothing lives there yet.
        - the NODATE lookup key is scoped to the same patient_id AND the
          same procedure -- a NODATE THA episode is never adopted into a
          TKA request, and vice versa.

    Only THIS function performs adoption -- peek_state() deliberately does
    not (see its docstring).
    """
    pid = _normalize_patient_id(patient_id)
    proc = _normalize_procedure(procedure)
    date_part = _normalize_surgery_date_for_key(surgery_date_raw)
    key = f"{pid}::{date_part}::{proc}"
    now = _utcnow()

    with _LOCK:
        existing = _STORE.get(key)

        if existing is not None and _is_session_expired(existing, now):
            existing = None

        if existing is not None:
            if _is_interview_stale(existing, now):
                _reset_transient_interview_state(existing)
            existing.surgery_date_raw = surgery_date_raw or existing.surgery_date_raw
            existing.last_updated = now
            return existing

        # No live entry under the exact requested key. If a REAL dated key
        # was requested, check for a matching NODATE episode to adopt
        # rather than starting empty.
        if date_part != _NODATE_SENTINEL:
            nodate_key = f"{pid}::{_NODATE_SENTINEL}::{proc}"
            nodate_state = _STORE.get(nodate_key)

            if nodate_state is not None:
                if _is_session_expired(nodate_state, now):
                    # Stale garbage -- clear it and fall through to a fresh
                    # dated episode rather than adopting expired data.
                    del _STORE[nodate_key]
                else:
                    if _is_interview_stale(nodate_state, now):
                        _reset_transient_interview_state(nodate_state)
                    nodate_state.episode_key = key
                    nodate_state.surgery_date_raw = surgery_date_raw
                    nodate_state.last_updated = now
                    _STORE[key] = nodate_state
                    del _STORE[nodate_key]
                    _evict_if_over_capacity(now, protected_key=key)
                    return nodate_state

        state = RecoverySessionState(
            episode_key=key,
            patient_id=pid,
            procedure=proc,
            surgery_date_raw=surgery_date_raw,
        )
        _STORE[key] = state
        _evict_if_over_capacity(now, protected_key=key)
        return state


def peek_state(
    *,
    patient_id: str,
    surgery_date_raw: Optional[str],
    procedure: str,
) -> Optional[RecoverySessionState]:
    """
    Read-only lookup for the EXACT (patient_id, surgery_date_raw, procedure)
    key -- does NOT create a new entry, does NOT touch last_updated, and
    does NOT perform NODATE adoption. Useful for diagnostics/tests that must
    not mutate state.

    IMPORTANT BLIND SPOT: because this never adopts, a None result for a
    REAL dated key does NOT prove no related state exists. If an episode
    currently lives only under the NODATE partition for the same
    patient_id + procedure (i.e. `PATIENT::NODATE::PROCEDURE`), calling
    peek_state(patient_id=..., surgery_date_raw=<real date>, procedure=...)
    returns None even though a migratable NODATE state exists and
    get_or_create_state() with those same arguments would adopt it.
    peek_state() returning None for a dated key is therefore only proof
    that nothing lives under THAT EXACT key -- never proof that no related
    NODATE episode exists. Only get_or_create_state() performs adoption;
    call that (not peek_state()) if the caller needs the adopted result.
    """
    key = make_episode_key(patient_id, surgery_date_raw, procedure)
    with _LOCK:
        return _STORE.get(key)


def _clear_all_state_for_tests() -> None:
    """Test-only helper: wipes the entire in-memory store. Never called from
    production code paths."""
    with _LOCK:
        _STORE.clear()
