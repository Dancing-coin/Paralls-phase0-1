# M6-5 layered impact_gate implementation evidence

## Scope and state

- Worktree: F:/codex-temp/paralls-v2-thread-a-bond-20261121, branch thread-a/ownership-bond-followup-20261121, parent 7601189a4b9580a6acd93c3164d9db5ba3af4b76.
- The layered Gate runtime, v2 signed input, optional Facility Pool content, Gateway, pack declarations and rebuildable obligation projection are A-owned. No B code was required. Previously selected B Information commits remain in A's history.
- Formal compensation behavior is now set to continue Presence evaluation and keep committed physical damage. No physical rollback is performed. A compensation step would apply only to a future reversible reservation.
- Python 3.12.2, SQLite 3.43.1. Commands set PYTHONPATH to this worktree's backend and TEMP, TMP, TMPDIR to fresh F-drive run roots. The import and temp paths were printed before pytest.

## Implementation findings and corrections

- The layered initializer now validates and reuses an already initialized Facility stream. This permits enabling the layered profile over archives that already contain the integrity Pool while initializing missing door and latch durability streams.
- The latch Machine now transitions only when the latch-durability Pool changes in the same Facility commit. A door-leaf-only hit no longer emits a latch transition without a matching durability receipt.
- Checkpoint manifest capture/validation already contained the signed physical input participant at the parent. The implementation keeps that participant and adds v2 event recognition plus exclusion from the combat participant. It does not duplicate the participant manifest field.
- A rebuildable impact_gate projection identifies signed impact inputs, Facility Owner transaction events, Presence assessment inputs and Place output events. It writes no workflow ledger. An obligation remains open until a committed Place decision exists.

## Verification run on the working tree

- Environment check asserted Python 3.12.2 and that app.__file__ resolves within the current A worktree backend. It also recorded SQLite and tempfile.gettempdir().
- Focused command:

  powershell
  & $py -m pytest -q -p no:cacheprovider backend/tests/test_facility_gate_layered_runtime.py backend/tests/test_m6_5_siege_runtime.py backend/tests/test_siege_physical_input_runtime.py backend/tests/test_facility_integrity_runtime.py backend/tests/test_rule_pack_validator.py backend/tests/test_world_replay_checkpoint_application.py

- Result: 164 passed, 6 warnings in 31.10s. Raw output: F:/paralls-verification/thread-a/m65g-obl-projection-01/pytest.log.
- Frozen selections: ownership selected=24 problems=0 improvements=0, modifier selected=12 problems=0 improvements=0, equipment selected=87 problems=0 improvements=0, inventory selected=56 problems=0 improvements=0. Raw outputs are under F:/paralls-verification/thread-a/m65g-narrow-ownership-02/, m65g-modifier-20261124-01/, m65g-equipment-20261124-01/, and m65g-inventory-20261124-01/.
- M6-5 layered selection: selected=16 problems=0 improvements=0. Raw output: F:/paralls-verification/thread-a/m65g-layered-selection-final-02/selection/batch-0000.log.
- Information selection: selected=25 problems=0 improvements=0. Raw output: F:/paralls-verification/thread-a/m65g-information-final-01/selection/batch-0000.log.
- git diff --check exited 0. It emitted only Git's CRLF-to-LF notice for the existing coordination comms file.
- Final-code shared-replay selection: selected=990 problems=2 improvements=0. Failures were test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage] and [wall-clock], both failing with Port 8000 occupied by an external process without a healthy backend. The same nodes failed with the same error on parent 7601189a. Raw final and parent outputs are under F:/paralls-verification/thread-a/m65g-shared-replay-final-01/ and m6-5-impact-gate-parent-shared-20261124-02/.
- Full backend suite on this current working-tree state: not run.

## Remaining gaps

- Production Gate profiles are intentionally unconfigured without authoritative values. The checked-in pack values are demo content only.
- No live Unreal transport or fully configured siege playthrough was run.
- The Presence contract requires a committed breach event as an assessment source. Hits that do not cross the integrity breach threshold remain open in the derived obligation projection, since the current source contract cannot issue a Presence assessment against a non-breach impact.
- Exact detached-commit and full-suite evidence remain pending.
- M6-5 is in progress. This evidence does not establish full Architecture v2 completion or merge readiness.

## Requirement status

- U1 partial, U2 not done, U3 partial, U4 partial, U5 partial, U6 partial, U7 partial, U8 partial, U9 partial, U10 evidence recorded, U11 selection registered.
