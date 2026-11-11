"""Blind sample of challenge_v2 for an independent second annotation (same method as v1).

All 90 challenge_v2 rows, shuffled (seed 20261112) and renamed B01..B90. The annotator sees only
v2/blind_items.tsv (opaque id + text) and LABELLING_GUIDELINE.md; v2/key.jsonl maps ids back and
holds the labels and categories.

  python backend/triage/data/annotation/build_annotation_sample_v2.py
"""
from __future__ import annotations

import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent
OUT = HERE / "v2"
SEED = 20261112


def main() -> None:
    rows = [json.loads(l) for l in open(DATA / "challenge_v2.jsonl", encoding="utf-8")]
    rng = random.Random(SEED)
    rng.shuffle(rows)
    OUT.mkdir(exist_ok=True)
    with open(OUT / "blind_items.tsv", "w", encoding="utf-8", newline="\n") as f:
        f.write("id\ttext\n")
        for n, r in enumerate(rows, 1):
            assert "\t" not in r["text"] and "\n" not in r["text"]
            f.write(f"B{n:02d}\t{r['text']}\n")
    with open(OUT / "key.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for n, r in enumerate(rows, 1):
            f.write(json.dumps({"anon_id": f"B{n:02d}", "id": r["id"], "label": r["label"],
                                "set": "challenge_v2", "split": "challenge_v2",
                                "group": r["category"]}, ensure_ascii=False) + "\n")
    print(len(rows), "items")


if __name__ == "__main__":
    main()
