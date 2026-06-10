from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_docs import _specs_without_plans, _undocumented_profiles, evaluate_docs
from common import repo_root


def test_evaluate_docs_proves_index_plan_and_profile_freshness() -> None:
    report = evaluate_docs(repo_root())
    statuses = {entry["id"]: entry["status"] for entry in report["results"]}

    assert statuses["docs_index_paths_exist"] == "proved"
    assert statuses["superpowers_specs_have_plans"] == "proved"
    assert statuses["harness_profiles_documented"] == "proved"
    assert statuses["harness_registry_documented"] == "proved"
    assert statuses["agents_md_is_short_entry_map"] == "proved"


def test_specs_without_plans_accepts_supported_plan_coverages() -> None:
    missing = _specs_without_plans(repo_root())

    assert "docs/superpowers/specs/2026-06-06-l1-raw-fact-emitter-design.md" not in missing
    assert "docs/superpowers/specs/2026-06-08-system-l1-full-phase1-implementation-design.md" not in missing
    assert "docs/superpowers/specs/2026-06-08-system-l1-tactile-emitter-design.md" not in missing
    assert "docs/superpowers/specs/2026-06-08-system-l1-thermal-emitter-design.md" not in missing
    assert "docs/superpowers/specs/2026-06-08-system-l1-olfactory-emitter-design.md" not in missing
    assert "docs/superpowers/specs/2026-06-08-system-l1-physiology-emitter-design.md" not in missing
    assert "docs/superpowers/specs/2026-06-08-system-l1-role-state-emitter-design.md" not in missing
    assert "docs/superpowers/specs/2026-06-08-system-l1-full-completion-continuation-design.md" not in missing


def test_undocumented_profiles_are_loaded_from_project_registry(tmp_path: Path) -> None:
    profile_dir = tmp_path / ".harness" / "profiles"
    profile_dir.mkdir(parents=True)
    (profile_dir / "custom.json").write_text(
        '{"schema_version": 1, "name": "custom", "order": 10, "script": "scripts/verification/custom.py", "requires_godot": false}',
        encoding="utf-8",
    )
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "harness.md").write_text("Profile: `custom`\nProfile: `all`\n", encoding="utf-8")

    assert _undocumented_profiles(tmp_path) == []
