from __future__ import annotations

import pytest

from app.gameplay.closed_generic_gameplay_families import (
    CLOSED_GAMEPLAY_FAMILIES,
    PRODUCTION_OUTPUT_CUSTODY_BLOCKER,
    ProductionOutputCustodyContent,
    admit_family_binding,
)


def test_custody_blocker_records_each_missing_committed_fact() -> None:
    assert PRODUCTION_OUTPUT_CUSTODY_BLOCKER.family_ref == "production_output_custody@1"
    assert any("quantity" in value and "absent" in value for value in PRODUCTION_OUTPUT_CUSTODY_BLOCKER.candidate_values)
    assert any("holder" in value and "mapping" in value for value in PRODUCTION_OUTPUT_CUSTODY_BLOCKER.candidate_values)
    assert any("container" in value and "unique" in value for value in PRODUCTION_OUTPUT_CUSTODY_BLOCKER.candidate_values)
    assert PRODUCTION_OUTPUT_CUSTODY_BLOCKER.status == "blocked"


def test_custody_family_is_promoted_after_committed_mapping_admission() -> None:
    family = next(item for item in CLOSED_GAMEPLAY_FAMILIES if item.family_ref == "production_output_custody@1")
    assert family.status == "generic_implemented"
    assert family.adapter_ref == "InventoryAuthorityService.settle_production_output_custody"
    assert PRODUCTION_OUTPUT_CUSTODY_BLOCKER.recommended_decision
