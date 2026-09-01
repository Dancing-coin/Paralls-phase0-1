# Task 5 Fix Round 1 Report

## Status

Complete.

## Fixes

- Verifier now explicitly requires `char_b` pending memory count to remain zero.
- Verifier now explicitly requires no Character Core command for `character:char_c`.
- Verifier now requires W1 to have a distinct cadence/window and source revision vector.
- Verifier now checks monotonic `char_a` and `char_b` Character Core revisions across W0/W1.
- Top-level fixture `zero_write` now includes the stale-read-set case, with a focused assertion.

## Verification

- Direct verifier: passed.
- Task 5 focused pytest: 4 passed.
- `git diff --check`: passed.

## Concerns

None.
