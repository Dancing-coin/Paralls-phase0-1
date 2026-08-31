# Owner Operation Conflict Matrix Design

Status: `approved design; required autonomous-admission preflight; no runtime registry`

## Purpose

This matrix prevents autonomous delivery from duplicating facts, overlapping
owner authority, reusing event families with incompatible meaning, or creating
inconsistent privacy and replay behavior. It is a source-controlled, read-only
governance artifact layered on the existing immutable
`GovernedAuthorityContractCatalog` and `OwnerOperationDescriptor` model.

It is not a runtime-writable registry, router, coordinator, writer, or truth
owner. It does not itself select a settlement owner or append an event.

## Matrix Row

Each admitted or proposed owner operation must have one immutable matrix row:

| Field | Rule |
| --- | --- |
| `operation_key` | canonical `domain:fact:outcome@revision`; unique semantic identity |
| `row_status` | `proposed`, `admitted`, `implemented`, `superseded`, `duplicate_closed`, or `rejected` |
| `product_loop` | the user-visible loop unlocked by the row and its dependencies |
| `fact_claim` | one literal truth fact, including subject and state transition if applicable |
| `source_claim` | committed source event/state family, owner, revision fence, and subject binding |
| `owner_ref` | exactly one truth owner; an explicit fixed cross-owner recipe type is required when more than one owner writes |
| `operation_descriptor` | descriptor ref/revision, capability, outcome family, predicate families, and effect types |
| `contract_ref` | immutable governed catalog contract ref/kind |
| `stream_claim` | fixed stream pattern and fixed event family/vector |
| `privacy_claim` | fixed projection scope and no-widening rule |
| `replay_claim` | append-derived receipt reader and full/checkpoint-tail projection reader |
| `lifecycle_claim` | terminal, correction, reversal, retry, and compensation rules; `none` is explicit |
| `package_claim` | immutable package/declaration/binding/policy/content/active-set pins, or `not_applicable` |
| `evidence` | contract, plan, focused tests, Harness report, and audit/checkpoint links |

## Mandatory Conflict Checks

Before a new row enters contract authoring, the autonomous loop compares it
with all `admitted` and `implemented` rows:

1. **Fact-claim collision**: two rows cannot claim the same subject-scoped
   canonical fact and terminal transition. The new row must be marked duplicate,
   replace the old row through an explicit migration, or use a distinct fact.
2. **Owner collision**: a second owner cannot claim a fact already owned by an
   existing owner. A new bounded owner is allowed only for an unclaimed fact
   with a non-overlapping event, stream, projection, and replay boundary.
3. **Event-family collision**: sharing an event family is allowed only when the
   same owner, fixed stream pattern, payload schema/meaning, privacy, replay
   reader, and lifecycle semantics are identical, or when the matrix defines
   disjoint immutable payload partitions. A shared companion ledger event such
   as a debit/credit may appear in several fixed atomic vectors without claiming
   their distinct root facts. A shared transform family must have disjoint fixed
   source/target/pin partitions. Otherwise the row requires a new literal event
   family; it cannot overload an existing family.
4. **Source/outcome duplicate**: the same committed source predicate plus the
   same outcome is a duplicate even when proposal names, packages, or callers
   differ. Package aliases cannot bypass this rule.
5. **Privacy collision**: a new row cannot widen an existing source or target
   scope. Mixed scope requires an already admitted explicit projection contract.
6. **Receipt/replay collision**: a row cannot reuse a receipt or replay reader
   unless it proves the same owner-local event vector. Combined cross-owner
   receipts are rejected.
7. **Lifecycle collision**: a second terminal/reversal/compensation definition
   for the same fact is rejected unless the first row is explicitly superseded
   through replay-compatible migration.
8. **Package/pin collision**: frozen package revisions, declaration digests,
   descriptor revisions, and active-set pins cannot be overwritten or
   reinterpreted by a later row.

The preflight disposition is exactly one of `new`, `duplicate_closed`,
`supersede_requires_migration`, `conflict_rejected`, or
`existing_row_extension`. Only `new` or a fully specified
`existing_row_extension` may proceed.

## Product-Oriented Selection

The matrix is not an excuse to select the smallest technically legal row. The
autonomous product-contract role ranks viable rows by user-visible loop value,
dependency unlock, content authoring leverage, coherence of the resulting
world, implementation/replay risk, and consistency with existing owner facts.
The selected row must record rejected higher-level and lower-level alternatives
so a later reviewer can understand why it was the best product move.

## New Owner Admission

A bounded new owner is permitted only after the matrix proves all of these:

- the fact claim is unowned and materially needed for a product loop;
- no existing owner can own it without violating its contract;
- its event family, stream pattern, privacy, receipt, replay, and lifecycle
  boundary are non-overlapping and fixed;
- it has no generic operation parameter, caller-selected authority coordinate,
  or cross-domain settlement role; and
- its descriptor/catalog row, focused RED tests, independent Harness, and
  full/checkpoint-tail replay evidence are planned before implementation.

## Process And Trace

The product-contract subagent creates the matrix row and a decision record.
The audit subagent independently performs the eight conflict checks before a
package is frozen, descriptor/catalog row installed, or runtime code written.
The final row contract must link both records, and the completion audit and
continuation checkpoint must record the final disposition.

All matrix data is documentation and source-controlled immutable catalog
metadata. Runtime remains limited to the existing catalog/descriptor read path
and the canonical `GameplayCommandEnvelope -> SettlementPlan ->
GameplayEventStore.append_batch()` spine.

## 2026-08-27 INF-4V Preflight Result

The matrix admits one `existing_row_extension` for the Organization owner:
committed actor-scoped Production completion evidence plus an explicit
organization-summary schedule/work-order proof yields exactly one
Organization-owned work-contribution acceptance event. It does not collide
with Economy wage accrual, Organization schedule recording, branch promotion,
or Social/Population truth because the accepted fact is a distinct
organization work-history projection. The row has a fixed stream, event,
privacy, source/revision, idempotency, receipt, replay, and terminal contract;
all generic work/payment/branch inputs remain zero-write.
