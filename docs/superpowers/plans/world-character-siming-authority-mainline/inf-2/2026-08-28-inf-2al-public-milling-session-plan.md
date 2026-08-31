# INF-2AL Public Milling Session Implementation Plan

Status: `implemented narrow vertical; generic service/payment remains blocked`

1. [x] Form one disjoint source tuple from INF-1AL's exact
   `mill_reinforced` public-use event.
2. [x] Freeze and adapter-validate immutable package v6 declaration/content
   digests; preserve v1-v5 package revisions.
3. [x] Add row-specific Contract terms, admission and fulfillment methods,
   descriptors and immutable catalog contracts.
4. [x] Route the exact fulfilled service through the existing Economy
   package-exchange handler with fixed 8 `currency:local` price and v6
   idempotency fence.
5. [x] Add RED-to-green focused tests and independent Harness for source,
   consent, account, price, privacy, revision, idempotency, receipt,
   zero-write and full/checkpoint-tail replay.
6. [x] Synchronize INF-2 register, audit, remaining-scope, conflict matrix,
   README, blocker taxonomy and continuation checkpoint; run all regressions.

This plan admits one named milling service exchange only. Generic service,
payment, transfer, market pricing, compensation or settlement remains blocked.
