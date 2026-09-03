from __future__ import annotations

import pytest

from app.gameplay.organization_government_social_platform_runtime import OrganizationGovernmentSocialProjector
from app.gameplay.organization_government_social_presentation import (
    OGSPresentationError,
    build_ogs_read_model,
    reject_speculative_ogs_state,
)


def test_ogs_presentation_is_read_only_and_rejects_speculative_truth() -> None:
    projection = OrganizationGovernmentSocialProjector().rebuild(())
    model = build_ogs_read_model(projection)
    assert model["speculative_truth"] is False
    with pytest.raises(TypeError):
        model["projection_hash"] = "forged"  # type: ignore[index]
    with pytest.raises(OGSPresentationError, match="ogs_presentation_speculative_truth_denied"):
        reject_speculative_ogs_state({"organization": "invented"})
