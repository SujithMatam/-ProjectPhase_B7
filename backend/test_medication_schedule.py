"""Focused tests for the report medication schedule and reminder configuration."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from agents.report_agent import ReportGenerationAgent
from medication_reminders import DEFAULT_REMINDER_EMAIL, MedicationReminderService


def test_daily_schedule_expands_doctor_frequencies() -> None:
    rows = ReportGenerationAgent.get_daily_medication_schedule("PT-B7-8921")
    paracetamol = [row for row in rows if row["medication"] == "Paracetamol"]
    enoxaparin = [row for row in rows if row["medication"] == "Enoxaparin"]
    oxycodone = [row for row in rows if row["medication"] == "Oxycodone"]

    assert [row["time"] for row in paracetamol] == ["08:00", "14:00", "20:00"]
    assert [row["time"] for row in enoxaparin] == ["08:00"]
    assert oxycodone[0]["time"] == "As needed"
    assert oxycodone[0]["reminder_enabled"] is False
    assert all(row["source"] == "doctor_report" for row in rows)


def test_reminder_defaults_to_requested_recipient() -> None:
    original = {
        key: os.environ.get(key)
        for key in ("MEDICATION_REMINDER_EMAIL", "REMINDER_SMTP_USER", "REMINDER_SMTP_PASSWORD")
    }
    for key in original:
        os.environ.pop(key, None)
    service = MedicationReminderService()
    status = service.status()
    try:
        assert status["recipient"] == DEFAULT_REMINDER_EMAIL
        assert status["email_configured"] is False
    finally:
        for key, value in original.items():
            if value is not None:
                os.environ[key] = value


if __name__ == "__main__":
    test_daily_schedule_expands_doctor_frequencies()
    test_reminder_defaults_to_requested_recipient()
    print("Medication schedule tests passed")
