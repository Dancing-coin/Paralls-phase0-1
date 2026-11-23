# M6-5 production Morale and Presence wiring

## Unit and environment

- Implementation commit `4506d9071f7f5779bdd46100419417aa8a30d4e8`.
- Detached worktree `F:\codex-temp\a-m6-5-siege-verify-4506d907` at the implementation commit.
- Python `3.12.2` from `D:\Temp\paralls-g0-py312\Scripts\python.exe`.
- SQLite `3.43.1`.
- `PYTHONPATH` pointed to the detached worktree's `backend`; `app.__file__` resolved to `F:\codex-temp\a-m6-5-siege-verify-4506d907\backend\app\__init__.py`.
- `TEMP`, `TMP`, pytest basetemp, and all new raw output were directed to `F:\paralls-verification\thread-a\m6-5-production-wiring-detached-4506d907-03\`.

## Implemented behavior

The production `main.py` transaction callback now dispatches committed death and Facility breach transactions through the M6-5 L5 reaction pack. The Morale handler reads the Organization roster and LifeState history at the casualty sequence and writes only the Morale Pool. On the first valid casualty it initializes that same Pool from its configured baseline before refolding. Repeating the committed reaction replays the prior receipt.

The Presence handler calls the Presence-owned passability writer. The production builder currently supplies no trusted Presence resolver or evidence principal registry. Under the confirmed policy, a breach without those inputs returns `place_assessment_unknown` and writes no Place event. The breach does not determine passability.

The existing durable Combat settlement is not a gate-impact source. It validates a single character target and character presence, LifeState, and faction sources. No committed gate impact producer carrying both gate identity and impact quantity was found. A trusted Presence decision event source is also absent. Those source contracts remain open.

## Verification

| Check | Result | Evidence level |
|---|---|---|
| Python and import identity | Python `3.12.2`; `app.__file__` inside the detached F-drive worktree | Verified |
| Targeted command | `python -m pytest -q -p no:cacheprovider --basetemp <F-drive output> backend/tests/test_m6_5_siege_runtime.py backend/tests/test_morale_refold_runtime.py backend/tests/test_facility_integrity_runtime.py backend/tests/test_place_passability_runtime.py backend/tests/test_l5_dispatch_runtime.py backend/tests/test_l5_reaction.py backend/tests/test_gameplay_store_main_lifecycle.py backend/tests/test_main_cold_start.py backend/tests/test_gameplay_outbox_pending_query.py backend/tests/test_gameplay_outbox_refresh.py` | `80 passed, 6 warnings` |
| Permanent unit selection | `selected=4 problems=0 improvements=0` | Verified; `docs/verification/selection/m6-5-production-wiring.json` |
| Frozen ownership selection | `selected=24 problems=0 improvements=0` | Verified |
| Frozen shared-replay selection | `selected=990 problems=2 improvements=0` | Not clean; two external Port 8000 failures below |
| Full suite on this implementation commit | Not run | Unverified |

The two shared-replay failures were `test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage]` and `[wall-clock]`. Both reported `RuntimeError: Port 8000 is occupied by an external process without a healthy backend`. The same failure category is recorded at the parent revision in earlier M6-5 evidence. The process was not stopped or modified.

Raw outputs are in `F:\paralls-verification\thread-a\m6-5-production-wiring-detached-4506d907-02\` and `F:\paralls-verification\thread-a\m6-5-production-wiring-detached-4506d907-03\`. The `-02` directory contains the ownership and shared-replay comparison. The `-03` directory contains the permanent unit selection comparison and the targeted pytest log.

## U1-U11 status

| DoD | Status |
|---|---|
| U1 Owner declaration and classification | Partial. Production dispatch names the Morale and Presence domains, but their complete v2 Owner declarations are not established here. |
| U2 FactType declarations | Not done. Complete Morale and Place FactType schemas and scopes remain unregistered. |
| U3 Event schema and P-3 | Partial. Existing Pool and Place event schemas are used, and related registration tests pass. This unit adds no new persisted event type. |
| U4 Shared mechanisms | Partial. The dispatch uses the committed-event gateway and existing Owner writers. Domain declarations and the full M6-5 contract are incomplete. |
| U5 R1, R2, and R3 | Partial. Component tests cover exact retries, historical revision pins, unknown-input zero-write behavior, and replay. The integrated production flow has not been proven through full checkpoint-free rebuild. |
| U6 Reader inventory and tests | Partial. The new dispatch and writer paths are covered by the unit selection and focused tests. The event reader inventories remain in the component evidence files. |
| U7 Read classification and visibility | Not done. Complete `read_as` and v2 visibility declarations are absent. |
| U8 Rule-pack settings and Resolver registration | Partial. The M6-5 command and reaction pack loads in production. No trusted Presence resolver is registered. |
| U9 Probe and frozen baseline | Partial. The 24-node ownership selection is clean. Shared-replay has two recorded environment failures. The full suite was not run on this commit. |
| U10 Changed files and verification levels | Verified. Implementation files are `backend/app/gameplay/m6_5_siege_runtime.py`, `backend/app/gameplay/morale_refold_runtime.py`, `backend/app/main.py`, `backend/tests/test_m6_5_siege_runtime.py`, `backend/tests/test_morale_refold_runtime.py`, `docs/v2-coordination/comms/2026-11-24-thread-a.md`, `packs/county_siege_morale_presence/pack.yaml`, `packs/county_siege_morale_presence/command_catalog/commands.yaml`, `packs/county_siege_morale_presence/play_patterns/play_pattern.yaml`, and `packs/county_siege_morale_presence/reactions/reactions.yaml`. Evidence files are this record and `docs/verification/selection/m6-5-production-wiring.json`. |
| U11 Permanent unit selection | Verified. The new four-node selection reports zero problems and zero improvements. |

This unit connects the committed-event dispatch to the existing Owner writers. It does not complete M6-5 or establish an end-to-end Presence decision because the trusted input source is still missing.
