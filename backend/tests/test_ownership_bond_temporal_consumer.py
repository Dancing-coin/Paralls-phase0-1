from __future__ import annotations

import json
import importlib.util
from types import SimpleNamespace

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.ownership_runtime import OwnershipAuthorityService
from app.world_runtime.temporal_contracts import TemporalAuthorization


def test_ownership_bond_expiry_consumer_is_available():
    assert importlib.util.find_spec("app.gameplay.ownership_bond_temporal_consumer") is not None


def _consumer(store):
    from app.gameplay.ownership_bond_temporal_consumer import OwnershipBondExpiryConsumer

    return OwnershipBondExpiryConsumer(store=store)


def _driver(store: GameplayEventStore, *, tick: int, authorized: bool = True):
    issuer = "world_runtime.population_cadence:world"
    timeline = "population:world"
    pins = {
        "timeline_id": timeline,
        "temporal_authorization_issuer_ref": issuer,
        "sampled_at": tick,
        "received_at": tick,
        "input_cutoff": tick,
        "confirmation_boundary": tick,
    }
    if authorized:
        grant = TemporalAuthorization(
            authorization_ref="authorization:population-ownership-temporal@1",
            revision="authorization:population-temporal@1",
            issuer_ref=issuer,
            timeline_id=timeline,
            participant_scope=("actor_gameplay.ownership_domain",),
            input_cutoff=tick,
            confirmation_boundary=tick,
            late_input_policy_ref="reject_after_cutoff",
            ordering_policy_ref="source_revision_then_event_ref",
            valid_until=tick,
        )
        pins["temporal_authorizations"] = json.dumps({
            "ownership": {**grant.payload(), "digest": grant.digest},
        })
    return SimpleNamespace(
        current_tick=tick,
        window_size=60,
        catch_up_limit=10,
        clock=SimpleNamespace(timeline=SimpleNamespace(timeline_id=timeline)),
        world_runtime=SimpleNamespace(store=store, mode=SimpleNamespace(world_ref="world"), is_paused=lambda: False),
        require_temporal_authorization=True,
        publish_window=SimpleNamespace(confirmed_time_pins=lambda: pins),
    )


def _seed_due_bond(store: GameplayEventStore, *, expires_at: int = 10) -> None:
    store.append_batch({
        "transaction_id": "tx:source",
        "command_id": "cmd:source",
        "expected_stream_revisions": {"gameplay:test:sources": 0},
        "events": [{
            "event_id": "evt:source", "event_type": "gameplay.test.source_recorded", "schema_version": 1,
            "stream_id": "gameplay:test:sources", "stream_revision": 0, "global_sequence": 0,
            "transaction_id": "tx:source", "command_id": "cmd:source", "causation_id": "evt:seed",
            "correlation_id": "corr:source", "visibility_policy": "authority_only", "payload": {},
        }],
        "idempotency_record": {"principal_ref": "actor:test.source", "idempotency_key": "source",
                               "payload_digest": "sha256:source"},
        "outbox_entries": [], "result_digest": "sha256:source", "projection_refresh_hints": [],
    })
    OwnershipAuthorityService(store=store).grant_bond(
        command_id="cmd:bond", bond_ref="bond:lease", subject_ref="actor:holder", target_ref="asset:mill",
        bond_type="custody", scope="region:north", term_expires_at=expires_at, source_event_ref="evt:source",
        attributes={"capacity": 1}, world_tick=0, expected_ownership_revision=0,
        idempotency_key="bond:lease", causation_id="evt:source", correlation_id="corr:bond",
    )


def test_due_bond_expiry_is_committed_at_confirmed_world_tick_and_retries_stably():
    store = GameplayEventStore()
    _seed_due_bond(store)
    consumer = _consumer(store)
    driver = _driver(store, tick=14)

    consumer.advance(driver)
    consumer.advance(driver)

    expiry_events = [event for event in store.read_events() if event.event_type == "gameplay.ownership.bond_expired"]
    assert len(expiry_events) == 1
    assert expiry_events[0].payload == {"bond_ref": "bond:lease", "world_tick": 14}
    assert consumer.last_errors == ()


@pytest.mark.parametrize("authorized", [False, True])
def test_missing_or_invalid_ownership_grant_makes_no_expiry_write(authorized):
    store = GameplayEventStore()
    _seed_due_bond(store)
    consumer = _consumer(store)
    driver = _driver(store, tick=14, authorized=authorized)
    if authorized:
        pins = driver.publish_window.confirmed_time_pins()
        grants = json.loads(pins["temporal_authorizations"])
        grants["ownership"]["participant_scope"] = ["actor_gameplay.economy_domain"]
        pins["temporal_authorizations"] = json.dumps(grants)

    before = store.export_snapshot()
    consumer.advance(driver)

    assert store.export_snapshot() == before
    assert consumer.last_errors


def test_bond_expiry_is_not_written_before_term_boundary():
    store = GameplayEventStore()
    _seed_due_bond(store)
    consumer = _consumer(store)

    consumer.advance(_driver(store, tick=9))

    assert not any(event.event_type == "gameplay.ownership.bond_expired" for event in store.read_events())
    assert consumer.last_errors == ()


def test_application_cadence_assembly_registers_the_ownership_expiry_consumer(monkeypatch):
    from app import main
    from app.gameplay.ownership_bond_temporal_consumer import OwnershipBondExpiryConsumer

    monkeypatch.setattr(main.settings, "population_runtime_profile", "benchmark_1x")
    main.reset_runtime_state()
    try:
        driver = main._build_population_driver()

        assert driver is not None
        assert isinstance(main._ownership_bond_expiry_consumer, OwnershipBondExpiryConsumer)
        assert main._ownership_bond_expiry_consumer.store is main.gameplay_event_store
    finally:
        main.close_runtime_resources()
