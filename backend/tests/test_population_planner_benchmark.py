"""Population planner performance benchmarks.

Non-functional acceptance criteria:
- plan_population_cycle() completes in < 50ms for 100 projections
- Seed derivation completes in < 10ms for a single actor
- Memory overhead stays under 10MB for a typical batch
"""
import time
from app.population_continuity.batch import PopulationPlanner
from app.population_continuity.siming_contracts import (
    PopulationCadenceInput,
    PopulationProjection,
    PopulationReadSet,
)


def test_planner_performance_for_typical_batch(benchmark=None):
    """Verify plan_population_cycle scales to production batch sizes."""
    cadence = PopulationCadenceInput(
        cadence_id="cadence:benchmark:1",
        world_ref="world:bakery",
        world_mode_ref="mode:bakery",
        world_mode_revision="mode:v1",
        cadence_source_ref="world:bakery",
        cadence_source_revision=1,
        window_start=100,
        window_end=200,
        base_checkpoint_ref="checkpoint:1",
        base_checkpoint_digest="sha256:base",
        base_revision_vector={"world:bakery": 1},
        policy_revision="policy:v1",
        selector_revision="selector:v1",
        ruleset_revision="ruleset:v1",
        deterministic_seed="seed:benchmark:1",
        catch_up_limit=100,
        budget=50,
        report_scope="organization:summary",
    )

    projections = [
        PopulationProjection(
            ref=f"projection:actor_{i}:behavior",
            scope="organization:summary",
            revision_vector={"world:bakery": 1},
            payload={
                "actor_ref": f"character:actor_{i}",
                "candidate_kind": "routine_work",
                "priority": i % 10,
            },
        )
        for i in range(100)
    ]

    read_set = PopulationReadSet.from_inputs(cadence, projections)
    planner = PopulationPlanner()

    start = time.perf_counter()
    report = planner.plan_population_cycle(read_set)
    elapsed_ms = (time.perf_counter() - start) * 1000

    # Acceptance: < 50ms for 100 projections
    assert elapsed_ms < 50, f"Planning took {elapsed_ms:.1f}ms, expected < 50ms"
    assert report.budget_used <= cadence.budget
    assert len(report.selected_cohort_refs) <= cadence.catch_up_limit

    if benchmark:
        benchmark(planner.plan_population_cycle, read_set)


if __name__ == "__main__":
    # Quick smoke test without pytest-benchmark
    test_planner_performance_for_typical_batch()
    print("Benchmark passed")
