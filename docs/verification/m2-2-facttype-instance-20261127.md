# M2-2 Event-to-FactType Instance Resolution

## Scope

- Code commit: `9520808e`, based on `81699019`.
- `FactTypeRegistry.resolve_event_fact_type` resolves an event only when its `stream_id` matches exactly one FactType declared for the event type and schema version. A declared payload `fact_type`, when present, must equal the stream reference.
- Registered wildcard scope templates resolve to the concrete FactType reference carried by the stream. A legacy domain stream, unknown schema, conflicting payload reference, or ambiguous match returns `None`.
- The resolver follows the formal event envelope, where `stream_id` equals the FactType ID. It does not alter event storage, event schemas, or existing readers.

## Verification

Environment: Python `3.12.2`, SQLite `3.43.1`, and `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.

| Check | Result |
|---|---|
| TDD red | Four new tests failed with `AttributeError` because `resolve_event_fact_type` was absent |
| Resolver tests | `4 passed, 132 deselected, 2 warnings` |
| RulePack, FactType registry, rejection, and Holdings registry modules | `177 passed, 2 warnings` |
| Registered selection | `selected=4 problems=0 improvements=0` |
| Frozen ownership / modifier / equipment / inventory / shared-replay | `24/0/0`, `12/0/0`, `87/0/0`, `56/0/0`, `990/0/0` |
| Full backend suite | Not run for this increment |

Raw output is under `F:\paralls-verification\thread-a\m2-2-facttype-instance-20261127-01` through `-05`. The corrected focused-module output is `-03\focused-corrected.log`; frozen five-selection outputs are under `-04`; the registered selection output is under `-05\registered`.

## Remaining M2-2 Gaps

- Existing Information and legacy Credential events use domain-specific stream IDs and do not resolve through the formal FactType-ID stream contract.
- Historical principal qualification, selector evaluation, runtime visibility enforcement, and the generic `read_as` entry point remain unimplemented.
- This increment does not complete M2-2 or U7.
