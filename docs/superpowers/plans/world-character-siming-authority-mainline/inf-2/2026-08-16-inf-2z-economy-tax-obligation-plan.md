# INF-2Z Economy Tax Obligation Plan

Status: `implemented and independently verified as one fixed Economy owner row; broader INF-2 remains incomplete`

1. [x] Add RED tests for owner-local tax open/settle/cancel/expire, source,
   revision, idempotency, privacy, zero-write and replay behavior.
2. [x] Extend the existing Economy owner/projection and closed lifecycle
   registry with the one fixed tax policy and formal owner append path.
3. [x] Add independent Harness assertions, report evidence, sync formal/plan/
   August status records, and run full/checkpoint-tail replay plus full tests.

The package must not record payment, debit/credit an account, create a new
policy writer, or widen to cross-domain settlement.
