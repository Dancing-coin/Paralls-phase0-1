from __future__ import annotations

from app.character_agent.skills.models import SkillEvaluationResult
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.resource_body_runtime import ResourceBodyActionSettlementService, ResourceBodyRuntimeProjector
from app.gameplay.skill_action_gate import SkillPathGameplayGate

from test_resource_body_runtime import ACTOR, _command, _materialize_stamina


def _evaluation(*, eligible: bool) -> SkillEvaluationResult:
    return SkillEvaluationResult(
        actor_id=ACTOR,
        action_id="skill:sword_slash",
        selected_path={"binding_id": "sword-slash", "eligibility_status": "eligible"} if eligible else {},
        viable_paths=[{"binding_id": "sword-slash"}] if eligible else [],
        blocked_paths=[] if eligible else [{"binding_id": "sword-slash", "missing_requirements": ["swordsmanship.basic"]}],
        recommendation_reason=["eligible_skill_path_available"] if eligible else ["no_eligible_skill_path"],
        learning_policy_snapshot={"promotion_enabled": False},
    )


def test_ineligible_skill_path_rejects_before_resource_or_action_write() -> None:
    store = GameplayEventStore()
    _materialize_stamina(store, 7)
    projector = ResourceBodyRuntimeProjector()

    result = SkillPathGameplayGate(
        resource_body_settlement=ResourceBodyActionSettlementService(store=store)
    ).settle(
        _command("cmd:skill-blocked"),
        skill_evaluation=_evaluation(eligible=False),
        resources=projector.rebuild_resources(ACTOR, store.read_events()),
        body=projector.rebuild_body(ACTOR, store.read_events()),
        enabled_group_ids=("core.resources", "core.body_runtime"),
    )

    assert result.accepted is False
    assert result.reason_code == "skill_path_not_eligible"
    assert [event.event_type for event in store.read_events()] == ["gameplay.resource.materialized"]


def test_eligible_skill_path_delegates_to_authority_resource_body_settlement() -> None:
    store = GameplayEventStore()
    _materialize_stamina(store, 7)
    projector = ResourceBodyRuntimeProjector()

    result = SkillPathGameplayGate(
        resource_body_settlement=ResourceBodyActionSettlementService(store=store)
    ).settle(
        _command("cmd:skill-success"),
        skill_evaluation=_evaluation(eligible=True),
        resources=projector.rebuild_resources(ACTOR, store.read_events()),
        body=projector.rebuild_body(ACTOR, store.read_events()),
        enabled_group_ids=("core.resources", "core.body_runtime"),
    )

    assert result.accepted is True
    assert [event.event_type for event in store.read_events()] == [
        "gameplay.resource.materialized",
        "gameplay.resource.adjusted",
        "gameplay.action.settled",
    ]
