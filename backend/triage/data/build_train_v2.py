"""Build the v2 training-only rows: authored_v2/*.tsv -> train_v2_extra.jsonl + TRAIN_V2_REPORT.md.

The rows are added to TRAIN only (model/common.py ``load_train(split, "v2")``); val, test,
challenge and challenge_v2 are untouched. A row is dropped if it
  * is an exact (normalised) duplicate of another v2 row or of any existing row,
  * has MiniLM cosine > 0.92 with any row of main val, main test, challenge or challenge_v2,
  * has cosine > 0.92 with one of the two routine messages in test_multi_agent_orchestration.py
    (so that test is not trained on), or
  * is labelled below the temperature stated in its text (label error).
``unseen_split_ok`` marks rows that may also be added to the unseen-scenario split's train: none
of their topics is an unseen val/test scenario and no cosine > 0.92 with an unseen val/test row.

  cd backend/triage/data && HF_HUB_OFFLINE=1 ../../.venv/Scripts/python build_train_v2.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np

from build_dataset import (EMBED_MODEL, NEAR_DUP, RANK, SPLITS, embed, norm_text, temp_floor,
                           temperatures_c)

HERE = Path(__file__).resolve().parent
SRC = HERE / "authored_v2"
CATEGORIES = ("negation", "wound_minimal_pair", "routine_multi_topic")
SCENARIOS = {
    "DVT_CALF", "PE_CHEST", "NEUROVASCULAR", "COMPARTMENT", "DISLOCATION", "FALL_INJURY",
    "SEPSIS_WOUND", "WOUND_OPEN", "HIGH_FEVER", "ALLERGIC_REACTION", "BLEEDING_ANTICOAG",
    "CLEAR_DRAINAGE", "CONSTIPATION", "IMPLANT_NOISE", "LOW_FEVER", "MED_SIDE_EFFECT",
    "MINOR_BLEEDING", "MISSED_DOSE", "UNCONTROLLED_PAIN", "WOUND_IRRITATION", "WOUND_REDNESS",
    "DAILY_ACTIVITY", "FOLLOWUP_ADMIN", "HIP_PRECAUTIONS", "MED_TIMING", "MOOD_SLEEP",
    "NORMAL_SWELLING", "NUTRITION", "REHAB_EXERCISE", "STIFFNESS", "WALKING_AIDS"}
# Rows removed on review of the writers' labels (text -> reason). Kept out of training rather
# than relabelled, so no label here is the reviewer's guess.
REVIEW_DROPS = {
    "the wet ring on my hip dressing has spread to the edges and it's leaking out of the sides now":
        "ambiguous: fluid type not stated, between YELLOW 'spreading ooze' and RED 'dressing "
        "soaked through' (guideline v1.1)",
}
ORCHESTRATION_MESSAGES = [   # backend/test_multi_agent_orchestration.py, must stay unseen
    "Since I didn't take my medicine yesterday, my knee wound is worse",
    "I am anxious, my knee hurts, and I need help with exercises",
]


def jl(path: Path) -> list[dict]:
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def read_authored() -> list[dict]:
    rows = []
    for cat in CATEGORIES:
        n = 0
        for ln, line in enumerate((SRC / f"{cat}.tsv").read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split("\t")
            assert len(parts) == 5, (cat, ln, line)
            label, surgery, tags, scen, text = (p.strip() for p in parts)
            assert label in RANK, (cat, ln, label)
            assert surgery in ("TKA", "THA", "ANY"), (cat, ln, surgery)
            scenarios = [s.strip() for s in scen.split(",") if s.strip() and s.strip() != "-"]
            bad = [s for s in scenarios if s not in SCENARIOS]
            assert not bad, (cat, ln, bad)
            n += 1
            if surgery == "ANY":
                import random
                surgery = random.Random("surgery:" + text).choice(["TKA", "THA"])
            rows.append({"id": f"V2-{cat.upper()}-{n:03d}", "text": text, "label": label,
                         "category": cat, "scenario_id": None, "scenarios": scenarios,
                         "surgery": surgery,
                         "tags": [t for t in tags.split(",") if t and t != "-"],
                         "origin": "generated_v2", "generator": "claude-opus-5-5",
                         "split": "train"})
    return rows


def main() -> None:
    rows = read_authored()
    n_written = Counter(r["category"] for r in rows)
    lab_written = Counter(r["label"] for r in rows)

    main_rows = {s: jl(HERE / "splits" / f"{s}.jsonl") for s in SPLITS}
    ch = jl(HERE / "challenge.jsonl")
    ch2 = jl(HERE / "challenge_v2.jsonl")
    un_val = jl(HERE / "splits_unseen_scenario" / "val.jsonl")
    un_test = jl(HERE / "splits_unseen_scenario" / "test.jsonl")
    unseen_held_scen = {r["scenario_id"] for r in un_val + un_test}

    protected = ([dict(r, _src="val") for r in main_rows["val"]] +
                 [dict(r, _src="test") for r in main_rows["test"]] +
                 [dict(r, _src="challenge") for r in ch] +
                 [dict(r, _src="challenge_v2") for r in ch2])
    all_existing = main_rows["train"] + protected
    existing_norm = {norm_text(r["text"]) for r in all_existing}

    e_new = embed([r["text"] for r in rows])
    e_prot = embed([r["text"] for r in protected])
    e_train = embed([r["text"] for r in main_rows["train"]])
    e_orch = embed(ORCHESTRATION_MESSAGES)
    e_un = embed([r["text"] for r in un_val + un_test])
    s_prot = e_new @ e_prot.T
    s_train = (e_new @ e_train.T).max(1)
    s_orch = (e_new @ e_orch.T).max(1)
    s_un = (e_new @ e_un.T).max(1)

    dropped, kept, seen = [], [], set()
    for i, r in enumerate(rows):
        nt = norm_text(r["text"])
        j = int(s_prot[i].argmax())
        why = None
        if r["text"] in REVIEW_DROPS:
            why = "review: " + REVIEW_DROPS[r["text"]]
        elif nt in seen:
            why = "exact duplicate of another v2 row"
        elif nt in existing_norm:
            why = "exact duplicate of an existing row"
        elif s_prot[i, j] > NEAR_DUP:
            m = protected[j]
            why = f"cosine {s_prot[i, j]:.3f} with `{m['id']}` ({m['_src']}) \"{m['text']}\""
        elif s_orch[i] > NEAR_DUP:
            why = f"cosine {s_orch[i]:.3f} with an orchestration-test message"
        elif RANK[r["label"]] < RANK[temp_floor(temperatures_c(r["text"]))]:
            why = f"labelled {r['label']} below stated temperature {temperatures_c(r['text'])}"
        seen.add(nt)
        if why:
            dropped.append((r, why))
            continue
        r["unseen_split_ok"] = bool(not (set(r["scenarios"]) & unseen_held_scen)
                                    and s_un[i] <= NEAR_DUP)
        r["max_cos_protected"] = round(float(s_prot[i, j]), 3)
        r["max_cos_train"] = round(float(s_train[i]), 3)
        kept.append(r)

    with open(HERE / "train_v2_extra.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in kept:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    idx = {id(r): k for k, r in enumerate(rows)}
    kept_i = [idx[id(r)] for r in kept]
    within = e_new[kept_i] @ e_new[kept_i].T
    np.fill_diagonal(within, 0)
    rep = ["# Training data v2 report\n",
           "Generated by `build_train_v2.py`. Rows in `train_v2_extra.jsonl` (origin "
           "`generated_v2`) are added to **train only**. They were written after `challenge_v2.jsonl` "
           "was committed (f340dc1), by three claude-opus-5-5 writers that were given only "
           "`LABELLING_GUIDELINE.md` v1.1 and `authored/README.md` and told not to open any "
           "challenge, split, report or test file.\n",
           "| category | written | kept | RED | YELLOW | GREEN | unseen_split_ok |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for c in CATEGORIES:
        k = [r for r in kept if r["category"] == c]
        cc = Counter(r["label"] for r in k)
        rep.append(f"| {c} | {n_written[c]} | {len(k)} | {cc['RED']} | {cc['YELLOW']} | "
                   f"{cc['GREEN']} | {sum(r['unseen_split_ok'] for r in k)} |")
    cc = Counter(r["label"] for r in kept)
    rep.append(f"| **all** | **{len(rows)}** | **{len(kept)}** | **{cc['RED']}** | "
               f"**{cc['YELLOW']}** | **{cc['GREEN']}** | "
               f"**{sum(r['unseen_split_ok'] for r in kept)}** |\n")
    rep.append(f"Labels as written: RED {lab_written['RED']}, YELLOW {lab_written['YELLOW']}, "
               f"GREEN {lab_written['GREEN']}.\n")
    rep.append(f"**Dropped: {len(dropped)}** (near-duplicate threshold: {EMBED_MODEL} cosine > {NEAR_DUP}).")
    for r, why in dropped:
        rep.append(f"- `{r['id']}` ({r['label']}) \"{r['text']}\": {why}")
    rep.append("")
    mp = max(r["max_cos_protected"] for r in kept)
    rep.append(f"Kept rows vs main val + main test + challenge + challenge_v2: highest cosine "
               f"**{mp:.3f}** (all <= {NEAR_DUP}); median closest "
               f"{float(np.median([r['max_cos_protected'] for r in kept])):.3f}.")
    rep.append(f"Kept rows vs the two orchestration-test messages: highest cosine "
               f"{float(s_orch[kept_i].max()):.3f}.")
    rep.append(f"Kept rows vs main train (allowed, for information): "
               f"{sum(r['max_cos_train'] > NEAR_DUP for r in kept)} above {NEAR_DUP}; median closest "
               f"{float(np.median([r['max_cos_train'] for r in kept])):.3f}.")
    rep.append(f"Pairs of kept v2 rows above {NEAR_DUP} (minimal pairs are meant to be close): "
               f"{int((within > NEAR_DUP).sum() // 2)}; highest {float(within.max()):.3f}.")
    rep.append(f"\n`unseen_split_ok`: no topic among the unseen-scenario val/test scenarios "
               f"({', '.join(sorted(unseen_held_scen))}) and cosine <= {NEAR_DUP} with every unseen "
               f"val/test row. Only these rows are added to `splits_unseen_scenario/train` for the v2 "
               f"unseen-scenario model.")
    (HERE / "TRAIN_V2_REPORT.md").write_text("\n".join(rep) + "\n", encoding="utf-8")
    print("\n".join(rep))


if __name__ == "__main__":
    main()
