from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.semantic_authority import (
    SemanticEffectCommand,
    SemanticSettlementAuthority,
    SemanticSurvivalStateActionCommand,
)
from app.gameplay.semantic_effects import EffectApplication, ResistanceProfile, StateDefinition
from app.gameplay.semantic_registry import SemanticRegistry, StateLifecyclePolicy, TagAssignment, TagDefinition
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.gameplay.survival_runtime import SurvivalAuthority


ACTOR = "character:ava"
STREAM = f"gameplay:survival:{ACTOR}"
WEATHER_FRONT_EVENT = "gameplay.ecology.weather_front.propagated:event:front-1"


def _registry(*, register_actions: bool = False) -> SemanticRegistry:
    registry = SemanticRegistry()
    registry.register_tag(TagDefinition(tag_ref="type:character", category="type", version="1"))
    registry.assign_tag(TagAssignment(entity_ref=ACTOR, tag_ref="type:character", source_ref="fixture", revision=1))
    registry.register_state_lifecycle(
        StateLifecyclePolicy(
            state_ref="state:cold",
            effect_ref="effect:cold_exposure",
            lifecycle="scheduled",
            revision="1",
            owner_ref=SurvivalAuthority._PRINCIPAL,
            stream_pattern="gameplay:survival:{actor_ref}",
            opened_event_type="gameplay.survival.obligation_opened",
            settled_event_type="gameplay.survival.obligation_settled",
            cancelled_event_type="gameplay.survival.obligation_cancelled",
            fragment_builder_ref="SurvivalAuthority.build_state_expiry_fragment",
            projection_scope="project",
        )
    )
    if register_actions:
        registry.register_survival_state_action_effects()
    return registry


def _weather_front_snapshot(registry: SemanticRegistry):
    return registry.build_snapshot(
        ACTOR,
        source_revision_vector={"semantic": 1, "ecology": 7},
        relation_refs=(WEATHER_FRONT_EVENT,),
    )


def _open_cold_state(store: GameplayEventStore) -> None:
    result = SurvivalAuthority(store=store).apply_effect_state(
        command=GameplayCommandEnvelope(
            command_id="command:survival:weather-front:seed",
            command_type="gameplay.survival.apply_state",
            command_version=1,
            principal_ref=SurvivalAuthority._PRINCIPAL,
            actor_ref=ACTOR,
            project_ref="project:demo",
            idempotency_key="survival:weather-front:seed",
            expected_revisions={STREAM: 0},
            causation_id="cause:survival:weather-front:seed",
            correlation_id="corr:survival:weather-front:seed",
            source_ref="proposal:fixture",
            submitted_at="fixture",
            pinned_revisions={"semantic": 1},
            payload={},
        ),
        application=EffectApplication(
            effect_ref="effect:cold_exposure",
            target_component_ref=ACTOR,
            magnitude=100,
            stack_key="cold",
            expires_at_tick=8,
            causal_chain_id="chain:survival:weather-front:seed",
        ),
        resistance=ResistanceProfile(
            effect_ref="effect:cold_exposure",
            source_ref=ACTOR,
            modifier_basis_points=0,
            revision=1,
        ),
        definition=StateDefinition(
            state_ref="state:cold",
            stack_policy="add",
            stack_limit=2,
            expiry_policy="scheduled",
        ),
    )
    assert result.committed


def test_weather_front_survival_contract_matrix_remains_closed_to_four_existing_rows() -> None:
    survival_contracts = tuple(
        contract
        for contract in SemanticRegistry.closed_lifecycle_owner_contracts()
        if contract.owner_ref == SurvivalAuthority._PRINCIPAL
    )

    assert {(contract.effect_ref, contract.state_ref) for contract in survival_contracts} == {
        ("effect:cold_exposure", "state:cold"),
        ("effect:dehydration_exposure", "state:dehydrated"),
        ("effect:fatigue_exposure", "state:fatigued"),
        ("effect:heat_exposure", "state:overheated"),
    }
    assert all("gameplay.ecology.weather_front.propagated" not in contract.event_types for contract in survival_contracts)


def test_weather_front_shaped_survival_apply_is_zero_write_without_owner_contract() -> None:
    store = GameplayEventStore()
    registry = _registry()
    snapshot = _weather_front_snapshot(registry)

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_closed_survival_state(
        SemanticEffectCommand(
            command_id="command:weather-front:survival:apply",
            idempotency_key="weather-front:survival:apply",
            principal_ref="authority:semantic",
            owner_ref=SurvivalAuthority._PRINCIPAL,
            stream_id=STREAM,
            expected_revision=0,
            effect_ref="effect:cold_exposure",
            target_ref=ACTOR,
            semantic_snapshot=snapshot,
            expected_snapshot_digest=snapshot.digest,
            causal_parent_refs=(WEATHER_FRONT_EVENT,),
            evidence_refs=(WEATHER_FRONT_EVENT,),
            privacy_scope="project",
        ),
        application=EffectApplication(
            effect_ref="effect:cold_exposure",
            target_component_ref=ACTOR,
            magnitude=100,
            stack_key="cold",
            expires_at_tick=8,
            causal_chain_id="chain:weather-front:survival:apply",
        ),
        resistance=ResistanceProfile(
            effect_ref="effect:cold_exposure",
            source_ref=ACTOR,
            modifier_basis_points=0,
            revision=1,
        ),
        state=StateDefinition(
            state_ref="state:cold",
            stack_policy="add",
            stack_limit=2,
            expiry_policy="scheduled",
        ),
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "semantic_closed_registry_revision_mismatch"
    assert store.read_events() == []
    assert store.list_outbox() == []


def test_weather_front_shaped_survival_action_is_zero_write_without_owner_contract() -> None:
    store = GameplayEventStore()
    _open_cold_state(store)
    registry = _registry(register_actions=True)
    snapshot = _weather_front_snapshot(registry)

    result = SemanticSettlementAuthority(store=store, registry=registry).settle_registered_survival_state_action(
        SemanticSurvivalStateActionCommand(
            command_id="command:weather-front:survival:action",
            idempotency_key="weather-front:survival:action",
            principal_ref="authority:semantic",
            owner_ref=SurvivalAuthority._PRINCIPAL,
            stream_id=STREAM,
            expected_revision=2,
            effect_ref="effect:state_dispel",
            target_ref=ACTOR,
            state_ref="state:cold",
            semantic_snapshot=snapshot,
            expected_snapshot_digest=snapshot.digest,
            reason_ref="reason:weather-front",
            privacy_scope="project",
        )
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "semantic_survival_state_action_route_mismatch"
    assert len(store.read_events()) == 2
    assert {event.event_type for event in store.read_events()} == {
        "gameplay.survival.state_applied",
        "gameplay.survival.obligation_opened",
    }
