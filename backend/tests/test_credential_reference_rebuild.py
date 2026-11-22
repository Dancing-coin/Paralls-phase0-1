"""R3 witness: discard a genuinely stored checkpoint and replay real truth."""
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from app.gameplay import credential_reference_chain, credential_runtime
from app.gameplay.credential_runtime import CredentialProjector
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.ownership_runtime import OwnershipAuthorityService
from app.gameplay.replay import GameplayProjectionReplay
from g3_credential_fixture import PACK, command, lifecycle, setup_reference


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()


def complete_state(store):
    projection = CredentialProjector().rebuild(store.read_events())
    return {"links": {key: asdict(link) for key, link in projection.links.items()},
        "source_revision_vector": dict(projection.source_revision_vector)}


def checkpoint_removal_witness():
    store, _, chain = setup_reference()
    receipts = lifecycle(chain)
    assert all(receipt.committed for receipt in receipts)
    events = store.read_events()
    before = complete_state(store)
    assert len(before["links"]) == 2
    assert before["source_revision_vector"] == {"gameplay:credentials": 4}
    assert {link["status"] for link in before["links"].values()} == {"superseded", "revoked"}
    assert all(link["issued_holder_ref"] == "actor:g3" and
        link["issued_holder_inventory_revision"] == 5 and link["source_event_id"]
        for link in before["links"].values())
    replay = GameplayProjectionReplay(projector_id="g3:credential-reference", projector_version="1")
    checkpoint = replay.create_checkpoint(events)
    store.save_projection_checkpoint(checkpoint)
    assert store.get_projection_checkpoint(checkpoint.checkpoint_id) == checkpoint
    snapshot = store.export_snapshot()
    assert len(snapshot["projection_checkpoints"]) == 1
    without_cache = deepcopy(snapshot)
    without_cache["projection_checkpoints"] = []
    assert [key for key in snapshot if snapshot[key] != without_cache[key]] == ["projection_checkpoints"]
    restored = GameplayEventStore.from_snapshot(without_cache)
    assert restored.list_projection_checkpoints() == []
    assert restored.export_snapshot() == without_cache
    assert restored.read_events() == events
    assert restored.export_snapshot()["transactions"] == snapshot["transactions"]
    after = complete_state(restored)
    assert before == after
    assert digest(before) == digest(after)
    original_event_digest = digest([event.model_dump(mode="json") for event in events])
    rebuilt_event_digest = digest([event.model_dump(mode="json") for event in restored.read_events()])
    assert original_event_digest == rebuilt_event_digest
    reloaded = credential_reference_chain.load_credential_pack(PACK)
    assert reloaded.content_hash == chain.pack.content_hash
    bond_store, _, bond_chain = setup_reference()
    bond_ref = "bond:g3:checkpoint"
    assert OwnershipAuthorityService(store=bond_store).grant_bond(
        command_id="cmd:g3:checkpoint-bond",
        bond_ref=bond_ref,
        subject_ref="actor:g3",
        target_ref="land:g3",
        bond_type="ownership",
        scope="asset:title",
        term_expires_at=30,
        source_event_ref=bond_store.read_events()[0].event_id,
        world_tick=1,
        expected_ownership_revision=bond_store.get_stream_head("gameplay:ownership"),
        idempotency_key=bond_ref,
        causation_id="cause:g3",
        correlation_id="corr:g3",
    ).committed
    bond_chain._owner.activate_v2_authority()
    bond_args = command("issue_credential") | {
        "command_id": "cmd:g3:checkpoint-credential",
        "idempotency_key": "g3:checkpoint-credential",
        "credential_id": "credential:g3:checkpoint",
        "credential_item_ref": "item:g3:2",
        "right_id": None,
        "bond_ref": bond_ref,
        "world_tick": 5,
    }
    assert bond_chain.execute("issue_credential", **bond_args).committed
    bond_before = complete_state(bond_store)
    bond_link = bond_before["links"]["credential:g3:checkpoint"]
    assert bond_link["bond_ref"] == bond_ref and "right_id" not in bond_link
    bond_events = bond_store.read_events()
    bond_replay = GameplayProjectionReplay(
        projector_id="g3:credential-bond-reference", projector_version="1"
    )
    bond_checkpoint = bond_replay.create_checkpoint(bond_events)
    bond_store.save_projection_checkpoint(bond_checkpoint)
    bond_snapshot = bond_store.export_snapshot()
    bond_without_cache = deepcopy(bond_snapshot)
    bond_without_cache["projection_checkpoints"] = []
    restored_bond_store = GameplayEventStore.from_snapshot(bond_without_cache)
    bond_after = complete_state(restored_bond_store)
    assert bond_before == bond_after
    return dict(checkpoint_id=checkpoint.checkpoint_id, checkpoint_count_before=1,
        checkpoint_count_after=len(restored.list_projection_checkpoints()),
        snapshot_changed_keys=["projection_checkpoints"], event_count=len(events),
        credential_event_count=sum(event.event_type in CredentialProjector._EVENT_TYPES for event in events),
        state_before=before, state_after=after, state_digest_before=digest(before), state_digest_after=digest(after),
        source_event_digest_before=original_event_digest, source_event_digest_after=rebuilt_event_digest,
        pack_digest_before=chain.pack.content_hash, pack_digest_after=reloaded.content_hash,
        bond_checkpoint_state_digest_before=digest(bond_before),
        bond_checkpoint_state_digest_after=digest(bond_after),
        model_ref=credential_reference_chain.MODEL,
        model_source_sha256=sha256(Path(credential_reference_chain.__file__).read_bytes()).hexdigest(),
        projector_source_sha256=sha256(Path(credential_runtime.__file__).read_bytes()).hexdigest(),
        checkpoint_kind="real generic GameplayProjectionReplay checkpoint; state_digest uses full CredentialProjector links")


def test_checkpoint_removal_rebuilds_complete_credential_state(tmp_path, record_property):
    evidence = checkpoint_removal_witness()
    (tmp_path / "r3-evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    record_property("g3_r3_evidence", json.dumps(evidence, sort_keys=True))
