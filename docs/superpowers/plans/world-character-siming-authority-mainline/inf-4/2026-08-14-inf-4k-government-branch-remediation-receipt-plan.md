# INF-4K Government Branch Remediation Receipt Plan

Status: `implemented and verified for one derived non-production remediation receipt row only`

1. [x] Complete INF-4L's durable accepted-preview evidence and Government-side
   revalidation before treating any remediation event as receipt-eligible.
2. [x] Re-run INF-4J predecessor Harness and inspect the source append,
   privacy, revision and replay evidence.
3. [x] Add focused RED tests for receipt creation/reconstruction, duplicate,
   zero-write failures, durable replay, outbox scope and production isolation.
4. [x] Extend only `GovernmentAuthority` with an append-derived immutable
   branch receipt and durable scenario projection reader. Do not add an event,
   store, coordinator or production receipt.
5. [x] Add a dedicated Harness with one selector per receipt capability and
   synchronize the INF-4 trees, root dependency record, August status and
   `docs/harness.md`.
6. [x] Run focused tests, INF-4J predecessor evidence, full/checkpoint-tail
   replay, docs gate, `git diff --check` and `python -m pytest -q`.
