import base64
import json
import struct
from pathlib import Path

import pytest

from app.config import Settings
from app.services import tts_service
from app.services.tts_service import DashScopeHttpTTSProvider, OpenAICompatibleTTSProvider, TTSProviderError, TTSService


def _pcm_wav(*, sample_rate_hz: int = 24000, channels: int = 1, samples: bytes = b"\x00\x00" * 240) -> bytes:
    byte_rate = sample_rate_hz * channels * 2
    fmt_chunk = struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, channels, sample_rate_hz, byte_rate, channels * 2, 16)
    data_chunk = struct.pack("<4sI", b"data", len(samples)) + samples
    return struct.pack("<4sI4s", b"RIFF", 4 + len(fmt_chunk) + len(data_chunk), b"WAVE") + fmt_chunk + data_chunk


def _wav_with_streaming_data_size(*, samples: bytes = b"\x00\x00" * 240) -> bytes:
    wav = bytearray(_pcm_wav(samples=samples))
    struct.pack_into("<I", wav, 40, 0x7FFFFFFF)
    return bytes(wav)


class _Provider:
    provider_name = "test_provider"

    def __init__(self, wav_bytes: bytes) -> None:
        self.wav_bytes = wav_bytes
        self.calls: list[dict[str, str]] = []

    def synthesize(self, *, content: str, voice_id: str) -> bytes:
        self.calls.append({"content": content, "voice_id": voice_id})
        return self.wav_bytes


def _real_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "tts_mode": "openai_compatible",
        "tts_provider_endpoint": "https://tts.example.test/v1/audio/speech",
        "tts_provider_api_key": "secret",
        "tts_provider_model": "speech-model",
        "tts_default_voice": "default-voice",
        "tts_voice_map": {"char_a": "voice-a"},
        "tts_output_sample_rate_hz": 24000,
    }
    values.update(overrides)
    return Settings(**values)


def _dashscope_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "tts_mode": "dashscope_http",
        "tts_provider_endpoint": "https://workspace.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer",
        "tts_provider_api_key": "secret",
        "tts_provider_model": "qwen-audio-3.0-tts-flash",
        "tts_default_voice": "default-voice",
        "tts_voice_map": {"char_a": "voice-a"},
        "tts_output_sample_rate_hz": 24000,
    }
    values.update(overrides)
    return Settings(**values)


def test_stub_mode_preserves_a_presentation_only_stub_payload() -> None:
    audio = TTSService(configuration=Settings(tts_default_voice="default-voice")).synthesize("char_a", "hello")

    assert audio.mode == "stub"
    assert audio.status == "stub"
    assert audio.provider == "stub"
    assert audio.voice_id == "default-voice"
    assert audio.payload is None


def test_real_provider_clip_uses_actor_voice_mapping_and_base64_wav_contract() -> None:
    provider = _Provider(_pcm_wav())
    audio = TTSService(configuration=_real_settings(), provider=provider).synthesize("char_a", "hello")

    assert provider.calls == [{"content": "hello", "voice_id": "voice-a"}]
    assert audio.mode == "clip"
    assert audio.status == "ready"
    assert audio.provider == "test_provider"
    assert audio.voice_id == "voice-a"
    assert audio.content_type == "audio/wav"
    assert audio.sample_rate_hz == 24000
    assert audio.channels == 1
    assert audio.sample_format == "pcm_s16le"
    assert base64.b64decode(audio.payload or "") == _pcm_wav()


def test_invalid_provider_audio_falls_back_to_stub_without_raising() -> None:
    provider = _Provider(_pcm_wav(sample_rate_hz=16000))
    audio = TTSService(configuration=_real_settings(), provider=provider).synthesize("char_a", "hello")

    assert audio.mode == "stub"
    assert audio.status == "fallback"
    assert audio.fallback_reason == "provider_unavailable:char_a"


def test_provider_audio_larger_than_the_encoded_payload_budget_falls_back_to_stub() -> None:
    provider = _Provider(_pcm_wav())
    audio = TTSService(configuration=_real_settings(tts_max_encoded_payload_bytes=4), provider=provider).synthesize(
        "char_a", "hello"
    )

    assert audio.mode == "stub"
    assert audio.status == "fallback"


def test_streaming_wav_data_size_uses_available_complete_pcm_bytes() -> None:
    provider = _Provider(_wav_with_streaming_data_size())
    audio = TTSService(configuration=_real_settings(), provider=provider).synthesize("char_a", "hello")

    assert audio.mode == "clip"
    assert audio.status == "ready"
    assert audio.sample_rate_hz == 24000
    assert audio.channels == 1
    assert audio.duration_ms == 10


def test_openai_compatible_provider_uses_wav_request_shape(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _Response:
        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return _pcm_wav()

    def fake_urlopen(request: object, *, timeout: float) -> _Response:
        captured["request"] = request
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(tts_service, "urlopen", fake_urlopen)
    provider = OpenAICompatibleTTSProvider(_real_settings(tts_provider_timeout_seconds=3.5))

    assert provider.synthesize(content="hello", voice_id="voice-a") == _pcm_wav()
    request = captured["request"]
    assert request is not None
    assert json.loads(request.data) == {
        "model": "speech-model",
        "input": "hello",
        "voice": "voice-a",
        "response_format": "wav",
        "sample_rate": 24000,
    }
    assert captured["timeout"] == 3.5


def test_openai_compatible_provider_requires_complete_configuration() -> None:
    with pytest.raises(TTSProviderError):
        OpenAICompatibleTTSProvider(Settings(tts_mode="openai_compatible"))


def test_dashscope_http_provider_posts_synthesis_request_then_downloads_wav(monkeypatch) -> None:
    captured: list[object] = []

    class _Response:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return self._payload

    def fake_urlopen(request: object, *, timeout: float) -> _Response:
        captured.append((request, timeout))
        if len(captured) == 1:
            return _Response(json.dumps({"output": {"audio": {"url": "https://download.example.test/clip.wav"}}}).encode())
        return _Response(_pcm_wav())

    monkeypatch.setattr(tts_service, "urlopen", fake_urlopen)
    provider = DashScopeHttpTTSProvider(_dashscope_settings(tts_provider_timeout_seconds=3.5))

    assert provider.synthesize(content="hello", voice_id="voice-a") == _pcm_wav()
    synthesis_request, synthesis_timeout = captured[0]
    assert json.loads(synthesis_request.data) == {
        "model": "qwen-audio-3.0-tts-flash",
        "input": {
            "text": "hello",
            "voice": "voice-a",
            "format": "wav",
            "sample_rate": 24000,
        },
    }
    assert synthesis_request.get_method() == "POST"
    assert synthesis_request.get_header("Authorization") == "Bearer secret"
    assert synthesis_request.get_header("Accept") == "application/json"
    assert synthesis_timeout == 3.5
    download_request, download_timeout = captured[1]
    assert download_request.full_url == "https://download.example.test/clip.wav"
    assert download_request.get_method() == "GET"
    assert download_request.get_header("Accept") == "audio/wav"
    assert download_timeout == 3.5


def test_dashscope_http_provider_rejects_missing_or_non_https_audio_url(monkeypatch) -> None:
    class _Response:
        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"output": {"audio": {"url": "http://download.example.test/clip.wav"}}}).encode()

    monkeypatch.setattr(tts_service, "urlopen", lambda *_args, **_kwargs: _Response())
    provider = DashScopeHttpTTSProvider(_dashscope_settings())

    with pytest.raises(TTSProviderError, match="HTTPS audio URL"):
        provider.synthesize(content="hello", voice_id="voice-a")


def test_dashscope_http_provider_upgrades_aliyuncs_download_urls_to_https() -> None:
    assert (
        DashScopeHttpTTSProvider._extract_audio_url(
            {"output": {"audio": {"url": "http://dashscope.oss-cn-beijing.aliyuncs.com/clip.wav?signature=redacted"}}}
        )
        == "https://dashscope.oss-cn-beijing.aliyuncs.com/clip.wav?signature=redacted"
    )


def test_dashscope_http_provider_requires_complete_configuration() -> None:
    with pytest.raises(TTSProviderError):
        DashScopeHttpTTSProvider(Settings(tts_mode="dashscope_http"))


def test_dashscope_http_provider_rejects_an_unexpanded_workspace_endpoint() -> None:
    with pytest.raises(TTSProviderError, match="configured Workspace ID"):
        DashScopeHttpTTSProvider(
            _dashscope_settings(
                tts_provider_endpoint="https://{llm-uecs5ipu21w5ilrh}.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer"
            )
        )


def test_dashscope_http_missing_workspace_id_falls_back_to_stub() -> None:
    audio = TTSService(
        configuration=_dashscope_settings(
            tts_provider_endpoint="https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer"
        )
    ).synthesize("char_a", "hello")

    assert audio.mode == "stub"
    assert audio.status == "fallback"
    assert audio.fallback_reason == "provider_unavailable:char_a"


def test_godot_voice_controller_consumes_the_complete_wav_contract() -> None:
    project_root = Path(__file__).resolve().parents[2]
    controller_source = (project_root / "scripts" / "audio" / "SpatialVoiceController.gd").read_text(encoding="utf-8")
    replica_source = (project_root / "scripts" / "character" / "CharacterReplica.gd").read_text(encoding="utf-8")
    live_probe_source = (project_root / "scripts" / "verification" / "TTSGodotLivePlaybackProbe.gd").read_text(encoding="utf-8")
    bridge_source = (project_root / "scripts" / "autoload" / "BackendBridge.gd").read_text(encoding="utf-8")

    assert "Marshalls.base64_to_raw(encoded)" in controller_source
    assert "func _decode_pcm_wav" in controller_source
    assert "chunk_id == \"data\" and data_end > wav_bytes.size()" in controller_source
    assert "AudioStreamWAV.new()" in controller_source
    assert "voice_clip_played:" in controller_source
    assert "voice.play_voice(payload)" in replica_source
    assert "tts_godot_playback_verified" in live_probe_source
    assert "voice.play_voice(payload)" in live_probe_source
    assert "ws.inbound_buffer_size = 1024 * 1024" in bridge_source
