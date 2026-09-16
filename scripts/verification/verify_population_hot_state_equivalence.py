from __future__ import annotations

from dataclasses import asdict, is_dataclass
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.gameplay.event_store import GameplayEventStore
from app.population_continuity.continuous import B0ContinuousResult, advance_b0_row
from app.population_continuity.models import WorldModeProfile
from app.population_continuity.roster import PopulationRoster
from app.population_continuity.siming_contracts import (
    PopulationCadenceInput,
    PopulationProjection,
    PopulationReadSet,
)
from app.population_continuity.world import WorldContinuityRuntime
from app.services.siming_population_capability import PopulationSimulationCapability
from scripts.verification.population_benchmark_metrics import percentile, peak_rss_bytes


WINDOW_END = 86_400


def root() -> Path:
    return ROOT


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def digest(value: object) -> str:
    encoded = json.dumps(
        _jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _actor_ids(population: int) -> tuple[str, ...]:
    if population < 1:
        raise ValueError("population_must_be_positive")
    return tuple(f"resident-{index:05d}" for index in range(population))


def _runtime(actor_ids: tuple[str, ...]) -> tuple[WorldContinuityRuntime, PopulationCadenceInput]:
    runtime = WorldContinuityRuntime(
        store=GameplayEventStore(),
        mode=WorldModeProfile(
            world_ref="hot-equivalence",
            mode="simulation",
            revision="mode:hot-equivalence:v1",
            cadence_class="daily",
            batch_limit=8,
            wake_budget=8,
            catch_up_limit=4,
            degraded_threshold=20,
        ),
        roster=PopulationRoster(actor_ids=actor_ids),
    )
    runtime.resume()
    cadence = runtime.build_population_cadence(
        window_start=0,
        window_end=WINDOW_END,
        cadence_id="cadence:hot-equivalence:0",
    )
    return runtime, cadence


def _initial_row() -> dict[str, object]:
    return {
        "last_update_tick": 0,
        "activity_phase": "rest",
        "fatigue": 0.2,
        "need_pressure": 0.1,
        "next_due_tick": 21_600,
        "starvation_credit": 0.0,
        "revision": 0,
    }


def _projection(
    cadence: PopulationCadenceInput, result: B0ContinuousResult
) -> PopulationProjection:
    actor_ref = f"character:{result.actor_id}"
    return PopulationProjection(
        ref=f"projection:{result.actor_id}:{cadence.window_start}",
        scope="public",
        revision_vector=dict(cadence.base_revision_vector),
        payload={
            "actor_ref": actor_ref,
            "candidate_kind": "routine_work",
            "behavior_kind": "routine_work",
            "fidelity_tier": "B0",
            "from_tick": result.from_tick,
            "to_tick": result.to_tick,
            "simulation_tick_cursor": result.to_tick,
            "actor_revision": result.actor_revision_before,
            "source_revision_vector": dict(cadence.base_revision_vector),
            "starvation_credit": result.values["starvation_credit"],
            "state_deltas": dict(result.values),
            "presentation_seed": {
                "task": "daily_routine",
                "activity_phase": result.values["activity_phase"],
                "threshold_refs": tuple(
                    f"b0:presentation-threshold:{tick}" for tick in result.due_ticks
                ),
            },
            "due_obligation_refs": (),
            "scope": "public",
            "idempotency_key": f"b0:{cadence.cadence_id}:{actor_ref}",
        },
    )


def _baseline(
    actor_ids: tuple[str, ...], cadence: PopulationCadenceInput
) -> tuple[tuple[B0ContinuousResult, ...], tuple[PopulationProjection, ...]]:
    # 基线保留普通字典布局，只与生产热表共享同一个纯积分规则。
    rows = {actor_id: _initial_row() for actor_id in actor_ids}
    results = tuple(
        advance_b0_row(
            actor_id=actor_id,
            row=rows[actor_id],
            window_start=cadence.window_start,
            window_end=cadence.window_end,
        )
        for actor_id in actor_ids
    )
    return results, tuple(_projection(cadence, result) for result in results)


def _projection_hash(projections: Iterable[PopulationProjection]) -> str:
    return digest(
        tuple(
            projection.model_dump(mode="json")
            for projection in sorted(projections, key=lambda item: item.ref)
        )
    )


def _capability_surface(
    cadence: PopulationCadenceInput, read_set: PopulationReadSet
) -> tuple[dict[str, object], int, int]:
    capability = PopulationSimulationCapability()
    cycle = capability.run_default_decision_cycle(cadence, read_set)
    decision = cycle.decision
    stats = capability.last_b0_stats
    surface = {
        "status": cycle.status,
        "b0_results": cycle.b0_results,
        "selected_candidates": decision.selected_candidates if decision else (),
        "deferred_candidates": decision.deferred_candidates if decision else (),
        "owner_bound_intents": cycle.report.owner_bound_intents,
        "owner_receipts": cycle.owner_receipts,
        "continuity_receipts": cycle.continuity_receipts,
        "cognition_stats": cycle.cognition_stats,
    }
    return (
        surface,
        len(cycle.report.owner_bound_intents),
        stats.due_count if stats is not None else -1,
    )


def _export_hot(runtime: WorldContinuityRuntime) -> tuple[tuple[str, dict[str, object]], ...]:
    return tuple(
        (actor_id, dict(row))
        for actor_id, row in runtime.population_hot_state.export_rows()
    )


def _baseline_final_rows(
    results: tuple[B0ContinuousResult, ...],
) -> tuple[tuple[str, dict[str, object]], ...]:
    return tuple(
        (
            result.actor_id,
            {**dict(result.values), "revision": result.actor_revision_before + 1},
        )
        for result in sorted(results, key=lambda item: item.actor_id)
    )


def _timings(
    actor_ids: tuple[str, ...], cadence: PopulationCadenceInput, repeats: int
) -> dict[str, float]:
    if repeats < 1:
        raise ValueError("repeats_must_be_positive")
    baseline_ms: list[float] = []
    serial_ms: list[float] = []
    parallel_ms: list[float] = []
    for _ in range(repeats):
        started = perf_counter()
        _baseline(actor_ids, cadence)
        baseline_ms.append((perf_counter() - started) * 1000)

        serial_runtime, serial_cadence = _runtime(actor_ids)
        started = perf_counter()
        serial_runtime.build_population_projections(serial_cadence, workers=1)
        serial_ms.append((perf_counter() - started) * 1000)

        parallel_runtime, parallel_cadence = _runtime(actor_ids)
        started = perf_counter()
        parallel_runtime.build_population_projections(
            parallel_cadence, workers=4, batch_size=256
        )
        parallel_ms.append((perf_counter() - started) * 1000)

    return {
        "baseline_p50_ms": round(percentile(baseline_ms, 0.5), 4),
        "baseline_p95_ms": round(percentile(baseline_ms), 4),
        "serial_p50_ms": round(percentile(serial_ms, 0.5), 4),
        "serial_p95_ms": round(percentile(serial_ms), 4),
        "parallel_p50_ms": round(percentile(parallel_ms, 0.5), 4),
        "parallel_p95_ms": round(percentile(parallel_ms), 4),
    }


def measure(population: int, repeats: int = 3) -> dict[str, object]:
    actor_ids = _actor_ids(population)
    serial_runtime, cadence = _runtime(actor_ids)
    parallel_runtime, parallel_cadence = _runtime(actor_ids)
    if cadence != parallel_cadence:
        raise AssertionError("equivalence_cadence_mismatch")

    baseline_results, baseline_projections = _baseline(actor_ids, cadence)
    serial_projections = serial_runtime.build_population_projections(cadence, workers=1)
    parallel_projections = parallel_runtime.build_population_projections(
        parallel_cadence, workers=4, batch_size=256
    )

    baseline_read_set = PopulationReadSet.from_inputs(cadence, baseline_projections)
    serial_read_set = PopulationReadSet.from_inputs(cadence, serial_projections)
    parallel_read_set = PopulationReadSet.from_inputs(cadence, parallel_projections)
    baseline_surface, baseline_owner_inputs, baseline_due_count = _capability_surface(
        cadence, baseline_read_set
    )
    serial_surface, serial_owner_inputs, serial_due_count = _capability_surface(
        cadence, serial_read_set
    )
    parallel_surface, parallel_owner_inputs, parallel_due_count = _capability_surface(
        cadence, parallel_read_set
    )

    serial_confirmation = serial_runtime.confirm_population_cadence(cadence)
    parallel_confirmation = parallel_runtime.confirm_population_cadence(parallel_cadence)
    replay_runtime = WorldContinuityRuntime(
        store=serial_runtime.store,
        mode=serial_runtime.mode,
        roster=serial_runtime.roster,
    )
    replay_confirmation = replay_runtime.confirm_population_cadence(cadence)

    baseline_projection_hash = _projection_hash(baseline_projections)
    serial_projection_hash = _projection_hash(serial_projections)
    parallel_projection_hash = _projection_hash(parallel_projections)
    baseline_capability_hash = digest(baseline_surface)
    serial_capability_hash = digest(serial_surface)
    parallel_capability_hash = digest(parallel_surface)
    baseline_candidate_hash = digest(baseline_surface["selected_candidates"])
    serial_candidate_hash = digest(serial_surface["selected_candidates"])
    parallel_candidate_hash = digest(parallel_surface["selected_candidates"])
    baseline_deferred_hash = digest(baseline_surface["deferred_candidates"])
    serial_deferred_hash = digest(serial_surface["deferred_candidates"])
    parallel_deferred_hash = digest(parallel_surface["deferred_candidates"])
    baseline_receipt_input_hash = digest(baseline_surface["owner_bound_intents"])
    serial_receipt_input_hash = digest(serial_surface["owner_bound_intents"])
    parallel_receipt_input_hash = digest(parallel_surface["owner_bound_intents"])
    baseline_final_hot_hash = digest(_baseline_final_rows(baseline_results))
    serial_final_hot_hash = digest(_export_hot(serial_runtime))
    parallel_final_hot_hash = digest(_export_hot(parallel_runtime))
    replay_final_hot_hash = digest(_export_hot(replay_runtime))
    equalities = (
        baseline_projection_hash == serial_projection_hash == parallel_projection_hash,
        baseline_read_set.read_set_digest
        == serial_read_set.read_set_digest
        == parallel_read_set.read_set_digest,
        baseline_capability_hash == serial_capability_hash == parallel_capability_hash,
        baseline_candidate_hash == serial_candidate_hash == parallel_candidate_hash,
        baseline_deferred_hash == serial_deferred_hash == parallel_deferred_hash,
        baseline_receipt_input_hash
        == serial_receipt_input_hash
        == parallel_receipt_input_hash,
        baseline_final_hot_hash
        == serial_final_hot_hash
        == parallel_final_hot_hash
        == replay_final_hot_hash,
        serial_confirmation.result_digest == parallel_confirmation.result_digest,
        serial_confirmation.result_digest == replay_confirmation.result_digest,
        baseline_owner_inputs == serial_owner_inputs == parallel_owner_inputs == 0,
        baseline_due_count == serial_due_count == parallel_due_count == 0,
    )

    return {
        "population": population,
        "window_seconds": WINDOW_END,
        "baseline_projection_hash": baseline_projection_hash,
        "serial_projection_hash": serial_projection_hash,
        "parallel_projection_hash": parallel_projection_hash,
        "baseline_read_set_digest": baseline_read_set.read_set_digest,
        "serial_read_set_digest": serial_read_set.read_set_digest,
        "parallel_read_set_digest": parallel_read_set.read_set_digest,
        "baseline_capability_hash": baseline_capability_hash,
        "serial_capability_hash": serial_capability_hash,
        "parallel_capability_hash": parallel_capability_hash,
        "baseline_candidate_hash": baseline_candidate_hash,
        "serial_candidate_hash": serial_candidate_hash,
        "parallel_candidate_hash": parallel_candidate_hash,
        "baseline_deferred_hash": baseline_deferred_hash,
        "serial_deferred_hash": serial_deferred_hash,
        "parallel_deferred_hash": parallel_deferred_hash,
        "baseline_owner_receipt_input_hash": baseline_receipt_input_hash,
        "serial_owner_receipt_input_hash": serial_receipt_input_hash,
        "parallel_owner_receipt_input_hash": parallel_receipt_input_hash,
        "baseline_final_hot_hash": baseline_final_hot_hash,
        "serial_final_hot_hash": serial_final_hot_hash,
        "parallel_final_hot_hash": parallel_final_hot_hash,
        "replay_final_hot_hash": replay_final_hot_hash,
        "candidate_input_hash": digest(serial_read_set.projections),
        "owner_receipt_input_count": serial_owner_inputs,
        "capability_due_count": serial_due_count,
        "confirmation": asdict(serial_confirmation),
        "parallel_confirmation": asdict(parallel_confirmation),
        "replay_confirmation": asdict(replay_confirmation),
        "baseline_serialized_bytes": len(
            json.dumps(_jsonable(baseline_projections), sort_keys=True).encode("utf-8")
        ),
        "hot_state_serialized_bytes": len(
            json.dumps(_jsonable(_export_hot(serial_runtime)), sort_keys=True).encode("utf-8")
        ),
        "peak_rss_bytes": peak_rss_bytes(),
        **_timings(actor_ids, cadence, repeats),
        "performance_claim": "equivalence_only",
        "equivalent": all(equalities),
    }


def main() -> int:
    scenarios = [measure(population) for population in (54, 100, 1_000, 10_000)]
    report = {
        "stage": 4,
        "python": platform.python_version(),
        "git_head": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root(),
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip(),
        "scenarios": scenarios,
        "overall_passed": all(item["equivalent"] for item in scenarios),
        "performance_claim": "equivalence_only_no_soa_or_vectorization_claim",
        "implementation_status": "written_and_backend_verified",
        "godot_status": "godot_unverified",
    }
    directory = root() / ".harness" / "verification"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "population-hot-state-equivalence-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"overall_population_hot_state_equivalence_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
