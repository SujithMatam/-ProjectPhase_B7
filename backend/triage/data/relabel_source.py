"""Re-label every distinct source sentence against LABELLING_GUIDELINE.md.

Outputs (next to this file):
  source_relabelled.jsonl  one row per distinct normalised sentence, with the
                           new label, scenario_id and a surgery that fits the text
  RELABEL_CHANGES.md       the change table plus the full per-sentence table

Run:  python backend/triage/data/relabel_source.py
"""
from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

from audit_source import load, normalise

HERE = Path(__file__).resolve().parent

# (sentence prefix, new label, scenario_id, surgery, reason if changed / note)
# surgery: TKA / THA when the wording fixes it, ANY when it fits both.
DECISIONS = [
    ("My {limb} calf is noticeably swollen", "RED", "DVT_CALF", "ANY", ""),
    ("I have a deep ache in my {limb} calf", "RED", "DVT_CALF", "ANY", ""),
    ("My {limb} calf hurts terribly whenever I stand", "RED", "DVT_CALF", "ANY", ""),
    ("I am suddenly having severe shortness of breath", "RED", "PE_CHEST", "ANY", ""),
    ("Feeling very faint and can't catch my breath", "RED", "PE_CHEST", "ANY", ""),
    ("I just coughed up a small amount of blood", "RED", "PE_CHEST", "ANY", ""),
    ("My {limb} toes have turned pale and cold", "RED", "NEUROVASCULAR", "ANY", ""),
    ("My foot feels completely dead and freezing", "RED", "NEUROVASCULAR", "ANY", ""),
    ("Total numbness in my entire {limb} foot", "RED", "NEUROVASCULAR", "ANY", ""),
    ("My wound has gaped open and there is heavy green", "RED", "SEPSIS_WOUND", "ANY", ""),
    ("Thick yellow and foul-smelling pus", "RED", "SEPSIS_WOUND", "ANY", ""),
    ("The redness around the surgical cut has spread", "RED", "SEPSIS_WOUND", "ANY", ""),
    ("I noticed black tarry stools", "RED", "BLEEDING_ANTICOAG", "ANY", ""),
    ("There is bright red blood in my urine", "RED", "BLEEDING_ANTICOAG", "ANY", ""),
    ("I have bleeding from my gums that won't stop", "RED", "BLEEDING_ANTICOAG", "ANY", ""),
    ("Extreme unrelenting pain in my operated leg", "RED", "COMPARTMENT", "ANY", ""),
    ("My shin feels rock hard and burning", "RED", "COMPARTMENT", "ANY", ""),
    ("The pain in my {limb} lower leg is unbearable", "RED", "COMPARTMENT", "ANY", ""),
    ("I felt a loud pop in my {limb} hip", "RED", "DISLOCATION", "THA", ""),
    ("Sudden violent popping sensation in my replaced hip", "RED", "DISLOCATION", "THA", ""),
    ("Heard a click and sudden inability to move my operated hip", "RED", "DISLOCATION", "THA", ""),
    ("My bandage is damp with pale watery discharge", "YELLOW", "CLEAR_DRAINAGE", "ANY", ""),
    ("I noticed some clear pinkish fluid leaking", "YELLOW", "CLEAR_DRAINAGE", "ANY", ""),
    ("There is a small amount of serosanguinous fluid", "YELLOW", "CLEAR_DRAINAGE", "ANY", ""),
    ("Feeling a little flushed and feverish", "YELLOW", "LOW_FEVER", "ANY", ""),
    ("I checked my temperature and it is 37.9", "YELLOW", "LOW_FEVER", "ANY", ""),
    ("Is a low fever normal a few days", "GREEN", "LOW_FEVER", "ANY",
     "General question; the patient does not report having a fever (rules 1-2)."),
    ("I have not had a bowel movement in 4 days", "YELLOW", "CONSTIPATION", "ANY", ""),
    ("Is it normal to go several days without passing stool", "GREEN", "CONSTIPATION", "ANY",
     "General question; no symptom reported (rule 2)."),
    ("The pain medication is making me extremely nauseous", "YELLOW", "MED_SIDE_EFFECT", "ANY", ""),
    ("A couple of my staples are pulling tight", "YELLOW", "WOUND_IRRITATION", "ANY", ""),
    ("One corner of the incision looks slightly puckered", "YELLOW", "WOUND_IRRITATION", "ANY", ""),
    ("When will my surgical clips or stitches be removed", "GREEN", "FOLLOWUP_ADMIN", "ANY",
     "Scheduling question; no symptom reported (rule 2)."),
    ("I hear a clicking or tapping noise inside my new knee", "GREEN", "IMPLANT_NOISE", "TKA",
     "Painless clicking with no instability is expected (GREEN list); nothing else reported."),
    ("Feels like metal hitting plastic", "GREEN", "IMPLANT_NOISE", "ANY",
     "Painless implant noise with no instability is expected (GREEN list)."),
    ("My artificial joint makes a knocking sound", "YELLOW", "IMPLANT_NOISE", "ANY",
     "Kept YELLOW: patient raises looseness; torn between GREEN and YELLOW, so higher (rule 6)."),
    ("I forgot my blood thinner dose", "YELLOW", "MISSED_DOSE", "ANY",
     "Reports a missed blood-thinner dose, which the guideline lists as YELLOW (needs pharmacist/team advice)."),
    ("Can I take paracetamol and ibuprofen together", "GREEN", "MED_TIMING", "TKA", ""),
    ("When should I take my pain medicine before", "GREEN", "MED_TIMING", "ANY", ""),
    ("My physical therapist gave me heel slide", "GREEN", "REHAB_EXERCISE", "TKA", ""),
    ("How many degrees should I be able to bend", "GREEN", "REHAB_EXERCISE", "TKA", ""),
    ("Can I bend forward to pick up my dropped phone", "GREEN", "HIP_PRECAUTIONS", "THA", ""),
    ("Can I cross my ankles while sitting", "GREEN", "HIP_PRECAUTIONS", "THA", ""),
    ("What is the correct way to sleep so I don't dislocate", "GREEN", "HIP_PRECAUTIONS", "THA", ""),
    ("My ankle and foot get swollen towards the afternoon", "GREEN", "NORMAL_SWELLING", "ANY", ""),
    ("How long should I keep ice packs on my knee", "GREEN", "NORMAL_SWELLING", "TKA", ""),
    ("What is the best way to elevate my operated leg", "GREEN", "NORMAL_SWELLING", "ANY", ""),
    ("Can I sleep on my stomach or side tonight", "GREEN", "DAILY_ACTIVITY", "ANY", ""),
    ("When is it safe for me to take a regular shower", "GREEN", "DAILY_ACTIVITY", "ANY", ""),
    ("When am I allowed to drive my car again", "GREEN", "DAILY_ACTIVITY", "ANY", ""),
    ("Should I take protein shakes", "GREEN", "NUTRITION", "ANY", ""),
    ("How much water should I drink each day", "GREEN", "NUTRITION", "ANY", ""),
    ("What foods should I eat to help my bone", "GREEN", "NUTRITION", "ANY", ""),
    ("I feel really frustrated and tearful", "GREEN", "MOOD_SLEEP", "ANY", ""),
    ("Is it normal to feel down and anxious", "GREEN", "MOOD_SLEEP", "ANY", ""),
    ("Having trouble sleeping through the night", "GREEN", "MOOD_SLEEP", "ANY", ""),
    ("How do I use a walking stick on the stairs after knee", "GREEN", "WALKING_AIDS", "TKA", ""),
    ("My discharge says WBAT", "GREEN", "WALKING_AIDS", "ANY", ""),
    ("Is it okay to put all my weight on my operated leg", "GREEN", "WALKING_AIDS", "ANY", ""),
    ("When can I transition from a walker", "GREEN", "WALKING_AIDS", "ANY", ""),
    ("Is knee tightness normal on Post-Op", "GREEN", "STIFFNESS", "TKA", ""),
    ("My knee feels tight like a rubber band", "GREEN", "STIFFNESS", "TKA", ""),
    ("How long does the morning stiffness usually last", "GREEN", "STIFFNESS", "TKA", ""),
]


def main() -> None:
    rng = random.Random(7)
    data = load()
    first: dict[str, dict] = {}
    for s in ("train", "val", "test"):
        for r in data[s]:
            first.setdefault(normalise(r["user_message"]), r)

    out_rows, table, changes = [], [], []
    used = set()
    for norm, r in first.items():
        hits = [d for d in DECISIONS if norm.startswith(d[0])]
        if len(hits) != 1:
            raise SystemExit(f"no unique decision for: {norm!r} ({len(hits)} hits)")
        prefix, new, scen, surg, reason = hits[0]
        used.add(prefix)
        old = r["expected_triage"]
        surgery = surg if surg != "ANY" else rng.choice(["TKA", "THA"])
        text = (norm.replace("{limb}", rng.choice(["Left", "Right"]))
                    .replace("{day}", str(rng.randint(2, 6))))
        out_rows.append({
            "text": text,
            "label": new,
            "old_label": old,
            "scenario_id": scen,
            "surgery": surgery,
            "origin": "source_template",
            "source_template": norm,
            "generator": "backend/data/dataset_builder.py (relabelled by claude-opus-5-5)",
        })
        table.append((norm, old, new, scen, surg, reason))
        if old != new:
            changes.append((norm, old, new, reason))
    missing = [d[0] for d in DECISIONS if d[0] not in used]
    if missing:
        raise SystemExit(f"decisions never used: {missing}")

    with open(HERE / "source_relabelled.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for row in out_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    L = ["# Re-labelling of the source sentences\n",
         "Generated by `relabel_source.py`. Every distinct source sentence (after normalising "
         "`Left`/`Right` and day numbers) was re-labelled against `LABELLING_GUIDELINE.md`.\n",
         f"Distinct sentences: {len(table)}. Changed: **{len(changes)}**. "
         f"Old labels {dict(Counter(t[1] for t in table))}; new labels {dict(Counter(t[2] for t in table))}.\n",
         "## Changes\n", "| sentence | old | new | reason |", "|---|---|---|---|"]
    for norm, old, new, reason in changes:
        L.append(f"| {norm} | {old} | {new} | {reason} |")
    L += ["\n## All sentences\n",
          "Surgery column: the procedure the wording fits. The source attached a random procedure "
          "to each row (see AUDIT.md section 3); the new rows use this column instead, and `ANY` "
          "sentences get TKA or THA at random.\n",
          "| sentence | old | new | scenario_id | surgery | note |", "|---|---|---|---|---|---|"]
    for norm, old, new, scen, surg, reason in sorted(table, key=lambda t: (t[3], t[0])):
        mark = f"**{new}**" if old != new else new
        L.append(f"| {norm} | {old} | {mark} | {scen} | {surg} | {reason} |")
    (HERE / "RELABEL_CHANGES.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:12 + len(changes)]))


if __name__ == "__main__":
    main()
