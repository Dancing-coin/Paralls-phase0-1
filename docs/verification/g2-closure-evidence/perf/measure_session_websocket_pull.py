"""Original two rounds, or one explicitly selected post-filter code round.

No runtime source is edited. Historical handler code is loaded from a detached
worktree; both handlers share the current component transport and send gate.
"""
from __future__ import annotations

import ast
import argparse
import gc
import hashlib
import json
import platform
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "tests"))

import uvicorn
from websockets.sync.client import connect
import app.main as main
from app.config import Settings
from app.gameplay.models import AtomicEventBatch, IdempotencyRecord
from test_embodied_interaction_session import _propose, _set_world_tick

BASELINE = Path(r"D:\Temp\paralls-g2-session-baseline-00146107")
OUTPUT = Path(__file__).with_name("session-websocket-pull-results.json")
CURRENT = main._handle_embodied_interaction_session_projection_pull
MESSAGE_TYPE = "embodied_interaction_session_projection_pull"


def git(*args: str, root: Path = ROOT) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def load_legacy_handler():
    path = BASELINE / "backend/app/main.py"
    names = {
        "_handle_embodied_interaction_session_projection_pull",
        "_embodied_session_event_envelope_from_gameplay_event",
        "_embodied_session_event_envelope_from_authority_event",
    }
    definitions = [node for node in ast.parse(path.read_text(encoding="utf-8")).body
                   if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in definitions} != names:
        raise RuntimeError("legacy_handler_source_incomplete")
    namespace = dict(vars(main))
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def seed(event_count: int, session_id: str) -> None:
    main.reset_runtime_state()
    _set_world_tick(main.embodied_interaction_session_service)
    if not _propose(main.embodied_interaction_session_service, session_id=session_id).accepted:
        raise RuntimeError("owner_proposal_fixture_failed")
    store = main.gameplay_event_store
    stream_id = f"session:{session_id}"
    proposal = store.read_stream(stream_id)[0]
    # Synthetic lifecycle-shaped history for read/copy scale. Commit through the
    # real Store; do not mutate Store internals or assert valid Owner transitions.
    tx = f"perf-history:{session_id}"
    events = [proposal.model_copy(update={
        "event_id": f"perf:{session_id}:{index}",
        "event_type": "embodied.interaction_session.accepted",
        "schema_version": 1, "stream_revision": 0, "global_sequence": 0,
        "transaction_id": tx, "command_id": tx,
        "payload": {key: value for key, value in proposal.payload.items() if key != "known_time"},
    }, deep=True) for index in range(1, event_count)]
    result = store.append_batch(AtomicEventBatch(
        transaction_id=tx, command_id=tx, expected_stream_revisions={stream_id: 1},
        events=events, idempotency_record=IdempotencyRecord(
            principal_ref="perf:fixture", idempotency_key=tx, payload_digest=tx),
        result_digest=tx,
    ))
    if not result.committed or len(store.read_stream(stream_id)) != event_count:
        raise RuntimeError("fixture_commit_or_count_failed")


def bind(ws) -> None:
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:session-read-benchmark", allowed_actor_refs=("character:siming",),
        issued_at=0, expires_at=int(main.time()) + 3600,
    )
    ws.send(json.dumps({"message_type": "websocket_session_bind", "payload": {
        "credential_kind": "trusted_local_launch", "credential": credential,
        "protocol_version": 2, "capability_offer": main.GameplayMirrorCapabilityOffer(
            protocol_version=2, supports_snapshot=True, supports_receipt=True,
            projection_schemas=("gameplay_runtime_state.godot.v1",),
        ).model_dump(),
    }}))
    ack = json.loads(ws.recv(timeout=10))
    bound = json.loads(ws.recv(timeout=10))
    if ack.get("payload", {}).get("accepted") is not True or bound.get("message_type") != "websocket_session_bound":
        raise RuntimeError("binding_failed")


def distribution(samples: list[dict]) -> dict:
    ordered = sorted(item["ms"] for item in samples)
    def percentile(p):
        index = (len(ordered) - 1) * p
        low = int(index)
        high = min(low + 1, len(ordered) - 1)
        return ordered[low] + (ordered[high] - ordered[low]) * (index - low)
    return dict(n=len(ordered), p50_ms=percentile(.50), p95_ms=percentile(.95),
                p99_ms=percentile(.99), max_ms=ordered[-1],
                gc_starts=sum(item["gc_starts"] for item in samples))


def measure(legacy: dict, url: str, event_count: int, round_number: int, gc_events: list, *, direct_gate=False) -> dict:
    session_id = f"g2-perf-{round_number}-{event_count}"
    seed(event_count, session_id)
    # Rebind the historical functions' globals to this fixture's actual services.
    for name in ("gameplay_event_store", "authority_event_bus", "embodied_interaction_session_service"):
        legacy[name] = getattr(main, name)
    contexts = []
    def current_handler(envelope, context):
        contexts.append(context)
        return CURRENT(envelope, context)
    def legacy_handler(envelope, context):
        return legacy["_handle_embodied_interaction_session_projection_pull"](envelope)
    handlers = {"current": current_handler, "historical_handler": legacy_handler}
    raw = {name: [] for name in handlers}
    warmups = {name: [] for name in handlers}
    direct = {"raw": [], "warmups": []}
    with connect(url, proxy=None, open_timeout=10, close_timeout=10) as ws:
        bind(ws)
        request = json.dumps({"message_type": MESSAGE_TYPE, "payload": {
            "session_id": session_id, "after_global_sequence": 0,
        }})
        for index in range(70):
            order = ("current", "historical_handler") if index % 2 == 0 else ("historical_handler", "current")
            for name in order:
                main._handle_embodied_interaction_session_projection_pull = handlers[name]
                gc_before = len(gc_events)
                started = time.perf_counter_ns()
                ws.send(request)
                response = json.loads(ws.recv(timeout=10))
                elapsed = (time.perf_counter_ns() - started) / 1_000_000
                payload = response.get("payload", {})
                if (response.get("message_type") != "embodied_interaction_session_event"
                        or payload.get("session_id") != session_id
                        or payload.get("semantic_action") != "handshake"):
                    raise RuntimeError("positive_pull_failed")
                if name == "current" and (payload.get("known_time") != 481
                        or any(key in payload for key in ("target_refs", "participant_private_terms", "slot_assignments", "reservation_refs"))):
                    raise RuntimeError("current_projection_contract_failed")
                item = dict(pair_index=index, ms=elapsed, gc_starts=len(gc_events) - gc_before)
                (warmups if index < 10 else raw)[name].append(item)
        if direct_gate:
            context = contexts[-1]
            original_read = main.gameplay_event_store.read_stream
            read_ms = []
            def timed_read(*args, **kwargs):
                started = time.perf_counter_ns()
                result = original_read(*args, **kwargs)
                read_ms.append((time.perf_counter_ns() - started) / 1_000_000)
                return result
            main.gameplay_event_store.read_stream = timed_read
            try:
                for index in range(70):
                    gc_before = len(gc_events)
                    started = time.perf_counter_ns()
                    event = main._session_initiator_event(session_id, context, now=int(main.time()))
                    elapsed = (time.perf_counter_ns() - started) / 1_000_000
                    if event is None or event.payload["known_time"] != 481:
                        raise RuntimeError("direct_gate_positive_failed")
                    item = dict(pair_index=index, ms=elapsed, read_ms=read_ms[-1],
                                gc_starts=len(gc_events) - gc_before)
                    direct["warmups" if index < 10 else "raw"].append(item)
            finally:
                main.gameplay_event_store.read_stream = original_read
    if not contexts or contexts[-1].binding is None:
        raise RuntimeError("bound_context_not_observed")
    summaries = {name: distribution(samples) for name, samples in raw.items()}
    ratio = summaries["current"]["p95_ms"] / summaries["historical_handler"]["p95_ms"]
    result = dict(round=round_number, event_count=event_count, summary=summaries,
                p95_ratio_diagnostic=ratio, raw=raw, warmups=warmups,
                bound_context_observed=True,
                candidate_relative_exceeded=ratio > 1.10,
                candidate_absolute_exceeded=event_count == 4096 and summaries["current"]["p95_ms"] >= 40)
    if direct_gate:
        direct["summary"] = distribution(direct["raw"])
        direct["read_summary"] = distribution([dict(ms=x["read_ms"], gc_starts=0) for x in direct["raw"]])
        direct["read_summary"].pop("gc_starts")
        result["direct_gate"] = direct
        # New budget wording is a proposal for the project lead, not a pass gate.
        result.pop("candidate_relative_exceeded")
        result.pop("candidate_absolute_exceeded")
    return result


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--post-filter", action="store_true",
                        help="one new-code round at 10/20/100/4096; preserve original two-round file")
    args = parser.parse_args()
    output = OUTPUT.with_name("session-websocket-pull-post-filter-round1.json") if args.post_filter else OUTPUT
    if output.exists():
        raise RuntimeError("refusing_to_overwrite_samples")
    # Use the same stub/in-memory configuration as the session test fixture.
    configured = Settings(dialogue_mode="stub", character_model_provider_kind="local",
                          heavenly_graph_path=":memory:", siming_llm_mode="disabled")
    for name in Settings.model_fields:
        setattr(main.settings, name, getattr(configured, name))
    legacy = load_legacy_handler()
    original_head = git("rev-parse", "HEAD")
    source_hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
        "backend/app/main.py", "backend/app/gameplay/event_store.py",
        "backend/app/services/embodied_interaction_session_service.py")}
    gc_events = []
    def gc_callback(phase, info):
        if phase == "start":
            gc_events.append(dict(generation=info["generation"]))
    gc.callbacks.append(gc_callback)
    # Actual TCP, one process. Deliberately no production spawn host/lifespan.
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(main.component_app, lifespan="off", log_level="critical",
        access_log=False, ws="websockets", ws_per_message_deflate=False))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    runs = []
    try:
        deadline = time.monotonic() + 15
        while not server.started:
            if not thread.is_alive() or time.monotonic() >= deadline:
                raise RuntimeError("loopback_server_start_failed")
            time.sleep(.01)
        for round_number in ((1,) if args.post_filter else (1, 2)):
            for count in ((10, 20, 100, 4096) if args.post_filter else (100, 4096)):
                result = measure(legacy, f"ws://127.0.0.1:{port}/ws", count, round_number, gc_events,
                                 direct_gate=args.post_filter)
                runs.append(result)
                print(json.dumps({key: value for key, value in result.items() if key not in ("raw", "warmups", "direct_gate")}), flush=True)
        if original_head != git("rev-parse", "HEAD"):
            raise RuntimeError("source_head_changed_during_measurement")
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        listener.close()
        main._handle_embodied_interaction_session_projection_pull = CURRENT
        gc.callbacks.remove(gc_callback)
        if thread.is_alive():
            raise RuntimeError("loopback_server_shutdown_failed")
    result = dict(environment=dict(platform=platform.platform(), python=sys.version,
        executable=sys.executable, current_commit=original_head,
        baseline_commit=git("rev-parse", "HEAD", root=BASELINE), source_sha256=source_hashes,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        transport="real TCP loopback; Uvicorn component_app; production spawn host not included",
        baseline="historical handler only, shares current Store, binding and send gate; not full historical server",
        fixture="one real Owner v2 proposal plus Store-committed synthetic lifecycle-shaped events in its stream",
        gc_enabled=gc.isenabled(), gc_thresholds=gc.get_threshold(), gc_starts=len(gc_events)), runs=runs)
    if args.post_filter:
        result["measurement_series"] = "post-filter new code round 1"
        result["budget_status"] = "待项目负责人定；10% 相对增量本路径不适用；历史 handler 比例仅诊断"
    output.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


if __name__ == "__main__":
    run()
