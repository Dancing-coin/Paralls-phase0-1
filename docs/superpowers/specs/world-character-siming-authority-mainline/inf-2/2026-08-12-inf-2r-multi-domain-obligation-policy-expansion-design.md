# INF-2R Multi-Domain Obligation Policy Expansion Design

Status: `implemented and verified for construction production due completion; ecology retry/compensation remain rejected`

Date: `2026-08-12`

## Purpose and ownership

INF-2R adds an explicit caller-driven obligation policy for construction
production completion. Ecology recovery/hazard follow-up is blocked because
`EcologyHazardAuthority` has no `OwnerAuthorizedFragment` builder. INF-2R reuses one
`SimulationClock`, `ScheduledObligation`, coordinator, event store, outbox,
and replay path. It does not create a background runner, global obligation
truth store, or generic owner that decides domain outcomes.

The first owner is `ConstructionProductionAuthority` in
`backend/app/gameplay/construction_production_runtime.py`. Its existing
`build_due_finish_fragment` targets
`gameplay:construction_production:{facility_ref}` and emits
`gameplay.construction_production.run_finished`. `SimulationClock.advance`
selects due work and `ObligationSettlementCoordinator.settle` assembles the
fragment only. Ecology must not enter the package until it exposes an
equivalent owner fragment builder.

## Models and events

An obligation carries owner, subject refs, policy ref/revision, due tick,
cadence, expected revision vector, retry and compensation policy, visibility,
activation lock reference, correlation/causal refs, and idempotency key.
Policies are deterministic functions of a pinned projection and command
envelope. The first lifecycle implementation commits production due/defer/
settle/cancel outcomes with common obligation correlation fields. Retry and
compensation are deferred until their owner event families are separately named.

`SettlementReceipt` remains append-derived and contains committed IDs, owner
stream revisions, accepted/deferred/rejected fragments, replayed idempotency
outcome, zero-write error, and redacted audit references. It is not persisted
as a second receipt database.

## Correctness and boundaries

Due selection is monotonic, explicit, sorted, and bounded by caller-supplied
catch-up budget. Read operations and background threads cannot advance time or
settle work. Domain policy may defer an obligation but cannot silently mutate
it. A lock holds interactive authority; due work becomes an owner-scoped
pending change and is released only at the pinned revision.

Missing policy, unauthorized fragment, revision mismatch, expired evidence,
lock conflict, retry exhaustion, overlapping writes, or cancellation race
causes structured zero-write rejection. Duplicate commands replay the original
scoped receipt. Public/actor/creator access is receipt and projection filtering
only; no view gains owner settlement rights.

## Replay, migration, and rollback

Replay orders obligations by committed events and fixed due selection, never by
wall clock. Full and checkpoint-tail replay must agree on obligation lifecycle,
owner projection, receipt digest, and pending-lock state. Policy schemas require
versioned readers/upcasters. Rollback cancels future work or emits owner
compensation events; it cannot rewind the shared clock or delete event history.

## Verified evidence

`ConstructionDueCompletionPolicy` is the sole INF-2R policy. It derives a
`ScheduledObligation` and calls the existing construction owner fragment
builder; `SimulationClock` remains caller-driven and
`ObligationSettlementCoordinator` remains an assembler. Non-empty retry and
compensation policies are explicitly rejected before fragment assembly with no
writes because no owner event family is registered for them.

`backend/tests/test_infra_multi_domain_obligation.py` proves success,
duplicate idempotency, revision conflict zero-write, cancellation zero-write,
retry/compensation zero-write, scoped receipt redaction, and full/checkpoint-
tail replay equivalence. The independent report is
`.harness/verification/infra-multi-domain-obligation-report.json`.

## Harness, non-goals, completion

`infra-multi-domain-obligation` independently checks the named construction
success, cancellation/revision/retry/compensation zero-write, duplicate,
privacy, full replay, and checkpoint-tail replay. Retry, compensation, and
ecology are blocked rather than implemented.

Non-goals: ecology recovery settlement, retry/compensation without owner event
maps, generic NPC scheduling, passive timer execution, universal economic
policy, a second coordinator, or P6/P7. Completion covers only the named
construction policy with independent evidence.
