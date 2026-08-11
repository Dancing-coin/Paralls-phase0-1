from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import OwnerAuthorizedFragment
from app.gameplay.settlement_plan import (
    SettlementPlan,
    build_atomic_event_batch,
    build_multi_stream_atomic_event_batch,
    build_multi_stream_atomic_event_batch_from_fragments,
)
from app.gameplay.shared_contracts import GameplayCommandEnvelope


def _event(event_id: str, *, stream_id: str, tx: str, command_id: str) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_type": "gameplay.contract.updated",
        "schema_version": 1,
        "stream_id": stream_id,
        "stream_revision": 0,
        "global_sequence": 0,
        "transaction_id": tx,
        "command_id": command_id,
        "causation_id": command_id,
        "correlation_id": f"corr:{command_id}",
        "visibility_policy": "project",
        "payload": {"stream_id": stream_id, "event_id": event_id},
    }


def _batch(
    *,
    tx: str,
    command_id: str,
    expected_stream_revisions: dict[str, int],
    read_stream_revisions: dict[str, int] | None = None,
    events: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "transaction_id": tx,
        "command_id": command_id,
        "expected_stream_revisions": expected_stream_revisions,
        "read_stream_revisions": read_stream_revisions or {},
        "pinned_revisions": {},
        "events": events,
        "idempotency_record": {
            "principal_ref": "principal:test",
            "idempotency_key": f"idempotency:{command_id}",
            "payload_digest": f"digest:{command_id}",
        },
        "outbox_entries": [],
        "result_digest": f"result:{command_id}",
        "projection_refresh_hints": [],
    }


def _fragment(
    *,
    fragment_id: str,
    owner_principal_ref: str,
    source_rule_ref: str,
    expected_revisions: dict[str, int],
    read_set_revisions: dict[str, int] | None = None,
    pinned_revisions: dict[str, int] | None = None,
    event_specs: dict[str, tuple[tuple[str, dict[str, object]], ...]],
    event_visibility_policies: dict[str, tuple[str, ...]] | None = None,
) -> OwnerAuthorizedFragment:
    payload: dict[str, object] = {
        "fragment_id": fragment_id,
        "owner_principal_ref": owner_principal_ref,
        "source_rule_ref": source_rule_ref,
        "expected_revisions": expected_revisions,
        "read_set_revisions": read_set_revisions or {},
        "pinned_revisions": pinned_revisions or {},
        "event_specs": event_specs,
        "event_visibility_policies": event_visibility_policies or {},
    }
    try:
        return OwnerAuthorizedFragment.model_validate(payload)
    except ValidationError as exc:
        pytest.fail(f"owner fragment should accept P5 read/visibility metadata: {exc}")


def test_command_envelope_maps_distinct_read_and_write_vectors_into_batch() -> None:
    try:
        command = GameplayCommandEnvelope.model_validate(
            {
                "command_id": "command:p5:read-write",
                "command_type": "gameplay.contract.reserve",
                "command_version": 1,
                "principal_ref": "principal:player",
                "actor_ref": "actor:player",
                "project_ref": "project:p5",
                "transaction_id": "tx:p5:read-write",
                "idempotency_key": "idempotency:p5:read-write",
                "expected_revisions": {"stream:session": 0},
                "read_set_revisions": {"stream:policy": 4, "stream:world": 9},
                "causation_id": "cause:p5:read-write",
                "correlation_id": "corr:p5:read-write",
                "source_ref": "source:godot",
                "submitted_at": "2026-08-11T00:00:00Z",
                "pinned_revisions": {"schema": 2},
                "payload": {
                    "stream_ref": "stream:session",
                    "event_type": "gameplay.contract_reserved",
                    "visibility_policy": "authority_only",
                },
            }
        )
    except ValidationError as exc:
        pytest.fail(f"command envelope should accept read_set_revisions: {exc}")

    batch = SettlementPlan.from_command_envelope(command).to_atomic_event_batch()

    assert batch.expected_stream_revisions == {"stream:session": 0}
    assert getattr(batch, "read_stream_revisions", None) == {"stream:policy": 4, "stream:world": 9}
    assert batch.pinned_revisions == {"schema": 2}


def test_fragment_batches_preserve_read_vectors_visibility_defaults_and_digest_inputs() -> None:
    organization = _fragment(
        fragment_id="fragment:organization:buyer",
        owner_principal_ref="actor_gameplay.organization_domain",
        source_rule_ref="rule:organization",
        expected_revisions={"gameplay:organization:bakery-a": 2},
        read_set_revisions={"policy:commerce": 7},
        pinned_revisions={"schema": 3},
        event_specs={
            "gameplay:organization:bakery-a": (
                ("gameplay.organization.commitment_accepted", {"commitment_ref": "commitment:1"}),
            )
        },
        event_visibility_policies={"gameplay:organization:bakery-a": ("authority_only",)},
    )
    inventory = _fragment(
        fragment_id="fragment:inventory:seller",
        owner_principal_ref="actor_gameplay.inventory_domain",
        source_rule_ref="rule:inventory",
        expected_revisions={"gameplay:inventory:supplier": 5},
        read_set_revisions={"world:market": 11},
        pinned_revisions={"schema": 3},
        event_specs={
            "gameplay:inventory:supplier": (
                ("gameplay.inventory.custody_reserved", {"commitment_ref": "commitment:1"}),
            )
        },
    )

    batch = build_multi_stream_atomic_event_batch_from_fragments(
        command_id="command:p5:fragments",
        idempotency_principal_ref="actor_gameplay.commerce_authority",
        idempotency_key="idempotency:p5:fragments",
        causation_id="cause:p5:fragments",
        correlation_id="corr:p5:fragments",
        fragments=(inventory, organization),
    )
    batch_same_inputs = build_multi_stream_atomic_event_batch_from_fragments(
        command_id="command:p5:fragments",
        idempotency_principal_ref="actor_gameplay.commerce_authority",
        idempotency_key="idempotency:p5:fragments",
        causation_id="cause:p5:fragments",
        correlation_id="corr:p5:fragments",
        fragments=(organization, inventory),
    )
    batch_changed_visibility = build_multi_stream_atomic_event_batch_from_fragments(
        command_id="command:p5:fragments",
        idempotency_principal_ref="actor_gameplay.commerce_authority",
        idempotency_key="idempotency:p5:fragments",
        causation_id="cause:p5:fragments",
        correlation_id="corr:p5:fragments",
        fragments=(
            inventory,
            _fragment(
                fragment_id="fragment:organization:buyer",
                owner_principal_ref="actor_gameplay.organization_domain",
                source_rule_ref="rule:organization",
                expected_revisions={"gameplay:organization:bakery-a": 2},
                read_set_revisions={"policy:commerce": 7},
                pinned_revisions={"schema": 3},
                event_specs={
                    "gameplay:organization:bakery-a": (
                        ("gameplay.organization.commitment_accepted", {"commitment_ref": "commitment:1"}),
                    )
                },
                event_visibility_policies={"gameplay:organization:bakery-a": ("project",)},
            ),
        ),
    )

    assert getattr(batch, "read_stream_revisions", None) == {"policy:commerce": 7, "world:market": 11}
    assert {event.stream_id: event.visibility_policy for event in batch.events} == {
        "gameplay:inventory:supplier": "project",
        "gameplay:organization:bakery-a": "authority_only",
    }
    assert batch.result_digest == batch_same_inputs.result_digest
    assert batch.result_digest != batch_changed_visibility.result_digest


def test_event_store_validates_read_heads_without_advancing_read_only_streams() -> None:
    store = GameplayEventStore()

    seed_policy = store.append_batch(
        _batch(
            tx="tx:p5:seed-policy",
            command_id="command:p5:seed-policy",
            expected_stream_revisions={"stream:policy": 0},
            events=[
                _event(
                    "evt:p5:seed-policy",
                    stream_id="stream:policy",
                    tx="tx:p5:seed-policy",
                    command_id="command:p5:seed-policy",
                )
            ],
        )
    )
    assert seed_policy.committed is True

    commit = store.append_batch(
        _batch(
            tx="tx:p5:write-session",
            command_id="command:p5:write-session",
            expected_stream_revisions={"stream:session": 0},
            read_stream_revisions={"stream:policy": 1},
            events=[
                _event(
                    "evt:p5:write-session",
                    stream_id="stream:session",
                    tx="tx:p5:write-session",
                    command_id="command:p5:write-session",
                )
            ],
        )
    )

    assert commit.committed is True
    assert commit.resulting_stream_revisions == {"stream:session": 1}
    assert store.get_stream_head("stream:policy") == 1

    stale = store.append_batch(
        _batch(
            tx="tx:p5:stale-read",
            command_id="command:p5:stale-read",
            expected_stream_revisions={"stream:session:second": 0},
            read_stream_revisions={"stream:policy": 0},
            events=[
                _event(
                    "evt:p5:stale-read",
                    stream_id="stream:session:second",
                    tx="tx:p5:stale-read",
                    command_id="command:p5:stale-read",
                )
            ],
        )
    )

    assert stale.committed is False
    assert stale.failure is not None
    assert stale.failure.error_code == "revision_conflict"
    assert stale.failure.stream_id == "stream:policy"
    assert store.get_stream_head("stream:policy") == 1
    assert store.get_stream_head("stream:session:second") == 0


def test_single_stream_builder_digest_changes_when_read_or_pin_inputs_change() -> None:
    baseline = build_atomic_event_batch(
        command_id="command:p5:single-digest",
        principal_ref="principal:test",
        stream_id="stream:single",
        expected_revision=3,
        event_specs=(("gameplay.contract.updated", {"value": 1}),),
        idempotency_key="idempotency:p5:single-digest",
        causation_id="cause:p5:single-digest",
        correlation_id="corr:p5:single-digest",
        read_stream_revisions={"stream:policy": 5},
        pinned_revisions={"schema": 2},
    )
    changed_read = build_atomic_event_batch(
        command_id="command:p5:single-digest",
        principal_ref="principal:test",
        stream_id="stream:single",
        expected_revision=3,
        event_specs=(("gameplay.contract.updated", {"value": 1}),),
        idempotency_key="idempotency:p5:single-digest",
        causation_id="cause:p5:single-digest",
        correlation_id="corr:p5:single-digest",
        read_stream_revisions={"stream:policy": 6},
        pinned_revisions={"schema": 2},
    )
    changed_pin = build_atomic_event_batch(
        command_id="command:p5:single-digest",
        principal_ref="principal:test",
        stream_id="stream:single",
        expected_revision=3,
        event_specs=(("gameplay.contract.updated", {"value": 1}),),
        idempotency_key="idempotency:p5:single-digest",
        causation_id="cause:p5:single-digest",
        correlation_id="corr:p5:single-digest",
        read_stream_revisions={"stream:policy": 5},
        pinned_revisions={"schema": 9},
    )

    assert baseline.idempotency_record.payload_digest != changed_read.idempotency_record.payload_digest
    assert baseline.result_digest != changed_read.result_digest
    assert baseline.idempotency_record.payload_digest != changed_pin.idempotency_record.payload_digest
    assert baseline.result_digest != changed_pin.result_digest


def test_multi_stream_builder_digest_changes_when_visibility_read_or_pin_inputs_change() -> None:
    expected_revisions = {"stream:a": 1, "stream:b": 4}
    event_specs = {
        "stream:a": (("gameplay.contract.updated", {"value": "a"}),),
        "stream:b": (("gameplay.contract.updated", {"value": "b"}),),
    }
    baseline = build_multi_stream_atomic_event_batch(
        command_id="command:p5:multi-digest",
        principal_ref="principal:test",
        expected_revisions=expected_revisions,
        event_specs=event_specs,
        idempotency_key="idempotency:p5:multi-digest",
        causation_id="cause:p5:multi-digest",
        correlation_id="corr:p5:multi-digest",
        read_stream_revisions={"stream:policy": 5},
        event_visibility_policies={"stream:a": ("authority_only",)},
        pinned_revisions={"schema": 2},
    )
    changed_visibility = build_multi_stream_atomic_event_batch(
        command_id="command:p5:multi-digest",
        principal_ref="principal:test",
        expected_revisions=expected_revisions,
        event_specs=event_specs,
        idempotency_key="idempotency:p5:multi-digest",
        causation_id="cause:p5:multi-digest",
        correlation_id="corr:p5:multi-digest",
        read_stream_revisions={"stream:policy": 5},
        event_visibility_policies={"stream:a": ("project",)},
        pinned_revisions={"schema": 2},
    )
    changed_read = build_multi_stream_atomic_event_batch(
        command_id="command:p5:multi-digest",
        principal_ref="principal:test",
        expected_revisions=expected_revisions,
        event_specs=event_specs,
        idempotency_key="idempotency:p5:multi-digest",
        causation_id="cause:p5:multi-digest",
        correlation_id="corr:p5:multi-digest",
        read_stream_revisions={"stream:policy": 8},
        event_visibility_policies={"stream:a": ("authority_only",)},
        pinned_revisions={"schema": 2},
    )
    changed_pin = build_multi_stream_atomic_event_batch(
        command_id="command:p5:multi-digest",
        principal_ref="principal:test",
        expected_revisions=expected_revisions,
        event_specs=event_specs,
        idempotency_key="idempotency:p5:multi-digest",
        causation_id="cause:p5:multi-digest",
        correlation_id="corr:p5:multi-digest",
        read_stream_revisions={"stream:policy": 5},
        event_visibility_policies={"stream:a": ("authority_only",)},
        pinned_revisions={"schema": 6},
    )

    assert baseline.idempotency_record.payload_digest != changed_visibility.idempotency_record.payload_digest
    assert baseline.result_digest != changed_visibility.result_digest
    assert baseline.idempotency_record.payload_digest != changed_read.idempotency_record.payload_digest
    assert baseline.result_digest != changed_read.result_digest
    assert baseline.idempotency_record.payload_digest != changed_pin.idempotency_record.payload_digest
    assert baseline.result_digest != changed_pin.result_digest
