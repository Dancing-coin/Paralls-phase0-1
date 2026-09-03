from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

import pytest

from app.gameplay.closed_generic_gameplay_families import FacilityLifecycleTransitionContent
from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    Facility,
    Plot,
    Recipe,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.patch_runtime import (
    CapabilityBindingRequest,
    GameplayPatchManifest,
    GameplayPatchRegistry,
    OutcomeDeclarationAuthorInput,
    PackageDefinition,
    PackageIdentity,
    PlatformExtension,
    TypedReadRequirement,
)
from closed_generic_manifest_fixtures import load_manifest


PACKAGE_REVISION = "package:facility-lifecycle-demo@1"
ROOT = Path(__file__).resolve().parents[2]
FACILITY_MANIFEST_SOURCE_REFS = (
    "docs/superpowers/specs/world-character-siming-authority-mainline/inf-1/package-industrial-facilities-v1.manifest.json",
    "docs/superpowers/specs/world-character-siming-authority-mainline/inf-1/package-industrial-facilities-v2.manifest.json",
    "docs/superpowers/specs/world-character-siming-authority-mainline/inf-1/package-industrial-facilities-v3-decommission.manifest.json",
    "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/package-industrial-facilities-v4-commissioning-review.manifest.json",
    "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/package-industrial-facilities-v5-public-workshop-session.manifest.json",
    "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/package-industrial-facilities-v6-public-milling-session.manifest.json",
    "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/package-industrial-facilities-v7-reinforced-mill-flour-output-purchase.manifest.json",
)


def _committed_lifecycle_manifest_rows() -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    rows: list[tuple[str, str, tuple[str, ...]]] = []
    manifest_root = ROOT / "docs" / "superpowers" / "specs" / "world-character-siming-authority-mainline"
    for path in sorted(manifest_root.rglob("*.manifest.json")):
        if "closed-generic/facility-lifecycle-transition" not in path.relative_to(ROOT).as_posix():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        extension = payload.get("platform_extension") or {}
        declarations = extension.get("outcome_declarations") or ()
        for declaration in declarations:
            declaration_ref = declaration.get("declaration_ref", "")
            declaration_text = json.dumps(declaration, sort_keys=True)
            definitions_text = json.dumps(extension.get("package_definitions") or (), sort_keys=True)
            if "decommission" not in f"{path.name} {declaration_text} {definitions_text}".lower():
                continue
            kinds = tuple(
                definition.get("typed_content", {}).get("facility_kind", "")
                for definition in extension.get("package_definitions") or ()
                if definition.get("typed_content", {}).get("facility_kind")
            )
            rows.append((path.relative_to(ROOT).as_posix(), declaration_ref, kinds))
    return tuple(rows)


def _normalized_source_refs(source_refs: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for source_ref in source_refs:
        path, _, suffix = source_ref.rpartition(":")
        normalized.append(path if suffix.isdigit() else source_ref)
    return tuple(normalized)


def _digest(value: object) -> str:
    return "sha256:" + sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _manifest() -> GameplayPatchManifest:
    return load_manifest("facility-lifecycle-transition-mill-v1")


def _bakery_manifest() -> GameplayPatchManifest:
    return load_manifest("facility-lifecycle-transition-bakery-v1")


def _setup() -> tuple[GameplayEventStore, ConstructionProductionAuthority, Facility]:
    store = GameplayEventStore()
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    manifest = _manifest()
    registry.install(manifest)
    registry.activate((manifest.patch_revision_id,))
    authority = ConstructionProductionAuthority(store=store, package_registry=registry)
    facility = Facility(
        facility_ref="facility:mill:transition:1",
        plot_ref="plot:mill:transition:1",
        facility_kind="mill_reinforced",
        condition=0.8,
        revision=0,
        lifecycle_status="active",
    )
    acquired = authority.settle_facility_acquisition(
        plot=Plot(plot_ref=facility.plot_ref, jurisdiction_ref="jurisdiction:local", owner_ref="organization:mill"),
        facility=facility,
        command_id="command:acquire",
        idempotency_key="idempotency:acquire",
        causation_id="causation:acquire",
        correlation_id="correlation:acquire",
    )
    assert acquired.committed
    return store, authority, facility


def _bakery_setup() -> tuple[GameplayEventStore, ConstructionProductionAuthority, Facility]:
    store = GameplayEventStore()
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    manifest = _bakery_manifest()
    registry.install(manifest)
    registry.activate((manifest.patch_revision_id,))
    authority = ConstructionProductionAuthority(store=store, package_registry=registry)
    facility = Facility(
        facility_ref="facility:bakery:transition:1",
        plot_ref="plot:bakery:transition:1",
        facility_kind="bakery_reinforced",
        condition=0.9,
        revision=0,
        lifecycle_status="active",
    )
    acquired = authority.settle_facility_acquisition(
        plot=Plot(
            plot_ref=facility.plot_ref,
            jurisdiction_ref="jurisdiction:local",
            owner_ref="organization:bakery",
        ),
        facility=facility,
        command_id="command:bakery-acquire",
        idempotency_key="idempotency:bakery-acquire",
        causation_id="causation:bakery-acquire",
        correlation_id="correlation:bakery-acquire",
    )
    assert acquired.committed
    return store, authority, facility


def _intent(facility: Facility, acquisition_event_id: str, *, expected_stream_revision: int = 1) -> object:
    from app.gameplay.closed_generic_gameplay_families import FacilityLifecycleTransitionIntent

    return FacilityLifecycleTransitionIntent(
        facility_ref=facility.facility_ref,
        acquisition_event_id=acquisition_event_id,
        expected_stream_revision=expected_stream_revision,
        expected_facility_revision=0,
        command_id="command:facility-lifecycle",
        causation_id="causation:facility-lifecycle",
        correlation_id="correlation:facility-lifecycle",
        submitted_at="2026-08-30T00:00:00Z",
    )


def _zero_write(store: GameplayEventStore) -> dict[str, object]:
    snapshot = store.export_snapshot()
    return {key: snapshot[key] for key in ("events", "outbox", "idempotency")}


def test_lifecycle_transition_family_commits_the_exact_admitted_mill_content_row() -> None:
    store, authority, facility = _setup()
    acquisition_id = store.read_stream(f"gameplay:construction_production:{facility.facility_ref}")[0].event_id

    result = authority.settle_facility_lifecycle_transition(
        intent=_intent(facility, acquisition_id)
    )

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.payload["family_ref"] == "facility_lifecycle_transition@1"
    assert event.payload["prior_kind"] == "mill_reinforced"
    assert event.payload["next_kind"] == "mill_reinforced"


def test_lifecycle_transition_family_consumes_admitted_bakery_content_through_same_adapter() -> None:
    store, authority, facility = _bakery_setup()
    acquisition_id = store.read_stream(
        f"gameplay:construction_production:{facility.facility_ref}"
    )[0].event_id

    result = authority.settle_facility_lifecycle_transition(
        intent=_intent(facility, acquisition_id)
    )

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.payload["family_ref"] == "facility_lifecycle_transition@1"
    assert event.payload["prior_kind"] == "bakery_reinforced"
    assert event.payload["next_kind"] == "bakery_reinforced"
    assert event.payload["content_digest"] == _bakery_manifest().content_digest


def test_lifecycle_transition_family_has_two_distinct_disk_backed_content_instances() -> None:
    mill = _manifest()
    bakery = _bakery_manifest()
    assert mill.content_digest != bakery.content_digest
    assert mill.platform_extension is not None
    assert bakery.platform_extension is not None
    assert mill.platform_extension.package_definitions[0].typed_content["facility_kind"] == "mill_reinforced"
    assert bakery.platform_extension.package_definitions[0].typed_content["facility_kind"] == "bakery_reinforced"


def test_lifecycle_transition_genericity_uses_two_committed_content_rows() -> None:
    rows = _committed_lifecycle_manifest_rows()
    assert rows == (
        (
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/facility-lifecycle-transition/package-facility-lifecycle-transition-bakery-v1.manifest.json",
            "declaration:facility-lifecycle-transition-bakery@1",
            ("bakery_reinforced",),
        ),
        (
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/facility-lifecycle-transition/package-facility-lifecycle-transition-mill-v1.manifest.json",
            "declaration:facility-lifecycle-transition-mill@1",
            ("mill_reinforced",),
        ),
    )


def test_lifecycle_transition_family_commits_fixed_terminal_event() -> None:
    store, authority, facility = _setup()
    acquisition_id = store.read_stream(f"gameplay:construction_production:{facility.facility_ref}")[0].event_id

    result = authority.settle_facility_lifecycle_transition(
        intent=_intent(facility, acquisition_id)
    )

    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.construction_production.facility_decommissioned"
    assert event.payload["family_ref"] == "facility_lifecycle_transition@1"
    assert event.payload["prior_lifecycle_status"] == "active"
    assert event.payload["next_lifecycle_status"] == "decommissioned"
    assert authority.projector().facilities[facility.facility_ref].lifecycle_status == "decommissioned"


def test_lifecycle_transition_rejects_active_run_without_writing() -> None:
    store, authority, facility = _setup()
    acquisition_id = store.read_stream(f"gameplay:construction_production:{facility.facility_ref}")[0].event_id
    started = authority.settle_start_run(
        facility=facility,
        recipe=Recipe(recipe_ref="recipe:mill:active-run", output_item="item:mill:active-run", duration_ticks=4),
        run_ref="run:facility-lifecycle:active-run",
        tick=0,
        command_id="command:lifecycle-transition:start-run",
        idempotency_key="idempotency:lifecycle-transition:start-run",
        causation_id="causation:lifecycle-transition:start-run",
        correlation_id="correlation:lifecycle-transition:start-run",
    )
    assert started.committed
    before = _zero_write(store)

    result = authority.settle_facility_lifecycle_transition(
        intent=_intent(facility, acquisition_id, expected_stream_revision=2)
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "construction_mill_decommission_active_run"
    assert _zero_write(store) == before
    assert authority.projector().runs["run:facility-lifecycle:active-run"].status == "started"


def test_lifecycle_transition_rejects_wrong_facility_kind_without_writing() -> None:
    store, authority, facility = _setup()
    acquisition_id = store.read_stream(f"gameplay:construction_production:{facility.facility_ref}")[0].event_id
    source = store.get_event(acquisition_id)
    store._events_by_id[acquisition_id] = source.model_copy(
        update={"payload": {**source.payload, "facility_kind": "oven"}}, deep=True
    )
    before = tuple(store.read_events())

    result = authority.settle_facility_lifecycle_transition(
        intent=_intent(facility, acquisition_id)
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "facility_lifecycle_transition_source_conflict"
    assert tuple(store.read_events()) == before


def test_lifecycle_transition_rejects_caller_selected_target_or_compensation() -> None:
    from app.gameplay.closed_generic_gameplay_families import FacilityLifecycleTransitionIntent

    with pytest.raises(Exception):
        FacilityLifecycleTransitionIntent.model_validate(
            {
                "facility_ref": "facility:mill:transition:1",
                "acquisition_event_id": "event:source",
                "expected_stream_revision": 1,
                "expected_facility_revision": 0,
                "command_id": "command:lifecycle",
                "causation_id": "cause:lifecycle",
                "correlation_id": "corr:lifecycle",
                "submitted_at": "2026-08-30T00:00:00Z",
                "to_lifecycle": "active",
                "compensation_mode": "refund",
            }
        )


def test_lifecycle_transition_replays_duplicate_and_rejects_changed_duplicate() -> None:
    store, authority, facility = _setup()
    acquisition_id = store.read_stream(f"gameplay:construction_production:{facility.facility_ref}")[0].event_id
    intent = _intent(facility, acquisition_id)
    first = authority.settle_facility_lifecycle_transition(intent=intent)
    before = tuple(store.read_events())

    duplicate = authority.settle_facility_lifecycle_transition(intent=intent)
    changed = authority.settle_facility_lifecycle_transition(
        intent=intent.model_copy(update={"correlation_id": "correlation:changed"})
    )

    assert duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert not changed.committed
    assert changed.failure is not None
    assert changed.failure.error_code == "idempotency_key_reused"
    assert tuple(store.read_events()) == before


def test_lifecycle_transition_full_and_checkpoint_tail_replay_match() -> None:
    store, authority, facility = _setup()
    acquisition_id = store.read_stream(f"gameplay:construction_production:{facility.facility_ref}")[0].event_id
    assert authority.settle_facility_lifecycle_transition(
        intent=_intent(facility, acquisition_id)
    ).committed

    full = authority.projector()
    tail = authority.projector(checkpoint_at=1)

    assert full.facilities == tail.facilities
    assert full.source_revision_vector == tail.source_revision_vector


def test_lifecycle_transition_rejects_tampered_activation_binding_without_writing() -> None:
    store, authority, facility = _setup()
    acquisition_id = store.read_stream(
        f"gameplay:construction_production:{facility.facility_ref}"
    )[0].event_id
    registry = authority._package_registry
    active = registry.active_patch_set
    assert active is not None
    assert len(active.capability_bindings) == 1
    registry._active = replace(
        active,
        capability_bindings=(
            replace(active.capability_bindings[0], declaration_ref="declaration:forged@1"),
        ),
    )
    before = tuple(store.read_events())

    result = authority.settle_facility_lifecycle_transition(
        intent=_intent(facility, acquisition_id)
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "facility_lifecycle_transition_binding_invalid"
    assert tuple(store.read_events()) == before
