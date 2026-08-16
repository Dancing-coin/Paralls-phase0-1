# INF-3I Weather-Front Organization Supply Edge Plan

Status: `completed and verified 2026-08-15`

1. [x] Bind one existing Ecology source, Organization owner, Organization stream,
   existing commitment event, projection, revision and receipt contract in the
   formal design.
2. [x] Add focused RED tests for source admission, owner settlement, idempotency,
   revision, privacy, zero-write and replay.
3. [x] Add sealed source admission and an Organization-owner settlement method
   that reuses `build_commerce_commitment_fragment` and one append batch.
4. [x] Add an independent Harness profile/report and update INF-3/root/August
   status documents.
5. [x] Run focused/predecessor tests, Harness, docs, diff and full pytest.

Stop if the edge requires a new target event family, a direct Ecology write, a
generic consumer selector, payment truth, or a second receipt/store.
