# INF-1S Survival Fatigue Owner Row Design

Status: `implemented bounded and verified 2026-08-15`

INF-1S admits exactly one finite Survival-owned lifecycle row:
`effect:fatigue_exposure -> state:fatigued`. It is not a registration API and
does not make effects, states, owners, streams, or event families caller selectable.

| Concern | Contract |
| --- | --- |
| Owner | existing `SurvivalAuthority` / `actor_gameplay.survival_domain` |
| Stream | existing `gameplay:survival:{actor_ref}` only |
| Event family | existing Survival apply/open/expiry/settle/cancel/retry/compensate and closed dispel/recovery-transform events only |
| Definition | `refresh`, stack limit `1`, scheduled expiry, existing `state:recovering` transform target |
| Privacy | existing project-scoped Survival projection and `world.survival.scoped_projection` outbox only |
| Write path | semantic proposal -> existing Survival owner fragment -> `GameplayCommandEnvelope` -> one `GameplayEventStore.append_batch()` -> outbox/replay |
| Receipt/replay | existing append result and `ObligationSettlementCoordinator.replay` only |

The row must reject unregistered owner/stream/event combinations, stale revisions,
mismatched privacy, and changed idempotency keys before append. It does not authorize
arbitrary new Survival rows or any non-Survival owner.
