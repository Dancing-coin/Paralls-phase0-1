from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.population_continuity.siming_contracts import PopulationCadenceInput
from app.services.authority_event_bus import InMemoryAuthorityEventBus


def _cadence() -> PopulationCadenceInput:
    return PopulationCadenceInput(
        cadence_id="cadence:test",
        world_ref="world:test",
        world_mode_ref="world-mode:test",
        world_mode_revision="mode:test:v1",
        cadence_source_ref="gameplay:organization:org:test",
        cadence_source_revision=1,
        window_start=1,
        window_end=2,
        base_checkpoint_ref="checkpoint:test",
        base_checkpoint_digest="sha256:test",
        base_revision_vector={"gameplay:organization:org:test": 1},
        policy_revision="policy:test",
        selector_revision="selector:test",
        ruleset_revision="rules:test",
        deterministic_seed="seed:test",
        catch_up_limit=1,
        budget=1,
        report_scope="organization:summary",
    )


def _store() -> GameplayEventStore:
    store = GameplayEventStore()
    result = store.append_batch(
        {
            "transaction_id": "tx:test",
            "command_id": "cmd:test",
            "expected_stream_revisions": {"gameplay:organization:org:test": 0},
            "events": [
                {
                    "event_id": "event:test",
                    "event_type": "gameplay.organization.schedule_recorded",
                    "schema_version": 1,
                    "stream_id": "gameplay:organization:org:test",
                    "stream_revision": 1,
                    "global_sequence": 1,
                    "transaction_id": "tx:test",
                    "command_id": "cmd:test",
                    "causation_id": "cause:test",
                    "correlation_id": "corr:test",
                    "visibility_policy": "organization:summary",
                    "payload": {"organization_ref": "org:test"},
                }
            ],
            "idempotency_record": {
                "principal_ref": "authority:test",
                "idempotency_key": "idempotency:test",
                "payload_digest": "sha256:test",
            },
            "result_digest": "sha256:result",
        }
    )
    assert result.committed
    return store


def test_authorized_cadence_publisher_uses_given_cadence_without_minting_time() -> None:
    import app.main as main

    store = _store()
    cadence = _cadence()
    main.authority_event_bus = InMemoryAuthorityEventBus()

    event = main.publish_authorized_population_cadence(
        cadence=cadence,
        store=store,
        organization_projection={
            "organization_ref": "org:test",
            "visibility_scope": "organization:summary",
            "source_revision_vector": dict(cadence.base_revision_vector),
            "schedule_event_id": "event:test",
            "schedule_event_revision": 1,
            "schedules": (),
        },
        room_id="room:test",
        scene_id="scene:test",
        zone_id="zone:test",
        causation_id="cause:test",
        correlation_id="corr:test",
    )

    assert event is not None
    assert event.event_type == "population_cadence_event"
    assert event.payload["population_cadence"] == cadence.model_dump(mode="json")


def test_cadence_publisher_rejects_source_revision_not_in_authorized_vector() -> None:
    import app.main as main

    store = _store()
    cadence = _cadence().model_copy(update={"base_revision_vector": {"gameplay:organization:org:test": 0}})
    main.authority_event_bus = InMemoryAuthorityEventBus()

    assert main.publish_authorized_population_cadence(
        cadence=cadence,
        store=store,
        organization_projection={},
        room_id="room:test",
        scene_id="scene:test",
        zone_id="zone:test",
        causation_id="cause:test",
        correlation_id="corr:test",
    ) is None
    assert main.authority_event_bus.list_events(include_realtime=True, current_only=False) == []


def test_game_start_remains_one_explicit_authorized_cadence() -> None:
    import app.main as main

    main.reset_runtime_state()
    events = main.authority_event_bus.list_events(
        event_type="population_cadence_event", include_realtime=True, current_only=False
    )
    assert len(events) == 1
    assert events[0].payload["population_cadence"]["cadence_id"].endswith("game-start:v3")
