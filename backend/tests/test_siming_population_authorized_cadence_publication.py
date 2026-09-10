from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    Facility,
    Plot,
    Recipe,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.organization_government_runtime import (
    OrganizationAuthority,
    WorkerContributionRef,
)
from app.population_continuity.siming_contracts import PopulationOwnerReceipt
from app.services.siming_population_capability import default_population_read_set_builder
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
            selector_revision="selector:generic:task3",
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
