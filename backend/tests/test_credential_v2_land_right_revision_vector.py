from __future__ import annotations

from copy import deepcopy
import json

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import GameplayEvent, IdempotencyRecord
from app.gameplay.credential_runtime import CredentialAuthorityService
from app.gameplay.credential_v2_event_schema import credential_link_stream_id
from app.gameplay.land_right_runtime import LandRightTransferAuthority, LandRightTransferPolicy
from g3_credential_fixture import command, setup_reference


def _holder_stream_id(item_ref: str) -> str:
    return credential_link_stream_id(item_ref).removesuffix(":link") + ":holder"


def _transfer(store, registry, credential_id: str, *, command_id: str):
    authority = LandRightTransferAuthority(
        store=store,
        inventory_registry=registry,
        policies=(LandRightTransferPolicy(
            asset_ref="land:g3",
            credential_presence_container_ids=("container:g3:bag",),
        ),),
    )
    return authority.transfer(
        command_id=command_id,
        asset_ref="land:g3",
        right_id="right:g3",
        from_holder_ref="actor:g3",
        to_holder_ref="actor:g4",
        credential_id=credential_id,
        expected_ownership_revision=store.get_stream_head("gameplay:ownership"),
        idempotency_key=f"key:{command_id}",
        causation_id="cause:g3",
        correlation_id="corr:g3",
    )


def _append_v2_fixture(store: GameplayEventStore):
    """Append a deterministic mixed-ledger row for isolating land-right CAS behavior."""
    credential_id = "credential:g3:2"
    item_ref = "item:g3:2"
    link_stream = credential_link_stream_id(credential_id)
    holder_stream = _holder_stream_id(item_ref)
    transaction_id = "tx:g3:synthetic-v2-credential"
    command_id = "cmd:g3:synthetic-v2-credential"
    shared = {
        "schema_version": 2,
        "stream_revision": 0,
        "global_sequence": 0,
        "transaction_id": transaction_id,
        "command_id": command_id,
        "causation_id": command_id,
        "correlation_id": "corr:g3",
        "visibility_policy": "authority_only",
    }
    events = [
        GameplayEvent(
            **shared,
            event_id="evt:g3:synthetic-v2-link",
            event_type="gameplay.credential.link_issued",
            stream_id=link_stream,
            payload={
                "credential_id": credential_id,
                "credential_item_ref": item_ref,
                "issued_holder_ref": "actor:g3",
                "issued_holder_inventory_revision": 5,
                "right_id": "right:g3",
                "credential_kind": "deed",
                "proves": "evidence_only",
                "issuer_ref": "authority:g3",
                "from_state": "absent",
                "to_state": "issued",
                "condition_ref": "credential_legacy_rule",
                "condition_revision": 1,
            },
        ),
        GameplayEvent(
            **shared,
            event_id="evt:g3:synthetic-v2-holder",
            event_type="gameplay.credential.item_claimed",
            stream_id=holder_stream,
            payload={
                "credential_id": credential_id,
                "item_ref": item_ref,
                "from_state": "absent",
                "to_state": "occupied",
                "condition_ref": "credential_legacy_rule",
                "condition_revision": 1,
            },
        ),
    ]
    result = store.append_batch({
        "transaction_id": transaction_id,
        "command_id": command_id,
        "expected_stream_revisions": {link_stream: 0, holder_stream: 0},
        "events": events,
        "idempotency_record": {
            "principal_ref": "test:g3:credential-v2-fixture",
            "idempotency_key": "key:g3:synthetic-v2-credential",
            "payload_digest": "digest:g3:synthetic-v2-credential",
        },
        "result_digest": "result:g3:synthetic-v2-credential",
    })
    assert result.committed, result.failure
    return link_stream, holder_stream


def test_fenced_v1_read_pin_does_not_reject_land_right_transfer():
    store, registry, chain = setup_reference()
    assert chain.execute("issue_credential", **command("issue_credential")).committed
    CredentialAuthorityService(store=store, inventory_registry=registry).activate_authority_fence()

    assert _transfer(store, registry, "credential:g3:1", command_id="cmd:g3:fenced-v1-read").committed


@pytest.mark.parametrize("stale_stream", ["v1", "v2-link", "v2-holder"])
def test_mixed_ledger_stale_credential_revision_is_rejected(stale_stream: str, monkeypatch: pytest.MonkeyPatch):
    store, registry, chain = setup_reference()
    assert chain.execute("issue_credential", **command("issue_credential")).committed
    link_stream, holder_stream = _append_v2_fixture(store)
    append = store.append_batch

    def stale_append(batch, **kwargs):
        if stale_stream == "v1":
            batch["expected_stream_revisions"]["gameplay:credentials"] -= 1
        elif stale_stream == "v2-link":
            batch["read_stream_revisions"][link_stream] -= 1
        else:
            batch["read_stream_revisions"][holder_stream] -= 1
        return append(batch, **kwargs)

    monkeypatch.setattr(store, "append_batch", stale_append)
    before = store.read_events()
    result = _transfer(store, registry, "credential:g3:2", command_id=f"cmd:g3:stale-{stale_stream}")
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "revision_conflict"
    assert store.read_events() == before


def test_v1_only_land_right_batch_matches_the_pre_migration_payload(monkeypatch: pytest.MonkeyPatch):
    store, registry, chain = setup_reference()
    assert chain.execute("issue_credential", **command("issue_credential")).committed
    append = store.append_batch
    captured = {}

    def capture(batch, **kwargs):
        captured.update(deepcopy(batch))
        return append(batch, **kwargs)

    monkeypatch.setattr(store, "append_batch", capture)
    result = _transfer(store, registry, "credential:g3:1", command_id="cmd:g3:v1-batch-bytes")
    assert result.committed
    expected_stream_revisions = {
        "gameplay:ownership": 1,
        "gameplay:credentials": 1,
        "gameplay:inventory:actor:g3": 5,
    }
    pinned_revisions = {
        "ownership": 1,
        "credentials": 1,
        "inventory": 5,
    }
    assert captured["expected_stream_revisions"] == expected_stream_revisions
    assert captured["pinned_revisions"] == pinned_revisions
    assert "read_stream_revisions" not in captured or captured["read_stream_revisions"] == {}
    events = [{
        "event_id": "evt:cmd:g3:v1-batch-bytes:land-right-transfer",
        "event_type": "gameplay.ownership.right_transferred",
        "schema_version": 1,
        "stream_id": "gameplay:ownership",
        "stream_revision": 0,
        "global_sequence": 0,
        "transaction_id": "tx:cmd:g3:v1-batch-bytes",
        "command_id": "cmd:g3:v1-batch-bytes",
        "causation_id": "cause:g3",
        "correlation_id": "corr:g3",
        "visibility_policy": "authority_only",
        "payload": {
            "right_id": "right:g3",
            "asset_ref": "land:g3",
            "from_holder_ref": "actor:g3",
            "to_holder_ref": "actor:g4",
            "credential_id": "credential:g3:1",
            "policy_ref": "land_right_policy:land:g3",
        },
    }]
    assert json.dumps({
        "expected_stream_revisions": captured["expected_stream_revisions"],
        "pinned_revisions": captured["pinned_revisions"],
        "events": captured["events"],
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8") == json.dumps({
        "expected_stream_revisions": expected_stream_revisions,
        "pinned_revisions": pinned_revisions,
        "events": events,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def test_land_right_commits_against_the_complete_v2_credential_read_vector():
    store, registry, _ = setup_reference()
    link_stream, holder_stream = _append_v2_fixture(store)
    result = _transfer(store, registry, "credential:g3:2", command_id="cmd:g3:land-right-vector")
    assert result.committed
    batch = store.get_transaction(result.transaction_id)
    assert batch is not None
    assert batch.read_stream_revisions == {link_stream: 1, holder_stream: 1}
    assert batch.pinned_revisions[link_stream] == 1
    assert batch.pinned_revisions[holder_stream] == 1
