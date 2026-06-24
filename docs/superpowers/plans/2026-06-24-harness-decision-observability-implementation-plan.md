# Harness Decision Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic decision manifests and failed-profile digests to the existing Harness evidence chain.

**Architecture:** Keep profile execution unchanged. Extend `scripts/verification/evidence.py` with pure helpers for change manifest collection and failure digest construction, then have `scripts/verification/harness.py` attach those artifacts while writing latest and archived run manifests.

**Tech Stack:** Python standard library, pytest, existing `.harness` JSON/Markdown files, existing Harness runner and lifecycle checks.

---

## File Structure

- Create: `.harness/changes/.gitkeep`
  - Keeps the versionable Harness change manifest directory present.
- Create: `.harness/templates/change-manifest-template.json`
  - Documents the schema for future `.harness/changes/*.json` entries.
- Modify: `scripts/verification/evidence.py`
  - Add deterministic helpers for active change collection, manifest error reporting, failed-check extraction, trace reference discovery, and digest construction.
- Modify: `scripts/verification/harness.py`
  - Generate failure digests for failed profiles and include active Harness changes plus digest refs in latest and archived run manifests.
- Modify: `scripts/verification/check_harness_lifecycle.py`
  - Add lifecycle checks for the decision-observability directory, template, and docs.
- Modify: `scripts/verification/tests/test_harness_runner.py`
  - Add runner/evidence tests for active changes, invalid manifests, failed-profile digests, and degraded digests.
- Modify: `scripts/verification/tests/test_formal_profile_checks.py`
  - Assert the new lifecycle result IDs are proved.
- Modify: `docs/harness.md`
  - Document the decision-observability workflow and generated failure digest artifacts.
- Modify: `.harness/features.json`
  - Record the new decision-observability Harness feature once implemented and verified.

## Task 1: Lock Evidence Helper Behavior With Tests

**Files:**
- Modify: `scripts/verification/tests/test_harness_runner.py`

- [ ] **Step 1: Add imports for the new evidence helper functions**

Add these imports near the existing `from harness import _write_harness_report` line:

```python
from evidence import (
    build_failure_digest,
    collect_harness_changes,
    extract_failed_checks,
)
```

- [ ] **Step 2: Write the failing test for active Harness change collection**

Append this test to `scripts/verification/tests/test_harness_runner.py`:

```python
def test_collect_harness_changes_reads_only_active_manifests(tmp_path: Path) -> None:
    changes_dir = tmp_path / ".harness" / "changes"
    changes_dir.mkdir(parents=True)
    active_path = changes_dir / "chg-active.json"
    superseded_path = changes_dir / "chg-superseded.json"
    rejected_path = changes_dir / "chg-rejected.json"

    active_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "chg-active",
                "title": "Active change",
                "status": "active",
                "verification_profiles": ["docs", "harness-lifecycle"],
            }
        ),
        encoding="utf-8",
    )
    superseded_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "chg-superseded",
                "title": "Old change",
                "status": "superseded",
                "verification_profiles": ["docs"],
            }
        ),
        encoding="utf-8",
    )
    rejected_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "chg-rejected",
                "title": "Rejected change",
                "status": "rejected",
                "verification_profiles": ["docs"],
            }
        ),
        encoding="utf-8",
    )

    result = collect_harness_changes(tmp_path)

    assert result["harness_change_errors"] == []
    assert result["harness_changes"] == [
        {
            "id": "chg-active",
            "title": "Active change",
            "status": "active",
            "path": ".harness/changes/chg-active.json",
            "verification_profiles": ["docs", "harness-lifecycle"],
        }
    ]
```

- [ ] **Step 3: Write the failing test for invalid manifest reporting**

Append this test:

```python
def test_collect_harness_changes_reports_invalid_manifest_without_raising(tmp_path: Path) -> None:
    changes_dir = tmp_path / ".harness" / "changes"
    changes_dir.mkdir(parents=True)
    (changes_dir / "broken.json").write_text("{not-json", encoding="utf-8")

    result = collect_harness_changes(tmp_path)

    assert result["harness_changes"] == []
    assert result["harness_change_errors"] == [
        {
            "path": ".harness/changes/broken.json",
            "error": "invalid_json",
        }
    ]
```

- [ ] **Step 4: Write the failing test for structured failed-check extraction**

Append this test:

```python
def test_extract_failed_checks_reads_missing_result_entries() -> None:
    report = {
        "results": [
            {"id": "docs_index_paths_exist", "status": "proved", "evidence": ["docs/INDEX.md"]},
            {"id": "runtime_trace_exists", "status": "missing", "evidence": []},
            {"id": "phase0_loop", "status": "failed", "evidence": ["phase0-report.json"]},
        ]
    }

    assert extract_failed_checks(report) == [
        {"id": "runtime_trace_exists", "status": "missing", "evidence": []},
        {"id": "phase0_loop", "status": "failed", "evidence": ["phase0-report.json"]},
    ]
```

- [ ] **Step 5: Write the failing test for degraded failure digest construction**

Append this test:

```python
def test_build_failure_digest_degrades_when_report_has_no_structured_checks(tmp_path: Path) -> None:
    report_path = tmp_path / ".harness" / "verification" / "custom-report.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(json.dumps({"overall_custom_passed": False}), encoding="utf-8")

    digest = build_failure_digest(
        project_root=tmp_path,
        run_id="run_digest",
        profile_result={
            "profile": "custom",
            "command": ["python", "scripts/verification/custom.py"],
            "exit_code": 1,
        },
        profile_config={
            "result_artifact": ".harness/verification/custom-report.json",
        },
    )

    assert digest["schema_version"] == 1
    assert digest["run_id"] == "run_digest"
    assert digest["profile"] == "custom"
    assert digest["status"] == "failed"
    assert digest["exit_code"] == 1
    assert digest["summary_status"] == "profile_failed_without_structured_checks"
    assert digest["primary_report"] == ".harness/verification/custom-report.json"
    assert digest["failed_checks"] == []
    assert digest["runtime_trace_refs"] == []
    assert digest["source_artifacts"] == [".harness/verification/custom-report.json"]
```

- [ ] **Step 6: Run the focused tests and confirm they fail**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_harness_runner.py
```

Expected: FAIL because `collect_harness_changes`, `extract_failed_checks`, and `build_failure_digest` are not implemented yet.

## Task 2: Implement Evidence Helpers

**Files:**
- Modify: `scripts/verification/evidence.py`

- [ ] **Step 1: Add helper constants and path normalization**

Append this code after the imports in `scripts/verification/evidence.py`:

```python
ACTIVE_HARNESS_CHANGE_STATUS = "active"
KNOWN_HARNESS_CHANGE_STATUSES = {"active", "superseded", "rejected"}


def _relative_path(project_root: Path, path: Path) -> str:
    return str(path.relative_to(project_root)).replace("\\", "/")
```

- [ ] **Step 2: Add Harness change collection**

Append this function to `scripts/verification/evidence.py`:

```python
def collect_harness_changes(project_root: Path) -> dict[str, object]:
    changes_dir = project_root / ".harness" / "changes"
    changes: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    if not changes_dir.exists():
        return {"harness_changes": changes, "harness_change_errors": errors}

    for path in sorted(changes_dir.glob("*.json")):
        relative = _relative_path(project_root, path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            errors.append({"path": relative, "error": "invalid_json"})
            continue
        if not isinstance(payload, dict):
            errors.append({"path": relative, "error": "not_json_object"})
            continue
        status = str(payload.get("status", ""))
        if status not in KNOWN_HARNESS_CHANGE_STATUSES:
            errors.append({"path": relative, "error": "invalid_status"})
            continue
        if status != ACTIVE_HARNESS_CHANGE_STATUS:
            continue
        change_id = payload.get("id")
        title = payload.get("title")
        if not isinstance(change_id, str) or change_id == "":
            errors.append({"path": relative, "error": "missing_id"})
            continue
        if not isinstance(title, str) or title == "":
            errors.append({"path": relative, "error": "missing_title"})
            continue
        verification_profiles = payload.get("verification_profiles", [])
        if not isinstance(verification_profiles, list):
            errors.append({"path": relative, "error": "invalid_verification_profiles"})
            continue
        changes.append(
            {
                "id": change_id,
                "title": title,
                "status": status,
                "path": relative,
                "verification_profiles": [str(profile) for profile in verification_profiles],
            }
        )
    return {"harness_changes": changes, "harness_change_errors": errors}
```

- [ ] **Step 3: Add failed-check extraction**

Append this function:

```python
def extract_failed_checks(report: dict[str, object]) -> list[dict[str, object]]:
    failed: list[dict[str, object]] = []
    results = report.get("results", [])
    if not isinstance(results, list):
        return failed
    passing_statuses = {"proved", "pass", "passed", "ok", "true"}
    for entry in results:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status", "")).lower()
        if status in passing_statuses:
            continue
        check_id = entry.get("id")
        if not isinstance(check_id, str) or check_id == "":
            continue
        evidence = entry.get("evidence", [])
        failed.append(
            {
                "id": check_id,
                "status": str(entry.get("status", "")),
                "evidence": evidence if isinstance(evidence, list) else [],
            }
        )
    return failed
```

- [ ] **Step 4: Add failure digest construction**

Append these functions:

```python
def build_failure_digest(
    *,
    project_root: Path,
    run_id: str,
    profile_result: dict[str, object],
    profile_config: dict[str, object],
) -> dict[str, object]:
    profile = str(profile_result["profile"])
    report_path = _resolve_profile_report(project_root, profile_config)
    source_artifacts = _source_artifacts(project_root, report_path)
    report = read_json_object(report_path) if report_path is not None else None
    failed_checks = extract_failed_checks(report or {})
    trace_refs = _runtime_trace_refs(project_root, profile)
    if report_path is None:
        summary_status = "profile_failed_without_report"
    elif not failed_checks:
        summary_status = "profile_failed_without_structured_checks"
    else:
        summary_status = "structured_checks_extracted"
    return {
        "schema_version": 1,
        "run_id": run_id,
        "profile": profile,
        "status": "failed",
        "exit_code": int(profile_result["exit_code"]),
        "summary_status": summary_status,
        "primary_report": _relative_path(project_root, report_path) if report_path is not None else None,
        "failed_checks": failed_checks,
        "runtime_trace_refs": trace_refs,
        "source_artifacts": source_artifacts,
    }


def _resolve_profile_report(project_root: Path, profile_config: dict[str, object]) -> Path | None:
    artifact = str(profile_config.get("result_artifact", "") or "")
    if artifact == "":
        return None
    path = project_root / artifact
    return path if path.exists() else None


def _source_artifacts(project_root: Path, report_path: Path | None) -> list[str]:
    if report_path is None:
        return []
    artifacts = [_relative_path(project_root, report_path)]
    markdown_path = report_path.with_suffix(".md")
    if markdown_path.exists():
        artifacts.append(_relative_path(project_root, markdown_path))
    return artifacts


def _runtime_trace_refs(project_root: Path, profile: str) -> list[str]:
    trace_path = project_root / ".harness" / "verification" / f"{profile}-runtime-trace.ndjson"
    if trace_path.exists():
        return [_relative_path(project_root, trace_path)]
    return []
```

- [ ] **Step 5: Extend `build_run_manifest` signature and return value**

Change the function signature to:

```python
def build_run_manifest(
    *,
    run_id: str,
    overall_passed: bool,
    profiles: list[dict[str, object]],
    artifacts: dict[str, str],
    harness_changes: list[dict[str, object]] | None = None,
    harness_change_errors: list[dict[str, object]] | None = None,
    failure_digest_artifacts: list[str] | None = None,
) -> dict[str, object]:
```

Replace the current return dictionary with:

```python
    return {
        "schema_version": 1,
        "run_id": run_id,
        "overall_harness_passed": overall_passed,
        "profile_exit_codes": [
            {
                "profile": str(profile["profile"]),
                "exit_code": int(profile["exit_code"]),
            }
            for profile in profiles
        ],
        "artifacts": artifacts,
        "harness_changes": harness_changes or [],
        "harness_change_errors": harness_change_errors or [],
        "failure_digest_artifacts": failure_digest_artifacts or [],
    }
```

- [ ] **Step 6: Run focused tests and confirm helper tests pass**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_harness_runner.py
```

Expected: previously added helper tests PASS. Runner integration tests that expect manifest fields may still be missing until Task 3.

- [ ] **Step 7: Commit Task 2**

Run:

```powershell
git add scripts/verification/evidence.py scripts/verification/tests/test_harness_runner.py
git commit -m "Expose harness change intent in evidence helpers" -m "Decision observability needs deterministic helper functions before runner integration. This adds active change collection, invalid manifest reporting, failed-check extraction, and failure digest construction without changing profile execution." -m "Constraint: Keep ordinary profile runs usable when a change manifest is malformed." -m "Rejected: LLM-generated failure summaries | deterministic reports are easier to test and review." -m "Confidence: high" -m "Scope-risk: narrow" -m "Tested: python -m pytest -q scripts/verification/tests/test_harness_runner.py"
```

## Task 3: Integrate Failure Digests Into Harness Runs

**Files:**
- Modify: `scripts/verification/harness.py`
- Modify: `scripts/verification/tests/test_harness_runner.py`

- [ ] **Step 1: Add failing runner integration test**

Append this test to `scripts/verification/tests/test_harness_runner.py`:

```python
def test_write_harness_report_records_active_changes_and_failure_digest(tmp_path: Path) -> None:
    changes_dir = tmp_path / ".harness" / "changes"
    changes_dir.mkdir(parents=True)
    (changes_dir / "chg-active.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "chg-active",
                "title": "Active change",
                "status": "active",
                "verification_profiles": ["docs"],
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / ".harness" / "verification" / "docs-report.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps(
            {
                "results": [
                    {"id": "docs_index_paths_exist", "status": "missing", "evidence": []}
                ]
            }
        ),
        encoding="utf-8",
    )

    report_paths = _write_harness_report(
        tmp_path,
        [
            {
                "profile": "docs",
                "command": ["python", "scripts/verification/check_docs.py"],
                "exit_code": 1,
            }
        ],
        overall_passed=False,
        run_id="run_observable",
        profile_configs={
            "docs": {
                "result_artifact": ".harness/verification/docs-report.json",
            }
        },
    )

    manifest = json.loads(report_paths["manifest"].read_text(encoding="utf-8"))
    digest_path = tmp_path / ".harness" / "verification" / "docs-failure-digest.json"
    archived_digest_path = report_paths["run_dir"] / "docs-failure-digest.json"

    assert manifest["harness_changes"] == [
        {
            "id": "chg-active",
            "title": "Active change",
            "status": "active",
            "path": ".harness/changes/chg-active.json",
            "verification_profiles": ["docs"],
        }
    ]
    assert manifest["harness_change_errors"] == []
    assert manifest["failure_digest_artifacts"] == [
        ".harness/verification/docs-failure-digest.json"
    ]
    assert digest_path.exists()
    assert archived_digest_path.exists()
```

- [ ] **Step 2: Update imports in `harness.py`**

Replace the existing evidence import with:

```python
from evidence import (
    build_failure_digest,
    build_run_diff,
    build_run_manifest,
    collect_harness_changes,
    read_json_object,
)
```

- [ ] **Step 3: Extend `_write_harness_report` signature**

Change the signature to:

```python
def _write_harness_report(
    project_root: Path,
    profiles: list[dict[str, object]],
    *,
    overall_passed: bool,
    run_id: str | None = None,
    profile_configs: dict[str, dict[str, object]] | None = None,
) -> dict[str, Path]:
```

- [ ] **Step 4: Generate failure digests before building the run manifest**

Add this block before the `manifest = build_run_manifest(...)` call:

```python
    profile_configs = profile_configs or {}
    failure_digest_artifacts: list[str] = []
    for profile in profiles:
        if int(profile["exit_code"]) == 0:
            continue
        profile_name = str(profile["profile"])
        digest = build_failure_digest(
            project_root=project_root,
            run_id=run_id,
            profile_result=profile,
            profile_config=profile_configs.get(profile_name, {}),
        )
        digest_path = log_dir / f"{profile_name}-failure-digest.json"
        archived_digest_path = run_dir / f"{profile_name}-failure-digest.json"
        digest_path.write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")
        archived_digest_path.write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")
        failure_digest_artifacts.append(str(digest_path.relative_to(project_root)).replace("\\", "/"))

    harness_change_result = collect_harness_changes(project_root)
```

- [ ] **Step 5: Pass change and digest data into `build_run_manifest`**

Change the `build_run_manifest(...)` call to:

```python
    manifest = build_run_manifest(
        run_id=run_id,
        overall_passed=overall_passed,
        profiles=profiles,
        artifacts={
            "latest_report_json": str(json_path),
            "latest_report_markdown": str(markdown_path),
            "archived_report_json": str(archived_json_path),
            "archived_report_markdown": str(archived_markdown_path),
        },
        harness_changes=list(harness_change_result["harness_changes"]),
        harness_change_errors=list(harness_change_result["harness_change_errors"]),
        failure_digest_artifacts=failure_digest_artifacts,
    )
```

- [ ] **Step 6: Pass profile configs from `main()`**

In both `_write_harness_report(...)` calls inside `main()`, add:

```python
profile_configs=registry.profiles,
```

The failing branch becomes:

```python
            report_paths = _write_harness_report(
                project_root,
                profile_results,
                overall_passed=False,
                run_id=run_id,
                profile_configs=registry.profiles,
            )
```

The success branch becomes:

```python
    report_paths = _write_harness_report(
        project_root,
        profile_results,
        overall_passed=True,
        run_id=run_id,
        profile_configs=registry.profiles,
    )
```

- [ ] **Step 7: Run runner tests**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_harness_runner.py
```

Expected: PASS.

- [ ] **Step 8: Commit Task 3**

Run:

```powershell
git add scripts/verification/harness.py scripts/verification/tests/test_harness_runner.py
git commit -m "Attach decision observability to harness runs" -m "The runner now writes deterministic failed-profile digests and links active Harness change manifests in run manifests. Profile execution remains unchanged; the new data is attached only at report construction time." -m "Constraint: Do not change profile pass/fail semantics." -m "Rejected: Generating digests during each profile script | the runner already owns aggregate evidence and archive paths." -m "Confidence: high" -m "Scope-risk: narrow" -m "Tested: python -m pytest -q scripts/verification/tests/test_harness_runner.py"
```

## Task 4: Add Templates, Lifecycle Checks, and Docs

**Files:**
- Create: `.harness/changes/.gitkeep`
- Create: `.harness/templates/change-manifest-template.json`
- Modify: `scripts/verification/check_harness_lifecycle.py`
- Modify: `scripts/verification/tests/test_formal_profile_checks.py`
- Modify: `docs/harness.md`
- Modify: `.harness/features.json`

- [ ] **Step 1: Create the versionable changes directory marker**

Create `.harness/changes/.gitkeep` as an empty file.

- [ ] **Step 2: Create the change manifest template**

Create `.harness/templates/change-manifest-template.json` with:

```json
{
  "schema_version": 1,
  "id": "chg-20260624-example-decision-observability",
  "title": "Example Harness decision observability change",
  "status": "active",
  "created_at": "2026-06-24",
  "changed_files": [
    "scripts/verification/harness.py"
  ],
  "evidence_refs": [
    ".harness/verification/harness-run-diff.json"
  ],
  "root_cause_hypothesis": "One sentence describing the observed gap this change addresses.",
  "predicted_fixes": [
    {
      "profile": "docs",
      "claim": "The profile exposes the intended evidence after this change."
    }
  ],
  "predicted_regressions": [
    {
      "profile": "harness-lifecycle",
      "risk": "Lifecycle docs or templates may fall out of sync."
    }
  ],
  "verification_profiles": [
    "docs",
    "harness-lifecycle"
  ]
}
```

- [ ] **Step 3: Add lifecycle checks**

In `scripts/verification/check_harness_lifecycle.py`, add these paths after `retention_policy_path`:

```python
    changes_dir = project_root / ".harness" / "changes"
    change_manifest_template = project_root / ".harness" / "templates" / "change-manifest-template.json"
    harness_guide = project_root / "docs" / "harness.md"
```

Add these `_result(...)` entries after `lifecycle_templates_exist`:

```python
        _result(
            "lifecycle_decision_manifest_surface_exists",
            "Harness decision manifest directory and template exist",
            changes_dir.exists()
            and change_manifest_template.exists()
            and _contains(
                change_manifest_template,
                [
                    '"schema_version"',
                    '"predicted_fixes"',
                    '"predicted_regressions"',
                    '"verification_profiles"',
                ],
            ),
            [".harness/changes/", ".harness/templates/change-manifest-template.json"],
        ),
        _result(
            "lifecycle_decision_observability_docs_exist",
            "Harness guide documents decision observability and failure digest artifacts",
            _contains(
                harness_guide,
                [
                    "Decision Observability",
                    ".harness/changes/",
                    "failure-digest",
                    "harness_changes",
                ],
            ),
            ["docs/harness.md"],
        ),
```

- [ ] **Step 4: Update formal profile test assertions**

In `scripts/verification/tests/test_formal_profile_checks.py`, add these assertions inside `test_harness_lifecycle_profile_proves_project06_hardening_artifacts()`:

```python
    assert statuses["lifecycle_decision_manifest_surface_exists"] == "proved"
    assert statuses["lifecycle_decision_observability_docs_exist"] == "proved"
```

- [ ] **Step 5: Document the workflow in `docs/harness.md`**

Add this section before `## Evidence Rules`:

```markdown
## Decision Observability

Harness-facing changes can be recorded under `.harness/changes/` as decision manifests. These manifests are project inputs, not generated evidence. An active manifest records the evidence that motivated a Harness change, the root-cause hypothesis, predicted fixes, predicted regressions, and the profiles that should verify the change.

The Harness runner includes active manifests in `harness-run-manifest.json` under `harness_changes`. Malformed manifests are reported under `harness_change_errors` so normal profile runs remain usable while evidence problems stay visible.

When a profile fails, the runner writes a deterministic failure digest such as `.harness/verification/phase0-failure-digest.json` and archives the same digest under that run's `.harness/verification/runs/run-.../` directory. A digest is an index into existing reports and traces; it does not replace the original profile report or runtime trace.
```

- [ ] **Step 6: Record the feature in `.harness/features.json`**

Add a feature entry to the existing `features` array:

```json
{
  "id": "decision-observability",
  "title": "Harness decision observability records active change intent and failed-profile digests",
  "status": "pass",
  "evidence": ".harness/changes/, .harness/templates/change-manifest-template.json, harness-run-manifest.json:harness_changes"
}
```

Keep valid JSON formatting.

- [ ] **Step 7: Run lifecycle and docs checks**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_formal_profile_checks.py
python scripts/verification/harness.py --profile harness-lifecycle
python scripts/verification/harness.py --profile docs
```

Expected: all PASS.

- [ ] **Step 8: Commit Task 4**

Run:

```powershell
git add .harness/changes/.gitkeep .harness/templates/change-manifest-template.json scripts/verification/check_harness_lifecycle.py scripts/verification/tests/test_formal_profile_checks.py docs/harness.md .harness/features.json
git commit -m "Document harness decision observability lifecycle" -m "Decision-observability artifacts need to be discoverable and guarded by the existing lifecycle profile. This adds the change manifest template, docs, lifecycle checks, and feature ledger entry." -m "Constraint: Keep decision manifests as versionable project inputs, not generated evidence." -m "Confidence: high" -m "Scope-risk: narrow" -m "Tested: python -m pytest -q scripts/verification/tests/test_formal_profile_checks.py; python scripts/verification/harness.py --profile harness-lifecycle; python scripts/verification/harness.py --profile docs"
```

## Task 5: Final Verification and Plan Closeout

**Files:**
- Read: `.harness/verification/harness-run-manifest.json`
- Read: `.harness/verification/harness-run-report.md`
- Read: `.harness/verification/harness-lifecycle-report.md`
- Read: `.harness/verification/docs-report.md`

- [ ] **Step 1: Run the focused test suite**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_harness_runner.py scripts/verification/tests/test_formal_profile_checks.py
```

Expected: PASS.

- [ ] **Step 2: Run focused Harness profiles**

Run:

```powershell
python scripts/verification/harness.py --profile harness-lifecycle
python scripts/verification/harness.py --profile docs
```

Expected: both PASS.

- [ ] **Step 3: Inspect latest run manifest for new fields**

Run:

```powershell
python -c "import json; p='.harness/verification/harness-run-manifest.json'; data=json.load(open(p, encoding='utf-8')); print(data['schema_version']); print('harness_changes' in data); print('harness_change_errors' in data); print('failure_digest_artifacts' in data)"
```

Expected output:

```text
1
True
True
True
```

- [ ] **Step 4: Run broad verification if local runtime is available**

Run:

```powershell
python scripts/verification/harness.py --profile all
```

Expected: PASS when Godot and backend runtime prerequisites are healthy.

If Godot runtime is unavailable, record the skipped broad verification in the final report and include the focused profile evidence from Steps 1-3.

- [ ] **Step 5: Commit verification evidence only if source files changed after Task 4**

If Step 4 only updates ignored `.harness/verification/` outputs, do not commit generated evidence. If any source docs or tests needed fixes, inspect `git status --short`, then stage the exact source files shown by git. For this plan, the expected source file set is:

```text
scripts/verification/evidence.py
scripts/verification/harness.py
scripts/verification/check_harness_lifecycle.py
scripts/verification/tests/test_harness_runner.py
scripts/verification/tests/test_formal_profile_checks.py
docs/harness.md
.harness/features.json
.harness/changes/.gitkeep
.harness/templates/change-manifest-template.json
```

Commit with:

```powershell
git add scripts/verification/evidence.py scripts/verification/harness.py scripts/verification/check_harness_lifecycle.py scripts/verification/tests/test_harness_runner.py scripts/verification/tests/test_formal_profile_checks.py docs/harness.md .harness/features.json .harness/changes/.gitkeep .harness/templates/change-manifest-template.json
git commit -m "Stabilize harness decision observability verification" -m "Focused verification exposed small source drift after lifecycle integration, so this commit keeps the implementation aligned with the approved design." -m "Confidence: high" -m "Scope-risk: narrow" -m "Tested: python -m pytest -q scripts/verification/tests/test_harness_runner.py scripts/verification/tests/test_formal_profile_checks.py; python scripts/verification/harness.py --profile harness-lifecycle; python scripts/verification/harness.py --profile docs"
```

## Implementation Notes

- Do not edit Godot scenes, backend runtime code, Siming runtime code, or profile semantics.
- Keep failure digests deterministic and file-based.
- Do not infer causality from `predicted_fixes` or `predicted_regressions` in this implementation.
- Keep generated digest artifacts under `.harness/verification/` and run archive directories.
- Leave unrelated untracked `.codegraph/` files untouched.
