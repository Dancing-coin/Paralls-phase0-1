from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.gameplay.event_store import GameplayEventStore
from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.models.siming_event import SimingInput
from app.population_continuity import (
    ScheduleGatedSupplyOwnerExecutor,
)
from app.population_continuity.owner_adapters import (
    OrganizationOperatingWindowDueOwnerExecutor,
    OrganizationProductionWorkContributionOwnerExecutor,
)
from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationProjection


ADMITTED_CAPABILITIES = {
    "population:organization-window-due:v1",
    "population:organization-production-work-contribution:v1",
    "population:inventory-output-custody:v1",
    "population:social-population-signal:v1",
}


def _runtime(tmp_path: Path, monkeypatch):
    import app.main as main

    main.reset_runtime_state()
    store = GameplayEventStore()
    monkeypatch.setattr(main, "gameplay_event_store", store)
    state = main.build_runtime_state(
        Settings(heavenly_graph_path=str(tmp_path / "runtime.sqlite3"))
    )
    return state, store


def _unsupported_cadence_event(
    *, candidate_kind: str, source_domain: str, scope: str
) -> AuthorityEvent:
    cadence = PopulationCadenceInput(
        cadence_id="cadence:unsupported:1",
        world_ref="world:test",
        world_mode_ref="mode:test",
        world_mode_revision="mode:test@1",
        cadence_source_ref="gameplay:organization:window:unsupported",
        cadence_source_revision=1,
        window_start=0,
        window_end=1,
        base_checkpoint_ref="checkpoint:test:1",
        base_checkpoint_digest="sha256:checkpoint:test",
        base_revision_vector={"gameplay:organization:window:unsupported": 1},
        policy_revision="policy:test@1",
        selector_revision="selector:generic:population:v1",
        ruleset_revision="rules:generic:test@1",
        deterministic_seed="seed:test:1",
        catch_up_limit=1,
        budget=1,
        report_scope=scope,
    )
    projection = PopulationProjection(
        ref="projection:unsupported:1",
        scope=scope,
        revision_vector={"gameplay:organization:window:unsupported": 1},
        payload={
            "actor_ref": "character:char_a",
            "candidate_kind": candidate_kind,
            "source_domain": source_domain,
        },
    )
    return AuthorityEvent(
        event_id="event:unsupported:1",
        event_type="population_cadence_event",
        producer_ts=1,
        room_id="room:test",
        scene_id="scene:test",
        zone_id="zone:test",
        source=AuthorityEventSource(layer="L2", system="test"),
        routing=AuthorityEventRouting(
            audience_mode="broadcast", routing_mode="event_type"
        ),
        priority="p2",
        durability="replayable",
        causation_id="cause:unsupported:1",
        correlation_id="corr:unsupported:1",
        payload={
            "population_cadence": cadence.model_dump(mode="json"),
            "population_projections": [projection.model_dump(mode="json")],
        },
    )


def test_default_runtime_wires_only_admitted_population_owner_executors(
    tmp_path: Path, monkeypatch
) -> None:
    state, store = _runtime(tmp_path, monkeypatch)
    try:
        capability = state.siming_runtime._population_capability
        assert isinstance(capability._owner_executor, ScheduleGatedSupplyOwnerExecutor)
        assert set(capability._owner_executors) == ADMITTED_CAPABILITIES
        assert isinstance(
            capability._owner_executors[
                "population:organization-production-work-contribution:v1"
            ],
            OrganizationProductionWorkContributionOwnerExecutor,
        )
        window_due = capability._owner_executors[
            "population:organization-window-due:v1"
        ]
        assert isinstance(window_due, OrganizationOperatingWindowDueOwnerExecutor)
        assert callable(window_due.submit_batch)
        assert all(
            executor._authority._store is store
            for executor in capability._owner_executors.values()
        )
    finally:
        state.close()


def test_report_only_tax_capability_has_no_runtime_owner_executor(
    tmp_path: Path, monkeypatch
) -> None:
    state, _ = _runtime(tmp_path, monkeypatch)
    try:
        capability = state.siming_runtime._population_capability
        assert "population:tax-pressure:v1" not in capability._owner_executors
    finally:
        state.close()


def test_active_inventory_and_social_capabilities_use_the_shared_package_registry(
    tmp_path: Path, monkeypatch
) -> None:
    import app.main as main

    state, _ = _runtime(tmp_path, monkeypatch)
    try:
        capability = state.siming_runtime._population_capability
        assert "population:inventory-output-custody:v1" in capability._owner_executors
        assert "population:social-population-signal:v1" in capability._owner_executors
        assert all(
            executor._authority._package_registry is main.production_package_registry
            for executor in capability._owner_executors.values()
            if hasattr(executor._authority, "_package_registry")
        )
    finally:
        state.close()


@pytest.mark.parametrize(
    ("candidate_kind", "source_domain", "scope"),
    (
        ("inventory_output_custody", "inventory", "public"),
        ("social_population_signal", "social", "public"),
    ),
)
def test_unsupported_population_capability_requeues_without_write(
    tmp_path: Path,
    monkeypatch,
    candidate_kind: str,
    source_domain: str,
    scope: str,
) -> None:
    state, store = _runtime(tmp_path, monkeypatch)
    try:
        before = store.export_snapshot()
        result = state.siming_runtime.tick(
            [
                SimingInput(
                    input_type="population_cadence_input",
                    source_event=_unsupported_cadence_event(
                        candidate_kind=candidate_kind,
                        source_domain=source_domain,
                        scope=scope,
                    ),
                )
            ]
        )
        population_audit = next(
            audit for audit in result.audit_records if "population_cycle" in audit.reason
        )
        assert "status=requeue" in population_audit.reason
        assert "reason=owner_rejected" in population_audit.reason
        assert store.export_snapshot() == before
    finally:
        state.close()
