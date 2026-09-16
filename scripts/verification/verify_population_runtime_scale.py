from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from scripts.verification.population_benchmark_metrics import (
    implementation_digest,
    peak_rss_bytes,
    percentile,
)

from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.gameplay.econ1_economy_runtime import OperatingWindow
from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.models.siming_heavenly_graph import HeavenlyGraphScope, HeavenlyNodeQuery
from app.population_continuity.models import WorldModeProfile
from app.population_continuity.owner_adapters import OrganizationOperatingWindowDueOwnerExecutor
from app.population_continuity.roster import PopulationRoster
from app.population_continuity.runtime_publication import RuntimeCadencePublisher
from app.population_continuity.siming_contracts import PopulationB0BatchStats, PopulationCadenceInput, PopulationProjection, PopulationReadSet
from app.population_continuity import world as world_module
from app.population_continuity.world import WorldContinuityRuntime
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.authority_graph_projector import HeavenlyAuthorityEventProjector
from app.services.behavior_turn_recorder import BehaviorTurnRecorder
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_pipeline import SimingEventPipeline
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_population_capability import PopulationSimulationCapability
from app.services.siming_runtime import SimingRuntime
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter


POPULATION_SIZES = (100, 1000, 10000)
WINDOW_COUNT = 30
PRESSURE_PROFILES = {
    "one_x": {"wall_budget_seconds": 1.0},
    "ten_x": {"wall_budget_seconds": 0.1},
}


class _MeasuredCapability(PopulationSimulationCapability):
    def __init__(self) -> None:
        super().__init__()
        self.default_cycle_count = 0
        self.b0_cycle_verified = True

    def run_default_decision_cycle(self, cadence_input, read_set):
        self.default_cycle_count += 1
        result = super().run_default_decision_cycle(cadence_input, read_set)
        expected = tuple(
            projection for projection in read_set.projections
            if projection.payload.get("fidelity_tier") == "B0"
        )
        self.b0_cycle_verified &= len(result.b0_results) == len(expected) and all(
            item.simulation_tick_cursor == cadence_input.window_end
            for item in result.b0_results
        )
        return result


def _digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _hot_state_hash(world: WorldContinuityRuntime) -> str:
    rows = [(actor_id, dict(row)) for actor_id, row in world.population_hot_state.export_rows()]
    return _digest(rows)


def _window_identity_evidence(
    *,
    cadence: PopulationCadenceInput,
    rows: list[dict[str, Any]],
    stats: PopulationB0BatchStats | None,
    roster: PopulationRoster,
) -> dict[str, Any]:
    actor_refs = [str(row["payload"].get("actor_ref", "")) for row in rows]
    projection_refs = [str(row.get("ref", "")) for row in rows]
    revisions = [row["payload"].get("actor_revision") for row in rows]
    idempotency_keys = [str(row["payload"].get("idempotency_key", "")) for row in rows]
    expected_actor_refs = {f"character:{actor_id}" for actor_id in roster.actor_ids}
    expected_keys = {
        f"b0:{cadence.cadence_id}:character:{actor_id}" for actor_id in roster.actor_ids
    }
    expected_vector = dict(cadence.base_revision_vector)

    def sample(index: int) -> dict[str, Any]:
        row = rows[index]
        payload = row["payload"]
        return {
            "actor_ref": payload.get("actor_ref"),
            "projection_ref": row.get("ref"),
            "actor_revision": payload.get("actor_revision"),
            "idempotency_key": payload.get("idempotency_key"),
        }

    revisions_valid = all(
        isinstance(revision, int) and not isinstance(revision, bool) and revision >= 0
        for revision in revisions
    )
    actor_revision_min = min(revisions) if revisions_valid and revisions else None
    actor_revision_max = max(revisions) if revisions_valid and revisions else None
    actor_revision_consistent = (
        revisions_valid and bool(revisions) and actor_revision_min == actor_revision_max
    )
    verified = (
        len(rows) == len(roster.actor_ids)
        and len(set(actor_refs)) == len(actor_refs)
        and set(actor_refs) == expected_actor_refs
        and set(idempotency_keys) == expected_keys
        and actor_revision_consistent
        and stats is not None
        and stats.cadence_id == cadence.cadence_id
        and stats.actor_count == len(rows)
        and all(
            row.get("ref")
            == f"projection:{str(row['payload'].get('actor_ref', '')).removeprefix('character:')}:{cadence.window_start}"
            and row["payload"].get("from_tick") == cadence.window_start
            and row["payload"].get("to_tick") == cadence.window_end
            and row["payload"].get("simulation_tick_cursor") == cadence.window_end
            and row.get("revision_vector") == expected_vector
            and row["payload"].get("source_revision_vector") == expected_vector
            for row in rows
        )
    )
    return {
        "verified": verified,
        "window_start": cadence.window_start,
        "window_end": cadence.window_end,
        "cadence_id": cadence.cadence_id,
        "read_set_digest": stats.read_set_digest if stats is not None else None,
        "source_revision_vector": expected_vector,
        "actor_count": len(rows),
        "actor_revision_min": actor_revision_min,
        "actor_revision_max": actor_revision_max,
        "actor_revision_consistent": actor_revision_consistent,
        "idempotency_key_template": f"b0:{cadence.cadence_id}:character:<actor_id>",
        "idempotency_key_set_digest": _digest(sorted(idempotency_keys)),
        "actor_ref_set_digest": _digest(sorted(actor_refs)),
        "projection_ref_set_digest": _digest(sorted(projection_refs)),
        "first_sample": sample(0) if rows else None,
        "last_sample": sample(-1) if rows else None,
        "policy_revision": cadence.policy_revision,
        "selector_revision": cadence.selector_revision,
        "ruleset_revision": cadence.ruleset_revision,
    }


def _siming_scope_for_event(event) -> HeavenlyGraphScope:
    payload = event.payload if isinstance(event.payload, dict) else {}
    return HeavenlyGraphScope(
        world_id=str(payload.get("world_id", "world:demo") or "world:demo"),
        session_id=str(payload.get("session_id", "session:demo") or "session:demo"),
        story_branch_id=str(payload.get("story_branch_id", "branch:main") or "branch:main"),
    )


def _mode(population: int) -> WorldModeProfile:
    return WorldModeProfile(
        world_ref=f"world:population-scale:{population}",
        mode="simulation",
        revision="mode:population-scale:v1",
        cadence_class="one-simulation-second",
        batch_limit=max(1, min(population, 256)),
        wake_budget=max(1, min(population, 256)),
        catch_up_limit=max(1, min(population, 256)),
        degraded_threshold=max(1, population),
    )


def _roster(population: int) -> PopulationRoster:
    return PopulationRoster(actor_ids=tuple(f"scale_{index:05d}" for index in range(population)))


def empty_scenario(*, population: int, window_count: int, wall_budget_seconds: float) -> dict[str, Any]:
    return {
        "population": population,
        "window_count": window_count,
        "window_seconds": 1,
        "wall_budget_seconds": wall_budget_seconds,
        "p95_budget_seconds": wall_budget_seconds * 0.8,
        "status": "not_run",
        "error": None,
        "windows_completed": 0,
        "window_wall_ms": [],
        "p50_wall_ms": None,
        "p95_wall_ms": None,
        "pure_kernel_ms": [],
        "protocol_packaging_ms": [],
        "owner_ms": None,
        "durable_transaction_ms": [],
        "pipeline_ms": [],
        "authority_graph_ms": [],
        "recovery_ms": None,
        "protocol_bytes": 0,
        "durable_store_bytes": None,
        "authority_graph_bytes": None,
        "process_peak_rss_bytes": None,
        "backlog_windows": [],
        "backlog_non_growing": False,
        "max_lag_windows": None,
        "serial_parallel_equivalent": None,
        "published_event_count": 0,
        "retained_event_count": 0,
        "pipeline_event_count": 0,
        "capability_cycle_count": 0,
        "authority_graph_event_count": 0,
        "behavior_turn_count": 0,
        "pipeline_verified": False,
        "authority_graph_verified": False,
        "behavior_turn_verified": False,
        "b0_cursor_verified": False,
        "input_roster_digest": None,
        "window_evidence": [],
        "window_evidence_verified": False,
        "character_registration_verified": False,
        "full_profile_loaded": None,
        "persistent_gameplay_verified": False,
        "recovery_verified": False,
        "committed_hot_state_hash": None,
        "recovered_hot_state_hash": None,
        "owner_scenario_verified": False,
        "passed": False,
    }


def _sustained_growth(values: list[int]) -> bool:
    return len(values) >= 4 and all(right > left for left, right in zip(values[-4:], values[-3:]))


def _cost_summary(values: list[float]) -> dict[str, float | int | None]:
    return {
        "samples": len(values),
        "p50_ms": median(values) if values else None,
        "p95_ms": percentile(values) if values else None,
        "total_ms": sum(values),
    }


def _sqlite_bytes(path: Path) -> int:
    return sum(
        candidate.stat().st_size
        for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm"))
        if candidate.exists()
    )


def _prepare_sparse_owner_batch(
    *, store: DurableGameplayEventStore, world: WorldContinuityRuntime, suffix: str,
) -> tuple[PopulationSimulationCapability, PopulationCadenceInput, PopulationReadSet]:
    authority = OrganizationAuthority(store=store)
    windows: list[tuple[str, str]] = []
    for name in ("alpha", "beta"):
        organization_ref = f"org:scale-{suffix}-{name}"
        window_ref = f"window:scale-{suffix}-{name}"
        opened = authority.open_operating_window(
            command_id=f"command:{window_ref}:open",
            idempotency_key=f"{window_ref}:open",
            causation_id=f"cause:{window_ref}:open",
            correlation_id=f"corr:{window_ref}",
            window=OperatingWindow(
                window_ref=window_ref,
                organization_ref=organization_ref,
                opens_at_tick=1,
                closes_at_tick=5,
                policy_revision="policy:window:1",
                source_revision="schedule:1",
            ),
            visibility_scope="project",
        )
        closed = authority.close_operating_window(
            command_id=f"command:{window_ref}:close",
            idempotency_key=f"{window_ref}:close",
            causation_id=f"cause:{window_ref}:close",
            correlation_id=f"corr:{window_ref}",
            organization_ref=organization_ref,
            window_ref=window_ref,
            expected_stream_revision=1,
            visibility_scope="project",
        )
        if not opened.committed or not closed.committed:
            raise RuntimeError("owner_probe_setup_failed")
        windows.append((organization_ref, window_ref))

    world_stream = f"world:{world.mode.world_ref}"
    cadence = PopulationCadenceInput(
        cadence_id=f"cadence:owner-scale:{suffix}",
        world_ref=world.mode.world_ref,
        world_mode_ref=f"world-mode:{world.mode.world_ref}",
        world_mode_revision=world.mode.revision,
        cadence_source_ref=world_stream,
        cadence_source_revision=store.get_stream_head(world_stream),
        window_start=100,
        window_end=101,
        base_checkpoint_ref=f"checkpoint:owner-scale:{suffix}",
        base_checkpoint_digest="sha256:owner-scale",
        base_revision_vector={world_stream: store.get_stream_head(world_stream)},
        policy_revision="policy:population:v1",
        selector_revision="selector:generic:population:v1",
        ruleset_revision="rules:population:v1",
        deterministic_seed=f"seed:owner-scale:{suffix}",
        catch_up_limit=2,
        budget=2,
        report_scope="organization:summary",
    )
    projections = tuple(
        PopulationProjection(
            ref=f"projection:{window_ref}",
            scope="organization:summary",
            revision_vector={f"gameplay:organization:window:{window_ref}": 2},
            payload={
                "actor_ref": f"character:{organization_ref.removeprefix('org:')}",
                "candidate_kind": "organization_operating_window_due",
                "fidelity_tier": "B1",
                "source_domain": "organization",
                "intent_kind": "operating_window_due",
                "stream_ref": f"gameplay:organization:window:{window_ref}",
                "organization_ref": organization_ref,
                "window_ref": window_ref,
            },
        )
        for organization_ref, window_ref in windows
    )
    read_set = PopulationReadSet.from_inputs(cadence, projections)
    capability = PopulationSimulationCapability(
        owner_executors={
            "population:organization-window-due:v1": OrganizationOperatingWindowDueOwnerExecutor(
                authority=authority
            )
        }
    )
    return capability, cadence, read_set


def _execute_sparse_owner_batch(
    *,
    store: DurableGameplayEventStore,
    capability: PopulationSimulationCapability,
    cadence: PopulationCadenceInput,
    read_set: PopulationReadSet,
    before_transactions: int,
) -> tuple[float, bool]:
    started = perf_counter()
    cycle = capability.run_default_decision_cycle(cadence, read_set)
    elapsed_ms = (perf_counter() - started) * 1000.0
    transactions = store.read_transactions()
    committed_batch = transactions[-1]
    verified = (
        cycle.status == "accepted"
        and cycle.production_append_count == 1
        and len(cycle.owner_receipts) == 2
        and all(receipt.committed for receipt in cycle.owner_receipts)
        and len(transactions) == before_transactions + 1
        and len(committed_batch.events) == 2
        and len(committed_batch.owner_fragments) == 2
    )
    return elapsed_ms, verified


def scenario_evidence_complete(result: dict[str, Any]) -> bool:
    return all(
        condition is True
        for condition in (
            result.get("status") == "completed",
            result.get("windows_completed") == result.get("window_count"),
            isinstance(result.get("p95_wall_ms"), (int, float)),
            isinstance(result.get("max_lag_windows"), int),
            result.get("serial_parallel_equivalent"),
            result.get("pipeline_verified"),
            result.get("authority_graph_verified"),
            result.get("behavior_turn_verified"),
            result.get("b0_cursor_verified"),
            result.get("window_evidence_verified"),
            result.get("character_registration_verified"),
            result.get("full_profile_loaded") is False,
            result.get("persistent_gameplay_verified"),
            result.get("recovery_verified"),
            result.get("owner_scenario_verified"),
        )
    )


def scenario_passed(result: dict[str, Any]) -> bool:
    p95_ms = result.get("p95_wall_ms")
    budget = result.get("wall_budget_seconds")
    return scenario_evidence_complete(result) and all(
        condition is True
        for condition in (
            isinstance(p95_ms, (int, float))
            and isinstance(budget, (int, float))
            and p95_ms <= budget * 800.0,
            result.get("backlog_non_growing"),
            isinstance(result.get("max_lag_windows"), int) and result["max_lag_windows"] <= 1,
        )
    )


def measure_scenario(
    *, population: int, window_count: int = WINDOW_COUNT,
    wall_budget_seconds: float, storage_path: Path,
) -> dict[str, Any]:
    result = empty_scenario(
        population=population, window_count=window_count, wall_budget_seconds=wall_budget_seconds,
    )
    graph: SQLiteHeavenlyGraphAdapter | None = None
    original_advance_b0_row = world_module.advance_b0_row
    capture_kernel = False
    kernel_window_ms = 0.0
    try:
        roster = _roster(population)
        mode = _mode(population)
        store = DurableGameplayEventStore(storage_path)
        world = WorldContinuityRuntime(store=store, mode=mode, roster=roster)
        if store.get_stream_head(f"world:{mode.world_ref}") == 0 and not world.resume().committed:
            raise RuntimeError("world_resume_failed")

        character_runtime = CharacterAgentRuntime(
            storage_root=storage_path.parent / f"character-{storage_path.stem}",
            continuity_actor_ids=set(roster.actor_ids),
        )
        result["character_registration_verified"] = all(
            character_runtime.supports_continuity_actor(actor_id) for actor_id in roster.actor_ids
        )
        result["full_profile_loaded"] = any(
            character_runtime._profile_registry.contains(actor_id) for actor_id in roster.actor_ids
        )

        bus = InMemoryAuthorityEventBus(history_limits={"population_cadence_event": 2})
        capability = _MeasuredCapability()
        graph_path = storage_path.with_suffix(".authority.sqlite3")
        graph = SQLiteHeavenlyGraphAdapter(graph_path)
        pipeline = SimingEventPipeline(
            bus=bus, consumer=SimingEventConsumer(),
            runtime=SimingRuntime(
                population_capability=capability,
                behavior_turn_recorder=BehaviorTurnRecorder(graph),
                behavior_turn_scope_resolver=_siming_scope_for_event,
            ),
            producer=SimingEventProducer(bus), audit_writer=SimingAuditWriter(),
        )
        pipeline_ms: list[float] = []
        graph_ms: list[float] = []
        pipeline_event_count = 0
        graph_event_count = 0

        def handle_population_event(event) -> None:
            nonlocal pipeline_event_count
            started = perf_counter()
            pipeline.handle_event(event)
            pipeline_ms.append((perf_counter() - started) * 1000.0)
            pipeline_event_count += 1

        projector = HeavenlyAuthorityEventProjector(
            graph,
            scope_resolver=_siming_scope_for_event,
        )

        def project_authority_event(event) -> None:
            nonlocal graph_event_count
            started = perf_counter()
            projector.project(event)
            graph_ms.append((perf_counter() - started) * 1000.0)
            graph_event_count += 1

        bus.subscribe("population_cadence_event", handle_population_event, consumer_id="siming")
        bus.subscribe("*", project_authority_event)
        publisher = RuntimeCadencePublisher(
            world_runtime=world, event_bus=bus,
            room_id="room:population-scale", scene_id="scene:population-scale", zone_id="zone:population-scale",
        )

        owner_probe = _prepare_sparse_owner_batch(
            store=store,
            world=world,
            suffix=f"{population}-{window_count}-{int(wall_budget_seconds * 1000)}",
        )

        durable_transaction_ms: list[float] = []
        write_delta = store._write_delta

        def measured_write_delta(**kwargs):
            started = perf_counter()
            try:
                return write_delta(**kwargs)
            finally:
                durable_transaction_ms.append((perf_counter() - started) * 1000.0)

        store._write_delta = measured_write_delta  # type: ignore[method-assign]

        def measured_advance_b0_row(**kwargs):
            nonlocal kernel_window_ms
            if not capture_kernel:
                return original_advance_b0_row(**kwargs)
            started = perf_counter()
            try:
                return original_advance_b0_row(**kwargs)
            finally:
                kernel_window_ms += (perf_counter() - started) * 1000.0

        world_module.advance_b0_row = measured_advance_b0_row
        total_ms: list[float] = []
        kernel_ms: list[float] = []
        packaging_ms: list[float] = []
        protocol_bytes = 0
        virtual_finish = 0.0
        backlog_windows: list[int] = []
        serial_parallel_equivalent = True
        b0_cursor_verified = True
        owner_ms: float | None = None
        owner_verified = False
        owner_window = window_count // 2
        window_evidence: list[dict[str, Any]] = []

        for window_start in range(window_count):
            storage_before = len(durable_transaction_ms)
            pipeline_before = len(pipeline_ms)
            graph_before = len(graph_ms)
            started = perf_counter()
            cadence = world.build_population_cadence(window_start=window_start, window_end=window_start + 1)
            kernel_window_ms = 0.0
            capture_kernel = True
            try:
                event = publisher(cadence)
            finally:
                capture_kernel = False
            cadence_elapsed_ms = (perf_counter() - started) * 1000.0
            if event is None:
                raise RuntimeError(f"population_window_publish_failed:{window_start}")
            kernel_ms.append(kernel_window_ms)
            storage_before_owner = len(durable_transaction_ms)
            if window_start == owner_window:
                owner_before_transactions = len(store.read_transactions())
                owner_ms, owner_verified = _execute_sparse_owner_batch(
                    store=store,
                    capability=owner_probe[0],
                    cadence=owner_probe[1],
                    read_set=owner_probe[2],
                    before_transactions=owner_before_transactions,
                )
            elapsed = perf_counter() - started
            elapsed_ms = elapsed * 1000.0
            total_ms.append(elapsed_ms)
            measured_children = (
                sum(durable_transaction_ms[storage_before:storage_before_owner])
                + sum(pipeline_ms[pipeline_before:])
                + sum(graph_ms[graph_before:])
            )
            packaging_ms.append(max(0.0, cadence_elapsed_ms - kernel_ms[-1] - measured_children))
            event_payload = event.model_dump(mode="json")
            protocol_bytes += len(
                json.dumps(event_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            )
            b0 = [
                item for item in event_payload["payload"]["population_projections"]
                if item["payload"].get("fidelity_tier") == "B0"
            ]
            b0_cursor_verified &= len(b0) == population and all(
                item["payload"].get("simulation_tick_cursor") == window_start + 1 for item in b0
            )
            window_evidence.append(
                _window_identity_evidence(
                    cadence=cadence,
                    rows=b0,
                    stats=capability.last_b0_stats,
                    roster=roster,
                )
            )
            del b0, event_payload, event
            arrival = window_start * wall_budget_seconds
            virtual_finish = max(virtual_finish, arrival) + elapsed
            delay = max(0.0, virtual_finish - (window_start + 1) * wall_budget_seconds)
            backlog_windows.append(int(delay / wall_budget_seconds + 0.999999))

            if window_start in {0, window_count - 1}:
                check_cadence = world.build_population_cadence(
                    window_start=window_start + 1,
                    window_end=window_start + 2,
                    cadence_id=f"cadence:equivalence:{population}:{window_start}",
                )
                world._projection_cache.clear()
                world._preview_results.clear()
                serial = world.build_population_projections(check_cadence, workers=1, batch_size=256)
                serial_payload = [item.model_dump(mode="json") for item in serial]
                world._projection_cache.clear()
                world._preview_results.clear()
                parallel = world.build_population_projections(check_cadence, workers=4, batch_size=256)
                parallel_payload = [item.model_dump(mode="json") for item in parallel]
                serial_parallel_equivalent &= _digest(serial_payload) == _digest(parallel_payload)
                del serial, serial_payload, parallel, parallel_payload, check_cadence
                world._cadence_cache.clear()
                world._projection_cache.clear()
                world._preview_results.clear()

        committed_hash = _hot_state_hash(world)
        recovery_started = perf_counter()
        recovered_store = DurableGameplayEventStore(storage_path)
        recovered_world = WorldContinuityRuntime(store=recovered_store, mode=mode, roster=roster)
        recovered_publisher = RuntimeCadencePublisher(
            world_runtime=recovered_world, event_bus=InMemoryAuthorityEventBus(),
            room_id="room:population-scale", scene_id="scene:population-scale", zone_id="zone:population-scale",
        )
        recovery_ms = (perf_counter() - recovery_started) * 1000.0
        recovered_hash = _hot_state_hash(recovered_world)
        persisted_events = recovered_store.read_stream(recovered_publisher.stream_id)
        behavior_turn_nodes = graph.query_nodes(
            HeavenlyNodeQuery(
                scope=HeavenlyGraphScope(
                    world_id="world:demo",
                    session_id="session:demo",
                    story_branch_id="branch:main",
                ),
                valid_at=2**63 - 1,
                node_types=["behavior_turn"],
                limit=1000,
            )
        )
        behavior_turn_count = sum(
            node.attributes.get("entity_kind") == "turn" for node in behavior_turn_nodes
        )

        result.update(
            status="completed", windows_completed=len(total_ms), window_wall_ms=total_ms,
            p50_wall_ms=median(total_ms), p95_wall_ms=percentile(total_ms),
            pure_kernel_ms=kernel_ms, protocol_packaging_ms=packaging_ms,
            durable_transaction_ms=durable_transaction_ms,
            pipeline_ms=pipeline_ms, authority_graph_ms=graph_ms,
            stage_costs={
                "pure_integrator": _cost_summary(kernel_ms),
                "protocol_packaging": _cost_summary(packaging_ms),
                "durable_transaction": _cost_summary(durable_transaction_ms),
                "siming_pipeline": _cost_summary(pipeline_ms),
                "authority_graph": _cost_summary(graph_ms),
                "sparse_owner": _cost_summary([owner_ms] if owner_ms is not None else []),
            },
            recovery_ms=recovery_ms, protocol_bytes=protocol_bytes,
            durable_store_bytes=_sqlite_bytes(storage_path),
            authority_graph_bytes=_sqlite_bytes(graph_path),
            process_peak_rss_bytes=peak_rss_bytes(), backlog_windows=backlog_windows,
            backlog_non_growing=not _sustained_growth(backlog_windows),
            max_lag_windows=max(backlog_windows, default=0),
            serial_parallel_equivalent=serial_parallel_equivalent,
            published_event_count=pipeline_event_count,
            retained_event_count=len(bus.list_events(
                event_type="population_cadence_event", include_realtime=True, current_only=False,
            )),
            pipeline_event_count=pipeline_event_count,
            capability_cycle_count=capability.default_cycle_count,
            authority_graph_event_count=graph_event_count,
            behavior_turn_count=behavior_turn_count,
            pipeline_verified=(pipeline_event_count == window_count and capability.default_cycle_count == window_count),
            authority_graph_verified=graph_event_count == window_count,
            behavior_turn_verified=behavior_turn_count == window_count,
            b0_cursor_verified=b0_cursor_verified and capability.b0_cycle_verified,
            input_roster_digest=_digest(roster.actor_ids),
            window_evidence=window_evidence,
            window_evidence_verified=(
                len(window_evidence) == window_count
                and all(item["verified"] is True for item in window_evidence)
            ),
            owner_ms=owner_ms,
            owner_scenario_verified=owner_verified,
            persistent_gameplay_verified=(
                len(persisted_events) == window_count
                and not any(
                    entry.topic == "population_cadence_event"
                    for entry in recovered_store.list_outbox(include_delivered=False)
                )
                and recovered_publisher.confirmed_tick == window_count
            ),
            recovery_verified=recovered_hash == committed_hash,
            committed_hot_state_hash=committed_hash,
            recovered_hot_state_hash=recovered_hash,
        )
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}:{exc}"
    finally:
        world_module.advance_b0_row = original_advance_b0_row
        if graph is not None:
            graph.close()
    result["passed"] = scenario_passed(result)
    return result


def build_report() -> dict[str, Any]:
    profiles: dict[str, dict[str, Any]] = {}
    all_scenarios: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="population-runtime-scale-") as directory:
        directory_path = Path(directory)
        for profile_name, profile in PRESSURE_PROFILES.items():
            scenarios = [
                measure_scenario(
                    population=population,
                    wall_budget_seconds=profile["wall_budget_seconds"],
                    storage_path=directory_path / f"{profile_name}-{population}.json",
                )
                for population in POPULATION_SIZES
            ]
            profiles[profile_name] = {
                **profile,
                "scenarios": scenarios,
                "ran_complete": len(scenarios) == len(POPULATION_SIZES)
                and all(scenario_evidence_complete(item) for item in scenarios),
                "passed": len(scenarios) == len(POPULATION_SIZES)
                and all(item.get("passed") is True for item in scenarios),
            }
            all_scenarios.extend(scenarios)
    kernel_total = sum(sum(item["pure_kernel_ms"]) for item in all_scenarios)
    total = sum(sum(item["window_wall_ms"]) for item in all_scenarios)
    cpu_kernel_share = kernel_total / total if total > 0 else None
    all_required_evidence = bool(all_scenarios) and all(
        scenario_evidence_complete(item) for item in all_scenarios
    )
    all_performance_gates_passed = all(
        profile.get("passed") is True for profile in profiles.values()
    )
    mandatory_one_x_passed = profiles.get("one_x", {}).get("passed") is True
    return {
        "measurement_schema_version": 1,
        "stage": 5,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "git_head": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
        ).stdout.strip(),
        "implementation_digest": implementation_digest(ROOT),
        "profiles": profiles,
        "provider_mode": "disabled_default",
        "game_instance_count": 1,
        "cpu_kernel_share": cpu_kernel_share,
        "protocol_persistence_share": (1.0 - cpu_kernel_share) if cpu_kernel_share is not None else None,
        "all_required_evidence": all_required_evidence,
        "all_performance_gates_passed": all_performance_gates_passed,
        "overall_passed": all_required_evidence and mandatory_one_x_passed,
        "implementation_status": "benchmark_completed" if all_required_evidence else "benchmark_evidence_incomplete",
        "godot_status": "godot_unverified",
    }


def main() -> int:
    report = build_report()
    directory = ROOT / ".harness" / "verification"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "population-runtime-scale-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"overall_population_runtime_scale_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
