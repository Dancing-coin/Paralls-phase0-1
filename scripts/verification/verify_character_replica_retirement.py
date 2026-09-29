from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from common import (
    repo_root,
    resolve_godot_exe,
    resolve_python_exe,
    run_command,
    verification_dir,
    write_json,
)

MATRIX = "docs/character/character-replica-retirement-matrix-2026-09-29.md"
MARKER = "character_replica_retirement_probe:"
SHELL_PATHS = {
    "scripts/character/CharacterReplica.gd",
    "scripts/presentation/character/CharacterReplica.gd",
    "scenes/phase0/CharacterReplica.tscn",
    "scenes/phase0/ValidationCharacterReplica.tscn",
}
STATIC_TESTS = [
    "scripts/verification/tests/test_character_action_foundation_progressive_replacement.py",
    "backend/tests/test_character_replica_convergence_static.py",
]


def inventory(root: Path) -> tuple[list[str], str]:
    paths = sorted(
        path.relative_to(root).as_posix()
        for directory in ("scenes", "scripts", "backend")
        for path in (root / directory).rglob("*")
        if path.is_file() and path.suffix in {".gd", ".tscn", ".py"}
    )
    digest = hashlib.sha256()
    callers = []
    for name in paths:
        content = (root / name).read_bytes()
        if b"CharacterReplica" not in content and b"legacy_character_replica" not in content:
            continue
        callers.append(name)
        digest.update((name + "\n").encode("utf-8"))
        digest.update(content)
        digest.update(b"\0")
    return callers, digest.hexdigest()


def matrix_rows(root: Path) -> list[dict[str, object]]:
    source = (root / MATRIX).read_text(encoding="utf-8")
    match = re.search(r"```json\s*(\[.*?\])\s*```", source, re.DOTALL)
    if match is None:
        raise ValueError("missing JSON caller matrix")
    rows = json.loads(match.group(1))
    fields = {
        "caller_path", "category", "current_state", "target_entry",
        "owner_lane", "compatibility_allowed", "evidence_command",
    }
    if not isinstance(rows, list) or any(not isinstance(row, dict) or not fields <= row.keys() for row in rows):
        raise ValueError("invalid caller matrix rows")
    names = [row["caller_path"] for row in rows]
    if len(names) != len(set(names)):
        raise ValueError("duplicate caller matrix row")
    for row in rows:
        name = str(row["caller_path"])
        category = row["category"]
        allowed = row["compatibility_allowed"]
        if category == "compatibility" and name not in SHELL_PATHS:
            raise ValueError(f"invalid compatibility classification: {name}")
        if category == "comment_only":
            path = root / name
            if path.exists():
                active_lines = [line for line in path.read_text(encoding="utf-8").splitlines()
                                if not line.lstrip().startswith("#")]
                if "CharacterReplica" in "\n".join(active_lines) or "legacy_character_replica" in "\n".join(active_lines):
                    raise ValueError(f"invalid comment_only classification: {name}")
        if allowed and category not in {"compatibility", "migration_test"}:
            raise ValueError(f"invalid compatibility allowance: {name}")
    return rows


def evaluate(root: Path, marker: dict[str, object] | None, static_passed: bool) -> dict[str, object]:
    callers, source_digest = inventory(root)
    matrix_digest = hashlib.sha256((root / MATRIX).read_bytes()).hexdigest() if (root / MATRIX).exists() else ""
    errors = []
    try:
        rows = matrix_rows(root)
        registered = {str(row["caller_path"]) for row in rows}
    except (OSError, ValueError, TypeError) as exc:
        registered = set()
        errors.append(str(exc))
    unregistered = sorted(set(callers) - registered)
    if unregistered:
        errors.append("unregistered_callers")
    if not static_passed:
        errors.append("static_tests_failed")
    if marker is None:
        errors.append("missing_godot_marker")
    else:
        for key in (
            "active_scene_instances", "runtime_script_references", "runtime_replica_lookups",
            "provider_lookups", "direct_body_writers_outside_motor",
            "direct_animation_writers_outside_controller", "compatibility_call_count",
            "backend_production_references",
        ):
            if marker.get(key) != 0:
                errors.append(f"nonzero_{key}")
        if marker.get("source_digest") != source_digest:
            errors.append("source_digest_mismatch")
        if marker.get("matrix_digest") != matrix_digest:
            errors.append("matrix_digest_mismatch")
        if marker.get("unregistered_callers") != unregistered:
            errors.append("godot_inventory_mismatch")
        if marker.get("passed") is not True:
            errors.append("godot_retirement_gate_failed")
    return {
        "source_digest": source_digest,
        "matrix_digest": matrix_digest,
        "registered_callers": len(registered),
        "active_reference_files": len(callers),
        "unregistered_callers": unregistered,
        "godot_marker": marker,
        "static_tests_passed": static_passed,
        "failed_checks": errors,
        "overall_character_replica_retirement_passed": not errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe")
    parser.add_argument("--python-exe")
    args = parser.parse_args()
    root = repo_root()
    output = verification_dir(root)
    python = resolve_python_exe(args.python_exe)
    static = run_command(
        [python, "-m", "pytest", "-q", *STATIC_TESTS],
        root, output / "character-replica-retirement-static.log", timeout_seconds=180,
    )
    marker = None
    godot_error = ""
    try:
        godot = resolve_godot_exe(args.godot_exe)
        if godot is None:
            raise FileNotFoundError("Godot executable unavailable")
        runtime = run_command(
            [str(godot), "--headless", "--path", str(root), "--scene",
             "res://scenes/phase0/StreetCombatDemo.tscn", "--quit-after", "120"],
            root, output / "character-replica-retirement-godot.log",
            env={"PARALLS_STREET_PROBE": "5"}, timeout_seconds=120,
        )
        for line in runtime.stdout.splitlines():
            if line.startswith(MARKER):
                marker = json.loads(line[len(MARKER):])
        if runtime.returncode != 0:
            godot_error = f"godot_exit_{runtime.returncode}"
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        godot_error = str(exc)
    report = evaluate(root, marker, static.returncode == 0)
    if godot_error:
        report["failed_checks"].append(godot_error)
        report["overall_character_replica_retirement_passed"] = False
    report_path = output / "character-replica-retirement-report.json"
    write_json(report_path, report)
    print(f"character_replica_retirement_report_json={report_path}")
    print(f"overall_character_replica_retirement_passed={report['overall_character_replica_retirement_passed']}")
    print(f"failed_checks={report['failed_checks']}")
    return 0 if report["overall_character_replica_retirement_passed"] else 1


if __name__ == "__main__":
    from run_context import run_scope

    with run_scope(Path(__file__).resolve().parents[2]):
        sys.exit(main())
