import pytest
from pydantic import ValidationError

from app.models.constraint_probe import ConstraintProbe


def test_constraint_probe_validates_kind_and_round_trips():
    value = ConstraintProbe(probe_id="q", target_environment_id="env_lamp", constraint_type="all",
        producer_ts=1, causation_id="cause", correlation_id="corr")
    assert ConstraintProbe.model_validate_json(value.model_dump_json()) == value
    with pytest.raises(ValidationError):
        ConstraintProbe.model_validate({**value.model_dump(), "constraint_type": "unknown"})
