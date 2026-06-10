from __future__ import annotations

import re
from pathlib import Path

from common import read_text, repo_root, verification_dir, write_json, write_markdown
from registry import load_profile_registry


SPEC_PLAN_COVERAGE: dict[str, tuple[str, ...]] = {
    "2026-06-08-system-l1-full-phase1-implementation-design.md": (
        "2026-06-08-system-l1-full-phase1-implementation-plan.md",
    ),
    "2026-06-08-system-l1-full-completion-continuation-design.md": (
        "2026-06-08-system-l1-runtime-wired-remaining-emitters-implementation-plan.md",
        "2026-06-08-system-l1-auditory-domain-completion-implementation-plan.md",
        "2026-06-08-system-l1-esm-full-domain-implementation-plan.md",
        "2026-06-08-system-l1-verification-truth-sync-implementation-plan.md",
    ),
    "2026-06-08-system-l1-tactile-emitter-design.md": (
        "2026-06-08-system-l1-remaining-emitter-implementation-plan.md",
    ),
    "2026-06-08-system-l1-thermal-emitter-design.md": (
        "2026-06-08-system-l1-remaining-emitter-implementation-plan.md",
    ),
    "2026-06-08-system-l1-olfactory-emitter-design.md": (
        "2026-06-08-system-l1-remaining-emitter-implementation-plan.md",
    ),
    "2026-06-08-system-l1-physiology-emitter-design.md": (
        "2026-06-08-system-l1-remaining-emitter-implementation-plan.md",
    ),
    "2026-06-08-system-l1-role-state-emitter-design.md": (
        "2026-06-08-system-l1-remaining-emitter-implementation-plan.md",
    ),
}


def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def _extract_index_refs(index_text: str) -> list[str]:
    refs: list[str] = []
    for value in re.findall(r"`([^`]+)`", index_text):
        if " " in value:
            continue
        if value.startswith(("docs/", "backend/", "scripts/", "scenes/")) or value in {"AGENTS.md", "PHASE0_README.md"}:
            refs.append(value.rstrip("/"))
    return refs


def _missing_index_refs(project_root: Path) -> list[str]:
    refs = _extract_index_refs(read_text(project_root / "docs" / "INDEX.md"))
    missing: list[str] = []
    for ref in refs:
        if not (project_root / ref).exists():
            missing.append(ref)
    return missing


def _specs_without_plans(project_root: Path) -> list[str]:
    specs_dir = project_root / "docs" / "superpowers" / "specs"
    plans_dir = project_root / "docs" / "superpowers" / "plans"
    missing: list[str] = []
    for spec in sorted(specs_dir.glob("*-design.md")):
        spec_slug = spec.stem.removesuffix("-design")
        expected_plan_names = (
            f"{spec_slug}-implementation-plan.md",
            f"{spec_slug}-implementation.md",
            *SPEC_PLAN_COVERAGE.get(spec.name, ()),
        )
        if not any((plans_dir / plan_name).exists() for plan_name in expected_plan_names):
            missing.append(str(spec.relative_to(project_root)).replace("\\", "/"))
    return missing


def _undocumented_profiles(project_root: Path) -> list[str]:
    harness_doc = read_text(project_root / "docs" / "harness.md")
    registry = load_profile_registry(project_root)
    profiles = [*registry.profile_order, "all"]
    return [profile for profile in profiles if f"`{profile}`" not in harness_doc]


def _missing_registry_doc_refs(project_root: Path) -> list[str]:
    combined_docs = "\n".join(
        [
            read_text(project_root / "docs" / "INDEX.md"),
            read_text(project_root / "docs" / "harness.md"),
        ]
    )
    required_refs = [
        ".harness/profiles/",
        ".harness/rules/",
        ".harness/verification/runs/",
    ]
    return [ref for ref in required_refs if ref not in combined_docs]


def _agents_md_is_short_entry_map(project_root: Path) -> bool:
    text = read_text(project_root / "AGENTS.md")
    lines = [line for line in text.splitlines() if line.strip()]
    return (
        len(lines) <= 120
        and "docs/INDEX.md" in text
        and "docs/harness.md" in text
        and "python scripts/verification/harness.py --profile all" in text
    )


def evaluate_docs(project_root: Path) -> dict[str, object]:
    missing_index_refs = _missing_index_refs(project_root)
    specs_without_plans = _specs_without_plans(project_root)
    undocumented_profiles = _undocumented_profiles(project_root)
    missing_registry_doc_refs = _missing_registry_doc_refs(project_root)

    results = [
        _result(
            "docs_index_paths_exist",
            "All local paths referenced by docs/INDEX.md exist",
            not missing_index_refs,
            ["docs/INDEX.md"],
            "\n".join(missing_index_refs),
        ),
        _result(
            "superpowers_specs_have_plans",
            "Every Superpowers design spec has a matching implementation plan",
            not specs_without_plans,
            ["docs/superpowers/specs", "docs/superpowers/plans"],
            "\n".join(specs_without_plans),
        ),
        _result(
            "harness_profiles_documented",
            "Every harness profile is documented in docs/harness.md",
            not undocumented_profiles,
            ["docs/harness.md"],
            "\n".join(undocumented_profiles),
        ),
        _result(
            "harness_registry_documented",
            "Harness profile/rule registry and run archive paths are documented",
            not missing_registry_doc_refs,
            ["docs/INDEX.md", "docs/harness.md"],
            "\n".join(missing_registry_doc_refs),
        ),
        _result(
            "agents_md_is_short_entry_map",
            "AGENTS.md stays a short entry map that points to docs and harness",
            _agents_md_is_short_entry_map(project_root),
            ["AGENTS.md", "docs/INDEX.md", "docs/harness.md"],
        ),
    ]
    return {
        "results": results,
        "overall_docs_passed": all(str(entry["status"]) == "proved" for entry in results),
    }


def main() -> int:
    project_root = repo_root()
    report = evaluate_docs(project_root)
    log_dir = verification_dir(project_root)
    json_path = log_dir / "docs-report.json"
    md_path = log_dir / "docs-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Docs Freshness Verification Report", report, "overall_docs_passed")

    print(f"docs_report_json={json_path}")
    print(f"docs_report_md={md_path}")
    print(f"overall_docs_passed={report['overall_docs_passed']}")
    for entry in report["results"]:
        print(f"{entry['id']}={entry['status']}")
    return 0 if report["overall_docs_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
