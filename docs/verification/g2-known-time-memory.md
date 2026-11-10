# G2 character memory known-time correction

Status: one existing character-memory path corrected; this is not completion
of G2 visibility, three-time semantics or authority fencing.

Subsequent call-chain inspection found that real player activation may pass a
Godot millisecond `producer_ts` to the comparison, while Population candidate
knowledge time can use seconds-based window ticks. The tests below use matching
synthetic values and do not establish that those production time domains match.
Delayed memory may become visible early; a trusted mapping and production-path
regression are still required.

On 2026-11-10 an in-memory exercise called the actual activation entry with
`producer_ts=100000` and a pending candidate whose `knowledge_available_at`
was 101. Activation acquired the lock and the event-memory count became one.
No confirmed Population time was supplied to that entry. This reproduces the
unconditional comparison; it does not establish the world time of a real
Godot session or repair any memory already projected.

The seed planner assigns `world_ref` from the cadence, but the production
continuity command does not carry that field. Its persisted candidate and
continuity event therefore do not establish the candidate's world. The
activation lock's default `world:default` is not a substitute: the production
bakery Population driver uses `world:bakery-district`. A safe correction needs
durable world provenance for new candidates, a separately supplied confirmed
time for that same world, and an explicit policy for legacy candidates whose
provenance cannot be established. It must preserve existing command digests,
replay semantics and the event timestamp/cursor meaning. Unknown provenance
cannot authorize early materialization. Previously projected memories and
receipts require separate investigation; this evidence does not undo them.

An early materialization attempt previously persisted a permanent
`temporal_knowledge_denied` receipt. The same candidate then replayed that
refusal after its knowledge time, including after restart. New early attempts
remain rejected for that call without consuming the final receipt. Existing
persisted temporal refusals remain intact; a later eligible materialization
uses a separate event-backed receipt, including after projection failure.
Permanent exposure-basis rejection retains its previous replay behavior.

Focused command (repository root):

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' -m pytest backend/tests/test_character_agent_seed_continuity.py backend/tests/test_character_session_recovery.py backend/tests/test_character_continuity_four_cursors.py backend/tests/test_population_seed_known_time.py backend/tests/test_character_agent_seed_projection_parse.py -q
```

Result: 105 passed, 6 deprecation warnings. Three added tests cover an early
attempt followed by restart and delivery, legacy refusal preservation and
restart, and projection failure after a deferred commit. A separate in-memory
graph checkpoint restore exercise verified replay and one memory after the
legacy path; it was not a Godot or production deployment test.
The graph checkpoint exercise is now also a regression test:
`python -m pytest backend/tests/test_character_agent_seed_continuity.py::test_legacy_deferred_memory_survives_graph_checkpoint_restore backend/tests/test_character_agent_seed_continuity.py::test_legacy_temporal_refusal_preserved_and_memory_delivered_once -q`
with the same Python 3.12 interpreter reported 2 passed and 2 deprecation
warnings. The full baseline below predates this additional test; runtime code
has not changed since that run.

Full G0-range command:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g2-known-time-20261110 --freeze
```

Windows 11, Python 3.12.2; full environment, source hashes, test manifest,
invocation, JUnit, results and failures are in
[g2-known-time-memory-evidence.zip](g2-known-time-memory-evidence.zip).
The run collected 9,985 nodes: 9,942 passed, 39 failed, 2 skipped, 2 xfailed;
no collection errors and source hashes remained stable. Every G0 and G1 node
retained its prior outcome; all three added nodes passed. Failure node, phase
and exception-type signatures equal both the approved G0 and G1 sets.

Rollback: revert the commit containing this record and code/tests only when
no `materialization_after_defer` event has been written. For an archive that
already contains such an event, old code does not recognize the new receipt
kind: restore a matching pre-change archive or implement and verify a forward
compatibility migration before rolling back. Do not rewrite historical hashes
or discard later facts. The general G2 gates, D2-D10, and B3 limitations
remain open.
