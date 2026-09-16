from __future__ import annotations

import pytest

from app.character_agent.models.simulation_seed import (
    CharacterModuleDelta,
    CharacterContinuityCommand,
    CharacterMemoryCandidate,
    CharacterSimulationSeedCandidate,
)
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.gameplay.runtime_state import StateGroupDefinition, StateGroupRegistry


def command_for_char_a(**updates: object) -> CharacterContinuityCommand:
    default_candidate = CharacterMemoryCandidate(
        candidate_id="memory:char_a:default",
        actor_ref="character:char_a",
        candidate_kind="event_experience",
        source_event_refs=("evt:frost:101",),
        event_valid_at=101,
        event_recorded_at=101,
        knowledge_available_at=101,
        exposure_basis="affected_directly",
        summary="frost reduced the crop supply",
        confidence=0.8,
        salience=0.7,
        visibility_scope="actor:self",
        privacy_disposition="actor_private",
        materialization_policy="on_activation",
        dedup_key="char_a:frost:default",
        source_revision_vector={"world:bakery": 101},
    )
    values: dict[str, object] = {
        "command_id": "continuity:char_a:101",
        "actor_ref": "character:char_a",
        "source_owner_receipt_refs": ("receipt:frost:101",),
        "expected_character_revision": 0,
        "source_revision_vector": {"world:bakery": 101},
        "state_delta": {"need_tension": {"physiological_pressure": 0.12}},
        "memory_candidate_refs": (default_candidate.candidate_id,),
        "exposure_evidence": {
            "exposure_basis": "affected_directly",
            "memory_candidates": [default_candidate.model_dump(mode="json")],
        },
        "policy_revision": "policy:character-continuity:v1",
        "idempotency_key": "continuity:char_a:101",
    }
    values.update(updates)
    return CharacterContinuityCommand(**values)


def command_with_presentation_seed() -> CharacterContinuityCommand:
    return command_for_char_a(
        state_delta={
            "presentation_seed": {"task": "replenish_family_food"},
            "activation_hints": ["supply_pressure"],
        }
    )


def command_with_memory_candidate(*, exposure_basis: str) -> CharacterContinuityCommand:
    candidate = CharacterMemoryCandidate(
        candidate_id="memory:char_a:101",
        actor_ref="character:char_a",
        candidate_kind="event_experience",
        source_event_refs=("evt:frost:101",),
        event_valid_at=101,
        event_recorded_at=101,
        knowledge_available_at=101,
        exposure_basis=exposure_basis,
        summary="frost reduced the crop supply",
        confidence=0.8,
        salience=0.7,
        visibility_scope="actor:self",
        privacy_disposition="actor_private",
        materialization_policy="on_activation",
        dedup_key=f"char_a:frost:{exposure_basis}",
        source_revision_vector={"world:bakery": 101},
    )
    return command_for_char_a(
        memory_candidate_refs=(candidate.candidate_id,),
        exposure_evidence={
            "exposure_basis": exposure_basis,
            "memory_candidates": [candidate.model_dump(mode="json")],
        },
        idempotency_key=f"continuity:char_a:{exposure_basis}",
        command_id=f"continuity:char_a:{exposure_basis}",
    )


class _CheckpointFailingContinuityStore:
    def __init__(self) -> None:
        self.current_states: list[dict[str, object]] = []
        self.fail_checkpoint_at = 16

    def write_current_state(self, *, snapshot: dict[str, object], **_: object) -> None:
        self.current_states.append(snapshot)

    def write_snapshot(self, *, snapshot: dict[str, object], **_: object) -> None:
        timeline = snapshot.get("session_timeline")
        if isinstance(timeline, list) and len(timeline) == self.fail_checkpoint_at:
            self.fail_checkpoint_at = -1
            raise RuntimeError("checkpoint_write_failed")

    def read_current_state(self, _: str) -> None:
        return None

    def read_snapshot(self, _: str) -> None:
        return None


def correction_for_char_a() -> CharacterContinuityCommand:
    return command_for_char_a(
        command_id="continuity:char_a:102",
        idempotency_key="continuity:char_a:102",
        expected_character_revision=1,
        source_owner_receipt_refs=("receipt:frost:102",),
        source_revision_vector={"world:bakery": 102},
        state_delta={"supersedes": "seed:character:char_a:supply"},
    )


def test_seed_command_updates_state_but_defers_memory_materialization() -> None:
    runtime = CharacterAgentRuntime()
    receipt = runtime.apply_character_continuity_command(command_for_char_a())
    assert receipt.status == "committed"
    assert runtime.get_need_tension_state_record("char_a").physiological_pressure > 0
    assert runtime.get_pending_seed_candidates("char_a")
    assert runtime.get_memory_bundle("char_a")["event_memories"] == []


def test_module_delta_is_typed_and_preserved_in_shared_seed_projection() -> None:
    runtime = CharacterAgentRuntime()
    receipt = runtime.apply_character_continuity_command(
        command_for_char_a(
            module_deltas=(
                CharacterModuleDelta(
                    group_id="character.commitments",
                    definition_version="1.0.0",
                    projection_schema_version=1,
                    expected_group_revision=0,
                    source_ref="evt:order:101",
                    payload={"next_due_tick": 120, "obligation_ref": "order:bakery:1"},
                ),
            ),
        )
    )

    assert receipt.status == "committed"
    projection = runtime.get_seed_projection("char_a")
    assert projection["module_deltas"][0]["group_id"] == "character.commitments"


def test_module_delta_rejects_duplicate_group_updates() -> None:
    with pytest.raises(ValueError, match="module_delta_group_duplicate"):
        command_for_char_a(
            module_deltas=(
                CharacterModuleDelta(
                    group_id="character.commitments",
                    definition_version="1.0.0",
                    projection_schema_version=1,
                    source_ref="evt:order:101",
                    payload={"next_due_tick": 120},
                ),
                CharacterModuleDelta(
                    group_id="character.commitments",
                    definition_version="1.0.0",
                    projection_schema_version=1,
                    source_ref="evt:order:102",
                    payload={"next_due_tick": 130},
                ),
            ),
        )


def test_character_core_merges_module_delta_and_rejects_stale_group_revision() -> None:
    runtime = CharacterAgentRuntime()
    initial = CharacterModuleDelta(
        group_id="character.commitments",
        definition_version="1.0.0",
        projection_schema_version=1,
        expected_group_revision=0,
        source_ref="evt:order:101",
        payload={"obligation_ref": "order:bakery:1", "next_due_tick": 120},
    )
    first = runtime.apply_character_continuity_command(
        command_for_char_a(module_deltas=(initial,))
    )
    stale = runtime.apply_character_continuity_command(
        command_for_char_a(
            command_id="continuity:char_a:stale-module",
            idempotency_key="continuity:char_a:stale-module",
            expected_character_revision=1,
            source_revision_vector={"world:bakery": 102},
            module_deltas=(
                initial.model_copy(
                    update={"source_ref": "evt:order:102", "payload": {"next_due_tick": 130}}
                ),
            ),
        )
    )

    assert first.status == "committed"
    assert stale.status == "rejected"
    assert stale.refusal_reason == "module_revision_conflict"
    assert runtime.get_shared_module_state("char_a") == {
        "character.commitments": {
            "definition_version": "1.0.0",
            "projection_schema_version": 1,
            "revision": 1,
            "payload": {"obligation_ref": "order:bakery:1", "next_due_tick": 120},
            "source_ref": "evt:order:101",
        }
    }


def test_character_core_rejects_module_not_declared_by_gameplay_registry() -> None:
    registry = StateGroupRegistry()
    registry.register(
        StateGroupDefinition(
            group_id="character.commitments",
            definition_version="1.0.0",
            projection_schema_version=1,
            shared_fields=("next_due_tick",),
            population_allowed_fields=("next_due_tick",),
        )
    )
    runtime = CharacterAgentRuntime(state_group_registry=registry)

    rejected = runtime.apply_character_continuity_command(
        command_for_char_a(
            module_deltas=(
                CharacterModuleDelta(
                    group_id="character.unknown",
                    definition_version="1.0.0",
                    projection_schema_version=1,
                    source_ref="evt:unknown:101",
                    payload={"next_due_tick": 120},
                ),
            ),
        )
    )

    assert rejected.status == "rejected"
    assert rejected.refusal_reason == "module_definition_unknown"


def test_character_core_rejects_module_fields_outside_declared_schema() -> None:
    registry = StateGroupRegistry()
    registry.register(
        StateGroupDefinition(
            group_id="character.commitments",
            definition_version="1.0.0",
            projection_schema_version=1,
            shared_fields=("next_due_tick",),
            population_allowed_fields=("next_due_tick",),
        )
    )
    runtime = CharacterAgentRuntime(state_group_registry=registry)

    rejected = runtime.apply_character_continuity_command(
        command_for_char_a(
            module_deltas=(
                CharacterModuleDelta(
                    group_id="character.commitments",
                    definition_version="1.0.0",
                    projection_schema_version=1,
                    source_ref="evt:unknown-field:101",
                    payload={"private_note": "forbidden"},
                ),
            ),
        )
    )

    assert rejected.status == "rejected"
    assert rejected.refusal_reason == "module_field_unknown"


def test_character_core_rejects_module_fields_when_group_declares_no_shared_schema() -> None:
    registry = StateGroupRegistry()
    registry.register(
        StateGroupDefinition(
            group_id="character.commitments",
            definition_version="1.0.0",
            projection_schema_version=1,
        )
    )
    runtime = CharacterAgentRuntime(state_group_registry=registry)

    rejected = runtime.apply_character_continuity_command(
        command_for_char_a(
            module_deltas=(
                CharacterModuleDelta(
                    group_id="character.commitments",
                    definition_version="1.0.0",
                    projection_schema_version=1,
                    source_ref="evt:undeclared-field:101",
                    payload={"next_due_tick": 120},
                ),
            ),
        )
    )

    assert rejected.status == "rejected"
    assert rejected.refusal_reason == "module_field_unknown"


def test_seed_projection_is_parsed_into_actor_local_context_not_raw_prompt_text() -> None:
    runtime = CharacterAgentRuntime()
    runtime.apply_character_continuity_command(command_with_presentation_seed())
    projection = runtime.get_seed_projection("char_a")
    assert projection["presentation_seed"]["task"] == "replenish_family_food"
    assert "raw_prompt" not in projection


def test_seed_command_rejects_stale_actor_revision_without_partial_write() -> None:
    runtime = CharacterAgentRuntime()
    runtime.apply_character_continuity_command(command_for_char_a())
    before = runtime.get_dynamic_state_record("char_a").model_dump()
    rejected = runtime.apply_character_continuity_command(
        command_for_char_a(expected_character_revision=0, command_id="continuity:stale", idempotency_key="continuity:stale")
    )
    assert rejected.status == "requeued"
    assert rejected.refusal_reason == "character_revision_conflict"
    assert runtime.get_dynamic_state_record("char_a").model_dump() == before


def test_memory_materialization_requires_exposure_and_is_idempotent() -> None:
    runtime = CharacterAgentRuntime()
    denied = runtime.apply_character_continuity_command(command_with_memory_candidate(exposure_basis="not_observed"))
    assert denied.status == "committed"
    materialized = runtime.materialize_pending_seed_memories("char_a", producer_ts=101)
    assert materialized[0].status == "rejected"
    assert materialized[0].refusal_reason == "memory_materialization_denied"
    replay = runtime.materialize_pending_seed_memories("char_a", producer_ts=101)
    assert replay[0].status == "idempotent_replay"


def test_seed_and_memory_cursor_advance_separately() -> None:
    runtime = CharacterAgentRuntime()
    receipt = runtime.apply_character_continuity_command(command_with_memory_candidate(exposure_basis="affected_directly"))
    assert receipt.cursor_vector["state_cursor"] == 101
    assert receipt.cursor_vector.get("memory_cursor", 0) == 0
    materialized = runtime.materialize_pending_seed_memories("char_a", producer_ts=101)
    assert materialized[0].status == "committed"
    assert materialized[0].memory_cursor == 101


def test_seed_correction_appends_supersession_without_deleting_subjective_memory() -> None:
    runtime = CharacterAgentRuntime()
    runtime.apply_character_continuity_command(command_with_memory_candidate(exposure_basis="affected_directly"))
    runtime.materialize_pending_seed_memories("char_a", producer_ts=101)
    correction = runtime.apply_character_continuity_command(correction_for_char_a())
    assert correction.status == "committed"
    assert runtime.get_memory_bundle("char_a")["event_memories"]
    assert runtime.get_seed_projection("char_a")["supersedes"] == "seed:character:char_a:supply"


def test_checkpoint_failure_keeps_current_state_tail_from_last_confirmed_checkpoint() -> None:
    continuity_store = _CheckpointFailingContinuityStore()
    runtime = CharacterAgentRuntime(continuity_store=continuity_store)

    for index in range(17):
        command = command_for_char_a(
            command_id=f"continuity:char_a:tail:{index}",
            idempotency_key=f"continuity:char_a:tail:{index}",
            expected_character_revision=index,
            source_revision_vector={"world:bakery": 101 + index},
            memory_candidate_refs=(),
            exposure_evidence={},
        )
        if index == 15:
            try:
                runtime.apply_character_continuity_command(command)
            except RuntimeError as exc:
                assert str(exc) == "checkpoint_write_failed"
        else:
            runtime.apply_character_continuity_command(command)

    assert len(continuity_store.current_states[-1]["session_timeline_tail"]) == 16
