from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from os import environ
from pathlib import Path

from common import repo_root, resolve_python_exe, verification_dir
from evidence import build_run_diff, build_run_manifest, read_json_object
from registry import load_profile_registry


PROFILE_REGISTRY = load_profile_registry(repo_root())
PROFILES = (*PROFILE_REGISTRY.profile_order, "all")
DEFAULT_GODOT_EXES = (
    Path(r"D:\godot\Godot_v4.6.3-stable_win64.exe"),
    Path(r"E:\涓嬭浇\Godot_v4.6.3-stable_win64.exe\Godot_v4.6.3-stable_win64_console.exe"),
)


def _run(args: list[str], cwd: Path) -> int:
    print(f"harness_run={' '.join(args)}")
    result = subprocess.run(args, cwd=str(cwd), check=False)
    print(f"harness_exit_code={result.returncode}")
    return result.returncode


def _write_harness_report(project_root: Path, profiles: list[dict[str, object]], *, overall_passed: bool, run_id: str | None = None) -> dict[str, Path]:
    run_id = run_id or datetime.now().strftime("run-%Y%m%d-%H%M%S-%f")
    report = {
        "run_id": run_id,
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

    lines = ["# Harness Run Report", "", f"- Run ID: `{run_id}`", f"- Overall: `{overall_passed}`", "", "| Profile | Exit Code | Command |", "| --- | --- | --- |"]
    for profile in profiles:
        command = " ".join(str(part) for part in profile["command"])
        lines.append(f"| `{profile['profile']}` | `{profile['exit_code']}` | `{command}` |")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    archived_markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = build_run_manifest(
        run_id=run_id,
        overall_passed=overall_passed,
        profiles=profiles,
        artifacts={
            "latest_report_json": str(json_path),
            "latest_report_markdown": str(markdown_path),
            "archived_report_json": str(archived_json_path),
            "archived_report_markdown": str(archived_markdown_path),
        },
    )
    diff = build_run_diff(previous_baseline, manifest)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    archived_manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
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
    profiles = registry.profile_order if args.profile == "all" else [args.profile]
    profile_results: list[dict[str, object]] = []
    run_id = datetime.now().strftime("run-%Y%m%d-%H%M%S-%f")

    for profile in profiles:
        print(f"harness_profile={profile}")
        command = _profile_command(profile, project_root, python_exe, godot_exe, registry.profiles)
        exit_code = _run(command, project_root)
        profile_results.append({"profile": profile, "command": command, "exit_code": exit_code})
        if exit_code != 0:
            report_paths = _write_harness_report(project_root, profile_results, overall_passed=False, run_id=run_id)
            print(f"harness_report_json={report_paths['json']}")
            print(f"harness_report_md={report_paths['markdown']}")
            print(f"harness_run_dir={report_paths['run_dir']}")
            return exit_code
    report_paths = _write_harness_report(project_root, profile_results, overall_passed=True, run_id=run_id)
    print(f"harness_report_json={report_paths['json']}")
    print(f"harness_report_md={report_paths['markdown']}")
    print(f"harness_run_dir={report_paths['run_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
