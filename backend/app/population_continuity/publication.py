from __future__ import annotations

from collections.abc import Callable, Mapping

from app.gameplay.event_store import GameplayEventStore
from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationProjection, PopulationOwnerReceipt, dump_population_projections
from app.population_continuity.store_projection_assembler import assemble_committed_population_projections
from app.services.authority_event_bus import AuthorityEventBusPort


def _population_owner_receipt_is_authorized(
    receipt: PopulationOwnerReceipt,
    *,
    cadence: PopulationCadenceInput,
    organization_projection: Mapping[str, object],
    store: GameplayEventStore,
) -> bool:
    if (
        receipt.owner_ref != "actor_gameplay.organization_domain"
        or receipt.event_family
        != "gameplay.organization.production_work_contribution_accepted"
        or not receipt.committed
        or (receipt.zero_write and receipt.idempotency_status != "duplicate_replayed")
        or not receipt.revision_vector
        or dict(receipt.revision_vector) != cadence.base_revision_vector
    ):
        return False
    organization_ref = organization_projection.get("organization_ref")
    if (
        not isinstance(organization_ref, str)
        or not organization_ref.startswith("org:")
        or organization_projection.get("scope") != "organization:summary"
    ):
        return False
    try:
        event = store.get_event(receipt.receipt_ref)
    except KeyError:
        return False
    if not (
        event.event_type
        == "gameplay.organization.production_work_contribution_accepted"
        and event.stream_id == f"gameplay:organization:{organization_ref}"
        and event.stream_revision == receipt.revision_vector.get(event.stream_id)
        and event.visibility_policy == "organization:summary"
        and event.payload.get("organization_ref") == organization_ref
    ):
        return False
    rows = organization_projection.get("acceptance_rows")
    return isinstance(rows, (list, tuple)) and sum(
        isinstance(row, Mapping) and dict(row) == dict(event.payload)
        for row in rows
    ) == 1


def publish_authorized_population_cadence(
    *,
    cadence: PopulationCadenceInput,
    store: GameplayEventStore,
    organization_projection: Mapping[str, object],
    room_id: str,
    scene_id: str,
    zone_id: str,
    causation_id: str,
    correlation_id: str,
    legacy_projections: tuple[PopulationProjection, ...] = (),
    population_projections: tuple[PopulationProjection, ...] = (),
    population_owner_receipt: PopulationOwnerReceipt | None = None,
    event_bus: AuthorityEventBusPort,
    legacy_projection_authorizer: Callable[..., bool] | None = None,
    publish_event: bool = True,
) -> AuthorityEvent | None:
    """Publish one caller-authorized cadence without creating cadence time."""
    source_ref = cadence.cadence_source_ref
    source_revision = cadence.cadence_source_revision
    source_vector_revision = cadence.base_revision_vector.get(source_ref, -1)
    receipt_pins_current_base = population_owner_receipt is not None and (
        _population_owner_receipt_is_authorized(
            population_owner_receipt,
            cadence=cadence,
            organization_projection=organization_projection,
            store=store,
        )
    )
    if population_owner_receipt is not None and not receipt_pins_current_base:
        return None
    if (
        not source_ref
        or source_revision < 1
        or source_vector_revision < source_revision
        or (
            source_vector_revision != source_revision
            and not receipt_pins_current_base
        )
        or any(store.get_stream_head(ref) != revision for ref, revision in cadence.base_revision_vector.items())
    ):
        return None
    source_event = next(
        (
            event
            for event in store.read_stream(source_ref, from_revision=source_revision, to_revision=source_revision)
            if event.stream_id == source_ref
            and event.stream_revision == source_revision
            and event.global_sequence >= 1
        ),
        None,
    )
    if source_event is None:
        return None

    source_payload = source_event.payload
    admitted_visibility = {"project", "public"}
    if cadence.report_scope == "organization:summary":
        admitted_visibility.add("organization:summary")
    declared_visibility = source_payload.get("visibility_scope")
    if (
        source_event.visibility_policy not in admitted_visibility
        or declared_visibility not in (None, source_event.visibility_policy)
    ):
        return None
    if source_event.event_type == "population.world.resume":
        source_authorized = (
            source_ref == f"world:{cadence.world_ref}"
            and source_payload.get("world_ref") == cadence.world_ref
            and source_payload.get("mode_revision") == cadence.world_mode_revision
        )
    elif source_event.event_type in {
        "population.activation.committed",
        "population.activation.region_assigned",
    }:
        source_authorized = (
            source_ref == f"population:{cadence.world_ref}"
            and source_payload.get("world_ref") == cadence.world_ref
        )
    elif source_event.event_type in {
        "gameplay.organization.schedule_recorded",
        "gameplay.organization.work_order_recorded",
    }:
        organization_ref = source_payload.get("organization_ref")
        projection_vector = organization_projection.get("source_revision_vector")
        source_authorized = (
            isinstance(organization_ref, str)
            and source_ref == f"gameplay:organization:{organization_ref}"
            and organization_projection.get("organization_ref") == organization_ref
            and isinstance(projection_vector, Mapping)
            and (
                projection_vector.get(source_ref) == source_revision
                or (
                    receipt_pins_current_base
                    and projection_vector.get(source_ref) == source_vector_revision
                )
            )
        )
    else:
        source_authorized = False
    if not source_authorized:
        return None

    metadata = dict(organization_projection)
    if population_owner_receipt is not None:
        metadata["acceptance_rows"] = [
            dict(store.get_event(population_owner_receipt.receipt_ref).payload)
        ]
    world_mode_projection = metadata.pop("_world_mode_projection", {})
    social_projection = metadata.pop("_social_projection", {})
    household_projection = metadata.pop("_household_projection", {})
    tax_projection = metadata.pop("_tax_projection", None)
    assembly_projection = dict(metadata)
    if isinstance(tax_projection, Mapping):
        assembly_projection["_tax_projection"] = tax_projection
    assembled = assemble_committed_population_projections(
        store=store, cadence=cadence, organization_projection=assembly_projection, incremental=True,
    )
    projections = (*legacy_projections, *population_projections, *assembled)
    accepted: dict[str, PopulationProjection] = {}
    for projection in projections:
        if (
            (
                projection in legacy_projections
                and not (legacy_projection_authorizer is not None and legacy_projection_authorizer(
                    projection,
                    cadence=cadence,
                    store=store,
                    organization_projection=metadata,
                ))
            )
            or
            projection.scope not in {cadence.report_scope, "public"}
            or not projection.revision_vector
            or any(
                cadence.base_revision_vector.get(ref) != revision
                for ref, revision in projection.revision_vector.items()
            )
            or any(
                store.get_stream_head(ref) != revision
                for ref, revision in projection.revision_vector.items()
            )
            or projection.ref in accepted
        ):
            return None
        accepted[projection.ref] = projection

    event = AuthorityEvent(
        event_id=f"event:population-cadence:{cadence.cadence_id}",
        event_type="population_cadence_event",
        producer_ts=cadence.window_start,
        room_id=room_id,
        scene_id=scene_id,
        zone_id=zone_id,
        source=AuthorityEventSource(layer="L2", system="world_runtime.cadence"),
        routing=AuthorityEventRouting(audience_mode="broadcast", routing_mode="event_type"),
        priority="p2",
        durability="realtime",
        causation_id=causation_id,
        correlation_id=correlation_id,
        payload={
            "population_cadence": cadence.model_dump(mode="json"),
            "world_mode_projection": world_mode_projection,
            "activation_projection": {},
            "activation_pending_projection": {},
            "social_projection": social_projection,
            "household_projection": household_projection,
            "organization_projection": metadata,
            "population_projections": dump_population_projections(tuple(accepted[ref] for ref in sorted(accepted))),
            **(
                {"population_owner_receipt": population_owner_receipt.model_dump(mode="json")}
                if population_owner_receipt is not None
                else {}
            ),
        },
    )
    if publish_event:
        event_bus.publish(event)
    return event
