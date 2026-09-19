"""离线复验六项验收证据；缺少原始证据或专用复验器时保持 incomplete。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from scripts.verification.population_godot_runner import source_manifest, write_json, _runtime_resource_paths
from scripts.verification.verify_population_godot_runtime import read_json
from scripts.verification.verify_population_runtime_correctness import source_snapshot


# 每个目录必须是完整采集目录，不能用人工 summary 替代。
REQUIRED = {
    "1": ("service-100", "service-1000"),
    "2": ("recovery",),
    "3": ("godot",),
    "4": ("mixed-soak", "multi-game"),
    "5": ("transport-cost", "realtime-short"),
    "6": ("correctness", "mainline", "change-lifecycle", "all"),
}


def _load(path: Path) -> dict:
    value = read_json(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("evidence_object_required")
    return value


def _verification_source_path(name: str) -> bool:
    # 删除后的路径不在当前 snapshot；按同一已声明源域判断，保留无关过程文档。
    fixed = {"project.godot", "scenes/phase0/PopulationProbe.tscn", "backend/pyproject.toml", "backend/ci-constraints.txt",
             *_runtime_resource_paths()[1:]}
    if name in fixed:
        return True
    suffix = Path(name).suffix
    runtime = ("backend/app/", "backend/assets/", "scripts/", "addons/", "assets/characters/profiles/")
    verification = ("backend/tests/", ".github/workflows/", ".harness/profiles/")
    return ("__pycache__" not in Path(name).parts and name.startswith(runtime)
            and suffix in {".py", ".gd", ".json", ".yaml", ".yml", ".cfg", ".tres"}
            or name.startswith(verification) and suffix in {".py", ".json", ".yml", ".yaml"})


def _identity(expected_commit: str) -> tuple[dict, dict]:
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", expected_commit) or revision != expected_commit:
        raise ValueError("current_commit_mismatch")
    runtime, complete = source_manifest(), source_snapshot(ROOT)
    changed = subprocess.check_output(["git", "diff", "--name-only", "--no-renames", "-z", "HEAD"], cwd=ROOT, text=True).split("\0")
    tracked = set(subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT, text=True).split("\0"))
    if any(_verification_source_path(path) for path in changed) or complete["files"].keys() - tracked:
        raise ValueError("uncommitted_verification_source")
    return runtime, complete


def _verify_profile(name: str, directory: Path, revision: str) -> dict:
    # 固定分发名单，不从证据文件加载代码，不启动 backend/provider/Godot。
    if name.startswith("service-"):
        from scripts.verification.verify_population_service_isolation import verify_artifacts
        result = verify_artifacts(directory, expected_commit=revision)
        if result.get("population") != int(name.removeprefix("service-")) or result.get("passed") is not True:
            raise ValueError("service_population_or_threshold_failed")
        return result
    if name == "godot":
        from scripts.verification.verify_population_godot_runtime import verify_artifacts
        result = verify_artifacts(directory)
        if result.get("status") != "passed" or result.get("godot_status") != "runtime_verified":
            raise ValueError("godot_runtime_required")
        return result
    if name == "transport-cost":
        from scripts.verification.verify_population_transport_cost import verify_artifacts
        result = verify_artifacts(directory, expected_commit=revision)
        if result.get("status") != "cost_comparison_passed" or result.get("formal_cost_matrix") is not True:
            raise ValueError("formal_transport_comparison_required")
        return result
    targets = {
        "recovery": ("verify_population_long_session_recovery", "verify_artifacts", {}),
        "correctness": ("verify_population_runtime_correctness", "verify_artifacts", {}),
        "mixed-soak": ("verify_population_mixed_soak", "verify_artifacts", {}),
        "multi-game": ("verify_population_multi_game_capacity", "verify_artifacts", {}),
        "realtime-short": ("verify_population_mixed_soak", "verify_short_artifacts", {}),
        "mainline": ("verify_population_harness_evidence", "verify_artifacts", {"profile": "mainline-unified-runtime"}),
        "change-lifecycle": ("verify_population_harness_evidence", "verify_artifacts", {"profile": "change-lifecycle"}),
        "all": ("verify_population_harness_evidence", "verify_artifacts", {"profile": "all"}),
    }
    module_name, function_name, options = targets[name]
    module = importlib.import_module("scripts.verification." + module_name)
    verifier = getattr(module, function_name, None)
    if verifier is None:
        raise ValueError(f"offline_verifier_missing:{module_name}.{function_name}")
    result = verifier(directory, expected_commit=revision, **options)
    if not isinstance(result, dict) or result.get("passed") is not True:
        raise ValueError("dedicated_evidence_verification_failed")
    return result


def aggregate(root: Path, *, expected_commit: str) -> dict:
    """evidence.json 只定位各目录；通过与否由原始证据专用复验器计算。"""
    root = root.resolve()
    identity_error = None
    try:
        runtime, complete = _identity(expected_commit)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        identity_error = str(exc)
        runtime = complete = {}
    try:
        index = _load(root / "evidence.json")
        if index.get("schema_version") != 1 or not isinstance(index.get("profiles"), dict):
            raise ValueError("evidence_index_schema_invalid")
        locations = index["profiles"]
        if set(locations) - {name for names in REQUIRED.values() for name in names}:
            raise ValueError("unknown_evidence_profile")
    except (OSError, ValueError) as exc:
        index_error = str(exc)
        locations = {}
    else:
        index_error = None
    rows = []
    seen = set()
    for item, names in REQUIRED.items():
        for name in names:
            row = dict(item=item, profile=name, status="incomplete")
            try:
                if identity_error or index_error:
                    raise ValueError(identity_error or index_error)
                relative = locations.get(name)
                if not isinstance(relative, str) or not relative:
                    raise ValueError("evidence_profile_missing")
                directory = (root / relative).resolve()
                if not directory.is_relative_to(root) or directory == root:
                    raise ValueError("evidence_directory_must_be_inside_root")
                if directory in seen:
                    raise ValueError("evidence_directory_reused")
                seen.add(directory)
                row["directory"] = directory.relative_to(root).as_posix()
                manifest = _load(directory / "manifest.json")
                if manifest.get("schema_version") != (2 if name == "recovery" else 1) or manifest.get("base_commit") != expected_commit:
                    raise ValueError("evidence_schema_or_commit_mismatch")
                expected_source = complete if name in {"correctness", "mainline", "change-lifecycle", "all"} else runtime
                if manifest.get("source") != expected_source:
                    raise ValueError("evidence_source_mismatch")
                if manifest.get("status") in {"not_run", "blocked", "static_only", "godot_unverified", "failed", "running"}:
                    raise ValueError("evidence_not_passed")
                row.update(result=_verify_profile(name, directory, expected_commit), status="passed")
            except (OSError, ValueError, KeyError, TypeError, ImportError, ET.ParseError) as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
            rows.append(row)
    # 长时间离线重放期间变码也不能保留通过结果。
    if not identity_error:
        try:
            if _identity(expected_commit) != (runtime, complete):
                raise ValueError("verification_source_changed")
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            identity_error = str(exc)
            for row in rows:
                row.update(status="incomplete", error=identity_error)
    items = {item: "passed" if all(row["status"] == "passed" for row in rows if row["item"] == item) else "incomplete"
             for item in REQUIRED}
    godot = "runtime_verified" if items["3"] == "passed" else "godot_unverified"
    report = dict(schema_version=1, profile="population-runtime-closure", base_commit=expected_commit,
                  checked_at=datetime.now(timezone.utc).isoformat(), source=complete,
                  status="passed" if all(value == "passed" for value in items.values()) else "incomplete",
                  implementation_status="not_inferred_from_evidence", backend_verification=items["1"],
                  godot_status=godot, items=items, profiles=rows)
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "closure-report.json", report)
    lines = ["# 群体运行时六项验收", "", f"总体：{report['status']}；Godot：{godot}", "",
             "实现状态以代码审查台账为准，本报告只复验运行证据。", "",
             "| 项目 | 证据 | 结果 | 缺口 |", "|---|---|---|---|"]
    suite = ET.Element("testsuite", name="population-runtime-closure", tests=str(len(rows)),
                       failures=str(sum(row["status"] != "passed" for row in rows)))
    for row in rows:
        reason = row.get("error", "")
        lines.append(f"| {row['item']} | {row['profile']} | {row['status']} | {reason.replace('|', '/').replace(chr(10), ' ')} |")
        case = ET.SubElement(suite, "testcase", classname=f"closure.item{row['item']}", name=row["profile"])
        if row["status"] != "passed":
            ET.SubElement(case, "failure", message=reason).text = reason
    (root / "closure-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    ET.ElementTree(suite).write(root / "closure-report.xml", encoding="utf-8", xml_declaration=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / ".harness/verification/population-runtime-closure")
    parser.add_argument("--expected-items", default="1,2,3,4,5,6")
    parser.add_argument("--require-godot-runtime", action="store_true", help="六项验收始终要求真实 Godot，此参数显式记录意图")
    parser.add_argument("--require-fresh-commit")
    args = parser.parse_args()
    if args.expected_items != "1,2,3,4,5,6":
        parser.error("六项总验收不可裁剪 expected-items")
    revision = args.require_fresh_commit or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    result = aggregate(args.root, expected_commit=revision)
    print(f"population_closure={result['status']} godot={result['godot_status']}")
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
