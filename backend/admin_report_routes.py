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
import tempfile

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from report_extractor import extract_report

router = APIRouter(prefix="/api/admin", tags=["admin"])

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


@router.post("/extract-report")
async def extract_report_endpoint(file: UploadFile = File(...)):
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

    # Write to a temp file -- pdfplumber/report_extractor works off a
    # file path, and this avoids holding the whole PDF in memory twice.
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(contents)
            tmp_path = tmp_file.name

        result = extract_report(tmp_path)

        return JSONResponse(
            content={
                "filename": file.filename,
                "extraction": result.to_dict(),
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