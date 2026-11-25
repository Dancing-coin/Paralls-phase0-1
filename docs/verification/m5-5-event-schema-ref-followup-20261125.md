# M5-5 `event_schema_ref` follow-up

## Scope

This follow-up verifies the committed `event_schema_ref` registration-resolution increment at `16ad9b9c`. It covers the rule-pack validator, Information production wiring, Holdings FactType registration, and Credential schema compatibility. It does not claim completion of M5-3, M5-4, M1-2 production wiring, or Architecture v2.

## Environment

- Worktree: `F:\codex-temp\paralls-v2-thread-a-bond-20261121`
- Branch: `thread-a/ownership-bond-followup-20261121`
- Code commit under test: `16ad9b9c`
- Python executable: `D:\Temp\paralls-g0-py312\Scripts\python.exe`
- `PYTHONPATH`: current A worktree `backend`
- SQLite: previously verified as 3.43.1 for this worktree

## Verification

Command:

```text
set PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend
D:\Temp\paralls-g0-py312\Scripts\python.exe -m pytest -q backend/tests/test_rule_pack_validator.py backend/tests/test_information_production_wiring.py backend/tests/test_holdings_fact_type_registry.py backend/tests/test_credential_v2_event_schema.py
```

Raw output: `F:\paralls-verification\thread-a\m5-5-event-schema-ref-20261125-03\pytest.log`

Result: **138 passed, 6 warnings, exit code 0**.

The run exercises registered Pool, Holdings, Machine, and Information schema references, rejection of unknown references, Information report production and recipient-private delivery, Holdings registration, and preservation of the Credential legacy schema symbol.

## Verification depth

- Focused regression: **verified**.
- Frozen ownership and shared-replay selections: inherited from the prior M5-5 evidence. This follow-up did not rerun them.
- Full backend suite: **not run**.
- Production deployment and production Gate values: **not verified**. The A worktree `.env` remains local demonstration configuration.
- M1-2 Inventory-to-Holdings production wiring: **blocked** by the shared `inventory_runtime.py` boundary.

## Status

The `event_schema_ref` increment is verified at focused-test depth. M5-5 remains open for the remaining package lifecycle and production-boundary items. This evidence does not authorize integration or merge.
