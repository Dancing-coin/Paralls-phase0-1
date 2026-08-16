# INF-2H Economy Account Settlement Spine Plan

Status: `implemented bounded and verified 2026-08-14`

1. [x] Name the existing economy owner, stream, event family, projection,
   privacy boundary and non-goals in the paired formal design.
2. [x] Add focused failing tests for the envelope/plan append path, authority
   outbox redaction, append-derived receipt, duplicate idempotency, stale
   revision and insufficient-funds zero writes, privacy, and replay.
3. [x] Replace only the `EconomyAuthorityService` raw account append helper
   with an owner-built `GameplayCommandEnvelope` plus `SettlementPlan` batch.
4. [x] Add an independent Harness profile/report with one assertion per listed
   capability; synchronize the INF-2 tree, root dependency records and August
   analysis with the bounded result.
5. [x] Run focused tests, dependent economy tests, Harness, docs check,
   `git diff --check`, checkpoint-tail replay, and full `python -m pytest -q`.

Do not extend this package to caller-open policy registration, generic payment,
or multi-domain settlement.  `EconomyAuthority` wage lifecycle remains a
separate principal and contract.
