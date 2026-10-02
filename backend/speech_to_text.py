"""
Local speech-to-text for OrthoSync voice messages.

Uses faster-whisper for local speech recognition.

Voice pipeline:
    microphone audio -> Whisper -> transcript -> normal OrthoSync text path

This module does NOT infer pain, distress, or diagnosis from the person's
voice. It only converts audio into text and reports transcription quality
information.
"""

from __future__ import annotations

import math
import os
import re
import threading
import wave
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

MAX_AUDIO_SECONDS = 120

# This is only a transcription-quality warning. It never controls medical
# triage.
LOW_CONFIDENCE_AVG_LOGPROB = -1.0

# Very low RMS means the WAV is effectively silent. This is deliberately low
# so that ordinary soft speech is not rejected.
MIN_WAV_RMS = 0.001

_DOMAIN_PROMPT = (
    "Orthopedic surgery recovery: knee, hip, incision, swelling, "
    "physiotherapy, medication, pain, wound."
)


@dataclass
class TranscriptionResult:
    text: str = ""
    status: str = "ok"
    language: Optional[str] = None
    language_probability: Optional[float] = None
    translated: bool = False
    duration_seconds: Optional[float] = None
    avg_logprob: Optional[float] = None
    low_confidence: bool = False
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_model = None
_model_lock = threading.Lock()
_transcribe_lock = threading.Lock()


def _model_name() -> str:
    return os.getenv("ORTHOSYNC_WHISPER_MODEL", "base").strip() or "base"


def _device() -> str:
    return os.getenv("ORTHOSYNC_WHISPER_DEVICE", "cpu").strip() or "cpu"


def _compute_type() -> str:
    return os.getenv("ORTHOSYNC_WHISPER_COMPUTE", "int8").strip() or "int8"


def _offline() -> bool:
    return os.getenv("ORTHOSYNC_WHISPER_OFFLINE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _load_model():
    """Load the Whisper model once and reuse it for later recordings."""
    global _model

    if _model is not None:
        return _model

    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel

            _model = WhisperModel(
                _model_name(),
                device=_device(),
                compute_type=_compute_type(),
                local_files_only=_offline(),
            )

    return _model


def warm_up() -> str:
    """
    Load the model ahead of the first patient interaction.

    Example:
        python -c "from speech_to_text import warm_up; print(warm_up())"
    """
    try:
        _load_model()
        return f"Speech model '{_model_name()}' is ready."
    except ImportError:
        return "faster-whisper is not installed. Run: pip install faster-whisper"
    except Exception as exc:
        return f"Speech model could not be loaded: {exc}"


def _wav_audio_stats(audio_path: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Return (duration_seconds, normalized_rms) for a PCM WAV.

    This is only used to distinguish an actually silent recording from a
    recording where VAD may have been too aggressive.
    """
    try:
        with wave.open(audio_path, "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()

            duration = (
                frame_count / float(sample_rate)
                if sample_rate > 0
                else None
            )

            if frame_count <= 0:
                return duration, 0.0

            # We only need a robust silence estimate. The recorder currently
            # generates 16-bit PCM WAV on web, so this path covers the active
            # Chrome recording format.
            if sample_width != 2:
                return duration, None

            raw = wav_file.readframes(frame_count)

            # Compute RMS from signed little-endian int16 samples without
            # requiring NumPy or another extra dependency.
            total_sq = 0.0
            sample_count = 0

            for offset in range(0, len(raw) - 1, 2 * channels):
                for channel in range(channels):
                    index = offset + (channel * 2)
                    if index + 1 >= len(raw):
                        break

                    value = int.from_bytes(
                        raw[index:index + 2],
                        byteorder="little",
                        signed=True,
                    )
                    total_sq += float(value * value)
                    sample_count += 1

            if sample_count == 0:
                return duration, 0.0

            rms = math.sqrt(total_sq / sample_count) / 32768.0
            return duration, rms
    except (wave.Error, OSError, EOFError, ValueError):
        return None, None


def _transcribe_once(
    model,
    audio_path: str,
    *,
    language: Optional[str],
    task: str = "transcribe",
    use_vad: bool,
):
    """
    Run one Whisper pass.

    The first pass uses a deliberately tolerant VAD configuration.
    If that misses usable speech, the caller can retry without VAD.
    """
    if use_vad:
        vad_parameters = {
            # Lower than the normal 0.5 setting so quieter speech has a chance.
            "threshold": 0.35,
            "neg_threshold": 0.20,
            "min_speech_duration_ms": 100,
            "min_silence_duration_ms": 1000,
            "speech_pad_ms": 400,
        }
    else:
        vad_parameters = None

    kwargs = {
        "beam_size": 5,
        "task": task,
        "initial_prompt": _DOMAIN_PROMPT,
        "condition_on_previous_text": False,
        "temperature": 0.0,
        "vad_filter": use_vad,
    }

    if use_vad:
        kwargs["vad_parameters"] = vad_parameters
    else:
        # Make the no-VAD recovery pass less eager to reject quiet speech.
        kwargs["no_speech_threshold"] = 0.85
        kwargs["log_prob_threshold"] = -1.5

    return model.transcribe(
        audio_path,
        language=language,
        **kwargs,
    )


def _segments_to_text(segments) -> str:
    segment_list = list(segments)

    text = " ".join(
        s.text.strip()
        for s in segment_list
        if getattr(s, "text", None) and s.text.strip()
    ).strip()

    return text, segment_list


def _result_from_segments(
    text: str,
    segment_list,
    *,
    language: Optional[str],
    language_probability: Optional[float],
    translated: bool,
    duration: Optional[float],
    extra_warnings: Optional[List[str]] = None,
) -> TranscriptionResult:
    warnings = list(extra_warnings or [])

    # A punctuation-only output is not usable speech.
    if not re.sub(r"[\W_]+", "", text):
        return TranscriptionResult(
            status="no_speech",
            language=language,
            language_probability=language_probability,
            translated=translated,
            duration_seconds=duration,
            warnings=warnings,
        )

    logprobs = [
        float(s.avg_logprob)
        for s in segment_list
        if getattr(s, "avg_logprob", None) is not None
    ]

    avg_logprob = (
        sum(logprobs) / len(logprobs)
        if logprobs
        else None
    )

    low_confidence = (
        avg_logprob is not None
        and avg_logprob < LOW_CONFIDENCE_AVG_LOGPROB
    )

    return TranscriptionResult(
        text=text,
        status="ok",
        language=language,
        language_probability=language_probability,
        translated=translated,
        duration_seconds=duration,
        avg_logprob=avg_logprob,
        low_confidence=low_confidence,
        warnings=warnings,
    )


def _run_transcription(model, audio_path: str) -> TranscriptionResult:
    forced_language = os.getenv("ORTHOSYNC_STT_LANGUAGE") or None

    wav_duration, wav_rms = _wav_audio_stats(audio_path)

    # The WAV parser is diagnostic and does not replace Whisper's own decoder.
    if wav_duration is not None:
        print(
            f"[OrthoSync STT] WAV duration={wav_duration:.2f}s "
            f"rms={wav_rms if wav_rms is not None else 'unknown'}",
            flush=True,
        )

    if wav_duration is not None and wav_duration > MAX_AUDIO_SECONDS:
        return TranscriptionResult(
            status="too_long",
            duration_seconds=wav_duration,
            warnings=[
                f"Recording is {wav_duration:.0f}s; the limit is "
                f"{MAX_AUDIO_SECONDS}s."
            ],
        )

    # If this is a valid PCM WAV and it is effectively silent, do not ask
    # no-VAD Whisper to hallucinate text from silence.
    if wav_rms is not None and wav_rms < MIN_WAV_RMS:
        print(
            "[OrthoSync STT] Recording is below the silence RMS threshold.",
            flush=True,
        )
        return TranscriptionResult(
            status="no_speech",
            duration_seconds=wav_duration,
            warnings=[
                "The received WAV contained essentially no microphone signal."
            ],
        )

    # Pass 1: tolerant VAD. This keeps normal silence filtering while making
    # quieter speech easier to detect.
    segments, info = _transcribe_once(
        model,
        audio_path,
        language=forced_language,
        task="transcribe",
        use_vad=True,
    )

    duration = float(
        getattr(info, "duration", wav_duration or 0) or 0
    )
    language = getattr(info, "language", None)
    language_probability = getattr(info, "language_probability", None)

    text, segment_list = _segments_to_text(segments)

    print(
        f"[OrthoSync STT] VAD pass: language={language!r} "
        f"prob={language_probability!r} text={text!r}",
        flush=True,
    )

    if text:
        translated = False

        if language and language != "en":
            translated_segments, translated_info = _transcribe_once(
                model,
                audio_path,
                language=language,
                task="translate",
                use_vad=True,
            )

            text, segment_list = _segments_to_text(translated_segments)
            translated = True

            translated_probability = getattr(
                translated_info,
                "language_probability",
                None,
            )

            if translated_probability is not None:
                language_probability = translated_probability

        return _result_from_segments(
            text,
            segment_list,
            language=language,
            language_probability=language_probability,
            translated=translated,
            duration=duration,
        )

    # Pass 2: recovery path only when the recording contains actual signal.
    # This is the important change for microphones/rooms where VAD was too
    # conservative.
    if wav_rms is not None and wav_rms >= MIN_WAV_RMS:
        print(
            "[OrthoSync STT] VAD found no text; retrying without VAD.",
            flush=True,
        )

        retry_language = forced_language or language

        retry_segments, retry_info = _transcribe_once(
            model,
            audio_path,
            language=retry_language,
            task="transcribe",
            use_vad=False,
        )

        retry_text, retry_segment_list = _segments_to_text(retry_segments)

        retry_language = (
            getattr(retry_info, "language", None)
            or retry_language
        )

        retry_probability = getattr(
            retry_info,
            "language_probability",
            None,
        )

        retry_duration = float(
            getattr(retry_info, "duration", duration) or duration
        )

        print(
            f"[OrthoSync STT] No-VAD pass: language={retry_language!r} "
            f"prob={retry_probability!r} text={retry_text!r}",
            flush=True,
        )

        if retry_text:
            translated = False

            if retry_language and retry_language != "en":
                translated_segments, translated_info = _transcribe_once(
                    model,
                    audio_path,
                    language=retry_language,
                    task="translate",
                    use_vad=False,
                )

                retry_text, retry_segment_list = _segments_to_text(
                    translated_segments
                )
                translated = True

                translated_probability = getattr(
                    translated_info,
                    "language_probability",
                    None,
                )

                if translated_probability is not None:
                    retry_probability = translated_probability

            warnings = [
                "The first voice-activity pass found no speech, so "
                "transcription was retried directly on the recording."
            ]

            return _result_from_segments(
                retry_text,
                retry_segment_list,
                language=retry_language,
                language_probability=retry_probability,
                translated=translated,
                duration=retry_duration,
                extra_warnings=warnings,
            )

    return TranscriptionResult(
        status="no_speech",
        language=language,
        language_probability=language_probability,
        duration_seconds=duration,
        warnings=[
            "No usable speech was produced by the transcription passes."
        ],
    )


def transcribe_audio(audio_path: str) -> TranscriptionResult:
    """Never raise to the API layer; always return a structured result."""
    try:
        model = _load_model()
    except ImportError:
        return TranscriptionResult(
            status="unavailable",
            warnings=[
                "faster-whisper is not installed. Run: pip install faster-whisper"
            ],
        )
    except Exception as exc:
        return TranscriptionResult(
            status="unavailable",
            warnings=[
                f"Speech model could not be loaded: {exc}. The first run needs "
                "internet once to download the model, or set "
                "ORTHOSYNC_WHISPER_MODEL to a local model folder."
            ],
        )

    try:
        with _transcribe_lock:
            return _run_transcription(model, audio_path)
    except Exception as exc:
        return TranscriptionResult(
            status="error",
            warnings=[
                f"Transcription failed: {type(exc).__name__}: {exc}"
            ],
        )
