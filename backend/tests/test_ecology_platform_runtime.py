from __future__ import annotations

from app.gameplay.ecology_platform_runtime import (
    CellRecord,
    CropRecord,
    EcologyPlatformAuthority,
    EcologyPlatformProjector,
    EnvironmentRecord,
    RegionRecord,
    ResourceRecord,
    SpeciesRecord,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.event_schema_registry import EventSchemaRegistry, register_general_ecology_platform_event_schemas


def _region() -> RegionRecord:
    return RegionRecord(
        region_ref="region:district",
        period_ref="period:spring:1",
        climate_profile_ref="climate:temperate",
        biome_tag_refs=("biome:river", "biome:plain"),
        jurisdiction_ref="jurisdiction:district",
    )


def _cell() -> CellRecord:
    return CellRecord(
        cell_ref="cell:a",
        region_ref="region:district",
        period_ref="period:spring:1",
        terrain_ref="terrain:loam",
        moisture_basis_points=6200,
    )


def _environment() -> EnvironmentRecord:
    return EnvironmentRecord(
        environment_ref="environment:district:spring:1",
        region_ref="region:district",
        period_ref="period:spring:1",
        weather_ref="weather:rain-light",
        temperature_centi_c=1834,
        moisture_basis_points=6400,
    )


def _resource() -> ResourceRecord:
    return ResourceRecord(
        resource_ref="resource:water:cell:a",
        region_ref="region:district",
        period_ref="period:spring:1",
        cell_ref="cell:a",
        material_ref="material:water",
        quantity=12,
    )


def _crop() -> CropRecord:
    return CropRecord(
        crop_ref="crop:wheat:cell:a",
        region_ref="region:district",
        period_ref="period:spring:1",
        cell_ref="cell:a",
        species_ref="species:wheat",
        growth_basis_points=4200,
        health_basis_points=9100,
    )


def _species() -> SpeciesRecord:
    return SpeciesRecord(
        species_ref="species:wheat",
        region_ref="region:district",
        period_ref="period:spring:1",
        trophic_role_ref="role:producer",
        population=240,
    )


def _seed(authority: EcologyPlatformAuthority) -> None:
    assert authority.record_region(
        command_id="command:ecology:region",
        idempotency_key="idempotency:ecology:region",
        region=_region(),
        expected_revision=0,
        causation_id="cause:ecology:region",
        correlation_id="corr:ecology:region",
    ).committed
    assert authority.record_cell(
        command_id="command:ecology:cell",
        idempotency_key="idempotency:ecology:cell",
        cell=_cell(),
        expected_revision=0,
        causation_id="cause:ecology:cell",
        correlation_id="corr:ecology:cell",
    ).committed
    assert authority.record_environment(
        command_id="command:ecology:environment",
        idempotency_key="idempotency:ecology:environment",
        environment=_environment(),
        expected_revision=0,
        causation_id="cause:ecology:environment",
        correlation_id="corr:ecology:environment",
    ).committed
    assert authority.record_resource(
        command_id="command:ecology:resource",
        idempotency_key="idempotency:ecology:resource",
        resource=_resource(),
        expected_revision=0,
        causation_id="cause:ecology:resource",
        correlation_id="corr:ecology:resource",
    ).committed
    assert authority.record_crop(
        command_id="command:ecology:crop",
        idempotency_key="idempotency:ecology:crop",
        crop=_crop(),
        expected_revision=0,
        causation_id="cause:ecology:crop",
        correlation_id="corr:ecology:crop",
    ).committed
    assert authority.record_species(
        command_id="command:ecology:species",
        idempotency_key="idempotency:ecology:species",
        species=_species(),
        expected_revision=0,
        causation_id="cause:ecology:species",
        correlation_id="corr:ecology:species",
    ).committed


def test_ecology_platform_records_and_close_are_deterministic_and_checkpoint_safe() -> None:
    store = GameplayEventStore()
    authority = EcologyPlatformAuthority(store=store)
    _seed(authority)

    first_transaction = store.read_transactions()[0]
    assert first_transaction.owner_fragments[0].owner_principal_ref == "actor_gameplay.ecology_domain"

    close = authority.close_region_period(
        command_id="command:ecology:close",
        idempotency_key="idempotency:ecology:close",
        close_ref="close:region:district:period:spring:1",
        region_ref="region:district",
        period_ref="period:spring:1",
        expected_revision=0,
        causation_id="cause:ecology:close",
        correlation_id="corr:ecology:close",
    )

    assert close.committed
    assert close.zero_write is False
    assert close.close is not None
    assert close.close.ordered_record_refs == (
        "region:district",
        "cell:a",
        "environment:district:spring:1",
        "resource:water:cell:a",
        "crop:wheat:cell:a",
        "species:wheat",
    )

    close_event = store.get_event(close.append_result.committed_event_ids[0])  # type: ignore[union-attr]
    assert close_event.event_type == "gameplay.ecology.region_period_closed@1"
    assert close_event.payload["close"]["ordered_record_refs"] == list(close.close.ordered_record_refs)

    projector = EcologyPlatformProjector()
    full = projector.rebuild(store.read_events())
    checkpoint = projector.create_checkpoint(store.read_events()[:3])
    tail = projector.rebuild(store.read_events()[3:], checkpoint=checkpoint)

    assert full == tail
    assert authority.replay().projection_hash == authority.replay(checkpoint_at=3).projection_hash
    assert full.closes["close:region:district:period:spring:1"].summary_digest == close.close.summary_digest


def test_ecology_platform_privacy_and_close_revision_vector_mismatch_are_zero_write() -> None:
    store = GameplayEventStore()
    authority = EcologyPlatformAuthority(store=store)

    before_private = store.export_snapshot()
    private = authority.record_region(
        command_id="command:ecology:private",
        idempotency_key="idempotency:ecology:private",
        region=_region(),
        expected_revision=0,
        causation_id="cause:ecology:private",
        correlation_id="corr:ecology:private",
        privacy_scope="authority_only",
    )
    assert not private.committed
    assert private.zero_write
    assert private.error_code == "ecology_platform_privacy_scope_denied"
    assert store.export_snapshot() == before_private

    _seed(authority)
    before_close = store.export_snapshot()
    mismatch = authority.close_region_period(
        command_id="command:ecology:close:mismatch",
        idempotency_key="idempotency:ecology:close:mismatch",
        close_ref="close:region:district:period:spring:1",
        region_ref="region:district",
        period_ref="period:spring:1",
        expected_revision=0,
        causation_id="cause:ecology:close:mismatch",
        correlation_id="corr:ecology:close:mismatch",
        required_revision_vector={"gameplay:ecology:platform:region:region:district": 99},
    )
    assert not mismatch.committed
    assert mismatch.zero_write
    assert mismatch.error_code == "ecology_platform_close_revision_vector_mismatch"
    assert store.export_snapshot() == before_close


def test_ecology_platform_event_bundle_is_admitted_by_registry_backed_store() -> None:
    registry = EventSchemaRegistry()
    register_general_ecology_platform_event_schemas(registry)
    store = GameplayEventStore(event_schema_registry=registry)
    authority = EcologyPlatformAuthority(store=store)
    result = authority.record_region(
        command_id="command:ecology:registry",
        idempotency_key="idempotency:ecology:registry",
        region=_region(),
        expected_revision=0,
        causation_id="cause:ecology:registry",
        correlation_id="corr:ecology:registry",
    )
    assert result.committed


def test_ecology_platform_duplicate_idempotency_and_revision_conflict_are_zero_write() -> None:
    store = GameplayEventStore()
    authority = EcologyPlatformAuthority(store=store)

    first = authority.record_species(
        command_id="command:ecology:species:first",
        idempotency_key="idempotency:ecology:species:first",
        species=_species(),
        expected_revision=0,
        causation_id="cause:ecology:species:first",
        correlation_id="corr:ecology:species:first",
    )
    assert first.committed
    before_duplicate = store.export_snapshot()

    duplicate = authority.record_species(
        command_id="command:ecology:species:first",
        idempotency_key="idempotency:ecology:species:first",
        species=_species(),
        expected_revision=0,
        causation_id="cause:ecology:species:first",
        correlation_id="corr:ecology:species:first",
    )
    assert duplicate.committed
    assert duplicate.zero_write
    assert duplicate.append_result is not None
    assert duplicate.append_result.idempotency_status == "duplicate_replayed"
    assert duplicate.append_result.committed_event_ids == first.append_result.committed_event_ids  # type: ignore[union-attr]
    assert store.export_snapshot() == before_duplicate

    changed = authority.record_species(
        command_id="command:ecology:species:changed",
        idempotency_key="idempotency:ecology:species:first",
        species=_species().model_copy(update={"population": 241}),
        expected_revision=0,
        causation_id="cause:ecology:species:first",
        correlation_id="corr:ecology:species:first",
    )
    assert not changed.committed
    assert changed.zero_write
    assert changed.error_code == "idempotency_key_reused"
    assert store.export_snapshot() == before_duplicate

    conflict = authority.record_species(
        command_id="command:ecology:species:conflict",
        idempotency_key="idempotency:ecology:species:conflict",
        species=_species().model_copy(update={"population": 242}),
        expected_revision=0,
        causation_id="cause:ecology:species:conflict",
        correlation_id="corr:ecology:species:conflict",
    )
    assert not conflict.committed
    assert conflict.zero_write
    assert conflict.error_code == "revision_conflict"
    assert store.export_snapshot() == before_duplicate
