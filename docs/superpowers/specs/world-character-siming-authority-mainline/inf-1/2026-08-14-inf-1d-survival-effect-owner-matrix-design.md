# INF-1D Survival Effect Owner Matrix Design

Status: `implemented and verified for the two named Survival matrix rows; cross-owner coverage remains incomplete`

Date: `2026-08-14`

## Scope

INF-1D expands the existing Survival owner mapping matrix by exactly one new
closed row. It does not make state lifecycle generic across owners.

| Effect | State | Owner | Stream | State/obligation events | Expiry fragment | Scope |
| --- | --- | --- | --- | --- | --- | --- |
| `effect:cold_exposure` | `state:cold@1` | `actor_gameplay.survival_domain` | `gameplay:survival:{actor_ref}` | existing `gameplay.survival.state_*` and `gameplay.survival.obligation_*` families | `SurvivalAuthority.build_state_expiry_fragment` | project |
| `effect:heat_exposure` | `state:overheated@1` | `actor_gameplay.survival_domain` | `gameplay:survival:{actor_ref}` | same existing Survival family | same existing fragment | project |

Both rows are explicit constants in the closed semantic registry. The semantic
authority only translates a proposal matching one complete row into the
existing Survival `GameplayCommandEnvelope`; it does not select a caller
stream, owner, event type, policy or fragment. Survival remains the sole writer
and opens the existing event-derived `ScheduledObligation`.

## Validation and non-goals

The state lifecycle registration requires its exact state, revision, owner,
stream pattern, event family, fragment builder and project scope. The bridge
requires its exact registered effect/state pair, matching target actor and
semantic snapshot, scheduled expiry and project scope. Any mismatched pair,
other owner, private scope or stale revision is zero-write.

This package does not approve arbitrary state definitions, ecology/economy/body
owner rows, periodic damage, generic rules, a new policy, a new scheduler, or a
new state truth store.

## Verification record

The focused suite and `infra-survival-heat-state-obligation` Harness profile
passed on `2026-08-14`. Evidence is at
`.harness/verification/infra-survival-heat-state-obligation-report.json`.
