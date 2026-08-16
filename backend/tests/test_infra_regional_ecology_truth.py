from __future__ import annotations

from app.gameplay.ecology_runtime import (
    CropRecord,
    EcologyHazardAuthority,
    EnvironmentalState,
    EnvironmentRegion,
    HazardRecord,
    ResourceNode,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.shared_contracts import GameplayCommandEnvelope


def _region() -> EnvironmentRegion:
    return EnvironmentRegion(
        region_ref="region:valley",
        climate_profile_ref="climate:temperate",
        biome_tags=("biome:field",),
        jurisdiction_ref="jurisdiction:valley",
        revision=0,
    )


def _envelope(*, expected_revision: int = 0, idempotency_key: str = "ecology:region:valley:initial") -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope(
        command_id="command:ecology:valley:initial",
        command_type="gameplay.ecology.region_bundle.record",
        command_version=1,
        principal_ref="authority:ecology",
        idempotency_key=idempotency_key,
        expected_revisions={"gameplay:ecology:region:valley": expected_revision},
        causation_id="cause:ecology:valley:initial",
        correlation_id="corr:ecology:valley:initial",
        source_ref="authority:ecology",
        submitted_at="2026-08-13T00:00:00Z",
    )


def _bundle() -> tuple[EnvironmentRegion, EnvironmentalState, ResourceNode, CropRecord, HazardRecord]:
    region = _region()
    return (
        region,
        EnvironmentalState(region_ref=region.region_ref, temperature_centi_c=175, moisture_basis_points=4_000, weather_ref="weather:clear", revision=0),
        ResourceNode(node_ref="resource:valley:water", region_ref=region.region_ref, substance_ref="substance:water", quantity=90, regeneration_per_tick=2, revision=0),
        CropRecord(crop_ref="crop:valley:wheat", region_ref=region.region_ref, plot_ref="plot:valley:1", health=100, growth_basis_points=5_000, revision=0, owner_ref="authority:crop"),
        HazardRecord(hazard_ref="hazard:valley:frost", region_ref=region.region_ref, effect_ref="effect:frost", severity_basis_points=5_000, due_tick=3, duration_ticks=1, causal_parent_refs=("event:weather:valley",), semantic_revision="semantic:1", rule_revision="rule:1", policy_revision="policy:1", idempotency_key="ecology:region:valley:initial"),
    )


def test_ecology_authority_records_all_canonical_region_facts_through_one_existing_stream() -> None:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)

    result = authority.record_region_bundle(envelope=_envelope(), region=_bundle()[0], environment=_bundle()[1], resource=_bundle()[2], crop=_bundle()[3], hazard=_bundle()[4])

    assert result.committed is True
    assert {event.stream_id for event in store.read_events()} == {"gameplay:ecology:region:valley"}
    assert [event.event_type for event in store.read_events()] == [
        "gameplay.ecology.region.recorded",
        "gameplay.ecology.environment.recorded",
        "gameplay.ecology.resource.recorded",
        "gameplay.ecology.crop.recorded",
        "gameplay.ecology.hazard.recorded",
    ]
    assert len(store.list_outbox()) == 5


def test_ecology_region_bundle_rejects_revision_or_region_mismatch_without_writes() -> None:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    region, environment, resource, crop, hazard = _bundle()
    stale = authority.record_region_bundle(envelope=_envelope(expected_revision=1), region=region, environment=environment, resource=resource, crop=crop, hazard=hazard)
    mismatch = authority.record_region_bundle(envelope=_envelope(), region=region, environment=environment.model_copy(update={"region_ref": "region:other"}), resource=resource, crop=crop, hazard=hazard)

    assert stale.failure is not None and stale.failure.error_code == "revision_conflict"
    assert mismatch.failure is not None and mismatch.failure.error_code == "ecology_region_bundle_mismatch"
    assert store.read_events() == []


def test_ecology_region_projection_is_scope_filtered_and_checkpoint_tail_equivalent() -> None:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    region, environment, resource, crop, hazard = _bundle()
    authority.record_region_bundle(envelope=_envelope(), region=region, environment=environment, resource=resource, crop=crop, hazard=hazard)

    public = authority.regional_projection(scope="public")
    authority_view = authority.regional_projection(scope="authority")

    assert public["regions"]["region:valley"]["jurisdiction_ref"] == "jurisdiction:valley"
    assert "causal_parent_refs" not in public["hazards"]["hazard:valley:frost"]
    assert authority_view["hazards"]["hazard:valley:frost"]["causal_parent_refs"] == ["event:weather:valley"]
    assert authority.regional_replay().projection_hash == authority.regional_replay(checkpoint_at=3).projection_hash


def test_ecology_retirement_is_owner_fragment_event_derived_and_idempotent() -> None:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    region, environment, resource, crop, hazard = _bundle()
    authority.record_region_bundle(envelope=_envelope(), region=region, environment=environment, resource=resource, crop=crop, hazard=hazard)
    retirement = GameplayCommandEnvelope(
        command_id="command:ecology:valley:retire-hazard",
        command_type="gameplay.ecology.hazard.retire",
        command_version=1,
        principal_ref="authority:ecology",
        idempotency_key="ecology:region:valley:retire-hazard",
        expected_revisions={"gameplay:ecology:region:valley": 5},
        causation_id="cause:ecology:valley:retire-hazard",
        correlation_id="corr:ecology:valley:retire-hazard",
        source_ref="authority:ecology",
        submitted_at="2026-08-13T00:01:00Z",
    )

    first = authority.retire_record(envelope=retirement, region_ref=region.region_ref, record_kind="hazard", record_ref=hazard.hazard_ref)
    duplicate = authority.retire_record(envelope=retirement, region_ref=region.region_ref, record_kind="hazard", record_ref=hazard.hazard_ref)

    assert first.committed is True
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert store.read_events()[-1].event_type == "gameplay.ecology.hazard.retired"
    assert hazard.hazard_ref not in authority.regional_projection(scope="authority")["hazards"]


def test_ecology_retirement_of_unknown_or_wrong_revision_is_zero_write() -> None:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    envelope = _envelope()

    unknown = authority.retire_record(envelope=envelope, region_ref="region:valley", record_kind="hazard", record_ref="hazard:missing")
    invalid_kind = authority.retire_record(envelope=envelope, region_ref="region:valley", record_kind="market", record_ref="market:missing")

    assert unknown.failure is not None and unknown.failure.error_code == "ecology_record_missing"
    assert invalid_kind.failure is not None and invalid_kind.failure.error_code == "ecology_record_kind_unsupported"
    assert store.read_events() == []


def test_ecology_update_replaces_one_record_only_after_owner_revision_check() -> None:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    region, environment, resource, crop, hazard = _bundle()
    authority.record_region_bundle(envelope=_envelope(), region=region, environment=environment, resource=resource, crop=crop, hazard=hazard)
    update = GameplayCommandEnvelope(
        command_id="command:ecology:valley:resource-update",
        command_type="gameplay.ecology.resource.record",
        command_version=1,
        principal_ref="authority:ecology",
        idempotency_key="ecology:region:valley:resource-update",
        expected_revisions={"gameplay:ecology:region:valley": 5},
        causation_id="cause:ecology:valley:resource-update",
        correlation_id="corr:ecology:valley:resource-update",
        source_ref="authority:ecology",
        submitted_at="2026-08-13T00:02:00Z",
    )

    result = authority.record_resource(
        envelope=update,
        resource=resource.model_copy(update={"quantity": 88, "revision": 1}),
    )

    assert result.committed is True
    assert authority.regional_projection(scope="public")["resources"][resource.node_ref]["quantity"] == 88
    assert len(store.read_events()) == 6


def test_ecology_private_or_bundle_overwrite_is_zero_write() -> None:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    region, environment, resource, crop, hazard = _bundle()
    private = authority.record_region_bundle(
        envelope=_envelope(),
        region=region,
        environment=environment,
        resource=resource,
        crop=crop,
        hazard=hazard.model_copy(update={"privacy_scope": "private_evidence"}),
    )
    first = authority.record_region_bundle(envelope=_envelope(), region=region, environment=environment, resource=resource, crop=crop, hazard=hazard)
    changed = authority.record_region_bundle(
        envelope=_envelope(),
        region=region,
        environment=environment,
        resource=resource.model_copy(update={"quantity": 89}),
        crop=crop,
        hazard=hazard,
    )

    assert private.failure is not None and private.failure.error_code == "ecology_privacy_scope_denied"
    assert first.committed is True
    assert changed.failure is not None and changed.failure.error_code == "ecology_bundle_not_initial"
    assert len(store.read_events()) == 5


def test_ecology_region_bundle_cannot_overwrite_existing_record_lifecycle() -> None:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    region, environment, resource, crop, hazard = _bundle()
    authority.record_region_bundle(envelope=_envelope(), region=region, environment=environment, resource=resource, crop=crop, hazard=hazard)
    overwrite = authority.record_region_bundle(
        envelope=_envelope(expected_revision=5, idempotency_key="ecology:region:valley:overwrite"),
        region=region,
        environment=environment,
        resource=resource,
        crop=crop,
        hazard=hazard,
    )

    assert overwrite.failure is not None and overwrite.failure.error_code == "ecology_bundle_not_initial"
    assert len(store.read_events()) == 5


def test_ecology_region_recorded_event_is_canonical() -> None:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    region, environment, resource, crop, hazard = _bundle()
    authority.record_region_bundle(envelope=_envelope(), region=region, environment=environment, resource=resource, crop=crop, hazard=hazard)
    assert store.read_events()[0].event_type == "gameplay.ecology.region.recorded"


def test_ecology_environment_recorded_event_is_canonical() -> None:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    region, environment, resource, crop, hazard = _bundle()
    authority.record_region_bundle(envelope=_envelope(), region=region, environment=environment, resource=resource, crop=crop, hazard=hazard)
    assert store.read_events()[1].event_type == "gameplay.ecology.environment.recorded"


def test_ecology_resource_recorded_event_is_canonical() -> None:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    region, environment, resource, crop, hazard = _bundle()
    authority.record_region_bundle(envelope=_envelope(), region=region, environment=environment, resource=resource, crop=crop, hazard=hazard)
    assert store.read_events()[2].event_type == "gameplay.ecology.resource.recorded"


def test_ecology_crop_recorded_event_is_canonical() -> None:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    region, environment, resource, crop, hazard = _bundle()
    authority.record_region_bundle(envelope=_envelope(), region=region, environment=environment, resource=resource, crop=crop, hazard=hazard)
    assert store.read_events()[3].event_type == "gameplay.ecology.crop.recorded"


def test_ecology_hazard_recorded_event_is_canonical() -> None:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    region, environment, resource, crop, hazard = _bundle()
    authority.record_region_bundle(envelope=_envelope(), region=region, environment=environment, resource=resource, crop=crop, hazard=hazard)
    assert store.read_events()[4].event_type == "gameplay.ecology.hazard.recorded"


def test_ecology_single_record_rejects_uncommitted_or_skipped_record_revision() -> None:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    _, _, resource, _, _ = _bundle()
    rejected = authority.record_resource(envelope=_envelope(), resource=resource.model_copy(update={"revision": 1}))

    assert rejected.failure is not None and rejected.failure.error_code == "ecology_record_revision_conflict"
    assert store.read_events() == []


def test_ecology_authority_only_visibility_is_hidden_from_public_projection() -> None:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    region, environment, resource, crop, hazard = _bundle()
    envelope = _envelope().model_copy(update={"payload": {"visibility_scope": "authority_only"}})

    result = authority.record_region_bundle(envelope=envelope, region=region, environment=environment, resource=resource, crop=crop, hazard=hazard)

    assert result.committed is True
    assert authority.regional_projection(scope="public")["regions"] == {}
    assert authority.regional_projection(scope="authority")["regions"][region.region_ref]["jurisdiction_ref"] == "jurisdiction:valley"


def _recorded_authority() -> tuple[EcologyHazardAuthority, EnvironmentRegion, EnvironmentalState, ResourceNode, CropRecord, HazardRecord]:
    authority = EcologyHazardAuthority(store=GameplayEventStore())
    region, environment, resource, crop, hazard = _bundle()
    result = authority.record_region_bundle(envelope=_envelope(), region=region, environment=environment, resource=resource, crop=crop, hazard=hazard)
    assert result.committed is True
    return authority, region, environment, resource, crop, hazard


def _retirement_envelope(*, record_kind: str, expected_revision: int = 5) -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope(
        command_id=f"command:ecology:valley:retire-{record_kind}",
        command_type=f"gameplay.ecology.{record_kind}.retire",
        command_version=1,
        principal_ref="authority:ecology",
        idempotency_key=f"ecology:region:valley:retire-{record_kind}",
        expected_revisions={"gameplay:ecology:region:valley": expected_revision},
        causation_id=f"cause:ecology:valley:retire-{record_kind}",
        correlation_id=f"corr:ecology:valley:retire-{record_kind}",
        source_ref="authority:ecology",
        submitted_at="2026-08-13T00:03:00Z",
    )


def test_ecology_region_retired_event_is_canonical() -> None:
    authority, region, _, _, _, _ = _recorded_authority()
    result = authority.retire_record(envelope=_retirement_envelope(record_kind="region"), region_ref=region.region_ref, record_kind="region", record_ref=region.region_ref)
    assert result.committed is True
    assert authority.store.read_events()[-1].event_type == "gameplay.ecology.region.retired"


def test_ecology_environment_retired_event_is_canonical() -> None:
    authority, region, _, _, _, _ = _recorded_authority()
    result = authority.retire_record(envelope=_retirement_envelope(record_kind="environment"), region_ref=region.region_ref, record_kind="environment", record_ref=region.region_ref)
    assert result.committed is True
    assert authority.store.read_events()[-1].event_type == "gameplay.ecology.environment.retired"


def test_ecology_resource_retired_event_is_canonical() -> None:
    authority, region, _, resource, _, _ = _recorded_authority()
    result = authority.retire_record(envelope=_retirement_envelope(record_kind="resource"), region_ref=region.region_ref, record_kind="resource", record_ref=resource.node_ref)
    assert result.committed is True
    assert authority.store.read_events()[-1].event_type == "gameplay.ecology.resource.retired"


def test_ecology_crop_retired_event_is_canonical() -> None:
    authority, region, _, _, crop, _ = _recorded_authority()
    result = authority.retire_record(envelope=_retirement_envelope(record_kind="crop"), region_ref=region.region_ref, record_kind="crop", record_ref=crop.crop_ref)
    assert result.committed is True
    assert authority.store.read_events()[-1].event_type == "gameplay.ecology.crop.retired"


def test_ecology_hazard_retired_event_is_canonical() -> None:
    authority, region, _, _, _, hazard = _recorded_authority()
    result = authority.retire_record(envelope=_retirement_envelope(record_kind="hazard"), region_ref=region.region_ref, record_kind="hazard", record_ref=hazard.hazard_ref)
    assert result.committed is True
    assert authority.store.read_events()[-1].event_type == "gameplay.ecology.hazard.retired"
