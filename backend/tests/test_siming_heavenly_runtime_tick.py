from app.models.authority_event import (
    AuthorityEvent,
    AuthorityEventRouting,
    AuthorityEventSource,
)
from app.models.siming_event import SimingOutput
from app.models.siming_event import SimingInput
from app.models.siming_adaptive_bridge import AdaptiveBridgeNodeProposal
from app.models.siming_heavenly_graph import HeavenlyGraphScope
from app.models.siming_resource_capability import (
    ResourceCapabilityPackage,
    ResourceMatch,
    ResourceRealizationRequest,
    StagingRequest,
    StagingResult,
)
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_heavenly_runtime_support import (
    PreparedHeavenlyCandidate,
    PreparedHeavenlyDecision,
)
from app.services.siming_runtime import SimingRuntime


def _event(event_type: str, *, payload: dict[str, object]) -> AuthorityEvent:
    return AuthorityEvent(
        event_id=f"event:{event_type}",
        event_type=event_type,
        producer_ts=100,
        room_id="room:main",
        scene_id="scene:throne",
        zone_id="zone:archive",
        source=AuthorityEventSource(layer="L1", system="test"),
        routing=AuthorityEventRouting(
            audience_mode="broadcast", routing_mode="event_type"
        ),
        priority="p2",
        durability="replayable",
        causation_id="cause:1",
        correlation_id="corr:destroy:1",
        payload=payload,
    )


def test_consumer_admits_structured_staging_ack() -> None:
    inputs = SimingEventConsumer().handle_event(
        _event(
            "siming_staging_ack",
            payload={
                "source": "character",
                "correlation_id": "corr:destroy:1",
                "accepted": True,
            },
        )
    )

    assert len(inputs) == 1
    assert inputs[0].input_type == "siming_staging_ack"


def test_producer_publishes_staging_request_as_non_catalyst_event() -> None:
    bus = InMemoryAuthorityEventBus()
    event = SimingEventProducer(bus).publish_outputs(
        [
            SimingOutput(
                output_type="staging_request",
                room_id="room:main",
                scene_id="scene:throne",
                zone_id="zone:archive",
                causation_id="event:destroy",
                correlation_id="corr:destroy:1",
                producer_ts=101,
                payload={"node_id": "runtime:bridge:proposal:destroy:1"},
            )
        ]
    )

    assert [item.event_type for item in event] == ["siming.staging_request"]


class _ActiveHeavenlySupport:
    def __init__(self) -> None:
        request = ResourceRealizationRequest(
            node_id="runtime:bridge:proposal:destroy:1",
            actor_bindings={"speaker": "char_b", "listener": "char_c"},
            target_object_id="obj_letter",
            target_environment_id="env_lamp",
            required_realization_keys=["look_at_target"],
            camera_pattern="two_actor_confrontation",
            semantic_purpose="private_confrontation",
            location_state="throne_room:letter_removed",
        )
        match = ResourceMatch(
            accepted=True,
            capability=ResourceCapabilityPackage(
                capability_id="main_demo_throne_room",
                asset_bundle="main_demo_throne_room",
                scene_refs=["scenes/phase0/MainDemo.tscn"],
                actor_ids=["char_b", "char_c"],
                object_ids=["obj_letter"],
                environment_ids=["env_lamp"],
                realization_keys=["look_at_target"],
                semantic_purposes=["private_confrontation"],
                load_cost=0.0,
                loaded=True,
                cooldown_until=0,
            ),
            realization_signature=request.signature("main_demo_throne_room"),
        )
        self.request = StagingRequest(
            scope=HeavenlyGraphScope(
                world_id="world:demo",
                session_id="session:demo",
                story_branch_id="branch:main",
                room_id="room:main",
                scene_id="scene:throne",
            ),
            node_id=request.node_id,
            correlation_id="corr:destroy:1",
            obligation_id="obligation:letter_consequence",
            recorded_at=100,
            resource_match=match,
        )
        self.prepared = PreparedHeavenlyDecision(
            mode="active",
            event_family="evidence_destruction_consequence",
            owns_event_family=True,
            correlation_id="corr:destroy:1",
            context_hash="context:destroy:1",
            eligible_node_refs=[self.request.node_id],
            eligible_candidates=[
                PreparedHeavenlyCandidate(
                    node_ref=self.request.node_id,
                    proposal=AdaptiveBridgeNodeProposal(
                        proposal_id="proposal:destroy:1",
                        pattern="private_confrontation",
                        correlation_id="corr:destroy:1",
                        causal_gap_ref="event:world_fact_event",
                        title="Confront the destruction",
                        target_actor_id="char_b",
                        supporting_fact_refs=["event:world_fact_event"],
                        realization_request=request,
                        autonomy_reason="char_b chooses to respond",
                    ),
                    staging_request=self.request,
                )
            ],
        )
        self.selected = []

    def prepare(self, siming_input: SimingInput) -> PreparedHeavenlyDecision:
        assert siming_input.source_event.correlation_id == "corr:destroy:1"
        return self.prepared

    def select_for_staging(
        self, prepared: PreparedHeavenlyDecision, selected_node_ref: str
    ) -> StagingRequest:
        assert prepared is self.prepared
        self.selected.append(selected_node_ref)
        return self.request


def test_active_graph_owned_event_stages_before_dispatch() -> None:
    support = _ActiveHeavenlySupport()
    event = _event(
        "world_fact_event",
        payload={"target_ref": "obj_letter", "current_state": "removed_from_surface"},
    )

    result = SimingRuntime(heavenly_support=support).tick(
        [SimingInput(input_type="world_fact_event", source_event=event)]
    )

    assert support.selected == ["runtime:bridge:proposal:destroy:1"]
    assert [output.output_type for output in result.outputs].count(
        "staging_request"
    ) == 1
    assert [output.output_type for output in result.outputs].count(
        "dispatch_intent"
    ) == 0


class _StagingHeavenlySupport(_ActiveHeavenlySupport):
    def __init__(self) -> None:
        super().__init__()
        self.acks = []

    def record_staging_ack(self, event: AuthorityEvent) -> StagingRequest:
        self.acks.append(event.payload["source"])
        return self.request

    def complete_staging(self, event: AuthorityEvent) -> StagingResult | None:
        if len(self.acks) != 3:
            return None
        return StagingResult(
            node_id=self.request.node_id,
            correlation_id=event.correlation_id,
            status="staged",
            story_node_lifecycle="staged",
            obligation_status="open",
            realization_signature=self.request.resource_match.realization_signature,
        )

    def find_candidate(self, event: AuthorityEvent) -> PreparedHeavenlyCandidate:
        return self.prepared.eligible_candidates[0]


def test_all_staging_acks_release_one_dispatch_intent() -> None:
    support = _StagingHeavenlySupport()
    inputs = [
        SimingInput(
            input_type="siming_staging_ack",
            source_event=_event(
                "siming_staging_ack",
                payload={
                    "source": source,
                    "correlation_id": "corr:destroy:1",
                    "accepted": True,
                },
            ),
        )
        for source in ("godot", "character", "esm")
    ]

    result = SimingRuntime(heavenly_support=support).tick(inputs)

    assert support.acks == ["godot", "character", "esm"]
    assert [output.output_type for output in result.outputs].count(
        "dispatch_intent"
    ) == 1
