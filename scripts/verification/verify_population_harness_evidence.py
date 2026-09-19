"""封存原 mainline/change-lifecycle/all harness；离线复验不启动引擎或后端。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scripts.verification.aggregate_population_closure import _identity
from scripts.verification.harness import _profile_command, _profiles_for_selection
from scripts.verification.population_godot_runner import child_environment, write_json
from scripts.verification.registry import load_profile_registry
from scripts.verification.verify_population_godot_runtime import read_json
from scripts.verification.verify_population_runtime_correctness import environment, git_head, run_logged


PROFILES = ("mainline-unified-runtime", "change-lifecycle", "all")
RAW_SUFFIXES = {".json", ".jsonl", ".ndjson", ".xml", ".log", ".txt", ".md", ".csv", ".png"}
TIMEOUT = 10800

# 原 mainline producer 的九个必要分项与固定产物名。
MAINLINE_EVIDENCE = {
    "mainline_world_runtime_suite": ("world_runtime", "mainline-unified-world-runtime.log", None),
    "asset_runtime_kimodo_contracts": ("asset_runtime_kimodo_contracts", "mainline-unified-asset-runtime.log", None),
    "runtime_cadence_continuity_observatory": ("runtime_cadence_continuity_observatory", "mainline-unified-continuity-observatory.log", None),
    "actor_local_perception": ("actor_local_perception", "mainline-unified-actor-local.log", "actor-local-perception-report.json"),
    "autonomous_social_contact": ("autonomous_social_contact", "mainline-unified-autonomous-contact.log", "autonomous-social-contact-report.json"),
    "character_agent_execution": ("character_agent_execution", "mainline-unified-character-agent-execution.log", "character-agent-execution-report.json"),
    "phase1_slice": ("phase1_slice", "mainline-unified-phase1-slice.log", "phase1-slice-report.json"),
    "authority_settlement_writeback": ("authority_settlement_writeback", "mainline-unified-settlement-writeback.log", None),
    "continuity_recovery_runtime": ("continuity_recovery_runtime", "mainline-unified-continuity-recovery.log", None),
}


def _required_results(payload, required):
    rows = payload.get("results")
    if (not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows)
            or len({row.get("id") for row in rows}) != len(rows)):
        raise ValueError("harness_required_result_invalid")
    index = {row.get("id"): row for row in rows}
    if any(index.get(key, {}).get("status") != "proved" for key in required):
        raise ValueError("harness_required_result_missing")
    return index


def _profile_report(name, payload, *, origin, python, godot, registry, raw_path, inputs, ancestors):
    flags = [value for key, value in payload.items() if key.startswith("overall_") and isinstance(value, bool)]
    if not flags or not all(flags):
        raise ValueError(f"harness_profile_result_failed:{name}")

    def reference(value):
        if not isinstance(value, str):
            raise ValueError("harness_evidence_reference_invalid")
        relative = PurePosixPath(value.replace("\\", "/"))
        if PureWindowsPath(value).drive or relative.is_absolute():
            try:
                relative = PurePosixPath(_path(value).relative_to(origin).as_posix())
            except ValueError:
                raise ValueError("harness_evidence_reference_outside_root") from None
        if ".." in relative.parts:
            raise ValueError("harness_evidence_reference_outside_root")
        if relative.is_relative_to(".harness/verification"):
            return raw_path("artifacts/" + relative.relative_to(".harness/verification").as_posix())
        if relative.as_posix() not in inputs:
            raise ValueError("harness_evidence_input_not_pinned")
        return None

    if name == "change-lifecycle":
        from scripts.verification.check_change_lifecycle import REQUIRED_RULE_IDS
        rows = _required_results(payload, REQUIRED_RULE_IDS)
        for key in REQUIRED_RULE_IDS:
            evidence = rows[key].get("evidence")
            if not isinstance(evidence, list) or not evidence:
                raise ValueError("harness_required_result_evidence_missing")
            for value in evidence:
                reference(value)
    elif name == "mainline-unified-runtime":
        rows = _required_results(payload, MAINLINE_EVIDENCE)
        artifacts = payload.get("artifacts", {})
        for key, (artifact, log, report) in MAINLINE_EVIDENCE.items():
            expected = [str(origin / ".harness/verification" / log)]
            if artifacts.get(artifact + "_log") != expected[0]:
                raise ValueError("harness_required_result_evidence_missing")
            if report is not None:
                expected.append(str(origin / ".harness/verification" / report))
                if artifacts.get(artifact + "_report") != expected[-1]:
                    raise ValueError("harness_required_result_evidence_missing")
            if rows[key].get("evidence") != expected:
                raise ValueError("harness_required_result_evidence_missing")
            for value in expected:
                path = reference(value)
                if path.suffix == ".json":
                    _profile_report(key, _load(path), origin=origin, python=python, godot=godot,
                        registry=registry, raw_path=raw_path, inputs=inputs, ancestors=ancestors)
    elif name == "gameplay-patch-runtime":
        from scripts.verification.verify_gameplay_patch_runtime import TEST_GROUPS
        rows = _required_results(payload, [key for key, _, _ in TEST_GROUPS])
        logs = payload.get("artifacts", {}).get("pytest_logs", {})
        for key, _, _ in TEST_GROUPS:
            expected = str(origin / ".harness/verification" / f"gameplay-patch-runtime-{key}.log")
            if logs.get(key) != expected or rows[key].get("evidence") != [expected]:
                raise ValueError("harness_required_result_evidence_missing")
            reference(expected)
    elif name in {"gameplay-foundation-all", "embodied-interaction-foundation-all"}:
        from scripts.verification.verify_gameplay_foundation_all import GAMEPLAY_FOUNDATION_PROFILES, _child_report_passed
        profiles = GAMEPLAY_FOUNDATION_PROFILES
        if name == "gameplay-foundation-all":
            if payload.get("dependency_profiles") != profiles:
                raise ValueError("harness_dependency_profiles_invalid")
        else:
            from scripts.verification import verify_embodied_interaction_foundation_all as embodied
            phases = dict(phase_6_gate_profile=embodied.PHASE_6_GATE_PROFILE,
                phase_6_session_profile=embodied.PHASE_6_SESSION_PROFILE,
                phase_7_handoff_profile=embodied.PHASE_7_HANDOFF_PROFILE,
                phase_7_carry_place_profile=embodied.PHASE_7_CARRY_PLACE_PROFILE)
            if (payload.get("phase_profiles") != embodied.PHASE_PROFILES
                    or any(payload.get(key) != value for key, value in phases.items())
                    or payload.get("phase_6_status") != "gate_satisfied"
                    or any(payload.get(key) != "backend_websocket_and_godot_live_runtime_verified" for key in (
                        "phase_6_interaction_session_status", "phase_7_handoff_status", "phase_7_carry_place_status"))):
                raise ValueError("harness_dependency_profiles_invalid")
            profiles = [*embodied.PHASE_PROFILES, *phases.values()]
        rows = _required_results(payload, profiles)
        for child in profiles:
            log = str(origin / ".harness/verification" / f"{name}-{child}.log")
            evidence = [log]
            if name == "gameplay-foundation-all":
                report = str(origin / registry.profiles[child]["result_artifact"])
                evidence.append(report)
                if not _child_report_passed(child, _load(reference(report))):
                    raise ValueError("harness_child_report_failed")
            if rows[child].get("evidence") != evidence:
                raise ValueError("harness_required_result_evidence_missing")
            _check_run(reference(log).read_text(encoding="utf-8").splitlines(), child,
                origin=origin, python=python, godot=godot, registry=registry, raw_path=raw_path,
                inputs=inputs, ancestors=ancestors)
    else:
        # 保留各叶子 producer 的异构验收规则；只绑定其明确列出的文件产物。
        for value in payload.get("artifacts", {}).values():
            if isinstance(value, str):
                reference(value)


def _hash(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def harness_inputs() -> dict:
    """广泛 profile 还读取文档、规则和场景；保留输入摘要，不封存私密配置。"""
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT, text=True).split("\0")
    paths = {ROOT / name for name in names if name and not name.startswith((".harness/verification/", ".superpowers/", ".runtime/"))
             and not Path(name).name.startswith(".env")}
    for folder in ("docs", ".harness/rules", ".harness/templates", ".harness/changes"):
        paths.update(path for path in (ROOT / folder).rglob("*") if path.suffix in {".md", ".json", ".yaml", ".yml"})
    text_suffixes = {".py", ".gd", ".md", ".tscn", ".tres", ".godot", ".json", ".yaml", ".yml", ".cfg",
                     ".ini", ".toml", ".txt", ".sql", ".csv", ".xml", ".ps1", ".sh"}
    return {path.relative_to(ROOT).as_posix(): (
        hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        if path.suffix in text_suffixes else _hash(path)) for path in sorted(paths) if path.is_file()}


def _load(path: Path) -> dict:
    value = read_json(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("harness_evidence_object_required")
    return value


def _path(value: str):
    path = PureWindowsPath(value) if PureWindowsPath(value).drive else PurePosixPath(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("harness_original_absolute_path_required")
    return path


def _files(directory: Path, *, exclude: Path | None = None) -> dict:
    # 明确允许的产物类型；不复制/摘要 SQLite、WAL、SHM 或旧存档。
    files = {}
    for path in directory.rglob("*"):
        if (not path.is_file() or path.suffix not in RAW_SUFFIXES or path.is_symlink()
                or path.name.endswith(".sqlite3.gameplay.json")
                or (exclude is not None and path.resolve().is_relative_to(exclude))):
            continue
        with path.open("rb") as handle:
            if handle.read(16) == b"SQLite format 3\x00":
                continue
        files[path.relative_to(directory).as_posix()] = path.stat().st_mtime_ns, path.stat().st_size
    return files


def _raw(directory: Path) -> dict:
    return {name: {"sha256": _hash(directory / name), "bytes": size}
            for name, (_, size) in _files(directory).items() if name != "manifest.json"}


def _expected_command(profile, origin, python, godot):
    command = [python, str(origin / "scripts/verification/harness.py"), "--profile", profile, "--python-exe", python]
    if godot:
        command += ["--godot-exe", godot]
    return command


def _check(directory: Path, manifest: dict, profile: str) -> dict:
    """只读捕获的原 stdout、archive 和各 profile 报告，不把包装器状态当证据。"""
    if profile not in PROFILES or manifest.get("profile") != profile:
        raise ValueError("harness_profile_mismatch")
    origin = _path(manifest["project_root"])
    python = str(_path(manifest["python_executable"]))
    godot = manifest.get("godot_executable")
    registry = load_profile_registry(ROOT)
    selected = _profiles_for_selection(profile, registry)
    needs_godot = any(registry.profiles[name].get("requires_godot") for name in selected)
    if needs_godot:
        if not godot or str(_path(godot)) != godot or not re.fullmatch(r"[0-9a-f]{64}", manifest.get("godot_sha256", "")):
            raise ValueError("explicit_godot_executable_required")
    elif godot is not None:
        raise ValueError("unexpected_godot_executable")
    if (manifest.get("command") != _expected_command(profile, origin, python, godot)
            or type(manifest.get("exit_code")) is not int or manifest["exit_code"] != 0
            or type(manifest.get("timeout_seconds")) is not int or not 1 <= manifest["timeout_seconds"] <= TIMEOUT):
        raise ValueError("harness_command_or_exit_invalid")
    start, end = (datetime.fromisoformat(manifest[key]) for key in ("started_at", "finished_at"))
    if start.tzinfo is None or end.tzinfo is None or not start <= end:
        raise ValueError("harness_timing_invalid")
    raw = _raw(directory)
    if raw != manifest.get("raw_files"):
        raise ValueError("harness_raw_files_mismatch")
    def raw_path(name):
        path = directory / name
        if name not in raw or not path.resolve().is_relative_to(directory):
            raise ValueError("harness_required_raw_file_missing")
        return path
    return _check_run(raw_path("process.log").read_text(encoding="utf-8").splitlines(), profile,
        origin=origin, python=python, godot=godot, registry=registry, raw_path=raw_path,
        inputs=manifest.get("harness_inputs", {}), ancestors=())


def _check_run(lines, profile, *, origin, python, godot, registry, raw_path, inputs, ancestors):
    if profile in ancestors:
        raise ValueError("harness_dependency_cycle")
    ancestors = (*ancestors, profile)
    selected = _profiles_for_selection(profile, registry)
    needs_godot = any(registry.profiles[name].get("requires_godot") for name in selected)
    runs = [line.removeprefix("harness_run_dir=") for line in lines if line.startswith("harness_run_dir=")]
    if len(runs) != 1:
        raise ValueError("fresh_harness_archive_missing")
    run_path = _path(runs[0])
    if run_path.parent != origin / ".harness/verification/runs":
        raise ValueError("harness_archive_outside_original_root")
    run_id = run_path.name
    archive = f"artifacts/runs/{run_id}"
    report = _load(raw_path(archive + "/harness-run-report.json"))
    original_manifest = _load(raw_path(archive + "/run-manifest.json"))
    if (report.get("run_id") != run_id or report.get("suite_id") != profile
            or report.get("overall_harness_passed") is not True
            or [row.get("profile") for row in report.get("profiles", [])] != selected
            or original_manifest.get("schema_version") != 1 or original_manifest.get("run_id") != run_id
            or original_manifest.get("suite_id") != profile or original_manifest.get("overall_harness_passed") is not True
            or original_manifest.get("profile_exit_codes") != [dict(profile=name, exit_code=0) for name in selected]):
        raise ValueError("harness_archive_coverage_or_result_invalid")
    controls = [line for line in lines if line.startswith(("harness_profile=", "harness_run=", "harness_exit_code="))]
    index = 0
    for row, name in zip(report["profiles"], selected):
        config = registry.profiles[name]
        expected = _profile_command(name, origin, python, godot, registry.profiles)
        attempts, maximum = row.get("attempts"), max(1, int(config.get("max_attempts", 1)))
        if (row.get("command") != expected or type(row.get("exit_code")) is not int or row["exit_code"] != 0
                or type(attempts) is not int or not 1 <= attempts <= maximum or row.get("max_attempts") != maximum):
            raise ValueError("harness_profile_command_attempts_invalid")
        if controls[index:index + 1] != [f"harness_profile={name}"]:
            raise ValueError("harness_profile_log_coverage_invalid")
        index += 1
        for attempt in range(attempts):
            pair = controls[index:index + 2]
            if (len(pair) != 2 or pair[0] != f"harness_run={' '.join(expected)}"
                    or not re.fullmatch(r"harness_exit_code=-?\d+", pair[1])):
                raise ValueError("harness_attempt_log_missing")
            code = int(pair[1].split("=", 1)[1])
            if (code == 0) != (attempt == attempts - 1):
                raise ValueError("harness_attempt_exit_mismatch")
            index += 2
        required = config.get("result_artifact")
        if name in {"mainline-unified-runtime", "change-lifecycle"}:
            required = f".harness/verification/{name}-report.json"
        if required:
            relative = PurePosixPath(str(required).replace("\\", "/"))
            if not relative.is_relative_to(".harness/verification") or ".." in relative.parts:
                raise ValueError("harness_result_artifact_outside_verification")
            payload = _load(raw_path("artifacts/" + relative.relative_to(".harness/verification").as_posix()))
            _profile_report(name, payload, origin=origin, python=python, godot=godot,
                registry=registry, raw_path=raw_path, inputs=inputs, ancestors=ancestors)
    if index != len(controls):
        raise ValueError("harness_unaccounted_attempts")
    return dict(passed=True, profile=profile, profiles=len(selected), run_id=run_id,
                godot_status="harness_verified" if needs_godot else "godot_unverified")


def verify_artifacts(directory: Path, *, expected_commit: str, profile: str) -> dict:
    directory = directory.resolve()
    manifest = _load(directory / "manifest.json")
    _, source = _identity(expected_commit)
    inputs = harness_inputs()
    if (manifest.get("schema_version") != 1 or manifest.get("base_commit") != expected_commit
            or manifest.get("status") != "passed" or manifest.get("source") != source
            or manifest.get("harness_inputs") != inputs):
        raise ValueError("harness_evidence_identity_or_status_invalid")
    result = _check(directory, manifest, profile)
    if _identity(expected_commit)[1] != source or harness_inputs() != inputs:
        raise ValueError("harness_source_changed_during_verification")
    return result


def collect(output: Path, *, profile: str, godot_exe: Path | None = None, timeout: int = TIMEOUT) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    latest = ROOT / ".harness/verification"
    latest.mkdir(parents=True, exist_ok=True)
    manifest = dict(schema_version=1, profile=profile, status="running", godot_status="godot_unverified",
                    started_at=datetime.now(timezone.utc).isoformat(), project_root=str(ROOT.resolve()),
                    python_executable=sys.executable, godot_executable=None, environment=environment(),
                    timeout_seconds=timeout, raw_files={})
    write_json(output / "manifest.json", manifest)
    prior = _files(latest, exclude=output)
    prior_runs = {path.name for path in (latest / "runs").glob("*") if path.is_dir()}
    try:
        if profile not in PROFILES or type(timeout) is not int or not 1 <= timeout <= TIMEOUT:
            raise ValueError("unsupported_profile_or_timeout")
        revision = git_head(ROOT)
        _, source = _identity(revision)
        inputs = harness_inputs()
        manifest.update(base_commit=revision, source=source, harness_inputs=inputs)
        if profile != "change-lifecycle":
            if godot_exe is None or not godot_exe.is_file():
                raise ValueError("explicit_godot_executable_required")
            manifest.update(godot_executable=str(godot_exe.resolve()), godot_sha256=_hash(godot_exe))
        command = _expected_command(profile, ROOT.resolve(), sys.executable, manifest["godot_executable"])
        manifest["command"] = command
        env = child_environment()
        env.update(PYTHONPATH=os.pathsep.join((str(ROOT), str(ROOT / "backend"))), PYTHONUNBUFFERED="1",
                   PYTEST_ADDOPTS="", CHARACTER_MODEL_PROVIDER_KIND="local", SIMING_LLM_MODE="disabled")
        if manifest["godot_executable"]:
            # 既有不带requires_godot的聚合profile还会启动子harness；显式路径需沿原环境继承。
            env["GODOT_EXE"] = manifest["godot_executable"]
        write_json(output / "manifest.json", manifest)
        manifest["exit_code"] = run_logged(command, cwd=ROOT, env=env, log=output / "process.log", timeout=timeout)
    except Exception as exc:
        manifest["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        # 失败也保留本轮已生成的原始文件；不移动或删除其他会话的旧证据。
        try:
            for name, stamp in _files(latest, exclude=output).items():
                if prior.get(name) == stamp:
                    continue
                target = output / "artifacts" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(latest / name, target)
            manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
            manifest["raw_files"] = _raw(output)
            if "error" not in manifest:
                result = _check(output, manifest, profile)
                if result["run_id"] in prior_runs:
                    raise ValueError("fresh_harness_archive_required")
                if _identity(revision)[1] != source or harness_inputs() != inputs:
                    raise ValueError("harness_source_changed_during_capture")
                manifest.update(status="passed", godot_status=result["godot_status"])
        except Exception as exc:
            manifest["error"] = f"{type(exc).__name__}: {exc}"
        if "error" in manifest:
            manifest["status"] = "failed"
        write_json(output / "manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--godot-exe", type=Path, help="mainline/all仅在准备验证Godot的机器显式提供")
    parser.add_argument("--timeout-seconds", type=int, default=TIMEOUT)
    parser.add_argument("--verify-artifacts", type=Path)
    parser.add_argument("--require-fresh-commit")
    args = parser.parse_args()
    if args.verify_artifacts:
        if not args.require_fresh_commit:
            parser.error("离线复验必须提供 --require-fresh-commit")
        result = verify_artifacts(args.verify_artifacts, expected_commit=args.require_fresh_commit, profile=args.profile)
        print(f"harness_evidence_passed={result['passed']}")
        return 0
    output = args.output or ROOT / ".harness/verification" / (args.profile + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    result = collect(output, profile=args.profile, godot_exe=args.godot_exe, timeout=args.timeout_seconds)
    print(f"harness_evidence_manifest={output / 'manifest.json'}")
    print(f"harness_evidence_status={result['status']}")
    if result.get("error"):
        print(result["error"])
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
