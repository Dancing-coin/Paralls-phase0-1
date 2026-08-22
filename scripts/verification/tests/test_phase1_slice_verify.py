from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_phase1_slice as verifier


def test_phase1_slice_isolates_legacy_probe_from_heavenly_runtime_mode() -> None:
    assert verifier.PHASE1_SLICE_VERIFY_ENV["SIMING_HEAVENLY_MODE"] == "off"
    assert verifier.PHASE1_SLICE_VERIFY_ENV["SIMING_LLM_MODE"] == "disabled"


def test_l1_mainline_contract_uses_a_fresh_graph_database_per_run() -> None:
    source = (Path(__file__).resolve().parents[1] / "verify_l1_world_fact_runtime.py").read_text(
        encoding="utf-8"
    )

    assert "uuid4" in source
    assert "l1-mainline-route-" in source
    assert "heavenly_graph_path" in source
