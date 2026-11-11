"""Unit tests for the hybrid decision step, the TRIAGE_MODE switch and the doctor-alert gate.

combine() is tested with fixed probabilities, so no model is loaded here.

    cd backend && .venv/Scripts/python -m pytest triage/test_classifier_triage.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from triage import classifier_triage as ct  # noqa: E402
from triage.safety_triage import SafetyTriageEngine, triage_mode  # noqa: E402

T = dict(t_red=0.2, t_yel=0.25, t_alert=0.65)


def P(red, yellow):
    return {"GREEN": 1 - red - yellow, "YELLOW": yellow, "RED": red}


def run(text, probs, temperature_c=None):
    return ct.combine(text, probs, T["t_red"], T["t_yel"], T["t_alert"], "test",
                      temperature_c=temperature_c)


def test_classifier_green():
    r = run("when can I shower?", P(0.01, 0.02))
    assert r["triage_level"] == "GREEN" and r["reason_codes"] == ["classifier"]
    assert r["doctor_alert"] is False and r["flags"] == [] and r["status_code"] == 1


def test_classifier_red_above_t_alert_emails():
    r = run("my calf is hot and hard", P(0.9, 0.05))
    assert r["triage_level"] == "RED" and r["doctor_alert"] is True and r["flags"] == []


def test_classifier_red_below_t_alert_is_red_without_email():
    r = run("my knee feels odd", P(0.4, 0.3))
    assert r["triage_level"] == "RED"                     # patient still gets RED advice
    assert r["action_protocol"] == ct.RED_PROTOCOL
    assert r["doctor_alert"] is False
    assert r["flags"] == [ct.SUPPRESSED_FLAG]


def test_override_red_always_emails_even_with_low_p_red():
    r = run("39.6 is this an emergency", P(0.25, 0.5))
    assert r["triage_level"] == "RED" and r["doctor_alert"] is True
    assert r["reason_codes"] == ["high_fever", "classifier"]


def test_override_raises_classifier_green():
    r = run("when can I shower?", P(0.01, 0.02), temperature_c=38.9)
    assert r["triage_level"] == "RED" and r["reason_codes"] == ["high_fever"]
    assert r["doctor_alert"] is True


def test_yellow_floor_from_temperature():
    r = run("temp 38.1", P(0.01, 0.02))
    assert r["triage_level"] == "YELLOW" and r["reason_codes"] == ["moderate_fever"]


def test_override_never_lowers_classifier():
    r = run("temp 38.1 and my calf is hard and hot", P(0.95, 0.03))
    assert r["triage_level"] == "RED" and r["reason_codes"] == ["classifier"]


def test_self_harm_gives_crisis_guidance():
    r = run("everyone would be better off without me", P(0.01, 0.05))
    assert r["triage_level"] == "RED" and r["reason_codes"] == ["self_harm"]
    assert r["category"] == "mental_health_crisis"
    assert r["action_protocol"] == ct.CRISIS_PROTOCOL
    assert r["doctor_alert"] is True


def test_rules_fallback_when_no_probabilities():
    r = ct.combine("x", None, None, None, None, "rules_fallback", fallback_level="RED")
    assert r["triage_level"] == "RED" and r["doctor_alert"] is True


@pytest.mark.parametrize("value, expected", [
    (None, "rules"), ("", "rules"), ("rules", "rules"), ("HYBRID", "hybrid"),
    (" hybrid ", "hybrid"), ("something", "rules"),
])
def test_triage_mode(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("TRIAGE_MODE", raising=False)
    else:
        monkeypatch.setenv("TRIAGE_MODE", value)
    assert triage_mode() == expected


def test_rules_mode_is_unchanged(monkeypatch):
    monkeypatch.delenv("TRIAGE_MODE", raising=False)
    for text in ("my calf is warm and swollen", "No chest pain, no chills", "fever of 39"):
        assert SafetyTriageEngine.evaluate(text) == SafetyTriageEngine.evaluate_rules(text)
    assert "triage_mode" not in SafetyTriageEngine.evaluate("chest pain")


def test_hybrid_mode_dispatches(monkeypatch):
    monkeypatch.setenv("TRIAGE_MODE", "hybrid")
    seen = {}

    def fake(symptoms, temperature_c=None, post_op_day=1):
        seen.update(symptoms=symptoms, temperature_c=temperature_c)
        return {"triage_level": "GREEN"}
    monkeypatch.setattr(ct, "evaluate", fake)
    SafetyTriageEngine.evaluate("hello", temperature_c=38.6)
    assert seen == {"symptoms": "hello", "temperature_c": 38.6}


def test_doctor_alert_gate(monkeypatch):
    for key in ("SMTP_PASSWORD", "SMTP_HOST", "SMTP_USERNAME", "DOCTOR_ALERT_EMAIL"):
        monkeypatch.delenv(key, raising=False)
    import doctor_alert
    sent = []
    monkeypatch.setattr(doctor_alert.DoctorAlertNotifier, "_send",
                        lambda self, **kw: sent.append(kw["patient_id"]))
    n = doctor_alert.DoctorAlertNotifier()
    suppressed = run("my knee feels odd", P(0.4, 0.3))
    assert n.notify_red_triage(patient_id="A", user_message="m", triage=suppressed) is False
    assert n.notify_red_triage_background(patient_id="A", user_message="m",
                                          triage=suppressed) is None
    rules_red = {"triage_level": "RED", "reasons": ["x"]}            # rules mode: no gate key
    assert n.notify_red_triage(patient_id="B", user_message="m", triage=rules_red) is True
    alerting = run("my calf is hot and hard", P(0.9, 0.05))
    assert n.notify_red_triage(patient_id="C", user_message="m", triage=alerting) is True
    assert sent == ["B", "C"]


def test_reasons_are_patient_readable_and_codes_are_kept():
    r = run("39.6 is this an emergency", P(0.25, 0.5))
    assert r["reason_codes"] == ["high_fever", "classifier"]
    assert r["reasons"] == ["a temperature of 38.5 °C or higher", "the symptoms you described"]
    assert run("temp 38.1", P(0.01, 0.02))["reasons"] == [
        "a temperature between 37.8 °C and 38.4 °C"]
    sh = run("everyone would be better off without me", P(0.01, 0.05))
    assert "harming yourself" in sh["reasons"][0]
    for res in (r, sh, run("when can I shower?", P(0.01, 0.02))):
        assert all("_" not in t for t in res["reasons"])           # no internal codes leak


def test_reason_text_unknown_code_and_dedup():
    assert ct.reason_text(["classifier", "something_new"]) == ["the symptoms you described"]
