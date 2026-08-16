from __future__ import annotations

from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    Facility,
    Plot,
    Recipe,
)
from app.gameplay import construction_production_runtime
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import WorkerContributionRef
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import build_atomic_event_batch


def _setup() -> tuple[GameplayEventStore, ConstructionProductionAuthority, Facility, Recipe]:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(facility_ref="facility:bakery", plot_ref="plot:bakery", facility_kind="oven", condition=1.0)
    recipe = Recipe(recipe_ref="recipe:bread", inputs={}, output_item="item:bread", duration_ticks=2)
    assert authority.settle_facility_acquisition(
        plot=Plot(plot_ref="plot:bakery", jurisdiction_ref="jurisdiction:bakery", owner_ref="organization:bakery"),
        facility=facility, command_id="facility:acquire", idempotency_key="facility:acquire", causation_id="cause", correlation_id="corr",
    ).committed
    return store, authority, facility, recipe


def _contribution() -> WorkerContributionRef:
    return WorkerContributionRef(
        actor_ref="character:char_b", assignment_ref="assignment:baker", work_order_ref="work:bread",
        evidence_refs=("evidence:input:bread:1",), contribution_digest="sha256:contribution:bread:1",
    )


def _finish_with_contribution() -> tuple[GameplayEventStore, ConstructionProductionAuthority]:
    store, authority, facility, recipe = _setup()
    assert authority.settle_start_run(
        facility=facility, recipe=recipe, run_ref="run:bread:1", tick=1,
        command_id="run:start", idempotency_key="run:start", causation_id="cause", correlation_id="corr",
        worker_contribution_refs=(_contribution(),),
    ).committed
    run = authority.projector().runs["run:bread:1"]
    assert authority.settle_finish_run(
        run, tick=3, recipe=recipe, command_id="run:finish", idempotency_key="run:finish", causation_id="cause", correlation_id="corr",
    ).committed
    return store, authority


def _evidence_kwargs(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "run_ref": "run:bread:1",
        "contribution": _contribution(),
        "evidence_ref": "evidence:production-completed:run:bread:1:sha256:contribution:bread:1",
        "observed_at": "2026-08-13T00:00:00Z",
        "command_id": "evidence:1",
        "idempotency_key": "evidence:1",
        "causation_id": "cause",
        "correlation_id": "corr",
    }
    values.update(overrides)
    return values


def _replay_events_into_store(events: list[object]) -> GameplayEventStore:
    replayed = GameplayEventStore()
    for index, event in enumerate(events, start=1):
        batch = build_atomic_event_batch(
            command_id=f"replay:{index}",
            principal_ref="actor_gameplay.construction_production_domain",
            stream_id=event.stream_id,
            expected_revision=replayed.get_stream_head(event.stream_id),
            event_specs=[(event.event_type, event.payload)],
            idempotency_key=f"replay:{index}",
            causation_id="replay",
            correlation_id="replay",
        ).model_copy(
            update={
                "events": [
                    event.model_copy(
                        update={
                            "stream_revision": 0,
                            "global_sequence": 0,
                            "transaction_id": f"transaction:replay:{index}",
                            "command_id": f"replay:{index}",
                        },
                        deep=True,
                    )
                ]
            },
            deep=True,
        )
        assert replayed.append_batch(batch).committed
    return replayed


def test_inf4z_production_start_commits_worker_contribution_linkage() -> None:
    store, authority, facility, recipe = _setup()

    assert authority.settle_start_run(
        facility=facility, recipe=recipe, run_ref="run:bread:1", tick=1,
        command_id="run:start", idempotency_key="run:start", causation_id="cause", correlation_id="corr",
        worker_contribution_refs=(_contribution(),),
    ).committed

    run = authority.projector().runs["run:bread:1"]
    assert run.worker_contribution_refs == ("sha256:contribution:bread:1",)
    event = [item for item in store.read_events() if item.event_type.endswith("run_started")][0]
    assert event.payload["worker_contributions"][0]["work_order_ref"] == "work:bread"


def test_inf4z_production_completed_evidence_requires_committed_finished_run() -> None:
    store, authority, facility, recipe = _setup()
    assert authority.settle_start_run(
        facility=facility, recipe=recipe, run_ref="run:bread:1", tick=1,
        command_id="run:start", idempotency_key="run:start", causation_id="cause", correlation_id="corr",
        worker_contribution_refs=(_contribution(),),
    ).committed

    result = authority.record_completed_work_evidence(
        run_ref="run:bread:1", contribution=_contribution(), evidence_ref="evidence:completed:bread:1",
        observed_at="2026-08-13T00:00:00Z", command_id="evidence:1", idempotency_key="evidence:1", causation_id="cause", correlation_id="corr",
    )

    assert result.committed is False
    assert result.failure and result.failure.error_code == "production_evidence_run_not_completed"
    assert len(store.read_events()) == 2


def test_inf4z_production_completed_evidence_has_owner_event_and_scoped_view() -> None:
    store, authority = _finish_with_contribution()

    result = authority.record_completed_work_evidence(**_evidence_kwargs())

    assert result.committed is True
    event = store.read_events()[-1]
    assert event.event_type == "gameplay.construction_production.work_completion_evidence_recorded"
    assert event.stream_id == "gameplay:construction_production:facility:bakery"
    assert event.visibility_policy == "actor:character:char_b"
    own = authority.completed_evidence_view_for(recipient_ref="character:char_b")
    other = authority.completed_evidence_view_for(recipient_ref="character:char_a")
    owner = authority.completed_evidence_view_for(recipient_ref="actor_gameplay.construction_production_domain")
    assert own.evidence_refs == ("evidence:production-completed:run:bread:1:sha256:contribution:bread:1",)
    assert other.evidence_refs == ()
    assert owner.evidence_refs == ("evidence:production-completed:run:bread:1:sha256:contribution:bread:1",)
    assert own.source_revision_vector == {event.stream_id: event.stream_revision}


def test_inf4z_production_evidence_uses_envelope_plan_and_redacted_outbox(monkeypatch) -> None:
    store, authority = _finish_with_contribution()
    seen: list[object] = []
    original = construction_production_runtime.SettlementPlan.from_command_envelope

    def observe(command):
        seen.append(command)
        return original(command)

    monkeypatch.setattr(
        construction_production_runtime.SettlementPlan,
        "from_command_envelope",
        observe,
    )

    assert authority.record_completed_work_evidence(**_evidence_kwargs()).committed

    assert len(seen) == 1
    command = seen[0]
    assert command.principal_ref == "actor_gameplay.construction_production_domain"
    assert command.payload["visibility_policy"] == "actor:character:char_b"
    outbox = store.list_outbox()[-1]
    assert outbox.audience == "actor:character:char_b"
    assert outbox.payload_projection == {
        "run_ref": "run:bread:1",
        "evidence_ref": "evidence:production-completed:run:bread:1:sha256:contribution:bread:1",
    }
    assert "contribution_digest" not in outbox.payload_projection


def test_inf4z_production_evidence_empty_ref_is_zero_write() -> None:
    store, authority = _finish_with_contribution()

    result = authority.record_completed_work_evidence(**_evidence_kwargs(evidence_ref=""))

    assert result.committed is False
    assert result.failure and result.failure.error_code == "production_evidence_ref_required"
    assert len(store.read_events()) == 3


def test_inf4z_production_evidence_untrusted_ref_is_zero_write() -> None:
    store, authority = _finish_with_contribution()

    result = authority.record_completed_work_evidence(
        **_evidence_kwargs(evidence_ref="evidence:actor-declared:bread:1")
    )

    assert result.committed is False
    assert result.failure and result.failure.error_code == "production_evidence_ref_untrusted"
    assert len(store.read_events()) == 3


def test_inf4z_production_evidence_stale_revision_is_zero_write() -> None:
    store, authority = _finish_with_contribution()

    result = authority.record_completed_work_evidence(
        **_evidence_kwargs(expected_stream_revision=0)
    )

    assert result.committed is False
    assert result.failure and result.failure.error_code == "production_evidence_revision_conflict"
    assert len(store.read_events()) == 3


def test_inf4z_production_evidence_mismatched_contribution_is_zero_write() -> None:
    store, authority = _finish_with_contribution()
    bad = _contribution().model_copy(update={"work_order_ref": "work:other"})

    result = authority.record_completed_work_evidence(
        **_evidence_kwargs(
                contribution=bad,
                evidence_ref="evidence:production-completed:run:bread:1:sha256:contribution:bread:1",
            command_id="evidence:bad",
            idempotency_key="evidence:bad",
        )
    )

    assert result.committed is False
    assert result.failure and result.failure.error_code == "production_evidence_contribution_mismatch"
    assert len(store.read_events()) == 3


def test_inf4z_production_evidence_duplicate_replays_same_owner_receipt() -> None:
    store, authority = _finish_with_contribution()
    kwargs = _evidence_kwargs()
    first = authority.record_completed_work_evidence(**kwargs)
    duplicate = authority.record_completed_work_evidence(**kwargs)

    assert first.committed and duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"


def test_inf4z_production_evidence_scoped_view_replays_from_checkpoint_tail() -> None:
    store, authority = _finish_with_contribution()
    assert authority.record_completed_work_evidence(**_evidence_kwargs()).committed
    events = store.read_events()
    replay = GameplayProjectionReplay(projector_id="production-evidence", projector_version="1")
    checkpoint = replay.create_checkpoint(events[:2])
    tail = replay.checkpoint_plus_tail_replay(checkpoint, events[2:])

    assert replay.full_replay(events).projection_hash == tail.projection_hash
    tail_store = _replay_events_into_store(events)
    tail_view = ConstructionProductionAuthority(store=tail_store).completed_evidence_view_for(
        recipient_ref="character:char_b"
    )
    full_view = authority.completed_evidence_view_for(recipient_ref="character:char_b")
    assert full_view.projection_hash == tail_view.projection_hash
    assert full_view.source_revision_vector == tail_view.source_revision_vector


def test_inf4z_production_evidence_changed_duplicate_is_zero_write() -> None:
    store, authority = _finish_with_contribution()
    kwargs = _evidence_kwargs()
    assert authority.record_completed_work_evidence(**kwargs).committed
    changed = authority.record_completed_work_evidence(**{**kwargs, "evidence_ref": "evidence:completed:bread:changed"})

    assert changed.committed is False
    assert changed.failure and changed.failure.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == 4
