# M1-3 Pool reader inventory recheck

Date: 2026-11-28

## Scope and basis

This is a bounded static inventory of Pool readers at A documentation HEAD `285318225cffc3e9a9733b6c1da72d8b45119e1c` and code/test tip `0b7852fe1152588aaf1ec4c718834677a0112b8d`. Searches covered `backend/app`, `backend/tests`, `scripts`, `packs`, and `Godot` for `PoolProjector`, `PoolAuthorityService`, `PoolProjection`, Pool event types, and the current Morale/Gate Pool FactType IDs.

The formal Owner table lists Morale / Formation and Production / Facility as stewarded Owners. FactType defines `primitive: pool` separately from `owner_ref`. The Pool primitive is therefore a shared implementation and does not establish a new `Pool` Owner. The Morale and Gate Pool facts remain owned by their respective domain Owners.

## Production reader map

| Production reader | Read/use | Authority classification | Focused test coverage |
|---|---|---|---|
| `PoolProjector.rebuild` and `PoolAuthorityService._read` in `pool_runtime.py` | Rebuilds value, reservations, bounds, integrated windows, thresholds, and stream revision; validates Owner command preconditions | Primitive projection and Owner command validation | `test_pool_runtime.py` |
| `MoraleRefoldAuthority.refold_after_casualty` in `morale_refold_runtime.py` | Reads Morale Pool state and historical Organization/LifeState inputs before committing the Morale Pool | Morale Owner settlement; `.projection` is a helper with no production caller found | `test_morale_refold_runtime.py`; dispatch and recovery cases in `test_m6_5_siege_runtime.py` |
| `FacilityIntegrityAuthority` in `facility_integrity_runtime.py` | Rebuilds Gate integrity Pool state before integrity commands | Production / Facility Owner command validation | `test_facility_integrity_runtime.py` |
| `FacilityGateLayeredAuthority` in `facility_gate_layered_runtime.py` | Rebuilds durability and integrity Pools, commits layered impacts, and emits threshold crossings | Production / Facility Owner settlement | `test_facility_gate_layered_runtime.py` |
| `rebuild_impact_gate_obligations` in `impact_gate_obligation.py`, accessed through `M6_5_SiegeRuntime` | Reads adjusted and threshold-crossed Pool events to derive open or settled physical-impact obligations | Derived recovery projection consumed by trusted M6-5 orchestration | `test_facility_gate_layered_runtime.py`; `test_m6_5_siege_runtime.py` |
| `PlacePassabilityAuthority` in `place_passability_runtime.py` | Reads the Gate integrity threshold crossing as input to a separately committed Place assessment | Trusted cross-domain source evidence | `test_place_passability_runtime.py` |
| `SiegePhysicalInputAuthority` in `siege_physical_input_runtime.py` | Validates a Gate threshold crossing as physical-impact source evidence | Trusted source-evidence validation | `test_siege_physical_input_runtime.py` |
| `HeavenlyAuthorityEventProjector`, subscribed by `main.py` to registered gameplay event types | Projects the seven registered Pool event types into the causal-event graph | Derived graph projection | Seven Pool cases in `test_authority_graph_projection.py::test_domain_schema_events_are_discovered_and_projected` |

The A-code search found no additional Pool runtime reader in `scripts` or `Godot`. Pool references in `packs` are declarative FactType, Pool definition, Resolver, pipeline, impact-profile, or reaction inputs. They are not additional executable readers. `main.py` does not special-case Pool events; it subscribes through the registered gameplay event list, and the graph projection regression verifies the Pool event cases.

## Current-tip verification

- Python: `3.12.2`, executable `F:\codex-temp\thread-a-python312\Scripts\python.exe`.
- SQLite: `3.43.1`.
- `PYTHONPATH`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`.
- Import check: `app.__file__ = F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- Focused command ran the eight test files listed above with `-B -m pytest -q -p no:cacheprovider`, F-drive `--basetemp`, and F-drive JUnit output.
- Result: `142 passed, 6 warnings in 7.78s`. Warnings are existing Starlette/httpx, AnyIO, and FastAPI `on_event` deprecations.
- Raw output: `F:\paralls-verification\thread-a\m1-3-reader-inventory-20261128-01\pytest.log` and `junit.xml`.

## Status

- Verified at the A-code repository boundary: all identified production Pool readers are classified above and their focused test files pass together.
- Static only: absence of executable consumers outside the searched A repository; this does not prove absence in external services or future code.
- Still open: no subject-facing Morale or Pool `read_as` route was found. U7 and M2-2 visibility/selector work remain incomplete. This inventory does not complete M1-3 U6 across uninspected external consumers, nor M1-3 as a whole.
- No runtime or package content changed. The full backend suite was not run, and `integration` was not modified.
