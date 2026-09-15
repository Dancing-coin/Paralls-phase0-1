from __future__ import annotations

import importlib.util
from pathlib import Path


def test_hot_state_equivalence_probe_matches_baseline_for_population_tiers() -> None:
    path = Path(__file__).parents[2] / "scripts" / "verification" / "verify_population_hot_state_equivalence.py"
    spec = importlib.util.spec_from_file_location("population_hot_state_equivalence", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    report = module.measure(100)
    assert report["equivalent"] is True
    assert report["baseline_hash"] == report["hot_state_hash"]
