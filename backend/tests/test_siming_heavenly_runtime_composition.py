import importlib

import pytest
from pydantic import ValidationError

import app.config as config_module
import app.main as main
from app.models.authority_event import (
    AuthorityEvent,
    AuthorityEventRouting,
    AuthorityEventSource,
)
from app.models.siming_event import SimingInput
from app.models.siming_adaptive_bridge import (
    AdaptiveBridgeValidationResult,
    GeneratedAdaptiveBridgeProposalBatch,
)
from app.services.siming_llm_provider import FakeSimingLlmCandidateProvider


def _reload_settings():
    return importlib.reload(config_module).settings


def _destruction_input(correlation_id: str = "corr:destroy:1") -> SimingInput:
    return SimingInput(
        input_type="world_fact_event",
        source_event=AuthorityEvent(
            event_id="evt:destroy:1",
            event_type="world_fact_event",
            producer_ts=100,
            room_id="room:main",
            scene_id="scene:throne",
            zone_id="zone:archive",
            source=AuthorityEventSource(layer="l1", system="test"),
            routing=AuthorityEventRouting(
                audience_mode="room", routing_mode="broadcast"
            ),
            priority="p2",
            durability="replayable",
            causation_id="cause:destroy:1",
            correlation_id=correlation_id,
            payload={
                "target_ref": "obj_letter",
                "current_state": "removed_from_surface",
            },
        ),
    )


def _proposal_batch(correlation_id: str) -> GeneratedAdaptiveBridgeProposalBatch:
    return GeneratedAdaptiveBridgeProposalBatch.model_validate(
        {
            "proposals": [
                {
                    "proposal_id": "proposal:destroy:1",
                    "pattern": "private_confrontation",
                    "correlation_id": correlation_id,
                    "causal_gap_ref": "fact:letter:destroyed",
                    "title": "Confront the destruction",
                    "target_actor_id": "char_b",
                    "supporting_fact_refs": ["fact:letter:destroyed"],
                    "required_actor_memory_refs": [],
                    "obligation_refs": [],
                    "attractor_refs": [],
                    "realization_request": {
                        "node_id": "runtime:bridge:proposal:destroy:1",
                        "actor_bindings": {"speaker": "char_b", "listener": "char_c"},
                        "target_object_id": "obj_letter",
                        "target_environment_id": "env_lamp",
                        "required_realization_keys": ["look_at_target"],
                        "camera_pattern": "two_actor_confrontation",
                        "semantic_purpose": "private_confrontation",
                        "location_state": "throne_room:letter_removed",
                    },
                    "autonomy_reason": "char_b chooses to respond",
                }
            ],
            "audit": {
                "provider": "fake",
                "route_id": "fake",
                "model": "fake",
                "request_id": "request:destroy:1",
                "correlation_id": correlation_id,
                "latency_ms": 1,
                "response_artifact_hash": "a" * 64,
            },
        }
    )


class _AcceptedBridge:
    def validate_and_commit(self, proposal, *, provider_audit):
        assert proposal.proposal_id == "proposal:destroy:1"
        assert provider_audit.correlation_id == proposal.correlation_id
        return AdaptiveBridgeValidationResult(
            accepted=True,
            proposal_id=proposal.proposal_id,
            graph_transaction_ref="story_instantiate:runtime:bridge:proposal:destroy:1",
            runtime_node_ref="runtime:bridge:proposal:destroy:1",
        )


def _support_with_candidate(state, correlation_id: str):
    support = state.siming_runtime.heavenly_support
    support._llm_provider = FakeSimingLlmCandidateProvider(
        [], adaptive_bridge_proposal_batch=_proposal_batch(correlation_id)
    )
    support._bridges = lambda context: _AcceptedBridge()
    return support


def test_active_mode_composes_shared_sqlite_graph(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SIMING_HEAVENLY_MODE", "active")
    monkeypatch.setenv("PARALLS_HEAVENLY_GRAPH_PATH", str(tmp_path / "runtime.sqlite3"))

    state = main.build_runtime_state(_reload_settings())
    try:
        assert state.siming_runtime.heavenly_support.mode == "active"
        assert state.heavenly_graph is state.character_graph_memory.graph
    finally:
        state.close()


def test_off_mode_keeps_char_b_graph_memory_without_siming_support(tmp_path) -> None:
    settings = config_module.Settings(
        siming_heavenly_mode="off",
        heavenly_graph_path=str(tmp_path / "runtime.sqlite3"),
    )

    state = main.build_runtime_state(settings)
    try:
        assert state.siming_runtime.heavenly_support is None
        assert state.character_graph_memory.graph is state.heavenly_graph
    finally:
        state.close()


def test_shadow_mode_marks_owned_family_advisory_and_support_cannot_publish(
    tmp_path,
) -> None:
    settings = config_module.Settings(
        siming_heavenly_mode="shadow",
        heavenly_graph_path=str(tmp_path / "runtime.sqlite3"),
    )

    state = main.build_runtime_state(settings)
    try:
        support = state.siming_runtime.heavenly_support
        assert support.mode == "shadow"
        assert "evidence_destruction_consequence" in support.GRAPH_OWNED_EVENT_FAMILIES
        assert support.prepare(_destruction_input()).owns_event_family is False
        assert not hasattr(support, "tick")
        assert not hasattr(support, "publish")
        assert not hasattr(support, "write_actor_memory")
    finally:
        state.close()


def test_active_support_rejects_second_selection_for_one_correlation(tmp_path) -> None:
    state = main.build_runtime_state(
        config_module.Settings(
            siming_heavenly_mode="active",
            heavenly_graph_path=str(tmp_path / "runtime.sqlite3"),
        )
    )
    try:
        prepared = state.siming_runtime.heavenly_support.prepare(_destruction_input())
        state.siming_runtime.heavenly_support.record_selection(
            prepared, "runtime:bridge:one"
        )

        with pytest.raises(ValueError, match="already selected"):
            state.siming_runtime.heavenly_support.record_selection(
                prepared, "runtime:bridge:two"
            )
    finally:
        state.close()


def test_active_owned_destruction_prepares_typed_eligible_bridge_candidate(
    tmp_path,
) -> None:
    state = main.build_runtime_state(
        config_module.Settings(
            siming_heavenly_mode="active",
            heavenly_graph_path=str(tmp_path / "runtime.sqlite3"),
        )
    )
    try:
        support = _support_with_candidate(state, "corr:destroy:1")

        prepared = support.prepare(_destruction_input())

        assert prepared.owns_event_family is True
        assert prepared.eligible_node_refs == ["runtime:bridge:proposal:destroy:1"]
        assert prepared.validation_audit_refs
    finally:
        state.close()


def test_selection_and_dispatch_reject_new_values_after_support_recreation(
    tmp_path,
) -> None:
    graph_path = tmp_path / "runtime.sqlite3"
    settings = config_module.Settings(
        siming_heavenly_mode="active", heavenly_graph_path=str(graph_path)
    )
    first_state = main.build_runtime_state(settings)
    try:
        first_support = first_state.siming_runtime.heavenly_support
        first_prepared = first_support.prepare(_destruction_input())
        first_support.record_selection(first_prepared, "runtime:bridge:one")
        first_support.record_dispatch(
            correlation_id="corr:destroy:1", dispatch_event_id="dispatch:one"
        )
    finally:
        first_state.close()

    second_state = main.build_runtime_state(settings)
    try:
        second_support = second_state.siming_runtime.heavenly_support
        second_prepared = second_support.prepare(_destruction_input())

        with pytest.raises(ValueError, match="already selected"):
            second_support.record_selection(second_prepared, "runtime:bridge:two")
        second_support.record_selection(second_prepared, "runtime:bridge:one")
        with pytest.raises(ValueError, match="already recorded"):
            second_support.record_dispatch(
                correlation_id="corr:destroy:1", dispatch_event_id="dispatch:two"
            )
    finally:
        second_state.close()


@pytest.mark.parametrize("failure_site", ["compile", "write"])
def test_preparation_graph_failure_is_non_activatable_degraded(
    tmp_path, monkeypatch, failure_site
) -> None:
    state = main.build_runtime_state(
        config_module.Settings(
            siming_heavenly_mode="active",
            heavenly_graph_path=str(tmp_path / "runtime.sqlite3"),
        )
    )
    try:
        support = state.siming_runtime.heavenly_support
        if failure_site == "compile":
            monkeypatch.setattr(
                support._compiler,
                "compile",
                lambda request: (_ for _ in ()).throw(OSError("graph offline")),
            )
        else:
            monkeypatch.setattr(
                support._memory,
                "write_entry",
                lambda **kwargs: (_ for _ in ()).throw(OSError("graph offline")),
            )

        prepared = support.prepare(_destruction_input())

        assert prepared.owns_event_family is False
        assert prepared.eligible_node_refs == []
        assert prepared.degraded_reason.startswith("graph_degraded:")
        with pytest.raises(ValueError, match="graph-owned"):
            support.record_dispatch(
                correlation_id="corr:destroy:1", dispatch_event_id="dispatch:one"
            )
    finally:
        state.close()


@pytest.mark.parametrize("mode", ["invalid", "ACTIVE"])
def test_heavenly_mode_rejects_unknown_values(monkeypatch, mode) -> None:
    monkeypatch.setenv("SIMING_HEAVENLY_MODE", mode)

    with pytest.raises(ValidationError):
        importlib.reload(config_module)
