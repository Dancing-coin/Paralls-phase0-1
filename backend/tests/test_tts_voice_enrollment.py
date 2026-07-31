import json

import pytest

from app.config import Settings
from app.services import tts_voice_enrollment
from app.services.tts_voice_enrollment import (
    CharacterVoiceSourceAsset,
    CharacterVoiceSourceAssetLoader,
    DashScopeVoiceEnrollmentProvider,
    TTSVoiceEnrollmentError,
    VoiceCloneEnrollmentService,
)


def _asset_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "contract": "character_voice_source_asset.v1",
        "asset_id": "character_voice_source:char_a:take_01",
        "actor_id": "char_a",
        "asset_kind": "voice_reference",
        "source_ref": "secure_asset://characters/char_a/voice/take_01.wav",
        "sha256": "a" * 64,
        "rights_status": "authorised",
        "consent_ref": "rights:voice-performer:agreement-2026-07",
        "retention_policy": "revocable",
    }
    payload.update(overrides)
    return payload


class _Issuer:
    def __init__(self, url: str = "https://secure.example.test/temporary/source.wav?signature=redacted") -> None:
        self.url = url
        self.requests: list[str] = []

    def issue_read_url(self, source_asset: CharacterVoiceSourceAsset) -> str:
        self.requests.append(source_asset.asset_id)
        return self.url


class _Provider:
    provider_name = "dashscope_http"

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def create_voice(self, *, source_url: str, target_model: str, prefix: str) -> str:
        self.calls.append({"source_url": source_url, "target_model": target_model, "prefix": prefix})
        return "qwen-audio-3.0-tts-flash-char-a-abc123"


def test_authorised_voice_asset_enrolls_to_a_candidate_record_without_source_url() -> None:
    asset = CharacterVoiceSourceAsset.model_validate(_asset_payload())
    issuer = _Issuer()
    provider = _Provider()

    record = VoiceCloneEnrollmentService(provider=provider).enroll(
        source_asset=asset,
        source_url_issuer=issuer,
        target_model="qwen-audio-3.0-tts-flash",
        prefix="char-a",
    )

    assert issuer.requests == [asset.asset_id]
    assert provider.calls == [
        {
            "source_url": "https://secure.example.test/temporary/source.wav?signature=redacted",
            "target_model": "qwen-audio-3.0-tts-flash",
            "prefix": "char-a",
        }
    ]
    assert record.actor_id == "char_a"
    assert record.voice_id == "qwen-audio-3.0-tts-flash-char-a-abc123"
    assert record.enrollment_status == "candidate"
    assert "source_url" not in record.model_dump()
    assert record.to_voice_binding_payload()["selection_status"] == "candidate"


def test_revoked_or_unapproved_voice_asset_cannot_enroll() -> None:
    provider = _Provider()
    service = VoiceCloneEnrollmentService(provider=provider)

    for rights_status in ("pending", "revoked"):
        asset = CharacterVoiceSourceAsset.model_validate(_asset_payload(rights_status=rights_status))
        with pytest.raises(TTSVoiceEnrollmentError, match="authorised"):
            service.enroll(
                source_asset=asset,
                source_url_issuer=_Issuer(),
                target_model="qwen-audio-3.0-tts-flash",
                prefix="char-a",
            )

    assert provider.calls == []


def test_voice_source_asset_requires_a_secure_asset_reference() -> None:
    with pytest.raises(ValueError, match="secure_asset"):
        CharacterVoiceSourceAsset.model_validate(_asset_payload(source_ref="https://public.example.test/take.wav"))


def test_enrollment_rejects_a_non_https_issued_source_url_before_provider_call() -> None:
    provider = _Provider()
    asset = CharacterVoiceSourceAsset.model_validate(_asset_payload())

    with pytest.raises(TTSVoiceEnrollmentError, match="HTTPS"):
        VoiceCloneEnrollmentService(provider=provider).enroll(
            source_asset=asset,
            source_url_issuer=_Issuer("http://secure.example.test/take.wav"),
            target_model="qwen-audio-3.0-tts-flash",
            prefix="char-a",
        )

    assert provider.calls == []


def test_voice_source_asset_loader_reads_yaml_manifest(tmp_path) -> None:
    manifest_path = tmp_path / "char_a.yaml"
    manifest_path.write_text(
        "\n".join(
            [
                "contract: character_voice_source_asset.v1",
                "asset_id: character_voice_source:char_a:take_01",
                "actor_id: char_a",
                "asset_kind: voice_reference",
                "source_ref: secure_asset://characters/char_a/voice/take_01.wav",
                f"sha256: {'a' * 64}",
                "rights_status: authorised",
                "consent_ref: rights:voice-performer:agreement-2026-07",
                "retention_policy: revocable",
            ]
        ),
        encoding="utf-8",
    )

    asset = CharacterVoiceSourceAssetLoader(tmp_path).load("char_a")

    assert asset.asset_id == "character_voice_source:char_a:take_01"


def test_dashscope_enrollment_provider_posts_the_official_create_voice_shape(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _Response:
        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"output": {"voice_id": "qwen-audio-3.0-tts-flash-char-a-abc123"}}).encode()

    def fake_urlopen(request: object, *, timeout: float) -> _Response:
        captured["request"] = request
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(tts_voice_enrollment, "urlopen", fake_urlopen)
    configuration = Settings(
        tts_mode="dashscope_http",
        tts_provider_api_key="secret",
        tts_voice_enrollment_endpoint="https://workspace.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/customization",
    )
    provider = DashScopeVoiceEnrollmentProvider(configuration)

    voice_id = provider.create_voice(
        source_url="https://secure.example.test/temporary/source.wav?signature=redacted",
        target_model="qwen-audio-3.0-tts-flash",
        prefix="char-a",
    )

    assert voice_id == "qwen-audio-3.0-tts-flash-char-a-abc123"
    request = captured["request"]
    assert request is not None
    assert json.loads(request.data) == {
        "model": "voice-enrollment",
        "input": {
            "action": "create_voice",
            "target_model": "qwen-audio-3.0-tts-flash",
            "prefix": "char-a",
            "url": "https://secure.example.test/temporary/source.wav?signature=redacted",
        },
    }
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == "Bearer secret"
    assert captured["timeout"] == 15.0
