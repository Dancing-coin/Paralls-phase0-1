from __future__ import annotations

from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Plot, Recipe
from app.gameplay.ecology_runtime import CropRecord, EcologyHazardAuthority, HazardRecord
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.semantic_effects import ResistanceProfile


def _hazard(**changes: object) -> HazardRecord:
    values = {
        "hazard_ref": "hazard:frost:admission:1",
        "region_ref": "region:valley",
        "effect_ref": "effect:frost",
        "severity_basis_points": 5_000,
        "due_tick": 3,
        "duration_ticks": 1,
        "causal_parent_refs": ("event:weather:1",),
        "semantic_revision": "semantic:1",
        "rule_revision": "rule:1",
        "policy_revision": "policy:1",
        "idempotency_key": "hazard:frost:admission:1",
        "privacy_scope": "project",
    }
    values.update(changes)
    return HazardRecord(**values)


def _crop(**changes: object) -> CropRecord:
    values = {
        "crop_ref": "crop:wheat:admission:1",
        "region_ref": "region:valley",
        "plot_ref": "plot:bakery:1",
        "health": 100,
        "growth_basis_points": 5_000,
        "revision": 0,
        "owner_ref": "authority:crop",
    }
    values.update(changes)
    return CropRecord(**values)


def _resistance() -> ResistanceProfile:
    return ResistanceProfile(effect_ref="effect:frost", source_ref="crop:wheat:admission:1", modifier_basis_points=0, revision=1)


def _start_due_run(store: GameplayEventStore, *, run_ref: str = "run:bakery:1", facility_ref: str = "facility:bakery:1", finish_tick: int = 3) -> None:
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(facility_ref=facility_ref, plot_ref="plot:bakery:1", facility_kind="bakery", condition=1)
    recipe = Recipe(recipe_ref="recipe:bread:1", inputs={}, output_item="item:bread", duration_ticks=finish_tick)
    authority.settle_facility_acquisition(plot=Plot(plot_ref=facility.plot_ref, jurisdiction_ref="jurisdiction:1", owner_ref="owner:1"), facility=facility, command_id=f"command:facility:{run_ref}", idempotency_key=f"idem:facility:{run_ref}", causation_id=f"cause:facility:{run_ref}", correlation_id=f"corr:facility:{run_ref}")
    authority.settle_start_run(facility=facility, recipe=recipe, run_ref=run_ref, tick=0, command_id=f"command:run:{run_ref}", idempotency_key=f"idem:run:{run_ref}", causation_id=f"cause:run:{run_ref}", correlation_id=f"corr:run:{run_ref}")


def test_committed_frost_source_has_owner_provenance_and_public_redaction() -> None:
    store = GameplayEventStore()
    ecology = EcologyHazardAuthority(store=store)
    ecology.settle_frost(hazard=_hazard(), crop=_crop(), resistance=_resistance())

    source = ecology.frost_source(hazard_ref="hazard:frost:admission:1", scope="authority")
    public = ecology.frost_source(hazard_ref="hazard:frost:admission:1", scope="public")

    assert source.accepted is True
    assert source.source is not None and source.source.plot_ref == "plot:bakery:1"
    assert source.source.evidence_refs == ("hazard:hazard:frost:admission:1",)
    assert public.source is not None and public.source.evidence_refs == ()


def test_frost_without_plot_is_not_a_production_source_and_adds_no_write() -> None:
    store = GameplayEventStore()
    ecology = EcologyHazardAuthority(store=store)
    ecology.settle_frost(hazard=_hazard(), crop=_crop(plot_ref=None), resistance=_resistance())
    before = len(store.read_events())

    source = ecology.frost_source(hazard_ref="hazard:frost:admission:1", scope="authority")

    assert source.accepted is False
    assert source.error_code == "frost_source_plot_missing"
    assert len(store.read_events()) == before


def test_private_or_stale_frost_source_is_zero_write() -> None:
    store = GameplayEventStore()
    ecology = EcologyHazardAuthority(store=store)
    private = ecology.settle_frost(
        hazard=_hazard(privacy_scope="private_evidence", idempotency_key="hazard:frost:private"),
        crop=_crop(),
        resistance=_resistance(),
    )
    stale = ecology.settle_frost(
        hazard=_hazard(hazard_ref="hazard:frost:stale", idempotency_key="hazard:frost:stale"),
        crop=_crop(revision=1),
        resistance=_resistance(),
    )

    assert private.error_code == "hazard_privacy_scope_denied"
    assert stale.error_code == "revision_conflict"
    assert store.read_events() == []


def test_duplicate_frost_source_settlement_is_idempotent() -> None:
    store = GameplayEventStore()
    ecology = EcologyHazardAuthority(store=store)
    first = ecology.settle_frost(hazard=_hazard(), crop=_crop(), resistance=_resistance())
    duplicate = ecology.settle_frost(hazard=_hazard(), crop=_crop(), resistance=_resistance())

    assert first.committed is True
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == 1


def test_construction_selects_one_due_target_from_committed_projection() -> None:
    store = GameplayEventStore()
    _start_due_run(store)

    selection = ConstructionProductionAuthority(store=store).select_due_run_for_plot(plot_ref="plot:bakery:1", due_tick=3)

    assert selection.accepted is True
    assert selection.target is not None and selection.target.run.run_ref == "run:bakery:1"
    assert selection.target.expected_revision == 2


def test_construction_target_missing_ambiguous_or_not_due_is_zero_write() -> None:
    store = GameplayEventStore()
    _start_due_run(store, run_ref="run:bakery:1", finish_tick=4)
    authority = ConstructionProductionAuthority(store=store)
    before = len(store.read_events())

    missing = authority.select_due_run_for_plot(plot_ref="plot:missing", due_tick=3)
    not_due = authority.select_due_run_for_plot(plot_ref="plot:bakery:1", due_tick=3)

    assert missing.error_code == "frost_production_target_missing"
    assert not_due.error_code == "frost_production_target_not_due"
    assert len(store.read_events()) == before


def test_construction_target_ambiguity_is_zero_write() -> None:
    store = GameplayEventStore()
    _start_due_run(store, run_ref="run:bakery:1", facility_ref="facility:bakery:1")
    _start_due_run(store, run_ref="run:bakery:2", facility_ref="facility:bakery:2")
    before = len(store.read_events())

    selection = ConstructionProductionAuthority(store=store).select_due_run_for_plot(plot_ref="plot:bakery:1", due_tick=3)

    assert selection.error_code == "frost_production_target_ambiguous"
    assert len(store.read_events()) == before


def test_admission_source_replay_matches_full_and_checkpoint_tail() -> None:
    store = GameplayEventStore()
    ecology = EcologyHazardAuthority(store=store)
    ecology.settle_frost(hazard=_hazard(), crop=_crop(), resistance=_resistance())

    assert ecology.replay().projection_hash == ecology.replay(checkpoint_at=1).projection_hash


def test_admission_target_selection_matches_full_and_checkpoint_tail_rebuild() -> None:
    store = GameplayEventStore()
    _start_due_run(store)
    authority = ConstructionProductionAuthority(store=store)

    full = authority.select_due_run_for_plot(plot_ref="plot:bakery:1", due_tick=3)
    checkpoint_tail = authority.select_due_run_for_plot(
        plot_ref="plot:bakery:1",
        due_tick=3,
        checkpoint_at=1,
    )

    assert checkpoint_tail == full
