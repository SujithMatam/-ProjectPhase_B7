"""Shared helpers for the triage classifier experiments (train.py, evaluate.py).

Labels are indexed by severity: 0 GREEN, 1 YELLOW, 2 RED. Input is the message text only.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import random
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
TRIAGE = HERE.parent
DATA = TRIAGE / "data"
REPO = TRIAGE.parent.parent
ART = HERE / "artifacts"            # committed: small heads + selection.json
CACHE = ART / "cache"               # gitignored: embeddings, predictions
SETFIT_DIR = ART / "setfit"         # gitignored: SetFit weights (reproduce with train.py)

LABELS = ("GREEN", "YELLOW", "RED")
L2I = {l: i for i, l in enumerate(LABELS)}
G, Y, R = 0, 1, 2
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
SEEDS = (0, 1, 2, 3, 4)
SETFIT_SEEDS = {"main": (0, 1, 2, 3, 4), "unseen": (0, 1, 2)}   # trimmed for CPU time
MAX_SEQ_LENGTH = 64                                               # longest message = 47 tokens
TRAIN_LOG = ART / "train.log"
SPLIT_DIRS = {"main": DATA / "splits", "unseen": DATA / "splits_unseen_scenario"}

# rule baselines: safety_triage.py loaded from git, text only
RULE_COMMITS = {
    "B0": "6e63cbf",   # pre-merge rules
    "B1": "9f60dfe",   # origin/main at the time of the experiment (Rishi's version)
}

RED_RECALL_TARGET = 0.95
YELLOW_FOUND_TARGET = 0.90


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import torch
        torch.manual_seed(seed)
    except ImportError:
        pass


# ---------------------------------------------------------------- data
def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def load_split(which: str, part: str) -> list[dict]:
    return load_jsonl(SPLIT_DIRS[which] / f"{part}.jsonl")


def load_challenge() -> list[dict]:
    return load_jsonl(DATA / "challenge.jsonl")


def load_challenge_v2() -> list[dict]:
    return load_jsonl(DATA / "challenge_v2.jsonl")


V2_EXTRA = DATA / "train_v2_extra.jsonl"     # origin "generated_v2", TRAIN only (build_train_v2.py)


def load_train(which: str, data: str = "v1") -> list[dict]:
    """Training rows. v2 = the frozen split's train + the generated_v2 rows. For the
    unseen-scenario split only the v2 rows flagged ``unseen_split_ok`` are added (no topic of an
    unseen val/test scenario and no near-duplicate of an unseen val/test row)."""
    rows = load_split(which, "train")
    if data == "v1":
        return rows
    extra = load_jsonl(V2_EXTRA)
    if which == "unseen":
        extra = [r for r in extra if r["unseen_split_ok"]]
    return rows + extra


def labels_of(rows: list[dict]) -> np.ndarray:
    return np.array([L2I[r["label"]] for r in rows])


# ---------------------------------------------------------------- embeddings
_ST = None


def sentence_model():
    global _ST
    if _ST is None:
        from sentence_transformers import SentenceTransformer
        _ST = SentenceTransformer(EMBED_MODEL, device="cpu")
    return _ST


def embed(texts: list[str]) -> np.ndarray:
    """Frozen all-MiniLM-L6-v2 embeddings (normalised), cached on disk by text."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / "minilm_embeddings.npz"
    cache: dict[str, np.ndarray] = {}
    if path.exists():
        z = np.load(path, allow_pickle=False)
        cache = dict(zip(z["texts"].tolist(), z["emb"]))
    missing = sorted({t for t in texts if t not in cache})
    if missing:
        e = sentence_model().encode(missing, batch_size=64, normalize_embeddings=True,
                                    show_progress_bar=False)
        cache.update(zip(missing, e))
        keys = sorted(cache)
        np.savez(path, texts=np.array(keys), emb=np.stack([cache[k] for k in keys]))
    return np.stack([cache[t] for t in texts]).astype(np.float32)


# ---------------------------------------------------------------- rule baselines
def load_rules(name: str):
    """Import backend/triage/safety_triage.py as it was at RULE_COMMITS[name]."""
    commit = RULE_COMMITS[name]
    src = subprocess.run(["git", "-C", str(REPO), "show", f"{commit}:backend/triage/safety_triage.py"],
                         capture_output=True, check=True).stdout
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"safety_triage_{name}_{commit}.py"
    path.write_bytes(src)
    spec = importlib.util.spec_from_file_location(f"safety_triage_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SafetyTriageEngine


def rule_predict(engine, texts: list[str]) -> np.ndarray:
    return np.array([L2I[engine.evaluate(t)["triage_level"]] for t in texts])


# ---------------------------------------------------------------- decision rules
def argmax_rule(p: np.ndarray) -> np.ndarray:
    return p.argmax(1)


def threshold_rule(p: np.ndarray, t_red: float, t_yel: float) -> np.ndarray:
    """RED if p(RED) >= t_red, else YELLOW if p(RED)+p(YELLOW) >= t_yel, else GREEN."""
    out = np.full(len(p), G)
    out[p[:, R] + p[:, Y] >= t_yel] = Y
    out[p[:, R] >= t_red] = R
    return out


def choose_thresholds(p: np.ndarray, y: np.ndarray) -> dict:
    """Pick both thresholds on validation data.

    t_red: the highest threshold with RED recall >= 0.95.
    t_yel: with t_red fixed, the highest threshold such that >= 90% of YELLOW-labelled rows
           are not called GREEN (predicted YELLOW or RED).
    """
    pr = np.sort(p[y == R, R])[::-1]
    k = math.ceil(RED_RECALL_TARGET * len(pr))
    t_red = float(pr[k - 1])
    yel = y == Y
    caught = yel & (p[:, R] >= t_red)
    s = np.sort((p[:, R] + p[:, Y])[yel & ~caught])[::-1]
    need = math.ceil(YELLOW_FOUND_TARGET * yel.sum()) - int(caught.sum())
    t_yel = 1.0 if need <= 0 else float(s[need - 1])
    pred = threshold_rule(p, t_red, t_yel)
    return {"t_red": t_red, "t_yel": t_yel,
            "val_red_recall": float((pred[y == R] == R).mean()),
            "val_yellow_found": float((pred[yel] >= Y).mean())}


def hybrid(rule_pred: np.ndarray, model_pred: np.ndarray) -> np.ndarray:
    """H1: the higher (more urgent) of the rule level and the model level."""
    return np.maximum(rule_pred, model_pred)


# ---------------------------------------------------------------- metrics
def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def confusion(y: np.ndarray, pred: np.ndarray) -> np.ndarray:
    """3x3, rows = true RED/YELLOW/GREEN, columns = predicted RED/YELLOW/GREEN."""
    order = (R, Y, G)
    return np.array([[int(((y == a) & (pred == b)).sum()) for b in order] for a in order])


def macro_f1(y: np.ndarray, pred: np.ndarray) -> float:
    f = []
    for c in (G, Y, R):
        tp = int(((pred == c) & (y == c)).sum())
        fp = int(((pred == c) & (y != c)).sum())
        fn = int(((pred != c) & (y == c)).sum())
        f.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return float(np.mean(f))


def metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    n_red = int((y == R).sum())
    k = int(((y == R) & (pred == R)).sum())
    pp = int((pred == R).sum())
    lo, hi = wilson(k, n_red)
    return {
        "n": int(len(y)), "n_red": n_red,
        "red_recall": k / n_red if n_red else float("nan"), "red_recall_ci": [lo, hi],
        "red_tp": k,
        "red_precision": k / pp if pp else float("nan"),
        "macro_f1": macro_f1(y, pred),
        "accuracy": float((y == pred).mean()),
        "red_to_green": int(((y == R) & (pred == G)).sum()),
        "red_to_yellow": int(((y == R) & (pred == Y)).sum()),
        "green_to_red": int(((y == G) & (pred == R)).sum()),
        "yellow_to_green": int(((y == Y) & (pred == G)).sum()),
        "under_triage": int((pred < y).sum()),
        "over_triage": int((pred > y).sum()),
        "confusion": confusion(y, pred).tolist(),
    }


def ece(p: np.ndarray, y: np.ndarray, bins: int = 10) -> dict:
    """Top-label expected calibration error (equal-width bins) plus RED-vs-rest ECE."""
    def _ece(conf, correct):
        edges = np.linspace(0, 1, bins + 1)
        idx = np.clip(np.digitize(conf, edges[1:-1], right=True), 0, bins - 1)
        tot, rows = 0.0, []
        for b in range(bins):
            m = idx == b
            if m.any():
                gap = abs(conf[m].mean() - correct[m].mean())
                tot += m.mean() * gap
                rows.append((float(edges[b]), float(edges[b + 1]), int(m.sum()),
                             float(conf[m].mean()), float(correct[m].mean())))
            else:
                rows.append((float(edges[b]), float(edges[b + 1]), 0, float("nan"), float("nan")))
        return float(tot), rows
    top, top_rows = _ece(p.max(1), (p.argmax(1) == y).astype(float))
    red, red_rows = _ece(p[:, R], (y == R).astype(float))
    return {"ece_top": top, "bins_top": top_rows, "ece_red": red, "bins_red": red_rows}
