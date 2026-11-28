# M1-3 Morale Pool Rule-Pack Increment

## Scope

Code commit `f76089a4` adds the approved narrow siege morale refold to immutable package version `county_siege_morale_presence@1.0.2`. The rule is the percentage of historically rostered garrison members whose LifeState is alive at the casualty sequence. Missing roster or member LifeState remains unknown and produces no morale write. The package pins two decimal places with half-up rounding. The prior `1.0.0` and `1.0.1` package directories remain available, and their runtime fallback retains the previous Decimal division precision.

The package declares the Morale Pool FactType, bounds and initial value, distribution aggregation with `casualty` trigger, and `morale_refold@1`. M6-5 startup derives the Pool definition from the selected package and evaluates that registered Resolver. `rule_pack_validator` accepts `casualty` as a distribution refold trigger.

## Baseline And Environment

- Branch: `thread-a/ownership-bond-followup-20261121`.
- Parent code commit: `2b840c6a`. Increment commit: `f76089a4`.
- Python: `3.12.2`, executable `F:\codex-temp\thread-a-python312\Scripts\python.exe`.
- SQLite: `3.43.1`.
- `PYTHONPATH`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`.
- Import check: `app.__file__ = F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- Package content hash: `county_siege_morale_presence@1.0.2 sha256:4e294533b2f45f43980a502c1d0350bca821f9541046f1620c1c7108b553674c`.

## Verified

Focused command:

```powershell
& 'F:\codex-temp\thread-a-python312\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider --basetemp 'F:\paralls-verification\thread-a\m1-3-morale-package-final-20261128-02\pytest-temp' backend/tests/test_m6_5_siege_runtime.py backend/tests/test_morale_refold_runtime.py backend/tests/test_pool_runtime.py backend/tests/test_rule_pack_validator.py
```

Result: `200 passed, 6 warnings in 8.38s`. The warnings are existing Starlette/httpx and FastAPI `on_event` deprecations. Raw output: `F:\paralls-verification\thread-a\m1-3-morale-package-final-20261128-02\pytest.log`.

Registered selections, compared with frozen baseline `absorb-main-3bf3418e`:

| Selection | Selected | Problems | Improvements |
|---|---:|---:|---:|
| `m1-3-pool` | 26 | 0 | 0 |
| `m1-3-pool-domain-owner` | 1 | 0 | 0 |
| `m3-3-morale-refold-replay` | 1 | 0 | 0 |
| `m5-1-aggregation-models` | 6 | 0 | 0 |
| `m5-1-pool-definitions` | 9 | 0 | 0 |
| `m5-5-facttype-refold` | 38 | 0 | 0 |
| `m6-5-organization-roster` | 3 | 0 | 0 |
| `m6-5-production-wiring` | 6 | 0 | 0 |

Frozen selections: ownership `24/0/0`, modifier `12/0/0`, equipment `87/0/0`, inventory `56/0/0`, shared-replay `990/0/0` (`selected/problems/improvements`). All 13 comparisons were serial and returned zero problems and improvements. The updated M1-3 U11 selection contains 26 nodes. Its exact-tip comparison returned `selected=26 problems=0 improvements=0`; raw output is under `F:\paralls-verification\thread-a\m1-3-morale-selection-20261128-01\`. The other selection outputs are under `F:\paralls-verification\thread-a\m1-3-morale-package-final-selections-20261128-02\`.

The pytest and selection runs used F-drive temporary/output directories. No verification artifacts were added to the repository.

## Unit DoD Status

| Item | Status | Evidence or gap |
|---|---|---|
| U1 Owner declaration and classification | Partial | `Morale` is registered and assigned a domain handler. The complete formal Owner declaration/classification is not established by this increment. |
| U2 FactType declaration | Verified for this FactType | The v1.0.2 package declares and loads the Morale Pool FactType with entity identity. |
| U3 event schema and P-3 | Partial | `gameplay.pool@1` resolves and Pool graph visibility tests pass; a complete P-3 assertion for this migration was not run. |
| U4 shared mechanism | Verified for the tested path | Pool and Morale commits use `OwnerCommitBuilder` and `replay_duplicate`; focused tests cover the Morale caller. |
| U5 R1/R2/R3 | Partial | Morale exact-retry and corrupt receipt rejection are tested. Checkpoint deletion/state-digest reconstruction was not tested for this increment. |
| U6 reader inventory and tests | Partial, partly static | M6-5 command dispatch and Morale projection call paths are present. A complete downstream reader inventory and subject-facing tests remain open. |
| U7 subject read and visibility | Partial | The package declares faction visibility. `GameplayReadAs` does not provide a Morale reader. |
| U8 package settings and Resolver | Verified | The selected locked package supplies the Pool definition and registered Resolver. |
| U9 migration probe | Not verified | No declaration-only probe was run for this increment. |
| U10 evidence and changed paths | Verified | This file lists the source, test, and package paths changed by the code commit. |
| U11 registered test selection | Verified | `docs/verification/selection/m1-3-pool.json` contains 26 nodes and compares with zero differences. |

Changed code and test files, verified by focused tests:

- `backend/app/gameplay/m6_5_siege_runtime.py`
- `backend/app/gameplay/morale_refold_runtime.py`
- `backend/app/gameplay/rule_pack_validator.py`
- `backend/tests/test_m6_5_siege_runtime.py`
- `backend/tests/test_morale_refold_runtime.py`

Changed package data, verified by package loading and locked-hash checks:

- `packs/county_siege_morale_presence_1_0_2/pack.yaml`
- `packs/county_siege_morale_presence_1_0_2/aggregation_models/morale.yaml`
- `packs/county_siege_morale_presence_1_0_2/command_catalog/commands.yaml`
- `packs/county_siege_morale_presence_1_0_2/entity_types/gate.yaml`
- `packs/county_siege_morale_presence_1_0_2/fact_types/gate_passability.yaml`
- `packs/county_siege_morale_presence_1_0_2/fact_types/morale.yaml`
- `packs/county_siege_morale_presence_1_0_2/impact_profiles/gate.yaml`
- `packs/county_siege_morale_presence_1_0_2/models/gate_resolvers.yaml`
- `packs/county_siege_morale_presence_1_0_2/models/morale_resolvers.yaml`
- `packs/county_siege_morale_presence_1_0_2/pipelines/impact_gate.yaml`
- `packs/county_siege_morale_presence_1_0_2/play_patterns/play_pattern.yaml`
- `packs/county_siege_morale_presence_1_0_2/pool_defs/morale.yaml`
- `packs/county_siege_morale_presence_1_0_2/reactions/reactions.yaml`

Additional evidence files are `docs/verification/m1-3-morale-rulepack-20261128.md` and `docs/verification/selection/m1-3-pool.json`.

## Remaining

- Full backend suite was not run for this increment.
- This verifies the Morale package declaration and M6-5 assembly path. It does not complete M1-3 or Architecture v2.
- Pool integration scheduling, non-zero rate-bearing production Pool content, full Owner classification, complete reader inventory, P-3, R3, and the declaration-only probe remain open or unverified. This increment does not satisfy M1-3 U1-U11 as a whole.
- Production siege Gate values remain unconfigured. No deployment manifest or `integration` branch was changed.
