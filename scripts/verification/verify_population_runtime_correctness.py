"""四个既有正确性 profile 与运行时回归；不代替固定机器性能或 Godot 验收。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory, gettempdir
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from scripts.verification.population_godot_runner import child_environment, object_digest, source_manifest, write_json
from scripts.verification.common import collection_output_path, collection_report_path
from scripts.verification.common import verification_dir
from scripts.verification.run_context import run_scope
from scripts.verification.verify_population_godot_runtime import digest, read_json
from scripts.verification.registry import load_profile_registry


NAME = "population-runtime-correctness"
PROFILES = (
    ("population-data-oriented-persistence", "population-data-oriented-persistence-report.json"),
    ("population-data-oriented-incremental-read", "population-data-oriented-incremental-report.json"),
    ("population-continuous-runtime", "population-continuous-runtime-report.json"),
    ("population-hot-state-equivalence", "population-hot-state-equivalence-report.json"),
)
FOCUSED_TESTS = (
    "test_runtime_execution.py", "test_runtime_execution_transport.py", "test_runtime_process.py",
    "test_runtime_websocket_shutdown.py", "test_process_qos.py",
    "test_runtime_process_transport.py", "test_runtime_asgi.py",
    "test_population_process_cognition_recovery.py",
    "test_runtime_process_generation_recovery.py",
    "test_population_process_outbox_recovery.py", "test_runtime_process_socket_recovery.py",
    "test_population_python_process.py",
    "test_runtime_enqueue_protocol.py", "test_runtime_enqueue_main.py",
    "test_runtime_storage_lease.py", "test_character_activation_lease.py",
    "test_character_dialogue_streaming.py", "test_dialogue_completion_lifecycle.py",
    "test_dialogue_review_fixes.py", "test_cognition_completion_revision.py",
    "test_cognition_wait.py", "test_cognition_poll_clock.py", "test_raw_cognition_main.py",
    "test_cognition_output_route.py", "test_siming_output_connection_main.py",
    "test_scheduled_cognition_source.py", "test_scheduled_cognition_main.py",
    "test_character_cognition_admission.py", "test_character_cognition_coordinator.py",
    "test_character_cognition_driver.py", "test_character_cognition_entry_plan.py",
    "test_character_cognition_main.py", "test_character_cognition_plans.py",
    "test_character_cognition_progress.py", "test_character_cognition_stage_store.py",
    "test_character_agent_l3_planning.py",
    "test_siming_continuation.py", "test_siming_admission.py", "test_siming_coordinator.py",
    "test_siming_candidate_requeue.py",
    "test_siming_driver.py", "test_siming_cognition_main.py", "test_siming_staging_plan.py",
    "test_siming_character_source.py", "test_siming_activation_policy.py", "test_siming_behavior_correlation.py",
    "test_siming_heavenly_runtime_composition.py", "test_siming_context_compiler.py",
    "test_siming_story_graph_runtime.py", "test_siming_heavenly_runtime_tick.py",
    "test_siming_event_pipeline.py", "test_siming_agent_loop_runtime.py",
    "test_character_agent_cognition_writeback.py", "test_character_debug_memory_reads.py",
    "test_character_memory_summary.py",
    "test_character_memory_recall_policy.py",
    "test_character_memory_hot_path_costs.py",
    "test_default_scene_pickup_authority.py",
    "test_websocket_test_support.py", "test_character_session_recovery.py", "test_character_session_sqlite.py",
    "test_sqlite_heavenly_graph_lazy_restore.py", "test_heavenly_graph_revision_summary.py",
    "test_heavenly_graph_current_time.py", "test_inventory_incremental_authority.py",
    "test_inventory_startup_lookup.py", "test_main_cold_start.py",
    "test_gameplay_event_store_lazy_restore.py", "test_gameplay_outbox_refresh.py",
    "test_gameplay_event_store_connection.py", "test_gameplay_store_main_lifecycle.py",
    "test_population_persistence_regression.py", "test_population_persistence_wal.py",
    "test_population_cold_ready_gate.py", "test_population_offline_maintenance.py",
    "test_population_recovery_state.py", "test_population_recovery_measurement.py",
    "test_population_long_session_recovery.py", "test_population_mixed_load_schedule.py",
    "test_population_tier_budgets.py", "test_population_service_isolation_gate.py",
    "test_population_service_owner_probe.py",
    "test_population_service_evidence.py",
    "test_population_checkpoint_closure.py", "test_population_durable_cadence_recovery.py",
    "test_population_clock_profile.py", "test_population_mirror_sources.py",
    "test_population_mirror_subscription.py", "test_population_presentation_projection.py",
    "test_godot_gameplay_mirror_delivery.py", "test_gameplay_mirror_session_access_service.py",
    "test_population_transport_metrics.py", "test_population_godot_evidence.py",
    "test_population_transport_cost.py", "test_mirror_delta_transport.py",
    "test_population_godot_runner.py", "test_population_correctness_gate.py",
    "test_population_correctness_evidence.py", "test_population_closure_aggregation.py",
    "test_population_recovery_evidence.py",
    "test_ask_normalized_history.py", "test_population_ask_audit.py",
    "test_heavenly_graph_candidate_query.py",
    "test_population_harness_evidence.py",
    "test_population_organization_due_source.py",
    "test_population_domain_cadence.py",
    "test_population_batch_settlement_equivalence.py",
    "test_population_conflict_activation.py",
    "test_population_conflict_source.py", "test_gameplay_event_type_cursor.py",
    "test_population_conflict_cadence.py",
    "test_population_mixed_transport.py",
    "test_population_mixed_mirror.py",
    "test_population_mixed_faults.py",
    "test_population_mixed_backend.py",
    "test_population_mixed_provider.py",
    "test_population_mixed_soak.py",
    "test_population_mixed_evidence.py",
    "test_population_mixed_authority.py",
    "test_population_mixed_cognition.py",
    "test_population_mixed_siming.py",
    "test_population_mixed_verification.py",
    "test_population_mixed_matrix.py",
    "test_population_multi_game_capacity.py",
    "test_population_mixed_fixture.py",
)
TIMEOUT_SECONDS = 1200
FOCUSED_PYTEST_ARGS = ("-m", "pytest", "-q", "-o", "junit_family=legacy")


def source_snapshot(root: Path) -> dict:
    runtime = source_manifest(root)
    files = dict(runtime["files"])
    paths = [root / "backend/pyproject.toml", root / "backend/ci-constraints.txt"]
    for folder in ("backend/tests", ".github/workflows", ".harness/profiles"):
        paths.extend(path for path in (root / folder).rglob("*")
                     if path.suffix in {".py", ".json", ".yml", ".yaml"})
    for path in paths:
        if path.is_file():
            files[path.relative_to(root).as_posix()] = digest(path.read_text(encoding="utf-8").encode("utf-8"))
    return {"source_sha256": object_digest(files), "files": files,
            "runtime_source_sha256": runtime.get("source_sha256")}


def git_head(root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def environment() -> dict:
    return {"python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
            "os": platform.platform(), "cpu": platform.processor(), "logical_cpus": os.cpu_count(),
            "architecture": platform.machine(), "godot": "not_run",
            "provider_mode": "controlled_test_providers_no_live_proof",
            "packages": sorted(f"{item.metadata['Name']}=={item.version}"
                               for item in importlib.metadata.distributions())}


def run_logged(command: list[str], *, cwd: Path, env: dict, log: Path, timeout: float) -> int:
    """日志直接落盘；超时仅终止本调用创建的进程树。"""
    with log.open("w", encoding="utf-8") as handle:
        with subprocess.Popen(command, cwd=cwd, env=env, stdout=handle, stderr=subprocess.STDOUT,
                              stdin=subprocess.DEVNULL, start_new_session=os.name != "nt") as process:
            try:
                return process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=15)
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=15)
                handle.write(f"\n[harness] timeout after {timeout:g} seconds\n")
                return 124


def _junit_result(path: Path) -> int:
    cases = ET.parse(path).findall(".//testcase")
    if not cases or any(case.find(name) is not None for case in cases for name in ("failure", "error", "skipped")):
        raise ValueError("focused_junit_failed_empty_or_skipped")
    return len(cases)


def _temporary_parent() -> Path:
    # 嵌套测试会再创建仓库和原始报告，使用系统短临时路径，避免随工作树层级增长。
    path = str(Path(gettempdir()).resolve())
    if os.name == "nt" and not path.startswith("\\\\?\\"):
        path = "\\\\?\\UNC\\" + path[2:] if path.startswith("\\\\") else "\\\\?\\" + path
    return Path(path)


def _business_temporary_path(path: str) -> str:
    # SQLite的as_uri将扩展前缀视为UNC authority；仅业务参数还原，cleanup继续使用原name。
    if os.name == "nt":
        if path.startswith("\\\\?\\UNC\\"):
            return "\\\\" + path[8:]
        if path.startswith("\\\\?\\"):
            return path[4:]
    return path


def run_correctness(root: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    before = source_snapshot(root)
    revision = git_head(root)
    started = datetime.now(timezone.utc).isoformat()
    env = child_environment()
    env.update(PYTHONPATH=os.pathsep.join((str(root), str(root / "backend"))),
               PARALLS_HEAVENLY_GRAPH_PATH=":memory:", CHARACTER_MODEL_PROVIDER_KIND="local",
               SIMING_LLM_MODE="disabled", PYTEST_ADDOPTS="")
    profiles = load_profile_registry(root).profiles
    steps = []
    latest = verification_dir(root) / "correctness-live"
    latest.mkdir(exist_ok=True)
    env.update({key: os.environ[key] for key in ("HARNESS_RUN_ID", "HARNESS_PROJECT_ROOT", "HARNESS_EVIDENCE_ROOT") if key in os.environ})
    env.update(HARNESS_ATTEMPT_ROOT=str(latest), HARNESS_ATTEMPT_ID="correctness-live")
    raw = output / "legacy"
    raw.mkdir()
    for name, report_name in PROFILES:
        step = {"profile": name, "status": "failed", "timeout_seconds": TIMEOUT_SECONDS,
                "started_at": datetime.now(timezone.utc).isoformat()}
        source = latest / report_name
        prefix = report_name.removesuffix("-report.json")
        prior = output / "excluded-prior" / name
        try:
            # 先隔离固定输出；未来mtime或未覆盖的旧文件都不能冒充本轮证据。
            prior.mkdir(parents=True)
            for path in latest.glob(prefix + "*"):
                if path.is_file():
                    shutil.move(str(path), prior / path.name)
            # 使用仓库注册的原 profile，不把新短测替换成旧 profile 的名字。
            command = [sys.executable, str(root / profiles[name]["script"])]
            step["command"] = command
            try:
                step["exit_code"] = run_logged(command, cwd=root, env=env, log=output / f"{name}.log", timeout=TIMEOUT_SECONDS)
            finally:
                # 汇总缺失、失败或超时仍先保留本轮原始日志/XML。
                for path in latest.glob(prefix + "*"):
                    if path.is_file():
                        shutil.copy2(path, raw / path.name)
            if not source.is_file():
                raise ValueError("profile_report_missing_or_stale")
            report = json.loads(source.read_text(encoding="utf-8"))
            if not isinstance(report, dict):
                raise ValueError("profile_report_object_required")
            if step["exit_code"] != 0 or report.get("overall_passed") is not True:
                raise ValueError("profile_did_not_pass")
            step.update(status="passed", report=f"legacy/{report_name}")
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
            step["error"] = f"{type(exc).__name__}: {exc}"
        step["finished_at"] = datetime.now(timezone.utc).isoformat()
        steps.append(step)
    junit = output / "focused.xml"
    command = [sys.executable, *FOCUSED_PYTEST_ARGS,
               f"--junitxml={junit}",
               *(str(root / "backend/tests" / name) for name in FOCUSED_TESTS)]
    step = {"profile": "runtime-focused-tests", "command": command, "status": "failed",
            "timeout_seconds": TIMEOUT_SECONDS, "pytest_workers": 1,
            "started_at": datetime.now(timezone.utc).isoformat()}
    try:
        # Windows 的临时 SQLite 文件名需要短路径；测试数据库不进入发布证据包。
        with TemporaryDirectory(prefix="pc-", dir=_temporary_parent()) as temporary:
            command.extend(["--basetemp", _business_temporary_path(temporary)])
            step["exit_code"] = run_logged(command, cwd=root, env=env, log=output / "focused.log", timeout=TIMEOUT_SECONDS)
        if step["exit_code"] != 0:
            raise ValueError("focused_pytest_failed")
        step.update(test_count=_junit_result(junit), status="passed", junit="focused.xml")
    except (OSError, ValueError, ET.ParseError, subprocess.SubprocessError) as exc:
        step["error"] = f"{type(exc).__name__}: {exc}"
    step["finished_at"] = datetime.now(timezone.utc).isoformat()
    steps.append(step)
    errors = []
    if source_snapshot(root) != before or git_head(root) != revision:
        errors.append("source_or_commit_changed_during_run")
    artifacts = {path.relative_to(output).as_posix(): {"sha256": digest(path.read_bytes()), "bytes": path.stat().st_size}
                 for path in sorted(output.rglob("*")) if path.is_file() and "excluded-prior" not in path.relative_to(output).parts}
    passed = not errors and all(step["status"] == "passed" for step in steps)
    result = {"schema_version": 1, "profile": NAME, "run_id": output.name,
              "base_commit": revision, "source": before, "environment": environment(), "seed": 0,
              "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
              "status": "passed" if passed else "failed", "overall_passed": passed,
              "godot_status": "godot_unverified", "performance_status": "not_run",
              "steps": steps, "raw_artifacts": artifacts, "errors": errors}
    write_json(output / "manifest.json", result)
    return result


def verify_artifacts(directory: Path, *, expected_commit: str) -> dict:
    """核对原始 pytest、四份 profile 数据与冻结命令，不启动测试或引擎。"""
    def load(name):
        value = read_json((directory / name).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("correctness_evidence_object_required")
        return value

    manifest = load("manifest.json")
    if (manifest.get("schema_version") != 1 or manifest.get("profile") != NAME
            or manifest.get("base_commit") != expected_commit or manifest.get("source") != source_snapshot(ROOT)
            or manifest.get("status") != "passed" or manifest.get("overall_passed") is not True
            or manifest.get("errors") != []):
        raise ValueError("correctness_evidence_identity_or_status_invalid")
    actual = {path.relative_to(directory).as_posix(): {"sha256": digest(path.read_bytes()), "bytes": path.stat().st_size}
              for path in directory.rglob("*") if path.is_file() and path.name != "manifest.json"
              and "excluded-prior" not in path.relative_to(directory).parts}
    if actual != manifest.get("raw_artifacts"):
        raise ValueError("correctness_raw_artifacts_mismatch")
    steps = manifest["steps"]
    if [step["profile"] for step in steps] != [name for name, _ in PROFILES] + ["runtime-focused-tests"]:
        raise ValueError("correctness_profile_coverage_invalid")
    prior = datetime.fromisoformat(manifest["started_at"])
    profiles = load_profile_registry(ROOT).profiles
    from pathlib import PurePosixPath, PureWindowsPath
    absolute = lambda value: PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()
    capture_root = None
    reports = {}
    for step, (name, filename) in zip(steps, PROFILES):
        if (step.get("status") != "passed" or type(step.get("exit_code")) is not int or step["exit_code"] != 0
                or step.get("timeout_seconds") != TIMEOUT_SECONDS or step.get("report") != f"legacy/{filename}"
                or len(step.get("command", [])) != 2
                or Path(step["command"][1]).name != Path(profiles[name]["script"]).name):
            raise ValueError("correctness_profile_command_or_exit_invalid")
        script = step["command"][1].replace("\\", "/")
        suffix = "/" + profiles[name]["script"].replace("\\", "/")
        root = script[:-len(suffix)] if script.endswith(suffix) else ""
        if not absolute(root) or ".." in script.split("/") or capture_root not in (None, root):
            raise ValueError("correctness_profile_source_root_invalid")
        capture_root = root
        start, end = (datetime.fromisoformat(step[key]) for key in ("started_at", "finished_at"))
        if not prior <= start <= end or not (directory / f"{name}.log").read_text(encoding="utf-8"):
            raise ValueError("correctness_profile_timing_or_log_invalid")
        prior = end
        report = load(f"legacy/{filename}")
        if report.get("overall_passed") is not True or report.get("git_head", expected_commit) != expected_commit:
            raise ValueError("correctness_legacy_profile_failed")
        reports[name] = report
    focused = steps[-1]
    if (focused.get("status") != "passed" or focused.get("exit_code") != 0 or focused.get("pytest_workers") != 1
            or focused.get("timeout_seconds") != TIMEOUT_SECONDS or focused.get("junit") != "focused.xml"):
        raise ValueError("correctness_focused_run_invalid")
    start, end = (datetime.fromisoformat(focused[key]) for key in ("started_at", "finished_at"))
    if not prior <= start <= end <= datetime.fromisoformat(manifest["finished_at"]):
        raise ValueError("correctness_focused_timing_invalid")
    count = _junit_result(directory / "focused.xml")
    command = focused["command"]
    if not isinstance(command, list) or len(command) != len(FOCUSED_TESTS) + 9 or not all(isinstance(value, str) for value in command):
        raise ValueError("correctness_focused_command_invalid")
    normalized = [value.replace("\\", "/") for value in command]
    first = normalized[7]
    marker = "/backend/tests/"
    origin = first.rsplit(marker, 1)[0] if marker in first else ""
    if (origin != capture_root or not absolute(origin) or not normalized[6].startswith("--junitxml=")
            or not absolute(normalized[6].removeprefix("--junitxml=")) or not absolute(normalized[-1])
            or command[1:6] != list(FOCUSED_PYTEST_ARGS)
            or not normalized[6].endswith("/focused.xml")
            or normalized[7:-2] != [origin + marker + name for name in FOCUSED_TESTS]
            or command[-2] != "--basetemp" or not command[-1]
            or any(".." in value.split("/") for value in normalized[6:])):
        raise ValueError("correctness_focused_command_invalid")
    files = [Path(value).name for value in command[7:-2]]
    cases = ET.parse(directory / "focused.xml").findall(".//testcase")
    observed = {case.get("classname", "").split(".")[1] for case in cases
                if case.get("classname", "").startswith("tests.")}
    if (count != focused.get("test_count") or files != list(FOCUSED_TESTS)
            or not {Path(name).stem for name in FOCUSED_TESTS}.issubset(observed)
            or command[1:3] != ["-m", "pytest"] or not (directory / "focused.log").read_text(encoding="utf-8")):
        raise ValueError("correctness_focused_test_coverage_invalid")
    _verify_legacy_measurements(directory, reports)
    return dict(passed=True, base_commit=expected_commit, profiles=list(reports), test_count=count,
                godot_status="godot_unverified", performance_status="not_run")


def _verify_legacy_measurements(directory: Path, reports: dict) -> None:
    """使用原始分项值复核既有合同，不能只相信四个 overall_passed。"""
    persistence = reports[PROFILES[0][0]]
    if type(persistence.get("test_returncode")) is not int or persistence["test_returncode"] != 0:
        raise ValueError("correctness_persistence_pytest_failed")
    delta = persistence["optimized_probe"]
    if (delta["delete_from_graph_tables"], delta["graph_nodes_inserts"], delta["restored_graph_nodes"]) != (0, 1, 2):
        raise ValueError("correctness_persistence_delta_invalid")
    for field in ("scale_probes", "session_checkpoint_probes"):
        if [row["population"] for row in persistence[field]] != [100, 1000, 10000]:
            raise ValueError("correctness_persistence_population_missing")
        for row in persistence[field]:
            if row["samples"] != 30 or row["passed"] is not True:
                raise ValueError("correctness_persistence_samples_invalid")
            if field == "scale_probes":
                if (row["delete_count"] != 0 or row["whole_graph_snapshot_calls"] != 0
                        or row["undo_entries"] != [1] * 30 or row["sql_changed_rows"] != [5] * 30
                        or row["reopened_node_versions"] != row["population"] + 30
                        or row["sql_write_tables"] != {name: 30 for name in (
                            "graph_nodes", "graph_stream_revisions", "graph_idempotency", "graph_revision_summaries", "graph_current_times")}):
                    raise ValueError("correctness_persistence_write_contract_invalid")
            else:
                n = row["population"]
                integers = ("session_append_bytes", "session_serialized_event_bytes", "current_state_serialized_bytes", "current_state_event_indexes")
                if any(not isinstance(row.get(name), list) or len(row[name]) != 30
                       or any(type(value) is not int or value <= 0 for value in row[name]) for name in integers):
                    raise ValueError("correctness_session_samples_invalid")
                page_size = row.get("sqlite_page_size")
                if (type(page_size) is not int or not 512 <= page_size <= 65536 or page_size & (page_size - 1)
                        or max(row["session_append_bytes"]) > 128 * page_size
                        or max(row["session_serialized_event_bytes"]) - min(row["session_serialized_event_bytes"]) >= 128
                        or row.get("continuity_receipt_statuses") != ["committed"] * 30
                        or any(type(row.get(name)) is not int for name in ("session_reopened_event_count", "runtime_event_count_before_reopen", "runtime_reopened_event_count", "runtime_reopened_revision"))
                        or row["session_reopened_event_count"] != n + 31
                        or row["runtime_event_count_before_reopen"] != n + 61
                        or row["runtime_reopened_event_count"] != n + 61
                        or row["checkpoint_event_indexes"] or row["checkpoint_count"] != 0
                        or row["current_state_contains_history"] != [False] * 30
                        or any(type(value) is not bool for value in row["current_state_contains_history"])
                        or row["runtime_reopened_revision"] != 30
                        or row["current_state_event_indexes"] != list(range(n + 32, n + 62))):
                    raise ValueError("correctness_session_projection_invalid")
    incremental = reports[PROFILES[1][0]]
    if ([row["history"] for row in incremental["history_scenarios"]] != [1000, 10000, 50000]
            or [row["population"] for row in incremental["projection_scale_scenarios"]] != [54, 100, 1000, 10000]
            or incremental["test_returncode"] != 0):
        raise ValueError("correctness_incremental_coverage_invalid")
    for row in incremental["history_scenarios"] + incremental["projection_scale_scenarios"]:
        if row["sample_count"] != 5 or len(row["samples"]) != 5 or not all(sample["published"] for sample in row["samples"]):
            raise ValueError("correctness_incremental_samples_invalid")
        if "history" in row:
            if (row["population"] != 100 or row["tail"] != 10 or row["prefix_checkpoint_sequence"] != row["history"]
                    or row["output_hash"] != row["full_oracle_hash"] or any(
                        (sample["read_events_calls"], sample["read_events_returned"], sample["read_stream_calls"], sample["read_stream_returned"]) != (1, 10, 1, 1)
                        for sample in row["samples"])):
                raise ValueError("correctness_incremental_read_contract_invalid")
        elif (row["input_hash"] != row["output_hash"] or row["published_projection_count"] != row["population"] or row["pipeline_audit_count"] != 5):
            raise ValueError("correctness_incremental_projection_invalid")
    continuous = reports[PROFILES[2][0]]
    junit = directory / "legacy/population-continuous-runtime-tests.xml"
    if _junit_result(junit) != continuous["test_count"] or continuous["exit_code"] != 0:
        raise ValueError("correctness_continuous_junit_invalid")
    observations = {prop.get("name"): prop.get("value") for case in ET.parse(junit).findall(".//testcase")
                    for prop in case.findall("./properties/property")}
    evidence = read_json(observations.get("continuous_runtime_evidence", "{}"))
    rosters = [read_json(value) for name, value in observations.items() if name.startswith("configured_roster_")]
    if (evidence.get("window_count", 0) < 2 or not evidence.get("actor_ids") or len(rosters) < 2
            or any(not row["actor_ids"] or row["default_fill"] or set(row["actor_ids"]) != set(row["b0_actor_ids"])
                   or row["character_core_actor_ids"] for row in rosters)):
        raise ValueError("correctness_continuous_runtime_evidence_invalid")
    hot = reports[PROFILES[3][0]]["scenarios"]
    if [row["population"] for row in hot] != [54, 100, 1000, 10000]:
        raise ValueError("correctness_hot_population_missing")
    for row in hot:
        for field in ("projection_hash", "read_set_digest", "capability_hash", "candidate_hash", "deferred_hash", "owner_receipt_input_hash", "final_hot_hash"):
            values = [row[f"{prefix}_{field}"] for prefix in ("baseline", "serial", "parallel")]
            if len(set(values)) != 1 or not all(isinstance(value, str) and value for value in values):
                raise ValueError("correctness_hot_oracle_mismatch")
        if (row["replay_final_hot_hash"] != row["serial_final_hot_hash"]
                or len({row[name]["result_digest"] for name in ("confirmation", "parallel_confirmation", "replay_confirmation")}) != 1
                or row["owner_receipt_input_count"] != 0 or row["capability_due_count"] != 0):
            raise ValueError("correctness_hot_replay_mismatch")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-artifacts", type=Path)
    parser.add_argument("--require-fresh-commit")
    args = parser.parse_args()
    if args.verify_artifacts:
        if not args.require_fresh_commit:
            parser.error("--verify-artifacts requires --require-fresh-commit")
        print(json.dumps(verify_artifacts(args.verify_artifacts, expected_commit=args.require_fresh_commit)))
        return 0
    with run_scope(ROOT):
        output = args.output or collection_output_path(ROOT, "population-correctness-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
        result = run_correctness(ROOT, output.resolve())
        write_json(collection_report_path(ROOT, output, "population-runtime-correctness-report.json"), result)
    print(f"population_correctness={result['status']} manifest={output / 'manifest.json'}")
    return 0 if result["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
