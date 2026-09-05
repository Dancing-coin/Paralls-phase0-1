from __future__ import annotations

import pytest

from app.gameplay.p5.stormnight_scenario import StormnightScenarioRunner


@pytest.mark.parametrize("outcome_kind", ("case_solved", "false_accusation", "culprit_escaped", "investigator_captured"))
def test_stormnight_scenario_runs_owner_bound_case_loop_and_replays(outcome_kind: str) -> None:
    result = StormnightScenarioRunner().run(outcome_kind=outcome_kind)
    assert result.case_opened
    assert result.action_window_committed
    assert result.statement_committed
    assert result.clue_committed
    assert result.custody_committed
    assert result.accusation_committed
    assert result.outcome_kind == outcome_kind
    assert result.outcome_committed
    assert result.full_replay_hash == result.tail_replay_hash
    assert result.owner_replay_hash.startswith("sha256:")
    assert result.phases_completed == 3
    assert result.agent_turn_proposed
    assert result.owner_replay_consistent
