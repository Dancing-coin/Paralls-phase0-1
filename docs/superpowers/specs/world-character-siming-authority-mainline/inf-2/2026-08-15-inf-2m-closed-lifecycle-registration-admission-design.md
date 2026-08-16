# INF-2M Closed Lifecycle Registration Admission

Status: `verified input-admission fence; owner-only write-spine closure remains open`

Date: `2026-08-15`

## Problem

`ObligationSettlementCoordinator` currently accepts caller-supplied lifecycle
registrations and, when an obligation has no `policy:*` source, can append a
caller-supplied `OwnerAuthorizedFragment`. That is a generic writer surface,
not a permitted owner-bound settlement path.

## Decision

INF-2M introduces an immutable registration reader for existing owner rows
only. It recognizes the already implemented Construction due-completion and
maintenance rows, Survival state expiry, Ecology frost crop-state expiry,
Economy wage accrual, and Economy scheduled account transfer.

The coordinator accepts an input registration only when it is an exact or
strictly less-capable view of one of those owner contracts. It derives policy
identity from the obligation's `policy:*` source and rejects missing, unknown,
forged, or widened registrations before `append_batch()`. Each closed contract
also carries the owner-local event family permitted for its lifecycle. A
fragment that contains a valid terminal event plus any unregistered event is
rejected before append; the semantic Construction dispel registration remains
an explicit opt-in capability. Every fragment event must also use the exact
visibility scope registered for that owner policy; omitted policy vectors use
the event-plan default `project` scope and therefore cannot satisfy an
`authority_only` lifecycle row.

Where a canonical policy declares a committed-open requirement, a caller cannot
weaken it through a less-capable registration view. In particular, Construction
due-completion requires the existing owner-authored `run_started` event whose
`due_obligation_id`, policy ref/revision, and due tick match the settlement.
The coordinator therefore rejects a shaped completion fragment before append
when that source event is absent.

## Boundary And Remaining Gap

This is an admission fence, not caller-open policy registration. Existing
owners build the fragments, but the current coordinator still calls
`GameplayEventStore.append_batch()` after receiving them. Therefore the
implementation has not yet satisfied the stricter owner-only write path:

`owner -> GameplayCommandEnvelope / SettlementPlan -> GameplayEventStore.append_batch() -> outbox/replay -> scoped projection`.

No policy is added and no generic fragment, payment, cross-domain business
outcome, runtime, scheduler, or receipt store is introduced. The coordinator
append capability is nevertheless a remaining generic writer surface. INF-2Q
must retire it by moving every committed lifecycle operation behind the
relevant existing authority's `GameplayCommandEnvelope -> SettlementPlan ->
append_batch()` method while retaining the coordinator only as a read-only
lifecycle/replay/receipt reader.

## Evidence

The package must prove closed contract shape, unknown-policy zero-write,
forged/widened registration zero-write, smuggled-event zero-write,
visibility-vector override zero-write, each admitted owner family's existing
replay/receipt behavior, committed-open zero-write where required, and
compatibility for permitted registrations. Each Harness capability uses its own
focused test selector.

The package report records thirteen independent passing selectors in
`.harness/verification/infra-closed-lifecycle-registration-admission-report.json`.
