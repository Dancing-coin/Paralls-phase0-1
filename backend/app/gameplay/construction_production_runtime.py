"""Minimal Construction/Production owner for the Econ-1 bakery slice."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping, Sequence

from pydantic import ConfigDict, Field

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent, StrictGameplayModel
from app.gameplay.settlement_plan import build_atomic_event_batch


class Plot(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    plot_ref: str = Field(min_length=1)
    jurisdiction_ref: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    revision: int = Field(default=0, ge=0)


class Blueprint(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    blueprint_ref: str = Field(min_length=1)
    facility_kind: str = Field(min_length=1)
    required_permit_ref: str = Field(min_length=1)
    revision: int = Field(default=1, ge=1)


class Facility(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    facility_ref: str = Field(min_length=1)
    plot_ref: str = Field(min_length=1)
    facility_kind: str = Field(min_length=1)
    condition: float = Field(ge=0, le=1)
    revision: int = Field(default=0, ge=0)


class Recipe(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    recipe_ref: str = Field(min_length=1)
    inputs: dict[str, int] = Field(default_factory=dict)
    output_item: str = Field(min_length=1)
    duration_ticks: int = Field(gt=0)


class ConstructionJob(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    job_ref: str = Field(min_length=1)
    plot_ref: str = Field(min_length=1)
    blueprint_ref: str = Field(min_length=1)
    status: Literal["planned", "started", "completed", "failed"] = "planned"
    reservation_refs: tuple[str, ...] = ()
    pinned_revisions: dict[str, int] = Field(default_factory=dict)


class ProductionRun(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_ref: str = Field(min_length=1)
    facility_ref: str = Field(min_length=1)
    recipe_ref: str = Field(min_length=1)
    status: Literal["started", "completed", "lost", "released"] = "started"
    started_tick: int = Field(ge=0)
    finish_tick: int = Field(ge=0)
    reservation_refs: tuple[str, ...] = ()
    output_item: str | None = None
    maintenance_obligation_ref: str | None = None
    work_order_ref: str | None = None
    shift_ref: str | None = None
    worker_contribution_refs: tuple[str, ...] = ()
    facility_slot_ref: str | None = None


@dataclass(frozen=True)
class ConstructionProductionProjection:
    """Read model rebuilt from this authority's committed facts only."""

    runs: Mapping[str, ProductionRun]
    source_revision_vector: Mapping[str, int]
    facilities: Mapping[str, Facility] = field(default_factory=dict)


class ConstructionProductionProjector:
    _STARTED = "gameplay.construction_production.run_started"
    _FINISHED = "gameplay.construction_production.run_finished"
    _MAINTENANCE = "gameplay.construction_production.maintenance_obligation_created"
    _ACQUIRED = "gameplay.construction_production.facility_acquired"

    def rebuild(self, events: Sequence[GameplayEvent]) -> ConstructionProductionProjection:
        runs: dict[str, ProductionRun] = {}
        facilities: dict[str, Facility] = {}
        revisions: dict[str, int] = {}
        for event in sorted(events, key=lambda value: (value.global_sequence, value.event_id)):
            if event.event_type not in {self._STARTED, self._FINISHED, self._MAINTENANCE, self._ACQUIRED}:
                continue
            payload = event.payload
            if event.event_type == self._ACQUIRED:
                facility_ref = str(payload.get("facility_ref", ""))
                if not facility_ref or facility_ref in facilities:
                    raise ValueError("facility_duplicate")
                facilities[facility_ref] = Facility(
                    facility_ref=facility_ref,
                    plot_ref=str(payload["plot_ref"]),
                    facility_kind=str(payload["facility_kind"]),
                    condition=float(payload["condition"]),
                    revision=int(payload.get("revision", 0)),
                )
                revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
                continue
            run_ref = str(payload.get("run_ref", ""))
            if not run_ref:
                raise ValueError("construction_event_payload_invalid")
            if event.event_type == self._STARTED:
                if run_ref in runs:
                    raise ValueError("production_run_duplicate")
                runs[run_ref] = ProductionRun(
                    run_ref=run_ref,
                    facility_ref=str(payload["facility_ref"]),
                    recipe_ref=str(payload["recipe_ref"]),
                    started_tick=int(payload["started_tick"]),
                    finish_tick=int(payload["finish_tick"]),
                    reservation_refs=tuple(payload.get("reservation_refs", ())),
                    output_item=(str(payload["output_item"]) if payload.get("output_item") else None),
                )
            elif event.event_type == self._FINISHED:
                run = runs.get(run_ref)
                if run is None or run.status != "started":
                    raise ValueError("production_run_missing")
                runs[run_ref] = run.model_copy(
                    update={"status": "completed", "output_item": str(payload["output_item"])}, deep=True
                )
            else:
                run = runs.get(run_ref)
                if run is None:
                    raise ValueError("production_run_missing")
                runs[run_ref] = run.model_copy(
                    update={"maintenance_obligation_ref": str(payload["obligation_ref"])}, deep=True
                )
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
        return ConstructionProductionProjection(
            runs=MappingProxyType(dict(sorted(runs.items()))),
            source_revision_vector=MappingProxyType(dict(sorted(revisions.items()))),
            facilities=MappingProxyType(dict(sorted(facilities.items()))),
        )


class ConstructionProductionAuthority:
    owner = "construction-production"
    _PRINCIPAL = "actor_gameplay.construction_production_domain"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store
        self._projector = ConstructionProductionProjector()

    def projector(self) -> ConstructionProductionProjection:
        return self._projector.rebuild(self._store.read_events())

    def settle_facility_acquisition(
        self,
        *,
        plot: Plot,
        facility: Facility,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        if facility.plot_ref != plot.plot_ref or facility.condition <= 0:
            raise ValueError("facility_acquisition_invalid")
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            return existing
        if facility.facility_ref in self.projector().facilities:
            raise ValueError("facility_duplicate")
        stream_id = f"gameplay:construction_production:{facility.facility_ref}"
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=self._store.get_stream_head(stream_id),
            event_specs=[
                (
                    "gameplay.construction_production.facility_acquired",
                    facility.model_dump(mode="json"),
                )
            ],
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            pinned_revisions={"plot": plot.revision, "facility": facility.revision},
        )
        return self._store.append_batch(batch)

    def settle_start_run(
        self,
        *,
        facility: Facility,
        recipe: Recipe,
        run_ref: str,
        tick: int,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
        reservation_refs: tuple[str, ...] = (),
    ) -> AppendBatchResult:
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            return existing
        run = self.start_run(
            facility=facility,
            recipe=recipe,
            run_ref=run_ref,
            tick=tick,
            reservation_refs=reservation_refs,
        )
        stream_id = f"gameplay:construction_production:{facility.facility_ref}"
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=self._store.get_stream_head(stream_id),
            event_specs=[
                (
                    "gameplay.construction_production.run_started",
                    {
                        "run_ref": run.run_ref,
                        "facility_ref": run.facility_ref,
                        "recipe_ref": run.recipe_ref,
                        "started_tick": run.started_tick,
                        "finish_tick": run.finish_tick,
                        "reservation_refs": run.reservation_refs,
                        "output_item": run.output_item,
                    },
                )
            ],
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            pinned_revisions={"facility": facility.revision, "recipe": recipe.duration_ticks},
        )
        return self._store.append_batch(batch)

    def settle_finish_run(
        self,
        run: ProductionRun,
        *,
        tick: int,
        recipe: Recipe,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            return existing
        completed = self.finish_run(run, tick=tick, recipe=recipe)
        stream_id = f"gameplay:construction_production:{completed.facility_ref}"
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=self._store.get_stream_head(stream_id),
            event_specs=[
                (
                    "gameplay.construction_production.run_finished",
                    {
                        "run_ref": completed.run_ref,
                        "facility_ref": completed.facility_ref,
                        "recipe_ref": completed.recipe_ref,
                        "completed_tick": tick,
                        "output_item": completed.output_item,
                    },
                )
            ],
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            pinned_revisions={"recipe": recipe.duration_ticks},
        )
        return self._store.append_batch(batch)

    def settle_maintenance_obligation(
        self,
        run: ProductionRun,
        *,
        obligation_ref: str,
        command_id: str,
        idempotency_key: str,
        causation_id: str,
        correlation_id: str,
    ) -> AppendBatchResult:
        if not obligation_ref:
            raise ValueError("maintenance_obligation_required")
        existing = self._store.get_by_idempotency(self._PRINCIPAL, idempotency_key)
        if existing is not None:
            return existing
        stream_id = f"gameplay:construction_production:{run.facility_ref}"
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=self._store.get_stream_head(stream_id),
            event_specs=[
                (
                    "gameplay.construction_production.maintenance_obligation_created",
                    {"run_ref": run.run_ref, "obligation_ref": obligation_ref},
                )
            ],
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )
        return self._store.append_batch(batch)

    @staticmethod
    def start_run(*, facility: Facility, recipe: Recipe, run_ref: str, tick: int, reservation_refs: tuple[str, ...] = ()) -> ProductionRun:
        if facility.condition <= 0:
            raise ValueError("facility_unavailable")
        return ProductionRun(
            run_ref=run_ref,
            facility_ref=facility.facility_ref,
            recipe_ref=recipe.recipe_ref,
            started_tick=tick,
            finish_tick=tick + recipe.duration_ticks,
            reservation_refs=reservation_refs,
            output_item=recipe.output_item,
        )

    @staticmethod
    def finish_run(run: ProductionRun, *, tick: int, recipe: Recipe) -> ProductionRun:
        if run.status != "started":
            raise ValueError("production_run_final")
        if tick < run.finish_tick:
            raise ValueError("production_not_due")
        return run.model_copy(update={"status": "completed", "output_item": recipe.output_item}, deep=True)

    @staticmethod
    def maintenance(run: ProductionRun, *, obligation_ref: str) -> ProductionRun:
        return run.model_copy(update={"maintenance_obligation_ref": obligation_ref}, deep=True)

__all__ = ["Blueprint", "ConstructionJob", "ConstructionProductionAuthority", "ConstructionProductionProjection", "ConstructionProductionProjector", "Facility", "Plot", "ProductionRun", "Recipe"]
