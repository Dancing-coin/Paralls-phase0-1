"""Participant admission uses the assembled runtime and queries existing owners only."""
import asyncio

import pytest

from test_status_application_lifecycle import application, _apply
from test_world_batch_settlement_application import inputs, submit


async def capture(main, refs=("batch:1",)):
    from app.world_runtime.replay_participants import capture_participants
    return await asyncio.wrap_future(main.runtime_execution.submit(lambda: capture_participants(
        main.gameplay_event_store, main._settlement_batch_coordinator,
        main._population_runtime_driver, main.status_temporal_consumer, refs,
        inventory_authority=main.inventory_authority_service)))


@pytest.mark.asyncio
async def test_participants_keep_pending_owner_work_and_frozen_inputs(application):
    main, start, advance = application
    await start()
    await _apply(main, "pending-status", duration=172800)
    await advance(86400)
    plan, window = inputs(main)
    result = await submit(main, plan=plan, window=window, budget=1)
    before = main.gameplay_event_store.export_snapshot()
    state = await capture(main)
    assert main.gameplay_event_store.export_snapshot() == before
    assert state["schema_version"] == 1
    assert state["population"]["confirmed_tick"] == 86400
    assert state["population"]["recovery_state"]["schema_version"] == 1
    assert state["batches"]["batch:1"]["input"]["projection_hash"] == result.input_digest
    operations = state["batches"]["batch:1"]["operations"]
    assert operations[0]["receipt"]["committed"] is True
    assert operations[1]["receipt"] is None
    assert state["batches"]["batch:1"]["recovery_cursor"] == 1
    assert len(state["status"]["pending_work"]) == 1
    assert state["migration"]["pending"] is False
    assert state["random_context"]["status"] == "not_applicable"


@pytest.mark.asyncio
async def test_missing_batch_or_required_status_binding_is_incomplete(application):
    main, start, advance = application
    await start()
    await advance(86400)
    with pytest.raises(ValueError, match="batch_frozen_input_missing"):
        await capture(main)
    plan, window = inputs(main)
    await submit(main, plan=plan, window=window, budget=0)
    await asyncio.wrap_future(main.runtime_execution.submit(lambda:
        main.status_temporal_consumer.bindings.__setitem__("actor:configured", None)))
    with pytest.raises(ValueError, match="replay_status_binding_missing"):
        await capture(main)


@pytest.mark.asyncio
async def test_saved_participant_receipts_and_frozen_claims_are_verified_against_store(application):
    import copy
    from app.world_runtime.replay_participants import validate_saved_participants
    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    await submit(main, plan=plan, window=window, budget=1)
    state = await capture(main)
    validate_saved_participants(main.gameplay_event_store, state, ("batch:1",),
        inventory_authority=main.inventory_authority_service)
    changed = copy.deepcopy(state)
    changed["batches"]["batch:1"]["receipts"]["window"] = None
    with pytest.raises(ValueError, match="replay_saved_receipt_mismatch"):
        validate_saved_participants(main.gameplay_event_store, changed, ("batch:1",),
            inventory_authority=main.inventory_authority_service)
    changed = copy.deepcopy(state)
    changed["batches"]["batch:1"]["frozen_input"]["state"]["plan"]["evidence_refs"] = []
    with pytest.raises(ValueError, match="replay_saved_frozen_input_mismatch"):
        validate_saved_participants(main.gameplay_event_store, changed, ("batch:1",),
            inventory_authority=main.inventory_authority_service)


@pytest.mark.asyncio
async def test_saved_manifest_rejects_missing_dependency_and_unsupported_decoder(application):
    import copy
    from app.world_runtime.replay_checkpoint import _manifest
    from app.world_runtime.replay_participants import validate_saved_participants
    main, start, advance = application
    await start()
    await advance(86400)
    plan, window = inputs(main)
    await submit(main, plan=plan, window=window, budget=1)
    state = await capture(main)
    assert state["external_dependencies"]
    changed = copy.deepcopy(state)
    changed["external_dependencies"] = {}
    with pytest.raises(ValueError, match="dependency"):
        validate_saved_participants(main.gameplay_event_store, changed, ("batch:1",),
            inventory_authority=main.inventory_authority_service)
    changed = copy.deepcopy(state)
    changed["versions"]["population_recovery"] = 999
    with pytest.raises(ValueError, match="decoder"):
        _manifest(changed, ("batch:1",))
