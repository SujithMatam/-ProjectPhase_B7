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
`rvns12345@gmail.com` and can be changed with `MEDICATION_REMINDER_EMAIL`.
Email delivery requires SMTP credentials in environment variables; no
credentials are stored in the repository:

```powershell
$env:MEDICATION_REMINDER_EMAIL="rvns12345@gmail.com"
$env:REMINDER_SMTP_USER="your-sender@gmail.com"
$env:REMINDER_SMTP_PASSWORD="your-gmail-app-password"
python -m uvicorn main:app --app-dir backend --reload
```

For RED doctor alerts, use `SMTP_PASSWORD` with the `SMTP_USERNAME` account
and `DOCTOR_ALERT_EMAIL` recipient. For medication reminders, use
`REMINDER_SMTP_USER` and `REMINDER_SMTP_PASSWORD`. These are separate
configuration channels. If using `setx` on Windows, close and reopen the
terminal before starting Uvicorn; `setx` does not update an already-running
server process. You can also set variables in the current PowerShell session
with `$env:NAME="value"` before starting the backend.

Optional SMTP settings are `REMINDER_SMTP_HOST` (defaults to
`smtp.gmail.com`), `REMINDER_SMTP_PORT` (defaults to `587`), and
`REMINDER_SMTP_FROM`. The reminder status is available at
`GET /api/medications/reminders/status`; the patient schedule is available at
`GET /api/medications/schedule/{patient_id}`.

Patient records and report-derived recovery data are stored in SQLite
(`PATIENT_DATABASE_PATH`, or `backend/patients.sqlite3` by default). The
scheduler starts on application startup, polls every 30 seconds, and sends
only doctor-recorded non-PRN doses when SMTP credentials are configured.
Without SMTP credentials it logs due reminders but does not send mail.

After signing in to `/admin`, `GET /api/admin/notifications/status` reports
whether each SMTP channel has credentials present without exposing passwords.

The local admin dashboard is available at `/admin`. Sign in with the seeded
local admin account (`admin` / `admin123`) to view patient records in a table,
upload a PDF for extraction, and press **Refresh database** after extraction
to reload the persisted SQLite records. Admin API access uses a process-local
bearer token and is intended for local development only.
