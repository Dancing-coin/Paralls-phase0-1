from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    Facility,
    Plot,
    PackageDeclaredFacilityTransformIntentV1,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry


PACKAGE_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "inf-1"
    / "package-industrial-facilities-v1.manifest.json"
)
FACILITY = "facility:industrial-transform:1"
PLOT = "plot:industrial-transform:1"
STREAM = f"gameplay:construction_production:{FACILITY}"


def _setup(*, package_active: bool = True):
    store = GameplayEventStore()
    manifest = GameplayPatchManifest.model_validate(json.loads(PACKAGE_PATH.read_text(encoding="utf-8")))
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    if package_active:
        registry.activate((manifest.patch_revision_id,))
    authority = ConstructionProductionAuthority(store=store, package_registry=registry)
    acquired = authority.settle_facility_acquisition(
        plot=Plot(plot_ref=PLOT, jurisdiction_ref="jurisdiction:industrial-transform:1", owner_ref="org:industrial:1"),
        facility=Facility(facility_ref=FACILITY, plot_ref=PLOT, facility_kind="oven", condition=0.8),
        command_id="facility:industrial-transform:acquire",
        idempotency_key="facility:industrial-transform:acquire",
        causation_id="cause:industrial-transform:acquire",
        correlation_id="corr:industrial-transform:acquire",
    )
    assert acquired.committed
    return store, authority, registry, acquired.committed_event_ids[0]


def _intent(source_event_id: str, **updates: object) -> PackageDeclaredFacilityTransformIntentV1:
    values = {
        "facility_ref": FACILITY,
        "acquisition_event_id": source_event_id,
        "expected_revision": 1,
        "expected_facility_revision": 0,
        "command_id": "command:industrial-transform:1",
        "idempotency_key": "pending",
        "causation_id": source_event_id,
        "correlation_id": "corr:industrial-transform:1",
        "submitted_at": "2026-08-19T00:00:00Z",
    }
    values.update(updates)
    values["idempotency_key"] = (
        f"construction:facility-transform:package:industrial-facilities:v1:"
        f"sha256:41e1b40bcd1fd13e1692f2f51aed7dea6dceee0b1605bf215fe6c673fcd11f88:"
        f"{FACILITY}:{values['acquisition_event_id']}"
    )
    return PackageDeclaredFacilityTransformIntentV1.model_validate(values)


def _zero_write(store: GameplayEventStore):
    snapshot = store.export_snapshot()
    return {key: snapshot[key] for key in ("events", "outbox", "idempotency")}


def test_package_transform_commits_one_project_event_and_append_receipt() -> None:
    store, authority, _registry, source_id = _setup()

    result = authority.transform_facility_from_package(_intent(source_id))

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.construction_production.facility_transformed"
    assert event.visibility_policy == "project"
    assert event.payload["prior_kind"] == "oven"
    assert event.payload["next_kind"] == "kiln"
    assert event.payload["package_revision"] == "package:industrial-facilities:v1"
    assert event.payload["content_digest"].startswith("sha256:")
    assert authority.projector().facilities[FACILITY].facility_kind == "kiln"
    assert authority.projector().facilities[FACILITY].revision == 1
    assert store.get_stream_head(STREAM) == 2
    assert store.list_outbox()[-1].audience == "project"
    receipt = authority.facility_package_transform_receipt_for(result=result, scope="project")
    assert receipt.committed_event_ids == tuple(result.committed_event_ids)
    with pytest.raises(ValueError, match="construction_facility_transform_receipt_scope_denied"):
        authority.facility_package_transform_receipt_for(result=result, scope="authority")


@pytest.mark.parametrize(
    ("setup_kwargs", "updates", "error"),
    [
        ({"package_active": False}, {}, "construction_facility_transform_package_inactive"),
        ({}, {"expected_revision": 0}, "revision_conflict"),
        ({}, {"expected_facility_revision": 1}, "construction_facility_transform_facility_revision_conflict"),
        ({}, {"acquisition_event_id": "event:missing"}, "construction_facility_transform_source_missing"),
    ],
)
def test_package_transform_rejections_are_zero_write(setup_kwargs, updates, error: str) -> None:
    store, authority, _registry, source_id = _setup(**setup_kwargs)
    before = _zero_write(store)

    result = authority.transform_facility_from_package(_intent(source_id, **updates))

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == error
    assert _zero_write(store) == before


def test_package_transform_rejects_non_oven_and_stale_acquisition_evidence_without_write() -> None:
    store, authority, _registry, source_id = _setup()
    source = store.get_event(source_id)
    store._events_by_id[source_id] = source.model_copy(
        update={"payload": {**source.payload, "facility_kind": "bakery"}},
        deep=True,
    )
    before = _zero_write(store)
    non_oven = authority.transform_facility_from_package(_intent(source_id))
    assert not non_oven.committed
    assert non_oven.failure is not None
    assert non_oven.failure.error_code == "construction_facility_transform_source_invalid"
    assert _zero_write(store) == before

    store, authority, _registry, source_id = _setup()
    source = store.get_event(source_id)
    store._events_by_id[source_id] = source.model_copy(update={"stream_revision": 0}, deep=True)
    before = _zero_write(store)
    stale = authority.transform_facility_from_package(_intent(source_id))
    assert not stale.committed
    assert stale.failure is not None
    assert stale.failure.error_code == "construction_facility_transform_source_revision_conflict"
    assert _zero_write(store) == before


def test_package_transform_exact_duplicate_replays_and_changed_duplicate_is_zero_write() -> None:
    store, authority, _registry, source_id = _setup()
    first = authority.transform_facility_from_package(_intent(source_id))
    before = _zero_write(store)

    duplicate = authority.transform_facility_from_package(_intent(source_id))
    changed = authority.transform_facility_from_package(_intent(source_id, correlation_id="corr:changed"))

    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert not changed.committed
    assert changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert _zero_write(store) == before


def test_package_transform_full_and_checkpoint_tail_replay_match_and_is_terminal() -> None:
    _store, authority, _registry, source_id = _setup()
    assert authority.transform_facility_from_package(_intent(source_id)).committed

    full = authority.projector()
    tail = authority.projector(checkpoint_at=1)
    assert full.facilities == tail.facilities
    assert full.source_revision_vector == tail.source_revision_vector
    assert not hasattr(authority, "compensate_facility_package_transform")
    assert not hasattr(authority, "reverse_facility_package_transform")


@pytest.mark.parametrize("mutation, error", [
    ("unadmitted", "construction_facility_transform_binding_unadmitted"),
    ("multiple", "construction_facility_transform_binding_ambiguous"),
    ("digest", "construction_facility_transform_digest_mismatch"),
])
def test_package_transform_binding_and_digest_conflicts_are_zero_write(mutation: str, error: str) -> None:
    store, authority, registry, source_id = _setup()
    active = registry.active_patch_set
    assert active is not None
    if mutation == "unadmitted":
        registry._active = replace(active, capability_bindings=())
    elif mutation == "multiple":
        registry._active = replace(active, capability_bindings=active.capability_bindings * 2)
    else:
        manifest = registry.candidate("package:industrial-facilities:v1")
        registry._candidates[manifest.patch_revision_id] = manifest.model_copy(
            update={"content_digest": "sha256:" + "0" * 64}, deep=True
        )
    before = _zero_write(store)

    result = authority.transform_facility_from_package(_intent(source_id))

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == error
    assert _zero_write(store) == before


def test_package_transform_rejects_private_or_project_binding_conflicting_evidence_without_write() -> None:
    store, authority, _registry, source_id = _setup()
    source = store.get_event(source_id)
    private = source.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    store._events_by_id[source_id] = private
    before = _zero_write(store)

    private_result = authority.transform_facility_from_package(_intent(source_id))

    assert not private_result.committed
    assert private_result.failure is not None
    assert private_result.failure.error_code == "construction_facility_transform_source_invalid"
    assert _zero_write(store) == before

    store, authority, _registry, source_id = _setup()
    source = store.get_event(source_id)
    conflicting = source.model_copy(update={"payload": {**source.payload, "plot_ref": "plot:other"}}, deep=True)
    store._events_by_id[source_id] = conflicting
    before = _zero_write(store)
    conflict_result = authority.transform_facility_from_package(_intent(source_id))

    assert not conflict_result.committed
    assert conflict_result.failure is not None
    assert conflict_result.failure.error_code == "construction_facility_transform_binding_conflict"
    assert _zero_write(store) == before
