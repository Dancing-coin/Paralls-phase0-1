from __future__ import annotations

from scripts.verification.phase1e_comparison import build_generalization_comparison


def test_generalization_fixture_has_three_distinct_samples() -> None:
    comparison = build_generalization_comparison()
    assert comparison.samples == ("frost-farm", "bakery-single-owner", "ownership-contract-debt")
    assert comparison.owner_diff["ownership-contract-debt"] == "ownership_contract_debt"
