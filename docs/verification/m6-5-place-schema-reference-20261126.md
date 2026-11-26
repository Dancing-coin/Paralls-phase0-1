# M6-5 Place FactType Schema Reference

## Scope

The package validator already accepts the `place` FactType primitive and the production event-schema registry already registers Place events. Its FactType `event_schema_ref` resolver did not map a Place schema reference, so a package could not declare the passability FactType needed by the formal four-layer `impact_gate` profile.

This increment adds `place@v1` to the schema-reference mapping. It resolves the event registrations in `PLACE_EVENT_SCHEMAS`. It does not add a Place FactType to a package, change an event schema or payload, or write passability facts.

## Verification

- Base: `dc71c55497a6ca1a2d7f125f49602e792195db4f`; Python 3.12.2; SQLite 3.43.1; `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- Regression-first evidence: before the production change, the new test failed with `EventSchemaRegistryError: event_schema_unregistered` for `place@v1`.
- Focused tests: `test_gameplay_event_schema_registry.py` and `test_rule_pack_validator.py` returned `141 passed, 2 warnings`.
- Registered impact-gate selection: `selected=23 problems=0 improvements=0`.
- Frozen ownership selection: `selected=24 problems=0 improvements=0`.
- Frozen shared-replay selection: `selected=990 problems=0 improvements=0`.
- Raw output: `F:\paralls-verification\thread-a\m6-5-place-schema-contract-20261126-01\` and `F:\paralls-verification\thread-a\m6-5-place-schema-exacttip-20261126-01\`.

## DoD Status

- U2: not complete. The schema-reference mapping is available, but the package still does not declare the Place FactType.
- U3: not newly verified by this increment. Existing Place events are registered, but no new graph-projection assertion was run.
- U9: the registered impact-gate, ownership, and shared-replay selections above have zero differences.
- U10: this evidence records the code and selection change. No full backend suite was run.
- U11: the new regression test is included in `docs/verification/selection/m6-5-impact-gate-layered-execution.json`.

M6-5 remains in progress. The versioned package declaration, compiled Pipeline production consumer, Resolver handler registration, and shared `main.py` wiring remain open.
