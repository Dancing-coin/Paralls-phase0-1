# INF-4K Government Branch Remediation Receipt Design

Status: `implemented and verified for one derived non-production remediation receipt row only`

## Closed Contract

INF-4K adds a read-derived receipt for the existing INF-4J failed-inspection
remediation append, only after INF-4L proves that append derives from durable
accepted-preview evidence. It creates no receipt stream, event, writer,
runtime, scheduler or promotion route.

| Concern | Contract |
| --- | --- |
| Sole writer | existing `GovernmentAuthority` / `actor_gameplay.government_domain` |
| Source | existing accepted failed `inspection` candidate through `BranchPreviewAuthority` |
| Stream/event | existing `gameplay:government_branch:{branch_ref}:{organization_ref}` / `gameplay.government.branch_inspection_remediation_recorded` |
| Receipt source | the same `GameplayEventStore.append_batch()` result, plus the existing Government scenario projection hash |
| Receipt type | immutable `BranchScenarioReceipt`, never production `SettlementReceipt` |
| Pins | production Government read revision and branch scenario stream revision |
| Privacy | `creator_debug` only |
| Replay | receipt reconstruction reads durable scenario events and the scoped projection; it never reads preview buffers |

The receipt records transaction id, committed event ids, scenario stream
revisions, source Government revision, projection hash, privacy scope and
idempotency status. Exact duplicate retry reconstructs the same receipt;
changed duplicate, privacy/source/scenario revision failure and non-remediation
events are zero-write and produce no receipt.

## Non-goals

This is not a generic branch receipt, cross-owner receipt, remediation
lifecycle, settlement coordinator, production receipt, promotion or population
truth surface. Production replay remains isolated and promotion remains
unsupported.

## Admission Boundary

INF-4L supplies the replayable, scoped admission event and Government rejects
missing, forged or mismatched evidence without writing. This reader is thereby
limited to a valid existing remediation event. Generic receipt, remediation
lifecycle and promotion remain blocked.

## Required Evidence

Focused tests and a dedicated Harness must independently prove new append
receipt, duplicate reconstruction, changed duplicate and privacy/revision zero
writes, receipt replay from durable events, checkpoint-tail projection
equivalence, scoped outbox, production isolation and promotion rejection.
