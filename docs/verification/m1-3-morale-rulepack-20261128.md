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

## P-3 Follow-up

Code/test commit `2cbe48d5` adds all seven Pool event types to `test_domain_schema_events_are_discovered_and_projected`. For each event, the test asserts that `FACT_TYPE_REGISTRY` discovers it, passes it to `HeavenlyAuthorityEventProjector`, and receives one graph node with domain `pool`. `main.py` subscribes the graph projector to every registered `gameplay.*` event type during startup.

Environment: Python `3.12.2`, SQLite `3.43.1`, `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`, and `app.__file__ = F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`. The focused command `python -B -m pytest -q -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\m1-3-p3-20261128-01\pytest-temp backend/tests/test_authority_graph_projection.py -k pool` returned `7 passed, 26 deselected, 6 warnings`. Raw output is `F:\paralls-verification\thread-a\m1-3-p3-20261128-01\pytest.log`.

The updated 33-node `m1-3-pool` selection returned `33/0/0`; frozen Ownership, Modifier, Equipment, Inventory, and shared-replay returned `24/0/0`, `12/0/0`, `87/0/0`, `56/0/0`, and `990/0/0`. These six serial comparisons cover 1,202 summed selected nodes including overlap. Raw comparison outputs are under `F:\paralls-verification\thread-a\m1-3-p3-20261128-01\selection-runs\`.

## Backend Full-Suite Recheck

At code/test commit `2cbe48d5`, `backend/tests` collected and ran with Python `3.12.2`, SQLite `3.43.1`, and the A-worktree import path. Result: `10,839 passed, 12 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1, in `1454.40s`. Raw output: `F:\paralls-verification\thread-a\m1-3-p3-backend-full-20261128-01\pytest.log`.

All 12 failed node IDs were rerun at parent `6816a2ee53617ed152e7e22fc03fd3774f397537`, before the P-3 test change. The same 12 node IDs failed with matching categories and output. Parent comparison output: `F:\paralls-verification\thread-a\m1-3-p3-parent-failure-compare-20261128-01\pytest.log`; isolated parent worktree was `F:\codex-temp\a-m13-p3-parent-verify-20261128-01\` and has been removed.

The repository-root `pytest` command stopped during collection with exit 2 because the Python 3.12.2 environment does not contain `jsonschema`, imported by `scripts/verification/tests/test_motion_profile_contract.py`. No project dependency was changed. This is an environment collection failure, separate from the completed backend suite.

## Unit DoD Status

| Item | Status | Evidence or gap |
|---|---|---|
| U1 Owner declaration and classification | Partial | The formal Owner document classifies `Morale / Formation` as stewarded. The repository still has no complete L3 declaration containing kind, writes, denies, invariants, commands, resolvers, and reads. |
| U2 FactType declaration | Verified for this FactType | The v1.0.2 package declares and loads the Morale Pool FactType with entity identity. |
| U3 event schema and P-3 | Verified for Pool events | All seven Pool event types are registered, resolve to the `pool` domain, and produce graph nodes in the explicit projector regression. Startup subscription to all registered `gameplay.*` types was statically checked. |
| U4 shared mechanism | Verified for the tested path | Pool and Morale commits use `OwnerCommitBuilder` and `replay_duplicate`; focused tests cover the Morale caller. |
| U5 R1/R2/R3 | Partial | Morale exact-retry and corrupt receipt rejection are tested. Checkpoint deletion/state-digest reconstruction was not tested for this increment. |
| U6 reader inventory and tests | Partial, partly static | The inspected A-side production readers are listed below. Subject-facing reads and consumers outside the inspected repository trees remain unverified. |
| U7 subject read and visibility | Partial | The package declares faction visibility. `GameplayReadAs` does not provide a Morale reader. |
| U8 package settings and Resolver | Verified | The selected locked package supplies the Pool definition and registered Resolver. |
| U9 migration probe and baseline | Partial | The 33-node unit selection and frozen five selections have zero differences. The success-standard probe must run after M1-3 is frozen and only add declarations/rule-pack data; that probe has not been run. |
| U10 evidence and changed paths | Verified | This file lists the source, test, and package paths changed by the code commit. |
| U11 registered test selection | Verified | `docs/verification/selection/m1-3-pool.json` contains 33 nodes at code/test commit `2cbe48d5` and compares with zero differences. |

### U6 Current A-Side Reader Inventory

Static search covered `backend/app/gameplay`, `backend/app/services/authority_graph_projector.py`, `backend/app/main.py`, tests, and scripts at code/test commit `2cbe48d5`.

| Reader | Use | Classification |
|---|---|---|
| `PoolProjector.rebuild` in `pool_runtime.py` | Rebuilds value, reservations, thresholds, and source revision from one Pool FactType stream | Owner projection/recovery |
| `MoraleRefoldAuthority.refold_after_casualty` and `.projection` | Reads the Morale Pool and historical Organization/LifeState inputs to commit or report Morale | Trusted settlement and projection helper |
| `FacilityIntegrityAuthority` in `facility_integrity_runtime.py` | Rebuilds Facility integrity Pool state before integrity commands | Trusted Owner command validation |
| `FacilityGateLayeredAuthority` in `facility_gate_layered_runtime.py` | Reads layered Gate Pool state, writes Pool adjustments and threshold crossings | Trusted Facility settlement |
| `ImpactGateObligationProjector` in `impact_gate_obligation.py` | Consumes Pool adjusted and threshold-crossed events for impact obligations | Derived obligation projection |
| `PlacePassabilityAuthority` in `place_passability_runtime.py` | Consumes Pool threshold crossings to revise Place passability | Trusted cross-domain input |
| `SiegePhysicalInputAuthority` in `siege_physical_input_runtime.py` | Validates a threshold crossing as the breach source for signed physical input | Trusted source-evidence validation |
| `HeavenlyAuthorityEventProjector`, subscribed in `main.py` to registered `gameplay.*` types | Projects registered Pool events into Siming's causal-event graph | Derived graph projection |

The Morale `projection` helper has no production caller in `backend/app`; M6-5 dispatch invokes `refold_after_casualty` instead. No subject-facing Pool or Morale query route was found in the inspected `main.py` call graph. This does not prove absence of external callers or downstream consumers outside the searched repository trees. The tested Pool graph projection cases are in `test_authority_graph_projection.py`; Pool/Morale command and settlement readers have focused tests listed above. No runtime behavior changed in this reader-inventory update.

## Pool Tick Integration Dependency

Static comparison of the formal RulePack format and Primitive General provisions with current packages shows that the Facility Gate integrity, Gate durability, latch durability, and Morale Pool definitions all use `integration: {mode: "none"}`. The formal design describes tick-triggered Process work as the mechanism that requests Pool integration, and the performance contract requires Pool integration and `temporal_process` ticks to share one compiled loop. The existing `PoolAuthorityService.integrate` method is a command primitive; no current production scheduler calls it from `PopulationDriver.current_tick`.

This leaves production Pool integration dependent on the M1-5 Process tick path and authored nonzero rate-bearing content. The demo's current Gate and Morale values remain unchanged, and no rate or deployment profile was inferred from test data or examples. M1-5 is still scheduled after domain migration work in the coordination board.

Changed code and test files, verified by focused tests:

- `backend/app/gameplay/m6_5_siege_runtime.py`
- `backend/app/gameplay/morale_refold_runtime.py`
- `backend/app/gameplay/rule_pack_validator.py`
- `backend/tests/test_m6_5_siege_runtime.py`
- `backend/tests/test_morale_refold_runtime.py`

P-3 follow-up test file:

- `backend/tests/test_authority_graph_projection.py`

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
