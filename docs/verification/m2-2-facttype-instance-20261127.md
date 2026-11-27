# M2-2 Event-to-FactType Instance Resolution

## Scope

- Code commits: `9520808e0a67919663d1d167efa389b2fdffb431` adds the resolver; `244a120920fc197ef9721bac34992226255e959b` rejects an explicitly null payload `fact_type`. The final code commit is based on `9520808e`.
- `FactTypeRegistry.resolve_event_fact_type` resolves an event only when its `stream_id` matches exactly one FactType declared for the event type and schema version. A declared payload `fact_type`, when present, must equal the stream reference.
- Registered wildcard scope templates resolve to the concrete FactType reference carried by the stream. A legacy domain stream, unknown schema, conflicting payload reference, or ambiguous match returns `None`.
- The resolver follows the formal event envelope, where `stream_id` equals the FactType ID. It does not alter event storage, event schemas, or existing readers.

## Verification

Environment: Python `3.12.2`, SQLite `3.43.1`, and `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.

| Check | Result |
|---|---|
| TDD red | Four new tests first failed with `AttributeError` because `resolve_event_fact_type` was absent. A fifth test then reproduced explicit `fact_type: null` being accepted; the fix checks key presence |
| Resolver tests at final code tip | `5 passed, 132 deselected, 2 warnings` |
| RulePack, FactType registry, rejection, and Holdings registry modules at final code tip | `178 passed, 2 warnings` |
| Registered selection at final code tip | `selected=5 problems=0 improvements=0` |
| Frozen ownership / modifier / equipment / inventory / shared-replay | `24/0/0`, `12/0/0`, `87/0/0`, `56/0/0`, `990/0/0` |
| Full backend suite | Not run for this increment |

Raw output is under `F:\paralls-verification\thread-a\m2-2-facttype-instance-20261127-01` through `-08`, plus the null-payload RED/GREEN runs under `F:\paralls-verification\thread-a\m2-2-facttype-null-20261127-01` and `-02`. The corrected focused-module output is `-03\focused-corrected.log`; the final frozen five-selection outputs are under `-06`; the final registered selection output is under `-07\registered`; the five resolver tests at final code tip are under `-08\focused.log`. An initial module command referenced the nonexistent `test_facttype_rejections.py` filename and exited 4 before collection; the corrected command used `test_credential_facttype_rejections.py` and passed.

## Remaining M2-2 Gaps

- Existing Information and legacy Credential events use domain-specific stream IDs and do not resolve through the formal FactType-ID stream contract.
- Historical principal qualification, selector evaluation, runtime visibility enforcement, and the generic `read_as` entry point remain unimplemented.
- This increment does not complete M2-2 or U7.
