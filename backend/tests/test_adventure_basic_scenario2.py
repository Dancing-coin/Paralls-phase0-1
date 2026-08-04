from __future__ import annotations

from app.gameplay.adventure_basic_reference import AdventureBasicScenario2


def _equipped_scenario(*, stamina: int = 24) -> AdventureBasicScenario2:
    scenario = AdventureBasicScenario2.create(stamina=stamina)
    assert scenario.purchase_sword().committed
    assert scenario.equip_sword().committed
    return scenario


def test_scenario2_injury_blocks_the_equipped_sword_without_stamina_write_then_recovery_restores_affordance() -> None:
    scenario = _equipped_scenario()

    before_injury = scenario.affordance()
    injury = scenario.apply_right_arm_injury()
    after_injury = scenario.affordance()
    before_swing_events = scenario.store.read_events()
    blocked = scenario.swing_sword()

    assert before_injury.overall_status == "available"
    assert injury.committed
    assert after_injury.overall_status == "blocked"
    assert after_injury.path_results[0].blocker_codes == ("required_body_function_unavailable",)
    assert not blocked.accepted
    assert blocked.reason_code == "body_function_unavailable"
    assert scenario.store.read_events() == before_swing_events
    assert scenario.resources().entries[scenario.stamina_resource_id].current == 24

    recovery = scenario.recover_right_arm()
    after_recovery = scenario.affordance()

    assert recovery.committed
    assert after_recovery.overall_status == "available"
    assert after_recovery.path_results[0].blocker_codes == ()


def test_scenario2_insufficient_stamina_blocks_without_action_or_resource_write() -> None:
    scenario = _equipped_scenario(stamina=10)

    affordance = scenario.affordance()
    before = scenario.store.read_events()
    result = scenario.swing_sword()

    assert affordance.overall_status == "blocked"
    assert affordance.path_results[0].blocker_codes == ("resource_insufficient",)
    assert not result.accepted
    assert result.reason_code == "resource_insufficient"
    assert scenario.store.read_events() == before
    assert scenario.resources().entries[scenario.stamina_resource_id].current == 10


def test_scenario2_successful_sword_action_consumes_stamina_and_settles_in_one_batch() -> None:
    scenario = _equipped_scenario(stamina=24)

    result = scenario.swing_sword()

    assert result.accepted
    assert result.append_result is not None and result.append_result.committed
    assert [event.event_type for event in scenario.store.read_transactions()[-1].events] == [
        "gameplay.resource.adjusted",
        "gameplay.action.settled",
    ]
    assert scenario.resources().entries[scenario.stamina_resource_id].current == 12
