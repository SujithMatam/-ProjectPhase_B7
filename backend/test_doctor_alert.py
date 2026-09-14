"""
Doctor RED-triage alert notification test suite.

Run directly:
    .venv/Scripts/python.exe test_doctor_alert.py

Plain-Python script (no pytest dependency), consistent with
test_phase2_intent.py / test_phase4_agents.py. No real email is ever sent:
smtplib.SMTP is mocked everywhere network I/O would otherwise occur.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from lam.orchestrator import LAMOrchestrator
from lam.schemas import IntentLabel
from agents.chat_agent import ChatAgent
from doctor_alert import DoctorAlertNotifier, doctor_alert_notifier

_FAILURES: List[str] = []


def _check(condition: bool, message: str) -> None:
    if not condition:
        _FAILURES.append(message)
        print(f"    !! FAILED: {message}")


def _recording_notify():
    """A notify_red_triage_background stand-in that records its kwargs
    synchronously (no real thread, no network) -- used for tests that only
    care about scheduling/call-count, not about background timing."""
    calls: List[Dict[str, Any]] = []

    def _fn(**kwargs) -> bool:
        calls.append(kwargs)
        return True

    return _fn, calls


# A fully explicit configuration -- used by tests that don't care about the
# prototype defaults, only that a fully-configured send behaves correctly.
_CONFIGURED_ENV = {
    "DOCTOR_ALERT_EMAIL": "doctor@example.com",
    "SMTP_HOST": "smtp.example.com",
    "SMTP_PORT": "587",
    "SMTP_USERNAME": "alerts@example.com",
    "SMTP_PASSWORD": "super-secret",
    "SMTP_FROM_EMAIL": "alerts@example.com",
}

# The fixed prototype default recipient -- the patient/user must never have
# to supply a doctor email address themselves.
_DEFAULT_RECIPIENT = "pranavtvm05@gmail.com"
_DEFAULT_SENDER = "chatbotlammm@gmail.com"
_DEFAULT_HOST = "smtp.gmail.com"
_DEFAULT_PORT = 587

_RED_MESSAGE = "I have severe chest pain and can't breathe."


# ---------------------------------------------------------------------------
# A + E. RED triage sends exactly ONE doctor alert, and the existing RED
# emergency response (intent/triage info) is unchanged.
# ---------------------------------------------------------------------------

def run_red_sends_one_alert_test() -> None:
    print("=" * 78)
    print("A/E -- RED triage sends exactly one doctor alert; RED response unchanged")
    print("=" * 78)

    notify_fn, calls = _recording_notify()
    with patch.object(doctor_alert_notifier, "notify_red_triage_background", side_effect=notify_fn):
        result = LAMOrchestrator.process(
            patient_id="P123",
            surgery_type="Total Knee Arthroplasty",
            affected_limb="Right",
            postop_day=8,
            user_message=_RED_MESSAGE,
        )

    print(f"    doctor alert calls = {len(calls)}")
    _check(len(calls) == 1, f"expected exactly 1 doctor alert for RED, got {len(calls)}")
    _check(result["triage_level"] == "RED", "RED response triage_level changed")
    _check(result["is_escalated"] is True, "RED response is_escalated changed")
    _check(result["intent"] == IntentLabel.EMERGENCY.value, "RED response intent changed")
    _check("CRITICAL EMERGENCY ALERT" in result["reply"], "RED patient-facing reply text changed")
    print("    CONFIRMED: one alert sent, RED response shape/content unchanged.")
    print()


# ---------------------------------------------------------------------------
# B. Alert payload contains patient_id, message, RED level, reasons, and
# surgery/postop context when supplied.
# ---------------------------------------------------------------------------

def run_alert_payload_contents_test() -> None:
    print("=" * 78)
    print("B -- alert payload contains required context")
    print("=" * 78)

    notify_fn, calls = _recording_notify()
    with patch.object(doctor_alert_notifier, "notify_red_triage_background", side_effect=notify_fn):
        LAMOrchestrator.process(
            patient_id="P123",
            surgery_type="Total Knee Arthroplasty",
            affected_limb="Right",
            postop_day=8,
            surgery_date="2026-09-01",
            user_message=_RED_MESSAGE,
        )

    _check(len(calls) == 1, f"expected exactly 1 call to inspect, got {len(calls)}")
    if calls:
        payload = calls[0]
        _check(payload.get("patient_id") == "P123", "payload missing/incorrect patient_id")
        _check(payload.get("user_message") == _RED_MESSAGE, "payload missing/incorrect original patient message")
        triage = payload.get("triage") or {}
        _check(triage.get("triage_level") == "RED", "payload triage missing RED level")
        _check(bool(triage.get("reasons")), "payload triage missing reason(s)")
        _check(payload.get("surgery_type") == "Total Knee Arthroplasty", "payload missing surgery type")
        _check(payload.get("surgery_date") == "2026-09-01", "payload missing surgery date")
        _check(payload.get("postop_day") == 8, "payload missing postop day")

    # Also verify the rendered email body itself (real _build_body, no network).
    body = DoctorAlertNotifier._build_body(
        patient_id="P123",
        user_message=_RED_MESSAGE,
        triage={
            "triage_level": "RED",
            "reasons": ["severe chest pain", "difficulty breathing"],
            "action_protocol": "Contact emergency services immediately.",
        },
        surgery_type="Total Knee Arthroplasty",
        surgery_date="2026-09-01",
        postop_day=8,
    )
    for expected in (
        "RED TRIAGE ALERT",
        "Patient ID: P123",
        "Surgery: Total Knee Arthroplasty",
        "Post-Op Day: 8",
        _RED_MESSAGE,
        "severe chest pain",
        "difficulty breathing",
        "Triage Level: RED",
    ):
        _check(expected in body, f"email body missing expected content: {expected!r}")
    print("    CONFIRMED: alert payload and rendered email body contain required context.")
    print()


# ---------------------------------------------------------------------------
# C. GREEN / non-RED triage sends ZERO doctor alerts.
# ---------------------------------------------------------------------------

def run_non_red_sends_zero_alerts_test() -> None:
    print("=" * 78)
    print("C -- GREEN/non-RED triage sends zero doctor alerts")
    print("=" * 78)

    notify_fn, calls = _recording_notify()
    with patch.object(doctor_alert_notifier, "notify_red_triage_background", side_effect=notify_fn):
        result = LAMOrchestrator.process(
            patient_id="P123",
            surgery_type="Total Knee Arthroplasty",
            affected_limb="Right",
            postop_day=8,
            user_message="How many heel slides should I do today?",
        )

    print(f"    doctor alert calls = {len(calls)}, triage_level = {result.get('triage_level')}")
    _check(len(calls) == 0, f"expected 0 doctor alerts for non-RED, got {len(calls)}")
    _check(result.get("triage_level") != "RED", "unexpectedly classified a benign message as RED")
    print("    CONFIRMED: no alert sent for non-RED triage.")
    print()


# ---------------------------------------------------------------------------
# D. Notifier failure does NOT stop the RED emergency response.
# ---------------------------------------------------------------------------

def run_notifier_failure_isolated_test() -> None:
    print("=" * 78)
    print("D -- notifier failure does not break the RED emergency response")
    print("=" * 78)

    def _boom(**_kwargs):
        raise RuntimeError("SMTP server unreachable")

    with patch.object(doctor_alert_notifier, "notify_red_triage_background", side_effect=_boom):
        result = LAMOrchestrator.process(
            patient_id="P123",
            surgery_type="Total Knee Arthroplasty",
            affected_limb="Right",
            postop_day=8,
            user_message=_RED_MESSAGE,
        )

    _check(result["triage_level"] == "RED", "RED response was affected by notifier failure")
    _check(result["is_escalated"] is True, "is_escalated was affected by notifier failure")
    _check("CRITICAL EMERGENCY ALERT" in result["reply"], "patient-facing reply was affected by notifier failure")
    print("    CONFIRMED: notifier exception is isolated; RED response still returned intact.")
    print()


def run_missing_config_does_not_crash_test() -> None:
    print("=" * 78)
    print("D2 -- missing SMTP configuration does not crash and is logged, not sent")
    print("=" * 78)

    env_clear = {k: "" for k in _CONFIGURED_ENV}
    with patch.dict(os.environ, env_clear, clear=False):
        for key in _CONFIGURED_ENV:
            os.environ.pop(key, None)
        result = LAMOrchestrator.process(
            patient_id="P123",
            surgery_type="Total Knee Arthroplasty",
            affected_limb="Right",
            postop_day=8,
            user_message=_RED_MESSAGE,
        )

    _check(result["triage_level"] == "RED", "RED response was affected by missing SMTP config")
    _check("CRITICAL EMERGENCY ALERT" in result["reply"], "patient reply changed when SMTP config missing")
    print("    CONFIRMED: missing configuration does not crash and patient response is unchanged.")
    print()


# ---------------------------------------------------------------------------
# C. RED response is returned even if the underlying SMTP send would block.
# Uses a threading.Event the mocked transport waits on, rather than a sleep,
# to prove the response returns before the background send is released.
# ---------------------------------------------------------------------------

def run_background_non_blocking_test() -> None:
    print("=" * 78)
    print("C -- RED response returns without waiting on a blocking SMTP transport")
    print("=" * 78)

    entered = threading.Event()
    release = threading.Event()

    class _BlockingSMTP:
        def __enter__(self):
            entered.set()
            # Blocks here until the test explicitly releases it -- this is
            # standing in for a slow/unreachable SMTP server.
            release.wait(timeout=5)
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self):
            pass

        def login(self, *_a, **_k):
            pass

        def send_message(self, *_a, **_k):
            pass

    real_background = DoctorAlertNotifier.notify_red_triage_background
    captured_futures: List[Any] = []

    def _wrapped_background(self, **kwargs):
        future = real_background(self, **kwargs)
        captured_futures.append(future)
        return future

    with patch.dict(os.environ, _CONFIGURED_ENV, clear=False), \
         patch("doctor_alert.smtplib.SMTP", return_value=_BlockingSMTP()), \
         patch.object(DoctorAlertNotifier, "notify_red_triage_background", _wrapped_background):

        start = time.monotonic()
        result = LAMOrchestrator.process(
            patient_id="P123",
            surgery_type="Total Knee Arthroplasty",
            affected_limb="Right",
            postop_day=8,
            user_message=_RED_MESSAGE,
        )
        elapsed = time.monotonic() - start

        print(f"    orchestrator.process() returned in {elapsed:.4f}s while transport was blocked")
        _check(result["triage_level"] == "RED", "RED response was affected by a blocked background transport")
        _check("CRITICAL EMERGENCY ALERT" in result["reply"], "patient reply changed while transport was blocked")
        _check(elapsed < 1.0, f"orchestrator appears to have waited on the background SMTP transport ({elapsed:.3f}s)")

        # Confirm the background thread genuinely reached the transport
        # (proves this is real async work, not silently skipped).
        started = entered.wait(timeout=5)
        _check(started, "background alert never attempted the transport at all")

        # Release the blocked transport and confirm the background task
        # completes cleanly, all while the mock is still in place.
        release.set()
        _check(len(captured_futures) == 1, f"expected exactly 1 scheduled background alert, got {len(captured_futures)}")
        if captured_futures:
            outcome = captured_futures[0].result(timeout=5)
            _check(outcome is True, "background alert should complete successfully once unblocked")

    print("    CONFIRMED: patient response returns immediately; background send completes independently.")
    print()


# ---------------------------------------------------------------------------
# D. A background transport exception must never affect the patient RED
# response and must never propagate out of the scheduled work.
# ---------------------------------------------------------------------------

def run_background_exception_isolated_test() -> None:
    print("=" * 78)
    print("D -- background transport exception does not affect the RED response")
    print("=" * 78)

    real_background = DoctorAlertNotifier.notify_red_triage_background
    captured_futures: List[Any] = []

    def _wrapped_background(self, **kwargs):
        future = real_background(self, **kwargs)
        captured_futures.append(future)
        return future

    with patch.dict(os.environ, _CONFIGURED_ENV, clear=False), \
         patch("doctor_alert.smtplib.SMTP", side_effect=OSError("connection refused")), \
         patch.object(DoctorAlertNotifier, "notify_red_triage_background", _wrapped_background):
        result = LAMOrchestrator.process(
            patient_id="P123",
            surgery_type="Total Knee Arthroplasty",
            affected_limb="Right",
            postop_day=8,
            user_message=_RED_MESSAGE,
        )

        _check(result["triage_level"] == "RED", "RED response was affected by a background transport failure")
        _check(result["is_escalated"] is True, "is_escalated was affected by a background transport failure")
        _check("CRITICAL EMERGENCY ALERT" in result["reply"], "patient reply changed on background transport failure")

        _check(len(captured_futures) == 1, f"expected exactly 1 scheduled background alert, got {len(captured_futures)}")
        if captured_futures:
            # Future.result() is the synchronization primitive here: it
            # blocks only until the background task finishes, and re-raises
            # any exception the task raised. notify_red_triage() must have
            # already caught the transport error internally, so this must
            # return False, not raise.
            outcome = captured_futures[0].result(timeout=5)
            _check(outcome is False, "background failure should resolve to False, not raise, out of the future")

    print("    CONFIRMED: background SMTP exception is caught internally and never affects the RED response.")
    print()


# ---------------------------------------------------------------------------
# F. No duplicate alert occurs if downstream code also receives precomputed
# triage (RED short-circuits before any specialized agent dispatch, and
# ChatAgent's own direct-call RED path carries no notification wiring).
# ---------------------------------------------------------------------------

def run_no_duplicate_alert_test() -> None:
    print("=" * 78)
    print("F -- no duplicate alert when downstream also sees precomputed triage")
    print("=" * 78)

    notify_fn, calls = _recording_notify()
    dispatch_calls: List[Dict[str, Any]] = []

    def _dispatch_stub(**kwargs):
        dispatch_calls.append(kwargs)
        return {"reply": "should not be reached", "triage_level": "RED", "is_escalated": True,
                "engine": "stub", "sources": []}

    with patch.object(doctor_alert_notifier, "notify_red_triage_background", side_effect=notify_fn), \
         patch("agents.agent_router.AgentRouter.dispatch", side_effect=_dispatch_stub):
        LAMOrchestrator.process(
            patient_id="P123",
            surgery_type="Total Knee Arthroplasty",
            affected_limb="Right",
            postop_day=8,
            user_message=_RED_MESSAGE,
        )

    print(f"    doctor alert calls = {len(calls)}, downstream dispatch calls = {len(dispatch_calls)}")
    _check(len(calls) == 1, f"expected exactly 1 doctor alert, got {len(calls)}")
    _check(len(dispatch_calls) == 0, "RED must short-circuit before any specialized-agent dispatch")

    # ChatAgent's own direct-call RED path (bypassing the orchestrator) must
    # not independently trigger a doctor alert -- notification is wired only
    # at the orchestrator's single Step 1 RED branch.
    notify_fn2, calls2 = _recording_notify()
    with patch.object(doctor_alert_notifier, "notify_red_triage_background", side_effect=notify_fn2):
        ChatAgent.answer_question(
            patient_id="P123",
            surgery_type="Total Knee Arthroplasty",
            affected_limb="Right",
            postop_day=8,
            user_message=_RED_MESSAGE,
            precomputed_triage={
                "triage_level": "RED",
                "reasons": ["severe chest pain"],
                "action_protocol": "Seek emergency care.",
                "is_escalated": True,
            },
        )
    print(f"    ChatAgent direct-call (precomputed RED) alert calls = {len(calls2)}")
    _check(len(calls2) == 0, "ChatAgent must not independently send a doctor alert (would duplicate)")
    print("    CONFIRMED: exactly one alert path exists; no duplicate is possible.")
    print()


# ---------------------------------------------------------------------------
# G. Existing Recovery/Wound/Medication behavior is not modified.
# ---------------------------------------------------------------------------

def run_unrelated_behavior_unchanged_test() -> None:
    print("=" * 78)
    print("G -- unrelated (non-RED) agent behavior is unmodified")
    print("=" * 78)

    notify_fn, calls = _recording_notify()
    with patch.object(doctor_alert_notifier, "notify_red_triage_background", side_effect=notify_fn):
        wound_result = LAMOrchestrator.process(
            patient_id="P123",
            surgery_type="Total Knee Arthroplasty",
            affected_limb="Right",
            postop_day=8,
            user_message="My wound looks a bit red today.",
        )
        med_result = LAMOrchestrator.process(
            patient_id="P123",
            surgery_type="Total Knee Arthroplasty",
            affected_limb="Right",
            postop_day=8,
            user_message="When should I take my next dose of medication?",
        )

    _check(len(calls) == 0, "non-RED wound/medication queries must never trigger a doctor alert")
    _check(wound_result.get("intent") == IntentLabel.WOUND_CARE.value, "Wound Care routing changed")
    _check(med_result.get("intent") == IntentLabel.MEDICATION.value, "Medication routing changed")
    print("    CONFIRMED: Wound Care / Medication routing and behavior unaffected.")
    print()


# ---------------------------------------------------------------------------
# Real DoctorAlertNotifier against a mocked SMTP transport -- no real email
# is ever sent; smtplib.SMTP is replaced with a MagicMock.
# ---------------------------------------------------------------------------

def run_real_notifier_mocked_transport_test() -> None:
    print("=" * 78)
    print("Transport -- real DoctorAlertNotifier sends via mocked SMTP only")
    print("=" * 78)

    notifier = DoctorAlertNotifier()
    mock_smtp_instance = MagicMock()
    mock_smtp_ctx = MagicMock()
    mock_smtp_ctx.__enter__.return_value = mock_smtp_instance
    mock_smtp_ctx.__exit__.return_value = False

    with patch.dict(os.environ, _CONFIGURED_ENV, clear=False), \
         patch("doctor_alert.smtplib.SMTP", return_value=mock_smtp_ctx) as mock_smtp_cls:
        sent = notifier.notify_red_triage(
            patient_id="P123",
            user_message=_RED_MESSAGE,
            triage={
                "triage_level": "RED",
                "reasons": ["severe chest pain", "difficulty breathing"],
                "action_protocol": "Contact emergency services immediately.",
            },
            surgery_type="Total Knee Arthroplasty",
            surgery_date="2026-09-01",
            postop_day=8,
        )

    _check(sent is True, "notify_red_triage should report success when transport succeeds")
    _check(mock_smtp_cls.called, "smtplib.SMTP was never invoked -- no transport attempt made")
    _check(mock_smtp_instance.starttls.called, "starttls() was not called")
    _check(mock_smtp_instance.login.called, "login() was not called")
    _check(mock_smtp_instance.send_message.called, "send_message() was not called")
    if mock_smtp_instance.send_message.called:
        sent_message = mock_smtp_instance.send_message.call_args[0][0]
        _check(sent_message["To"] == "doctor@example.com", "email not addressed to configured DOCTOR_ALERT_EMAIL")
        _check("P123" in str(sent_message.get_content()), "email body missing patient id")

    # Transport failure must be caught and reported as False, never raised.
    with patch.dict(os.environ, _CONFIGURED_ENV, clear=False), \
         patch("doctor_alert.smtplib.SMTP", side_effect=OSError("connection refused")):
        sent_fail = notifier.notify_red_triage(
            patient_id="P123",
            user_message=_RED_MESSAGE,
            triage={"triage_level": "RED", "reasons": ["severe chest pain"]},
        )
    _check(sent_fail is False, "notify_red_triage should report failure, not raise, on transport error")
    print("    CONFIRMED: real notifier only ever talks to the mocked SMTP transport; failures are swallowed.")
    print()


# ---------------------------------------------------------------------------
# Recipient defaulting -- DOCTOR_ALERT_EMAIL absent falls back to the fixed
# prototype address; an explicit value still overrides it.
# ---------------------------------------------------------------------------

def run_default_recipient_test() -> None:
    print("=" * 78)
    print("Recipient defaulting -- DOCTOR_ALERT_EMAIL absent vs. explicit override")
    print("=" * 78)

    notifier = DoctorAlertNotifier()

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("DOCTOR_ALERT_EMAIL", None)
        _check(
            notifier.recipient == _DEFAULT_RECIPIENT,
            f"expected default recipient {_DEFAULT_RECIPIENT!r} when "
            f"DOCTOR_ALERT_EMAIL is absent, got {notifier.recipient!r}",
        )
        print(f"    DOCTOR_ALERT_EMAIL absent -> recipient = {notifier.recipient!r}")

    with patch.dict(os.environ, {"DOCTOR_ALERT_EMAIL": "override@example.com"}, clear=False):
        _check(
            notifier.recipient == "override@example.com",
            f"explicit DOCTOR_ALERT_EMAIL was not honoured, got {notifier.recipient!r}",
        )
        print(f"    DOCTOR_ALERT_EMAIL='override@example.com' -> recipient = {notifier.recipient!r}")

    print("    CONFIRMED: fixed default recipient applies only when DOCTOR_ALERT_EMAIL is unset; "
          "an explicit value always overrides it.")
    print()


# ---------------------------------------------------------------------------
# Sender defaulting -- SMTP_USERNAME (and therefore the From: address, via
# SMTP_FROM_EMAIL's fallback) defaults to the dedicated sending account.
# ---------------------------------------------------------------------------

def run_default_sender_test() -> None:
    print("=" * 78)
    print("Sender defaulting -- SMTP_USERNAME absent vs. explicit override")
    print("=" * 78)

    notifier = DoctorAlertNotifier()

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("SMTP_USERNAME", None)
        _check(
            notifier._smtp_username == _DEFAULT_SENDER,
            f"expected default sending account {_DEFAULT_SENDER!r} when "
            f"SMTP_USERNAME is absent, got {notifier._smtp_username!r}",
        )
        print(f"    SMTP_USERNAME absent -> _smtp_username = {notifier._smtp_username!r}")

    with patch.dict(os.environ, {"SMTP_USERNAME": "override-sender@example.com"}, clear=False):
        _check(
            notifier._smtp_username == "override-sender@example.com",
            f"explicit SMTP_USERNAME was not honoured, got {notifier._smtp_username!r}",
        )
        print(f"    SMTP_USERNAME='override-sender@example.com' -> _smtp_username = {notifier._smtp_username!r}")

    print(f"    CONFIRMED: fixed default sending account {_DEFAULT_SENDER!r} applies only when "
          "SMTP_USERNAME is unset; an explicit value always overrides it.")
    print()


# ---------------------------------------------------------------------------
# With only SMTP_PASSWORD supplied, the prototype defaults (recipient, host,
# port, username) must be sufficient to send -- via a mocked transport only.
# ---------------------------------------------------------------------------

def run_default_configuration_end_to_end_test() -> None:
    print("=" * 78)
    print("Defaults end-to-end -- only SMTP_PASSWORD set, rest use prototype defaults")
    print("=" * 78)

    notifier = DoctorAlertNotifier()
    mock_smtp_instance = MagicMock()
    mock_smtp_ctx = MagicMock()
    mock_smtp_ctx.__enter__.return_value = mock_smtp_instance
    mock_smtp_ctx.__exit__.return_value = False

    with patch.dict(os.environ, {"SMTP_PASSWORD": "super-secret"}, clear=False):
        for key in ("DOCTOR_ALERT_EMAIL", "SMTP_HOST", "SMTP_USERNAME", "SMTP_FROM_EMAIL", "SMTP_PORT"):
            os.environ.pop(key, None)

        with patch("doctor_alert.smtplib.SMTP", return_value=mock_smtp_ctx) as mock_smtp_cls:
            sent = notifier.notify_red_triage(
                patient_id="P123",
                user_message=_RED_MESSAGE,
                triage={"triage_level": "RED", "reasons": ["severe chest pain"]},
            )

    _check(sent is True, "expected the alert to send successfully using only prototype defaults + SMTP_PASSWORD")
    _check(mock_smtp_cls.called, "smtplib.SMTP was never invoked -- no transport attempt made")
    if mock_smtp_cls.called:
        call_args, _call_kwargs = mock_smtp_cls.call_args
        _check(call_args[0] == _DEFAULT_HOST, f"expected default SMTP host {_DEFAULT_HOST!r}, got {call_args[0]!r}")
        _check(call_args[1] == _DEFAULT_PORT, f"expected default SMTP port {_DEFAULT_PORT!r}, got {call_args[1]!r}")
    if mock_smtp_instance.send_message.called:
        sent_message = mock_smtp_instance.send_message.call_args[0][0]
        _check(
            sent_message["To"] == _DEFAULT_RECIPIENT,
            f"expected mocked email addressed to default recipient {_DEFAULT_RECIPIENT!r}, got {sent_message['To']!r}",
        )
        _check(
            sent_message["From"] == _DEFAULT_SENDER,
            f"expected mocked email sent from default sender {_DEFAULT_SENDER!r}, got {sent_message['From']!r}",
        )
    if mock_smtp_instance.login.called:
        login_args = mock_smtp_instance.login.call_args[0]
        _check(
            login_args[0] == _DEFAULT_SENDER,
            f"expected SMTP login with default sending account {_DEFAULT_SENDER!r}, got {login_args[0]!r}",
        )
    print("    CONFIRMED: with only SMTP_PASSWORD set, recipient/sender/host/port all fall back "
          "to the fixed prototype defaults (From: chatbotlammm@gmail.com, To: pranavtvm05@gmail.com) "
          "and the (mocked) send succeeds -- no real email sent.")
    print()


def main() -> int:
    run_red_sends_one_alert_test()
    run_alert_payload_contents_test()
    run_non_red_sends_zero_alerts_test()
    run_notifier_failure_isolated_test()
    run_missing_config_does_not_crash_test()
    run_background_non_blocking_test()
    run_background_exception_isolated_test()
    run_no_duplicate_alert_test()
    run_unrelated_behavior_unchanged_test()
    run_real_notifier_mocked_transport_test()
    run_default_recipient_test()
    run_default_sender_test()
    run_default_configuration_end_to_end_test()

    print("=" * 78)
    if _FAILURES:
        print(f"RESULT: {len(_FAILURES)} FAILURE(S)")
        for f in _FAILURES:
            print(f"  - {f}")
        return 1
    print("RESULT: ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
