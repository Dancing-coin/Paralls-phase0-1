from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    Facility,
    MillFacilityDecommissionIntentV1,
    PackageDeclaredFacilityTransformIntentV1,
    Plot,
    Recipe,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry


ROOT = Path(__file__).resolve().parents[2]
V2_PATH = ROOT / "docs" / "superpowers" / "specs" / "world-character-siming-authority-mainline" / "inf-1" / "package-industrial-facilities-v2.manifest.json"
V3_PATH = ROOT / "docs" / "superpowers" / "specs" / "world-character-siming-authority-mainline" / "inf-1" / "package-industrial-facilities-v3-decommission.manifest.json"
V3_REVISION = "package:industrial-facilities:v3"
V3_DIGEST = "sha256:bde53b49ee207d90c2d2bfd7e7ff95ef03638a41719883a21c2b83a3e15930ca"
V3_DECLARATION_DIGEST = "sha256:ad800530f5e9a85baad29c5825a0e7edfc7e6cfa664a20208f5d2566819a7c3c"
FACILITY = "facility:mill-decommission:1"
PLOT = "plot:mill-decommission:1"
STREAM = f"gameplay:construction_production:{FACILITY}"


def _manifest(path: Path) -> GameplayPatchManifest:
    return GameplayPatchManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _setup() -> tuple[GameplayEventStore, ConstructionProductionAuthority, GameplayPatchRegistry, str, str]:
    store = GameplayEventStore()
    v2, v3 = _manifest(V2_PATH), _manifest(V3_PATH)
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install_many((v2, v3))
    registry.activate((v2.patch_revision_id,))
    authority = ConstructionProductionAuthority(store=store, package_registry=registry)
    acquired = authority.settle_facility_acquisition(
        plot=Plot(plot_ref=PLOT, jurisdiction_ref="jurisdiction:mill-decommission:1", owner_ref="org:mill:1"),
        facility=Facility(facility_ref=FACILITY, plot_ref=PLOT, facility_kind="mill", condition=0.8),
        command_id="facility:mill-decommission:acquire",
        idempotency_key="facility:mill-decommission:acquire",
        causation_id="cause:mill-decommission:acquire",
        correlation_id="corr:mill-decommission:acquire",
    )
    assert acquired.committed
    acquisition_id = acquired.committed_event_ids[0]
    reinforced = authority.reinforce_mill_from_package(
        PackageDeclaredFacilityTransformIntentV1(
            facility_ref=FACILITY,
            acquisition_event_id=acquisition_id,
            expected_revision=1,
            expected_facility_revision=0,
            command_id="facility:mill-decommission:reinforce",
            idempotency_key=(
                "construction:facility-mill-reinforcement:package:industrial-facilities:v2:"
                "sha256:8deea88c5e49c2aa06f30bbf1bd78ed103e26d8fb31769fe5564dbb7cc279896:"
                "sha256:73d3313283bf584254281a2ca1b60d888585f6ba89e6370a30d622e4529b1bc8:"
                f"descriptor:construction-facility-mill-reinforcement@1:{FACILITY}:{acquisition_id}:1:0"
            ),
            causation_id=acquisition_id,
            correlation_id="corr:mill-decommission:reinforce",
            submitted_at="2026-08-21T00:00:00Z",
        )
    )
    assert reinforced.committed, reinforced.failure
    registry.activate((v3.patch_revision_id,))
    return store, authority, registry, acquisition_id, reinforced.committed_event_ids[0]


def _intent(acquisition_id: str, reinforcement_id: str, **updates: object) -> MillFacilityDecommissionIntentV1:
    values: dict[str, object] = {
        "facility_ref": FACILITY,
        "acquisition_event_id": acquisition_id,
        "reinforcement_event_id": reinforcement_id,
        "expected_revision": 2,
        "expected_facility_revision": 1,
        "command_id": "command:mill-decommission:1",
        "idempotency_key": "pending",
        "causation_id": reinforcement_id,
        "correlation_id": "corr:mill-decommission:1",
        "submitted_at": "2026-08-21T00:00:00Z",
    }
    values.update(updates)
    values["idempotency_key"] = (
        f"construction:facility-mill-decommission:{V3_REVISION}:{V3_DIGEST}:{V3_DECLARATION_DIGEST}:"
        f"descriptor:construction-facility-mill-decommission@1:{values['facility_ref']}:"
        f"{values['acquisition_event_id']}:1:{values['reinforcement_event_id']}:2:"
        f"{values['expected_facility_revision']}"
    )
    return MillFacilityDecommissionIntentV1.model_validate(values)


def _zero_write(store: GameplayEventStore) -> dict[str, object]:
    snapshot = store.export_snapshot()
    return {key: snapshot[key] for key in ("events", "outbox", "idempotency")}


def test_mill_decommission_commits_only_fixed_project_lifecycle_event_and_receipt() -> None:
    store, authority, _registry, acquisition_id, reinforcement_id = _setup()

    result = authority.decommission_reinforced_mill(_intent(acquisition_id, reinforcement_id))

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.construction_production.facility_decommissioned"
    assert event.visibility_policy == "project"
    assert event.payload["prior_kind"] == event.payload["next_kind"] == "mill_reinforced"
    assert event.payload["prior_lifecycle_status"] == "active"
    assert event.payload["next_lifecycle_status"] == "decommissioned"
    assert event.payload["package_revision"] == V3_REVISION
    assert event.payload["content_digest"] == V3_DIGEST
    assert event.payload["declaration_digest"] == V3_DECLARATION_DIGEST
    facility = authority.projector().facilities[FACILITY]
    assert facility.facility_kind == "mill_reinforced"
    assert facility.lifecycle_status == "decommissioned"
    assert facility.revision == 2
    assert store.get_stream_head(STREAM) == 3
    assert authority.facility_decommission_receipt_for(
        result=result, scope="project"
    ).committed_event_ids == tuple(result.committed_event_ids)


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("private_acquisition", "construction_mill_decommission_source_private"),
        ("private_reinforcement", "construction_mill_decommission_source_private"),
        ("wrong_reinforcement", "construction_mill_decommission_source_invalid"),
        ("stale_stream", "revision_conflict"),
        ("stale_facility", "construction_mill_decommission_facility_revision_conflict"),
    ],
)
def test_mill_decommission_source_privacy_and_revision_conflicts_are_zero_write(mutation: str, error: str) -> None:
    store, authority, _registry, acquisition_id, reinforcement_id = _setup()
    if mutation == "private_acquisition":
        event = store.get_event(acquisition_id)
        store._events_by_id[acquisition_id] = event.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    elif mutation == "private_reinforcement":
        event = store.get_event(reinforcement_id)
        store._events_by_id[reinforcement_id] = event.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    elif mutation == "wrong_reinforcement":
        event = store.get_event(reinforcement_id)
        store._events_by_id[reinforcement_id] = event.model_copy(
            update={"payload": {**event.payload, "next_kind": "kiln"}}, deep=True
        )
    updates = {"expected_revision": 1} if mutation == "stale_stream" else {}
    updates = {"expected_facility_revision": 0} if mutation == "stale_facility" else updates
    before = _zero_write(store)

    result = authority.decommission_reinforced_mill(_intent(acquisition_id, reinforcement_id, **updates))

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == error
    assert _zero_write(store) == before


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("inactive", "construction_mill_decommission_package_inactive"),
        ("unadmitted", "construction_mill_decommission_binding_unadmitted"),
        ("ambiguous", "construction_mill_decommission_binding_ambiguous"),
        ("digest", "construction_mill_decommission_digest_mismatch"),
    ],
)
def test_mill_decommission_binding_admission_rejections_are_zero_write(mutation: str, error: str) -> None:
    store, authority, registry, acquisition_id, reinforcement_id = _setup()
    active = registry.active_patch_set
    assert active is not None
    if mutation == "inactive":
        registry._active = None
    elif mutation == "unadmitted":
        registry._active = replace(active, capability_bindings=())
    elif mutation == "ambiguous":
        registry._active = replace(active, capability_bindings=active.capability_bindings * 2)
    else:
        manifest = registry.candidate(V3_REVISION)
        registry._candidates[manifest.patch_revision_id] = manifest.model_copy(
            update={"content_digest": "sha256:" + "0" * 64}, deep=True
        )
    before = _zero_write(store)

    result = authority.decommission_reinforced_mill(_intent(acquisition_id, reinforcement_id))

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == error
    assert _zero_write(store) == before


def test_mill_decommission_rejects_committed_started_run_without_releasing_or_compensating() -> None:
    store, authority, _registry, acquisition_id, reinforcement_id = _setup()
    facility = authority.projector().facilities[FACILITY]
    started = authority.settle_start_run(
        facility=facility,
        recipe=Recipe(recipe_ref="recipe:mill:1", output_item="item:flour", duration_ticks=4),
        run_ref="run:mill-decommission:1",
        tick=0,
        command_id="run:mill-decommission:start",
        idempotency_key="run:mill-decommission:start",
        causation_id="cause:mill-decommission:run",
        correlation_id="corr:mill-decommission:run",
    )
    assert started.committed
    before = _zero_write(store)

    result = authority.decommission_reinforced_mill(
        _intent(acquisition_id, reinforcement_id, expected_revision=3)
    )

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "construction_mill_decommission_active_run"
    assert _zero_write(store) == before
    assert authority.projector().runs["run:mill-decommission:1"].status == "started"


def test_mill_decommission_duplicate_replay_and_checkpoint_tail_are_terminal() -> None:
    store, authority, _registry, acquisition_id, reinforcement_id = _setup()
    first = authority.decommission_reinforced_mill(_intent(acquisition_id, reinforcement_id))
    assert first.committed
    before = _zero_write(store)

    duplicate = authority.decommission_reinforced_mill(_intent(acquisition_id, reinforcement_id))
    changed = authority.decommission_reinforced_mill(
        _intent(acquisition_id, reinforcement_id, correlation_id="corr:mill-decommission:changed")
    )
    full = authority.projector()
    tail = authority.projector(checkpoint_at=2)

    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert not changed.committed and changed.failure is not None
    assert changed.failure.error_code == "idempotency_key_reused"
    assert _zero_write(store) == before
    assert full.facilities == tail.facilities
    assert full.source_revision_vector == tail.source_revision_vector
    assert not hasattr(authority, "reactivate_mill")
    assert not hasattr(authority, "compensate_mill_decommission")
