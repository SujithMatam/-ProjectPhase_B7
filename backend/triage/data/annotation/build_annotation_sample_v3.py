"""Blind items for an independent second annotation of challenge_v3 and the integration set.

All 91 challenge_v3 rows and all 272 integration-set rows, pooled, shuffled (seed 20261114) and
renamed C001..C363, so the annotator cannot tell which set a message comes from. The annotator
sees only v3/blind_items.tsv (opaque id + text) and LABELLING_GUIDELINE.md; v3/key.jsonl maps ids
back and holds the labels, sets and categories.

  python backend/triage/data/annotation/build_annotation_sample_v3.py
"""
from __future__ import annotations

import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent
OUT = HERE / "v3"
SEED = 20261114


def main() -> None:
    rows = [dict(json.loads(l), _set="challenge_v3") for l in open(DATA / "challenge_v3.jsonl", encoding="utf-8")]
    rows += [dict(json.loads(l), _set="integration") for l in open(DATA / "integration_set.jsonl", encoding="utf-8")]
    rng = random.Random(SEED)
    rng.shuffle(rows)
    OUT.mkdir(exist_ok=True)
    with open(OUT / "blind_items.tsv", "w", encoding="utf-8", newline="\n") as f:
        f.write("id\ttext\n")
        for n, r in enumerate(rows, 1):
            assert "\t" not in r["text"] and "\n" not in r["text"]
            f.write(f"C{n:03d}\t{r['text']}\n")
    with open(OUT / "key.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for n, r in enumerate(rows, 1):
            group = f"challenge_v3:{r['category']}" if r["_set"] == "challenge_v3" else "integration"
            f.write(json.dumps({"anon_id": f"C{n:03d}", "id": r["id"], "label": r["label"],
                                "set": r["_set"], "group": group}, ensure_ascii=False) + "\n")
    print(len(rows), "items")


if __name__ == "__main__":
    main()
