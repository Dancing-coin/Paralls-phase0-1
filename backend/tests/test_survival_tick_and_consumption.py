from __future__ import annotations

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.survival_runtime import NeedDefinition, NeedState, SurvivalAuthority, SurvivalMode, SurvivalPolicy


def test_disabled_and_narrative_modes_do_not_consume_or_decay() -> None:
    definition = NeedDefinition(need_ref="need:food", category="food", decay_per_tick=0.2)
    state = NeedState(need_ref="need:food", value=1, last_tick=0)
    for mode in (SurvivalMode.DISABLED, SurvivalMode.NARRATIVE):
        next_state, plan = SurvivalAuthority.tick(policy=SurvivalPolicy(policy_ref="p", mode=mode, revision="v1"), definition=definition, state=state, tick=5)
        assert next_state == state
        assert plan is None


def test_simulation_tick_is_deterministic_and_yields_proposal_only() -> None:
    definition = NeedDefinition(need_ref="need:food", category="food", decay_per_tick=0.2)
    state = NeedState(need_ref="need:food", value=0.6, last_tick=0)
    policy = SurvivalPolicy(policy_ref="p", mode=SurvivalMode.SIMULATION, revision="v1")
    first = SurvivalAuthority.tick(policy=policy, definition=definition, state=state, tick=1)
    second = SurvivalAuthority.tick(policy=policy, definition=definition, state=state, tick=1)
    assert first == second
    assert first[1] is not None


def test_settle_tick_and_consumption_append_survival_events_only_after_acceptance() -> None:
    store = GameplayEventStore()
    authority = SurvivalAuthority(store=store)
    definition = NeedDefinition(need_ref="need:food", category="food", decay_per_tick=0.2)
    state = NeedState(need_ref="need:food", value=0.6, last_tick=0)
    policy = SurvivalPolicy(policy_ref="p", mode=SurvivalMode.SIMULATION, revision="v1")
    result = authority.settle_tick(
        actor_ref="character:survivor", policy=policy, definition=definition, state=state, tick=1,
        command_id="command:survival:tick:1", idempotency_key="idem:survival:tick:1",
        causation_id="cause:survival:tick:1", correlation_id="corr:survival:1",
    )
    assert result is not None and result.committed is True
    assert store.read_events()[-1].event_type == "gameplay.survival.need_tick"
    plan = authority.projector().latest_plan
    assert plan is not None
    with pytest.raises(ValueError, match="reservation_required"):
        authority.settle_consumption(
            actor_ref="character:survivor", plan=plan, command_id="command:survival:consume:1",
            idempotency_key="idem:survival:consume:1", causation_id="cause:survival:consume:1",
            correlation_id="corr:survival:1", accepted_reservation_refs=(),
        )
    assert len(store.read_events()) == 1
