"""
Voice message pipeline.

The important rule is that a successful transcript is passed to the exact
same OrthoSync LAM entry point used by typed messages. Voice input does not
create a separate safety or medical-answer path.

    audio -> transcription -> transcript -> LAMOrchestrator -> response
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from speech_to_text import MAX_AUDIO_SECONDS, TranscriptionResult

_EMERGENCY_LINE = (
    "If this is an emergency, please contact your local emergency number or "
    "your hospital right away."
)

LANGUAGE_NAMES = {
    "hi": "Hindi",
    "ta": "Tamil",
    "ml": "Malayalam",
    "te": "Telugu",
    "kn": "Kannada",
    "es": "Spanish",
    "en": "English",
}


def _failure_reply(result: TranscriptionResult) -> str:
    if result.status == "unavailable":
        body = (
            "I can't listen to voice messages on this server yet because the "
            "speech-recognition component is not available. Please type your "
            "message instead and I'll help right away."
        )
    elif result.status == "no_speech":
        body = (
            "I couldn't detect usable speech in that recording 🎤. Try speaking "
            "a little closer to the microphone in a quieter place, or type your "
            "message instead."
        )
    elif result.status == "too_long":
        minutes = MAX_AUDIO_SECONDS // 60
        body = (
            f"That voice message is too long for me. I can handle up to "
            f"{minutes} minutes per recording. Please record a shorter message "
            "or type it."
        )
    else:
        body = (
            "Sorry, I had trouble processing that voice message. Please try "
            "again, or type your message instead."
        )

    return f"{body} {_EMERGENCY_LINE}"


def _heads_up(result: TranscriptionResult) -> str:
    """Warn the patient when the transcript may differ from what they said."""
    if result.translated:
        language = LANGUAGE_NAMES.get(
            result.language or "",
            result.language or "another language",
        )
        return (
            f'(I heard this in {language} and translated it to English: '
            f'"{result.text}". If that is not what you meant, please try again '
            "or type it.)"
        )

    if result.low_confidence:
        return (
            f'(I am not fully sure I heard that correctly. I understood: '
            f'"{result.text}". If that is not what you said, please try again '
            "or type it.)"
        )

    return ""


def run_voice_pipeline(
    *,
    audio_path: str,
    transcribe_fn: Callable[[str], TranscriptionResult],
    chat_fn: Callable[[str], Dict[str, Any]],
) -> Dict[str, Any]:
    result = transcribe_fn(audio_path)

    if result.status != "ok":
        return {
            "reply": _failure_reply(result),
            "triage_level": None,
            "is_escalated": False,
            "engine": "Voice Input",
            "sources": [],
            "intent": None,
            "target_agent": None,
            "action": None,
            "scope_status": None,
            "transcript": "",
            "transcription": result.to_dict(),
        }

    # This call is deliberately the same callable used by the production
    # /api/voice/chat route to reach LAMOrchestrator.process().
    chat_result = dict(chat_fn(result.text))

    note = _heads_up(result)

    if note:
        reply = str(chat_result.get("reply", ""))
        is_red = (
            chat_result.get("triage_level") == "RED"
            or chat_result.get("is_escalated") is True
        )

        # Keep an emergency alert before any transcription-quality note.
        chat_result["reply"] = (
            f"{reply}\n\n{note}" if is_red else f"{note}\n\n{reply}"
        )

    chat_result["transcript"] = result.text
    chat_result["transcription"] = result.to_dict()

    return chat_result
