"""classify(text) -> {level, probabilities, ...} with the model chosen on validation data.

The default model and both decision thresholds come from artifacts/selection.json (main split).
`level` uses the thresholded safety rule (RED if p(RED) >= t_red, else YELLOW if
p(RED)+p(YELLOW) >= t_yel, else GREEN); `level_argmax` is the plain argmax.

  M1: frozen all-MiniLM-L6-v2 + the committed LR head (artifacts/m1_main.json).
  M2: SetFit weights in artifacts/setfit/ (not committed; run train.py to rebuild them).

This module does not combine with the rules (H1). The production path is
triage/classifier_triage.py (TRIAGE_MODE=hybrid), which loads the same model and thresholds.

  backend/.venv/Scripts/python backend/triage/model/predict.py "my calf is hot and hard"
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

ART = Path(__file__).resolve().parent / "artifacts"
LABELS = ("GREEN", "YELLOW", "RED")


@lru_cache(maxsize=1)
def _selection() -> dict:
    return json.loads((ART / "selection.json").read_text(encoding="utf-8"))["splits"]["main"]


@lru_cache(maxsize=2)
def _load(model: str):
    sel = _selection()
    if model == "M1":
        from sentence_transformers import SentenceTransformer
        head = json.loads((ART / "m1_main.json").read_text(encoding="utf-8"))
        assert head["classes"] == list(LABELS)
        st = SentenceTransformer(head["embedding_model"], device="cpu")
        W, b = np.array(head["coef"]), np.array(head["intercept"])

        def proba(text: str) -> np.ndarray:
            z = st.encode([text], normalize_embeddings=True, show_progress_bar=False) @ W.T + b
            z = np.exp(z - z.max(1, keepdims=True))
            return (z / z.sum(1, keepdims=True))[0]
        return proba, sel["M1"]["t_red"], sel["M1"]["t_yel"]
    if model == "M2":
        seed, it = sel["M2"]["best_seed"], sel["M2"]["num_iterations"]
        path = ART / "setfit" / f"m2_main_it{it}_seed{seed}"
        if not path.exists():
            raise FileNotFoundError(
                f"SetFit weights not found at {path}. They are not committed; rebuild with\n"
                f"  backend/.venv/Scripts/python backend/triage/model/train.py setfit "
                f"--split main --seed {seed} --iters {it} --save")
        from setfit import SetFitModel
        sf = SetFitModel.from_pretrained(str(path))
        assert list(sf.model_head.classes_) == [0, 1, 2]
        t = sel["M2"]["seeds"][str(seed)]

        def proba(text: str) -> np.ndarray:
            return np.asarray(sf.predict_proba([text], as_numpy=True, show_progress_bar=False))[0]
        return proba, t["t_red"], t["t_yel"]
    raise ValueError(f"unknown model {model!r} (M1 or M2)")


def classify(text: str, model: str | None = None) -> dict:
    """Triage one patient message (text only).

    Returns {"level", "level_argmax", "probabilities": {GREEN, YELLOW, RED}, "model",
    "thresholds"}. `level` is the thresholded safety rule chosen on validation data."""
    model = model or _selection()["best_model"]
    proba, t_red, t_yel = _load(model)
    p = proba(text)
    if p[2] >= t_red:
        level = "RED"
    elif p[2] + p[1] >= t_yel:
        level = "YELLOW"
    else:
        level = "GREEN"
    return {"level": level, "level_argmax": LABELS[int(p.argmax())],
            "probabilities": {l: float(v) for l, v in zip(LABELS, p)},
            "model": model, "thresholds": {"t_red": t_red, "t_yel": t_yel}}


if __name__ == "__main__":
    for msg in sys.argv[1:] or ["my calf is hot and hard", "when can I shower?"]:
        print(json.dumps({"text": msg, **classify(msg)}, indent=1))
