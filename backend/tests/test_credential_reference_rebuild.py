"""R3 witness: discard a genuinely stored checkpoint and replay real truth."""
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from app.gameplay import credential_reference_chain, credential_runtime
from app.gameplay.credential_runtime import CredentialProjector
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay
from g3_credential_fixture import PACK, lifecycle, setup_reference


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
    return dict(checkpoint_id=checkpoint.checkpoint_id, checkpoint_count_before=1,
        checkpoint_count_after=len(restored.list_projection_checkpoints()),
        snapshot_changed_keys=["projection_checkpoints"], event_count=len(events),
        credential_event_count=sum(event.event_type in CredentialProjector._EVENT_TYPES for event in events),
        state_before=before, state_after=after, state_digest_before=digest(before), state_digest_after=digest(after),
        source_event_digest_before=original_event_digest, source_event_digest_after=rebuilt_event_digest,
        pack_digest_before=chain.pack.content_hash, pack_digest_after=reloaded.content_hash,
        model_ref=credential_reference_chain.MODEL,
        model_source_sha256=sha256(Path(credential_reference_chain.__file__).read_bytes()).hexdigest(),
        projector_source_sha256=sha256(Path(credential_runtime.__file__).read_bytes()).hexdigest(),
        checkpoint_kind="real generic GameplayProjectionReplay checkpoint; state_digest uses full CredentialProjector links")


def test_checkpoint_removal_rebuilds_complete_credential_state(tmp_path, record_property):
    evidence = checkpoint_removal_witness()
    (tmp_path / "r3-evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    record_property("g3_r3_evidence", json.dumps(evidence, sort_keys=True))
