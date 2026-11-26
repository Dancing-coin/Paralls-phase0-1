# M2-2 Morale event-time producer

## Scope

This increment lets the Morale refold path pass a trusted optional `event_time`
from the casualty source event into the Pool adjustment event. Calls that do not
provide a time retain the legacy omitted field and remain replay-compatible.

## Implementation

| File | Change | Status |
|---|---|---|
| `backend/app/gameplay/pool_runtime.py` | Optional strict nonnegative `event_time` on Pool adjustment, included in the idempotency digest and committed event | verified |
| `backend/app/gameplay/morale_refold_runtime.py` | Pass `death.event_time` to the refold adjustment | verified |
| `backend/tests/test_morale_refold_runtime.py` | Regression for casualty time propagation | verified |
| `backend/tests/test_pool_runtime.py` | Regression for invalid boolean time rejection | verified |

## Verification

- Python: 3.12.2 (`D:\Temp\paralls-g0-py312\Scripts\python.exe`)
- Focused Pool + Morale: `22 passed, 2 warnings`
- M5-3/M6-5/Morale/Presence/Information + Pool: `147 passed, 6 warnings`
- Temporary pytest paths: `F:/paralls-verification/thread-a/m2-2-morale-time-20261127/`
- Full backend suite: not run for this increment.

## Boundaries

- No event-store or model changes.
- No change to legacy events without `event_time`.
- This adds one authoritative producer for Morale only. Public `read_as`,
  principal qualification, selector interpretation, and event-to-FactType
  visibility mapping remain unresolved M2-2 dependencies.
