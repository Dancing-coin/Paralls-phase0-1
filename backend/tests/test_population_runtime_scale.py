from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_scale():
    path = Path(__file__).parents[2] / "scripts" / "verification" / "verify_population_runtime_scale.py"
    spec = importlib.util.spec_from_file_location("population_runtime_scale", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scale_matrix_uses_required_populations_windows_and_independent_budgets() -> None:
    scale = _load_scale()

    assert scale.POPULATION_SIZES == (100, 1000)
    assert scale.WINDOW_COUNT == 30
    assert scale.PRESSURE_PROFILES == {
        "one_x": {"wall_budget_seconds": 1.0},
        "ten_x": {"wall_budget_seconds": 0.1},
    }


def test_small_real_runtime_probe_restarts_with_identical_hot_state(tmp_path) -> None:
    scale = _load_scale()

    result = scale.measure_scenario(
        population=3,
        window_count=2,
        wall_budget_seconds=1.0,
        storage_path=tmp_path / "gameplay.json",
    )

    assert result["status"] == "completed"
    assert result["authority_graph_verified"] is True
    assert result["authority_graph_event_count"] == 0
    assert result["authority_graph_probe"]["projected_count"] == 1
    assert result["passed"] is True
    assert result["windows_completed"] == 2
    assert result["published_event_count"] == 2
    assert result["retained_event_count"] == 2
    assert result["pipeline_event_count"] == 2
    assert result["character_registration_verified"] is True
    assert result["full_profile_loaded"] is False
    assert result["persistent_gameplay_verified"] is True
    assert result["recovered_hot_state_hash"] == result["committed_hot_state_hash"]
    assert result["b0_cursor_verified"] is True
    assert result["owner_scenario_verified"] is True
    assert result["behavior_turn_verified"] is True
    assert result["behavior_turn_count"] == 2
    assert result["owner_ms"] > 0
    assert result["protocol_bytes"] > 0
    assert len(result["window_wall_ms"]) == 2
    assert result["stage_costs"]["pure_integrator"]["samples"] == 2
    assert result["stage_costs"]["durable_transaction"]["samples"] > 0
    assert result["durable_store_bytes"] > 0
    assert "durable_snapshot" not in result["stage_costs"]
    assert result["input_roster_digest"] == scale._digest(
        ("scale_00000", "scale_00001", "scale_00002")
    )
    assert result["window_evidence_verified"] is True
    assert len(result["window_evidence"]) == 2
    for window_start, evidence in enumerate(result["window_evidence"]):
        assert evidence["verified"] is True
        assert evidence["window_start"] == window_start
        assert evidence["actor_count"] == 3
        assert evidence["actor_revision_min"] == evidence["actor_revision_max"]
        assert evidence["actor_revision_consistent"] is True
        assert evidence["read_set_digest"].startswith("sha256:")
        assert evidence["idempotency_key_template"].endswith(":character:<actor_id>")
        assert evidence["idempotency_key_set_digest"].startswith("sha256:")
        assert evidence["first_sample"]["actor_ref"].startswith("character:")
        assert evidence["last_sample"]["projection_ref"].endswith(
            f":{window_start}"
        )


def test_scale_overall_gate_requires_one_x_and_keeps_ten_x_independent(monkeypatch) -> None:
    scale = _load_scale()
    monkeypatch.setattr(scale, "POPULATION_SIZES", (100,))

    def fake_measure_scenario(
        *, population, wall_budget_seconds, storage_path, window_count=scale.WINDOW_COUNT
    ):
        scenario = scale.empty_scenario(
            population=population,
            window_count=window_count,
            wall_budget_seconds=wall_budget_seconds,
        )
        scenario.update(
            status="completed",
            windows_completed=window_count,
            p95_wall_ms=100.0 if wall_budget_seconds == 1.0 else 1000.0,
            backlog_non_growing=wall_budget_seconds == 1.0,
            max_lag_windows=0 if wall_budget_seconds == 1.0 else 2,
            persistent_gameplay_verified=True,
            recovery_verified=True,
            serial_parallel_equivalent=True,
            character_registration_verified=True,
            full_profile_loaded=False,
            b0_cursor_verified=True,
            window_evidence_verified=True,
            pipeline_verified=True,
            authority_graph_verified=True,
            behavior_turn_verified=True,
            owner_scenario_verified=True,
            pure_kernel_ms=[1.0],
            window_wall_ms=[100.0],
        )
        scenario["passed"] = scale.scenario_passed(scenario)
        return scenario

    monkeypatch.setattr(scale, "measure_scenario", fake_measure_scenario)

    report = scale.build_report()

    assert report["profiles"]["one_x"]["passed"] is True
    assert report["profiles"]["ten_x"]["passed"] is False
    assert report["all_performance_gates_passed"] is False
    assert report["overall_passed"] is True


def test_admission_fails_closed_when_any_required_evidence_is_missing() -> None:
    scale = _load_scale()
    scenario = scale.empty_scenario(population=100, window_count=30, wall_budget_seconds=1.0)
    scenario.update(
        status="completed",
        windows_completed=30,
        p95_wall_ms=10.0,
        backlog_non_growing=True,
        max_lag_windows=0,
        persistent_gameplay_verified=True,
        recovery_verified=True,
        serial_parallel_equivalent=True,
        character_registration_verified=True,
        full_profile_loaded=False,
        b0_cursor_verified=True,
        window_evidence_verified=True,
        pipeline_verified=True,
        authority_graph_verified=True,
        behavior_turn_verified=True,
        owner_scenario_verified=True,
    )

    assert scale.scenario_passed(scenario) is True
    scenario["serial_parallel_equivalent"] = None
    assert scale.scenario_passed(scenario) is False


def test_scale_graph_gate_rejects_missing_real_non_population_projection(tmp_path, monkeypatch):
    scale = _load_scale()
    monkeypatch.setattr(scale.HeavenlyAuthorityEventProjector, 'project', lambda self, event: None)
    result = scale.measure_scenario(population=3, window_count=1, wall_budget_seconds=1.0,
                                    storage_path=tmp_path / 'gameplay.json')
    assert result['status'] == 'completed'
    assert result['authority_graph_event_count'] == 0
    assert result['authority_graph_probe']['projected_count'] == 0
    assert result['authority_graph_verified'] is False
    assert result['passed'] is False
