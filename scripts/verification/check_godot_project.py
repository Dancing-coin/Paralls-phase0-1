from __future__ import annotations

import re
from pathlib import Path

from common import read_text, repo_root, verification_dir, write_json, write_markdown


RESOURCE_PATTERN = re.compile(r"res://([^\"'\)\],\s]+)")
GENERATED_ARTIFACT_ROOT = ".harness/verification/"


def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def _resource_to_path(project_root: Path, resource: str) -> Path:
    return project_root / resource.removeprefix("res://")


def _project_resources(project_root: Path) -> list[tuple[Path, str]]:
    resources: list[tuple[Path, str]] = []
    scan_roots = [project_root / "project.godot", project_root / "scenes", project_root / "scripts"]
    for root in scan_roots:
        paths = [root] if root.is_file() else list(root.rglob("*"))
        for path in paths:
            if not path.is_file() or path.suffix not in {".godot", ".tscn", ".gd", ".tres"}:
                continue
            text = read_text(path)
            for match in RESOURCE_PATTERN.finditer(text):
                resource = match.group(1)
                if resource.startswith(GENERATED_ARTIFACT_ROOT):
                    continue
                resources.append((path, "res://" + resource))
    return resources


def _main_scene(project_root: Path) -> str:
    match = re.search(r'run/main_scene="(res://[^"]+)"', read_text(project_root / "project.godot"))
    return match.group(1) if match else ""


def _autoload_resources(project_root: Path) -> list[str]:
    resources: list[str] = []
    in_autoload = False
    for line in read_text(project_root / "project.godot").splitlines():
        stripped = line.strip()
        if stripped == "[autoload]":
            in_autoload = True
            continue
        if in_autoload and stripped.startswith("[") and stripped.endswith("]"):
            break
        if in_autoload and "res://" in stripped:
            match = re.search(r'"?\*?(res://[^"]+)"?', stripped)
            if match:
                resources.append(match.group(1))
    return resources


def _blend_files(project_root: Path) -> list[str]:
    return sorted(
        str(path.relative_to(project_root)).replace("\\", "/")
        for path in project_root.rglob("*.blend")
        if ".godot" not in path.parts
    )


def _blend_import_is_noninteractive(project_root: Path) -> bool:
    if not _blend_files(project_root):
        return True
    return bool(re.search(r"(?m)^import/blender/enabled=false$", read_text(project_root / "project.godot")))


def evaluate_godot_project(project_root: Path) -> dict[str, object]:
    main_scene = _main_scene(project_root)
    autoloads = _autoload_resources(project_root)
    blend_files = _blend_files(project_root)
    missing_autoloads = [resource for resource in autoloads if not _resource_to_path(project_root, resource).exists()]
    missing_resources = [
        f"{source.relative_to(project_root)} -> {resource}"
        for source, resource in _project_resources(project_root)
        if not _resource_to_path(project_root, resource).exists()
    ]

    results = [
        _result(
            "project_main_scene_exists",
            "Godot project declares a main scene and the scene exists",
            bool(main_scene) and _resource_to_path(project_root, main_scene).exists(),
            [main_scene] if main_scene else [],
            main_scene or "run/main_scene missing",
        ),
        _result(
            "autoload_scripts_exist",
            "Godot autoload entries point at existing scripts",
            bool(autoloads) and not missing_autoloads,
            autoloads,
            "\n".join(missing_autoloads),
        ),
        _result(
            "scene_resource_paths_exist",
            "Godot scenes and scripts reference existing res:// resources",
            not missing_resources,
            ["project.godot", "scenes", "scripts"],
            "\n".join(missing_resources),
        ),
        _result(
            "blend_import_is_noninteractive",
            "Godot .blend import is disabled when Blender is not a project prerequisite",
            _blend_import_is_noninteractive(project_root),
            ["project.godot", *blend_files],
            "\n".join(blend_files),
        ),
    ]
    return {
        "results": results,
        "overall_godot_project_passed": all(str(entry["status"]) == "proved" for entry in results),
    }


def main() -> int:
    project_root = repo_root()
    report = evaluate_godot_project(project_root)
    log_dir = verification_dir(project_root)
    json_path = log_dir / "godot-project-report.json"
    md_path = log_dir / "godot-project-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Godot Project Verification Report", report, "overall_godot_project_passed")

    print(f"godot_project_report_json={json_path}")
    print(f"godot_project_report_md={md_path}")
    print(f"overall_godot_project_passed={report['overall_godot_project_passed']}")
    for entry in report["results"]:
        print(f"{entry['id']}={entry['status']}")
    return 0 if report["overall_godot_project_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
