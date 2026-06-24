from __future__ import annotations

import json
from pathlib import Path

ACTIVE_HARNESS_CHANGE_STATUS = "active"
KNOWN_HARNESS_CHANGE_STATUSES = {"active", "superseded", "rejected"}


def _relative_path(project_root: Path, path: Path) -> str:
    return str(path.relative_to(project_root)).replace("\\", "/")


def read_json_object(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def build_run_manifest(
    *,
    run_id: str,
    overall_passed: bool,
    profiles: list[dict[str, object]],
    artifacts: dict[str, str],
    harness_changes: list[dict[str, object]] | None = None,
    harness_change_errors: list[dict[str, object]] | None = None,
    failure_digest_artifacts: list[str] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "run_id": run_id,
        "overall_harness_passed": overall_passed,
        "profile_exit_codes": [
            {
                "profile": str(profile["profile"]),
                "exit_code": int(profile["exit_code"]),
            }
            for profile in profiles
        ],
        "artifacts": artifacts,
        "harness_changes": harness_changes or [],
        "harness_change_errors": harness_change_errors or [],
        "failure_digest_artifacts": failure_digest_artifacts or [],
    }


def collect_harness_changes(project_root: Path) -> dict[str, object]:
    changes_dir = project_root / ".harness" / "changes"
    changes: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    if not changes_dir.exists():
        return {"harness_changes": changes, "harness_change_errors": errors}

    for path in sorted(changes_dir.glob("*.json")):
        relative = _relative_path(project_root, path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            errors.append({"path": relative, "error": "invalid_json"})
            continue
        if not isinstance(payload, dict):
            errors.append({"path": relative, "error": "not_json_object"})
            continue
        status = str(payload.get("status", ""))
        if status not in KNOWN_HARNESS_CHANGE_STATUSES:
            errors.append({"path": relative, "error": "invalid_status"})
            continue
        if status != ACTIVE_HARNESS_CHANGE_STATUS:
            continue
        change_id = payload.get("id")
        title = payload.get("title")
        if not isinstance(change_id, str) or change_id == "":
            errors.append({"path": relative, "error": "missing_id"})
            continue
        if not isinstance(title, str) or title == "":
            errors.append({"path": relative, "error": "missing_title"})
            continue
        verification_profiles = payload.get("verification_profiles", [])
        if not isinstance(verification_profiles, list):
            errors.append({"path": relative, "error": "invalid_verification_profiles"})
            continue
        changes.append(
            {
                "id": change_id,
                "title": title,
                "status": status,
                "path": relative,
                "verification_profiles": [str(profile) for profile in verification_profiles],
            }
        )
    return {"harness_changes": changes, "harness_change_errors": errors}


def extract_failed_checks(report: dict[str, object]) -> list[dict[str, object]]:
    failed: list[dict[str, object]] = []
    results = report.get("results", [])
    if not isinstance(results, list):
        return failed
    passing_statuses = {"proved", "pass", "passed", "ok", "true"}
    for entry in results:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status", "")).lower()
        if status in passing_statuses:
            continue
        check_id = entry.get("id")
        if not isinstance(check_id, str) or check_id == "":
            continue
        evidence = entry.get("evidence", [])
        failed.append(
            {
                "id": check_id,
                "status": str(entry.get("status", "")),
                "evidence": evidence if isinstance(evidence, list) else [],
            }
        )
    return failed


def build_failure_digest(
    *,
    project_root: Path,
    run_id: str,
    profile_result: dict[str, object],
    profile_config: dict[str, object],
) -> dict[str, object]:
    profile = str(profile_result["profile"])
    report_path = _resolve_profile_report(project_root, profile_config)
    source_artifacts = _source_artifacts(project_root, report_path)
    report = read_json_object(report_path) if report_path is not None else None
    failed_checks = extract_failed_checks(report or {})
    trace_refs = _runtime_trace_refs(project_root, profile)
    if report_path is None:
        summary_status = "profile_failed_without_report"
    elif not failed_checks:
        summary_status = "profile_failed_without_structured_checks"
    else:
        summary_status = "structured_checks_extracted"
    return {
        "schema_version": 1,
        "run_id": run_id,
        "profile": profile,
        "status": "failed",
        "exit_code": int(profile_result["exit_code"]),
        "summary_status": summary_status,
        "primary_report": _relative_path(project_root, report_path) if report_path is not None else None,
        "failed_checks": failed_checks,
        "runtime_trace_refs": trace_refs,
        "source_artifacts": source_artifacts,
    }


def _resolve_profile_report(project_root: Path, profile_config: dict[str, object]) -> Path | None:
    artifact = str(profile_config.get("result_artifact", "") or "")
    if artifact == "":
        return None
    path = project_root / artifact
    return path if path.exists() else None


def _source_artifacts(project_root: Path, report_path: Path | None) -> list[str]:
    if report_path is None:
        return []
    artifacts = [_relative_path(project_root, report_path)]
    markdown_path = report_path.with_suffix(".md")
    if markdown_path.exists():
        artifacts.append(_relative_path(project_root, markdown_path))
    return artifacts


def _runtime_trace_refs(project_root: Path, profile: str) -> list[str]:
    trace_path = project_root / ".harness" / "verification" / f"{profile}-runtime-trace.ndjson"
    if trace_path.exists():
        return [_relative_path(project_root, trace_path)]
    return []


def build_run_diff(previous: dict[str, object] | None, current: dict[str, object]) -> dict[str, object]:
    previous_profiles = _profile_exit_codes(previous)
    current_profiles = _profile_exit_codes(current)
    all_profiles = sorted({*previous_profiles, *current_profiles})
    changes = [
        {
            "profile": profile,
            "previous_exit_code": previous_profiles.get(profile),
            "current_exit_code": current_profiles.get(profile),
        }
        for profile in all_profiles
        if previous_profiles.get(profile) != current_profiles.get(profile)
    ]
    return {
        "schema_version": 1,
        "previous_run_id": previous.get("run_id") if previous else None,
        "current_run_id": current["run_id"],
        "overall_changed": None if previous is None else previous.get("overall_harness_passed") != current.get("overall_harness_passed"),
        "profile_exit_code_changes": changes,
    }


def _profile_exit_codes(manifest: dict[str, object] | None) -> dict[str, int]:
    if not manifest:
        return {}
    exit_codes: dict[str, int] = {}
    for entry in manifest.get("profile_exit_codes", []):
        if not isinstance(entry, dict):
            continue
        exit_codes[str(entry["profile"])] = int(entry["exit_code"])
    return exit_codes
