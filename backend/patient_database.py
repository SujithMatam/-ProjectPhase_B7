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


def initialize_database(path: Optional[str] = None) -> None:
    with connection_scope(path) as connection:
        connection.executescript(SCHEMA)


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
