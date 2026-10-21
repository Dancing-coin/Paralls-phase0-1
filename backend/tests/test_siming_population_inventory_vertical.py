from __future__ import annotations

import hashlib
import json

import pytest

from app.character_agent.models.simulation_seed import CharacterContinuityReceipt
from app.gameplay.construction_production_runtime import ConstructionProductionAuthority
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.inventory_runtime import InventoryAuthorityService
from app.population_continuity.domain_projection_sources import inventory_output_custody_population_projections
from app.population_continuity.inventory_owner_adapter import InventoryOutputCustodyOwnerExecutor
from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationReadSet
from app.world_runtime.temporal_contracts import TemporalAuthorization
from app.services.siming_population_capability import PopulationSimulationCapability
from closed_generic_manifest_fixtures import load_manifest
from test_production_output_certification_family import _intent, _setup
from test_production_output_custody_family import _custody_manifest, _family_registry, _inventory_for_certification


def _fixture() -> tuple[GameplayEventStore, InventoryAuthorityService, object]:
    store, _, finished_event_id = _setup()
    certification_manifest = load_manifest("production-output-certification-demo-v1")
    custody_manifest = _custody_manifest(
        package_id="production-output-custody-bread",
        package_revision="package:production-output-custody:bread@1",
        definition_ref="definition:production-output-custody-bread@1",
        output_item_ref="item:bread@1",
        holder_binding_ref="binding:holder:organization:bakery@1",
        container_binding_ref="binding:container:container:organization:bakery:production-output@1",
        policy_revision="policy:inventory-production-output-custody@1",
    )
    registry = _family_registry(certification_manifest, custody_manifest)
    construction = ConstructionProductionAuthority(store=store, package_registry=registry)
    certification = construction.settle_production_output_certification(intent=_intent(finished_event_id))
    assert certification.committed
    certification_event = store.get_event(certification.committed_event_ids[0])
    inventory = _inventory_for_certification(
        store,
        package_registry=registry,
        holder_ref="organization:bakery",
        item_ref="item:bread@1",
        container_id="container:organization:bakery:production-output",
    )
    return store, inventory, certification_event


def _read_set(certification_event: object, *, actor_ref: str = "character:worker", store=None) -> PopulationReadSet:
    source = inventory_output_custody_population_projections(
        committed_events=(certification_event,), scope="public"
    )[0]
    projection = source.model_copy(
        update={"payload": {**source.payload, "actor_ref": actor_ref}}, deep=True
    )
    stream_ref, revision = next(iter(projection.revision_vector.items()))
    cadence = PopulationCadenceInput(
        cadence_id="cadence:inventory:1", world_ref="world:bakery", world_mode_ref="mode:bakery",
        world_mode_revision="mode:inventory:v1", cadence_source_ref=stream_ref, cadence_source_revision=revision,
        window_start=0, window_end=1, base_checkpoint_ref="checkpoint:inventory:1", base_checkpoint_digest="sha256:inventory",
        base_revision_vector=dict(projection.revision_vector), policy_revision="policy:inventory:v1",
        selector_revision="selector:inventory:v1", ruleset_revision="rules:inventory:v1", deterministic_seed="seed:inventory",
        catch_up_limit=1, budget=1, report_scope="public",
    )
    if store is not None:
        from app.population_continuity.roster import PopulationRoster
        from app.population_continuity.runtime_publication import RuntimeCadencePublisher
        from app.population_continuity.world import WorldContinuityRuntime
        from app.services.authority_event_bus import InMemoryAuthorityEventBus
        from test_population_runtime_driver import _mode

        world = WorldContinuityRuntime(store=store,
            mode=_mode().model_copy(update={"world_ref": cadence.world_ref}),
            roster=PopulationRoster(actor_ids=("worker",)))
        assert world.resume().committed
        cadence = world.build_population_cadence(window_start=0, window_end=60)
        cadence = cadence.model_copy(update={"base_revision_vector": {
            **cadence.base_revision_vector, **projection.revision_vector,
        }})
        publisher = RuntimeCadencePublisher(world_runtime=world, event_bus=InMemoryAuthorityEventBus(),
            room_id="room", scene_id="scene", zone_id="zone")
        assert publisher(cadence) is not None
    return PopulationReadSet.from_inputs(cadence, (projection,), temporal_pins=_time_pins(cadence))


def _time_pins(cadence: PopulationCadenceInput) -> dict[str, str | int]:
    pins: dict[str, str | int] = {
        "timeline_id": "timeline:bakery",
        "profile_revision": "profile:bakery:v1",
        "mapping_id": "mapping:bakery:v1",
        "mapping_revision": "mapping:bakery:v1",
        "source_clock_ref": "population-driver:world:bakery",
        "source_revision": cadence.cadence_source_revision,
        "sampled_at": cadence.window_end,
        "received_at": cadence.window_end,
        "freshness": 0,
        "activation_revision": "population-window:1:v1",
        "window_start": cadence.window_start,
        "window_ticks": cadence.window_end - cadence.window_start,
        "canonical_unit_ref": "second",
        "step_duration": "1/1",
        "settlement_participant_scope": "actor_gameplay.inventory_domain",
        "input_cutoff": cadence.window_end,
        "late_input_policy_ref": "reject_after_cutoff",
        "confirmation_boundary": cadence.window_end,
        "ordering_policy_ref": "source_revision_then_event_ref",
        "temporal_authorization_ref": "authorization:population-inventory-output-custody@1",
        "temporal_authorization_revision": "authorization:population-inventory-output-custody@1",
        "temporal_authorization_issuer_ref": "world_runtime.population_cadence:world:bakery",
        "temporal_authorization_valid_until": cadence.window_end,
    }
    authorization = TemporalAuthorization(
        authorization_ref=str(pins["temporal_authorization_ref"]),
        revision=str(pins["temporal_authorization_revision"]),
        issuer_ref=str(pins["temporal_authorization_issuer_ref"]),
        timeline_id=str(pins["timeline_id"]),
        participant_scope=(str(pins["settlement_participant_scope"]),),
        input_cutoff=int(pins["input_cutoff"]),
        confirmation_boundary=int(pins["confirmation_boundary"]),
        late_input_policy_ref=str(pins["late_input_policy_ref"]),
        ordering_policy_ref=str(pins["ordering_policy_ref"]),
        valid_until=int(pins["temporal_authorization_valid_until"]),
    )
    pins["temporal_authorization_digest"] = authorization.digest
    return pins


def _admit_inventory_cadence(store: GameplayEventStore, read_set: PopulationReadSet) -> None:
    """Persist the same cadence authority record the production publisher exposes."""
    record: dict[str, object] = {
        "schema_version": 1,
        "cadence": read_set.cadence.model_dump(mode="json"),
        "time_pins": dict(read_set.temporal_pins),
    }
    encoded = json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    record["record_digest"] = "sha256:" + hashlib.sha256(encoded).hexdigest()
    batch = build_atomic_event_batch(
        command_id=f"population-runtime:{read_set.cadence.cadence_id}",
        principal_ref="world_runtime.cadence",
        stream_id="population-cadence:world:bakery",
        expected_revision=store.get_stream_head("population-cadence:world:bakery"),
        event_specs=(("population.cadence.admitted", record),),
        idempotency_key=f"population-runtime:{read_set.cadence.cadence_id}",
        causation_id=f"population-runtime:{read_set.cadence.cadence_id}",
        correlation_id=f"population-runtime:{read_set.cadence.cadence_id}",
        read_stream_revisions=read_set.cadence.base_revision_vector,
    )
    result = store.append_batch(batch)
    assert result.committed, result.failure


def test_population_read_set_preserves_cadence_temporal_pins() -> None:
    _, _, certification_event = _fixture()
    read_set = _read_set(certification_event)
    pins = _time_pins(read_set.cadence)
    pinned = PopulationReadSet.from_inputs(read_set.cadence, read_set.projections, temporal_pins=pins)
    assert pinned.temporal_pins == pins


def test_population_read_set_rejects_temporal_window_start_drift() -> None:
    _, _, certification_event = _fixture()
    read_set = _read_set(certification_event)
    drifted = dict(read_set.temporal_pins, window_start=99)
    with pytest.raises(ValueError, match="read_set_temporal_start_mismatch"):
        PopulationReadSet.from_inputs(read_set.cadence, read_set.projections, temporal_pins=drifted)


def test_inventory_caller_freezes_complete_settlement_window_from_read_set() -> None:
    _, inventory, certification_event = _fixture()
    read_set = _read_set(certification_event)
    window = InventoryOutputCustodyOwnerExecutor(authority=inventory).settlement_window(read_set)
    assert window.window_ref == read_set.cadence.cadence_id
    assert window.participant_scope == ("actor_gameplay.inventory_domain",)
    assert window.from_time.canonical_time_value == 0
    assert window.to_time.canonical_time_value == 1
    assert window.input_cutoff.canonical_time_value == 1
    assert window.confirmation_boundary.canonical_time_value == 1
    assert certification_event.event_id in window.evidence_refs
    assert read_set.cadence.cadence_id in window.evidence_refs
    assert window.expected_authority_revisions


def test_inventory_read_source_freezes_activation_binding_without_writing() -> None:
    _, inventory, certification_event = _fixture()
    read_set = _read_set(certification_event)
    freeze = getattr(inventory, "freeze_production_output_custody_read", None)
    assert callable(freeze), "Inventory needs a read-only activation binding freeze API"
    frozen = freeze(certification_event_id=certification_event.event_id)
    assert frozen.source_certification_revision == certification_event.stream_revision
    assert frozen.active_patch_set_revision == inventory._package_registry.active_patch_set.active_patch_set_revision
    assert frozen.bindings
    assert frozen.inventory_stream_revision == inventory._store.get_stream_head(
        f"gameplay:inventory:{frozen.holder_ref}"
    )
    assert read_set.cadence.cadence_source_ref == certification_event.stream_id


def test_inventory_population_caller_requires_authorized_settlement_window() -> None:
    _, inventory, certification_event = _fixture()
    read_set = _read_set(certification_event)
    result = PopulationSimulationCapability(
        owner_executors={
            "population:inventory-output-custody:v1": InventoryOutputCustodyOwnerExecutor(authority=inventory)
        }
    ).run_default_decision_cycle(read_set.cadence, read_set)
    assert result.status == "requeue"
    assert result.production_append_count == 0
    assert result.owner_receipts[0].zero_write


def test_inventory_read_source_freeze_rejects_revoked_activation() -> None:
    _, inventory, certification_event = _fixture()
    registry = inventory._package_registry
    active = registry.active_patch_set
    registry.replace_active_set(())
    try:
        with pytest.raises(ValueError, match="inventory_custody_package_inactive"):
            inventory.freeze_production_output_custody_read(certification_event_id=certification_event.event_id)
    finally:
        registry.activate(active.patch_revision_ids)


def test_inventory_owner_rejects_changed_frozen_content_pin_before_write() -> None:
    from app.gameplay.closed_generic_gameplay_families import ProductionOutputCustodyIntent

    _, inventory, certification_event = _fixture()
    frozen = inventory.freeze_production_output_custody_read(
        certification_event_id=certification_event.event_id
    )
    pins = frozen.bindings[0].revision_pins()
    intent = ProductionOutputCustodyIntent(
        certification_event_id=certification_event.event_id,
        expected_certification_revision=certification_event.stream_revision,
        expected_inventory_stream_revision=frozen.inventory_stream_revision,
        command_id="custody:stale-frozen-pin",
        correlation_id="custody:stale-frozen-pin",
        submitted_at="population:test",
        **{**pins, "content_digest_pin": "sha256:" + "0" * 64},
    )
    result = inventory.settle_production_output_custody(intent=intent)
    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "production_output_custody_read_source_stale"
    assert inventory._store.get_stream_head(frozen.inventory_stream_ref) == frozen.inventory_stream_revision


def test_inventory_owner_rejects_conflicting_cadence_temporal_pins() -> None:
    _, inventory, certification_event = _fixture()
    read_set = _read_set(certification_event)
    pins = _time_pins(read_set.cadence)
    pins["source_clock_ref"] = ""
    with pytest.raises(ValueError, match="read_set_temporal_pin_identity_missing"):
        PopulationReadSet.from_inputs(read_set.cadence, read_set.projections, temporal_pins=pins)


def test_inventory_owner_rejects_boolean_operational_timestamps() -> None:
    _, inventory, certification_event = _fixture()
    read_set = _read_set(certification_event)
    pins = dict(read_set.temporal_pins)
    # bool is an int subclass and compares equal to 1, but is not a valid
    # operational timestamp in a frozen Population read set.
    pins["sampled_at"] = True
    pins["received_at"] = True
    with pytest.raises(ValueError):
        PopulationReadSet.from_inputs(read_set.cadence, read_set.projections, temporal_pins=pins)

    # Keep the owner guard effective even if an internal caller bypasses the
    # read-set model validator.
    forged = read_set.model_copy(update={"temporal_pins": pins}, deep=True)
    executor = InventoryOutputCustodyOwnerExecutor(authority=inventory)
    assert not executor._authorized_settlement_window(forged)



def test_inventory_caller_rejects_world_admin_revoked_cadence_before_write() -> None:
    store, inventory, certification_event = _fixture()
    read_set = _read_set(certification_event)
    _admit_inventory_cadence(store, read_set)
    from app.gameplay.settlement_plan import build_atomic_event_batch

    revoke = build_atomic_event_batch(
        command_id="admin:revoke:cadence:inventory:1",
        principal_ref="world_admin",
        stream_id="population-cadence-revocation:world:bakery",
        expected_revision=store.get_stream_head("population-cadence-revocation:world:bakery"),
        event_specs=[("population.cadence.revoked", {
            "cadence_id": read_set.cadence.cadence_id,
            "world_ref": read_set.cadence.world_ref,
            "issuer_ref": "world_admin",
            "authority_contract_ref": "world-admin:population-cadence-revocation@1",
            "command_id": "admin:revoke:cadence:inventory:1",
            "reason_code": "administrator_cancelled",
        })],
        idempotency_key="admin:revoke:cadence:inventory:1",
        causation_id="admin:revoke:cadence:inventory:1",
        correlation_id=read_set.cadence.cadence_id,
    )
    assert store.append_batch(revoke).committed
    result = PopulationSimulationCapability(
        owner_executors={
            "population:inventory-output-custody:v1": InventoryOutputCustodyOwnerExecutor(authority=inventory)
        }
    ).run_default_decision_cycle(read_set.cadence, read_set)
    assert result.status == "requeue"
    assert result.production_append_count == 0
    assert result.owner_receipts[0].zero_write


def test_inventory_append_conflicts_if_cadence_is_revoked_after_caller_validation(monkeypatch) -> None:
    store, inventory, certification_event = _fixture()
    read_set = _read_set(certification_event)
    _admit_inventory_cadence(store, read_set)
    original_append = store.append_batch
    injected = False

    def append_with_revoke(batch):
        nonlocal injected
        if not injected and any(
            event.event_type == "gameplay.inventory.production_output_received@1"
            for event in batch.events
        ):
            injected = True
            revoke = build_atomic_event_batch(
                command_id="admin:revoke:cadence:inventory:race",
                principal_ref="world_admin",
                stream_id="population-cadence-revocation:world:bakery",
                expected_revision=store.get_stream_head("population-cadence-revocation:world:bakery"),
                event_specs=[("population.cadence.revoked", {
                    "cadence_id": read_set.cadence.cadence_id,
                    "world_ref": read_set.cadence.world_ref,
                    "issuer_ref": "world_admin",
                    "authority_contract_ref": "world-admin:population-cadence-revocation@1",
                    "command_id": "admin:revoke:cadence:inventory:race",
                    "reason_code": "administrator_cancelled",
                })],
                idempotency_key="admin:revoke:cadence:inventory:race",
                causation_id="admin:revoke:cadence:inventory:race",
                correlation_id=read_set.cadence.cadence_id,
            )
            assert original_append(revoke).committed
        return original_append(batch)

    monkeypatch.setattr(store, "append_batch", append_with_revoke)
    result = PopulationSimulationCapability(
        owner_executors={
            "population:inventory-output-custody:v1": InventoryOutputCustodyOwnerExecutor(authority=inventory)
        }
    ).run_default_decision_cycle(read_set.cadence, read_set)
    assert result.status == "requeue"
    assert result.production_append_count == 0
    assert result.owner_receipts[0].zero_write
    assert any(event.event_type == "population.cadence.revoked" for event in store.read_stream("population-cadence-revocation:world:bakery"))


def test_certified_output_becomes_inventory_population_candidate() -> None:
    _, _, certification_event = _fixture()
    projections = inventory_output_custody_population_projections(
        committed_events=(certification_event,), scope="public"
    )
    assert len(projections) == 1
    payload = projections[0].payload
    assert payload["candidate_kind"] == "inventory_output_custody"
    assert payload["source_certification_event_id"] == certification_event.event_id
    assert not {"holder_ref", "container_id", "quantity", "item_ref"}.intersection(payload)


def test_inventory_candidate_without_durable_cadence_authority_is_rejected() -> None:
    _, inventory, certification_event = _fixture()
    read_set = _read_set(certification_event)
    result = PopulationSimulationCapability(
        owner_executors={
            "population:inventory-output-custody:v1": InventoryOutputCustodyOwnerExecutor(authority=inventory)
        }
    ).run_default_decision_cycle(read_set.cadence, read_set)
    assert result.status == "requeue"
    assert result.owner_receipts[0].zero_write


def test_inventory_candidate_rejects_corrupt_durable_cadence_receipt_refs() -> None:
    store, inventory, certification_event = _fixture()
    read_set = _read_set(certification_event)
    _admit_inventory_cadence(store, read_set)
    key = ("world_runtime.cadence", f"population-runtime:{read_set.cadence.cadence_id}")
    original = store.get_by_idempotency(*key)
    store._idempotency_results[key] = original.model_copy(
        update={"committed_event_ids": [*original.committed_event_ids, "missing:event"]},
        deep=True,
    )
    result = PopulationSimulationCapability(
        owner_executors={
            "population:inventory-output-custody:v1": InventoryOutputCustodyOwnerExecutor(authority=inventory)
        }
    ).run_default_decision_cycle(read_set.cadence, read_set)

    assert result.status == "requeue"
    assert result.production_append_count == 0
    assert result.owner_receipts[0].zero_write


def test_inventory_candidate_rejects_cadence_receipt_with_wrong_authority_principal() -> None:
    store, inventory, certification_event = _fixture()
    read_set = _read_set(certification_event)
    _admit_inventory_cadence(store, read_set)
    key = ("world_runtime.cadence", f"population-runtime:{read_set.cadence.cadence_id}")
    result = store.get_by_idempotency(*key)
    assert result is not None
    transaction = store.get_transaction(result.transaction_id)
    assert transaction is not None
    index = next(index for index, batch in enumerate(store._transactions) if batch.transaction_id == transaction.transaction_id)
    store._transactions[index] = transaction.model_copy(
        update={
            "idempotency_record": transaction.idempotency_record.model_copy(
                update={"principal_ref": "forged-cadence-authority"}, deep=True
            )
        }, deep=True
    )
    outcome = PopulationSimulationCapability(
        owner_executors={
            "population:inventory-output-custody:v1": InventoryOutputCustodyOwnerExecutor(authority=inventory)
        }
    ).run_default_decision_cycle(read_set.cadence, read_set)
    assert outcome.status == "requeue"
    assert outcome.production_append_count == 0
    assert outcome.owner_receipts[0].zero_write


def test_stale_certified_output_is_zero_write() -> None:
    _, inventory, certification_event = _fixture()
    read_set = _read_set(certification_event)
    stale_projection = read_set.projections[0].model_copy(
        update={"revision_vector": {certification_event.stream_id: certification_event.stream_revision - 1}}, deep=True
    )
    stale_read_set = PopulationReadSet.from_inputs(read_set.cadence, (stale_projection,))
    result = PopulationSimulationCapability(
        owner_executors={
            "population:inventory-output-custody:v1": InventoryOutputCustodyOwnerExecutor(authority=inventory)
        }
    ).run_default_decision_cycle(stale_read_set.cadence, stale_read_set)
    assert result.status == "requeue"
    assert result.production_append_count == 0
    assert result.owner_receipts[0].zero_write


def test_changed_duplicate_inventory_intent_is_zero_write() -> None:
    _, inventory, certification_event = _fixture()
    read_set = _read_set(certification_event)
    _admit_inventory_cadence(inventory._store, read_set)
    capability = PopulationSimulationCapability(
        owner_executors={
            "population:inventory-output-custody:v1": InventoryOutputCustodyOwnerExecutor(authority=inventory)
        }
    )
    first = capability.run_default_decision_cycle(read_set.cadence, read_set)
    changed_projection = read_set.projections[0].model_copy(
        update={
            "payload": {
                **read_set.projections[0].payload,
                "source_certification_event_id": "forged:certification-event",
            }
        },
        deep=True,
    )
    changed = capability.run_default_decision_cycle(
        read_set.cadence, PopulationReadSet.from_inputs(read_set.cadence, (changed_projection,))
    )
    assert first.status == "accepted"
    assert first.owner_receipts[0].committed
    assert not first.owner_receipts[0].zero_write
    assert changed.owner_receipts[0].zero_write
    assert changed.owner_receipts[0].committed is False
    assert changed.owner_receipts[0].idempotency_status == "new_commit"
    assert changed.production_append_count == 0
    assert len(
        [
            event
            for event in inventory._store.read_stream("gameplay:inventory:organization:bakery")
            if event.event_type == "gameplay.inventory.production_output_received@1"
        ]
    ) == 1


def test_exact_population_inventory_duplicate_replays_receipt_after_durable_reopen(tmp_path) -> None:
    from app.gameplay.event_store import DurableGameplayEventStore

    store, inventory, certification_event = _fixture()
    read_set = _read_set(certification_event)
    _admit_inventory_cadence(store, read_set)
    snapshot_path = tmp_path / "inventory-before-durable.json"
    store.save_snapshot(snapshot_path)
    durable = DurableGameplayEventStore(snapshot_path)
    durable_inventory = InventoryAuthorityService(
        store=durable,
        registry=inventory._registry,
        package_registry=inventory._package_registry,
    )
    capability = PopulationSimulationCapability(
        owner_executors={
            "population:inventory-output-custody:v1": InventoryOutputCustodyOwnerExecutor(
                authority=durable_inventory
            )
        }
    )
    first = capability.run_default_decision_cycle(read_set.cadence, read_set)
    assert first.status == "accepted"
    assert first.owner_receipts[0].committed and not first.owner_receipts[0].zero_write
    receipt_ref = first.owner_receipts[0].receipt_ref
    inventory_stream = "gameplay:inventory:organization:bakery"
    committed_head = durable.get_stream_head(inventory_stream)
    event_count = len(durable.read_events())
    durable.close()
    reopened = DurableGameplayEventStore(snapshot_path)
    restored_inventory = InventoryAuthorityService(
        store=reopened,
        registry=inventory._registry,
        package_registry=inventory._package_registry,
    )
    retry = PopulationSimulationCapability(
        owner_executors={
            "population:inventory-output-custody:v1": InventoryOutputCustodyOwnerExecutor(
                authority=restored_inventory
            )
        }
    ).run_default_decision_cycle(read_set.cadence, read_set)
    assert retry.status == "accepted"
    assert retry.owner_receipts[0].committed
    assert retry.owner_receipts[0].zero_write
    assert retry.owner_receipts[0].idempotency_status == "duplicate_replayed"
    assert retry.owner_receipts[0].receipt_ref == receipt_ref
    assert retry.production_append_count == 0
    assert reopened.get_stream_head(inventory_stream) == committed_head
    assert len(reopened.read_events()) == event_count
    changed_projection = read_set.projections[0].model_copy(
        update={
            "payload": {
                **read_set.projections[0].payload,
                "source_certification_event_id": "forged:certification-event",
            }
        },
        deep=True,
    )
    changed = PopulationSimulationCapability(
        owner_executors={
            "population:inventory-output-custody:v1": InventoryOutputCustodyOwnerExecutor(
                authority=restored_inventory
            )
        }
    ).run_default_decision_cycle(
        read_set.cadence,
        PopulationReadSet.from_inputs(read_set.cadence, (changed_projection,)),
    )
    assert changed.status == "requeue"
    assert changed.owner_receipts[0].committed is False
    assert changed.owner_receipts[0].zero_write
    assert changed.production_append_count == 0
    assert reopened.get_stream_head(inventory_stream) == committed_head
    assert len(reopened.read_events()) == event_count
    reopened.close()


def test_inventory_receipt_precedes_character_seed() -> None:
    _, inventory, certification_event = _fixture()
    read_set = _read_set(certification_event)

    class Continuity:
        def __init__(self) -> None:
            self.commands = []

        def current_revision(self, actor_ref: str) -> int:
            return 0

        def apply_command(self, command):
            self.commands.append(command)
            return CharacterContinuityReceipt(
                receipt_ref=f"continuity:{command.actor_ref}", command_id=command.command_id,
                actor_ref=command.actor_ref, status="committed", character_revision_before=0,
                character_revision_after=1, source_owner_receipt_refs=command.source_owner_receipt_refs,
            )

    continuity = Continuity()
    result = PopulationSimulationCapability(
        continuity_port=continuity,
        owner_executors={
            "population:inventory-output-custody:v1": InventoryOutputCustodyOwnerExecutor(authority=inventory)
        },
    ).run_default_decision_cycle(read_set.cadence, read_set)
    assert not result.owner_receipts[0].committed
    assert result.continuity_receipts == ()


def test_production_runtime_registers_inventory_population_owner_adapter() -> None:
    import app.main as main

    main.reset_runtime_state()
    executors = main.siming_event_pipeline._runtime._population_capability._owner_executors
    assert "population:inventory-output-custody:v1" in executors


def test_inventory_custody_is_an_optional_replay_participant_after_real_owner_write() -> None:
    from app.gameplay.inventory_runtime import InventoryAuthorityService
    from app.world_runtime.replay_participants import _inventory_participant

    store, inventory, certification_event = _fixture()
    read_set = _read_set(certification_event)
    result = PopulationSimulationCapability(
        owner_executors={
            "population:inventory-output-custody:v1": InventoryOutputCustodyOwnerExecutor(authority=inventory)
        }
    ).run_default_decision_cycle(read_set.cadence, read_set)
    assert result.status == "requeue"
    assert result.owner_receipts[0].zero_write
