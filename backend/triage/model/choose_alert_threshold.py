"""Choose the doctor-alert threshold t_alert on VALIDATION data only and store it in selection.json.

t_alert is the LOWEST threshold t for which the val rows with p(RED) >= t have RED precision
>= 0.90 (at least one such row). The candidates are the distinct val p(RED) values. The
doctor-alert email fires for an override RED or p(RED) >= t_alert; a classifier RED with
t_red <= p(RED) < t_alert still gets the RED patient advice but no email
(classifier_triage.py, "alert_suppressed_low_confidence").

Reads val probabilities from artifacts/cache/preds/ (written by train.py from the saved model).
Writes, per model, {"t_alert", "t_alert_val_precision", "t_alert_val_red_recall",
"t_alert_val_n_flagged"} next to t_red / t_yel in selection.json:
  main   M1, M2 (shipped seed)      -> used by classifier_triage.py
  unseen M1, M2 (shipped seed)      -> used only by evaluate_shipped.py for the unseen-scenario test

  backend/.venv/Scripts/python backend/triage/model/choose_alert_threshold.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import ART, CACHE, R, labels_of, load_split  # noqa: E402

PRECISION_TARGET = 0.90


def choose_t_alert(p_red: np.ndarray, y: np.ndarray, target: float = PRECISION_TARGET) -> dict:
    is_red = y == R
    for t in np.unique(p_red):                       # ascending
        flagged = p_red >= t
        prec = float(is_red[flagged].mean())
        if prec >= target:
            return {"t_alert": float(t), "t_alert_val_precision": prec,
                    "t_alert_val_red_recall": float((flagged & is_red).sum() / is_red.sum()),
                    "t_alert_val_n_flagged": int(flagged.sum())}
    raise RuntimeError("no threshold reaches the precision target on val")


def _val(split: str, pred_file: str):
    d = np.load(CACHE / "preds" / pred_file, allow_pickle=True)
    rows = {r["id"]: r for r in load_split(split, "val")}
    ids = [str(i) for i in d["val_ids"]]
    y = labels_of([rows[i] for i in ids])
    return d["val_p"][:, R], y


def main() -> None:
    path = ART / "selection.json"
    sel = json.loads(path.read_text(encoding="utf-8"))
    for split in ("main", "unseen"):
        s = sel["splits"][split]
        p, y = _val(split, f"m1_{split}.npz")
        s["M1"].update(choose_t_alert(p, y))
        seed, it = s["M2"]["best_seed"], s["M2"]["num_iterations"]
        p, y = _val(split, f"m2_{split}_it{it}_seed{seed}.npz")
        s["M2"]["seeds"][str(seed)].update(choose_t_alert(p, y))
        print(split, "M1", {k: round(v, 4) for k, v in s["M1"].items() if k.startswith("t_")},
              "| M2 seed", seed,
              {k: round(v, 4) for k, v in s["M2"]["seeds"][str(seed)].items() if k.startswith("t_")})
    sel["t_alert_rule"] = (f"lowest threshold on val p(RED) with val RED precision >= "
                           f"{PRECISION_TARGET} (model/choose_alert_threshold.py); doctor email "
                           f"fires for an override RED or p(RED) >= t_alert")
    path.write_text(json.dumps(sel, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
