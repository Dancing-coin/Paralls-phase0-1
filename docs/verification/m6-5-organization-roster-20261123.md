# M6-5 Organization roster input

## Scope

This unit adds an as-of-`global_sequence` roster query over the existing committed Organization membership stream. The existing Owner writer and persisted event remain the only source of membership facts. The query filters by configured `organization_ref` and versioned `role_ref`, verifies Owner transaction provenance, and returns the Organization stream revision visible at the requested sequence. No event type or persisted payload changed.

Code commit: `9cb0cbd5af691911a2b11e5e1be9e8e10d1bcba0`.

## Baseline and environment

| Item | Result |
|---|---|
| Base SHA | `581f171930c2a0b7f19e6be92710d18323215bde` |
| Branch | `thread-a/ownership-bond-followup-20261121` |
| Python | `3.12.2` |
| SQLite | `3.43.1` |
| `app.__file__` | `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py` |
| `PYTHONPATH` | `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend` |

## Verification

| Check | Command/result | Depth |
|---|---|---|
| TDD red | New roster tests failed because `organization_garrison_roster_at` was absent | Verified |
| Targeted suite | `D:\Temp\paralls-g0-py312\Scripts\python.exe -m pytest -q backend/tests/test_organization_government_social_platform_runtime.py` → `9 passed, 2 warnings` | Verified |
| Unit selection | `compare_selection.py --selection docs/verification/selection/m6-5-organization-roster.json` → `selected=3 problems=0 improvements=0` | Verified |
| P-3 registry | `gameplay.organization.membership_delegation_recorded@1` is registered and resolves to domain `organization` | Verified |
| Full suite / all selections | Not run | Unverified |

Raw output is in `F:\paralls-verification\thread-a\m6-5-roster-red-20261123\` and the selected-node run is in `F:\paralls-verification\thread-a\m6-5-roster-selection-20261123\`.

## Reader inventory

`rg` over `backend/app`, `backend/tests`, `scripts`, and probes found the following direct persisted-event declarations and readers:

| Role | Path and lines |
|---|---|
| Organization writer | `backend/app/gameplay/organization_government_runtime.py:6921-6986` |
| Organization event schema and replay projector | `backend/app/gameplay/organization_government_social_platform_runtime.py:363,442` |
| Central schema visibility | `backend/app/gameplay/event_schema_registry.py:356` |
| Governed operation contracts | `backend/app/gameplay/governed_contract_catalog.py:1560,1845` |
| Existing tests | `backend/tests/test_organization_government_social_platform_runtime.py:459` and `:569-689` |
| New historical roster query | `backend/app/gameplay/organization_government_social_platform_runtime.py:115-175` |

The new query reads only the Organization stream through the requested sequence. It selects the latest membership state per member and returns unknown for an empty roster, malformed history, or an event without an Organization Owner transaction receipt. Changes committed after the cutoff do not affect the result.

## U1-U11 status for this input unit

| DoD | Status | Evidence or reason |
|---|---|---|
| U1 Owner declaration | Not done | This query does not migrate the Organization Owner declaration. |
| U2 FactType declaration | Not done | Existing membership event is reused; no new FactType declaration was added. |
| U3 schema visibility | Verified | Existing event is in the central registry and maps to `organization`. |
| U4 shared mechanism | Not applicable | Query does not append facts. |
| U5 R1-R3 | Not applicable | No new writer or receipt path was added. |
| U6 readers | Verified for this event | Direct writer, projector, event schema, governed operation and tests are listed above. |
| U7 visibility/read boundary | Partially verified | Source events are `project`; `read_as` qualification is outside this unit. |
| U8 package/resolver | Not done | No resolver or package content was added. |
| U9 probe and baseline | Partial | Three dedicated tests and their registered unit selection passed; no full suite run. |
| U10 evidence | Verified | This file records the change and verification. |
| U11 selection | Verified | `docs/verification/selection/m6-5-organization-roster.json`. |

This source-query unit does not complete Morale refolding, Presence integrity input, Gateway/L5 dispatch, or M6-5. Existing legacy membership events remain readable because their event type and payload are unchanged. No full v2 Owner migration claim is made.
