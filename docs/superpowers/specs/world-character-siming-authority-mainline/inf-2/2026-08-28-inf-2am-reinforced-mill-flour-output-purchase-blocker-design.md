# INF-2AM Reinforced-Mill Flour Output Purchase Blocker

Status: `historical blocker; superseded by implemented INF-1AM source and INF-2AM narrow vertical`

## Purpose

This record is the durable blocker disposition for the only currently
plausible INF-2 Slot-C product loop:

```text
one committed mill_reinforced production completion
-> one Inventory-owned flour custody fact
-> one fixed Economy purchase outcome
```

The direction is product-significant because it would connect the existing
reinforced-mill production and public-use loop to an owned output that can be
consumed by a later Economy operation. It is not a generic output, payment,
transfer, market, or settlement capability.

## Conflict-Matrix Preflight

The candidate is not yet `new` or `existing_row_extension`:

| Check | Result | Evidence |
| --- | --- | --- |
| Fact collision | not formed | `inventory.output_received` is an existing generic receipt primitive, not a mill-specific custody fact |
| Owner collision | unresolved | Inventory owns custody and Economy owns ledger truth, but no row-specific source/consumer contract joins them |
| Event collision | unresolved | Existing `output_received` and package-exchange events have different provenance and cannot be relabeled |
| Source/outcome duplicate | rejected | INF-2AA delivery payment and INF-2AC package exchange are closed partitions |
| Privacy | unresolved | the source holder/container and buyer scope are not committed |
| Receipt/replay | unresolved | no exact Inventory source reader or Economy root-outcome reader exists |
| Lifecycle | unresolved | no fixed sale completion, reversal, retry, or compensation rule exists |
| Package/pins | unresolved | a new immutable package revision would be required; v1 through v6 cannot be reused or modified |

Disposition: `owner-contract blocked`.

## Fixed Direction, Not Admitted Content

The following identifiers are candidate labels only and are not frozen:

- row id: `INF-2AM`;
- candidate package revision: `package:industrial-facilities:v7`;
- source mode: `inventory_custody@1`;
- existing source owner: `actor_gameplay.inventory_domain`;
- reusable Economy capability family: `capability:package-declared-negotiated-exchange@1`;
- reusable Economy lifecycle shape: `package_declared_negotiated_exchange@1`;
- candidate outcome ref: `outcome:industrial-facility-reinforced-mill-flour-output-purchase@1`;
- candidate declaration ref: `declaration:industrial-facility-reinforced-mill-flour-output-purchase@1`;
- candidate policy ref: `policy:industrial-facility-reinforced-mill-flour-output-purchase-price@1`.

These labels do not admit a package, descriptor, catalog row, event, or write
path. The existing exchange substrate can be reused only after every source
and party pin below is fixed.

## Exact Missing Business Decisions

The next approval packet must supply all of these literals; no default may be
inserted:

1. **Production source**: exact `recipe_ref`, source `run_finished` event
   family/schema, required `mill_reinforced` facility and earlier v2
   reinforcement provenance, event revision, facility revision, and stream
   head fence.
2. **Item identity**: immutable flour `definition_ref`, `definition_schema_ref`,
   typed content, and the exact item instance derivation rule. The generic
   `output_item` string is insufficient.
3. **Custody binding**: Inventory owner, source holder, destination container,
   inventory stream, privacy scope, quantity, and owner-derived idempotency
   key. Container selection cannot be caller-provided or “first available”.
4. **Party binding**: fixed seller/provider and buyer/receiver, or an explicit
   owner-derived rule that resolves exactly one of each from committed facts.
5. **Economy terms**: currency, fixed or bounded price policy and revision,
   exact Economy root event/outcome, account-opened pins, and insufficient-
   balance behavior.
6. **Lifecycle**: terminal, retry, reversal, correction, and compensation
   semantics. The source custody event and Economy settlement must retain
   separate owner receipts; no combined receipt is valid.
7. **Package content**: complete immutable v2 manifest content, declaration
   claim, adapter-derived declaration digest, normalized content digest, and
   active-set/descriptor pins for a new revision only.

## Rejected Shortcuts

- `run_finished.output_item` cannot be treated as Inventory custody.
- The P1 bakery `item:flour` fixture cannot define a district mill output.
- `archive_token` custody cannot stand in for flour.
- INF-2AA delivery payment cannot be reused without a committed delivery row.
- INF-2AC package exchange cannot be reused with a renamed outcome.
- Low-level `open_account`, `transfer`, or reservation helpers cannot create a
  business row by themselves.
- Caller-selected source, actor, item, container, account, price, owner,
  stream, event, privacy, receipt, or compensation is zero-write.

## Gate To Implementation

Only after the missing literals are approved and committed may the row proceed:

```text
row-specific Inventory source contract
-> new immutable package v7 freeze/digest validation
-> exact descriptor/catalog admission
-> RED tests
-> Inventory custody implementation
-> Economy fixed purchase implementation
-> independent Harness and full/checkpoint-tail replay proof
```

Until then, Slot C remains `owner-contract blocked`, Goal remains `active`,
and August INF A-D remains `not complete`.

## Evidence

- `backend/app/gameplay/construction_production_runtime.py` committed
  `run_finished` payload contains `facility_ref`, `recipe_ref`, completed tick,
  and `output_item`, but no Inventory custody binding.
- `backend/app/gameplay/inventory_runtime.py` `record_output_receipt()` accepts
  caller-supplied source, actor, item, definition, container, and quantity.
- `backend/app/gameplay/economy_runtime.py` supports only already admitted,
  fixed package-exchange source modes and exact party/account resolution.
- `inf-2/2026-08-20-inf-2-remaining-rows-blocker-design-packet.md` records the
  durable Slot-C blocker and rejects relabeling existing partitions.
