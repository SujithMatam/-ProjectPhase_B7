"""Choose the v3 seed and thresholds on VALIDATION data only -> artifacts/selection_v3.json.

Rules (stated in REPORT.md "v3", committed before any v3 training run):
  * t_red per seed: the v2 rule (select_v2.py): lowest val over-triage (YELLOW->RED + GREEN->RED)
    among thresholds with pipeline val RED recall >= 0.93 (overrides + classifier on val).
  * t_yel and t_alert per seed: their v2 rules.
  * Shipped seed: the lowest val over-triage at its own operating point; ties -> higher val RED
    recall, then higher val macro F1 (argmax), then the lower seed number. (v2 picked the seed by
    val macro F1; the seed that rule would pick is recorded for information.)
The same is done for the unseen-scenario split (3 seeds), used only for the unseen-scenario test.

  backend/.venv/Scripts/python backend/triage/model/select_v3.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))
from common import ART, SETFIT_SEEDS  # noqa: E402
from select_v2 import IT, SHIP_TARGET, choose_all  # noqa: E402


def over(d: dict) -> int:
    return d["val_yellow_to_red"] + d["val_green_to_red"]


def main() -> None:
    sel = {"note": "every choice here uses validation data only (select_v3.py)",
           "data": ("v3 = frozen train + data/train_v2_extra.jsonl (generated_v2) + "
                    "data/train_v3_extra.jsonl (generated_v3), TRAIN only"),
           "t_red_rule": (f"lowest val over-triage (YELLOW->RED + GREEN->RED) among t_red with "
                          f"val RED recall >= {SHIP_TARGET}, recall measured for the pipeline "
                          f"(overrides + classifier) on val"),
           "t_yel_rule": "highest t_yel with >= 90% of YELLOW val rows not called GREEN by the pipeline",
           "t_alert_rule": "lowest p(RED) threshold with val RED precision >= 0.90",
           "seed_rule": ("lowest val over-triage at the seed's own operating point; ties: higher val "
                         "RED recall, higher val macro F1 (argmax), lower seed"),
           "splits": {}}
    for split in ("main", "unseen"):
        s = {"M1": {**choose_all(split, f"m1_{split}_v3.npz"), "head_file": f"m1_{split}_v3.json"}}
        s["M1"]["C"] = json.loads((ART / f"m1_{split}_v3.json").read_text(encoding="utf-8"))["C"]
        seeds = {sd: choose_all(split, f"m2_{split}_v3_it{IT}_seed{sd}.npz") for sd in SETFIT_SEEDS[split]}
        best = min(seeds, key=lambda k: (over(seeds[k]), -seeds[k]["val_red_recall"],
                                         -seeds[k]["val_macro_f1"], k))
        by_f1 = max(seeds, key=lambda k: (seeds[k]["val_macro_f1"], -k))
        s["M2"] = {"num_iterations": IT, "seeds": {str(k): v for k, v in seeds.items()},
                   "best_seed": best, "weights_dir": f"m2_{split}_v3_it{IT}_seed{best}",
                   "seed_by_v2_rule_val_macro_f1": by_f1,
                   "val_macro_f1_mean": float(np.mean([v["val_macro_f1"] for v in seeds.values()]))}
        s["best_model"] = "M2"
        sel["splits"][split] = s
        for sd, d in seeds.items():
            print(f"{split} seed {sd}: t_red {d['t_red']:.3f} t_yel {d['t_yel']:.3f} t_alert "
                  f"{d['t_alert']:.3f} val recall {d['val_red_recall']:.3f} Y->R {d['val_yellow_to_red']} "
                  f"G->R {d['val_green_to_red']} over {over(d)} macroF1 {d['val_macro_f1']:.3f}"
                  + ("  <- shipped" if sd == best else ""))
        print(f"{split}: M1 t_red {s['M1']['t_red']:.3f} over {over(s['M1'])}; seed by val macro F1 "
              f"would be {by_f1}")
    (ART / "selection_v3.json").write_text(json.dumps(sel, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
