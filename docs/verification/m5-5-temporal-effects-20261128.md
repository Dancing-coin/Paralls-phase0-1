# M5-5 Temporal Effects Static Package Declaration

## Change

The offline rule-pack loader now accepts a `temporal_effects` content section and exposes its entries through `LoadedPack.temporal_effects`.

This increment defines a provisional static entry shape with exactly four fields:

- `process_fact_type_ref` must reference a declared `process` FactType with `process_kind: temporal`.
- `pool_fact_type_ref` must reference a declared `pool` FactType with a registered Pool definition.
- `tick_policy_ref` and `exit_condition_ref` must be nonempty versioned references matching the loader's identifier syntax. Their targets are not resolved because no registries or namespaces are defined in the current package contract.

`next_tick` is instance state and is not stored in a package template. The loader does not schedule ticks, persist process instances, or settle Pool changes. The production consumer, package-version migration semantics, reference namespaces, and formal documentation remain open. This A-side shape is an implementation proposal and does not complete the formal temporal-process contract.

## Verification

- Python `3.12.2`; SQLite `3.43.1`; `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- RED: the three new tests failed because the loader rejected the unregistered `temporal_effects` content section.
- GREEN: `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend F:\codex-temp\thread-a-python312\Scripts\python.exe -m pytest backend/tests/test_rule_pack_validator.py --basetemp F:\paralls-verification\thread-a\m5-5-temporal-effects-20261128-01\pytest-validator` returned `140 passed, 2 warnings`.
- M5-5 registered selection: `selected=38 problems=0 improvements=0`.
- New temporal-effects selection: `selected=3 problems=0 improvements=0`.
- Frozen Ownership, Modifier, Equipment, Inventory, and shared-replay selections: `24/0/0`, `12/0/0`, `87/0/0`, `56/0/0`, and `990/0/0` respectively.
- `git diff --check` passed. Full backend suite was not run.
- Raw output: `F:\paralls-verification\thread-a\m5-5-temporal-effects-20261128-01\`.

## Status

M5-5 remains in progress. This change validates a provisional static declaration only. No production scheduler, instance lifecycle, persisted event, command registration, or deployment behavior is verified.
