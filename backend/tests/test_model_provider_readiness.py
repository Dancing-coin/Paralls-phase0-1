from __future__ import annotations

import json

from app.world_runtime.model_provider_readiness import (
    ModelProviderKind,
    ModelProviderReadinessStatus,
    build_model_provider_readiness_report,
    write_model_provider_readiness_report,
)


def test_readiness_report_contains_required_provider_rows() -> None:
    report = build_model_provider_readiness_report(env={})

    rows = {row.provider_kind: row for row in report.rows}

    assert set(rows) == {
        "character_text",
        "siming_candidate",
        "vla_spatial",
        "production_multimodal",
    }
    for row in rows.values():
        assert row.provider_id
        assert row.model_id
        assert row.schema_version == "model-provider-readiness.v1"
        assert row.required_input_refs
        assert row.output_schema_status
        assert row.timeout_degrade_status
        assert row.context_isolation_status
        assert "forbidden" in row.world_truth_write_status
        assert row.verification_evidence
        assert row.readiness_status != "mock_verified"


def test_missing_http_credentials_are_blocked_not_real_verified() -> None:
    report = build_model_provider_readiness_report(
        env={
            "CHARACTER_MODEL_PROVIDER_KIND": "qwen",
            "CHARACTER_MODEL_ENDPOINT": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "SIMING_LLM_MODE": "http",
            "SIMING_LLM_PROVIDER_ORDER": "seed_doubao,qwen",
            "SIMING_LLM_ENDPOINT": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        }
    )
    rows = {row.provider_kind: row for row in report.rows}

    assert rows["character_text"].readiness_status == "blocked_missing_credentials"
    assert rows["siming_candidate"].readiness_status == "blocked_missing_credentials"
    assert rows["character_text"].readiness_status != "real_provider_verified"
    assert rows["siming_candidate"].readiness_status != "real_provider_verified"


def test_configured_http_without_real_smoke_is_unverified() -> None:
    report = build_model_provider_readiness_report(
        env={
            "CHARACTER_MODEL_PROVIDER_KIND": "qwen",
            "CHARACTER_MODEL_ENDPOINT": "https://dashscope.aliyuncs.com/compatible-mode/v1?token=redacted",
            "CHARACTER_MODEL_API_KEY": "test-secret-key",
            "SIMING_LLM_MODE": "http",
            "SIMING_LLM_PROVIDER_ORDER": "seed_doubao,qwen",
            "SIMING_LLM_ENDPOINT": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
            "SIMING_LLM_API_KEY": "test-secret-key",
        }
    )
    rows = {row.provider_kind: row for row in report.rows}

    assert rows["character_text"].readiness_status == "http_configured_unverified"
    assert rows["siming_candidate"].readiness_status == "http_configured_unverified"
    assert rows["character_text"].endpoint_host_redacted == "dashscope.aliyuncs.com"
    assert "test-secret-key" not in json.dumps(report.to_dict())


def test_real_verified_requires_explicit_smoke_checker() -> None:
    calls: list[ModelProviderKind] = []

    def smoke_checker(kind: ModelProviderKind, env: dict[str, str]) -> bool:
        calls.append(kind)
        return kind == ModelProviderKind.CHARACTER_TEXT

    report = build_model_provider_readiness_report(
        env={
            "MODEL_PROVIDER_READINESS_REAL_SMOKE": "1",
            "CHARACTER_MODEL_PROVIDER_KIND": "qwen",
            "CHARACTER_MODEL_ENDPOINT": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "CHARACTER_MODEL_API_KEY": "test-secret-key",
            "SIMING_LLM_MODE": "disabled",
        },
        real_smoke_checker=smoke_checker,
    )
    rows = {row.provider_kind: row for row in report.rows}

    assert calls == [ModelProviderKind.CHARACTER_TEXT]
    assert rows["character_text"].readiness_status == ModelProviderReadinessStatus.REAL_PROVIDER_VERIFIED.value


def test_vla_defaults_to_blocked_missing_artifacts() -> None:
    report = build_model_provider_readiness_report(env={})
    rows = {row.provider_kind: row for row in report.rows}

    assert rows["vla_spatial"].mode == "blocked"
    assert rows["vla_spatial"].readiness_status == "blocked_missing_artifacts"
    assert "PerceptionQueryFrame" in rows["vla_spatial"].required_input_refs


def test_report_writer_redacts_endpoint_and_omits_api_keys(tmp_path) -> None:
    report = build_model_provider_readiness_report(
        env={
            "CHARACTER_MODEL_ENDPOINT": "https://example.invalid/v1/chat/completions?api_key=secret",
            "CHARACTER_MODEL_API_KEY": "secret-key",
        }
    )

    json_path, markdown_path = write_model_provider_readiness_report(report, project_root=tmp_path)

    written_json = json_path.read_text(encoding="utf-8")
    written_markdown = markdown_path.read_text(encoding="utf-8")
    assert "secret-key" not in written_json
    assert "api_key=secret" not in written_json
    assert "secret-key" not in written_markdown
    assert "api_key=secret" not in written_markdown
    assert "example.invalid" in written_json


def test_readiness_report_carries_run_id_and_route_identity() -> None:
    report = build_model_provider_readiness_report(
        env={
            "LLM_CLOSURE_RUN_ID": "fixture-run",
            "SIMING_LLM_MODE": "http",
            "SIMING_LLM_ROUTES_JSON": json.dumps(
                [
                    {
                        "route_id": "deepseek-live",
                        "provider": "deepseek_chat",
                        "model": "deepseek-chat",
                        "endpoint": "https://api.deepseek.com/chat/completions",
                        "api_key": "route-secret",
                        "timeout_seconds": 60.0,
                        "enabled": True,
                    }
                ]
            ),
        }
    )
    rows = {row.provider_kind: row for row in report.rows}

    assert report.verification_run_id == "fixture-run"
    assert rows["siming_candidate"].provider_id == "deepseek_chat"
    assert rows["siming_candidate"].model_id == "deepseek-chat"
    assert rows["siming_candidate"].readiness_status == "http_configured_unverified"
    assert "route-secret" not in json.dumps(report.to_dict())
