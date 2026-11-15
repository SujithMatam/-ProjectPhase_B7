"""
FastAPI routes for OrthoSync voice messages.

POST /api/voice/chat accepts multipart form data containing:
    file          WAV/MP3/M4A/AAC/OGG/OPUS/WEBM/MP4/FLAC
    patient_id
    surgery_type
    affected_limb
    postop_day
    surgery_date
    chat_history  JSON list of prior turns

After transcription, the transcript goes through the same
LAMOrchestrator.process() path used by typed chat.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from lam.orchestrator import LAMOrchestrator
from speech_to_text import transcribe_audio
from voice_pipeline import run_voice_pipeline

router = APIRouter(prefix="/api/voice", tags=["voice"])

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = (
    ".wav",
    ".mp3",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".webm",
    ".mp4",
    ".flac",
)
MAX_HISTORY_TURNS = 20


def _parse_chat_history(raw: Optional[str]) -> List[Dict[str, str]]:
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="chat_history must be valid JSON.",
        ) from exc

    if not isinstance(data, list):
        raise HTTPException(
            status_code=400,
            detail="chat_history must be a JSON list.",
        )

    cleaned: List[Dict[str, str]] = []
    for item in data:
        if isinstance(item, dict):
            cleaned.append({str(key): str(value) for key, value in item.items()})

    return cleaned[-MAX_HISTORY_TURNS:]


@router.post("/chat")
def voice_chat(
    file: UploadFile = File(...),
    patient_id: str = Form("PT-B7-8921"),
    surgery_type: str = Form("Total Knee Arthroplasty (TKA)"),
    affected_limb: str = Form("Right"),
    postop_day: int = Form(3),
    surgery_date: Optional[str] = Form(None),
    chat_history: Optional[str] = Form(None),
):
    filename = (file.filename or "").strip()
    extension = os.path.splitext(filename)[1].lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported audio type. Allowed: "
                + ", ".join(ALLOWED_EXTENSIONS)
            ),
        )

    patient_id = patient_id.strip()
    if not patient_id:
        raise HTTPException(
            status_code=400,
            detail="patient_id must not be blank.",
        )

    history = _parse_chat_history(chat_history)

    try:
        contents = file.file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"The recording could not be read: {exc}",
        ) from exc

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="The recording is empty.",
        )

    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail="The recording is too large (maximum 25 MB).",
        )

    def chat_fn(text: str):
        # Safety triage is performed on the actual transcript before any
        # downstream scope/intent/agent generation, exactly like /api/chat.
        return LAMOrchestrator.process(
            patient_id=patient_id,
            surgery_type=surgery_type,
            affected_limb=affected_limb,
            postop_day=postop_day,
            surgery_date=surgery_date,
            user_message=text,
            chat_history=history,
        )

    tmp_path: Optional[str] = None

    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=extension,
        ) as tmp_file:
            tmp_file.write(contents)
            tmp_path = tmp_file.name

        result = run_voice_pipeline(
            audio_path=tmp_path,
            transcribe_fn=transcribe_audio,
            chat_fn=chat_fn,
        )

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Voice message failed unexpectedly: {exc}",
        ) from exc
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
