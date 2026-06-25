# Harness Evolution Agent Design

## Status

- Date: `2026-06-25`
- Status: `approved`
- Scope: `D:\Paralls-phase0-1\.worktrees\harness-decision-observability`
- Purpose: add a governed Evolution Agent prototype on top of the existing Harness decision-observability layer.
- Design mode: user-approved aggressive path, based on `Code as Agent Harness` and the existing `codex/harness-decision-observability` worktree.

## Source Grounding

The design applies the code-as-agent-harness framing to this repository's verification layer. The relevant paper treats code and code-adjacent artifacts as executable, inspectable, and stateful harness substrate. For this project, the concrete substrate is not a new agent runtime. It is the existing `.harness` evidence system:

- profile and rule manifests under `.harness/profiles/` and `.harness/rules/`
- decision manifests under `.harness/changes/`
- run manifests, baselines, diffs, reports, failure digests, screenshots, logs, and runtime traces under `.harness/verification/`
- workflow source-of-truth docs under `docs/harness.md` and `docs/ai-engineering-workflow.md`

The previous decision-observability design made harness-facing changes attributable by adding change manifests, failure digests, and run manifest links. This design extends that foundation into a minimal Evolution Agent lane: it can diagnose harness failures, propose governed harness mutation candidates, and evaluate those candidates against fixed replay expectations.

## Problem

The current harness can prove whether profiles pass, preserve run evidence, and connect active harness changes to failed profile digests. That is enough for reviewable evidence, but it does not yet support adaptive harness improvement.

After a profile fails repeatedly, a future agent still has to infer manually:

- whether the failure points to product behavior, missing validator coverage, weak failure digesting, profile policy, retry budget, stale docs, or rule evidence drift
- whether a proposed harness improvement is overfitting to a single run
- whether the proposal touches only harness policy or crosses into product runtime behavior
- which fixed replay checks should guard against regression
- whether a risky harness change requires human approval before promotion

Without this layer, harness evolution remains ad hoc. The system has evidence, but it does not yet have a governed path from telemetry to candidate improvement.

## Design Goal

Add a first-version Evolution Agent prototype for the harness itself.

The prototype should:

1. read existing harness telemetry from run archives, failure digests, diffs, reports, and decision manifests
2. produce a structured evolution report that clusters recurring harness failure patterns
3. propose candidate harness mutations as versionable manifests
4. classify candidate risk tiers and approval requirements
5. validate candidate manifests and replay-set coverage through a new `harness-evolution` profile

The prototype should not automatically apply patches, promote candidates, edit business runtime behavior, or change permission boundaries without human review.

## Chosen Approach

Use a governed Evolution Agent lane with two explicit modes:

- `analyze`: read telemetry and write a structured evolution report
- `propose`: run analysis and write one candidate mutation manifest

This is intentionally more aggressive than simply improving failure digests, but it remains governed. The Evolution Agent can create a proposal; it cannot silently change the operational harness. Promotion still happens through normal human-reviewed implementation, tests, and harness profiles.

The design adds one new profile:

```text
harness-evolution
```

Recommended `all` placement is after `harness-reference` and before expensive runtime profiles. The new profile checks harness meta-state before Phase 0 or Phase 1 Godot runtime evidence is collected.

## Architecture

### Versioned Evolution Inputs

`.harness/evolution/` becomes the versionable source-of-truth directory for the evolution lane.

Initial contents:

- `.harness/evolution/config.json`
- `.harness/evolution/replay-sets/default.json`
- `.harness/evolution/candidates/.gitkeep`

These files are project inputs. They should not be ignored as generated evidence.

### Generated Evolution Evidence

Generated reports stay under `.harness/verification/`.

Initial outputs:

- `.harness/verification/harness-evolution-report.json`
- `.harness/verification/harness-evolution-report.md`

These reports summarize analyzed run history, detected failure patterns, candidate recommendations, missing telemetry, and promotion readiness.

### Shared Pure Logic

`scripts/verification/evolution.py` owns deterministic helpers:

- schema readers
- replay-set validation
- candidate manifest validation
- run archive discovery
- failure digest discovery
- failure pattern aggregation
- risk-tier classification
- report construction

The module should avoid shell execution and filesystem mutation except through explicit caller-owned paths. This keeps focused unit tests cheap and deterministic.

### Analyze And Propose CLI

`scripts/verification/analyze_harness_evolution.py` is the CLI entrypoint.

Supported modes:

```powershell
python scripts/verification/analyze_harness_evolution.py --mode analyze
python scripts/verification/analyze_harness_evolution.py --mode propose --candidate-id evo-20260625-example
```

`analyze` writes only report artifacts.

`propose` writes the same report artifacts plus exactly one candidate manifest under `.harness/evolution/candidates/`.

### Profile Check

`scripts/verification/check_harness_evolution.py` validates evolution-lane governance:

- config schema is valid
- replay set schema is valid
- candidate manifests are valid
- risky candidates include approval requirements
- candidates stay inside harness mutation scope
- generated report exists after the analyzer has been run, when required by the profile policy

The profile is a deterministic sensor for the Evolution Agent itself.

## Data Model

### Evolution Config

Path:

```text
.harness/evolution/config.json
```

Initial shape:

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

`max_runs_to_analyze` prevents unbounded archive scans.

`profiles_in_scope` limits the first version to harness and high-value runtime evidence. It can include runtime profiles as telemetry sources without allowing product runtime mutation.

`allowed_mutation_types` constrains candidate generation to harness-facing changes.

`promotion_requires_profiles` records the minimum verification profiles that must pass before a candidate can be considered promotable.

### Replay Set

Path:

```text
.harness/evolution/replay-sets/default.json
```

Initial shape:

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

The replay set guards against optimizing only for the most recent failure. First-version replay is manifest-based and profile-based; it does not need to snapshot whole workspaces.

### Candidate Mutation Manifest

Path:

```text
.harness/evolution/candidates/<id>.json
```

Initial shape:

```json
{
  "schema_version": 1,
  "id": "evo-20260625-tighten-phase0-digest",
  "status": "proposed",
  "mutation_type": "failure_digest",
  "risk_tier": "sandbox-edit",
  "source_failures": [
    "run-20260625-000000-000000",
    "phase0"
  ],
  "hypothesis": "phase0 failures need resource-missing classification before raw Godot logs are inspected.",
  "proposed_changes": [
    {
      "path": "scripts/verification/evidence.py",
      "summary": "Classify missing res:// resources from Godot log snippets."
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

Allowed `status` values:

```text
proposed | evaluated | rejected | promoted
```

Allowed `risk_tier` values:

```text
read-only | sandbox-edit | full-access
```

Allowed `mutation_type` values come from `.harness/evolution/config.json`.

`proposed_changes[*].path` must point to harness-owned surfaces in the first version:

- `.harness/`
- `scripts/verification/`
- `docs/harness.md`
- `docs/ai-engineering-workflow.md`
- `.github/workflows/harness.yml`

Product runtime paths such as `backend/`, `scenes/`, `scripts/characters/`, or Siming runtime modules are out of scope for first-version candidates. If telemetry suggests product behavior is broken, the report should classify it as `product_runtime_failure`, not emit a harness mutation candidate that edits product code.

## Execution Flow

### Analyze Mode

Command:

```powershell
python scripts/verification/analyze_harness_evolution.py --mode analyze
```

Flow:

1. read `.harness/evolution/config.json`
2. read recent `.harness/verification/runs/*/run-manifest.json` up to `max_runs_to_analyze`
3. read referenced failure digest artifacts when present
4. read run diffs and active `.harness/changes/*.json` summaries when present
5. aggregate failure patterns:
   - repeated profile failures
   - repeated rule or check misses
   - failed profiles without structured checks
   - missing runtime trace refs for runtime profiles
   - retry budget anomalies
   - active change verification profiles not matching actual failed profiles
6. write `harness-evolution-report.json` and `harness-evolution-report.md`

### Propose Mode

Command:

```powershell
python scripts/verification/analyze_harness_evolution.py --mode propose --candidate-id evo-20260625-example
```

Flow:

1. execute the same analysis flow
2. choose one candidate mutation from the highest-confidence harness-owned failure pattern
3. write one candidate manifest under `.harness/evolution/candidates/`
4. leave all operational harness files unchanged

`propose` mode must fail if the candidate id already exists. Candidate manifests are reviewable project inputs and should not be overwritten implicitly.

## Governance

The Evolution Agent does not promote its own work.

Promotion requires a normal implementation path:

1. human reviews a candidate manifest
2. implementation plan converts the candidate into concrete edits
3. edits are made through normal repository workflow
4. focused unit tests pass
5. required promotion profiles pass
6. broad harness verification runs when the change affects shared policy

Risk gating:

- `read-only`: analysis, docs, report schema, or candidate manifest changes
- `sandbox-edit`: local harness code, profile policy, rule evidence, failure digest, docs gate, retry policy
- `full-access`: network, credentials, release/publish, destructive filesystem operations, deployment, Git history mutation, CI secrets, permission boundaries

Any `full-access` candidate must set:

```json
"requires_human_approval": true
```

The `harness-evolution` profile must fail if a risky candidate omits that flag.

First-version candidates should normally be `read-only` or `sandbox-edit`. `full-access` is included in the schema so the gate is explicit if a future candidate crosses that boundary.

## Error Handling

The evolution lane should not make ordinary profile verification unusable.

- Missing config: `harness-evolution` fails with a structured missing result.
- Invalid config: `harness-evolution` fails and reports schema errors.
- No run history: analyzer writes `insufficient_history`; this is not a crash.
- Missing failure digest refs: analyzer records `missing_digest_refs`; candidate confidence is reduced.
- Malformed candidate manifest: `harness-evolution` fails.
- Risky candidate without required approval: `harness-evolution` fails.
- Proposed change path outside harness scope: candidate is rejected as `out_of_scope`.
- Unsupported mutation type: candidate is rejected as `unsupported_mutation_type`.
- Existing candidate id in propose mode: analyzer exits non-zero without overwriting.

## Testing

Focused tests should cover `scripts/verification/evolution.py` and the analyzer/profile integration.

Minimum cases:

- valid evolution config loads
- invalid config produces deterministic errors
- replay set validates expected artifacts and regression guards
- candidate schema validates required fields and status values
- risky candidate requires `requires_human_approval`
- out-of-scope product runtime paths are rejected
- recent run manifests are discovered in stable order
- repeated profile failures are aggregated into a report pattern
- missing failure digest references degrade confidence rather than crashing
- propose mode writes exactly one candidate manifest
- propose mode refuses to overwrite an existing candidate id
- `harness-evolution` profile is registered and documented

Minimum validation command set:

```powershell
python -m pytest -q scripts/verification/tests/test_harness_evolution.py
python scripts/verification/harness.py --profile harness-evolution
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile harness-lifecycle
```

Broad verification remains:

```powershell
python scripts/verification/harness.py --profile all
```

Known current risk: broad `all` may still fail for pre-existing runtime or Godot resource issues unrelated to this design. Such failures should be reported as residual runtime risk, not hidden.

## Documentation Updates

Implementation should update:

- `docs/harness.md` with the `harness-evolution` profile, command surface, and Evolution Agent workflow
- `docs/ai-engineering-workflow.md` with the rule that Evolution Agent candidates are proposals, not approval to patch
- `.harness/features.json` with the evolution lane after implementation evidence exists
- `.harness/templates/` only if the implementation needs a reusable candidate template

## Non-Goals

- no automatic patch application
- no automatic promotion of candidate manifests
- no LLM-generated source edits in this first version
- no product runtime edits from the Evolution Agent
- no Godot scene, backend authority, Siming runtime, or character runtime behavior changes
- no new third-party dependencies
- no whole-workspace snapshot or container replay system
- no replacement of existing profile pass/fail semantics
- no causal proof that a harness change fixed a later run

## Success Criteria

The implementation is successful when:

- `.harness/evolution/` records valid config, replay set, and candidate manifests
- `analyze` mode writes a structured evolution report from existing harness telemetry
- `propose` mode writes a governed candidate manifest without changing operational harness files
- risky candidates cannot pass `harness-evolution` without explicit approval requirements
- out-of-scope product runtime edits are rejected as harness mutation candidates
- `harness-evolution` is registered, documented, and covered by focused tests
- `docs`, `harness-lifecycle`, and `harness-evolution` pass after implementation
