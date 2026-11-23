from decimal import Decimal

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.morale_refold_runtime import MoraleRefoldAuthority
from app.gameplay.pool_runtime import PoolDefinition
from app.gameplay.settlement_plan import build_atomic_event_batch


ORGANIZATION = "organization:garrison:east@1"
ROLE = "role:garrison-defender@1"
MORALE_FACT = "fact:unit:garrison-east:morale"


def _append(store, *, principal, stream_id, event_type, payload, command_id):
    revision = store.get_stream_head(stream_id)
    result = store.append_batch(build_atomic_event_batch(
        command_id=command_id,
        principal_ref=principal,
        stream_id=stream_id,
        expected_revision=revision,
        event_specs=((event_type, payload),),
        idempotency_key=command_id,
        causation_id=f"cause:{command_id}",
        correlation_id="corr:siege-east",
    ))
    assert result.committed
    return store.get_event(result.committed_event_ids[0])


def _seed_garrison(store, *, members):
    organization_stream = f"gameplay:organization:{ORGANIZATION}"
    for index, member in enumerate(members):
        _append(
            store,
            principal="actor_gameplay.organization_domain",
            stream_id=organization_stream,
            event_type="gameplay.organization.membership_delegation_recorded@1",
            payload={
                "organization_ref": ORGANIZATION,
                "member_ref": member,
                "role_ref": ROLE,
                "provenance_ref": f"provenance:appointment-{index}@1",
                "source_revision_pin": index,
                "delegation_state": "active",
            },
            command_id=f"garrison:{index}",
        )
        _append(
            store,
            principal="authority:character:life-state:presence-admission",
            stream_id=f"gameplay:character:life:{member}",
            event_type="gameplay.character.life_state_changed",
            payload={"actor_ref": member, "from_state": "unknown", "to_state": "alive"},
            command_id=f"life-alive:{index}",
        )


def _seed_roster_only(store, *, members):
    organization_stream = f"gameplay:organization:{ORGANIZATION}"
    for index, member in enumerate(members):
        _append(
            store,
            principal="actor_gameplay.organization_domain",
            stream_id=organization_stream,
            event_type="gameplay.organization.membership_delegation_recorded@1",
            payload={
                "organization_ref": ORGANIZATION,
                "member_ref": member,
                "role_ref": ROLE,
                "provenance_ref": f"provenance:appointment-{index}@1",
                "source_revision_pin": index,
                "delegation_state": "active",
            },
            command_id=f"garrison:{index}",
        )


def _authority(store):
    definition = PoolDefinition(
        fact_type=MORALE_FACT,
        lower=Decimal("0"),
        upper=Decimal("100"),
        initial=Decimal("100"),
        aggregation_mode="distribution",
        refold_model_ref="morale_refold@1",
    )
    return MoraleRefoldAuthority(
        store=store,
        definitions={(ORGANIZATION, ROLE): definition},
    )


def test_morale_refold_uses_historical_roster_and_life_states_at_death():
    store = GameplayEventStore()
    members = tuple(f"character:defender-{index}" for index in range(4))
    _seed_garrison(store, members=members)
    death = _append(
        store,
        principal="authority:character:life-state",
        stream_id=f"gameplay:character:life:{members[0]}",
        event_type="gameplay.character.life_state_changed",
        payload={"actor_ref": members[0], "from_state": "alive", "to_state": "dead"},
        command_id="life-dead:defender-0",
    )
    _append(
        store,
        principal="authority:character:life-state:presence-admission",
        stream_id=f"gameplay:character:life:{members[1]}",
        event_type="gameplay.character.life_state_changed",
        payload={"actor_ref": members[1], "from_state": "unknown", "to_state": "alive"},
        command_id="life-late:defender-1",
    )

    authority = _authority(store)
    assert authority.initialize(
        organization_ref=ORGANIZATION,
        role_ref=ROLE,
        command_id="morale:init",
        idempotency_key="morale:init",
    ).committed
    result = authority.refold_after_casualty(death_event_id=death.event_id)

    assert result.committed
    projection = authority.projection(MORALE_FACT)
    assert projection.value == Decimal("75")
    transaction = store.get_transaction(result.transaction_id)
    assert transaction is not None
    assert transaction.read_stream_revisions[
        f"gameplay:character:life:{members[1]}"
    ] == 2
    assert transaction.pinned_revisions[
        f"input:gameplay:character:life:{members[1]}"
    ] == 1

    _append(
        store,
        principal="actor_gameplay.organization_domain",
        stream_id=f"gameplay:organization:{ORGANIZATION}",
        event_type="gameplay.organization.membership_delegation_recorded@1",
        payload={
            "organization_ref": ORGANIZATION,
            "member_ref": members[1],
            "role_ref": ROLE,
            "provenance_ref": "provenance:revocation@1",
            "source_revision_pin": 4,
            "delegation_state": "revoked",
        },
        command_id="garrison:later-revocation",
    )
    retry = authority.refold_after_casualty(death_event_id=death.event_id)
    assert retry.committed
    assert retry.idempotency_status == "duplicate_replayed"
    assert retry.committed_event_ids == result.committed_event_ids


def test_morale_refold_with_missing_member_life_state_writes_nothing():
    store = GameplayEventStore()
    _seed_roster_only(store, members=("character:defender-0", "character:defender-1"))
    death = _append(
        store,
        principal="authority:character:life-state",
        stream_id="gameplay:character:life:character:defender-0",
        event_type="gameplay.character.life_state_changed",
        payload={"actor_ref": "character:defender-0", "from_state": "alive", "to_state": "dead"},
        command_id="life-dead:defender-0",
    )
    authority = _authority(store)
    assert authority.initialize(
        organization_ref=ORGANIZATION,
        role_ref=ROLE,
        command_id="morale:init",
        idempotency_key="morale:init",
    ).committed
    before = store.export_snapshot()

    result = authority.refold_after_casualty(death_event_id=death.event_id)

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "morale_input_unknown"
    assert store.export_snapshot() == before
