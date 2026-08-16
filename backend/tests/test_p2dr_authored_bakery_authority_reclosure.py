from __future__ import annotations

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Plot, Recipe
from app.gameplay.econ1_economy_runtime import EconomyAuthority, MarketQuote, OperatingWindow, PurchasePosting, WageAccrual
from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyProjector, EconomyRuntimeError
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import OrganizationAuthority, WorkerContributionRef
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.shared_contracts import GameplayCommandEnvelope


ORGANIZATION = "org:bakery-authored"
BAKER = "character:char_b"
COUNTER = "character:char_c"
BAKER_WORK_ORDER = "work:bread"
COUNTER_WORK_ORDER = "work:flour"
OBSERVED_AT = "2026-08-15T09:00:00Z"


def _record_schedule(
    authority: OrganizationAuthority,
    *,
    recipient_ref: str,
    work_order_ref: str,
    organization_ref: str = ORGANIZATION,
    visibility_scope: str | None = None,
) -> None:
    assert authority.record_schedule(
        command_id=f"p2dr:schedule:{recipient_ref}:{work_order_ref}",
        organization_ref=organization_ref,
        recipient_ref=recipient_ref,
        membership_ref=f"membership:{recipient_ref.rsplit(':', 1)[1]}",
        assignment_ref=f"assignment:{recipient_ref.rsplit(':', 1)[1]}",
        role="baker/production" if recipient_ref == BAKER else "counter/procurement",
        shift_ref=f"shift:{recipient_ref.rsplit(':', 1)[1]}",
        operating_window_ref="window:bakery-authored",
        work_order_ref=work_order_ref,
        effective_from="2026-08-15T08:00:00Z",
        effective_to=None,
        visibility_scope=visibility_scope or f"actor:{recipient_ref}",
    ).committed


def _quote() -> MarketQuote:
    return MarketQuote(
        quote_ref="quote:flour:fixed",
        item_ref="item:flour",
        unit_price=5,
        quantity_limit=10,
        valid_until_tick=5,
        public_digest="sha256:quote:flour:fixed",
    )


def _posting() -> PurchasePosting:
    return PurchasePosting(
        posting_ref="purchase:flour:1",
        quote_ref="quote:flour:fixed",
        buyer_ref=ORGANIZATION,
        quantity=2,
        total_amount=10,
    )


def _setup() -> tuple[GameplayEventStore, OrganizationAuthority, EconomyAuthority]:
    store = GameplayEventStore()
    organization = OrganizationAuthority(store=store)
    _record_schedule(organization, recipient_ref=BAKER, work_order_ref=BAKER_WORK_ORDER)
    _record_schedule(organization, recipient_ref=COUNTER, work_order_ref=COUNTER_WORK_ORDER)
    return store, organization, EconomyAuthority(store=store)


def _settle_counter_procurement(
    economy: EconomyAuthority,
    organization: OrganizationAuthority,
    *,
    command_id: str = "p2dr:procurement:1",
    idempotency_key: str = "p2dr:procurement:1",
    schedule=None,
):
    return economy.settle_scheduled_procurement(
        quote=_quote(),
        posting=_posting(),
        organization_schedule=(
            schedule
            if schedule is not None
            else organization.schedule_view_for(
                organization_ref=ORGANIZATION,
                recipient_ref=COUNTER,
                observed_at=OBSERVED_AT,
            )
        ),
        recipient_ref=COUNTER,
        work_order_ref=COUNTER_WORK_ORDER,
        observed_at=OBSERVED_AT,
        tick=1,
        command_id=command_id,
        idempotency_key=idempotency_key,
        causation_id="cause:p2dr:procurement",
        correlation_id="corr:p2dr:window",
    )


def _replay_events_into_store(events: list[object]) -> GameplayEventStore:
    replayed = GameplayEventStore()
    for index, event in enumerate(events, start=1):
        batch = build_atomic_event_batch(
            command_id=f"p2dr:replay:{index}",
            principal_ref="replay:p2dr",
            stream_id=event.stream_id,
            expected_revision=replayed.get_stream_head(event.stream_id),
            event_specs=[(event.event_type, event.payload)],
            idempotency_key=f"p2dr:replay:{index}",
            causation_id="cause:p2dr:replay",
            correlation_id="corr:p2dr:replay",
        ).model_copy(
            update={
                "events": [
                    event.model_copy(
                        update={
                            "stream_revision": 0,
                            "global_sequence": 0,
                            "transaction_id": f"transaction:p2dr:replay:{index}",
                            "command_id": f"p2dr:replay:{index}",
                        },
                        deep=True,
                    )
                ]
            },
            deep=True,
        )
        assert replayed.append_batch(batch).committed
    return replayed


def _wage_open_command(store: GameplayEventStore) -> GameplayCommandEnvelope:
    stream_id = f"gameplay:economy:wage:{BAKER}"
    return GameplayCommandEnvelope(
        command_id="p2dr:wage:open",
        command_type="gameplay.economy.open_wage_obligation",
        command_version=1,
        principal_ref=EconomyAuthority._PRINCIPAL,
        actor_ref=BAKER,
        project_ref=None,
        transaction_id="transaction:p2dr:wage:open",
        idempotency_key="p2dr:wage:open",
        expected_revisions={stream_id: store.get_stream_head(stream_id)},
        causation_id="cause:p2dr:wage",
        correlation_id="corr:p2dr:window",
        source_ref=EconomyAuthority._PRINCIPAL,
        submitted_at=OBSERVED_AT,
        pinned_revisions={"wage_policy": 1},
        payload={"visibility_scope": "project"},
    )


def test_p2dr_uses_existing_authored_counter_schedule_to_commit_procurement() -> None:
    store, organization, economy = _setup()

    registry = CharacterProfileRegistry.from_directory("assets/characters/profiles")
    assert registry.get("char_b") is not None
    assert registry.get("char_c") is not None

    result = _settle_counter_procurement(economy, organization)

    assert result.committed
    event = store.read_events()[-1]
    assert event.event_type == "gameplay.economy.purchase_posted"
    assert event.stream_id == f"gameplay:economy:{ORGANIZATION}"
    assert event.visibility_policy == f"actor:{COUNTER}"
    assert event.payload["work_order_ref"] == COUNTER_WORK_ORDER
    assert event.payload["recipient_ref"] == COUNTER
    assert event.payload["organization_schedule_source_revisions"] == {
        f"gameplay:organization:{ORGANIZATION}": 8
    }
    assert store.read_transactions()[-1].read_stream_revisions == {
        f"gameplay:organization:{ORGANIZATION}": 8
    }
    outbox = store.list_outbox()[-1]
    assert outbox.topic == "economy.procurement_work.scoped_projection"
    assert outbox.audience == f"actor:{COUNTER}"


def test_p2dr_procurement_rejects_forged_or_cross_actor_schedule_without_write() -> None:
    store, organization, economy = _setup()
    forged = organization.schedule_view_for(
        organization_ref=ORGANIZATION,
        recipient_ref=BAKER,
        observed_at=OBSERVED_AT,
    )
    before = len(store.read_events())

    result = _settle_counter_procurement(economy, organization, schedule=forged)

    assert result.committed is False
    assert result.failure and result.failure.error_code == "organization_schedule_recipient_denied"
    assert len(store.read_events()) == before


def test_p2dr_procurement_rejects_another_organization_without_write() -> None:
    store = GameplayEventStore()
    organization = OrganizationAuthority(store=store)
    economy = EconomyAuthority(store=store)
    other_organization = "org:other"
    _record_schedule(
        organization,
        organization_ref=other_organization,
        recipient_ref=COUNTER,
        work_order_ref=COUNTER_WORK_ORDER,
    )
    schedule = organization.schedule_view_for(
        organization_ref=other_organization,
        recipient_ref=COUNTER,
        observed_at=OBSERVED_AT,
    )
    before = len(store.read_events())

    result = economy.settle_scheduled_procurement(
        quote=_quote(),
        posting=_posting().model_copy(update={"buyer_ref": other_organization}),
        organization_schedule=schedule,
        recipient_ref=COUNTER,
        work_order_ref=COUNTER_WORK_ORDER,
        observed_at=OBSERVED_AT,
        tick=1,
        command_id="p2dr:procurement:other-organization",
        idempotency_key="p2dr:procurement:other-organization",
        causation_id="cause:p2dr:procurement",
        correlation_id="corr:p2dr:window",
    )

    assert result.committed is False
    assert result.failure and result.failure.error_code == "scheduled_procurement_unsupported"
    assert len(store.read_events()) == before


def test_p2dr_procurement_rejects_public_schedule_source_without_write() -> None:
    store = GameplayEventStore()
    organization = OrganizationAuthority(store=store)
    economy = EconomyAuthority(store=store)
    _record_schedule(
        organization,
        recipient_ref=COUNTER,
        work_order_ref=COUNTER_WORK_ORDER,
        visibility_scope="public",
    )
    schedule = organization.schedule_view_for(
        organization_ref=ORGANIZATION,
        recipient_ref=COUNTER,
        observed_at=OBSERVED_AT,
    )
    before = len(store.read_events())

    result = _settle_counter_procurement(economy, organization, schedule=schedule)

    assert result.committed is False
    assert result.failure and result.failure.error_code == "organization_schedule_privacy_denied"
    assert len(store.read_events()) == before


def test_p2dr_procurement_duplicate_replays_but_changed_key_is_zero_write() -> None:
    store, organization, economy = _setup()
    first = _settle_counter_procurement(economy, organization)
    duplicate = _settle_counter_procurement(economy, organization)
    before = len(store.read_events())
    changed = _settle_counter_procurement(
        economy,
        organization,
        command_id="p2dr:procurement:changed",
    )

    assert first.committed and duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert changed.committed is False
    assert changed.failure and changed.failure.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == before


def test_p2dr_procurement_rejects_stale_schedule_revision_without_write() -> None:
    store, organization, economy = _setup()
    stale = organization.schedule_view_for(
        organization_ref=ORGANIZATION,
        recipient_ref=COUNTER,
        observed_at=OBSERVED_AT,
    )
    _record_schedule(organization, recipient_ref=COUNTER, work_order_ref="work:later")
    before = len(store.read_events())

    result = _settle_counter_procurement(economy, organization, schedule=stale)

    assert result.committed is False
    assert result.failure and result.failure.error_code == "organization_schedule_revision_conflict"
    assert len(store.read_events()) == before


def test_p2dr_procurement_is_scoped_and_full_checkpoint_tail_replay_matches() -> None:
    store, organization, economy = _setup()
    assert _settle_counter_procurement(economy, organization).committed
    events = store.read_events()
    replay = GameplayProjectionReplay(projector_id="p2dr-procurement", projector_version="1")
    checkpoint = replay.create_checkpoint(events[:4])
    tail = replay.checkpoint_plus_tail_replay(checkpoint, events[4:])
    replayed = _replay_events_into_store(events)

    assert replay.full_replay(events).projection_hash == tail.projection_hash
    entry = store.list_outbox()[-1]
    assert entry.audience == f"actor:{COUNTER}"
    assert entry.audience != f"actor:{BAKER}"
    assert EconomyProjector().rebuild(replayed.read_events()).source_revision_vector == EconomyProjector().rebuild(store.read_events()).source_revision_vector


def test_p2dr_shared_window_composes_counter_procurement_and_baker_production_to_wage_payment() -> None:
    store, organization, economy = _setup()
    production = ConstructionProductionAuthority(store=store)
    accounts = EconomyAuthorityService(store=store)
    window = OperatingWindow(
        window_ref="window:bakery-authored",
        organization_ref=ORGANIZATION,
        opens_at_tick=1,
        closes_at_tick=5,
        policy_revision="policy:window:1",
        source_revision="schedule:bakery-authored:1",
    )
    assert organization.open_operating_window(
        command_id="p2dr:window:open",
        idempotency_key="p2dr:window:open",
        causation_id="cause:p2dr:window",
        correlation_id="corr:p2dr:window",
        window=window,
        visibility_scope="project",
    ).committed

    facility = Facility(
        facility_ref="facility:bakery-authored",
        plot_ref="plot:bakery-authored",
        facility_kind="oven",
        condition=1,
    )
    recipe = Recipe(recipe_ref="recipe:bread-authored", inputs={}, output_item="item:bread", duration_ticks=2)
    contribution = WorkerContributionRef(
        actor_ref=BAKER,
        assignment_ref="assignment:char_b",
        work_order_ref=BAKER_WORK_ORDER,
        evidence_refs=("evidence:input:bread-authored:1",),
        contribution_digest="sha256:contribution:bread-authored:1",
    )
    assert production.settle_facility_acquisition(
        plot=Plot(
            plot_ref="plot:bakery-authored",
            jurisdiction_ref="jurisdiction:bakery-authored",
            owner_ref=ORGANIZATION,
        ),
        facility=facility,
        command_id="p2dr:facility:acquire",
        idempotency_key="p2dr:facility:acquire",
        causation_id="cause:p2dr:production",
        correlation_id="corr:p2dr:window",
    ).committed
    assert production.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:bread-authored:1",
        tick=1,
        command_id="p2dr:run:start",
        idempotency_key="p2dr:run:start",
        causation_id="cause:p2dr:production",
        correlation_id="corr:p2dr:window",
        worker_contribution_refs=(contribution,),
    ).committed
    run = production.projector().runs["run:bread-authored:1"]
    assert production.settle_finish_run(
        run,
        tick=3,
        recipe=recipe,
        command_id="p2dr:run:finish",
        idempotency_key="p2dr:run:finish",
        causation_id="cause:p2dr:production",
        correlation_id="corr:p2dr:window",
    ).committed
    evidence_ref = "evidence:production-completed:run:bread-authored:1:sha256:contribution:bread-authored:1"
    assert production.record_completed_work_evidence(
        run_ref="run:bread-authored:1",
        contribution=contribution,
        evidence_ref=evidence_ref,
        observed_at=OBSERVED_AT,
        command_id="p2dr:evidence:baker",
        idempotency_key="p2dr:evidence:baker",
        causation_id="cause:p2dr:production",
        correlation_id="corr:p2dr:window",
    ).committed
    assert _settle_counter_procurement(economy, organization).committed

    assert economy.open_wage_obligation(
        command=_wage_open_command(store),
        accrual_ref="accrual:bread-authored:1",
        organization_ref=ORGANIZATION,
        work_evidence_refs=(evidence_ref,),
        wage_amount_minor=75,
        due_tick=5,
        policy_revision="policy:wage:bakery-authored:1",
    ).committed
    evidence_event = next(
        event
        for event in store.read_events()
        if event.event_type == "gameplay.construction_production.work_completion_evidence_recorded"
    )
    evidence_view = production.completed_evidence_view_for(recipient_ref=BAKER)
    assert economy.settle_production_evidence_wage_accrual(
        command_id="p2dr:wage:accrue",
        idempotency_key="p2dr:wage:accrue",
        causation_id="cause:p2dr:wage",
        correlation_id="corr:p2dr:window",
        organization_ref=ORGANIZATION,
        worker_ref=BAKER,
        wage_obligation_ref="accrual:bread-authored:1",
        work_evidence_refs=(evidence_ref,),
        production_evidence_projection_digest=evidence_view.projection_hash,
        production_evidence_source_event_refs=(evidence_event.event_id,),
        production_evidence_source_revision_vector=evidence_view.source_revision_vector,
        production_wage_plan_digest="sha256:p2dr:production-wage:1",
        wage_amount_minor=75,
        wage_policy_revision="policy:wage:bakery-authored:1",
        expected_wage_revision=1,
    ).committed
    assert organization.close_operating_window(
        command_id="p2dr:window:close",
        idempotency_key="p2dr:window:close",
        causation_id="cause:p2dr:window",
        correlation_id="corr:p2dr:window",
        organization_ref=ORGANIZATION,
        window_ref=window.window_ref,
        expected_stream_revision=1,
        visibility_scope="project",
    ).committed
    assert organization.record_operating_window_due(
        command_id="p2dr:window:due",
        idempotency_key="p2dr:window:due",
        causation_id="cause:p2dr:window",
        correlation_id="corr:p2dr:window",
        organization_ref=ORGANIZATION,
        window_ref=window.window_ref,
        expected_stream_revision=2,
        visibility_scope="project",
    ).committed
    assert accounts.open_account(
        command_id="p2dr:account:bakery",
        account_id="account:bakery-authored",
        owner_ref=ORGANIZATION,
        currency_ref="currency:coin",
        initial_balance=100,
        idempotency_key="p2dr:account:bakery",
        causation_id="cause:p2dr:accounts",
        correlation_id="corr:p2dr:window",
    ).committed
    assert accounts.open_account(
        command_id="p2dr:account:baker",
        account_id="account:baker-authored",
        owner_ref=BAKER,
        currency_ref="currency:coin",
        initial_balance=0,
        idempotency_key="p2dr:account:baker",
        causation_id="cause:p2dr:accounts",
        correlation_id="corr:p2dr:window",
    ).committed
    accrual = WageAccrual(
        accrual_ref="accrual:bread-authored:1",
        organization_ref=ORGANIZATION,
        payee_actor_ref=BAKER,
        work_evidence_refs=(evidence_ref,),
        wage_policy_revision="policy:wage:bakery-authored:1",
        amount=75,
    )
    assert economy.pay_wage(
        accrual,
        payer_account_id="account:bakery-authored",
        payee_account_id="account:baker-authored",
        command_id="p2dr:wage:pay",
        idempotency_key="p2dr:wage:pay",
        causation_id="cause:p2dr:wage",
        correlation_id="corr:p2dr:window",
    ).committed

    events = store.read_events()
    assert any(event.payload.get("work_order_ref") == COUNTER_WORK_ORDER for event in events)
    assert any(event.payload.get("work_evidence_refs") == (evidence_ref,) for event in events)
    assert EconomyProjector().rebuild(events).balances["account:baker-authored"] == 75
    replay = GameplayProjectionReplay(projector_id="p2dr-window", projector_version="1")
    checkpoint = replay.create_checkpoint(events[: len(events) // 2])
    assert replay.full_replay(events).projection_hash == replay.checkpoint_plus_tail_replay(checkpoint, events[len(events) // 2 :]).projection_hash


def test_p2dr_insufficient_funds_is_zero_write_until_economy_records_overdue() -> None:
    store = GameplayEventStore()
    economy = EconomyAuthority(store=store)
    accounts = EconomyAuthorityService(store=store)
    accrual = WageAccrual(
        accrual_ref="accrual:p2dr:overdue:1",
        organization_ref=ORGANIZATION,
        payee_actor_ref=BAKER,
        work_evidence_refs=("evidence:production-completed:p2dr:1",),
        wage_policy_revision="policy:wage:p2dr:1",
        amount=75,
    )
    assert accounts.open_account(
        command_id="p2dr:overdue:account:bakery",
        account_id="account:p2dr:bakery",
        owner_ref=ORGANIZATION,
        currency_ref="currency:coin",
        initial_balance=10,
        idempotency_key="p2dr:overdue:account:bakery",
        causation_id="cause:p2dr:overdue",
        correlation_id="corr:p2dr:overdue",
    ).committed
    assert accounts.open_account(
        command_id="p2dr:overdue:account:baker",
        account_id="account:p2dr:baker",
        owner_ref=BAKER,
        currency_ref="currency:coin",
        initial_balance=0,
        idempotency_key="p2dr:overdue:account:baker",
        causation_id="cause:p2dr:overdue",
        correlation_id="corr:p2dr:overdue",
    ).committed
    before = len(store.read_events())

    try:
        economy.pay_wage(
            accrual,
            payer_account_id="account:p2dr:bakery",
            payee_account_id="account:p2dr:baker",
            command_id="p2dr:overdue:pay",
            idempotency_key="p2dr:overdue:pay",
            causation_id="cause:p2dr:overdue",
            correlation_id="corr:p2dr:overdue",
        )
    except EconomyRuntimeError as exc:
        assert str(exc) == "economy_insufficient_funds"
    else:
        raise AssertionError("insufficient-funds payment must reject")

    assert len(store.read_events()) == before
    overdue = economy.mark_overdue(
        accrual,
        command_id="p2dr:overdue:record",
        idempotency_key="p2dr:overdue:record",
        causation_id="cause:p2dr:overdue",
        correlation_id="corr:p2dr:overdue",
    )
    assert overdue.committed
    assert store.read_events()[-1].event_type == "gameplay.economy.wage_overdue"
