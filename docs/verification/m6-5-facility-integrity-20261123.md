# M6-5 Facility gate integrity input

## Scope and contract

Commit `34d7e7342afb12ff308a807e6a03b6639ca90797` adds `FacilityIntegrityAuthority`, which writes configured `fact:facility:<gate>:integrity` streams through the existing Pool primitive using the Production/Facility Owner principal. Definitions must declare a `breach` threshold. A crossing emits the existing committed `gameplay.pool.threshold_crossed` event. The writer does not update Presence passability.

General `Facility.condition` and legacy acquisition/repair events remain in their existing Construction projection and are not treated as gate integrity. No legacy event name or payload changed. The integrity Pool stream is the only current source for this new gate-integrity fact.

## Baseline and environment

| Item | Result |
|---|---|
| Base SHA | `8a144daf697062a4d399d4097af9b26eebe471d3` |
| Unit commit | `34d7e7342afb12ff308a807e6a03b6639ca90797` |
| Python | `3.12.2` |
| SQLite | `3.43.1` |
| `app.__file__` | `F:\codex-temp\a-m6-5-facility-verify-34d7e734\backend\app\__init__.py` |
| `PYTHONPATH` | `F:\codex-temp\a-m6-5-facility-verify-34d7e734\backend` |

## Verification of the standalone commit

| Check | Command/result | Status |
|---|---|---|
| TDD red | Initial facility writer test failed collection because the writer module did not exist. A later Owner receipt assertion also failed because Pool recorded the generic principal. | Verified |
| Targeted suite | Facility integrity, Pool, Construction Production, facility repair and gameplay schema registry test files → `49 passed, 2 warnings` | Verified in detached worktree at `34d7e734` |
| Permanent selection | `selected=5 problems=0 improvements=0` | Verified in detached worktree at `34d7e734` |
| P-3 | `gameplay.pool.threshold_crossed` is registered; its current registry domain is `pool`, not `unknown` | Verified |
| Full suite | Not run | Unverified |

Raw output is in `F:\paralls-verification\thread-a\m6-5-facility-integrity-commit-34d7e734\`.

## Reader and writer inventory

| Role | Path and lines |
|---|---|
| New Production/Facility writer | `backend/app/gameplay/facility_integrity_runtime.py:16-96` |
| Shared Pool writer and projector | `backend/app/gameplay/pool_runtime.py:147-329,329-645` |
| Pool event declarations | `backend/app/gameplay/pool_event_schema.py:1-27` |
| Production EventSchema factory registration | `backend/app/gameplay/event_schema_registry.py:443-451` |
| Graph/FactType schema discovery | `backend/app/gameplay/event_schema_registry.py:420-440`; `backend/app/models/fact_type.py:54-67` |
| Existing general condition projection and readers | `backend/app/gameplay/construction_production_runtime.py:286-300,1150-1210,5549,5633-5645,5825,7407` |
| Existing repair event assertions | `backend/tests/test_infra_construction_facility_repair.py:66,167` |
| New Owner and rebuild tests | `backend/tests/test_facility_integrity_runtime.py:19-113`; `backend/tests/test_pool_runtime.py:140-177` |

No persisted event schema change was made. The writer uses the existing Pool event types and the production EventSchema factory already registers them. Current L5 code only compiles declarations. No production consumer dispatches the committed breach event yet.

## U1-U11 status for this input unit

| DoD | Status | Evidence or reason |
|---|---|---|
| U1 Owner declaration | Not done | This input writer does not migrate the Production/Facility Owner declaration. |
| U2 FactType declaration | Not done | The domain FactType schema/visibility declaration is still pending. |
| U3 schema visibility | Verified for event type | Existing Pool event is registered and resolves to `pool`; domain Owner mapping is not yet explicit in the graph registry. |
| U4 shared mechanism | Verified | Uses `PoolAuthorityService` with the Production/Facility transaction principal and Owner fragment. |
| U5 R1-R3 | Partial | Exact retry and Pool rebuild are tested. R2 transaction/receipt validation and full snapshot restore are not covered in this unit. |
| U6 readers | Verified for the existing Pool event types | Writer, Pool projector, schema discovery, factory and previous condition readers are enumerated. Presence dispatcher is not implemented. |
| U7 visibility/read boundary | Not done | Existing Pool events are `authority_only`; downstream `read_as` and cross-owner trigger authorization remain unverified. |
| U8 package/resolver | Not done | Facility threshold configuration is supplied as `PoolDefinition`; no production package or resolver registration was added. |
| U9 probe and baseline | Partial | Dedicated tests and selection passed; no full suite run. |
| U10 evidence | Verified | This file lists changed code/test/selection and verification. |
| U11 selection | Verified | `docs/verification/selection/m6-5-facility-integrity.json`, five nodes. |

## Remaining input and dispatch work

Code search found no committed gate-impact producer carrying both gate identity and damage quantity. The new Owner writer therefore exposes the committed integrity input operation but is not connected to a combat/impact command source. It must not be driven by `facility_repaired` or generic condition changes. The L5 production dispatcher and trusted `reevaluate_passability` output registration also remain unimplemented. M6-5 and Morale/Presence end-to-end validation remain incomplete.
