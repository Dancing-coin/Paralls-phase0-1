# Harness Reliability

## Evidence Retention

Every harness run writes latest evidence under `.harness/verification/` and immutable run-id evidence under `.harness/verification/runs/<run-id>/`.

The retention policy is declared in `.harness/retention-policy.json`:

- keep the latest `baseline.json`
- diff each new run against the previous baseline
- retain archived run directories under `.harness/verification/runs/`
- keep generated evidence ignored while preserving `.harness/profiles/`, `.harness/rules/`, `.harness/templates/`, and `.harness/ci/` as source inputs

## Local CI Equivalent

`.harness/ci/local-ci-gate.ps1` is the local equivalent of the GitHub Actions harness workflow. It runs focused verification tests, compiles verification scripts, and executes the full harness.

## Clean State

Use `.harness/clean-state-checklist.md` before ending a harness-hardening session. The checklist verifies tests, full harness evidence, profile/rule versionability, templates, and handoff state.

## Reference Coverage

Use `.harness/templates/HARNESS_CHECKLIST.md` before shipping a Harness Engineering change that adds tools, permissions, orchestration, memory/state, or verification surfaces. The `harness-reference` profile checks reference coverage against `.harness/references/awesome-harness-engineering.json`, so each borrowed Harness Engineering category has at least one current project artifact and a removal criterion.

## External CI Caveat

`.github/workflows/harness.yml` defines the hosted CI entry point. A hosted run still depends on provisioning Python and Godot on the runner. Until that run is observed externally, local CI equivalence remains the authoritative local proof.
