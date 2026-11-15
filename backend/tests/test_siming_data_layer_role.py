import pytest

from app.services.siming_data_layer import SimingDataLayer
from test_siming_data_layer import _snapshot


def test_persist_and_load_after_reopen_with_room_isolation(tmp_path):
    path = tmp_path / "siming.db"
    layer = SimingDataLayer(path)
    layer.save_snapshot(_snapshot(), sim_tick_ts=100, world_ts=99)
    layer.close()
    reopened = SimingDataLayer(path)
    try:
        assert reopened.latest_snapshot("room:1") == _snapshot()
        assert reopened.latest_snapshot("other") is None
    finally:
        reopened.close()


@pytest.mark.parametrize("method", ["load_state_tree_snapshot", "load_global_situation_snapshot", "load_narrative_snapshot"])
def test_phase2_recovery_is_explicitly_unavailable(tmp_path, method):
    layer = SimingDataLayer(tmp_path / "siming.db")
    try:
        with pytest.raises(NotImplementedError, match="Phase 2"):
            getattr(layer, method)("room:1", 100)
    finally:
        layer.close()
