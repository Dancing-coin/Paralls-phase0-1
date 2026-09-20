from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from common import (artifact_path, evidence_revision, repo_root, resolve_python_exe,
                    run_command, verification_dir, write_json)
from evidence import collect_harness_changes, extract_failed_checks
from registry import load_profile_registry, select_profiles
from run_context import attempt_scope, current_run, run_scope


def _resolve_godot_exe(explicit: str | None) -> str | None:
    for value in (explicit, os.environ.get("GODOT_EXE")):
        if value and Path(value).is_file():
            return value
    return None


def _profile_command(profile: str, project_root: Path, python_exe: str,
                     godot_exe: str | None, profiles=None) -> list[str]:
    config = (profiles or load_profile_registry(project_root).profiles)[profile]
    command = [python_exe, str(project_root / str(config["script"]))]
    if config.get("requires_godot"):
        if godot_exe:
            command.extend(["--godot-exe", godot_exe])
        command.extend(["--python-exe", python_exe])
    return command


def _profiles_for_selection(selection: str, registry) -> list[str]:
    return select_profiles(registry, profile=selection)


def _source_dirty_paths(project_root: Path) -> list[str]:
    """列出相对 HEAD 的当前脏路径供定位；不是 dirty 起点的逐文件运行差异。"""
    paths = set()
    for arguments in (['diff', '--name-only', '-z', 'HEAD', '--'],
                      ['ls-files', '--others', '--exclude-standard', '-z']):
        output = subprocess.check_output(['git', *arguments], cwd=project_root, stderr=subprocess.DEVNULL)
        paths.update(path for path in output.decode('utf-8', errors='replace').split('\0') if path)
    return sorted(paths)


def _write_harness_report(project_root: Path, profiles: list[dict[str, object]], *,
                          overall_passed: bool, run_id: str | None = None,
                          suite_id: str | None = None, profile_configs=None,
                          revision: str | None = None, pending=None) -> dict[str, Path]:
    root = verification_dir(project_root)
    run_id = run_id or current_run(project_root).run_id
    report = {"schema_version": 2, "run_id": run_id, "suite_id": suite_id,
              "revision": revision, "overall_harness_passed": overall_passed,
              "cleanup_status": "pending", "profiles": profiles,
              "not_executed": pending or [], **collect_harness_changes(project_root)}
    report['failure_digest_artifacts'] = [
        row['failure_digest'] for row in profiles if row.get('failure_digest')]
    json_path = root / "harness-run-report.json"
    markdown_path = root / "harness-run-report.md"
    manifest_path = root / "run-manifest.json"
    write_json(json_path, report)
    write_json(manifest_path, {**report, "profile_exit_codes": [
        {"profile": row["profile"], "exit_code": row["exit_code"]} for row in profiles]})
    lines = ["# Harness Run Report", "", f"Run: {run_id}; suite: {suite_id}", "",
             "| Profile | Status | Failure |", "| --- | --- | --- |"]
    lines.extend(f"| {row['profile']} | {row.get('status')} | {row.get('failure_kind')} |" for row in profiles)
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path, "manifest": manifest_path, "run_dir": root}


def _publish_artifacts(parent: Path, attempt_root: Path, run_id: str) -> None:
    index_path = parent / ".harness-artifacts.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"run_id": run_id, "artifacts": {}}
    if index.get("run_id") != run_id:
        raise ValueError("artifact index run mismatch")
    artifacts = index["artifacts"]
    for path in attempt_root.iterdir():
        if path.is_file() and not path.name.startswith("."):
            artifacts[path.name] = path.relative_to(parent).as_posix()
    child_index = attempt_root / ".harness-artifacts.json"
    if child_index.exists():
        payload = json.loads(child_index.read_text(encoding="utf-8"))
        if payload.get("run_id") != run_id:
            raise ValueError("child artifact index run mismatch")
        for key, ref in payload["artifacts"].items():
            resolved = (attempt_root / ref).resolve()
            if not resolved.is_relative_to(attempt_root):
                raise ValueError("child artifact reference escapes scope")
            artifacts[key] = resolved.relative_to(parent).as_posix()
    write_json(index_path, index)


def _execute_profile(project_root, run, profile, config, python_exe, godot_exe, revision):
    command = _profile_command(profile, project_root, python_exe, godot_exe, {profile: config})
    result = {"schema_version": 2, "run_id": run.run_id, "profile": profile,
              "revision": revision, "attempt": 0, "attempts": 0, "command": command,
              "exit_code": 1, "status": "failed", "failure_kind": None,
              "failed_checks": [], "duration_seconds": 0.0}
    if config.get("requires_godot") and not godot_exe:
        return {**result, "status": "blocked", "failure_kind": "environment",
                "message": "Godot executable not found. Set GODOT_EXE or pass --godot-exe."}
    parent = verification_dir(project_root)
    max_attempts = max(1, int(config.get("max_attempts", 1)))
    for attempt in range(1, max_attempts + 1):
        start = time.monotonic()
        with attempt_scope(run, profile, attempt) as directory:
            for key in ("failure_digest", "evidence", "message", "failed_checks"):
                result.pop(key, None)
            result.update(attempt=attempt, attempts=attempt, status="failed", failure_kind=None,
                          exit_code=1, failed_checks=[])
            try:
                outcome = run_command(command, project_root, directory / "command.log",
                                      timeout_seconds=float(config.get("timeout_seconds", 900)))
                result["exit_code"] = outcome.returncode
                # 只打印受限诊断尾部；完整受限日志留在本轮目录供显式导出。
                print(outcome.stdout[-4000:], end="")
                failure = "timeout" if outcome.returncode == 124 else "process" if outcome.returncode else None
                ref = str(config.get("result_artifact", ""))
                if ref:
                    prefix = ".harness/verification/"
                    if not ref.startswith(prefix):
                        raise ValueError("result_artifact must use the evidence namespace")
                    report_path = (directory / ref[len(prefix):]).resolve()
                    if not report_path.is_relative_to(directory):
                        raise ValueError("result_artifact escapes attempt")
                    try:
                        payload = json.loads(report_path.read_text(encoding="utf-8"))
                        if not isinstance(payload, dict):
                            raise ValueError("report is not an object")
                        key = config.get("success_key")
                        if key and payload.get(key) is not True:
                            if failure != "timeout":
                                failure = "assertion"
                        elif outcome.returncode and failure != "timeout":
                            failure = "process"
                        result["failed_checks"] = extract_failed_checks(payload)
                        result["evidence"] = {"path": report_path.relative_to(run.evidence_root).as_posix(),
                                              "sha256": hashlib.sha256(report_path.read_bytes()).hexdigest()}
                    except (OSError, ValueError) as exc:
                        failure = "evidence"
                        result["message"] = str(exc)
                if evidence_revision(project_root) != revision:
                    failure = "evidence"
                    result["message"] = "Source inputs changed during verification"
                    try:
                        result["source_dirty_paths"] = _source_dirty_paths(project_root)
                    except (OSError, subprocess.CalledProcessError):
                        result["source_change_diagnostic_error"] = "git_paths_unavailable"
                result["failure_kind"] = failure
                result["status"] = "failed" if failure else "passed"
                if failure and not result["exit_code"]:
                    result["exit_code"] = 1
            except RuntimeError as exc:
                result.update(status="failed", failure_kind="cleanup", message=str(exc))
            except (OSError, ValueError) as exc:
                result.update(exit_code=1, status="blocked", failure_kind="environment", message=str(exc))
            result["duration_seconds"] = round(time.monotonic() - start, 3)
            write_json(directory / "profile-result.json", result)
            if result['status'] != 'passed':
                digest_path = directory / f'{profile}-failure-digest.json'
                write_json(digest_path, {**result, 'summary_status': 'structured_checks_extracted'
                                        if result['failed_checks'] else 'profile_failed_without_structured_checks'})
                result['failure_digest'] = digest_path.relative_to(parent).as_posix()
            if result["status"] == "passed":
                _publish_artifacts(parent, directory, run.run_id)
        print(f"harness_profile={profile} status={result['status']} failure={result['failure_kind']}")
        # 默认不猜测故障是否瞬时；仅显式配置且归类为进程故障的退出码可重试。
        if not (result["failure_kind"] == "process" and result["exit_code"] in config.get("retry_exit_codes", [])):
            break
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--profile")
    selection.add_argument("--suite")
    parser.add_argument("--godot-exe")
    parser.add_argument("--python-exe")
    parser.add_argument("--export-evidence", type=Path)
    args = parser.parse_args()
    project_root = repo_root()
    rows = []
    exit_code = 1
    try:
        registry = load_profile_registry(project_root)
        selected = select_profiles(registry, profile=args.profile, suite=args.suite)
        revision = evidence_revision(project_root)
        with run_scope(project_root, export_to=args.export_evidence) as run:
            try:
                for profile in selected:
                    row = _execute_profile(project_root, run, profile, registry.profiles[profile],
                                           resolve_python_exe(args.python_exe), _resolve_godot_exe(args.godot_exe), revision)
                    rows.append(row)
                    if row["status"] != "passed":
                        break
            except KeyboardInterrupt:
                completed = len(rows)
                rows.append({"schema_version": 2, "run_id": run.run_id, "profile": "<cancelled>",
                             "attempt": 0, "attempts": 0, "exit_code": 130,
                             "status": "cancelled", "failure_kind": "cancelled",
                             "failed_checks": [], "duration_seconds": 0.0,
                             "revision": revision})
                exit_code = 130
                _write_harness_report(project_root, rows, overall_passed=False, run_id=run.run_id,
                                      suite_id=args.suite or args.profile or "boundaries", revision=revision,
                                      pending=selected[completed:])
                raise
            exit_code = 0 if len(rows) == len(selected) and all(row["status"] == "passed" for row in rows) else 1
            _write_harness_report(project_root, rows, overall_passed=exit_code == 0, run_id=run.run_id,
                                  suite_id=args.suite or args.profile or "boundaries", revision=revision,
                                  pending=selected[len(rows):])
        print(f"overall_harness_passed={exit_code == 0} cleanup_status={'passed' if run.owns_root else 'delegated'}")
    except KeyboardInterrupt:
        print("harness_status=cancelled")
        return 130
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"harness_status=failed error={exc}")
        return 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
