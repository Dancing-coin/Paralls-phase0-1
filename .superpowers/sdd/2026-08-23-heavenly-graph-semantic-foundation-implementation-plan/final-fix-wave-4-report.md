# Final Fix Wave 4 Report

Date: 2026-08-24
Scope: Heavenly Graph same-scope lifecycle-marker diff reads only. No runtime, LLM, or Godot changes.

## Fix

`_bounded_branch_markers` now identifies the left and right scope keys before
opening marker windows. When both keys are identical, it opens one bounded
window, reuses its saturation result, and merges that window once. The output
therefore contains no duplicate lifecycle markers while retaining the existing
window limit and truncation semantics. Distinct scope keys retain the original
two-window behavior.

## TDD evidence

Added a dual-adapter regression that compares the same branch on both sides,
wraps its four-marker stream in an indexing spy, and asserts both the total
four-entry inspection cap and four unique returned marker identifiers.

RED:

- `python -m pytest -q backend/tests/test_heavenly_graph_final_fix_wave4.py`
  -> `2 failed, 1 warning`; both adapters indexed the same stream a second time.

GREEN:

- Wave 4 regression: `2 passed, 1 warning`.
- Wave 1, Wave 2/3, and Wave 4 focused graph tests: `59 passed, 1 warning`.

## Verification

- Graph harness: `python scripts/verification/harness.py --profile heavenly-graph-semantic-foundation` -> exit `0`, overall `True`.
- Verifier and harness-registry tests: `29 passed`.
- Docs gate: `python scripts/verification/check_docs.py` -> overall `True`.
- Compile: `python -m compileall -q backend/app backend/tests scripts/verification` -> exit `0`.
- Diff check: `git diff --check` -> clean.

## Residual concerns

- The existing Starlette/httpx deprecation warning remains.
- Cross-namespace relation admission remains the explicitly documented v1 single-scope fail-closed contract from Wave 1.
