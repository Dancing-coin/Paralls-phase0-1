import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.population_continuity.recovery import PopulationRecoveryCheckpoint, recovery_digest


@pytest.fixture
def checkpoint_state():
    # This checkpoint was produced by G3 before daily rhythm was introduced.
    return json.loads(Path(__file__).with_name("population_legacy_checkpoint.json").read_text(encoding="utf-8"))


def _with_phase(checkpoint, phase):
    data = json.loads(json.dumps(checkpoint))
    state = data["recovery_state"]
    for actor in state["actors"]:
        actor["activity_phase"] = phase
    state["state_digest"] = recovery_digest({k: v for k, v in state.items() if k != "state_digest"})
    return json.dumps(data)


@pytest.mark.parametrize("phase", ["rest", "routine", "routine_work", "leisure", "morning", "afternoon", "evening", "night"])
def test_checkpoint_loads_legacy_and_daily_rhythm_phases(checkpoint_state, phase):
    checkpoint = PopulationRecoveryCheckpoint.model_validate_json(_with_phase(checkpoint_state, phase))
    assert all(actor.activity_phase == phase for actor in checkpoint.recovery_state.actors)


def test_checkpoint_rejects_unknown_activity_phase(checkpoint_state):
    with pytest.raises(ValidationError, match="literal_error"):
        PopulationRecoveryCheckpoint.model_validate_json(_with_phase(checkpoint_state, "noon"))
