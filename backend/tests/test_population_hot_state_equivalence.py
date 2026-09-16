from __future__ import annotations

import importlib.util
from pathlib import Path


def test_hot_state_equivalence_probe_covers_real_world_and_capability_surfaces() -> None:
    path = Path(__file__).parents[2] / "scripts" / "verification" / "verify_population_hot_state_equivalence.py"
    spec = importlib.util.spec_from_file_location("population_hot_state_equivalence", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    report = module.measure(54, repeats=1)

    assert report["equivalent"] is True
    assert report["population"] == 54
    assert report["baseline_projection_hash"] == report["serial_projection_hash"]
    assert report["baseline_projection_hash"] == report["parallel_projection_hash"]
    assert report["baseline_read_set_digest"] == report["serial_read_set_digest"]
    assert report["baseline_read_set_digest"] == report["parallel_read_set_digest"]
    assert report["baseline_capability_hash"] == report["serial_capability_hash"]
    assert report["baseline_capability_hash"] == report["parallel_capability_hash"]
    assert report["baseline_candidate_hash"] == report["serial_candidate_hash"]
    assert report["baseline_candidate_hash"] == report["parallel_candidate_hash"]
    assert report["baseline_deferred_hash"] == report["serial_deferred_hash"]
    assert report["baseline_deferred_hash"] == report["parallel_deferred_hash"]
    assert report["baseline_owner_receipt_input_hash"] == report["serial_owner_receipt_input_hash"]
    assert report["baseline_owner_receipt_input_hash"] == report["parallel_owner_receipt_input_hash"]
    assert report["baseline_final_hot_hash"] == report["serial_final_hot_hash"]
    assert report["baseline_final_hot_hash"] == report["parallel_final_hot_hash"]
    assert report["baseline_final_hot_hash"] == report["replay_final_hot_hash"]
    assert report["owner_receipt_input_count"] == 0
    assert report["capability_due_count"] == 0
    assert report["confirmation"]["presentation_due_count"] == 54 * 4
    assert report["performance_claim"] == "equivalence_only"
