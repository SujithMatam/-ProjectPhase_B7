"""
Isolated runner for the three agent test suites.

    .venv/Scripts/python.exe run_agent_tests.py [extra pytest args]

What it does before invoking pytest:
    1. Points PATIENT_DATABASE_PATH at a FRESH temp sqlite file, so no test
       can read from or write to the real backend/patients.sqlite3 dev
       database (test_pain_symptoms_agent.py additionally overrides this
       with its own temp file; both are isolated from the real DB).
    2. Clears every environment variable whose name contains "SMTP" or
       "DOCTOR_ALERT", so no test run can ever send a real doctor-alert
       e-mail.
    3. Runs pytest (from backend/.venv) on exactly:
           test_pain_symptoms_agent.py
           test_recovery_progress_agent.py
           test_rehabilitation_agent.py

The three suites are plain-Python scripts whose `_check()` raises
AssertionError, so pytest reports a real failure for every failed check
(their own `main()` runners still work and print a summary too).

Any extra command-line arguments are forwarded to pytest verbatim
(e.g. `-k pain`, `-x`, `-q`).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
VENV_PYTHON = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    VENV_PYTHON = BACKEND_DIR / ".venv" / "bin" / "python"

TEST_FILES = (
    "test_pain_symptoms_agent.py",
    "test_recovery_progress_agent.py",
    "test_rehabilitation_agent.py",
)


def _isolated_environment() -> dict:
    env = dict(os.environ)
    for key in list(env):
        upper = key.upper()
        if "SMTP" in upper or "DOCTOR_ALERT" in upper:
            del env[key]

    temp_dir = tempfile.mkdtemp(prefix="agent_tests_")
    env["PATIENT_DATABASE_PATH"] = os.path.join(temp_dir, "patients.sqlite3")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def main(argv: list) -> int:
    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    env = _isolated_environment()
    print(f"[run_agent_tests] python={python}")
    print(f"[run_agent_tests] PATIENT_DATABASE_PATH={env['PATIENT_DATABASE_PATH']}")
    print("[run_agent_tests] SMTP*/DOCTOR_ALERT* variables cleared")

    command = [python, "-m", "pytest", *TEST_FILES, "-p", "no:cacheprovider", *argv]
    if not any(arg.startswith("-q") or arg.startswith("-v") for arg in argv):
        command.append("-q")
    completed = subprocess.run(command, cwd=str(BACKEND_DIR), env=env)
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
