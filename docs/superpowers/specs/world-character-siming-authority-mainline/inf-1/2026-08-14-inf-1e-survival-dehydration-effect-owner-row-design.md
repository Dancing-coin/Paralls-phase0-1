# INF-1E Survival Dehydration Effect Owner Row Design

Status: `implemented and verified; generic owner matrix remains incomplete`

## Scope

INF-1E adds exactly one closed semantic-to-Survival state lifecycle row. It
does not generalize the effect/state matrix or create a new state, obligation,
scheduler, event-store, or semantic writer owner.

| Effect | State | Owner | Stream | State/obligation events | Expiry fragment | Scope |
| --- | --- | --- | --- | --- | --- | --- |
| `effect:dehydration_exposure` | `state:dehydrated@1` | `actor_gameplay.survival_domain` | `gameplay:survival:{actor_ref}` | existing `gameplay.survival.state_*` and `gameplay.survival.obligation_*` | `SurvivalAuthority.build_state_expiry_fragment` | project |

The semantic authority may only validate this complete registered pair and
construct a `GameplayCommandEnvelope` for the existing Survival authority.
`SurvivalAuthority.apply_effect_state()` remains the sole domain writer and
uses its existing `GameplayEventStore.append_batch()` path, scoped outbox, and
event-derived projection. The semantic evaluator remains proposal-only.

## Admission and rejection

The registry must accept the new scheduled lifecycle only when the state,
revision, owner, stream pattern, opened/settled/cancelled event types, fragment
builder and `project` scope exactly match the table. The bridge must also pin
the target actor, semantic snapshot digest and expected Survival stream
revision. Unpaired effect/state, another owner/stream, non-project privacy,
stale revision, changed idempotency payload and unregistered state all reject
before a new append.

The ordinary Survival state stack policy remains owner-evaluated: add,
replace, refresh and reject, stack limit, expiry, dispel and transform retain
the same existing event-derived implementation. This row does not claim that
those policies are generic across owners.

## Required proof

A dedicated focused suite and Harness profile must independently prove:

1. registered owner append with the state and open obligation events;
2. duplicate idempotency without a second append;
3. changed duplicate zero write;
4. stale revision zero write;
5. privacy zero write;
6. unmapped pair zero write;
7. due settlement and full/checkpoint-tail replay;
8. scoped outbox audience.

All other state/effect owner rows remain blocked unless a separate formal
contract names their existing authority, stream, event family, reader scope,
revision/idempotency behavior, replay reader and zero-write rejection.

Evidence: `.harness/verification/infra-survival-dehydration-state-obligation-report.json`.
