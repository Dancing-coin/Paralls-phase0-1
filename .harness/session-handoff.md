# Harness Session Handoff

## Latest Verified State

- Full harness command: `python scripts\verification\harness.py --profile all`
- Local CI equivalent: `.harness/ci/local-ci-gate.ps1`
- Evidence root: `.harness/verification/`
- Archive root: `.harness/verification/runs/<run-id>/`

## Current Harness Profiles

- `docs`
- `boundaries`
- `drift`
- `backend-contract`
- `godot-project`
- `release-gate`
- `harness-lifecycle`
- `phase0`
- `phase1-slice`

## Remaining Risks

- GitHub Actions has a workflow entry point, but external hosted CI execution must be verified in the target GitHub environment.
- Future product modules must add their own profile and rule manifests from `.harness/templates/`.
- Generated evidence retention is local policy; long-term storage or pruning automation can be added when release cadence is known.
