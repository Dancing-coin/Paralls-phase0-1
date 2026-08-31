from __future__ import annotations

from app.gameplay.ecology_runtime import (
    CropRecord,
    EcologyHazardAuthority,
    EnvironmentalState,
    EnvironmentRegion,
    HazardRecord,
    ResourceNode,
)
from app.gameplay.event_schema_registry import (
    EventSchemaRegistry,
    register_inf3_grain_harvest_event_schemas,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog
from app.gameplay.shared_contracts import GameplayCommandEnvelope


REGION_REF = "region:inf3:grain"
STREAM = f"gameplay:ecology:{REGION_REF}"
PROJECT_REF = "project:inf3-grain"


def _seed() -> GameplayEventStore:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    result = authority.record_region_bundle(
        envelope=GameplayCommandEnvelope(
            command_id="command:inf3:grain:seed",
            command_type="gameplay.ecology.region_bundle.record",
            command_version=1,
            principal_ref="authority:ecology",
            project_ref=PROJECT_REF,
            idempotency_key="inf3:grain:seed",
            expected_revisions={STREAM: 0},
            causation_id="cause:inf3:grain:seed",
            correlation_id="corr:inf3:grain",
            source_ref="authority:ecology",
            submitted_at="2026-08-28T00:00:00Z",
            payload={"visibility_scope": "project"},
        ),
        region=EnvironmentRegion(
            region_ref=REGION_REF,
            climate_profile_ref="climate:temperate",
            biome_tags=("biome:field",),
            jurisdiction_ref="jurisdiction:inf3:grain",
            revision=0,
        ),
        environment=EnvironmentalState(
            region_ref=REGION_REF,
            temperature_centi_c=1800,
            moisture_basis_points=5000,
            weather_ref="weather:clear",
            revision=0,
        ),
        resource=ResourceNode(
            node_ref="resource:inf3:grain:water",
            region_ref=REGION_REF,
            substance_ref="substance:water",
            quantity=90,
            regeneration_per_tick=2,
            revision=0,
        ),
        crop=CropRecord(
            crop_ref="crop:inf3:grain:cover",
            region_ref=REGION_REF,
            plot_ref="plot:inf3:grain:cover",
            health=100,
            growth_basis_points=5000,
            revision=0,
            owner_ref="authority:crop",
        ),
        hazard=HazardRecord(
            hazard_ref="hazard:inf3:grain:cover",
            region_ref=REGION_REF,
            effect_ref="effect:frost",
            severity_basis_points=100,
            due_tick=10,
            duration_ticks=1,
            semantic_revision="semantic:1",
            rule_revision="rule:1",
            policy_revision="policy:1",
            idempotency_key="inf3:grain:cover",
        ),
    )
    assert result.committed
    return store


def _admit_envelope(store: GameplayEventStore, *, key: str = "inf3:grain:admit"):
    return GameplayCommandEnvelope(
        command_id=f"command:{key}",
        command_type="gameplay.ecology.grain_crop.admit",
        command_version=1,
        principal_ref="authority:ecology",
        project_ref=PROJECT_REF,
        idempotency_key=f"ecology:grain-crop-admission:{PROJECT_REF}:crop:inf3:grain:wheat:v1",
        expected_revisions={STREAM: store.get_stream_head(STREAM)},
        causation_id=f"cause:{key}",
        correlation_id="corr:inf3:grain",
        source_ref="authority:ecology",
        submitted_at="2026-08-28T00:01:00Z",
        payload={
            "visibility_scope": "project",
            "crop_ref": "crop:inf3:grain:wheat",
            "region_ref": REGION_REF,
            "plot_ref": "plot:inf3:grain:1",
        },
    )


def _harvest_envelope(store: GameplayEventStore, *, key: str = "inf3:grain:harvest"):
    admission = next(
        (
            event
            for event in reversed(store.read_events())
            if event.event_type == "gameplay.ecology.grain_crop.admitted"
        ),
        None,
    )
    admission_id = admission.event_id if admission is not None else "event:missing"
    admission_revision = admission.stream_revision if admission is not None else 0
    return GameplayCommandEnvelope(
        command_id=f"command:{key}",
        command_type="gameplay.ecology.grain_crop.harvest",
        command_version=1,
        principal_ref="authority:ecology",
        project_ref=PROJECT_REF,
        idempotency_key=f"ecology:grain-harvest:{admission_id}:{admission_revision}:v1",
        expected_revisions={STREAM: store.get_stream_head(STREAM)},
        causation_id=admission_id,
        correlation_id="corr:inf3:grain",
        source_ref="authority:ecology",
        submitted_at="2026-08-28T00:02:00Z",
        payload={"visibility_scope": "project", "target_region_ref": REGION_REF},
    )


def test_inf3_grain_admission_commits_fixed_project_visible_crop_fact() -> None:
    store = _seed()
    authority = EcologyHazardAuthority(store=store)

    result = authority.admit_grain_crop(
        envelope=_admit_envelope(store),
        crop_ref="crop:inf3:grain:wheat",
        region_ref=REGION_REF,
        plot_ref="plot:inf3:grain:1",
    )

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.ecology.grain_crop.admitted"
    assert event.visibility_policy == "project"
    assert event.payload["project_ref"] == PROJECT_REF
    assert event.payload["species"] == "grain:wheat"
    assert event.payload["maturity_status"] == "mature"
    assert event.payload["yield_quantity"] == 10
    assert event.payload["plot_ref"] == "plot:inf3:grain:1"


def test_inf3_grain_harvest_commits_one_ecology_owned_terminal_event_and_receipt() -> None:
    store = _seed()
    authority = EcologyHazardAuthority(store=store)
    admission = authority.admit_grain_crop(
        envelope=_admit_envelope(store),
        crop_ref="crop:inf3:grain:wheat",
        region_ref=REGION_REF,
        plot_ref="plot:inf3:grain:1",
    )
    assert admission.committed

    result = authority.harvest_grain_crop(envelope=_harvest_envelope(store))

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.ecology.grain_harvested"
    assert event.visibility_policy == "project"
    assert event.payload["crop_ref"] == "crop:inf3:grain:wheat"
    assert event.payload["item_definition"] == "grain:wheat@1"
    assert event.payload["yield_quantity"] == 10
    assert event.payload["terminal"] == "v1_terminal_no_compensation"
    assert event.payload["project_ref"] == PROJECT_REF
    assert result.idempotency_status == "new_commit"
    assert store.list_outbox()[-1].audience == "project"
    assert store.list_outbox()[-1].topic == "ecology.grain_harvest.scoped_projection"


def test_inf3_grain_harvest_full_and_checkpoint_tail_replay_match() -> None:
    store = _seed()
    authority = EcologyHazardAuthority(store=store)
    assert authority.admit_grain_crop(
        envelope=_admit_envelope(store),
        crop_ref="crop:inf3:grain:wheat",
        region_ref=REGION_REF,
        plot_ref="plot:inf3:grain:1",
    ).committed
    result = authority.harvest_grain_crop(envelope=_harvest_envelope(store))
    assert result.committed

    full = authority.regional_replay()
    tail = authority.regional_replay(checkpoint_at=result.committed_event_ids and 6)
    assert full.projection_hash == tail.projection_hash
    assert full.state == tail.state


def test_inf3_grain_harvest_rejects_unknown_source_without_write() -> None:
    store = _seed()
    before = store.export_snapshot()

    result = EcologyHazardAuthority(store=store).harvest_grain_crop(
        envelope=_harvest_envelope(store).model_copy(
            update={"payload": {"visibility_scope": "project", "target_region_ref": "region:unknown"}}
        )
    )

    assert not result.committed
    assert store.export_snapshot() == before


def test_inf3_grain_harvest_rejects_private_source_without_write() -> None:
    store = _seed()
    authority = EcologyHazardAuthority(store=store)
    admitted = authority.admit_grain_crop(
        envelope=_admit_envelope(store),
        crop_ref="crop:inf3:grain:wheat",
        region_ref=REGION_REF,
        plot_ref="plot:inf3:grain:1",
    )
    assert admitted.committed
    source = store.get_event(admitted.committed_event_ids[0])
    store._events_by_id[source.event_id] = source.model_copy(
        update={"visibility_policy": "authority_only"}, deep=True
    )
    store._events = [
        store._events_by_id[event.event_id] for event in store._events
    ]
    before = store.export_snapshot()

    result = authority.harvest_grain_crop(envelope=_harvest_envelope(store))

    assert not result.committed
    assert store.export_snapshot() == before


def test_inf3_grain_harvest_rejects_stale_target_revision_without_write() -> None:
    store = _seed()
    authority = EcologyHazardAuthority(store=store)
    admitted = authority.admit_grain_crop(
        envelope=_admit_envelope(store),
        crop_ref="crop:inf3:grain:wheat",
        region_ref=REGION_REF,
        plot_ref="plot:inf3:grain:1",
    )
    assert admitted.committed
    before = store.export_snapshot()

    result = authority.harvest_grain_crop(
        envelope=_harvest_envelope(store).model_copy(
            update={"expected_revisions": {STREAM: 5}}
        )
    )

    assert not result.committed
    assert store.export_snapshot() == before


def test_inf3_grain_harvest_rejects_ambiguous_eligible_crops_without_write() -> None:
    store = _seed()
    authority = EcologyHazardAuthority(store=store)
    assert authority.admit_grain_crop(
        envelope=_admit_envelope(store),
        crop_ref="crop:inf3:grain:wheat",
        region_ref=REGION_REF,
        plot_ref="plot:inf3:grain:1",
    ).committed
    second = _admit_envelope(store, key="inf3:grain:admit:second").model_copy(
        update={
            "idempotency_key": "ecology:grain-crop-admission:project:inf3-grain:crop:inf3:grain:wheat-2:v1",
            "expected_revisions": {STREAM: store.get_stream_head(STREAM)},
            "payload": {
                "visibility_scope": "project",
                "crop_ref": "crop:inf3:grain:wheat-2",
                "region_ref": REGION_REF,
                "plot_ref": "plot:inf3:grain:2",
            },
        },
        deep=True,
    )
    assert authority.admit_grain_crop(
        envelope=second,
        crop_ref="crop:inf3:grain:wheat-2",
        region_ref=REGION_REF,
        plot_ref="plot:inf3:grain:2",
    ).committed
    before = store.export_snapshot()

    result = authority.harvest_grain_crop(envelope=_harvest_envelope(store))

    assert not result.committed
    assert store.export_snapshot() == before


def test_inf3_grain_harvest_duplicate_replays_and_changed_duplicate_is_zero_write() -> None:
    store = _seed()
    authority = EcologyHazardAuthority(store=store)
    assert authority.admit_grain_crop(
        envelope=_admit_envelope(store),
        crop_ref="crop:inf3:grain:wheat",
        region_ref=REGION_REF,
        plot_ref="plot:inf3:grain:1",
    ).committed
    request = _harvest_envelope(store)
    first = authority.harvest_grain_crop(envelope=request)
    assert first.committed
    before = store.export_snapshot()

    duplicate = authority.harvest_grain_crop(
        envelope=request
    )
    changed = authority.harvest_grain_crop(
        envelope=request.model_copy(update={"causation_id": "event:forged"})
    )

    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed
    assert store.export_snapshot() == before


def test_inf3_grain_contract_and_event_schemas_are_static_and_exact() -> None:
    contract = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:ecology-grain-harvest@1",
        contract_kind="ecology_consumer",
    )
    assert contract.owner_ref == "authority:ecology"
    assert contract.stream_patterns == ("gameplay:ecology:{region_ref}",)
    assert contract.event_types == (
        "gameplay.ecology.grain_crop.admitted",
        "gameplay.ecology.grain_harvested",
    )
    assert contract.projection_scope == "project"

    registry = EventSchemaRegistry()
    register_inf3_grain_harvest_event_schemas(registry)
    assert registry.get("gameplay.ecology.grain_crop.admitted", 1).schema_digest
    assert registry.get("gameplay.ecology.grain_harvested", 1).schema_digest
