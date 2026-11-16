import pytest
from pydantic import ValidationError

from app.models.feasibility_response import FeasibilityResponse


def test_feasibility_response_validates_boolean_and_round_trips():
    value = FeasibilityResponse(response_id="f", proposal_ref="p", feasible=False,
        constraints=["cooldown_active"], producer_ts=1, causation_id="p", correlation_id="corr")
    assert FeasibilityResponse.model_validate_json(value.model_dump_json()) == value
    with pytest.raises(ValidationError):
        FeasibilityResponse.model_validate({**value.model_dump(), "feasible": "false"})
