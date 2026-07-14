# Harness Engineering Optimization Design

## Status

- Date: 2026-07-14
- Status: awaiting-user-review
- Scope: D:/Paralls-phase0-1
- Extends: docs/superpowers/specs/2026-06-03-harness-engineering-design.md
- Reference: https://lilianweng.github.io/posts/2026-07-04-harness/
- Decision mode: design sections approved interactively; this written artifact awaits final user review before implementation planning

## Executive Summary

Paralls already has a useful repository-owned Harness Engineering layer:

- versioned profile and rule registries
- one stable runner command family
- generated reports and run archives
- failure digests and runtime traces
- governed evolution candidate manifests
- explicit OpenSpec, Superpowers, Harness, and Goal workflow boundaries

The next optimization should not replace that architecture. It should evolve it into two deliberately separated layers:

1. Core Harness records deterministic facts, executes verifiers, owns acceptance, and preserves evidence.
2. Agent Harness selects relevant context, proposes root-cause hypotheses, and writes reviewable candidate manifests without changing verifier truth or applying patches.

The work proceeds in three independently deliverable stages:

- P0 Core Observability: make every run attributable and comparable.
- P1 Feedback Efficiency: reduce unnecessary verification work without weakening acceptance.
- P2 Governed Evolution: generate evidence-grounded Harness proposals with held-in and held-out evaluation.

## Problem

The current Harness is strong at declaring whether a profile passed, but weak at explaining the run as a whole.

Current aggregate evidence primarily records:

- selected profile
- command
- exit code
- attempt count
- links to some generated reports and failure digests

This leaves several gaps:

1. Run attribution is incomplete.
   Aggregate records do not consistently preserve duration, environment identity, stdout/stderr references, process termination state, or a deterministic terminal-cause classification.

2. Baselines are not selection-aware.
   A single-profile run can become the previous baseline for a later full run. The resulting diff reports many meaningless null-to-zero changes rather than a comparable regression.

3. CI and local runtime proof are conflated.
   The hosted workflow still invokes the full and mainline runtime entry points even though Godot runtime proof is a local acceptance responsibility. GitHub CI should execute a registry-derived non-Godot suite.

4. Retention policy is declarative rather than operational.
   The policy declares a bounded full archive, while the generated run directory can grow indefinitely.

5. Evolution analysis observes symptoms more than mechanisms.
   It can count recurring profile and check failures, but it does not yet have enough structured telemetry to distinguish environment failures, timeouts, verifier failures, product regressions, missing evidence, or different causal mechanisms that share one surface error.

6. Agent inference and verifier truth are not represented as separate data types.
   Future root-cause analysis must not overwrite deterministic run facts.

## Goals

### P0 Goals

- Record every run, profile, and attempt with enough evidence to explain what happened.
- Separate deterministic terminal cause from inferred root cause.
- Compare only compatible baseline families.
- Preserve the existing local full-Harness command.
- Move hosted CI to a non-Godot suite derived from versioned manifests.
- Keep old evidence readable without rewriting archived runs.

### P1 Goals

- Recommend the smallest relevant profile set for a change.
- Explain why each profile was selected.
- Keep profile selection advisory; it must not replace broad completion gates.
- Add a searchable run index and suite-aware comparison.
- Enforce tiered evidence retention with durable pins.

### P2 Goals

- Build bounded context packs from structured evidence.
- Generate falsifiable root-cause hypotheses with confidence and evidence references.
- Generate candidate manifests rather than patches.
- Use triggering failures as held-in cases.
- Use independent canaries and preserved successful behavior as held-out guards.
- Require human approval and the normal spec, plan, implementation, and verification workflow before operational Harness behavior changes.

## Non-Goals

- No changes to Backend, Godot, Siming, ESM, character cognition, or world-truth authority.
- No automatic application of Agent Harness proposals.
- No candidate permission to modify verifier logic, held-out canaries, CI permissions, model configuration, or original run evidence.
- No model-weight training or joint model and Harness optimization.
- No external observability platform, database, queue, or service.
- No replacement of existing narrow verification scripts.
- No claim that repository-visible held-out fixtures are cryptographically secret.
- No change that allows advisory profile selection to satisfy a broad completion claim.

## Design Principles

### Facts And Inference Stay Separate

Core Harness owns observed facts and deterministic verdicts. Agent Harness may append hypotheses, but it cannot rewrite:

- exit codes
- timestamps
- terminal causes
- structured check results
- artifact references
- suite verdicts

### The Evaluator Stays Outside The Evolution Loop

Candidate generation cannot edit:

- profile verifier implementations used for evaluation
- rule manifests selected as protected acceptance truth
- held-out canary cases
- model or reasoning budgets
- CI permission boundaries

### Suggestions Do Not Become Acceptance

Change-aware selection exists to accelerate development feedback. The final command for broad local completion remains the complete local suite.

### Evidence Is File-Native And Layered

The file system remains the durable state surface:

- detailed evidence for recent and pinned runs
- compact manifests for older runs
- indexes for discovery
- on-demand access to full logs when retained

### Compatibility Comes Before Cleanup

Schema v2 readers must continue to read schema v1 artifacts. Existing archives are not rewritten in place.

## Architecture

~~~text
User / approved spec
        |
        v
Protected authority zone
  - verifier and rules
  - held-out canaries
  - CI and model configuration
        |
        v
Core Harness
  - suite registry
  - advisory impact selector
  - runner and attempt telemetry
  - terminal-cause classifier
  - evidence store, baseline families, index, retention
        |
        +------------------------------+
        | deterministic facts/verdicts |
        +------------------------------+
                       |
                       v
Agent Harness
  - context-pack builder
  - failure analyst
  - root-cause hypotheses
  - candidate proposer
  - evaluation brief
                       |
                       v
Human approval
  -> normal spec
  -> normal plan
  -> implementation
  -> held-in and held-out evaluation
  -> Core Harness verdict
~~~

## Core Harness Components

### Suite Registry

Profiles remain the smallest executable verification units. Suites become named, versioned selections of profiles.

Initial suites:

- local-full: every profile currently included in all, including local Godot runtime proof
- ci-non-godot: profiles eligible for broad verification that require neither Godot nor live provider credentials
- held-out-canary: protected evaluation cases used after an approved Harness implementation

Backward compatibility:

- --profile NAME continues to run one profile.
- --profile all remains an alias for local-full.
- a new --suite NAME entry point selects a versioned suite.

Profile manifests gain explicit metadata:

- requires_godot
- requires_live_credentials
- include_in_all
- timeout_seconds
- retry_on
- failure_domain
- watch_paths
- depends_on_profiles
- risk_class

Legacy manifests receive conservative defaults in the loader. Live-provider profiles must be explicitly marked as requiring credentials.

### Advisory Impact Selector

The selector maps changed paths to profile manifests through watch_paths and dependency metadata.

It writes a selection report containing:

- changed paths
- recommended profiles
- transitive dependencies
- a reason for every recommendation
- uncovered or unknown paths
- verification scope not covered by the recommendation

Unknown paths cause conservative expansion rather than optimistic omission.

The selector never writes a pass verdict. A report produced from recommended profiles must state that broad completion remains unverified until the relevant suite runs.

### Runner And Attempt Telemetry

The runner creates a provisional attempt record before starting each subprocess. It streams process output to run-owned log files and atomically finalizes the record after the process exits.

Every attempt records:

- normalized command
- start and finish timestamps
- duration
- exit code
- process completion state
- deterministic terminal cause
- log and artifact references
- environment requirements and resolution

### Terminal-Cause Classifier

Core classification is intentionally narrow and deterministic.

Initial terminal causes:

- environment_missing
- timeout
- process_crash
- report_missing
- report_invalid
- structured_check_failed
- interrupted
- unknown

Failure domain is separately derived from manifest or structured-check metadata:

- environment
- harness
- product
- evidence
- unknown

Core does not claim a deeper mechanism such as race condition, incorrect routing, or stale documentation unless a verifier emits that fact explicitly.

### Evidence Store

The evidence store owns:

- latest convenience artifacts
- immutable retained run artifacts
- baseline-family pointers
- suite-aware diffs
- compact historical manifests
- a searchable run index
- evidence pins

All stored paths must be repository-relative. Machine-local absolute paths may appear only inside raw logs where they are unavoidable.

## Agent Harness Components

### Context-Pack Builder

The builder selects only evidence relevant to a failure family or candidate:

- run and profile facts
- failed structured checks
- environment summary
- selected log excerpts
- prior hypotheses and candidate outcomes
- preserved passing behavior

It does not copy every historical log into one context.

### Failure Analyst

The analyst produces RootCauseHypothesis records. A hypothesis includes:

- hypothesis_id
- source failure facts
- proposed causal mechanism
- target Harness component
- confidence
- supporting and contradicting evidence
- expected fix
- at-risk regressions

Hypotheses are append-only interpretations. They cannot replace FailureFact records.

### Candidate Proposer

The proposer writes candidate manifests only. A candidate is not a patch and not implementation approval.

Candidate manifests include:

- source failure facts
- hypothesis reference
- bounded proposed changes
- editable-surface allowlist
- expected fixes
- at-risk regressions
- held-in case references
- held-out suite reference
- required promotion profiles
- human approval requirement
- QA evidence references

The initial P2 proposal allowlist is deliberately limited to Agent-facing Harness surfaces:

- AGENTS.md
- docs/ai-engineering-workflow.md
- Harness workflow and reliability documentation
- .harness/templates/
- repository-local context, memory, workflow, and Agent configuration introduced for the Agent Harness

Core runner code, verifier implementations, profile and rule truth, suite definitions, retention enforcement, CI configuration, held-out artifacts, and product runtime paths are outside the initial candidate scope.

Expanding candidates into Core Harness code is a separate future design decision. It is not implied by this design.

### Evaluation Brief

After a human approves a candidate and normal implementation occurs, the evaluation brief compares:

- held-in outcomes against the motivating failures
- held-out outcomes against canaries and preserved successes
- predicted effects against observed effects
- new regressions or telemetry gaps

Only Core Harness verifiers decide whether the implementation passed.

## Data Contracts

### RunRecord

RunRecord schema v2 contains:

- schema_version
- run_id
- suite_id
- selection_mode
- selected_profiles
- selected_profile_set_hash
- git_commit
- git_dirty
- environment_fingerprint
- started_at
- finished_at
- duration_ms
- overall_verdict
- profile_results
- artifact_refs
- active_harness_change_refs

Selection mode is one of:

- explicit-profile
- explicit-suite
- legacy-all
- advisory-selection
- held-out-evaluation

### EnvironmentFingerprint

The environment fingerprint contains bounded, non-secret values:

- operating system and architecture
- Python executable identity and version
- Godot availability and version when resolved
- runner schema version
- relevant declared capability flags

It must not capture credentials, tokens, environment-variable values, user directories beyond normalized executable identity, or arbitrary host metadata.

### ProfileAttemptRecord

ProfileAttemptRecord schema v2 contains:

- profile
- attempt
- command
- started_at
- finished_at
- duration_ms
- completion_state
- exit_code
- terminal_cause
- failure_domain
- stdout_ref
- stderr_ref
- structured_report_ref
- trace_refs
- screenshot_refs
- source_artifact_refs

Completion state is one of:

- passed
- failed
- timed_out
- preflight_failed
- interrupted

If an earlier attempt fails and a later attempt passes, the aggregate profile status is flaky_pass rather than passed.

### FailureFact

FailureFact is Core-owned and contains:

- fact_id
- run_id
- profile
- attempt
- terminal_cause
- failure_domain
- failed_check_ids
- evidence_refs
- observed_notes

### RootCauseHypothesis

RootCauseHypothesis is Agent-owned and contains:

- hypothesis_id
- failure_fact_refs
- target_component
- causal_mechanism
- confidence
- supporting_evidence_refs
- contradicting_evidence_refs
- expected_fix
- at_risk_regressions

### Compatibility

Schema readers accept v1 and v2:

- v1 paths are normalized when possible at read time.
- missing v2 fields become explicit legacy_unknown values.
- v1 archives are never rewritten.
- diffs between v1 and v2 require a compatible normalized baseline family; otherwise the result is no_comparable_baseline.

## Baseline Families And Diffing

A baseline is comparable only when all of the following match:

~~~text
schema_version
+ suite_id
+ selected_profile_set_hash
+ environment_class
~~~

Environment class distinguishes at minimum:

- local-with-godot
- local-without-godot
- hosted-ci-non-godot
- held-out-evaluator

When no compatible baseline exists, the diff records no_comparable_baseline. It must not synthesize a list of null-to-zero profile changes.

Diff output includes:

- profile verdict changes
- attempt-count changes
- duration changes
- terminal-cause changes
- structured-check changes
- artifact availability changes

Duration regressions are evidence, not automatic failures, until an explicit budget rule exists.

## Retention And Pins

Retention is tiered:

1. Keep the most recent 25 unpinned runs with full reports, logs, traces, screenshots, and attempt records.
2. Always keep the latest successful compatible baseline for every active baseline family.
3. Preserve compact RunRecord, FailureFact, metrics, and index entries for older runs.
4. Permanently pin runs referenced by:
   - active or historical Harness candidates
   - QA review artifacts
   - release evidence
   - explicit human pin manifests

Compaction is two-phase:

1. Write and validate the compact record and verify every pin.
2. Remove only bulky artifacts that the compact record declares removable.

Compaction must be idempotent. An interrupted compaction cannot leave a run without either its full or validated compact representation.

## Retry And Failure Handling

Retries are explicit manifest policy.

- max_attempts remains supported.
- retry_on lists eligible terminal causes.
- structured product or verifier failures are not retried unless the manifest explicitly identifies a transient subclass.
- missing environment requirements fail before subprocess execution.
- timeouts terminate only the process tree started for that attempt.
- interrupted runs preserve provisional records and logs.
- missing or invalid reports produce FailureFacts rather than crashing aggregate report generation.

The console prints concise progress and artifact locations. Full subprocess output remains in files.

## CI And Local Verification

### Hosted CI

GitHub Actions runs ci-non-godot.

Suite resolution must prove that every selected profile:

- has requires_godot set to false
- has requires_live_credentials set to false
- is included by the suite manifest

The release-gate verifier checks the resolved suite rather than searching for hardcoded full-runtime commands.

Hosted CI uploads the compact run bundle and failure artifacts when available.

### Local Broad Completion

Local broad completion remains:

~~~powershell
python scripts/verification/harness.py --profile all
~~~

This continues to include Godot-backed runtime proof when the local environment provides Godot.

Advisory selections may be used during development, but their reports must never claim local-full completion.

## Held-In And Held-Out Evaluation

Held-in cases are the real failures that motivated a candidate. They are expected to improve after an approved implementation.

Held-out evaluation combines:

- fixed canary cases
- previously passing behavior
- protected regression profiles
- selected historical negative results not used to generate the candidate

The proposal context contains only the held-out suite identity and risk categories, not raw held-out case details or results.

Because repository-local fixtures may still be readable by a sufficiently privileged agent, this is a logical and permission-governed holdout rather than cryptographic secrecy. The protection comes from:

- excluding held-out artifacts from candidate mutation scope
- excluding raw canary content from generated proposal context
- running evaluation through Core Harness
- requiring human review of candidate and evaluation evidence

## Delivery Stages

Implementation planning should produce one master plan with three explicit phase checkpoints. P1 work does not begin until the P0 acceptance gate passes, and P2 work does not begin until the P1 acceptance gate passes. Each checkpoint must leave the repository in a supported, independently verifiable state.

### P0 Core Observability

Deliverables:

- schema v2 models and compatibility readers
- suite registry and local-full compatibility alias
- ci-non-godot suite
- attempt-level logging, timing, timeout, and interruption records
- deterministic terminal-cause classification
- environment fingerprinting
- compatible baseline families and suite-aware diffing
- updated release-gate semantics

P0 acceptance:

- every synthetic failure mode produces a complete FailureFact
- incompatible selections produce no_comparable_baseline
- CI suite resolves no Godot or credential-backed profile
- local --profile all behavior remains available
- current aggregate reports remain readable through compatibility views

### P1 Feedback Efficiency

Deliverables:

- watch-path and dependency metadata
- advisory change-impact selection
- selection report with reasons and uncovered scope
- run index and baseline-family queries
- tiered retention, compaction, and pin manifests

P1 acceptance:

- known file changes select the expected profiles and dependencies
- unknown paths expand conservatively
- advisory runs cannot satisfy broad completion
- compaction is idempotent
- pinned evidence and latest compatible baselines survive retention

### P2 Governed Evolution

Deliverables:

- context-pack builder
- RootCauseHypothesis records
- richer candidate manifest schema
- held-in and held-out evaluation brief
- component, experience, and decision observability reports

P2 acceptance:

- a recurring failure family produces an evidence-linked, falsifiable candidate
- Agent output cannot mutate Core facts
- candidates cannot target protected paths
- candidates do not apply code
- promotion-ready state requires human approval, QA artifacts, held-in improvement, and no held-out regression
- operational Harness changes still enter through the normal repository workflow

## Testing Strategy

### Unit Tests

P0:

- v1 and v2 manifest loading
- path normalization
- environment fingerprint redaction
- terminal-cause classification
- timeout and interruption handling
- retry eligibility and flaky_pass
- baseline-family matching
- CI suite filtering

P1:

- change-path matching
- dependency closure
- conservative unknown-path handling
- selection explanation
- run index queries
- retention pins
- compaction idempotence

P2:

- context-pack bounds
- immutable Core facts
- hypothesis validation
- candidate path allowlist
- lifecycle and QA gates
- held-out exclusion from proposal context
- evaluation-brief comparison

### Synthetic Integration Profiles

The runner test fixture set includes profiles that:

- pass with a structured report
- fail with structured checks
- exit without a report
- write invalid JSON
- crash
- time out
- fail once and pass on retry
- are interrupted with partial output

### Regression Verification

Implementation must preserve the existing focused test surfaces and add targeted tests beside:

- harness runner
- registry
- formal profile checks
- harness evolution
- docs checks

Godot-backed behavior is verified locally through the existing runtime profiles. CI-specific tests verify suite resolution without invoking Godot.

## Security And Permission Boundaries

- Core evidence files are append-only for Agent Harness consumers.
- Candidate manifests use explicit path allowlists.
- Protected paths cannot be proposed as changes.
- Credentials and environment-variable values are never persisted.
- Held-out evaluators and rules are outside candidate mutation scope.
- Agent hypotheses always cite Core evidence.
- No automatic patch, rollback, merge, or promotion is introduced.

## Documentation And Registry Follow-Through

Implementation must keep the following synchronized:

- docs/harness.md
- docs/harness-architecture.md
- docs/harness-reliability.md
- docs/ai-engineering-workflow.md
- .harness/profiles/
- .harness/rules/
- suite manifests introduced by this design
- scripts/verification/tests/test_harness_registry.py
- release-gate metadata and workflow

Any new profile or suite must have:

- a versioned manifest
- documented purpose and evidence
- registry tests
- a deterministic report surface

## Risks And Mitigations

### Schema Complexity

Risk: telemetry fields make the runner harder to understand.

Mitigation: keep schemas in focused modules, keep the runner as orchestration, and preserve narrow profile scripts.

### False Causal Confidence

Risk: Agent analysis presents a plausible story as fact.

Mitigation: store hypotheses separately, require confidence and contradicting evidence, and preserve Core terminal cause.

### Overfitting To Held-In Cases

Risk: a candidate fixes the observed failure but damages unrelated behavior.

Mitigation: held-out canaries, preserved success behavior, and no-regression promotion rules.

### Retention Data Loss

Risk: compaction removes evidence still needed by a candidate or release.

Mitigation: explicit pins, two-phase compaction, latest-baseline preservation, and idempotence tests.

### Advisory Selection Becomes A Shortcut

Risk: a focused run is reported as full completion.

Mitigation: selection reports explicitly list uncovered scope and cannot emit a broad suite verdict.

### CI Scope Drifts Back Toward Godot

Risk: future workflow edits reintroduce runtime profiles.

Mitigation: release-gate evaluates resolved suite capabilities and fails if any CI-selected profile requires Godot or live credentials.

## Success Criteria

This design is successfully implemented when:

- Core Harness can explain every run without Agent inference.
- Agent Harness can propose a root cause without changing Core truth.
- baseline diffs compare only compatible runs.
- hosted CI runs only the non-Godot, non-credential suite.
- local full verification retains Godot runtime proof.
- advisory profile selection reduces feedback work without weakening acceptance.
- recent evidence is detailed, historical evidence is compact, and referenced evidence remains pinned.
- every evolution candidate is traceable to failure facts and predicted outcomes.
- no candidate applies itself or edits protected evaluator surfaces.
- held-in improvement and held-out non-regression are required before a Harness implementation is considered promotion-ready.

## Final Decisions

- Use a two-layer Core Harness and Agent Harness architecture.
- Implement all three stages in order: attribution, feedback efficiency, governed evolution.
- Keep Agent Harness candidate-only.
- Keep change-aware selection advisory.
- Use mixed held-in and held-out evaluation.
- Use tiered retention with permanent evidence pins.
- Separate deterministic failure facts from Agent root-cause hypotheses.
- Keep local full runtime proof and hosted non-Godot CI as distinct acceptance surfaces.
