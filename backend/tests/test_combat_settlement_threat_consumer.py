from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.canonical_combat_authority import (
    CombatFactionRelationAuthority,
    FactionRelationRequest,
    THREAT_PRINCIPAL,
)
from app.gameplay.combat_durable_adapter import CombatSourceContext, DurableEmbodiedCombatAdapter
from app.gameplay.event_store import DurableGameplayEventStore
from app.models.embodied_interaction import ActionAttempt, AuthorityResult
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.activation_sources import ActivationSourceReader
from app.population_continuity.activation_presence import PopulationActivationPresenceService
from app.population_continuity.models import ActivationGrant, ActivationProposal
from app.population_continuity.presence_runtime import PopulationPresenceAuthority
from app.services.embodied_authority_settlement_service import EmbodiedAuthoritySettlementService


ROOT = Path(__file__).resolve().parents[2]


def _attempt(key: str = "hit-1") -> ActionAttempt:
    attempt_id = f"attempt:{key}"
    contact = f"contact:{attempt_id}:100:short_punch_contact_window"
    canonical = (
        "street-contact-evidence:v1"
        f"|ref={contact}|attempt={attempt_id}|tick=100|marker=short_punch_contact_window"
        "|actor=character:char_a|target=character:char_b"
    )
    return ActionAttempt.model_validate({
        "attempt_id": attempt_id,
        "actor_ref": "character:char_a",
        "action_instance_id": f"action:{key}",
        "semantic_action_id": "action:melee.short_punch",
        "target_refs": ["character:char_b"],
        "contact_marker_id": "short_punch_contact_window",
        "physics_tick": 100,
        "connection_epoch": 1,
        "client_sequence": 1,
        "physics_evidence_refs": [contact],
        "physics_evidence_digest": "sha256:" + sha256(canonical.encode()).hexdigest(),
        "action_descriptor_digest": "sha256:" + "0" * 64,
        "authority_route": "esm",
        "idempotency_key": f"street:{key}",
        "command_version": "v1",
        "causation_id": f"cause:{key}",
        "correlation_id": f"corr:{key}",
        "source": "player",
        "privacy_scope": "public",
    })


def _sources(store: DurableGameplayEventStore) -> CombatSourceContext:
    policy = dict(world_ref="world:demo", package_revision="package:bakery-authored-agents:v1",
                  policy_revision="policy:population:v1", scope_grant=("actor:self",))
    actors = ("character:char_a", "character:char_b")
    activation = ProfileActivationAuthority(
        registry=CharacterProfileRegistry.from_directory(ROOT / "assets/characters/profiles"),
        store=store,
        grants=tuple(ActivationGrant(profile_ref=actor, **policy) for actor in actors),
    )
    producer_ref = "population:siming"
    population = PopulationActivationPresenceService(
        store=store,
        presence_authority=PopulationPresenceAuthority(
            store=store,
            activation_sources=ActivationSourceReader(authority=activation, producer_ref=producer_ref),
        ),
        activation_authority=activation,
        producer_ref=producer_ref,
    )
    presence_events = []
    for actor in actors:
        result = population.commit_and_spawn(
            ActivationProposal(
                proposal_id=f"proposal:{actor}", profile_ref=actor, **policy,
                activation_reason="population-cadence", cadence_class="simulation",
                expected_revisions={"population:world:demo": store.get_stream_head("population:world:demo")},
                idempotency_key=f"activation:{actor}", correlation_id=f"corr:{actor}",
                source_ref="population:siming",
            ),
            presence_idempotency_key=f"presence:{actor}",
            presence_expected_revision=store.get_stream_head("presence:world:demo"),
        )
        assert result.presence is not None and result.presence.committed
        presence_events.append(store.get_event(result.presence.committed_event_ids[0]))
    life_events = [store.read_stream(f"gameplay:character:life:{actor}")[-1] for actor in actors]
    faction = CombatFactionRelationAuthority(store=store, authorized_callers=("combat:policy-caller",)).record(
        FactionRelationRequest(
            world_ref="world:demo", timeline_ref="timeline:main", actor_ref=actors[0], target_ref=actors[1],
            hostile=True, command_id="faction:hit", idempotency_key="faction:hit", causation_id="cause:faction",
            correlation_id="corr:faction", authorized_caller="combat:policy-caller",
        )
    )
    assert faction.committed
    return CombatSourceContext(
        world_ref="world:demo", timeline_ref="timeline:main", encounter_ref="encounter:real-1",
        actor_incarnation_ref="character:char_a@1", target_incarnation_ref="character:char_b@1",
        presence_source_event_ids=tuple(event.event_id for event in presence_events),
        life_state_source_event_ids=tuple(event.event_id for event in life_events),
        faction_source_event_id=faction.committed_event_ids[0],
    )


def _owner(store: DurableGameplayEventStore) -> EmbodiedAuthoritySettlementService:
    owner = EmbodiedAuthoritySettlementService(store=store)
    assert owner.record_street_pose("char_a", (0.0, 0.2, -9.8), physics_tick=100)
    assert owner.record_street_pose("char_b", (1.0, 0.2, -9.8), physics_tick=100)
    return owner


def test_real_embodied_settlement_is_consumed_by_canonical_threat_owner(tmp_path: Path) -> None:
    store = DurableGameplayEventStore(tmp_path / "combat-threat.db")
    source = _sources(store)
    owner = _owner(store)
    attempt = _attempt()
    receipt = owner.settle_street_combat(attempt)
    assert receipt.outcome == "committed"
    adapter = DurableEmbodiedCombatAdapter(authority=owner, store=store)

    result = adapter.consume_committed_hit(
        attempt, source=source, command_id="threat:hit", idempotency_key="threat:hit",
    )
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    transaction = store.get_transaction(result.transaction_id)
    assert transaction is not None and transaction.idempotency_record.principal_ref == THREAT_PRINCIPAL
    assert event.payload["damage"] == 20
    assert event.payload["policy_revision"] == "threat:confirmed-hit-1to1@1"
    assert event.payload["embodied_event_id"] == receipt.committed_event_ids[0]
    assert event.payload["embodied_transaction_id"] == receipt.transaction_id
    assert event.payload["attempt_payload_digest"] == attempt.payload_digest
    assert adapter.replay_settlements(source.encounter_ref) == []
    store.close()


def test_one_hit_is_consumed_once_even_when_caller_retry_key_changes(tmp_path: Path) -> None:
    store = DurableGameplayEventStore(tmp_path / "combat-threat-once.db")
    source = _sources(store)
    owner = _owner(store)
    attempt = _attempt("once")
    receipt = owner.settle_street_combat(attempt)
    assert receipt.outcome == "committed"
    adapter = DurableEmbodiedCombatAdapter(authority=owner, store=store)
    first = adapter.consume_committed_hit(attempt, source=source, command_id="transport:1", idempotency_key="transport:1")
    retry = adapter.consume_committed_hit(attempt, source=source, command_id="transport:2", idempotency_key="transport:2")
    assert first.committed and retry.committed and retry.idempotency_status == "duplicate_replayed"
    assert retry.transaction_id == first.transaction_id
    changed = adapter.consume_committed_hit(
        attempt, source=replace(source, encounter_ref="encounter:other"),
        command_id="transport:3", idempotency_key="transport:3",
    )
    assert not changed.committed and changed.failure.error_code == "threat_idempotency_key_reused"
    assert store.read_stream("gameplay:combat:encounter:encounter:other") == []
    assert len(store.read_stream("gameplay:combat:encounter:encounter:real-1")) == 1
    store.close()


def test_threat_consumer_duplicate_replays_after_durable_reopen(tmp_path: Path) -> None:
    path = tmp_path / "combat-threat-reopen.db"
    store = DurableGameplayEventStore(path)
    source = _sources(store)
    owner = _owner(store)
    attempt = _attempt("reopen")
    assert owner.settle_street_combat(attempt).outcome == "committed"
    first = DurableEmbodiedCombatAdapter(authority=owner, store=store).consume_committed_hit(
        attempt, source=source, command_id="threat:reopen", idempotency_key="threat:reopen",
    )
    assert first.committed
    store.close()

    reopened = DurableGameplayEventStore(path)
    recovered_owner = _owner(reopened)
    adapter = DurableEmbodiedCombatAdapter(authority=recovered_owner, store=reopened)
    duplicate = adapter.consume_committed_hit(
        attempt, source=source, command_id="threat:reopen", idempotency_key="threat:reopen",
    )
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert len(reopened.read_stream("gameplay:combat:encounter:encounter:real-1")) == 1
    reopened.close()


def test_threat_consumer_missing_source_or_spoofed_receipt_writes_nothing(tmp_path: Path) -> None:
    store = DurableGameplayEventStore(tmp_path / "combat-threat-closed.db")
    owner = _owner(store)
    adapter = DurableEmbodiedCombatAdapter(authority=owner, store=store)
    attempt = _attempt("closed")
    missing = adapter.consume_committed_hit(attempt, source=None, command_id="threat:closed", idempotency_key="threat:closed")
    assert not missing.committed and missing.failure.error_code == "threat_source_unavailable"
    spoofed = AuthorityResult(
        attempt_id=attempt.attempt_id, action_instance_id=attempt.action_instance_id, outcome="committed",
        transaction_id="spoofed", committed_event_ids=["spoofed:event"], causation_id=attempt.causation_id,
        correlation_id=attempt.correlation_id, authority_scope="embodied", committed_projection={"damage": 20},
    )
    result = adapter.consume_committed_hit(
        attempt, source=replace(_empty_source(), encounter_ref="encounter:spoof"),
        authority_result=spoofed, command_id="threat:spoof", idempotency_key="threat:spoof",
    )
    assert not result.committed and result.failure.error_code == "embodied_receipt_invalid"
    assert store.read_events() == []
    store.close()


def _empty_source() -> CombatSourceContext:
    return CombatSourceContext(
        world_ref="world:demo", timeline_ref="timeline:main", encounter_ref="encounter:empty",
        actor_incarnation_ref="character:char_a@1", target_incarnation_ref="character:char_b@1",
        presence_source_event_ids=("missing:presence:a", "missing:presence:b"),
        life_state_source_event_ids=("missing:life:a", "missing:life:b"),
        faction_source_event_id="missing:faction",
    )


def test_canonical_owner_cannot_consume_same_hit_with_another_request_key(tmp_path):
    from app.gameplay.canonical_combat_authority import CanonicalCombatThreatAuthority
    with_store = DurableGameplayEventStore(tmp_path / "direct-repeat.db")
    try:
        source = _sources(with_store)
        owner = _owner(with_store)
        attempt = _attempt("direct-repeat")
        receipt = owner.settle_street_combat(attempt)
        threat = CanonicalCombatThreatAuthority(store=with_store)
        args = dict(attempt=attempt, authority_result=receipt,
                    presence_event_ids=source.presence_source_event_ids,
                    life_event_ids=source.life_state_source_event_ids,
                    faction_event_id=source.faction_source_event_id,
                    world_ref=source.world_ref, timeline_ref=source.timeline_ref,
                    encounter_ref=source.encounter_ref,
                    actor_incarnation_ref=source.actor_incarnation_ref,
                    target_incarnation_ref=source.target_incarnation_ref)
        first = threat.record_confirmed_hit(**args, command_id="direct:1", idempotency_key="direct:1")
        assert first.committed
        repeated = threat.record_confirmed_hit(**args, command_id="direct:2", idempotency_key="direct:2")
        assert repeated.committed and repeated.idempotency_status == "duplicate_replayed"
        assert repeated.transaction_id == first.transaction_id
        assert len(with_store.read_stream(f"gameplay:combat:encounter:{source.encounter_ref}")) == 1
    finally:
        with_store.close()
