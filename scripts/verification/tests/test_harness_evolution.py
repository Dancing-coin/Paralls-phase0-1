from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evolution import (
    analyze_harness_evolution,
    build_candidate_from_analysis,
    evaluate_harness_evolution,
    load_candidate_manifests,
    load_evolution_config,
    load_replay_set,
    write_candidate_manifest,
)
from common import verification_dir
from run_context import run_scope


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _candidate() -> dict[str, object]:
    return {
        "schema_version": 1,
        "id": "evo-reviewed",
        "status": "proposed",
        "mutation_type": "docs_gate",
        "risk_tier": "sandbox-edit",
        "source_failures": ["run-1"],
        "hypothesis": "需要验证诊断改进是否有效。",
        "proposed_changes": [{"path": "scripts/verification/check_docs.py", "summary": "补充诊断"}],
        "replay_set": "default",
        "promotion_checks": ["docs"],
        "requires_human_approval": False,
    }


def _reviewed_candidate(project_root: Path) -> tuple[dict[str, object], Path]:
    _write_json(project_root / ".harness/evolution/config.json", {
        "schema_version": 1, "max_runs_to_analyze": 20, "profiles_in_scope": ["docs"],
        "allowed_mutation_types": ["docs_gate"], "promotion_requires_profiles": ["docs"],
    })
    replay_path = project_root / ".harness/evolution/replay-sets/default.json"
    _write_json(replay_path, {
        "schema_version": 1, "id": "default",
        "profile_cases": [{"profile": "docs", "expected_artifacts": ["docs-report.json"]}],
        "regression_guards": ["profile_exit_code_does_not_worsen"],
    })
    candidate = {
        **_candidate(), "status": "evaluated", "lifecycle_stage": "promotion-ready",
        "baseline_revision": "baseline-sha", "candidate_revision": "candidate-sha",
        "evaluation_set_digest": hashlib.sha256(replay_path.read_bytes()).hexdigest(),
        "effectiveness": "accepted",
    }
    review_path = project_root / ".harness/evolution/evaluations/reviewed.json"
    _write_json(review_path, {
        "schema_version": 1, "candidate_id": candidate["id"],
        "baseline_revision": candidate["baseline_revision"],
        "candidate_revision": candidate["candidate_revision"],
        "evaluation_set_digest": candidate["evaluation_set_digest"],
        "effectiveness": "accepted", "overall_evaluation_passed": True,
        "acceptance_reason": "固定目标指标改善，核心任务无回归。",
        "criteria_unchanged": True,
        "results": [
            {"run_id": "baseline-run", "profile": "docs", "revision": "baseline-sha", "status": "passed", "exit_code": 0},
            {"run_id": "candidate-run", "profile": "docs", "revision": "candidate-sha", "status": "passed", "exit_code": 0},
        ],
    })
    review_ref = review_path.relative_to(project_root).as_posix()
    candidate["qa_review_artifacts"] = [review_ref]
    candidate["qa_review_artifact_digests"] = {review_ref: hashlib.sha256(review_path.read_bytes()).hexdigest()}
    return candidate, review_path


def test_default_analysis_ignores_implicit_repository_history(tmp_path: Path) -> None:
    _write_json(tmp_path / ".harness/verification/runs/old/run-manifest.json", {
        "run_id": "old", "profile_exit_codes": [{"profile": "docs", "exit_code": 1}],
    })
    report = analyze_harness_evolution(tmp_path, {})
    assert report["history_status"] == "insufficient_history"
    assert report["effectiveness"] == "not_evaluated"
    assert report["candidate_recommendations"] == []


def test_old_candidate_is_not_evaluated(tmp_path: Path) -> None:
    write_candidate_manifest(tmp_path, _candidate())
    candidates, errors = load_candidate_manifests(tmp_path, allowed_mutation_types=["docs_gate"])
    assert errors == []
    assert candidates[0]["effectiveness"] == "not_evaluated"


@pytest.mark.parametrize("change", [
    "missing", "digest", "revision", "candidate_id", "failed", "missing_results", "unexecuted",
    "changed_criteria", "set_digest", "claim_only", "status_bypass", "run_id_reuse", "candidate_failed",
])
def test_promotion_rejects_invalid_evaluation_evidence(tmp_path: Path, change: str) -> None:
    candidate, review_path = _reviewed_candidate(tmp_path)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    if change == "missing":
        review_path.unlink()
    elif change == "digest":
        review_path.write_text("{}", encoding="utf-8")
    else:
        if change == "revision":
            review["candidate_revision"] = "another-sha"
        elif change == "candidate_id":
            review["candidate_id"] = "another-candidate"
        elif change == "failed":
            review["overall_evaluation_passed"] = False
            review["effectiveness"] = "rejected"
        elif change == "missing_results":
            review["results"] = []
        elif change == "unexecuted":
            review["results"][1]["status"] = "blocked"
        elif change == "changed_criteria":
            review["criteria_unchanged"] = False
        elif change == "set_digest":
            candidate["evaluation_set_digest"] = "a" * 64
            review["evaluation_set_digest"] = "a" * 64
        elif change == "claim_only":
            candidate["status"] = "proposed"
            candidate["lifecycle_stage"] = "proposed"
            review["overall_evaluation_passed"] = False
        elif change == "status_bypass":
            candidate["status"] = "promoted"
            candidate["lifecycle_stage"] = "proposed"
            review["overall_evaluation_passed"] = False
        elif change == "run_id_reuse":
            review["results"][1]["run_id"] = review["results"][0]["run_id"]
        elif change == "candidate_failed":
            review["results"][1].update(status="failed", exit_code=1)
        _write_json(review_path, review)
        ref = review_path.relative_to(tmp_path).as_posix()
        candidate["qa_review_artifact_digests"][ref] = hashlib.sha256(review_path.read_bytes()).hexdigest()
    write_candidate_manifest(tmp_path, candidate)
    candidates, errors = load_candidate_manifests(tmp_path, allowed_mutation_types=["docs_gate"])
    assert candidates == []
    assert errors


def test_promotion_accepts_matching_reviewed_evaluation(tmp_path: Path) -> None:
    candidate, _ = _reviewed_candidate(tmp_path)
    write_candidate_manifest(tmp_path, candidate)
    candidates, errors = load_candidate_manifests(tmp_path, allowed_mutation_types=["docs_gate"])
    assert errors == []
    assert candidates[0]["effectiveness"] == "accepted"


def test_promotion_cannot_omit_configured_required_checks(tmp_path: Path) -> None:
    candidate, _ = _reviewed_candidate(tmp_path)
    write_candidate_manifest(tmp_path, candidate)
    _write_json(tmp_path / ".harness/evolution/config.json", {
        "schema_version": 1, "max_runs_to_analyze": 20, "profiles_in_scope": ["docs"],
        "allowed_mutation_types": ["docs_gate"], "promotion_requires_profiles": ["docs", "harness-evolution"],
    })
    candidates, errors = load_candidate_manifests(tmp_path, allowed_mutation_types=["docs_gate"])
    assert candidates == []
    assert any("harness-evolution" in error for error in errors)


def test_rejected_evaluation_keeps_failure_reason_without_allowing_promotion(tmp_path: Path) -> None:
    candidate, review_path = _reviewed_candidate(tmp_path)
    candidate.update(status="rejected", lifecycle_stage="rejected", effectiveness="rejected")
    review = json.loads(review_path.read_text(encoding="utf-8"))
    review.update(effectiveness="rejected", overall_evaluation_passed=False, rejection_reason="候选任务发生回归。")
    review["results"][1].update(status="failed", exit_code=1)
    _write_json(review_path, review)
    ref = review_path.relative_to(tmp_path).as_posix()
    candidate["qa_review_artifact_digests"][ref] = hashlib.sha256(review_path.read_bytes()).hexdigest()
    write_candidate_manifest(tmp_path, candidate)
    candidates, errors = load_candidate_manifests(tmp_path, allowed_mutation_types=["docs_gate"])
    assert errors == []
    assert candidates[0]["effectiveness"] == "rejected"


@pytest.mark.parametrize("ref", ["../outside.json", ".harness/../outside.json", "C:/outside.json", "\\\\server\\outside.json"])
def test_promotion_rejects_unsafe_artifact_reference(tmp_path: Path, ref: str) -> None:
    candidate, _ = _reviewed_candidate(tmp_path)
    candidate["qa_review_artifacts"] = [ref]
    candidate["qa_review_artifact_digests"] = {ref: "a" * 64}
    write_candidate_manifest(tmp_path, candidate)
    candidates, errors = load_candidate_manifests(tmp_path, allowed_mutation_types=["docs_gate"])
    assert candidates == []
    assert any("unsafe" in error for error in errors)


@pytest.mark.parametrize("candidate_id", ["../escape", "nested/name", "absolute", "..\\escape"])
def test_candidate_writer_rejects_path_traversal(tmp_path: Path, candidate_id: str) -> None:
    if candidate_id == "absolute":
        candidate_id = (tmp_path / "escape").as_posix()
    with pytest.raises(ValueError, match="candidate id"):
        write_candidate_manifest(tmp_path, {**_candidate(), "id": candidate_id})


def test_candidate_rejects_mutation_scope_traversal(tmp_path: Path) -> None:
    candidate = _candidate()
    candidate["proposed_changes"] = [{"path": "scripts/verification/../../backend/app.py", "summary": "越界"}]
    write_candidate_manifest(tmp_path, candidate)
    candidates, errors = load_candidate_manifests(tmp_path, allowed_mutation_types=["docs_gate"])
    assert candidates == []
    assert errors


@pytest.mark.parametrize("path,accepted", [
    (".agents/skills/harness-verification/SKILL.md", True),
    (".agents/skills/other/SKILL.md", False),
])
def test_workflow_skill_scope_is_limited_to_the_single_pilot(tmp_path: Path, path: str, accepted: bool) -> None:
    candidate = _candidate()
    candidate.update(mutation_type="workflow_skill", proposed_changes=[{"path": path, "summary": "验证清理试点"}])
    write_candidate_manifest(tmp_path, candidate)
    candidates, errors = load_candidate_manifests(tmp_path, allowed_mutation_types=["workflow_skill"])
    assert bool(candidates) is accepted
    assert bool(errors) is not accepted


def test_explicit_history_rejects_digest_outside_input_root(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    _write_json(input_root / "run-manifest.json", {
        "schema_version": 1, "run_id": "run-1", "profile_exit_codes": [],
        "failure_digest_artifacts": ["../outside.json"],
    })
    _write_json(tmp_path / "outside.json", {"run_id": "run-1", "profile": "docs", "failed_checks": []})
    with pytest.raises(ValueError, match="unsafe"):
        analyze_harness_evolution(tmp_path, {}, input_root=input_root)


def test_explicit_history_reads_exported_top_level_manifest(tmp_path: Path) -> None:
    _write_json(tmp_path / "harness-run-manifest.json", {
        "schema_version": 1, "run_id": "exported-run", "profile_exit_codes": [{"profile": "docs", "exit_code": 1}],
        "failure_digest_artifacts": [],
    })
    report = analyze_harness_evolution(tmp_path, {}, input_root=tmp_path)
    assert report["run_ids_analyzed"] == ["exported-run"]
    assert report["failure_patterns"][0]["failure_count"] == 1
    assert report["effectiveness"] == "not_evaluated"


@pytest.mark.parametrize("field,value", [("profile_exit_codes", None), ("profile_exit_codes", [{}]), ("failure_digest_artifacts", [42])])
def test_explicit_history_rejects_malformed_manifest_fields(tmp_path: Path, field: str, value: object) -> None:
    manifest = {"schema_version": 1, "run_id": "run-1", "profile_exit_codes": [], "failure_digest_artifacts": []}
    manifest[field] = value
    _write_json(tmp_path / "run-manifest.json", manifest)
    with pytest.raises(ValueError, match=field):
        analyze_harness_evolution(tmp_path, {}, input_root=tmp_path)


def test_explicit_history_rejects_digest_from_another_run(tmp_path: Path) -> None:
    _write_json(tmp_path / "run-manifest.json", {
        "schema_version": 1, "run_id": "run-1", "profile_exit_codes": [], "failure_digest_artifacts": ["digest.json"],
    })
    _write_json(tmp_path / "digest.json", {"run_id": "other-run", "profile": "docs", "failed_checks": []})
    with pytest.raises(ValueError, match="run_id mismatch"):
        analyze_harness_evolution(tmp_path, {}, input_root=tmp_path)


def test_replay_set_rejects_path_traversal(tmp_path: Path) -> None:
    replay_set, errors = load_replay_set(tmp_path, "../outside")
    assert replay_set == {}
    assert any("unsafe" in error for error in errors)


def test_load_evolution_config_accepts_valid_config(tmp_path: Path) -> None:
    _write_json(
        tmp_path / ".harness" / "evolution" / "config.json",
        {
            "schema_version": 1,
            "max_runs_to_analyze": 3,
            "profiles_in_scope": ["docs", "phase0"],
            "allowed_mutation_types": ["failure_digest", "docs_gate"],
            "promotion_requires_profiles": ["docs", "harness-evolution"],
        },
    )

    config, errors = load_evolution_config(tmp_path)

    assert errors == []
    assert config["max_runs_to_analyze"] == 3
    assert config["profiles_in_scope"] == ["docs", "phase0"]
    assert config["allowed_mutation_types"] == ["failure_digest", "docs_gate"]


def test_load_evolution_config_reports_invalid_config_without_raising(tmp_path: Path) -> None:
    _write_json(
        tmp_path / ".harness" / "evolution" / "config.json",
        {
            "schema_version": 2,
            "max_runs_to_analyze": 0,
            "profiles_in_scope": ["docs", 5],
            "allowed_mutation_types": [],
            "promotion_requires_profiles": ["docs"],
        },
    )

    config, errors = load_evolution_config(tmp_path)

    assert config == {}
    assert errors == [
        ".harness/evolution/config.json: unsupported schema_version 2",
        ".harness/evolution/config.json: max_runs_to_analyze must be a positive integer",
        ".harness/evolution/config.json: profiles_in_scope must be a non-empty list of strings",
        ".harness/evolution/config.json: allowed_mutation_types must be a non-empty list of strings",
    ]


def test_load_replay_set_accepts_default_replay_set(tmp_path: Path) -> None:
    _write_json(
        tmp_path / ".harness" / "evolution" / "replay-sets" / "default.json",
        {
            "schema_version": 1,
            "id": "default",
            "profile_cases": [
                {
                    "profile": "docs",
                    "expected_artifacts": [".harness/verification/docs-report.json"],
                }
            ],
            "regression_guards": ["profile_exit_code_does_not_worsen", "report_schema_stable"],
        },
    )

    replay_set, errors = load_replay_set(tmp_path, "default")

    assert errors == []
    assert replay_set["id"] == "default"
    assert replay_set["profile_cases"][0]["profile"] == "docs"


def test_load_candidate_manifests_rejects_out_of_scope_and_unapproved_full_access(tmp_path: Path) -> None:
    candidates_dir = tmp_path / ".harness" / "evolution" / "candidates"
    _write_json(
        candidates_dir / "bad.json",
        {
            "schema_version": 1,
            "id": "evo-bad",
            "status": "proposed",
            "mutation_type": "failure_digest",
            "risk_tier": "full-access",
            "source_failures": ["run-1", "phase0"],
            "hypothesis": "Bad candidate",
            "proposed_changes": [
                {
                    "path": "backend/app/main.py",
                    "summary": "Out of scope product edit",
                }
            ],
            "replay_set": "default",
            "promotion_checks": ["docs", "harness-evolution"],
            "requires_human_approval": False,
        },
    )

    candidates, errors = load_candidate_manifests(
        tmp_path,
        allowed_mutation_types=["failure_digest"],
    )

    assert candidates == []
    assert errors == [
        ".harness/evolution/candidates/bad.json: full-access candidates require human approval",
        ".harness/evolution/candidates/bad.json: backend/app/main.py is outside first-version harness mutation scope",
    ]


def test_load_candidate_manifests_requires_qa_artifacts_before_promotion_ready_or_promoted(tmp_path: Path) -> None:
    candidates_dir = tmp_path / ".harness" / "evolution" / "candidates"
    for filename, status, lifecycle_stage in [
        ("promoted.json", "promoted", None),
        ("promotion-ready.json", "evaluated", "promotion-ready"),
    ]:
        payload = {
            "schema_version": 1,
            "id": f"evo-{filename.removesuffix('.json')}",
            "status": status,
            "mutation_type": "docs_gate",
            "risk_tier": "sandbox-edit",
            "source_failures": ["run-1", "docs"],
            "hypothesis": "Repeated docs profile failures need better diagnostics.",
            "proposed_changes": [
                {
                    "path": "scripts/verification/check_docs.py",
                    "summary": "Tighten docs diagnostics for repeated failures.",
                }
            ],
            "replay_set": "default",
            "promotion_checks": ["docs", "harness-evolution"],
            "requires_human_approval": False,
            "qa_review_required": True,
            "qa_review_artifacts": [],
        }
        if lifecycle_stage is not None:
            payload["lifecycle_stage"] = lifecycle_stage
        _write_json(candidates_dir / filename, payload)

    candidates, errors = load_candidate_manifests(
        tmp_path,
        allowed_mutation_types=["docs_gate"],
    )

    assert candidates == []
    assert errors == [
        ".harness/evolution/candidates/promoted.json: promoted candidates require qa_review_artifacts",
        ".harness/evolution/candidates/promotion-ready.json: promotion-ready candidates require qa_review_artifacts",
    ]


def test_analyze_harness_evolution_aggregates_repeated_profile_failures(tmp_path: Path) -> None:
    for run_id in ["run-1", "run-2"]:
        run_dir = tmp_path / "input" / run_id
        _write_json(
            run_dir / "run-manifest.json",
            {
                "schema_version": 1,
                "run_id": run_id,
                "overall_harness_passed": False,
                "profile_exit_codes": [
                    {"profile": "docs", "exit_code": 1},
                    {"profile": "harness-lifecycle", "exit_code": 0},
                ],
                "failure_digest_artifacts": [
                    "docs-failure-digest.json"
                ],
            },
        )
        _write_json(
            run_dir / "docs-failure-digest.json",
            {
                "schema_version": 1,
                "run_id": run_id,
                "profile": "docs",
                "status": "failed",
                "exit_code": 1,
                "summary_status": "structured_checks_extracted",
                "failed_checks": [
                    {"id": "superpowers_specs_have_plans", "status": "missing", "evidence": []}
                ],
                "runtime_trace_refs": [],
                "source_artifacts": [".harness/verification/docs-report.json"],
            },
        )

    report = analyze_harness_evolution(
        tmp_path,
        {
            "max_runs_to_analyze": 20,
            "profiles_in_scope": ["docs", "harness-lifecycle"],
            "allowed_mutation_types": ["docs_gate"],
            "promotion_requires_profiles": ["docs", "harness-evolution"],
        },
        input_root=tmp_path / "input",
    )

    assert report["overall_harness_evolution_analyzed"] is True
    assert report["history_status"] == "analyzed"
    assert report["failure_patterns"] == [
        {
            "id": "repeated_profile_failure.docs",
            "profile": "docs",
            "failure_count": 2,
            "run_ids": ["run-1", "run-2"],
            "suggested_mutation_type": "docs_gate",
            "confidence": "medium",
        }
    ]
    assert report["check_patterns"] == [
        {
            "id": "repeated_check_failure.docs.superpowers_specs_have_plans",
            "profile": "docs",
            "check_id": "superpowers_specs_have_plans",
            "failure_count": 2,
            "run_ids": ["run-1", "run-2"],
        }
    ]


def test_analyze_harness_evolution_records_missing_digest_refs(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "input" / "run-1" / "run-manifest.json",
        {
            "schema_version": 1,
            "run_id": "run-1",
            "overall_harness_passed": False,
            "profile_exit_codes": [{"profile": "phase0", "exit_code": 1}],
            "failure_digest_artifacts": [
                "phase0-failure-digest.json"
            ],
        },
    )

    report = analyze_harness_evolution(
        tmp_path,
        {
            "max_runs_to_analyze": 20,
            "profiles_in_scope": ["phase0"],
            "allowed_mutation_types": ["failure_digest"],
            "promotion_requires_profiles": ["docs", "harness-evolution"],
        },
        input_root=tmp_path / "input",
    )

    assert report["telemetry_gaps"] == [
        {
            "id": "missing_digest_ref",
            "run_id": "run-1",
            "path": "phase0-failure-digest.json",
        }
    ]


def test_build_candidate_from_analysis_creates_governed_candidate() -> None:
    analysis = {
        "failure_patterns": [
            {
                "id": "repeated_profile_failure.docs",
                "profile": "docs",
                "failure_count": 2,
                "run_ids": ["run-1", "run-2"],
                "suggested_mutation_type": "docs_gate",
                "confidence": "medium",
            }
        ]
    }
    config = {
        "promotion_requires_profiles": ["docs", "harness-lifecycle", "harness-evolution"],
    }

    candidate = build_candidate_from_analysis(
        candidate_id="evo-docs-gate",
        analysis=analysis,
        config=config,
        replay_set_id="default",
    )

    assert candidate == {
        "schema_version": 1,
        "id": "evo-docs-gate",
        "status": "proposed",
        "lifecycle_stage": "proposed",
        "mutation_type": "docs_gate",
        "risk_tier": "sandbox-edit",
        "source_failures": ["run-1", "run-2", "docs"],
        "hypothesis": "Repeated docs profile failures suggest a harness-owned docs_gate improvement may be needed.",
        "proposed_changes": [
            {
                "path": "scripts/verification/check_docs.py",
                "summary": "Tighten docs_gate diagnostics for repeated docs profile failures.",
            }
        ],
        "replay_set": "default",
        "promotion_checks": ["docs", "harness-lifecycle", "harness-evolution"],
        "requires_human_approval": False,
        "qa_review_required": True,
        "qa_review_artifacts": [],
        "qa_review_artifact_digests": {},
        "baseline_revision": "",
        "candidate_revision": "",
        "evaluation_set_digest": "",
        "effectiveness": "not_evaluated",
    }


def test_write_candidate_manifest_refuses_to_overwrite_existing_candidate(tmp_path: Path) -> None:
    candidate = {
        "schema_version": 1,
        "id": "evo-docs-gate",
        "status": "proposed",
        "mutation_type": "docs_gate",
        "risk_tier": "sandbox-edit",
        "source_failures": ["run-1", "docs"],
        "hypothesis": "Repeated docs profile failures suggest a harness-owned docs_gate improvement may be needed.",
        "proposed_changes": [
            {
                "path": "scripts/verification/check_docs.py",
                "summary": "Tighten docs_gate diagnostics.",
            }
        ],
        "replay_set": "default",
        "promotion_checks": ["docs", "harness-evolution"],
        "requires_human_approval": False,
    }

    write_candidate_manifest(tmp_path, candidate)

    try:
        write_candidate_manifest(tmp_path, candidate)
    except FileExistsError as exc:
        assert "evo-docs-gate.json already exists" in str(exc)
    else:
        raise AssertionError("expected FileExistsError")


def test_evaluate_harness_evolution_proves_valid_surface_after_analysis(tmp_path: Path) -> None:
    _write_json(
        tmp_path / ".harness" / "evolution" / "config.json",
        {
            "schema_version": 1,
            "max_runs_to_analyze": 20,
            "profiles_in_scope": ["docs", "harness-lifecycle"],
            "allowed_mutation_types": ["docs_gate", "failure_digest"],
            "promotion_requires_profiles": ["docs", "harness-lifecycle", "harness-evolution"],
        },
    )
    _write_json(
        tmp_path / ".harness" / "evolution" / "replay-sets" / "default.json",
        {
            "schema_version": 1,
            "id": "default",
            "profile_cases": [
                {
                    "profile": "docs",
                    "expected_artifacts": [".harness/verification/docs-report.json"],
                }
            ],
            "regression_guards": ["profile_exit_code_does_not_worsen", "report_schema_stable"],
        },
    )
    (tmp_path / ".harness" / "evolution" / "candidates").mkdir(parents=True)
    analysis = {
            "schema_version": 1,
            "overall_harness_evolution_analyzed": True,
            "history_status": "insufficient_history",
            "failure_patterns": [],
            "check_patterns": [],
            "telemetry_gaps": [],
            "candidate_recommendations": [],
            "results": [],
        }
    with run_scope(tmp_path):
        _write_json(verification_dir(tmp_path) / "harness-evolution-report.json", analysis)
        report = evaluate_harness_evolution(tmp_path)
    statuses = {entry["id"]: entry["status"] for entry in report["results"]}

    assert report["overall_harness_evolution_passed"] is True
    assert report["effectiveness"] == "not_evaluated"
    assert statuses["evolution_config_valid"] == "proved"
    assert statuses["evolution_replay_set_valid"] == "proved"
    assert statuses["evolution_candidates_governed"] == "proved"
    assert statuses["evolution_candidate_lifecycle_governed"] == "proved"
    assert statuses["evolution_report_exists"] == "proved"


def test_analyze_harness_evolution_cli_analyze_writes_report(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    _write_json(
        tmp_path / ".harness" / "evolution" / "config.json",
        {
            "schema_version": 1,
            "max_runs_to_analyze": 20,
            "profiles_in_scope": ["docs"],
            "allowed_mutation_types": ["docs_gate"],
            "promotion_requires_profiles": ["docs", "harness-evolution"],
        },
    )
    _write_json(
        tmp_path / ".harness" / "evolution" / "replay-sets" / "default.json",
        {
            "schema_version": 1,
            "id": "default",
            "profile_cases": [
                {"profile": "docs", "expected_artifacts": [".harness/verification/docs-report.json"]}
            ],
            "regression_guards": ["profile_exit_code_does_not_worsen"],
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "verification" / "analyze_harness_evolution.py"),
            "--mode",
            "analyze",
            "--project-root",
            str(tmp_path),
        ],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0
    assert "harness_evolution_report_json=" in result.stdout
    assert "history_status=insufficient_history" in result.stdout
    assert "effectiveness=not_evaluated" in result.stdout
    report_path = next(line.split("=", 1)[1] for line in result.stdout.splitlines() if line.startswith("harness_evolution_report_json="))
    assert not Path(report_path).exists()
    assert not (tmp_path / ".harness" / "verification").exists()


def test_analyze_harness_evolution_cli_propose_writes_candidate(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    _write_json(
        tmp_path / ".harness" / "evolution" / "config.json",
        {
            "schema_version": 1,
            "max_runs_to_analyze": 20,
            "profiles_in_scope": ["docs"],
            "allowed_mutation_types": ["docs_gate"],
            "promotion_requires_profiles": ["docs", "harness-evolution"],
        },
    )
    _write_json(
        tmp_path / ".harness" / "evolution" / "replay-sets" / "default.json",
        {
            "schema_version": 1,
            "id": "default",
            "profile_cases": [
                {"profile": "docs", "expected_artifacts": [".harness/verification/docs-report.json"]}
            ],
            "regression_guards": ["profile_exit_code_does_not_worsen"],
        },
    )
    for run_id in ["run-1", "run-2"]:
        _write_json(
            tmp_path / "input" / run_id / "run-manifest.json",
            {
                "schema_version": 1,
                "run_id": run_id,
                "overall_harness_passed": False,
                "profile_exit_codes": [{"profile": "docs", "exit_code": 1}],
                "failure_digest_artifacts": [],
            },
        )

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "verification" / "analyze_harness_evolution.py"),
            "--mode",
            "propose",
            "--candidate-id",
            "evo-docs-gate",
            "--input-root",
            str(tmp_path / "input"),
            "--project-root",
            str(tmp_path),
        ],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        check=False,
    )

    candidate_path = tmp_path / ".harness" / "evolution" / "candidates" / "evo-docs-gate.json"
    assert result.returncode == 0
    assert "harness_evolution_candidate=" in result.stdout
    assert candidate_path.exists()
