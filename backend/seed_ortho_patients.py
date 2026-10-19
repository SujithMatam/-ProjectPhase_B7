"""
seed_ortho_patients.py
Generates and seeds 50 realistic de-identified orthopedic post-op patient
records into patients.sqlite3, fully compatible with patient_database.py schema.

Data is modelled after:
- ACORN registry field definitions (elective TKA/THA, PROMS)
- NHS / AAOS post-op recovery milestones
- OAI (Osteoarthritis Initiative) demographic distributions

Run from project root:
    python backend/seed_ortho_patients.py
    python backend/seed_ortho_patients.py --count 100   # generate more
    python backend/seed_ortho_patients.py --clear       # wipe + re-seed
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Allow import of patient_database without the full FastAPI app
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))
import patient_database as db

# ============================================================================
# CLINICAL REFERENCE DATA  (sourced from AAOS / NHS post-op protocols)
# ============================================================================

SURGERY_TYPES = [
    "Total Knee Arthroplasty",
    "Total Hip Arthroplasty",
    "Anterior Cruciate Ligament Reconstruction",
    "Rotator Cuff Repair",
    "Partial Knee Replacement (Unicompartmental)",
    "Hip Resurfacing",
    "Spinal Fusion (L4-L5)",
    "Tibial Plateau Fracture ORIF",
    "Shoulder Arthroplasty",
    "Ankle Arthroscopy",
]

LIMBS = {
    "Total Knee Arthroplasty":                 ["Left", "Right"],
    "Total Hip Arthroplasty":                  ["Left", "Right"],
    "Anterior Cruciate Ligament Reconstruction":["Left", "Right"],
    "Rotator Cuff Repair":                     ["Left", "Right"],
    "Partial Knee Replacement (Unicompartmental)": ["Left", "Right"],
    "Hip Resurfacing":                         ["Left", "Right"],
    "Spinal Fusion (L4-L5)":                   ["Central"],
    "Tibial Plateau Fracture ORIF":            ["Left", "Right"],
    "Shoulder Arthroplasty":                   ["Left", "Right"],
    "Ankle Arthroscopy":                       ["Left", "Right"],
}

IMPLANTS = {
    "Total Knee Arthroplasty":                 ["Stryker Triathlon", "Zimmer Biomet NexGen", "DePuy Attune", "Smith+Nephew Journey II"],
    "Total Hip Arthroplasty":                  ["Zimmer Biomet Taperloc", "DePuy Pinnacle", "Stryker Accolade II", "Smith+Nephew R3"],
    "Anterior Cruciate Ligament Reconstruction":["Patellar tendon graft", "Hamstring tendon graft", "Quadriceps tendon graft"],
    "Rotator Cuff Repair":                     ["Arthrex SwiveLock anchors", "Mitek HEALIX anchors", "Stryker PASTA anchors"],
    "Partial Knee Replacement (Unicompartmental)": ["Oxford Phase 3", "Stryker Triathlon PKR"],
    "Hip Resurfacing":                         ["Smith+Nephew Birmingham Hip", "DePuy ASR"],
    "Spinal Fusion (L4-L5)":                   ["Medtronic TLIF cage + pedicle screws"],
    "Tibial Plateau Fracture ORIF":            ["Synthes LCP periarticular plate", "Stryker AxSOS plate"],
    "Shoulder Arthroplasty":                   ["DePuy Global Advantage", "Zimmer Biomet Comprehensive"],
    "Ankle Arthroscopy":                       ["No implant (arthroscopic debridement)"],
}

WEIGHT_BEARING = {
    "Total Knee Arthroplasty":                 "Full weight-bearing as tolerated",
    "Total Hip Arthroplasty":                  "Partial weight-bearing with crutches for 6 weeks",
    "Anterior Cruciate Ligament Reconstruction":"Partial weight-bearing with brace for 4 weeks",
    "Rotator Cuff Repair":                     "Non-weight-bearing (arm in sling 4-6 weeks)",
    "Partial Knee Replacement (Unicompartmental)": "Full weight-bearing as tolerated",
    "Hip Resurfacing":                         "Full weight-bearing as tolerated from Day 1",
    "Spinal Fusion (L4-L5)":                   "Mobilise with physiotherapist from Day 2",
    "Tibial Plateau Fracture ORIF":            "Non-weight-bearing for 6-8 weeks",
    "Shoulder Arthroplasty":                   "Non-weight-bearing (arm in sling 4 weeks)",
    "Ankle Arthroscopy":                       "Partial weight-bearing with boot for 2 weeks",
}

SURGEONS = [
    "Dr. Amir Rajan", "Dr. Sarah Chen", "Dr. Priya Nair", "Dr. James Okafor",
    "Dr. Emily Walsh", "Dr. Rahul Menon", "Dr. Lisa Park", "Dr. Carlos Silva",
    "Dr. Ananya Sharma", "Dr. Michael O'Brien", "Dr. Fatima Al-Hassan",
]

FIRST_NAMES_M = ["Arjun", "James", "Mohammed", "Chen", "David", "Ravi", "Liam", "Samuel", "Thomas", "Anand", "George", "Carlos", "Vikram", "Patrick", "Kwame"]
FIRST_NAMES_F = ["Priya", "Sarah", "Aisha", "Li", "Emma", "Divya", "Sophie", "Amara", "Chloe", "Meena", "Grace", "Isabella", "Sneha", "Fiona", "Amira"]
LAST_NAMES    = ["Sharma", "Johnson", "Patel", "Williams", "Brown", "Kumar", "Davis", "Osei", "Martinez", "Thompson", "Nair", "Wilson", "Gupta", "Taylor", "Robinson", "Iyer", "Moore", "Singh", "Anderson", "Lee"]

ALLERGIES_POOL = [
    None, None, None,   # most patients have no known allergies
    "Penicillin", "NSAIDs", "Latex", "Aspirin", "Codeine", "Sulfa drugs",
    "Penicillin, Latex", "NSAIDs, Aspirin",
]

MEDICATIONS_BY_SURGERY: dict[str, list[dict]] = {
    "Total Knee Arthroplasty": [
        {"name": "Enoxaparin (Clexane)", "dose": "40mg SC OD", "purpose": "DVT prophylaxis", "times": ["08:00"]},
        {"name": "Paracetamol", "dose": "1g oral QDS", "purpose": "Analgesia", "times": ["08:00","12:00","17:00","22:00"]},
        {"name": "Celecoxib", "dose": "200mg oral BD", "purpose": "Anti-inflammatory analgesia", "times": ["08:00","20:00"]},
        {"name": "Oxycodone IR", "dose": "5mg oral PRN", "purpose": "Breakthrough pain", "times": []},
        {"name": "Omeprazole", "dose": "20mg oral OD", "purpose": "Gastric protection", "times": ["08:00"]},
    ],
    "Total Hip Arthroplasty": [
        {"name": "Rivaroxaban", "dose": "10mg oral OD", "purpose": "DVT/PE prophylaxis for 35 days", "times": ["08:00"]},
        {"name": "Paracetamol", "dose": "1g oral QDS", "purpose": "Analgesia", "times": ["08:00","12:00","17:00","22:00"]},
        {"name": "Diclofenac", "dose": "50mg oral TDS", "purpose": "Anti-inflammatory", "times": ["08:00","14:00","20:00"]},
        {"name": "Tramadol", "dose": "50mg oral PRN", "purpose": "Moderate pain relief", "times": []},
        {"name": "Omeprazole", "dose": "20mg oral OD", "purpose": "Gastric protection", "times": ["08:00"]},
    ],
    "Anterior Cruciate Ligament Reconstruction": [
        {"name": "Aspirin", "dose": "75mg oral OD", "purpose": "DVT prophylaxis for 2 weeks", "times": ["08:00"]},
        {"name": "Ibuprofen", "dose": "400mg oral TDS with food", "purpose": "Pain and inflammation", "times": ["08:00","14:00","20:00"]},
        {"name": "Paracetamol", "dose": "1g oral QDS", "purpose": "Analgesia", "times": ["08:00","12:00","17:00","22:00"]},
        {"name": "Co-codamol 30/500", "dose": "2 tablets oral PRN", "purpose": "Breakthrough pain", "times": []},
    ],
    "Rotator Cuff Repair": [
        {"name": "Aspirin", "dose": "75mg oral OD", "purpose": "DVT prophylaxis for 2 weeks", "times": ["08:00"]},
        {"name": "Paracetamol", "dose": "1g oral QDS", "purpose": "Analgesia", "times": ["08:00","12:00","17:00","22:00"]},
        {"name": "Naproxen", "dose": "500mg oral BD with food", "purpose": "Anti-inflammatory", "times": ["08:00","20:00"]},
        {"name": "Tramadol", "dose": "50mg oral PRN max 3 doses/day", "purpose": "Moderate breakthrough pain", "times": []},
    ],
    "DEFAULT": [
        {"name": "Paracetamol", "dose": "1g oral QDS", "purpose": "Analgesia", "times": ["08:00","12:00","17:00","22:00"]},
        {"name": "Ibuprofen", "dose": "400mg oral TDS with food", "purpose": "Anti-inflammatory", "times": ["08:00","14:00","20:00"]},
        {"name": "Aspirin", "dose": "75mg oral OD", "purpose": "DVT prophylaxis", "times": ["08:00"]},
    ],
}

TRIAGE_LEVELS = ["GREEN", "GREEN", "GREEN", "YELLOW", "GREEN", "GREEN", "RED"]

SYMPTOMS_BY_LEVEL = {
    "GREEN":  ["Mild swelling of operative leg", "Aching at incision site", "Fatigue after physiotherapy session"],
    "YELLOW": ["Moderate wound redness around incision (3-4cm)", "Low-grade fever 37.8C", "Increased pain score (7/10) after physiotherapy"],
    "RED":    ["Warm, swollen calf with throbbing — suspected DVT", "High fever 39.2C with purulent wound drainage", "Sudden shortness of breath and chest tightness"],
}

ACTIONS_BY_LEVEL = {
    "GREEN":  ["Advised elevation and ice therapy", "Reassured; continue prescribed exercises", "Advised to monitor and report any change"],
    "YELLOW": ["Instructed patient to contact surgical team same day", "Advised GP review within 24 hours", "Paused physiotherapy, recommended wound check"],
    "RED":    ["Emergency escalation — advised 999/ED immediately", "Surgical team alerted by doctor alert system", "Patient instructed to stop all activity and call emergency services"],
}


# ============================================================================
# GENERATION HELPERS
# ============================================================================

def _rand_date_past(max_days: int = 90) -> date:
    return date.today() - timedelta(days=random.randint(3, max_days))


def _build_metrics(surgery_date: date, postop_day: int, surgery_type: str) -> list[dict]:
    """Generate daily recovery metrics up to postop_day."""
    # ROM benchmarks vary by surgery
    base_flex  = 45.0 if "Knee" in surgery_type else 0.0
    target_flex = 120.0 if "Knee" in surgery_type else 90.0
    records = []
    for day in range(1, postop_day + 1):
        progress = day / max(postop_day, 1)
        pain = max(0.0, round(9.0 - 7.0 * progress + random.uniform(-1, 1), 1))
        rom_flex = round(base_flex + (target_flex - base_flex) * progress + random.uniform(-5, 5), 1) if "Knee" in surgery_type or "ACL" in surgery_type else None
        rom_ext  = round(max(0.0, 15.0 - 12.0 * progress + random.uniform(-2, 2)), 1) if "Knee" in surgery_type else None
        swelling_opts = ["None", "Mild", "Mild", "Moderate"] if day < 7 else ["None", "None", "Mild"]
        records.append({
            "day": day,
            "date": str(surgery_date + timedelta(days=day)),
            "pain_score": pain,
            "rom_flexion": rom_flex,
            "rom_extension": rom_ext,
            "exercise_completed": random.choice([True, True, True, False]),
            "swelling": random.choice(swelling_opts),
            "triage": random.choice(["GREEN", "GREEN", "GREEN", "GREEN", "YELLOW"]) if day > 3 else "GREEN",
        })
    return records


def _build_triage_events(patient_id: str, postop_day: int) -> list[dict]:
    """Sparse triage events — 1-3 events over recovery period."""
    events = []
    num_events = random.randint(1, 3)
    used_days = set()
    for _ in range(num_events):
        day = random.randint(1, max(1, postop_day))
        if day in used_days:
            continue
        used_days.add(day)
        level = random.choice(TRIAGE_LEVELS)
        event_date = date.today() - timedelta(days=(postop_day - day))
        events.append({
            "timestamp": f"{event_date}T{random.randint(8,20):02d}:{random.randint(0,59):02d}:00",
            "level": level,
            "symptom": random.choice(SYMPTOMS_BY_LEVEL[level]),
            "action": random.choice(ACTIONS_BY_LEVEL[level]),
        })
    return sorted(events, key=lambda e: e["timestamp"])


def generate_patient(idx: int) -> dict:
    """Generate one realistic ortho patient record."""
    gender = random.choice(["Male", "Female"])
    first_name = random.choice(FIRST_NAMES_M if gender == "Male" else FIRST_NAMES_F)
    last_name  = random.choice(LAST_NAMES)
    full_name  = f"{first_name} {last_name}"
    patient_id = f"PT-{1000 + idx}"

    surgery_type = random.choice(SURGERY_TYPES)
    affected_limb = random.choice(LIMBS[surgery_type])
    surgery_date = _rand_date_past(max_days=90)
    postop_day   = (date.today() - surgery_date).days

    meds_template = MEDICATIONS_BY_SURGERY.get(surgery_type, MEDICATIONS_BY_SURGERY["DEFAULT"])
    medications = []
    for m in meds_template:
        adherence = round(random.uniform(0.72, 1.0), 2)
        med = {"name": m["name"], "dose": m["dose"], "purpose": m["purpose"], "adherence_pct": adherence}
        if m["times"]:
            med["times"] = m["times"]
        medications.append(med)

    return {
        "patient_id": patient_id,
        "full_name":  full_name,
        "age":        random.randint(28, 84),
        "gender":     gender,
        "allergies":  random.choice(ALLERGIES_POOL),
        "surgery_type":          surgery_type,
        "affected_limb":         affected_limb,
        "surgery_date":          str(surgery_date),
        "postop_day":            postop_day,
        "surgeon":               random.choice(SURGEONS),
        "implant":               random.choice(IMPLANTS[surgery_type]),
        "weight_bearing_status": WEIGHT_BEARING[surgery_type],
        "current_medications":   medications,
        "metrics_history":       _build_metrics(surgery_date, postop_day, surgery_type),
        "triage_events":         _build_triage_events(patient_id, postop_day),
    }


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed orthopedic patient records into patients.sqlite3")
    parser.add_argument("--count", type=int, default=50, help="Number of patients to generate (default: 50)")
    parser.add_argument("--clear", action="store_true", help="Delete all existing patients before seeding")
    parser.add_argument("--db", type=str, default=None, help="Path to SQLite DB (default: backend/patients.sqlite3)")
    args = parser.parse_args()

    db_path = args.db

    if args.clear:
        import sqlite3, os
        db_file = db_path or db.database_path()
        if os.path.exists(db_file):
            conn = sqlite3.connect(db_file)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("DELETE FROM patients")
            conn.commit()
            conn.close()
            print(f"[CLEAR] Deleted all existing patient records from {db_file}")

    db.initialize_database(db_path)

    random.seed(42)
    print(f"[*] Generating {args.count} orthopedic patient records ...")
    seeded, skipped = 0, 0
    for i in range(args.count):
        patient = generate_patient(i)
        try:
            db.create_patient(patient, db_path)
            seeded += 1
            surgery_day = patient['postop_day']
            print(f"  [+] {patient['patient_id']} | {patient['full_name']:22s} | {patient['surgery_type']:45s} | Day {surgery_day:3d}")
        except Exception as e:
            skipped += 1
            print(f"  [SKIP] PT-{1000+i} already exists: {e}")

    print(f"\n[DONE] Seeded {seeded} patients ({skipped} skipped as duplicates)")
    print(f"       Database: {db.database_path(db_path)}")

    # Quick summary stats
    all_ids = db.list_patient_ids(db_path)
    print(f"       Total patients in DB: {len(all_ids)}")


if __name__ == "__main__":
    main()
