from app.character_agent.execution.kimodo_adapter_contract import KimodoActionRequest
from app.character_agent.execution.kimodo_adapter_contract import KimodoRealizationPlan


def test_kimodo_action_request_carries_semantic_and_target_metadata() -> None:
    request = KimodoActionRequest(
        actor_id="char_a",
        semantic_keys=["approach", "greeting_nod"],
        target_actor_id="char_c",
        execution_mode="skeletal_animation",
    )

    assert request.semantic_keys == ["approach", "greeting_nod"]
    assert request.target_actor_id == "char_c"


def test_kimodo_realization_plan_carries_generated_motion_and_local_fallback_assets() -> None:
    plan = KimodoRealizationPlan(
        actor_id="char_a",
        semantic_keys=["approach", "greeting_nod"],
        execution_mode="skeletal_animation",
        generated_motion_allowed=True,
        local_fallback_asset_refs=["res://motions/approach.anim"],
        missing_semantic_keys=["greeting_nod"],
    )

    assert plan.generated_motion_allowed is True
    assert plan.local_fallback_asset_refs == ["res://motions/approach.anim"]
    assert plan.missing_semantic_keys == ["greeting_nod"]
