# INF-2D Economy Wage Terminal Lifecycle Implementation Plan

Status: `implemented and verified for the named Economy row`

Date: `2026-08-14`

1. Add RED tests for retry, cancel, expiry, settled-only compensation,
   revision/terminal zero-write, idempotency, privacy and checkpoint-tail replay.
2. Add only Economy owner fragment builders and the authority-owned exact wage
   lifecycle registration. Do not change `SimulationClock`, coordinator writer ownership,
   account payment, or worker evidence admission.
3. Add a dedicated Harness profile with one test assertion per capability.
4. Synchronize August/root docs and record the remaining generic lifecycle and
   receipt gaps.
5. Run focused tests/profiles, `git diff --check`, and full pytest.

## Execution record

The RED tests confirmed that Economy lacked retry/cancel/expiry fragments. The
owner now supplies exact fragments; expiry records only a terminal unpaid
obligation state. The coordinator replay check precedes the revision gate for
an existing retry idempotency key. Final repository verification remains
required for this turn.

The closed registration now lives on `EconomyAuthority`, with an independent
Harness selector. This prevents callers from treating a test-local fixture as
an open policy-registration surface and does not authorize another row.
