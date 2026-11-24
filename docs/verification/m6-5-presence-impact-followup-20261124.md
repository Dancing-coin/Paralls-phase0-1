# M6-5 Presence assessment for every signed Gate impact

## Scope

- Branch: `thread-a/ownership-bond-followup-20261121`.
- Parent: `9b46742ee5a4c709e166ff247b5161101d4cd1f1`.
- Implementation commit: `e246f2c08734ebc358bf81f3bc5637d29f869280`.
- This A-owned change completes the signed Presence assessment step for each committed layered v2 Gate impact, including impacts that do not breach integrity. V1 breach-bound receipts remain readable.
- The assessment binds the signed impact event, gate incarnation, all three current Facility streams, current Place revision, and its own signed Presence input. The Place output read vector pins every source stream, including the immutable impact input stream.
- When Presence returns the existing Place state, it commits a private confirmation event. The derived obligation settles from the signed impact, Facility Owner transaction, signed Presence input, and Place transition or confirmation. Unknown input remains open and does not write a Place decision.
- Production Gate profiles remain unconfigured without authoritative values. Demo/test values are not production tuning. No `integration` change was made.

## Implementation and test changes

- Added the registered `gameplay.presence.assessment_input_received@2` schema and accepted `PresenceAssessmentReceiptV2` on the existing HTTP route.
- Reused the existing Presence Owner and physical-input principal. The separate signed receipt references a committed v2 impact and current Facility revision vector without requiring a breach event.
- Preserved the old v1 event and breach validation path.
- Extended the impact obligation projection to associate signed Presence inputs and both Place transition and same-state confirmation receipts with each impact.
- Extended checkpoint cut/tail coverage to include both signed Gate impact and Presence v2 input receipts after a Facility commit.
- Added a read-vector regression test. The first run failed with `KeyError` because the impact input stream was missing from the Place output read set. The implementation now pins that stream and the breach and non-breach cases pass.

## Environment

- Python: `3.12.2` using `D:\Temp\paralls-g0-py312\Scripts\python.exe`.
- SQLite: `3.43.1`.
- `PYTHONPATH`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`.
- `app.__file__`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- Test `TEMP`, `TMP`, and `TMPDIR` all pointed to the specific F-drive run directory. No verification output was stored on D:.

## Verification

- Focused command from the repository root:

  ```powershell
  & $py -m pytest -q -p no:cacheprovider backend/tests/test_facility_gate_layered_runtime.py backend/tests/test_m6_5_siege_runtime.py backend/tests/test_siege_physical_input_runtime.py backend/tests/test_facility_integrity_runtime.py backend/tests/test_rule_pack_validator.py backend/tests/test_world_replay_checkpoint_application.py
  ```

  Result: `169 passed, 6 warnings in 28.58s`. Raw output: `F:/paralls-verification/thread-a/m65-presence-focused-final-01/pytest.log`.
- New exact behaviors include non-breach and breach impacts (`20` and `270` are test-only demo magnitudes), current revision validation, stale and wrong-incarnation zero-write rejection, exact retry, unchanged-state private confirmation, durable restart/recovery, production EventSchema registration and checkpoint participant reconstruction.
- M6-5 selection on the final exact code commit: `selected=21 problems=0 improvements=0`. Raw output: `F:/paralls-verification/thread-a/m65-presence-selection-exact-e246f2c0-01/compare.log`.
- Frozen ownership: `24/0/0`, modifier: `12/0/0`, equipment: `87/0/0`, inventory: `56/0/0`. Raw outputs are under `F:/paralls-verification/thread-a/m65-presence-{ownership,modifier,equipment,inventory}-01/compare.log`.
- Information report selection: `25/0/0`; siege Information selection: `25/0/0`. Raw output: `F:/paralls-verification/thread-a/m65-presence-information-source-01/compare.log` and `F:/paralls-verification/thread-a/m65-presence-information-02/compare.log`.
- Frozen shared-replay on the final exact code commit: `selected=990 problems=0 improvements=0`. Raw output: `F:/paralls-verification/thread-a/m65-presence-shared-exact-e246f2c0-01/compare.log`.
- Full backend suite on exact commit: `10628 passed, 19 failed, 2 skipped, 2 xfailed, 227 warnings in 1401.22s`, exit 1. Raw output: `F:/paralls-verification/thread-a/m65-presence-backend-suite-e246f2c0-01/full.log`.
- The exact 19 failing backend node IDs were rerun at parent `9b46742ee5a4c709e166ff247b5161101d4cd1f1`: `19 failed in 29.02s`, with the same node set. Parent raw output and node list: `F:/paralls-verification/thread-a/m65-presence-parent-compare-9b46742e-01/parent.log` and `failed-nodeids.txt`. These full-suite failures are not newly introduced by this change.
- A repository-root `pytest` attempt stopped during collection because `scripts/verification/tests/test_motion_profile_contract.py` imports missing `jsonschema`. Running from `backend/` also failed collection because the repository root was no longer on the Python import path. The project backend suite was then run from the repository root with the explicit `backend/tests` target above.
- `git diff --cached --check` exited 0 before the implementation commit. The P-1 staged-added-lines scan reported zero credential-pattern matches: `F:/paralls-verification/thread-a/m65-presence-secret-scan-01/scan.json`.

## Not verified

- No live Unreal transport or configured production Gate profile was available. Production balance values remain unset.
- No full configured siege run was performed.
- This exact change was not merged to `integration` and does not establish completion of the broader M6-5 milestone or Architecture v2.

## Requirement status

- U1 partial, U2 not done, U3 partial, U4 partial, U5 partial, U6 partial, U7 not done, U8 partial, U9 exact-code focused and registered selections verified with 19 baseline full-suite failures, U10 evidence recorded, U11 M6-5 selection updated.
