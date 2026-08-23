from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from os import environ
from pathlib import Path

from common import repo_root, resolve_python_exe, verification_dir
from evidence import (
    build_failure_digest,
    build_run_diff,
    build_run_manifest,
    collect_harness_changes,
    read_json_object,
)
from registry import load_profile_registry


PROFILE_REGISTRY = load_profile_registry(repo_root())
PROFILES = (*PROFILE_REGISTRY.profiles.keys(), "all")
DEFAULT_GODOT_EXES = (
    Path(r"D:\godot\Godot_v4.6.3-stable_win64.exe"),
    Path(r"E:\涓嬭浇\Godot_v4.6.3-stable_win64.exe\Godot_v4.6.3-stable_win64_console.exe"),
)


def _run(args: list[str], cwd: Path) -> int:
    print(f"harness_run={' '.join(args)}")
    result = subprocess.run(args, cwd=str(cwd), check=False)
    print(f"harness_exit_code={result.returncode}")
    return result.returncode


def _write_harness_report(
    project_root: Path,
    profiles: list[dict[str, object]],
    *,
    overall_passed: bool,
    run_id: str | None = None,
    suite_id: str | None = None,
    profile_configs: dict[str, dict[str, object]] | None = None,
) -> dict[str, Path]:
    run_id = run_id or datetime.now().strftime("run-%Y%m%d-%H%M%S-%f")
    report = {
        "run_id": run_id,
        "suite_id": suite_id,
        "overall_harness_passed": overall_passed,
        "profiles": profiles,
    }
    log_dir = verification_dir(project_root)
    run_dir = log_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = log_dir / "harness-run-report.json"
    markdown_path = log_dir / "harness-run-report.md"
    manifest_path = log_dir / "harness-run-manifest.json"
    baseline_path = log_dir / "baseline.json"
    diff_path = log_dir / "harness-run-diff.json"
    archived_json_path = run_dir / "harness-run-report.json"
    archived_markdown_path = run_dir / "harness-run-report.md"
    archived_manifest_path = run_dir / "run-manifest.json"
    archived_diff_path = run_dir / "harness-run-diff.json"
    previous_baseline = read_json_object(baseline_path)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    archived_json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# Harness Run Report", "", f"- Run ID: `{run_id}`", f"- Suite ID: `{suite_id}`", f"- Overall: `{overall_passed}`", "", "| Profile | Exit Code | Command |", "| --- | --- | --- |"]
    for profile in profiles:
        command = " ".join(str(part) for part in profile["command"])
        lines.append(f"| `{profile['profile']}` | `{profile['exit_code']}` | `{command}` |")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    archived_markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    profile_configs = profile_configs or {}
    failure_digest_artifacts: list[str] = []
    archived_failure_digest_artifacts: list[str] = []
    for profile in profiles:
        if int(profile["exit_code"]) == 0:
            continue
        profile_name = str(profile["profile"])
        digest = build_failure_digest(
            project_root=project_root,
            run_id=run_id,
            profile_result=profile,
            profile_config=profile_configs.get(profile_name, {}),
        )
        digest_path = log_dir / f"{profile_name}-failure-digest.json"
        archived_digest_path = run_dir / f"{profile_name}-failure-digest.json"
        digest_path.write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")
        archived_digest_path.write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")
        failure_digest_artifacts.append(str(digest_path.relative_to(project_root)).replace("\\", "/"))
        archived_failure_digest_artifacts.append(str(archived_digest_path.relative_to(project_root)).replace("\\", "/"))

    harness_change_result = collect_harness_changes(project_root)
    manifest = build_run_manifest(
        run_id=run_id,
        suite_id=suite_id,
        overall_passed=overall_passed,
        profiles=profiles,
        artifacts={
            "latest_report_json": str(json_path),
            "latest_report_markdown": str(markdown_path),
            "archived_report_json": str(archived_json_path),
            "archived_report_markdown": str(archived_markdown_path),
        },
        harness_changes=list(harness_change_result["harness_changes"]),
        harness_change_errors=list(harness_change_result["harness_change_errors"]),
        failure_digest_artifacts=failure_digest_artifacts,
    )
    archived_manifest = build_run_manifest(
        run_id=run_id,
        suite_id=suite_id,
        overall_passed=overall_passed,
        profiles=profiles,
        artifacts={
            "latest_report_json": str(json_path),
            "latest_report_markdown": str(markdown_path),
            "archived_report_json": str(archived_json_path),
            "archived_report_markdown": str(archived_markdown_path),
        },
        harness_changes=list(harness_change_result["harness_changes"]),
        harness_change_errors=list(harness_change_result["harness_change_errors"]),
        failure_digest_artifacts=archived_failure_digest_artifacts,
    )
    diff = build_run_diff(previous_baseline, manifest)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    archived_manifest_path.write_text(json.dumps(archived_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    baseline_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    diff_path.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
    archived_diff_path.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "json": json_path,
        "markdown": markdown_path,
        "manifest": manifest_path,
        "baseline": baseline_path,
        "diff": diff_path,
        "run_dir": run_dir,
    }


def _resolve_godot_exe(explicit: str | None) -> str | None:
    candidates = [explicit, environ.get("GODOT_EXE"), *[str(path) for path in DEFAULT_GODOT_EXES]]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def _profile_command(profile: str, project_root: Path, python_exe: str, godot_exe: str | None, profiles: dict[str, dict[str, object]] | None = None) -> list[str]:
    profiles = profiles or PROFILE_REGISTRY.profiles
    profile_config = profiles.get(profile)
    if profile_config is None:
        raise ValueError(f"Unsupported profile: {profile}")

    command = [python_exe, str(project_root / str(profile_config["script"]))]
    if profile_config.get("requires_godot") and godot_exe:
        command.extend(["--godot-exe", godot_exe])
    if profile_config.get("requires_godot"):
        command.extend(["--python-exe", python_exe])
    return command


def _missing_godot_result(profile: str, project_root: Path, python_exe: str, profiles: dict[str, dict[str, object]]) -> dict[str, object]:
    return {
        "profile": profile,
        "command": _profile_command(profile, project_root, python_exe, None, profiles),
        "exit_code": 1,
        "attempts": 0,
        "max_attempts": 1,
    }


def _result_artifact_exists(project_root: Path, profile_config: dict[str, object]) -> bool:
    artifact = str(profile_config.get("result_artifact", "") or "")
    if artifact == "":
        return False
    path = project_root / artifact
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    for key, value in payload.items():
        if key.startswith("overall_") and isinstance(value, bool):
            return value
    return False


def _profiles_for_selection(selection: str, registry: object) -> list[str]:
    if selection != "all":
        return [selection]
    profile_order = list(getattr(registry, "profile_order"))
    profiles = getattr(registry, "profiles")
    return [
        profile
        for profile in profile_order
        if bool(profiles[profile].get("include_in_all", True))
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=PROFILES, default="boundaries")
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    registry = load_profile_registry(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    godot_exe = _resolve_godot_exe(args.godot_exe)
    profiles = _profiles_for_selection(args.profile, registry)
    profile_results: list[dict[str, object]] = []
    run_id = datetime.now().strftime("run-%Y%m%d-%H%M%S-%f")

    for profile in profiles:
        print(f"harness_profile={profile}")
        profile_config = registry.profiles[profile]
        if profile_config.get("requires_godot") and godot_exe is None:
            profile_results.append(_missing_godot_result(profile, project_root, python_exe, registry.profiles))
            report_paths = _write_harness_report(
                project_root,
                profile_results,
                overall_passed=False,
                run_id=run_id,
                suite_id=args.profile,
                profile_configs=registry.profiles,
            )
            print("harness_error=Godot executable not found. Set GODOT_EXE or pass --godot-exe.")
            print(f"harness_report_json={report_paths['json']}")
            print(f"harness_report_md={report_paths['markdown']}")
            print(f"harness_run_dir={report_paths['run_dir']}")
            return 1

        command = _profile_command(profile, project_root, python_exe, godot_exe, registry.profiles)
        max_attempts = max(1, int(profile_config.get("max_attempts", 1)))
        exit_code = 1
        attempts = 0
        for attempt in range(1, max_attempts + 1):
            attempts = attempt
            exit_code = _run(command, project_root)
            if exit_code == 0:
                break
            if _result_artifact_exists(project_root, profile_config):
                break
        profile_results.append(
            {
                "profile": profile,
                "command": command,
                "exit_code": exit_code,
                "attempts": attempts,
                "max_attempts": max_attempts,
            }
        )
        if exit_code != 0:
            report_paths = _write_harness_report(
                project_root,
                profile_results,
                overall_passed=False,
                run_id=run_id,
                suite_id=args.profile,
                profile_configs=registry.profiles,
            )
            print(f"harness_report_json={report_paths['json']}")
            print(f"harness_report_md={report_paths['markdown']}")
            print(f"harness_run_dir={report_paths['run_dir']}")
            return exit_code
    report_paths = _write_harness_report(
        project_root,
        profile_results,
        overall_passed=True,
        run_id=run_id,
        suite_id=args.profile,
        profile_configs=registry.profiles,
    )
    print(f"harness_report_json={report_paths['json']}")
    print(f"harness_report_md={report_paths['markdown']}")
    print(f"harness_run_dir={report_paths['run_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
