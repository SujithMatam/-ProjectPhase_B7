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
    email TEXT,
    phone_number TEXT,
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
CREATE TABLE IF NOT EXISTS patient_credentials (
    patient_id TEXT PRIMARY KEY REFERENCES patients(patient_id) ON DELETE CASCADE,
    username TEXT NOT NULL,
    email TEXT,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wound_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    postop_day INTEGER,
    date TEXT NOT NULL DEFAULT (date('now')),
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    onset TEXT,
    progression TEXT,
    appearance TEXT,
    warmth TEXT,
    drainage TEXT,
    drainage_type TEXT,
    separation TEXT,
    pain TEXT,
    fever TEXT,
    dressing_status TEXT,
    redness_score REAL,
    visual_flag TEXT,
    triage_level TEXT,
    summary TEXT
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
CREATE TABLE IF NOT EXISTS patient_scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    scan_type TEXT NOT NULL,         -- 'XRAY', 'MRI', 'CT', 'ULTRASOUND'
    body_part TEXT NOT NULL,         -- 'Knee', 'Hip', 'Shoulder', 'Spine', 'Ankle'
    laterality TEXT,                 -- 'Left', 'Right', 'Bilateral', 'Central'
    scan_date TEXT,                  -- ISO date of scan
    file_path TEXT,                  -- absolute or repo-relative path to image file
    file_format TEXT,                -- 'JPEG', 'PNG', 'DICOM'
    source_dataset TEXT,             -- e.g. 'Kaggle:orvile/digital-knee-xray-images'
    findings TEXT,                   -- radiologist/AI findings text
    kl_grade INTEGER,                -- Kellgren-Lawrence OA grade 0-4 (NULL if N/A)
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


def _ensure_symptom_assessment_columns(connection: sqlite3.Connection) -> None:
    """
    Additive migration for a symptom_assessments table created by an OLDER
    version of SCHEMA (before pain_severity_category existed) -- adds the
    column in place, without dropping or rewriting any existing row, so an
    already-existing local SQLite database keeps every historical
    assessment. A brand-new database already gets the column straight from
    SCHEMA above; this is a no-op for it (the column already exists).
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
        # Migrate existing tables if columns are missing
        for col in ["email", "phone_number"]:
            try:
                connection.execute(f"ALTER TABLE patients ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError:
                pass
        for col in ["email"]:
            try:
                connection.execute(f"ALTER TABLE patient_credentials ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError:
                pass

        _ensure_symptom_assessment_columns(connection)
        connection.execute(
            """INSERT OR IGNORE INTO patient_credentials
               (patient_id, username, password_hash)
               SELECT patient_id, patient_id, LOWER(patient_id) FROM patients"""
        )
        # Ensure demo account credentials and emails are populated if patients exist
        try:
            for pid, uname, em, pw, ph in [
                ('PT-B7-8921', 'Rishi Priyan V N', 'b7@amrita.edu', 'password123', '+91 98765 43210'),
                ('PT-B7-8922', 'Sujith Matam', 'sujith@amrita.edu', 'password123', '+91 98765 43211'),
            ]:
                has_patient = connection.execute("SELECT 1 FROM patients WHERE patient_id = ?", (pid,)).fetchone()
                if has_patient:
                    connection.execute(
                        """INSERT OR REPLACE INTO patient_credentials
                           (patient_id, username, email, password_hash)
                           VALUES (?, ?, ?, ?)""",
                        (pid, uname, em, pw)
                    )
                    connection.execute(
                        "UPDATE patients SET email = ?, phone_number = ? WHERE patient_id = ? AND (email IS NULL OR email = '')",
                        (em, ph, pid)
                    )
        except Exception:
            pass


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
    email = str(record.get("email") or "").strip().lower() or None
    phone_number = str(record.get("phone_number") or "").strip() or None
    password = str(record.get("password") or record.get("password_hash") or "").strip()

    demo_defaults = {
        'PT-B7-8921': {'email': 'b7@amrita.edu', 'password': 'password123', 'phone': '+91 98765 43210'},
        'PT-B7-8922': {'email': 'sujith@amrita.edu', 'password': 'password123', 'phone': '+91 98765 43211'},
    }
    if required in demo_defaults:
        if not email:
            email = demo_defaults[required]['email']
        if not phone_number:
            phone_number = demo_defaults[required]['phone']
        if not password:
            password = demo_defaults[required]['password']

    if not password:
        password = required.lower()

    with connection_scope(path) as connection:
        connection.execute(
            """INSERT INTO patients (patient_id, full_name, age, gender, allergies, email, phone_number)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (required, record.get("full_name") or "Unnamed patient", record.get("age"),
             record.get("gender"), record.get("allergies"), email, phone_number),
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
        username = str(record.get("username") or record.get("full_name") or required).strip()
        connection.execute(
            """INSERT OR REPLACE INTO patient_credentials
               (patient_id, username, email, password_hash) VALUES (?, ?, ?, ?)""",
            (required, username, email, password),
        )
    return get_patient(required, path)  # type: ignore[return-value]


def authenticate_patient(
    identifier: str,
    password: str,
    path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Authenticate by patient ID, username, or email."""
    clean_identifier = str(identifier or "").strip().casefold()
    clean_password = str(password or "").strip()
    with connection_scope(path) as connection:
        row = connection.execute(
            """SELECT patient_id FROM patient_credentials
               WHERE (LOWER(patient_id) = ? OR LOWER(username) = ? OR LOWER(COALESCE(email, '')) = ?)
                 AND (password_hash = ? OR LOWER(password_hash) = LOWER(?))""",
            (clean_identifier, clean_identifier, clean_identifier, clean_password, clean_password),
        ).fetchone()
        if not row:
            row = connection.execute(
                """SELECT p.patient_id FROM patients p
                   JOIN patient_credentials pc ON p.patient_id = pc.patient_id
                   WHERE LOWER(COALESCE(p.email, '')) = ?
                     AND (pc.password_hash = ? OR LOWER(pc.password_hash) = LOWER(?))""",
                (clean_identifier, clean_password, clean_password),
            ).fetchone()
    return get_patient(row["patient_id"], path) if row else None


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
        cred = connection.execute("SELECT email, username FROM patient_credentials WHERE patient_id = ?", (patient_id,)).fetchone()
        if cred:
            if not result.get("email") and cred["email"]:
                result["email"] = cred["email"]
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
        result["scans"] = [
            {k: item[k] for k in ("id", "scan_type", "body_part", "laterality",
                                   "scan_date", "file_path", "file_format",
                                   "source_dataset", "findings", "kl_grade")}
            for item in connection.execute(
                "SELECT * FROM patient_scans WHERE patient_id = ? ORDER BY scan_date DESC",
                (patient_id,)
            )
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


def save_wound_assessment(
    patient_id: str,
    record: Dict[str, Any],
    path: Optional[str] = None,
) -> int:
    """Save completed wound assessment to SQLite."""
    initialize_database(path)
    with connection_scope(path) as connection:
        cursor = connection.execute(
            """INSERT INTO wound_assessments
               (patient_id, postop_day, onset, progression, appearance, warmth,
                drainage, drainage_type, separation, pain, fever, dressing_status,
                redness_score, visual_flag, triage_level, summary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                patient_id,
                record.get("postop_day"),
                record.get("onset"),
                record.get("progression"),
                record.get("appearance"),
                record.get("warmth"),
                record.get("drainage"),
                record.get("drainage_type"),
                record.get("separation"),
                record.get("pain"),
                record.get("fever"),
                record.get("dressing_status"),
                record.get("redness_score"),
                record.get("visual_flag"),
                record.get("triage_level", "GREEN"),
                record.get("summary"),
            ),
        )
        return cursor.lastrowid


def get_recent_wound_assessments(
    patient_id: str,
    limit: int = 3,
    path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve recent completed wound assessments for longitudinal comparison."""
    initialize_database(path)
    with connection_scope(path) as connection:
        rows = connection.execute(
            """SELECT * FROM wound_assessments
               WHERE patient_id = ?
               ORDER BY id DESC LIMIT ?""",
            (patient_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]


def record_triage_event(
    patient_id: str,
    level: str,
    symptom: str,
    action: str,
    timestamp: Optional[str] = None,
    path: Optional[str] = None,
) -> None:
    """Record a clinical triage alert event in SQLite."""
    from datetime import datetime
    initialize_database(path)
    clean_id = (patient_id or "").strip().upper()
    ts = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M")
    with connection_scope(path) as connection:
        connection.execute(
            """INSERT INTO triage_events (patient_id, timestamp, level, symptom, action)
               VALUES (?, ?, ?, ?, ?)""",
            (clean_id, ts, level, symptom, action),
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


def add_patient_scan(
    patient_id: str,
    scan_type: str,
    body_part: str,
    file_path: str,
    *,
    laterality: Optional[str] = None,
    scan_date: Optional[str] = None,
    file_format: Optional[str] = None,
    source_dataset: Optional[str] = None,
    findings: Optional[str] = None,
    kl_grade: Optional[int] = None,
    path: Optional[str] = None,
) -> int:
    """Insert a scan record for a patient. Returns the new row id.

    Args:
        patient_id:     Patient ID (must already exist).
        scan_type:      'XRAY', 'MRI', 'CT', or 'ULTRASOUND'.
        body_part:      'Knee', 'Hip', 'Shoulder', 'Spine', 'Ankle', etc.
        file_path:      Absolute or repo-relative path to the image file.
        laterality:     'Left', 'Right', 'Bilateral', or 'Central'.
        scan_date:      ISO-format date string of when the scan was taken.
        file_format:    'JPEG', 'PNG', 'DICOM', etc.
        source_dataset: Attribution string, e.g. 'Kaggle:orvile/digital-knee-xray-images'.
        findings:       Free-text radiological / AI findings.
        kl_grade:       Kellgren-Lawrence osteoarthritis grade (0-4), or None.
        path:           Override DB file path.
    """
    initialize_database(path)
    with connection_scope(path) as conn:
        cursor = conn.execute(
            """INSERT INTO patient_scans
               (patient_id, scan_type, body_part, laterality, scan_date,
                file_path, file_format, source_dataset, findings, kl_grade)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (patient_id, scan_type, body_part, laterality, scan_date,
             file_path, file_format, source_dataset, findings, kl_grade),
        )
        return cursor.lastrowid  # type: ignore[return-value]


def list_patient_scans(patient_id: str, path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all scan records for a patient, newest first."""
    initialize_database(path)
    with connection_scope(path) as conn:
        return [
            {k: row[k] for k in ("id", "scan_type", "body_part", "laterality",
                                  "scan_date", "file_path", "file_format",
                                  "source_dataset", "findings", "kl_grade")}
            for row in conn.execute(
                "SELECT * FROM patient_scans WHERE patient_id = ? ORDER BY scan_date DESC",
                (patient_id,),
            )
        ]
