"""
Patient memory for the Pain & Symptoms and Recovery Progress agents --
"remember before asking".

A thin, best-effort wrapper over the EXISTING patient_database.py functions
(no schema change, no new table, no new column). It gives an agent one
place to read what is already on record for a patient before it asks a
question, and one place to write what an interview concluded:

    READ (load_patient_memory):
        - today's `metrics` row (pain_score / swelling / triage / ROM), if any
        - the `metrics` rows of the last 7 days (recent_metrics), so the
          Recovery agent can confirm a value logged today or yesterday
          instead of asking, and show a trend when two or more exist
        - the request's own `current_rom` text, parsed into flexion /
          extension degrees (request_rom) -- a value the client already
          sent is never asked for again
        - the last three completed `symptom_assessments` rows, oldest first
        - the procedure (TKA/THA/GEN), surgery_type and weight_bearing_status
          from `patients`/`surgeries`

    WRITE:
        - write_today_metrics(): today's `metrics` pain_score / swelling /
          triage / rom_flexion / rom_extension / exercise_completed (update
          the row for today's date if it exists, otherwise insert one --
          the table already has every one of these columns)
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

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple


def today_iso(today: Optional[str] = None) -> str:
    """ISO date (YYYY-MM-DD) used as the `metrics.date` key for "today".
    `today` lets tests pin the date; production callers leave it None."""
    return today or date.today().isoformat()


def _parse_iso(value: Any) -> Optional[date]:
    text = str(value or "").strip()
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _as_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------------
# The request's current_rom field ("flexion 85, extension 5", "85/5",
# "bend 85 degrees, straighten to 3") -> {"rom_flexion": 85.0, "rom_extension": 5.0}.
# Parsing only; nothing is inferred.
# ----------------------------------------------------------------------------

_ROM_PAIR_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:°|degrees?)?\s*/\s*(\d+(?:\.\d+)?)\s*(?:°|degrees?)?\s*$")
_FLEXION_RE = re.compile(r"\b(?:flexion|flex|bend(?:ing)?|bent)\b[^0-9]{0,20}?(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:°|degrees?)?\s*(?:of\s+)?(?:flexion|flex|bend(?:ing)?)\b", re.IGNORECASE)
_EXTENSION_RE = re.compile(r"\b(?:extension|ext|straighten(?:ing)?|straight|lag)\b[^0-9]{0,20}?(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:°|degrees?)?\s*(?:of\s+)?(?:extension|ext|straightening)\b", re.IGNORECASE)


def parse_current_rom(text: Optional[str]) -> Dict[str, float]:
    """Degrees named in a free-text ROM field. Returns only what is
    explicitly labelled (or an unambiguous "flexion/extension" pair)."""
    result: Dict[str, float] = {}
    if not text:
        return result
    raw = str(text).strip()
    pair = _ROM_PAIR_RE.match(raw)
    if pair:
        result["rom_flexion"] = float(pair.group(1))
        result["rom_extension"] = float(pair.group(2))
        return result
    flexion = _FLEXION_RE.search(raw)
    if flexion:
        result["rom_flexion"] = float(flexion.group(1) or flexion.group(2))
    extension = _EXTENSION_RE.search(raw)
    if extension:
        result["rom_extension"] = float(extension.group(1) or extension.group(2))
    return result


@dataclass
class PatientMemory:
    patient_id: str
    today_metrics: Optional[Dict[str, Any]] = None
    recent_metrics: List[Dict[str, Any]] = field(default_factory=list)
    request_rom: Dict[str, float] = field(default_factory=dict)
    recent_assessments: List[Dict[str, Any]] = field(default_factory=list)
    surgery_type: Optional[str] = None
    procedure: Optional[str] = None
    weight_bearing_status: Optional[str] = None
    record_found: bool = False
    today: str = field(default_factory=today_iso)

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

    # ------------------------------------------------------------------
    # Recent-metrics helpers (Recovery agent).
    # ------------------------------------------------------------------

    def metric_series(self, column: str, *, days: int = 7) -> List[Tuple[str, float]]:
        """(date, value) pairs for `column` over the last `days` days,
        oldest first, one per date (the last row written for a date wins).
        Only numeric, non-null values are returned."""
        today_date = _parse_iso(self.today) or date.today()
        cutoff = today_date - timedelta(days=days - 1)
        by_date: Dict[str, float] = {}
        for row in self.recent_metrics:
            row_date = _parse_iso(row.get("date"))
            value = _as_float(row.get(column))
            if row_date is None or value is None or row_date < cutoff or row_date > today_date:
                continue
            by_date[row_date.isoformat()] = value
        return sorted(by_date.items())

    def latest_metric(self, column: str, *, within_days: int = 1) -> Optional[Tuple[str, float, int]]:
        """The most recent logged value of `column` no older than
        `within_days` days (0 = today only, 1 = today or yesterday), as
        (date, value, days_ago) -- or None."""
        today_date = _parse_iso(self.today) or date.today()
        series = self.metric_series(column, days=max(within_days + 1, 1))
        if not series:
            return None
        row_date_text, value = series[-1]
        row_date = _parse_iso(row_date_text) or today_date
        days_ago = (today_date - row_date).days
        if days_ago > within_days:
            return None
        return row_date_text, value, days_ago

    def today_metric(self, column: str) -> Optional[float]:
        if not self.today_metrics:
            return None
        return _as_float(self.today_metrics.get(column))


def empty_memory(patient_id: str, today: Optional[str] = None) -> PatientMemory:
    return PatientMemory(patient_id=str(patient_id or "").strip().upper(), today=today_iso(today))


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
    recent_days: int = 7,
    current_rom: Optional[str] = None,
    today: Optional[str] = None,
) -> PatientMemory:
    """
    Read everything an agent should know BEFORE asking anything. Always
    returns a PatientMemory; every read is independent and best-effort, so
    a failure in one leaves the others intact. `current_rom` is the
    request's own free-text ROM field, parsed into request_rom.
    """
    memory = empty_memory(patient_id, today)
    memory.request_rom = parse_current_rom(current_rom)
    clean_id = memory.patient_id
    if not clean_id:
        return memory

    try:
        from patient_database import get_patient

        record = get_patient(clean_id)
    except Exception as exc:
        print(f"[MEMORY] patient record lookup failed: {exc}")
        record = None

    if record:
        memory.record_found = True
        memory.surgery_type = record.get("surgery_type")
        memory.procedure = _resolve_procedure(memory.surgery_type)
        memory.weight_bearing_status = record.get("weight_bearing_status")
        today_key = memory.today
        today_date = _parse_iso(today_key) or date.today()
        cutoff = today_date - timedelta(days=max(recent_days, 1) - 1)
        for row in record.get("metrics_history") or []:
            row_date_text = str(row.get("date") or "").strip()
            if row_date_text == today_key:
                memory.today_metrics = dict(row)
                # Keep scanning -- the LAST row for today wins, matching
                # insertion order (a later write supersedes an earlier one).
            row_date = _parse_iso(row_date_text)
            if row_date is not None and cutoff <= row_date <= today_date:
                memory.recent_metrics.append(dict(row))

    try:
        from patient_database import get_recent_symptom_assessments

        memory.recent_assessments = get_recent_symptom_assessments(
            clean_id, limit=assessments_limit,
        )
    except Exception as exc:
        print(f"[MEMORY] symptom history lookup failed: {exc}")
        memory.recent_assessments = []

    return memory


def write_today_metrics(
    patient_id: str,
    *,
    pain_score: Optional[float] = None,
    swelling: Optional[str] = None,
    triage: Optional[str] = None,
    rom_flexion: Optional[float] = None,
    rom_extension: Optional[float] = None,
    exercise_completed: Optional[bool] = None,
    postop_day: Optional[int] = None,
    today: Optional[str] = None,
) -> bool:
    """
    Record today's values in the existing `metrics` table. Updates today's
    row in place when one exists (only the supplied, non-None columns are
    touched), otherwise inserts a new row for today. Returns True on
    success, False on any failure (logged, never raised) or when nothing
    was supplied.

    Numeric columns must be exact numbers; callers pass None for a
    category-only, range-only or unknown value so nothing fabricated is
    ever stored.
    """
    clean_id = str(patient_id or "").strip().upper()
    if not clean_id:
        return False

    columns: List[Tuple[str, Any]] = [
        ("pain_score", pain_score), ("swelling", swelling), ("triage", triage),
        ("rom_flexion", rom_flexion), ("rom_extension", rom_extension),
        ("exercise_completed", None if exercise_completed is None else int(bool(exercise_completed))),
    ]
    supplied = [(column, value) for column, value in columns if value is not None]
    if not supplied:
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
                assignments = [f"{column} = ?" for column, _ in supplied]
                params: List[Any] = [value for _, value in supplied]
                if postop_day is not None:
                    assignments.append("day = COALESCE(day, ?)")
                    params.append(postop_day)
                params.append(existing["id"])
                connection.execute(
                    f"UPDATE metrics SET {', '.join(assignments)} WHERE id = ?", params,
                )
            else:
                names = ["patient_id", "day", "date"] + [column for column, _ in supplied]
                values: List[Any] = [clean_id, postop_day, today_key] + [value for _, value in supplied]
                connection.execute(
                    f"INSERT INTO metrics ({', '.join(names)}) VALUES ({', '.join(['?'] * len(values))})",
                    values,
                )
        return True
    except Exception as exc:
        print(f"[MEMORY] today's metrics write failed: {exc}")
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
        print(f"[MEMORY] symptom assessment write failed: {exc}")
        return False


def load_recent_assessments(patient_id: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Prior completed assessments, oldest first; [] on any failure."""
    try:
        from patient_database import get_recent_symptom_assessments

        return get_recent_symptom_assessments(patient_id, limit=limit)
    except Exception as exc:
        print(f"[MEMORY] symptom history lookup failed: {exc}")
        return []
