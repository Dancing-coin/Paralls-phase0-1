from __future__ import annotations

import json
from io import BytesIO
from urllib.error import HTTPError

from app.world_runtime.intelligence_upgrade import PerceptionQueryFrame, SampleInputRef, SpatialReference, TimeWindow
from app.world_runtime.vla_model_registry import default_vla_model_registry
from app.world_runtime.vla_percept_bridge import vla_result_to_modality_result
from app.world_runtime.vla_provider import (
    DisabledVLAProvider,
    DeterministicMockVLAProvider,
    HTTPVLAProviderAdapter,
    LocalVLAProviderAdapter,
    VLAAdvisoryRoute,
    VLAProviderRequest,
    VLAProviderStatus,
)


def _request(with_artifacts: bool = True, *, transportable_artifact: bool = False) -> VLAProviderRequest:
    frame = PerceptionQueryFrame(
        query_id="pqf:char_b:1",
        consumer_kind="character",
        subject_id="char_b",
        time_window=TimeWindow(started_at=0, ended_at=1),
        spatial_reference=SpatialReference(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus"),
        visual_inputs=[
            SampleInputRef(
                provider_kind="visual_patch",
                ref_id="runtime://artifact/visual.png",
                stable_source_ref="data:image/png;base64,aGVsbG8=" if transportable_artifact else "",
            )
        ]
        if with_artifacts
        else [],
        attention_context={"target_object_ids": ["obj_chair"]},
        structured_fact_refs=["raw_fact_event:visual_fact:1"],
        grounding_collider_refs=["collider:obj_chair:seat"],
        grounding_affordance_refs=["inspect"],
        multimodal_context_id="character_mm:char_b",
        cache_namespace="character_mm:char_b:vla_cache",
    )
    return VLAProviderRequest.from_pqf(frame, owner_kind="character", owner_id="char_b", model_id="qwen3-vl-plus")


def test_mock_provider_returns_schema_valid_advisory_visual_spatial_result() -> None:
    result = DeterministicMockVLAProvider().interpret(_request())
    modality = vla_result_to_modality_result(result)

    assert result.status == VLAProviderStatus.MOCK_PROVIDER_VERIFIED
    assert result.advisory is True
    assert result.findings[0]["advisory"] is True
    assert modality.modality == "visual_spatial"
    assert modality.findings[0]["advisory"] is True


def test_provider_blocks_missing_artifacts_without_reading_godot_scene() -> None:
    result = DeterministicMockVLAProvider().interpret(_request(with_artifacts=False))

    assert result.status == VLAProviderStatus.BLOCKED_MISSING_ARTIFACTS
    assert result.missing_inputs == ["artifact_refs"]
    assert result.advisory is True


def test_disabled_provider_returns_typed_advisory_degradation() -> None:
    result = DisabledVLAProvider().interpret(_request())

    assert result.status == VLAProviderStatus.DISABLED
    assert result.advisory is True
    assert result.fallback_reason == "provider_disabled"


def test_http_and_local_adapters_report_missing_credentials_or_artifact_degradation() -> None:
    request = _request()
    missing = HTTPVLAProviderAdapter(endpoint="", api_key="", model_id="qwen3-vl-plus").interpret(request)
    configured = HTTPVLAProviderAdapter(endpoint="https://example.invalid/vla", api_key="redacted", model_id="qwen3-vl-plus").interpret(request)
    local = LocalVLAProviderAdapter(model_id="qwen3-vl-local", endpoint="local://qwen3-vl").interpret(request)

    assert missing.status == VLAProviderStatus.BLOCKED_MISSING_CREDENTIALS
    assert configured.status == VLAProviderStatus.BLOCKED_MISSING_ARTIFACTS
    assert local.status == VLAProviderStatus.CONFIGURED_UNVERIFIED


class _FakeHttpResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_http_adapter_sends_pqf_artifact_and_projects_only_advisory_fields(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout: float):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeHttpResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "findings": [
                                        {
                                            "finding_type": "visual_spatial_advisory",
                                            "summary": "A chair-shaped object may be near the target.",
                                            "confidence": 0.73,
                                            "candidate_entity_refs": ["obj_chair", "invented_object"],
                                            "candidate_collider_refs": ["collider:obj_chair:seat", "invented_collider"],
                                            "candidate_anchor_refs": ["world_anchor:object:obj_chair", "invented_anchor"],
                                            "candidate_affordance_refs": ["inspect", "kick"],
                                            "action": "kick(obj_chair)",
                                            "world_state": "chair_tipped",
                                            "controls_actor": True,
                                        }
                                    ],
                                    "confidence": 0.73,
                                    "conflict_refs": ["l1_fact:chair:position"],
                                }
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("app.world_runtime.vla_provider.urlopen", fake_urlopen)
    result = HTTPVLAProviderAdapter(
        endpoint="https://provider.example/v1",
        api_key="test-secret",
        model_id="qwen3-vl-plus",
        model_version="2026-07-29",
    ).interpret(_request(transportable_artifact=True))

    payload = captured["payload"]
    assert captured["url"] == "https://provider.example/v1/chat/completions"
    assert captured["timeout"] == 8.0
    assert payload["model"] == "qwen3-vl-plus"
    assert "response_format" not in payload
    assert "enable_thinking" not in payload
    assert any(item.get("type") == "image_url" for item in payload["messages"][1]["content"])
    assert result.status == VLAProviderStatus.REAL_PROVIDER_VERIFIED
    assert result.advisory is True
    assert result.findings[0]["candidate_entity_refs"] == ["obj_chair"]
    assert result.findings[0]["candidate_collider_refs"] == ["collider:obj_chair:seat"]
    assert result.findings[0]["candidate_anchor_refs"] == ["world_anchor:object:obj_chair"]
    assert result.findings[0]["candidate_affordance_refs"] == ["inspect"]
    assert "action" not in result.findings[0]
    assert "world_state" not in result.findings[0]
    assert "controls_actor" not in result.findings[0]
    assert result.conflict_refs == ["l1_fact:chair:position"]


def test_http_adapter_exposes_and_enforces_the_pqf_grounding_catalog(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout: float):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeHttpResponse(
            {"choices": [{"message": {"content": json.dumps({"findings": [{"summary": "unknown object", "candidate_entity_refs": ["invented"]}]})}}]}
        )

    monkeypatch.setattr("app.world_runtime.vla_provider.urlopen", fake_urlopen)
    result = HTTPVLAProviderAdapter(endpoint="https://provider.example/v1", api_key="test-secret", model_id="qwen3.7-flash").interpret(
        _request(transportable_artifact=True)
    )

    content = captured["payload"]["messages"][1]["content"]
    prompt = next(item["text"] for item in content if item["type"] == "text")
    assert '"entity_refs": ["char_b", "obj_chair"]' in prompt
    assert '"collider_refs": ["collider:obj_chair:seat"]' in prompt
    assert '"anchor_refs": ["world_anchor:object:obj_chair"]' in prompt
    assert '"affordance_refs": ["inspect"]' in prompt
    assert "Required shape:" in prompt
    assert "no Markdown, prose wrapper, or code fence" in prompt
    assert result.findings[0]["candidate_entity_refs"] == []
    assert result.findings[0]["uncertainty"] == "provider returned no refs from the grounded candidate catalog"


def test_http_adapter_sends_route_specific_qwen_thinking_capability(monkeypatch) -> None:
    captured: list[dict[str, object]] = []

    def fake_urlopen(request, timeout: float):
        captured.append(json.loads(request.data.decode("utf-8")))
        return _FakeHttpResponse({"choices": [{"message": {"content": '{"findings": [], "confidence": 0}'}}]})

    monkeypatch.setattr("app.world_runtime.vla_provider.urlopen", fake_urlopen)
    adapter = HTTPVLAProviderAdapter(
        endpoint="https://provider.example/v1",
        api_key="test-secret",
        model_id="qwen3.7-flash",
        advisory_fast_enable_thinking=False,
        advisory_deep_enable_thinking=True,
    )

    fast = adapter.interpret(_request(transportable_artifact=True))
    deep_request = _request(transportable_artifact=True).model_copy(
        update={"advisory_route": VLAAdvisoryRoute.ADVISORY_DEEP, "model_id": "qwen3.7-plus"}
    )
    deep = adapter.interpret(deep_request)

    assert fast.provider_thinking_enabled is False
    assert deep.provider_thinking_enabled is True
    assert captured[0]["enable_thinking"] is False
    assert captured[1]["enable_thinking"] is True


def test_http_adapter_only_uses_json_mode_when_explicitly_enabled(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout: float):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeHttpResponse({"choices": [{"message": {"content": "```json\n{\"findings\": [], \"confidence\": 0}\n```"}}]})

    monkeypatch.setattr("app.world_runtime.vla_provider.urlopen", fake_urlopen)
    result = HTTPVLAProviderAdapter(
        endpoint="https://provider.example/v1",
        api_key="test-secret",
        model_id="qwen3-vl-flash",
        json_mode_enabled=True,
    ).interpret(_request(transportable_artifact=True))

    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert result.status == VLAProviderStatus.REAL_PROVIDER_VERIFIED


def test_http_adapter_projects_provider_string_findings_as_advisory_only(monkeypatch) -> None:
    def fake_urlopen(request, timeout: float):
        return _FakeHttpResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "findings": ["A visual detail may be near the subject."],
                                    "confidence": 0.68,
                                    "conflict_refs": [],
                                    "missing_inputs": [],
                                }
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("app.world_runtime.vla_provider.urlopen", fake_urlopen)
    result = HTTPVLAProviderAdapter(
        endpoint="https://provider.example/v1",
        api_key="test-secret",
        model_id="qwen3-vl-plus",
    ).interpret(_request(transportable_artifact=True))

    assert result.status == VLAProviderStatus.REAL_PROVIDER_VERIFIED
    assert result.findings[0]["summary"] == "A visual detail may be near the subject."
    assert result.findings[0]["confidence"] == 0.68
    assert result.findings[0]["evidence_artifact_refs"] == ["runtime://artifact/visual.png"]


def test_http_adapter_projects_single_provider_finding_string_as_advisory_only(monkeypatch) -> None:
    def fake_urlopen(request, timeout: float):
        return _FakeHttpResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "findings": "A visual detail may be near the subject.",
                                    "confidence": 0.68,
                                    "conflict_refs": [],
                                    "missing_inputs": [],
                                }
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("app.world_runtime.vla_provider.urlopen", fake_urlopen)
    result = HTTPVLAProviderAdapter(
        endpoint="https://provider.example/v1",
        api_key="test-secret",
        model_id="qwen3.7-flash",
    ).interpret(_request(transportable_artifact=True))

    assert result.status == VLAProviderStatus.REAL_PROVIDER_VERIFIED
    assert result.findings[0]["summary"] == "A visual detail may be near the subject."
    assert result.findings[0]["confidence"] == 0.68


def test_http_adapter_blocks_opaque_artifact_refs_without_network_io(monkeypatch) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("opaque artifact refs must not be guessed as provider URLs")

    monkeypatch.setattr("app.world_runtime.vla_provider.urlopen", fail_if_called)
    result = HTTPVLAProviderAdapter(
        endpoint="https://provider.example/v1",
        api_key="test-secret",
        model_id="qwen3-vl-plus",
    ).interpret(_request())

    assert result.status == VLAProviderStatus.BLOCKED_MISSING_ARTIFACTS
    assert result.missing_inputs == ["eligible_visual_artifact_ref"]


def test_http_adapter_maps_transport_timeout_to_advisory_degradation(monkeypatch) -> None:
    def timeout(*args, **kwargs):
        raise TimeoutError("provider timed out")

    monkeypatch.setattr("app.world_runtime.vla_provider.urlopen", timeout)
    result = HTTPVLAProviderAdapter(
        endpoint="https://provider.example/v1",
        api_key="test-secret",
        model_id="qwen3-vl-plus",
    ).interpret(_request(transportable_artifact=True))

    assert result.status == VLAProviderStatus.TIMEOUT
    assert result.advisory is True
    assert result.fallback_reason == "provider_timeout"
    assert result.failure_phase == "transport_timeout"


def test_http_adapter_records_redacted_http_error_metadata(monkeypatch) -> None:
    def http_error(*args, **kwargs):
        raise HTTPError(
            "https://provider.example/v1/chat/completions",
            400,
            "Bad Request",
            {},
            BytesIO(b'{"error":{"message":"response_format is unsupported","code":"invalid_parameter","param":"response_format.type"}}'),
        )

    monkeypatch.setattr("app.world_runtime.vla_provider.urlopen", http_error)
    result = HTTPVLAProviderAdapter(
        endpoint="https://provider.example/v1",
        api_key="test-secret",
        model_id="qwen3.7-flash",
    ).interpret(_request(transportable_artifact=True))

    assert result.status == VLAProviderStatus.ERROR
    assert result.fallback_reason == "provider_http_error"
    assert result.provider_http_status == 400
    assert result.provider_error_code == "invalid_parameter"
    assert result.provider_error_param == "response_format.type"
    assert result.provider_error_category == "unsupported_json_mode"
    assert result.failure_phase == "provider_http_response"


def test_model_registry_marks_qwen_seed_and_robotics_boundaries() -> None:
    registry = default_vla_model_registry()

    assert "qwen3-vl-plus" in registry
    assert "seed-vl-advisor" in registry
    assert "world_truth_write" in registry["qwen3-vl-plus"].forbidden_runtime_roles
    assert "actor_control" in registry["seed-vl-advisor"].forbidden_runtime_roles
    assert registry["openvla-action-head-research-only"].allowed_runtime_roles == []
    assert "robotics_action_head_runtime_control" in registry["openvla-action-head-research-only"].forbidden_runtime_roles
