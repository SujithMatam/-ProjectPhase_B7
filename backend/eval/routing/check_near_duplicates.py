"""
Near-duplicate guard for routing sentences.

    .venv/Scripts/python.exe eval/routing/check_near_duplicates.py heldout
        every heldout_v2 sentence vs every case in cases.py

    .venv/Scripts/python.exe eval/routing/check_near_duplicates.py heldout --set heldout_v3
        every heldout_v3 sentence vs every case in cases.py AND heldout_v2.py

    .venv/Scripts/python.exe eval/routing/check_near_duplicates.py prototypes "sentence one" "sentence two" ...
        candidate prototype sentences vs every case in cases.py, heldout_v2.py
        AND heldout_v3.py

Cosine similarity with all-MiniLM-L6-v2 (normalised embeddings), the same
model the intent classifier uses.  Exit code 1 when any pair is above the
threshold (default 0.85, --threshold to change).  The nearest neighbour of
every checked sentence is printed so the margin to the threshold is visible.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def nearest(candidates, pool, model):
    """For each candidate text: (best cosine, id, text) over the pool."""
    cand_emb = model.encode([c for c in candidates], normalize_embeddings=True, convert_to_numpy=True)
    pool_emb = model.encode([p["text"] for p in pool], normalize_embeddings=True, convert_to_numpy=True)
    sims = cand_emb @ pool_emb.T
    out = []
    for i, text in enumerate(candidates):
        j = int(sims[i].argmax())
        out.append((float(sims[i][j]), pool[j]["id"], pool[j]["text"], text))
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=("heldout", "prototypes"))
    parser.add_argument("sentences", nargs="*")
    parser.add_argument("--threshold", type=float, default=0.85)
    parser.add_argument("--set", default="heldout_v2", choices=("heldout_v2", "heldout_v3"),
                        help="heldout mode only: which held-out set to check (default heldout_v2)")
    args = parser.parse_args(argv)

    from sentence_transformers import SentenceTransformer
    from cases import CASES
    import heldout_v2
    import heldout_v3

    model = SentenceTransformer(MODEL_NAME)
    if args.mode == "heldout":
        held = heldout_v2 if args.set == "heldout_v2" else heldout_v3
        texts = [c["text"] for c in held.CASES]
        labels = [c["id"] for c in held.CASES]
        # Each held-out set is checked against every set written before it.
        pool = list(CASES) if args.set == "heldout_v2" else list(CASES) + list(heldout_v2.CASES)
    else:
        if not args.sentences:
            parser.error("give at least one candidate sentence")
        texts = list(args.sentences)
        labels = [f"P{i + 1}" for i in range(len(texts))]
        pool = list(CASES) + list(heldout_v2.CASES) + list(heldout_v3.CASES)

    rows = nearest(texts, pool, model)
    worst = 0.0
    bad = 0
    print(f"| Sentence | Nearest case | Cosine |")
    print(f"|---|---|---|")
    for label, (score, cid, ctext, text) in zip(labels, rows):
        flag = " **> threshold**" if score > args.threshold else ""
        print(f"| {label} \"{text}\" | {cid} \"{ctext}\" | {score:.3f}{flag} |")
        worst = max(worst, score)
        bad += score > args.threshold
    print()
    print(f"pool={len(pool)} checked={len(texts)} max_cosine={worst:.3f} threshold={args.threshold} above={bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
