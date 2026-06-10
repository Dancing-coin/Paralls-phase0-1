from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_boundaries import evaluate_boundaries
from common import repo_root


def test_evaluate_boundaries_proves_core_runtime_ownership_rules() -> None:
    report = evaluate_boundaries(repo_root())
    statuses = {entry["id"]: entry["status"] for entry in report["results"]}

    assert statuses["visual_fact_emitter_exists"] == "proved"
    assert statuses["harness_artifacts_are_project_local"] == "proved"
    assert statuses["backend_parses_player_input_models"] == "proved"
    assert statuses["player_input_mapper_emits_structured_intents"] == "proved"
    assert statuses["godot_world_changes_consume_backend_results"] == "proved"
    assert statuses["siming_service_emits_high_level_outputs_only"] == "proved"
    assert statuses["siming_event_bus_port_exists"] == "proved"
    assert statuses["siming_projected_event_reaches_godot_bus"] == "proved"
    assert statuses["runtime_trace_schema_is_enriched"] == "proved"


def test_boundaries_prove_siming_llm_runtime_containment() -> None:
    report = evaluate_boundaries(repo_root())
    statuses = {entry["id"]: entry["status"] for entry in report["results"]}

    assert statuses["siming_llm_stays_inside_runtime"] == "proved"
