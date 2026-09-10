from __future__ import annotations

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationProjection
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
                    "event_type": "gameplay.organization.work_order_recorded",
                    "schema_version": 1,
                    "stream_id": "gameplay:organization:org:test",
                    "stream_revision": 1,
                    "global_sequence": 1,
                    "transaction_id": "tx:test",
                    "command_id": "cmd:test",
                    "causation_id": "cause:test",
                    "correlation_id": "corr:test",
                    "visibility_policy": "organization:summary",
                    "payload": {
                        "organization_ref": "org:test",
                        "visibility_scope": "organization:summary",
                    },
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


def _commit(
    store: GameplayEventStore,
    *,
    event_id: str,
    event_type: str,
    stream_id: str,
    payload: dict[str, object],
    visibility_policy: str = "project",
) -> None:
    batch = build_atomic_event_batch(
        command_id=f"command:{event_id}",
        principal_ref="test:publisher",
        stream_id=stream_id,
        expected_revision=store.get_stream_head(stream_id),
        event_specs=((event_type, payload),),
        idempotency_key=f"idempotency:{event_id}",
        causation_id=f"causation:{event_id}",
        correlation_id="correlation:publisher",
    )
    batch = batch.model_copy(
        update={
            "events": [
                event.model_copy(update={"visibility_policy": visibility_policy})
                for event in batch.events
            ]
        },
        deep=True,
    )
    assert store.append_batch(batch).committed


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


def test_publisher_includes_assembled_projection_from_multi_stream_vector() -> None:
    import app.main as main

    store = _store()
    evidence_stream = "gameplay:construction_production:facility:test"
    extra_stream = "gameplay:inventory:unrelated"
    _commit(
        store,
        event_id="event:evidence:test",
        event_type="gameplay.construction_production.work_completion_evidence_recorded",
        stream_id=evidence_stream,
        payload={
            "committed": True,
            "evidence_kind": "production-completed",
            "outcome": "completed",
            "verification_state": "verified",
            "actor_ref": "character:worker",
            "assignment_ref": "assignment:test",
            "work_order_ref": "work:test",
            "observed_at": "2026-09-10T12:00:00Z",
        },
        visibility_policy="organization:summary",
    )
    _commit(
        store,
        event_id="event:extra:test",
        event_type="gameplay.inventory.unrelated_recorded",
        stream_id=extra_stream,
        payload={},
    )
    cadence = _cadence().model_copy(
        update={
            "base_revision_vector": {
                "gameplay:organization:org:test": 1,
                evidence_stream: 1,
                extra_stream: 1,
            }
        }
    )
    main.authority_event_bus = InMemoryAuthorityEventBus()

    event = main.publish_authorized_population_cadence(
        cadence=cadence,
        store=store,
        organization_projection={
            "scope": "organization:summary",
            "organization_ref": "org:test",
            "source_revision_vector": {"gameplay:organization:org:test": 1},
            "schedule_event_id": "event:test",
            "schedule_event_revision": 1,
            "schedule": {
                "recipient_ref": "character:worker",
                "assignment_ref": "assignment:test",
                "work_order_ref": "work:test",
            },
        },
        room_id="room:test",
        scene_id="scene:test",
        zone_id="zone:test",
        causation_id="cause:test",
        correlation_id="corr:test",
    )

    assert event is not None
    assert [row["ref"] for row in event.payload["population_projections"]] == [
        "projection:organization-production-work-contribution:event:command:event:evidence:test:1"
    ]


@pytest.mark.parametrize(
    ("event_type", "visibility_policy", "source_payload"),
    (
        (
            "gameplay.inventory.unrelated_recorded",
            "organization:summary",
            {"organization_ref": "org:test", "visibility_scope": "organization:summary"},
        ),
        (
            "gameplay.organization.work_order_recorded",
            "authority_only",
            {"organization_ref": "org:test", "visibility_scope": "authority_only"},
        ),
        (
            "gameplay.organization.work_order_recorded",
            "organization:summary",
            {"organization_ref": "org:other", "visibility_scope": "organization:summary"},
        ),
    ),
)
def test_publisher_rejects_unauthorized_cadence_source(
    event_type: str,
    visibility_policy: str,
    source_payload: dict[str, object],
) -> None:
    import app.main as main

    store = GameplayEventStore()
    _commit(
        store,
        event_id="event:source:test",
        event_type=event_type,
        stream_id="gameplay:organization:org:test",
        payload=source_payload,
        visibility_policy=visibility_policy,
    )
    main.authority_event_bus = InMemoryAuthorityEventBus()

    assert main.publish_authorized_population_cadence(
        cadence=_cadence(),
        store=store,
        organization_projection={
            "organization_ref": "org:test",
            "visibility_scope": "organization:summary",
            "source_revision_vector": {"gameplay:organization:org:test": 1},
        },
        room_id="room:test",
        scene_id="scene:test",
        zone_id="zone:test",
        causation_id="cause:test",
        correlation_id="corr:test",
    ) is None
    assert main.authority_event_bus.list_events(include_realtime=True, current_only=False) == []


def test_publisher_rejects_arbitrary_legacy_projection_payload() -> None:
    import app.main as main

    store = _store()
    main.authority_event_bus = InMemoryAuthorityEventBus()

    assert main.publish_authorized_population_cadence(
        cadence=_cadence(),
        store=store,
        organization_projection={
            "organization_ref": "org:test",
            "visibility_scope": "organization:summary",
            "source_revision_vector": {"gameplay:organization:org:test": 1},
        },
        room_id="room:test",
        scene_id="scene:test",
        zone_id="zone:test",
        causation_id="cause:test",
        correlation_id="corr:test",
        legacy_projections=(
            PopulationProjection(
                ref="projection:forged",
                scope="organization:summary",
                revision_vector={"gameplay:organization:org:test": 1},
                payload={
                    "candidate_kind": "schedule_gated_supply",
                    "owner_ref": "forged:owner",
                },
            ),
        ),
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
