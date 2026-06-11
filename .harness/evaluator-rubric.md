# Harness Evaluator Rubric

## Scoring

| Criterion | Target | Evidence |
| --- | --- | --- |
| Instructions | Agent can discover `AGENTS.md`, `docs/INDEX.md`, and `docs/harness.md`. | `docs` profile |
| Scope | Profiles and feature ledger define current and future verification scope. | `.harness/features.json`, `.harness/profiles/` |
| Verification | Focused tests, static profiles, and runtime profiles pass. | `harness.py --profile all` |
| Reference coverage | External Harness Engineering categories are mapped to maintained project artifacts. | `.harness/references/awesome-harness-engineering.json`, `harness-reference` profile |
| State | Run manifest, baseline, diff, and session handoff preserve continuity. | `.harness/verification/`, `.harness/session-handoff.md` |
| Lifecycle | Local CI gate and clean-state checklist define start/end flow. | `.harness/ci/local-ci-gate.ps1`, `.harness/clean-state-checklist.md` |
| Reliability | Retention policy and reliability docs explain evidence handling. | `.harness/retention-policy.json`, `docs/harness-reliability.md` |

## Passing Standard

The harness is acceptable when every profile in `.harness/profiles/` passes, every rule in `.harness/rules/` has evidence, and the local CI gate matches the release gate profile.
