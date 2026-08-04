from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from common import repo_root, resolve_python_exe, verification_dir, write_json, write_markdown


GAMEPLAY_FOUNDATION_PROFILES = [
    "gameplay-foundation-contract",
    "gameplay-event-replay",
    "gameplay-foundation-event-spine",
    "gameplay-state-groups",
    "gameplay-resource-body",
    "gameplay-status-tags",
    "gameplay-effective-stats",
    "gameplay-ability-affordance",
    "gameplay-inventory",
    "gameplay-possession-equipment",
    "gameplay-ownership-authority",
    "gameplay-economy-authority",
    "gameplay-patch-runtime",
    "godot-gameplay-mirror",
    "adventure-basic",
]

PROFILE_OVERALL_KEYS = {
    "gameplay-foundation-contract": "overall_gameplay_foundation_contract_passed",
    "gameplay-event-replay": "overall_gameplay_event_replay_passed",
    "gameplay-foundation-event-spine": "overall_gameplay_foundation_event_spine_passed",
    "gameplay-state-groups": "overall_gameplay_state_groups_passed",
    "gameplay-resource-body": "overall_gameplay_resource_body_passed",
    "gameplay-status-tags": "overall_gameplay_status_tags_passed",
    "gameplay-effective-stats": "overall_gameplay_effective_stats_passed",
    "gameplay-ability-affordance": "overall_gameplay_ability_affordance_passed",
    "gameplay-inventory": "overall_gameplay_inventory_passed",
    "gameplay-possession-equipment": "overall_gameplay_possession_equipment_passed",
    "gameplay-ownership-authority": "overall_gameplay_ownership_authority_passed",
    "gameplay-economy-authority": "overall_gameplay_economy_authority_passed",
    "gameplay-patch-runtime": "overall_gameplay_patch_runtime_passed",
    "godot-gameplay-mirror": "overall_godot_gameplay_mirror_passed",
    "adventure-basic": "overall_adventure_basic_passed",
}


def _child_report_passed(profile: str, report: dict[str, object]) -> bool:
    overall_key = PROFILE_OVERALL_KEYS.get(profile)
    if overall_key is None or report.get(overall_key) is not True:
        return False
    if profile == "adventure-basic":
        return report.get("adventure_basic_required_scenarios_complete") is True
    return True


def _read_json_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    profile_results: list[dict[str, object]] = []

    for profile in GAMEPLAY_FOUNDATION_PROFILES:
        command = [
            python_exe,
            str(project_root / "scripts" / "verification" / "harness.py"),
            "--profile",
            profile,
            "--python-exe",
            python_exe,
        ]
        if args.godot_exe:
            command.extend(["--godot-exe", args.godot_exe])
        log_path = log_dir / f"gameplay-foundation-all-{profile}.log"
        with log_path.open("w", encoding="utf-8") as log_handle:
            result = subprocess.run(
                command,
                cwd=str(project_root),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

        profile_manifest = _read_json_object(project_root / ".harness" / "profiles" / f"{profile}.json")
        result_artifact = project_root / str(profile_manifest.get("result_artifact", ""))
        report = _read_json_object(result_artifact)
        passed = result.returncode == 0 and _child_report_passed(profile, report)
        profile_results.append(
            {
                "id": profile,
                "title": f"{profile} dependency profile passed its own acceptance gate",
                "status": "proved" if passed else "missing",
                "evidence": [str(log_path), str(result_artifact)] if passed else [str(log_path)],
                "notes": "" if passed else f"exit_code={result.returncode}; child_report_passed={_child_report_passed(profile, report)}",
            }
        )
        if not passed:
            break

    overall = len(profile_results) == len(GAMEPLAY_FOUNDATION_PROFILES) and all(
        entry["status"] == "proved" for entry in profile_results
    )
    report = {
        "overall_gameplay_foundation_all_passed": overall,
        "dependency_profiles": GAMEPLAY_FOUNDATION_PROFILES,
        "results": profile_results,
        "scope": (
            "Fail-closed aggregate of the currently implemented Gameplay Foundation profiles. "
            "A green aggregate proves only what every child report explicitly proves; it does not "
            "upgrade partial adventure-basic, migration, mirror, or Godot evidence into broader closure."
        ),
    }
    json_path = log_dir / "gameplay-foundation-all-report.json"
    markdown_path = log_dir / "gameplay-foundation-all-report.md"
    write_json(json_path, report)
    write_markdown(markdown_path, "Gameplay Foundation Aggregate Report", report, "overall_gameplay_foundation_all_passed")
    print(f"gameplay_foundation_all_report_json={json_path}")
    print(f"gameplay_foundation_all_report_md={markdown_path}")
    print(f"overall_gameplay_foundation_all_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
