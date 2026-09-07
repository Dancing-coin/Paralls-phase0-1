from __future__ import annotations

from app.character_agent.models.simulation_seed import CharacterContinuityReceipt
from app.gameplay.construction_production_runtime import ConstructionProductionAuthority
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import InventoryAuthorityService
from app.population_continuity.domain_projection_sources import inventory_output_custody_population_projections
from app.population_continuity.inventory_owner_adapter import InventoryOutputCustodyOwnerExecutor
from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationReadSet
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


def _read_set(certification_event: object, *, actor_ref: str = "character:worker") -> PopulationReadSet:
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
    return PopulationReadSet.from_inputs(cadence, (projection,))


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


def test_selected_inventory_candidate_reaches_existing_inventory_owner() -> None:
    _, inventory, certification_event = _fixture()
    read_set = _read_set(certification_event)
    result = PopulationSimulationCapability(
        owner_executors={
            "population:inventory-output-custody:v1": InventoryOutputCustodyOwnerExecutor(authority=inventory)
        }
    ).run_default_decision_cycle(read_set.cadence, read_set)
    assert result.status == "accepted"
    assert result.owner_receipts[0].owner_ref == "actor_gameplay.inventory_domain"
    assert result.owner_receipts[0].event_family == "gameplay.inventory.production_output_received@1"


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
    capability = PopulationSimulationCapability(
        owner_executors={
            "population:inventory-output-custody:v1": InventoryOutputCustodyOwnerExecutor(authority=inventory)
        }
    )
    first = capability.run_default_decision_cycle(read_set.cadence, read_set)
    changed_projection = read_set.projections[0].model_copy(
        update={"payload": {**read_set.projections[0].payload, "summary": "changed caller payload"}}, deep=True
    )
    changed = capability.run_default_decision_cycle(
        read_set.cadence, PopulationReadSet.from_inputs(read_set.cadence, (changed_projection,))
    )
    assert first.owner_receipts[0].committed
    assert changed.owner_receipts[0].idempotency_status == "duplicate_replayed"
    assert changed.owner_receipts[0].zero_write
    assert changed.production_append_count == 0


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
    assert result.owner_receipts[0].committed
    assert result.continuity_receipts[0].source_owner_receipt_refs == (result.owner_receipts[0].receipt_ref,)
