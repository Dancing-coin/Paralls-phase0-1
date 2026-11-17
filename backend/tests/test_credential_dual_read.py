from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json

import pytest

from app.gameplay.credential_runtime import CredentialAuthorityService, CredentialProjector, CredentialRuntimeError
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AtomicEventBatch, GameplayEvent, IdempotencyRecord
from app.gameplay.credential_v2_event_schema import credential_link_stream_id
from app.gameplay.replay import GameplayProjectionReplay
from g3_credential_fixture import command, setup_reference


ISSUED_V2 = "gameplay.credential.link_issued"
REVOKED_V2 = "gameplay.credential.link_revoked"
SUPERSEDED_V2 = "gameplay.credential.link_superseded"


def _state(store: GameplayEventStore) -> dict[str, object]:
    projection = CredentialProjector().rebuild(store.read_events())
    return {
        "links": {key: asdict(link) for key, link in projection.links.items()},
        "source_revision_vector": dict(projection.source_revision_vector),
    }


def _append_v2(store: GameplayEventStore, *, name: str, event_type: str, payload: dict[str, object]) -> GameplayEvent:
    credential_id = payload["credential_id"]
    stream_id = credential_link_stream_id(credential_id)
    tx = f"tx:v2:{name}"
    command_id = f"cmd:v2:{name}"
    event = GameplayEvent(
        event_id=f"evt:v2:{name}", event_type=event_type, schema_version=2,
        stream_id=stream_id, stream_revision=0, global_sequence=0,
        transaction_id=tx, command_id=command_id, causation_id=command_id,
        correlation_id="corr:g3:v2", visibility_policy="authority_only", payload=payload,
    )
    result = store.append_batch(AtomicEventBatch(
        transaction_id=tx, command_id=command_id,
        expected_stream_revisions={stream_id: store.get_stream_head(stream_id)},
        events=[event], idempotency_record=IdempotencyRecord(
            principal_ref="actor_gameplay.credential_domain", idempotency_key=f"key:v2:{name}",
            payload_digest=f"digest:v2:{name}",
        ), result_digest=f"result:v2:{name}",
    ))
    assert result.committed, result.failure
    return store.get_event(result.committed_event_ids[0])


def _issued_payload(credential_id: str, item_ref: str) -> dict[str, object]:
    return {
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
        "condition_ref": "credential_issue_rule",
        "condition_revision": 1,
    }


def _revoked_payload(credential_id: str) -> dict[str, object]:
    return {
        "credential_id": credential_id,
        "issuer_ref": "authority:g3",
        "reason": "lost",
        "from_state": "issued",
        "to_state": "revoked",
        "condition_ref": "credential_revoke_rule",
        "condition_revision": 1,
    }


def test_v1_only_projection_bytes_match_the_pre_dual_read_baseline():
    store, _, chain = setup_reference()
    for kind in ("issue_credential", "supersede_credential", "revoke_credential"):
        chain.execute(kind, **command(kind))
    canonical = json.dumps(_state(store), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    assert sha256(canonical).hexdigest() == "592fc4930b29514e43a6b93b2deca3b79cbf7e2f295a10034856f6144dac5031"
    assert canonical.decode() == (
        '{"links":{"credential:g3:1":{"credential_id":"credential:g3:1","credential_item_ref":"item:g3:1",'
        '"credential_kind":"deed","issued_holder_inventory_revision":5,"issued_holder_ref":"actor:g3",'
        '"issuer_ref":"authority:g3","proves":"evidence_only","right_id":"right:g3",'
        '"source_event_id":"evt:cmd:g3:supersede_credential:credential:1","status":"superseded"},'
        '"credential:g3:2":{"credential_id":"credential:g3:2","credential_item_ref":"item:g3:2",'
        '"credential_kind":"deed","issued_holder_inventory_revision":5,"issued_holder_ref":"actor:g3",'
        '"issuer_ref":"authority:g3","proves":"evidence_only","right_id":"right:g3",'
        '"source_event_id":"evt:cmd:g3:revoke_credential:credential:1","status":"revoked"}},'
        '"source_revision_vector":{"gameplay:credentials":4}}'
    )


def test_v2_only_ledger_projects_an_instance_scoped_issued_link():
    store = GameplayEventStore()
    _append_v2(store, name="issued-only", event_type=ISSUED_V2,
        payload=_issued_payload("credential:g3:1", "item:g3:1"))
    projection = CredentialProjector().rebuild(store.read_events())
    assert projection.links["credential:g3:1"].status == "active"
    assert projection.links["credential:g3:1"].source_event_id == "evt:v2:issued-only"
    assert dict(projection.source_revision_vector) == {credential_link_stream_id("credential:g3:1"): 1}


def test_v1_issued_then_v2_revoked_projects_in_global_order():
    store, _, chain = setup_reference()
    receipt = chain.execute("issue_credential", **command("issue_credential"))
    v2 = _append_v2(store, name="revoke-v1", event_type=REVOKED_V2,
        payload=_revoked_payload("credential:g3:1"))
    events = store.read_events()
    reversed_events = list(reversed(events))
    projection = CredentialProjector().rebuild(reversed_events)
    assert v2.global_sequence > store.get_event(receipt.committed_event_ids[0]).global_sequence
    assert projection.links["credential:g3:1"].status == "revoked"
    assert projection.links["credential:g3:1"].source_event_id == v2.event_id


def test_v1_issued_then_v2_supersede_and_v2_replacement_keep_two_links():
    store, _, chain = setup_reference()
    chain.execute("issue_credential", **command("issue_credential"))
    _append_v2(store, name="supersede-v1", event_type=SUPERSEDED_V2, payload={
        "credential_id": "credential:g3:1", "replacement_credential_id": "credential:g3:2",
        "issuer_ref": "authority:g3", "from_state": "issued", "to_state": "superseded",
        "condition_ref": "credential_supersede_rule", "condition_revision": 1,
    })
    _append_v2(store, name="replacement-v2", event_type=ISSUED_V2,
        payload=_issued_payload("credential:g3:2", "item:g3:2"))
    links = CredentialProjector().rebuild(store.read_events()).links
    assert links["credential:g3:1"].status == "superseded"
    assert links["credential:g3:2"].status == "active"
    assert links["credential:g3:2"].source_event_id == "evt:v2:replacement-v2"


def test_cross_version_duplicate_credential_id_fails_closed():
    store, _, chain = setup_reference()
    chain.execute("issue_credential", **command("issue_credential"))
    _append_v2(store, name="duplicate-v2", event_type=ISSUED_V2,
        payload=_issued_payload("credential:g3:1", "item:g3:1"))
    with pytest.raises(CredentialRuntimeError, match="^credential_duplicate$"):
        CredentialProjector().rebuild(store.read_events())


def test_mixed_ledger_preserves_r2_receipt_replay_and_r3_checkpoint_rebuild():
    store, registry, chain = setup_reference()
    first = chain.execute("issue_credential", **command("issue_credential"))
    _append_v2(store, name="mixed-revoke", event_type=REVOKED_V2,
        payload=_revoked_payload("credential:g3:1"))
    owner = CredentialAuthorityService(store=store, inventory_registry=registry)
    retry = owner.issue_credential(**command("issue_credential"))
    assert retry == first.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)

    before = _state(store)
    before_digest = sha256(json.dumps(before, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    checkpoint = GameplayProjectionReplay(projector_id="g3:credential-v2-mixed", projector_version="1").create_checkpoint(store.read_events())
    store.save_projection_checkpoint(checkpoint)
    snapshot = deepcopy(store.export_snapshot())
    assert len(snapshot["projection_checkpoints"]) == 1
    snapshot["projection_checkpoints"] = []
    restored = GameplayEventStore.from_snapshot(snapshot)
    after = _state(restored)
    after_digest = sha256(json.dumps(after, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    assert after == before
    assert after_digest == before_digest
