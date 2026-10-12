from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.character_agent.models.simulation_seed import CharacterContinuityCommand
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.gameplay.event_store import GameplayEventStore
from app.population_continuity.activation import ProfileActivationAuthority


def runtime_case():
    runtime = CharacterAgentRuntime()
    store = GameplayEventStore()
    authority = ProfileActivationAuthority(registry=runtime._profile_registry, store=store)
    runtime.set_activation_authority(authority)
    return runtime, authority, store


def take_lock(authority, store, actor_ref="character:char_a"):
    receipt = authority.lock(
        world_ref="world:default", profile_ref=actor_ref,
        expected_revision=store.get_stream_head("population:world:default"),
    )
    assert receipt.committed
    return authority.active_lock(world_ref="world:default", profile_ref=actor_ref)


def command(**updates: object) -> CharacterContinuityCommand:
    values = dict(
        command_id="continuity:lock:1", actor_ref="character:char_a", expected_character_revision=0,
        from_tick=0, to_tick=1, simulation_tick_cursor=1,
        source_revision_vector={"world:default": 1}, policy_revision="policy:character-continuity:v1",
        idempotency_key="continuity:lock:1", state_delta={"presentation_seed": {"task": "care"}},
    )
    values.update(updates)
    return CharacterContinuityCommand(**values)


def test_legacy_command_wire_shape_is_unchanged() -> None:
    value = command().model_dump(mode="json")
    assert set(value) == {
        "command_id", "actor_ref", "source_owner_receipt_refs", "expected_character_revision", "from_tick",
        "to_tick", "simulation_tick_cursor", "source_revision_vector", "state_delta", "module_deltas",
        "memory_candidate_refs", "exposure_evidence", "policy_revision", "idempotency_key", "world_effect_required",
    }


def test_active_lock_read_returns_an_isolated_credential() -> None:
    runtime, authority, store = runtime_case()
    lock = take_lock(authority, store)
    changed = lock.model_copy(update={"status": "released"})
    assert changed.status == "released"
    assert authority.active_lock(world_ref="world:default", profile_ref="character:char_a").status == "active"


def test_current_lock_credential_allows_core_continuity() -> None:
    runtime, authority, store = runtime_case()
    lock = take_lock(authority, store)
    pinned = command(activation_lock_ref=lock.lock_ref, activation_lock_revision=lock.held_revision)
    receipt = runtime.apply_character_continuity_command(pinned)
    assert receipt.status == "committed"
    assert runtime.get_continuity_revision("char_a") == 1
    assert pinned.model_dump(mode="json")["activation_lock_revision"] == lock.held_revision


def test_released_lock_rejects_old_command_without_core_write() -> None:
    runtime, authority, store = runtime_case()
    lock = take_lock(authority, store)
    old = command(activation_lock_ref=lock.lock_ref, activation_lock_revision=lock.held_revision)
    assert authority.release_lock(lock_ref=lock.lock_ref, expected_revision=store.get_stream_head("population:world:default")).committed
    before = runtime._session_store.event_count("char_a")
    receipt = runtime.apply_character_continuity_command(old)
    assert receipt.status == "rejected"
    assert receipt.refusal_reason == "handoff_lock_stale"
    assert runtime._session_store.event_count("char_a") == before
    assert runtime.get_continuity_revision("char_a") == 0


def test_new_lock_generation_rejects_old_command_with_same_lock_ref() -> None:
    runtime, authority, store = runtime_case()
    first = take_lock(authority, store)
    old = command(activation_lock_ref=first.lock_ref, activation_lock_revision=first.held_revision)
    assert authority.release_lock(lock_ref=first.lock_ref, expected_revision=store.get_stream_head("population:world:default")).committed
    current = take_lock(authority, store)
    assert current.lock_ref == first.lock_ref
    assert current.held_revision != first.held_revision
    receipt = runtime.apply_character_continuity_command(old)
    assert receipt.status == "rejected"
    assert runtime.get_continuity_revision("char_a") == 0


def test_other_actors_lock_is_not_a_continuity_credential() -> None:
    runtime, authority, store = runtime_case()
    lock = take_lock(authority, store, "character:char_b")
    receipt = runtime.apply_character_continuity_command(
        command(activation_lock_ref=lock.lock_ref, activation_lock_revision=lock.held_revision),
    )
    assert receipt.status == "rejected"
    assert runtime.get_continuity_revision("char_a") == 0


def test_committed_command_replays_after_lock_release() -> None:
    runtime, authority, store = runtime_case()
    lock = take_lock(authority, store)
    pinned = command(activation_lock_ref=lock.lock_ref, activation_lock_revision=lock.held_revision)
    first = runtime.apply_character_continuity_command(pinned)
    assert first.status == "committed"
    assert authority.release_lock(lock_ref=lock.lock_ref, expected_revision=store.get_stream_head("population:world:default")).committed
    before = runtime._session_store.event_count("char_a")
    duplicate = runtime.apply_character_continuity_command(pinned)
    assert duplicate.status == "idempotent_replay"
    assert duplicate.receipt_ref == first.receipt_ref
    assert runtime._session_store.event_count("char_a") == before


@pytest.mark.parametrize("value", [True, None])
def test_core_checks_credentials_after_model_copy(value: object) -> None:
    runtime, authority, store = runtime_case()
    take_lock(authority, store, "character:char_b")
    lock = take_lock(authority, store)
    assert lock.held_revision == 1
    pinned = command(activation_lock_ref=lock.lock_ref, activation_lock_revision=lock.held_revision)
    forged = pinned.model_copy(update={"activation_lock_revision": value})
    before = runtime._session_store.event_count("char_a")
    receipt = runtime.apply_character_continuity_command(forged)
    assert receipt.status == "rejected"
    assert runtime._session_store.event_count("char_a") == before


@pytest.mark.parametrize("updates", [
    {"activation_lock_ref": "lock:missing"},
    {"activation_lock_revision": 0},
    {"activation_lock_ref": "lock:missing", "activation_lock_revision": True},
])
def test_lock_credentials_must_be_complete_and_strict(updates: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        command(**updates)
