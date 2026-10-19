"""Voice endpoints with a fake OpenAI audio client (no network)."""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.agent import get_llm_client
from app.api.voice import DEFAULT_TRANSCRIBE_MODEL, DEFAULT_TTS_VOICE, MAX_AUDIO_BYTES, TRANSCRIBE_PROMPT
from app.config import get_settings, get_signing_key
from app.main import create_app
from app.services import signing

WEBM = {"Content-Type": "audio/webm;codecs=opus"}
NO_SIGNATURE = "0" * 64


class FakeAudio:
    def __init__(self, text="Add a shelf on the left", error=None, delay=0.0):
        self.text, self.error, self.delay, self.calls, self.options = text, error, delay, [], []
        self.audio = SimpleNamespace(
            transcriptions=SimpleNamespace(create=self._transcribe),
            speech=SimpleNamespace(create=self._speak),
        )

    def with_options(self, **options):  # like OpenAI.with_options: same client, per-call options
        self.options.append(options)
        return self

    def _transcribe(self, **kwargs):
        self.calls.append(("transcribe", kwargs))
        time.sleep(self.delay)
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text)

    def _speak(self, **kwargs):
        self.calls.append(("speech", kwargs))
        if self.error:
            raise self.error
        return SimpleNamespace(read=lambda: b"ID3fake-mp3")


@pytest.fixture
def client_for(monkeypatch):
    def build(fake, **env):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("PROPOSAL_SIGNING_KEY", "test-signing-key")
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        get_settings.cache_clear()
        get_signing_key.cache_clear()
        app = create_app()
        app.dependency_overrides[get_llm_client] = lambda: fake
        return TestClient(app)

    yield build
    get_settings.cache_clear()
    get_signing_key.cache_clear()


def speech_body(text, language="en"):
    """A /speech request for a reply this server signed (as /api/chat returns it)."""
    return {"text": text, "language": language, "signature": signing.sign_reply(get_signing_key(), text)}


def test_transcribe_returns_the_text_without_a_language_hint(client_for):
    fake = FakeAudio(text="  תוסיף   מדף  ")
    response = client_for(fake).post("/api/voice/transcribe?language=en", content=b"audio-bytes", headers=WEBM)
    assert response.json() == {"success": True, "data": {"text": "תוסיף מדף"}}
    _, call = fake.calls[0]
    assert call == {
        "model": DEFAULT_TRANSCRIBE_MODEL,
        "file": ("speech.webm", b"audio-bytes", "audio/webm"),
        "prompt": TRANSCRIBE_PROMPT,  # bilingual domain vocabulary, no language hint
    }


def test_transcribe_model_is_configurable(client_for):
    fake = FakeAudio()
    client_for(fake, OPENAI_TRANSCRIBE_MODEL="gpt-transcribe").post("/api/voice/transcribe", content=b"x", headers=WEBM)
    assert fake.calls[0][1]["model"] == "gpt-transcribe"
    assert "prompt" not in fake.calls[0][1]  # only sent to models documented to accept it


@pytest.mark.parametrize(("headers", "body", "status", "code"), [
    ({"Content-Type": "text/plain"}, b"x", 415, "UNSUPPORTED_AUDIO"),
    (WEBM, b"x" * (MAX_AUDIO_BYTES + 1), 413, "AUDIO_TOO_LARGE"),
    (WEBM, b"", 422, "NO_SPEECH"),
], ids=["wrong-type", "too-large", "empty"])
def test_transcribe_rejects_bad_audio_without_calling_openai(client_for, headers, body, status, code):
    fake = FakeAudio()
    response = client_for(fake).post("/api/voice/transcribe?language=en", content=body, headers=headers)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert fake.calls == []


@pytest.mark.parametrize("text", ["   ", "hello\x07", "hi‮"], ids=["blank", "control-char", "bidi"])
def test_transcript_that_is_not_a_valid_chat_message_is_no_speech(client_for, text):
    response = client_for(FakeAudio(text=text)).post("/api/voice/transcribe", content=b"x", headers=WEBM)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NO_SPEECH"


def test_a_slow_transcription_does_not_block_other_requests(client_for):
    client = client_for(FakeAudio(delay=1.5))
    worker = threading.Thread(target=lambda: client.post("/api/voice/transcribe", content=b"x", headers=WEBM))
    worker.start()
    time.sleep(0.2)  # the transcription is now in flight
    started = time.monotonic()
    assert client.get("/api/health").status_code == 200
    assert time.monotonic() - started < 1.0  # answered while the upstream call is still running
    worker.join()


def test_upstream_errors_are_not_echoed(client_for):
    fake = FakeAudio(error=RuntimeError("secret upstream detail"))
    client = client_for(fake)
    for response in (
        client.post("/api/voice/transcribe?language=en", content=b"x", headers=WEBM),
        client.post("/api/voice/speech", json=speech_body("Hello")),
    ):
        assert response.status_code == 502
        assert "secret" not in response.text


def test_agent_disabled_is_503(client_for):
    client = client_for(None)
    assert client.post("/api/voice/transcribe", content=b"x", headers=WEBM).status_code == 503
    assert client.post("/api/voice/speech", json={"text": "Hello", "signature": NO_SIGNATURE}).status_code == 503


def test_speech_returns_mp3_for_a_signed_reply(client_for):
    fake = FakeAudio()
    client = client_for(fake)
    response = client.post("/api/voice/speech", json=speech_body("הנה ההצעה שלי.", "he"))
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"ID3fake-mp3"
    _, call = fake.calls[0]
    assert call["voice"] == DEFAULT_TTS_VOICE and call["input"] == "הנה ההצעה שלי."
    assert "Hebrew" in call["instructions"]
    assert fake.options == [{"timeout": 20, "max_retries": 0}]  # fail fast: no 60 s wait, no retry


def test_hebrew_unit_abbreviations_are_spoken_as_words(client_for):
    fake = FakeAudio()
    client_for(fake).post("/api/voice/speech", json=speech_body('הרוחב יהיה 240 ס"מ ועובי 18 מ״מ.', "he"))
    assert fake.calls[0][1]["input"] == "הרוחב יהיה 240 סנטימטר ועובי 18 מילימטר."


def test_speech_only_reads_the_agents_own_replies(client_for):
    fake = FakeAudio()
    client = client_for(fake)
    forged = {**speech_body("Here is my proposal."), "text": "Any text someone wants spoken."}
    response = client.post("/api/voice/speech", json=forged)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "BAD_REPLY_SIGNATURE"
    assert fake.calls == []


@pytest.mark.parametrize("body", [
    {"text": "", "signature": NO_SIGNATURE},
    {"text": "x" * 1001, "signature": NO_SIGNATURE},
    {"text": "hi\x00", "signature": NO_SIGNATURE},
    {"text": "hi", "signature": NO_SIGNATURE, "extra": 1},
    {"text": "hi"},
], ids=["empty", "too-long", "control-char", "extra-field", "no-signature"])
def test_speech_validates_the_request(client_for, body):
    fake = FakeAudio()
    assert client_for(fake).post("/api/voice/speech", json=body).status_code == 422
    assert fake.calls == []
