import base64
import json
import struct
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.config import Settings, settings
from app.models.dialogue_audio import DialogueAudio
from app.services.tts_voice_profiles import TTSVoiceProfileError, TTSVoiceProfileResolver


class TTSProviderError(RuntimeError):
    pass


class TTSProvider(Protocol):
    """Adapter boundary for a provider that returns one complete PCM WAV clip."""

    provider_name: str

    def synthesize(self, *, content: str, voice_id: str) -> bytes: ...


@dataclass(frozen=True)
class _PcmWavInfo:
    sample_rate_hz: int
    channels: int
    duration_ms: int


class OpenAICompatibleTTSProvider:
    """HTTP slot for providers accepting OpenAI's /audio/speech request shape."""

    provider_name = "openai_compatible"

    def __init__(self, configuration: Settings) -> None:
        if not configuration.tts_provider_endpoint or not configuration.tts_provider_api_key or not configuration.tts_provider_model:
            raise TTSProviderError("openai_compatible TTS requires endpoint, API key, and model")
        self._endpoint = configuration.tts_provider_endpoint
        self._api_key = configuration.tts_provider_api_key
        self._model = configuration.tts_provider_model
        self._sample_rate_hz = configuration.tts_output_sample_rate_hz
        self._timeout_seconds = configuration.tts_provider_timeout_seconds

    def synthesize(self, *, content: str, voice_id: str) -> bytes:
        body = json.dumps(
            {
                "model": self._model,
                "input": content,
                "voice": voice_id,
                "response_format": "wav",
                "sample_rate": self._sample_rate_hz,
            }
        ).encode("utf-8")
        request = Request(
            self._endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "audio/wav",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise TTSProviderError("TTS provider request failed") from exc


class DashScopeHttpTTSProvider:
    """DashScope non-realtime TTS adapter returning the downloaded complete WAV clip."""

    provider_name = "dashscope_http"

    def __init__(self, configuration: Settings) -> None:
        if not configuration.tts_provider_endpoint or not configuration.tts_provider_api_key or not configuration.tts_provider_model:
            raise TTSProviderError("dashscope_http TTS requires endpoint, API key, and model")
        endpoint = urlparse(configuration.tts_provider_endpoint)
        if (
            endpoint.scheme != "https"
            or not endpoint.netloc
            or "{" in endpoint.netloc
            or "}" in endpoint.netloc
        ):
            raise TTSProviderError("dashscope_http TTS endpoint requires a configured Workspace ID")
        self._endpoint = configuration.tts_provider_endpoint
        self._api_key = configuration.tts_provider_api_key
        self._model = configuration.tts_provider_model
        self._sample_rate_hz = configuration.tts_output_sample_rate_hz
        self._timeout_seconds = configuration.tts_provider_timeout_seconds

    def synthesize(self, *, content: str, voice_id: str) -> bytes:
        body = json.dumps(
            {
                "model": self._model,
                "input": {
                    "text": content,
                    "voice": voice_id,
                    "format": "wav",
                    "sample_rate": self._sample_rate_hz,
                },
            }
        ).encode("utf-8")
        request = Request(
            self._endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                response_payload = json.loads(response.read())
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            raise TTSProviderError("DashScope TTS synthesis request failed") from exc

        audio_url = self._extract_audio_url(response_payload)
        download_request = Request(audio_url, headers={"Accept": "audio/wav"}, method="GET")
        try:
            with urlopen(download_request, timeout=self._timeout_seconds) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise TTSProviderError("DashScope TTS audio download failed") from exc

    @staticmethod
    def _extract_audio_url(response_payload: object) -> str:
        if not isinstance(response_payload, dict):
            raise TTSProviderError("DashScope TTS response must be a JSON object")
        output = response_payload.get("output")
        if not isinstance(output, dict):
            raise TTSProviderError("DashScope TTS response is missing output")
        audio = output.get("audio")
        audio_url = audio.get("url") if isinstance(audio, dict) else output.get("audio_url")
        if not isinstance(audio_url, str):
            raise TTSProviderError("DashScope TTS response did not include an HTTPS audio URL")
        parsed = urlparse(audio_url)
        if parsed.scheme == "http" and parsed.hostname and parsed.hostname.endswith(".aliyuncs.com"):
            parsed = parsed._replace(scheme="https")
            return parsed.geturl()
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise TTSProviderError("DashScope TTS response did not include an HTTPS audio URL")
        return audio_url


class TTSService:
    def __init__(self, *, configuration: Settings | None = None, provider: TTSProvider | None = None) -> None:
        self._configuration = configuration or settings
        self._provider = provider
        self._voice_profile_resolver = TTSVoiceProfileResolver(self._configuration)

    def synthesize(self, actor_id: str, content: str) -> DialogueAudio:
        voice_id = self._legacy_voice_id(actor_id)
        if self._configuration.tts_mode == "stub":
            return self._stub_audio(actor_id=actor_id, voice_id=voice_id)

        try:
            voice_id = self.resolve_voice_id(actor_id)
            provider = self._provider or self._build_provider()
            wav_bytes = provider.synthesize(content=content, voice_id=voice_id)
            wav = _inspect_pcm_wav(wav_bytes, expected_sample_rate_hz=self._configuration.tts_output_sample_rate_hz)
            encoded_payload = base64.b64encode(wav_bytes).decode("ascii")
            if len(encoded_payload) > self._configuration.tts_max_encoded_payload_bytes:
                raise TTSProviderError("provider WAV exceeds the configured encoded payload budget")
        except (TTSProviderError, TTSVoiceProfileError):
            return self._fallback_audio(actor_id=actor_id, voice_id=voice_id)

        return DialogueAudio(
            mode="clip",
            status="ready",
            provider=provider.provider_name,
            voice_id=voice_id,
            content_type="audio/wav",
            encoding="base64",
            payload=encoded_payload,
            sample_rate_hz=wav.sample_rate_hz,
            channels=wav.channels,
            sample_format="pcm_s16le",
            duration_ms=wav.duration_ms,
        )

    def resolve_voice_id(self, actor_id: str) -> str:
        """Resolve an approved presentation binding or retain the legacy map."""
        resolved = self._voice_profile_resolver.resolve(actor_id)
        return resolved if resolved is not None else self._legacy_voice_id(actor_id)

    def _legacy_voice_id(self, actor_id: str) -> str:
        return self._configuration.tts_voice_map.get(actor_id, self._configuration.tts_default_voice)

    def _build_provider(self) -> TTSProvider:
        if self._configuration.tts_mode == "openai_compatible":
            return OpenAICompatibleTTSProvider(self._configuration)
        if self._configuration.tts_mode == "dashscope_http":
            return DashScopeHttpTTSProvider(self._configuration)
        raise TTSProviderError("unsupported TTS mode")

    @staticmethod
    def _stub_audio(*, actor_id: str, voice_id: str) -> DialogueAudio:
        return DialogueAudio(
            mode="stub",
            status="stub",
            provider="stub",
            voice_id=voice_id,
            fallback_reason=f"stub://{actor_id}",
        )

    @staticmethod
    def _fallback_audio(*, actor_id: str, voice_id: str) -> DialogueAudio:
        return DialogueAudio(
            mode="stub",
            status="fallback",
            provider="stub",
            voice_id=voice_id,
            fallback_reason=f"provider_unavailable:{actor_id}",
        )


def _inspect_pcm_wav(wav_bytes: bytes, *, expected_sample_rate_hz: int) -> _PcmWavInfo:
    if len(wav_bytes) < 12 or wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
        raise TTSProviderError("provider did not return a WAV file")

    offset = 12
    fmt: tuple[int, int, int, int] | None = None
    data_size: int | None = None
    while offset + 8 <= len(wav_bytes):
        chunk_id = wav_bytes[offset : offset + 4]
        chunk_size = struct.unpack_from("<I", wav_bytes, offset + 4)[0]
        chunk_start = offset + 8
        chunk_end = chunk_start + chunk_size
        effective_chunk_size = chunk_size
        if chunk_end > len(wav_bytes):
            if chunk_id != b"data":
                raise TTSProviderError("provider returned a truncated WAV file")
            # DashScope WAV clips can retain a streaming placeholder here even
            # though the complete PCM payload ends at EOF.
            chunk_end = len(wav_bytes)
            effective_chunk_size = chunk_end - chunk_start
        if chunk_id == b"fmt ":
            if chunk_size < 16:
                raise TTSProviderError("provider returned an invalid WAV fmt chunk")
            fmt = struct.unpack_from("<HHII", wav_bytes, chunk_start)
        elif chunk_id == b"data":
            data_size = effective_chunk_size
        offset = chunk_end + (effective_chunk_size % 2)

    if fmt is None or data_size is None:
        raise TTSProviderError("provider WAV is missing fmt or data")
    audio_format, channels, sample_rate_hz, byte_rate = fmt
    if audio_format != 1 or channels != 1 or sample_rate_hz != expected_sample_rate_hz:
        raise TTSProviderError("provider WAV must be PCM mono at the configured sample rate")
    if byte_rate != sample_rate_hz * channels * 2 or data_size % 2 != 0:
        raise TTSProviderError("provider WAV must contain 16-bit PCM samples")
    return _PcmWavInfo(
        sample_rate_hz=sample_rate_hz,
        channels=channels,
        duration_ms=(data_size * 1000) // byte_rate,
    )
