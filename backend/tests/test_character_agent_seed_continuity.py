from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import pytest

from app.character_agent.models.simulation_seed import (
    CharacterModuleDelta,
    CharacterContinuityCommand,
    CharacterMemoryCandidate,
    CharacterSimulationSeedCandidate,
)
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.storage.graph_continuity_store import CharacterGraphContinuityStore
from app.character_agent.storage.memory_store import CharacterAgentMemoryStore
from app.models.siming_heavenly_graph import HeavenlyGraphScope
from app.models.character_agent_runtime import CharacterIntentDecision
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
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
        "from_tick": 100,
        "to_tick": 101,
        "simulation_tick_cursor": 101,
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
        self.snapshots: list[dict[str, object]] = []
        self.fail_checkpoint_at = 16

    def write_current_state(self, *, snapshot: dict[str, object], **_: object) -> None:
        if snapshot.get('event_index') == self.fail_checkpoint_at:
            self.fail_checkpoint_at = -1
            raise RuntimeError('current_state_write_failed')
        self.current_states.append(snapshot)

    def write_snapshot(self, *, snapshot: dict[str, object], **_: object) -> None:
        timeline = snapshot.get("session_timeline")
        if isinstance(timeline, list) and len(timeline) == self.fail_checkpoint_at:
            self.fail_checkpoint_at = -1
            raise RuntimeError("checkpoint_write_failed")
        self.snapshots.append(snapshot)

    def read_current_state(self, _: str) -> None:
        return None

    def read_snapshot(self, _: str) -> None:
        return None


class _CurrentStateFailingContinuityStore(_CheckpointFailingContinuityStore):
    def write_current_state(self, *, snapshot: dict[str, object], **_: object) -> None:
        raise RuntimeError("current_state_write_failed")


class _CurrentAfterCheckpointFailingContinuityStore:
    def __init__(self) -> None:
        self.snapshot: dict[str, object] | None = None
        self.current_state: dict[str, object] | None = None
        self._fail_current = False

    @staticmethod
    def _anchored(
        snapshot: dict[str, object], source_event_ref: str
    ) -> dict[str, object]:
        return {
            **deepcopy(snapshot),
            CharacterGraphContinuityStore.SOURCE_EVENT_REF_FIELD: source_event_ref,
        }

    def write_snapshot(
        self,
        *,
        actor_id: str,
        snapshot: dict[str, object],
        source_event_ref: str,
        **_: object,
    ) -> None:
        if actor_id != "char_a":
            return
        self.snapshot = self._anchored(snapshot, source_event_ref)
        self._fail_current = snapshot.get("checkpoint_event_index") == 16

    def write_current_state(
        self,
        *,
        actor_id: str,
        snapshot: dict[str, object],
        source_event_ref: str,
        **_: object,
    ) -> None:
        if actor_id != "char_a":
            return
        if snapshot.get('event_index') == 16 and not self._fail_current:
            self._fail_current = True
            raise RuntimeError("current_after_checkpoint_write_failed")
        self.current_state = self._anchored(snapshot, source_event_ref)

    def read_snapshot(self, actor_id: str) -> dict[str, object] | None:
        return deepcopy(self.snapshot) if actor_id == "char_a" else None

    def read_current_state(self, actor_id: str) -> dict[str, object] | None:
        return deepcopy(self.current_state) if actor_id == "char_a" else None


class _NoGlobalReceiptScan(dict[str, object]):
    def items(self):
        raise AssertionError("continuity persistence scanned every actor receipt")


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


def test_materialization_memory_failure_retries_committed_fact_without_duplicate(
    tmp_path: Path, monkeypatch
) -> None:
    memory_store = CharacterAgentMemoryStore(storage_root=tmp_path)
    runtime = CharacterAgentRuntime(storage_root=tmp_path, memory_store=memory_store)
    runtime.apply_character_continuity_command(
        command_with_memory_candidate(exposure_basis="affected_directly")
    )
    original_write = memory_store.write_event
    failed = False

    def fail_once(event) -> None:
        nonlocal failed
        if not failed:
            failed = True
            raise RuntimeError("materialization_memory_projection_failed")
        original_write(event)

    monkeypatch.setattr(memory_store, "write_event", fail_once)

    with pytest.raises(RuntimeError, match="materialization_memory_projection_failed"):
        runtime.materialize_pending_seed_memories("char_a", producer_ts=101)

    replay = runtime.materialize_pending_seed_memories("char_a", producer_ts=101)
    materialization_events = [
        event
        for event in runtime.get_session_timeline("char_a")
        if event.get("payload", {}).get("materialization_receipt")
    ]
    assert replay[0].status == "idempotent_replay"
    assert len(materialization_events) == 1
    assert len(runtime.get_memory_bundle("char_a")["event_memories"]) == 1

    restarted = CharacterAgentRuntime(
        storage_root=tmp_path,
        memory_store=CharacterAgentMemoryStore(storage_root=tmp_path),
    )
    restarted_replay = restarted.materialize_pending_seed_memories(
        "char_a", producer_ts=101
    )
    restarted_materialization_events = [
        event
        for event in restarted.get_session_timeline("char_a")
        if event.get("payload", {}).get("materialization_receipt")
    ]
    assert restarted_replay[0].status == "idempotent_replay"
    assert len(restarted_materialization_events) == 1
    assert len(restarted.get_memory_bundle("char_a")["event_memories"]) == 1


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


def test_compact_current_failure_keeps_committed_session_and_next_publish() -> None:
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
                assert str(exc) == "current_state_write_failed"
        else:
            runtime.apply_character_continuity_command(command)

    assert continuity_store.current_states[-1]['event_index'] == 17
    assert runtime.get_memory_revision('char_a') == 17
    assert continuity_store.snapshots == []


def test_compact_current_persists_exact_committed_event_cursor() -> None:
    continuity_store = _CheckpointFailingContinuityStore()
    continuity_store.fail_checkpoint_at = -1
    runtime = CharacterAgentRuntime(continuity_store=continuity_store)

    for index in range(16):
        runtime.apply_character_continuity_command(
            command_for_char_a(
                command_id=f"continuity:char_a:checkpoint:{index}",
                idempotency_key=f"continuity:char_a:checkpoint:{index}",
                expected_character_revision=index,
                source_revision_vector={"world:bakery": 201 + index},
                memory_candidate_refs=(),
                exposure_evidence={},
            )
        )

    assert continuity_store.snapshots == []
    assert continuity_store.current_states[-1]['event_index'] == 16
    assert continuity_store.current_states[-1]['event_id'] == runtime.get_session_timeline('char_a')[-1]['event_id']


def test_committed_session_event_restores_after_current_state_write_failure(
    tmp_path: Path,
) -> None:
    command = command_for_char_a()
    first = CharacterAgentRuntime(
        storage_root=tmp_path,
        continuity_store=_CurrentStateFailingContinuityStore(),
    )

    try:
        first.apply_character_continuity_command(command)
    except RuntimeError as exc:
        assert str(exc) == "current_state_write_failed"
    else:  # pragma: no cover
        raise AssertionError("injected graph projection failure did not propagate")

    second = CharacterAgentRuntime(storage_root=tmp_path)
    assert second.get_continuity_revision("char_a") == 1
    assert second.get_need_tension_state_record("char_a").physiological_pressure == 0.12
    assert second.get_pending_seed_candidates("char_a")

    replay = second.apply_character_continuity_command(command)
    assert replay.status == "idempotent_replay"


def test_continuity_persistence_does_not_copy_full_timeline_or_scan_other_receipts() -> None:
    continuity_store = _CheckpointFailingContinuityStore()
    continuity_store.fail_checkpoint_at = -1
    runtime = CharacterAgentRuntime(continuity_store=continuity_store)
    runtime._continuity_receipts = _NoGlobalReceiptScan()

    def fail_full_timeline_copy(_: str) -> list[dict[str, object]]:
        raise AssertionError("continuity persistence copied the full timeline")

    runtime.get_session_timeline = fail_full_timeline_copy
    receipt = runtime.apply_character_continuity_command(command_for_char_a())

    assert receipt.status == "committed"


def test_current_state_payload_stays_bounded_as_committed_history_grows() -> None:
    continuity_store = _CheckpointFailingContinuityStore()
    continuity_store.fail_checkpoint_at = -1
    runtime = CharacterAgentRuntime(continuity_store=continuity_store)

    payload_sizes: list[int] = []
    for index in range(33):
        runtime.apply_character_continuity_command(
            command_for_char_a(
                command_id=f"continuity:char_a:bounded:{index}",
                idempotency_key=f"continuity:char_a:bounded:{index}",
                expected_character_revision=index,
                source_revision_vector={"world:bakery": 1000 + index},
                memory_candidate_refs=(),
                exposure_evidence={},
            )
        )
        if index in {16, 32}:
            payload_sizes.append(
                len(
                    json.dumps(
                        continuity_store.current_states[-1],
                        separators=(",", ":"),
                    ).encode("utf-8")
                )
            )

    latest = continuity_store.current_states[-1]
    assert 'session_timeline_tail' not in latest
    assert 'working_memory' not in latest
    assert len(latest.get('goal_history', [])) <= 8
    assert "continuity_receipts" not in latest
    assert "materialization_receipts" not in latest
    assert payload_sizes[1] - payload_sizes[0] < 128


def test_restored_legacy_session_publishes_compact_current_without_history_copy(
    tmp_path: Path,
) -> None:
    actor_id = "char_a"
    history = [
        {
            "event_id": f"legacy:{index}",
            "event_index": index + 1,
            "actor_id": actor_id,
            "event_type": "legacy_probe_event",
            "producer_ts": index,
            "payload": {"probe": "fixed"},
        }
        for index in range(100)
    ]
    (tmp_path / "character_agent_session_store.json").write_text(
        json.dumps({actor_id: history}, separators=(",", ":")),
        encoding="utf-8",
    )
    continuity_store = _CheckpointFailingContinuityStore()
    continuity_store.fail_checkpoint_at = -1
    runtime = CharacterAgentRuntime(
        storage_root=tmp_path, continuity_store=continuity_store
    )

    receipt = runtime.apply_character_continuity_command(
        command_for_char_a(
            memory_candidate_refs=(),
            exposure_evidence={},
        )
    )

    assert receipt.status == "committed"
    assert continuity_store.snapshots == []
    assert continuity_store.current_states[-1]['event_index'] == 101
    assert 'session_timeline_tail' not in continuity_store.current_states[-1]
    assert len(runtime.get_session_timeline(actor_id)) == 101


def test_stale_graph_current_cannot_override_newer_committed_session(
    tmp_path: Path,
) -> None:
    continuity_store = _CurrentAfterCheckpointFailingContinuityStore()
    runtime = CharacterAgentRuntime(
        storage_root=tmp_path, continuity_store=continuity_store
    )
    for index in range(15):
        command = command_for_char_a(
            command_id=f"continuity:checkpoint-current:{index}",
            idempotency_key=f"continuity:checkpoint-current:{index}",
            expected_character_revision=index,
            state_delta={
                "presentation_seed": {"step": index},
                "need_tension": {"physiological_pressure": index / 100},
            },
            memory_candidate_refs=(),
            exposure_evidence={},
        )
        if index == 14:
            with pytest.raises(
                RuntimeError, match="current_after_checkpoint_write_failed"
            ):
                runtime.apply_character_continuity_command(command)
        else:
            assert runtime.apply_character_continuity_command(command).status == (
                "committed"
            )
        if index == 0:
            runtime._record_goal_state_event(
                "char_a",
                101,
                CharacterIntentDecision(
                    actor_id="char_a",
                    selected_intent="hold_position",
                    persona_passed=True,
                    logic_passed=True,
                    gain_loss_passed=True,
                    rationale="checkpoint replay probe",
                    primary_goal="preserve_checkpoint_truth",
                    immediate_goal="hold_position",
                ),
            )

    assert continuity_store.snapshot is None
    assert continuity_store.current_state is not None
    assert continuity_store.current_state['event_index'] == 15
    assert runtime._session_store.read_runtime_state('char_a')['event_index'] == 16

    full_replay = CharacterAgentRuntime(storage_root=tmp_path)
    restored = CharacterAgentRuntime(
        storage_root=tmp_path, continuity_store=continuity_store
    )

    assert restored.get_continuity_revision("char_a") == 15
    assert restored.get_continuity_revision("char_a") == (
        full_replay.get_continuity_revision("char_a")
    )
    assert restored.get_dynamic_state("char_a") == full_replay.get_dynamic_state(
        "char_a"
    )
    assert restored.get_need_tension_state(
        "char_a"
    ) == full_replay.get_need_tension_state("char_a")
    assert restored.get_seed_projection("char_a") == full_replay.get_seed_projection(
        "char_a"
    )
    assert restored.get_goal_state_history(
        "char_a"
    ) == full_replay.get_goal_state_history("char_a")
    assert restored.get_session_timeline("char_a") == full_replay.get_session_timeline(
        "char_a"
    )


def test_compact_current_does_not_duplicate_committed_goal_on_restore(
    tmp_path: Path,
) -> None:
    continuity_store = _CurrentAfterCheckpointFailingContinuityStore()
    runtime = CharacterAgentRuntime(
        storage_root=tmp_path, continuity_store=continuity_store
    )
    runtime.apply_character_continuity_command(
        command_for_char_a(memory_candidate_refs=(), exposure_evidence={})
    )
    runtime._record_goal_state_event(
        "char_a",
        102,
        CharacterIntentDecision(
            actor_id="char_a",
            selected_intent="observe",
            persona_passed=True,
            logic_passed=True,
            gain_loss_passed=True,
            rationale="current tail replay probe",
            primary_goal="observe_without_duplication",
            immediate_goal="observe",
        ),
    )
    runtime.apply_character_continuity_command(
        command_for_char_a(
            command_id="continuity:newer-current",
            idempotency_key="continuity:newer-current",
            expected_character_revision=1,
            memory_candidate_refs=(),
            exposure_evidence={},
        )
    )

    full_replay = CharacterAgentRuntime(storage_root=tmp_path)
    restored = CharacterAgentRuntime(
        storage_root=tmp_path, continuity_store=continuity_store
    )

    assert continuity_store.snapshot is None
    assert continuity_store.current_state is not None
    assert continuity_store.current_state['event_index'] == 3
    assert restored.get_goal_state_history(
        "char_a"
    ) == full_replay.get_goal_state_history("char_a")


def test_memory_projection_failure_cannot_duplicate_committed_continuity_event(
    tmp_path: Path, monkeypatch
) -> None:
    command = command_for_char_a()
    first = CharacterAgentRuntime(storage_root=tmp_path)
    original_write = first._memory_store.write_event
    failed = False

    def fail_once(event: dict[str, object]) -> None:
        nonlocal failed
        if event.get("event_type") == "character_simulation_seed_event" and not failed:
            failed = True
            raise RuntimeError("memory_projection_failed")
        original_write(event)

    monkeypatch.setattr(first._memory_store, "write_event", fail_once)

    with pytest.raises(RuntimeError, match="memory_projection_failed"):
        first.apply_character_continuity_command(command)

    same_process_replay = first.apply_character_continuity_command(command)
    assert same_process_replay.status == "idempotent_replay"
    assert first.get_continuity_revision("char_a") == 1
    assert len(first.get_session_timeline("char_a")) == 1

    second = CharacterAgentRuntime(storage_root=tmp_path)
    restarted_replay = second.apply_character_continuity_command(command)
    assert restarted_replay.status == "idempotent_replay"
    assert second.get_continuity_revision("char_a") == 1
    assert len(second.get_session_timeline("char_a")) == 1


def test_newer_committed_session_tail_wins_over_stale_graph_current(
    tmp_path: Path,
) -> None:
    graph = InMemoryHeavenlyGraphAdapter()
    continuity_store = CharacterGraphContinuityStore(
        graph,
        scope_resolver=lambda actor_id: HeavenlyGraphScope(
            world_id="world:continuity",
            session_id="session:continuity",
            story_branch_id="branch:main",
            graph_namespace="actor_private",
            owner_actor_id=actor_id,
        ),
    )
    first_command = command_for_char_a(
        memory_candidate_refs=(), exposure_evidence={}
    )
    first = CharacterAgentRuntime(
        storage_root=tmp_path, continuity_store=continuity_store
    )
    first.apply_character_continuity_command(first_command)

    second_command = command_for_char_a(
        command_id="continuity:char_a:newer",
        idempotency_key="continuity:char_a:newer",
        expected_character_revision=1,
        source_revision_vector={"world:bakery": 102},
        memory_candidate_refs=(),
        exposure_evidence={},
    )
    without_graph = CharacterAgentRuntime(storage_root=tmp_path)
    without_graph.apply_character_continuity_command(second_command)

    restored = CharacterAgentRuntime(
        storage_root=tmp_path, continuity_store=continuity_store
    )

    assert restored.get_continuity_revision("char_a") == 2
    assert restored.apply_character_continuity_command(second_command).status == (
        "idempotent_replay"
    )
    assert len(restored.get_session_timeline("char_a")) == 2
