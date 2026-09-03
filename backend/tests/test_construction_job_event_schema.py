from __future__ import annotations

import pytest

from app.gameplay.event_schema_registry import EventSchemaRegistry


def test_construction_job_events_have_source_controlled_schema_registrations() -> None:
    registry = EventSchemaRegistry()
    from app.gameplay.event_schema_registry import register_construction_job_event_schemas

    register_construction_job_event_schemas(registry)
    registry.require("gameplay.construction_production.construction_job_started@1", 1)
    registry.require("gameplay.construction_production.construction_job_completed@1", 1)
    registry.require("gameplay.construction_production.construction_job_failed@1", 1)


def test_construction_job_schema_registration_is_idempotent() -> None:
    registry = EventSchemaRegistry()
    from app.gameplay.event_schema_registry import register_construction_job_event_schemas

    register_construction_job_event_schemas(registry)
    register_construction_job_event_schemas(registry)
    assert len(registry.export_snapshot()["registrations"]) == 3


def test_construction_production_failure_schema_is_source_controlled() -> None:
    registry = EventSchemaRegistry()
    from app.gameplay.event_schema_registry import register_construction_production_failure_event_schemas

    register_construction_production_failure_event_schemas(registry)
    registry.require("gameplay.construction_production.run_failed@1", 1)


def test_construction_maintenance_obligation_schema_is_source_controlled() -> None:
    registry = EventSchemaRegistry()
    from app.gameplay.event_schema_registry import register_construction_maintenance_obligation_event_schemas

    register_construction_maintenance_obligation_event_schemas(registry)
    registry.require("gameplay.construction_production.maintenance_obligation_created", 1)


def test_construction_output_certification_schema_is_source_controlled() -> None:
    registry = EventSchemaRegistry()
    from app.gameplay.event_schema_registry import register_construction_output_certification_event_schemas

    register_construction_output_certification_event_schemas(registry)
    registry.require("gameplay.construction_production.production_output_certified@1", 1)


def test_inventory_output_custody_schema_is_source_controlled() -> None:
    registry = EventSchemaRegistry()
    from app.gameplay.event_schema_registry import register_inventory_output_custody_event_schemas

    register_inventory_output_custody_event_schemas(registry)
    registry.require("gameplay.inventory.production_output_received@1", 1)


def test_construction_lifecycle_and_run_schemas_are_source_controlled() -> None:
    registry = EventSchemaRegistry()
    from app.gameplay.event_schema_registry import register_construction_lifecycle_event_schemas

    register_construction_lifecycle_event_schemas(registry)
    for event_type in (
        "gameplay.construction_production.facility_acquired",
        "gameplay.construction_production.facility_transformed",
        "gameplay.construction_production.facility_decommissioned",
        "gameplay.construction_production.run_started",
        "gameplay.construction_production.run_finished",
    ):
        registry.require(event_type, 1)


def test_construction_production_schema_bundle_registers_all_owner_events_idempotently() -> None:
    from app.gameplay.event_schema_registry import register_construction_production_event_schemas

    registry = EventSchemaRegistry()
    register_construction_production_event_schemas(registry)
    register_construction_production_event_schemas(registry)
    registered = {
        item["event_type"]
        for item in registry.export_snapshot()["registrations"]
    }
    assert {
        "gameplay.construction_production.construction_job_started@1",
        "gameplay.construction_production.construction_job_completed@1",
        "gameplay.construction_production.construction_job_failed@1",
        "gameplay.construction_production.run_failed@1",
        "gameplay.construction_production.maintenance_obligation_created",
        "gameplay.construction_production.production_output_certified@1",
        "gameplay.construction_production.facility_acquired",
        "gameplay.construction_production.facility_transformed",
        "gameplay.construction_production.facility_decommissioned",
        "gameplay.construction_production.run_started",
        "gameplay.construction_production.run_finished",
        "gameplay.inventory.production_output_received@1",
    } <= registered


def test_construction_maintenance_and_repair_schema_bundle_is_source_controlled() -> None:
    from app.gameplay.event_schema_registry import register_construction_maintenance_event_schemas

    registry = EventSchemaRegistry()
    register_construction_maintenance_event_schemas(registry)
    register_construction_maintenance_event_schemas(registry)
    for event_type in (
        "gameplay.construction_production.facility_repaired",
        "gameplay.construction_production.facility_repair_compensated",
        "gameplay.construction_production.maintenance_state_applied",
        "gameplay.construction_production.maintenance_state_obligation_opened",
        "gameplay.construction_production.maintenance_state_obligation_settled",
        "gameplay.construction_production.maintenance_state_expired",
        "gameplay.construction_production.maintenance_state_dispelled",
        "gameplay.construction_production.maintenance_state_obligation_cancelled",
    ):
        registry.require(event_type, 1)
