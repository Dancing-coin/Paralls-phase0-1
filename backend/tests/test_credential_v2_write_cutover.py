from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from app.gameplay.credential_runtime import (
    CredentialAuthorityService,
    CredentialProjector,
    CredentialRuntimeError,
)
from app.gameplay.credential_v2_event_schema import credential_link_stream_id
from g3_credential_fixture import command, setup_reference


def _issue_args(credential_id: str, item_ref: str, *, suffix: str) -> dict[str, str]:
    return {
        "command_id": f"cmd:v2:{suffix}",
        "credential_id": credential_id,
        "credential_item_ref": item_ref,
        "credential_holder_ref": "actor:g3",
        "right_id": "right:g3",
        "credential_kind": "deed",
        "proves": "evidence_only",
        "issuer_ref": "authority:g3",
        "idempotency_key": f"key:v2:{suffix}",
        "causation_id": "cause:g3",
        "correlation_id": "corr:g3",
    }


def _new_v2_service(store, registry):
    service = CredentialAuthorityService(store=store, inventory_registry=registry)
    service.activate_v2_authority()
    return service


def test_v2_issue_supersede_revoke_are_atomic_across_link_and_holder_streams():
    store, registry, _ = setup_reference()
    service = _new_v2_service(store, registry)

    issued = service.issue_credential(**command("issue_credential"))
    assert issued.committed
    issued_batch = store.get_transaction(issued.transaction_id)
    assert [event.event_type for event in issued_batch.events] == [
        "gameplay.credential.link_issued",
        "gameplay.credential.item_claimed",
    ]
    assert {event.stream_id for event in issued_batch.events} == {
        credential_link_stream_id("credential:g3:1"),
        credential_link_stream_id("item:g3:1").replace(":link", ":holder"),
    }
    assert all(event.schema_version == 2 for event in issued_batch.events)
    replay = service.issue_credential(**command("issue_credential"))
    assert replay == issued.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)

    replaced = service.supersede_credential(**command("supersede_credential"))
    assert replaced.committed
    replaced_batch = store.get_transaction(replaced.transaction_id)
    assert [event.event_type for event in replaced_batch.events] == [
        "gameplay.credential.link_superseded",
        "gameplay.credential.link_issued",
        "gameplay.credential.item_released",
        "gameplay.credential.item_claimed",
    ]
    links = CredentialProjector().rebuild(store.read_events()).links
    assert links["credential:g3:1"].status == "superseded"
    assert links["credential:g3:2"].status == "active"

    revoked = service.revoke_credential(**command("revoke_credential"))
    assert revoked.committed
    revoked_batch = store.get_transaction(revoked.transaction_id)
    assert [event.event_type for event in revoked_batch.events] == [
        "gameplay.credential.link_revoked",
        "gameplay.credential.item_released",
    ]
    assert CredentialProjector().rebuild(store.read_events()).links["credential:g3:2"].status == "revoked"


def test_v2_cutover_rejects_new_v1_writes_from_an_old_service():
    store, registry, _ = setup_reference()
    old_service = CredentialAuthorityService(store=store, inventory_registry=registry)
    new_service = CredentialAuthorityService(store=store, inventory_registry=registry)
    new_service.activate_v2_authority()

    with pytest.raises(CredentialRuntimeError, match="^credential_authority_fence_mismatch$"):
        old_service.issue_credential(**_issue_args(
            "credential:g3:old-writer", "item:g3:1", suffix="old-writer"
        ))
    assert store.read_stream("gameplay:credentials") == []


def test_v2_holder_stream_cas_rejects_concurrent_issue_for_the_same_item():
    store, registry, _ = setup_reference()
    first_service = _new_v2_service(store, registry)
    second_service = _new_v2_service(store, registry)
    append = store.append_batch
    barrier = Barrier(2)

    def synchronized_append(batch, **kwargs):
        barrier.wait(timeout=5)
        return append(batch, **kwargs)

    store.append_batch = synchronized_append

    def issue(service, credential_id, command_id):
        return service.issue_credential(**_issue_args(credential_id, "item:g3:1", suffix=command_id))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda values: issue(*values),
            [
                (first_service, "credential:g3:parallel-a", "parallel-a"),
                (second_service, "credential:g3:parallel-b", "parallel-b"),
            ],
        ))
    assert sum(result.committed for result in results) == 1
    rejected = next(result for result in results if not result.committed)
    assert rejected.failure is not None
    assert rejected.failure.error_code == "revision_conflict"
    links = CredentialProjector().rebuild(store.read_events()).links
    assert sum(link.status == "active" and link.credential_item_ref == "item:g3:1" for link in links.values()) == 1


@pytest.mark.parametrize("kind", ["issue_credential", "supersede_credential", "revoke_credential"])
def test_v1_receipt_replays_after_v2_cutover(kind):
    store, registry, _ = setup_reference()
    service = CredentialAuthorityService(store=store, inventory_registry=registry)
    if kind != "issue_credential":
        assert service.issue_credential(**command("issue_credential")).committed
    if kind == "revoke_credential":
        assert service.supersede_credential(**command("supersede_credential")).committed
    args = command(kind)
    receipt = getattr(service, kind)(**args)
    assert receipt.committed
    service.activate_v2_authority()
    before = store.read_events()
    retry = getattr(service, kind)(**args)
    assert retry == receipt.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
    assert store.read_events() == before


def test_v1_idempotency_key_reuse_still_rejected_after_v2_cutover():
    store, registry, _ = setup_reference()
    service = CredentialAuthorityService(store=store, inventory_registry=registry)
    args = command("issue_credential")
    assert service.issue_credential(**args).committed
    service.activate_v2_authority()
    before = store.read_events()
    with pytest.raises(CredentialRuntimeError, match="^idempotency_key_reused$"):
        service.issue_credential(**(args | {"issuer_ref": "authority:other"}))
    assert store.read_events() == before


def test_holder_cas_rejects_issue_when_other_issue_commits_after_projection():
    from threading import Event, Thread

    store, registry, _ = setup_reference()
    first = _new_v2_service(store, registry)
    second = _new_v2_service(store, registry)
    paused, resume = Event(), Event()
    read_events = store.read_events
    def pause_after_snapshot():
        events = read_events()
        if not paused.is_set():
            paused.set()
            assert resume.wait(10)
        return events
    store.read_events = pause_after_snapshot
    results = []
    def delayed_issue():
        results.append(first.issue_credential(**_issue_args("credential:g3:race-a", "item:g3:1", suffix="race-a")))
    thread = Thread(target=delayed_issue)
    thread.start()
    assert paused.wait(10)
    try:
        winner = second.issue_credential(**_issue_args("credential:g3:race-b", "item:g3:1", suffix="race-b"))
    finally:
        resume.set()
        thread.join(10)
    assert not thread.is_alive()
    assert winner.committed
    assert len(results) == 1 and not results[0].committed
    assert results[0].failure.error_code == "revision_conflict"
    links = CredentialProjector().rebuild(read_events()).links
    assert sum(link.status == "active" and link.credential_item_ref == "item:g3:1" for link in links.values()) == 1
