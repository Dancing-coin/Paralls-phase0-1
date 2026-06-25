# Harness Evolution Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a governed Harness Evolution Agent prototype that analyzes harness telemetry, writes evolution reports, and proposes reviewable mutation candidates without applying patches automatically.

**Architecture:** Keep the existing harness runner and decision-observability behavior intact. Add a focused `scripts/verification/evolution.py` module for deterministic schema validation and telemetry analysis, a small CLI for analyze/propose modes, and a `harness-evolution` profile that verifies governance surfaces, candidates, docs, and generated reports.

**Tech Stack:** Python standard library, pytest, existing `.harness` JSON/Markdown manifests, existing `scripts/verification/harness.py`, existing profile/rule registry, existing report helpers in `scripts/verification/common.py`.

---

## File Structure

- Create: `.harness/evolution/config.json`
  - Versioned config for profile scope, mutation types, replay policy, and promotion checks.
- Create: `.harness/evolution/replay-sets/default.json`
  - Versioned fixed replay set used by first-version candidate governance.
- Create: `.harness/evolution/candidates/.gitkeep`
  - Keeps the candidate manifest directory versionable before candidates exist.
- Create: `.harness/templates/evolution-candidate-template.json`
  - Documents the candidate mutation manifest schema.
- Create: `.harness/profiles/harness-evolution.json`
  - Registers the new profile at order `45`, after `harness-reference` and before runtime profiles.
- Create: `.harness/rules/harness-evolution-rules.json`
  - Maps stable `harness-evolution` result IDs to report evidence.
- Create: `scripts/verification/evolution.py`
  - Pure-ish deterministic helpers for loading evolution config, replay sets, candidates, run history, failure digests, report construction, and proposal creation.
- Create: `scripts/verification/analyze_harness_evolution.py`
  - CLI entrypoint for `--mode analyze` and `--mode propose`.
- Create: `scripts/verification/check_harness_evolution.py`
  - Harness profile script that validates evolution governance and writes reports.
- Create: `scripts/verification/tests/test_harness_evolution.py`
  - Focused tests for schema validation, failure aggregation, proposal generation, overwrite protection, and profile checks.
- Modify: `docs/harness.md`
  - Add command surface entry, profile docs, Evolution Agent workflow, generated artifacts, and evidence rules.
- Modify: `docs/ai-engineering-workflow.md`
  - Document that Evolution Agent candidates are proposals and do not authorize implementation by themselves.
- Modify: `.harness/features.json`
  - Record the new evolution lane after implementation evidence exists.
- Modify: `scripts/verification/tests/test_formal_profile_checks.py`
  - Assert the new formal profile proves required result IDs.

## Task 1: Add Failing Evolution Unit Tests

**Files:**
- Create: `scripts/verification/tests/test_harness_evolution.py`

- [ ] **Step 1: Create the test file with imports and JSON helpers**

Create `scripts/verification/tests/test_harness_evolution.py` with this initial content:

```python
from __future__ import annotations

import json
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
```

- [ ] **Step 2: Add a failing config loader test**

Append this test:

```python
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
```

- [ ] **Step 3: Add a failing invalid config test**

Append this test:

```python
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
```

- [ ] **Step 4: Add a failing replay set test**

Append this test:

```python
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
```

- [ ] **Step 5: Add a failing candidate governance test**

Append this test:

```python
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
```

- [ ] **Step 6: Add a failing run-history analysis test**

Append this test:

```python
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
```

- [ ] **Step 7: Add a failing missing-digest degradation test**

Append this test:

```python
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
```

- [ ] **Step 8: Add failing candidate proposal tests**

Append these tests:

```python
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
```

- [ ] **Step 9: Add a failing profile evaluation test**

Append this test:

```python
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
    assert statuses["evolution_report_exists"] == "proved"
```

- [ ] **Step 10: Run the focused test file and verify it fails**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_harness_evolution.py
```

Expected: FAIL with import errors such as `ModuleNotFoundError: No module named 'evolution'` or missing function errors.

## Task 2: Implement Evolution Helper Module

**Files:**
- Create: `scripts/verification/evolution.py`
- Test: `scripts/verification/tests/test_harness_evolution.py`

- [ ] **Step 1: Create `scripts/verification/evolution.py` with constants and basic JSON helpers**

Create `scripts/verification/evolution.py`:

```python
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


SUPPORTED_SCHEMA_VERSION = 1
KNOWN_CANDIDATE_STATUSES = {"proposed", "evaluated", "rejected", "promoted"}
KNOWN_RISK_TIERS = {"read-only", "sandbox-edit", "full-access"}
HARNESS_MUTATION_PREFIXES = (
    ".harness/",
    "scripts/verification/",
    ".github/workflows/harness.yml",
)
HARNESS_MUTATION_EXACT_PATHS = {
    "docs/harness.md",
    "docs/ai-engineering-workflow.md",
}


def _relative_path(project_root: Path, path: Path) -> str:
    return str(path.relative_to(project_root)).replace("\\", "/")


def _read_json(path: Path) -> tuple[dict[str, object], list[str]]:
    relative = str(path).replace("\\", "/")
    if not path.exists():
        return {}, [f"{relative}: missing"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}, [f"{relative}: invalid json"]
    except UnicodeDecodeError:
        return {}, [f"{relative}: invalid text"]
    except OSError:
        return {}, [f"{relative}: read error"]
    if not isinstance(payload, dict):
        return {}, [f"{relative}: expected json object"]
    return payload, []


def _project_relative_read_json(project_root: Path, path: Path) -> tuple[dict[str, object], list[str]]:
    payload, errors = _read_json(path)
    if not errors:
        return payload, []
    relative = _relative_path(project_root, path) if path.is_relative_to(project_root) else str(path)
    return {}, [error.replace(str(path).replace("\\", "/"), relative) for error in errors]


def _is_non_empty_string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(entry, str) and entry != "" for entry in value)
```

- [ ] **Step 2: Add config loading**

Append:

```python
def load_evolution_config(project_root: Path) -> tuple[dict[str, object], list[str]]:
    path = project_root / ".harness" / "evolution" / "config.json"
    payload, read_errors = _project_relative_read_json(project_root, path)
    if read_errors:
        return {}, read_errors

    errors: list[str] = []
    relative = ".harness/evolution/config.json"
    if payload.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        errors.append(f"{relative}: unsupported schema_version {payload.get('schema_version')}")
    if not isinstance(payload.get("max_runs_to_analyze"), int) or int(payload.get("max_runs_to_analyze", 0)) <= 0:
        errors.append(f"{relative}: max_runs_to_analyze must be a positive integer")
    if not _is_non_empty_string_list(payload.get("profiles_in_scope")):
        errors.append(f"{relative}: profiles_in_scope must be a non-empty list of strings")
    if not _is_non_empty_string_list(payload.get("allowed_mutation_types")):
        errors.append(f"{relative}: allowed_mutation_types must be a non-empty list of strings")
    if not _is_non_empty_string_list(payload.get("promotion_requires_profiles")):
        errors.append(f"{relative}: promotion_requires_profiles must be a non-empty list of strings")
    return ({}, errors) if errors else (payload, [])
```

- [ ] **Step 3: Add replay set loading**

Append:

```python
def load_replay_set(project_root: Path, replay_set_id: str) -> tuple[dict[str, object], list[str]]:
    path = project_root / ".harness" / "evolution" / "replay-sets" / f"{replay_set_id}.json"
    payload, read_errors = _project_relative_read_json(project_root, path)
    if read_errors:
        return {}, read_errors

    errors: list[str] = []
    relative = f".harness/evolution/replay-sets/{replay_set_id}.json"
    if payload.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        errors.append(f"{relative}: unsupported schema_version {payload.get('schema_version')}")
    if payload.get("id") != replay_set_id:
        errors.append(f"{relative}: id must match {replay_set_id}")
    profile_cases = payload.get("profile_cases")
    if not isinstance(profile_cases, list) or not profile_cases:
        errors.append(f"{relative}: profile_cases must be a non-empty list")
    else:
        for index, case in enumerate(profile_cases):
            if not isinstance(case, dict):
                errors.append(f"{relative}: profile_cases[{index}] must be an object")
                continue
            if not isinstance(case.get("profile"), str) or case.get("profile") == "":
                errors.append(f"{relative}: profile_cases[{index}].profile must be a non-empty string")
            if not _is_non_empty_string_list(case.get("expected_artifacts")):
                errors.append(f"{relative}: profile_cases[{index}].expected_artifacts must be a non-empty list of strings")
    if not _is_non_empty_string_list(payload.get("regression_guards")):
        errors.append(f"{relative}: regression_guards must be a non-empty list of strings")
    return ({}, errors) if errors else (payload, [])
```

- [ ] **Step 4: Add candidate validation**

Append:

```python
def _is_harness_mutation_path(path: str) -> bool:
    return path in HARNESS_MUTATION_EXACT_PATHS or any(path.startswith(prefix) for prefix in HARNESS_MUTATION_PREFIXES)


def _candidate_errors(relative: str, payload: dict[str, object], allowed_mutation_types: list[str]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        errors.append(f"{relative}: unsupported schema_version {payload.get('schema_version')}")
    for field in ("id", "status", "mutation_type", "risk_tier", "hypothesis", "replay_set"):
        if not isinstance(payload.get(field), str) or payload.get(field) == "":
            errors.append(f"{relative}: {field} must be a non-empty string")
    if payload.get("status") not in KNOWN_CANDIDATE_STATUSES:
        errors.append(f"{relative}: invalid status {payload.get('status')}")
    if payload.get("risk_tier") not in KNOWN_RISK_TIERS:
        errors.append(f"{relative}: invalid risk_tier {payload.get('risk_tier')}")
    if payload.get("mutation_type") not in allowed_mutation_types:
        errors.append(f"{relative}: unsupported mutation_type {payload.get('mutation_type')}")
    if not _is_non_empty_string_list(payload.get("source_failures")):
        errors.append(f"{relative}: source_failures must be a non-empty list of strings")
    if not _is_non_empty_string_list(payload.get("promotion_checks")):
        errors.append(f"{relative}: promotion_checks must be a non-empty list of strings")
    if not isinstance(payload.get("requires_human_approval"), bool):
        errors.append(f"{relative}: requires_human_approval must be boolean")
    if payload.get("risk_tier") == "full-access" and payload.get("requires_human_approval") is not True:
        errors.append(f"{relative}: full-access candidates require human approval")

    proposed_changes = payload.get("proposed_changes")
    if not isinstance(proposed_changes, list) or not proposed_changes:
        errors.append(f"{relative}: proposed_changes must be a non-empty list")
    else:
        for index, change in enumerate(proposed_changes):
            if not isinstance(change, dict):
                errors.append(f"{relative}: proposed_changes[{index}] must be an object")
                continue
            change_path = change.get("path")
            if not isinstance(change_path, str) or change_path == "":
                errors.append(f"{relative}: proposed_changes[{index}].path must be a non-empty string")
            elif not _is_harness_mutation_path(change_path):
                errors.append(f"{relative}: {change_path} is outside first-version harness mutation scope")
            if not isinstance(change.get("summary"), str) or change.get("summary") == "":
                errors.append(f"{relative}: proposed_changes[{index}].summary must be a non-empty string")
    return errors


def load_candidate_manifests(
    project_root: Path,
    *,
    allowed_mutation_types: list[str],
) -> tuple[list[dict[str, object]], list[str]]:
    candidates_dir = project_root / ".harness" / "evolution" / "candidates"
    candidates: list[dict[str, object]] = []
    errors: list[str] = []
    if not candidates_dir.exists():
        return candidates, errors
    for path in sorted(candidates_dir.glob("*.json")):
        relative = _relative_path(project_root, path)
        payload, read_errors = _project_relative_read_json(project_root, path)
        if read_errors:
            errors.extend(read_errors)
            continue
        candidate_errors = _candidate_errors(relative, payload, allowed_mutation_types)
        if candidate_errors:
            errors.extend(candidate_errors)
            continue
        candidates.append(payload)
    return candidates, errors
```

- [ ] **Step 5: Add run discovery and analysis**

Append:

```python
def _recent_run_manifests(project_root: Path, max_runs: int) -> list[dict[str, object]]:
    runs_dir = project_root / ".harness" / "verification" / "runs"
    if not runs_dir.exists():
        return []
    manifests: list[dict[str, object]] = []
    for path in sorted(runs_dir.glob("*/run-manifest.json"), reverse=True)[:max_runs]:
        payload, _errors = _project_relative_read_json(project_root, path)
        if payload:
            manifests.append(payload)
    return list(reversed(manifests))


def _load_digest(project_root: Path, digest_ref: str) -> dict[str, object] | None:
    path = project_root / digest_ref
    payload, errors = _project_relative_read_json(project_root, path)
    return None if errors else payload


def _suggested_mutation_type(profile: str) -> str:
    if profile == "docs":
        return "docs_gate"
    if profile in {"phase0", "phase1-slice", "character-agent-execution"}:
        return "failure_digest"
    return "validator"


def analyze_harness_evolution(project_root: Path, config: dict[str, object]) -> dict[str, object]:
    max_runs = int(config.get("max_runs_to_analyze", 20))
    profiles_in_scope = set(str(profile) for profile in config.get("profiles_in_scope", []))
    manifests = _recent_run_manifests(project_root, max_runs)
    if not manifests:
        return {
            "schema_version": 1,
            "overall_harness_evolution_analyzed": True,
            "history_status": "insufficient_history",
            "run_ids_analyzed": [],
            "failure_patterns": [],
            "check_patterns": [],
            "telemetry_gaps": [],
            "candidate_recommendations": [],
            "results": [],
        }

    profile_failures: dict[str, list[str]] = defaultdict(list)
    check_failures: dict[tuple[str, str], list[str]] = defaultdict(list)
    telemetry_gaps: list[dict[str, object]] = []
    run_ids: list[str] = []

    for manifest in manifests:
        run_id = str(manifest.get("run_id", ""))
        if run_id:
            run_ids.append(run_id)
        for entry in manifest.get("profile_exit_codes", []):
            if not isinstance(entry, dict):
                continue
            profile = str(entry.get("profile", ""))
            if profiles_in_scope and profile not in profiles_in_scope:
                continue
            if int(entry.get("exit_code", 0)) != 0:
                profile_failures[profile].append(run_id)
        for digest_ref in manifest.get("failure_digest_artifacts", []):
            if not isinstance(digest_ref, str):
                continue
            digest = _load_digest(project_root, digest_ref)
            if digest is None:
                telemetry_gaps.append({"id": "missing_digest_ref", "run_id": run_id, "path": digest_ref})
                continue
            profile = str(digest.get("profile", ""))
            if profiles_in_scope and profile not in profiles_in_scope:
                continue
            for check in digest.get("failed_checks", []):
                if isinstance(check, dict) and isinstance(check.get("id"), str):
                    check_failures[(profile, str(check["id"]))].append(run_id)

    failure_patterns = [
        {
            "id": f"repeated_profile_failure.{profile}",
            "profile": profile,
            "failure_count": len(failures),
            "run_ids": failures,
            "suggested_mutation_type": _suggested_mutation_type(profile),
            "confidence": "medium" if len(failures) >= 2 else "low",
        }
        for profile, failures in sorted(profile_failures.items())
        if failures
    ]
    check_patterns = [
        {
            "id": f"repeated_check_failure.{profile}.{check_id}",
            "profile": profile,
            "check_id": check_id,
            "failure_count": len(failures),
            "run_ids": failures,
        }
        for (profile, check_id), failures in sorted(check_failures.items())
        if len(failures) >= 2
    ]

    return {
        "schema_version": 1,
        "overall_harness_evolution_analyzed": True,
        "history_status": "analyzed",
        "run_ids_analyzed": run_ids,
        "failure_patterns": failure_patterns,
        "check_patterns": check_patterns,
        "telemetry_gaps": telemetry_gaps,
        "candidate_recommendations": failure_patterns[:1],
        "results": [],
    }
```

- [ ] **Step 6: Add candidate construction and writing**

Append:

```python
def build_candidate_from_analysis(
    *,
    candidate_id: str,
    analysis: dict[str, object],
    config: dict[str, object],
    replay_set_id: str,
) -> dict[str, object]:
    patterns = analysis.get("failure_patterns", [])
    if not isinstance(patterns, list) or not patterns:
        raise ValueError("No failure patterns available for candidate generation.")
    pattern = patterns[0]
    if not isinstance(pattern, dict):
        raise ValueError("Invalid failure pattern.")
    profile = str(pattern["profile"])
    mutation_type = str(pattern.get("suggested_mutation_type", "validator"))
    proposed_path = "scripts/verification/check_docs.py" if mutation_type == "docs_gate" else "scripts/verification/evidence.py"
    proposed_summary = (
        "Tighten docs_gate diagnostics for repeated docs profile failures."
        if mutation_type == "docs_gate"
        else f"Tighten {mutation_type} diagnostics for repeated {profile} profile failures."
    )
    return {
        "schema_version": 1,
        "id": candidate_id,
        "status": "proposed",
        "mutation_type": mutation_type,
        "risk_tier": "sandbox-edit",
        "source_failures": [*list(pattern.get("run_ids", [])), profile],
        "hypothesis": f"Repeated {profile} profile failures suggest a harness-owned {mutation_type} improvement may be needed.",
        "proposed_changes": [
            {
                "path": proposed_path,
                "summary": proposed_summary,
            }
        ],
        "replay_set": replay_set_id,
        "promotion_checks": list(config.get("promotion_requires_profiles", [])),
        "requires_human_approval": False,
    }


def write_candidate_manifest(project_root: Path, candidate: dict[str, object]) -> Path:
    candidate_id = str(candidate["id"])
    path = project_root / ".harness" / "evolution" / "candidates" / f"{candidate_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"{candidate_id}.json already exists")
    path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
```

- [ ] **Step 7: Add profile evaluation helper**

Append:

```python
def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def evaluate_harness_evolution(project_root: Path) -> dict[str, object]:
    config, config_errors = load_evolution_config(project_root)
    replay_set, replay_errors = load_replay_set(project_root, "default")
    candidates, candidate_errors = load_candidate_manifests(
        project_root,
        allowed_mutation_types=list(config.get("allowed_mutation_types", [])) if config else [],
    )
    report_path = project_root / ".harness" / "verification" / "harness-evolution-report.json"
    report, report_errors = _project_relative_read_json(project_root, report_path)

    results = [
        _result(
            "evolution_config_valid",
            "Harness evolution config exists and validates",
            bool(config) and not config_errors,
            [".harness/evolution/config.json"],
            "\n".join(config_errors),
        ),
        _result(
            "evolution_replay_set_valid",
            "Default harness evolution replay set exists and validates",
            bool(replay_set) and not replay_errors,
            [".harness/evolution/replay-sets/default.json"],
            "\n".join(replay_errors),
        ),
        _result(
            "evolution_candidates_governed",
            "Candidate manifests are schema-valid, scoped, and approval-gated",
            not candidate_errors,
            [".harness/evolution/candidates/"],
            "\n".join(candidate_errors),
        ),
        _result(
            "evolution_report_exists",
            "Harness evolution report exists after analyzer execution",
            bool(report) and report.get("schema_version") == 1 and report.get("overall_harness_evolution_analyzed") is True,
            [".harness/verification/harness-evolution-report.json"],
            "\n".join(report_errors),
        ),
    ]
    return {
        "results": results,
        "candidate_count": len(candidates),
        "overall_harness_evolution_passed": all(str(entry["status"]) == "proved" for entry in results),
    }
```

- [ ] **Step 8: Run the focused tests and verify the helper passes its unit behavior**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_harness_evolution.py
```

Expected: tests still fail for missing CLI/profile scripts if the test runner imports all tests, or pass the helper-level tests if only helper tests are present. If failures mention logic mismatch in `evolution.py`, fix before continuing.

## Task 3: Add Analyzer CLI

**Files:**
- Create: `scripts/verification/analyze_harness_evolution.py`
- Modify: `scripts/verification/tests/test_harness_evolution.py`

- [ ] **Step 1: Add CLI behavior tests**

Append these imports to `scripts/verification/tests/test_harness_evolution.py`:

```python
import subprocess
```

Append this test:

```python
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
```

Append this test:

```python
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
```

- [ ] **Step 2: Run the CLI tests and verify they fail**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_harness_evolution.py -k "cli"
```

Expected: FAIL because `scripts/verification/analyze_harness_evolution.py` does not exist.

- [ ] **Step 3: Implement `analyze_harness_evolution.py`**

Create `scripts/verification/analyze_harness_evolution.py`:

```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import repo_root, verification_dir
from evolution import (
    analyze_harness_evolution,
    build_candidate_from_analysis,
    load_evolution_config,
    load_replay_set,
    write_candidate_manifest,
)


def _write_report(project_root: Path, report: dict[str, object]) -> dict[str, Path]:
    log_dir = verification_dir(project_root)
    json_path = log_dir / "harness-evolution-report.json"
    md_path = log_dir / "harness-evolution-report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Harness Evolution Report",
        "",
        f"- History Status: `{report.get('history_status')}`",
        f"- Patterns: `{len(report.get('failure_patterns', []))}`",
        f"- Telemetry Gaps: `{len(report.get('telemetry_gaps', []))}`",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["analyze", "propose"], default="analyze")
    parser.add_argument("--candidate-id", default=None)
    parser.add_argument("--replay-set", default="default")
    parser.add_argument("--project-root", default=None)
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else repo_root()
    config, config_errors = load_evolution_config(project_root)
    _replay_set, replay_errors = load_replay_set(project_root, args.replay_set)
    if config_errors or replay_errors:
        for error in [*config_errors, *replay_errors]:
            print(f"harness_evolution_error={error}")
        return 1

    report = analyze_harness_evolution(project_root, config)
    report_paths = _write_report(project_root, report)
    print(f"harness_evolution_report_json={report_paths['json']}")
    print(f"harness_evolution_report_md={report_paths['markdown']}")

    if args.mode == "propose":
        if not args.candidate_id:
            print("harness_evolution_error=--candidate-id is required in propose mode")
            return 1
        try:
            candidate = build_candidate_from_analysis(
                candidate_id=args.candidate_id,
                analysis=report,
                config=config,
                replay_set_id=args.replay_set,
            )
            candidate_path = write_candidate_manifest(project_root, candidate)
        except (FileExistsError, ValueError) as exc:
            print(f"harness_evolution_error={exc}")
            return 1
        print(f"harness_evolution_candidate={candidate_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the CLI tests and verify they pass**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_harness_evolution.py -k "cli"
```

Expected: PASS.

## Task 4: Add Versioned Evolution Manifests And Profile Check

**Files:**
- Create: `.harness/evolution/config.json`
- Create: `.harness/evolution/replay-sets/default.json`
- Create: `.harness/evolution/candidates/.gitkeep`
- Create: `.harness/templates/evolution-candidate-template.json`
- Create: `.harness/profiles/harness-evolution.json`
- Create: `.harness/rules/harness-evolution-rules.json`
- Create: `scripts/verification/check_harness_evolution.py`
- Modify: `scripts/verification/tests/test_formal_profile_checks.py`

- [ ] **Step 1: Add failing formal profile assertions**

Modify `scripts/verification/tests/test_formal_profile_checks.py`.

Add this import:

```python
from check_harness_evolution import evaluate_harness_evolution
```

Add this test near the other profile tests:

```python
def test_harness_evolution_profile_proves_governed_evolution_surface() -> None:
    report = evaluate_harness_evolution(repo_root())
    statuses = {entry["id"]: entry["status"] for entry in report["results"]}

    assert statuses["evolution_config_valid"] == "proved"
    assert statuses["evolution_replay_set_valid"] == "proved"
    assert statuses["evolution_candidates_governed"] == "proved"
    assert statuses["evolution_report_exists"] == "proved"
```

- [ ] **Step 2: Run the formal profile test and verify it fails**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_formal_profile_checks.py -k "harness_evolution"
```

Expected: FAIL because `check_harness_evolution.py` is missing.

- [ ] **Step 3: Create evolution config**

Create `.harness/evolution/config.json`:

```json
{
  "schema_version": 1,
  "max_runs_to_analyze": 20,
  "profiles_in_scope": [
    "docs",
    "harness-lifecycle",
    "change-lifecycle",
    "harness-reference",
    "phase0",
    "phase1-slice"
  ],
  "allowed_mutation_types": [
    "validator",
    "profile_policy",
    "failure_digest",
    "docs_gate",
    "rule_evidence"
  ],
  "promotion_requires_profiles": [
    "docs",
    "harness-lifecycle",
    "harness-evolution"
  ]
}
```

- [ ] **Step 4: Create default replay set**

Create `.harness/evolution/replay-sets/default.json`:

```json
{
  "schema_version": 1,
  "id": "default",
  "profile_cases": [
    {
      "profile": "harness-lifecycle",
      "expected_artifacts": [
        ".harness/verification/harness-lifecycle-report.json"
      ]
    },
    {
      "profile": "docs",
      "expected_artifacts": [
        ".harness/verification/docs-report.json"
      ]
    }
  ],
  "regression_guards": [
    "profile_exit_code_does_not_worsen",
    "report_schema_stable"
  ]
}
```

- [ ] **Step 5: Create candidate directory marker**

Create `.harness/evolution/candidates/.gitkeep` as an empty file.

- [ ] **Step 6: Create candidate template**

Create `.harness/templates/evolution-candidate-template.json`:

```json
{
  "schema_version": 1,
  "id": "evo-20260625-example-failure-digest",
  "status": "proposed",
  "mutation_type": "failure_digest",
  "risk_tier": "sandbox-edit",
  "source_failures": [
    "run-20260625-000000-000000",
    "profile-name"
  ],
  "hypothesis": "One sentence describing why this harness mutation should improve reliability, cost, or diagnosability.",
  "proposed_changes": [
    {
      "path": "scripts/verification/evidence.py",
      "summary": "One sentence describing the harness-owned change."
    }
  ],
  "replay_set": "default",
  "promotion_checks": [
    "docs",
    "harness-lifecycle",
    "harness-evolution"
  ],
  "requires_human_approval": false
}
```

- [ ] **Step 7: Create profile manifest**

Create `.harness/profiles/harness-evolution.json`:

```json
{
  "schema_version": 1,
  "name": "harness-evolution",
  "order": 45,
  "script": "scripts/verification/check_harness_evolution.py",
  "requires_godot": false,
  "description": "Governed Harness Evolution Agent config, replay set, candidate, and report checks"
}
```

- [ ] **Step 8: Create rule manifest**

Create `.harness/rules/harness-evolution-rules.json`:

```json
{
  "schema_version": 1,
  "name": "harness-evolution-rules",
  "profile": "harness-evolution",
  "description": "Mechanical invariants enforced by scripts/verification/check_harness_evolution.py",
  "rules": [
    {
      "id": "evolution_config_valid",
      "title": "Harness evolution config exists and validates",
      "evidence": [
        ".harness/verification/harness-evolution-report.json:results.evolution_config_valid"
      ]
    },
    {
      "id": "evolution_replay_set_valid",
      "title": "Default harness evolution replay set exists and validates",
      "evidence": [
        ".harness/verification/harness-evolution-report.json:results.evolution_replay_set_valid"
      ]
    },
    {
      "id": "evolution_candidates_governed",
      "title": "Candidate manifests are schema-valid, scoped, and approval-gated",
      "evidence": [
        ".harness/verification/harness-evolution-report.json:results.evolution_candidates_governed"
      ]
    },
    {
      "id": "evolution_report_exists",
      "title": "Harness evolution report exists after analyzer execution",
      "evidence": [
        ".harness/verification/harness-evolution-report.json:results.evolution_report_exists"
      ]
    }
  ]
}
```

- [ ] **Step 9: Create profile check script**

Create `scripts/verification/check_harness_evolution.py`:

```python
from __future__ import annotations

from common import repo_root, verification_dir, write_json, write_markdown
from evolution import evaluate_harness_evolution


def main() -> int:
    project_root = repo_root()
    report = evaluate_harness_evolution(project_root)
    log_dir = verification_dir(project_root)
    json_path = log_dir / "harness-evolution-report.json"
    md_path = log_dir / "harness-evolution-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Harness Evolution Verification Report", report, "overall_harness_evolution_passed")

    print(f"harness_evolution_report_json={json_path}")
    print(f"harness_evolution_report_md={md_path}")
    print(f"overall_harness_evolution_passed={report['overall_harness_evolution_passed']}")
    for entry in report["results"]:
        print(f"{entry['id']}={entry['status']}")
    return 0 if report["overall_harness_evolution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 10: Generate the initial evolution report before profile evaluation**

Run:

```powershell
python scripts/verification/analyze_harness_evolution.py --mode analyze
```

Expected: exit code 0 and output includes `harness_evolution_report_json=`.

- [ ] **Step 11: Run formal profile and focused evolution tests**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_harness_evolution.py scripts/verification/tests/test_formal_profile_checks.py -k "harness_evolution or evolution"
```

Expected: PASS.

## Task 5: Wire Documentation, Feature Ledger, And Docs Gate

**Files:**
- Modify: `docs/harness.md`
- Modify: `docs/ai-engineering-workflow.md`
- Modify: `.harness/features.json`
- Test: `scripts/verification/harness.py --profile docs`
- Test: `scripts/verification/harness.py --profile harness-lifecycle`

- [ ] **Step 1: Update `docs/harness.md` command surface**

In `docs/harness.md`, add this command after `harness-reference`:

```powershell
python scripts/verification/harness.py --profile harness-evolution
```

- [ ] **Step 2: Update `docs/harness.md` registry section**

Add `.harness/evolution/` to the registry list:

```markdown
- `.harness/evolution/`: versionable evolution config, replay sets, and candidate mutation manifests.
```

- [ ] **Step 3: Add `harness-evolution` profile docs**

Add this section after `harness-reference` and before `phase0`:

```markdown
### `harness-evolution`

Static governance checks for the Harness Evolution Agent prototype. Use this when changing evolution config, replay sets, candidate manifests, analyzer behavior, or promotion governance.

Current mechanical invariants include:

- `.harness/evolution/config.json` exists and validates
- `.harness/evolution/replay-sets/default.json` exists and validates
- candidate manifests under `.harness/evolution/candidates/` are schema-valid, harness-scoped, and approval-gated
- `.harness/verification/harness-evolution-report.json` exists after analyzer execution

Analyzer commands:

```powershell
python scripts/verification/analyze_harness_evolution.py --mode analyze
python scripts/verification/analyze_harness_evolution.py --mode propose --candidate-id evo-20260625-example-failure-digest
```

Output:

- `.harness/verification/harness-evolution-report.json`
- `.harness/verification/harness-evolution-report.md`
- optional `.harness/evolution/candidates/<id>.json` in propose mode
```
```

- [ ] **Step 4: Update `all` profile docs**

In the `all` section, include `harness-evolution` after `harness-reference` and before `phase0`.

- [ ] **Step 5: Add Evolution Agent workflow section**

Add this section near the existing Decision Observability section:

```markdown
## Harness Evolution

The Harness Evolution Agent is a governed proposal lane. It reads existing Harness telemetry, writes an evolution report, and may create candidate mutation manifests under `.harness/evolution/candidates/`.

It does not apply patches or promote its own proposals. A candidate must be converted into a normal implementation plan, implemented through the repository workflow, and verified through its promotion profiles before it can become operational harness behavior.

First-version candidates may target harness-owned surfaces such as `.harness/`, `scripts/verification/`, `docs/harness.md`, `docs/ai-engineering-workflow.md`, and `.github/workflows/harness.yml`. Product runtime paths such as `backend/`, `scenes/`, character scripts, or Siming runtime modules are outside the mutation scope.
```

- [ ] **Step 6: Update `docs/ai-engineering-workflow.md` governance**

Add this paragraph under `Source Of Truth`:

```markdown
Evolution Agent candidate manifests are proposals, not implementation approval. A candidate under `.harness/evolution/candidates/` must still be reviewed, converted into an implementation plan, implemented through normal edits, and verified by its promotion profiles before it changes operational harness behavior.
```

- [ ] **Step 7: Update `.harness/features.json`**

Append this feature entry to the `features` array:

```json
{
  "id": "harness-evolution-agent",
  "name": "Governed Harness Evolution Agent proposal lane",
  "status": "pass",
  "evidence": ".harness/evolution/, scripts/verification/analyze_harness_evolution.py, and harness-evolution profile"
}
```

- [ ] **Step 8: Run docs profile**

Run:

```powershell
python scripts/verification/harness.py --profile docs
```

Expected: PASS.

- [ ] **Step 9: Run harness lifecycle profile**

Run:

```powershell
python scripts/verification/harness.py --profile harness-lifecycle
```

Expected: PASS.

## Task 6: Final Verification And Commit

**Files:**
- All files touched in Tasks 1-5

- [ ] **Step 1: Run focused evolution tests**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_harness_evolution.py
```

Expected: PASS.

- [ ] **Step 2: Run formal profile tests**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_formal_profile_checks.py
```

Expected: PASS.

- [ ] **Step 3: Run analyzer**

Run:

```powershell
python scripts/verification/analyze_harness_evolution.py --mode analyze
```

Expected: PASS and writes:

- `.harness/verification/harness-evolution-report.json`
- `.harness/verification/harness-evolution-report.md`

- [ ] **Step 4: Run new profile**

Run:

```powershell
python scripts/verification/harness.py --profile harness-evolution
```

Expected: PASS.

- [ ] **Step 5: Run docs and lifecycle profiles**

Run:

```powershell
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile harness-lifecycle
```

Expected: both PASS.

- [ ] **Step 6: Run compile check**

Run:

```powershell
python -m compileall -q scripts/verification
```

Expected: exit code 0.

- [ ] **Step 7: Run broad harness**

Run:

```powershell
python scripts/verification/harness.py --profile all
```

Expected: PASS if existing runtime prerequisites are present. If it fails at a known pre-existing Godot/runtime resource issue, capture the failed profile, failure digest path, and generated run directory in the final report rather than hiding it.

- [ ] **Step 8: Inspect git status**

Run:

```powershell
git status --short
```

Expected: only intended source files and versioned `.harness` inputs are modified or added. Generated files under `.harness/verification/` should remain untracked or ignored.

- [ ] **Step 9: Commit with Lore protocol**

Commit message template:

```text
Make harness evolution proposals governed and replayable

The harness already records run evidence and decision context. This adds a
governed evolution lane so future agents can turn telemetry into reviewable
candidate mutations without silently changing the operational harness.

Constraint: Evolution Agent candidates must remain proposals until reviewed and implemented through the normal plan/test/harness workflow.
Rejected: Automatic patch application from analysis mode | too much governance risk for first version
Confidence: high
Scope-risk: moderate
Directive: Do not let propose mode modify operational harness files; it may only write candidate manifests.
Tested: python -m pytest -q scripts/verification/tests/test_harness_evolution.py
Tested: python -m pytest -q scripts/verification/tests/test_formal_profile_checks.py
Tested: python scripts/verification/harness.py --profile harness-evolution
Tested: python scripts/verification/harness.py --profile docs
Tested: python scripts/verification/harness.py --profile harness-lifecycle
Not-tested: Document any all-profile failure here with profile and digest path
```

## Self-Review Checklist

- [ ] The plan implements every design requirement from `docs/superpowers/specs/2026-06-25-harness-evolution-agent-design.md`.
- [ ] No task asks an agent to edit product runtime code under `backend/`, `scenes/`, character scripts, or Siming runtime modules.
- [ ] Analyze mode writes only generated reports.
- [ ] Propose mode writes only one candidate manifest and refuses overwrites.
- [ ] `full-access` candidates require `requires_human_approval=true`.
- [ ] `harness-evolution` is registered at order `45`, documented, and included in `all`.
- [ ] Generated evidence remains under `.harness/verification/`.
- [ ] The broad verification caveat for pre-existing runtime/Godot failures is reported honestly.
