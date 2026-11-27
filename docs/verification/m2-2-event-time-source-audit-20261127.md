# M2-2 migrated-domain event-time source audit

- Snapshot: A branch after `b42a1c2420f7c808944243120ec50a27663e9ac6`.
- Method: static `rg` inventory of every `event_time` occurrence under `backend/app`, followed by tracing the source-to-derived-event call paths. No tests ran.
- Scope is the current A-side migrated and M6-5 domains. This is not proof that all future Owner domains have an event-time producer.

## Findings

| Path | Source and propagation | Classification |
|---|---|---|
| Information report | `InformationAuthority.publish_siege_report` receives the session world tick, writes `published_at_world_tick` in the report payload, and persists the same tick as `GameplayEvent.event_time`. The post-delivery knowledge event receives the publication time. | Authoritative for newly published reports when the configured world clock is available. Legacy records without time remain unknown. |
| Signed siege physical input | `M6_5SiegeRuntime._event_time_for_input` reuses an existing input event's time on retry; otherwise it queries the session world clock. `SiegePhysicalInputAuthority` persists it with the signed input. | Authoritative for new inputs with a configured clock. Exact retry reuses persisted time. Legacy inputs remain unknown. |
| Facility integrity and layered durability | Signed impact handlers copy the committed physical-input event time to derived Pool events. | Derived time, preserving the physical input's occurrence time. Generic `apply_delta` still accepts an optional time from its trusted caller. |
| Presence / Place | Signed assessment commits copy the persisted physical-input time to Place events. | Derived time, preserving the signed input's occurrence time. Older input events without time remain unknown. |
| Morale | `MoraleRefoldAuthority` forwards the committed casualty event's `event_time` to the Pool adjustment. | Derived time only when the casualty event has known time. Missing historical time stays unknown. |
| Ownership and Credential | No `GameplayEvent.event_time` producer was found in these runtimes. Bond and Credential `world_tick` fields support term/expiry checks. | Do not treat `world_tick` as occurrence time or infer `known_time` from it. |
| Other gameplay modules | The complete `backend/app/gameplay` search returned no other `event_time` uses. `embodied_interaction_session_service.py` has a separate payload field named `known_time`, not persisted `GameplayEvent.event_time`. | Outside the migrated-domain event-time producer set audited here. |

## Evidence and limits

- Search commands: `rg -l event_time backend/app -g '*.py'` and `rg -n event_time backend/app/gameplay -g '*.py'`, followed by direct inspection of `information_runtime.py`, `m6_5_siege_runtime.py`, `siege_physical_input_runtime.py`, `facility_integrity_runtime.py`, `facility_gate_layered_runtime.py`, `place_passability_runtime.py`, `morale_refold_runtime.py`, `ownership_runtime.py`, and `credential_runtime.py`.
- Python 3.12.2 and the A-worktree `app.__file__` had been verified for the adjacent code increment. This static audit did not run Python or tests.
- This inventory does not create timestamps for historical events and does not establish subject-specific `known_time`. No fallback to global sequence, stream revision, Bond expiry ticks, or arbitrary caller input is justified by this evidence.
- M2-2 remains blocked on trusted principal qualification and selector evaluation, runtime FactType/visibility enforcement, classification of any newly migrated read path, and the subject-facing `read_as` entry point. U7 is not complete.
