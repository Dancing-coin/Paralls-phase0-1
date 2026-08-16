# INF-C5 (INF-4) Deterministic Fixed-Base Branch Replay Contract

Status: `implemented and independently verified`

## Purpose

INF-C5 makes the existing isolated branch replay boundary explicit without
creating another branch writer, runtime, event store, or promotion authority.
The contract canonicalizes the fixed base, calibration/source digests,
deterministic family/candidate input ordering and replay projection digest.
`BranchPreviewAuthority` remains the only isolated branch authority. Production
promotion remains an existing owner operation and is admitted only for the
already registered Organization supply row.

## Fixed Contract

| Field | Value |
| --- | --- |
| contract | `FixedBaseBranchReplayContract` |
| branch owner | existing `BranchPreviewAuthority` / `authority:branch_preview` |
| isolated stream | `gameplay:branch_preview:{branch_ref}` |
| base pin | `base_event_digest`, `base_checkpoint_sequence`, `tail_boundary` |
| source pin | calibration digest, dataset/source digest map, family and candidate digests |
| ordering | canonical sorted source/family/candidate digest tuples |
| projection | isolated branch projection digest, recomputed for full and checkpoint-tail replay |
| privacy | `creator_debug` for isolated branch evidence; existing production owner scope remains `project` |
| fixed promotion consumer | existing `OrganizationAuthority.promote_branch_supply` only |
| write path | existing authority -> `GameplayCommandEnvelope` / `SettlementPlan` -> one `GameplayEventStore.append_batch()` -> outbox/replay -> scoped projection |

## Admission

The pure contract rejects a mismatched branch stream, privacy scope, base,
calibration or source digest before an isolated snapshot or owner fragment is
accepted. Candidate and family inputs are canonicalized before the planner
input digest is formed. Durable replay validates the contract embedded in the
redacted branch descriptor and recomputes one projection digest for both full
and checkpoint-tail replay.

The existing Organization supply admission carries the same contract and its
digest. `OrganizationAuthority` revalidates that fixed contract before it can
construct the existing production fragment. Unknown promotion remains
`branch_promotion_unsupported` and zero-write; no generic branch promotion is
introduced.

## Non-goals

This contract does not append events, select owners, register policies, create
population/NPC/social truth, promote arbitrary branches, or implement complete
group simulation. It does not change the existing branch scenario or
production owner receipts. Existing branch evolution may extend the final
projection; the fixed contract remains the immutable replay-input/base pin and
the reader computes the resulting projection digest.

## Verification

Independent focused assertions are in
`backend/tests/test_infra_fixed_base_branch_replay_contract.py`, with one
selector per capability. The independent Harness profile is
`infra-fixed-base-branch-replay-contract` and its report is
`.harness/verification/infra-fixed-base-branch-replay-contract-report.json`.
The report covers canonical ordering, wrong base/calibration zero-write,
cross-branch stream rejection, full/checkpoint-tail digest equality, the fixed
Organization admission, and unsupported promotion zero-write.
