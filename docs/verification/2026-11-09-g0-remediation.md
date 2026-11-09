# G0 remediation evidence

The code changes for this work are on `codex/g0-b3-ingress-20261109`.
The original baseline is commit `5321266d`. This record does not approve G0 or G1.

## Full backend run

At code commit `e351aa88`, Python 3.12.2 in an isolated environment ran
`python -m pytest backend/tests -q --tb=short` from the repository root.
The result was 9886 passed, 26 failed, 2 skipped and 2 xfailed; exit code 1.
The unedited output is [g0-python312-e351aa88.log](g0-python312-e351aa88.log).
This run predates the subsequent test fixture and synchronization commits.

The separate `phase0` harness run at `7fd5b509` failed with 74 backend test
failures and weak player locomotion evidence. It does not establish the status
of the later commit. Fifteen earlier profiles in that harness invocation passed.

## Boundaries and remaining work

- B1 receipt validation, B2 active-failure recall and B4 checkpoint identity
  have focused regression coverage on this branch.
- B3 has a bound-controller and authorized-spatial-sample server ingress. A
  bound controller can request its server-owned initial or last admitted
  position and connection epoch; a live WebSocket test covers that request,
  sample admission, object interaction and an idempotent retry. Godot does not
  yet send those samples. Deployment scope, client acknowledgments, renewal of
  the one-use controller enrollment on reconnect and a real Godot-to-server
  object interaction still need implementation and verification.
- Historical evaluation source pins differ from the current authored profiles.
  The pinned `char_a` content exists at commit `19551f49`; its SHA-256 matches
  the historical policy. Do not replace the pin with the current file's digest.
- The full-run failures include historical evaluation, diagnostic mind-frame
  behavior and a missing WebSocket scheduling trace. The economy replay fixture
  composition, two other fixtures, the stormnight action-window assertion and
  the queued administrator authorization test were subsequently fixed and
  verified in focused runs, not in a new full run.
- The historical player locomotion audit looked for a direct shell-to-motor
  call; the current route uses a bridge and character actor. Positive movement
  was logged. The audit now recognizes the current actor-owned motor path and
  its focused tests pass, but the strict harness has not yet been rerun.
- Python 3.12.2 is not the CI-pinned 3.12.14. The local environment lacks the
  optional `tokenizers` package required by one calibration test.

The original baseline and classification are maintained in the separate
Paralls-docs repository. No merge into main is implied by this record.
