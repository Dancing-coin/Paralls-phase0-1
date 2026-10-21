from __future__ import annotations

from types import SimpleNamespace

import pytest

from app import main


class _Execution:
    def submit(self, fn):
        return fn()


class _Caller:
    def __init__(self):
        self.request = None

    def submit(self, **request):
        self.request = request
        return "random-result"


def test_population_economy_random_application_ingress_uses_confirmed_driver_pins(monkeypatch):
    caller = _Caller()
    driver = SimpleNamespace(
        current_tick=60,
        clock=SimpleNamespace(timeline=SimpleNamespace(timeline_id="population:world")),
        publish_window=SimpleNamespace(confirmed_time_pins=lambda: {
            "timeline_id": "population:world", "sampled_at": 60, "input_cutoff": 60,
            "confirmation_boundary": 60,
        }),
    )
    monkeypatch.setattr(main, "runtime_execution", _Execution())
    monkeypatch.setattr(main, "_mirror_transport_accepting", True)
    monkeypatch.setattr(main, "economy_random_caller", caller)
    monkeypatch.setattr(main, "_population_runtime_driver", driver)

    result = main.submit_population_economy_random(
        policy_ref="policy:economy_lottery@1", operation_ref="lottery:1",
        effect_ref="effect:lottery:1", target_ref="char_a", actor_ref="char_a",
        world_ref="world", timeline_ref="population:world", draw_index=0,
        world_tick=60, idempotency_key="random:1", command_id="cmd:random:1",
        pins=None,
    )

    assert result == "random-result"
    assert caller.request["pins"] == driver.publish_window.confirmed_time_pins()
    assert caller.request["world_tick"] == 60
    assert caller.request["timeline_ref"] == "population:world"


def test_population_economy_random_application_ingress_rejects_stale_tick(monkeypatch):
    caller = _Caller()
    driver = SimpleNamespace(
        current_tick=60,
        clock=SimpleNamespace(timeline=SimpleNamespace(timeline_id="population:world")),
        publish_window=SimpleNamespace(confirmed_time_pins=lambda: {
            "timeline_id": "population:world", "sampled_at": 60, "input_cutoff": 60,
            "confirmation_boundary": 60,
        }),
    )
    monkeypatch.setattr(main, "runtime_execution", _Execution())
    monkeypatch.setattr(main, "_mirror_transport_accepting", True)
    monkeypatch.setattr(main, "economy_random_caller", caller)
    monkeypatch.setattr(main, "_population_runtime_driver", driver)

    with pytest.raises(ValueError, match="economy_random_temporal_pins_stale"):
        main.submit_population_economy_random(
            policy_ref="policy:economy_lottery@1", operation_ref="lottery:stale",
            effect_ref="effect:lottery:stale", target_ref="char_a", actor_ref="char_a",
            world_ref="world", timeline_ref="population:world", draw_index=0,
            world_tick=59, idempotency_key="random:stale", command_id="cmd:random:stale",
            pins=None,
        )
    assert caller.request is None


def test_application_ingress_reaches_population_caller_economy_owner_and_durable_store(
    tmp_path, monkeypatch,
):
    from app.gameplay.event_store import DurableGameplayEventStore
    from app.gameplay.economy_runtime import EconomyAuthorityService
    from app.population_continuity.economy_random_caller import PopulationEconomyRandomCaller
    from test_population_economy_random_caller import _registry, _setup

    store, _world, _publisher, driver = _setup(tmp_path)
    try:
        assert driver.tick(60).published_cadence_ids == ("cadence:world:0",)
        caller = PopulationEconomyRandomCaller(
            store=store,
            registry=_registry(tmp_path),
            authority=EconomyAuthorityService(store=store),
            population_driver=driver,
        )
        monkeypatch.setattr(main, "runtime_execution", _Execution())
        monkeypatch.setattr(main, "_mirror_transport_accepting", True)
        monkeypatch.setattr(main, "economy_random_caller", caller)
        monkeypatch.setattr(main, "_population_runtime_driver", driver)

        result = main.submit_population_economy_random(
            policy_ref="policy:economy_lottery@1", operation_ref="lottery:app:1",
            effect_ref="effect:lottery:app:1", target_ref="char_a", actor_ref="char_a",
            world_ref="world", timeline_ref="population:world", draw_index=0,
            world_tick=60, idempotency_key="random:app:1", command_id="cmd:random:app:1",
            pins=None,
        )

        assert isinstance(store, DurableGameplayEventStore)
        assert result.committed
        assert len(result.committed_event_ids) == 1
        event = store.get_event(result.committed_event_ids[0])
        assert event.event_type == "gameplay.economy.random_result_committed@1"
        assert event.visibility_policy == "authority_only"
        assert event.payload["seed"]
        assert event.payload["result_ref"]
        receipt = caller.authority.lookup_random_business_receipt(
            idempotency_key="random:app:1", scope="authority",
        )
        assert receipt.transaction_id == result.transaction_id
    finally:
        store.close()
