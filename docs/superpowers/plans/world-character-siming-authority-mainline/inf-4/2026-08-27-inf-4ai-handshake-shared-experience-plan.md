# INF-4AI Handshake Shared-Experience Implementation Plan

Status: `implemented and verified narrow vertical; generic social/session expansion remains blocked`

1. Add focused RED tests for exact committed two-party handshake admission,
   source/private/stale/changed-duplicate zero-write, append-derived receipt,
   and full/checkpoint-tail replay. The tests must prove the method is absent
   before implementation.
2. Add the one immutable Social owner descriptor and governed catalog row.
   The catalog must remain read-only and must not register a generic social
   operation.
3. Add a single row-specific `SocialFactAuthority` method and view. It rereads
   the full committed session vector, derives both participant target streams
   and idempotency, then writes the fixed two-event same-owner vector through
   `GameplayCommandEnvelope -> SettlementPlan -> append_batch()`.
4. Add an independent Harness that runs exact success, zero-write/privacy/
   duplicate, and full/checkpoint-tail replay checks.
5. Run the focused tests, Harness, catalog regression, INF-focused suite,
   continuation gate, docs Harness, `compileall`, and `git diff --check`.
   Update the conflict matrix, audit, remaining-scope, README, taxonomy, and
   checkpoint without marking August INF A-D complete.

Implementation evidence: `8 passed` in the dedicated INF-4AI suite,
`31 passed` including P5 Social and governed-catalog regressions, and a green
independent `inf4ai-p5-actor-private-expression` Harness. The event/schema,
catalog, owner adapter, privacy, idempotency, receipt, zero-write, and
full/checkpoint-tail replay boundaries are closed only for this exact
handshake row.
