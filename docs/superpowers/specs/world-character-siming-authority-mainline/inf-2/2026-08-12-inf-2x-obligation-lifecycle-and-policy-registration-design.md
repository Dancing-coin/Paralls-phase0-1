# INF-2X Obligation Lifecycle And Policy Registration Design

Status: `implemented and verified for policy:construction_due_completion@1 only; broader lifecycle remains planned`

## Purpose and inherited baseline

INF-2X turns the existing caller-driven due selection into an event-derived,
owner-authorized obligation lifecycle. It inherits one `SimulationClock`,
`ScheduledObligation` model, `ObligationSettlementCoordinator`, activation
lock/pending changes, `SettlementReceipt`, `GameplayEventStore`, outbox and
replay. Existing tick, due sort, catch-up budget, closed filtering and rewind
rejection are foundations, not proof of retry/cancel/compensation semantics.

## Ownership and boundary

The clock selects due work only; it cannot decide an economic, body,
construction or ecology outcome. The coordinator assembles non-overlapping
`OwnerAuthorizedFragment`s only. `ConstructionProductionAuthority` is the sole
registered INF-2X row: `policy:construction_due_completion@1` on
`gameplay:construction_production:{facility_ref}`, with
`gameplay.construction_production.obligation_settled` and
`gameplay.construction_production.obligation_cancelled` correlation events.
Every added policy must name its owner, source view, event family, expected
revisions and privacy class in a registration table before code begins.
Survival, economy and ecology have no admitted INF-2X lifecycle row; ecology
recovery/retry remains blocked rather than becoming a coordinator responsibility.

The only write sequence is caller command -> pinned due selection -> owner
policy/fragment -> `SettlementPlan` when cross-domain -> `append_batch` ->
outbox/replay/scoped projection. No daemon, projector, client, LLM, Siming or
creator tool may advance time or settle an obligation.

## Model and lifecycle events

`ScheduledObligation` pins owner, policy ref/revision, due tick, source vector,
idempotency key, expected revisions, visibility, retry policy and compensation
policy. For the registered construction row, only `settled` and `cancelled`
are admitted lifecycle transitions, derived from owner-stream correlation
events containing obligation ID, prior/current state, policy revision, due tick
and attempt/reason. There is no second obligation database or receipt store;
receipts are append-derived. `scheduled`, `deferred`, `failed`, `compensated`
and retry transitions need separately named owner events and remain unsupported.

Retry must have a deterministic next-due policy, bounded attempts and a named
owner failure event. Cancellation requires a causal/authorization reason and
may affect only future work. Compensation requires an explicit named owner
compensation event and inverse semantics; where absent it remains rejected.

## Correctness, privacy, recovery and completion

Due work is monotonic, caller-budgeted and stable sorted. Lock conflict creates
a pending change at its pinned revision; release only proceeds through owner
validation. Missing registration, stale source/owner revision, expired
evidence, unauthorized policy/view, overlap, cancellation race, changed
idempotency reuse and retry exhaustion are structured zero-write outcomes.
Duplicate equal commands return the original filtered receipt. A changed request
that reuses the same idempotency key is rebuilt into the same append batch and
is zero-write rejected by its batch payload digest; the coordinator must not
blindly replay by key.

The same batch-plus-obligation digest rule applies to the existing registered
retry, cancellation, expiry and compensation operations. It binds the complete
`ScheduledObligation` input even if a particular owner event omits fields such
as `due_tick`; no terminal operation may treat key presence as sufficient.

Receipts and lifecycle projections use authority/owner/actor/public/creator
scopes; they never expose hidden subject evidence or grant control. Full and
checkpoint-tail replay reconstruct lifecycle state, lock/pending state, owner
heads and receipt digest without wall clock. Schema readers/upcasters are
versioned. Historic events are immutable; rollback uses future cancellation or
named compensation, never clock rewind.

## Harness and completion

`infra-obligation-lifecycle` independently proves construction-row settlement,
registration owner/stream and fragment-revision zero-write, missing correlation and forged
committed-obligation-identity zero-write,
retry/compensation rejection, cancellation/idempotency, cancellation revision
and terminal-state rejection, project-scope privacy, and full/checkpoint-tail
replay. Evidence: `.harness/verification/infra-obligation-lifecycle-report.json`.
Non-goals: universal domain policies, defer/release, retry/failure,
generic compensation, ecology policy without an ecology fragment, a second
scheduler/store, and P6/P7. Completion is only this registered owner policy,
not a universal lifecycle claim.
