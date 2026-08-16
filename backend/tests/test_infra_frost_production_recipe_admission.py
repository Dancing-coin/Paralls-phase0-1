from __future__ import annotations

from app.gameplay.construction_production_runtime import ConstructionProductionAuthority, Facility, Plot, Recipe
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.settlement_plan import build_atomic_event_batch


def _authority_with_run() -> ConstructionProductionAuthority:
    store = GameplayEventStore()
    authority = ConstructionProductionAuthority(store=store)
    facility = Facility(facility_ref="facility:bakery:recipe:1", plot_ref="plot:bakery:recipe:1", facility_kind="bakery", condition=1)
    recipe = Recipe(recipe_ref="recipe:bread:recipe:1", inputs={"item:flour": 2}, output_item="item:bread", duration_ticks=3)
    authority.settle_facility_acquisition(
        plot=Plot(plot_ref=facility.plot_ref, jurisdiction_ref="jurisdiction:1", owner_ref="owner:1"),
        facility=facility,
        command_id="command:facility:recipe:1",
        idempotency_key="idem:facility:recipe:1",
        causation_id="cause:facility:recipe:1",
        correlation_id="corr:facility:recipe:1",
    )
    authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:bakery:recipe:1",
        tick=0,
        command_id="command:run:recipe:1",
        idempotency_key="idem:run:recipe:1",
        causation_id="cause:run:recipe:1",
        correlation_id="corr:run:recipe:1",
    )
    return authority


def test_committed_run_started_event_derives_authority_recipe_with_source_revision() -> None:
    authority = _authority_with_run()

    result = authority.recipe_for_run(
        run_ref="run:bakery:recipe:1",
        expected_source_revision=2,
        scope="authority",
    )

    assert result.accepted is True
    assert result.recipe is not None
    assert result.recipe.recipe == Recipe(
        recipe_ref="recipe:bread:recipe:1",
        inputs={},
        output_item="item:bread",
        duration_ticks=3,
    )
    assert result.recipe.source_stream_revision == 2


def test_recipe_public_missing_and_stale_queries_are_zero_write() -> None:
    authority = _authority_with_run()
    before = len(authority._store.read_events())

    public = authority.recipe_for_run(run_ref="run:bakery:recipe:1", expected_source_revision=2, scope="public")
    missing = authority.recipe_for_run(run_ref="run:missing", expected_source_revision=0, scope="authority")
    stale = authority.recipe_for_run(run_ref="run:bakery:recipe:1", expected_source_revision=1, scope="authority")

    assert public.error_code == "construction_recipe_scope_denied"
    assert missing.error_code == "construction_recipe_missing"
    assert stale.error_code == "construction_recipe_revision_conflict"
    assert len(authority._store.read_events()) == before


def test_duplicate_run_start_reuses_one_committed_recipe_snapshot() -> None:
    authority = _authority_with_run()
    facility = authority.projector().facilities["facility:bakery:recipe:1"]
    duplicate = authority.settle_start_run(
        facility=facility,
        recipe=Recipe(recipe_ref="recipe:bread:recipe:1", inputs={"item:flour": 2}, output_item="item:bread", duration_ticks=3),
        run_ref="run:bakery:recipe:1",
        tick=0,
        command_id="command:run:recipe:1",
        idempotency_key="idem:run:recipe:1",
        causation_id="cause:run:recipe:1",
        correlation_id="corr:run:recipe:1",
    )

    assert duplicate.idempotency_status == "duplicate_replayed"
    assert len(authority._store.read_events()) == 2
    assert authority.recipe_for_run(run_ref="run:bakery:recipe:1", expected_source_revision=2, scope="authority").accepted


def test_legacy_run_event_without_recipe_snapshot_is_zero_write_rejected() -> None:
    store = GameplayEventStore()
    stream_id = "gameplay:construction_production:facility:legacy:1"
    store.append_batch(
        build_atomic_event_batch(
            command_id="command:legacy:run:1",
            principal_ref="actor_gameplay.construction_production_domain",
            stream_id=stream_id,
            expected_revision=0,
            event_specs=[("gameplay.construction_production.run_started", {
                "run_ref": "run:legacy:1",
                "facility_ref": "facility:legacy:1",
                "recipe_ref": "recipe:legacy:1",
                "started_tick": 0,
                "finish_tick": 3,
                "reservation_refs": (),
                "output_item": "item:bread",
            })],
            idempotency_key="idem:legacy:run:1",
            causation_id="cause:legacy:run:1",
            correlation_id="corr:legacy:run:1",
        )
    )
    authority = ConstructionProductionAuthority(store=store)
    before = len(store.read_events())

    result = authority.recipe_for_run(run_ref="run:legacy:1", expected_source_revision=1, scope="authority")

    assert result.error_code == "construction_recipe_snapshot_missing"
    assert len(store.read_events()) == before


def test_recipe_admission_is_idempotent_and_checkpoint_tail_rebuild_is_equal() -> None:
    authority = _authority_with_run()

    first = authority.recipe_for_run(run_ref="run:bakery:recipe:1", expected_source_revision=2, scope="authority")
    duplicate = authority.recipe_for_run(run_ref="run:bakery:recipe:1", expected_source_revision=2, scope="authority")
    checkpoint_tail = authority.recipe_for_run(
        run_ref="run:bakery:recipe:1",
        expected_source_revision=2,
        scope="authority",
        checkpoint_at=1,
    )

    assert duplicate == first
    assert checkpoint_tail == first
