"""Train the triage classifiers and choose everything on validation data.

  M1  frozen all-MiniLM-L6-v2 embeddings + logistic regression (class_weight balanced, C tuned on val)
  M2  SetFit on all-MiniLM-L6-v2. num_iterations in {1, 3} tuned on the MAIN split's val with
      seed 0; the chosen value is reused for the unseen-scenario split. Then 5 seeds on the main
      split and 3 seeds on the unseen-scenario split.

Test, challenge and the unseen-scenario test are predicted here but only read by evaluate.py.
Runs are strictly sequential, one Python process at a time; a run whose predictions already
exist in artifacts/cache/preds/ is skipped, so `all` resumes after an interruption. Progress is
appended to artifacts/train.log.

Run from the repo root with the backend venv (HF_HUB_OFFLINE=1 if the model is cached):
  backend/.venv/Scripts/python backend/triage/model/train.py all          # everything, in order
  backend/.venv/Scripts/python backend/triage/model/train.py m1
  backend/.venv/Scripts/python backend/triage/model/train.py setfit --split main --seed 0 --iters 3 [--save]
  backend/.venv/Scripts/python backend/triage/model/train.py select

Outputs: artifacts/m1_{main,unseen}.json (LR heads, committed), artifacts/selection.json and
artifacts/train.log (committed), artifacts/cache/ (predictions, trainer scratch; gitignored),
artifacts/setfit/ (main-split SetFit weights; gitignored).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (ART, CACHE, EMBED_MODEL, LABELS, MAX_SEQ_LENGTH, SETFIT_DIR, SETFIT_SEEDS,  # noqa: E402
                    TRAIN_LOG, choose_thresholds, embed, labels_of, load_challenge, load_split,
                    macro_f1, seed_everything)

PREDS = CACHE / "preds"
C_GRID = [float(c) for c in np.logspace(-3, 3, 13)]
SETFIT_ITERS = (1, 3)
SETFIT_ARGS = {"batch_size": 32, "num_epochs": 1, "body_learning_rate": 2e-5}
SPLITS = ("main", "unseen")
TUNE_SPLIT = "main"


def log(msg: str) -> None:
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    ART.mkdir(parents=True, exist_ok=True)
    with open(TRAIN_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def eval_sets(split: str) -> dict[str, list[dict]]:
    sets = {"val": load_split(split, "val"), "test": load_split(split, "test")}
    if split == "main":
        sets["challenge"] = load_challenge()
    return sets


def save_preds(name: str, sets: dict[str, list[dict]], probs: dict[str, np.ndarray], extra: dict) -> None:
    PREDS.mkdir(parents=True, exist_ok=True)
    arrs = {}
    for k, rows in sets.items():
        arrs[f"{k}_p"] = probs[k]
        arrs[f"{k}_ids"] = np.array([r["id"] for r in rows])
    np.savez(PREDS / f"{name}.npz", meta=json.dumps(extra), **arrs)


def has_preds(name: str) -> bool:
    return (PREDS / f"{name}.npz").exists()


def load_preds(name: str) -> dict:
    z = np.load(PREDS / f"{name}.npz", allow_pickle=False)
    out = {k: z[k] for k in z.files if k != "meta"}
    out["meta"] = json.loads(str(z["meta"]))
    return out


def setfit_name(split: str, iters: int, seed: int) -> str:
    return f"m2_{split}_it{iters}_seed{seed}"


# ---------------------------------------------------------------- M1
def train_m1(split: str) -> dict:
    from sklearn.linear_model import LogisticRegression
    seed_everything(0)
    train = load_split(split, "train")
    sets = eval_sets(split)
    xtr, ytr = embed([r["text"] for r in train]), labels_of(train)
    xv, yv = embed([r["text"] for r in sets["val"]]), labels_of(sets["val"])
    grid = []
    for c in C_GRID:
        clf = LogisticRegression(C=c, class_weight="balanced", max_iter=5000).fit(xtr, ytr)
        grid.append((macro_f1(yv, clf.predict_proba(xv).argmax(1)), c, clf))
    best_f1 = max(g[0] for g in grid)
    f1, c, clf = next(g for g in grid if g[0] == best_f1)        # smallest C among ties
    assert list(clf.classes_) == [0, 1, 2]
    probs = {k: clf.predict_proba(embed([r["text"] for r in rows])) for k, rows in sets.items()}
    head = {"model": "M1", "embedding_model": EMBED_MODEL, "normalize_embeddings": True,
            "classes": list(LABELS), "C": c, "class_weight": "balanced", "split": split,
            "coef": clf.coef_.tolist(), "intercept": clf.intercept_.tolist(),
            "val_macro_f1_argmax": f1,
            "c_grid": [{"C": g[1], "val_macro_f1": g[0]} for g in grid]}
    ART.mkdir(parents=True, exist_ok=True)
    (ART / f"m1_{split}.json").write_text(json.dumps(head, indent=1) + "\n", encoding="utf-8")
    save_preds(f"m1_{split}", sets, probs, {"C": c})
    log(f"M1 {split}: C={c:g} val macro-F1 {f1:.3f}")
    return head


# ---------------------------------------------------------------- M2 (SetFit)
def train_setfit(split: str, seed: int, iters: int, save: bool = False) -> None:
    name = setfit_name(split, iters, seed)
    if has_preds(name) and (not save or (SETFIT_DIR / name).exists()):
        log(f"{name}: predictions exist, skipped")
        return
    from datasets import Dataset
    from setfit import SetFitModel, Trainer, TrainingArguments
    seed_everything(seed)
    train = load_split(split, "train")
    sets = eval_sets(split)
    ds = Dataset.from_dict({"text": [r["text"] for r in train], "label": labels_of(train).tolist()})
    model = SetFitModel.from_pretrained(EMBED_MODEL)
    model.model_body.max_seq_length = MAX_SEQ_LENGTH
    args = TrainingArguments(num_iterations=iters, seed=seed, report_to="none", logging_steps=10_000,
                             output_dir=str(CACHE / "trainer"), save_strategy="no",
                             max_length=MAX_SEQ_LENGTH, **SETFIT_ARGS)
    log(f"{name}: start ({len(train)} train rows, num_iterations {iters}, "
        f"~{2 * iters * len(train)} pairs, max_seq_length {model.model_body.max_seq_length})")
    t0 = time.time()
    Trainer(model=model, args=args, train_dataset=ds).train()
    secs = time.time() - t0
    assert model.model_body.max_seq_length == MAX_SEQ_LENGTH
    assert list(model.model_head.classes_) == [0, 1, 2], model.model_head.classes_
    probs = {k: np.asarray(model.predict_proba([r["text"] for r in rows], as_numpy=True))
             for k, rows in sets.items()}
    save_preds(name, sets, probs, {"seed": seed, "num_iterations": iters, "train_secs": secs,
                                   "max_seq_length": MAX_SEQ_LENGTH, **SETFIT_ARGS})
    if save:
        model.save_pretrained(str(SETFIT_DIR / name))
    yv = labels_of(sets["val"])
    log(f"{name}: done, val macro-F1 {macro_f1(yv, probs['val'].argmax(1)):.3f} ({secs / 60:.1f} min)")


def chosen_iters() -> tuple[int, dict]:
    """num_iterations by val macro-F1 (argmax) on the main split, seed 0; ties -> fewer."""
    yv = labels_of(load_split(TUNE_SPLIT, "val"))
    tune = {it: macro_f1(yv, load_preds(setfit_name(TUNE_SPLIT, it, 0))["val_p"].argmax(1))
            for it in SETFIT_ITERS}
    return max(tune, key=lambda k: (tune[k], -k)), tune


# ---------------------------------------------------------------- selection (val only)
def select() -> dict:
    it, tune = chosen_iters()
    sel: dict = {"note": "every choice here uses validation data only", "splits": {}}
    for split in SPLITS:
        yv = labels_of(load_split(split, "val"))
        s: dict = {}
        m1 = load_preds(f"m1_{split}")
        s["M1"] = {"C": m1["meta"]["C"], "val_macro_f1": macro_f1(yv, m1["val_p"].argmax(1)),
                   **choose_thresholds(m1["val_p"], yv)}
        seeds = {}
        for sd in SETFIT_SEEDS[split]:
            p = load_preds(setfit_name(split, it, sd))
            seeds[sd] = {"val_macro_f1": macro_f1(yv, p["val_p"].argmax(1)),
                         **choose_thresholds(p["val_p"], yv)}
        ship = max(seeds, key=lambda k: (seeds[k]["val_macro_f1"], -k))
        s["M2"] = {"num_iterations": it, "num_iterations_tuned_on": f"{TUNE_SPLIT} val, seed 0",
                   "tuning_val_macro_f1": tune, "seeds": seeds, "best_seed": ship,
                   "val_macro_f1_mean": float(np.mean([v["val_macro_f1"] for v in seeds.values()]))}
        best = "M2" if s["M2"]["val_macro_f1_mean"] > s["M1"]["val_macro_f1"] else "M1"
        s["best_model"] = best
        s["best_model_rule"] = "higher val macro-F1 (argmax; M2 = mean over seeds)"
        sel["splits"][split] = s
        log(f"select {split}: M1 {s['M1']['val_macro_f1']:.3f}, M2 (it {it}) "
            f"{s['M2']['val_macro_f1_mean']:.3f} -> best {best}, shipped seed {ship}")
    (ART / "selection.json").write_text(json.dumps(sel, indent=1) + "\n", encoding="utf-8")
    return sel


def run_all() -> None:
    """Every step in order, each SetFit run in its own child process, one at a time."""
    def child(*a: str) -> None:
        subprocess.run([sys.executable, str(Path(__file__).resolve()), *a], check=True)

    log("=== train.py all ===")
    if not all(has_preds(f"m1_{sp}") for sp in SPLITS):
        child("m1")
    for it in SETFIT_ITERS:
        child("setfit", "--split", TUNE_SPLIT, "--seed", "0", "--iters", str(it), "--save")
    it, tune = chosen_iters()
    log(f"num_iterations tuning on {TUNE_SPLIT} val (seed 0): {tune} -> {it}")
    for split in ("main", "unseen"):
        for sd in SETFIT_SEEDS[split]:
            args = ["setfit", "--split", split, "--seed", str(sd), "--iters", str(it)]
            child(*args, *(["--save"] if split == "main" else []))
    child("select")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["all", "m1", "setfit", "select"])
    ap.add_argument("--split", choices=SPLITS, default="main")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--iters", type=int, default=SETFIT_ITERS[-1])
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()
    if a.cmd == "m1":
        for sp in SPLITS:
            train_m1(sp)
    elif a.cmd == "setfit":
        train_setfit(a.split, a.seed, a.iters, a.save)
    elif a.cmd == "select":
        select()
    else:
        run_all()


if __name__ == "__main__":
    main()
