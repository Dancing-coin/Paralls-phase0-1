# Temporal migration binding recovery

The existing Population temporal-profile migration can commit its owner and
migration receipts, activate the new clock, then fail while updating Status
bindings. Previously an exact retry returned the committed receipt because the
clock already had the new profile, leaving `migration_pending` set and blocking
further advancement. The retry now completes the binding update before clearing
the pending state. An already updated binding is accepted only when its full
binding fields match the current driver pins and world; inconsistent bindings
still reject. No historical events, digest or receipt format changes.

The regression was observed failing before the fix. The application-level
tests inject failures both before and after the binding update, verify that an
inconsistent binding rejects with the pending state retained, retry the same
request, assert one Status migration event and advance to the pending expiry.
The existing clock-activation failure and durable restart tests remain covered.

On Windows 11, Python 3.12.2, the focused command reported 70 passed:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' -m pytest backend/tests/test_temporal_profile_migration.py backend/tests/test_status_application_lifecycle.py backend/tests/test_status_temporal_consumer.py backend/tests/test_population_durable_cadence_recovery.py backend/tests/test_world_runtime_population_cadence.py -q
```

The G0-range run used the following command and collected 10,012 nodes:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g2-migration-binding-20261110 --freeze
```

Result: 9,969 passed, 39 failed, 2 skipped, 2 xfailed, no collection errors.
All 10,010 prior nodes retained their setup/call/teardown outcomes; both new
nodes passed. The 39 failure node/phase/error-type signatures match the prior
run. One stack hash differs only in an AnyIO cancel-scope identifier; after
normalizing that identifier all 39 stacks match. Python, OS, package and
dependency hashes and pytest environment match the preceding run; source and
HEAD were unchanged during execution. The [archive](g2-temporal-binding-recovery-evidence.zip)
contains the frozen test manifest, environment, invocation, node list, JUnit,
results and failure details.

Rollback: revert this unit's commit with the runtime stopped. It changes no
persisted format; reverting restores the possibility that an exact retry reports
success while the in-memory driver remains blocked after a binding failure.
Recovery then requires a verified restart or other operational repair. This
unit does not provide per-stream authority epoch fencing, a trusted handoff,
general visibility enforcement or complete three-time semantics. D2-D10 and
the G2 visibility performance gate remain open; B3 client integration remains
unaccepted.
