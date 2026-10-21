from __future__ import annotations

from pathlib import Path

from app.gameplay.economy_random_registry import EconomyRandomPolicyRegistry
from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.event_store import DurableGameplayEventStore
from app.population_continuity.economy_random_caller import PopulationEconomyRandomCaller
from app.population_continuity.roster import PopulationRoster
from app.population_continuity.runtime_publication import RuntimeCadencePublisher
from app.population_continuity.world import WorldContinuityRuntime
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.world_runtime.population_driver import PopulationCadenceDriver
from test_population_runtime_driver import _mode


ROOT = Path(__file__).resolve().parents[2]
POLICY_DIR = ROOT / "assets" / "gameplay" / "economy_random"


def _setup(tmp_path: Path):
    store = DurableGameplayEventStore(tmp_path / "random-population.db")
    world = WorldContinuityRuntime(store=store, mode=_mode(), roster=PopulationRoster(actor_ids=("char_a",)))
    assert world.resume().committed
    publisher = RuntimeCadencePublisher(
        world_runtime=world, event_bus=InMemoryAuthorityEventBus(),
        room_id="room", scene_id="scene", zone_id="zone",
    )
    driver = PopulationCadenceDriver(
        world_runtime=world, publish_window=publisher, window_size=60,
        catch_up_limit=1, initial_tick=0,
    )
    driver.require_temporal_authorization = True
    return store, world, publisher, driver


def _registry(tmp_path: Path) -> EconomyRandomPolicyRegistry:
    directory = tmp_path / "policy"
    directory.mkdir()
    for source in POLICY_DIR.glob("*.yaml"):
        content = source.read_text(encoding="utf-8")
        content = content.replace("[char_a, char_b]", "[char_a]")
        content = content.replace("[world:main]", "[world]")
        content = content.replace("[timeline:main]", "[population:world]")
        (directory / source.name).write_text(content, encoding="utf-8")
    return EconomyRandomPolicyRegistry.from_directory(directory)


def test_explicit_random_demand_uses_durable_confirmed_population_read_set(tmp_path: Path):
    store, world, publisher, driver = _setup(tmp_path)
    try:
        assert driver.tick(60).published_cadence_ids == ("cadence:world:0",)
        registry = _registry(tmp_path)
        caller = PopulationEconomyRandomCaller(
            store=store, registry=registry, authority=EconomyAuthorityService(store=store),
            population_driver=driver,
        )
        result = caller.submit(
            policy_ref="policy:economy_lottery@1", operation_ref="lottery:explicit:1",
            effect_ref="effect:lottery:entry-1", target_ref="char_a", actor_ref="char_a",
            world_ref="world", timeline_ref="population:world", draw_index=0, world_tick=60,
            idempotency_key="lottery:explicit:1", command_id="cmd:lottery:explicit:1", pins=None,
        )
        assert result.committed, result.failure
        event = store.get_event(result.committed_event_ids[0])
        assert event.payload["window_ref"] == "cadence:world:0"
        assert event.payload["world_tick"] == 60
        transaction = store.get_transaction(result.transaction_id)
        assert transaction is not None
        assert transaction.read_stream_revisions == {
            "gameplay:economy": transaction.read_stream_revisions["gameplay:economy"],
            "population-cadence:world": store.get_stream_head("population-cadence:world"),
            "population-cadence-revocation:world": 0,
        }
        duplicate = caller.submit(
            policy_ref="policy:economy_lottery@1", operation_ref="lottery:explicit:1",
            effect_ref="effect:lottery:entry-1", target_ref="char_a", actor_ref="char_a",
            world_ref="world", timeline_ref="population:world", draw_index=0, world_tick=60,
            idempotency_key="lottery:explicit:1", command_id="cmd:lottery:explicit:1", pins=None,
        )
        assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
        assert duplicate.committed_event_ids == result.committed_event_ids
    finally:
        store.close()


def test_random_caller_rejects_forged_pins_and_revoked_window_without_economy_write(tmp_path: Path):
    store, world, publisher, driver = _setup(tmp_path)
    try:
        assert driver.tick(60).published_cadence_ids == ("cadence:world:0",)
        caller = PopulationEconomyRandomCaller(
            store=store, registry=_registry(tmp_path), authority=EconomyAuthorityService(store=store),
            population_driver=driver,
        )
        pins = dict(publisher.confirmed_time_pins)
        pins["input_cutoff"] = 61
        rejected = caller.submit(
            policy_ref="policy:economy_lottery@1", operation_ref="lottery:explicit:2",
            effect_ref="effect:lottery:entry-2", target_ref="char_a", actor_ref="char_a",
            world_ref="world", timeline_ref="population:world", draw_index=0, world_tick=60,
            idempotency_key="lottery:explicit:2", command_id="cmd:lottery:explicit:2", pins=pins,
        )
        assert not rejected.committed
        assert store.read_stream("gameplay:economy") == []
        # Existing cadence revoke event is durable source truth. The fixture uses
        # the existing authority contract only to exercise fail-closed behavior.
        publisher.revoke_cadence(cadence_id="cadence:world:0", reason_code="test-revoke",
                                 caller_principal_ref="world_admin")
        rejected = caller.submit(
            policy_ref="policy:economy_lottery@1", operation_ref="lottery:explicit:3",
            effect_ref="effect:lottery:entry-3", target_ref="char_a", actor_ref="char_a",
            world_ref="world", timeline_ref="population:world", draw_index=0, world_tick=60,
            idempotency_key="lottery:explicit:3", command_id="cmd:lottery:explicit:3", pins=None,
        )
        assert not rejected.committed
        assert store.read_stream("gameplay:economy") == []
    finally:
        store.close()


def test_revoke_racing_caller_checks_conflicts_with_economy_append(tmp_path: Path):
    store, world, publisher, driver = _setup(tmp_path)
    try:
        assert driver.tick(60).published_cadence_ids == ("cadence:world:0",)
        caller = PopulationEconomyRandomCaller(
            store=store, registry=_registry(tmp_path), authority=EconomyAuthorityService(store=store),
            population_driver=driver,
        )
        original_read_stream = store.read_stream
        revoked = False

        def revoke_after_head_capture(stream_id: str, *args, **kwargs):
            nonlocal revoked
            result = original_read_stream(stream_id, *args, **kwargs)
            if stream_id == "population-cadence-revocation:world" and not revoked:
                revoked = True
                publisher.revoke_cadence(
                    cadence_id="cadence:world:0", reason_code="race-revoke",
                    caller_principal_ref="world_admin",
                )
            return result

        store.read_stream = revoke_after_head_capture
        rejected = caller.submit(
            policy_ref="policy:economy_lottery@1", operation_ref="lottery:race:1",
            effect_ref="effect:lottery:race-1", target_ref="char_a", actor_ref="char_a",
            world_ref="world", timeline_ref="population:world", draw_index=0, world_tick=60,
            idempotency_key="lottery:race:1", command_id="cmd:lottery:race:1", pins=None,
        )
        assert revoked
        assert not rejected.committed
        assert rejected.failure is not None
        assert rejected.failure.error_code == "economy_random_anchor_conflict"
        assert store.read_stream("gameplay:economy") == []
    finally:
        store.close()
