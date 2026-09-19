import importlib.util
from pathlib import Path
import sqlite3

import pytest

from app.character_agent.storage.session_store import CharacterAgentSessionStore


def _load_probe():
    path = Path(__file__).parents[2] / "scripts/verification/verify_population_data_oriented_persistence.py"
    spec = importlib.util.spec_from_file_location("population_persistence_wal_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_session_wal_measurement_starts_after_recycled_migration_frames():
    result = _load_probe().measure_session_and_checkpoint_scale(20000, repeats=2)
    assert result["passed"], result
    assert min(result["session_append_bytes"]) > 0
    assert result["session_reopened_event_count"] == 20003
    assert result["runtime_reopened_event_count"] == 20005
    assert result["checkpoint_count"] == 0
    assert result["current_state_event_indexes"] == [20004, 20005]
    assert not any(result["current_state_contains_history"])


def test_session_wal_measurement_rejects_busy_checkpoint_then_can_reset(tmp_path):
    probe = _load_probe()
    path = tmp_path / "session.sqlite"
    store = CharacterAgentSessionStore(database_path=path)
    reader = sqlite3.connect(path)
    try:
        store.append_event("a", "first", 1, {})
        reader.execute("BEGIN")
        assert reader.execute("SELECT event_count FROM character_session_heads").fetchone() == (1,)
        store.append_event("a", "second", 2, {})
        store._connection.execute("PRAGMA busy_timeout=0")
        wal_path = Path(str(path) + "-wal")
        with pytest.raises(RuntimeError, match="session_wal_checkpoint_failed"):
            probe._reset_session_wal(store, wal_path)
        assert wal_path.stat().st_size > 0
        reader.rollback()
        page_size = probe._reset_session_wal(store, wal_path)
        assert page_size == store._connection.execute("PRAGMA page_size").fetchone()[0]
        assert wal_path.stat().st_size == 0
        assert store.event_count("a") == 2
    finally:
        reader.close()
        store.close()


def test_session_probe_exports_actual_raw_values_required_for_offline_gate():
    result = _load_probe().measure_session_and_checkpoint_scale(10, repeats=2)
    assert result['passed']
    assert type(result['sqlite_page_size']) is int and result['sqlite_page_size'] > 0
    assert result['continuity_receipt_statuses'] == ['committed', 'committed']
    assert result['runtime_event_count_before_reopen'] == result['runtime_reopened_event_count'] == 15
    assert all(0 < value <= 128 * result['sqlite_page_size'] for value in result['session_append_bytes'])
