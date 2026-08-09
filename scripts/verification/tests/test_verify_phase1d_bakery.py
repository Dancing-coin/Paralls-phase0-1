from __future__ import annotations

from scripts.verification.verify_phase1d_bakery import _failure_matrix
from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario


def test_phase1d_failure_matrix_is_structured_zero_write_and_recoverable() -> None:
    entries = _failure_matrix(BakeryReferenceScenario.default())
    cases = {str(entry["case"]) for entry in entries}
    assert {
        "material_shortage",
        "qualification",
        "capacity",
        "funds",
        "quote_expiry",
        "permit_expiry",
        "facility_unavailable",
        "overdue_obligation",
        "stale_revision",
        "duplicate",
    } <= cases
    assert all(entry["zero_write"] and entry["recovery_observed"] for entry in entries)
