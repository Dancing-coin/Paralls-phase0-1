"""Bounded corruption of real test-owned store data, without replacement APIs."""
import pytest

from app.gameplay.credential_runtime import CredentialAuthorityService, CredentialRuntimeError
from g3_credential_fixture import command, setup_reference

KINDS = ("issue_credential", "revoke_credential", "supersede_credential")


def committed(kind):
    store, registry, chain = setup_reference()
    if kind != "issue_credential":
        chain.execute("issue_credential", **command("issue_credential"))
    if kind == "revoke_credential":
        chain.execute("supersede_credential", **command("supersede_credential"))
    service = CredentialAuthorityService(store=store, inventory_registry=registry)
    invoke = getattr(service, kind)
    args = command(kind)
    receipt = invoke(**args)
    assert receipt.committed
    return store, invoke, args, receipt


def replace_receipt(store, args, receipt, **changes):
    store._idempotency_results[("actor_gameplay.credential_domain", args["idempotency_key"])] = receipt.model_copy(update=changes, deep=True)


def refuses_without_append(store, invoke, args, code):
    before = store.export_snapshot()
    with pytest.raises(CredentialRuntimeError, match=f"^{code}$"):
        invoke(**args)
    assert store.export_snapshot() == before


@pytest.mark.parametrize("kind", KINDS)
def test_replay_event_missing(kind):
    store, invoke, args, receipt = committed(kind)
    del store._events_by_id[receipt.committed_event_ids[-1]]
    refuses_without_append(store, invoke, args, "credential_replay_event_missing")


@pytest.mark.parametrize("damage", ["uncommitted", "receipt_command", "receipt_transaction", "transaction_missing", "transaction_command", "event_changed", "event_order", "sequence", "revisions"])
def test_replay_transaction_mismatch(damage):
    store, invoke, args, receipt = committed("supersede_credential")
    if damage == "uncommitted":
        replace_receipt(store, args, receipt, committed=False)
    elif damage == "receipt_command":
        replace_receipt(store, args, receipt, command_id="cmd:wrong")
    elif damage == "receipt_transaction":
        replace_receipt(store, args, receipt, transaction_id="tx:wrong")
    elif damage == "transaction_missing":
        del store._transaction_results[receipt.transaction_id]
    elif damage == "transaction_command":
        index = next(i for i, batch in enumerate(store._transactions) if batch.transaction_id == receipt.transaction_id)
        store._transactions[index] = store._transactions[index].model_copy(update={"command_id": "cmd:wrong"}, deep=True)
    elif damage == "event_changed":
        event_id = receipt.committed_event_ids[0]
        event = store._events_by_id[event_id]
        store._events_by_id[event_id] = event.model_copy(update={"payload": event.payload | {"issuer_ref": "authority:wrong"}}, deep=True)
    elif damage == "event_order":
        replace_receipt(store, args, receipt, committed_event_ids=list(reversed(receipt.committed_event_ids)))
    elif damage == "sequence":
        replace_receipt(store, args, receipt, global_sequence_range=(1, 2))
    else:
        replace_receipt(store, args, receipt, resulting_stream_revisions={})
    refuses_without_append(store, invoke, args, "credential_replay_transaction_mismatch")


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("damage", ["empty", "extra", "duplicate", "transaction_count"])
def test_replay_event_count_mismatch(kind, damage):
    store, invoke, args, receipt = committed(kind)
    if damage == "transaction_count":
        index = next(i for i, batch in enumerate(store._transactions) if batch.transaction_id == receipt.transaction_id)
        batch = store._transactions[index]
        store._transactions[index] = batch.model_copy(update={"events": batch.events + batch.events[:1]}, deep=True)
    else:
        ids = [] if damage == "empty" else receipt.committed_event_ids + receipt.committed_event_ids[:1]
        if damage == "duplicate" and len(receipt.committed_event_ids) == 2:
            ids = [receipt.committed_event_ids[0]] * 2
        replace_receipt(store, args, receipt, committed_event_ids=ids)
    refuses_without_append(store, invoke, args, "credential_replay_event_count_mismatch")


@pytest.mark.parametrize("kind", KINDS)
def test_normal_retry_returns_original_receipt(kind):
    store, invoke, args, first = committed(kind)
    before = store.export_snapshot()
    replay = invoke(**args)
    assert replay == first.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
    assert store.export_snapshot() == before
