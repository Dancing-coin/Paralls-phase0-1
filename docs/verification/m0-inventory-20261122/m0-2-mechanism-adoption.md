# M0-2 Shared mechanism adoption

- Code scan SHA: `0e67fe812280e7e518c84c27653153f5a69f2330`; latest coordination baseline checked was `0ecf65aae1698fabba06f06491f7800abdc1728a` and differs only in coordination docs.
- Commands: read-only AST import/call scan over `backend/app/gameplay/**/*_runtime.py`; `rg -n 'OwnerCommitBuilder|StoreReadSnapshot|ProjectionCheckpointer|pinned_revisions' backend`.
- Scan time: 2026-11-22 Asia/Shanghai.
- Conclusion level: static-only.

## Shared base symbols and adoption

`owner_runtime_base.py` has no `__all__`. Its non-underscore module symbols are imported `GameplayEventStore`, `AppendBatchResult`, and `GameplayFailure`, plus the functions `replay_duplicate` and `rejected_result` (`owner_runtime_base.py:3-8, 11-33`). Python therefore exposes the imported public names as well as the two helpers.

| Runtime | Imported | Called | Import evidence |
|---|---|---|---|
| `contract_runtime.py` | `replay_duplicate`, `rejected_result` | both | line 16 |
| `credential_runtime.py` | `replay_duplicate` | replay helper | line 14 |
| `debt_runtime.py` | `replay_duplicate` | replay helper | line 26 |
| `econ1_economy_runtime.py` | `rejected_result` | rejection helper | line 13 |
| `economy_runtime.py` | `rejected_result` | rejection helper | line 23 |
| `gift_runtime.py` | `replay_duplicate` | replay helper | line 14 |
| `land_right_runtime.py` | `replay_duplicate` | replay helper | line 14 |
| `ownership_runtime.py` | both | both | line 17 |
| `survival_runtime.py` | `rejected_result` | rejection helper via function-local import | line 304 |

All other runtime files in the 36-file recursive set do not import or call these two functions in the static scan. This does not test behavioral equivalence.

## Local `_digest` variants

All top-level/local `_digest` definitions inside runtime files were enumerated with AST. Prefix means the `_digest` function body constructs a `sha256:`-prefixed digest. Decimal / bytes columns report explicit handling in that function body.

| File | Prefix / input handling evidence |
|---|---|
| `ability_runtime.py:322` | no prefix; no explicit Decimal/bytes handling |
| `action_window_runtime.py:311-313` | prefix; no explicit Decimal/bytes handling |
| `civilization_capability_runtime.py:20-22` | prefix; no explicit Decimal/bytes handling |
| `contract_runtime.py:1432-1433` | no prefix; Mapping/object `__dict__` fallback; no explicit Decimal/bytes handling |
| `credential_runtime.py:552-553` | no prefix; Mapping/object `__dict__` fallback; no explicit Decimal/bytes handling |
| `debt_runtime.py:947-948` | no prefix; Mapping/object `__dict__` fallback; no explicit Decimal/bytes handling |
| `ecology_platform_runtime.py:18-20` | prefix; no explicit Decimal/bytes handling |
| `economy_runtime.py:5219` | no prefix; Mapping/object `__dict__` fallback; no explicit Decimal/bytes handling |
| `equipment_runtime.py:955` | no prefix; no explicit Decimal/bytes handling |
| `gift_runtime.py:215` | no prefix; no explicit Decimal/bytes handling |
| `government_treasury_runtime.py:342` | no prefix; no explicit Decimal/bytes handling |
| `inventory_runtime.py:3046` | no prefix; no explicit Decimal/bytes handling |
| `land_right_runtime.py:203` | no prefix; no explicit Decimal/bytes handling |
| `modifier_runtime.py:159-165` | no prefix; explicitly canonicalizes `Decimal`; no explicit bytes handling |
| `ownership_runtime.py:522` | no prefix; no explicit Decimal/bytes handling |
| `reference_data_runtime.py:16-17` | prefix; `default=str`; no explicit Decimal/bytes handling |
| `resource_body_runtime.py:1302` | no prefix; no explicit Decimal/bytes handling |

The table covers named `_digest` functions in `*_runtime.py`; helper names such as `patch_runtime._canonical_digest`, class methods with different names, and inline SHA calculations are outside this exact scan. The queried debt and contract functions both return bare hex and use the Mapping/object fallback above. No change or consolidation is proposed.

## Store and checkpoint symbols

The whole-backend `rg` query returned no matches for `OwnerCommitBuilder`, `StoreReadSnapshot`, or `ProjectionCheckpointer`.

`pinned_revisions` is a field in persisted models (`models.py:54,119`) and receives non-negative integer shape checks (`models.py:64,134`). The inspected append paths validate expected/read revisions, idempotency, and event sequence; `rg` found no Store equality validation of `pinned_revisions` against current heads in `event_store.py`. Domain code sometimes validates its own pin maps, for example `resource_body_runtime.py:1148`. This is a static finding about Store-level checking.

## `visibility_policy` literals

AST counted dictionary entries whose key is `visibility_policy` and whose value is a string literal in `*_runtime.py` files: **96**, comprising `authority_only` 38, `project` 56, and `organization:summary` 2, across 18 files. These are hard-coded event-construction literals. Non-dictionary/model-copy assignments and literals outside runtime files are excluded by this query.

Reproduction command: Python 3.12 AST walk over all recursive `*_runtime.py` files, count `ast.Dict` key/value pairs with literal key `visibility_policy` and literal string value. No runtime test was run.
