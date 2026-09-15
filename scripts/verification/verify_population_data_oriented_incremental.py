from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from statistics import median
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import ProjectionCheckpoint
from app.population_continuity.siming_contracts import PopulationCadenceInput
from app.population_continuity.store_projection_assembler import assemble_committed_population_projections


def root() -> Path:
    return Path(__file__).resolve().parents[2]


def _digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _append_social_event(store: GameplayEventStore, index: int) -> None:
    stream_id = f"gameplay:social:population:{index}"
    event_id = f"evt:population:signal:{index}"
    tx = f"tx:population:signal:{index}"
    command_id = f"cmd:population:signal:{index}"
    store.append_batch(
        {
            "transaction_id": tx,
            "command_id": command_id,
            "expected_stream_revisions": {stream_id: 0},
            "pinned_revisions": {"policy": 1},
            "events": [
                {
                    "event_id": event_id,
                    "event_type": "gameplay.social.population_signal_recorded@1",
                    "schema_version": 1,
                    "stream_id": stream_id,
                    "stream_revision": 0,
                    "global_sequence": 0,
                    "transaction_id": tx,
                    "command_id": command_id,
                    "causation_id": command_id,
                    "correlation_id": tx,
                    "visibility_policy": "public",
                    "payload": {
                        "committed": True,
                        "signal_id": f"signal:population:{index}",
                        "source_event_id": event_id,
                        "source_domain": "social",
                        "visibility_scope": "public",
                        "materialization_state": "proposed",
                    },
                }
            ],
            "idempotency_record": {
                "principal_ref": "verification",
                "idempotency_key": f"population:signal:{index}",
                "payload_digest": _digest(event_id),
            },
            "outbox_entries": [],
            "result_digest": _digest(tx),
            "projection_refresh_hints": [],
        }
    )


def _fixture(history: int) -> tuple[GameplayEventStore, PopulationCadenceInput]:
    store = GameplayEventStore()
    for index in range(history):
        _append_social_event(store, index)
    heads = store.get_stream_heads()
    cadence = PopulationCadenceInput(
        cadence_id=f"cadence:verification:{history}",
        world_ref="world:verification",
        world_mode_ref="mode:verification",
        world_mode_revision="mode:1",
        cadence_source_ref="world:verification",
        cadence_source_revision=history,
        window_start=0,
        window_end=1,
        base_checkpoint_ref=f"checkpoint:verification:{history}",
        base_checkpoint_digest=_digest(heads),
        base_revision_vector=heads,
        policy_revision="policy:population:v1",
        selector_revision="selector:population:v1",
        ruleset_revision="rules:population:v1",
        deterministic_seed=f"seed:verification:{history}",
        catch_up_limit=history,
        budget=history,
        report_scope="public",
    )
    return store, cadence


def _run_assembler(
    store: GameplayEventStore,
    cadence: PopulationCadenceInput,
    checkpoint: ProjectionCheckpoint | None = None,
) -> tuple[tuple[object, ...], dict[str, int], float]:
    counts = {"read_calls": 0, "events_returned": 0}
    original = store.read_events

    def counted_read_events(**kwargs: object):
        counts["read_calls"] += 1
        events = original(**kwargs)
        counts["events_returned"] += len(events)
        return events

    store.read_events = counted_read_events  # type: ignore[method-assign]
    started = perf_counter()
    try:
        projections = assemble_committed_population_projections(
            store=store,
            cadence=cadence,
            organization_projection={},
            checkpoint=checkpoint,
        )
    finally:
        store.read_events = original  # type: ignore[method-assign]
    elapsed_ms = (perf_counter() - started) * 1000
    return projections, counts, elapsed_ms


def _measure(population: int, history: int) -> dict[str, object]:
    store, cadence = _fixture(history)
    full, full_counts, full_ms = _run_assembler(store, cadence)
    midpoint = history // 2
    checkpoint_projections = [
        projection.model_dump(mode="json")
        for projection in full
        if int(str(projection.payload["source_event_refs"][0]).rsplit(":", 1)[-1]) < midpoint
    ]
    checkpoint = ProjectionCheckpoint(
        checkpoint_id=f"checkpoint:verification:{history}",
        projector_id="population-continuity",
        projector_version="1",
        projection_schema_version=1,
        source_revision_vector={},
        last_global_sequence=midpoint,
        state={"population_projections": checkpoint_projections},
        projection_hash=_digest(checkpoint_projections),
    )
    tail, tail_counts, tail_ms = _run_assembler(store, cadence, checkpoint)
    full_hash = _digest([projection.model_dump(mode="json") for projection in full])
    tail_hash = _digest([projection.model_dump(mode="json") for projection in tail])
    return {
        "population": population,
        "history": history,
        "full_projection_count": len(full),
        "tail_projection_count": len(tail),
        "full_hash": full_hash,
        "tail_hash": tail_hash,
        "replay_equivalent": full_hash == tail_hash,
        "full": {"ms": round(full_ms, 4), **full_counts},
        "tail": {"ms": round(tail_ms, 4), **tail_counts},
    }


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * percentile))]


def main() -> int:
    scenarios: list[dict[str, object]] = []
    for population in (54, 100, 1000, 10000):
        for history in (max(32, population // 4), population):
            samples = [_measure(population, history) for _ in range(5)]
            full_ms = [float(sample["full"]["ms"]) for sample in samples]  # type: ignore[index]
            tail_ms = [float(sample["tail"]["ms"]) for sample in samples]  # type: ignore[index]
            scenarios.append(
                {
                    "population": population,
                    "history": history,
                    "samples": samples,
                    "p50_ms": {"full": round(median(full_ms), 4), "tail": round(median(tail_ms), 4)},
                    "p95_ms": {"full": round(_percentile(full_ms, 0.95), 4), "tail": round(_percentile(tail_ms, 0.95), 4)},
                }
            )
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "backend/tests/test_population_incremental_benchmark.py",
        "backend/tests/test_population_parallel_determinism.py",
    ]
    result = subprocess.run(command, cwd=root(), capture_output=True, text=True, check=False)
    equivalent = all(sample["replay_equivalent"] for scenario in scenarios for sample in scenario["samples"])
    report = {
        "overall_passed": result.returncode == 0 and equivalent,
        "implementation_status": "written_and_backend_verified" if result.returncode == 0 and equivalent else "backend_verification_failed",
        "godot_status": "godot_unverified",
        "python": platform.python_version(),
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=root(), capture_output=True, text=True, check=False).stdout.strip(),
        "scenarios": scenarios,
        "test_command": command,
        "test_output": result.stdout + result.stderr,
    }
    directory = root() / ".harness" / "verification"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "population-data-oriented-incremental-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"overall_population_data_oriented_incremental_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
