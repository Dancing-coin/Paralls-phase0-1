from app.models.siming_event import FairnessStateSnapshot
from app.models.siming_runtime_state import (
    GroupSimulationBranchSnapshot, NarrativeObligation, NarrativeObligationLedgerSnapshot,
    StateTreeNode, StateTreeSnapshot, StorylineStateSnapshot,
)
from app.services.rule_based_storyline_projection import RuleBasedStorylineProjection


def _inputs(obligations, phase="rising", pressure=0.0, fairness=1.0):
    state = StateTreeSnapshot(
        snapshot_id="state:1", schema_version=1, producer_system="test", room_id="room:1",
        scene_id="scene:1", zone_id="zone:1", world_ts=1, sim_tick_ts=2,
        causation_id="cause", correlation_id="corr",
        environment=StateTreeNode(node_id="env", owner_system="l1", authority="mirror", status="fresh"),
        character=StateTreeNode(node_id="char", owner_system="char", authority="mirror", status="fresh"),
        storyline=StateTreeNode(node_id="story", owner_system="siming", authority="editable", status="fresh"),
        group_simulation=GroupSimulationBranchSnapshot(status="fresh", summary={"avg_need_pressure": pressure}),
    )
    fairness_snapshot = FairnessStateSnapshot(
        snapshot_id="fairness:1", room_id="room:1", scene_id="scene:1", zone_id="zone:1",
        causation_id="cause", correlation_id="corr", overall_fairness_score=fairness,
    )
    storyline = StorylineStateSnapshot(
        snapshot_id="storyline:1", schema_version=1, producer_system="test", room_id="room:1",
        world_ts=1, sim_tick_ts=2, causation_id="cause", correlation_id="corr",
        active_phase=phase,
    )
    ledger = NarrativeObligationLedgerSnapshot(
        ledger_id="ledger:1", schema_version=1, producer_system="test", room_id="room:1",
        world_ts=1, sim_tick_ts=2, causation_id="cause", correlation_id="corr", obligations=obligations,
    )
    return state, fairness_snapshot, storyline, ledger


def _obligation(ref, kind, status="open"):
    return NarrativeObligation(obligation_id=ref, source_ref="event:1", obligation_type=kind, status=status, reason=ref)


def test_open_obligations_become_hints():
    inputs = _inputs([_obligation("open", "open_opportunity"), _obligation("done", "open_opportunity", "closed")])
    result = RuleBasedStorylineProjection().project(state_tree=inputs[0], fairness=inputs[1], storyline=inputs[2], ledger=inputs[3])
    assert [item["obligation_id"] for item in result.candidate_hints] == ["open"]


def test_hints_sorted_by_weight_descending():
    inputs = _inputs([_obligation("plain", "other"), _obligation("reveal", "unresolved_reveal")])
    weights = RuleBasedStorylineProjection().project(state_tree=inputs[0], fairness=inputs[1], storyline=inputs[2], ledger=inputs[3]).candidate_hints
    assert weights[0]["obligation_id"] == "reveal"


def test_max_hints_limit():
    inputs = _inputs([_obligation(str(i), "open_opportunity") for i in range(8)])
    result = RuleBasedStorylineProjection(max_hints=3).project(state_tree=inputs[0], fairness=inputs[1], storyline=inputs[2], ledger=inputs[3])
    assert len(result.candidate_hints) == 3


def test_phase_match_setup_accepts_all():
    inputs = _inputs([_obligation("x", "other")], phase="setup")
    result = RuleBasedStorylineProjection().project(state_tree=inputs[0], fairness=inputs[1], storyline=inputs[2], ledger=inputs[3])
    assert result.candidate_hints[0]["phase_match"] is True


def test_phase_match_rising_filters():
    inputs = _inputs([_obligation("x", "resolution_required")], phase="rising")
    result = RuleBasedStorylineProjection().project(state_tree=inputs[0], fairness=inputs[1], storyline=inputs[2], ledger=inputs[3])
    assert result.candidate_hints[0]["phase_match"] is False


def test_unresolved_reveal_maps_to_fact_reveal_band():
    inputs = _inputs([_obligation("x", "unresolved_reveal")])
    result = RuleBasedStorylineProjection().project(state_tree=inputs[0], fairness=inputs[1], storyline=inputs[2], ledger=inputs[3])
    assert result.candidate_hints[0]["suggested_band"] == "fact_reveal"


def test_group_pressure_increases_weight():
    low = _inputs([_obligation("x", "other")], pressure=0.0)
    high = _inputs([_obligation("x", "other")], pressure=1.0)
    low_weight = RuleBasedStorylineProjection().project(state_tree=low[0], fairness=low[1], storyline=low[2], ledger=low[3]).candidate_hints[0]["weight"]
    high_weight = RuleBasedStorylineProjection().project(state_tree=high[0], fairness=high[1], storyline=high[2], ledger=high[3]).candidate_hints[0]["weight"]
    assert high_weight > low_weight


def test_summary_mode_is_rule_based():
    inputs = _inputs([])
    result = RuleBasedStorylineProjection().project(state_tree=inputs[0], fairness=inputs[1], storyline=inputs[2], ledger=inputs[3])
    assert result.summary["mode"] == "rule_based"


def test_projection_id_format():
    inputs = _inputs([])
    result = RuleBasedStorylineProjection().project(state_tree=inputs[0], fairness=inputs[1], storyline=inputs[2], ledger=inputs[3])
    assert result.projection_id == "projection:room:1:2"


def test_empty_ledger():
    inputs = _inputs([])
    result = RuleBasedStorylineProjection().project(state_tree=inputs[0], fairness=inputs[1], storyline=inputs[2], ledger=inputs[3])
    assert result.candidate_hints == [] and result.status == "fresh"
