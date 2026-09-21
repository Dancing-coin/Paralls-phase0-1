from app.models.siming_event import SimingAuditCorrection, SimingAuditRecord
from app.models.siming_runtime_state import NarrativeReadModel, SimingCheckpoint
from app.services.siming_audit_writer import SqliteSimingAuditWriter


def test_durable_audit_reads_old_records_without_growing_in_memory(tmp_path) -> None:
    path = tmp_path / "siming-audit.sqlite3"
    writer = SqliteSimingAuditWriter(path)
    for index in range(300):
        writer.record(SimingAuditRecord(
            audit_id=f"audit:{index}", room_id="room:1", correlation_id=f"correlation:{index}",
            causation_id=f"cause:{index}", source_event_id=f"event:{index}",
            status="recorded", reason="accepted",
        ))
    writer.record_checkpoint(SimingCheckpoint(
        checkpoint_id="checkpoint:1", schema_version=1, room_id="room:1", world_ts=1,
        sim_tick_ts=1, checkpoint_type="pre_decision", causation_id="cause:1",
        correlation_id="correlation:1",
    ))
    for index in range(2):
        writer.record_read_model(NarrativeReadModel(
            read_model_id=f"model:{index}", schema_version=1, producer_system="siming",
            room_id="room:1", scene_scope="scene:1", world_ts=index, sim_tick_ts=index,
        ))
    assert writer._records_by_id == {}
    assert writer._checkpoints_by_id == {}
    assert writer._read_models_by_id == {}
    writer.close()

    restored = SqliteSimingAuditWriter(path)
    assert restored.get_record("audit:0").reason == "accepted"
    assert [item.audit_id for item in restored.find_by_correlation(
        room_id="room:1", correlation_id="correlation:0")] == ["audit:0"]
    assert [item.audit_id for item in restored.find_by_causation(
        room_id="room:1", causation_id="cause:299")] == ["audit:299"]
    assert [item.checkpoint_id for item in restored.list_checkpoints(room_id="room:1")] == ["checkpoint:1"]
    assert [item.read_model_id for item in restored.list_read_models(room_id="room:1")] == ["model:0", "model:1"]
    assert restored.latest_read_model(room_id="room:1").read_model_id == "model:1"
    restored.append_correction("audit:0", SimingAuditCorrection(
        correction_id="correction:0", status="recorded", reason="checked",
        causation_id="cause:0", producer_ts=2,
    ))
    restored.record(restored.get_record("audit:0"))
    assert restored.duplicate_count == 1
    assert restored.get_record("audit:0").correction_records[0].reason == "checked"
    restored.close()

    again = SqliteSimingAuditWriter(path)
    assert again.get_record("audit:0").correction_records[0].reason == "checked"
    again.close()
