"""Owner-local Ecology rollout layer 2 platform primitives."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Literal, Mapping, Sequence

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent, OwnerAuthorizedFragment, ProjectionCheckpoint, ReplayResult, StrictGameplayModel
from app.gameplay.settlement_plan import build_atomic_event_batch


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


class EcologyPlatformRuntimeError(ValueError):
    pass


class EcologyPlatformModel(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RegionRecord(EcologyPlatformModel):
    region_ref: str = Field(min_length=1)
    period_ref: str = Field(min_length=1)
    climate_profile_ref: str = Field(min_length=1)
    biome_tag_refs: tuple[str, ...] = ()
    jurisdiction_ref: str = Field(min_length=1)


class CellRecord(EcologyPlatformModel):
    cell_ref: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    period_ref: str = Field(min_length=1)
    terrain_ref: str = Field(min_length=1)
    moisture_basis_points: int = Field(ge=0)


class EnvironmentRecord(EcologyPlatformModel):
    environment_ref: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    period_ref: str = Field(min_length=1)
    weather_ref: str = Field(min_length=1)
    temperature_centi_c: int
    moisture_basis_points: int = Field(ge=0)


class ResourceRecord(EcologyPlatformModel):
    resource_ref: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    period_ref: str = Field(min_length=1)
    cell_ref: str = Field(min_length=1)
    material_ref: str = Field(min_length=1)
    quantity: int = Field(ge=0)


class CropRecord(EcologyPlatformModel):
    crop_ref: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    period_ref: str = Field(min_length=1)
    cell_ref: str = Field(min_length=1)
    species_ref: str = Field(min_length=1)
    growth_basis_points: int = Field(ge=0)
    health_basis_points: int = Field(ge=0)


class SpeciesRecord(EcologyPlatformModel):
    species_ref: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    period_ref: str = Field(min_length=1)
    trophic_role_ref: str = Field(min_length=1)
    population: int = Field(ge=0)


class RegionPeriodClose(EcologyPlatformModel):
    close_ref: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    period_ref: str = Field(min_length=1)
    ordered_record_refs: tuple[str, ...] = Field(min_length=1)
    record_counts: dict[str, int] = Field(default_factory=dict)
    revision_vector: dict[str, int] = Field(default_factory=dict)
    summary_digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_record_counts(self) -> "RegionPeriodClose":
        if any(revision < 0 or isinstance(revision, bool) for revision in self.revision_vector.values()):
            raise ValueError("ecology_platform_revision_vector_invalid")
        if any(count < 0 or isinstance(count, bool) for count in self.record_counts.values()):
            raise ValueError("ecology_platform_record_counts_invalid")
        return self


class EcologyPlatformWriteResult(EcologyPlatformModel):
    committed: bool
    zero_write: bool
    error_code: str | None = None
    append_result: AppendBatchResult | None = None
    close: RegionPeriodClose | None = None
    revision_vector: dict[str, int] = Field(default_factory=dict)


@dataclass(frozen=True)
class EcologyPlatformProjection:
    regions: Mapping[str, RegionRecord]
    cells: Mapping[str, CellRecord]
    environments: Mapping[str, EnvironmentRecord]
    resources: Mapping[str, ResourceRecord]
    crops: Mapping[str, CropRecord]
    species: Mapping[str, SpeciesRecord]
    closes: Mapping[str, RegionPeriodClose]
    source_revision_vector: Mapping[str, int]
    last_global_sequence: int = 0
    applied_event_ids: tuple[str, ...] = ()

    def to_state(self) -> dict[str, object]:
        return {
            "regions": {key: value.model_dump(mode="json") for key, value in self.regions.items()},
            "cells": {key: value.model_dump(mode="json") for key, value in self.cells.items()},
            "environments": {key: value.model_dump(mode="json") for key, value in self.environments.items()},
            "resources": {key: value.model_dump(mode="json") for key, value in self.resources.items()},
            "crops": {key: value.model_dump(mode="json") for key, value in self.crops.items()},
            "species": {key: value.model_dump(mode="json") for key, value in self.species.items()},
            "closes": {key: value.model_dump(mode="json") for key, value in self.closes.items()},
            "source_revision_vector": dict(self.source_revision_vector),
            "last_global_sequence": self.last_global_sequence,
            "applied_event_ids": list(self.applied_event_ids),
        }


class EcologyPlatformProjector:
    projector_id = "ecology-platform"
    projector_version = "1"
    projection_schema_version = 1

    def rebuild(
        self,
        events: Sequence[object],
        *,
        checkpoint: ProjectionCheckpoint | EcologyPlatformProjection | None = None,
    ) -> EcologyPlatformProjection:
        projection = self._checkpoint_projection(checkpoint)
        regions = dict(projection.regions)
        cells = dict(projection.cells)
        environments = dict(projection.environments)
        resources = dict(projection.resources)
        crops = dict(projection.crops)
        species = dict(projection.species)
        closes = dict(projection.closes)
        revisions = dict(projection.source_revision_vector)
        applied_event_ids = list(projection.applied_event_ids)
        last_global_sequence = projection.last_global_sequence

        for event in sorted((event for event in events if getattr(event, "event_id", None)), key=lambda item: (item.global_sequence, item.event_id)):
            if event.event_id in applied_event_ids:
                continue
            if not event.stream_id.startswith("gameplay:ecology:platform:"):
                continue
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
            last_global_sequence = max(last_global_sequence, event.global_sequence)
            payload = dict(event.payload)
            if event.event_type == "gameplay.ecology.region.recorded@1":
                region = RegionRecord.model_validate(payload["record"])
                regions[region.region_ref] = region
            elif event.event_type == "gameplay.ecology.cell.recorded@1":
                cell = CellRecord.model_validate(payload["record"])
                cells[cell.cell_ref] = cell
            elif event.event_type == "gameplay.ecology.environment.recorded@1":
                environment = EnvironmentRecord.model_validate(payload["record"])
                environments[environment.environment_ref] = environment
            elif event.event_type == "gameplay.ecology.resource.recorded@1":
                resource = ResourceRecord.model_validate(payload["record"])
                resources[resource.resource_ref] = resource
            elif event.event_type == "gameplay.ecology.crop.recorded@1":
                crop = CropRecord.model_validate(payload["record"])
                crops[crop.crop_ref] = crop
            elif event.event_type == "gameplay.ecology.species.recorded@1":
                value = SpeciesRecord.model_validate(payload["record"])
                species[value.species_ref] = value
            elif event.event_type == "gameplay.ecology.region_period_closed@1":
                close = RegionPeriodClose.model_validate(payload["close"])
                closes[close.close_ref] = close
            applied_event_ids.append(event.event_id)

        return EcologyPlatformProjection(
            regions=MappingProxyType(dict(sorted(regions.items()))),
            cells=MappingProxyType(dict(sorted(cells.items()))),
            environments=MappingProxyType(dict(sorted(environments.items()))),
            resources=MappingProxyType(dict(sorted(resources.items()))),
            crops=MappingProxyType(dict(sorted(crops.items()))),
            species=MappingProxyType(dict(sorted(species.items()))),
            closes=MappingProxyType(dict(sorted(closes.items()))),
            source_revision_vector=MappingProxyType(dict(sorted(revisions.items()))),
            last_global_sequence=last_global_sequence,
            applied_event_ids=tuple(applied_event_ids),
        )

    def create_checkpoint(self, events: Sequence[object]) -> ProjectionCheckpoint:
        projection = self.rebuild(events)
        state = projection.to_state()
        return ProjectionCheckpoint(
            checkpoint_id=f"checkpoint:{self.projector_id}:{projection.last_global_sequence}",
            projector_id=self.projector_id,
            projector_version=self.projector_version,
            projection_schema_version=self.projection_schema_version,
            source_revision_vector=dict(projection.source_revision_vector),
            last_global_sequence=projection.last_global_sequence,
            state=state,
            applied_event_ids=list(projection.applied_event_ids),
            projection_hash=_digest(
                {
                    "state": state,
                    "source_revision_vector": dict(projection.source_revision_vector),
                    "last_global_sequence": projection.last_global_sequence,
                    "applied_event_ids": list(projection.applied_event_ids),
                }
            ),
        )

    @staticmethod
    def _checkpoint_projection(checkpoint: ProjectionCheckpoint | EcologyPlatformProjection | None) -> EcologyPlatformProjection:
        if checkpoint is None:
            return EcologyPlatformProjection(
                regions=MappingProxyType({}),
                cells=MappingProxyType({}),
                environments=MappingProxyType({}),
                resources=MappingProxyType({}),
                crops=MappingProxyType({}),
                species=MappingProxyType({}),
                closes=MappingProxyType({}),
                source_revision_vector=MappingProxyType({}),
            )
        if isinstance(checkpoint, EcologyPlatformProjection):
            return checkpoint
        state = checkpoint.state
        return EcologyPlatformProjection(
            regions=MappingProxyType({
                key: RegionRecord.model_validate(value)
                for key, value in dict(state.get("regions", {})).items()
            }),
            cells=MappingProxyType({
                key: CellRecord.model_validate(value)
                for key, value in dict(state.get("cells", {})).items()
            }),
            environments=MappingProxyType({
                key: EnvironmentRecord.model_validate(value)
                for key, value in dict(state.get("environments", {})).items()
            }),
            resources=MappingProxyType({
                key: ResourceRecord.model_validate(value)
                for key, value in dict(state.get("resources", {})).items()
            }),
            crops=MappingProxyType({
                key: CropRecord.model_validate(value)
                for key, value in dict(state.get("crops", {})).items()
            }),
            species=MappingProxyType({
                key: SpeciesRecord.model_validate(value)
                for key, value in dict(state.get("species", {})).items()
            }),
            closes=MappingProxyType({
                key: RegionPeriodClose.model_validate(value)
                for key, value in dict(state.get("closes", {})).items()
            }),
            source_revision_vector=MappingProxyType({
                str(key): int(value)
                for key, value in dict(state.get("source_revision_vector", {})).items()
            }),
            last_global_sequence=checkpoint.last_global_sequence,
            applied_event_ids=tuple(checkpoint.applied_event_ids),
        )


class EcologyPlatformAuthority:
    _PRINCIPAL = "actor_gameplay.ecology_domain"

    def __init__(self, *, store: GameplayEventStore) -> None:
        self._store = store
        self._projector = EcologyPlatformProjector()

    def record_region(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        region: RegionRecord,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
        privacy_scope: str = "project",
    ) -> EcologyPlatformWriteResult:
        return self._record(
            kind="region",
            record_ref=region.region_ref,
            record=region,
            command_id=command_id,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            causation_id=causation_id,
            correlation_id=correlation_id,
            privacy_scope=privacy_scope,
        )

    def record_cell(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        cell: CellRecord,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
        privacy_scope: str = "project",
    ) -> EcologyPlatformWriteResult:
        return self._record(
            kind="cell",
            record_ref=cell.cell_ref,
            record=cell,
            command_id=command_id,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            causation_id=causation_id,
            correlation_id=correlation_id,
            privacy_scope=privacy_scope,
        )

    def record_environment(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        environment: EnvironmentRecord,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
        privacy_scope: str = "project",
    ) -> EcologyPlatformWriteResult:
        return self._record(
            kind="environment",
            record_ref=environment.environment_ref,
            record=environment,
            command_id=command_id,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            causation_id=causation_id,
            correlation_id=correlation_id,
            privacy_scope=privacy_scope,
        )

    def record_resource(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        resource: ResourceRecord,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
        privacy_scope: str = "project",
    ) -> EcologyPlatformWriteResult:
        return self._record(
            kind="resource",
            record_ref=resource.resource_ref,
            record=resource,
            command_id=command_id,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            causation_id=causation_id,
            correlation_id=correlation_id,
            privacy_scope=privacy_scope,
        )

    def record_crop(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        crop: CropRecord,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
        privacy_scope: str = "project",
    ) -> EcologyPlatformWriteResult:
        return self._record(
            kind="crop",
            record_ref=crop.crop_ref,
            record=crop,
            command_id=command_id,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            causation_id=causation_id,
            correlation_id=correlation_id,
            privacy_scope=privacy_scope,
        )

    def record_species(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        species: SpeciesRecord,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
        privacy_scope: str = "project",
    ) -> EcologyPlatformWriteResult:
        return self._record(
            kind="species",
            record_ref=species.species_ref,
            record=species,
            command_id=command_id,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            causation_id=causation_id,
            correlation_id=correlation_id,
            privacy_scope=privacy_scope,
        )

    def close_region_period(
        self,
        *,
        command_id: str,
        idempotency_key: str,
        close_ref: str,
        region_ref: str,
        period_ref: str,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
        required_revision_vector: Mapping[str, int] | None = None,
        privacy_scope: str = "project",
    ) -> EcologyPlatformWriteResult:
        if privacy_scope != "project":
            return self._rejected("ecology_platform_privacy_scope_denied")
        projection = self.projection()
        matching_records = self._close_records(projection, region_ref=region_ref, period_ref=period_ref)
        if not matching_records:
            return self._rejected("ecology_platform_close_sources_missing")
        revision_vector = dict(sorted(self._close_revision_vector(projection, matching_records).items()))
        normalized_required = dict(sorted((required_revision_vector or {}).items()))
        if required_revision_vector is not None and normalized_required != revision_vector:
            return self._rejected("ecology_platform_close_revision_vector_mismatch")
        close = self._build_close(
            close_ref=close_ref,
            region_ref=region_ref,
            period_ref=period_ref,
            matching_records=matching_records,
            revision_vector=revision_vector,
        )
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=self._close_stream(region_ref=region_ref, period_ref=period_ref),
            expected_revision=expected_revision,
            event_specs=(("gameplay.ecology.region_period_closed@1", {"close": close.model_dump(mode="json")}),),
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            read_stream_revisions=revision_vector,
            pinned_revisions=revision_vector,
        )
        batch = batch.model_copy(
            update={
                "owner_fragments": [
                    OwnerAuthorizedFragment(
                        fragment_id=f"fragment:ecology-platform:close:{command_id}",
                        owner_principal_ref=self._PRINCIPAL,
                        source_rule_ref="ecology-platform:explicit-owner-operation@1",
                        expected_revisions={self._close_stream(region_ref=region_ref, period_ref=period_ref): expected_revision},
                        read_set_revisions=revision_vector,
                        pinned_revisions=revision_vector,
                        event_specs={
                            self._close_stream(region_ref=region_ref, period_ref=period_ref): (
                                ("gameplay.ecology.region_period_closed@1", {"close": close.model_dump(mode="json")}),
                            )
                        },
                        event_visibility_policies={
                            self._close_stream(region_ref=region_ref, period_ref=period_ref): ("project",),
                        },
                    )
                ],
            },
            deep=True,
        )
        return self._from_append(self._store.append_batch(batch), close=close)

    def projection(self, *, checkpoint_at: int | None = None) -> EcologyPlatformProjection:
        events = self._relevant_events()
        if checkpoint_at is None:
            return self._projector.rebuild(events)
        prefix = [event for event in events if event.global_sequence <= checkpoint_at]
        tail = [event for event in events if event.global_sequence > checkpoint_at]
        checkpoint = self._projector.rebuild(prefix)
        return self._projector.rebuild(tail, checkpoint=checkpoint)

    def replay(self, *, checkpoint_at: int | None = None) -> ReplayResult:
        projection = self.projection(checkpoint_at=checkpoint_at)
        state = projection.to_state()
        projection_hash = _digest(
            {
                "state": state,
                "source_revision_vector": dict(projection.source_revision_vector),
                "last_global_sequence": projection.last_global_sequence,
                "applied_event_ids": list(projection.applied_event_ids),
            }
        )
        return ReplayResult(
            succeeded=True,
            projector_id=self._projector.projector_id,
            projector_version=self._projector.projector_version,
            projection_hash=projection_hash,
            state=state,
            source_revision_vector=dict(projection.source_revision_vector),
            last_global_sequence=projection.last_global_sequence,
            applied_event_ids=list(projection.applied_event_ids),
            applied_event_count=len(projection.applied_event_ids),
        )

    def _relevant_events(self) -> list[GameplayEvent]:
        return [
            event
            for event in self._store.read_events()
            if event.event_type in {
                "gameplay.ecology.region.recorded@1",
                "gameplay.ecology.cell.recorded@1",
                "gameplay.ecology.environment.recorded@1",
                "gameplay.ecology.resource.recorded@1",
                "gameplay.ecology.crop.recorded@1",
                "gameplay.ecology.species.recorded@1",
                "gameplay.ecology.region_period_closed@1",
            }
            and event.stream_id.startswith("gameplay:ecology:platform:")
        ]

    def _record(
        self,
        *,
        kind: str,
        record_ref: str,
        record: EcologyPlatformModel,
        command_id: str,
        idempotency_key: str,
        expected_revision: int,
        causation_id: str,
        correlation_id: str,
        privacy_scope: str,
    ) -> EcologyPlatformWriteResult:
        if privacy_scope != "project":
            return self._rejected("ecology_platform_privacy_scope_denied")
        stream_id = self._stream_id(kind=kind, record_ref=record_ref)
        batch = build_atomic_event_batch(
            command_id=command_id,
            principal_ref=self._PRINCIPAL,
            stream_id=stream_id,
            expected_revision=expected_revision,
            event_specs=((f"gameplay.ecology.{kind}.recorded@1", {"record": record.model_dump(mode="json")}),),
            idempotency_key=idempotency_key,
            causation_id=causation_id,
            correlation_id=correlation_id,
            read_stream_revisions={stream_id: expected_revision},
            pinned_revisions={stream_id: expected_revision},
        )
        batch = batch.model_copy(
            update={
                "owner_fragments": [
                    OwnerAuthorizedFragment(
                        fragment_id=f"fragment:ecology-platform:{kind}:{command_id}",
                        owner_principal_ref=self._PRINCIPAL,
                        source_rule_ref="ecology-platform:explicit-owner-operation@1",
                        expected_revisions={stream_id: expected_revision},
                        read_set_revisions={stream_id: expected_revision},
                        pinned_revisions={stream_id: expected_revision},
                        event_specs={stream_id: ((f"gameplay.ecology.{kind}.recorded@1", {"record": record.model_dump(mode="json")}),)},
                        event_visibility_policies={stream_id: ("project",)},
                    )
                ],
            },
            deep=True,
        )
        return self._from_append(self._store.append_batch(batch))

    def _from_append(self, append_result: AppendBatchResult, *, close: RegionPeriodClose | None = None) -> EcologyPlatformWriteResult:
        zero_write = not append_result.committed or append_result.idempotency_status != "new_commit"
        return EcologyPlatformWriteResult(
            committed=append_result.committed,
            zero_write=zero_write,
            error_code=append_result.failure.error_code if append_result.failure is not None else None,
            append_result=append_result,
            close=close,
            revision_vector=dict(append_result.resulting_stream_revisions),
        )

    @staticmethod
    def _rejected(error_code: str) -> EcologyPlatformWriteResult:
        return EcologyPlatformWriteResult(committed=False, zero_write=True, error_code=error_code)

    def _build_close(
        self,
        *,
        close_ref: str,
        region_ref: str,
        period_ref: str,
        matching_records: Mapping[str, EcologyPlatformModel],
        revision_vector: Mapping[str, int],
    ) -> RegionPeriodClose:
        groups = self._close_groups(matching_records)
        ordered_record_refs = tuple(
            ref
            for kind in ("region", "cell", "environment", "resource", "crop", "species")
            for ref in sorted(groups[kind])
        )
        record_counts = {kind: len(groups[kind]) for kind in ("region", "cell", "environment", "resource", "crop", "species")}
        payload = {
            "close_ref": close_ref,
            "region_ref": region_ref,
            "period_ref": period_ref,
            "ordered_record_refs": ordered_record_refs,
            "record_counts": record_counts,
            "revision_vector": dict(sorted(revision_vector.items())),
        }
        payload["summary_digest"] = _digest(payload)
        return RegionPeriodClose.model_validate(payload)

    def _close_records(self, projection: EcologyPlatformProjection, *, region_ref: str, period_ref: str) -> dict[str, EcologyPlatformModel]:
        records: dict[str, EcologyPlatformModel] = {}
        records.update(
            {
                f"region:{record.region_ref}": record
                for record in projection.regions.values()
                if record.region_ref == region_ref and record.period_ref == period_ref
            }
        )
        records.update(
            {
                f"cell:{record.cell_ref}": record
                for record in projection.cells.values()
                if record.region_ref == region_ref and record.period_ref == period_ref
            }
        )
        records.update(
            {
                f"environment:{record.environment_ref}": record
                for record in projection.environments.values()
                if record.region_ref == region_ref and record.period_ref == period_ref
            }
        )
        records.update(
            {
                f"resource:{record.resource_ref}": record
                for record in projection.resources.values()
                if record.region_ref == region_ref and record.period_ref == period_ref
            }
        )
        records.update(
            {
                f"crop:{record.crop_ref}": record
                for record in projection.crops.values()
                if record.region_ref == region_ref and record.period_ref == period_ref
            }
        )
        records.update(
            {
                f"species:{record.species_ref}": record
                for record in projection.species.values()
                if record.region_ref == region_ref and record.period_ref == period_ref
            }
        )
        return records

    @staticmethod
    def _close_groups(records: Mapping[str, EcologyPlatformModel]) -> dict[str, list[str]]:
        groups = {kind: [] for kind in ("region", "cell", "environment", "resource", "crop", "species")}
        for key in records:
            kind, record_ref = key.split(":", 1)
            groups[kind].append(record_ref)
        return groups

    @staticmethod
    def _close_revision_vector(projection: EcologyPlatformProjection, matching_records: Mapping[str, EcologyPlatformModel]) -> dict[str, int]:
        vector: dict[str, int] = {}
        for key in matching_records:
            if key.startswith("region:"):
                record = matching_records[key]
                vector[EcologyPlatformAuthority._stream_id("region", record.region_ref)] = projection.source_revision_vector.get(
                    EcologyPlatformAuthority._stream_id("region", record.region_ref),
                    0,
                )
            elif key.startswith("cell:"):
                record = matching_records[key]
                vector[EcologyPlatformAuthority._stream_id("cell", record.cell_ref)] = projection.source_revision_vector.get(
                    EcologyPlatformAuthority._stream_id("cell", record.cell_ref),
                    0,
                )
            elif key.startswith("environment:"):
                record = matching_records[key]
                vector[EcologyPlatformAuthority._stream_id("environment", record.environment_ref)] = projection.source_revision_vector.get(
                    EcologyPlatformAuthority._stream_id("environment", record.environment_ref),
                    0,
                )
            elif key.startswith("resource:"):
                record = matching_records[key]
                vector[EcologyPlatformAuthority._stream_id("resource", record.resource_ref)] = projection.source_revision_vector.get(
                    EcologyPlatformAuthority._stream_id("resource", record.resource_ref),
                    0,
                )
            elif key.startswith("crop:"):
                record = matching_records[key]
                vector[EcologyPlatformAuthority._stream_id("crop", record.crop_ref)] = projection.source_revision_vector.get(
                    EcologyPlatformAuthority._stream_id("crop", record.crop_ref),
                    0,
                )
            elif key.startswith("species:"):
                record = matching_records[key]
                vector[EcologyPlatformAuthority._stream_id("species", record.species_ref)] = projection.source_revision_vector.get(
                    EcologyPlatformAuthority._stream_id("species", record.species_ref),
                    0,
                )
        return dict(sorted(vector.items()))

    @staticmethod
    def _stream_id(kind: str, record_ref: str) -> str:
        if not kind or not record_ref:
            raise EcologyPlatformRuntimeError("ecology_platform_stream_invalid")
        return f"gameplay:ecology:platform:{kind}:{record_ref}"

    @staticmethod
    def _close_stream(*, region_ref: str, period_ref: str) -> str:
        if not region_ref or not period_ref:
            raise EcologyPlatformRuntimeError("ecology_platform_stream_invalid")
        return f"gameplay:ecology:platform:close:{region_ref}:{period_ref}"


__all__ = [
    "CellRecord",
    "CropRecord",
    "EcologyPlatformAuthority",
    "EcologyPlatformModel",
    "EcologyPlatformProjection",
    "EcologyPlatformProjector",
    "EcologyPlatformRuntimeError",
    "EcologyPlatformWriteResult",
    "EnvironmentRecord",
    "RegionPeriodClose",
    "RegionRecord",
    "ResourceRecord",
    "SpeciesRecord",
]
