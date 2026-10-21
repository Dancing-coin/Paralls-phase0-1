from __future__ import annotations

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.world_runtime.replay_participants import (
    _life_state_participant, validate_life_state_checkpoint_tail,
)
from test_life_state_case_death_caller import _seed
from test_population_activation_presence_service import _proposal, _service_with_store


def test_empty_life_state_checkpoint_accepts_first_owner_alive_tail():
    store = GameplayEventStore()
    saved = _life_state_participant(store)
    assert saved is not None
    assert saved["actors"] == {}
    start = store.get_last_global_sequence()

    _, service = _service_with_store(store)
    result = service.commit_and_spawn(_proposal(), presence_idempotency_key="presence:first-tail",
                                      presence_expected_revision=0)
    assert result.activation.committed and result.presence.committed
    assert result.life_state is not None and result.life_state.committed

    current = _life_state_participant(store)
    assert current["actors"]["character:char_a"]["state"] == "alive"
    before = store.export_snapshot()
    validate_life_state_checkpoint_tail(store, saved, current, start,
                                        store.get_last_global_sequence())
    assert store.export_snapshot() == before


def test_historical_schema1_case_death_rebuilds_as_dead():
    store, confirmation_id = _seed()
    result = store.append_batch(build_atomic_event_batch(
        command_id="life:historical", principal_ref="authority:character:life-state",
        stream_id="gameplay:character:life:character:death:1", expected_revision=0,
        schema_version=1,
        event_specs=(("gameplay.character.life_state_changed", {
            "actor_ref": "character:death:1", "from_state": "unknown", "to_state": "dead",
            "source_confirmation_event_id": confirmation_id,
            "source_confirmation_revision": 2,
            "policy_revision": "policy:character-life-state-case-death@1",
            "visibility_policy": "project",
        }),), idempotency_key="life:historical", causation_id=confirmation_id,
        correlation_id="life:historical",
    ))
    assert result.committed

    participant = _life_state_participant(store)
    assert participant["actors"]["character:death:1"]["state"] == "dead"


def test_case_death_replay_rejects_forged_confirmation_owner():
    store, confirmation_id = _seed()
    source = store.get_event(confirmation_id)
    forged = store.append_batch(build_atomic_event_batch(
        command_id="life:forged-source", principal_ref="untrusted:case-death",
        stream_id="gameplay:conflict:forged", expected_revision=0,
        event_specs=(("gameplay.conflict.world_death_commit_confirmed", source.payload),),
        idempotency_key="life:forged-source", causation_id=confirmation_id,
        correlation_id="life:forged-source",
    ))
    assert forged.committed
    result = store.append_batch(build_atomic_event_batch(
        command_id="life:forged", principal_ref="authority:character:life-state",
        stream_id="gameplay:character:life:character:death:1", expected_revision=0,
        schema_version=2,
        event_specs=(("gameplay.character.life_state_changed", {
            "actor_ref": "character:death:1", "from_state": "unknown", "to_state": "dead",
            "source_confirmation_event_id": forged.committed_event_ids[0],
            "source_confirmation_revision": 1,
            "policy_revision": "policy:character-life-state-case-death@2",
            "visibility_policy": "project",
        }),), idempotency_key="life:forged", causation_id=forged.committed_event_ids[0],
        correlation_id="life:forged",
    ))
    assert result.committed
    before = store.export_snapshot()
    with pytest.raises(ValueError, match="replay_life_state_source_mismatch"):
        _life_state_participant(store)
    assert store.export_snapshot() == before


def test_case_death_replay_rejects_confirmation_without_terminal_fact():
    store, confirmation_id = _seed()
    payload = dict(store.get_event(confirmation_id).payload)
    payload["source_event_id"] = "event:missing-terminal"
    confirmation = store.append_batch(build_atomic_event_batch(
        command_id="life:missing-terminal", principal_ref="authority:p5:investigation-conflict",
        stream_id="gameplay:conflict:missing-terminal", expected_revision=0,
        event_specs=(("gameplay.conflict.world_death_commit_confirmed", payload),),
        idempotency_key="life:missing-terminal", causation_id="life:missing-terminal",
        correlation_id="life:missing-terminal",
    ))
    assert confirmation.committed
    life = store.append_batch(build_atomic_event_batch(
        command_id="life:missing-terminal-death",
        principal_ref="authority:character:life-state",
        stream_id="gameplay:character:life:character:death:1", expected_revision=0,
        schema_version=2,
        event_specs=(("gameplay.character.life_state_changed", {
            "actor_ref": "character:death:1", "from_state": "unknown", "to_state": "dead",
            "source_confirmation_event_id": confirmation.committed_event_ids[0],
            "source_confirmation_revision": 1,
            "policy_revision": "policy:character-life-state-case-death@2",
            "visibility_policy": "project",
        }),), idempotency_key="life:missing-terminal-death",
        causation_id=confirmation.committed_event_ids[0],
        correlation_id="life:missing-terminal-death",
    ))
    assert life.committed
    before = store.export_snapshot()
    with pytest.raises(ValueError, match="replay_life_state_source_missing"):
        _life_state_participant(store)
    assert store.export_snapshot() == before


def test_alive_replay_rejects_forged_activation_and_presence_owners():
    store = GameplayEventStore()
    _, service = _service_with_store(store)
    real = service.commit_and_spawn(_proposal(), presence_idempotency_key="presence:real",
                                    presence_expected_revision=0)
    assert real.activation.committed and real.presence.committed
    activation_payload = dict(store.get_event(real.activation.committed_event_ids[0]).payload)
    activation_payload["profile_ref"] = "character:char_b"
    activation = store.append_batch(build_atomic_event_batch(
        command_id="life:fake-activation", principal_ref="untrusted:activation",
        stream_id="population:world:bakery", expected_revision=1,
        event_specs=(("population.activation.committed", activation_payload),),
        idempotency_key="life:fake-activation", causation_id="life:fake-activation",
        correlation_id="life:fake-activation",
    ))
    assert activation.committed
    presence_payload = dict(store.get_event(real.presence.committed_event_ids[0]).payload)
    presence_payload.update(character_ref="character:char_b",
                            source_activation_event_id=activation.committed_event_ids[0])
    presence = store.append_batch(build_atomic_event_batch(
        command_id="life:fake-presence", principal_ref="untrusted:presence",
        stream_id="presence:world:bakery", expected_revision=1,
        event_specs=(("population.presence.spawned", presence_payload),),
        idempotency_key="life:fake-presence", causation_id="life:fake-presence",
        correlation_id="life:fake-presence",
    ))
    assert presence.committed
    life = store.append_batch(build_atomic_event_batch(
        command_id="life:fake-alive",
        principal_ref="authority:character:life-state:presence-admission",
        stream_id="gameplay:character:life:character:char_b", expected_revision=0,
        schema_version=2,
        event_specs=(("gameplay.character.life_state_changed", {
            "actor_ref": "character:char_b", "world_ref": "world:bakery",
            "incarnation": presence_payload["incarnation"],
            "from_state": "unknown", "to_state": "alive",
            "source_activation_event_id": activation.committed_event_ids[0],
            "source_presence_event_id": presence.committed_event_ids[0],
            "source_activation_revision": 2, "source_presence_revision": 2,
            "policy_revision": "policy:character-life-state-presence-admission@1",
            "visibility_policy": "project",
        }),), idempotency_key="life:fake-alive", causation_id="life:fake-alive",
        correlation_id="life:fake-alive",
    ))
    assert life.committed
    before = store.export_snapshot()
    with pytest.raises(ValueError, match="replay_life_state_source_mismatch"):
        _life_state_participant(store)
    assert store.export_snapshot() == before
