# Final Fix Wave 3 Report

Date: 2026-08-24
Scope: Heavenly Graph marker scanning only. No runtime, LLM, or Godot changes.

## Fix

`_bounded_branch_markers` now inspects a deterministic bounded window from each branch stream before filtering or sorting. The window is `max(marker_limit + 1, 4)`, so ineligible or policy-mismatched marker history cannot force an unbounded scan. If either stream has more entries than its inspected window, the result reports `truncated=True` even when no inspected marker is eligible. Only the inspected windows are merged and ordered.

## TDD evidence

Extended the dual-adapter Wave 2 regression module with a policy-mismatched 20-marker stream and a spy that raises if more than the four-marker minimum window is inspected.

RED:

- Wave 3 spy run: `2 failed, 8 passed`; both adapters iterated beyond the allowed bound through ineligible marker history.

GREEN:

- Wave 2/Wave 3 regression module: `10 passed, 1 warning`.
- Combined graph gate: `295 passed, 1 warning`.

## Verification

- Verifier and harness-registry tests: `29 passed`.
- Focused graph harness: `python scripts/verification/harness.py --profile heavenly-graph-semantic-foundation` -> exit `0`, overall `True`.
- Docs gate: `python scripts/verification/check_docs.py` -> overall `True`.
- Compile: `python -m compileall -q backend/app backend/tests scripts/verification` -> exit `0`.
- Diff check: `git diff --check` -> clean.

## Residual concerns

- Existing Starlette/httpx deprecation warning remains.
- Cross-namespace relation admission remains the explicitly documented v1 single-scope fail-closed contract from Wave 1.
