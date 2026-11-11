"""Choose the v2 model and its thresholds on VALIDATION data only -> artifacts/selection_v2.json.

Operating-point rule for t_red (new in v2; v1 used "highest t_red with classifier val RED recall
>= 0.95"):
  * val RED recall is measured for the **shipped pipeline** on val: a val row is called RED if an
    override (temperature >= 38.5 °C in the text, self-harm) fires or p(RED) >= t_red.
  * Over-triage = YELLOW->RED + GREEN->RED on val.
  * The shipped t_red is the one with the **lowest over-triage among thresholds with val RED
    recall >= 0.93** (ties: higher recall, then higher t_red). Because raising t_red never adds a
    RED call, this is the highest t_red that keeps val RED recall >= 0.93.
  * The operating-point table reports the highest t_red reaching val RED recall 0.90 / 0.93 / 0.95.
t_yel (t_red fixed): highest threshold with >= 90% of YELLOW val rows not called GREEN by the
pipeline (unchanged target). t_alert: unchanged rule (lowest p(RED) threshold with val RED
precision >= 0.90, choose_alert_threshold.py). Seed: best val macro F1 (argmax), as in v1.

The same rule is also applied to the v1 models (key "v1_under_v2_rule") so the effect of the data
and of the rule can be separated in REPORT.md; v1's shipped thresholds stay in selection.json.

  backend/.venv/Scripts/python backend/triage/model/select_v2.py
"""
from __future__ import annotations

import json
import math
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))
from choose_alert_threshold import choose_t_alert  # noqa: E402
from common import ART, CACHE, G, R, Y, SETFIT_SEEDS, labels_of, load_split, macro_f1  # noqa: E402
from triage.overrides import LEVEL_RANK, evaluate_overrides  # noqa: E402

TARGETS = (0.90, 0.93, 0.95)
SHIP_TARGET = 0.93
YELLOW_FOUND_TARGET = 0.90
IT = 3
_O = {"GREEN": G, "YELLOW": Y, "RED": R}


@lru_cache(maxsize=None)
def override_level(text: str) -> int:
    ov = evaluate_overrides(text)
    return _O[max((o.level for o in ov), key=LEVEL_RANK.get)] if ov else G


def val_arrays(split: str, npz: str):
    d = np.load(CACHE / "preds" / npz, allow_pickle=True)
    rows = {r["id"]: r for r in load_split(split, "val")}
    vr = [rows[str(i)] for i in d["val_ids"]]
    return d["val_p"], labels_of(vr), np.array([override_level(r["text"]) for r in vr])


def point(p, y, ov, t_red) -> dict:
    red = (ov == R) | (p[:, R] >= t_red)
    n_red = int((y == R).sum())
    return {"t_red": float(t_red),
            "val_red_recall": float((red & (y == R)).sum() / n_red),
            "val_red_recall_classifier_only": float(((p[:, R] >= t_red) & (y == R)).sum() / n_red),
            "val_yellow_to_red": int((red & (y == Y)).sum()),
            "val_green_to_red": int((red & (y == G)).sum()),
            "val_red_calls": int(red.sum()), "val_n": int(len(y)),
            "val_n_yellow": int((y == Y).sum()), "val_n_green": int((y == G).sum())}


def operating_points(p, y, ov) -> dict:
    cands = [point(p, y, ov, t) for t in np.unique(p[:, R])[::-1]]       # descending t_red
    table = {}
    for tgt in TARGETS:
        table[f"{tgt:.2f}"] = next(c for c in cands if c["val_red_recall"] >= tgt - 1e-12)
    ok = [c for c in cands if c["val_red_recall"] >= SHIP_TARGET - 1e-12]
    ship = min(ok, key=lambda c: (c["val_yellow_to_red"] + c["val_green_to_red"],
                                  -c["val_red_recall"], -c["t_red"]))
    return {"table": table, "shipped": ship}


def choose_t_yel(p, y, ov, t_red) -> dict:
    yel = y == Y
    caught = yel & ((ov >= Y) | (p[:, R] >= t_red))
    s = np.sort((p[:, R] + p[:, Y])[yel & ~caught])[::-1]
    need = math.ceil(YELLOW_FOUND_TARGET * yel.sum()) - int(caught.sum())
    t_yel = 1.0 if need <= 0 else float(s[need - 1])
    clf = np.where(p[:, R] >= t_red, R, np.where(p[:, R] + p[:, Y] >= t_yel, Y, G))
    level = np.maximum(clf, ov)
    return {"t_yel": t_yel, "val_yellow_found": float((level[yel] >= Y).mean()),
            "val_macro_f1_pipeline": macro_f1(y, level)}


def choose_all(split: str, npz: str) -> dict:
    p, y, ov = val_arrays(split, npz)
    op = operating_points(p, y, ov)
    t_red = op["shipped"]["t_red"]
    out = {"t_red": t_red, **{k: v for k, v in op["shipped"].items() if k != "t_red"},
           **choose_t_yel(p, y, ov, t_red), **choose_t_alert(p[:, R], y),
           "val_macro_f1": macro_f1(y, p.argmax(1)), "operating_points": op["table"],
           "preds": npz}
    return out


def main() -> None:
    sel = {"note": "every choice here uses validation data only (select_v2.py)",
           "data": "v2 = frozen train + data/train_v2_extra.jsonl (generated_v2), TRAIN only",
           "t_red_rule": (f"lowest val over-triage (YELLOW->RED + GREEN->RED) among t_red with "
                          f"val RED recall >= {SHIP_TARGET}, recall measured for the pipeline "
                          f"(overrides + classifier) on val"),
           "t_yel_rule": "highest t_yel with >= 90% of YELLOW val rows not called GREEN by the pipeline",
           "t_alert_rule": "lowest p(RED) threshold with val RED precision >= 0.90",
           "splits": {}, "v1_under_v2_rule": {}}
    v1 = json.loads((ART / "selection.json").read_text(encoding="utf-8"))["splits"]
    for split in ("main", "unseen"):
        s = {"M1": {**choose_all(split, f"m1_{split}_v2.npz"),
                    "head_file": f"m1_{split}_v2.json"}}
        s["M1"]["C"] = json.loads((ART / f"m1_{split}_v2.json").read_text(encoding="utf-8"))["C"]
        seeds = {sd: choose_all(split, f"m2_{split}_v2_it{IT}_seed{sd}.npz")
                 for sd in SETFIT_SEEDS[split]}
        best = max(seeds, key=lambda k: (seeds[k]["val_macro_f1"], -k))
        s["M2"] = {"num_iterations": IT, "seeds": {str(k): v for k, v in seeds.items()},
                   "best_seed": best, "weights_dir": f"m2_{split}_v2_it{IT}_seed{best}",
                   "val_macro_f1_mean": float(np.mean([v["val_macro_f1"] for v in seeds.values()]))}
        s["best_model"] = "M2" if s["M2"]["val_macro_f1_mean"] > s["M1"]["val_macro_f1"] else "M1"
        sel["splits"][split] = s
        v1seed = v1[split]["M2"]["best_seed"]
        sel["v1_under_v2_rule"][split] = {
            "M2_seed": v1seed,
            "M2": choose_all(split, f"m2_{split}_it{IT}_seed{v1seed}.npz"),
            "M1": choose_all(split, f"m1_{split}.npz")}
        b = s["M2"]["seeds"][str(best)]
        print(f"{split}: M1 {s['M1']['val_macro_f1']:.3f} M2 mean {s['M2']['val_macro_f1_mean']:.3f} "
              f"-> {s['best_model']}, seed {best}: t_red {b['t_red']:.3f} t_yel {b['t_yel']:.3f} "
              f"t_alert {b['t_alert']:.3f} val recall {b['val_red_recall']:.3f} "
              f"Y->R {b['val_yellow_to_red']} G->R {b['val_green_to_red']}")
    (ART / "selection_v2.json").write_text(json.dumps(sel, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
