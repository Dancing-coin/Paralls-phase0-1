# G2 visibility budget measurement

Status: historical paired runs include budget exceedances. The recorded economy domain-view samples at `0b587890` are numerically below the candidate thresholds, not a performance acceptance result. The session/WebSocket `read_as` path is not implemented and has not been performance-tested; no positive session reads may be enabled using these samples.

## Review correction: implementation versions and budget status (2026-11-11)

The 71.46–79.44 ms economy samples were archived at `e3fb3fda`. The later
23–24.49 ms samples used the same benchmark script and economy view source,
but a different event-store implementation: `f60a487c` added scalar event
copying in place of deep copying on eligible reads, and `59084f36` simplified
its guard loops. The fixture contains 4,095 unrelated scalar-payload events
and one economy event, so this difference affects almost the entire scan.
Comparing these numbers without the code versions overstated comparability.

To isolate the copy change, `g2-session-visibility-denial/compare_copy_paths.py`
measured the same 4,096-event store and domain view in one process, alternating
the current read-copy helper with `event.model_copy(deep=True)` for each
principal. Each independent run used five warmups and 60 pairs; event digests,
allowed results, redaction and denied results were equal across the paths.
Only the helper is temporarily replaced inside the isolated diagnostic
process; no production code or historical events are changed.

| Run | Deep-copy median range | Current-copy median range | Deep-copy p95 range | Current-copy p95 range |
|---:|---:|---:|---:|---:|
| 1 | 32.75–33.37 ms | 12.37–12.57 ms | 43.73–43.99 ms | 23.32–23.39 ms |
| 2 | 32.72–33.08 ms | 12.53–12.57 ms | 43.43–44.71 ms | 23.89–24.48 ms |

Median deep/current ratios were 2.61–2.66. This supports a substantial copy
cost contribution; it does not explain the full historical latency gap. In
particular, this deep-copy rerun did not reproduce the historical 71–79 ms
p95. It is a helper substitution on current code, not an exact historical
checkout rerun. Shared-process allocation/GC and uncontrolled system load
remain limitations. The old component experiment's unexplained tails also
remain unresolved. Raw samples, source hashes and fixture hash are retained
in `g2-session-visibility-denial/copy-path-comparison-run1.json` and `-run2.json`.

Keep 40 ms / 10% as an unchanged candidate target, not a current release
gate pass. A release decision needs fixed code/dependency/fixture identities,
GC and load conditions, repeated measurements with rejection and allowed
principals, and coverage of the actual storage and authenticated session
path. These diagnostics do not provide that evidence. Do not replace the
target with a looser number to accommodate historical samples, and do not
enable positive session reads on the strength of the 24.49 ms result.

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-session-visibility-denial/compare_copy_paths.py --output docs/verification/g2-session-visibility-denial/copy-path-comparison-run1.json
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-session-visibility-denial/compare_copy_paths.py --output docs/verification/g2-session-visibility-denial/copy-path-comparison-run2.json
```

## Current-HEAD Principal View Rerun (2026-11-11)

At code HEAD `0b587890ba732686b3d1d565a73848e83640701a`, the same
principal-aware economy domain-view script was rerun in two independent
processes. Each run used 5 warmups and 60 alternating samples for
`actor:owner`, `authority:economy`, and the denied `actor:other` at 256, 1,024,
and 4,096 events. At 4,096 events, owner view p95 was 23.64/24.48 ms,
authority view 23.06/23.78 ms, and denied view 23.21/23.04 ms across the two
runs. Across all rows, maximum p95 ratio was 1.028 and maximum 4,096-event
view p95 was 24.49 ms. This existing in-memory domain view is within the
provisional 10% relative and 40 ms absolute thresholds in these runs.

Raw samples and a per-principal comparison are archived in
`docs/verification/g2-session-visibility-denial/principal-view-run1.json`,
`principal-view-run2.json`, and `performance-comparison.json`. Commands were:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_economy_principals.py --repeats 60 --warmups 5 --output D:/Temp/g2-session-visibility-denial-baseline-20261110-r1/principal-view-run1.json
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_economy_principals.py --repeats 60 --warmups 5 --output D:/Temp/g2-session-visibility-denial-baseline-20261110-r1/principal-view-run2.json
```

The measurement uses an in-memory economy fixture and a caller-supplied
principal string. It does not exercise a bound WebSocket identity, the session
Owner's missing disclosure facts, the approved historical authorization rules,
transport, durable-store contention or the positive session projection path.
Thus it updates the measured cost of this existing domain view but does not
close the session visibility budget gate or justify serving session events.

## Existing Economy Principal View

`measure_economy_principals.py` measures the existing
`EconomyPrivacyQueryService.account_redacted_payload` for the account owner,
the configured economy authority, and a denied unrelated actor. It compares
each call with `EconomyProjector.rebuild(store.read_events())` and account
lookup, alternating order for 60 samples after five warmups. The harness checks
the returned balance and owner-field redaction, and verifies the denied error.
The fixture contains one real economy account event and 255, 1,023 or 4,095
synthetic unrelated events, held in the in-memory store. Two independent
processes ran on Windows 11 / Python 3.12.2; individual samples and environment
are retained in `economy-principals-results.json` and its `-repeat` companion.

| Events | Run | Baseline p95 range | View p95 range | Maximum p95 ratio |
|---:|---:|---:|---:|---:|
| 256 | 1 | 1.95-2.45 ms | 1.94-2.07 ms | 1.00 |
| 256 | 2 | 1.94-3.27 ms | 1.96-2.95 ms | 1.01 |
| 1,024 | 1 | 10.25-12.07 ms | 9.39-12.09 ms | 1.00 |
| 1,024 | 2 | 7.98-13.27 ms | 7.98-19.13 ms | 1.44 |
| 4,096 | 1 | 66.47-76.80 ms | 71.79-79.44 ms | 1.14 |
| 4,096 | 2 | 69.17-76.65 ms | 71.46-76.15 ms | 1.03 |

These are real domain authorization and redaction calls, but the caller supplies
the principal string and the query is not a production-authenticated `read_as`
route. The fixture, hot in-memory store and one account are not representative
production traffic. The view includes full domain reconstruction, unlike the
earlier metadata scan; their absolute times and budgets are not interchangeable.
Ratios of independently computed p95 values are sensitive to scheduling and do
not establish marginal cost. Neither measurement satisfies the G2 performance
gate, and historical exceedances remain in force. No runtime behavior changed.

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_economy_principals.py --output D:/Temp/g2-economy-principals-20261110.json
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_economy_principals.py --output D:/Temp/g2-economy-principals-20261110-repeat.json
```

### Economy View Component Diagnostic

`diagnose_economy_components.py` separately times a full in-memory event
read, rebuilding the economy projection from an already copied list, and the
owner's complete redacted view. It uses the same 4,096-event fixture, 120
samples after 10 warmups, rotating and reversing call order. Two independent
processes produced the following measurements in milliseconds:

| Run | Read median / p95 | Projection median / p95 | View median / p95 |
|---:|---:|---:|---:|
| 1 | 51.48 / 130.11 | 2.49 / 8.81 | 54.09 / 139.65 |
| 2 | 65.66 / 144.07 | 3.66 / 9.20 | 71.93 / 158.25 |

The full samples and environment are in `economy-components-a.json` and
`economy-components-b.json`. The large variation and tails are not explained
by this experiment; the retained event list also affects memory and GC, and
the components are not additive measurements of a single request. The data
points to investigating copying before projection on this fixture, not to a
production latency conclusion. Filtering to account event types is not a
semantics-preserving shortcut: `EconomyProjector` validates cross-domain source
events and other economy invariants and tracks the economy stream revision.
The durable type index also requires separate consideration of corrupt or
inconsistent index data. No validation or runtime behavior was changed.

The general `GameplayProjectionReplay.continue_replay` checks each stream's
revision but does not prove that a global interval is complete. The isolated
`probe_replay_continuity.py` demonstrates a successful continuation from
sequence 1 to 3 with sequence 2 on a different stream omitted: the cursor is
3 in both results, but applied IDs and hashes differ. The world checkpoint
wrapper in `world_runtime/replay_checkpoint.py` separately validates the
complete interval before invoking replay. Other callers intentionally pass
scoped or type-filtered event sets, so adding unconditional global-contiguity
checks to the generic replay would change those contracts. An economy cache
needs an explicit complete global cut, atomic state publication, retained
cross-domain provenance and equivalence/failure tests; a successful generic
replay alone is insufficient evidence. This probe does not establish a live
production incident or implement the cache.

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/probe_replay_continuity.py
```

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/diagnose_economy_components.py --output D:/Temp/g2-economy-components-a.json
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/diagnose_economy_components.py --output D:/Temp/g2-economy-components-b.json
```

Command, from the repository root:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_visibility_baseline.py --output D:/Temp/paralls-g2-visibility-baseline/results.json
```

Environment: Windows 11 `10.0.26200`, Python 3.12.2, 30 samples after 5
warmups per row. The fixture contains 256, 1,024 and 4,096 events across four
streams and four provisional principals. The script measures the current
`read_events()` deep-copy cost and a separate metadata scan; it does not change
the runtime or claim that the provisional scan is the G2 contract.

The first grouped rerun's largest observed p95 values were:

| Events | Raw read p95 | Provisional principal scan p95 | Max ratio |
|---:|---:|---:|---:|
| 256 | 1.90 ms | 1.90 ms | 1.001x |
| 1,024 | 10.17 ms | 8.42 ms | 0.828x |
| 4,096 | 36.41 ms | 37.87 ms | 1.040x |

The 4,096-event public-observer row produced the maximum ratio in that
grouped run. Because raw and filtered calls were sampled in separate groups,
the result was repeated with alternating paired calls. The paired rerun is
stored in `paired-results.json` and was run with 60 samples after 5 warmups.
Its largest rows were:

| Events | Principal | Raw p95 | Paired filtered p95 | p95 ratio |
|---:|---|---:|---:|---:|
| 256 | `principal:town-authority` | 2.11 ms | 2.08 ms | 0.99x |
| 1,024 | `principal:debug-probe` | 11.23 ms | 12.40 ms | 1.104x |
| 4,096 | `principal:debug-probe` | 45.68 ms | 46.70 ms | 1.022x |

The paired 4,096-event row exceeds the provisional 40 ms absolute budget, and
the 1,024-event debug row exceeds the 10% relative budget. The provisional
budget is therefore not met in that run. The 4,096-event raw read itself was
45.68 ms p95 in that row, so its absolute threshold exceedance cannot be
attributed solely to the provisional filter. A second paired run, preserved as
`paired-results-rerun.json`, met both provisional limits for all fixture rows;
its highest 4,096-event filtered p95 was 37.79 ms and its highest p95 ratio was
1.03x. The difference between runs makes the tail estimate unstable; a passing
rerun does not erase the exceedance. Expansion of G2 visibility coverage is
paused while the variance is investigated; no runtime visibility code has
been installed. These are local synthetic measurements, not production SLOs.
The final contract still needs real visibility classes, delay/time semantics
and unauthorized-read behavior.

Paired measurement command:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_paired.py --output docs/verification/g2-visibility-budget/paired-results.json
```

## Tail diagnostic

Two further 4,096-event debug-principal runs recorded 120 alternating pairs
after 10 warmups; raw samples are retained in `tail-diagnostic.json` and
`tail-diagnostic-no-gc.json`. With normal garbage collection, raw/filtered
wall p95 were 37.01/36.83 ms. Every measured call triggered collections.
With cyclic GC disabled for the diagnostic process, raw/filtered p95 were
30.61/31.22 ms. The normal-GC recording predates the `gc_enabled` output
field; GC was enabled for that invocation.

This comparison indicates a substantial GC contribution in these runs, but
the runs were sequential and have no controlled system-load record. It does
not establish the cause of the earlier 46.70 ms result. Process CPU samples
are quantized in approximately 15.625 ms increments in this environment and
cannot reliably separate scheduling from execution for individual reads.
Disabling GC is solely an experiment, not a production recommendation. The
earlier exceedance and the pause on expanding visibility coverage remain.

An additional same-process run alternated GC enabled and disabled over 160
pairs, with raw-first order balanced within each group. Normal-GC raw and
filtered p95 were 32.12 and 32.31 ms; disabled-GC p95 were 31.01 and 31.37
ms. Each pair was preceded by an explicit full collection, changing the normal
GC workload, so these numbers are not comparable to the ordinary-read budget
as a pass/fail test. They show an effect under the controlled setup, not the
cause of the earlier exceedance. See `tail-diagnostic-interleaved-gc.json`.

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/diagnose_tail.py --output docs/verification/g2-visibility-budget/tail-diagnostic.json
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/diagnose_tail.py --disable-gc --output docs/verification/g2-visibility-budget/tail-diagnostic-no-gc.json
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/diagnose_tail.py --compare-gc --repeats 160 --output docs/verification/g2-visibility-budget/tail-diagnostic-interleaved-gc.json
```

The output is `results.json` in this directory. The source script records the
fixture, principals, policies, environment and median/p95/p99 aggregates.
The grouped run sampled raw and filtered reads separately. The paired runs
alternate order but remain sensitive to scheduling noise; repeat against the
real implementation and production-shaped workload before making a production
budget decision.

## Component diagnostic

`diagnose_components.py` records 200 alternating 4,096-event raw/filtered
pairs, individual GC callbacks, thread CPU time and a separate scan of an
already copied event list. On the same Windows/Python environment, raw wall
p95 was 39.20 ms, filtered p95 was 39.30 ms, and the scan alone was 0.42 ms.
Among filtered calls, 33 with a generation-2 collection had a 38.98 ms median
and 40.24 ms p95; 167 without one had a 32.54 ms median and 33.16 ms p95.
The filtered call's aggregate GC callback durations had a 7.72 ms p95.
These observations support a GC contribution in this run; they do not prove
the cause of the earlier 46.70 ms result. Thread CPU measurements still
occurred in 15.625 ms increments and cannot resolve individual scheduling
delays. Raw samples are in `component-diagnostic.json`.

This is diagnostic evidence, not another budget pass: it registers GC
callbacks and retains an extra copied event list, both of which may affect the
workload. The fixture also correlates policy, stream and owner by the same
index; the scan counts visible events rather than building a production
projection. Its timing cannot establish performance or correctness of the
actual principal-aware contract. The earlier exceedance and the gate on
expanding visibility remain in force.

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/diagnose_components.py --output docs/verification/g2-visibility-budget/component-diagnostic.json
```

## Owner Process GC Configuration

`backend/app/services/runtime_process.py` sets the generation-zero GC
threshold to 21,000 in the spawned runtime owner process. Earlier measurements
used the interpreter default. A further synthetic paired run explicitly used
`(21000, 10, 10)` and retained 60 samples per row after five warmups; its
aggregates are in `paired-owner-gc.json`.

At 4,096 events, filtered p95 ranged from 30.04 to 30.49 ms and the largest
p95 ratio was 1.024. However, the 256-event private-owner row measured raw
p95 2.165 ms and filtered p95 3.002 ms, a 1.387 ratio. The complete run
therefore did not meet the 10% candidate for every row. Since GC and system
load were not controlled between this and prior processes, these values do not
isolate the effect of the threshold. They do not erase previous failures or
demonstrate a production principal-facing path. The runtime owner setting is
not necessarily used by every caller or deployment.

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_paired.py --gc-threshold0 21000 --output docs/verification/g2-visibility-budget/paired-owner-gc.json
```

## Existing Mirror Access Measurement

The existing Godot mirror is a real principal-facing path with a live
backend-issued session binding and actor scope. It uses an already filtered
state-group view, not the proposed event-level `read_as` contract. The
following diagnostic uses the actual session authentication, mirror access,
subscription registry, serializer and state-group projector with synthetic
cached state. Each of two independent processes recorded 1,000 samples after
50 warmups per operation and rotated operation order. Individual samples,
environment and source hashes are in `mirror-access-results.json` and
`mirror-access-results-repeat.json`.

| Synthetic groups | Run | Raw cached snapshot p95 | Bound principal p95 | Ratio |
|---:|---:|---:|---:|---:|
| 1 | 1 | 0.0281 ms | 0.0299 ms | 1.064 |
| 1 | 2 | 0.0341 ms | 0.0381 ms | 1.117 |
| 8 | 1 | 0.1209 ms | 0.1209 ms | 1.000 |
| 8 | 2 | 0.1109 ms | 0.1145 ms | 1.032 |
| 32 | 1 | 0.4390 ms | 0.4352 ms | 0.991 |
| 32 | 2 | 0.4444 ms | 0.4459 ms | 1.003 |

The fixture verifies the allowed snapshot and field allowlist, and checks that
out-of-scope and expired bindings reject before producing a snapshot. Those
rejection timings are in the raw data and are not comparable to a successful
full snapshot. Separate `authority_view` and `godot_field_filter` timings
measure real projector calls with different output field sets; they are not a
controlled measurement of incremental filtering alone. Group counts and values
are synthetic; the cached source excludes event-store reads, refresh, socket
transport and client rendering. This is not an end-to-end Godot run or a
production workload/SLO. Ratios of separately sampled p95 values are noisy;
the 1-group second run exceeds 10%, and neither run erases the previous
4,096-event exceedance. D6 and the existing event visibility gate remain open.

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_mirror_access.py --output docs/verification/g2-visibility-budget/mirror-access-results.json
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_mirror_access.py --output docs/verification/g2-visibility-budget/mirror-access-results-repeat.json
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' -m pytest backend/tests/test_gameplay_mirror_session_access_service.py backend/tests/test_godot_gameplay_mirror_delivery.py backend/tests/test_state_group_views.py -q
```

The existing targeted tests reported 35 passed, 2 warnings. No runtime code
was changed by this diagnostic. Roll back this measurement independently by
reverting its commit; it changes no event or snapshot format.

## Filter Order Experiment

`measure_filter_before_copy.py` compares raw in-memory reads with two fixture
operations: copying all events before filtering, and filtering under the
store lock before deep-copying each selected event. The fixture uses the
existing store builder, adds nested mutable payloads, and varies the private
owner independently of policy and stream. The script checks equal results and
that mutating a returned nested payload does not affect a subsequent read.
Each of four independent runs uses 60 samples after six warmups, rotating the
three operation orders. Full individual samples and script SHA-256 are in
`filter-order-results*.json` and `filter-order-all-results*.json`.

| Fixture | Events / selected | Run | Raw p95 | Copy then filter p95 | Filter then copy p95 |
|---|---:|---:|---:|---:|---:|
| Mixed | 4,096 / 1,366 | 1 | 49.15 ms | 50.74 ms | 15.39 ms |
| Mixed | 4,096 / 1,366 | 2 | 53.31 ms | 56.52 ms | 20.49 ms |
| All selected | 4,096 / 4,096 | 1 | 48.93 ms | 49.07 ms | 49.03 ms |
| All selected | 4,096 / 4,096 | 2 | 51.18 ms | 51.30 ms | 50.27 ms |

At 1,024 all-selected events, filter-then-copy p95 was 14.16 and 14.11 ms,
against raw 11.03 and 10.93 ms respectively. Both exceed a 1.10 p95 ratio;
the all-selected 4,096 rows also exceed 40 ms. The fixture has more nested
data than the earlier baseline, so these are not directly comparable runs.
The all-selected predicate is a constant-true shortcut, not real authority
resolution. The experiment accesses private store fields and only exercises
the in-memory store; durable SQLite reads use a different implementation.
It models neither refusal semantics nor trusted identity, time, distortion,
pagination, concurrency or projection construction. It suggests a possible
optimization for selective reads, but is not a production implementation or
evidence that the visibility budget passes. D6 and the existing gate remain
open. Reverting the experiment commit removes the diagnostic only.

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_filter_before_copy.py --output docs/verification/g2-visibility-budget/filter-order-results.json
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_filter_before_copy.py --output docs/verification/g2-visibility-budget/filter-order-results-repeat.json
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_filter_before_copy.py --all-visible --output docs/verification/g2-visibility-budget/filter-order-all-results.json
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_filter_before_copy.py --all-visible --output docs/verification/g2-visibility-budget/filter-order-all-results-repeat.json
```

## Durable Store Read Diagnostic

`measure_durable_read.py` uses the real `DurableGameplayEventStore` to append
the existing synthetic fixture, close and reopen an isolated SQLite database,
and compare the stored events with the in-memory source. It measures the real
`read_events` method and that same read followed by the provisional fixture
scan for four principals. Each of two independent processes records 60 pairs
per row after five warmups, with alternating operation order. All samples,
fixture directory paths, environment and source hash are retained in
`durable-read-results.json` and `durable-read-results-repeat.json`.

| Events | Run | Raw p95 range | Read plus scan p95 range | Maximum p95 ratio |
|---:|---:|---:|---:|---:|
| 256 | 1 | 0.90–0.93 ms | 0.93–0.99 ms | 1.07 |
| 256 | 2 | 0.91–0.95 ms | 0.95–0.99 ms | 1.08 |
| 1,024 | 1 | 7.37–7.61 ms | 7.53–7.84 ms | 1.04 |
| 1,024 | 2 | 7.44–7.69 ms | 7.65–8.24 ms | 1.07 |
| 4,096 | 1 | 41.34–42.41 ms | 42.29–43.50 ms | 1.03 |
| 4,096 | 2 | 42.31–42.98 ms | 43.35–43.98 ms | 1.03 |

Both 4,096 rows exceed the candidate 40 ms absolute budget even before the
scan. The fixture has small payloads and correlated policy, stream and owner;
the scan counts results rather than creating projections or enforcing the
specified refusal, identity, timing and distortion rules. Repeated reads use a
hot SQLite/OS cache, and the harness retains a reference list and a raw result
while sampling, potentially affecting GC. This is not a production SLO, an
end-to-end workload, or evidence that the relative gate for real `read_as`
passes. The existing gate remains open.

SQLite schema 3 stores newly appended full events in `full_value` using the
store's encoded representation; the `value` column contains only event type.
Older rows may retain complete JSON in `value`. Thus the existing event-type
index cannot directly filter visibility metadata across both formats. A future
index or migration must preserve history, handle both formats and enforce
authorization without trusting stale or caller-supplied index entries. The
diagnostic itself changes no runtime or archive format; revert its commit to
remove it independently. Isolated fixture databases are left at the paths in
the result files.

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_durable_read.py --output docs/verification/g2-visibility-budget/durable-read-results.json
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_durable_read.py --output docs/verification/g2-visibility-budget/durable-read-results-repeat.json
```

## Cache Admission Diagnostic

The durable store's decoded-text cache is bounded to 512 entries and 2 MiB.
The 4,096-event sequential fixture can churn that cache. To examine this cost,
`measure_cache_admission.py` opens two independent store instances over each
previously created isolated 4,096-event fixture. On one instance only, the
experiment disables cache insertion by replacing its `_remember_json_text`
method; the other retains normal behavior. Both still query SQLite, decode,
validate and create fresh models. The script compares full initial results,
then alternates the instances for 60 read-plus-fixture-scan samples per
principal, after five warmups. Individual samples and source hashes are in
`cache-admission-results.json` and `cache-admission-results-repeat.json`.

| Run | Normal p95 range | No-insertion p95 range |
|---:|---:|---:|
| 1 | 35.76–36.82 ms | 31.18–31.70 ms |
| 2 | 37.31–38.13 ms | 32.61–32.90 ms |

These are synthetic hot-cache samples with the same simplified count-only
policy as the preceding diagnostic. They do not measure subsequent point-read
cache hits, mixed workloads, cold I/O, multiple writers or full authorization.
The experiment changes an instance method and is not a proposed production
implementation; it cannot establish that bypassing admission preserves hooks,
concurrency or cache behavior. It does not erase previous budget exceedances or
demonstrate the real `read_as` contract. No runtime or archive format changed.
The fixture database paths are recorded in the results; the databases remain
on disk. Revert this diagnostic's commit to remove it independently.

```powershell
$fixture = (Get-Content docs/verification/g2-visibility-budget/durable-read-results.json -Raw | ConvertFrom-Json).fixture_directory
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_cache_admission.py --database (Join-Path $fixture 'events-4096.db') --output docs/verification/g2-visibility-budget/cache-admission-results.json
$fixture = (Get-Content docs/verification/g2-visibility-budget/durable-read-results-repeat.json -Raw | ConvertFrom-Json).fixture_directory
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_cache_admission.py --database (Join-Path $fixture 'events-4096.db') --output docs/verification/g2-visibility-budget/cache-admission-results-repeat.json
```

## Decoder Comparison

`measure_decoder_comparison.py` reads the two existing 4,096-event SQLite
fixtures in read-only mode and compares the standard-library decoder with the
already-installed `zlib-ng` decoder. Each run alternates decoder order for
100 samples after 10 warmups and checks every decoded body against the
standard-library output. The two independent fixture databases have the same
compressed-body hash. Median times were 6.69/6.19 ms and 6.80/6.28 ms
(standard/native). The fixture's truncated and checksum-damaged sample was
rejected by both; both accepted the sampled trailing byte. These three cases
are not a proof of full decoder equivalence.

This measures decompression only, without SQLite query time, UTF-8 decoding,
model validation, cache, authorization, time filtering or projections. The
roughly 0.5 ms median difference cannot establish the 40 ms or 10% gates, and
does not justify changing the existing decoder without broader compatibility
and end-to-end evidence. Historical exceedances remain valid; D6 stays open.
The scripts and individual samples can be removed by reverting this diagnostic
commit; no runtime or archive format changed.

```powershell
$fixture = (Get-Content docs/verification/g2-visibility-budget/durable-read-results.json -Raw | ConvertFrom-Json).fixture_directory
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_decoder_comparison.py --database (Join-Path $fixture 'events-4096.db') --output docs/verification/g2-visibility-budget/decoder-comparison.json
$fixture = (Get-Content docs/verification/g2-visibility-budget/durable-read-results-repeat.json -Raw | ConvertFrom-Json).fixture_directory
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/measure_decoder_comparison.py --database (Join-Path $fixture 'events-4096.db') --output docs/verification/g2-visibility-budget/decoder-comparison-repeat.json
```
