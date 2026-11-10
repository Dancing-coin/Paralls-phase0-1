# Character memory world-time boundary

Production character runtime now obtains the known-time comparison from the
confirmed Population driver for the candidate's world. The Population seed
world is persisted with the character continuity event; it is checked
separately on retries so the existing command digest and legacy receipts are
not rewritten. The client `producer_ts` still supplies the event timestamp
and memory cursor. A missing, invalid, migrating or different-world clock
does not authorize materialization. Existing exposure refusals retain their
precedence. The driver time is sampled conservatively: during publication it
may still be the preceding confirmed tick.

Legacy candidates without persisted world provenance stay deferred in the
production assembly. A legacy command replay does not retroactively attach
provenance. Previously materialized memories remain in history and are not
automatically removed or reclassified. Runtimes constructed without a
`memory_known_time_provider` retain their legacy behavior, so this is not a
universal principal-facing visibility boundary or a complete three-time
implementation. The trusted Population-to-character in-process path supplies
the world; this field is not independent authentication of arbitrary callers.
Finding provenance currently scans the character event history when candidates
exist; long-history performance has not been measured against a production
budget. D2-D10 and the B3 client acceptance limitations remain open.

## Candidate Time Update Limitation

The existing same-world candidate update also allows a new continuity command
to change `knowledge_available_at`. On Windows 11 / Python 3.12.2, the
following isolated in-memory exercise committed a candidate with event time 99
and knowledge time 101, deferred it at world tick 100, then committed another
command for the same candidate and world with knowledge time 100. The next
materialization committed and exposed the memory at tick 100. It uses the real
continuity and materialization methods and the test fixture, not the production
cadence or an authenticated external ingress.

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g2-visibility-budget/probe_candidate_time_update.py
```

The seed planner derives the candidate ID from actor and projection ID and
permits source payloads to specify times. Existing domain behavior permits
same-world updates; the inspected contract establishes event time <= knowledge
time but does not establish which authority can correct a previously recorded
knowledge time or how correction evidence is verified. Thus the earlier
world-binding fix does not prevent an earlier-time update from authorizing
materialization. A G2 implementation needs a source-bound correction contract,
including historical conflicting updates, exact retries, restart and already
materialized memories. Rejecting all earlier corrections without that contract
would decide domain behavior not established here. No runtime code changed;
revert this diagnostic commit to remove the probe and note.

## Cadence provenance audit

The seed planner copies `world_ref` from the cadence into the continuity
command. The production clock provider separately checks that this world
matches the active Population driver and that migration is not pending before
returning its current tick. This prevents a mismatched world label from using
that driver's clock, but the label itself does not authenticate the cadence.

The regular `RuntimeCadencePublisher` validates source revisions, commits a
`population.cadence.admitted` record and delivers through the outbox. There is
also a game-start path in `main.py` that calls the authorized publication
function directly: it checks a committed source event, revision vector and
projection scope, but does not commit a cadence admission through that outbox.
The in-process authority bus and Siming consumer accept a cadence by event
type; they are not an independent proof of origin. The inspected HTTP and
WebSocket adapter publishing sites construct other event types, but this static
inspection does not establish that every possible in-process caller is trusted
or that future ingress cannot publish an equivalent event.

Consequently the earlier world-time change protects its documented production
clock comparison, not cadence authenticity, canonical-writer fencing or general
principal visibility. A future enforcement change must account for both the
startup publication and outbox retry/recovery paths before treating this
provenance as an authority boundary. No runtime behavior changed in this audit.

Focused verification (Windows 11, Python 3.12.2):

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' -m pytest backend/tests/test_character_activation_known_world_time.py backend/tests/test_character_population_integrated_loop.py backend/tests/test_character_agent_seed_continuity.py backend/tests/test_character_session_recovery.py backend/tests/test_character_continuity_four_cursors.py backend/tests/test_population_seed_known_time.py backend/tests/test_character_activation_lease.py backend/tests/test_siming_population_capability.py backend/tests/test_siming_population_production_boundaries.py -q
```

216 passed, 8 warnings. The activation regression was observed failing before
implementation. Tests cover different clock domains, delayed delivery,
missing and different worlds, restart, retry with changed world, serialized
retry, exposure denial, driver migration, and seed-to-character propagation.

Full G0-range command:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g2-memory-world-time-v3-20261110 --freeze
```

The [evidence archive](g2-memory-world-time-evidence.zip) contains the
environment, frozen manifest, invocation, node list, JUnit, results and
failures. 10,010 nodes: 9,967 passed, 39 failed, 2 skipped, 2 xfailed; no
collection errors. All 9,937 approved G0 nodes and all 10,003 nodes from the
previous G2 run retained their individual phase outcomes; seven new nodes
passed. Failure node, phase and exception-type signatures match both runs.
One prior failure's stack hash differed only in an AnyIO cancel-scope ID;
after normalizing that ID all 39 stacks matched the preceding run. Python,
OS, package and dependency hashes and pytest environment match; source and
HEAD remained stable during the run.

Rollback: revert this unit only with the runtime stopped and a verified
archive/recovery plan. Older code ignores the added event metadata and does
not enforce this world-time comparison, so rollback restores the known early
exposure risk and must not be treated as preserving the protection. Check
compatibility of serialized commands containing `world_ref` and retained
events before restoring an older runtime; do not discard later facts or
rewrite historical hashes. The existing `materialization_after_defer` archive
restriction in [the previous unit](g2-known-time-memory.md) also applies.
