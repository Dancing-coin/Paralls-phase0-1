import hashlib
import json

import httpx
import pytest

from app.models.siming_adaptive_bridge import (
    AdaptiveBridgeNodeProposal,
    GeneratedAdaptiveBridgeProposalBatch,
    SimingLlmProposalAudit,
)
from app.services.siming_llm_provider import (
    DisabledSimingLlmCandidateProvider,
    FakeSimingLlmCandidateProvider,
    HttpSimingLlmCandidateProvider,
    SimingLlmProviderError,
    SimingLlmProviderInvalidOutput,
    SimingLlmProviderRouter,
    SimingLlmProviderTimeout,
)


def compiled_context_payload() -> dict[str, object]:
    return {
        "scope": {"room_id": "room_demo", "scene_id": "scene_demo"},
        "private_context": "do not expose this in the audit",
    }


def private_confrontation_payload() -> dict[str, object]:
    return {
        "proposal_id": "bridge:destroy:1",
        "pattern": "private_confrontation",
        "correlation_id": "corr:destroy:1",
        "causal_gap_ref": "gap:destroy:1",
        "title": "A private confrontation",
        "target_actor_id": "actor:one",
        "supporting_fact_refs": ["fact:destroy:1"],
        "required_actor_memory_refs": ["memory:destroy:1"],
        "obligation_refs": ["obligation:destroy:1"],
        "attractor_refs": ["attractor:destroy:1"],
        "realization_request": {
            "node_id": "bridge:destroy:1",
            "actor_bindings": {"actor:one": "role:confronted"},
            "required_realization_keys": ["set:private_room"],
            "camera_pattern": "two_shot",
            "semantic_purpose": "confrontation",
            "location_state": "private_room",
        },
        "autonomy_reason": "The unresolved action needs a voluntary response.",
    }


class ResponseWithBridge:
    def __init__(
        self,
        payload: dict[str, object],
        *,
        chat: bool = False,
        request_id: str | None = "request-live",
    ) -> None:
        body = json.dumps({"proposals": [payload]})
        self._data = {"choices": [{"message": {"content": body}}]} if chat else {"output_text": body}
        self.content = json.dumps(self._data).encode()
        self.headers = {"x-request-id": request_id} if request_id is not None else {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._data


def response_with_bridge(payload: dict[str, object], *, chat: bool = False) -> ResponseWithBridge:
    return ResponseWithBridge(payload, chat=chat)


def test_http_provider_returns_typed_bridge_batch(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response_with_bridge(private_confrontation_payload()))
    provider = HttpSimingLlmCandidateProvider(
        api_key="secret", endpoint="https://example.test/v1/responses",
        model="model-live", timeout_seconds=8, route_id="route-live",
    )

    batch = provider.generate_adaptive_bridge_proposals(
        compiled_context=compiled_context_payload(), correlation_id="corr:destroy:1",
    )

    assert batch.proposals[0].pattern == "private_confrontation"
    assert batch.audit.route_id == "route-live"
    assert batch.audit.model == "model-live"
    assert batch.audit.request_id == "request-live"
    assert batch.audit.response_artifact_hash == hashlib.sha256(
        json.dumps({"output_text": json.dumps({"proposals": [private_confrontation_payload()]})}).encode()
    ).hexdigest()
    assert "secret" not in batch.model_dump_json()
    assert "do not expose this" not in batch.model_dump_json()


def test_chat_provider_returns_typed_bridge_batch(monkeypatch) -> None:
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: response_with_bridge(private_confrontation_payload(), chat=True),
    )
    provider = HttpSimingLlmCandidateProvider(
        api_key="secret", endpoint="https://example.test/v1/chat/completions",
        model="model-live", timeout_seconds=8, route_id="route-live", provider_name="deepseek_chat",
    )

    batch = provider.generate_adaptive_bridge_proposals(
        compiled_context=compiled_context_payload(), correlation_id="corr:destroy:1",
    )

    assert batch.proposals[0].proposal_id == "bridge:destroy:1"


def test_http_provider_uses_safe_request_id_when_response_header_is_absent(monkeypatch) -> None:
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: ResponseWithBridge(
            private_confrontation_payload(), request_id=None
        ),
    )
    provider = HttpSimingLlmCandidateProvider(
        api_key="secret", endpoint="https://example.test/v1/responses",
        model="model-live", timeout_seconds=8,
    )

    batch = provider.generate_adaptive_bridge_proposals(
        compiled_context=compiled_context_payload(), correlation_id="corr:destroy:1",
    )

    assert batch.audit.request_id == "not_provided"


def test_responses_bridge_schema_resolves_resource_request_definition() -> None:
    provider = HttpSimingLlmCandidateProvider(
        api_key="secret", endpoint="https://example.test/v1/responses",
        model="model-live", timeout_seconds=8,
    )

    payload = provider._adaptive_bridge_payload(compiled_context_payload(), "corr:destroy:1")
    schema = payload["text"]["format"]["schema"]
    proposal_schema = schema["properties"]["proposals"]["items"]

    assert proposal_schema["properties"]["realization_request"]["$ref"] == "#/$defs/ResourceRealizationRequest"
    assert "ResourceRealizationRequest" in schema["$defs"]


def test_http_provider_rejects_invalid_bridge_schema(monkeypatch) -> None:
    invalid = private_confrontation_payload()
    invalid["pattern"] = "world_mutation"
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response_with_bridge(invalid))
    provider = HttpSimingLlmCandidateProvider(
        api_key="secret", endpoint="https://example.test/v1/responses",
        model="model-live", timeout_seconds=8,
    )

    with pytest.raises(SimingLlmProviderInvalidOutput):
        provider.generate_adaptive_bridge_proposals(
            compiled_context=compiled_context_payload(), correlation_id="corr:destroy:1",
        )


def test_http_provider_translates_bridge_timeout(monkeypatch) -> None:
    def timeout(*args: object, **kwargs: object) -> None:
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "post", timeout)
    provider = HttpSimingLlmCandidateProvider(
        api_key="secret", endpoint="https://example.test/v1/responses",
        model="model-live", timeout_seconds=8,
    )

    with pytest.raises(SimingLlmProviderTimeout):
        provider.generate_adaptive_bridge_proposals(
            compiled_context=compiled_context_payload(), correlation_id="corr:destroy:1",
        )


def proposal_batch() -> GeneratedAdaptiveBridgeProposalBatch:
    return GeneratedAdaptiveBridgeProposalBatch(
        proposals=[AdaptiveBridgeNodeProposal.model_validate(private_confrontation_payload())],
        audit=SimingLlmProposalAudit(
            provider="fake", route_id="fake", model="fake", request_id="fake",
            correlation_id="corr:destroy:1", latency_ms=0,
            response_artifact_hash=hashlib.sha256(b"fake").hexdigest(),
        ),
    )


def test_disabled_and_fake_providers_return_safe_bridge_batches() -> None:
    disabled = DisabledSimingLlmCandidateProvider()
    disabled_batch = disabled.generate_adaptive_bridge_proposals(
        compiled_context=compiled_context_payload(), correlation_id="corr:destroy:1",
    )
    assert disabled_batch.proposals == []
    assert disabled_batch.audit.provider == "disabled"

    provider = FakeSimingLlmCandidateProvider([], adaptive_bridge_proposal_batch=proposal_batch())
    batch = provider.generate_adaptive_bridge_proposals(
        compiled_context=compiled_context_payload(), correlation_id="corr:destroy:1",
    )
    batch.proposals[0].supporting_fact_refs.append("mutated")

    second = provider.generate_adaptive_bridge_proposals(
        compiled_context=compiled_context_payload(), correlation_id="corr:destroy:1",
    )
    assert second.proposals[0].supporting_fact_refs == ["fact:destroy:1"]


def test_router_returns_first_non_empty_bridge_batch_after_failure() -> None:
    class FailingProvider:
        def generate_adaptive_bridge_proposals(self, **_: object) -> GeneratedAdaptiveBridgeProposalBatch:
            raise SimingLlmProviderTimeout("first route timed out")

    router = SimingLlmProviderRouter(
        [FailingProvider(), FakeSimingLlmCandidateProvider([], adaptive_bridge_proposal_batch=proposal_batch())]
    )

    batch = router.generate_adaptive_bridge_proposals(
        compiled_context=compiled_context_payload(), correlation_id="corr:destroy:1",
    )

    assert batch.proposals[0].proposal_id == "bridge:destroy:1"


def test_router_raises_last_bridge_provider_error() -> None:
    class FailingProvider:
        def __init__(self, message: str) -> None:
            self._message = message

        def generate_adaptive_bridge_proposals(self, **_: object) -> GeneratedAdaptiveBridgeProposalBatch:
            raise SimingLlmProviderError(self._message)

    router = SimingLlmProviderRouter([FailingProvider("first"), FailingProvider("last")])

    with pytest.raises(SimingLlmProviderError, match="last"):
        router.generate_adaptive_bridge_proposals(
            compiled_context=compiled_context_payload(), correlation_id="corr:destroy:1",
        )
