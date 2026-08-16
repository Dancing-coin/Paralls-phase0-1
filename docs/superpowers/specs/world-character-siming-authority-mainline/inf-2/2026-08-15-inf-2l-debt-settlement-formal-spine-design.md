# INF-2L Debt Settlement Formal Spine Design

Status: `implemented bounded and verified 2026-08-16; owner-local replay reader closure backfilled`

`DebtAuthorityService` is the existing authority for the fixed simple-debt
transaction lifecycle. Its legacy adapter creates raw event dictionaries and
appends them directly. INF-2L replaces only that adapter with a typed,
owner-bound formal write path; it does not create a payment runtime or a
generic cross-domain writer.

| Concern | Contract |
| --- | --- |
| Sole settlement authority | existing `DebtAuthorityService` / `actor_gameplay.debt_domain` |
| Input | existing validated simple-debt issue, payment, cancellation, correction, reopening, overdue/default methods only |
| Streams | existing `gameplay:economy`, `gameplay:contracts`, `gameplay:debt`, `gameplay:commerce` |
| Event family | existing `account_debited`/`account_credited`, simple-debt contract, debt claim and debt-commerce settlement events only |
| Write path | `DebtAuthorityService` -> `GameplayCommandEnvelope` -> `DebtSettlementPlan` -> owner-authorized fragments -> one `GameplayEventStore.append_batch()` -> authority-scoped redacted outbox -> existing Economy/Debt projections |
| Revisions | exact current four-stream vector is both expected and read/pinned before append |
| Privacy | canonical entries remain `authority_only`; outbox is authority-scoped and redacts accounts, amounts, parties and reasons |
| Receipt | the sole `AppendBatchResult`; no receipt stream or coordinator |
| Replay reader | `DebtAuthorityService.replay_projection` delegates to the existing `GameplayProjectionReplay` over the canonical store; full/checkpoint-tail hashes must match |

`DebtSettlementPlan` is a local, closed adapter for this exact authority and
event family. It cannot accept caller-selected stream IDs or event types. Its
fragments are proof of the already existing Debt settlement owner's selected
rows, not a new owner for arbitrary Economy, Contract or Commerce facts.

Focused tests must prove issue and repayment use Envelope/plan/fragments and
one batch, duplicate replay, changed idempotency zero write, revision conflict
zero write, redaction/privacy, full/checkpoint-tail replay and legacy output
compatibility. All non-simple-debt policy/payment registration and arbitrary
cross-domain settlement remain blocked.

Verification is recorded by `infra-debt-settlement-formal-spine`: ten
separate Harness selectors prove issue and repayment formal fragments/redacted
outboxes, legacy event compatibility, exact duplicate zero-write,
changed-idempotency zero-write, stale-revision zero-write, closed event/type-to-
stream admission zero-write, and full/checkpoint-tail replay. This bounded
migration does not change the remaining open-policy or generic-settlement
completion condition.
