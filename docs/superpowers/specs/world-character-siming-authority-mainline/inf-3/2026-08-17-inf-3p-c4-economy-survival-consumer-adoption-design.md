# INF-3P C4 Economy and Survival Consumer Adoption

Status: `implemented and independently verified`

## Purpose

Adopt the already verified `INF-C4 (INF-3)` read-only
`EcologyConsumerAdmissionCheck` in the remaining pre-registered weather-front
consumer owners: Economy quote / quote fanout and Survival cold / heat. This
is an integration of closed contracts, not a new C4 substrate package.

## Exact Contracts

| Consumer | Existing owner | Stream | Existing event family | Scope |
| --- | --- | --- | --- | --- |
| Economy quote | `actor_gameplay.economy_domain` | `gameplay:economy` | `gameplay.economy.dynamic_quote_published` | project |
| Economy quote fanout | `actor_gameplay.economy_domain` | `gameplay:economy` | `gameplay.economy.dynamic_quote_published` | project |
| Survival cold | `actor_gameplay.survival_domain` | `gameplay:survival:{profile_ref}` | `state_applied`, `obligation_opened` | project |
| Survival heat | `actor_gameplay.survival_domain` | `gameplay:survival:{profile_ref}` | `state_applied`, `obligation_opened` | project |

For every row the existing opaque Ecology admission remains required. C4 only
checks the already committed source pin, existing owner/stream/event/scope,
target revision, idempotency key, receipt reader and replay reader. The target
owner then builds its own fragment and sends its own command/plan to the one
`GameplayEventStore.append_batch()` path.

## Rejection Boundary

Unknown contract, forged or private source, target revision mismatch, wrong
owner/stream/scope, or a rejected C4 result must return the existing owner
error and produce zero writes. C4 cannot mint admission, choose a consumer,
build a fragment, append events, or register any row.

## Non-goals

No generic consumer registry, generic fanout, ecology-to-target write access,
retry/compensation policy, scheduler, runtime/store/bus, population/NPC/social
truth owner, or production branch promotion is introduced.
