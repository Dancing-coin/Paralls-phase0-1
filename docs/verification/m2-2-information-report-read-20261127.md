# M2-2 Information Recipient-Private Read Increment

## Scope

- Implementation commit: `8faeab2331187b3e13f3c2583fb8c3f6087dd090`, based on A `bf52c7a44a5723d1aaede97b5207e38aa0c97455`.
- This increment adds an Information-only report read for one actor/report pair and exposes it through the WebSocket envelope handler.
- It does not implement the generic `read_as(principal, scope, as_of_tick, fact_types)` contract and does not satisfy U7.
- No persistent event type, payload, snapshot, or storage-core contract changed.

## Read Contract

- The WebSocket handler requires the current backend-issued session binding and a requested actor already present in its immutable `allowed_actor_refs`.
- The handler obtains current world time from `_session_world_clock_tick`; a missing clock or future `as_of_tick` fails closed. The request cannot supply a principal or visibility qualification.
- `InformationAuthority.read_report_for_recipient` reads the deterministic report and SocialDelivery streams, verifies the exact event types, recipient visibility, time window, source revision, committed transaction principals, and current revocation/expiry state.
- Reports with unknown `event_time`, deliveries with malformed/unknown time fields, missing delivery, expiry, revocation, or malformed report content return unavailable.
- The returned projection contains the Information FactType, report identity, summary, Owner, source revision, `event_time`, recipient `known_time`, and tick freshness.
- Revocations currently use an event-type-filtered history read because the existing revocation contract has no recipient/source index. This is a bounded selector over a registered event type, but runtime cost grows with the number of matching revocation events.

## Verification

Environment: Python `3.12.2`, SQLite `3.43.1`, `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`. `PYTHONPATH`, `TEMP`, `TMP`, `TMPDIR`, pytest basetemp, logs and measurement output were on F:.

| Check | Result |
|---|---|
| Information runtime, checkpoint-tail, production wiring, WebSocket context tests | `41 passed, 6 warnings` |
| New registered selection | `selected=5 problems=0 improvements=0` |
| Frozen ownership selection | `24/0/0` |
| Frozen modifier selection | `12/0/0` |
| Frozen equipment selection | `87/0/0` |
| Frozen inventory selection | `56/0/0` |
| Frozen shared-replay selection | `990/0/0` |
| Full backend suite | Not run for this increment |

Raw outputs for the exact-commit focused run and new selection are in `F:\paralls-verification\thread-a\m2-2-information-read-20261127-13\`. The real WebSocket-to-Information-authority test was also rerun independently in `F:\paralls-verification\thread-a\m2-2-information-read-20261127-12\`. Frozen selections are in `F:\paralls-verification\thread-a\m2-2-information-read-20261127-08\`.

The P-1 staged code scan checked assignment-shaped secrets, AWS/GitHub tokens, JWTs, and private-key headers. It reported `patterns-scanned=5 credential-pattern-hits=0`; raw output is `F:\paralls-verification\thread-a\m2-2-information-read-20261127-11\p1-code-scan.log`.

## D6 Durable Read Diagnostic

The existing `measure_durable_read.py` diagnostic was run in two independent processes, each with 60 alternating samples after five warmups. It measures a real durable `read_events()` plus a synthetic fixture scan. It does not exercise this Information authorization path, projection construction, revocation distribution, network delivery, cold storage, or production workload. It cannot pass or fail a production SLO.

| Event count | Run 1 raw p95 | Run 1 read + scan p95 | Run 1 max ratio | Run 2 raw p95 | Run 2 read + scan p95 | Run 2 max ratio |
|---:|---:|---:|---:|---:|---:|---:|
| 256 | 1.18–1.19 ms | 1.23–1.25 ms | 1.05 | 1.09–1.68 ms | 1.11–1.85 ms | 1.28 |
| 1,024 | 7.52–7.62 ms | 7.85–7.96 ms | 1.05 | 6.91–14.29 ms | 6.98–15.00 ms | 1.10 |
| 4,096 | 42.81–43.38 ms | 43.95–44.62 ms | 1.05 | 56.91–65.23 ms | 60.62–69.69 ms | 1.07 |

The project records provisional diagnostic budgets of 40 ms absolute and 1.10 relative p95. Both runs exceed the absolute figure at 4,096 events, and run 2 exceeds the relative figure for one 256-event and one 1,024-event row. Historical exceedances remain. D6 is not passed. The synthetic fixture and SQLite 3.43.1 also do not establish real workload or the concurrent-WAL environment requirement.

The first run's fixture was initially created under `D:\codex-temp\user-temp\paralls-g2-durable-visibility-jal2epym`. The three databases (about 4.0 MiB total) were moved to `F:\paralls-verification\thread-a\m2-2-d6-durable-visibility-20261127-01\fixture\`; the D source directory is absent. The first result's fixture path was updated to its current F-drive location. Run 2's fixture is under `F:\paralls-verification\thread-a\m2-2-d6-durable-visibility-20261127-02\tmp\`.

## Remaining M2-2 Gaps

- Generic principal qualification and selector execution for faction, role, group, owner, and holder selectors.
- Runtime consumption of the compiled event-schema-to-FactType candidates and FactType visibility policy.
- `read_as` across registered FactTypes, with generic known-time and distortion semantics.
- Classification and migration of principal-facing readers. Existing Ownership/Credential reads are currently trusted-owner, recovery, debug, or replay paths based on the recorded static audit.
- Production D6 workload, tail latency, cache behavior, and bounded revocation lookup.

M2-2 remains blocked and U7 remains incomplete. No full backend run or production visibility-budget pass is claimed.
