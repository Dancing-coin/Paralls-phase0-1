# F2 Harness Replay Privacy And Zero-Write Gates

Status: `implemented-and-verified; complete profile fresh-green`

## Objective

Give all future creator and research tracks one proof vocabulary. F2 separates
committed gameplay truth, preview proposals, branch/counterfactual reports,
and read-only research annotations.

## Required proof bundle

Every executable track must name a focused test set, Harness profile/rule IDs,
full and checkpoint-tail replay equivalence, deterministic projection hashes,
privacy filtering, permission-denial parity, rejected-intent zero-write proof,
stale/duplicate idempotency, migration/rollback evidence, and audit evidence.
Research tracks additionally require read-only enforcement, proposal/result
separation, reproducibility metadata, and no world-truth commit path.

## Work packages

1. profile and rule taxonomy for foundation, P6 and P7;
2. replay sets and deterministic hash requirements;
3. privacy, denial, zero-write and idempotency assertions;
4. migration/rollback and audit retention assertions;
5. blocked/planned reporting and evidence freshness rules.

## Dependencies and successors

F2 consumes F0-F1 contract names. It gates P6C/P6D and the DG opening checklist;
P7A-D add read-only, branch-replay, world-model and robotics-specific profiles
after P6D. No profile may claim a broader product than its assertions prove.

## Non-goals and stop conditions

F2 does not claim full-repository green status, durable production transport,
complete world simulation, or robot safety outside a tested slice. Missing
profile, stale evidence, failed replay, privacy leak, or a non-zero rejected
write keeps the corresponding track `planned` or `blocked`.
