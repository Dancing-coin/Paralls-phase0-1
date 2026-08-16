# INF-4E Branch-Domain Consequence Blocker

Status: `partially superseded by INF-4F/INF-4G isolated evaluation and projection; branch-domain settlement/receipt and production zero-write boundary remain blocked`

Date: `2026-08-14`

## Evidence

`BranchPreviewAuthority` now stores an isolated owner-fragment evaluation
record for the two closed `supply`/`inspection` mappings and, after an accepted
evaluation, an isolated redacted planned commitment/inspection projection. It
invokes the existing fragment-builder validation only and records a digest or
rejection; it has no settlement API, production-equivalent branch receipt, or
promotion. The authority intentionally does not call
`GameplayEventStore.append_batch()` and `promote()` returns
`branch_promotion_unsupported`.

Current evidence:

- `.harness/verification/infra-isolated-branch-evolution-report.json`
- `.harness/verification/infra-isolated-branch-owner-disposition-report.json`
- `.harness/verification/infra-isolated-branch-owner-fragment-evaluation-report.json`
- `.harness/verification/infra-isolated-branch-owner-consequence-projection-report.json`
- `.harness/verification/infra-population-world-mode-complete-report.json`
- `backend/app/population_continuity/branch_preview.py`

## Missing contract

A legitimate branch-domain consequence requires, before implementation:

1. one existing target domain owner and an exact owner-authorized fragment
   contract for the selected branch candidate;
2. a declared branch-local settlement record/event family and receipt boundary
   that cannot be mistaken for production canonical events or receipts;
3. source revision/vector, policy, privacy and idempotency rules for that
   branch-local consequence;
4. a defined relation between a target owner's production fragment semantics
   and its non-production branch evaluation, without invoking the target
   production writer or creating a second event store/runtime;
5. separate zero-production-write, full/checkpoint-tail branch replay, privacy,
   stale source and unsupported-promotion evidence.

INF-4G supersedes this record's former missing evaluation/reducer condition for
two fixed projected semantics. It still does not execute a fragment or define a
branch-domain receipt. Reusing production `OrganizationAuthority` or
`GovernmentAuthority` fragments directly for settlement would mutate production
truth or require an unapproved second store/authority surface.

## Admission decision

The former missing owner-validation mapping is resolved for two fragment
evaluations, and the former missing redacted local projection is resolved by
INF-4G. Production-equivalent branch settlement remains blocked: the current
safe behavior is isolated replayable analysis/projection and production zero-write.
`branch_promotion_unsupported` remains required. This does not block the
already verified INF-4C activation-pending schedule merge, but it prevents
claiming production-equivalent branch scenario evolution or complete population
simulation.

## Next action

An explicit owner-bound branch settlement/receipt contract must be approved in
a new formal design before a focused failing test or code is added. No SOC-1,
GAME-1, P6 or P7 work follows from this record.
