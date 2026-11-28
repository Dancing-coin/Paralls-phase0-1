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
| `m1-3-pool` | 17 | 0 | 0 |
| `m1-3-pool-domain-owner` | 1 | 0 | 0 |
| `m3-3-morale-refold-replay` | 1 | 0 | 0 |
| `m5-1-aggregation-models` | 6 | 0 | 0 |
| `m5-1-pool-definitions` | 9 | 0 | 0 |
| `m5-5-facttype-refold` | 38 | 0 | 0 |
| `m6-5-organization-roster` | 3 | 0 | 0 |
| `m6-5-production-wiring` | 6 | 0 | 0 |

Frozen selections: ownership `24/0/0`, modifier `12/0/0`, equipment `87/0/0`, inventory `56/0/0`, shared-replay `990/0/0` (`selected/problems/improvements`). All 13 comparisons were serial and returned zero problems and improvements. Raw outputs: `F:\paralls-verification\thread-a\m1-3-morale-package-final-selections-20261128-02\`.

The pytest and selection runs used F-drive temporary/output directories. No verification artifacts were added to the repository.

## Remaining

- Full backend suite was not run for this increment.
- This verifies the Morale package declaration and M6-5 assembly path. It does not complete M1-3 or Architecture v2.
- Pool integration scheduling, non-zero rate-bearing production Pool content, broader Owner/domain mappings, complete M1-3 U1-U10 acceptance, and R1/R2/R3 remain open or unverified.
- Production siege Gate values remain unconfigured. No deployment manifest or `integration` branch was changed.
