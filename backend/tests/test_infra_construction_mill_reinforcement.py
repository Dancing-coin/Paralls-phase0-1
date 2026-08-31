from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    Facility,
    PackageDeclaredFacilityTransformIntentV1,
    Plot,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry, GameplayPatchRuntimeError


PACKAGE_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "inf-1"
    / "package-industrial-facilities-v2.manifest.json"
)
PACKAGE_REVISION = "package:industrial-facilities:v2"
CONTENT_DIGEST = "sha256:8deea88c5e49c2aa06f30bbf1bd78ed103e26d8fb31769fe5564dbb7cc279896"
FACILITY = "facility:mill-reinforcement:1"
PLOT = "plot:mill-reinforcement:1"
STREAM = f"gameplay:construction_production:{FACILITY}"


def _manifest() -> GameplayPatchManifest:
    return GameplayPatchManifest.model_validate(json.loads(PACKAGE_PATH.read_text(encoding="utf-8")))


def _setup(*, package_active: bool = True):
    store = GameplayEventStore()
    manifest = _manifest()
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    if package_active:
        registry.activate((manifest.patch_revision_id,))
    authority = ConstructionProductionAuthority(store=store, package_registry=registry)
    acquired = authority.settle_facility_acquisition(
        plot=Plot(plot_ref=PLOT, jurisdiction_ref="jurisdiction:mill-reinforcement:1", owner_ref="org:mill:1"),
        facility=Facility(facility_ref=FACILITY, plot_ref=PLOT, facility_kind="mill", condition=0.8),
        command_id="facility:mill-reinforcement:acquire",
        idempotency_key="facility:mill-reinforcement:acquire",
        causation_id="cause:mill-reinforcement:acquire",
        correlation_id="corr:mill-reinforcement:acquire",
    )
    assert acquired.committed
    return store, authority, registry, acquired.committed_event_ids[0]


def _intent(source_event_id: str, **updates: object) -> PackageDeclaredFacilityTransformIntentV1:
    values = {
        "facility_ref": FACILITY,
        "acquisition_event_id": source_event_id,
        "expected_revision": 1,
        "expected_facility_revision": 0,
        "command_id": "command:mill-reinforcement:1",
        "idempotency_key": "pending",
        "causation_id": source_event_id,
        "correlation_id": "corr:mill-reinforcement:1",
        "submitted_at": "2026-08-20T00:00:00Z",
    }
    values.update(updates)
    values["idempotency_key"] = (
        f"construction:facility-mill-reinforcement:{PACKAGE_REVISION}:{CONTENT_DIGEST}:"
        f"sha256:73d3313283bf584254281a2ca1b60d888585f6ba89e6370a30d622e4529b1bc8:"
        f"descriptor:construction-facility-mill-reinforcement@1:{FACILITY}:"
        f"{values['acquisition_event_id']}:1:{values['expected_facility_revision']}"
    )
    return PackageDeclaredFacilityTransformIntentV1.model_validate(values)


def _zero_write(store: GameplayEventStore):
    snapshot = store.export_snapshot()
    return {key: snapshot[key] for key in ("events", "outbox", "idempotency")}


def test_mill_manifest_digest_normalizes_and_binds_exact_descriptor() -> None:
    manifest = _manifest()
    assert manifest.content_digest == CONTENT_DIGEST
    assert manifest.content_digest == manifest.expected_content_digest()
    declaration = manifest.platform_extension.outcome_declarations[0]  # type: ignore[union-attr]
    assert declaration.declaration_digest == "sha256:73d3313283bf584254281a2ca1b60d888585f6ba89e6370a30d622e4529b1bc8"

    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    active = registry.activate((PACKAGE_REVISION,))

    assert len(active.capability_bindings) == 1
    binding = active.capability_bindings[0]
    assert binding.binding_ref == "binding:industrial-facilities-mill-to-mill-reinforced@1"
    assert binding.package_revision == PACKAGE_REVISION
    assert binding.content_digest == CONTENT_DIGEST
    assert binding.declaration_digest == declaration.declaration_digest
    assert binding.descriptor_ref == "descriptor:construction-facility-mill-reinforcement@1"


def test_mill_manifest_digest_claim_failures_are_nonmutating() -> None:
    raw = json.loads(PACKAGE_PATH.read_text(encoding="utf-8"))
    raw["platform_extension"]["outcome_declarations"][0]["declaration_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="platform_declaration_digest_mismatch"):
        GameplayPatchManifest.model_validate(raw)

    raw = json.loads(PACKAGE_PATH.read_text(encoding="utf-8"))
    raw["content_digest"] = "sha256:" + "0" * 64
    manifest = GameplayPatchManifest.model_validate(raw)
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    with pytest.raises(GameplayPatchRuntimeError, match="patch_digest_mismatch"):
        registry.install(manifest)
    assert registry._candidates == {}


def test_mill_reinforcement_commits_fixed_project_event_and_append_receipt() -> None:
    store, authority, _registry, source_id = _setup()

    result = authority.reinforce_mill_from_package(_intent(source_id))

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.construction_production.facility_transformed"
    assert event.visibility_policy == "project"
    assert event.payload["prior_kind"] == "mill"
    assert event.payload["next_kind"] == "mill_reinforced"
    assert event.payload["package_revision"] == PACKAGE_REVISION
    assert event.payload["content_digest"] == CONTENT_DIGEST
    assert authority.projector().facilities[FACILITY].facility_kind == "mill_reinforced"
    assert authority.projector().facilities[FACILITY].revision == 1
    assert store.get_stream_head(STREAM) == 2
    assert store.list_outbox()[-1].audience == "project"
    receipt = authority.facility_package_transform_receipt_for(result=result, scope="project")
    assert receipt.committed_event_ids == tuple(result.committed_event_ids)


@pytest.mark.parametrize(
    ("setup_kwargs", "updates", "error"),
    [
        ({"package_active": False}, {}, "construction_mill_reinforcement_package_inactive"),
        ({}, {"expected_revision": 0}, "revision_conflict"),
        ({}, {"expected_facility_revision": 1}, "construction_mill_reinforcement_facility_revision_conflict"),
        ({}, {"acquisition_event_id": "event:missing"}, "construction_mill_reinforcement_source_missing"),
    ],
)
def test_mill_reinforcement_rejections_are_zero_write(setup_kwargs, updates, error: str) -> None:
    store, authority, _registry, source_id = _setup(**setup_kwargs)
    before = _zero_write(store)

    result = authority.reinforce_mill_from_package(_intent(source_id, **updates))

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == error
    assert _zero_write(store) == before


def test_mill_reinforcement_unknown_active_package_is_zero_write() -> None:
    store, authority, registry, source_id = _setup()
    active = registry.active_patch_set
    assert active is not None
    registry._active = replace(active, patch_revision_ids=(), capability_bindings=())
    before = _zero_write(store)

    result = authority.reinforce_mill_from_package(_intent(source_id))

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "construction_mill_reinforcement_package_unknown"
    assert _zero_write(store) == before


def test_mill_reinforcement_rejects_private_stale_or_conflicting_evidence_without_write() -> None:
    store, authority, _registry, source_id = _setup()
    source = store.get_event(source_id)
    store._events_by_id[source_id] = source.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    before = _zero_write(store)
    private = authority.reinforce_mill_from_package(_intent(source_id))
    assert not private.committed and private.failure is not None
    assert private.failure.error_code == "construction_mill_reinforcement_source_invalid"
    assert _zero_write(store) == before

    store, authority, _registry, source_id = _setup()
    source = store.get_event(source_id)
    store._events_by_id[source_id] = source.model_copy(update={"stream_revision": 0}, deep=True)
    before = _zero_write(store)
    stale = authority.reinforce_mill_from_package(_intent(source_id))
    assert not stale.committed and stale.failure is not None
    assert stale.failure.error_code == "construction_mill_reinforcement_source_revision_conflict"
    assert _zero_write(store) == before

    store, authority, _registry, source_id = _setup()
    source = store.get_event(source_id)
    store._events_by_id[source_id] = source.model_copy(
        update={"payload": {**source.payload, "facility_kind": "oven"}}, deep=True
    )
    before = _zero_write(store)
    wrong_kind = authority.reinforce_mill_from_package(_intent(source_id))
    assert not wrong_kind.committed and wrong_kind.failure is not None
    assert wrong_kind.failure.error_code == "construction_mill_reinforcement_source_invalid"
    assert _zero_write(store) == before

    store, authority, _registry, source_id = _setup()
    source = store.get_event(source_id)
    store._events_by_id[source_id] = source.model_copy(
        update={"payload": {**source.payload, "plot_ref": "plot:other"}}, deep=True
    )
    before = _zero_write(store)
    conflicting = authority.reinforce_mill_from_package(_intent(source_id))
    assert not conflicting.committed and conflicting.failure is not None
    assert conflicting.failure.error_code == "construction_mill_reinforcement_binding_conflict"
    assert _zero_write(store) == before


@pytest.mark.parametrize("mutation, error", [
    ("unadmitted", "construction_mill_reinforcement_binding_unadmitted"),
    ("multiple", "construction_mill_reinforcement_binding_ambiguous"),
    ("digest", "construction_mill_reinforcement_digest_mismatch"),
    ("active_pin", "construction_mill_reinforcement_binding_conflict"),
])
def test_mill_reinforcement_binding_and_digest_conflicts_are_zero_write(mutation: str, error: str) -> None:
    store, authority, registry, source_id = _setup()
    active = registry.active_patch_set
    assert active is not None
    if mutation == "unadmitted":
        registry._active = replace(active, capability_bindings=())
    elif mutation == "multiple":
        registry._active = replace(active, capability_bindings=active.capability_bindings * 2)
    elif mutation == "active_pin":
        registry._active = replace(
            active,
            capability_bindings=(replace(active.capability_bindings[0], active_patch_set_revision="sha256:" + "0" * 64),),
        )
    else:
        manifest = registry.candidate(PACKAGE_REVISION)
        registry._candidates[manifest.patch_revision_id] = manifest.model_copy(
            update={"content_digest": "sha256:" + "0" * 64}, deep=True
        )
    before = _zero_write(store)

    result = authority.reinforce_mill_from_package(_intent(source_id))

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == error
    assert _zero_write(store) == before


def test_mill_reinforcement_duplicate_replay_and_checkpoint_tail_are_terminal() -> None:
    store, authority, _registry, source_id = _setup()
    first = authority.reinforce_mill_from_package(_intent(source_id))
    assert first.committed
    before = _zero_write(store)

    duplicate = authority.reinforce_mill_from_package(_intent(source_id))
    changed = authority.reinforce_mill_from_package(_intent(source_id, correlation_id="corr:changed"))
    full = authority.projector()
    tail = authority.projector(checkpoint_at=1)

    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert not changed.committed and changed.failure is not None
    assert changed.failure.error_code == "idempotency_key_reused"
    assert _zero_write(store) == before
    assert full.facilities == tail.facilities
    assert full.source_revision_vector == tail.source_revision_vector
    assert not hasattr(authority, "compensate_mill_reinforcement")
    assert not hasattr(authority, "reverse_mill_reinforcement")
