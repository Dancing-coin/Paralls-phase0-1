# Harness Clean State Checklist

Run this checklist before ending a harness-hardening session or before claiming the full project harness is ready.

## Verification

- [ ] `python -m pytest -q scripts\verification\tests` passes.
- [ ] `python -m compileall -q scripts\verification` passes.
- [ ] `python scripts\verification\harness.py --profile all` passes.

## Evidence

- [ ] `.harness/verification/harness-run-report.json` exists.
- [ ] `.harness/verification/harness-run-manifest.json` exists.
- [ ] `.harness/verification/harness-run-diff.json` exists.
- [ ] `.harness/verification/baseline.json` exists.
- [ ] The latest run has an archive under `.harness/verification/runs/<run-id>/`.

## Source Inputs

- [ ] `.harness/profiles/*.json` are not ignored by git.
- [ ] `.harness/rules/*.json` are not ignored by git.
- [ ] `.harness/templates/` is present for future profiles.
- [ ] `.harness/ci/local-ci-gate.ps1` matches the release gate profile.

## Handoff

- [ ] `.harness/session-handoff.md` lists the latest run id and remaining risks.
- [ ] `.harness/features.json` reflects current profile status and evidence.
- [ ] `.harness/quality-document.md` and `.harness/evaluator-rubric.md` match the current harness structure.
