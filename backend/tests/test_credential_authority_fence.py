from __future__ import annotations

from app.gameplay.credential_runtime import CredentialAuthorityService
from app.gameplay.models import IdempotencyRecord
from g3_credential_fixture import command, setup_reference


def test_credential_service_registers_g2_fence_and_only_fenced_context_can_write_v1():
    store, registry, _ = setup_reference()
    service = CredentialAuthorityService(store=store, inventory_registry=registry)

    assert store.get_authority_stream("gameplay:credentials") is None
    service.activate_authority_fence()
    assert store.get_authority_stream("gameplay:credentials") == {
        "stream_id": "gameplay:credentials",
        "scope_ref": "scope:credential-domain",
        "epoch": 1,
        "writer_ref": "actor_gameplay.credential_domain",
    }
    receipt = service.issue_credential(**command("issue_credential"))
    assert receipt.committed
    original = store.get_transaction(receipt.transaction_id)
    assert original is not None

    legacy_transaction = "tx:legacy-writer:credential"
    legacy_command = "cmd:legacy-writer:credential"
    legacy = original.model_copy(update={
        "transaction_id": legacy_transaction,
        "command_id": legacy_command,
        "events": [event.model_copy(update={
            "event_id": "evt:legacy-writer:credential:1",
            "transaction_id": legacy_transaction,
            "command_id": legacy_command,
        }) for event in original.events],
        "idempotency_record": IdempotencyRecord(
            principal_ref="actor_gameplay.credential_domain",
            idempotency_key="legacy-writer:credential",
            payload_digest="legacy-writer:credential:digest",
        ),
    })
    before = store.export_snapshot()
    rejected = store.append_batch(legacy)
    assert not rejected.committed
    assert rejected.failure is not None
    assert rejected.failure.error_code == "authority_context_invalid"
    assert store.export_snapshot() == before
