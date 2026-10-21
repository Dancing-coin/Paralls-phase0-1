from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace
import pytest

from app.gameplay.canonical_combat_authority import (
    FACTION_PRINCIPAL,
    CanonicalCombatThreatAuthority,
    CombatFactionRelationAuthority,
    FactionRelationRequest,
)
from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.models.embodied_interaction import AuthorityResult


def _request(caller: str = "combat:policy-caller") -> FactionRelationRequest:
    return FactionRelationRequest(
        world_ref="world:demo", timeline_ref="timeline:main",
        actor_ref="character:street_bandage", target_ref="character:char_a", hostile=True,
        command_id="faction:1", idempotency_key="faction:1", causation_id="cause:1",
        correlation_id="corr:1", authorized_caller=caller,
    )


def test_faction_owner_requires_authorized_caller_and_persists_receipt(tmp_path: Path) -> None:
    store = DurableGameplayEventStore(tmp_path / "faction.db")
    owner = CombatFactionRelationAuthority(store=store, authorized_callers=("combat:policy-caller",))
    denied = owner.record(_request("untrusted"))
    assert not denied.committed and denied.failure.error_code == "faction_caller_not_authorized"
    committed = owner.record(_request())
    assert committed.committed
    event = store.get_event(committed.committed_event_ids[0])
    tx = store.get_transaction(committed.transaction_id)
    assert tx is not None and tx.idempotency_record.principal_ref == FACTION_PRINCIPAL
    assert event.payload["hostile"] is True
    replay = owner.record(_request())
    assert replay.committed and replay.idempotency_status == "duplicate_replayed"
    store.close()


def test_faction_replay_survives_durable_reopen_and_changed_payload_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "faction-reopen.db"
    store = DurableGameplayEventStore(path)
    owner = CombatFactionRelationAuthority(store=store, authorized_callers=("combat:policy-caller",))
    committed = owner.record(_request())
    assert committed.committed
    store.close()

    reopened = DurableGameplayEventStore(path)
    owner = CombatFactionRelationAuthority(store=reopened, authorized_callers=("combat:policy-caller",))
    replay = owner.record(_request())
    assert replay.committed and replay.idempotency_status == "duplicate_replayed"
    changed = owner.record(replace(_request(), hostile=False))
    assert not changed.committed
    assert changed.failure.error_code == "faction_idempotency_key_reused"
    assert len(reopened.read_events()) == 1
    reopened.close()


def test_faction_owner_rejects_non_boolean_hostile_without_write(tmp_path: Path) -> None:
    store = DurableGameplayEventStore(tmp_path / "faction-type.db")
    owner = CombatFactionRelationAuthority(store=store, authorized_callers=("combat:policy-caller",))
    result = owner.record(replace(_request(), hostile=1))
    assert not result.committed and result.failure.error_code == "faction_request_invalid"
    assert store.read_events() == []
    store.close()


def test_threat_rejects_multi_event_embodied_receipt() -> None:
    owner = CanonicalCombatThreatAuthority(store=object())
    attempt = SimpleNamespace(idempotency_key="hit:1", attempt_id="attempt:1", payload_digest="sha256:" + "0" * 64)
    result = AuthorityResult(
        attempt_id="attempt:1", action_instance_id="action:1", transaction_id="tx:1",
        outcome="committed", committed_event_ids=["event:1", "event:2"],
        causation_id="cause:1", correlation_id="corr:1", authority_scope="world:demo",
        committed_projection={"damage": 1},
    )
    assert owner._embodied_receipt_matches(attempt, result) is False


def test_threat_does_not_treat_unknown_life_state_as_alive() -> None:
    actor_ref, target_ref = "character:street_bandage", "character:char_a"
    presence = [
        SimpleNamespace(event_id=f"presence:{actor_ref}", event_type="population.presence.spawned", stream_id="presence:world:demo", schema_version=1, visibility_policy="project", transaction_id="tx:p1", payload={"timeline_ref": "timeline:main", "world_ref": "world:demo", "character_ref": actor_ref.removeprefix("character:"), "incarnation": 1}),
        SimpleNamespace(event_id=f"presence:{target_ref}", event_type="population.presence.spawned", stream_id="presence:world:demo", schema_version=1, visibility_policy="project", transaction_id="tx:p2", payload={"timeline_ref": "timeline:main", "world_ref": "world:demo", "character_ref": target_ref.removeprefix("character:"), "incarnation": 1}),
    ]
    life = [
        SimpleNamespace(event_id=f"life:{actor_ref}", event_type="gameplay.character.life_state_changed", stream_id="gameplay:character:life:street_bandage", schema_version=1, visibility_policy="project", transaction_id="tx:l1", payload={"timeline_ref": "timeline:main", "actor_ref": actor_ref, "to_state": "unknown"}),
        SimpleNamespace(event_id=f"life:{target_ref}", event_type="gameplay.character.life_state_changed", stream_id="gameplay:character:life:char_a", schema_version=1, visibility_policy="project", transaction_id="tx:l2", payload={"timeline_ref": "timeline:main", "actor_ref": target_ref, "to_state": "unknown"}),
    ]
    class SourceStore:
        def transaction_owns_event(self, **kwargs): return True
        def read_stream(self, stream_id):
            return {"presence:world:demo": presence, "gameplay:character:life:street_bandage": life[:1], "gameplay:character:life:char_a": life[1:]}[stream_id]
    owner = CanonicalCombatThreatAuthority(store=SourceStore())
    attempt = SimpleNamespace(actor_ref=actor_ref, target_refs=[target_ref])
    assert owner._valid_sources(presence + life, attempt, "world:demo", "timeline:main", "character:street_bandage@1", "character:char_a@1") is False


def test_threat_owner_fails_closed_without_canonical_sources(tmp_path: Path) -> None:
    store = DurableGameplayEventStore(tmp_path / "threat.db")
    owner = CanonicalCombatThreatAuthority(store=store)
    result = owner.record_confirmed_hit(
        attempt=object(), authority_result=object(), presence_event_ids=(), life_event_ids=(),
        faction_event_id="missing", world_ref="world:demo", timeline_ref="timeline:main",
        encounter_ref="encounter:1", actor_incarnation_ref="character:street_bandage@1",
        target_incarnation_ref="character:char_a@1", command_id="threat:missing", idempotency_key="threat:missing",
    )
    assert not result.committed and result.failure.error_code == "threat_source_unavailable"
    assert store.read_events() == []
    store.close()


def test_threat_rejects_superseded_hostile_faction_relation(tmp_path: Path) -> None:
    store = DurableGameplayEventStore(tmp_path / "threat-stale-faction.db")
    owner = CanonicalCombatThreatAuthority(store=store)
    actor = "character:street_bandage"
    target = "character:char_a"
    presence_actor = _append_source(store, "presence:actor", "population.presence.spawned", "presence:world:demo", {
        "world_ref": "world:demo", "timeline_ref": "timeline:main", "character_ref": "street_bandage", "incarnation": 1,
    }, "population.presence_authority")
    presence_target = _append_source(store, "presence:target", "population.presence.spawned", "presence:world:demo", {
        "world_ref": "world:demo", "timeline_ref": "timeline:main", "character_ref": "char_a", "incarnation": 1,
    }, "population.presence_authority")
    life_actor = _append_source(store, "life:actor", "gameplay.character.life_state_changed", "gameplay:character:life:street_bandage", {
        "actor_ref": actor, "timeline_ref": "timeline:main", "to_state": "alive",
    }, "authority:character:life-state")
    life_target = _append_source(store, "life:target", "gameplay.character.life_state_changed", "gameplay:character:life:char_a", {
        "actor_ref": target, "timeline_ref": "timeline:main", "to_state": "alive",
    }, "authority:character:life-state")
    faction_owner = CombatFactionRelationAuthority(store=store, authorized_callers=("combat:policy-caller",))
    hostile = faction_owner.record(_request())
    assert hostile.committed
    hostile_event_id = hostile.committed_event_ids[0]
    friendly = faction_owner.record(replace(
        _request(), hostile=False, command_id="faction:2", idempotency_key="faction:2",
        causation_id="cause:2", correlation_id="corr:2",
    ))
    assert friendly.committed

    attempt = SimpleNamespace(
        actor_ref=actor, target_refs=[target], causation_id="cause:hit", correlation_id="corr:hit",
        idempotency_key="hit:1", attempt_id="hit:1", payload_digest="sha256:" + "0" * 64,
    )
    authority_result = AuthorityResult(
        attempt_id="hit:1", action_instance_id="action:1", transaction_id="embodied:1",
        outcome="committed", committed_event_ids=["embodied:event"], causation_id="cause:hit",
        correlation_id="corr:hit", authority_scope="world:demo", committed_projection={"damage": 1},
    )
    result = owner.record_confirmed_hit(
        attempt=attempt, authority_result=authority_result,
        presence_event_ids=(presence_actor.committed_event_ids[0], presence_target.committed_event_ids[0]),
        life_event_ids=(life_actor.committed_event_ids[0], life_target.committed_event_ids[0]),
        faction_event_id=hostile_event_id, world_ref="world:demo", timeline_ref="timeline:main",
        encounter_ref="encounter:1", actor_incarnation_ref="character:street_bandage@1",
        target_incarnation_ref="character:char_a@1", command_id="threat:1", idempotency_key="threat:1",
    )
    assert not result.committed
    assert result.failure.error_code == "target_not_eligible"
    assert store.read_stream("gameplay:combat:encounter:encounter:1") == []
    store.close()


def _append_source(store, command_id, event_type, stream_id, payload, principal):
    return store.append_batch(build_atomic_event_batch(
        command_id=command_id, principal_ref=principal, stream_id=stream_id,
        expected_revision=store.get_stream_head(stream_id), event_specs=((event_type, payload),),
        idempotency_key=command_id, causation_id=command_id, correlation_id=command_id,
    ))


def _real_population_sources(store):
    from app.character_agent.profile.registry import CharacterProfileRegistry
    from app.population_continuity.activation import ProfileActivationAuthority
    from app.population_continuity.activation_presence import PopulationActivationPresenceService
    from app.population_continuity.models import ActivationGrant, ActivationProposal
    from app.population_continuity.presence_runtime import PopulationPresenceAuthority

    actors = ("character:char_a", "character:char_b")
    policy = dict(world_ref="world:demo", package_revision="package:bakery-authored-agents:v1",
                  policy_revision="policy:population:v1", scope_grant=("actor:self",))
    service = PopulationActivationPresenceService(
        store=store, presence_authority=PopulationPresenceAuthority(store=store),
        activation_authority=ProfileActivationAuthority(
            registry=CharacterProfileRegistry.from_directory(Path(__file__).resolve().parents[2] / "assets/characters/profiles"),
            store=store, grants=tuple(ActivationGrant(profile_ref=actor, **policy) for actor in actors)),
    )
    presence = []
    for actor in actors:
        result = service.commit_and_spawn(ActivationProposal(
            proposal_id=f"proposal:{actor}", profile_ref=actor, **policy,
            activation_reason="population-cadence", cadence_class="simulation",
            expected_revisions={"population:world:demo": store.get_stream_head("population:world:demo")},
            idempotency_key=f"activation:{actor}", correlation_id=f"corr:{actor}", source_ref="population:siming",
        ), presence_idempotency_key=f"presence:{actor}",
            presence_expected_revision=store.get_stream_head("presence:world:demo"))
        assert result.presence is not None and result.presence.committed and not result.recovery_required
        presence.append(store.get_event(result.presence.committed_event_ids[0]))
    life = [store.read_stream(f"gameplay:character:life:{actor}")[-1] for actor in actors]
    relation = CombatFactionRelationAuthority(store=store, authorized_callers=("combat:policy-caller",)).record(
        replace(_request(), actor_ref=actors[0], target_ref=actors[1]))
    assert relation.committed
    return presence + life + [store.get_event(relation.committed_event_ids[0])]


def test_threat_accepts_real_population_presence_and_initial_alive_after_durable_reopen(tmp_path):
    path = tmp_path / "real-population.db"
    store = DurableGameplayEventStore(path)
    sources = _real_population_sources(store)
    ids = [event.event_id for event in sources]
    store.close()
    reopened = DurableGameplayEventStore(path)
    owner = CanonicalCombatThreatAuthority(store=reopened)
    sources = [reopened.get_event(event_id) for event_id in ids]
    assert "timeline_ref" not in sources[0].payload
    assert owner._valid_sources(sources, SimpleNamespace(actor_ref="character:char_a", target_refs=["character:char_b"]),
                                "world:demo", "timeline:main", "character:char_a@1", "character:char_b@1")
    reopened.close()


@pytest.mark.parametrize("change", ["world", "timeline", "incarnation", "source_ref", "owner", "dead", "legacy_dead"])
def test_threat_real_sources_reject_scope_or_provenance_changes(tmp_path, change):
    store = DurableGameplayEventStore(tmp_path / f"real-{change}.db")
    sources = _real_population_sources(store)
    world, timeline, incarnation = "world:demo", "timeline:main", "character:char_a@1"
    if change == "world": world = "world:other"
    elif change == "timeline": timeline = "timeline:other"
    elif change == "incarnation": incarnation = "character:char_a@2"
    elif change == "source_ref":
        sources[2] = sources[2].model_copy(update={"payload": {**sources[2].payload, "source_presence_event_id": sources[1].event_id}})
    elif change == "owner":
        sources[2] = sources[2].model_copy(update={"transaction_id": sources[4].transaction_id})
    elif change == "dead":
        _append_source(store, "dead", "gameplay.character.life_state_changed", sources[2].stream_id,
                       {"actor_ref": "character:char_a", "to_state": "dead"}, "authority:character:life-state")
    elif change == "legacy_dead":
        _append_source(store, "dead", "gameplay.character.life_state_changed", "gameplay:character:life:char_a",
                       {"actor_ref": "character:char_a", "to_state": "dead"}, "authority:character:life-state")
    assert not CanonicalCombatThreatAuthority(store=store)._valid_sources(
        sources, SimpleNamespace(actor_ref="character:char_a", target_refs=["character:char_b"]),
        world, timeline, incarnation, "character:char_b@1")
    store.close()


def test_threat_rejects_owned_life_event_with_wrong_activation_revision(tmp_path):
    store = DurableGameplayEventStore(tmp_path / "bad-activation-pin.db")
    sources = _real_population_sources(store)
    original = sources[2]
    malformed = store.append_batch(build_atomic_event_batch(
        command_id="malformed-life", principal_ref="authority:character:life-state:presence-admission",
        stream_id=original.stream_id, schema_version=2,
        expected_revision=store.get_stream_head(original.stream_id),
        event_specs=((original.event_type, {**original.payload, "source_activation_revision": 999}),),
        idempotency_key="malformed-life", causation_id="malformed-life", correlation_id="malformed-life",
    ))
    assert malformed.committed
    sources[2] = store.get_event(malformed.committed_event_ids[0])
    assert not CanonicalCombatThreatAuthority(store=store)._valid_sources(
        sources, SimpleNamespace(actor_ref="character:char_a", target_refs=["character:char_b"]),
        "world:demo", "timeline:main", "character:char_a@1", "character:char_b@1")
    store.close()
