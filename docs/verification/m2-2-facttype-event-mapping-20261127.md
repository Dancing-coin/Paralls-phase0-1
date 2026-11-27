# M2-2 FactType event-schema candidate mapping

- Code commit: `b42a1c2420f7c808944243120ec50a27663e9ac6`.
- Change: `FactTypeRegistry` now builds an immutable exact `(event_type, schema_version)` index from the validated schema references of compiled FactTypes. It returns all candidates for shared schemas and retains the legacy Credential schema alias.
- The index provides candidate metadata only. It does not choose an instance FactType, determine visibility, evaluate selectors, or implement a subject-facing `read_as` API.
- Python: `3.12.2`; SQLite: `3.43.1`; `app.__file__` resolved to `F:\\codex-temp\\paralls-v2-thread-a-bond-20261121\\backend\\app\\__init__.py`. `PYTHONPATH`, pytest basetemp, and retained outputs were on F:.

## Verification

- Focused registry, RulePack, FactType, EventSchema, Holdings, and selector-registration tests: `147 passed, 2 warnings` in `4.49s`.
- The two new tests verify all three candidates for `gameplay.pool.adjusted@1`, no candidates for `@2`, and preservation of the legacy Credential alias. The new registered selection returned `selected=2 problems=0 improvements=0`.
- Related registered selections: event-schema reference resolution `2/0/0`, schema-ref retention `1/0/0`, schema index `1/0/0`, and principal-selector registration `6/0/0`.
- Frozen Ownership/Modifier/Equipment/Inventory/shared-replay selections returned `24/12/87/56/990`, all with zero problems or improvements. This is 1,169 frozen nodes.
- Raw focused output: `F:\\paralls-verification\\thread-a\\m2-2-facttype-event-mapping-focused-20261127-01\\focused.log`. Raw selection output: `F:\\paralls-verification\\thread-a\\m2-2-facttype-event-mapping-20261127-01\\`.
- Full backend suite was not run for this increment.

## Remaining M2-2 work

M2-2 remains blocked. The runtime event-to-FactType and visibility consumer, principal qualification and selector execution, reader classification, subject-facing `read_as`, and authoritative event-time source inventory across migrated domains remain incomplete. U7 is not complete. The index does not establish production visibility behavior.
