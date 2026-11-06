from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.activation_sources import ActivationSourceReader
from app.population_continuity.models import ActivationGrant, ActivationProposal
from app.population_continuity.presence_runtime import (
    CharacterDespawnRequest,
    CharacterSpawnRequest,
    PopulationPresenceAuthority,
)
from app.world_runtime.replay_participants import _presence_participant


PROFILES = Path(__file__).resolve().parents[2] / "assets/characters/profiles"
PRODUCER = "population:siming"
# Presence admits only sources committed by the activation owner under a
# configured grant, so the fixture uses real authored profiles.
ALICE, BOB = "character:char_a", "character:char_b"


def _composition(store):
    grants = tuple(ActivationGrant(profile_ref=profile, world_ref=world, package_revision="package:1",
        policy_revision="policy:1", scope_grant=("actor:self",))
        for profile, world in ((ALICE, "world:a"), (BOB, "world:b")))
    activation = ProfileActivationAuthority(store=store,
        registry=CharacterProfileRegistry.from_directory(PROFILES), grants=grants)
    presence = PopulationPresenceAuthority(store=store,
        activation_sources=ActivationSourceReader(authority=activation, producer_ref=PRODUCER))
    return activation, presence


def _activate(activation, world, character, key):
    receipt = activation.commit(ActivationProposal(
        proposal_id=key, profile_ref=character, world_ref=world, package_revision="package:1",
        policy_revision="policy:1", scope_grant=("actor:self",), cadence_class="active",
        activation_reason="population-cadence", source_ref=PRODUCER,
        expected_revisions={f"population:{world}": 0}, idempotency_key=key, correlation_id=world,
    ))
    assert receipt.committed
    return receipt.committed_event_ids[0]


def _spawn(authority, world, character, activation, key, revision=0):
    result = authority.spawn(CharacterSpawnRequest(
        world_ref=world, character_ref=character, activation_event_id=activation,
        idempotency_key=key, expected_revision=revision,
    ))
    assert result.committed
    return result


def test_presence_participant_uses_owner_projection_at_bounded_cut_and_isolates_worlds():
    store = GameplayEventStore()
    activation, authority = _composition(store)
    a = _activate(activation, "world:a", ALICE, "activation:a")
    b = _activate(activation, "world:b", BOB, "activation:b")
    _spawn(authority, "world:a", ALICE, a, "spawn:a")
    second = _spawn(authority, "world:b", BOB, b, "spawn:b", revision=0)
    cut = store.get_event(second.committed_event_ids[0]).global_sequence
    later = authority.despawn(CharacterDespawnRequest(
        world_ref="world:a", character_ref=ALICE, incarnation=1,
        idempotency_key="despawn:a", expected_revision=1, reason="window_closed",
    ))
    assert later.committed

    participant = _presence_participant(store, authority, boundary_sequence=cut)
    assert participant["rows"] == [{
        "world_ref": "world:a", "character_ref": ALICE,
        "incarnation": 1, "status": "present",
    }, {
        "world_ref": "world:b", "character_ref": BOB,
        "incarnation": 1, "status": "present",
    }]
    assert participant["reconstruction_api"] == "PopulationPresenceAuthority.projection"
    assert all(ref["global_sequence"] <= cut for ref in participant["event_refs"])


def test_presence_participant_rejects_store_mismatch():
    store = GameplayEventStore()
    activation, authority = _composition(store)
    source = _activate(activation, "world:a", ALICE, "activation:a")
    _spawn(authority, "world:a", ALICE, source, "spawn:a")
    participant = _presence_participant(store, authority)
    assert participant["view_digest"]
    try:
        _presence_participant(store, PopulationPresenceAuthority(store=GameplayEventStore()))
    except ValueError as exc:
        assert str(exc) == "replay_presence_store_mismatch"
    else:
        raise AssertionError("store mismatch must be rejected")


def test_presence_owner_projection_survives_durable_close_reopen(tmp_path):
    path = tmp_path / "presence-replay.sqlite3"
    store = DurableGameplayEventStore(path)
    activation, authority = _composition(store)
    source = _activate(activation, "world:a", ALICE, "activation:a")
    _spawn(authority, "world:a", ALICE, source, "spawn:a")
    store.close()
    reopened = DurableGameplayEventStore(path)
    _, reopened_authority = _composition(reopened)
    participant = _presence_participant(reopened, reopened_authority)
    assert participant["rows"][0]["character_ref"] == ALICE
    assert reopened_authority.projection("world:a") == {
        ALICE: {"incarnation": 1, "status": "present"}
    }
    reopened.close()


def test_respawn_after_durable_reopen_allocates_new_incarnation_and_invalidates_old_target(tmp_path):
    path = tmp_path / "presence-incarnation.sqlite3"
    store = DurableGameplayEventStore(path)
    activation, authority = _composition(store)
    source = _activate(activation, "world:a", ALICE, "activation:a")
    first = _spawn(authority, "world:a", ALICE, source, "spawn:one")
    departed = authority.despawn(CharacterDespawnRequest(
        world_ref="world:a", character_ref=ALICE, incarnation=first.incarnation,
        idempotency_key="despawn:one", expected_revision=1, reason="explicit_departure",
    ))
    assert departed.committed and departed.incarnation == 1
    departed_cut = store.get_event(departed.committed_event_ids[0]).global_sequence
    store.close()

    reopened = DurableGameplayEventStore(path)
    _, restored = _composition(reopened)
    second = _spawn(restored, "world:a", ALICE, source, "spawn:two", revision=2)
    assert second.incarnation == 2
    replay = restored.spawn(CharacterSpawnRequest(
        world_ref="world:a", character_ref=ALICE, activation_event_id=source,
        idempotency_key="spawn:two", expected_revision=2,
    ))
    assert replay.idempotency_status == "duplicate_replayed" and replay.incarnation == 2
    before = reopened.read_events()
    # expected_revision is only the caller's CAS hint, not request identity, so a
    # retry with a newer hint replays the original receipt.
    newer_hint = restored.spawn(CharacterSpawnRequest(
        world_ref="world:a", character_ref=ALICE, activation_event_id=source,
        idempotency_key="spawn:two", expected_revision=3,
    ))
    assert newer_hint.idempotency_status == "duplicate_replayed" and newer_hint.incarnation == 2
    # Reusing the key for a different source is a different request: rejected,
    # reported as a mismatch against the original receipt, and nothing is written.
    changed = restored.spawn(CharacterSpawnRequest(
        world_ref="world:a", character_ref=ALICE, activation_event_id="event:other",
        idempotency_key="spawn:two", expected_revision=3,
    ))
    assert not changed.committed and changed.zero_write
    assert changed.stop_reason == "presence_original_receipt_invalid"
    assert reopened.read_events() == before
    stale = restored.despawn(CharacterDespawnRequest(
        world_ref="world:a", character_ref=ALICE, incarnation=1,
        idempotency_key="despawn:stale-old-target", expected_revision=3, reason="stale_target",
    ))
    assert not stale.committed and stale.stop_reason == "presence_incarnation_not_active"
    current = _presence_participant(reopened, restored)
    at_departure = _presence_participant(reopened, restored, boundary_sequence=departed_cut)
    assert current["rows"] == [{
        "world_ref": "world:a", "character_ref": ALICE,
        "incarnation": 2, "status": "present",
    }]
    assert at_departure["rows"] == []
    assert all(ref["global_sequence"] <= departed_cut for ref in at_departure["event_refs"])
    reopened.close()
