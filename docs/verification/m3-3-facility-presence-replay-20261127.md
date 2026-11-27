# M3-3 Facility and Presence replay validation

## Change

Implementation commit: `32373b52fff0f7c2105e6eb3eda05fdafe875b00`.

Facility layered impact, legacy Presence assessment, and signed-impact Presence assessment now validate an existing durable receipt through `replay_duplicate`. Facility validates the full multi-stream transaction and event list. Presence validates both the passability-change event and the unchanged-state confirmation event, including their stream and source-event relationship. A malformed receipt returns a rejected result before any append. No event names, payload semantics, or physical damage behavior changed.

## TDD

- The first failing run covered Facility's multi-event receipt and both signed-impact Presence outcomes. All three tests failed against the old direct-return paths. Facility returned a committed replay for a truncated receipt. Presence raised `IndexError` for an empty committed-event list.
- A legacy Presence corruption test was added after the shared-helper implementation and passed in the final test run. Its expected outcome is a rejected receipt with no change to the store snapshot.
- Red output: `F:/paralls-verification/thread-a/m3-3-facility-presence-red-20261127-01/red.log`.

## Verification

Environment: Python 3.12.2 from `D:\Temp\paralls-g0-py312\Scripts\python.exe`, SQLite 3.43.1, `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`, and `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.

| Check | Result |
|---|---|
| Facility, Presence, physical-input, and M6-5 siege runtime focused files | `76 passed, 6 warnings` |
| New registered selection | `selected=4 problems=0 improvements=0` |
| Frozen Ownership / Modifier / Equipment / Inventory / shared-replay | `24/0/0`, `12/0/0`, `87/0/0`, `56/0/0`, `990/0/0`; total `1,169` selected nodes with zero differences |
| Full backend suite | Not run |

Focused raw output: `F:/paralls-verification/thread-a/m3-3-facility-presence-integration-20261127-01/`. Selection output: `F:/paralls-verification/thread-a/m3-3-facility-presence-selections-20261127-01/`.

## Limits

This closes these Facility and Presence retry paths only. M3-3 remains in progress because repository-wide direct/custom replay paths remain to inventory and validate. The full backend suite was not run. Production Gate values remain unconfigured because no authoritative production profile or deployment input is present; `.env.example` remains demonstration configuration. No production deployment, UE transport, or complete siege run was verified.
