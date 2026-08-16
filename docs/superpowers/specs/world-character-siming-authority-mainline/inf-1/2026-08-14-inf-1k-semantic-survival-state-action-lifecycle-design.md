# INF-1K Semantic Survival State Action Lifecycle

Status: `implemented and verified; closed Survival-only rows`

## Scope

INF-1K closes the remaining state-action segment for the already admitted
Survival lifecycle only. A semantic proposal may select an event-derived,
still-open Survival state-expiry obligation and request exactly one of these
owner-authorized actions:

| Action effect | Source state | Existing owner | Stream | Domain events | Result |
| --- | --- | --- | --- | --- | --- |
| `effect:state_dispel` | `state:cold`, `state:overheated`, `state:dehydrated` | `SurvivalAuthority` | `gameplay:survival:{actor_ref}` | `state_dispelled`, `obligation_cancelled` | removes the admitted source state |
| `effect:state_transform_recovery` | `state:cold`, `state:overheated`, `state:dehydrated` | `SurvivalAuthority` | `gameplay:survival:{actor_ref}` | `state_dispelled`, `state_transformed`, `obligation_cancelled` | replaces the source with the fixed `state:recovering` remedy state |

The recovery replacement is closed as
`state:recovering` / `effect:remedy` / one stack / magnitude `50`. Callers
cannot select the replacement state, effect, stack count or magnitude.

## Boundary

`SemanticSettlementAuthority` reads the existing project-scoped Survival
projection to locate a new matching open obligation. For an idempotency replay,
it reconstructs the same candidate from the committed `obligation_opened`
evidence instead of treating current projection state as fresh authority. It
then asks `SurvivalAuthority` for its existing dispel or transform fragment.
The existing `ObligationSettlementCoordinator` validates the registered
`policy:survival_state_expiry@1` lifecycle and sends that owner fragment
through the sole event-store append path. No semantic stream, obligation,
scheduler, clock, projection owner, or cross-domain action is introduced.

The proposal must pin `authority:semantic`, `project` scope,
`{"semantic": 1}`, the target snapshot digest, exact Survival owner/stream,
and the current stream revision. Missing/open-mismatched state evidence,
unsupported action/state, private scope, stale revision, stale source vector,
altered duplicate, and malformed reason are zero-write.

## Evidence

Focused tests and the dedicated Harness profile separately prove successful
dispel and transform, every rejection boundary, duplicate idempotency,
revision conflict, project-only outbox scope, and full/checkpoint-tail replay.
This is an owner-local lifecycle closure. It does not admit arbitrary remedy
states, general state actions, generic semantic owner dispatch, or a second
runtime/store.

Fresh evidence: `.harness/verification/infra-semantic-survival-state-action-report.json`
records fifteen independent assertions, including exact replay and changed
snapshot idempotency zero-write rejection. The complete semantic owner matrix
remains blocked under INF-1I.
