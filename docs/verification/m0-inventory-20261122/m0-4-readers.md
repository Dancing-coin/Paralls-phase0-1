# M0-4 Static reader and importer inventory

- Code scan SHA: `0e67fe812280e7e518c84c27653153f5a69f2330`; latest coordination baseline checked was `0ecf65aae1698fabba06f06491f7800abdc1728a` and differs only in coordination docs.
- Commands: Python 3.12 AST parse of `backend/app/**/*.py` imports; AST scan of `read_stream`, `read_events`, and `get_event` calls; compare with `docs/verification/g2-visibility-budget/read-path-inventory.md`.
- Scan time: 2026-11-22 Asia/Shanghai.
- Conclusion level: static-only. Import counts include runtime modules, services, population-continuity code and other `backend/app` consumers. Same importing file counts once per runtime; function-local imports are traversed by AST. Tests are excluded from importer counts.

## Current read path count

AST result for `backend/app` non-test Python files:

```text
CALLS 993 FILES 115 BY_METHOD {'get_event': 410, 'read_stream': 261, 'read_events': 322}
RUNTIME_SCOPED_FILES 29
READS_IN_RUNTIME_FILES 531
```

The prior G2 inventory (`read-path-inventory.md:5-6`) records **987 calls / 113 files**, split as `read_stream=260`, `read_events=319`, `get_event=408`. The current count is +6 calls and +2 files. The enclosing runtime files contain 531 calls over 29 files. These are source-local counts, not proof that each call reads its enclosing runtime's own state.

## Importer counts by runtime

Counts are distinct importer files under `backend/app`; they include function-local imports. `call/read` is not automatically attributable from an import edge alone. The legacy G2 inventory classifies individual call sites, but its runtime aggregation is not a one-to-one authority map. “Audience” below is limited to already known read paths and does not imply authorization.

| Runtime | Importer files | Local read calls in runtime file | Known audience-facing read paths |
|---|---:|---:|---|
| ability | 5 | 0 | equipment/affordance consumers |
| action_consequence | 1 | 2 | action outcome consumers |
| action_window | 3 | 0 | P5 action sessions |
| adventure_basic_mirror | 1 | 0 | mirror path |
| bakery_reference | 2 | 7 | bakery vertical / mirror |
| civilization_capability | 2 | 1 | population capability input |
| construction_production | 7 | 74 | production, public works, facility consumers |
| contract | 7 | 35 | economy completion consumers and contract callers |
| credential | 4 | 10 | credential reference chain and land-right caller |
| daily_rhythm | 2 | 1 | population continuity |
| debt | 5 | 9 | economy privacy views, commerce, adventure |
| ecology_platform | 1 | 1 | ecology presentation |
| ecology | 2 | 50 | temporal/process consumers |
| econ1_economy | 7 | 6 | bakery/population settlement |
| economy_platform | 0 | 0 | none established |
| economy | 15 | 117 | economy and contract consumers |
| equipment | 7 | 4 | ability, phase3 composition, equipment command service |
| frost_farm | 0 | 0 | none established |
| gift | 1 | 1 | commerce |
| government_treasury | 1 | 3 | treasury |
| inventory_platform | 1 | 1 | inventory platform |
| inventory | 21 | 28 | production and custody flows |
| land_right | 1 | 1 | credential/reference flow |
| life_state | 1 | 10 | action consequence |
| modifier | 5 | 0 | equipment/phase3 composition |
| organization_government | 17 | 112 | broad government and organization workflows |
| organization_government_social_platform | 5 | 0 | social platform/presentation |
| ownership | 9 | 9 | credential, commerce and land rights |
| patch | 15 | 0 | content and package admission |
| reference_data | 1 | 1 | population branch preview |
| resource_body | 17 | 3 | abilities, equipment, recovery, soul sources |
| p5/scripted_mystery_case | 3 | 4 | P5 evidence and sessions |
| soul_effect | 0 | 4 | none established |
| soul_fact | 1 | 7 | soul effect |
| soul | 2 | 5 | soul fact/vulnerability |
| survival | 4 | 22 | bakery and population continuity |
The AST count is 36 runtime files when nested `p5/` is included. Local read counts sum to 528. Importer fan-out and per-file read calls are distinct measures. The AST does not establish that a call reads this runtime's data or that its result reaches a subject.

## Reproduction notes

The importer scan parsed every Python file under `backend/app`, collected `ImportFrom` nodes whose module ended in a discovered runtime module name, and deduplicated importer paths per runtime. The read-path scan counted AST calls with terminal name `read_stream`, `read_events`, or `get_event`, excluding test paths. It does not resolve aliases, `getattr`, dynamically loaded plugins, or whether multiple imported runtime objects share a Store instance.
