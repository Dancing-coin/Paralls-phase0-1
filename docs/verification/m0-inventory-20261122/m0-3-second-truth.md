# M0-3 Second-truth recheck

- Code scan SHA: `0e67fe812280e7e518c84c27653153f5a69f2330`; latest coordination baseline checked was `0ecf65aae1698fabba06f06491f7800abdc1728a` and differs only in coordination docs.
- Commands: `rg -n` for the six B0 fields, event-prefix routing, subscriptions, revision references, private runtime imports; source line inspection.
- Scan time: 2026-11-22 Asia/Shanghai.
- Conclusion level: static-only; facts only, no remediation proposal.

## B0 six fields

`daily_rhythm_runtime.py:14-17` maps four state fields to registered FactTypes; `daily_rhythm_runtime.py:54-55` constructs an initial row containing `last_update_tick`, `activity_phase`, `fatigue`, `need_pressure`, `next_due_tick`, and `starvation_credit`. `population_continuity/hot_state.py:11-18,321-326` declares and initializes the same six hot fields. `population_continuity/continuous.py:64-96` reads and transforms them. `population_continuity/world.py:702-706,818` publishes results into hot-state operations.

The hot-state implementation is a separate mutable in-memory representation backed by lists and dictionaries (`hot_state.py:51-66,130-152,302-326`); no SQL or direct database write appears in this class. Separately, `daily_rhythm_runtime.py:68-104` appends initialized/updated events to its event store. This scan did not find an Owner declaration assigning the six fields to a registered Owner or establish that every hot-state write is event-backed. The FactType names exist, but that alone does not establish Owner ownership.

## Siming wildcard and FactType subscriptions

`main.py:2287-2293` selects gameplay event types from `FACT_TYPE_REGISTRY.event_types()` and subscribes the graph projector to each enumerated type. `main.py:2297-2299` separately subscribes a `fact_type` loop. The Siming authority-event handlers at lines 2278-2280 are exact strings. No `subscribe("*")` registration was found in these paths.

`services/authority_graph_projector.py:24,46-64` still stores a current projection payload and copies a `source_revision_vector`; comments at lines 47-49 describe the intended Owner-revision reconciliation/OwnerFactQuery direction. This is a stored projection with revision metadata, not evidence of complete OwnerFactQuery reconciliation.

## Three Siming copies

| Copy | Mutable state evidence | Owner revision reconciliation evidence |
|---|---|---|
| State tree | `services/siming_state_tree.py:32,45-46,114-115` stores `_latest_snapshot` | no Owner revision vector check found in this file |
| Global situation layer | `services/siming_global_situation.py:112,210,222-239` stores snapshots and mutates lifecycle/freshness | no Owner revision vector check found in this file |
| Narrative core | `services/siming_narrative_core.py:17-33` stores per-room open counts and revisions; update increments local revision and installs state | no Owner revision comparison found in this file |

The three components have local state/snapshot representations. Search results do not establish a shared Owner revision reconciliation path across them.

## Prefix routing and private cross-runtime imports

- Exact search for `DOMAIN_BY_EVENT_PREFIX` and `domain_by_event_prefix` returned no matches under `backend/`.
- `main.py:2289-2290` uses `event_type.startswith("gameplay.")` to filter registered gameplay types for subscription. This is a subscription namespace filter, not a domain-to-Owner mapping.
- `ecology_runtime.py:25` imports `_take_weather_quote_admission_issuer` and `_take_weather_quote_fanout_admission_issuer` from `economy_runtime.py`.
- `construction_production_runtime.py:54,78,83-84` imports and calls private `patch_runtime._canonical_digest`.

No additional second-truth instance outside the task's named review surfaces was conclusively established by this targeted scan.
