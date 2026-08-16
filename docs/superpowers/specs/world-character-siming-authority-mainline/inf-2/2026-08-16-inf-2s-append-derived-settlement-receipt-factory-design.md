# INF-2S Append-Derived Settlement Receipt Factory

Status: `implemented and verified; arbitrary settlement remains blocked`

## Purpose

INF-2S makes `SettlementReceipt` an explicit read-only summary of one
`GameplayEventStore.append_batch()` result. It removes owner-local field-by-
field receipt construction from the existing obligation, Economy-account and
Commerce receipt readers without adding a receipt store, coordinator writer,
or cross-domain settlement path.

## Contract

`SettlementReceipt.from_append_result(result, audit_refs, pinned_revisions,
projection_digests)` is the only shared constructor used by the admitted
readers. It copies transaction id, committed event ids, resulting stream
revisions, idempotency status and failure only from the supplied
`AppendBatchResult`; metadata parameters may add references/digests but cannot
replace append-derived fields.

| Reader | Existing owner | Scope | Additional metadata |
| --- | --- | --- | --- |
| obligation compatibility reader | `ObligationSettlementCoordinator` (read-only) | existing scoped projection | obligation id, policy revision |
| account receipt reader | `EconomyAuthorityService` | authority only | economy transaction ref |
| commerce receipt reader | `CommerceAuthority` | authority only | commerce transaction ref |

The receipt factory has no store reference and never appends. Rejected append
results must remain `zero_write=True` and retain the original structured error.

## Completion Evidence

Focused tests must separately prove committed and rejected factory derivation,
and delegation by each of the three admitted readers. The dedicated Harness
also reruns owner-only obligation and existing Economy/Commerce replay tests.
This does not implement arbitrary cross-domain business settlement or
caller-open policy registration.

Evidence: `.harness/verification/infra-append-derived-settlement-receipt-report.json`.
