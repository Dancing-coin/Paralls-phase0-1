from __future__ import annotations

from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Plot, Recipe
from app.gameplay.ecology_runtime import CropRecord, EcologyHazardAuthority, EnvironmentalState, EnvironmentRegion, HazardRecord, ResourceNode
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.shared_contracts import GameplayCommandEnvelope


def _bundle(*, privacy_scope: str = "project") -> tuple[EnvironmentRegion, EnvironmentalState, ResourceNode, CropRecord, HazardRecord]:
    region = EnvironmentRegion(region_ref="region:propagation", climate_profile_ref="climate:temperate", biome_tags=("biome:field",), jurisdiction_ref="jurisdiction:propagation", revision=0)
    return (
        region,
        EnvironmentalState(region_ref=region.region_ref, temperature_centi_c=175, moisture_basis_points=4_000, weather_ref="weather:clear", revision=0),
        ResourceNode(node_ref="resource:propagation:water", region_ref=region.region_ref, substance_ref="substance:water", quantity=90, regeneration_per_tick=2, revision=0),
        CropRecord(crop_ref="crop:propagation:wheat", region_ref=region.region_ref, plot_ref="plot:propagation:bakery", health=100, growth_basis_points=5_000, revision=0, owner_ref="authority:crop"),
        HazardRecord(hazard_ref="hazard:propagation:frost", region_ref=region.region_ref, effect_ref="effect:frost", source_crop_ref="crop:propagation:wheat", severity_basis_points=5_000, due_tick=3, duration_ticks=1, causal_parent_refs=("event:weather:propagation",), semantic_revision="semantic:1", rule_revision="rule:1", policy_revision="policy:1", idempotency_key="ecology:propagation:initial", privacy_scope=privacy_scope),
    )


def _envelope(*, visibility_scope: str = "project", idempotency_key: str = "ecology:propagation:initial", expected_revision: int = 0) -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope(
        command_id=f"command:{idempotency_key}", command_type="gameplay.ecology.region_bundle.record", command_version=1,
        principal_ref="authority:ecology", idempotency_key=idempotency_key,
        expected_revisions={"gameplay:ecology:region:propagation": expected_revision},
        causation_id=f"cause:{idempotency_key}", correlation_id=f"corr:{idempotency_key}", source_ref="authority:ecology",
        submitted_at="2026-08-13T01:00:00Z", payload={"visibility_scope": visibility_scope},
    )


def _record_source(store: GameplayEventStore, *, visibility_scope: str = "project") -> EcologyHazardAuthority:
    authority = EcologyHazardAuthority(store=store)
    region, environment, resource, crop, hazard = _bundle()
    result = authority.record_region_bundle(envelope=_envelope(visibility_scope=visibility_scope), region=region, environment=environment, resource=resource, crop=crop, hazard=hazard)
    assert result.committed is True
    return authority


def _start_due_run(store: GameplayEventStore) -> ConstructionProductionAuthority:
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(facility_ref="facility:propagation:bakery", plot_ref="plot:propagation:bakery", facility_kind="bakery", condition=1)
    recipe = Recipe(recipe_ref="recipe:propagation:bread", inputs={}, output_item="item:bread", duration_ticks=3)
    authority.settle_facility_acquisition(plot=Plot(plot_ref=facility.plot_ref, jurisdiction_ref="jurisdiction:propagation", owner_ref="owner:propagation"), facility=facility, command_id="command:facility:propagation", idempotency_key="idem:facility:propagation", causation_id="cause:facility:propagation", correlation_id="corr:facility:propagation")
    authority.settle_start_run(facility=facility, recipe=recipe, run_ref="run:propagation:bakery", tick=0, command_id="command:run:propagation", idempotency_key="idem:run:propagation", causation_id="cause:run:propagation", correlation_id="corr:run:propagation")
    return authority


def _intent(store: GameplayEventStore):
    ecology = _record_source(store)
    intent, error_code = ecology.admit_canonical_frost_to_construction(hazard_ref="hazard:propagation:frost")
    assert error_code is None and intent is not None
    return intent


def test_registered_canonical_frost_edge_commits_one_construction_owner_fragment() -> None:
    store = GameplayEventStore()
    construction = _start_due_run(store)
    intent = _intent(store)
    before = len(store.read_events())

    result = construction.settle_canonical_frost_due_finish(intent.command, admission=intent.admission)

    assert result.committed is True
    assert len(store.read_events()) == before + 1
    event = store.read_events()[-1]
    assert event.event_type == "gameplay.construction_production.run_finished"
    assert event.payload["canonical_hazard_propagation"]["edge_ref"] == "ecology-hazard:frost-to-construction-finish:v1"


def test_unknown_canonical_hazard_edge_is_zero_write() -> None:
    store = GameplayEventStore()
    construction = _start_due_run(store)
    intent = _intent(store)
    before = len(store.read_events())

    unknown = construction.settle_canonical_frost_due_finish(intent.command.model_copy(update={"edge_ref": "ecology-hazard:unknown"}), admission=intent.admission)

    assert unknown.error_code == "canonical_hazard_edge_unsupported"
    assert len(store.read_events()) == before


def test_disabled_canonical_hazard_edge_is_zero_write() -> None:
    store = GameplayEventStore()
    construction = _start_due_run(store)
    intent = _intent(store)
    before = len(store.read_events())

    disabled = construction.settle_canonical_frost_due_finish(intent.command.model_copy(update={"enabled": False}), admission=intent.admission)

    assert disabled.error_code == "canonical_hazard_edge_disabled"
    assert len(store.read_events()) == before


def test_missing_canonical_hazard_source_is_zero_write() -> None:
    store = GameplayEventStore()
    construction = _start_due_run(store)
    intent = _intent(store)
    before = len(store.read_events())

    missing = construction.settle_canonical_frost_due_finish(intent.command.model_copy(update={"hazard_event_id": "event:missing"}), admission=intent.admission)

    assert missing.error_code == "canonical_hazard_admission_required"
    assert len(store.read_events()) == before


def test_stale_canonical_hazard_source_revision_is_zero_write() -> None:
    store = GameplayEventStore()
    construction = _start_due_run(store)
    intent = _intent(store)
    before = len(store.read_events())

    stale = construction.settle_canonical_frost_due_finish(intent.command.model_copy(update={"ecology_stream_revision": intent.command.ecology_stream_revision - 1}), admission=intent.admission)

    assert stale.error_code == "canonical_hazard_source_revision_conflict"
    assert len(store.read_events()) == before


def test_canonical_hazard_privacy_scope_is_zero_write() -> None:
    store = GameplayEventStore()
    construction = _start_due_run(store)
    intent = _intent(store)
    before = len(store.read_events())

    privacy = construction.settle_canonical_frost_due_finish(intent.command.model_copy(update={"privacy_scope": "authority_only"}), admission=intent.admission)

    assert privacy.error_code == "canonical_hazard_privacy_scope_denied"
    assert len(store.read_events()) == before


def test_canonical_hazard_direct_consumer_invocation_is_zero_write() -> None:
    store = GameplayEventStore()
    construction = _start_due_run(store)
    intent = _intent(store)
    before = len(store.read_events())

    direct = construction.settle_canonical_frost_due_finish(intent.command.model_copy(update={"source_authority_ref": "client:godot"}), admission=intent.admission)

    assert direct.error_code == "canonical_hazard_source_authority_required"
    assert len(store.read_events()) == before


def test_forged_ecology_command_without_transient_admission_is_zero_write() -> None:
    store = GameplayEventStore()
    construction = _start_due_run(store)
    intent = _intent(store)
    before = len(store.read_events())

    forged = construction.settle_canonical_frost_due_finish(intent.command)

    assert forged.error_code == "canonical_hazard_admission_required"
    assert len(store.read_events()) == before


def test_real_class_forged_canonical_hazard_admission_is_zero_write() -> None:
    store = GameplayEventStore()
    construction = _start_due_run(store)
    intent = _intent(store)
    before = len(store.read_events())
    forged_admission = type(
        "CanonicalHazardConsumerAdmission",
        (),
        {
            "edge_ref": intent.command.edge_ref,
            "hazard_event_id": intent.command.hazard_event_id,
            "crop_event_id": intent.command.crop_event_id,
        },
    )()

    forged = construction.settle_canonical_frost_due_finish(
        intent.command,
        admission=forged_admission,
    )

    assert forged.error_code == "canonical_hazard_admission_required"
    assert len(store.read_events()) == before


def test_module_api_cannot_issue_forged_canonical_hazard_admission() -> None:
    store = GameplayEventStore()
    construction = _start_due_run(store)
    intent = _intent(store)
    before = len(store.read_events())
    from app.gameplay import construction_production_runtime as runtime
    from app.gameplay import ecology_runtime

    assert not hasattr(runtime, "CanonicalHazardConsumerAdmission")
    assert not hasattr(runtime, "_issue_canonical_hazard_admission")
    assert not hasattr(runtime, "_CANONICAL_HAZARD_ADMISSION_ISSUER")
    assert not hasattr(ecology_runtime, "_ECOLOGY_CANONICAL_HAZARD_ADMISSION_ISSUER")
    forged_admission = object()

    forged = construction.settle_canonical_frost_due_finish(
        intent.command,
        admission=forged_admission,
    )

    assert forged.error_code == "canonical_hazard_admission_required"
    assert len(store.read_events()) == before


def test_canonical_hazard_pins_exact_linked_crop_with_multiple_crops_in_region() -> None:
    store = GameplayEventStore()
    ecology = _record_source(store)
    _, _, resource, crop, _ = _bundle()
    second = crop.model_copy(update={"crop_ref": "crop:propagation:other", "plot_ref": "plot:propagation:other"})
    envelope = _envelope(idempotency_key="ecology:propagation:other-crop", expected_revision=5)
    assert ecology.record_record(envelope=envelope, record_kind="crop", record=second).committed is True
    before = len(store.read_events())

    proposal = ecology.propose_canonical_frost_to_construction(hazard_ref="hazard:propagation:frost")

    assert proposal.accepted is True and proposal.command is not None
    assert proposal.command.crop_ref == crop.crop_ref
    assert len(store.read_events()) == before

def test_canonical_hazard_without_an_active_linked_crop_is_zero_write() -> None:
    store = GameplayEventStore()
    ecology = _record_source(store)
    missing_linked = HazardRecord(**{**_bundle()[4].model_dump(), "hazard_ref": "hazard:propagation:unlinked", "source_crop_ref": "crop:propagation:missing", "idempotency_key": "ecology:propagation:unlinked"})
    unlinked_envelope = _envelope(idempotency_key="ecology:propagation:unlinked", expected_revision=5)
    assert ecology.record_record(envelope=unlinked_envelope, record_kind="hazard", record=missing_linked).committed is True
    after_unlinked = len(store.read_events())

    rejected = ecology.propose_canonical_frost_to_construction(hazard_ref="hazard:propagation:unlinked")

    assert rejected.error_code == "canonical_hazard_crop_source_missing"
    assert len(store.read_events()) == after_unlinked


def test_authority_only_canonical_source_cannot_propose_a_project_edge() -> None:
    store = GameplayEventStore()
    ecology = _record_source(store, visibility_scope="authority_only")
    before = len(store.read_events())

    proposal = ecology.propose_canonical_frost_to_construction(hazard_ref="hazard:propagation:frost")

    assert proposal.accepted is False
    assert proposal.error_code == "canonical_hazard_source_privacy_denied"
    assert len(store.read_events()) == before


def test_retired_canonical_hazard_cannot_propose_an_edge_or_write() -> None:
    store = GameplayEventStore()
    ecology = _record_source(store)
    retirement = _envelope(idempotency_key="ecology:propagation:retire-hazard", expected_revision=5).model_copy(
        update={"command_type": "gameplay.ecology.hazard.retire"}
    )
    assert ecology.retire_record(envelope=retirement, region_ref="region:propagation", record_kind="hazard", record_ref="hazard:propagation:frost").committed is True
    before = len(store.read_events())

    proposal = ecology.propose_canonical_frost_to_construction(hazard_ref="hazard:propagation:frost")

    assert proposal.accepted is False
    assert proposal.error_code == "canonical_hazard_source_retired"
    assert len(store.read_events()) == before


def test_canonical_hazard_edge_is_idempotent_and_source_revision_conflicts_after_proposal() -> None:
    store = GameplayEventStore()
    construction = _start_due_run(store)
    intent = _intent(store)
    first = construction.settle_canonical_frost_due_finish(intent.command, admission=intent.admission)
    duplicate = construction.settle_canonical_frost_due_finish(intent.command, admission=intent.admission)

    assert first.committed is True
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == 8

    stale_store = GameplayEventStore()
    stale_construction = _start_due_run(stale_store)
    stale_intent = _intent(stale_store)
    ecology = EcologyHazardAuthority(store=stale_store)
    _, _, resource, _, _ = _bundle()
    update = _envelope(idempotency_key="ecology:propagation:resource-update", expected_revision=5)
    assert ecology.record_resource(envelope=update, resource=resource.model_copy(update={"quantity": 89, "revision": 1})).committed is True
    before = len(stale_store.read_events())

    rejected = stale_construction.settle_canonical_frost_due_finish(stale_intent.command, admission=stale_intent.admission)

    assert rejected.error_code == "canonical_hazard_source_revision_conflict"
    assert len(stale_store.read_events()) == before


def test_canonical_hazard_edge_scopes_provenance_and_replays_checkpoint_tail() -> None:
    store = GameplayEventStore()
    construction = _start_due_run(store)
    intent = _intent(store)
    assert construction.settle_canonical_frost_due_finish(intent.command, admission=intent.admission).committed is True

    public = construction.canonical_frost_finish_projection(scope="public")
    authority = construction.canonical_frost_finish_projection(scope="authority")

    assert public["finished_runs"][0]["run_ref"] == "run:propagation:bakery"
    assert public["canonical_hazard_propagation"] == ()
    assert authority["canonical_hazard_propagation"][0]["hazard_ref"] == "hazard:propagation:frost"
    assert construction.canonical_frost_replay().projection_hash == construction.canonical_frost_replay(checkpoint_at=4).projection_hash
