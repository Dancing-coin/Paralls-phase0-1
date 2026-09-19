from dataclasses import asdict
import json

import pytest

from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.population_continuity.activation_policy import ActivationPolicy
from app.population_continuity.conflict_activation import PopulationConflictSource
from app.population_continuity.roster import PopulationRoster
from test_character_cognition_admission import service
from test_population_conflict_activation import conflict, fixture


def setup(tmp_path):
    store, owner, packages, profiles = fixture(tmp_path)
    archive, admissions = service(tmp_path / "sessions.sqlite3")
    source = PopulationConflictSource(store=store, world_ref="world:test",
        roster=PopulationRoster(actor_ids=("char_a", "char_b", "char_c", "resident_1")),
        package_registry=packages, profiles=profiles, policy=ActivationPolicy(), admissions=admissions)
    return store, owner, source, archive, admissions


def admit(store, admissions, wake, **extra):
    return admissions.admit(source_event=store.get_event(wake.source_event_id), actor_id=wake.actor_id,
        delivery_id=wake.candidate_key, source_kind=wake.source_kind, payload={},
        source_pins=extra or {"population_wake": json.loads(json.dumps(asdict(wake)))},
        now=100., expires_at=200., producer_ts=1)


def test_source_uses_filtered_global_cursor_and_keeps_unadmitted_actor(tmp_path, monkeypatch):
    store, owner, source, archive, admissions = setup(tmp_path)
    try:
        event_id = conflict(owner)
        reads, read = [], store.read_events
        def checked(**kwargs):
            reads.append(kwargs)
            assert kwargs.get("event_type") == source.EVENT or kwargs.get("limit") == 1
            return read(**kwargs)
        monkeypatch.setattr(store, "read_events", checked)
        first = source.read()
        assert [wake.actor_id for wake in first.wakes] == ["char_a", "char_b"]
        assert {wake.source_event_id for wake in first.wakes} == {event_id}
        assert first.cursor == store.get_last_global_sequence()
        receipt = admit(store, admissions, first.wakes[0])
        assert store.append_batch(build_atomic_event_batch(command_id="command:noise", principal_ref="untrusted",
            stream_id="stream:noise", expected_revision=0, event_specs=[("noise", {})],
            idempotency_key="key:noise", causation_id="cause:noise", correlation_id="corr:noise")).committed
        second = source.read()
        assert [wake.actor_id for wake in second.wakes] == ["char_b"]
        assert admissions.read(receipt.child_key).state == "admitted"
        assert archive.event_count("char_a") == 0
        assert len(store.read_stream("gameplay:social:case:case:conflict@1")) == 1
        assert any(row.get("global_sequence_after") == first.cursor for row in reads)
    finally:
        archive.close()


def test_child_commit_survives_source_checkpoint_failure_and_two_database_reopen(tmp_path, monkeypatch):
    store, owner, source, archive, admissions = setup(tmp_path)
    conflict(owner)
    wakes = source.read().wakes
    receipts = [admit(store, admissions, wake) for wake in wakes]
    def fail(*args):
        raise RuntimeError("checkpoint unavailable")
    monkeypatch.setattr(store, "save_projection_checkpoint", fail)
    with pytest.raises(RuntimeError, match="checkpoint unavailable"):
        source.read()
    archive.close()
    reopened = DurableGameplayEventStore(tmp_path / "gameplay.sqlite3")
    archive, admissions = service(tmp_path / "sessions.sqlite3")
    try:
        source._store, source._admissions = reopened, admissions
        assert source.read().wakes == ()
        assert [admissions.read(row.child_key) for row in receipts] == receipts
        assert reopened.get_projection_checkpoint(source.checkpoint_id).state["source_event_ids"] == []
        assert archive.event_count("char_a") == archive.event_count("char_b") == 0
    finally:
        archive.close()


def test_unmatched_real_child_receipt_cannot_clear_pending_source(tmp_path):
    store, owner, source, archive, admissions = setup(tmp_path)
    try:
        conflict(owner)
        wake = source.read().wakes[0]
        admit(store, admissions, wake, population_wake={"candidate_key": "other"})
        with pytest.raises(ValueError, match="conflict_child_receipt_mismatch"):
            source.read()
    finally:
        archive.close()


@pytest.mark.parametrize("damage", ["hash", "anchor", "vector"])
def test_corrupt_source_checkpoint_fails_closed_without_child_admission(tmp_path, damage):
    from app.population_continuity.store_projection_assembler import _checkpoint_digest
    store, owner, source, archive, admissions = setup(tmp_path)
    try:
        conflict(owner)
        source.read()
        checkpoint = store.get_projection_checkpoint(source.checkpoint_id)
        if damage == "anchor":
            checkpoint.state["anchor"]["digest"] = "sha256:" + "0" * 64
        elif damage == "vector":
            checkpoint.source_revision_vector = {}
        checkpoint.projection_hash = "corrupted" if damage == "hash" else _checkpoint_digest(checkpoint)
        store.save_projection_checkpoint(checkpoint)
        with pytest.raises(ValueError, match="conflict_source_(checkpoint|anchor|vector)_invalid"):
            source.read()
        assert admissions.list_pending() == ()
        assert store.get_last_global_sequence() == 1
    finally:
        archive.close()


def test_current_terminal_case_removes_source_but_package_pause_only_defers(tmp_path):
    store, owner, source, archive, admissions = setup(tmp_path)
    try:
        conflict(owner)
        expected = source.read().wakes
        packages = source._packages
        from app.gameplay.patch_runtime import GameplayPatchRegistry
        source._packages = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
        blocked = source.read()
        assert blocked.wakes == () and len(blocked.diagnostics) == 2
        assert store.get_projection_checkpoint(source.checkpoint_id).state["source_event_ids"]
        source._packages = packages
        assert source.read().wakes == expected
        conflict(owner, "final", 1)
        assert source.read().wakes == ()
        assert store.get_projection_checkpoint(source.checkpoint_id).state["source_event_ids"] == []
    finally:
        archive.close()
