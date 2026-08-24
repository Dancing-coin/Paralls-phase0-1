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
from app.models.siming_resource_capability import StagingAck
from app.models.siming_adaptive_bridge import (
    AdaptiveBridgeValidationResult,
    GeneratedAdaptiveBridgeProposalBatch,
)
from app.services.siming_llm_provider import (
    FakeSimingLlmCandidateProvider,
    SimingLlmProviderTimeout,
)
from app.services.authority_event_bus import (
    AuthorityRecoveryLedger,
    InMemoryAuthorityEventBus,
)
from app.services.phase0_authority_event_adapter import Phase0AuthorityEventAdapter
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_pipeline import SimingEventPipeline
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_heavenly_runtime_support import SimingHeavenlyRuntimeSupport


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
            source=AuthorityEventSource(layer="L1", system="esm"),
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
                    "obligation_refs": ["obligation:letter_consequence"],
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


class _CapturingBridge:
    def __init__(self) -> None:
        self.proposal = None

    def validate_and_commit(self, proposal, *, provider_audit):
        del provider_audit
        self.proposal = proposal
        return AdaptiveBridgeValidationResult(
            accepted=True,
            proposal_id=proposal.proposal_id,
            graph_transaction_ref="story_instantiate:captured",
            runtime_node_ref="runtime:captured",
        )


class _AutonomyAwareBridge:
    def __init__(self, *, actor_autonomy, **kwargs) -> None:
        del kwargs
        self._actor_autonomy = actor_autonomy

    def validate_and_commit(self, proposal, *, provider_audit):
        del provider_audit
        if not self._actor_autonomy(proposal):
            return AdaptiveBridgeValidationResult(
                accepted=False,
                proposal_id=proposal.proposal_id,
                reason_codes=["actor_autonomy_rejected"],
            )
        return AdaptiveBridgeValidationResult(
            accepted=True,
            proposal_id=proposal.proposal_id,
            graph_transaction_ref="story_instantiate:runtime:bridge:proposal:destroy:1",
            runtime_node_ref="runtime:bridge:proposal:destroy:1",
        )


class _UnavailableProposalProvider:
    def generate_adaptive_bridge_proposals(self, **kwargs):
        del kwargs
        raise SimingLlmProviderTimeout("provider timed out")


def _support_with_candidate(state, correlation_id: str):
    support = state.siming_runtime.heavenly_support
    support._llm_provider = FakeSimingLlmCandidateProvider(
        [], adaptive_bridge_proposal_batch=_proposal_batch(correlation_id)
    )
    support._bridges = lambda context: _AcceptedBridge()
    return support


def _staging_ack_input(*, source: str, producer_ts: int) -> SimingInput:
    correlation_id = "corr:destroy:1"
    event = Phase0AuthorityEventAdapter().staging_ack_event(
        StagingAck(source=source, correlation_id=correlation_id, accepted=True),
        room_id="room:main",
        scene_id="scene:throne",
        zone_id="zone:archive",
        producer_ts=producer_ts,
    )
    return SimingInput(input_type="siming_staging_ack", source_event=event)


def _authority_destruction_event() -> AuthorityEvent:
    return _destruction_input().source_event.model_copy(
        update={
            "event_id": "result:letter:removed",
            "event_type": "esm_result_event",
            "routing": AuthorityEventRouting(
                audience_mode="room", routing_mode="event_type", target_ids=["siming"]
            ),
            "payload": {
                "result_id": "result:letter:removed",
                "result_type": "object_state_result",
                "target_object_id": "obj_letter",
                "current_state": "removed_from_surface",
                "settlement_status": "applied",
            },
        }
    )


class _CrashBeforeAuthorityPublishProducer(SimingEventProducer):
    def __init__(self, bus: InMemoryAuthorityEventBus) -> None:
        super().__init__(bus)
        self._crash_once = True

    def publish_events(self, events: list[AuthorityEvent]) -> list[AuthorityEvent]:
        if self._crash_once:
            self._crash_once = False
            raise RuntimeError("simulated crash before authority publication")
        return super().publish_events(events)


class _CrashAfterAuthorityPublishProducer(SimingEventProducer):
    def __init__(self, bus: InMemoryAuthorityEventBus) -> None:
        super().__init__(bus)
        self._crash_once = True

    def publish_events(self, events: list[AuthorityEvent]) -> list[AuthorityEvent]:
        published = super().publish_events(events)
        if self._crash_once:
            self._crash_once = False
            raise RuntimeError("simulated crash after authority publication")
        return published


class _CompleteAuthorityLedgerBus(InMemoryAuthorityEventBus):
    def authority_recovery_ledger(self) -> AuthorityRecoveryLedger:
        return AuthorityRecoveryLedger(
            event_ids=frozenset(
                event.event_id
                for event in self.list_events(
                    include_realtime=True,
                    current_only=False,
                )
            ),
            is_complete_across_restart=True,
        )


def test_active_mode_composes_shared_sqlite_graph(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SIMING_HEAVENLY_MODE", "active")
    monkeypatch.setenv("PARALLS_HEAVENLY_GRAPH_PATH", str(tmp_path / "runtime.sqlite3"))

    state = main.build_runtime_state(_reload_settings())
    try:
        assert state.siming_runtime.heavenly_support.mode == "active"
        assert state.heavenly_graph is state.character_graph_memory.graph
    finally:
        state.close()


def test_authority_destruction_seeds_durable_story_context(tmp_path) -> None:
    state = main.build_runtime_state(
        config_module.Settings(
            siming_heavenly_mode="active",
            heavenly_graph_path=str(tmp_path / "runtime.sqlite3"),
        )
    )
    try:
        event = _destruction_input().source_event.model_copy(
            update={
                "event_type": "esm_result_event",
                "payload": {
                    "result_id": "result:letter:destroyed",
                    "result_type": "object_state_result",
                    "target_object_id": "obj_letter",
                    "current_state": "removed_from_surface",
                    "settlement_status": "applied",
                },
            }
        )
        support = state.siming_runtime.heavenly_support
        support.record_authority_outcome(event)
        scope = support._scope_for(event)

        assert support._memory.get_entry(
            scope=scope, entry_id="fact:letter:removed", valid_at=100
        ) is not None
        assert support._story.read_runtime_node(
            scope=scope, node_id="runtime:N3:main", valid_at=100
        ).outcome_semantic == "resolved_with_divergence"
        assert support._story.read_runtime_node(
            scope=scope, node_id="runtime:N4:main", valid_at=100
        ).terminal is True
        assert support._story.read_runtime_node(
            scope=scope, node_id="runtime:N5:main", valid_at=100
        ).reachability == "unreachable_by_ledger"
        assert support._obligations.read(
            scope=scope, obligation_id="O2", valid_at=100
        ).status == "transformed"
        assert support._obligations.read(
            scope=scope, obligation_id="O6", valid_at=100
        ).status == "open"
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


def test_active_support_does_not_admit_ordinary_object_state_visual_fact() -> None:
    event = _destruction_input().source_event.model_copy(
        update={
            "event_type": "visual_fact_event",
            "payload": {
                "fact_type": "object_state_change",
                "target_object_id": "obj_letter",
                "relation_type": "object_state_changed",
            },
        }
    )

    assert event.payload["relation_type"] != "actor_observes_object_removal"
    assert SimingHeavenlyRuntimeSupport._event_family(event) == "visual_fact_event"


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


def test_graph_owned_tick_selects_after_same_correlation_authority_outcome(
    tmp_path,
) -> None:
    state = main.build_runtime_state(
        config_module.Settings(
            siming_heavenly_mode="active",
            heavenly_graph_path=str(tmp_path / "runtime.sqlite3"),
        )
    )
    try:
        destruction = _destruction_input().source_event.model_copy(
            update={
                "event_id": "result:letter:removed",
                "event_type": "esm_result_event",
                "routing": AuthorityEventRouting(
                    audience_mode="room", routing_mode="event_type", target_ids=["siming"]
                ),
                "payload": {
                    "result_id": "result:letter:removed",
                    "result_type": "object_state_result",
                    "target_object_id": "obj_letter",
                    "current_state": "removed_from_surface",
                    "settlement_status": "applied",
                },
            }
        )
        support = state.siming_runtime.heavenly_support
        support.record_authority_outcome(destruction)
        state.siming_runtime.tick([SimingInput(input_type="esm_result_event", source_event=destruction)])
        state.character_graph_memory.write_event(
            {
                "event_id": "char_b:observed:letter-removal",
                "event_index": 101,
                "actor_id": "char_b",
                "event_type": "character_perceived_event",
                "producer_ts": 101,
                "payload": {
                    "summary": "char_b watched the letter disappear",
                    "target_object_id": "obj_letter",
                    "percept_channel": "visual",
                    "source_ref_lineage": ["result:letter:removed"],
                },
            }
        )
        proposal = _proposal_batch("corr:destroy:1").proposals[0].model_copy(
            update={
                "causal_gap_ref": "fact:letter:removed",
                "supporting_fact_refs": ["fact:letter:removed"],
                "obligation_refs": ["O6"],
            }
        )
        support._llm_provider = FakeSimingLlmCandidateProvider(
            [],
            adaptive_bridge_proposal_batch=_proposal_batch("corr:destroy:1").model_copy(
                update={"proposals": [proposal]}
            ),
        )
        visual = destruction.model_copy(
            update={
                "event_id": "visual:char_b:letter-removal",
                "event_type": "visual_fact_event",
                "producer_ts": 102,
                "source": AuthorityEventSource(layer="L1", system="visual_fact", actor_id="char_b"),
                "routing": AuthorityEventRouting(
                    audience_mode="room", routing_mode="event_type", target_ids=["siming"]
                ),
                "payload": {
                    "target_object_id": "obj_letter",
                    "relation_type": "actor_observes_object_removal",
                    "established_fact_id": "visual:char_b:letter-removal",
                },
            }
        )

        result = state.siming_runtime.tick(
            [SimingInput(input_type="visual_fact_event", source_event=visual)]
        )

        assert "staging_request" in [output.output_type for output in result.outputs]
        assert support.find_candidate(visual) is not None
        published = SimingEventProducer(InMemoryAuthorityEventBus()).publish_outputs(
            result.outputs
        )
        assert "siming.staging_request" in [event.event_type for event in published]
    finally:
        state.close()


def test_prepare_rejects_obligation_reference_misclassified_as_supporting_fact(tmp_path) -> None:
    state = main.build_runtime_state(
        config_module.Settings(
            siming_heavenly_mode="active",
            heavenly_graph_path=str(tmp_path / "runtime.sqlite3"),
        )
    )
    try:
        destruction = _destruction_input().source_event.model_copy(
            update={
                "event_type": "esm_result_event",
                "routing": AuthorityEventRouting(
                    audience_mode="room", routing_mode="event_type", target_ids=["siming"]
                ),
                "payload": {
                    "result_id": "result:letter:removed",
                    "result_type": "object_state_result",
                    "target_object_id": "obj_letter",
                    "current_state": "removed_from_surface",
                    "settlement_status": "applied",
                },
            }
        )
        support = state.siming_runtime.heavenly_support
        support.record_authority_outcome(destruction)
        malformed = _proposal_batch("corr:destroy:1").proposals[0].model_copy(
            update={
                "pattern": "consequence_reveal",
                "causal_gap_ref": "fact:letter:removed",
                "supporting_fact_refs": ["fact:letter:removed", "obligation:O6"],
                "obligation_refs": [],
            }
        )
        support._llm_provider = FakeSimingLlmCandidateProvider(
            [],
            adaptive_bridge_proposal_batch=_proposal_batch("corr:destroy:1").model_copy(
                update={"proposals": [malformed]}
            ),
        )
        visual = destruction.model_copy(
            update={
                "event_id": "visual:char_b:letter-removal",
                "event_type": "visual_fact_event",
                "producer_ts": 102,
                "source": AuthorityEventSource(layer="L1", system="visual_fact", actor_id="char_b"),
                "payload": {
                    "target_object_id": "obj_letter",
                    "relation_type": "actor_observes_object_removal",
                    "established_fact_id": "visual:char_b:letter-removal",
                },
            }
        )

        prepared = support.prepare(
            SimingInput(input_type="visual_fact_event", source_event=visual)
        )

        assert prepared.eligible_node_refs == []
        audit = state.heavenly_graph.get_node(
            node_id="adaptive_bridge_audit:proposal:destroy:1",
            scope=support._scope_for(visual),
            valid_at=102,
        )
        assert audit is not None
        assert audit.attributes["validation"]["accepted"] is False
        assert "supporting_fact_missing" in audit.attributes["validation"]["reason_codes"]
        assert audit.attributes["proposal"]["supporting_fact_refs"] == [
            "fact:letter:removed",
            "obligation:O6",
        ]
        assert audit.attributes["proposal"]["obligation_refs"] == []
    finally:
        state.close()


@pytest.mark.parametrize(
    "event_update",
    [
        {"source": AuthorityEventSource(layer="L1", system="visual_fact")},
        {"payload": {"result_id": "result:letter:removed", "result_type": "object_state_result", "target_object_id": "obj_letter", "current_state": "removed_from_surface", "settlement_status": "rejected"}},
        {"payload": {"result_id": "result:letter:removed", "result_type": "constraint_state_result", "target_object_id": "obj_letter", "current_state": "removed_from_surface", "settlement_status": "applied"}},
    ],
)
def test_non_authoritative_or_non_applied_destruction_does_not_seed_graph(tmp_path, event_update) -> None:
    state = main.build_runtime_state(
        config_module.Settings(
            siming_heavenly_mode="active",
            heavenly_graph_path=str(tmp_path / "runtime.sqlite3"),
        )
    )
    try:
        event = _destruction_input().source_event.model_copy(
            update={
                "event_type": "esm_result_event",
                "payload": {
                    "result_id": "result:letter:removed",
                    "result_type": "object_state_result",
                    "target_object_id": "obj_letter",
                    "current_state": "removed_from_surface",
                    "settlement_status": "applied",
                },
                **event_update,
            }
        )
        support = state.siming_runtime.heavenly_support

        assert support.record_authority_outcome(event) is None
        assert support._memory.get_entry(
            scope=support._scope_for(event),
            entry_id="fact:letter:removed",
            valid_at=100,
        ) is None
        assert support._story.read_runtime_node(
            scope=support._scope_for(event), node_id="runtime:N3:main", valid_at=100
        ) is None
    finally:
        state.close()


def test_active_candidate_staging_contract_survives_runtime_restart(tmp_path) -> None:
    graph_path = tmp_path / "runtime.sqlite3"
    settings = config_module.Settings(
        siming_heavenly_mode="active", heavenly_graph_path=str(graph_path)
    )
    first_state = main.build_runtime_state(settings)
    try:
        support = _support_with_candidate(first_state, "corr:destroy:1")
        prepared = support.prepare(_destruction_input())
        assert prepared.eligible_node_refs == ["runtime:bridge:proposal:destroy:1"]
    finally:
        first_state.close()

    second_state = main.build_runtime_state(settings)
    try:
        candidate = second_state.siming_runtime.heavenly_support.find_candidate(
            _destruction_input().source_event
        )
        assert candidate is not None
        assert candidate.staging_request.node_id == "runtime:bridge:proposal:destroy:1"
        assert candidate.staging_request.obligation_id == "letter_consequence"
        assert candidate.staging_request.resource_match.accepted is True
        assert candidate.proposal.target_actor_id == "char_b"
    finally:
        second_state.close()


def _prepare_staged_graph_dispatch(state) -> SimingInput:
    support = state.siming_runtime.heavenly_support
    destruction = _authority_destruction_event()
    support.record_authority_outcome(destruction)
    state.siming_runtime.tick(
        [SimingInput(input_type="esm_result_event", source_event=destruction)]
    )
    state.character_graph_memory.write_event(
        {
            "event_id": "char_b:observed:letter-removal",
            "event_index": 101,
            "actor_id": "char_b",
            "event_type": "character_perceived_event",
            "producer_ts": 101,
            "payload": {
                "summary": "char_b watched the letter disappear",
                "target_object_id": "obj_letter",
                "percept_channel": "visual",
                "source_ref_lineage": ["result:letter:removed"],
            },
        }
    )
    proposal = _proposal_batch("corr:destroy:1").proposals[0].model_copy(
        update={
            "causal_gap_ref": "fact:letter:removed",
            "supporting_fact_refs": ["fact:letter:removed"],
            "obligation_refs": ["O6"],
        }
    )
    support._llm_provider = FakeSimingLlmCandidateProvider(
        [],
        adaptive_bridge_proposal_batch=_proposal_batch("corr:destroy:1").model_copy(
            update={"proposals": [proposal]}
        ),
    )
    visual = destruction.model_copy(
        update={
            "event_id": "visual:char_b:letter-removal",
            "event_type": "visual_fact_event",
            "producer_ts": 102,
            "source": AuthorityEventSource(
                layer="L1", system="visual_fact", actor_id="char_b"
            ),
            "routing": AuthorityEventRouting(
                audience_mode="room", routing_mode="event_type", target_ids=["siming"]
            ),
            "payload": {
                "target_object_id": "obj_letter",
                "relation_type": "actor_observes_object_removal",
                "established_fact_id": "visual:char_b:letter-removal",
            },
        }
    )
    prepared = support.prepare(
        SimingInput(input_type="visual_fact_event", source_event=visual)
    )
    support.select_for_staging(prepared, prepared.eligible_node_refs[0])
    for source, producer_ts in (("godot", 201), ("character", 202)):
        state.siming_runtime.tick(
            [_staging_ack_input(source=source, producer_ts=producer_ts)]
        )
    return _staging_ack_input(source="esm", producer_ts=203)


def test_graph_dispatch_stays_unknown_after_crash_before_authority_publication_without_durable_ledger(
    tmp_path,
) -> None:
    graph_path = tmp_path / "runtime.sqlite3"
    settings = config_module.Settings(
        siming_heavenly_mode="active", heavenly_graph_path=str(graph_path)
    )
    first_state = main.build_runtime_state(settings)
    try:
        final_ack = _prepare_staged_graph_dispatch(first_state)
        first_bus = InMemoryAuthorityEventBus()
        crashing_pipeline = SimingEventPipeline(
            bus=first_bus,
            consumer=SimingEventConsumer(),
            runtime=first_state.siming_runtime,
            producer=_CrashBeforeAuthorityPublishProducer(first_bus),
            audit_writer=SimingAuditWriter(),
        )
        with pytest.raises(RuntimeError, match="before authority publication"):
            crashing_pipeline.handle_event(final_ack.source_event)
        assert first_bus.list_events(event_type="siming.opportunity") == []
    finally:
        first_state.close()

    second_state = main.build_runtime_state(settings)
    try:
        recovery_bus = InMemoryAuthorityEventBus()
        audit_writer = SimingAuditWriter()
        recovery_pipeline = SimingEventPipeline(
            bus=recovery_bus,
            consumer=SimingEventConsumer(),
            runtime=second_state.siming_runtime,
            producer=SimingEventProducer(recovery_bus),
            audit_writer=audit_writer,
        )
        recovery_pipeline.handle_event(final_ack.source_event)

        dispatches = recovery_bus.list_events(event_type="siming.opportunity")
        assert dispatches == []
        assert [record.reason for record in audit_writer.find_by_correlation(
            room_id=final_ack.source_event.room_id,
            correlation_id=final_ack.source_event.correlation_id,
        )] == ["dispatch_recovery_authority_unknown"]
    finally:
        second_state.close()


def test_graph_dispatch_retries_after_prepublication_crash_with_complete_durable_ledger(
    tmp_path,
) -> None:
    graph_path = tmp_path / "runtime.sqlite3"
    settings = config_module.Settings(
        siming_heavenly_mode="active", heavenly_graph_path=str(graph_path)
    )
    first_state = main.build_runtime_state(settings)
    try:
        final_ack = _prepare_staged_graph_dispatch(first_state)
        first_bus = InMemoryAuthorityEventBus()
        crashing_pipeline = SimingEventPipeline(
            bus=first_bus,
            consumer=SimingEventConsumer(),
            runtime=first_state.siming_runtime,
            producer=_CrashBeforeAuthorityPublishProducer(first_bus),
            audit_writer=SimingAuditWriter(),
        )
        with pytest.raises(RuntimeError, match="before authority publication"):
            crashing_pipeline.handle_event(final_ack.source_event)
        assert first_bus.list_events(event_type="siming.opportunity") == []
    finally:
        first_state.close()

    second_state = main.build_runtime_state(settings)
    try:
        recovery_bus = _CompleteAuthorityLedgerBus()
        recovery_pipeline = SimingEventPipeline(
            bus=recovery_bus,
            consumer=SimingEventConsumer(),
            runtime=second_state.siming_runtime,
            producer=SimingEventProducer(recovery_bus),
            audit_writer=SimingAuditWriter(),
        )
        recovery_pipeline.handle_event(final_ack.source_event)

        dispatches = recovery_bus.list_events(event_type="siming.opportunity")
        assert len(dispatches) == 1
        assert dispatches[0].event_id == (
            "siming:dispatch_intent:207:siming_staging_ack:203:esm:corr:destroy:1"
        )
    finally:
        second_state.close()


def test_graph_dispatch_is_not_republished_after_authority_publication_crash(tmp_path) -> None:
    graph_path = tmp_path / "runtime.sqlite3"
    settings = config_module.Settings(
        siming_heavenly_mode="active", heavenly_graph_path=str(graph_path)
    )
    authority_bus = InMemoryAuthorityEventBus()
    first_state = main.build_runtime_state(settings)
    try:
        final_ack = _prepare_staged_graph_dispatch(first_state)
        crashing_pipeline = SimingEventPipeline(
            bus=authority_bus,
            consumer=SimingEventConsumer(),
            runtime=first_state.siming_runtime,
            producer=_CrashAfterAuthorityPublishProducer(authority_bus),
            audit_writer=SimingAuditWriter(),
        )
        with pytest.raises(RuntimeError, match="after authority publication"):
            crashing_pipeline.handle_event(final_ack.source_event)
        assert len(authority_bus.list_events(event_type="siming.opportunity")) == 1
    finally:
        first_state.close()

    second_state = main.build_runtime_state(settings)
    try:
        recovery_pipeline = SimingEventPipeline(
            bus=authority_bus,
            consumer=SimingEventConsumer(),
            runtime=second_state.siming_runtime,
            producer=SimingEventProducer(authority_bus),
            audit_writer=SimingAuditWriter(),
        )
        recovery_pipeline.handle_event(final_ack.source_event)

        assert len(authority_bus.list_events(event_type="siming.opportunity")) == 1
        assert second_state.siming_runtime.heavenly_support.has_dispatch(
            final_ack.source_event
        ) is True
    finally:
        second_state.close()


def test_graph_dispatch_stays_unknown_after_restart_without_durable_authority_ledger(
    tmp_path,
) -> None:
    graph_path = tmp_path / "runtime.sqlite3"
    settings = config_module.Settings(
        siming_heavenly_mode="active", heavenly_graph_path=str(graph_path)
    )
    first_state = main.build_runtime_state(settings)
    try:
        final_ack = _prepare_staged_graph_dispatch(first_state)
        first_bus = InMemoryAuthorityEventBus()
        crashing_pipeline = SimingEventPipeline(
            bus=first_bus,
            consumer=SimingEventConsumer(),
            runtime=first_state.siming_runtime,
            producer=_CrashAfterAuthorityPublishProducer(first_bus),
            audit_writer=SimingAuditWriter(),
        )
        with pytest.raises(RuntimeError, match="after authority publication"):
            crashing_pipeline.handle_event(final_ack.source_event)
        assert len(first_bus.list_events(event_type="siming.opportunity")) == 1
    finally:
        first_state.close()

    second_state = main.build_runtime_state(settings)
    try:
        restarted_bus = InMemoryAuthorityEventBus()
        audit_writer = SimingAuditWriter()
        recovery_pipeline = SimingEventPipeline(
            bus=restarted_bus,
            consumer=SimingEventConsumer(),
            runtime=second_state.siming_runtime,
            producer=SimingEventProducer(restarted_bus),
            audit_writer=audit_writer,
        )
        recovery_pipeline.handle_event(final_ack.source_event)

        assert restarted_bus.list_events(event_type="siming.opportunity") == []
        assert [record.reason for record in audit_writer.find_by_correlation(
            room_id=final_ack.source_event.room_id,
            correlation_id=final_ack.source_event.correlation_id,
        )] == ["dispatch_recovery_authority_unknown"]
    finally:
        second_state.close()


def test_active_bridge_rejects_proactive_actor_under_supervision(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(main, "SimingAdaptiveBridge", _AutonomyAwareBridge)
    state = main.build_runtime_state(
        config_module.Settings(
            siming_heavenly_mode="active",
            heavenly_graph_path=str(tmp_path / "runtime.sqlite3"),
        )
    )
    try:
        state.character_agent_runtime.apply_supervision_authorization(
            {
                "authorization_id": "auth:char-b:quiet",
                "actor_id": "char_b",
                "approved_level": "medium",
                "approved_by": "strategy_service",
                "approval_reason": "proactive initiation is forbidden",
                "constraints": {"allow_proactive_initiation": False},
                "effective_from_ts": 100,
                "producer_ts": 100,
            }
        )
        support = state.siming_runtime.heavenly_support
        support._llm_provider = FakeSimingLlmCandidateProvider(
            [], adaptive_bridge_proposal_batch=_proposal_batch("corr:destroy:1")
        )

        prepared = support.prepare(_destruction_input())

        assert prepared.owns_event_family is True
        assert prepared.eligible_node_refs == []
    finally:
        state.close()


def test_active_bridge_rejects_proposal_for_unsupported_actor(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(main, "SimingAdaptiveBridge", _AutonomyAwareBridge)
    state = main.build_runtime_state(
        config_module.Settings(
            siming_heavenly_mode="active",
            heavenly_graph_path=str(tmp_path / "runtime.sqlite3"),
        )
    )
    try:
        support = state.siming_runtime.heavenly_support
        proposal_batch = _proposal_batch("corr:destroy:1")
        unsupported_proposal = proposal_batch.proposals[0].model_copy(
            update={"target_actor_id": "char_unknown"}
        )
        support._llm_provider = FakeSimingLlmCandidateProvider(
            [],
            adaptive_bridge_proposal_batch=proposal_batch.model_copy(
                update={"proposals": [unsupported_proposal]}
            ),
        )

        prepared = support.prepare(_destruction_input())

        assert prepared.owns_event_family is True
        assert prepared.eligible_node_refs == []
    finally:
        state.close()


def test_active_support_returns_non_activatable_result_when_llm_is_unavailable(
    tmp_path,
) -> None:
    state = main.build_runtime_state(
        config_module.Settings(
            siming_heavenly_mode="active",
            heavenly_graph_path=str(tmp_path / "runtime.sqlite3"),
        )
    )
    try:
        support = state.siming_runtime.heavenly_support
        support._llm_provider = _UnavailableProposalProvider()

        prepared = support.prepare(_destruction_input())

        assert prepared.owns_event_family is False
        assert prepared.eligible_node_refs == []
        assert prepared.degraded_reason.startswith("llm_unavailable:")
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
