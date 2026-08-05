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
            rows = connection.execute("SELECT node_id, payload_json FROM graph_nodes").fetchall()
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


def _collect_result_ids(log: str, graph_payload: dict[str, object]) -> set[str]:
    found = {result_id for result_id in RESULT_IDS if result_id in log}

    def walk(value: object) -> None:
        if isinstance(value, str):
            found.update(result_id for result_id in RESULT_IDS if result_id == value or result_id in value)
        elif isinstance(value, dict):
            for key, child in value.items():
                walk(key)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(graph_payload)
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
        runtime_env = {"SIMING_HEAVENLY_MODE": "active", "SIMING_LLM_MODE": "http", "PARALLS_HEAVENLY_GRAPH_PATH": str(db_path), "SIMING_HEAVENLY_AUTOTEST": "1", "SIMING_HEAVENLY_AUTOTEST_DIR": str(db_path.parent)}
        _, backend_process = ensure_backend(root, python_exe, prefer_fresh_backend=True, env=runtime_env)
        godot_process, lines = _start_logged_process([str(godot_exe), "--headless", "--path", str(root), "--scene", "res://scenes/phase0/MainDemo.tscn", "--render-thread", "safe"], root, verification_dir(root) / "siming-heavenly-runtime-godot.log", runtime_env)
        if not _wait_marker(godot_process, lines, "siming_heavenly_restart_ready", 90):
            return _write_report(root, None, preflight, "godot_restart_marker_missing")
        stop_backend(backend_process)
        backend_process = None
        wait_for_backend_release()
        _, backend_process = ensure_backend(root, python_exe, prefer_fresh_backend=True, env=runtime_env)
        if not _wait_marker(godot_process, lines, "siming_heavenly_godot_complete", 90):
            return _write_report(root, None, preflight, "godot_complete_marker_missing")
        graph_payload = _read_graph_payload(db_path)
        log = read_text(verification_dir(root) / "siming-heavenly-runtime-godot.log")
        captures = tuple(db_path.parent / name for name in CAPTURE_NAMES)
        audit = _provider_audit_from_graph(graph_payload)
        evidence = LiveEvidence(_collect_result_ids(log, graph_payload), captures[0], captures[1], captures[2], audit, graph_payload)
        return _write_report(root, evidence, preflight)
    finally:
        if godot_process is not None:
            stop_backend(godot_process)
        stop_backend(backend_process)
        wait_for_backend_release()


if __name__ == "__main__":
    raise SystemExit(main())
