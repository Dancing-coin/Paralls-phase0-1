# M2-2 exact event-schema reference resolution

- Code commit: `c55b009fa601f0334345741f1fcb3d8dc5e08948`.
- Change: expose the existing explicit schema-reference table as `resolve_event_schema_ref()`, returning exact `(event_type, schema_version)` keys. `require_event_schema_ref()` reuses the resolver and preserves registration checks and the legacy Credential reference behavior.
- This is an input mechanism for a future FactType mapping consumer. It does not evaluate visibility or selectors and does not implement `read_as`.
- Python: `3.12.2`; SQLite: `3.43.1`; `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`. `PYTHONPATH`, `TEMP`, `TMP`, `PYTHONPYCACHEPREFIX`, pytest basetemp, and retained outputs were set to F-drive paths.

## Verification

- TDD red: test collection failed because `resolve_event_schema_ref` was not yet exported from the registry module.
- EventSchema, RulePack, FactType, and Holdings focused tests: `174 passed, 2 warnings`.
- All 40 registered selections: zero problems and zero improvements. The new M2-2 selection returned `selected=2 problems=0 improvements=0`.
- Frozen five selections: Ownership 24, Modifier 12, Equipment 87, Inventory 56, and shared-replay 990. Total `1,169` selected nodes, zero problems and zero improvements.
- Current A-tip full backend suite: `10,794 passed, 6 failed, 2 skipped, 2 xfailed, 227 warnings`, exit code 1. Four failures reproduced at the parent commit: missing `tokenizers`, two Godot script parse failures, and the population readiness report missing `resource_bounds`. Two additional full-suite failures were environmental: the recovery subprocess inherited malformed `GIT_CONFIG_COUNT` values and the ASGI import timed out. With `GIT_CONFIG_COUNT=0`, the recovery test passed at the parent; the ASGI test passed at both the parent and current commit when run alone.
- Full-suite failure and parent-comparison raw outputs are under `F:\paralls-verification\thread-a\m2-2-event-schema-resolution-20261127-05\`, `...-06\`, and `...-07\`. Selection outputs are under `...-04\`.

## Remaining M2-2 work

M2-2 remains blocked. The exact schema-ref resolver and immutable FactType reverse index exist, but the runtime event-to-FactType/visibility consumer, principal qualification and selector evaluation, subject-facing `read_as`, reader classification, and authoritative time producers across domains are incomplete. U7 is not complete. Full backend regression is not green.
