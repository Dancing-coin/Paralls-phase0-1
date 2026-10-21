from dataclasses import replace

import pytest

from app.gameplay.canonical_combat_authority import CanonicalCombatThreatAuthority
from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.settlement_plan import build_atomic_event_batch
from test_combat_settlement_threat_consumer import _sources, _owner, _attempt


def _begin(owner, source, attempt, receipt, **changes):
    values = dict(attempt=attempt, authority_result=receipt,
                  presence_event_ids=source.presence_source_event_ids,
                  life_event_ids=source.life_state_source_event_ids,
                  faction_event_id=source.faction_source_event_id,
                  world_ref=source.world_ref, timeline_ref=source.timeline_ref,
                  encounter_ref=source.encounter_ref,
                  actor_incarnation_ref=source.actor_incarnation_ref,
                  target_incarnation_ref=source.target_incarnation_ref,
                  command_id="begin:1", idempotency_key="begin:1", authorized_caller="backend:combat")
    values.update(changes)
    return owner.begin_encounter(**values)


def _hit(owner, source, attempt, receipt):
    return owner.record_confirmed_hit(
        attempt=attempt, authority_result=receipt,
        presence_event_ids=source.presence_source_event_ids, life_event_ids=source.life_state_source_event_ids,
        faction_event_id=source.faction_source_event_id, world_ref=source.world_ref,
        timeline_ref=source.timeline_ref, encounter_ref=source.encounter_ref,
        actor_incarnation_ref=source.actor_incarnation_ref, target_incarnation_ref=source.target_incarnation_ref,
        command_id="hit", idempotency_key="hit")


def test_encounter_end_clears_projection_and_rejects_new_hit_after_durable_restart(tmp_path):
    path = tmp_path / "lifecycle.db"
    store = DurableGameplayEventStore(path)
    source, attempt = _sources(store), _attempt()
    receipt = _owner(store).settle_street_combat(attempt)
    owner = CanonicalCombatThreatAuthority(store=store, authorized_callers=("backend:combat",))
    begun = _begin(owner, source, attempt, receipt)
    assert begun.committed
    assert _hit(owner, source, attempt, receipt).committed
    before = owner.encounter_projection(world_ref=source.world_ref, timeline_ref=source.timeline_ref,
                                        encounter_ref=source.encounter_ref)
    assert before["state"] == "active"
    assert before["rows"] == [{"actor_ref": "character:char_a", "target_ref": "character:char_b", "threat": 20}]
    boundary = store.read_events()[-1].global_sequence
    end_args = dict(world_ref=source.world_ref, timeline_ref=source.timeline_ref, encounter_ref=source.encounter_ref,
                    command_id="end:1", idempotency_key="end:1", authorized_caller="backend:combat",
                    expected_revision=2, reason="combat-complete")
    ended = owner.end_encounter(**end_args)
    assert ended.committed
    assert owner.encounter_projection(world_ref=source.world_ref, timeline_ref=source.timeline_ref,
                                      encounter_ref=source.encounter_ref)["rows"] == []
    store.close()
    store = DurableGameplayEventStore(path)
    owner = CanonicalCombatThreatAuthority(store=store, authorized_callers=("backend:combat",))
    assert owner.end_encounter(**end_args).transaction_id == ended.transaction_id
    assert not owner.end_encounter(**{**end_args, "reason": "changed"}).committed
    assert owner.encounter_projection(world_ref=source.world_ref, timeline_ref=source.timeline_ref,
                                      encounter_ref=source.encounter_ref, checkpoint_at=boundary) == before
    recovered_hit = _hit(owner, source, attempt, receipt)
    assert recovered_hit.committed and recovered_hit.idempotency_status == "duplicate_replayed"
    assert not _begin(owner, source, attempt, receipt, command_id="begin:2", idempotency_key="begin:2").committed
    # Exact receipt lookup is recovery; a fresh hit after end is forbidden.
    next_attempt = _attempt("next")
    next_receipt = _owner(store).settle_street_combat(next_attempt)
    assert not _hit(owner, source, next_attempt, next_receipt).committed
    assert len(store.read_stream(f"gameplay:combat:encounter:{source.encounter_ref}")) == 3
    store.close()


@pytest.mark.parametrize("change", ["caller", "world", "timeline", "incarnation", "receipt"])
def test_encounter_begin_rejects_untrusted_or_changed_sources_zero_write(tmp_path, change):
    store = DurableGameplayEventStore(tmp_path / f"{change}.db")
    source, attempt = _sources(store), _attempt()
    receipt = _owner(store).settle_street_combat(attempt)
    owner = CanonicalCombatThreatAuthority(store=store, authorized_callers=("backend:combat",))
    changes = {"caller": {"authorized_caller": "untrusted"}, "world": {"world_ref": "world:other"},
               "timeline": {"timeline_ref": "timeline:other"}, "incarnation": {"target_incarnation_ref": "character:char_b@2"},
               "receipt": {"authority_result": receipt.model_copy(update={"transaction_id": "forged"})}}[change]
    count = len(store.read_events())
    assert not _begin(owner, source, attempt, receipt, **changes).committed
    assert len(store.read_events()) == count
    store.close()


def test_target_eligibility_is_read_only_and_rejects_superseded_life(tmp_path):
    store = DurableGameplayEventStore(tmp_path / "target.db")
    source, attempt = _sources(store), _attempt()
    owner = CanonicalCombatThreatAuthority(store=store)
    args = dict(attempt=attempt, presence_event_ids=source.presence_source_event_ids,
                life_event_ids=source.life_state_source_event_ids, faction_event_id=source.faction_source_event_id,
                world_ref=source.world_ref, timeline_ref=source.timeline_ref,
                actor_incarnation_ref=source.actor_incarnation_ref,
                target_incarnation_ref=source.target_incarnation_ref)
    before = len(store.read_events())
    assert owner.target_eligibility(**args)["eligible"]
    assert len(store.read_events()) == before
    life_stream = f"gameplay:character:life:{attempt.target_refs[0]}"
    store.append_batch(build_atomic_event_batch(
        command_id="life:despawn", principal_ref="authority:character:life-state:presence-admission",
        stream_id=life_stream, expected_revision=store.get_stream_head(life_stream), schema_version=2,
        event_specs=(("gameplay.character.life_state_changed", {"actor_ref": attempt.target_refs[0],
                       "world_ref": source.world_ref, "incarnation": 1, "from_state": "alive", "to_state": "despawned",
                       "policy_revision": "policy:character-life-state-presence-admission@1",
                       "source_presence_event_id": source.presence_source_event_ids[1],
                       "source_presence_revision": 1}),),
        idempotency_key="life:despawn", causation_id="life:despawn", correlation_id="life:despawn"))
    assert not owner.target_eligibility(**args)["eligible"]
    store.close()


@pytest.mark.parametrize("revision", [True, False, -1, 0])
def test_end_rejects_invalid_expected_revision_without_write(tmp_path, revision):
    store = DurableGameplayEventStore(tmp_path / f"revision-{revision}.db")
    owner = CanonicalCombatThreatAuthority(store=store, authorized_callers=("backend:combat",))
    before = len(store.read_events())
    result = owner.end_encounter(world_ref="world:demo", timeline_ref="timeline:main", encounter_ref="encounter:x",
                                 command_id="end", idempotency_key="end", authorized_caller="backend:combat",
                                 expected_revision=revision, reason="done")
    assert not result.committed
    assert len(store.read_events()) == before
    store.close()
