# INF-3L Weather-Front Owner-Contract Matrix Plan

Status: `implemented and independently verified; finite existing-owner matrix`

1. [x] Re-run the existing Ecology weather-front Construction, Organization and
   Economy focused tests and inspect owner/stream/event/projection/receipt
   mappings.
2. [x] Add separate RED tests for Construction and Economy pre-append catalog
   mismatches, each proving zero writes.
3. [x] Add the two immutable catalog rows. Keep the existing Organization row
   unchanged and do not add mutation or registration methods.
4. [x] Make Construction one-facility/two-facility maintenance and Economy
   weather quote settlement consume only their respective row before batch
   construction.
5. [x] Add an independent Harness profile with one selector per matrix row,
   two distinct pre-append zero-write selectors, revision/idempotency/privacy
   selectors, and checkpoint-tail replay.
6. [x] Synchronize INF-3 indexes, August analysis, main audit and Harness
   documentation; run focused, predecessor, full replay and root tests.

## Stop Condition

Any new consumer remains unsupported-input zero-write until it has its own
existing target owner, event family, stream, scoped projection, revision,
idempotency, append-derived receipt and replay reader. No catalog row is a
fallback authority.
