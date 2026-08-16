# INF-4M Durable Isolated Branch Snapshot Design

Status: `implemented and verified; existing BranchPreviewAuthority and non-production stream only`

## Purpose

INF-4B/G prove deterministic in-memory branch analysis and checkpoint-tail
projection, but a fresh authority instance cannot rebuild that analysis buffer.
INF-4M records an explicitly requested, creator-debug snapshot of an already
accepted branch buffer on the existing `gameplay:branch_preview:{branch_ref}`
stream. It does not settle a domain fragment, create production truth, or
permit promotion.

## Existing-owner Contract

| Concern | Contract |
| --- | --- |
| Owner | existing `BranchPreviewAuthority` / `authority:branch_preview` |
| Stream | existing `gameplay:branch_preview:{branch_ref}` only |
| Event | `gameplay.branch_preview.isolated_snapshot_recorded` |
| Privacy | `creator_debug` only |
| Input | an in-memory buffer previously accepted by `preview()` in the same authority instance |
| Write path | `BranchPreviewAuthority -> GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch() -> creator-debug outbox` |
| Projection | replay the persisted redacted buffer through the existing branch reducer; full and checkpoint-tail results must match |
| Receipt | the ordinary append result only; no `SettlementReceipt`, domain receipt, or production receipt |

The payload carries only the existing redacted descriptor/candidate/disposition/
consequence/projection records plus their digest. It excludes owner-only grant,
reservation and evidence references. Exact duplicates replay through the store;
changed same-key payload, stale stream revision, missing local accepted buffer,
wrong stream, wrong privacy, malformed records and promotion are zero-write.

## Non-goals

This is not production-equivalent branch settlement, a generic branch event
family, a population/NPC/social truth store, a second runtime/store/clock, or
branch promotion. Organization and Government scenario settlement remain their
own existing-owner rows.

## Evidence

Focused tests and the `infra-durable-isolated-branch-snapshot` Harness prove
explicit append, fresh-instance reconstruction, idempotency, stale/privacy and
missing-buffer zero writes, redaction, and full/checkpoint-tail replay. The
report is `.harness/verification/infra-durable-isolated-branch-snapshot-report.json`.
