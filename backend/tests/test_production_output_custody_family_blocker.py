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


def test_blocked_custody_binding_is_zero_write_and_has_no_adapter() -> None:
    family = next(item for item in CLOSED_GAMEPLAY_FAMILIES if item.family_ref == "production_output_custody@1")
    content = ProductionOutputCustodyContent(
        output_item_definition_ref="item:bread@1",
        holder_binding_ref="binding:holder@1",
        container_binding_ref="binding:container@1",
        policy_revision_ref="policy:custody@1",
    )
    with pytest.raises(ValueError, match="blocker:production-output-custody-committed-facts@1"):
        admit_family_binding(
            family_ref=family.family_ref,
            package_revision="package:custody@1",
            content_digest="sha256:" + "1" * 64,
            declaration_ref="declaration:custody@1",
            declaration_digest="sha256:" + "2" * 64,
            descriptor_ref=family.descriptor_ref,
            descriptor_revision=family.descriptor_ref,
            active_set_revision="sha256:" + "3" * 64,
            typed_content=content.model_dump(mode="json"),
        )
    assert family.adapter_ref is None
