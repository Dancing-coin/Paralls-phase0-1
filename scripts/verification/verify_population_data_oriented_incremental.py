from __future__ import annotations

try:
    from .common import verification_dir
except ImportError:
    from common import verification_dir

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.settlement_plan import (
    build_atomic_event_batch,
    build_multi_stream_atomic_event_batch,
)
from app.population_continuity.publication import publish_authorized_population_cadence
from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationProjection
from app.population_continuity.store_projection_assembler import assemble_committed_population_projections
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_pipeline import SimingEventPipeline
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_population_capability import PopulationSimulationCapability
from app.services.siming_runtime import SimingRuntime
from scripts.verification.population_benchmark_metrics import peak_rss_bytes, percentile


WORLD_REF = "benchmark"
WORLD_STREAM = f"world:{WORLD_REF}"
WORLD_MODE_REVISION = "mode:benchmark:v1"
PUBLIC_STREAM_A = "gameplay:social:population:public:a"
PUBLIC_STREAM_B = "gameplay:social:population:public:b"
PRIVATE_STREAM = "gameplay:social:population:private"
SOCIAL_STREAMS = (PUBLIC_STREAM_A, PUBLIC_STREAM_B, PRIVATE_STREAM)


def root() -> Path:
    return ROOT


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _encoded_bytes(value: object) -> int:
    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _append_world_source(store: GameplayEventStore) -> None:
    store.append_batch(
        build_atomic_event_batch(
            command_id="benchmark-world-resume",
            principal_ref="verification",
            stream_id=WORLD_STREAM,
            expected_revision=0,
            event_specs=((
                "population.world.resume",
                {
                    "committed": True,
                    "world_ref": WORLD_REF,
                    "mode_revision": WORLD_MODE_REVISION,
                    "visibility_scope": "project",
                },
            ),),
            idempotency_key="benchmark-world-resume",
            causation_id="benchmark-world-resume",
            correlation_id="benchmark-world-resume",
        )
    )


def _social_event_spec(index: int, stream_id: str, visibility: str) -> tuple[str, dict[str, object]]:
    return (
        "gameplay.social.population_signal_recorded@1",
        {
            "committed": True,
            "signal_ref": f"signal:benchmark:{index:08d}",
            "provenance_ref": f"provenance:benchmark:{index:08d}",
            "source_domain": "social",
            "source_stream_ref": stream_id,
            "visibility_scope": visibility,
            "materialization_state": "proposed",
        },
    )


def _append_history(
    store: GameplayEventStore,
    *,
    start: int,
    count: int,
    batch_ref: str,
) -> None:
    for offset in range(0, count, 1_000):
        size = min(1_000, count - offset)
        specs: dict[str, list[tuple[str, dict[str, object]]]] = {
            stream_id: [] for stream_id in SOCIAL_STREAMS
        }
        visibilities: dict[str, list[str]] = {stream_id: [] for stream_id in SOCIAL_STREAMS}
        for index in range(start + offset, start + offset + size):
            if index % 10 == 0:
                stream_id, visibility = PRIVATE_STREAM, "actor:self"
            elif index % 2 == 0:
                stream_id, visibility = PUBLIC_STREAM_A, "public"
            else:
                stream_id, visibility = PUBLIC_STREAM_B, "public"
            specs[stream_id].append(_social_event_spec(index, stream_id, visibility))
            visibilities[stream_id].append(visibility)
        specs = {stream_id: events for stream_id, events in specs.items() if events}
        visibilities = {
            stream_id: values
            for stream_id, values in visibilities.items()
            if stream_id in specs
        }
        command_id = f"benchmark-history:{batch_ref}:{offset}"
        store.append_batch(
            build_multi_stream_atomic_event_batch(
                command_id=command_id,
                principal_ref="verification",
                expected_revisions={
                    stream_id: store.get_stream_head(stream_id) for stream_id in specs
                },
                event_specs=specs,
                event_visibility_policies=visibilities,
                idempotency_key=command_id,
                causation_id=command_id,
                correlation_id=command_id,
            )
        )


def _cadence(store: GameplayEventStore, *, sample: int, population: int) -> PopulationCadenceInput:
    heads = store.get_stream_heads()
    return PopulationCadenceInput(
        cadence_id=f"cadence:benchmark:{population}:{sample}",
        world_ref=WORLD_REF,
        world_mode_ref="mode:benchmark",
        world_mode_revision=WORLD_MODE_REVISION,
        cadence_source_ref=WORLD_STREAM,
        cadence_source_revision=1,
        window_start=sample,
        window_end=sample + 1,
        base_checkpoint_ref=f"checkpoint:benchmark:{sample}",
        base_checkpoint_digest=_digest(heads),
        base_revision_vector=heads,
        policy_revision="policy:population:v1",
        selector_revision="selector:generic:population:v1",
        ruleset_revision="rules:population:v1",
        deterministic_seed=f"seed:benchmark:{sample}",
        catch_up_limit=population,
        budget=population,
        report_scope="public",
    )


def _population_projections(population: int) -> tuple[PopulationProjection, ...]:
    return tuple(
        PopulationProjection(
            ref=f"projection:benchmark:resident:{index:05d}",
            scope="public",
            revision_vector={WORLD_STREAM: 1},
            payload={
                "actor_ref": f"character:benchmark:{index:05d}",
                "candidate_kind": "routine_work",
                "behavior_kind": "routine_work",
                "fidelity_tier": "B0",
                "budget_cost": 0,
                "fallback": "no-op",
                "state_deltas": {"energy": -1, "location_tick": index % 16},
                "presentation_seed": {"activity": "routine_work", "variant": index % 8},
            },
        )
        for index in range(population)
    )


def _pipeline() -> tuple[InMemoryAuthorityEventBus, SimingAuditWriter]:
    bus = InMemoryAuthorityEventBus()
    audit = SimingAuditWriter()
    pipeline = SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=SimingRuntime(population_capability=PopulationSimulationCapability()),
        producer=SimingEventProducer(bus),
        audit_writer=audit,
    )
    bus.subscribe(
        "population_cadence_event",
        pipeline.handle_event,
        consumer_id="benchmark-siming-runtime",
    )
    return bus, audit


def _publish(
    *,
    cadence: PopulationCadenceInput,
    store: GameplayEventStore,
    bus: InMemoryAuthorityEventBus,
    population_projections: tuple[PopulationProjection, ...],
):
    return publish_authorized_population_cadence(
        cadence=cadence,
        store=store,
        organization_projection={"scope": "public"},
        room_id="room:benchmark",
        scene_id="scene:benchmark",
        zone_id="zone:benchmark",
        causation_id=f"cause:{cadence.cadence_id}",
        correlation_id=f"correlation:{cadence.cadence_id}",
        population_projections=population_projections,
        event_bus=bus,
    )


def _publish_with_read_metrics(
    *,
    cadence: PopulationCadenceInput,
    store: GameplayEventStore,
    bus: InMemoryAuthorityEventBus,
    population_projections: tuple[PopulationProjection, ...],
) -> tuple[object | None, dict[str, int], float]:
    metrics = {
        "read_events_calls": 0,
        "read_events_returned": 0,
        "read_events_encoded_bytes": 0,
        "read_stream_calls": 0,
        "read_stream_returned": 0,
        "read_stream_encoded_bytes": 0,
    }
    original_read_events = store.read_events
    original_read_stream = store.read_stream

    def counted_read_events(**kwargs: object):
        events = original_read_events(**kwargs)
        metrics["read_events_calls"] += 1
        metrics["read_events_returned"] += len(events)
        metrics["read_events_encoded_bytes"] += _encoded_bytes(
            [event.model_dump(mode="json") for event in events]
        )
        return events

    def counted_read_stream(stream_id: str, **kwargs: object):
        events = original_read_stream(stream_id, **kwargs)
        metrics["read_stream_calls"] += 1
        metrics["read_stream_returned"] += len(events)
        metrics["read_stream_encoded_bytes"] += _encoded_bytes(
            [event.model_dump(mode="json") for event in events]
        )
        return events

    store.read_events = counted_read_events  # type: ignore[method-assign]
    store.read_stream = counted_read_stream  # type: ignore[method-assign]
    started = perf_counter()
    try:
        event = _publish(
            cadence=cadence,
            store=store,
            bus=bus,
            population_projections=population_projections,
        )
    finally:
        elapsed_ms = (perf_counter() - started) * 1_000
        store.read_events = original_read_events  # type: ignore[method-assign]
        store.read_stream = original_read_stream  # type: ignore[method-assign]
    return event, metrics, elapsed_ms


def _projection_payload(event: object) -> list[dict[str, Any]]:
    payload = getattr(event, "payload", {})
    rows = payload.get("population_projections", []) if isinstance(payload, dict) else []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _checkpoint_id() -> str:
    context = {
        "world_ref": WORLD_REF,
        "world_mode_revision": WORLD_MODE_REVISION,
        "report_scope": "public",
        "policy_revision": "policy:population:v1",
        "selector_revision": "selector:generic:population:v1",
        "ruleset_revision": "rules:population:v1",
        "organization_ref": None,
    }
    return "checkpoint:population:" + _digest(context).split(":", 1)[1]


def measure_incremental_history(
    *,
    history: int,
    population: int = 100,
    tail: int = 10,
    samples: int = 5,
) -> dict[str, object]:
    if history < 1 or population < 1 or tail < 1 or samples < 1:
        raise ValueError("benchmark_dimensions_invalid")
    store = GameplayEventStore()
    _append_world_source(store)
    if history > 1:
        _append_history(
            store,
            start=1,
            count=history - 1,
            batch_ref=f"prefix:{history}",
        )
    bus, _audit = _pipeline()
    population_projections = _population_projections(population)
    prefix_cadence = _cadence(store, sample=0, population=population)
    prefix_started = perf_counter()
    prefix_event = _publish(
        cadence=prefix_cadence,
        store=store,
        bus=bus,
        population_projections=population_projections,
    )
    prefix_ms = (perf_counter() - prefix_started) * 1_000
    checkpoint = store.get_projection_checkpoint(_checkpoint_id())

    sample_rows: list[dict[str, object]] = []
    final_event = prefix_event
    next_event_index = history
    for sample in range(1, samples + 1):
        _append_history(
            store,
            start=next_event_index,
            count=tail,
            batch_ref=f"tail:{history}:{sample}",
        )
        next_event_index += tail
        cadence = _cadence(store, sample=sample, population=population)
        event, metrics, elapsed_ms = _publish_with_read_metrics(
            cadence=cadence,
            store=store,
            bus=bus,
            population_projections=population_projections,
        )
        final_event = event
        sample_rows.append(
            {
                "sample": sample,
                "published": event is not None,
                "elapsed_ms": round(elapsed_ms, 4),
                **metrics,
            }
        )

    final_cadence = _cadence(store, sample=samples, population=population)
    assembled = assemble_committed_population_projections(
        store=store,
        cadence=final_cadence,
        organization_projection={"scope": "public"},
    )
    oracle_rows = [
        projection.model_dump(mode="json")
        for projection in sorted((*population_projections, *assembled), key=lambda item: item.ref)
    ]
    output_rows = _projection_payload(final_event) if final_event is not None else []
    input_events = store.read_events()
    input_rows = [event.model_dump(mode="json") for event in input_events]
    social_events = [event for event in input_events if event.stream_id in SOCIAL_STREAMS]
    source_streams = {event.stream_id for event in social_events}
    elapsed = [float(row["elapsed_ms"]) for row in sample_rows]
    output_hash = _digest(output_rows)
    full_oracle_hash = _digest(oracle_rows)
    reads_are_incremental = all(
        row["read_events_calls"] == 1
        and row["read_events_returned"] == tail
        and row["read_stream_calls"] == 1
        and row["read_stream_returned"] == 1
        for row in sample_rows
    )
    prefix_sequence = checkpoint.last_global_sequence if checkpoint is not None else -1
    replay_equivalent = output_hash == full_oracle_hash
    return {
        "population": population,
        "history": history,
        "tail": tail,
        "sample_count": samples,
        "prefix_checkpoint_sequence": prefix_sequence,
        "prefix_elapsed_ms": round(prefix_ms, 4),
        "full_oracle_event_count": store.get_last_global_sequence(),
        "full_oracle_projection_count": len(oracle_rows),
        "source_stream_count": len(source_streams),
        "private_event_count": sum(
            event.visibility_policy == "actor:self" for event in social_events
        ),
        "same_stream_update_count": len(social_events) - len(source_streams),
        "input_encoded_bytes": _encoded_bytes(input_rows),
        "output_encoded_bytes": _encoded_bytes(output_rows),
        "input_hash": _digest(input_rows),
        "output_hash": output_hash,
        "full_oracle_hash": full_oracle_hash,
        "replay_equivalent": replay_equivalent,
        "p50_ms": round(percentile(elapsed, 0.50), 4),
        "p95_ms": round(percentile(elapsed, 0.95), 4),
        "peak_rss_bytes": peak_rss_bytes(),
        "samples": sample_rows,
        "overall_passed": (
            prefix_event is not None
            and prefix_sequence == history
            and reads_are_incremental
            and replay_equivalent
        ),
    }


def measure_projection_scale(*, population: int, samples: int = 5) -> dict[str, object]:
    if population < 1 or samples < 1:
        raise ValueError("benchmark_dimensions_invalid")
    store = GameplayEventStore()
    _append_world_source(store)
    bus, audit = _pipeline()
    projections = _population_projections(population)
    sample_rows: list[dict[str, object]] = []
    final_event = None
    audit_count = 0
    for sample in range(samples):
        cadence = _cadence(store, sample=sample, population=population)
        correlation_id = f"correlation:{cadence.cadence_id}"
        started = perf_counter()
        final_event = _publish(
            cadence=cadence,
            store=store,
            bus=bus,
            population_projections=projections,
        )
        elapsed_ms = (perf_counter() - started) * 1_000
        records = audit.find_by_correlation(
            room_id="room:benchmark",
            correlation_id=correlation_id,
        )
        cycle_audits = [record for record in records if record.reason.startswith("population_")]
        audit_count += len(cycle_audits)
        sample_rows.append(
            {
                "sample": sample + 1,
                "published": final_event is not None,
                "elapsed_ms": round(elapsed_ms, 4),
                "population_cycle_audits": len(cycle_audits),
            }
        )
    input_rows = [projection.model_dump(mode="json") for projection in projections]
    output_rows = _projection_payload(final_event) if final_event is not None else []
    elapsed = [float(row["elapsed_ms"]) for row in sample_rows]
    input_hash = _digest(input_rows)
    output_hash = _digest(output_rows)
    published_projection_count = len(output_rows)
    all_published = all(bool(row["published"]) for row in sample_rows)
    return {
        "population": population,
        "sample_count": samples,
        "published_projection_count": published_projection_count,
        "pipeline_audit_count": audit_count,
        "input_encoded_bytes": _encoded_bytes(input_rows),
        "output_encoded_bytes": _encoded_bytes(output_rows),
        "input_hash": input_hash,
        "output_hash": output_hash,
        "p50_ms": round(percentile(elapsed, 0.50), 4),
        "p95_ms": round(percentile(elapsed, 0.95), 4),
        "peak_rss_bytes": peak_rss_bytes(),
        "samples": sample_rows,
        "overall_passed": (
            all_published
            and audit_count == samples
            and published_projection_count == population
            and input_hash == output_hash
        ),
    }


def main() -> int:
    history_scenarios = [
        measure_incremental_history(history=history, population=100, tail=10)
        for history in (1_000, 10_000, 50_000)
    ]
    projection_scenarios = [
        measure_projection_scale(population=population)
        for population in (54, 100, 1_000, 10_000)
    ]
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "backend/tests/test_population_incremental_benchmark.py",
        "backend/tests/test_population_checkpoint_closure.py",
    ]
    test_result = subprocess.run(
        command,
        cwd=root(),
        capture_output=True,
        text=True,
        check=False,
    )
    scenario_passed = all(
        bool(scenario["overall_passed"])
        for scenario in (*history_scenarios, *projection_scenarios)
    )
    overall_passed = test_result.returncode == 0 and scenario_passed
    report = {
        "stage": "population_data_oriented_incremental_read",
        "overall_passed": overall_passed,
        "implementation_status": (
            "written_and_backend_verified" if overall_passed else "backend_verification_failed"
        ),
        "godot_status": "godot_unverified",
        "python": platform.python_version(),
        "git_head": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root(),
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip(),
        "history_scenarios": history_scenarios,
        "projection_scale_scenarios": projection_scenarios,
        "test_command": command,
        "test_returncode": test_result.returncode,
        "test_output": test_result.stdout + test_result.stderr,
    }
    directory = verification_dir(root())
    directory.mkdir(parents=True, exist_ok=True)
    evidence = directory / "population-data-oriented-incremental-report.json"
    evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"evidence={evidence}")
    print(f"overall_population_data_oriented_incremental_passed={overall_passed}")
    return 0 if overall_passed else 1


if __name__ == "__main__":
    from pathlib import Path
    from run_context import run_scope

    with run_scope(Path(__file__).resolve().parents[2]):
        raise SystemExit(main())
