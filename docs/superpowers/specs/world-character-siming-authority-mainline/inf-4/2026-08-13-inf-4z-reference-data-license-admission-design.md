# INF-4Z Reference-Data License Admission Design

Status: `implemented and verified for the documented reference-data admission vertical`

Date: `2026-08-13`

## Authorization and scope

The user has authorized completion work for the remaining INF infrastructure.
This amendment admits one narrow owner on the existing `GameplayEventStore`:
`ReferenceDataAuthority`. It owns only reference-dataset license and usage
metadata. It does not own calibration outcomes, population truth, branches,
social truth, civilization progression, P6, or P7.

## Canonical contract

| Field | Contract |
| --- | --- |
| Owner | `authority:reference_data` |
| Stream | `gameplay:reference_data:{dataset_ref}` |
| Events | `gameplay.reference_data.dataset_registered`, `.dataset_corrected`, `.dataset_revoked` |
| Write path | authority -> `GameplayCommandEnvelope` -> owner fragment / `SettlementPlan` -> `GameplayEventStore.append_batch()` -> outbox/replay -> scoped projection |
| Read projection | event-derived `ReferenceDatasetView`, frozen with source event refs, stream vector, revision and digest |
| Consumer | `BranchPreviewAuthority.preview_authorized()` only, as a read-only calibration admission gate |
| Privacy | authority view holds license/provenance; preview receives only frozen allowed-scope/digest contract and must not expose license data in its public report |

`ReferenceDataset.license_ref` remains legacy caller metadata and is never
authoritative. The new authoritative path accepts only
`FrozenReferenceDatasetInput` made from a current authority-scoped view.

## Lifecycle and rejection

The owner may register, correct, or revoke a dataset. All transitions append
events to the single owner stream. Unknown datasets, owner mismatch, changed
idempotency reuse, stale expected revision, forged projection digest/event
refs/vector, revoked dataset, non-authority read, dataset/calibration mismatch,
and preview scope denial reject without a production write. There is no delete,
branch promotion, or external ingestion writer.

## Completion conditions

The package completes only when focused tests and a dedicated Harness profile
independently prove canonical append/outbox, zero-write rejections, duplicate
idempotency, correction/revocation, authority/preview privacy, authoritative
branch admission, and full/checkpoint-tail replay. August analysis, formal
dependency design/plan, `docs/harness.md`, and the evidence report must be
synchronized. P6/P7 and any civilization progression remain excluded.

## Evidence

`infra-reference-data-license-admission` independently proves ten named
capabilities: canonical append/outbox, authoritative branch admission,
correction projection/outbox, revoked-preview, forged input, owner, revision
and privacy zero-write, duplicate handling, and full/checkpoint-tail replay.
Evidence:
`.harness/verification/infra-reference-data-license-admission-report.json`.
