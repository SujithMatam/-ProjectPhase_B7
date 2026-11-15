import sys
sys.path.insert(0, "backend")
import patient_database as db

# Check one TKA patient and one ACL patient
for pid in ["PT-1005", "PT-1009", "PT-1010"]:
    p = db.get_patient(pid)
    if not p:
        print(f"{pid}: not found")
        continue
    print(f"\n{pid} | {p['full_name']} | {p['surgery_type']} | Post-op Day {p['postop_day']}")
    print(f"  Scans: {len(p.get('scans', []))}")
    for s in p.get("scans", []):
        print(f"    [{s['scan_type']}] {s['body_part']} ({s['laterality']}) "
              f"| Date: {s['scan_date']} | KL={s['kl_grade']} | Source: {s['source_dataset']}")
        print(f"      Findings: {s['findings'][:80]}...")
        print(f"      File: {s['file_path']}")

# Total scan count
import sqlite3
conn = sqlite3.connect("backend/patients.sqlite3")
total = conn.execute("SELECT COUNT(*) FROM patient_scans").fetchone()[0]
by_type = conn.execute("SELECT scan_type, COUNT(*) FROM patient_scans GROUP BY scan_type").fetchall()
by_part = conn.execute("SELECT body_part, COUNT(*) FROM patient_scans GROUP BY body_part").fetchall()
conn.close()
print(f"\n=== DB Summary ===")
print(f"Total scan records: {total}")
print(f"By type: {dict(by_type)}")
print(f"By body part: {dict(by_part)}")
