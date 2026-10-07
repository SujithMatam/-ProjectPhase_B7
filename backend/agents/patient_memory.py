"""
Patient memory for the Pain & Symptoms agent -- "remember before asking".

A thin, best-effort wrapper over the EXISTING patient_database.py functions
(no schema change, no new table, no new column). It gives the Pain agent one
place to read what is already on record for a patient before it asks a
question, and one place to write what an interview concluded:

    READ (load_patient_memory):
        - today's `metrics` row (pain_score / swelling / triage), if any
        - the last three completed `symptom_assessments` rows, oldest first
        - the procedure (TKA/THA/GEN), surgery_type and weight_bearing_status
          from `patients`/`surgeries`

    WRITE:
        - write_today_metrics(): today's `metrics` pain_score/swelling
          (update the row for today's date if it exists, otherwise insert
          one -- the table already has `date`, `pain_score`, `swelling`,
          `triage` and `day` columns, so nothing new is needed)
        - write_symptom_assessment(): one completed assessment row via the
          existing patient_database.save_symptom_assessment()

Every function here is BEST-EFFORT: a missing/unknown patient_id, a closed
database, or a foreign-key failure is logged and swallowed, never raised --
memory must never block or fail a patient-facing turn. A patient with no
record at all gets an empty PatientMemory, and the agent behaves exactly as
it would with no memory.

Nothing here infers or calculates a clinical value: it only reads back what
the application previously stored and writes what the patient reported.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional


def today_iso(today: Optional[str] = None) -> str:
    """ISO date (YYYY-MM-DD) used as the `metrics.date` key for "today".
    `today` lets tests pin the date; production callers leave it None."""
    return today or date.today().isoformat()


@dataclass
class PatientMemory:
    patient_id: str
    today_metrics: Optional[Dict[str, Any]] = None
    recent_assessments: List[Dict[str, Any]] = field(default_factory=list)
    surgery_type: Optional[str] = None
    procedure: Optional[str] = None
    weight_bearing_status: Optional[str] = None
    record_found: bool = False

    @property
    def today_pain_score(self) -> Optional[int]:
        """Today's logged pain score as an int, or None when today has no
        row / no score. Never fabricates a number from a category."""
        if not self.today_metrics:
            return None
        value = self.today_metrics.get("pain_score")
        if value is None:
            return None
        try:
            score = int(round(float(value)))
        except (TypeError, ValueError):
            return None
        return score if 0 <= score <= 10 else None

    @property
    def today_swelling(self) -> Optional[str]:
        if not self.today_metrics:
            return None
        value = self.today_metrics.get("swelling")
        return str(value).strip() if value else None

    @property
    def previous_assessment(self) -> Optional[Dict[str, Any]]:
        """The most recently COMPLETED assessment (the list is oldest
        first), or None for a patient with no history."""
        return self.recent_assessments[-1] if self.recent_assessments else None


def empty_memory(patient_id: str) -> PatientMemory:
    return PatientMemory(patient_id=str(patient_id or "").strip().upper())


def _resolve_procedure(surgery_type: Optional[str]) -> Optional[str]:
    if not surgery_type:
        return None
    try:
        from lam.schemas import resolve_procedure_code

        return resolve_procedure_code(str(surgery_type))
    except Exception:
        return None


def load_patient_memory(
    patient_id: str,
    *,
    assessments_limit: int = 3,
    today: Optional[str] = None,
) -> PatientMemory:
    """
    Read everything the Pain agent should know BEFORE asking anything.
    Always returns a PatientMemory; every read is independent and
    best-effort, so a failure in one leaves the others intact.
    """
    memory = empty_memory(patient_id)
    clean_id = memory.patient_id
    if not clean_id:
        return memory

    try:
        from patient_database import get_patient

        record = get_patient(clean_id)
    except Exception as exc:
        print(f"[PAIN][MEMORY] patient record lookup failed: {exc}")
        record = None

    if record:
        memory.record_found = True
        memory.surgery_type = record.get("surgery_type")
        memory.procedure = _resolve_procedure(memory.surgery_type)
        memory.weight_bearing_status = record.get("weight_bearing_status")
        today_key = today_iso(today)
        for row in record.get("metrics_history") or []:
            if str(row.get("date") or "").strip() == today_key:
                memory.today_metrics = dict(row)
                # Keep scanning -- the LAST row for today wins, matching
                # insertion order (a later write supersedes an earlier one).

    try:
        from patient_database import get_recent_symptom_assessments

        memory.recent_assessments = get_recent_symptom_assessments(
            clean_id, limit=assessments_limit,
        )
    except Exception as exc:
        print(f"[PAIN][MEMORY] symptom history lookup failed: {exc}")
        memory.recent_assessments = []

    return memory


def write_today_metrics(
    patient_id: str,
    *,
    pain_score: Optional[float] = None,
    swelling: Optional[str] = None,
    triage: Optional[str] = None,
    postop_day: Optional[int] = None,
    today: Optional[str] = None,
) -> bool:
    """
    Record today's pain_score/swelling in the existing `metrics` table.
    Updates today's row in place when one exists (only the supplied,
    non-None columns are touched), otherwise inserts a new row for today.
    Returns True on success, False on any failure (logged, never raised).

    `pain_score` must be an exact number; callers pass None for a
    category-only or unknown score so nothing fabricated is ever stored.
    """
    clean_id = str(patient_id or "").strip().upper()
    if not clean_id:
        return False
    if pain_score is None and swelling is None and triage is None:
        return False

    today_key = today_iso(today)
    try:
        from patient_database import connection_scope, initialize_database

        initialize_database()
        with connection_scope() as connection:
            existing = connection.execute(
                "SELECT id FROM metrics WHERE patient_id = ? AND date = ? ORDER BY id DESC LIMIT 1",
                (clean_id, today_key),
            ).fetchone()

            if existing is not None:
                assignments: List[str] = []
                params: List[Any] = []
                for column, value in (
                    ("pain_score", pain_score), ("swelling", swelling), ("triage", triage),
                ):
                    if value is not None:
                        assignments.append(f"{column} = ?")
                        params.append(value)
                if postop_day is not None:
                    assignments.append("day = COALESCE(day, ?)")
                    params.append(postop_day)
                params.append(existing["id"])
                connection.execute(
                    f"UPDATE metrics SET {', '.join(assignments)} WHERE id = ?", params,
                )
            else:
                connection.execute(
                    """INSERT INTO metrics
                       (patient_id, day, date, pain_score, swelling, triage)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (clean_id, postop_day, today_key, pain_score, swelling, triage),
                )
        return True
    except Exception as exc:
        print(f"[PAIN][MEMORY] today's metrics write failed: {exc}")
        return False


def write_symptom_assessment(patient_id: str, record: Dict[str, Any]) -> bool:
    """One completed assessment row via the existing
    patient_database.save_symptom_assessment(). Best-effort: an unknown
    patient_id fails the foreign-key check and is logged, not raised."""
    try:
        from patient_database import save_symptom_assessment

        save_symptom_assessment(patient_id, record)
        return True
    except Exception as exc:
        print(f"[PAIN][MEMORY] symptom assessment write failed: {exc}")
        return False


def load_recent_assessments(patient_id: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Prior completed assessments, oldest first; [] on any failure."""
    try:
        from patient_database import get_recent_symptom_assessments

        return get_recent_symptom_assessments(patient_id, limit=limit)
    except Exception as exc:
        print(f"[PAIN][MEMORY] symptom history lookup failed: {exc}")
        return []
