"""
Wound image analysis API routes.

This is intentionally a standalone endpoint for the current prototype. The
future trained wound model can replace the classical CV implementation inside
wound_cv_analysis.py without requiring a Flutter API redesign.
"""

from __future__ import annotations

import os
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from wound_cv_analysis import analyze_wound_image

router = APIRouter(prefix="/api/wound-image", tags=["wound-image"])

MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024
ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


@router.post("/analyze")
async def analyze_wound_image_endpoint(file: UploadFile = File(...)):
    """
    Accept a wound photo and analyze the actual uploaded pixels.

    The current implementation uses deterministic classical computer vision,
    not a trained medical model. The JSON response always contains the
    analysis disclaimer so callers do not treat it as a diagnosis.
    """

    filename = (file.filename or "").strip()
    extension = os.path.splitext(filename)[1].lower()

    if not filename or extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Please upload a JPG, JPEG, PNG, or WEBP image. "
                "HEIC is not enabled in the current Pillow-based prototype."
            ),
        )

    try:
        contents = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"The image upload could not be read: {exc}",
        ) from exc

    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")

    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail="The image is too large. Please upload a file smaller than 15 MB.",
        )

    tmp_path: str | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            delete=False,
            suffix=extension,
        ) as tmp_file:
            tmp_file.write(contents)
            tmp_path = tmp_file.name

        result = analyze_wound_image(tmp_path)

        return JSONResponse(
            content={
                "filename": filename,
                "analysis": result.to_dict(),
            }
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "The image was received, but the image-analysis service "
                f"could not process it: {exc}"
            ),
        ) from exc

    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

