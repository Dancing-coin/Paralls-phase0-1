import pytest
from pydantic import ValidationError

from app.models.esm_execution_state import ExecutionConfirmation


def test_execution_confirmation_validates_state_and_round_trips():
    value = ExecutionConfirmation(confirmation_id="c", request_ref="r", execution_state="aborted",
        producer_ts=1, causation_id="cause", correlation_id="corr")
    assert ExecutionConfirmation.model_validate_json(value.model_dump_json()) == value
    with pytest.raises(ValidationError):
        ExecutionConfirmation.model_validate({**value.model_dump(), "execution_state": "sent"})
