"""Daily medication schedule and email reminder service.

The report remains the source of truth for medication names and doses. This
module only derives reminder times from the doctor's frequency notation; it
never invents a dose or changes a prescription.
"""

from __future__ import annotations

import logging
import os
import smtplib
import threading
import time
from datetime import datetime
from email.message import EmailMessage
from typing import Any, Dict, List

from agents.report_agent import ReportGenerationAgent

LOGGER = logging.getLogger(__name__)

DEFAULT_REMINDER_EMAIL = "rvns12345@gamil.com"
def build_daily_schedule(patient_id: str) -> List[Dict[str, Any]]:
    """Return today's display/reminder rows from the doctor's report."""
    return ReportGenerationAgent.get_daily_medication_schedule(patient_id)


class MedicationReminderService:
    """Small process-local scheduler for configured SMTP email reminders."""

    def __init__(self) -> None:
        self.recipient = os.getenv("MEDICATION_REMINDER_EMAIL", DEFAULT_REMINDER_EMAIL)
        self._sent: set[tuple[str, str, str]] = set()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def email_configured(self) -> bool:
        return bool(os.getenv("REMINDER_SMTP_USER") and os.getenv("REMINDER_SMTP_PASSWORD"))

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run,
            name="medication-reminder-scheduler",
            daemon=True,
        )
        self._thread.start()
        LOGGER.info("Medication reminder scheduler started for %s", self.recipient)

    def stop(self) -> None:
        self._stop.set()

    def status(self) -> Dict[str, Any]:
        return {
            "recipient": self.recipient,
            "scheduler_running": bool(self._thread and self._thread.is_alive()),
            "email_configured": self.email_configured,
            "smtp_host": os.getenv("REMINDER_SMTP_HOST", "smtp.gmail.com"),
            "note": (
                "Set REMINDER_SMTP_USER and REMINDER_SMTP_PASSWORD to send email."
                if not self.email_configured
                else "SMTP email reminders are enabled."
            ),
        }

    def _run(self) -> None:
        while not self._stop.is_set():
            now = datetime.now()
            minute = now.strftime("%H:%M")
            for patient_id in self._patient_ids():
                for row in build_daily_schedule(patient_id):
                    if row["time"] == minute and row["reminder_enabled"]:
                        key = (now.date().isoformat(), patient_id, row["medication"] + minute)
                        if key not in self._sent:
                            self._sent.add(key)
                            try:
                                self._send_email(patient_id, row)
                            except (OSError, smtplib.SMTPException, ValueError) as exc:
                                LOGGER.error(
                                    "Medication reminder delivery failed for %s: %s",
                                    row["medication"], exc,
                                )
            self._stop.wait(30)

    @staticmethod
    def _patient_ids() -> List[str]:
        return ReportGenerationAgent.known_patient_ids()

    def _send_email(self, patient_id: str, row: Dict[str, Any]) -> None:
        if not self.email_configured:
            LOGGER.warning(
                "Medication reminder due but SMTP is not configured: %s %s %s",
                patient_id, row["medication"], row["time"],
            )
            return

        message = EmailMessage()
        message["Subject"] = f"OrthoSync medication reminder: {row['medication']}"
        message["From"] = os.getenv("REMINDER_SMTP_FROM", os.environ["REMINDER_SMTP_USER"])
        message["To"] = self.recipient
        message.set_content(
            f"Medication reminder for patient {patient_id}\n\n"
            f"Medicine: {row['medication']}\n"
            f"Dose: {row['dose']}\n"
            f"Time: {row['time']}\n"
            f"Purpose: {row['purpose']}\n\n"
            "Follow the doctor's prescription label. Do not take an extra dose "
            "or change the schedule based on this reminder."
        )

        host = os.getenv("REMINDER_SMTP_HOST", "smtp.gmail.com")
        port = int(os.getenv("REMINDER_SMTP_PORT", "587"))
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(os.environ["REMINDER_SMTP_USER"], os.environ["REMINDER_SMTP_PASSWORD"])
            smtp.send_message(message)
        LOGGER.info("Medication reminder sent to %s for %s", self.recipient, row["medication"])


reminder_service = MedicationReminderService()
