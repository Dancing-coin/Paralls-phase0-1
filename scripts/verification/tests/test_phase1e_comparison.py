from __future__ import annotations

from scripts.verification.phase1e_comparison import build_generalization_comparison


def test_comparison_keeps_sample_fields_out_of_shared_contract() -> None:
    report = build_generalization_comparison()
    assert len(report.samples) == 3
    assert not set(report.shared_contract_fields) & {field for fields in report.sample_only_fields.values() for field in fields}
    assert "Population Simulation" in report.deferred_domains
    assert set(report.replay_hashes) == set(report.samples)
    assert all(value for value in report.replay_hashes.values())
