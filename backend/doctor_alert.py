"""Doctor RED-triage alert notification.

Sends a single email to a configured doctor address whenever the
deterministic SafetyTriageEngine (see triage/safety_triage.py) produces a
RED triage level for a patient message. This module owns ONLY the
notification side effect -- it never influences triage determination and
never affects the patient-facing response.

Configuration is read from environment variables at send time (never
hardcoded, never logged), with prototype defaults so the patient/user is
never asked to supply a doctor email address themselves:

    DOCTOR_ALERT_EMAIL   recipient doctor address
                         (default: pranavtvm05@gmail.com for this prototype)
    SMTP_HOST            SMTP server host (default: smtp.gmail.com)
    SMTP_PORT            SMTP server port (default: 587)
    SMTP_USERNAME        SMTP auth username
                         (default: chatbotlammm@gmail.com, the dedicated
                         prototype sending account)
    SMTP_PASSWORD        SMTP auth password -- NO default, must be set via
                         environment (e.g. a Gmail App Password); never
                         hardcoded and never logged
    SMTP_FROM_EMAIL      From: address (defaults to SMTP_USERNAME, i.e.
                         chatbotlammm@gmail.com by default)

If SMTP_PASSWORD (or any other required value) is missing, the alert is
skipped and logged -- the application must never crash and RED patient
handling must be unaffected either way.

SMTP is network I/O and must never delay the patient-facing RED response.
notify_red_triage() itself stays synchronous (so it is directly testable),
but callers on the request path should use notify_red_triage_background(),
which hands the send off to a small bounded background thread pool and
returns immediately.
"""

from __future__ import annotations

import concurrent.futures
import logging
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger(__name__)

# Prototype defaults: the patient/user must never have to supply a doctor
# email address, so RED alerts default to this fixed sender/recipient pair
# unless DOCTOR_ALERT_EMAIL / SMTP_USERNAME override them. SMTP_PASSWORD has
# NO default -- it must always come from the environment (e.g. a Gmail App
# Password) and is never hardcoded or logged.
_DEFAULT_DOCTOR_ALERT_EMAIL = "pranavtvm05@gmail.com"
_DEFAULT_SMTP_HOST = "smtp.gmail.com"
_DEFAULT_SMTP_PORT = "587"
_DEFAULT_SMTP_USERNAME = "chatbotlammm@gmail.com"

# Small, bounded, module-level pool shared by all alerts -- avoids spawning
# an uncontrolled thread per RED request while keeping the send off the
# request path entirely.
_ALERT_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=2, thread_name_prefix="doctor-alert"
)


class DoctorAlertNotifier:
    """Best-effort emailer for RED-triage doctor alerts."""

    @property
    def recipient(self) -> str:
        return os.getenv("DOCTOR_ALERT_EMAIL") or _DEFAULT_DOCTOR_ALERT_EMAIL

    @property
    def _smtp_host(self) -> str:
        return os.getenv("SMTP_HOST") or _DEFAULT_SMTP_HOST

    @property
    def _smtp_username(self) -> str:
        return os.getenv("SMTP_USERNAME") or _DEFAULT_SMTP_USERNAME

    @property
    def is_configured(self) -> bool:
        return bool(
            self.recipient
            and self._smtp_host
            and self._smtp_username
            and os.getenv("SMTP_PASSWORD")
        )

    def notify_red_triage(
        self,
        *,
        patient_id: str,
        user_message: str,
        triage: Dict[str, Any],
        surgery_type: Optional[str] = None,
        surgery_date: Optional[str] = None,
        postop_day: Optional[int] = None,
    ) -> bool:
        """Send the RED alert email. Never raises: any failure is caught,
        logged, and reported back as False so the caller's patient-facing
        RED response is never affected."""
        try:
            self._send(
                patient_id=patient_id,
                user_message=user_message,
                triage=triage,
                surgery_type=surgery_type,
                surgery_date=surgery_date,
                postop_day=postop_day,
            )
            return True
        except Exception as exc:  # noqa: BLE001 -- must never propagate
            LOGGER.error("Doctor RED-triage alert failed to send: %s", exc)
            return False

    def notify_red_triage_background(
        self,
        *,
        patient_id: str,
        user_message: str,
        triage: Dict[str, Any],
        surgery_type: Optional[str] = None,
        surgery_date: Optional[str] = None,
        postop_day: Optional[int] = None,
    ) -> Optional["concurrent.futures.Future[bool]"]:
        """Non-blocking entry point for the request path.

        Schedules notify_red_triage() on the small bounded background
        executor and returns immediately -- the patient-facing RED response
        must never wait on SMTP connection/login/send. notify_red_triage()
        already catches and logs every send failure internally, so nothing
        it raises can reach this caller; scheduling itself is also wrapped
        so that even an executor-level failure can never propagate.
        """
        try:
            return _ALERT_EXECUTOR.submit(
                self.notify_red_triage,
                patient_id=patient_id,
                user_message=user_message,
                triage=triage,
                surgery_type=surgery_type,
                surgery_date=surgery_date,
                postop_day=postop_day,
            )
        except Exception as exc:  # noqa: BLE001 -- must never propagate
            LOGGER.error("Failed to schedule doctor RED-triage alert: %s", exc)
            return None

    def _send(
        self,
        *,
        patient_id: str,
        user_message: str,
        triage: Dict[str, Any],
        surgery_type: Optional[str],
        surgery_date: Optional[str],
        postop_day: Optional[int],
    ) -> None:
        if not self.is_configured:
            LOGGER.warning(
                "RED triage alert NOT sent for patient %s -- doctor alert "
                "email is not fully configured (SMTP_PASSWORD must be set "
                "via environment; DOCTOR_ALERT_EMAIL/SMTP_HOST/SMTP_USERNAME "
                "already default for this prototype).",
                patient_id,
            )
            return

        message = EmailMessage()
        message["Subject"] = f"RED TRIAGE ALERT - Patient {patient_id}"
        message["From"] = os.getenv("SMTP_FROM_EMAIL") or self._smtp_username
        message["To"] = self.recipient
        message.set_content(
            self._build_body(
                patient_id=patient_id,
                user_message=user_message,
                triage=triage,
                surgery_type=surgery_type,
                surgery_date=surgery_date,
                postop_day=postop_day,
            )
        )

        host = self._smtp_host
        port = int(os.getenv("SMTP_PORT", _DEFAULT_SMTP_PORT))
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(self._smtp_username, os.getenv("SMTP_PASSWORD"))
            smtp.send_message(message)

        LOGGER.info("RED triage alert sent to %s for patient %s", self.recipient, patient_id)

    @staticmethod
    def _build_body(
        *,
        patient_id: str,
        user_message: str,
        triage: Dict[str, Any],
        surgery_type: Optional[str],
        surgery_date: Optional[str],
        postop_day: Optional[int],
    ) -> str:
        reasons: List[str] = triage.get("reasons") or []

        lines = ["RED TRIAGE ALERT", ""]
        lines.append(f"Patient ID: {patient_id}")
        if surgery_type:
            lines.append(f"Surgery: {surgery_type}")
        if surgery_date:
            lines.append(f"Surgery Date: {surgery_date}")
        if postop_day is not None:
            lines.append(f"Post-Op Day: {postop_day}")

        lines.append("")
        lines.append("Patient message:")
        lines.append(f"\"{user_message}\"")

        lines.append("")
        lines.append("Reason(s):")
        if reasons:
            lines.extend(f"- {reason}" for reason in reasons)
        else:
            lines.append("- Not specified")

        lines.append("")
        lines.append(f"Triage Level: {triage.get('triage_level', 'RED')}")

        action_protocol = triage.get("action_protocol")
        if action_protocol:
            lines.append("")
            lines.append("Action Protocol:")
            lines.append(action_protocol)

        lines.append("")
        lines.append(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")

        return "\n".join(lines)


doctor_alert_notifier = DoctorAlertNotifier()
