# A current-tip G5 selection verification

This is a cross-unit regression addendum for A branch tip `022f774d07fbbadc262a0a410738988fc9a780cb`. It does not change any implementation and does not close the units whose production wiring or contracts remain incomplete.

## Environment and outputs

- Python: `D:\Temp\paralls-g0-py312\Scripts\python.exe`, version 3.12.2
- `PYTHONPATH`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`
- `TEMP`, `TMP`, and comparator output: `F:\paralls-verification\thread-a\a-current-tip-selections-20261126\`
- Runner: `docs/verification/absorb-main-3bf3418e/compare_selection.py`

## Results

| Registered selection | Result |
|---|---|
| `m1-3-pool.json` | `selected=17 problems=0 improvements=0` |
| `m5-5-facttype-refold.json` | `selected=22 problems=0 improvements=0` |
| `m1-2-holdings.json` | `selected=24 problems=0 improvements=0` |
| `m3-2-store-read-snapshot.json` | `selected=7 problems=0 improvements=0` |
| Frozen `modifier.json` | `selected=12 problems=0 improvements=0` |
| Frozen `equipment.json` | `selected=87 problems=0 improvements=0` |
| Frozen `inventory.json` | `selected=56 problems=0 improvements=0` |

Raw logs are `m1-3-pool.log`, `m5-5.log`, `m1-2.log`, `m3-2.log`, `modifier-run02.log`, `equipment-run02.log`, and `inventory-run02.log` in the output directory. M3-1, M5-3, Ownership, and shared-replay current-tip results are recorded in their unit evidence and the same branch tip was used for this run.

## Interpretation

- M1-3 remains `待门禁` because the production world-tick integration caller and full U1-U11 closure are not implemented.
- M1-2 remains `阻塞` because its production Inventory command migration would modify the shared `inventory_runtime.py` boundary.
- M5-5 remains in progress because formal `temporal_effects` fields and production package lifecycle wiring are unspecified or absent.
- M3-2 remains a mechanism verification result, not a claim that all reader paths use the snapshot.
- Backend full suite was not run at this tip.
