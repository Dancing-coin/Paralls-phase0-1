# INF-1A Survival State Obligation Lifecycle Design

Status: `implemented and verified for one Survival-owned scheduled state-expiry row; INF-1 generic lifecycle remains incomplete`

## Scope

This is the first real durable INF-1 owner row. It does not create a semantic
state truth store: the existing `SurvivalAuthority` remains the sole owner of
survival state. The semantic evaluator stays pure and may only propose a typed
state application.

| Concern | Contract |
| --- | --- |
| Owner | existing `actor_gameplay.survival_domain` / `SurvivalAuthority` |
| Stream | existing `gameplay:survival:{actor_ref}` |
| State events | `gameplay.survival.state_applied`, `.state_dispelled`, `.state_transformed`, `.state_expired` |
| Obligation events | `gameplay.survival.obligation_opened`, `.obligation_settled`, `.obligation_cancelled` |
| Write spine | owner -> `GameplayCommandEnvelope` / `SettlementPlan` -> owner fragment -> existing `GameplayEventStore.append_batch()` -> outbox/replay -> scoped projection |
| Reader | event-derived survival state/obligation view with stream revision vector |
| Privacy | project-scoped state projection; public receipt redacts causal/evidence detail |

`StateDefinition` is admitted only with closed `add`, `replace`, `refresh` or
`reject` semantics and a fixed stack limit. `scheduled` expiry opens one typed
`ScheduledObligation`; only the existing single `SimulationClock` may select it
as due, and the existing `ObligationSettlementCoordinator` may append the
Survival owner fragment. No projector, clock read, client, LLM, Siming, creator
or semantic evaluator may expire state directly.

Dispel and transform are explicit Survival owner commands. They cancel the
committed matching obligation through the same owner stream; unknown, stale,
private, forged, terminal or policy-mismatched requests are zero-write. This
package proves one Survival row only. The closed semantic matrix admits
`state:cold@1` only with this owner, stream, event family and fragment builder;
all other scheduled state rows remain rejected. It does not make generic effect
ownership, periodic damage, ecology effects, retry or compensation complete.

## Completion conditions

Focused tests and the dedicated `infra-survival-state-obligation` Harness profile
independently prove apply,
all four stack policies, obligation-open/due/settled/cancelled/expired state,
dispel/transform, duplicate idempotency, revision conflict, privacy, replay and
zero-write rejection. The following INF-2 package will generalize lifecycle
registration, retry/compensation and a second owner; it must not be inferred
from this Survival row.
