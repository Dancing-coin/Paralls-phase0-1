# F2 Harness Replay Privacy And Zero-Write Gates Plan

Status: `completed; complete profile fresh-green`

## Work packages

1. Define profile/rule IDs for F0-F2, P6 and P7 without claiming those tracks
   are implemented.
2. Define replay sets, full/checkpoint-tail equivalence, deterministic hashes,
   schema/revision inputs, and evidence freshness.
3. Define privacy filtering, permission denial, rejected zero-write,
   stale/duplicate idempotency and audit assertions.
4. Define migration/rollback proof and research-only proposal/result separation.
5. Add the approved taxonomy to `docs/harness.md` and run docs/boundaries
   checks; do not fabricate generated reports.

## Verification plan

Every future executable track receives a checklist with focused tests, Harness
profile, replay, privacy, denial, zero-write, migration, rollback and audit
owners. P7 adds branch reproducibility and robotics safety assertions.

## Done/blocked

Done means the taxonomy is documented and each downstream track has an evidence
owner. Missing profile, failed replay, privacy leak, stale report or non-zero
rejected write keeps the track planned or blocked.
