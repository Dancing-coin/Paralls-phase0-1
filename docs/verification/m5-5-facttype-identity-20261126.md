# M5-5 FactType identity and scope consistency

## Change

The FactType schema requires `identity` to be present and one of `singleton`, `entity_ref`, `collection_ref`, or `region_ref`. This increment adds dedicated validator rejections for missing and unknown identity values and enforces the schema's scope pairing: singleton requires `global`, while the other three identities cannot use `global`.

The direct `FactTypeRegistry.compile` test fixture now supplies `entity_ref`, matching its `fact:credential:*:link` identifier. Existing package contents already declared valid identities.

## Verification

Implementation commit: `177765ba300a26f6aebfc77bcdb291e58da480ad`. Enum coverage commit: `38a1ccd0`.

- Python: `D:\Temp\paralls-g0-py312\Scripts\python.exe --version` returned `Python 3.12.2`.
- Import path: with `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`, importing `app` returned `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- Red test: the two new missing/unknown identity cases failed before the validator change with `Failed: DID NOT RAISE RegistrationRejected`.
- Focused tests: `python -m pytest -q backend\tests\test_rule_pack_validator.py backend\tests\test_credential_fact_type_registry.py backend\tests\test_credential_facttype_rejections.py` returned **124 passed, 2 warnings**. Warnings are the existing Starlette/httpx and anyio deprecations.
- Resolution-order regression assertion: `test_unrelated_fact_types_follow_owner_order_with_stable_fact_id_tiebreak` returned **1 passed, 2 warnings**, asserting uniqueness and consecutive values starting at 10.
- Identity enum focused tests: `pytest -q backend\tests\test_rule_pack_validator.py -k identity` returned **5 passed, 118 deselected, 2 warnings**, including positive `collection_ref` and `region_ref` cases.
- After registering the two positive cases, the full validator test file returned **123 passed, 2 warnings** and the M5-5 selection returned **29 selected, 0 problems, 0 improvements**.
- M5-5 registered selection: 27 selected, 0 problems, 0 improvements.
- Frozen G5 selections: ownership 24/0/0, modifier 12/0/0, equipment 87/0/0, inventory 56/0/0, shared-replay 990/0/0 (selected/problems/improvements).
- Raw commands and outputs are in `F:/paralls-verification/thread-a/m5-5-identity-contract-20261126-01/`, `m5-5-facttype-selection-20261126-02/`, and `m5-5-g5-20261126-01/`.

## Scope and remaining work

This verifies the FactType identity and scope contract increment only. It does not close M5-5. The separate catalog audit still identifies validator rules that require formal registration contracts or package representations. The full 10,745-node suite was not rerun for this increment. The latest full-suite evidence remains the 7ab4d72e worktree result recorded in `m5-3-full-backend-20261126.md`, not this change.

Status is verified for this increment; the broader M5-5 unit remains in progress.
