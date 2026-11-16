import pytest
from pydantic import ValidationError

from app.models.environment_proposal import EnvironmentProposal
from app.models.feasibility_response import FeasibilityResponse
from app.models.constraint_probe import ConstraintProbe, ConstraintStateResult
from app.models.esm_execution_state import ExecutionConfirmation


@pytest.mark.parametrize("model,data", [
    (EnvironmentProposal, dict(proposal_id="p", candidate_ref="c", decision_ref="d", room_id="r", scene_id="s", zone_id="z", target_environment_id="e", goal="create_opportunity", requested_change_type="light_level_drop", requested_strength="medium", constraints_known=[], fallback_options=[], producer_ts=1, causation_id="cause", correlation_id="corr")),
    (FeasibilityResponse, dict(response_id="f", proposal_ref="p", feasible=True, constraints=[], estimated_effect={"light_level": "low"}, alternative_suggestions=[], producer_ts=1, causation_id="cause", correlation_id="corr")),
    (ConstraintProbe, dict(probe_id="q", target_environment_id="e", constraint_type="all", producer_ts=1, causation_id="cause", correlation_id="corr")),
    (ConstraintStateResult, dict(state_id="s", probe_ref="q", active_constraints={}, cooldown_remaining=0, producer_ts=1, causation_id="cause", correlation_id="corr")),
    (ExecutionConfirmation, dict(confirmation_id="c", request_ref="r", execution_state="confirmed", rollback_token=None, producer_ts=1, causation_id="cause", correlation_id="corr")),
])
def test_protocol_model_round_trip_and_rejects_extra(model, data):
    value = model.model_validate(data)
    assert model.model_validate_json(value.model_dump_json()) == value
    with pytest.raises(ValidationError):
        model.model_validate({**data, "unexpected": True})
    for field in ("producer_ts", "causation_id", "correlation_id"):
        with pytest.raises(ValidationError):
            model.model_validate({**data, field: -1 if field == "producer_ts" else " "})
    with pytest.raises(ValidationError):
        model.model_validate({**data, "producer_ts": True})


def test_proposal_rejects_blank_target_and_invalid_strength():
    data = dict(proposal_id="p", candidate_ref="c", decision_ref="d", room_id="r", scene_id="s", zone_id="z", target_environment_id="", goal="create_opportunity", requested_change_type="light_level_drop", requested_strength="extreme", constraints_known=[], fallback_options=[], producer_ts=1, causation_id="cause", correlation_id="corr")
    with pytest.raises(ValidationError):
        EnvironmentProposal.model_validate(data)
