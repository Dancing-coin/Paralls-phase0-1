from __future__ import annotations

import argparse
import json
import os
import queue
import sqlite3
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from common import (
    ensure_backend,
    read_text,
    repo_root,
    resolve_godot_exe,
    resolve_python_exe,
    stop_backend,
    verification_dir,
    wait_for_backend_release,
    write_json,
    write_markdown,
)


RESULT_IDS = (
    "preflight_live_ready", "authority_removed_from_surface", "godot_object_disappeared",
    "char_b_observed", "char_b_restart_recalled", "cross_actor_isolated",
    "summary_free_context_rebuilt", "n3_divergence", "n4_terminal", "n5_unreachable",
    "o2_to_o6", "online_private_confrontation", "validator_accepted",
    "resource_signature_recorded", "single_dispatch", "char_b_visible_reaction",
    "outcome_written_back",
)
CAPTURE_NAMES = (
    "siming-heavenly-before-destruction.png",
    "siming-heavenly-after-destruction.png",
    "siming-heavenly-char-b-reaction.png",
)


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    reasons: tuple[str, ...] = ()
    summary: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceEvaluation:
    overall: bool
    reasons: tuple[str, ...] = ()


@dataclass
class LiveEvidence:
    result_ids: set[str]
    before_capture: Path
    after_capture: Path
    reaction_capture: Path
    provider_audit: dict[str, object]
    graph_payload: dict[str, object]

    @property
    def captures(self) -> tuple[Path, Path, Path]:
        return self.before_capture, self.after_capture, self.reaction_capture


def _project_env() -> dict[str, str]:
    values: dict[str, str] = {}
    root = repo_root()
    for path in (root / ".env", root / "backend" / ".env"):
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name.strip():
                values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, _project_env().get(name, default)).strip()


def _routes() -> list[dict[str, object]]:
    raw = _env("SIMING_LLM_ROUTES_JSON")
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []


def live_preflight(project_root: Path, godot_exe: str | None = None) -> PreflightResult:
    reasons: list[str] = []
    summary: dict[str, object] = {"godot_exe_present": False, "routes": []}
    try:
        summary["godot_exe_present"] = resolve_godot_exe(godot_exe).exists()
    except FileNotFoundError:
        reasons.append("godot_exe_required")
    if _env("SIMING_HEAVENLY_MODE") != "active":
        reasons.append("siming_heavenly_mode_active_required")
    if _env("SIMING_LLM_MODE") != "http":
        reasons.append("online_siming_llm_required")

    routes = _routes()
    configured: list[dict[str, str]] = []
    if routes:
        for route in routes:
            if not route.get("enabled", True) or str(route.get("provider", "")).lower() in {"disabled", "fake"}:
                continue
            configured.append({"route_id": str(route.get("route_id", "")), "model": str(route.get("model", ""))})
            if not route.get("endpoint"):
                reasons.append("online_route_endpoint_required")
            if not route.get("model"):
                reasons.append("online_route_model_required")
            if not route.get("api_key"):
                reasons.append("online_route_api_key_required")
        if not configured:
            reasons.append("online_http_route_required")
    else:
        provider = _env("SIMING_LLM_PROVIDER_ORDER", "openai_responses").split(",")[0].strip().lower()
        if provider in {"", "disabled", "fake"}:
            reasons.append("online_http_route_required")
        if not _env("SIMING_LLM_ENDPOINT"):
            reasons.append("online_endpoint_required")
        if not _env("SIMING_LLM_MODEL"):
            reasons.append("online_model_required")
        if not _env("SIMING_LLM_API_KEY"):
            reasons.append("online_api_key_required")
        configured.append({"route_id": provider or "unconfigured", "model": _env("SIMING_LLM_MODEL")})
    summary["routes"] = configured

    db_value = _env("PARALLS_HEAVENLY_GRAPH_PATH", ".runtime/siming-heavenly.sqlite3")
    db_path = Path(db_value)
    if not db_path.is_absolute():
        db_path = project_root / db_path
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        probe = db_path.parent / ".siming-heavenly-write-check"
        probe.write_text("ok", encoding="ascii")
        probe.unlink()
        summary["sqlite_parent_writable"] = True
    except OSError:
        summary["sqlite_parent_writable"] = False
        reasons.append("sqlite_parent_not_writable")
    return PreflightResult(not reasons, tuple(dict.fromkeys(reasons)), summary)


def _meaningful_capture(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 16
    except OSError:
        return False


def evaluate_live_evidence(evidence: LiveEvidence) -> EvidenceEvaluation:
    reasons: list[str] = []
    missing = sorted(set(RESULT_IDS) - set(evidence.result_ids))
    if missing:
        reasons.append("missing_result_ids:" + ",".join(missing))
    if not all(_meaningful_capture(path) for path in evidence.captures):
        reasons.append("three_meaningful_captures_required")
    audit = evidence.provider_audit
    for field_name in ("provider", "route_id", "model", "request_id"):
        if not str(audit.get(field_name, "")).strip():
            reasons.append(f"provider_audit_{field_name}_required")
    if str(audit.get("provider", "")).lower() in {"disabled", "fake"}:
        reasons.append("online_provider_audit_required")
    if str(audit.get("request_id", "")).lower() in {"not_requested", "disabled", "fake"}:
        reasons.append("online_provider_request_required")
    graph_text = json.dumps(evidence.graph_payload, ensure_ascii=False).lower()
    for node_id in ("n3", "n4", "n5", "o2", "o6"):
        if node_id not in graph_text:
            reasons.append(f"graph_node_required:{node_id.upper()}")
    char_b = evidence.graph_payload.get("char_b", {})
    if not isinstance(char_b, dict) or not char_b.get("Event") or not char_b.get("Observation"):
        reasons.append("char_b_event_observation_required")
    return EvidenceEvaluation(not reasons, tuple(dict.fromkeys(reasons)))


def _owned_db_path(project_root: Path, requested: str | None) -> Path:
    root = (verification_dir(project_root) / "siming-heavenly-runtime").resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = Path(requested) if requested else root / "siming-heavenly.sqlite3"
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if path != root and root not in path.parents:
        raise ValueError("sqlite path must remain under verifier-owned directory")
    return path


def _read_graph_payload(path: Path) -> dict[str, object]:
    payload: dict[str, object] = {"node_ids": [], "char_b": {}, "artifacts": []}
    if not path.exists():
        return payload
    try:
        with sqlite3.connect(str(path)) as connection:
            rows = connection.execute(
                """
                SELECT current.node_id, current.payload_json
                FROM graph_nodes AS current
                WHERE current.revision = (
                    SELECT MAX(candidate.revision)
                    FROM graph_nodes AS candidate
                    WHERE candidate.scope_json = current.scope_json
                      AND candidate.node_id = current.node_id
                )
                """
            ).fetchall()
    except sqlite3.Error:
        return payload
    node_ids: set[str] = set()
    char_b: dict[str, bool] = {}
    artifacts: list[dict[str, object]] = []
    for node_id, raw in rows:
        node_ids.add(str(node_id))
        try:
            item = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(item, dict):
            artifacts.append(item)
        text = json.dumps(item, ensure_ascii=False).lower()
        if "char_b" in text:
            if "event" in text:
                char_b["Event"] = True
            if "observation" in text:
                char_b["Observation"] = True
    payload["node_ids"] = sorted(node_ids)
    payload["char_b"] = char_b
    payload["artifacts"] = artifacts
    return payload


def _restart_boundary_ready(graph_payload: dict[str, object]) -> bool:
    """Require the durable pre-restart chain before stopping the first backend."""
    artifacts = [
        artifact
        for artifact in graph_payload.get("artifacts", [])
        if isinstance(artifact, dict)
    ]

    def attributes(artifact: dict[str, object]) -> dict[str, object]:
        value = artifact.get("attributes")
        return value if isinstance(value, dict) else {}

    def provenance(artifact: dict[str, object]) -> dict[str, object]:
        value = artifact.get("provenance")
        return value if isinstance(value, dict) else {}

    removal = next(
        (
            artifact
            for artifact in artifacts
            if attributes(artifact).get("world_anchor_id") == "obj_letter"
            and attributes(artifact).get("state_value") == "removed_from_surface"
            and str(attributes(artifact).get("authority_result_ref", ""))
        ),
        None,
    )
    if removal is None:
        return False
    authority_result_ref = str(attributes(removal)["authority_result_ref"])
    correlation_id = str(provenance(removal).get("correlation_id", ""))
    if not correlation_id:
        return False
    related = [
        artifact
        for artifact in artifacts
        if str(provenance(artifact).get("correlation_id", "")) == correlation_id
    ]

    # Character memory is private and keeps its own event correlation. Link it
    # to the world fact through the durable authority result reference instead
    # of assuming it shares the Siming correlation ID.
    actor_memory = [
        artifact
        for artifact in artifacts
        if str(artifact.get("node_type", "")).startswith("actor_memory:")
    ]
    has_event = any(
        str(artifact.get("node_type", "")) == "actor_memory:event"
        and isinstance(attributes(artifact).get("record"), dict)
        and attributes(artifact)["record"].get("actor_id") == "char_b"
        and authority_result_ref in attributes(artifact)["record"].get("refs", [])
        for artifact in actor_memory
    )
    has_observation = any(
        str(artifact.get("node_type", "")) == "actor_memory:observation"
        and isinstance(attributes(artifact).get("record"), dict)
        and attributes(artifact)["record"].get("actor_id") == "char_b"
        and attributes(artifact)["record"].get("observed_entity_id") == "obj_letter"
        and authority_result_ref in attributes(artifact)["record"].get("refs", [])
        for artifact in actor_memory
    )
    bridge_accepted = any(
        str(artifact.get("node_type", "")) == "adaptive_bridge_audit"
        and isinstance(attributes(artifact).get("proposal"), dict)
        and attributes(artifact)["proposal"].get("pattern") == "private_confrontation"
        and isinstance(attributes(artifact).get("validation"), dict)
        and attributes(artifact)["validation"].get("accepted") is True
        for artifact in related
    )
    has_staging_request = any(
        str(artifact.get("node_type", "")) == "memory:intervention_outcome"
        and attributes(artifact).get("stage") == "proposal"
        and str(attributes(artifact).get("selected_node_ref", ""))
        and isinstance(attributes(artifact).get("staging_request"), dict)
        and str(attributes(artifact)["staging_request"].get("node_id", ""))
        for artifact in related
    )
    has_selection = any(
        str(artifact.get("node_type", "")) == "memory:intervention_outcome"
        and attributes(artifact).get("stage") == "selection"
        and str(attributes(artifact).get("selected_node_ref", ""))
        for artifact in related
    )
    staging_ack_sources = {
        str(attributes(artifact)["staging_ack"].get("source", ""))
        for artifact in related
        if str(artifact.get("node_type", "")) == "memory:intervention_outcome"
        and attributes(artifact).get("stage") == "staging_ack"
        and isinstance(attributes(artifact).get("staging_ack"), dict)
        and attributes(artifact)["staging_ack"].get("accepted") is True
    }
    return (
        has_event
        and has_observation
        and bridge_accepted
        and has_staging_request
        and has_selection
        and {"character", "esm"}.issubset(staging_ack_sources)
    )


def _wait_for_restart_boundary(path: Path, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _restart_boundary_ready(_read_graph_payload(path)):
            return True
        time.sleep(0.1)
    return _restart_boundary_ready(_read_graph_payload(path))


def _collect_result_ids(
    log: str,
    graph_payload: dict[str, object],
    *,
    preflight_ready: bool = False,
) -> set[str]:
    found = {"preflight_live_ready"} if preflight_ready else set()
    artifacts = [
        artifact
        for artifact in graph_payload.get("artifacts", [])
        if isinstance(artifact, dict)
    ]

    def attributes(artifact: dict[str, object]) -> dict[str, object]:
        value = artifact.get("attributes")
        return value if isinstance(value, dict) else {}

    def provenance(artifact: dict[str, object]) -> dict[str, object]:
        value = artifact.get("provenance")
        return value if isinstance(value, dict) else {}

    removal = next(
        (
            artifact
            for artifact in artifacts
            if attributes(artifact).get("world_anchor_id") == "obj_letter"
            and attributes(artifact).get("state_value") == "removed_from_surface"
            and str(attributes(artifact).get("authority_result_ref", ""))
        ),
        None,
    )
    if removal is None:
        return found

    authority_result_ref = str(attributes(removal)["authority_result_ref"])
    correlation_id = str(provenance(removal).get("correlation_id", ""))
    if not correlation_id:
        return found
    related = [
        artifact
        for artifact in artifacts
        if str(provenance(artifact).get("correlation_id", "")) == correlation_id
    ]
    found.add("authority_removed_from_surface")

    restart_complete = (
        "siming_heavenly_restart_ready" in log
        and "siming_heavenly_godot_complete" in log
    )
    if restart_complete:
        found.add("godot_object_disappeared")

    actor_memory = [
        artifact
        for artifact in artifacts
        if str(artifact.get("node_type", "")).startswith("actor_memory:")
    ]
    observation = next(
        (
            artifact
            for artifact in actor_memory
            if str(artifact.get("node_type", "")) == "actor_memory:observation"
            and isinstance(attributes(artifact).get("record"), dict)
            and attributes(artifact)["record"].get("actor_id") == "char_b"
            and attributes(artifact)["record"].get("observed_entity_id") == "obj_letter"
            and authority_result_ref in attributes(artifact)["record"].get("refs", [])
        ),
        None,
    )
    char_b_event = any(
        str(artifact.get("node_type", "")) == "actor_memory:event"
        and isinstance(attributes(artifact).get("record"), dict)
        and attributes(artifact)["record"].get("actor_id") == "char_b"
        and authority_result_ref in attributes(artifact)["record"].get("refs", [])
        for artifact in actor_memory
    )
    if observation is not None and char_b_event:
        found.add("char_b_observed")
        owner_ids = {
            str(scope.get("owner_actor_id", ""))
            for artifact in actor_memory
            if isinstance((scope := artifact.get("scope")), dict)
        }
        if owner_ids == {"char_b"}:
            found.add("cross_actor_isolated")
        if restart_complete:
            found.add("char_b_restart_recalled")

    story_nodes = {
        str(attributes(artifact).get("blueprint_id", "")): attributes(artifact)
        for artifact in related
        if str(artifact.get("node_type", "")) == "runtime_story_node"
    }
    n3, n4, n5 = (story_nodes.get(node_id, {}) for node_id in ("N3", "N4", "N5"))
    if n3.get("lifecycle") == "resolved" and n3.get("outcome_semantic") == "resolved_with_divergence":
        found.add("n3_divergence")
    if n4.get("lifecycle") == "aborted" and n4.get("closure_reason") == "closed_by_player_choice" and n4.get("terminal") is True:
        found.add("n4_terminal")
    if n5.get("reachability") == "unreachable_by_ledger":
        found.add("n5_unreachable")

    obligations = {
        str(attributes(artifact).get("entry_id", "")): attributes(artifact)
        for artifact in related
        if str(artifact.get("node_type", "")) == "memory:storyline_obligation"
    }
    if obligations.get("obligation:O2", {}).get("lifecycle") == "transformed" and obligations.get("obligation:O6", {}).get("lifecycle") == "open":
        found.add("o2_to_o6")

    bridge_audit = next(
        (
            attributes(artifact)
            for artifact in related
            if str(artifact.get("node_type", "")) == "adaptive_bridge_audit"
            and isinstance(attributes(artifact).get("proposal"), dict)
            and attributes(artifact)["proposal"].get("pattern") == "private_confrontation"
        ),
        {},
    )
    if bridge_audit:
        found.update({"online_private_confrontation", "summary_free_context_rebuilt"})
        if isinstance(bridge_audit.get("validation"), dict) and bridge_audit["validation"].get("accepted") is True:
            found.add("validator_accepted")

    staged = [
        attributes(artifact)
        for artifact in related
        if attributes(artifact).get("stage") == "staging"
        and attributes(artifact).get("staging_status") == "staged"
        and str(attributes(artifact).get("realization_signature", ""))
    ]
    if staged:
        found.add("resource_signature_recorded")
    dispatches = [
        artifact for artifact in related if attributes(artifact).get("stage") == "dispatch"
    ]
    if len(dispatches) == 1:
        found.add("single_dispatch")
        if restart_complete:
            found.add("char_b_visible_reaction")

    if any(
        str(artifact.get("node_id", "")).startswith("story_outcome:")
        and attributes(artifact).get("record_type") == "outcome_port"
        and authority_result_ref in attributes(artifact).get("supporting_fact_refs", [])
        for artifact in related
    ):
        found.add("outcome_written_back")
    return found


def _provider_audit_from_graph(graph_payload: dict[str, object]) -> dict[str, object]:
    def walk(value: object) -> dict[str, object] | None:
        if isinstance(value, dict):
            candidate = value.get("provider_audit")
            if isinstance(candidate, dict):
                return dict(candidate)
            if all(str(value.get(field, "")).strip() for field in ("provider", "route_id", "model", "request_id")):
                return {field: value[field] for field in ("provider", "route_id", "model", "request_id")}
            for child in value.values():
                found = walk(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = walk(child)
                if found:
                    return found
        return None

    return walk(graph_payload) or {}


def _start_logged_process(args: list[str], cwd: Path, log_path: Path, env: dict[str, str]) -> tuple[subprocess.Popen[str], queue.Queue[str | None]]:
    process = subprocess.Popen(args, cwd=str(cwd), env={**os.environ, **env}, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)
    line_queue: queue.Queue[str | None] = queue.Queue()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def reader() -> None:
        with log_path.open("w", encoding="utf-8") as handle:
            if process.stdout is not None:
                for line in iter(process.stdout.readline, ""):
                    handle.write(line)
                    handle.flush()
                    line_queue.put(line)
            line_queue.put(None)

    threading.Thread(target=reader, daemon=True).start()
    return process, line_queue


def _wait_marker(process: subprocess.Popen[str], line_queue: queue.Queue[str | None], marker: str, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline and process.poll() is None:
        try:
            line = line_queue.get(timeout=0.1)
        except queue.Empty:
            continue
        if line is None:
            break
        if marker in line:
            return True
    return False


def _write_report(root: Path, evidence: LiveEvidence | None, preflight: PreflightResult, reason: str = "") -> int:
    evaluation = evaluate_live_evidence(evidence) if evidence else EvidenceEvaluation(False, (reason or "live_runtime_not_attempted",))
    results = [{"id": result_id, "status": "proved" if evidence and result_id in evidence.result_ids else "missing", "title": result_id, "notes": ""} for result_id in RESULT_IDS]
    report = {"overall_siming_heavenly_runtime_passed": bool(preflight.ok and evaluation.overall), "preflight": {"ok": preflight.ok, "reasons": list(preflight.reasons), "summary": preflight.summary}, "provider_audit": evidence.provider_audit if evidence else {}, "graph": evidence.graph_payload if evidence else {}, "captures": [str(path) for path in evidence.captures] if evidence else [], "results": results, "reasons": list(evaluation.reasons)}
    path = verification_dir(root) / "siming-heavenly-runtime-report.json"
    write_json(path, report)
    write_markdown(verification_dir(root) / "siming-heavenly-runtime-report.md", "Siming Heavenly Runtime", report, "overall_siming_heavenly_runtime_passed")
    print(json.dumps({"report": str(path), "overall": report["overall_siming_heavenly_runtime_passed"], "preflight_ok": preflight.ok, "reasons": list(preflight.reasons) + list(evaluation.reasons)}, ensure_ascii=True))
    return 0 if report["overall_siming_heavenly_runtime_passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    parser.add_argument("--sqlite-path", default=None)
    args = parser.parse_args()
    root = repo_root()
    preflight = live_preflight(root, args.godot_exe)
    if args.preflight:
        print(json.dumps({"ok": preflight.ok, "reasons": list(preflight.reasons), "summary": preflight.summary}, ensure_ascii=True))
        return 0 if preflight.ok else 1
    if not preflight.ok:
        return _write_report(root, None, preflight)
    backend_process = None
    godot_process = None
    try:
        db_path = _owned_db_path(root, args.sqlite_path)
        if db_path.exists():
            db_path.unlink()
        python_exe = resolve_python_exe(args.python_exe)
        godot_exe = resolve_godot_exe(args.godot_exe)
        # Keep the pre-restart authority/observation phase bounded. The
        # post-restart phase switches character cognition to the real provider
        # and proves that the recovered context drives the visible reaction.
        runtime_env = {
            "SIMING_HEAVENLY_MODE": "active",
            "SIMING_LLM_MODE": "http",
            "SIMING_LLM_TIMEOUT_SECONDS": _env("SIMING_LLM_TIMEOUT_SECONDS", "30"),
            "PARALLS_HEAVENLY_GRAPH_PATH": str(db_path),
            "SIMING_HEAVENLY_AUTOTEST": "1",
            "SIMING_HEAVENLY_AUTOTEST_DIR": str(db_path.parent),
            "PHASE0_DEBUG_LOGGING": "1",
            "DIALOGUE_MODE": "http",
            "CHARACTER_MODEL_PROVIDER_KIND": "local",
            "CHARACTER_MODEL_ROUTE_OVERRIDE": "local_only",
        }
        online_character_env = {
            **runtime_env,
            "CHARACTER_MODEL_PROVIDER_KIND": "deepseek",
            "CHARACTER_MODEL_ROUTE_OVERRIDE": "",
            "CHARACTER_MODEL_ENDPOINT": _env("SIMING_LLM_ENDPOINT"),
            "CHARACTER_MODEL_API_KEY": _env("SIMING_LLM_API_KEY"),
            "CHARACTER_MODEL_MODEL": _env("SIMING_LLM_MODEL", "deepseek-chat"),
            "CHARACTER_MODEL_TIMEOUT_SECONDS": _env("SIMING_LLM_TIMEOUT_SECONDS", "30"),
        }
        _, backend_process = ensure_backend(root, python_exe, prefer_fresh_backend=True, env=runtime_env)
        godot_process, lines = _start_logged_process([str(godot_exe), "--path", str(root), "--scene", "res://scenes/phase0/MainDemo.tscn", "--render-thread", "safe"], root, verification_dir(root) / "siming-heavenly-runtime-godot.log", runtime_env)
        if not _wait_marker(godot_process, lines, "siming_heavenly_restart_ready", 300):
            return _write_report(root, None, preflight, "godot_restart_marker_missing")
        if not _wait_for_restart_boundary(db_path):
            return _write_report(root, None, preflight, "restart_boundary_graph_incomplete")
        stop_backend(backend_process)
        backend_process = None
        wait_for_backend_release()
        _, backend_process = ensure_backend(root, python_exe, prefer_fresh_backend=True, env=online_character_env)
        if not _wait_marker(godot_process, lines, "siming_heavenly_godot_complete", 300):
            return _write_report(root, None, preflight, "godot_complete_marker_missing")
        graph_payload = _read_graph_payload(db_path)
        log = read_text(verification_dir(root) / "siming-heavenly-runtime-godot.log")
        captures = tuple(db_path.parent / name for name in CAPTURE_NAMES)
        audit = _provider_audit_from_graph(graph_payload)
        evidence = LiveEvidence(
            _collect_result_ids(log, graph_payload, preflight_ready=preflight.ok),
            captures[0],
            captures[1],
            captures[2],
            audit,
            graph_payload,
        )
        return _write_report(root, evidence, preflight)
    finally:
        if godot_process is not None:
            stop_backend(godot_process)
        stop_backend(backend_process)
        wait_for_backend_release()


if __name__ == "__main__":
    raise SystemExit(main())
