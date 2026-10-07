"""
Rehabilitation & Exercise Session State.

Process-scoped, in-memory bookkeeping for one patient's active
Rehabilitation conversation -- the same narrow pattern as
agents/pain_state.py (one pending question, ask counts, a cached patient
memory snapshot, a 30-minute interview TTL, a capped store, per-instance
locking), plus the few facts the Rehabilitation agent establishes before it
answers an exercise question:

    - exercises_done_today    True / False / "unknown"
    - exercise_safety         False (no sharp pain or next-day swelling),
                              True (reported; the exercise named, if any,
                              is kept separately), or "unknown"
    - weight_bearing_status   NWB / PWB / WBAT / FWB as the PATIENT stated
                              it this session -- kept HERE ONLY, never
                              written to the `surgeries` table
    - exercise_barrier        what the patient says makes the exercises
                              hard (free text), or "none"

Unlike Pain (which re-derives its clinical facts from chat_history every
turn), these facts live in the session for the TTL: the orchestrator has
no Rehabilitation continuation hook, so a bare "no" after a Rehabilitation
question is not guaranteed to come back through chat_history anyway (see
agents/REHAB_AGENT_CHANGES.md, "shared changes needed"). Everything here is
best-effort and lost on restart; the durable record is patient_database.py
(the agent writes today's exercise_completed there via patient_memory.py).

Lock ordering is `_LOCK` (module) before `self._lock` (instance), exactly
as in pain_state.py, so this can never deadlock against itself.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


INTERVIEW_TTL = timedelta(minutes=30)
MAX_STORE_SIZE = 500


@dataclass
class RehabSessionState:
    """One patient's active Rehabilitation conversation. ALL mutation goes
    through the methods below so no two fields are ever observed out of
    sync (see pain_state.PainSessionState for the threading rationale)."""

    patient_id: str
    last_updated: datetime = field(default_factory=_utcnow)

    _pending_field: Optional[str] = None
    _pending_is_second: bool = False
    _ask_counts: Dict[str, int] = field(default_factory=dict)
    _facts: Dict[str, Any] = field(default_factory=dict)
    # The exercise/activity the patient asked about ("stairs", "heel
    # slides", ...), whether the question named a specific exercise
    # (direct) and how many questions the agent has asked since that
    # question was put -- the "at most two / at most one" budget.
    _topic: Optional[str] = None
    _topic_label: Optional[str] = None
    _direct: bool = False
    _episode_asked: int = 0
    _barrier_offered: bool = False
    _memory: Optional[Any] = field(default=None, repr=False, compare=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)

    # ------------------------------------------------------------------
    # Pending question / ask counts
    # ------------------------------------------------------------------
    @property
    def pending_field(self) -> Optional[str]:
        with self._lock:
            return self._pending_field

    @property
    def pending_is_second(self) -> bool:
        with self._lock:
            return self._pending_is_second

    def mark_pending(self, field_name: str, *, second: bool = False) -> None:
        with self._lock:
            self._pending_field = field_name
            self._pending_is_second = second
            self.last_updated = _utcnow()

    def clear_pending(self) -> None:
        with self._lock:
            self._pending_field = None
            self._pending_is_second = False
            self.last_updated = _utcnow()

    def ask_count_of(self, field_name: str) -> int:
        with self._lock:
            return self._ask_counts.get(field_name, 0)

    def note_asked(self, field_name: str) -> int:
        with self._lock:
            self._ask_counts[field_name] = self._ask_counts.get(field_name, 0) + 1
            self.last_updated = _utcnow()
            return self._ask_counts[field_name]

    def resolve(self, field_name: str) -> None:
        """A value now exists for `field_name`; stop tracking it as pending."""
        with self._lock:
            if self._pending_field == field_name:
                self._pending_field = None
                self._pending_is_second = False
            self.last_updated = _utcnow()

    # ------------------------------------------------------------------
    # Facts
    # ------------------------------------------------------------------
    def set_fact(self, field_name: str, value: Any) -> None:
        with self._lock:
            self._facts[field_name] = value
            self.last_updated = _utcnow()

    def get_fact(self, field_name: str) -> Any:
        with self._lock:
            return self._facts.get(field_name)

    def has_fact(self, field_name: str) -> bool:
        with self._lock:
            return field_name in self._facts

    def facts(self) -> Dict[str, Any]:
        """A shallow copy -- callers must never mutate this in place."""
        with self._lock:
            return dict(self._facts)

    # ------------------------------------------------------------------
    # Topic / question budget
    # ------------------------------------------------------------------
    @property
    def topic(self) -> Optional[str]:
        with self._lock:
            return self._topic

    @property
    def topic_label(self) -> Optional[str]:
        with self._lock:
            return self._topic_label

    @property
    def direct(self) -> bool:
        with self._lock:
            return self._direct

    @property
    def episode_asked(self) -> int:
        with self._lock:
            return self._episode_asked

    def start_episode(self, *, topic: Optional[str], topic_label: Optional[str], direct: bool) -> None:
        """The patient put a (new) exercise question: remember what it is
        about and reset the per-question budget. Facts are kept -- they
        are not asked again within the session."""
        with self._lock:
            if topic:
                self._topic = topic
                self._topic_label = topic_label
            self._direct = direct
            self._episode_asked = 0
            self.last_updated = _utcnow()

    def note_question_asked(self) -> int:
        with self._lock:
            self._episode_asked += 1
            self.last_updated = _utcnow()
            return self._episode_asked

    @property
    def barrier_offered(self) -> bool:
        with self._lock:
            return self._barrier_offered

    def mark_barrier_offered(self) -> None:
        with self._lock:
            self._barrier_offered = True
            self.last_updated = _utcnow()

    # ------------------------------------------------------------------
    # Memory snapshot
    # ------------------------------------------------------------------
    @property
    def memory(self) -> Optional[Any]:
        with self._lock:
            return self._memory

    def set_memory(self, memory: Any) -> None:
        with self._lock:
            self._memory = memory
            self.last_updated = _utcnow()

    # ------------------------------------------------------------------
    # Staleness
    # ------------------------------------------------------------------
    def _reset_for_staleness(self) -> None:
        with self._lock:
            self._pending_field = None
            self._pending_is_second = False
            self._ask_counts = {}
            self._facts = {}
            self._topic = None
            self._topic_label = None
            self._direct = False
            self._episode_asked = 0
            self._barrier_offered = False
            self._memory = None
            self.last_updated = _utcnow()

    def _touch(self) -> None:
        with self._lock:
            self.last_updated = _utcnow()

    def is_stale(self, now: datetime) -> bool:
        with self._lock:
            return (now - self.last_updated) > INTERVIEW_TTL

    def get_last_updated(self) -> datetime:
        with self._lock:
            return self.last_updated


_STORE: Dict[str, RehabSessionState] = {}
_LOCK = threading.Lock()


def _normalize_patient_id(patient_id: Optional[str]) -> str:
    return (patient_id or "UNKNOWN_PATIENT").strip().upper()


def _evict_if_over_capacity(now: datetime, protected_key: Optional[str] = None) -> None:
    if len(_STORE) <= MAX_STORE_SIZE:
        return
    candidates = [key for key in _STORE if key != protected_key]
    overflow = len(_STORE) - MAX_STORE_SIZE
    oldest_keys = sorted(candidates, key=lambda key: _STORE[key].get_last_updated())[:overflow]
    for key in oldest_keys:
        del _STORE[key]


def get_or_create_state(patient_id: str) -> RehabSessionState:
    """Fetch (creating if needed) the state for `patient_id`. A session
    untouched for longer than INTERVIEW_TTL is reset in place, so a patient
    returning after a real gap is asked the safety questions afresh."""
    key = _normalize_patient_id(patient_id)
    now = _utcnow()
    with _LOCK:
        existing = _STORE.get(key)
        if existing is not None:
            if existing.is_stale(now):
                existing._reset_for_staleness()
            else:
                existing._touch()
            return existing
        state = RehabSessionState(patient_id=key)
        _STORE[key] = state
        _evict_if_over_capacity(now, protected_key=key)
        return state


def peek_state(patient_id: str) -> Optional[RehabSessionState]:
    """Read-only lookup: never creates state, never touches last_updated,
    None when no live (non-stale) session exists."""
    key = _normalize_patient_id(patient_id)
    with _LOCK:
        state = _STORE.get(key)
        if state is None or state.is_stale(_utcnow()):
            return None
        return state


def _clear_all_state_for_tests() -> None:
    with _LOCK:
        _STORE.clear()
