from __future__ import annotations

import pytest

from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.event_store import DurableGameplayEventStore
from app.population_continuity.economy_random_caller import PopulationEconomyRandomCaller
from app.services.embodied_controller_auth_service import (
    EmbodiedControllerAuthService, EmbodiedControllerEnrollment,
)
from app.services.economy_random_command_service import EconomyRandomCommand, EconomyRandomCommandService
from test_population_economy_random_caller import _setup, _registry


def _auth():
    auth = EmbodiedControllerAuthService()
    secret = auth.create_trusted_local_launch_credential(
        actor_id="char_a", controller_instance_id="controller", issued_at=0, expires_at=5)
    result = auth.bind_controller(EmbodiedControllerEnrollment(
        credential_kind="trusted_local_launch", credential=secret, actor_id="char_a",
        controller_instance_id="controller", protocol_version=1),
        remote_host="127.0.0.1", now=1, connection_ref="connection")
    assert result.accepted
    return auth


def _command():
    return EconomyRandomCommand(request_id="player-explicit-draw-1", actor_ref="char_a",
        policy_ref="policy:economy_lottery@1", world_ref="world",
        timeline_ref="population:world", world_tick=60)


def test_real_controller_explicit_demand_consumes_economy_receipt_and_reopens(tmp_path):
    store, _, _, driver = _setup(tmp_path)
    registry = _registry(tmp_path)
    auth = _auth()
    assert driver.tick(60).published_cadence_ids
    service = EconomyRandomCommandService(store=store, controller_auth=auth,
        caller=PopulationEconomyRandomCaller(store=store, registry=registry, population_driver=driver))
    first = service.submit(_command(), connection_ref="connection")
    trigger = store.get_event(first.trigger_receipt.committed_event_ids[0])
    random = store.get_event(first.economy_receipt.committed_event_ids[0])
    assert trigger.visibility_policy == "authority_only"
    assert random.causation_id == trigger.event_id
    assert first.result_ref == random.payload["result_ref"]
    count = len(store.read_events())
    store.close()
    reopened = DurableGameplayEventStore(tmp_path / "random-population.db")
    try:
        # A new auth instance must be re-enrolled through the existing issuer.
        recovered = EconomyRandomCommandService(store=reopened, controller_auth=_auth(),
            caller=PopulationEconomyRandomCaller(store=reopened, registry=registry))
        duplicate = recovered.submit(_command(), connection_ref="connection")
        assert duplicate.economy_receipt.committed_event_ids == first.economy_receipt.committed_event_ids
        assert duplicate.economy_receipt.idempotency_status == "duplicate_replayed"
        assert duplicate.result_ref == first.result_ref
        assert len(reopened.read_events()) == count
        with pytest.raises(ValueError, match="trigger_identity_conflict"):
            recovered.submit(_command().model_copy(update={"world_tick": 61}), connection_ref="connection")
        assert len(reopened.read_events()) == count
    finally:
        reopened.close()


def test_unbound_or_other_actor_cannot_generate_trigger(tmp_path):
    store, _, _, driver = _setup(tmp_path)
    try:
        service = EconomyRandomCommandService(store=store, controller_auth=_auth(),
            caller=PopulationEconomyRandomCaller(store=store, registry=_registry(tmp_path), population_driver=driver))
        count = len(store.read_events())
        for command, connection in [(_command(), "unknown"),
                (_command().model_copy(update={"actor_ref": "char_b"}), "connection")]:
            with pytest.raises(ValueError, match="controller_binding"):
                service.submit(command, connection_ref=connection)
        assert len(store.read_events()) == count
    finally:
        store.close()


def test_trigger_partial_success_retries_original_operation_without_extra_trigger(tmp_path):
    store, _, _, driver = _setup(tmp_path)
    try:
        assert driver.tick(60).published_cadence_ids
        caller = PopulationEconomyRandomCaller(store=store, registry=_registry(tmp_path), population_driver=driver)
        service = EconomyRandomCommandService(store=store, controller_auth=_auth(), caller=caller)
        original = caller.submit
        def lose_response(**kwargs):
            committed = original(**kwargs)
            assert committed.committed
            raise TimeoutError("response lost after commit")
        caller.submit = lose_response
        with pytest.raises(TimeoutError):
            service.submit(_command(), connection_ref="connection")
        count = len(store.read_events())
        caller.submit = original
        recovered = service.submit(_command(), connection_ref="connection")
        assert recovered.economy_receipt.committed_event_ids
        assert len(store.read_events()) == count
        assert len(store.read_stream("economy-random-commands:char_a")) == 1
    finally:
        store.close()


def test_trigger_committed_owner_not_started_recovers_without_generating_new_demand(tmp_path):
    store, _, _, driver = _setup(tmp_path)
    try:
        assert driver.tick(60).published_cadence_ids
        registry = _registry(tmp_path)
        caller = PopulationEconomyRandomCaller(store=store, registry=registry, population_driver=driver)
        service = EconomyRandomCommandService(store=store, controller_auth=_auth(), caller=caller)
        def interrupted(**kwargs):
            raise TimeoutError("owner not started")
        caller.submit = interrupted
        with pytest.raises(TimeoutError):
            service.submit(_command(), connection_ref="connection")
        assert len(store.read_stream("economy-random-commands:char_a")) == 1
        assert not store.read_stream("gameplay:economy")
        recovered = EconomyRandomCommandService(store=store, controller_auth=_auth(),
            caller=PopulationEconomyRandomCaller(store=store, registry=registry, population_driver=driver))
        result = recovered.submit(_command(), connection_ref="connection")
        assert result.economy_receipt.committed_event_ids
        assert len(store.read_stream("economy-random-commands:char_a")) == 1
    finally:
        store.close()
