from __future__ import annotations

import json
from pathlib import Path


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
    }


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
