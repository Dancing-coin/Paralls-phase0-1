from types import SimpleNamespace

from app.models.siming_runtime_state import GroupSimulationBranchSnapshot
from app.services.population_simulation_bridge import PopulationGroupSimulationBridge


def _world(rows):
    return SimpleNamespace(
        export_rows=lambda: tuple(rows),
        latest_confirmation=SimpleNamespace(window_end=120),
    )


def test_summarize_with_live_actors():
    result = PopulationGroupSimulationBridge(_world([
        ("actor:a", {"fatigue": 0.2, "need_pressure": 0.4, "activity_phase": "morning"}),
        ("actor:b", {"fatigue": 0.4, "need_pressure": 0.6, "activity_phase": "evening"}),
    ])).summarize(room_id="room:main")

    assert result.status == "fresh"
    assert result.summary["mode"] == "live"
    assert result.summary["actor_count"] == 2
    assert result.summary["phase_distribution"] == {"morning": 1, "evening": 1}
    assert result.summary["last_batch_tick"] == 120


def test_summarize_with_no_actors():
    result = PopulationGroupSimulationBridge(_world([])).summarize(room_id="room:main")
    assert result.status == "fresh"
    assert result.summary["actor_count"] == 0
    assert result.summary["avg_fatigue"] == 0.0


def test_summarize_unavailable_when_world_not_initialized():
    result = PopulationGroupSimulationBridge(None).summarize(room_id="room:main")
    assert result.status == "unavailable"


def test_avg_fatigue_calculation():
    result = PopulationGroupSimulationBridge(_world([
        ("a", {"fatigue": 0.2, "need_pressure": 0.0, "activity_phase": "morning"}),
        ("b", {"fatigue": 0.4, "need_pressure": 0.0, "activity_phase": "morning"}),
        ("c", {"fatigue": 0.6, "need_pressure": 0.0, "activity_phase": "evening"}),
    ])).summarize(room_id="room:main")
    assert result.summary["avg_fatigue"] == 0.4


def test_phase_distribution():
    result = PopulationGroupSimulationBridge(_world([
        ("a", {"fatigue": 0.0, "need_pressure": 0.0, "activity_phase": "morning"}),
        ("b", {"fatigue": 0.0, "need_pressure": 0.0, "activity_phase": "morning"}),
        ("c", {"fatigue": 0.0, "need_pressure": 0.0, "activity_phase": "evening"}),
    ])).summarize(room_id="room:main")
    assert result.summary["phase_distribution"] == {"evening": 1, "morning": 2}
