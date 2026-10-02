"""
Unit tests for speech_to_text.py and voice_pipeline.py.

These tests use a fake faster-whisper-compatible model, so they validate our
pipeline logic without requiring a real Whisper model or microphone.
They do NOT measure transcription accuracy on real speech.
"""

import speech_to_text as stt
from voice_pipeline import run_voice_pipeline


class Seg:
    def __init__(self, text, avg_logprob=-0.3):
        self.text = text
        self.avg_logprob = avg_logprob
        self.no_speech_prob = 0.01


class Info:
    def __init__(self, language="en", duration=5.0, language_probability=0.98):
        self.language = language
        self.duration = duration
        self.language_probability = language_probability


class FakeModel:
    """One (segments, info) pair is consumed for each transcribe() call."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def transcribe(self, path, **kwargs):
        self.calls.append(kwargs)
        segments, info = self.script.pop(0)

        def lazy():
            yield from segments

        return lazy(), info


class ExplodingSegments:
    def __iter__(self):
        raise AssertionError(
            "segments were consumed for an over-long recording"
        )


def use_model(model):
    stt._load_model = lambda: model


def test_english_ok():
    m = FakeModel([
        ([Seg("My knee is swollen."), Seg("It hurts.")], Info())
    ])
    use_model(m)
    r = stt.transcribe_audio("x.wav")
    assert r.status == "ok"
    assert r.text == "My knee is swollen. It hurts."
    assert not r.translated
    assert not r.low_confidence
    assert len(m.calls) == 1


def test_silence_is_no_speech():
    use_model(FakeModel([([], Info())]))
    assert stt.transcribe_audio("x.wav").status == "no_speech"


def test_punctuation_only_is_no_speech():
    use_model(FakeModel([([Seg("..."), Seg(" . ")], Info())]))
    assert stt.transcribe_audio("x.wav").status == "no_speech"


def test_non_english_is_translated():
    m = FakeModel([
        ([Seg("ignored first pass")], Info(language="hi")),
        ([Seg("I have chest pain.")], Info(language="hi")),
    ])
    use_model(m)
    r = stt.transcribe_audio("x.wav")
    assert r.status == "ok"
    assert r.translated
    assert r.language == "hi"
    assert r.text == "I have chest pain."
    assert len(m.calls) == 2
    assert m.calls[1]["task"] == "translate"
    assert m.calls[1]["language"] == "hi"


def test_low_confidence_flag():
    use_model(FakeModel([
        ([Seg("mumbled", avg_logprob=-1.4)], Info())
    ]))
    r = stt.transcribe_audio("x.wav")
    assert r.status == "ok"
    assert r.low_confidence


def test_too_long_is_rejected_before_consuming_segments():
    use_model(FakeModel([
        (ExplodingSegments(), Info(duration=500.0))
    ]))
    r = stt.transcribe_audio("x.wav")
    assert r.status == "too_long"


def test_engine_not_installed():
    def raise_import():
        raise ImportError("no faster_whisper")

    stt._load_model = raise_import
    r = stt.transcribe_audio("x.wav")
    assert r.status == "unavailable"
    assert "pip install faster-whisper" in r.warnings[0]


def test_engine_crash_is_contained():
    class Boom:
        def transcribe(self, *args, **kwargs):
            raise RuntimeError("decode failed")

    use_model(Boom())
    r = stt.transcribe_audio("x.wav")
    assert r.status == "error"
    assert "decode failed" in r.warnings[0]


def ok_result(text="my calf is swollen", **kwargs):
    return stt.TranscriptionResult(text=text, status="ok", **kwargs)


def make_chat(reply="chat reply", **extra):
    seen = []

    def chat_fn(text):
        seen.append(text)
        return {
            "reply": reply,
            "triage_level": "GREEN",
            "is_escalated": False,
            "engine": "x",
            "sources": [],
            "intent": "pain_symptoms",
            "target_agent": "PainSymptomsAgent",
            "action": "assess",
            "scope_status": "in_scope",
            **extra,
        }

    return chat_fn, seen


def test_transcript_reaches_chat_function_unchanged():
    chat_fn, seen = make_chat()
    out = run_voice_pipeline(
        audio_path="x",
        transcribe_fn=lambda p: ok_result(),
        chat_fn=chat_fn,
    )
    assert seen == ["my calf is swollen"]
    assert out["transcript"] == "my calf is swollen"
    assert out["reply"] == "chat reply"
    assert out["triage_level"] == "GREEN"


def test_failures_never_reach_chat_and_never_fake_triage():
    for status in ("unavailable", "no_speech", "too_long", "error"):
        chat_fn, seen = make_chat()
        res = stt.TranscriptionResult(status=status)
        out = run_voice_pipeline(
            audio_path="x",
            transcribe_fn=lambda p, r=res: r,
            chat_fn=chat_fn,
        )
        assert seen == [], status
        assert out["triage_level"] is None, status
        assert out["is_escalated"] is False, status
        assert "emergency" in out["reply"].lower(), status
        assert out["transcript"] == "", status


def test_low_confidence_adds_check_note_before_normal_reply():
    chat_fn, _ = make_chat()
    res = ok_result(low_confidence=True)
    out = run_voice_pipeline(
        audio_path="x",
        transcribe_fn=lambda p: res,
        chat_fn=chat_fn,
    )
    assert out["reply"].endswith("chat reply")
    assert "not fully sure" in out["reply"]


def test_translation_note_names_the_language():
    chat_fn, _ = make_chat()
    res = ok_result(translated=True, language="ml")
    out = run_voice_pipeline(
        audio_path="x",
        transcribe_fn=lambda p: res,
        chat_fn=chat_fn,
    )
    assert "Malayalam" in out["reply"]
    assert "translated" in out["reply"]


def test_emergency_alert_stays_first_and_escalation_is_preserved():
    alert = "CRITICAL EMERGENCY ALERT: go to the ER"
    chat_fn, _ = make_chat(
        reply=alert,
        triage_level="RED",
        is_escalated=True,
    )
    res = ok_result(low_confidence=True)
    out = run_voice_pipeline(
        audio_path="x",
        transcribe_fn=lambda p: res,
        chat_fn=chat_fn,
    )
    assert out["reply"].startswith(alert)
    assert out["triage_level"] == "RED"
    assert out["is_escalated"] is True


if __name__ == "__main__":
    tests = [
        (name, fn)
        for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    ]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception as exc:
            failed += 1
            print(f"FAIL  {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
