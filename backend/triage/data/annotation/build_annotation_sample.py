"""Blind sample for an independent second annotation.

300 rows from splits/ (100 per label, every scenario represented) + all 150 challenge rows,
shuffled together and given opaque ids (T001...). The annotator sees only blind_items.tsv
(id, text) and LABELLING_GUIDELINE.md; key.jsonl maps the opaque ids back.

  python backend/triage/data/annotation/build_annotation_sample.py
"""
from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent
SEED = 20261111
PER_LABEL = 100
LABELS = ("RED", "YELLOW", "GREEN")


def main() -> None:
    rows = [json.loads(l) for s in ("train", "val", "test")
            for l in open(DATA / "splits" / f"{s}.jsonl", encoding="utf-8")]
    rows.sort(key=lambda r: r["id"])
    challenge = [json.loads(l) for l in open(DATA / "challenge.jsonl", encoding="utf-8")]
    rng = random.Random(SEED)

    by_scen = defaultdict(list)
    for r in rows:
        by_scen[r["scenario_id"]].append(r)
    picked = {}
    for s in sorted(by_scen):                       # one row per scenario first
        r = rng.choice(by_scen[s])
        picked[r["id"]] = r
    for lab in LABELS:                              # then fill each label to 100
        pool = [r for r in rows if r["label"] == lab and r["id"] not in picked]
        need = PER_LABEL - sum(r["label"] == lab for r in picked.values())
        for r in rng.sample(pool, need):
            picked[r["id"]] = r

    items = [{"id": r["id"], "text": r["text"], "label": r["label"], "set": "split",
              "split": r["split"], "group": r["scenario_id"]} for r in picked.values()]
    items += [{"id": r["id"], "text": r["text"], "label": r["label"], "set": "challenge",
               "split": "challenge", "group": r["category"]} for r in challenge]
    items.sort(key=lambda x: x["id"])
    rng.shuffle(items)
    for n, it in enumerate(items, 1):
        it["anon_id"] = f"T{n:03d}"

    with open(HERE / "blind_items.tsv", "w", encoding="utf-8", newline="\n") as f:
        f.write("id\ttext\n")
        for it in items:
            assert "\t" not in it["text"] and "\n" not in it["text"]
            f.write(f"{it['anon_id']}\t{it['text']}\n")
    with open(HERE / "key.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for it in items:
            f.write(json.dumps({k: it[k] for k in ("anon_id", "id", "label", "set", "split", "group")},
                               ensure_ascii=False) + "\n")
    sp = [i for i in items if i["set"] == "split"]
    print(len(items), "items;", {l: sum(i["label"] == l for i in sp) for l in LABELS},
          "scenarios", len({i["group"] for i in sp}),
          "splits", {s: sum(i["split"] == s for i in sp) for s in ("train", "val", "test")})


if __name__ == "__main__":
    main()
