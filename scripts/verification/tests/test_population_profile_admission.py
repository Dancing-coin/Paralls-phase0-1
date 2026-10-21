from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/verification"))


@pytest.fixture(autouse=True)
def isolated_harness_environment(monkeypatch):
    for key in ("HARNESS_RUN_ID", "HARNESS_PROJECT_ROOT", "HARNESS_EVIDENCE_ROOT",
                "HARNESS_ATTEMPT_ROOT", "HARNESS_ATTEMPT_ID"):
        monkeypatch.delenv(key, raising=False)


def test_phase3_aggregate_reads_current_run_predecessors_in_separate_attempts() -> None:
    context = importlib.import_module("run_context")
    harness = importlib.import_module("harness")
    verifier = importlib.import_module("verify_phase3_population_continuity")
    common = importlib.import_module("common")
    names = ("phase3a-profile-activation", "phase3b-world-mode-continuity",
             "phase3c-batch-intent-merge", "phase3d-bakery-district-population")
    with context.run_scope(ROOT) as run:
        for name in names:
            with context.attempt_scope(run, name, 1) as directory:
                (directory / f"{name}-report.json").write_text(json.dumps({
                    "overall_passed": True, "replay_hash": f"replay:{name}", "zero_write": True,
                }), encoding="utf-8")
                harness._publish_artifacts(run.evidence_root, directory, run.run_id)
        with context.attempt_scope(run, "phase3-population-continuity", 1):
            assert verifier.main() == 0
            result = json.loads(common.artifact_path(ROOT, ".harness/verification/phase3-population-continuity-report.json")
                                .read_text(encoding="utf-8"))
            assert set(result["phases"]) == set(names)
            assert all(report["overall_passed"] is True for report in result["phases"].values())
            assert result["replay_hash"] == "replay:phase3d-bakery-district-population"


def test_phase3_aggregate_still_refuses_missing_predecessors() -> None:
    context = importlib.import_module("run_context")
    verifier = importlib.import_module("verify_phase3_population_continuity")
    with context.run_scope(ROOT):
        assert verifier.main() == 1


def test_phase3_aggregate_rejects_an_index_from_another_run() -> None:
    context = importlib.import_module("run_context")
    verifier = importlib.import_module("verify_phase3_population_continuity")
    with context.run_scope(ROOT) as run:
        (run.evidence_root / ".harness-artifacts.json").write_text(json.dumps({
            "run_id": "another-run", "artifacts": {},
        }), encoding="utf-8")
        with context.attempt_scope(run, "phase3-population-continuity", 1):
            with pytest.raises(ValueError, match="本轮"):
                verifier.main()


def test_domain_verifier_matches_all_actual_runtime_owner_capabilities() -> None:
    verifier = importlib.import_module("verify_siming_population_domain_owner_adaptation")
    actual, same_store, adapter_contracts = verifier._runtime_owner_ids()
    assert same_store and adapter_contracts
    assert "population:organization-window-due:v1" in actual
    assert actual == verifier.RUNTIME_OWNER_CAPABILITIES
    assert "population:tax-pressure:v1" not in actual


def test_domain_verifier_refuses_an_extra_runtime_owner_capability(monkeypatch) -> None:
    context = importlib.import_module("run_context")
    common = importlib.import_module("common")
    verifier = importlib.import_module("verify_siming_population_domain_owner_adaptation")
    actual, same_store, adapter_contracts = verifier._runtime_owner_ids()
    monkeypatch.setattr(verifier, "_runtime_owner_ids", lambda: (actual | {"population:unadmitted:v1"}, same_store, adapter_contracts))
    monkeypatch.setattr(verifier, "_focused_tests", lambda: (True, "focused tests run separately"))
    with context.run_scope(ROOT):
        assert verifier.main() == 1
        result = json.loads(common.artifact_path(ROOT, ".harness/verification/siming-population-domain-owner-adaptation-report.json")
                            .read_text(encoding="utf-8"))
        assert result["harness_checks"]["only_runtime_admitted_capability_ids_reach_owners"] is False
        assert "population:unadmitted:v1" in result["runtime_owner_capability_ids"]
