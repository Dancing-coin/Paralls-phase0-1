from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    Facility,
    Plot,
    Recipe,
)
from app.gameplay.closed_generic_gameplay_families import ProductionOutputCertificationIntent
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import ContainerSpec
from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.p5.social_knowledge import SocialFactAuthority
from app.gameplay.organization_government_social_platform_runtime import PopulationSignalMaterializationProposalIntent
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.organization_government_runtime import (
    OrganizationAuthority,
    WorkerContributionRef,
)
from app.population_continuity.source_inputs import OrganizationScheduleInput
from app.population_continuity.batch import PopulationPlanner
from app.population_continuity.siming_contracts import PopulationOwnerReceipt
from app.services.siming_population_capability import default_population_read_set_builder
from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationProjection, PopulationReadSet
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
    assert events[0].payload["population_cadence"]["cadence_id"].endswith("game-start:v4")


def test_game_start_upgrade_preserves_v3_audit_and_restarts_on_same_sqlite(tmp_path, monkeypatch) -> None:
    import app.main as main
    from app.models.behavior_turn import BehaviorTurnRecordRequest, BehaviorTurnStageRecord
    from app.models.siming_heavenly_graph import GraphProvenance, GraphRevisionVector, HeavenlyGraphScope, HeavenlyNodeQuery
    from app.services.behavior_turn_recorder import BehaviorTurnRecorder
    from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter

    database_path = str(tmp_path / "upgrade.sqlite3")
    scope = HeavenlyGraphScope(world_id="world:demo", session_id="session:demo", story_branch_id="branch:main")
    legacy_correlation = "population:bakery-district:game-start:v3"
    # 预置升级必须保留的旧版审计键，避免回归测试依赖 Git 或历史源码。
    legacy_request = BehaviorTurnRecordRequest(
        turn_id=f"siming:{legacy_correlation}", scope=scope,
        valid_at=1, recorded_at=1, policy_revision="policy:siming-runtime:v1",
        source_revision_vector=GraphRevisionVector(source_revision=1), scope_digest="scope:siming-authority",
        provenance=GraphProvenance(
            source_kind="authority_event", source_ref="event:population-cadence:game-start:v3",
            causation_id="game-start:bakery", correlation_id=legacy_correlation, producer_system="siming_runtime",
        ),
        transaction_id=f"siming-behavior-turn:{legacy_correlation}",
        idempotency_key=f"siming-behavior-turn:{legacy_correlation}",
        stages=(BehaviorTurnStageRecord(stage="context", payload={
            "population_cadence": {"cadence_id": "cadence:bakery-district:game-start:v3", "selector_revision": "selector:population:v1"},
        }),),
    )
    legacy_graph = SQLiteHeavenlyGraphAdapter(database_path)
    try:
        assert BehaviorTurnRecorder(legacy_graph).record(legacy_request).applied
        legacy_nodes = legacy_graph.query_nodes(HeavenlyNodeQuery(scope=scope, valid_at=10))
    finally:
        legacy_graph.close()

    try:
        with monkeypatch.context() as patch:
            patch.setattr(main.settings, "heavenly_graph_path", database_path)
            first_start_nodes = None
            for _ in range(2):
                main.reset_runtime_state()
                events = main.authority_event_bus.list_events(event_type="population_cadence_event", include_realtime=True, current_only=False)
                assert len(events) == 1
                event = events[0]
                assert event.correlation_id == "population:bakery-district:game-start:v4"
                assert event.payload["population_cadence"]["cadence_id"] == "cadence:bakery-district:game-start:v4"
                assert event.payload["population_cadence"]["selector_revision"] == "selector:generic:population:v1"
                nodes = main.heavenly_graph.query_nodes(HeavenlyNodeQuery(scope=scope, valid_at=10, limit=None))
                assert all(node in nodes for node in legacy_nodes)
                assert BehaviorTurnRecorder(main.heavenly_graph).record(legacy_request).replayed
                assert any(node.attributes.get("correlation_id") == event.correlation_id for node in nodes)
                if first_start_nodes is not None:
                    assert nodes == first_start_nodes
                first_start_nodes = nodes
    finally:
        main.reset_runtime_state()


def test_population_read_set_accepts_current_source_vector_subset() -> None:
    cadence = _cadence().model_copy(
        update={
            "base_revision_vector": {
                "gameplay:organization:org:test": 1,
                "gameplay:inventory:organization:test": 1,
            }
        }
    )
    projection = PopulationProjection(
        ref="projection:inventory:test",
        scope="organization:summary",
        revision_vector={"gameplay:inventory:organization:test": 1},
        payload={"actor_ref": "character:worker", "candidate_kind": "inventory_output_custody"},
    )
    read_set = PopulationReadSet.from_inputs(cadence, (projection,))
    assert PopulationPlanner._valid_population_read_set(read_set)


@pytest.mark.parametrize("revision_vector", ({"gameplay:inventory:organization:test": 0}, {}))
def test_population_read_set_rejects_stale_or_missing_source_pin(
    revision_vector: dict[str, int],
) -> None:
    cadence = _cadence().model_copy(
        update={
            "base_revision_vector": {
                "gameplay:organization:org:test": 1,
                "gameplay:inventory:organization:test": 1,
            }
        }
    )
    projection = PopulationProjection(
        ref="projection:inventory:test",
        scope="organization:summary",
        revision_vector=revision_vector,
        payload={"actor_ref": "character:worker", "candidate_kind": "inventory_output_custody"},
    )
    read_set = PopulationReadSet.from_inputs(cadence, (projection,))
    assert not PopulationPlanner._valid_population_read_set(read_set)


def _task4_cadence(
    *,
    source_ref: str,
    source_revision: int,
    base_revision_vector: dict[str, int],
    cadence_id: str,
    report_scope: str = "organization:summary",
) -> PopulationCadenceInput:
    return PopulationCadenceInput(
        cadence_id=cadence_id,
        world_ref="world:task4",
        world_mode_ref="world-mode:task4",
        world_mode_revision="mode:task4:v1",
        cadence_source_ref=source_ref,
        cadence_source_revision=source_revision,
        window_start=1,
        window_end=2,
        base_checkpoint_ref=f"checkpoint:{cadence_id}",
        base_checkpoint_digest=f"sha256:{cadence_id}",
        base_revision_vector=base_revision_vector,
        policy_revision="policy:population:v1",
        selector_revision="selector:generic:population:v1",
        ruleset_revision="rules:population:v1",
        deterministic_seed=f"seed:{cadence_id}",
        catch_up_limit=1,
        budget=1,
        report_scope=report_scope,
    )


def _organization_authorized_cadence_fixture(*, cadence_id: str) -> tuple[object, GameplayEventStore, dict[str, object], str, int]:
    import app.main as main

    main.reset_runtime_state()
    store = main.gameplay_event_store
    organization = OrganizationAuthority(
        store=store, package_registry=main.production_package_registry
    )
    schedule = organization.record_schedule(
        command_id=f"task4:{cadence_id}:schedule",
        organization_ref="org:task4-bakery",
        recipient_ref="character:worker",
        membership_ref=f"membership:{cadence_id}",
        assignment_ref=f"assignment:{cadence_id}",
        role="baker",
        shift_ref=f"shift:{cadence_id}",
        operating_window_ref=f"window:{cadence_id}",
        work_order_ref="work:task4-bread",
        effective_from="2026-09-01T00:00:00Z",
        effective_to=None,
        visibility_scope="organization:summary",
    )
    assert schedule.committed, schedule.failure
    organization_stream = "gameplay:organization:org:task4-bakery"
    organization_revision = store.get_stream_head(organization_stream)
    view = organization.schedule_view_for(
        organization_ref="org:task4-bakery",
        recipient_ref="character:worker",
        observed_at="2026-09-10T12:00:00Z",
    )
    organization_projection = OrganizationScheduleInput.freeze(
        recipient_ref="character:worker",
        observed_at="2026-09-10T12:00:00Z",
        view=view,
    ).model_dump(mode="json")
    return main, store, organization_projection, organization_stream, organization_revision


def _inventory_runtime_fixture() -> tuple[object, GameplayEventStore, PopulationCadenceInput, dict[str, object], str]:
    main, store, organization_projection, organization_stream, organization_revision = _organization_authorized_cadence_fixture(
        cadence_id="inventory"
    )
    construction = ConstructionProductionAuthority(
        store=store, package_registry=main.production_package_registry
    )
    facility = Facility(
        facility_ref="facility:task4-bakery",
        plot_ref="plot:task4-bakery",
        facility_kind="bakery",
        condition=1.0,
    )
    assert construction.settle_facility_acquisition(
        plot=Plot(
            plot_ref=facility.plot_ref,
            jurisdiction_ref="jurisdiction:task4",
            owner_ref="organization:bakery",
        ),
        facility=facility,
        command_id="task4:facility",
        idempotency_key="task4:facility",
        causation_id="task4",
        correlation_id="population:task4:inventory",
    ).committed
    recipe = Recipe(
        recipe_ref="recipe:flour-to-bread@1",
        inputs={},
        output_item="item:bread@1",
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    assert construction.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:task4-bakery",
        tick=10,
        command_id="task4:start",
        idempotency_key="task4:start",
        causation_id="task4",
        correlation_id="population:task4:inventory",
    ).committed
    run = construction.projector().runs["run:task4-bakery"]
    assert construction.settle_finish_run(
        run,
        tick=11,
        recipe=recipe,
        command_id="task4:finish",
        idempotency_key="task4:finish",
        causation_id="task4",
        correlation_id="population:task4:inventory",
    ).committed
    finished = store.read_stream("gameplay:construction_production:facility:task4-bakery")[-1]
    certification = construction.settle_production_output_certification(
        intent=ProductionOutputCertificationIntent(
            run_finished_event_id=finished.event_id,
            expected_run_finished_revision=3,
            expected_stream_revision=3,
            expected_facility_revision=0,
            command_id="task4:certification",
            causation_id=finished.event_id,
            correlation_id="population:task4:inventory",
            submitted_at="2026-09-10T12:00:00Z",
        )
    )
    assert certification.committed, certification.failure
    certification_event_id = certification.committed_event_ids[0]
    container = main.inventory_authority_service.create_container(
        command_id="task4:inventory-container",
        actor_ref="organization:bakery",
        spec=ContainerSpec(
            container_id="container:organization:bakery:production-output",
            capacity_weight=100,
            capacity_volume=100,
            capacity_slots=4,
        ),
        idempotency_key="task4:inventory-container",
        causation_id="task4",
        correlation_id="population:task4:inventory",
    )
    assert container.committed, container.failure
    certification_stream = finished.stream_id
    certification_revision = store.get_stream_head(certification_stream)
    cadence = _task4_cadence(
        source_ref=organization_stream,
        source_revision=organization_revision,
        base_revision_vector={
            organization_stream: organization_revision,
            certification_stream: certification_revision,
        },
        cadence_id="cadence:task4:inventory",
    )
    return main, store, cadence, organization_projection, certification_event_id


def test_certified_output_enters_authorized_cadence_and_uses_inventory_owner() -> None:
    main, store, cadence, organization_projection, _ = _inventory_runtime_fixture()
    event = main.publish_authorized_population_cadence(
        cadence=cadence,
        store=store,
        organization_projection=organization_projection,
        room_id="room:task4",
        scene_id="scene:task4",
        zone_id="zone:task4",
        causation_id="task4:inventory",
        correlation_id="population:task4:inventory",
    )
    assert event is not None
    assert any(
        item["payload"]["candidate_kind"] == "inventory_output_custody"
        for item in event.payload["population_projections"]
    )
    audits = main.siming_audit_writer.find_by_correlation(
        room_id="room:task4", correlation_id="population:task4:inventory"
    )
    assert any("status=accepted" in audit.reason and "owners=1" in audit.reason for audit in audits)
    owner_events = [
        item
        for item in store.read_events()
        if item.event_type == "gameplay.inventory.production_output_received@1"
    ]
    assert len(owner_events) == 1


def _social_runtime_fixture(*, private: bool = False) -> tuple[object, GameplayEventStore, PopulationCadenceInput, dict[str, object]]:
    main, store, organization_projection, organization_stream, organization_revision = _organization_authorized_cadence_fixture(
        cadence_id="social-private" if private else "social-public"
    )
    if private:
        signal_stream = "gameplay:social:population:signal:task4-private@1"
        _commit(
            store,
            event_id="event:task4:private-signal",
            event_type="gameplay.social.population_signal_recorded@1",
            stream_id=signal_stream,
            payload={
                "signal_ref": "signal:task4-private@1",
                "provenance_ref": "provenance:task4-private@1",
                "source_revision_pin": 1,
                "materialization_state": "proposed",
                "visibility_scope": "actor_private",
            },
            visibility_policy="actor:character:worker",
        )
        cadence = _task4_cadence(
            source_ref=signal_stream,
            source_revision=1,
            base_revision_vector={signal_stream: 1},
            cadence_id="cadence:task4:social-private",
            report_scope="public",
        )
        return main, store, cadence, organization_projection

    signal_ref = "signal:task4-public@1"
    social = SocialFactAuthority(
        registry=main.production_social_policy_registry,
        store=store,
        package_registry=main.production_package_registry,
    )
    result = social.record_admitted_population_signal_materialization_proposal(
        intent=PopulationSignalMaterializationProposalIntent(
            signal_ref=signal_ref,
            provenance_ref="provenance:task4-public@1",
            source_revision_pin=1,
            materialization_state="proposed",
            visibility_scope="public",
        ),
        binding_ref="binding:population-materialization@1",
        command_id="task4:social-source",
        idempotency_key=f"social:population-signal:{signal_ref}:1:v1",
        causation_id="task4:social-source",
        correlation_id="population:task4:social",
        expected_revision=0,
    )
    assert result.resolution.result_kind == "committed_success"
    source_stream = f"gameplay:social:population:{signal_ref}"
    cadence = _task4_cadence(
        source_ref=organization_stream,
        source_revision=organization_revision,
        base_revision_vector={
            organization_stream: organization_revision,
            source_stream: 1,
        },
        cadence_id="cadence:task4:social-public",
    )
    return main, store, cadence, organization_projection


def test_public_population_signal_enters_authorized_cadence_and_uses_social_owner() -> None:
    main, store, cadence, organization_projection = _social_runtime_fixture()
    event = main.publish_authorized_population_cadence(
        cadence=cadence,
        store=store,
        organization_projection=organization_projection,
        room_id="room:task4",
        scene_id="scene:task4",
        zone_id="zone:task4",
        causation_id="task4:social",
        correlation_id="population:task4:social",
    )
    assert event is not None
    assert any(
        item["payload"]["candidate_kind"] == "social_population_signal"
        for item in event.payload["population_projections"]
    )
    audits = main.siming_audit_writer.find_by_correlation(
        room_id="room:task4", correlation_id="population:task4:social"
    )
    assert any("status=accepted" in audit.reason and "owners=1" in audit.reason for audit in audits)
    owner_events = [
        item
        for item in store.read_events()
        if item.event_type == "gameplay.social.population_signal_recorded@1"
        and item.stream_id == "gameplay:social:population:signal:task4-public@1"
    ]
    assert len(owner_events) == 1


def test_private_social_signal_never_publishes_population_cadence_candidate() -> None:
    main, store, cadence, organization_projection = _social_runtime_fixture(private=True)
    assert main.publish_authorized_population_cadence(
        cadence=cadence,
        store=store,
        organization_projection=organization_projection,
        room_id="room:task4",
        scene_id="scene:task4",
        zone_id="zone:task4",
        causation_id="task4:social-private",
        correlation_id="population:task4:social-private",
    ) is None
    assert not main.authority_event_bus.list_events(
        event_type="population_cadence_event",
        room_id="room:task4",
        include_realtime=True,
        current_only=False,
    )


def _tax_runtime_fixture() -> tuple[object, GameplayEventStore, PopulationCadenceInput, dict[str, object]]:
    main, store, organization_projection, organization_stream, organization_revision = _organization_authorized_cadence_fixture(
        cadence_id="tax"
    )
    economy = EconomyAuthorityService(store=store)
    due = economy.record_tax_due(
        command_id="task5:tax-due",
        organization_ref="org:task4-bakery",
        period_ref="period:2026-09",
        assessed_amount_minor=27,
        policy_revision="policy:commercial@7",
        policy_digest="sha256:commercial-policy",
        due_calendar_ref="calendar:monthly",
        evidence_refs=("evidence:task5-taxable",),
        source_digest="sha256:task5-tax-source",
        idempotency_key="task5:tax-due",
        causation_id="task5",
        correlation_id="population:task5:tax",
    )
    assert due.committed, due.failure
    due_event = store.read_events()[-1]
    opened = economy.open_tax_obligation(
        command_id="task5:tax-open",
        tax_due_event_id=due_event.event_id,
        due_tick=10,
        idempotency_key="task5:tax-open",
        causation_id=due_event.event_id,
        correlation_id="population:task5:tax",
        expected_revision=1,
    )
    assert opened.committed, opened.append_result.failure
    economy_revision = store.get_stream_head("gameplay:economy")
    tax_projection = economy.tax_population_pressure_projection_for(
        organization_ref="org:task4-bakery",
        recipient_ref=str(organization_projection["recipient_ref"]),
    )
    assert tax_projection is not None
    organization_projection = {
        **organization_projection,
        "_tax_projection": tax_projection,
    }
    cadence = _task4_cadence(
        source_ref=organization_stream,
        source_revision=organization_revision,
        base_revision_vector={
            organization_stream: organization_revision,
            "gameplay:economy": economy_revision,
        },
        cadence_id="cadence:task5:tax",
        report_scope="organization:summary",
    )
    return main, store, cadence, organization_projection


def test_tax_due_enters_authorized_cadence_as_report_only_pressure() -> None:
    main, store, cadence, organization_projection = _tax_runtime_fixture()
    event = main.publish_authorized_population_cadence(
        cadence=cadence,
        store=store,
        organization_projection=organization_projection,
        room_id="room:task5",
        scene_id="scene:task5",
        zone_id="zone:task5",
        causation_id="task5:tax",
        correlation_id="population:task5:tax",
    )
    assert event is not None
    tax = next(
        item
        for item in event.payload["population_projections"]
        if item["payload"]["candidate_kind"] == "tax_pressure"
    )
    read_set = default_population_read_set_builder(
        event, PopulationCadenceInput.from_authority_event(event)
    )
    serialized = json.dumps(read_set.model_dump(mode="json"), sort_keys=True)
    assert "amount_minor" not in serialized
    assert "account:" not in serialized
    assert "evidence:" not in serialized
    audits = main.siming_audit_writer.find_by_correlation(
        room_id="room:task5", correlation_id="population:task5:tax"
    )
    assert any("status=accepted" in audit.reason and "owners=0" in audit.reason for audit in audits)
    assert not any(
        item.event_type == "gameplay.economy.tax_obligation_settled"
        for item in store.read_events()
    )


@dataclass
class _ProductionRuntimeFixture:
    stale_organization_revision: bool = False

    def __post_init__(self) -> None:
        import app.main as main

        main.reset_runtime_state()
        self.main = main
        self.store = main.gameplay_event_store
        self.organization = OrganizationAuthority(store=self.store)
        self.production = ConstructionProductionAuthority(store=self.store)
        self.correlation_id = "population:task3:production"
        self._owner_receipt: PopulationOwnerReceipt | None = None
        self._setup_private_completed_evidence()
        self.authorization_stream = "gameplay:organization:org:task3-bakery"
        self.authorization_revision = 4

    def _setup_private_completed_evidence(self) -> None:
        observed_at = "2026-09-10T12:00:00Z"
        self.organization.record_schedule(
            command_id="task3:schedule",
            organization_ref="org:task3-bakery",
            recipient_ref="character:char_b",
            membership_ref="membership:task3",
            assignment_ref="assignment:task3",
            role="baker",
            shift_ref="shift:task3",
            operating_window_ref="window:task3",
            work_order_ref="work:task3-bread",
            effective_from="2026-09-01T00:00:00Z",
            effective_to=None,
            visibility_scope="organization:summary",
        )
        facility = Facility(
            facility_ref="facility:task3-bakery",
            plot_ref="plot:task3-bakery",
            facility_kind="oven",
            condition=1.0,
        )
        assert self.production.settle_facility_acquisition(
            plot=Plot(
                plot_ref="plot:task3-bakery",
                jurisdiction_ref="jurisdiction:task3",
                owner_ref="org:task3-bakery",
            ),
            facility=facility,
            command_id="task3:facility",
            idempotency_key="task3:facility",
            causation_id="task3",
            correlation_id=self.correlation_id,
        ).committed
        contribution = WorkerContributionRef(
            actor_ref="character:char_b",
            assignment_ref="assignment:task3",
            work_order_ref="work:task3-bread",
            evidence_refs=("evidence:task3-input",),
            contribution_digest="sha256:task3-contribution",
        )
        recipe = Recipe(
            recipe_ref="recipe:task3-bread",
            inputs={},
            output_item="item:task3-bread",
            duration_ticks=1,
        )
        assert self.production.settle_start_run(
            facility=facility,
            recipe=recipe,
            run_ref="run:task3-bread",
            tick=1,
            command_id="task3:start",
            idempotency_key="task3:start",
            causation_id="task3",
            correlation_id=self.correlation_id,
            worker_contribution_refs=(contribution,),
        ).committed
        run = self.production.projector().runs["run:task3-bread"]
        assert self.production.settle_finish_run(
            run,
            tick=2,
            recipe=recipe,
            command_id="task3:finish",
            idempotency_key="task3:finish",
            causation_id="task3",
            correlation_id=self.correlation_id,
        ).committed
        evidence = self.production.record_completed_work_evidence(
            run_ref="run:task3-bread",
            contribution=contribution,
            evidence_ref="evidence:production-completed:run:task3-bread:sha256:task3-contribution",
            observed_at=observed_at,
            command_id="task3:evidence",
            idempotency_key="task3:evidence",
            causation_id="task3",
            correlation_id=self.correlation_id,
        )
        assert evidence.committed
        self.evidence_event_id = evidence.committed_event_ids[0]
        self.evidence_stream = "gameplay:construction_production:facility:task3-bakery"

    def _accept_private_evidence(self) -> PopulationOwnerReceipt | None:
        organization_stream = "gameplay:organization:org:task3-bakery"
        organization_revision = self.store.get_stream_head(organization_stream)
        if self.stale_organization_revision:
            organization_revision -= 1
        result = self.organization.accept_production_work_contribution(
            organization_ref="org:task3-bakery",
            source_evidence_event_id=self.evidence_event_id,
            expected_source_stream_revision=self.store.get_stream_head(self.evidence_stream),
            expected_organization_stream_revision=organization_revision,
            command_id="task3:accept",
            idempotency_key=(
                "organization:production-work-contribution:org:task3-bakery:"
                f"{self.evidence_event_id}:{self.store.get_stream_head(self.evidence_stream)}:"
                "event:task3:schedule:4:4:v1"
            ),
            causation_id="task3:private-evidence",
            correlation_id=self.correlation_id,
        )
        if not result.committed:
            return None
        receipt = PopulationOwnerReceipt(
            receipt_ref=result.committed_event_ids[0],
            owner_ref="actor_gameplay.organization_domain",
            event_family="gameplay.organization.production_work_contribution_accepted",
            committed=True,
            revision_vector=dict(result.resulting_stream_revisions),
            zero_write=False,
            idempotency_status=result.idempotency_status,
        )
        return receipt

    def _organization_projection(self) -> dict[str, object]:
        view = self.organization.work_contribution_acceptance_view_for(
            organization_ref="org:task3-bakery"
        )
        return {
            "scope": "organization:summary",
            "organization_ref": "org:task3-bakery",
            "source_revision_vector": dict(view.source_revision_vector),
            "acceptance_rows": list(view.acceptance_rows),
        }

    def _cadence(self, receipt: PopulationOwnerReceipt, *, suffix: str) -> PopulationCadenceInput:
        return PopulationCadenceInput(
            cadence_id=f"cadence:task3:{suffix}",
            world_ref="world:task3",
            world_mode_ref="world-mode:task3",
            world_mode_revision="mode:task3:v1",
            cadence_source_ref=self.authorization_stream,
            cadence_source_revision=self.authorization_revision,
            window_start=10,
            window_end=11,
            base_checkpoint_ref="checkpoint:task3",
            base_checkpoint_digest="sha256:task3",
            base_revision_vector=dict(receipt.revision_vector),
            policy_revision="policy:population:v1",
            selector_revision="selector:generic:population:v1",
            ruleset_revision="rules:population:v1",
            deterministic_seed=f"seed:task3:{suffix}",
            catch_up_limit=1,
            budget=1,
            report_scope="organization:summary",
        )

    def publish_authorized_cadence_after_completed_work(self):
        receipt = self._accept_private_evidence()
        if receipt is None:
            return None
        self._owner_receipt = receipt
        return self.publish_receipt_authorized_cadence(receipt, suffix="first")

    def publish_receipt_authorized_cadence(
        self, receipt: PopulationOwnerReceipt, *, suffix: str = "next"
    ):
        return self.main.publish_authorized_population_cadence(
            cadence=self._cadence(receipt, suffix=suffix),
            store=self.store,
            organization_projection=self._organization_projection(),
            room_id="room:task3",
            scene_id="scene:task3",
            zone_id="zone:task3",
            causation_id=receipt.receipt_ref,
            correlation_id=self.correlation_id,
            population_owner_receipt=receipt,
        )

    def population_cycle_audit_for(self, event_id: str) -> dict[str, object]:
        audit = next(
            item
            for item in self.main.siming_audit_writer.find_by_correlation(
                room_id="room:task3", correlation_id=self.correlation_id
            )
            if item.source_event_id == event_id and item.reason.startswith("population_cycle")
        )
        owner_events = [
            event
            for event in self.store.read_events()
            if event.event_type
            == "gameplay.organization.production_work_contribution_accepted"
            and event.correlation_id == self.correlation_id
        ]
        return {
            "status": "accepted" if "status=accepted" in audit.reason else "requeue",
            "owner_event_family": owner_events[0].event_type if len(owner_events) == 1 else "",
            "owner_receipt_count": len(owner_events),
            "continuity_receipt_count": int("receipts=1" in audit.reason),
        }

    def owner_receipt_for(self, _event_id: str) -> PopulationOwnerReceipt:
        assert self._owner_receipt is not None
        return self._owner_receipt

    def read_set_for(self, event_id: str):
        event = next(
            item
            for item in self.main.authority_event_bus.list_events(
                event_type="population_cadence_event", include_realtime=True, current_only=False
            )
            if item.event_id == event_id
        )
        return default_population_read_set_builder(
            event, PopulationCadenceInput.from_authority_event(event)
        )

    def owner_write_count(self) -> int:
        return sum(
            event.event_type == "gameplay.organization.production_work_contribution_accepted"
            for event in self.store.read_events()
        )

    def population_cadence_event_count(self) -> int:
        return sum(
            event.correlation_id == self.correlation_id
            for event in self.main.authority_event_bus.list_events(
                event_type="population_cadence_event", include_realtime=True, current_only=False
            )
        )

    def continuity_receipt_count(self) -> int:
        return sum(
            item.source_event_id.startswith("event:population-cadence:cadence:task3:")
            and item.reason.startswith("population_cycle")
            and "receipts=1" in item.reason
            for item in self.main.siming_audit_writer.find_by_correlation(
                room_id="room:task3", correlation_id=self.correlation_id
            )
        )


def production_runtime_fixture(
    *, stale_organization_revision: bool = False
) -> _ProductionRuntimeFixture:
    return _ProductionRuntimeFixture(stale_organization_revision=stale_organization_revision)


def test_committed_work_evidence_runs_through_real_authorized_cadence() -> None:
    fixture = production_runtime_fixture()
    event = fixture.publish_authorized_cadence_after_completed_work()
    assert event is not None
    cycle = fixture.population_cycle_audit_for(event.event_id)
    assert cycle["status"] == "accepted"
    assert cycle["owner_event_family"] == "gameplay.organization.production_work_contribution_accepted"
    assert cycle["owner_receipt_count"] == 1
    assert cycle["continuity_receipt_count"] == 1


def test_production_owner_rejection_publishes_no_follow_up_cadence() -> None:
    fixture = production_runtime_fixture(stale_organization_revision=True)
    assert fixture.publish_authorized_cadence_after_completed_work() is None
    assert fixture.population_cadence_event_count() == 0
    assert fixture.owner_write_count() == 0
    assert fixture.continuity_receipt_count() == 0


def test_production_receipt_is_the_only_next_batch_source() -> None:
    fixture = production_runtime_fixture()
    first = fixture.publish_authorized_cadence_after_completed_work()
    assert first is not None
    receipt = fixture.owner_receipt_for(first.event_id)
    second = fixture.publish_receipt_authorized_cadence(receipt)
    assert second is not None
    read_set = fixture.read_set_for(second.event_id)
    assert read_set.cadence.cadence_source_ref == fixture.authorization_stream
    assert read_set.cadence.cadence_source_revision < read_set.cadence.base_revision_vector[
        fixture.authorization_stream
    ]
    assert read_set.projections[0].payload["source_owner_receipt_ref"] == receipt.receipt_ref
    assert fixture.owner_write_count() == 1


def test_unmatched_owner_receipt_publishes_no_cadence_event() -> None:
    fixture = production_runtime_fixture()
    first = fixture.publish_authorized_cadence_after_completed_work()
    assert first is not None
    receipt = fixture.owner_receipt_for(first.event_id).model_copy(
        update={"receipt_ref": "receipt:forged"}
    )

    assert fixture.main.publish_authorized_population_cadence(
        cadence=fixture._cadence(fixture.owner_receipt_for(first.event_id), suffix="forged"),
        store=fixture.store,
        organization_projection=fixture._organization_projection(),
        room_id="room:task3",
        scene_id="scene:task3",
        zone_id="zone:task3",
        causation_id="receipt:forged",
        correlation_id=fixture.correlation_id,
        population_owner_receipt=receipt,
    ) is None
    assert fixture.population_cadence_event_count() == 1


@pytest.mark.parametrize(
    "receipt_update",
    (
        {"owner_ref": "actor_gameplay.forged_domain"},
        {"event_family": "gameplay.organization.forged"},
        {"receipt_ref": "receipt:forged"},
        {"committed": False},
    ),
)
def test_invalid_equal_revision_receipt_publishes_no_cadence_event(
    receipt_update: dict[str, object],
) -> None:
    import app.main as main

    store = _store()
    main.authority_event_bus = InMemoryAuthorityEventBus()
    receipt = PopulationOwnerReceipt(
        receipt_ref="event:test",
        owner_ref="actor_gameplay.organization_domain",
        event_family="gameplay.organization.production_work_contribution_accepted",
        committed=True,
        revision_vector={"gameplay:organization:org:test": 1},
        zero_write=False,
    ).model_copy(update=receipt_update)

    assert main.publish_authorized_population_cadence(
        cadence=_cadence(),
        store=store,
        organization_projection={
            "scope": "organization:summary",
            "organization_ref": "org:test",
            "source_revision_vector": {"gameplay:organization:org:test": 1},
            "acceptance_rows": ({"event_id": "event:test", "organization_ref": "org:test"},),
        },
        room_id="room:test",
        scene_id="scene:test",
        zone_id="zone:test",
        causation_id="cause:test",
        correlation_id="corr:test",
        population_owner_receipt=receipt,
    ) is None
    assert main.authority_event_bus.list_events(include_realtime=True, current_only=False) == []


@pytest.mark.parametrize(
    ("acceptance_organization", "visibility_policy"),
    (("org:other", "organization:summary"), ("org:test", "project")),
)
def test_receipt_acceptance_must_match_organization_scope(
    acceptance_organization: str,
    visibility_policy: str,
) -> None:
    import app.main as main

    store = GameplayEventStore()
    schedule_stream = "gameplay:organization:org:test"
    acceptance_stream = f"gameplay:organization:{acceptance_organization}"
    _commit(
        store,
        event_id="event:schedule:test",
        event_type="gameplay.organization.work_order_recorded",
        stream_id=schedule_stream,
        payload={"organization_ref": "org:test", "visibility_scope": "organization:summary"},
        visibility_policy="organization:summary",
    )
    _commit(
        store,
        event_id="event:acceptance:test",
        event_type="gameplay.organization.production_work_contribution_accepted",
        stream_id=acceptance_stream,
        payload={"organization_ref": acceptance_organization},
        visibility_policy=visibility_policy,
    )
    base_vector = {
        schedule_stream: store.get_stream_head(schedule_stream),
        acceptance_stream: store.get_stream_head(acceptance_stream),
    }
    cadence = _cadence().model_copy(
        update={
            "cadence_source_ref": schedule_stream,
            "cadence_source_revision": 1,
            "base_revision_vector": base_vector,
        }
    )
    receipt = PopulationOwnerReceipt(
        receipt_ref="event:acceptance:test",
        owner_ref="actor_gameplay.organization_domain",
        event_family="gameplay.organization.production_work_contribution_accepted",
        committed=True,
        revision_vector=base_vector,
        zero_write=False,
    )
    main.authority_event_bus = InMemoryAuthorityEventBus()

    assert main.publish_authorized_population_cadence(
        cadence=cadence,
        store=store,
        organization_projection={
            "scope": "organization:summary",
            "organization_ref": "org:test",
            "source_revision_vector": base_vector,
            "acceptance_rows": (
                {"event_id": "event:acceptance:test", "organization_ref": acceptance_organization},
            ),
        },
        room_id="room:test",
        scene_id="scene:test",
        zone_id="zone:test",
        causation_id="cause:test",
        correlation_id="corr:test",
        population_owner_receipt=receipt,
    ) is None
    assert main.authority_event_bus.list_events(include_realtime=True, current_only=False) == []
