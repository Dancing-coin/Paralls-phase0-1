import json
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.config import Settings
from app.services.tts_voice_catalog_importer import (
    TTSVoiceCatalogImportError,
    VoiceCatalogCandidateRequest,
    import_xlsx_voice_catalog,
    rank_voice_catalog_candidates,
)
from app.services.tts_service import TTSService


def _catalog_payload(
    *,
    provider: str = "dashscope_http",
    model: str = "qwen-audio-3.0-tts-flash",
    allowed_presentation_instructions: list[str] | None = None,
) -> dict[str, object]:
    return {
        "contract": "tts_voice_catalog.v1",
        "provider": provider,
        "model": model,
        "catalog_revision": "2026-07-23",
        "allowed_presentation_instructions": allowed_presentation_instructions or [],
        "voices": [
            {
                "voice_id": "qwen-audio-3.0-tts-flash-longlanghongmo",
                "language_tags": ["zh-CN"],
                "trait_tags": ["soft", "warm"],
            }
        ],
    }


def _bindings_payload(
    *,
    status: str = "approved",
    voice_id: str = "qwen-audio-3.0-tts-flash-longlanghongmo",
    presentation_instruction: str | None = None,
) -> dict[str, object]:
    return {
        "contract": "tts_voice_bindings.v1",
        "bindings": [
            {
                "contract": "tts_voice_profile.v1",
                "actor_id": "char_a",
                "provider": "dashscope_http",
                "model": "qwen-audio-3.0-tts-flash",
                "voice_id": voice_id,
                "catalog_revision": "2026-07-23",
                "selection_status": status,
                "approved_by": "human-listening-review",
                "presentation_instruction": presentation_instruction,
            }
        ],
    }


def _settings(*, catalog_path: str, bindings_path: str, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "tts_mode": "dashscope_http",
        "tts_provider_endpoint": "https://workspace.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer",
        "tts_provider_api_key": "secret",
        "tts_provider_model": "qwen-audio-3.0-tts-flash",
        "tts_default_voice": "legacy-default",
        "tts_voice_map": {"char_a": "legacy-a"},
        "tts_voice_profiles_enabled": True,
        "tts_presentation_instructions_enabled": False,
        "tts_voice_catalog_path": catalog_path,
        "tts_voice_bindings_path": bindings_path,
    }
    values.update(overrides)
    return Settings(**values)


class _Provider:
    provider_name = "test_provider"

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def synthesize(self, *, content: str, voice_id: str) -> bytes:
        self.calls.append({"content": content, "voice_id": voice_id})
        return b"not-used"


class _InstructionCapableProvider(_Provider):
    supports_presentation_instruction = True

    def synthesize(self, *, content: str, voice_id: str, presentation_instruction: str | None = None) -> bytes:
        self.calls.append(
            {
                "content": content,
                "voice_id": voice_id,
                "presentation_instruction": presentation_instruction or "",
            }
        )
        return b"not-used"


def _write_catalog_xlsx(path, rows: list[list[str]]) -> None:
    shared_strings = [value for row in rows for value in row]
    unique_strings = list(dict.fromkeys(shared_strings))
    string_indexes = {value: index for index, value in enumerate(unique_strings)}
    shared_xml = "".join(f"<si><t>{value}</t></si>" for value in unique_strings)
    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = "".join(
            f'<c r="{chr(64 + column_index)}{row_index}" t="s"><v>{string_indexes[value]}</v></c>'
            for column_index, value in enumerate(row, start=1)
        )
        sheet_rows.append(f'<row r="{row_index}">{cells}</row>')

    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Voices" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/sharedStrings.xml",
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"{shared_xml}</sst>",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetData>{''.join(sheet_rows)}</sheetData></worksheet>",
        )


def test_xlsx_catalog_import_normalizes_supported_columns_and_ranks_advisory_candidates(tmp_path) -> None:
    source_path = tmp_path / "official-flash-catalog.xlsx"
    _write_catalog_xlsx(
        source_path,
        [
            ["voice_id", "language_tags", "trait_tags", "usage_tags", "age_impression", "voice_gender_presentation"],
            ["flash-a", "zh-CN; en-US", "warm, soft", "dialogue|social", "young_adult", "female"],
            ["flash-b", "zh-CN", "calm, controlled", "dialogue|guard", "mature_adult", "male"],
        ],
    )

    catalog = import_xlsx_voice_catalog(
        source_path,
        provider="dashscope_http",
        model="qwen-audio-3.0-tts-flash",
        catalog_revision="2026-08-02",
    )
    candidates = rank_voice_catalog_candidates(
        catalog,
        VoiceCatalogCandidateRequest(
            required_language_tags=("zh-CN",),
            preferred_trait_tags=("warm", "soft"),
            preferred_usage_tags=("dialogue",),
            age_impression="young_adult",
            voice_gender_presentation="female",
        ),
    )

    assert catalog.voices[0].language_tags == ["zh-CN", "en-US"]
    assert [candidate.voice_id for candidate in candidates] == ["flash-a", "flash-b"]
    assert candidates[0].score > candidates[1].score
    assert candidates[0].matched_trait_tags == ("soft", "warm")
    assert candidates[0].matched_usage_tags == ("dialogue",)


def test_xlsx_catalog_import_rejects_missing_or_duplicate_voice_ids(tmp_path) -> None:
    source_path = tmp_path / "invalid-catalog.xlsx"
    _write_catalog_xlsx(source_path, [["voice_id", "language_tags"], ["same", "zh-CN"], ["same", "zh-CN"]])

    with pytest.raises(TTSVoiceCatalogImportError, match="duplicate voice_id"):
        import_xlsx_voice_catalog(
            source_path,
            provider="dashscope_http",
            model="qwen-audio-3.0-tts-flash",
            catalog_revision="2026-08-02",
        )


def test_voice_catalog_ranking_excludes_entries_without_each_required_language(tmp_path) -> None:
    source_path = tmp_path / "catalog.xlsx"
    _write_catalog_xlsx(
        source_path,
        [["voice_id", "language_tags"], ["zh-only", "zh-CN"], ["bilingual", "zh-CN, en-US"]],
    )
    catalog = import_xlsx_voice_catalog(
        source_path,
        provider="dashscope_http",
        model="qwen-audio-3.0-tts-flash",
        catalog_revision="2026-08-02",
    )

    candidates = rank_voice_catalog_candidates(
        catalog,
        VoiceCatalogCandidateRequest(required_language_tags=("zh-CN", "en-US")),
    )

    assert [candidate.voice_id for candidate in candidates] == ["bilingual"]


def test_approved_matching_binding_overrides_the_legacy_actor_voice_map(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    bindings_path = tmp_path / "bindings.json"
    catalog_path.write_text(json.dumps(_catalog_payload()), encoding="utf-8")
    bindings_path.write_text(json.dumps(_bindings_payload()), encoding="utf-8")

    service = TTSService(configuration=_settings(catalog_path=str(catalog_path), bindings_path=str(bindings_path)))

    assert service.resolve_voice_id("char_a") == "qwen-audio-3.0-tts-flash-longlanghongmo"


def test_unapproved_profile_binding_falls_back_without_calling_the_provider(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    bindings_path = tmp_path / "bindings.json"
    catalog_path.write_text(json.dumps(_catalog_payload()), encoding="utf-8")
    bindings_path.write_text(json.dumps(_bindings_payload(status="candidate")), encoding="utf-8")
    provider = _Provider()

    audio = TTSService(
        configuration=_settings(catalog_path=str(catalog_path), bindings_path=str(bindings_path)),
        provider=provider,
    ).synthesize("char_a", "hello")

    assert provider.calls == []
    assert audio.mode == "stub"
    assert audio.status == "fallback"


def test_provider_or_model_mismatch_falls_back_without_calling_the_provider(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    bindings_path = tmp_path / "bindings.json"
    catalog_path.write_text(json.dumps(_catalog_payload(model="qwen-audio-3.0-tts-plus")), encoding="utf-8")
    bindings_path.write_text(json.dumps(_bindings_payload()), encoding="utf-8")
    provider = _Provider()

    audio = TTSService(
        configuration=_settings(catalog_path=str(catalog_path), bindings_path=str(bindings_path)),
        provider=provider,
    ).synthesize("char_a", "hello")

    assert provider.calls == []
    assert audio.mode == "stub"
    assert audio.status == "fallback"


def test_required_voice_language_rejects_an_incompatible_binding_before_provider_call(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    bindings_path = tmp_path / "bindings.json"
    catalog_path.write_text(json.dumps(_catalog_payload()), encoding="utf-8")
    bindings_path.write_text(json.dumps(_bindings_payload()), encoding="utf-8")
    provider = _Provider()

    audio = TTSService(
        configuration=_settings(
            catalog_path=str(catalog_path),
            bindings_path=str(bindings_path),
            tts_voice_required_language="en-US",
        ),
        provider=provider,
    ).synthesize("char_a", "hello")

    assert provider.calls == []
    assert audio.mode == "stub"
    assert audio.status == "fallback"


def test_profile_mode_uses_legacy_mapping_for_actors_without_a_binding(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    bindings_path = tmp_path / "bindings.json"
    catalog_path.write_text(json.dumps(_catalog_payload()), encoding="utf-8")
    bindings_path.write_text(json.dumps(_bindings_payload()), encoding="utf-8")
    service = TTSService(configuration=_settings(catalog_path=str(catalog_path), bindings_path=str(bindings_path)))

    assert service.resolve_voice_id("char_b") == "legacy-default"


def test_disabled_profile_mode_preserves_legacy_mapping_without_reading_assets() -> None:
    service = TTSService(
        configuration=Settings(
            tts_mode="stub",
            tts_default_voice="legacy-default",
            tts_voice_map={"char_a": "legacy-a"},
            tts_voice_profiles_enabled=False,
            tts_voice_catalog_path="not-a-real-file.json",
            tts_voice_bindings_path="not-a-real-file.json",
        )
    )

    assert service.resolve_voice_id("char_a") == "legacy-a"


def test_authored_presentation_instruction_requires_enabled_feature_and_catalog_allowlist(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    bindings_path = tmp_path / "bindings.json"
    catalog_path.write_text(
        json.dumps(_catalog_payload(allowed_presentation_instructions=["calm_guard"])), encoding="utf-8"
    )
    bindings_path.write_text(
        json.dumps(_bindings_payload(presentation_instruction="calm_guard")), encoding="utf-8"
    )
    service = TTSService(
        configuration=_settings(
            catalog_path=str(catalog_path),
            bindings_path=str(bindings_path),
            tts_presentation_instructions_enabled=True,
        )
    )

    assert service.resolve_presentation_instruction("char_a") == "calm_guard"


def test_allowed_authored_presentation_instruction_reaches_only_a_capable_provider(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    bindings_path = tmp_path / "bindings.json"
    catalog_path.write_text(
        json.dumps(_catalog_payload(allowed_presentation_instructions=["calm_guard"])), encoding="utf-8"
    )
    bindings_path.write_text(
        json.dumps(_bindings_payload(presentation_instruction="calm_guard")), encoding="utf-8"
    )
    provider = _InstructionCapableProvider()

    audio = TTSService(
        configuration=_settings(
            catalog_path=str(catalog_path),
            bindings_path=str(bindings_path),
            tts_presentation_instructions_enabled=True,
        ),
        provider=provider,
    ).synthesize("char_a", "hello")

    assert provider.calls == [
        {
            "content": "hello",
            "voice_id": "qwen-audio-3.0-tts-flash-longlanghongmo",
            "presentation_instruction": "calm_guard",
        }
    ]
    assert audio.mode == "stub"  # The test adapter deliberately returns non-WAV bytes.
    assert audio.status == "fallback"


def test_allowed_authored_presentation_instruction_rejects_a_provider_without_declared_capability(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    bindings_path = tmp_path / "bindings.json"
    catalog_path.write_text(
        json.dumps(_catalog_payload(allowed_presentation_instructions=["calm_guard"])), encoding="utf-8"
    )
    bindings_path.write_text(
        json.dumps(_bindings_payload(presentation_instruction="calm_guard")), encoding="utf-8"
    )
    provider = _Provider()

    audio = TTSService(
        configuration=_settings(
            catalog_path=str(catalog_path),
            bindings_path=str(bindings_path),
            tts_presentation_instructions_enabled=True,
        ),
        provider=provider,
    ).synthesize("char_a", "hello")

    assert provider.calls == []
    assert audio.mode == "stub"
    assert audio.status == "fallback"


def test_disallowed_or_unsupported_authored_presentation_instruction_falls_back_before_provider_call(tmp_path) -> None:
    catalog_path = tmp_path / "catalog.json"
    bindings_path = tmp_path / "bindings.json"
    catalog_path.write_text(json.dumps(_catalog_payload()), encoding="utf-8")
    bindings_path.write_text(
        json.dumps(_bindings_payload(presentation_instruction="calm_guard")), encoding="utf-8"
    )
    provider = _InstructionCapableProvider()

    audio = TTSService(
        configuration=_settings(
            catalog_path=str(catalog_path),
            bindings_path=str(bindings_path),
            tts_presentation_instructions_enabled=True,
        ),
        provider=provider,
    ).synthesize("char_a", "hello")

    assert provider.calls == []
    assert audio.mode == "stub"
    assert audio.status == "fallback"
