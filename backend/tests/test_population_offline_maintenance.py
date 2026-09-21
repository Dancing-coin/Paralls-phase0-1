from pathlib import Path
import sqlite3

import pytest

from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.siming_audit_writer import SqliteSimingAuditWriter
from app.models.siming_event import SimingAuditRecord
from app.world_runtime.storage_lease import RuntimeStorageLease
from scripts.verification import verify_population_long_session_recovery as recovery
from test_population_durable_cadence_recovery import _publisher, _runtime


def archive(tmp_path):
    graph = tmp_path / "archive.sqlite3"
    with sqlite3.connect(graph) as connection:
        connection.execute("CREATE TABLE proof(value TEXT)")
        connection.execute("INSERT INTO proof VALUES('archive-copy')")
    gameplay = graph.with_name(graph.name + ".gameplay.json")
    world = _runtime(gameplay)
    publisher = _publisher(world, InMemoryAuthorityEventBus())
    for start in range(0, 40 * 60, 60):
        assert publisher(world.build_population_cadence(window_start=start, window_end=start + 60))
    return graph, gameplay, world


def checkpoints(path):
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT * FROM checkpoints ORDER BY id").fetchall()


def test_backup_archive_includes_committed_siming_audit(tmp_path):
    graph, _, _ = archive(tmp_path)
    audit = graph.with_name(graph.name + ".siming-audit.sqlite3")
    writer = SqliteSimingAuditWriter(audit)
    writer.record(SimingAuditRecord(
        audit_id="audit:old", room_id="room:1", correlation_id="correlation:old",
        causation_id="cause:old", source_event_id="event:old",
        status="recorded", reason="accepted",
    ))

    backup = tmp_path / "backup"
    copied = recovery.backup_archive(graph, backup)
    restored = SqliteSimingAuditWriter(backup / audit.name)
    assert audit.name in copied
    assert restored.get_record("audit:old") == writer.get_record("audit:old")
    restored.close()
    writer.close()


def test_offline_rebuild_backs_up_and_preserves_authority_after_both_checkpoints_corrupt(tmp_path):
    graph, gameplay, before = archive(tmp_path)
    expected = before.export_recovery_state()
    authority = recovery.authority_digest(gameplay)
    with sqlite3.connect(gameplay) as connection:
        connection.execute("UPDATE checkpoints SET value='broken' WHERE projector_id='population-recovery:world'")
    output = tmp_path / "rebuild"
    report = recovery.maintain_archive(graph, mode=before.mode, roster=before.roster, output=output, rebuild=True)
    assert report["passed"] and report["rebuilt_checkpoints"] == 42
    assert report["authority_digest_before"] == report["authority_digest_after"] == authority
    with sqlite3.connect(output / "backup" / gameplay.name) as connection:
        assert connection.execute("SELECT COUNT(*) FROM checkpoints WHERE value='broken'").fetchone()[0] == 2
    with sqlite3.connect(output / "backup" / graph.name) as connection:
        assert connection.execute("SELECT value FROM proof").fetchone()[0] == "archive-copy"
    restored = _runtime(gameplay)
    publisher = _publisher(restored, InMemoryAuthorityEventBus())
    assert publisher.replayed_windows == 8
    assert restored.export_recovery_state() == expected


@pytest.mark.parametrize("rebuild", [False, True])
def test_maintenance_refuses_a_live_archive_before_creating_backup(tmp_path, rebuild):
    graph, _, world = archive(tmp_path)
    output = tmp_path / "refused"
    with RuntimeStorageLease(graph), pytest.raises(RuntimeError, match="runtime_storage_in_use"):
        recovery.maintain_archive(graph, mode=world.mode, roster=world.roster, output=output, rebuild=rebuild)
    assert not output.exists()


def test_audit_rejects_archive_requiring_full_checkpoint_rebuild(tmp_path):
    graph, gameplay, world = archive(tmp_path)
    with sqlite3.connect(gameplay) as connection:
        connection.execute("DELETE FROM checkpoints WHERE projector_id='population-recovery:world'")
    authority = recovery.authority_digest(gameplay)
    before = checkpoints(gameplay)
    with pytest.raises(ValueError, match="population_recovery_checkpoint_rebuild_required"):
        recovery.maintain_archive(graph, mode=world.mode, roster=world.roster, output=tmp_path / "audit", rebuild=False)
    assert checkpoints(gameplay) == before
    assert recovery.authority_digest(gameplay) == authority


@pytest.mark.parametrize("changed", ["outbox", "projection_refresh"])
def test_pending_digest_detects_state_change_without_authority_event_change(tmp_path, changed):
    _, gameplay, world = archive(tmp_path)
    bus = InMemoryAuthorityEventBus()
    bus.subscribe("population_cadence_event", lambda _: (_ for _ in ()).throw(RuntimeError("offline")))
    publisher = _publisher(world, bus)
    assert publisher(world.build_population_cadence(window_start=2400, window_end=2460)) is None
    before = recovery.pending_state(world.store)
    events = world.store.read_events()
    heads = world.store.get_stream_heads()
    assert before["outbox"]["count"] == before["projection_refresh"]["count"] == 1
    entry = world.store.list_outbox(include_delivered=False)[0]
    if changed == "outbox":
        world.store.mark_outbox_retryable(entry.outbox_id, "second_failure")
    else:
        with sqlite3.connect(gameplay) as connection:
            connection.execute("UPDATE transactions SET refresh_state='done' WHERE transaction_id=?", (entry.transaction_id,))
    after = recovery.pending_state(world.store)
    assert before[changed] != after[changed]
    assert world.store.read_events() == events and world.store.get_stream_heads() == heads
    comparison = recovery.compare_oracles({"pending": after}, {"pending": before})
    assert not comparison["oracle_matches"] and comparison["oracle_differences"] == ["pending"]
    assert comparison["pending_before"] == before and comparison["pending_after"] == after


def test_checkpoint_swap_failure_rolls_back_and_audit_leaves_source_unchanged(tmp_path, monkeypatch):
    graph, gameplay, world = archive(tmp_path)
    before = checkpoints(gameplay)
    authority = recovery.authority_digest(gameplay)
    report = recovery.maintain_archive(graph, mode=world.mode, roster=world.roster, output=tmp_path / "audit", rebuild=False)
    assert report["passed"] and checkpoints(gameplay) == before
    rebuild_copy = recovery.rebuild_population_copy

    def inject_failure(*args, **kwargs):
        result = rebuild_copy(*args, **kwargs)
        with sqlite3.connect(gameplay) as connection:
            connection.execute("""CREATE TRIGGER fail_checkpoint BEFORE INSERT ON checkpoints
                WHEN NEW.id LIKE 'population-recovery:%'
                BEGIN SELECT RAISE(ABORT, 'checkpoint_swap_failed'); END""")
        return result

    monkeypatch.setattr(recovery, "rebuild_population_copy", inject_failure)
    with pytest.raises(sqlite3.IntegrityError, match="checkpoint_swap_failed"):
        recovery.maintain_archive(graph, mode=world.mode, roster=world.roster, output=tmp_path / "failed", rebuild=True)
    assert checkpoints(gameplay) == before
    assert recovery.authority_digest(gameplay) == authority


def test_rebuild_keeps_pending_window_for_normal_delivery_retry(tmp_path):
    graph, gameplay, world = archive(tmp_path)
    bus = InMemoryAuthorityEventBus()
    bus.subscribe("population_cadence_event", lambda _: (_ for _ in ()).throw(RuntimeError("offline")))
    publisher = _publisher(world, bus)
    cadence = world.build_population_cadence(window_start=2400, window_end=2460)
    assert publisher(cadence) is None
    pending = world.store.list_outbox(include_delivered=False)
    authority = recovery.authority_digest(gameplay)
    recovery.maintain_archive(graph, mode=world.mode, roster=world.roster, output=tmp_path / "rebuild", rebuild=True)
    assert recovery.authority_digest(gameplay) == authority
    restored = _runtime(gameplay)
    assert restored.store.list_outbox(include_delivered=False) == pending
    runtime_bus = InMemoryAuthorityEventBus()
    restored_publisher = _publisher(restored, runtime_bus)
    assert restored_publisher.confirmed_tick == 2400
    assert not runtime_bus.list_events(include_realtime=True)
    assert restored_publisher(cadence) is not None
    assert restored_publisher.confirmed_tick == 2460
    assert len(runtime_bus.list_events(include_realtime=True)) == 1
    assert not restored.store.list_outbox(include_delivered=False)
