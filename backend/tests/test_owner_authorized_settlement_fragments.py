from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.settlement_plan import (
    OwnerAuthorizedFragment,
    build_multi_stream_atomic_event_batch_from_fragments,
)


def test_owner_authorized_fragments_preserve_provenance_in_one_atomic_batch() -> None:
    organization = OwnerAuthorizedFragment(
        fragment_id="fragment:organization:buyer",
        owner_principal_ref="actor_gameplay.organization_domain",
        source_rule_ref="p4b:budget-grant",
        expected_revisions={"gameplay:organization:organization:bakery-a": 0},
        event_specs={
            "gameplay:organization:organization:bakery-a": (
                ("gameplay.organization.commerce_commitment_accepted", {"commitment_ref": "commitment:1"}),
            )
        },
    )
    inventory = OwnerAuthorizedFragment(
        fragment_id="fragment:inventory:seller",
        owner_principal_ref="actor_gameplay.inventory_domain",
        source_rule_ref="p4b:custody-reservation",
        expected_revisions={"gameplay:inventory:organization:supplier": 0},
        event_specs={
            "gameplay:inventory:organization:supplier": (
                ("gameplay.inventory.custody_reserved_for_commerce", {"commitment_ref": "commitment:1"}),
            )
        },
    )

    batch = build_multi_stream_atomic_event_batch_from_fragments(
        command_id="p4b:commit:commitment:1",
        idempotency_principal_ref="actor_gameplay.commerce_authority",
        idempotency_key="p4b:commitment:1",
        causation_id="cause:commitment:1",
        correlation_id="correlation:commitment:1",
        fragments=(organization, inventory),
    )
    receipt = GameplayEventStore().append_batch(batch)

    assert receipt.committed
    assert tuple(fragment.owner_principal_ref for fragment in batch.owner_fragments) == (
        "actor_gameplay.inventory_domain",
        "actor_gameplay.organization_domain",
    )
    assert {event.stream_id for event in batch.events} == {
        "gameplay:organization:organization:bakery-a",
        "gameplay:inventory:organization:supplier",
    }


def test_owner_authorized_fragments_reject_overlapping_streams() -> None:
    first = OwnerAuthorizedFragment(
        fragment_id="fragment:first",
        owner_principal_ref="actor_gameplay.organization_domain",
        source_rule_ref="p4b:first",
        expected_revisions={"gameplay:organization:organization:bakery-a": 0},
        event_specs={"gameplay:organization:organization:bakery-a": (("gameplay.organization.first", {}),)},
    )
    second = first.model_copy(update={"fragment_id": "fragment:second"})

    try:
        build_multi_stream_atomic_event_batch_from_fragments(
            command_id="p4b:overlap",
            idempotency_principal_ref="actor_gameplay.commerce_authority",
            idempotency_key="p4b:overlap",
            causation_id="cause:overlap",
            correlation_id="correlation:overlap",
            fragments=(first, second),
        )
    except ValueError as exc:
        assert str(exc) == "settlement_fragment_stream_overlap"
    else:
        raise AssertionError("fragments must not silently share a target stream")
