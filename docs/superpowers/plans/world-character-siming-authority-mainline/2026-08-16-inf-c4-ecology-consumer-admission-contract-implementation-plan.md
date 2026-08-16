# INF-C4 Ecology Consumer Admission Contract Implementation Plan

Status: `implemented and independently verified as a finite read-only substrate`

1. [x] Add focused RED tests for two existing target owners and the closed
   source/owner/stream/scope/revision/idempotency contract.
2. [x] Implement a read-only check result over the existing event store and
   governed catalog with no append, registration, or fragment API.
3. [x] Reuse the check in existing Construction maintenance and Organization
   supply pre-fragment paths while retaining their domain admission and owner
   fragment builders.
4. [x] Add independent Harness checks for success, zero-write rejection,
   idempotency, revision, privacy, and full/checkpoint-tail replay.
5. [x] Synchronize the formal, August, audit, and Harness documentation.

No caller-open consumer registration, arbitrary target list, ecology-owned
target mutation, retry/compensation system, scheduler, second runtime/store,
or new truth owner is in scope.
