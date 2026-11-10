"""Measure the existing session-bound Godot mirror with synthetic state groups."""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.metadata
import json
import math
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from app.gameplay.godot_mirror_delivery import GameplayMirrorSubscription, GameplayMirrorSubscriptionRegistry
from app.gameplay.runtime_state import CharacterGameRuntimeStateBuilder, StateGroupDefinition, StateGroupRegistry
from app.gameplay.state_group_views import StateGroupConsumerViewPolicy, StateGroupViewProjector
from app.services.gameplay_mirror_session_access_service import (
    GameplayMirrorSessionAccessError,
    GameplayMirrorSessionAccessService,
    GameplayMirrorSubscriptionRequest,
)
from app.services.websocket_session_auth_service import (
    WebSocketConnectionContext,
    WebSocketSessionAuthService,
    WebSocketSessionEnrollment,
)


def fixture(group_count: int):
    actor = "actor:fixture"
    groups = tuple(f"group:{index}" for index in range(group_count))
    registry = StateGroupRegistry()
    for group in groups:
        registry.register(StateGroupDefinition(group_id=group, definition_version="v1", projection_schema_version=1))
    state = CharacterGameRuntimeStateBuilder(registry).build(
        actor_ref=actor, enabled_group_ids=groups,
        group_payloads={group: {"public": {"value": index}, "private": "excluded"}
                        for index, group in enumerate(groups)},
        source_revision_vector={"stream:fixture": 1}, registry_revision="r1",
        world_config_revision="w1", active_patch_set_revision="p1",
    )
    projector = StateGroupViewProjector([
        StateGroupConsumerViewPolicy(group_id=group, godot_allowed_fields=("public",))
        for group in groups
    ])
    view = projector.godot_view(state, allowed_group_ids=groups)
    registry = GameplayMirrorSubscriptionRegistry(projection_source=lambda _: view)
    auth = WebSocketSessionAuthService()

    def context(principal: str, scope: tuple[str, ...], observed_at: int):
        credential = auth.create_trusted_local_launch_credential(
            principal_ref=principal, allowed_actor_refs=scope, issued_at=1, expires_at=100,
        )
        result = auth.bind_session(
            WebSocketSessionEnrollment(credential_kind="trusted_local_launch", credential=credential, protocol_version=1),
            remote_host="127.0.0.1", now=2,
        )
        if not result.accepted or result.binding is None:
            raise RuntimeError("fixture_bind_failed")
        return WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=observed_at, binding=result.binding)

    allowed = context("principal:allowed", (actor,), 2)
    denied = context("principal:other", ("actor:other",), 2)
    expired = context("principal:expired", (actor,), 101)
    service = GameplayMirrorSessionAccessService(registry=registry, binding_resolver=auth.resolve_binding)
    request = GameplayMirrorSubscriptionRequest(actor_ref=actor)
    snapshot = service.subscribe(context=allowed, request=request)
    subscription = GameplayMirrorSubscription(session_ref=allowed.binding.session_ref, actor_ref=actor)
    if snapshot != registry.after_commit_snapshot(subscription):
        raise RuntimeError("fixture_snapshot_mismatch")
    expected = {group: {"public": {"value": index}} for index, group in enumerate(groups)}
    if {key: value["payload"] for key, value in snapshot["groups"].items()} != expected:
        raise RuntimeError("fixture_field_filter_failed")

    def refusal(context, reason):
        try:
            service.snapshot(context=context, actor_ref=actor)
        except GameplayMirrorSessionAccessError as exc:
            if str(exc) == reason:
                return
            raise
        raise RuntimeError("fixture_refusal_missing")

    return {
        "raw_projection": lambda: registry.after_commit_snapshot(subscription),
        "allowed": lambda: service.snapshot(context=allowed, actor_ref=actor),
        "denied_scope": lambda: refusal(denied, "mirror_scope_unauthorized"),
        "expired": lambda: refusal(expired, "websocket_session_renewal_required"),
        "authority_view": lambda: projector.authority_view(state, allowed_group_ids=groups),
        "godot_field_filter": lambda: projector.godot_view(state, allowed_group_ids=groups),
    }


def summary(samples: list[int]) -> dict[str, float]:
    ordered = sorted(samples)
    return {
        "median_ms": statistics.median(samples) / 1_000_000,
        "p95_ms": ordered[math.ceil(len(ordered) * 0.95) - 1] / 1_000_000,
        "p99_ms": ordered[math.ceil(len(ordered) * 0.99) - 1] / 1_000_000,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=1000)
    parser.add_argument("--warmups", type=int, default=50)
    args = parser.parse_args()
    if args.repeats < 1 or args.warmups < 1:
        parser.error("repeats and warmups must be positive")
    rows = []
    for group_count in (1, 8, 32):
        calls = fixture(group_count)
        for _ in range(args.warmups):
            for call in calls.values():
                call()
        samples = {name: [] for name in calls}
        names = tuple(calls)
        for index in range(args.repeats):
            for offset in range(len(names)):
                name = names[(index + offset) % len(names)]
                start = time.perf_counter_ns()
                calls[name]()
                samples[name].append(time.perf_counter_ns() - start)
        rows.append({"group_count": group_count, "samples_ns": samples,
                     "summary": {name: summary(values) for name, values in samples.items()}})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sources = (
        "backend/app/gameplay/godot_mirror_delivery.py",
        "backend/app/gameplay/godot_mirror_projection.py",
        "backend/app/gameplay/runtime_state.py",
        "backend/app/gameplay/state_group_views.py",
        "backend/app/services/gameplay_mirror_session_access_service.py",
        "backend/app/services/websocket_session_auth_service.py",
    )
    args.output.write_text(json.dumps({
        "measurement": "existing_mirror_session_access_synthetic_state",
        "scope": "cached Godot mirror session access and separate state-group field projection; not principal event read_as",
        "python": sys.version, "platform": platform.platform(),
        "executable": sys.executable, "pydantic": importlib.metadata.version("pydantic"),
        "git_head": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources},
        "gc_threshold": gc.get_threshold(),
        "repeats": args.repeats, "warmups": args.warmups, "rows": rows,
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
