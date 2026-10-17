import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from patient_database import (
    initialize_database,
    create_patient,
    authenticate_patient,
    get_patient,
)
from main import app

client = TestClient(app)


def test_patient_auth_in_database():
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tf:
        db_path = tf.name

    try:
        initialize_database(db_path)

        # 1. Create demo patient and verify demo accounts authenticate by email and ID
        create_patient({"patient_id": "PT-B7-8921", "full_name": "Rishi Priyan V N"}, path=db_path)
        demo1 = authenticate_patient("b7@amrita.edu", "password123", path=db_path)
        assert demo1 is not None
        assert demo1["patient_id"] == "PT-B7-8921"

        demo2 = authenticate_patient("PT-B7-8921", "password123", path=db_path)
        assert demo2 is not None

        # 2. Register a new patient with custom credentials
        new_data = {
            "patient_id": "PT-TEST-1001",
            "full_name": "Test User",
            "email": "testuser@amrita.edu",
            "phone_number": "+91 99999 88888",
            "password": "SecretPassword@123",
            "surgery_type": "Total Knee Arthroplasty (TKA)",
            "affected_limb": "Left",
            "surgery_date": "2026-10-10",
            "postop_day": 7,
        }
        created = create_patient(new_data, path=db_path)
        assert created["patient_id"] == "PT-TEST-1001"
        assert created.get("email") == "testuser@amrita.edu"

        # 3. Authenticate with email
        auth_by_email = authenticate_patient("testuser@amrita.edu", "SecretPassword@123", path=db_path)
        assert auth_by_email is not None
        assert auth_by_email["patient_id"] == "PT-TEST-1001"

        # 4. Authenticate with patient_id
        auth_by_id = authenticate_patient("PT-TEST-1001", "SecretPassword@123", path=db_path)
        assert auth_by_id is not None
        assert auth_by_id["patient_id"] == "PT-TEST-1001"

        # 5. Wrong password fails
        bad_auth = authenticate_patient("testuser@amrita.edu", "WrongPassword", path=db_path)
        assert bad_auth is None

        # 6. Unknown user fails
        unknown_auth = authenticate_patient("unknown@amrita.edu", "password", path=db_path)
        assert unknown_auth is None
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_api_patient_register_and_login():
    test_id = "PT-API-9999"
    test_email = "api_user_test@amrita.edu"
    test_pass = "MySecurePass99!"

    # Register via endpoint
    reg_resp = client.post(
        "/api/patient-register",
        json={
            "patient_id": test_id,
            "email": test_email,
            "full_name": "API Test Patient",
            "password": test_pass,
            "phone_number": "+91 91234 56789",
            "surgery_type": "Total Knee Arthroplasty (TKA)",
            "affected_limb": "Right",
            "surgery_date": "2026-10-12",
            "postop_day": 5,
        },
    )
    assert reg_resp.status_code in [201, 409]

    # Login with email
    login_resp = client.post(
        "/api/patient-login",
        json={"identifier": test_email, "password": test_pass},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert "patient" in data
    assert data["patient"]["patient_id"] == test_id

    # Login with patient_id
    login_id_resp = client.post(
        "/api/patient-login",
        json={"identifier": test_id, "password": test_pass},
    )
    assert login_id_resp.status_code == 200

    # Login with invalid password
    bad_resp = client.post(
        "/api/patient-login",
        json={"identifier": test_email, "password": "WrongPassword"},
    )
    assert bad_resp.status_code == 401
