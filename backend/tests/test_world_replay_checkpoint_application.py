"""Scoped replay through the serialized application ingress, without owner writes."""
import asyncio
from copy import deepcopy
import json

import pytest
from test_status_application_lifecycle import application, _apply
from test_world_batch_settlement_application import inputs, submit
from test_temporal_profile_migration import request as migration_request
from test_inf4ao_public_milling_social_ack import _notice


async def capture(main, refs=("batch:1",), ref="replay:test"):
    return await asyncio.wrap_future(main.submit_replay_checkpoint(
        checkpoint_ref=ref, batch_refs=refs,
        advancement_owner_ref=main._population_runtime_driver.clock.timeline.advancement_owner_ref))


async def tail_call(main, tail=None, checkpoint_ref="replay:test", **kw):
    return await asyncio.wrap_future(main.submit_replay_tail(
        checkpoint_ref=checkpoint_ref, tail=tail,
        advancement_owner_ref=main._population_runtime_driver.clock.timeline.advancement_owner_ref, **kw))


@pytest.mark.asyncio
async def test_application_durable_cut_tail_full_replay_and_old_migration_pins(application, record_property):
    main, start, advance = application
    await start()
    await _apply(main, "replay-timed", duration=259200)
    await advance(86400)
    plan, window = inputs(main)
    first = await submit(main, plan=plan, window=window, budget=1)
    cut = await capture(main)
    assert cut.status == "consistent", cut.diagnostics
    old_store = main.gameplay_event_store
    await advance(172800)
    await asyncio.wrap_future(main.submit_temporal_profile_migration(**migration_request(main)))
    completed = await submit(main, budget=1)
    assert completed.receipts[0] == first.receipts[0]
    tail = await tail_call(main)
    assert tail.status == "verified", tail.diagnostics
    await main._stop_population_runtime_on_shutdown()
    await start()
    assert old_store is not main.gameplay_event_store
    before = await asyncio.wrap_future(main.runtime_execution.submit(lambda: main.gameplay_event_store.export_snapshot()))
    result = await tail_call(main, tail.payload)
    assert result.status == "verified", result.diagnostics
    assert result.result["full_digest"] == result.result["result_digest"]
    assert result.result["participants"]["batches"]
    assert "population-seconds:v1" in str(cut.checkpoint.state)
    assert "population-thirds:v2" in str(tail.payload)
    duplicate = deepcopy(tail.payload)
    duplicate["events"] += duplicate["events"]
    again = await tail_call(main, duplicate)
    assert again.status == "verified" and again.result == result.result
    after = await asyncio.wrap_future(main.runtime_execution.submit(lambda: main.gameplay_event_store.export_snapshot()))
    assert after == before
    record_property("scoped_replay", json.dumps(dict(cut=cut.checkpoint.model_dump(mode="json"), tail=tail.payload, result=result.result)))


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["gap", "changed_duplicate", "digest", "decoder", "receipt", "frozen_input"])
async def test_application_tail_faults_fail_closed(application, fault):
    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    await submit(main, plan=plan, window=window, budget=1)
    assert (await capture(main)).status == "consistent"
    await submit(main, budget=1)
    tail = await tail_call(main)
    assert tail.status == "verified"
    value = deepcopy(tail.payload)
    if fault == "gap":
        value["events"] = value["events"][1:]
    elif fault == "changed_duplicate":
        changed = deepcopy(value["events"][0])
        changed["payload"]["injected"] = True
        value["events"].append(changed)
    elif fault == "digest":
        value["result_digest"] = "wrong"
    elif fault == "decoder":
        value["version"] = 999
    elif fault == "receipt":
        value["participants"]["batches"] = {}
    else:
        value["participants"].pop("batches")
    from app.world_runtime.replay_checkpoint import _tail_hash
    if fault in {"gap", "receipt", "frozen_input"}:
        value["digest"] = _tail_hash(value)
    failed = await tail_call(main, value)
    assert failed.status in {"incomplete", "divergent"}
    assert failed.result is None
    expected = {"gap": "event_tail_gap", "changed_duplicate": "event_tail_conflict",
        "digest": "replay_tail_digest_conflict", "decoder": "replay_decoder_unsupported",
        "receipt": "replay_participant_missing", "frozen_input": "replay_participant_missing"}
    assert failed.diagnostics == (expected[fault],)


@pytest.mark.asyncio
async def test_application_missing_participant_and_wrong_principal_have_no_checkpoint(application):
    main, start, advance = application
    await start()
    await advance(86400)
    missing = await capture(main)
    assert missing.status == "incomplete" and missing.checkpoint is None
    with pytest.raises(ValueError, match="replay_advancement_owner_mismatch"):
        await asyncio.wrap_future(main.submit_replay_checkpoint(checkpoint_ref="forbidden", batch_refs=("batch:1",), advancement_owner_ref="character:reader"))
    assert not any(getattr(route, "path", "").startswith("/replay") for route in main.app.routes)


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["batch_input", "owner", "migration"])
async def test_application_cut_rejects_changes_during_capture(application, monkeypatch, mutation):
    from app.world_runtime import replay_participants
    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    await submit(main, plan=plan, window=window, budget=0)
    original = replay_participants.capture_participants
    calls = []
    def changing(*args):
        observed = original(*args)
        if not calls:
            calls.append(True)
            if mutation == "batch_input":
                saved = main.gameplay_event_store.get_projection_checkpoint("batch-input:batch:1")
                main.gameplay_event_store.save_projection_checkpoint(saved.model_copy(update={"projection_hash": "changed"}))
            elif mutation == "owner":
                coordinator = main._settlement_batch_coordinator
                coordinator.execute(coordinator.load("batch:1"), budget=1)
            else:
                main._population_runtime_driver.migration_pending = True
        return observed
    monkeypatch.setattr(replay_participants, "capture_participants", changing)
    result = await capture(main)
    assert result.status == "incomplete" and result.checkpoint is None
    assert main.gameplay_event_store.get_projection_checkpoint("replay:test") is None
    if mutation == "batch_input":
        # The concurrent input update advances no authority event sequence.
        assert not main.gameplay_event_store.read_stream("gameplay:organization:window:window:1")


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["receipt", "frozen_input", "decoder"])
async def test_application_required_persisted_dependencies_are_not_dropped(application, monkeypatch, missing):
    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    await submit(main, plan=plan, window=window, budget=1)
    store = main.gameplay_event_store
    if missing == "receipt":
        original = store.get_by_idempotency
        monkeypatch.setattr(store, "get_by_idempotency", lambda owner, key:
            None if owner == plan.operations[0].owner_ref else original(owner, key))
    elif missing == "frozen_input":
        original = store.get_projection_checkpoint
        monkeypatch.setattr(store, "get_projection_checkpoint", lambda ref:
            None if ref == "batch-input:batch:1" else original(ref))
    else:
        original = store.get_projection_checkpoint
        def unsupported(ref):
            saved = original(ref)
            return saved.model_copy(update={"projector_version": "999"}) if ref == "batch-input:batch:1" else saved
        monkeypatch.setattr(store, "get_projection_checkpoint", unsupported)
    cut = await capture(main)
    assert cut.status == "incomplete" and cut.checkpoint is None
    assert any(word in " ".join(cut.diagnostics) for word in ("receipt", "frozen_input", "decoder"))


@pytest.mark.asyncio
async def test_application_conflicted_b_stays_pending_after_checkpoint_replay_and_restart(application):
    from app.gameplay.econ1_economy_runtime import WageAccrual
    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    econ = main._settlement_batch_coordinator.adapters[(plan.operations[1].owner_ref, plan.operations[1].owner_contract_ref)]
    def prior():
        return econ.owner.accrue_wage(WageAccrual(accrual_ref="prior", organization_ref="org:bakery",
            payee_actor_ref="character:char_b", work_evidence_refs=("evidence:verified",),
            wage_policy_revision="policy:1", amount=1), completed_evidence_refs={"evidence:verified"},
            command_id="prior", idempotency_key="prior", causation_id="cause", correlation_id="corr")
    assert (await asyncio.wrap_future(main.runtime_execution.submit(prior))).committed
    first = await submit(main, plan=plan, window=window, budget=2)
    assert first.stage == "pending_recovery" and first.recovery_cursor == 1
    cut = await capture(main)
    assert cut.status == "consistent", cut.diagnostics
    tail = await tail_call(main)
    await main._stop_population_runtime_on_shutdown()
    await start()
    result = await tail_call(main, tail.payload)
    assert result.status == "verified", result.diagnostics
    batch = result.result["participants"]["batches"]["batch:1"]
    assert batch["recovery_cursor"] == 1 and batch["stage"] == "pending_recovery"
    assert await submit(main, budget=2) == first


@pytest.mark.asyncio
async def test_inventory_participant_survives_durable_reopen_and_checkpoint_tail(application, tmp_path):
    from app.gameplay.event_store import DurableGameplayEventStore
    from app.world_runtime.replay_participants import capture_participants
    from test_siming_population_inventory_vertical import _read_set
    from app.services.siming_population_capability import PopulationSimulationCapability
    from app.population_continuity.inventory_owner_adapter import InventoryOutputCustodyOwnerExecutor

    main, start, advance = application
    await start()
    store = main.gameplay_event_store
    assert isinstance(store, DurableGameplayEventStore)
    inventory = main.inventory_authority_service
    assert inventory._store is store
    path = store._snapshot_path
    await advance(86400)
    # Explicitly advance the admitted population driver so this test uses a
    # real cadence authority event rather than fixture-only temporal pins.
    await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main._population_runtime_driver.tick(main._population_runtime_driver.current_tick + 60)
    ))
    plan, window = inputs(main)
    await submit(main, plan=plan, window=window, budget=1)
    before_inventory = await asyncio.wrap_future(main.submit_replay_checkpoint(
        checkpoint_ref="replay:before-inventory", batch_refs=("batch:1",),
        advancement_owner_ref=main._population_runtime_driver.clock.timeline.advancement_owner_ref))
    assert before_inventory.status == "consistent", before_inventory.diagnostics
    from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Plot, Recipe
    from app.gameplay.closed_generic_gameplay_families import ProductionOutputCertificationIntent
    construction = ConstructionProductionAuthority(store=store, package_registry=main.production_package_registry)
    facility = Facility(facility_ref="facility:rw50", plot_ref="plot:rw50", facility_kind="bakery", condition=1.0)
    acquired = construction.settle_facility_acquisition(
        plot=Plot(plot_ref=facility.plot_ref, jurisdiction_ref="jurisdiction:local", owner_ref="organization:bakery"),
        facility=facility, command_id="rw50:acquire", idempotency_key="rw50:acquire",
        causation_id="rw50", correlation_id="rw50")
    assert acquired.committed, acquired.failure
    recipe = Recipe(recipe_ref="recipe:flour-to-bread@1", inputs={}, output_item="item:bread@1",
        duration_ticks=1, failure_policy_mode="terminal", failure_policy_revision="policy:failure:terminal@1")
    started = construction.settle_start_run(facility=facility, recipe=recipe, run_ref="run:rw50", tick=10,
        command_id="rw50:start", idempotency_key="rw50:start", causation_id="rw50", correlation_id="rw50")
    assert started.committed, started.failure
    finished = construction.settle_finish_run(construction.projector().runs["run:rw50"], tick=11, recipe=recipe,
        command_id="rw50:finish", idempotency_key="rw50:finish", causation_id="rw50", correlation_id="rw50")
    assert finished.committed, finished.failure
    source_event = store.read_stream(f"gameplay:construction_production:{facility.facility_ref}")[-1]
    cert_result = construction.settle_production_output_certification(intent=ProductionOutputCertificationIntent(
        run_finished_event_id=source_event.event_id, expected_run_finished_revision=3,
        expected_stream_revision=3, expected_facility_revision=0, command_id="rw50:certify",
        causation_id=source_event.event_id, correlation_id="rw50", submitted_at="population:rw50"))
    assert cert_result.committed, cert_result.failure
    certification = store.get_event(cert_result.committed_event_ids[0])
    from app.gameplay.inventory_runtime import ContainerSpec
    container = inventory.create_container(command_id="rw50:container", actor_ref="organization:bakery",
        spec=ContainerSpec("container:organization:bakery:production-output", 100, 100, 4),
        idempotency_key="rw50:container", causation_id="rw50", correlation_id="rw50")
    assert container.committed, container.failure
    read_set = _read_set(certification)
    # Reuse the cadence authority record admitted by the running population
    # driver; direct fixture pins are intentionally insufficient for Inventory.
    cadence_event = next(
        event for event in reversed(store.read_events())
        if event.event_type == "population.cadence.admitted"
    )
    cadence_record = cadence_event.payload
    from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationReadSet
    admitted_cadence = PopulationCadenceInput.model_validate(cadence_record["cadence"])
    read_set = PopulationReadSet.from_inputs(
        admitted_cadence, read_set.projections, temporal_pins=cadence_record["time_pins"]
    )
    result = PopulationSimulationCapability(owner_executors={
        "population:inventory-output-custody:v1": InventoryOutputCustodyOwnerExecutor(authority=inventory)
    }).run_default_decision_cycle(read_set.cadence, read_set)
    assert result.status == "accepted", result.owner_receipts

    from app.world_runtime.replay_participants import validate_saved_participants
    validate_saved_participants(
        store, before_inventory.checkpoint.state["participants"], ("batch:1",),
        boundary_sequence=before_inventory.checkpoint.last_global_sequence,
        inventory_authority=inventory,
        social_authority=main.social_fact_authority_service,
    )
    assert "inventory" not in before_inventory.checkpoint.state["participants"]
    assert "inventory_domain" in before_inventory.checkpoint.state["participants"]
    from app.world_runtime.replay_participants import _inventory_participant
    contaminated = deepcopy(before_inventory.checkpoint.state["participants"])
    contaminated["inventory"] = _inventory_participant(store, inventory)
    with pytest.raises(ValueError, match="replay_inventory_participant_scope_mismatch"):
        validate_saved_participants(
            store, contaminated, ("batch:1",),
            boundary_sequence=before_inventory.checkpoint.last_global_sequence,
            inventory_authority=inventory,
        )

    cut = await capture(main)
    assert cut.status == "consistent", cut.diagnostics
    saved_inventory = cut.checkpoint.state["participants"].get("inventory")
    assert saved_inventory is not None
    assert saved_inventory["rows"] and saved_inventory["event_refs"]
    assert saved_inventory["source_revision_vector"]
    assert saved_inventory["view_digest"]

    from app.world_runtime.replay_participants import validate_saved_participants
    from app.gameplay.event_store import GameplayEventStoreSnapshotError
    with pytest.raises(ValueError, match="replay_inventory_domain_authority_missing"):
        validate_saved_participants(
            store, cut.checkpoint.state["participants"], ("batch:1",),
            boundary_sequence=cut.checkpoint.last_global_sequence,
        )
    for field, mutate in (
        ("rows", lambda value: value["rows"].append({"forged": True})),
        ("event_refs", lambda value: value["event_refs"].pop()),
        ("source_revision_vector", lambda value: value["source_revision_vector"].clear()),
        ("view_digest", lambda value: value.__setitem__("view_digest", "forged")),
    ):
        changed = deepcopy(cut.checkpoint.state["participants"])
        mutate(changed["inventory"])
        with pytest.raises(ValueError, match="replay_saved_inventory"):
            validate_saved_participants(
                store, changed, ("batch:1",),
                boundary_sequence=cut.checkpoint.last_global_sequence,
                inventory_authority=inventory,
            )

    tail = await tail_call(main)
    assert tail.status == "verified", tail.diagnostics
    await main._stop_population_runtime_on_shutdown()
    assert store._closed
    with pytest.raises(GameplayEventStoreSnapshotError, match="gameplay_snapshot_closed"):
        store.read_events()
    from app.gameplay.inventory_runtime import InventoryAuthorityService
    reopened = DurableGameplayEventStore(path)
    restored_inventory = InventoryAuthorityService(
        store=reopened, registry=inventory._registry, package_registry=inventory._package_registry)
    assert restored_inventory is not inventory and restored_inventory._store is reopened
    from app.gameplay.p5.social_knowledge import SocialFactAuthority
    social = main.social_fact_authority_service
    restored_social = SocialFactAuthority(
        registry=social._registry, store=reopened,
        package_registry=getattr(social, "_package_registry", None))
    from app.world_runtime.replay_checkpoint import replay_scoped_tail
    restored = replay_scoped_tail(store=reopened, checkpoint_ref="replay:test", tail=tail.payload,
        inventory_authority=restored_inventory, social_authority=restored_social)
    assert restored.status == "verified", restored.diagnostics
    assert restored.result["full_digest"] == restored.result["result_digest"]
    assert restored.result["participants"]["inventory"] == saved_inventory
    changed_tail = deepcopy(tail.payload)
    changed_tail["participants"].pop("inventory")
    from app.world_runtime.replay_checkpoint import _tail_hash
    changed_tail["digest"] = _tail_hash(changed_tail)
    omitted = replay_scoped_tail(store=reopened, checkpoint_ref="replay:test", tail=changed_tail,
        inventory_authority=restored_inventory)
    assert omitted.status == "divergent"
    assert omitted.diagnostics == ("replay_participant_scope_conflict",)

    # A participant tail cannot smuggle a custody event beyond the captured
    # durable source boundary.  The copied event is deliberately moved one
    # sequence past the real tail; replay must compare it with the source and
    # fail closed instead of accepting a future Inventory row.
    future_tail = deepcopy(tail.payload)
    source_inventory_event = next(
        event for event in reopened.read_events()
        if event.event_type == "gameplay.inventory.production_output_received@1"
    )
    future_event = source_inventory_event.model_dump(mode="json")
    future_event["event_id"] = f"{future_event['event_id']}:future"
    future_event["global_sequence"] = future_tail["to_sequence"] + 1
    future_tail["events"].append(future_event)
    future_tail["to_sequence"] += 1
    future_tail["digest"] = _tail_hash(future_tail)
    future = replay_scoped_tail(store=reopened, checkpoint_ref="replay:test", tail=future_tail,
        inventory_authority=restored_inventory)
    assert future.status in {"incomplete", "divergent"}
    assert future.result is None
    assert future.diagnostics == ("replay_source_conflict",)
    reopened.close()


@pytest.mark.asyncio
async def test_application_checkpoint_digest_conflict_is_rejected(application):
    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    await submit(main, plan=plan, window=window, budget=1)
    cut = await capture(main)
    tail = await tail_call(main)
    await asyncio.wrap_future(main.runtime_execution.submit(lambda:
        main.gameplay_event_store.save_projection_checkpoint(
            cut.checkpoint.model_copy(update={"projection_hash": "corrupted"}))))
    result = await tail_call(main, tail.payload)
    assert result.status == "divergent"
    assert result.diagnostics == ("replay_checkpoint_digest_conflict",)


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["receipt", "frozen_input"])
async def test_application_tail_restore_requires_durable_dependencies(application, monkeypatch, missing):
    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    await submit(main, plan=plan, window=window, budget=1)
    assert (await capture(main)).status == "consistent"
    tail = await tail_call(main)
    store = main.gameplay_event_store
    if missing == "receipt":
        original = store.get_by_idempotency
        monkeypatch.setattr(store, "get_by_idempotency", lambda owner, key:
            None if owner == plan.operations[0].owner_ref else original(owner, key))
    else:
        original = store.get_projection_checkpoint
        monkeypatch.setattr(store, "get_projection_checkpoint", lambda ref:
            None if ref == "batch-input:batch:1" else original(ref))
    result = await tail_call(main, tail.payload)
    assert result.status in {"incomplete", "divergent"}
    assert result.result is None
    assert missing in " ".join(result.diagnostics)


@pytest.mark.asyncio
async def test_first_social_fact_after_empty_cut_replays_after_durable_reopen(application):
    from app.population_continuity.social_owner_adapter import SocialPopulationSignalOwnerExecutor
    from app.services.siming_population_capability import PopulationSimulationCapability
    from test_siming_population_social_signal_vertical import _read_set

    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    assert (await submit(main, plan=plan, window=window, budget=1)).receipts
    cut = await capture(main, ref="replay:first-social")
    assert cut.status == "consistent", cut.diagnostics

    def settle_social():
        capability = PopulationSimulationCapability(owner_executors={
            "population:social-population-signal:v1": SocialPopulationSignalOwnerExecutor(
                authority=main.social_fact_authority_service)
        })
        return capability.run_default_decision_cycle(_read_set().cadence, _read_set())

    result = await asyncio.wrap_future(main.runtime_execution.submit(settle_social))
    assert result.status == "accepted"
    tail = await tail_call(main, checkpoint_ref="replay:first-social")
    assert tail.status == "verified", tail.diagnostics

    await main._stop_population_runtime_on_shutdown()
    await start()
    before = await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.export_snapshot()))
    replayed = await tail_call(main, tail.payload, checkpoint_ref="replay:first-social")
    assert replayed.status == "verified", replayed.diagnostics
    assert cut.checkpoint.state["participants"]["social"]["event_refs"] == []
    assert tail.payload["participants"]["social"]["event_refs"]
    assert replayed.result["full_digest"] == replayed.result["result_digest"]
    assert await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.export_snapshot())) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("first_before_cut", [True, False])
async def test_second_social_delivery_recipient_joins_same_durable_cut(application, first_before_cut):
    from app.gameplay.p5.social_delivery import SocialDeliveryWindow

    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    assert (await submit(main, plan=plan, window=window, budget=1)).receipts
    source_store, notice = _notice(effective_from=86400, effective_to=172800)
    source_id = notice.event_id

    def deliver(recipient, index):
        authority = main.social_delivery_caller.authority
        if index == 1:
            for transaction in source_store.read_transactions():
                assert main.gameplay_event_store.append_batch(transaction).committed
        result = authority.record_delivery(
            delivery_ref=f"delivery:multi:{index}", source_stream_id=notice.stream_id,
            source_revision=notice.stream_revision, source_event_id=source_id, recipient_ref=recipient,
            window=SocialDeliveryWindow(86400, 172800, None), world_now=86400,
            operational_now=10, command_id=f"delivery:multi:{index}",
            idempotency_key=f"delivery:multi:{index}", causation_id=source_id,
            correlation_id=f"delivery:multi:{index}",
        )
        assert result.committed, result.error_code

    if first_before_cut:
        await asyncio.wrap_future(main.runtime_execution.submit(
            lambda: deliver("org:mill:1", 1)))
    cut = await capture(main, ref="replay:multi-social-delivery")
    assert cut.status == "consistent", cut.diagnostics
    if not first_before_cut:
        await asyncio.wrap_future(main.runtime_execution.submit(
            lambda: deliver("org:mill:1", 1)))
    await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: deliver("org:mill:2", 2)))
    tail = await tail_call(main, checkpoint_ref="replay:multi-social-delivery")
    assert tail.status == "verified", tail.diagnostics

    await main._stop_population_runtime_on_shutdown()
    await start()
    before = await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.export_snapshot()))
    replayed = await tail_call(main, tail.payload, checkpoint_ref="replay:multi-social-delivery")
    assert replayed.status == "verified", replayed.diagnostics
    if first_before_cut:
        assert cut.checkpoint.state["participants"]["social_delivery"]["recipient_ref"] == "org:mill:1"
    else:
        assert cut.checkpoint.state["participants"]["social_delivery"]["scope"] == "project:social-delivery-unbound"
    assert tail.payload["participants"]["social_delivery"]["recipient_refs"] == [
        "org:mill:1", "org:mill:2",
    ]
    delivery_state = tail.payload["participants"]["social_delivery"]
    assert len(delivery_state["event_refs"]) == 2
    for recipient in delivery_state["recipient_refs"]:
        scoped = delivery_state["recipients"][recipient]
        assert len(scoped["event_refs"]) == 1
        assert scoped["projection"]["recipient_ref"] == recipient
        assert len(scoped["projection"]["deliveries"]) == 1
    assert replayed.result["full_digest"] == replayed.result["result_digest"]
    assert await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.export_snapshot())) == before

    from app.world_runtime.replay_checkpoint import _tail_hash
    for fault in ("recipient_refs", "recipient_projection", "event_refs", "view_digest"):
        damaged = deepcopy(tail.payload)
        delivery_state = damaged["participants"]["social_delivery"]
        if fault == "recipient_refs":
            delivery_state["recipient_refs"].pop()
        elif fault == "recipient_projection":
            delivery_state["recipients"]["org:mill:2"]["projection_hash"] = "sha256:forged"
        elif fault == "event_refs":
            delivery_state["event_refs"].pop()
        else:
            delivery_state["view_digest"] = "sha256:forged"
        damaged["digest"] = _tail_hash(damaged)
        rejected = await tail_call(main, damaged, checkpoint_ref="replay:multi-social-delivery")
        assert rejected.status in {"incomplete", "divergent"} and rejected.result is None, fault
        assert await asyncio.wrap_future(main.runtime_execution.submit(
            lambda: main.gameplay_event_store.export_snapshot())) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("notice_before_cut", [True, False])
async def test_first_social_delivery_after_empty_cut_replays_after_restart(application, notice_before_cut):
    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    assert (await submit(main, plan=plan, window=window, budget=1)).receipts
    source_store, notice = _notice(effective_from=86400, effective_to=172800)

    def import_source_transactions():
        for transaction in source_store.read_transactions():
            assert main.gameplay_event_store.append_batch(transaction).committed

    if notice_before_cut:
        await asyncio.wrap_future(main.runtime_execution.submit(import_source_transactions))
    cut = await capture(main, ref="replay:first-social-delivery")
    assert cut.status == "consistent", cut.diagnostics
    if not notice_before_cut:
        await asyncio.wrap_future(main.runtime_execution.submit(import_source_transactions))

    delivery = await asyncio.wrap_future(main.submit_social_delivery(
        notice_event_id=notice.event_id,
        command_id="social-replay:first-delivery",
        idempotency_key="social-replay:first-delivery",
        causation_id=notice.event_id,
        correlation_id="social-replay:first-delivery",
    ))
    assert delivery is not None and delivery.result.committed
    tail = await tail_call(main, checkpoint_ref="replay:first-social-delivery")
    assert tail.status == "verified", tail.diagnostics

    await main._stop_population_runtime_on_shutdown()
    await start()
    before = await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.export_snapshot()))
    replayed = await tail_call(main, tail.payload, checkpoint_ref="replay:first-social-delivery")
    assert replayed.status == "verified", replayed.diagnostics
    assert cut.checkpoint.state["participants"]["social_delivery"]["scope"] == (
        "project:social-delivery" if notice_before_cut else "project:social-delivery-unbound"
    )
    assert cut.checkpoint.state["participants"]["social_delivery"]["event_refs"] == []
    assert tail.payload["participants"]["social_delivery"]["event_refs"]
    assert replayed.result["full_digest"] == replayed.result["result_digest"]
    assert await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: main.gameplay_event_store.export_snapshot())) == before


@pytest.mark.asyncio
async def test_social_population_participant_survives_durable_reopen_and_checkpoint_tail(application):
    from app.services.siming_population_capability import PopulationSimulationCapability
    from app.population_continuity.social_owner_adapter import SocialPopulationSignalOwnerExecutor
    from test_siming_population_social_signal_vertical import _read_set

    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    await submit(main, plan=plan, window=window, budget=1)

    def settle_social():
        capability = PopulationSimulationCapability(owner_executors={
            "population:social-population-signal:v1": SocialPopulationSignalOwnerExecutor(
                authority=main.social_fact_authority_service
            )
        })
        return capability.run_default_decision_cycle(_read_set().cadence, _read_set())

    social_result = await asyncio.wrap_future(main.runtime_execution.submit(settle_social))
    assert social_result.status == "accepted"

    # Feed the application ingress from a committed Government source.  The
    # source transactions are copied through the supported append API so the
    # replay participant is backed by the same durable event store.
    source_store, notice = _notice(effective_from=86400, effective_to=172800)

    def import_source_transactions():
        for transaction in source_store.read_transactions():
            result = main.gameplay_event_store.append_batch(transaction)
            assert result.committed, result.failure

    await asyncio.wrap_future(main.runtime_execution.submit(import_source_transactions))
    delivery = await asyncio.wrap_future(main.submit_social_delivery(
        notice_event_id=notice.event_id,
        command_id="social-replay:bound-delivery",
        idempotency_key="social-replay:bound-delivery",
        causation_id=notice.event_id,
        correlation_id="social-replay:bound-delivery",
    ))
    assert delivery is not None and delivery.result.committed
    cut = await capture(main, ref="replay:social-population")
    assert cut.status == "consistent", cut.diagnostics

    tail = await tail_call(main, checkpoint_ref="replay:social-population")
    assert tail.status == "verified", tail.diagnostics
    assert "social" in tail.payload["participants"]
    assert "social_delivery" in tail.payload["participants"]

    # Participant membership and projection claims are part of the replay
    # contract.  Removing or changing them must fail closed before restore.
    missing_delivery = deepcopy(tail.payload)
    del missing_delivery["participants"]["social_delivery"]
    rejected = await tail_call(
        main, tail=missing_delivery, checkpoint_ref="replay:social-population"
    )
    assert rejected.status in {"divergent", "incomplete"}

    tampered_delivery = deepcopy(tail.payload)
    tampered_delivery["participants"]["social_delivery"]["recipient_ref"] = "org:tampered"
    rejected = await tail_call(
        main, tail=tampered_delivery, checkpoint_ref="replay:social-population"
    )
    assert rejected.status in {"divergent", "incomplete"}

    tampered_refs = deepcopy(tail.payload)
    tampered_refs["participants"]["social_delivery"]["event_refs"] = []
    rejected = await tail_call(
        main, tail=tampered_refs, checkpoint_ref="replay:social-population"
    )
    assert rejected.status in {"divergent", "incomplete"}

    old_store = main.gameplay_event_store
    await main._stop_population_runtime_on_shutdown()
    await start()
    assert old_store is not main.gameplay_event_store
    replayed = await tail_call(main, tail=tail.payload, checkpoint_ref="replay:social-population")
    assert replayed.status == "verified", replayed.diagnostics
    assert replayed.result["full_digest"] == replayed.result["result_digest"]
    assert "social" in replayed.result["participants"]


@pytest.mark.asyncio
async def test_population_activation_presence_application_checkpoint_tail_and_new_durable_authority(application):
    from app.population_continuity.models import ActivationGrant, ActivationProposal

    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    await submit(main, plan=plan, window=window, budget=1)
    empty_cut = await capture(main, refs=("batch:1",), ref="replay:before-presence-app")
    assert empty_cut.status == "consistent", empty_cut.diagnostics
    assert empty_cut.checkpoint.state["participants"]["presence"]["rows"] == []
    assert empty_cut.checkpoint.state["participants"]["life_state"]["actors"] == {}
    grants = (ActivationGrant(
        profile_ref="character:char_a", world_ref="world:bakery",
        package_revision="package:bakery-authored-agents:v1",
        policy_revision="policy:population:v1", scope_grant=("actor:self",),
    ),)
    # Contract fixture: this grant is deliberately not attributed to an existing issuer.
    await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: setattr(main.population_activation_authority, "grants", grants)))
    proposal = ActivationProposal(
        proposal_id="proposal:app-presence", profile_ref="character:char_a",
        world_ref="world:bakery", package_revision="package:bakery-authored-agents:v1",
        policy_revision="policy:population:v1", activation_reason="population-cadence",
        scope_grant=("actor:self",), cadence_class="simulation",
        expected_revisions={"population:world:bakery": 0},
        idempotency_key="activation:app-presence", correlation_id="corr:app-presence",
        source_ref="population:contract-fixture",
    )
    result = await asyncio.wrap_future(main.submit_population_activation_presence(
        proposal=proposal, presence_idempotency_key="presence:app-presence",
        presence_expected_revision=0))
    assert result.activation.committed and result.presence.committed
    first_tail = await tail_call(main, checkpoint_ref="replay:before-presence-app")
    assert first_tail.status == "verified", first_tail.diagnostics
    assert set(first_tail.payload["participants"]) == set(empty_cut.checkpoint.state["participants"]), (
        set(first_tail.payload["participants"]) - set(empty_cut.checkpoint.state["participants"]),
        set(empty_cut.checkpoint.state["participants"]) - set(first_tail.payload["participants"]),
    )
    assert first_tail.payload["participants"]["presence"]["rows"][0]["status"] == "present"
    assert first_tail.payload["participants"]["life_state"]["actors"]["character:char_a"]["state"] == "alive"
    first_store = main.gameplay_event_store
    from app.gameplay.event_store import DurableGameplayEventStore
    assert isinstance(first_store, DurableGameplayEventStore)
    first_path = first_store._snapshot_path
    cut = await capture(main, refs=("batch:1",), ref="replay:presence-app")
    assert cut.status == "consistent", cut.diagnostics
    from app.population_continuity.presence_runtime import CharacterDespawnRequest
    despawn = await asyncio.wrap_future(main.runtime_execution.submit(lambda:
        main.population_presence_authority.despawn(CharacterDespawnRequest(
            world_ref="world:bakery", character_ref="character:char_a", incarnation=1,
            idempotency_key="despawn:app-presence", expected_revision=1, reason="contract-test"))))
    assert despawn.committed
    tail = await tail_call(main, checkpoint_ref="replay:presence-app")
    assert tail.status == "verified", tail.diagnostics
    participant = tail.payload["participants"]["presence"]
    assert cut.checkpoint.state["participants"]["presence"]["rows"] == [{
        "world_ref": "world:bakery", "character_ref": "character:char_a",
        "incarnation": 1, "status": "present",
    }]
    assert participant["rows"] == []

    from app.world_runtime.replay_checkpoint import _tail_hash
    for fault in ("rows", "view_digest", "event_refs", "missing", "decoder"):
        changed = deepcopy(tail.payload)
        if fault == "missing":
            del changed["participants"]["presence"]
        elif fault == "decoder":
            changed["participants"]["versions"].pop("presence")
        else:
            changed["participants"]["presence"][fault] = {
                "rows": [{"character_ref": "forged"}], "view_digest": "sha256:forged", "event_refs": [],
            }[fault]
        # Recompute the envelope hash: rejection must come from participant validation.
        changed["digest"] = _tail_hash(changed)
        rejected = await tail_call(main, tail=changed, checkpoint_ref="replay:presence-app")
        assert rejected.status in {"incomplete", "divergent"} and rejected.result is None, fault
    from app.world_runtime.replay_participants import validate_saved_participants
    with pytest.raises(ValueError, match="replay_presence_participant_missing"):
        validate_saved_participants(first_store, tail.payload["participants"], ("batch:1",),
            inventory_authority=main.inventory_authority_service,
            social_authority=main.social_fact_authority_service)
    with pytest.raises(ValueError, match="replay_saved_presence_event_scope_mismatch"):
        validate_saved_participants(first_store, tail.payload["participants"], ("batch:1",),
            boundary_sequence=cut.checkpoint.last_global_sequence,
            inventory_authority=main.inventory_authority_service,
            social_authority=main.social_fact_authority_service,
            presence_authority=main.population_presence_authority)
    # Capture rejects an omitted Presence authority when Presence facts exist.
    from app.world_runtime.replay_participants import capture_participants
    with pytest.raises(ValueError, match="replay_presence_participant_missing"):
        await asyncio.wrap_future(main.runtime_execution.submit(lambda: capture_participants(
            main.gameplay_event_store, main._settlement_batch_coordinator,
            main._population_runtime_driver, main.status_temporal_consumer, ("batch:1",),
            inventory_authority=main.inventory_authority_service)))
    await main._stop_population_runtime_on_shutdown()
    await start()
    assert first_store is not main.gameplay_event_store
    assert isinstance(main.gameplay_event_store, DurableGameplayEventStore)
    assert main.gameplay_event_store._snapshot_path == first_path
    assert main.population_presence_authority.store is main.gameplay_event_store
    first_replayed = await tail_call(main, tail=first_tail.payload,
                                     checkpoint_ref="replay:before-presence-app")
    assert first_replayed.status == "verified", first_replayed.diagnostics
    assert first_replayed.result["full_digest"] == first_replayed.result["result_digest"]
    replayed = await tail_call(main, tail=tail.payload, checkpoint_ref="replay:presence-app")
    assert replayed.status == "verified", replayed.diagnostics
    assert replayed.result["full_digest"] == replayed.result["result_digest"]
