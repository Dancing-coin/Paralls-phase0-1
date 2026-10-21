from pathlib import Path
from dataclasses import replace

import pytest

from app.gameplay.combat_durable_adapter import CombatSourceContext, DurableEmbodiedCombatAdapter
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStoreSnapshotError
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.models.embodied_interaction import ActionAttempt
from app.services.embodied_authority_settlement_service import EmbodiedAuthoritySettlementService


def _attempt(key: str) -> ActionAttempt:
    import hashlib

    attempt_id = f"attempt:{key}"
    ref = f"contact:{attempt_id}:100:short_punch_contact_window"
    canonical = (
        "street-contact-evidence:v1"
        f"|ref={ref}|attempt={attempt_id}|tick=100|marker=short_punch_contact_window"
        "|actor=character:street_bandage|target=character:char_a"
    )
    return ActionAttempt.model_validate({
        "attempt_id": attempt_id,
        "actor_ref": "character:street_bandage",
        "action_instance_id": f"action:{key}",
        "semantic_action_id": "action:melee.unarmed_punch",
        "target_refs": ["character:char_a"],
        "contact_marker_id": "short_punch_contact_window",
        "physics_tick": 100,
        "connection_epoch": 1,
        "client_sequence": 1,
        "physics_evidence_refs": [ref],
        "physics_evidence_digest": "sha256:" + hashlib.sha256(canonical.encode()).hexdigest(),
        "action_descriptor_digest": "sha256:" + "0" * 64,
        "authority_route": "esm",
        "idempotency_key": f"street:{key}",
        "command_version": "v1",
        "causation_id": f"cause:{key}",
        "correlation_id": f"corr:{key}",
        "source": "player",
        "privacy_scope": "public",
    })


def _source() -> CombatSourceContext:
    return CombatSourceContext(
        world_ref="world:demo",
        timeline_ref="timeline:main",
        encounter_ref="encounter:1",
        actor_incarnation_ref="character:street_bandage@1",
        target_incarnation_ref="character:char_a@1",
        presence_source_event_ids=("event:cmd:source-presence:1", "event:cmd:source-presence-target:1"),
        life_state_source_event_ids=("event:cmd:source-life:1", "event:cmd:source-life-target:1"),
        faction_source_event_id="event:cmd:source-faction:1",
    )


def _authority() -> EmbodiedAuthoritySettlementService:
    service = EmbodiedAuthoritySettlementService()
    assert service.record_street_pose("street_bandage", (0.0, 0.2, -9.8), physics_tick=100)
    assert service.record_street_pose("char_a", (-2.0, 0.2, -9.8), physics_tick=100)
    return service


def test_missing_world_sources_fail_closed_without_embodied_write(tmp_path: Path) -> None:
    store = DurableGameplayEventStore(tmp_path / "combat.db")
    adapter = DurableEmbodiedCombatAdapter(authority=_authority(), store=store)
    result = adapter.settle_and_record(_attempt("missing"), source=None, command_id="cmd:missing", idempotency_key="combat:missing")
    assert result.error_code == "combat_truth_source_unavailable"
    assert result.authority_result.outcome == "rejected"
    assert store.read_events() == []
    store.close()


def test_fixture_principals_cannot_admit_combat_sources(tmp_path: Path) -> None:
    store = DurableGameplayEventStore(tmp_path / "spoofed-sources.db")
    _seed_sources(store)
    authority = _authority()
    adapter = DurableEmbodiedCombatAdapter(authority=authority, store=store)
    before = authority.mutation_count
    result = adapter.settle_and_record(
        _attempt("spoofed"), source=_source(), command_id="spoofed", idempotency_key="spoofed",
    )
    assert result.error_code == "combat_truth_source_unavailable"
    assert result.authority_result.outcome == "rejected"
    assert authority.mutation_count == before
    assert adapter.replay_settlements("encounter:1") == []
    store.close()


def test_record_committed_settlement_fails_closed_on_unowned_source_fixture(tmp_path: Path) -> None:
    store = DurableGameplayEventStore(tmp_path / "unowned-recovery.db")
    _seed_sources(store)
    authority = _authority()
    adapter = DurableEmbodiedCombatAdapter(authority=authority, store=store)
    attempt = _attempt("unowned-recovery")
    embodied = authority.settle_street_combat(attempt)
    assert embodied.outcome == "committed"
    before = authority.mutation_count
    result = adapter.record_committed_settlement(
        attempt, authority_result=embodied, source=_source(),
        command_id="unowned-recovery", idempotency_key="unowned-recovery",
    )
    assert result.error_code == "combat_truth_source_unavailable"
    assert result.append_result is None
    assert authority.mutation_count == before
    assert adapter.replay_settlements("encounter:1") == []
    store.close()


@pytest.mark.parametrize("change", [
    {"actor_incarnation_ref": "prefix-character:street_bandage@1-suffix"},
    {"actor_incarnation_ref": "character:char_a@1", "target_incarnation_ref": "character:street_bandage@1"},
    {"life_state_source_event_ids": ("event:cmd:source-life-target:1", "event:cmd:source-life:1")},
    {"presence_source_event_ids": ()},
])
def test_invalid_source_identity_rejected_without_owner_mutation(tmp_path: Path, change: dict) -> None:
    store = DurableGameplayEventStore(tmp_path / "invalid.db")
    _seed_sources(store)
    authority = _authority()
    adapter = DurableEmbodiedCombatAdapter(authority=authority, store=store)
    before = authority.mutation_count
    result = adapter.settle_and_record(_attempt("invalid"), source=replace(_source(), **change), command_id="invalid", idempotency_key="invalid")
    assert result.error_code == "combat_truth_source_unavailable"
    assert authority.mutation_count == before
    assert adapter.replay_settlements("encounter:1") == []
    store.close()


@pytest.mark.parametrize("stream,event_type,payload", [
    ("presence:world:demo", "population.presence.despawned", {"world_ref": "world:demo", "character_ref": "char_a", "incarnation": 1}),
    ("life:street_bandage", "gameplay.character.life_state_changed", {"actor_ref": "character:street_bandage", "to_state": "dead"}),
    ("life:char_a", "gameplay.character.life_state_changed", {"actor_ref": "character:char_a", "to_state": "dead"}),
])
def test_superseded_sources_fail_closed(tmp_path: Path, stream: str, event_type: str, payload: dict) -> None:
    store = DurableGameplayEventStore(tmp_path / "superseded.db")
    _seed_sources(store)
    result = store.append_batch(build_atomic_event_batch(
        command_id="supersede", principal_ref="authority:test-source", stream_id=stream,
        expected_revision=store.get_stream_head(stream), event_specs=((event_type, payload),),
        idempotency_key="supersede", causation_id="supersede", correlation_id="supersede",
    ))
    assert result.committed
    authority = _authority()
    adapter = DurableEmbodiedCombatAdapter(authority=authority, store=store)
    before = authority.mutation_count
    rejected = adapter.settle_and_record(_attempt("stale"), source=_source(), command_id="stale", idempotency_key="stale")
    assert rejected.error_code == "combat_truth_source_unavailable"
    assert authority.mutation_count == before
    assert adapter.replay_settlements("encounter:1") == []
    store.close()


def test_missing_canonical_faction_owner_keeps_combat_closed(tmp_path: Path) -> None:
    store = DurableGameplayEventStore(tmp_path / "faction-owner-missing.db")
    _seed_sources(store)
    owner = _authority()
    adapter = DurableEmbodiedCombatAdapter(authority=owner, store=store)
    before = owner.mutation_count
    result = adapter.settle_and_record(
        _attempt("missing-faction-owner"), source=_source(),
        command_id="missing-faction-owner", idempotency_key="missing-faction-owner",
    )
    assert result.error_code == "combat_truth_source_unavailable"
    assert owner.mutation_count == before
    assert adapter.replay_settlements("encounter:1") == []
    store.close()


def test_stale_faction_source_rejected(tmp_path: Path) -> None:
    store = DurableGameplayEventStore(tmp_path / "faction-stale.db")
    _seed_sources(store)
    result = store.append_batch(build_atomic_event_batch(
        command_id="faction-change", principal_ref="authority:test-source", stream_id="faction:1",
        expected_revision=store.get_stream_head("faction:1"), event_specs=(("gameplay.combat.faction_relation_recorded", {
            "actor_ref": "character:street_bandage", "target_ref": "character:char_a", "hostile": False,
        }),), idempotency_key="faction-change", causation_id="faction-change", correlation_id="faction-change",
    ))
    assert result.committed
    authority = _authority()
    adapter = DurableEmbodiedCombatAdapter(authority=authority, store=store)
    before = authority.mutation_count
    rejected = adapter.settle_and_record(_attempt("stale-faction"), source=_source(), command_id="stale-faction", idempotency_key="stale-faction")
    assert rejected.error_code == "combat_truth_source_unavailable"
    assert authority.mutation_count == before
    store.close()


def test_corrupt_durable_receipt_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    store = DurableGameplayEventStore(tmp_path / "corrupt.db")
    _seed_sources(store)
    authority = _authority()
    adapter = DurableEmbodiedCombatAdapter(authority=authority, store=store)
    embodied = authority.settle_street_combat(_attempt("corrupt"))
    assert embodied.outcome == "committed"
    monkeypatch.setattr(store, "get_by_idempotency", lambda *_args: (_ for _ in ()).throw(GameplayEventStoreSnapshotError("bad receipt")))
    result = adapter.record_committed_settlement(_attempt("corrupt"), authority_result=embodied, source=_source(), command_id="corrupt", idempotency_key="corrupt")
    assert result.error_code == "receipt_invalid"
    assert adapter.replay_settlements("encounter:1") == []
    store.close()


def _seed_sources(store: DurableGameplayEventStore) -> None:
    rows = [
        ("source-presence", "presence:world:demo", "population.presence.spawned", {"world_ref": "world:demo", "timeline_ref": "timeline:main", "character_ref": "street_bandage", "incarnation": 1}),
        ("source-presence-target", "presence:world:demo", "population.presence.spawned", {"world_ref": "world:demo", "timeline_ref": "timeline:main", "character_ref": "char_a", "incarnation": 1}),
        ("source-life", "life:street_bandage", "gameplay.character.life_state_changed", {"actor_ref": "character:street_bandage", "timeline_ref": "timeline:main", "to_state": "alive"}),
        ("source-life-target", "life:char_a", "gameplay.character.life_state_changed", {"actor_ref": "character:char_a", "timeline_ref": "timeline:main", "to_state": "alive"}),
        ("source-faction", "faction:1", "gameplay.combat.faction_relation_recorded", {"actor_ref": "character:street_bandage", "target_ref": "character:char_a", "timeline_ref": "timeline:main", "hostile": True}),
    ]
    for command, stream, event_type, payload in rows:
        result = store.append_batch(build_atomic_event_batch(
            command_id=f"cmd:{command}", principal_ref="authority:test-source", stream_id=stream,
            expected_revision=store.get_stream_head(stream), event_specs=((event_type, payload),), idempotency_key=f"id:{command}",
            causation_id=f"cause:{command}", correlation_id="corr:source",
        ))
        assert result.committed
