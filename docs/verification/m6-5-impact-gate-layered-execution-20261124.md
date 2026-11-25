# M6-5 layered impact_gate implementation evidence

## Scope and state

- Worktree: F:/codex-temp/paralls-v2-thread-a-bond-20261121, branch thread-a/ownership-bond-followup-20261121, parent 7601189a4b9580a6acd93c3164d9db5ba3af4b76. Implementation commit: a9f5385a7f05e7f52611062b236f5392a5e3e611.
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
- Exact detached worktree at commit a9f5385a repeated the focused command with 164 passed, 6 warnings. Exact commit M6-5 (16), ownership (24), modifier (12), equipment (87), inventory (56) and Information (25) selections all reported zero problems and improvements. Raw outputs are under F:/paralls-verification/thread-a/m65g-exact-a9f5385a-01/ and the m65g-exact-{m65,own,mod,equip,inv,info}-a9f5385a/ directories.
- git diff --check exited 0. It emitted only Git's CRLF-to-LF notice for the existing coordination comms file.
- Final-code shared-replay selection: selected=990 problems=2 improvements=0. Failures were test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage] and [wall-clock], both failing with Port 8000 occupied by an external process without a healthy backend. The same nodes failed with the same error on parent 7601189a. Raw final and parent outputs are under F:/paralls-verification/thread-a/m65g-shared-replay-final-01/ and m6-5-impact-gate-parent-shared-20261124-02/.
- Full backend suite on this current working-tree state: not run.

## Remaining gaps

- The `gate-03` profile values were selected and exercised in the local runtime probe. They are now included in the tracked root `.env.example` for deployment configuration. This repository has no production deployment manifest or server target, so no live environment is claimed as configured.
- No live Unreal transport or fully configured siege playthrough was run.
- The Presence contract requires a committed breach event as an assessment source. Hits that do not cross the integrity breach threshold remain open in the derived obligation projection, since the current source contract cannot issue a Presence assessment against a non-breach impact.
- Exact commit full backend suite: 10,630 passed, 12 failed, 2 skipped, 2 xfailed, 227 warnings, exit 1 in 1465.42s. All 12 failed node IDs were rerun at the exact parent 7601189a in a detached worktree and all 12 failed there as well; the node sets match, with no new failure node. Parent selected-run evidence identifies a missing tokenizers module, Godot CharacterMotor parse/type resolution, and existing Population/Task8 gate failures. Full implementation output: F:/paralls-verification/thread-a/m65g-full-a9f5385a-01/full.log. Parent comparison: F:/paralls-verification/thread-a/m65g-full-a9f5385a-01/parent-comparison.json and F:/paralls-verification/thread-a/m65g-full-parent-7601189a-01/baseline/results.json.
- P-1 scan of every staged added line relative to origin/integration found 0 credential-pattern hits. Scan output: F:/paralls-verification/thread-a/m65g-secret-scan-02/scan.json.
- M6-5 is in progress. This evidence does not establish full Architecture v2 completion or merge readiness.

## Requirement status

- U1 partial, U2 not done, U3 partial, U4 partial, U5 partial, U6 partial, U7 partial, U8 partial, U9 partial, U10 evidence recorded, U11 selection registered.

## 2026-11-25 local configured Gate profile follow-up

- The A worktree root `.env` now supplies `SIEGE_FACILITY_GATE_PROFILES_JSON` for `gate-03`. The selected profile uses 0–100 bounds and initial 100 for door durability, latch durability and integrity; integrity breach enter/reset thresholds are 40/45; `impact_kind:battering-ram@1` applies `-20`. The file is ignored by Git and remains local to this A worktree. No application default or tracked deployment configuration was changed.
- The exact runtime smoke used Python 3.12.2, SQLite 3.43.1 and `app.__file__` under the A worktree. Fourteen independently signed, monotonically revised impact inputs exhausted door and latch durability, reduced integrity to 20, and produced one breach-enter event. The Facility runtime wrote no Place fact, preserving Presence's separate assessment authority. Raw output is `F:/paralls-verification/thread-a/m6-5-gate-profile-runtime-20261125-01/runtime.log`; the probe is `F:/paralls-verification/thread-a/verify-configured-gate-20261125.py`.
- Focused tests on this configuration: `184 passed, 6 warnings` across Facility Gate layered runtime, M6-5 siege runtime, signed physical input, Facility integrity, RulePack validation and checkpoint replay. Raw output is `F:/paralls-verification/thread-a/m6-5-gate-profile-focused-20261125-01/pytest.log`.
- Exact M6-5 Gate selection: `selected=21 problems=0 improvements=0`. Raw output is under `F:/paralls-verification/thread-a/m6-5-gate-profile-selection-20261125-01/`.
- This config and evidence cover the local A runtime only. No production server deployment, real UE transport, full configured siege session, shared-replay selection or full backend suite was run in this follow-up. M6-5 remains in progress.


- 2026-11-25 Gate-to-Presence follow-up: the configured 14-impact probe was extended to submit an independently signed Presence assessment against the breach impact. Runtime output: `python=3.12.2`, `app=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`, `sqlite=3.43.1`, `impact_commits=14 breach_events=1 values={durability:0,latch-durability:0,integrity:20}`, `place_commits=1 passability=passable`, and `latest_impact_obligation=settled`. The integrity Pool remains at 20 after Presence assessment, confirming the accepted compensation contract preserves committed physical damage. Raw output: `F:/paralls-verification/thread-a/m6-5-gate-presence-obligation-20261125-01/runtime.log`. Probe source remains outside the repository at `F:/paralls-verification/thread-a/verify-configured-gate-20261125.py`. This is a local runtime probe, not a live UE or production deployment run.

## 2026-11-26 tracked configuration follow-up

- The root `.env.example` now carries the same `gate-03` values as the previously exercised local profile: integrity and durability bounds 0–100, initial values 100, breach enter/reset thresholds 40/45, and battering-ram delta -20.
- The environment variable is consumed by application startup through `Settings.siege_facility_gate_profiles`. This update makes the profile available as tracked deployment input; the actual production environment remains unverified because no deployment target or manifest is present in this repository.
- The JSON profile was validated against `FacilityGateProfileSettings`. Python `3.12.2`, SQLite `3.43.1`, and `PYTHONPATH=F:/codex-temp/paralls-v2-thread-a-bond-20261121/backend` were verified; `app.__file__` resolved to `F:/codex-temp/paralls-v2-thread-a-bond-20261121/backend/app/__init__.py`.
- Command: `python -B -m pytest -q -p no:cacheprovider --basetemp F:/paralls-verification/thread-a/m6-5-gate-profile-template-20261126-02/pytest-tmp backend/tests/test_m6_5_siege_runtime.py backend/tests/test_facility_gate_layered_runtime.py backend/tests/test_config_runtime_modes.py`. Result: `52 passed, 6 warnings in 2.79s`. Raw output: `F:/paralls-verification/thread-a/m6-5-gate-profile-template-20261126-02/pytest.log`.
- No runtime code changed, and the prior signed-input runtime evidence remains applicable to the same values. Live production deployment, UE transport, and a full configured siege session remain unverified.
