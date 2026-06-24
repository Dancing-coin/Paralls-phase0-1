# Harness Decision Observability Design

## Status

- Date: `2026-06-24`
- Scope: `D:\Paralls-phase0-1`
- Purpose: add a minimal decision-observability layer to the existing Harness evidence chain.
- Decision mode: user-approved brainstorming scope B, based on `Agentic Harness Engineering: Observability-Driven Automatic Evolution of Coding-Agent Harnesses`.

## Problem

The current Harness already produces strong run evidence through profile reports, run manifests, archived run directories, baselines, diffs, and runtime traces. Agents can verify whether a profile passed or failed, and they can compare the latest run with the previous baseline.

The remaining gap is attribution context. A later agent can see that a Harness run changed, but it cannot reliably answer:

- which Harness-facing change was intended to affect the run
- what evidence motivated that change
- which profiles the change was expected to fix
- which profiles were considered regression risks
- where to start reading when a profile fails

Without that decision layer, Harness improvement remains mostly memory-driven. The goal of this design is to make Harness changes easier to review, test, and repair without introducing automatic rollback or changing runtime behavior.

## Design Goal

Upgrade the existing Harness evidence chain into a minimal, deterministic decision-observability system.

The first version should provide:

1. a versionable change manifest input surface
2. generated failure digest artifacts for failed profiles
3. run manifest links that connect active Harness changes to generated failure summaries

The goal is not to create a self-evolving Harness agent. The goal is to make future Harness edits attributable, predictable, and easier for agents to inspect.

## Chosen Approach

Use a lightweight schema plus runner integration.

This design adds:

1. `.harness/changes/` for active and historical Harness change manifests
2. deterministic failure digest generation under `.harness/verification/`
3. `harness_changes` and `failure_digest_artifacts` fields in `harness-run-manifest.json`
4. lifecycle/docs checks so the decision-observability workflow remains discoverable

It deliberately avoids:

- automatic rollback
- LLM-generated summaries
- causal attribution claims
- changes to Godot runtime, backend authority behavior, Siming logic, or existing profile semantics

## Architecture

### Decision Manifest Input

`.harness/changes/` becomes the versionable input directory for Harness-facing change manifests. Each manifest records the evidence, hypothesis, intended fixes, regression risks, and verification profiles for one logical Harness change.

The initial schema is intentionally small:

```json
{
  "schema_version": 1,
  "id": "chg-20260624-harness-failure-digest",
  "title": "Add failure digest evidence to harness runs",
  "status": "active",
  "created_at": "2026-06-24",
  "changed_files": [
    "scripts/verification/harness.py",
    "scripts/verification/evidence.py"
  ],
  "evidence_refs": [
    ".harness/verification/harness-run-diff.json",
    ".harness/verification/phase0-report.json"
  ],
  "root_cause_hypothesis": "Agents need a compact profile-level failure summary before reading raw reports and traces.",
  "predicted_fixes": [
    {
      "profile": "phase0",
      "claim": "A failed phase0 run exposes primary failed checks and trace refs in one digest artifact."
    }
  ],
  "predicted_regressions": [
    {
      "profile": "harness-lifecycle",
      "risk": "New evidence files may not be documented or checked by lifecycle rules."
    }
  ],
  "verification_profiles": [
    "harness-lifecycle",
    "docs"
  ]
}
```

Supported `status` values are:

- `active`: included in new run manifests
- `superseded`: retained for history but not included in new run manifests
- `rejected`: retained for history but not included in new run manifests

The Harness runner should not attempt to prove that a manifest caused a later pass or failure. It should only surface the declared intent next to the run evidence.

### Failure Digest Output

When a profile fails, the Harness runner writes a deterministic digest under `.harness/verification/<profile>-failure-digest.json`. The digest is an index into existing evidence, not a replacement for profile reports or traces.

The initial digest shape is:

```json
{
  "schema_version": 1,
  "run_id": "run-...",
  "profile": "phase0",
  "status": "failed",
  "exit_code": 1,
  "summary_status": "structured_checks_extracted",
  "primary_report": ".harness/verification/phase0-report.json",
  "failed_checks": [
    {
      "id": "dialogue_loop_observable",
      "status": "missing",
      "evidence": []
    }
  ],
  "runtime_trace_refs": [
    ".harness/verification/phase0-runtime-trace.ndjson"
  ],
  "source_artifacts": [
    ".harness/verification/phase0-report.json",
    ".harness/verification/phase0-report.md"
  ]
}
```

The digest should copy only compact check metadata. It should reference runtime traces by path rather than embedding trace rows.

### Run Manifest Integration

`scripts/verification/harness.py` continues to own profile execution and report writing. During report construction it calls `scripts/verification/evidence.py` helpers to:

1. read active manifests from `.harness/changes/`
2. generate failure digest artifacts for failed profiles
3. include both surfaces in the latest and archived run manifests

The extended `harness-run-manifest.json` shape adds:

```json
{
  "harness_changes": [
    {
      "id": "chg-20260624-harness-failure-digest",
      "status": "active",
      "path": ".harness/changes/chg-20260624-harness-failure-digest.json",
      "verification_profiles": [
        "harness-lifecycle",
        "docs"
      ]
    }
  ],
  "failure_digest_artifacts": [
    ".harness/verification/phase0-failure-digest.json"
  ]
}
```

Existing `baseline.json` and `harness-run-diff.json` keep their current roles. They compare run manifests and profile exit codes; they do not become attribution engines.

## Data Flow

1. An agent or developer creates `.harness/changes/<id>.json` for a Harness-facing change.
2. A normal Harness command runs, for example `python scripts/verification/harness.py --profile phase0`.
3. If a profile fails, the runner writes a profile failure digest in `.harness/verification/`.
4. The runner writes latest and archived run reports.
5. The runner writes latest and archived run manifests with active change summaries and failure digest artifact refs.
6. The runner updates `baseline.json` and `harness-run-diff.json` using the existing diff path.

## Error Handling

Bad change manifests should not make ordinary profile verification unusable. The runner records manifest read or schema errors in a `harness_change_errors` field and continues profile reporting.

If a profile report does not exist, the digest still records the profile name, command, and exit code, with `primary_report` set to `null`.

If structured checks cannot be extracted from a profile report, the digest writes:

```json
{
  "failed_checks": [],
  "summary_status": "profile_failed_without_structured_checks"
}
```

If runtime trace artifacts are absent, `runtime_trace_refs` remains an empty list. Static profiles should not be treated as missing runtime evidence.

## Testing

Focused tests should cover the deterministic evidence helpers and the runner integration:

- active manifests are collected
- `superseded` and `rejected` manifests are ignored by new run manifests
- invalid manifests are recorded without interrupting ordinary profile reporting
- failed profiles produce failure digest artifacts
- reports without structured checks produce a degraded digest
- run manifests include `harness_changes` and `failure_digest_artifacts`

The lifecycle check should verify:

- `.harness/changes/` exists
- a change manifest template or documented schema exists
- `docs/harness.md` describes the decision-observability workflow

Minimum validation for the implementation plan:

```powershell
python -m pytest -q scripts/verification/tests/test_harness_runner.py
python scripts/verification/harness.py --profile harness-lifecycle
python scripts/verification/harness.py --profile docs
```

Broader verification remains:

```powershell
python scripts/verification/harness.py --profile all
```

## Non-Goals

- no automatic rollback
- no LLM-generated failure summaries
- no causal attribution report in the first version
- no new third-party dependencies
- no change to profile pass/fail semantics
- no change to Godot runtime behavior
- no change to backend authority behavior
- no change to Siming runtime behavior

## Success Criteria

- each Harness-facing change can record its evidence, hypothesis, predicted fixes, predicted regressions, and verification profiles
- each failed profile can emit a compact failure digest that points to the relevant report and trace artifacts
- each run manifest links active Harness changes and generated failure digest artifacts
- invalid change manifests are visible as evidence problems but do not block ordinary profile runs
- existing Harness baseline and diff behavior remains compatible
- docs and lifecycle checks make the workflow discoverable to future agents
