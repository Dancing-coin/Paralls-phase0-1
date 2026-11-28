# M5-5 Process Kind Registration Validation

## Change

FactType registration now accepts an explicit `process_kind` only when the primitive is `process` and the value is `temporal` or `stepwise`. Omitted `process_kind` remains valid and retains the documented `stepwise` default. Invalid values use the existing `facttype_process_kind_invalid` rejection code.

## Verification

- Python `3.12.2`; `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`; SQLite `3.43.1`.
- RED: three new registry tests for an unknown string, `None`, and an integer all failed because the registry accepted each value.
- GREEN: FactType registry and RulePack validator tests returned `169 passed, 2 warnings`.
- New process-kind selection: `selected=3 problems=0 improvements=0`.
- M5-5 selection: `selected=38 problems=0 improvements=0`.
- Frozen Ownership, Modifier, Equipment, Inventory, and shared-replay selections returned `24/0/0`, `12/0/0`, `87/0/0`, `56/0/0`, and `990/0/0`.
- Full backend suite was not run. `git diff --check` was checked before commit.
- Raw output: `F:\paralls-verification\thread-a\m5-5-process-kind-20261128-01\`.

## Status

This closes the FactType `process_kind` value-validation gap only. The broader M5-5 Owner declaration, invariant grammar, Resolver capability attestation, and temporal-effects runtime contracts remain open.
