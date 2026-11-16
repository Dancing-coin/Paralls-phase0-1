import pytest

from app.gameplay.credential_runtime import CredentialProjector, CredentialRuntimeError
from app.gameplay.fact_type_registry import ResolverInputError, RestrictedInputs
from g3_credential_fixture import command, lifecycle, setup_reference


def test_reference_lifecycle_uses_real_owner_transactions():
    store, _, chain = setup_reference()
    inventory_revision = store.get_stream_head("gameplay:inventory:actor:g3")
    assert inventory_revision == 5  # container + two instantiate/move pairs
    receipts = lifecycle(chain)
    assert all(receipt.committed for receipt in receipts)
    assert [len(receipt.committed_event_ids) for receipt in receipts] == [1, 2, 1]
    for receipt in receipts:
        batch = store.get_transaction(receipt.transaction_id)
        assert batch.idempotency_record.principal_ref == "actor_gameplay.credential_domain"
        assert [event.event_id for event in batch.events] == receipt.committed_event_ids
        assert all(store.get_event(event.event_id) == event for event in batch.events)
    links = CredentialProjector().rebuild(store.read_events()).links
    assert {key: link.status for key, link in links.items()} == {
        "credential:g3:1": "superseded", "credential:g3:2": "revoked"}
    assert {link.issued_holder_ref for link in links.values()} == {"actor:g3"}
    assert all(link.issued_holder_inventory_revision == inventory_revision for link in links.values())


def test_restricted_frame_is_frozen_has_no_capabilities_and_keeps_captured_revision():
    store, _, chain = setup_reference()
    args = command("issue_credential")
    frame = chain.freeze_inputs("issue_credential", args)
    with pytest.raises(TypeError):
        frame.values["command@1"]["credential_kind"] = "forged"
    args["credential_kind"] = "changed-after-freeze"
    assert chain.evaluate(frame) is None
    old_heads = dict(frame.source_revision_vector)
    chain.execute("issue_credential", **command("issue_credential"))
    assert dict(frame.source_revision_vector) == old_heads
    assert old_heads["gameplay:credentials"] == 0
    assert store.get_stream_head("gameplay:credentials") == 1
    assert chain.evaluate(frame) is None
    with pytest.raises(ResolverInputError, match="^resolver_input_invalid$"):
        RestrictedInputs({"store": store}, ["store"])
    inputs = RestrictedInputs(dict(frame.values) | {"store": store}, list(frame.values))
    with pytest.raises(ResolverInputError, match="^resolver_input_undeclared$"):
        inputs["store"]


def test_qualification_rejection_cannot_write_and_retry_is_owned():
    store, _, chain = setup_reference()
    args = command("issue_credential")
    before = store.read_events()
    with pytest.raises(CredentialRuntimeError, match="^ownership_right_missing$"):
        chain.execute("issue_credential", **(args | {"right_id": "right:missing"}))
    assert store.read_events() == before
    first = chain.execute("issue_credential", **args)
    replay = chain.execute("issue_credential", **args)
    assert replay == first.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
    assert len(store.read_events()) == len(before) + 1


def test_supersede_retains_no_ownership_precondition():
    store, _, chain = setup_reference()
    chain.execute("issue_credential", **command("issue_credential"))
    frame = chain.freeze_inputs("supersede_credential", command("supersede_credential"))
    assert "ownership.rights@1" not in frame.values
    assert "gameplay:ownership" not in frame.source_revision_vector
    assert chain.evaluate(frame) is None
    receipt = chain.execute("supersede_credential", **command("supersede_credential"))
    assert receipt.committed and len(receipt.committed_event_ids) == 2
    assert "gameplay:ownership" not in store.get_transaction(receipt.transaction_id).pinned_revisions
