# flutter_application_1

A new Flutter project.

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Learn Flutter](https://docs.flutter.dev/get-started/learn-flutter)
- [Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Flutter learning resources](https://docs.flutter.dev/reference/learning-resources)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.

## Medication schedule and email reminders

The clinical report displays a daily medication table derived from the
doctor's medication records. Frequency abbreviations are expanded as follows:
`OD` = 08:00, `BD` = 08:00 and 20:00, and `TDS` = 08:00, 14:00, and 20:00.
`PRN` medicines are shown as "As needed" and do not receive an automatic
reminder.

When the backend starts, its medication reminder scheduler checks the report
schedule every 30 seconds. The current recipient defaults to
`rvns12345@gamil.com` and can be changed with `MEDICATION_REMINDER_EMAIL`.
Email delivery requires SMTP credentials in environment variables; no
credentials are stored in the repository:

```powershell
$env:MEDICATION_REMINDER_EMAIL="rvns12345@gamil.com"
$env:REMINDER_SMTP_USER="your-sender@gmail.com"
$env:REMINDER_SMTP_PASSWORD="your-gmail-app-password"
python -m uvicorn main:app --app-dir backend --reload
```

Optional SMTP settings are `REMINDER_SMTP_HOST` (defaults to
`smtp.gmail.com`), `REMINDER_SMTP_PORT` (defaults to `587`), and
`REMINDER_SMTP_FROM`. The reminder status is available at
`GET /api/medications/reminders/status`; the patient schedule is available at
`GET /api/medications/schedule/{patient_id}`.
