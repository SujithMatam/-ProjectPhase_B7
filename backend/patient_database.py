"""Small SQLite persistence layer for patient reports and recovery data.

The database stores only values supplied by the report/application.  It does
not calculate or infer clinical values; callers may continue to use the
report agent's non-persistent template for unknown IDs.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

DEFAULT_DATABASE_PATH = str(Path(__file__).with_name("patients.sqlite3"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    age INTEGER,
    gender TEXT,
    allergies TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS surgeries (
    patient_id TEXT PRIMARY KEY REFERENCES patients(patient_id) ON DELETE CASCADE,
    surgery_type TEXT,
    affected_limb TEXT,
    surgery_date TEXT,
    postop_day INTEGER,
    surgeon TEXT,
    implant TEXT,
    weight_bearing_status TEXT
);
CREATE TABLE IF NOT EXISTS medications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    dose TEXT,
    purpose TEXT,
    adherence_pct REAL,
    times_json TEXT
);
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    day INTEGER,
    date TEXT,
    pain_score REAL,
    rom_flexion REAL,
    rom_extension REAL,
    exercise_completed INTEGER,
    swelling TEXT,
    triage TEXT
);
CREATE TABLE IF NOT EXISTS triage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    timestamp TEXT,
    level TEXT,
    symptom TEXT,
    action TEXT
);
CREATE TABLE IF NOT EXISTS source_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT REFERENCES patients(patient_id) ON DELETE SET NULL,
    filename TEXT,
    extraction_method TEXT,
    raw_text_preview TEXT,
    extracted_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS symptom_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    postop_day INTEGER,
    pain_score REAL,
    pain_severity_category TEXT,
    onset TEXT,
    location TEXT,
    worsening_or_improving TEXT,
    pain_characteristics TEXT,
    swelling TEXT,
    warmth_or_redness TEXT,
    stiffness TEXT,
    numbness_or_weakness TEXT,
    fever_or_temperature TEXT,
    temperature_c REAL,
    triage_level TEXT
);
"""


def database_path(path: Optional[str] = None) -> str:
    return path or os.getenv("PATIENT_DATABASE_PATH", DEFAULT_DATABASE_PATH)


def get_connection(path: Optional[str] = None) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path(path), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def connection_scope(path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    connection = get_connection(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _ensure_symptom_assessment_columns(connection: sqlite3.Connection) -> None:
    """
    Additive migration for a symptom_assessments table created by an OLDER
    version of SCHEMA (before pain_severity_category existed) -- adds the
    column in place, without dropping or rewriting any existing row, so an
    already-existing local SQLite database keeps every historical
    assessment. A brand-new database already gets the column straight from
    SCHEMA above; this is a no-op for it (the column already exists).
    `PRAGMA table_info` is read every call rather than cached, since this
    only runs once per initialize_database() call and a stale cache could
    otherwise wrongly skip a genuinely-needed ALTER TABLE.
    """
    existing_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(symptom_assessments)")
    }
    if not existing_columns:
        # Table doesn't exist yet -- SCHEMA above (already executed this
        # same call) will have just created it with the column present.
        return
    if "pain_severity_category" not in existing_columns:
        connection.execute(
            "ALTER TABLE symptom_assessments ADD COLUMN pain_severity_category TEXT"
        )


def initialize_database(path: Optional[str] = None) -> None:
    with connection_scope(path) as connection:
        connection.executescript(SCHEMA)
        _ensure_symptom_assessment_columns(connection)


def _insert_children(connection: sqlite3.Connection, patient: Dict[str, Any]) -> None:
    patient_id = patient["patient_id"]
    for medication in patient.get("current_medications", []):
        connection.execute(
            """INSERT INTO medications
               (patient_id, name, dose, purpose, adherence_pct, times_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (patient_id, medication.get("name", "Unnamed medication"),
             medication.get("dose"), medication.get("purpose"),
             medication.get("adherence_pct"),
             json.dumps(medication.get("times") or medication.get("schedule_times"))
             if medication.get("times") or medication.get("schedule_times") else None),
        )
    for metric in patient.get("metrics_history", []):
        connection.execute(
            """INSERT INTO metrics
               (patient_id, day, date, pain_score, rom_flexion, rom_extension,
                exercise_completed, swelling, triage)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (patient_id, metric.get("day"), metric.get("date"),
             metric.get("pain_score"), metric.get("rom_flexion"),
             metric.get("rom_extension"), int(bool(metric.get("exercise_completed")))
             if metric.get("exercise_completed") is not None else None,
             metric.get("swelling"), metric.get("triage")),
        )
    for event in patient.get("triage_events", []):
        connection.execute(
            """INSERT INTO triage_events
               (patient_id, timestamp, level, symptom, action)
               VALUES (?, ?, ?, ?, ?)""",
            (patient_id, event.get("timestamp"), event.get("level"),
             event.get("symptom"), event.get("action")),
        )


def create_patient(patient: Dict[str, Any], path: Optional[str] = None) -> Dict[str, Any]:
    """Insert a patient and related records. Duplicate IDs raise IntegrityError."""
    initialize_database(path)
    required = str(patient.get("patient_id", "")).strip()
    if not required:
        raise ValueError("patient_id is required")
    record = dict(patient)
    record["patient_id"] = required
    with connection_scope(path) as connection:
        connection.execute(
            """INSERT INTO patients (patient_id, full_name, age, gender, allergies)
               VALUES (?, ?, ?, ?, ?)""",
            (required, record.get("full_name") or "Unnamed patient", record.get("age"),
             record.get("gender"), record.get("allergies")),
        )
        connection.execute(
            """INSERT INTO surgeries
               (patient_id, surgery_type, affected_limb, surgery_date, postop_day,
                surgeon, implant, weight_bearing_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (required, record.get("surgery_type"), record.get("affected_limb"),
             record.get("surgery_date"), record.get("postop_day"), record.get("surgeon"),
             record.get("implant"), record.get("weight_bearing_status")),
        )
        _insert_children(connection, record)
    return get_patient(required, path)  # type: ignore[return-value]


def seed_patients(patients: Iterable[Dict[str, Any]], path: Optional[str] = None) -> None:
    initialize_database(path)
    for patient in patients:
        try:
            create_patient(patient, path)
        except sqlite3.IntegrityError:
            # Startup is idempotent and must not overwrite user data.
            continue


def get_patient(patient_id: str, path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    initialize_database(path)
    with connection_scope(path) as connection:
        row = connection.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,)).fetchone()
        surgery = connection.execute("SELECT * FROM surgeries WHERE patient_id = ?", (patient_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result.pop("created_at", None)
        result.pop("updated_at", None)
        if surgery:
            result.update({k: surgery[k] for k in (
                "surgery_type", "affected_limb", "surgery_date", "postop_day",
                "surgeon", "implant", "weight_bearing_status")})
        result["current_medications"] = []
        for item in connection.execute("SELECT * FROM medications WHERE patient_id = ? ORDER BY id", (patient_id,)):
            medication = {k: item[k] for k in ("name", "dose", "purpose", "adherence_pct")}
            if item["times_json"]:
                medication["times"] = json.loads(item["times_json"])
            result["current_medications"].append(medication)
        result["metrics_history"] = [
            {k: item[k] for k in ("day", "date", "pain_score", "rom_flexion", "rom_extension",
                                  "exercise_completed", "swelling", "triage")}
            for item in connection.execute("SELECT * FROM metrics WHERE patient_id = ? ORDER BY id", (patient_id,))
        ]
        result["triage_events"] = [
            {k: item[k] for k in ("timestamp", "level", "symptom", "action")}
            for item in connection.execute("SELECT * FROM triage_events WHERE patient_id = ? ORDER BY id", (patient_id,))
        ]
        return result


def list_patient_ids(path: Optional[str] = None) -> List[str]:
    initialize_database(path)
    with connection_scope(path) as connection:
        return [row[0] for row in connection.execute("SELECT patient_id FROM patients ORDER BY patient_id")]


def list_patients(path: Optional[str] = None) -> List[Dict[str, Any]]:
    initialize_database(path)
    return [
        get_patient(patient_id, path)
        for patient_id in list_patient_ids(path)
    ]


def delete_patient(patient_id: str, path: Optional[str] = None) -> bool:
    """Delete a patient and all dependent clinical records."""
    clean_id = str(patient_id or "").strip().upper()
    if not clean_id:
        return False
    initialize_database(path)
    with connection_scope(path) as connection:
        cursor = connection.execute(
            "DELETE FROM patients WHERE patient_id = ?", (clean_id,)
        )
        return cursor.rowcount > 0


def save_source_report(patient_id: Optional[str], filename: str, extraction: Dict[str, Any],
                       path: Optional[str] = None) -> None:
    initialize_database(path)
    with connection_scope(path) as connection:
        connection.execute(
            """INSERT INTO source_reports
               (patient_id, filename, extraction_method, raw_text_preview, extracted_json)
               VALUES (?, ?, ?, ?, ?)""",
            (patient_id, filename, extraction.get("extraction_method"),
             extraction.get("raw_text_preview"), json.dumps(extraction)),
        )


_SYMPTOM_ASSESSMENT_FIELDS = (
    "postop_day", "pain_score", "pain_severity_category", "onset", "location",
    "worsening_or_improving", "pain_characteristics", "swelling", "warmth_or_redness",
    "stiffness", "numbness_or_weakness", "fever_or_temperature", "temperature_c",
    "triage_level",
)


def save_symptom_assessment(patient_id: str, assessment: Dict[str, Any],
                             path: Optional[str] = None) -> None:
    """
    Persist ONE completed Pain & Symptoms assessment for `patient_id`, reusing
    this same patient database (no second, competing persistence mechanism).

    `assessment` may supply any subset of _SYMPTOM_ASSESSMENT_FIELDS -- missing
    fields are stored as NULL, never guessed.

    `pain_score` (REAL) and `pain_severity_category` (TEXT) are mutually
    exclusive, never both populated by the same assessment: an exact 0-10
    score (e.g. 7) is stored in `pain_score`, leaving `pain_severity_category`
    NULL; a patient-described category only ("mild"/"moderate"/"severe", with
    no exact number ever given, even after a simplified rephrase) is stored
    in `pain_severity_category`, leaving `pain_score` NULL -- never coerced
    into a fabricated exact numeric score (see
    agents/pain_integration.py::build_persistable_record, which is what
    decides which of the two columns a given assessment's pain_score value
    belongs in before calling this function).

    Raises sqlite3.IntegrityError if
    `patient_id` does not exist in the `patients` table (e.g. a generic/unknown
    patient_id that was never seeded/created) -- callers must treat persistence
    as best-effort and never let a failure here interrupt the patient-facing
    conversation (see agents/specialized_agents.py::PainSymptomsAgent).
    """
    initialize_database(path)
    clean_id = str(patient_id or "").strip().upper()
    with connection_scope(path) as connection:
        connection.execute(
            f"""INSERT INTO symptom_assessments
                (patient_id, {", ".join(_SYMPTOM_ASSESSMENT_FIELDS)})
                VALUES (?, {", ".join(["?"] * len(_SYMPTOM_ASSESSMENT_FIELDS))})""",
            (clean_id, *(assessment.get(field) for field in _SYMPTOM_ASSESSMENT_FIELDS)),
        )


def get_recent_symptom_assessments(patient_id: str, limit: int = 5,
                                    path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Most recent completed symptom assessments for `patient_id`, oldest first
    (so callers can read `[-1]` for "the last completed assessment"). Returns
    an empty list for a patient with no prior assessments -- never raises for
    an unknown patient_id, so a fresh conversation always works with no
    history available.
    """
    initialize_database(path)
    clean_id = str(patient_id or "").strip().upper()
    with connection_scope(path) as connection:
        rows = connection.execute(
            f"""SELECT created_at, {", ".join(_SYMPTOM_ASSESSMENT_FIELDS)}
                FROM symptom_assessments WHERE patient_id = ?
                ORDER BY id DESC LIMIT ?""",
            (clean_id, limit),
        ).fetchall()
        return [dict(row) for row in rows][::-1]
