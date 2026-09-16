from __future__ import annotations

import hashlib
import json
import pytest

from app.gameplay.event_store import GameplayEventStore
from app.population_continuity.models import WorldModeProfile
from app.population_continuity.roster import PopulationRoster
from app.population_continuity.siming_contracts import PopulationReadSet
from app.population_continuity.world import WorldContinuityRuntime
from app.population_continuity.hot_state import PopulationDueIndex


def test_unchanged_due_tick_refreshes_revision_without_accumulating_heap_entries():
    index = PopulationDueIndex()
    for revision in range(30):
        for actor in range(100):
            index.schedule(str(actor), "b0", 21600, revision)
    assert len(index._heap) == 100
    assert index.get("0", "b0") == (21600, 29)
    assert index.due_items(30) == ()
    assert len(index.pop_due(21600)) == 100


def _runtime(population: int | None = None) -> WorldContinuityRuntime:
    runtime = WorldContinuityRuntime(
        store=GameplayEventStore(),
        mode=WorldModeProfile(
            world_ref="due-test",
            mode="simulation",
            revision="mode:due:v1",
            cadence_class="daily",
            batch_limit=3,
            wake_budget=3,
            catch_up_limit=2,
            degraded_threshold=20,
        ),
        roster=(
            PopulationRoster(
                actor_ids=tuple(f"resident-{index:05d}" for index in range(population))
            )
            if population is not None
            else None
        ),
    )
    runtime.resume()
    return runtime


def test_preview_is_readonly_and_confirmation_advances_every_actor() -> None:
    runtime = _runtime()
    cadence = runtime.build_population_cadence(window_start=100, window_end=3_700)
    before = runtime.population_hot_state.export_rows()

    projections = runtime.build_population_projections(cadence)

    assert runtime.population_hot_state.export_rows() == before
    assert len(projections) == len(runtime.roster.actor_ids)
    # 首次确认从可重建初始 tick 0 补算，不能跳过未计算间隙。
    assert {row.payload["from_tick"] for row in projections} == {0}
    assert {row.payload["to_tick"] for row in projections} == {3_700}
    assert {row.payload["simulation_tick_cursor"] for row in projections} == {3_700}

    receipt = runtime.confirm_population_cadence(cadence)

    assert receipt.status == "committed"
    assert receipt.advanced_count == len(runtime.roster.actor_ids)
    assert all(
        runtime.population_hot_state.read(actor)["last_update_tick"] == 3_700
        for actor in runtime.roster.actor_ids
    )


def test_confirmation_is_idempotent_but_rejects_overlap_and_rule_conflict() -> None:
    runtime = _runtime()
    first = runtime.build_population_cadence(window_start=0, window_end=3_600)
    committed = runtime.confirm_population_cadence(first)
    revisions = {
        actor: runtime.population_hot_state.read(actor)["revision"]
        for actor in runtime.roster.actor_ids
    }

    repeated = runtime.confirm_population_cadence(first)

    assert repeated.status == "idempotent_replay"
    assert repeated.result_digest == committed.result_digest
    assert revisions == {
        actor: runtime.population_hot_state.read(actor)["revision"]
        for actor in runtime.roster.actor_ids
    }

    overlap = runtime.build_population_cadence(window_start=1_800, window_end=5_400)
    with pytest.raises(ValueError, match="population_cadence_confirmation_conflict"):
        runtime.confirm_population_cadence(overlap)

    next_window = runtime.build_population_cadence(
        window_start=3_600,
        window_end=7_200,
        ruleset_revision="rules:population:v2",
    )
    with pytest.raises(ValueError, match="population_cadence_confirmation_context_invalid"):
        runtime.confirm_population_cadence(next_window)


def test_replay_rebuilds_hot_rows_and_due_backlog_without_a_full_snapshot() -> None:
    source = _runtime()
    cadences = []
    for start in range(0, 86_400, 21_600):
        cadence = source.build_population_cadence(window_start=start, window_end=start + 21_600)
        source.build_population_projections(cadence)
        source.confirm_population_cadence(cadence)
        cadences.append(cadence)

    restored = _runtime()
    for cadence in cadences:
        restored.confirm_population_cadence(cadence)

    assert restored.population_hot_state.export_rows() == source.population_hot_state.export_rows()
    assert restored.due_population_work(86_400) == source.due_population_work(86_400)
    assert all(
        restored.population_hot_state.read(actor)["last_update_tick"] == 86_400
        for actor in restored.roster.actor_ids
    )


def test_due_selection_does_not_gate_b0_cursor_and_failed_work_can_requeue() -> None:
    runtime = _runtime()
    first = runtime.build_population_cadence(window_start=0, window_end=3_600)
    receipt = runtime.confirm_population_cadence(first)

    assert receipt.due_count == 0
    assert receipt.advanced_count == len(runtime.roster.actor_ids)

    second = runtime.build_population_cadence(window_start=3_600, window_end=21_600)
    preview = runtime.build_population_projections(second)
    due_before_confirm = runtime.due_population_work(21_600)
    assert len(due_before_confirm) == len(runtime.roster.actor_ids)
    assert runtime.build_population_projections(second) is preview
    assert runtime.due_population_work(21_600) == due_before_confirm
    receipt = runtime.confirm_population_cadence(second)

    assert receipt.advanced_count == len(runtime.roster.actor_ids)
    assert receipt.presentation_due_count == len(runtime.roster.actor_ids)
    assert receipt.due_count == len(runtime.roster.actor_ids)
    assert receipt.deferred_count == 0
    assert runtime.due_population_work(21_600) == ()
    assert len(runtime.due_population_work(43_200)) == len(runtime.roster.actor_ids)
    assert runtime.latest_confirmation == receipt
    assert runtime.last_population_confirmation == receipt

    due = runtime.claim_due_population_work(43_200, limit=1)
    assert len(due) == 1
    actor_id, obligation_id, due_tick = due[0]
    runtime.requeue_due_population_work(actor_id, obligation_id, due_tick, revision=1)
    assert runtime.due_population_work(43_200)[0] == due[0]


def test_b0_confirmation_preserves_independent_authorized_due_work() -> None:
    runtime = _runtime(2)
    runtime.requeue_due_population_work(
        "resident-00000", "b1:authorized-work", 21_600, revision=0
    )
    cadence = runtime.build_population_cadence(window_start=0, window_end=21_600)

    runtime.confirm_population_cadence(cadence)

    assert runtime.due_population_work(21_600) == (
        ("resident-00000", "b1:authorized-work", 21_600),
    )


@pytest.mark.parametrize("population", [54, 100, 1_000, 10_000])
def test_projection_digest_and_candidate_input_are_equal_for_serial_and_parallel_rules(
    population: int,
) -> None:
    serial_runtime = _runtime(population)
    parallel_runtime = _runtime(population)
    cadence = serial_runtime.build_population_cadence(window_start=100, window_end=7_300)
    parallel_cadence = parallel_runtime.build_population_cadence(window_start=100, window_end=7_300)
    serial = serial_runtime.build_population_projections(cadence, workers=1)
    parallel = parallel_runtime.build_population_projections(parallel_cadence, workers=4, batch_size=3)

    def digest(rows):
        payload = [item.model_dump(mode="json") for item in rows]
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    assert digest(serial) == digest(parallel)
    assert PopulationReadSet.from_inputs(cadence, serial).read_set_digest == PopulationReadSet.from_inputs(
        parallel_cadence, parallel
    ).read_set_digest


def test_full_day_and_phase_sized_windows_integrate_to_the_same_objective_state() -> None:
    full = _runtime()
    split = _runtime()
    full.confirm_population_cadence(
        full.build_population_cadence(window_start=0, window_end=86_400)
    )
    for start in range(0, 86_400, 21_600):
        split.confirm_population_cadence(
            split.build_population_cadence(window_start=start, window_end=start + 21_600)
        )

    for actor_id in full.roster.actor_ids:
        full_row = dict(full.population_hot_state.read(actor_id))
        split_row = dict(split.population_hot_state.read(actor_id))
        full_row.pop("revision")
        split_row.pop("revision")
        assert full_row == split_row


def test_confirmation_rejects_a_gap_after_the_first_confirmed_cursor() -> None:
    runtime = _runtime()
    runtime.confirm_population_cadence(
        runtime.build_population_cadence(window_start=0, window_end=3_600)
    )
    skipped = runtime.build_population_cadence(window_start=7_200, window_end=10_800)

    with pytest.raises(ValueError, match="population_cadence_confirmation_conflict"):
        runtime.confirm_population_cadence(skipped)


def test_confirmation_is_atomic_when_one_preview_revision_becomes_stale() -> None:
    runtime = _runtime()
    cadence = runtime.build_population_cadence(window_start=0, window_end=3_600)
    runtime.build_population_projections(cadence)
    runtime.population_hot_state.upsert("char_a", {"fatigue": 0.3}, 1)

    with pytest.raises(ValueError, match="hot_state_revision_conflict"):
        runtime.confirm_population_cadence(cadence)

    assert runtime.population_hot_state.read("char_a")["revision"] == 1
    assert runtime.population_hot_state.read("char_b")["revision"] == 0
    assert runtime.population_hot_state.read("char_b")["last_update_tick"] == 0


def test_historical_cadence_replays_after_the_world_stream_advances() -> None:
    source = _runtime()
    cadence = source.build_population_cadence(window_start=0, window_end=3_600)
    source.confirm_population_cadence(cadence)
    source.pause(reason="test")
    source.resume()

    restored = WorldContinuityRuntime(store=source.store, mode=source.mode, roster=source.roster)
    receipt = restored.confirm_population_cadence(cadence)

    assert receipt.status == "committed"
    assert all(
        restored.population_hot_state.read(actor_id)["last_update_tick"] == 3_600
        for actor_id in restored.roster.actor_ids
    )


def test_unclaimed_threshold_work_is_deduplicated_across_thirty_daily_windows() -> None:
    runtime = _runtime()
    for day in range(30):
        start = day * 86_400
        cadence = runtime.build_population_cadence(
            window_start=start,
            window_end=start + 86_400,
        )
        receipt = runtime.confirm_population_cadence(cadence)
        assert receipt.advanced_count == len(runtime.roster.actor_ids)
        assert receipt.due_backlog_count == 0
        assert receipt.deferred_count == 0

    assert runtime.due_population_work(30 * 86_400) == ()
