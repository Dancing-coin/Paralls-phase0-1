from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_l1_runtime_edges_verify_reports_legacy_probe_isolation_path() -> None:
    source = (ROOT / "verify_l1_runtime_edges.py").read_text(encoding="utf-8")

    assert '"id": "backend_connected_observed"' in source
    assert '"id": "zone_bootstrap_observed"' in source
    assert '"id": "legacy_disconnect_reseed_probe"' in source
    assert '"status": "proved" if legacy_edge_probe_supported else "isolated"' in source
    assert "older probe no longer matches the reconnect/privacy/environment edge contract" in source


def test_l1_runtime_edges_verify_hard_pass_uses_current_runtime_truth_not_legacy_probe_counts() -> None:
    source = (ROOT / "verify_l1_runtime_edges.py").read_text(encoding="utf-8")

    overall_section = source.split('"overall_l1_runtime_edges_passed": (', 1)[1].split("),", 1)[0]

    assert "backend_connected_ok" in overall_section
    assert "initial_zone_bootstrap_ok" in overall_section
    assert "health_overlap_ok" in overall_section
    assert "disconnect_ok" not in overall_section
    assert "privacy_reseed_ok" not in overall_section
    assert "environment_cycle_ok" not in overall_section
