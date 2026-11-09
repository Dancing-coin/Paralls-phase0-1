# G1 world-admin test barrier

The contract replay full run exposed a previously passing test failure: the
`identity_changed` queued-authorization case returned 200 rather than 403.
The original test signalled on any `RuntimeExecution.submit`. The running
Siming driver also submits to that queue on its polling loop. A controlled
diagnostic in the accompanying archive submits an unrelated command first,
changes the principal before the HTTP request starts, and reproduces a 200
with the replacement principal. The original failing run did not record the
identity of the submission that signalled its barrier.

The test now waits specifically for the cadence revocation command and
asserts that an unrelated submission does not signal the barrier. The 403,
unauthorized response, and unchanged-store assertions remain intact.

From `backend`, using `D:/Temp/paralls-g0-py312/Scripts/python.exe`,
`-m pytest tests/test_world_admin_cadence_revocation_application.py tests/test_world_admin_cadence_production.py -q -p no:cacheprovider`
passed 16 tests. The diagnostic command and source are in the archive; it
passed once. The full run after the fix included the uncommitted contract
replay migration: 9,976 collected, 9,933 passed, 39 failed, 2 skipped and 2
xfailed. All G0 nodes and failure signatures match the approved baseline;
the known WebSocket stack has a different runtime cancel-scope identifier.
The full environment and source manifests are in the archive.

Evidence: [g1-contract-replay-evidence.zip](g1-contract-replay-evidence.zip).
Rollback: revert the commit containing this record and the world-admin test
change. The original test race then remains present; runtime code is untouched.
