# Durable store schema write fence

An already-open durable store previously kept writing after another connection
changed its database schema marker. The durable store now verifies schema 3
inside the SQLite write transaction, after `BEGIN IMMEDIATE`, including group
commit. A missing or changed marker rejects before writes. The check covers
code containing this change; an older process does not run it and must still
be stopped or fenced separately during migration. This is not an authority
epoch, writer identity, or handoff implementation.

Focused command:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' -m pytest backend/tests/test_gameplay_event_store_connection.py backend/tests/test_gameplay_event_store_persistence.py backend/tests/test_gameplay_event_store_contract.py -q
```

50 passed, 2 warnings. The changed-schema append test was observed failing
before implementation; changed and missing markers and group commit now
reject without writing events or outbox entries.

Full G0-range command:

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g2-schema-fence-20261110 --freeze
```

Windows 11, Python 3.12.2. The [evidence archive](g2-schema-fence-evidence.zip)
contains environment, source hashes, manifests, invocation, JUnit, results
and failures. 10,003 nodes were collected: 9,960 passed, 39 failed, 2 skipped
and 2 xfailed. No collection errors occurred; source hashes were stable. All
G0 and previous full-run nodes retained their per-phase outcomes, all three
new nodes passed, and failure node/phase/exception signatures match both.
Python, OS, package and dependency hashes, and pytest environment match the
previous run.

Rollback: revert this unit's commit. It changes no database schema, event or
snapshot format; rolling it back removes the check for this code version.
Do not treat rollback as safe after enabling a future schema that depends on
this check without a separate migration and old-writer shutdown plan.
D2-D10 and B3 client acceptance remain open.
