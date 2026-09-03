# INF-2AO Production Output Market Eligibility Owner-Admission Design

Status: `autonomous row-specific contract; implementation in progress`

## Product Decision

After a certified production output has been committed to Inventory custody,
Economy records one authority-only eligibility marker saying that this exact
lot may be considered by a later, separately admitted fixed exchange. The
marker is not a price, quote, payment, debit, credit, transfer, market order,
or settlement. It creates no account mutation and no Inventory mutation.

This row closes a real product gap between production and economic listing
without introducing a generic market or payment authority.

## Fixed Contract

| Field | Fixed value |
| --- | --- |
| capability | `capability:economy-production-output-market-eligibility@1` |
| outcome family | `outcome:economy-production-output-market-eligibility@1` |
| contract | `inf:economy-production-output-market-eligibility@1` |
| descriptor | `descriptor:economy-production-output-market-eligibility@1` |
| owner | existing `EconomyAuthorityService` |
| source owner | existing `InventoryAuthorityService` |
| source event | `gameplay.inventory.production_output_received@1` |
| source predicate | `family_ref=production_output_custody@1`, project-visible, exact item/quantity/holder/container mapping |
| source revision fence | exact source event revision equals source Inventory stream head |
| target stream | `gameplay:economy` |
| target event | `gameplay.economy.production_output_market_eligible@1` |
| privacy | `authority_only` |
| policy revision | `policy:economy-production-output-market-eligibility@1` |
| idempotency | `economy:production-output-market-eligibility:{source_event_id}:{source_revision}:{economy_head}:v1` |
| receipt | append-derived `GameplayEventStore.append_batch()` receipt |
| replay | Economy owner projection, full and checkpoint-tail |
| lifecycle | v1 terminal/no compensation; no reversal, retry-as-new, downgrade or refund |

The marker payload copies only source-derived identity and quantity:

```text
eligibility_ref = eligibility:production-output-market-listing@1
source_event_id / source_revision / source_stream_id
item_ref / quantity / holder_ref / container_id
facility_ref / project_ref / recipe_ref
mapping_revision
status = eligible
terminal = v1_terminal_no_compensation
```

No currency, amount, account, buyer, receiver, price policy, market order,
payment vector, or Inventory command is accepted from caller or package.

## Admission And Zero-Write Rules

Before append, Economy must resolve exactly one source event and verify its
Inventory stream head, project visibility, `production_output_custody@1`
family marker, positive quantity, non-empty item/holder/container, and source
provenance. Missing, private, stale, malformed, duplicate, changed-duplicate,
wrong-stream, mapping-conflicting, or revision-conflicting input is zero-write.
The target Economy stream head must equal the expected revision. A second
eligible marker for the same source event is duplicate rejection/replay.

The caller supplies only source event id, expected source revision, command,
correlation and submission metadata. Owner, stream, event, privacy, receipt,
idempotency, and lifecycle coordinates are fixed here.

## Why No New Owner

Economy already owns authority-only economic markers and the `gameplay:economy`
projection. Inventory remains the source/custody owner. The row is a one-way
read-and-record bridge with separate source and target receipts; no new truth
domain or cross-owner writer is required.

## Separation From Generic Surfaces

This row does not authorize generic payment, transfer, treasury, market pricing,
listing, order matching, account selection, or settlement. A later sale or
service exchange still requires its own exact package/descriptor and fixed
party/account/currency/price contract. Existing INF-2AM/AC rows remain distinct
historical partitions.

## Verification Contract

Focused tests must cover success, source privacy, stale source, wrong stream,
forged family/provenance, duplicate and changed duplicate, target revision,
append-derived receipt, no account mutation, and full/checkpoint-tail replay.
An independent Harness must report the same source and target revision vectors.
