import pytest
from pydantic import ValidationError

from app.models.environment_proposal import EnvironmentProposal
from test_esm_proposal_evaluation import proposal


def test_environment_proposal_json_and_required_fields():
    value = proposal()
    assert EnvironmentProposal.model_validate_json(value.model_dump_json()) == value
    data = value.model_dump()
    for field in ("proposal_id", "room_id", "scene_id", "zone_id", "target_environment_id", "goal", "requested_change_type"):
        with pytest.raises(ValidationError):
            EnvironmentProposal.model_validate({**data, field: " "})


def test_proposal_rejects_non_json_fallback_shape():
    with pytest.raises(ValidationError):
        EnvironmentProposal.model_validate({**proposal().model_dump(), "fallback_options": ["untyped"]})
    with pytest.raises(ValidationError):
        EnvironmentProposal.model_validate({**proposal().model_dump(), "fallback_options": [{"invalid": object()}]})
