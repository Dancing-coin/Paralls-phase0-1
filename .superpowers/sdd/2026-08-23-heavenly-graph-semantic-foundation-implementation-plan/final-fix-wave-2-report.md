# Final Fix Wave 2 Report

Date: 2026-08-24
Scope: Heavenly Graph foundation only. No runtime, LLM, or Godot changes.

## Fixes

- Removed the semantic endpoint-filter bypass that re-added `closes_branch_node` relations for authority readers. Closed marker relations now obey the same two-visible-endpoint rule as every other semantic relation.
- Historical `ConflictSetQuery` reads now honor branch availability, fork valid/recorded coordinates, close-node tombstones, discard markers, and existing reader visibility/policy filtering through the shared semantic result path.
- `diff_branches` lifecycle marker selection is bounded. The adapter scans append-ordered marker streams and stops at `marker_limit + 1` eligible markers, returning only `marker_limit` and setting `truncated` when the extra marker proves saturation. It does not materialize or sort the complete marker history.

## TDD evidence

Added `backend/tests/test_heavenly_graph_final_fix_wave2.py` with InMemory/SQLite regressions for all three findings.

RED:

- First run: `6 failed`; four reproduced the endpoint/lifecycle defects and two exposed an invalid private-scope fixture. After correcting the fixture shape and adding the marker spy, the RED run reproduced close-marker endpoint leakage, pre-fork conflict history visibility, and unbounded marker iteration against both adapters.

GREEN:

- Final-fix Wave 2 suite: `8 passed, 1 warning`.
- Combined Wave 1/Wave 2 graph gate: `293 passed, 1 warning`.

## Verification

- Verifier and harness-registry tests: `29 passed`.
- Focused graph harness: `python scripts/verification/harness.py --profile heavenly-graph-semantic-foundation` -> exit `0`, overall `True`.
- Docs gate: `python scripts/verification/check_docs.py` -> overall `True`.
- Compile: `python -m compileall -q backend/app backend/tests scripts/verification` -> exit `0`.
- Diff check: `git diff --check` -> clean.

The existing branch lifecycle compatibility assertion was updated to reflect the Wave 2 fail-closed endpoint contract: a close marker relation is not exposed when its target node is hidden by the lifecycle tombstone.

## Residual concerns

- The existing Starlette/httpx deprecation warning remains.
- Cross-namespace relation admission remains the explicitly documented v1 single-scope fail-closed contract from Wave 1.
