"""
Admin Report Extraction API.

Add this router to your existing FastAPI app, e.g. in main.py:

    from admin_report_routes import router as admin_report_router
    app.include_router(admin_report_router)

This does NOT touch /api/chat or any existing patient-facing endpoint --
it's a new, separate route for the admin dashboard only.
"""

from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from report_extractor import extract_report
from patient_database import create_patient, save_source_report
import sqlite3

router = APIRouter(prefix="/api/admin", tags=["admin"])

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


@router.post("/extract-report")
async def extract_report_endpoint(file: UploadFile = File(...), patient_id: str | None = None):
    """
    Accepts a single uploaded PDF, runs the dynamic extraction pipeline,
    and returns the structured fields as JSON.

    This is intentionally synchronous/blocking on the LLM call -- for an
    admin uploading one report at a time and watching the result appear,
    that's the right trade-off over adding background job infrastructure
    under time pressure. If batch upload becomes a requirement later,
    this endpoint is the natural place to add a queue.
    """

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    contents = await file.read()

    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 20MB).")

    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Keep the upload in a project-local staging directory.  This avoids
    # relying on an OS temp directory and keeps extraction cleanup explicit.
    tmp_path = None
    try:
        staging_dir = os.path.join(os.path.dirname(__file__), ".report_uploads")
        os.makedirs(staging_dir, exist_ok=True)
        tmp_path = os.path.join(staging_dir, f"{uuid.uuid4().hex}.pdf")
        with open(tmp_path, "wb") as tmp_file:
            tmp_file.write(contents)

        result = extract_report(tmp_path)
        extraction = result.to_dict()
        linked_patient_id = patient_id.strip().upper() if patient_id else None
        if extraction.get("full_name"):
            # Persist only values explicitly extracted from the report.  A
            # supplied ID links the source report; otherwise create a new
            # stable record ID without guessing any clinical values.
            if not linked_patient_id:
                linked_patient_id = f"PT-{uuid.uuid4().hex[:12].upper()}"
            extracted_patient = {
                "patient_id": linked_patient_id,
                "full_name": extraction["full_name"],
                "age": int(extraction["age"]) if str(extraction.get("age", "")).isdigit() else None,
                "gender": extraction.get("sex"),
                "surgery_type": extraction.get("surgery_type"),
                "surgery_date": extraction.get("surgery_date"),
                "current_medications": [
                    {"name": medication}
                    for medication in extraction.get("prescriptions", [])
                ],
            }
            try:
                create_patient(extracted_patient)
            except sqlite3.IntegrityError:
                if not patient_id:
                    raise HTTPException(
                        status_code=409,
                        detail="Generated patient ID already exists; please retry the upload.",
                    )
        save_source_report(linked_patient_id, file.filename, extraction)

        return JSONResponse(
            content={
                "filename": file.filename,
                "extraction": extraction,
                "source_report_saved": True,
                "patient_id": linked_patient_id,
            }
        )

    except Exception as exc:
        # Never let an unexpected extraction error leak a raw traceback
        # to the admin dashboard -- log it server-side in a real
        # deployment; here, return a clean, actionable message.
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed unexpectedly: {exc}",
        )

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)