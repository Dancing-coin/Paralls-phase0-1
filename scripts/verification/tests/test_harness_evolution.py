from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

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


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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
        run_dir = tmp_path / ".harness" / "verification" / "runs" / run_id
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
                    f".harness/verification/runs/{run_id}/docs-failure-digest.json"
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
        tmp_path / ".harness" / "verification" / "runs" / "run-1" / "run-manifest.json",
        {
            "schema_version": 1,
            "run_id": "run-1",
            "overall_harness_passed": False,
            "profile_exit_codes": [{"profile": "phase0", "exit_code": 1}],
            "failure_digest_artifacts": [
                ".harness/verification/runs/run-1/phase0-failure-digest.json"
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
    )

    assert report["telemetry_gaps"] == [
        {
            "id": "missing_digest_ref",
            "run_id": "run-1",
            "path": ".harness/verification/runs/run-1/phase0-failure-digest.json",
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
    _write_json(
        tmp_path / ".harness" / "verification" / "harness-evolution-report.json",
        {
            "schema_version": 1,
            "overall_harness_evolution_analyzed": True,
            "history_status": "insufficient_history",
            "failure_patterns": [],
            "check_patterns": [],
            "telemetry_gaps": [],
            "candidate_recommendations": [],
            "results": [],
        },
    )

    report = evaluate_harness_evolution(tmp_path)
    statuses = {entry["id"]: entry["status"] for entry in report["results"]}

    assert report["overall_harness_evolution_passed"] is True
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
    assert (tmp_path / ".harness" / "verification" / "harness-evolution-report.json").exists()


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
            tmp_path / ".harness" / "verification" / "runs" / run_id / "run-manifest.json",
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
