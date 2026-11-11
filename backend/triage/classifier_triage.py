"""Hybrid triage: deterministic overrides + the learned classifier (TRIAGE_MODE=hybrid).

    level = max(override levels, classifier thresholded level)

* **Overrides** (``overrides.py``): temperature from the text or the request's ``temperature_c``
  (>= 38.5 °C RED, 37.8-38.4 °C YELLOW floor) and self-harm disclosures (RED, crisis guidance).
* **Classifier**: v2 (REPORT.md "v2: over-triage fix"): the SetFit model M2
  (``model/artifacts/setfit/m2_main_v2_it3_seed0``) when its weights are present, otherwise M1
  (frozen MiniLM + the committed LR head ``m1_main_v2.json``). Thresholds t_red / t_yel / t_alert
  come from ``model/artifacts/selection_v2.json`` and were all chosen on val.
  ``TRIAGE_MODEL_VERSION=v1`` pins the v1 model (``selection.json``). Which model was loaded is
  logged once and returned as ``model_used``.
* ``reasons`` is patient-readable text (``REASON_TEXT``); the internal codes are in
  ``reason_codes``.
* **No LLM** is involved anywhere in this path; the LLM never decides triage.
* The final level is never lower than any component's level (max over components).

Why the keyword engine (``SafetyTriageEngine`` rules) is NOT part of the max in hybrid mode
-----------------------------------------------------------------------------------------------
REPORT.md Finding 4: H1 = max(rules, M2) catches **no** RED message that M2 (thresholded) misses,
on the main test split, the challenge set or the unseen-scenario test. Every level the rules raise
is a non-RED message: on test they add 7 false REDs, on the challenge set 12, and macro F1 drops
from 0.63 to 0.54. They fire on negated keywords ("No chest pain, no chills" -> RED) and on single
words ("red", "pus", "chills"). The two RED gaps the rules were meant to cover - numbers and
self-harm - are handled here by ``overrides.py``, which reads the temperature value and is
negation-aware, instead of by keyword lists. Rules mode (the default) is unchanged.

Doctor-alert gate
-----------------
The email fires only for an override RED or p(RED) >= t_alert (the lowest val threshold with RED
precision >= 0.90; ``model/choose_alert_threshold.py``). A classifier RED with
t_red <= p(RED) < t_alert still gets the RED patient advice, but ``doctor_alert`` is False and
``flags`` contains ``"alert_suppressed_low_confidence"``; ``doctor_alert.py`` honours that flag.

If the classifier cannot be loaded or fails at run time, this module falls back to the rules
engine for the classifier component (logged, ``model_used = "rules_fallback"``) so that triage
never silently degrades to overrides only.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from triage.overrides import LEVEL_RANK, evaluate_overrides

LOGGER = logging.getLogger(__name__)

ART = Path(__file__).resolve().parent / "model" / "artifacts"
LABELS = ("GREEN", "YELLOW", "RED")
SUPPRESSED_FLAG = "alert_suppressed_low_confidence"

_STATUS = {"GREEN": 1, "YELLOW": 2, "RED": 3}

RED_PROTOCOL = (
    "Immediate contact with hospital emergency triage or operating surgeon. "
    "Do NOT wait. Suspected complication requires physical examination and immediate "
    "Doppler/bloodwork."
)
CRISIS_PROTOCOL = (
    "If you may act on thoughts of harming yourself or are in immediate "
    "danger, call your local emergency number or go to the nearest "
    "emergency department now. If possible, stay with someone you trust "
    "and contact a local crisis service or healthcare professional "
    "immediately. Do not wait for a reply in this chat."
)
YELLOW_PROTOCOL = (
    "Contact the orthopedic nursing hotline or schedule same-day follow-up. "
    "Elevate limb, apply cold therapy (20 mins per session), and closely monitor wound."
)
GREEN_PROTOCOL = (
    "Continue prescribed home rehabilitation exercises, cryotherapy, elevation, "
    "and oral medication schedule. Log next check-in as scheduled."
)
# Patient-facing wording for each internal reason code. Callers (orchestrator, chat_agent,
# symptom_agent, doctor_alert) print ``reasons`` verbatim, so ``reasons`` carries this text and
# the machine codes live in ``reason_codes``.
REASON_TEXT = {
    "high_fever": "a temperature of 38.5 °C or higher",
    "moderate_fever": "a temperature between 37.8 °C and 38.4 °C",
    "self_harm": ("what you told us about thoughts of harming yourself; you deserve support "
                  "right now and you do not have to manage this alone"),
    "classifier": "the symptoms you described",
}
DEFAULT_REASON_TEXT = "the symptoms you described"


def reason_text(codes: List[str]) -> List[str]:
    """Patient-readable reasons for the given codes, in order, without duplicates."""
    out: List[str] = []
    for c in codes:
        t = REASON_TEXT.get(c, DEFAULT_REASON_TEXT)
        if t not in out:
            out.append(t)
    return out


_URGENCY = {
    "RED": "EMERGENCY - IMMEDIATE CLINICAL ESCALATION REQUIRED",
    "YELLOW": "MODERATE RISK - SAME DAY / NEXT MORNING SURGEON CONTACT",
    "GREEN": "NORMAL RECOVERY PROTOCOL",
}


def selection_file() -> Path:
    """Model version: ``TRIAGE_MODEL_VERSION=v1`` pins the v1 model (selection.json); otherwise
    v2 (selection_v2.json) when present, else v1."""
    v1, v2 = ART / "selection.json", ART / "selection_v2.json"
    if os.environ.get("TRIAGE_MODEL_VERSION", "").strip().lower() == "v1":
        return v1
    return v2 if v2.exists() else v1


class _Classifier:
    """Lazy, thread-safe loader for M2 (preferred) or M1."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loaded = False
        self.selection_file: Optional[str] = None
        self.proba = None
        self.model_used: Optional[str] = None
        self.t_red = self.t_yel = self.t_alert = None
        self.load_error: Optional[str] = None

    def load(self) -> bool:
        if self._loaded:
            return self.proba is not None
        with self._lock:
            if self._loaded:
                return self.proba is not None
            try:
                self._load_inner()
            except Exception as exc:  # noqa: BLE001 - logged and reported via model_used
                self.load_error = f"{type(exc).__name__}: {exc}"
                LOGGER.error("[TRIAGE][HYBRID] classifier unavailable (%s); "
                             "falling back to the rules engine for the classifier component",
                             self.load_error)
                print(f"[TRIAGE][HYBRID] classifier unavailable: {self.load_error}")
            self._loaded = True
            return self.proba is not None

    def _load_inner(self) -> None:
        import numpy as np

        sel_file = selection_file()
        sel = json.loads(sel_file.read_text(encoding="utf-8"))["splits"]["main"]
        m2 = sel["M2"]
        seed, it = m2["best_seed"], m2["num_iterations"]
        m2_path = ART / "setfit" / m2.get("weights_dir", f"m2_main_it{it}_seed{seed}")
        self.selection_file = sel_file.name
        if m2_path.exists():
            from setfit import SetFitModel
            sf = SetFitModel.from_pretrained(str(m2_path))
            assert list(sf.model_head.classes_) == [0, 1, 2]
            t = m2["seeds"][str(seed)]

            def proba(text: str):
                return np.asarray(sf.predict_proba([text], as_numpy=True,
                                                   show_progress_bar=False))[0]
            self.model_used = f"M2:{m2_path.name}"
        else:
            from sentence_transformers import SentenceTransformer
            head = json.loads((ART / sel["M1"].get("head_file", "m1_main.json"))
                              .read_text(encoding="utf-8"))
            assert head["classes"] == list(LABELS)
            st = SentenceTransformer(head["embedding_model"], device="cpu")
            W, b = np.array(head["coef"]), np.array(head["intercept"])
            t = sel["M1"]

            def proba(text: str):
                z = st.encode([text], normalize_embeddings=True, show_progress_bar=False) @ W.T + b
                z = np.exp(z - z.max(1, keepdims=True))
                return (z / z.sum(1, keepdims=True))[0]
            self.model_used = "M1:m1_main.json"
            LOGGER.warning("[TRIAGE][HYBRID] M2 weights not found at %s; using M1", m2_path)
        self.t_red, self.t_yel, self.t_alert = t["t_red"], t["t_yel"], t["t_alert"]
        self.proba = proba
        LOGGER.info("[TRIAGE][HYBRID] classifier loaded: %s (t_red=%.3f t_yel=%.3f t_alert=%.3f)",
                    self.model_used, self.t_red, self.t_yel, self.t_alert)
        print(f"[TRIAGE][HYBRID] classifier loaded: {self.model_used} "
              f"(t_red={self.t_red:.3f} t_yel={self.t_yel:.3f} t_alert={self.t_alert:.3f})")


_CLASSIFIER = _Classifier()


def threshold_level(p_red: float, p_yel: float, t_red: float, t_yel: float) -> str:
    if p_red >= t_red:
        return "RED"
    if p_red + p_yel >= t_yel:
        return "YELLOW"
    return "GREEN"


def combine(text: str, probabilities: Optional[Dict[str, float]], t_red: Optional[float],
            t_yel: Optional[float], t_alert: Optional[float], model_used: str,
            temperature_c: Optional[float] = None,
            fallback_level: Optional[str] = None) -> Dict[str, Any]:
    """Pure decision step: overrides + classifier probabilities -> result dict.

    Exposed separately so evaluation can feed cached probabilities through exactly the same
    max / gate logic that runs in production."""
    overrides = evaluate_overrides(text, temperature_c)

    if probabilities is not None:
        clf_level = threshold_level(probabilities["RED"], probabilities["YELLOW"], t_red, t_yel)
    else:
        clf_level = fallback_level or "GREEN"

    components = [(o.level, o.reason) for o in overrides] + [(clf_level, "classifier")]
    level = max((c[0] for c in components), key=LEVEL_RANK.get)
    reason_codes = [name for lvl, name in components if lvl == level]

    override_red = any(o.level == "RED" for o in overrides)
    flags: List[str] = []
    if level == "RED":
        if override_red:
            doctor_alert = True
        elif probabilities is not None:
            doctor_alert = probabilities["RED"] >= t_alert
        else:
            doctor_alert = True          # rules fallback: keep today's behaviour (always email)
        if not doctor_alert:
            flags.append(SUPPRESSED_FLAG)
    else:
        doctor_alert = False

    crisis = next((o for o in overrides if o.category == "mental_health_crisis"), None)
    result: Dict[str, Any] = {
        "triage_level": level,
        "status_code": _STATUS[level],
        "reasons": reason_text(reason_codes),      # patient-readable (shown in replies)
        "reason_codes": reason_codes,              # internal: high_fever | moderate_fever | ...
        "is_escalated": level != "GREEN",
        "triage_mode": "hybrid",
        "model_used": model_used,
        "probabilities": probabilities,
        "classifier_level": clf_level,
        "overrides": [{"level": o.level, "reason": o.reason, "detail": o.detail,
                       "evidence": o.evidence} for o in overrides],
        "thresholds": {"t_red": t_red, "t_yel": t_yel, "t_alert": t_alert},
        "doctor_alert": doctor_alert,
        "flags": flags,
    }
    if crisis is not None:
        result.update(urgency="IMMEDIATE CRISIS SUPPORT REQUIRED",
                      action_protocol=CRISIS_PROTOCOL, category="mental_health_crisis")
    else:
        result.update(urgency=_URGENCY[level],
                      action_protocol={"RED": RED_PROTOCOL, "YELLOW": YELLOW_PROTOCOL,
                                       "GREEN": GREEN_PROTOCOL}[level])
    return result


def evaluate(symptoms: str, temperature_c: Optional[float] = None,
             post_op_day: int = 1) -> Dict[str, Any]:
    """Hybrid triage of one text. Same call signature and result keys as
    SafetyTriageEngine.evaluate (triage_level, urgency, status_code, reasons, action_protocol,
    is_escalated, category for a crisis), plus probabilities / model_used / doctor_alert / flags.
    """
    text = symptoms or ""
    probabilities = None
    fallback_level = None
    model_used = "rules_fallback"
    t = {"t_red": None, "t_yel": None, "t_alert": None}
    if _CLASSIFIER.load():
        try:
            p = _CLASSIFIER.proba(text)
            probabilities = {l: float(v) for l, v in zip(LABELS, p)}
            model_used = _CLASSIFIER.model_used
            t = {"t_red": _CLASSIFIER.t_red, "t_yel": _CLASSIFIER.t_yel,
                 "t_alert": _CLASSIFIER.t_alert}
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("[TRIAGE][HYBRID] classifier failed on input (%s); using rules", exc)
            probabilities = None
    if probabilities is None:
        from triage.safety_triage import SafetyTriageEngine
        fallback_level = SafetyTriageEngine.evaluate_rules(
            text, temperature_c=temperature_c, post_op_day=post_op_day)["triage_level"]
    return combine(text, probabilities, t["t_red"], t["t_yel"], t["t_alert"], model_used,
                   temperature_c=temperature_c, fallback_level=fallback_level)


def model_info() -> Dict[str, Any]:
    _CLASSIFIER.load()
    return {"model_used": _CLASSIFIER.model_used or "rules_fallback",
            "t_red": _CLASSIFIER.t_red, "t_yel": _CLASSIFIER.t_yel,
            "t_alert": _CLASSIFIER.t_alert, "load_error": _CLASSIFIER.load_error,
            "selection_file": _CLASSIFIER.selection_file}
