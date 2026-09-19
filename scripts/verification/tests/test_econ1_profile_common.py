from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import econ1_profile_common as profile_common
from common import write_json
from harness import _publish_artifacts
from run_context import attempt_scope, run_scope


def test_econ1_profile_consumes_a_same_run_published_predecessor(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setattr(profile_common, "repo_root", lambda: project_root)

    with run_scope(project_root) as run:
        with attempt_scope(run, "phase1c-frost-farm", 1) as predecessor_scope:
            write_json(
                predecessor_scope / "phase1c-frost-farm-report.json",
                {"overall_phase1c_frost_farm_passed": True},
            )
            _publish_artifacts(run.evidence_root, predecessor_scope, run.run_id)

        with attempt_scope(run, "econ1-construction-production", 1) as consumer_scope:
            exit_code = profile_common.run_profile(
                name="econ1-construction-production",
                overall_key="overall_econ1_construction_production_passed",
                predecessor="phase1c-frost-farm-report.json",
                checks={"real_business_check": True},
            )
            report = json.loads(
                (consumer_scope / "econ1-construction-production-report.json").read_text(encoding="utf-8")
            )

    assert exit_code == 0
    assert report["predecessor"]["passed"] is True
    assert report["overall_econ1_construction_production_passed"] is True
