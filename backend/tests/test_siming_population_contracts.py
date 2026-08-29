from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.character_agent.models.simulation_seed import (
    CharacterContinuityCommand,
    CharacterMemoryCandidate,
    CharacterSimulationSeedCandidate,
)
from app.models.authority_event import (
    AuthorityEvent,
    AuthorityEventRouting,
    AuthorityEventSource,
)
from app.population_continuity.siming_contracts import (
    PopulationCadenceInput,
    PopulationProjection,
    PopulationReadSet,
)


def cadence(**updates: object) -> PopulationCadenceInput:
    values: dict[str, object] = {
        "cadence_ref": "cadence:bakery:1",
        "cadence_owner_ref": "owner:world-mode",
        "world_ref": "world:bakery",
        "mode_ref": "mode:bakery",
        "mode_revision": "mode:v1",
        "source_refs": ("source:world:bakery",),
        "source_revision_vector": {"world:bakery": 1},
        "window_start": 100,
        "window_end": 101,
        "base_checkpoint_ref": "checkpoint:bakery:1",
        "base_checkpoint_digest": "sha256:checkpoint",
        "base_revision_vector": {"world:bakery": 1},
        "policy_revision": "policy:v1",
        "selector_revision": "selector:v1",
        "ruleset_revision": "ruleset:v1",
        "deterministic_seed": "seed:bakery:1",
        "catch_up_limit": 2,
        "budget": 2,
        "report_scope": "organization:summary",
    }
    values.update(updates)
    return PopulationCadenceInput(**values)


def projection(ref: str, **payload: object) -> PopulationProjection:
    return PopulationProjection(
        ref=ref,
        scope="organization:summary",
        revision_vector={"world:bakery": 1},
        payload=payload,
    )


def cadence_event(**payload: object) -> AuthorityEvent:
    event_payload = {"population_cadence": cadence(**payload).model_dump()}
    return AuthorityEvent(
        event_id="event:cadence:1",
        event_type="population_cadence_event",
        producer_ts=100,
        room_id="room:bakery",
        scene_id="scene:bakery",
        zone_id="zone:bakery",
        source=AuthorityEventSource(layer="world", system="world-mode"),
        routing=AuthorityEventRouting(audience_mode="authority", routing_mode="broadcast"),
        priority="p1",
        ttl=None,
        durability="replayable",
        causation_id="cause:cadence:1",
        correlation_id="corr:cadence:1",
        payload=event_payload,
    )


def test_missing_cadence_source_pin_is_rejected() -> None:
    with pytest.raises(ValidationError, match="cadence_source_pin_incomplete"):
        PopulationCadenceInput(**cadence().model_dump(exclude={"source_refs"}))


def test_read_set_digest_is_stable_under_projection_reorder() -> None:
    first = PopulationReadSet.from_inputs(cadence(), (projection("b", value=2), projection("a", value=1)))
    second = PopulationReadSet.from_inputs(cadence(), (projection("a", value=1), projection("b", value=2)))
    assert first.read_set_digest == second.read_set_digest
    assert first.projections == second.projections


def test_actor_scoped_seed_is_pending_and_not_a_memory_record() -> None:
    candidate = CharacterMemoryCandidate(
        candidate_id="memory-candidate:1",
        actor_ref="character:char_a",
        candidate_kind="event_experience",
        source_event_refs=("event:1",),
        event_valid_at=100,
        knowledge_available_at=100,
        exposure_basis="affected_directly",
        summary="A delivery was delayed.",
        confidence=0.8,
        salience=0.5,
        visibility_scope="actor_observable",
        privacy_disposition="actor_private",
        materialization_policy="pending",
        dedup_key="event:1",
        source_revision_vector={"world:bakery": 1},
    )
    seed = CharacterSimulationSeedCandidate(
        seed_id="seed:1",
        actor_ref="character:char_a",
        world_ref="world:bakery",
        from_tick=100,
        to_tick=101,
        source_event_refs=("event:1",),
        source_owner_receipt_refs=("receipt:owner:1",),
        state_deltas={"need_tension": {"physiological_pressure": 0.1}},
        memory_candidates=(candidate,),
        drift_candidates=(),
        activation_hints=(),
        presentation_seed={"task": "replenish_family_food"},
        visibility_scope="actor_private",
        privacy_disposition="actor_private",
        source_revision_vector={"world:bakery": 1},
        ruleset_revision="ruleset:v1",
        selector_revision="selector:v1",
        deterministic_seed="seed:deterministic",
        owner_effect_status="settled",
        idempotency_key="seed:1",
    )
    assert seed.materialization_status == "pending"
    assert not hasattr(seed, "memory_record")


def test_world_effect_continuity_command_without_owner_receipt_rejects() -> None:
    with pytest.raises(ValidationError, match="owner_settlement_required"):
        CharacterContinuityCommand(
            command_id="command:1",
            actor_ref="character:char_a",
            source_owner_receipt_refs=(),
            expected_character_revision=0,
            source_revision_vector={"world:bakery": 1},
            state_delta={"world_effect": "open"},
            memory_candidate_refs=(),
            exposure_evidence={},
            policy_revision="policy:v1",
            idempotency_key="command:1",
            world_effect_required=True,
        )
