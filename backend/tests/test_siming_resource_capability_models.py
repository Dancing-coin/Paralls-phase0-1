import pytest
from pydantic import ValidationError

from app.models.siming_resource_capability import (
    ResourceRealizationRequest,
    StagingResult,
)


def realization_request(*, semantic_purpose: str) -> ResourceRealizationRequest:
    return ResourceRealizationRequest(
        node_id="runtime:bridge:1",
        actor_bindings={"speaker": "char_b", "listener": "char_c"},
        target_object_id="obj_letter",
        required_realization_keys=["look_at_target", "focus_attention"],
        camera_pattern="two_actor_confrontation",
        semantic_purpose=semantic_purpose,
        location_state="throne_room:letter_removed",
    )


def test_signature_changes_with_semantic_purpose() -> None:
    first = realization_request(semantic_purpose="evidence_reveal").signature(
        "main_demo_throne_room"
    )
    second = realization_request(semantic_purpose="private_confrontation").signature(
        "main_demo_throne_room"
    )

    assert first != second


def test_staging_result_cannot_claim_story_resolution() -> None:
    with pytest.raises(ValidationError, match="story"):
        StagingResult(
            node_id="runtime:bridge:1",
            correlation_id="corr:1",
            status="staged",
            story_node_lifecycle="staged",
            obligation_status="open",
            realization_signature="sig:1",
            story_resolved=True,
        )
