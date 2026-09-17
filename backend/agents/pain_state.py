"""
Pain & Symptoms Session State.

Lightweight, explicit, process-scoped bookkeeping for one patient's active
Pain & Symptoms conversation. Deliberately narrow in scope:

    - pending_field: which Pain field the agent is currently waiting on an
      answer for. Used by pain_logic.py's own turn handling AND by the LAM
      orchestrator's narrow active-Pain-follow-up routing check (see
      lam/orchestrator.py::_has_active_pain_followup) -- the orchestrator
      peeks this object as ONE of the two required signals before letting a
      short reply stay with Pain, mirroring how Recovery's
      check_recovery_continuation() peeks RecoverySessionState.
    - ask_counts: how many times each field has been asked, so a repeated
      "I don't know" can be told apart from a first uncertain answer
      (mirrors recovery_state.py's ask_count_of()/mark_unknown() pattern, at
      much smaller scale -- Pain has no day-gating, no verified-day
      derivation, and no milestone comparison, so none of
      RecoverySessionState's day-derivation machinery applies here).
    - cached structured facts (pain_score / swelling): SUPPLEMENTAL only --
      see below.
    - active_history_start: the ACTIVE-ASSESSMENT HISTORY BOUNDARY -- the
      index into a `chat_history` list from which entries belong to the
      CURRENTLY ACTIVE Pain assessment (see start_new_assessment()). This is
      what stops a COMPLETED older Pain assessment's facts (pain_score,
      onset, location, ...) from becoming live facts again in a LATER, new
      Pain assessment in the same chat -- both
      specialized_agents.py::PainSymptomsAgent.handle() (for
      pain_logic.build_assessment) and lam/orchestrator.py's cumulative-
      safety step (for pain_logic.build_cumulative_triage_text) slice
      chat_history at this same boundary before reconstructing anything.
      Cleared together with the rest of this state's bookkeeping by
      clear_pending() and TTL staleness, and (re-)established by
      start_new_assessment() whenever a turn is determined NOT to be a
      continuation of the currently pending question.

Free-text clinical facts (onset, location, worsening/improving, stiffness,
...) are still re-derived every turn from chat_history + the current
message (see pain_logic.py) -- the same robust pattern
agents/wound_care_agent.py already uses for its own multi-turn assessment --
so a server restart or an expired/evicted session here never loses a fact
the patient already STATED IN THE CONVERSATION; only the retry-counting/
routing bookkeeping in THIS module is process-scoped, in-memory, and
therefore best-effort.

STRUCTURED-FACT CACHE (pain_score / swelling only):
Unlike a free-text fact, a structured API field (pain_score,
swelling_description) supplied on one turn leaves NO trace in chat_history
if the frontend doesn't resupply it on a later turn -- there is nothing for
pain_logic.build_assessment()'s chat_history reconstruction to recover, so
without this cache a cumulative-safety evaluation (or the ongoing
assessment itself) would silently lose it (confirmed gap: "My pain suddenly
got much worse today" + pain_score=8, then "my calf" with pain_score
omitted -- cumulative safety must still see the 8). This cache exists
SOLELY to bridge that one gap. It is explicitly SUPPLEMENTAL, never the
sole source of truth:
    - it only ever holds the two structured fields that can otherwise
      silently vanish across turns (pain_score, swelling) -- never onset/
      location/etc., which chat_history already covers, and never
      temperature_c, which keeps its own existing direct per-turn path
      straight into SafetyTriageEngine (see lam/orchestrator.py) and so
      never needs this kind of cross-turn bridging;
    - a LATER free-text correction (e.g. "Actually wait, it's more like a
      5.") must always be able to override a stale cached value -- callers
      apply cached facts as a FALLBACK/BASELINE only for a field pain_logic
      could not otherwise resolve from chat_history/corrections, never as
      an unconditional override (see pain_logic.build_assessment's
      `cached_facts` parameter for the exact precedence);
    - it is cleared whenever the active assessment concludes
      (clear_pending()) and whenever the interview goes stale past
      INTERVIEW_TTL (get_or_create_state()), so it can never leak into a
      later, unrelated Pain assessment for the same patient.

This is a separate, durable, cross-session record of COMPLETED assessments --
see patient_database.py's symptom_assessments table (save_symptom_assessment /
get_recent_symptom_assessments) -- this module does not attempt to replace
that; it only tracks the transient, within-conversation pending question and
the transient structured-fact cache described above.

Explicit limitation (same acceptance as recovery_state.py): PROCESS-SCOPED,
IN-MEMORY state. Does not survive a backend restart or multiple worker
processes without shared storage. Accepted for the same reason Recovery
accepts it -- this is about a genuinely agentic conversation within one
sitting, not durable cross-session tracking (that is patient_database.py's
job, separately).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Shorter than Recovery's SESSION_TTL/INTERVIEW_TTL -- a Pain conversation is
# expected to complete within a handful of turns in one sitting, not persist
# across a multi-hour gap. A single constant is enough here (no separate
# "keep durable facts but reset interview bookkeeping" distinction is needed,
# because this module never stores durable facts in the first place).
INTERVIEW_TTL = timedelta(minutes=30)
MAX_STORE_SIZE = 500


@dataclass
class PainSessionState:
    """
    One patient's active Pain & Symptoms interview bookkeeping. ALL mutation
    flows through this class's own methods so pending_field and ask_counts
    can never be observed out of sync with each other.

    THREAD SAFETY: the module-level `_LOCK` (see below) only guards the
    `_STORE` dict itself (lookup/creation/eviction) -- once a
    PainSessionState object is RETURNED to a caller, the SAME object
    instance is shared across every concurrent request for that patient_id
    (FastAPI/Starlette runs synchronous path-operation functions in a
    threadpool, so two requests for the same patient really can execute
    concurrently). Every method below therefore also acquires this
    instance's OWN `_lock` for its entire body, so a property read or a
    mutation is never observed half-applied (e.g. pending_field updated but
    last_updated not yet, or a dict mutation torn mid-update). An `RLock`
    (not a plain `Lock`) is used so a method can safely call another method
    on `self` in the future without a self-deadlock, even though none
    currently do. Lock ordering is always `_LOCK` (module) before
    `self._lock` (instance) -- see get_or_create_state()/peek_state(),
    which are the only places both are ever held at once -- so this can
    never deadlock against itself.
    """

    patient_id: str
    last_updated: datetime = field(default_factory=_utcnow)

    _pending_field: Optional[str] = None
    _ask_counts: Dict[str, int] = field(default_factory=dict)
    _cached_structured_facts: Dict[str, Any] = field(default_factory=dict)
    _active_history_start: Optional[int] = None
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)

    @property
    def pending_field(self) -> Optional[str]:
        with self._lock:
            return self._pending_field

    @property
    def active_history_start(self) -> Optional[int]:
        """
        The index into a `chat_history` list from which entries belong to
        the CURRENTLY ACTIVE Pain assessment -- see start_new_assessment().
        None means no active-assessment boundary has been established yet
        (e.g. a brand-new patient, or right after clear_pending()/TTL
        reset) -- callers should treat that as "no scoping information
        available" and fall back to their own caller-appropriate default
        (specialized_agents.py::PainSymptomsAgent.handle() always
        establishes one before using it; lam/orchestrator.py only reads
        this when `pain_context` already guarantees an active assessment
        exists).
        """
        with self._lock:
            return self._active_history_start

    def ask_count_of(self, field_name: str) -> int:
        with self._lock:
            return self._ask_counts.get(field_name, 0)

    def mark_pending(self, field_name: str) -> None:
        """The agent is now asking about `field_name`; at most one field is
        pending at a time."""
        with self._lock:
            self._pending_field = field_name
            self.last_updated = _utcnow()

    def start_new_assessment(self, history_len: int) -> None:
        """
        Begin a genuinely FRESH Pain assessment: discard any leftover
        interview bookkeeping from a PREVIOUS assessment for this patient
        (whether it concluded normally -- clear_pending() already ran, so
        this is a no-op on top of that -- or was simply ABANDONED mid-
        interview, e.g. the patient switched to a different domain and
        later came back with a brand-new Pain complaint instead of
        answering the old pending question) and record the ACTIVE-
        ASSESSMENT HISTORY BOUNDARY: `history_len` is the length of the
        caller's `chat_history` list at the moment this fresh assessment
        begins, so every entry at or after that index belongs to THIS
        assessment, and everything before it -- including an abandoned
        interview's cached pending_field/ask_counts/structured facts, and
        any COMPLETED older assessment's conversation turns -- is excluded
        from this assessment's own re-derivation of chat_history (see
        specialized_agents.py::PainSymptomsAgent.handle() and
        lam/orchestrator.py's cumulative-safety step, which both slice
        chat_history at this same boundary via `active_history_start`).

        Idempotent/safe to call on a state that is already mid-assessment
        with the SAME boundary already correct (callers only call this when
        they have already determined, via the two-signal continuation
        check, that this turn is NOT a continuation of the current pending
        question) -- it never needs to distinguish "truly the first-ever
        assessment for this patient" from "a later, unrelated assessment
        after an earlier one concluded/was abandoned"; both cases reset to
        the exact same clean state.

        Durable historical facts from a genuinely COMPLETED assessment
        remain available separately, and ONLY as an explicit factual
        comparison, via patient_database.symptom_assessments (see
        pain_integration.load_recent_assessments/build_trend_note) -- this
        method never touches that table; it only ever resets THIS transient,
        in-memory bookkeeping.
        """
        with self._lock:
            self._pending_field = None
            self._ask_counts = {}
            self._cached_structured_facts = {}
            self._active_history_start = history_len
            self.last_updated = _utcnow()

    def clear_pending(self) -> None:
        """
        FULL INTERVIEW RESET -- called when the active Pain assessment
        CONCLUDES. Clears the pending field, the retry/ask-count
        bookkeeping, the structured-fact cache, AND the active-assessment
        history-start boundary (see start_new_assessment()) together --
        once an assessment concludes, none of its bookkeeping may leak into
        whatever Pain assessment (if any) comes next for this patient.

        REAL, VERIFIED LIFECYCLE (do not add to this list without finding
        an actual call site first -- see the investigation this comment
        reflects):
            - assessment CONCLUSION -> this method (full reset). The ONLY
              production call site today is
              specialized_agents.py::PainSymptomsAgent.handle(), at the
              exact moment the assessment concludes. There is no call site
              that uses this for a merely temporary, single-field clear.
            - INTERVIEW_TTL staleness -> _reset_for_staleness() (same
              effect, different trigger: elapsed time rather than
              conclusion).
            - an explicit different-domain topic switch (e.g. "Can I climb
              stairs?") does NOT call this method and does NOT otherwise
              clear this session: lam/orchestrator.py's `pain_context`
              gating means PainSymptomsAgent.handle() is simply never
              invoked for that turn, so this state object is left
              untouched (not reset) until the patient either returns to
              Pain and resolves the pending field, or INTERVIEW_TTL
              elapses. The topic switch is isolated from THIS patient's
              other agents (Daily Activity, Medication, ...) by that same
              `pain_context` gating -- see
              lam/orchestrator.py::_has_active_pain_followup -- not by
              this session being destroyed.

        Ask-count clearing: verified directly that pain_logic's first-vs-
        second-uncertainty resolution (whether "idk" gets the simplified
        ALT rephrase, or is recorded as "unknown") is driven entirely by
        `needs_alt`, reconstructed fresh from EACH conversation's own
        chat_history -- never by this ask_counts dict, which
        specialized_agents.py consumes only as a cosmetic
        `variation_seed` for acknowledgment-phrase-pool rotation. A stale
        ask_count surviving into an unrelated later assessment therefore
        does not currently cause an incorrect "unknown" resolution.
        Clearing it here regardless is still correct: it matches this
        method's own "full interview reset" contract, keeps the
        acknowledgment-phrase rotation from an abandoned assessment from
        bleeding into an unrelated one, and guards against a future change
        that DOES key retry-limiting off ask_count_of() (mirroring
        recovery_logic.py's own RETRY_EXHAUSTED pattern) -- exactly the
        kind of change a leaked stale count would silently break.
        """
        with self._lock:
            self._pending_field = None
            self._ask_counts = {}
            self._cached_structured_facts = {}
            self._active_history_start = None
            self.last_updated = _utcnow()

    def cache_structured_facts(self, facts: Dict[str, Any]) -> None:
        """
        Merge any NON-None structured Pain facts supplied on THIS turn into
        the supplemental cache (see module docstring) -- so a LATER turn
        that doesn't resupply them can still use them as a fallback
        baseline. Only ever overwrites a key that was actually supplied
        this call; omitting a key (or passing None for it) leaves whatever
        was cached from an earlier turn untouched. Never itself decides
        precedence against a free-text value -- that is
        pain_logic.build_assessment()'s job via its `cached_facts`
        parameter.
        """
        with self._lock:
            for key, value in facts.items():
                if value is not None:
                    self._cached_structured_facts[key] = value
            self.last_updated = _utcnow()

    def cached_structured_facts(self) -> Dict[str, Any]:
        """A shallow copy -- callers must never mutate this in place."""
        with self._lock:
            return dict(self._cached_structured_facts)

    def note_asked(self, field_name: str) -> int:
        """Record that `field_name` was asked (and answered with genuine
        uncertainty) this turn -- used for the first-uncertain-answer ->
        rephrase, second-uncertain-answer -> record "unknown" policy. Returns
        the new ask count for `field_name`."""
        with self._lock:
            self._ask_counts[field_name] = self._ask_counts.get(field_name, 0) + 1
            self.last_updated = _utcnow()
            return self._ask_counts[field_name]

    def resolve(self, field_name: str) -> None:
        """A real value now exists for `field_name` -- stop tracking it as
        pending/retried."""
        with self._lock:
            self._ask_counts.pop(field_name, None)
            if self._pending_field == field_name:
                self._pending_field = None
            self.last_updated = _utcnow()

    def _reset_for_staleness(self) -> None:
        """Internal only -- called by get_or_create_state() while it
        already holds the module-level `_LOCK`. Acquires this instance's
        OWN lock too (consistent `_LOCK` -> `self._lock` ordering, see
        class docstring) rather than touching private fields directly, so
        this reset can never race against a concurrent method call on the
        same object. Also clears the active-assessment history-start
        boundary (see start_new_assessment()) -- a patient returning after
        a real TTL gap must not have a later assessment scoped against a
        long-stale boundary either."""
        with self._lock:
            self._pending_field = None
            self._ask_counts = {}
            self._cached_structured_facts = {}
            self._active_history_start = None
            self.last_updated = _utcnow()

    def _touch(self) -> None:
        """Internal only -- refresh last_updated under this instance's own
        lock. See _reset_for_staleness()."""
        with self._lock:
            self.last_updated = _utcnow()

    def is_stale(self, now: datetime) -> bool:
        """
        Whether this session has been untouched for longer than
        INTERVIEW_TTL, as of `now`. Reads last_updated under this
        instance's OWN lock -- writes to last_updated already happen
        inside every mutating method's `with self._lock:` block, but
        `state.last_updated` itself is a plain dataclass field, so any
        DIRECT external read of it (as the module-level staleness/eviction
        helpers used to do) was unguarded and could observe a torn/
        in-progress write. Every staleness check and every eviction
        comparison now goes through this method (or get_last_updated()
        below) instead of touching the field directly.
        """
        with self._lock:
            return (now - self.last_updated) > INTERVIEW_TTL

    def get_last_updated(self) -> datetime:
        """Locked read of last_updated -- used by _evict_if_over_capacity()
        to sort candidates for eviction without reading the field directly
        outside this instance's lock. `datetime` objects are themselves
        immutable, so returning the value is safe once read."""
        with self._lock:
            return self.last_updated


_STORE: Dict[str, PainSessionState] = {}
_LOCK = threading.Lock()
# FastAPI/Starlette runs synchronous path-operation functions in a
# threadpool, so every store read/mutate is guarded with a plain lock rather
# than assuming single-threaded access (same rationale as recovery_state.py).


def _normalize_patient_id(patient_id: Optional[str]) -> str:
    """
    `main.py::ChatRequest` now rejects an explicitly blank/whitespace-only
    patient_id at the API boundary (a `field_validator` on `patient_id`),
    and omitting the field entirely resolves to a real, non-blank default
    -- so the "UNKNOWN_PATIENT" fallback below is no longer reachable via
    the actual /api/chat request path. It is INTENTIONALLY kept anyway, as
    a defensive fallback for callers that bypass that boundary entirely:
    this module's own functions are called directly (not through the API)
    by test code, and are general-purpose enough that a future internal
    caller could reasonably do the same. Removing this fallback would turn
    a blank/None patient_id from a clean, contained "UNKNOWN_PATIENT"
    bucket into an outright crash (`None.strip()`) for any such caller.
    The API-boundary validator is the REAL fix (it stops blank patient_id
    from ever reaching here via user traffic); this is only a last-resort
    safety net for non-API callers.
    """
    return (patient_id or "UNKNOWN_PATIENT").strip().upper()


def _evict_if_over_capacity(now: datetime, protected_key: Optional[str] = None) -> None:
    if len(_STORE) <= MAX_STORE_SIZE:
        return
    candidates = [key for key in _STORE if key != protected_key]
    overflow = len(_STORE) - MAX_STORE_SIZE
    # get_last_updated() (not the raw `.last_updated` field) -- a locked
    # read on each candidate, never touching another state's field
    # directly outside its own lock.
    oldest_keys = sorted(candidates, key=lambda key: _STORE[key].get_last_updated())[:overflow]
    for key in oldest_keys:
        del _STORE[key]


def get_or_create_state(patient_id: str) -> PainSessionState:
    """
    Fetch (creating if needed) the PainSessionState for `patient_id`. A
    session untouched for longer than INTERVIEW_TTL has its interview
    bookkeeping (pending_field / ask_counts) AND its structured-fact cache
    cleared in place -- a patient returning after a real gap gets a fresh
    interview rather than resuming stale retry counts or a stale cached
    pain_score/swelling value from a long-abandoned conversation.
    """
    key = _normalize_patient_id(patient_id)
    now = _utcnow()
    with _LOCK:
        existing = _STORE.get(key)
        if existing is not None:
            # Routed through the instance's own methods (never touching
            # private fields directly) so this reset/touch is guarded by
            # `existing._lock` too -- consistent `_LOCK` -> `self._lock`
            # ordering with every other code path (see PainSessionState's
            # class docstring).
            if existing.is_stale(now):
                existing._reset_for_staleness()
            else:
                existing._touch()
            return existing
        state = PainSessionState(patient_id=key)
        _STORE[key] = state
        _evict_if_over_capacity(now, protected_key=key)
        return state


def peek_state(patient_id: str) -> Optional[PainSessionState]:
    """
    Read-only lookup -- does NOT create a new entry and does NOT touch
    last_updated. Returns None if no live (non-stale) session exists. Used by
    the LAM orchestrator's active-Pain-follow-up routing check, which must
    never create state merely by looking.
    """
    key = _normalize_patient_id(patient_id)
    with _LOCK:
        state = _STORE.get(key)
        if state is None:
            return None
        if state.is_stale(_utcnow()):
            return None
        return state


def _clear_all_state_for_tests() -> None:
    """Test-only helper: wipes the entire in-memory store. Never called from
    production code paths."""
    with _LOCK:
        _STORE.clear()
