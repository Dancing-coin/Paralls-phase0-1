# INF-2AM Reinforced Mill Flour Output Purchase Owner-Admission Contract

Status: `implemented and verified narrow vertical; generic payment/transfer remains blocked`

## Exact Row

```text
one project-visible INF-1AM certified flour output
-> existing InventoryAuthorityService
-> one fixed provider-held flour custody receipt
-> existing EconomyAuthorityService
-> one authority-only fixed flour-output purchase
```

The Inventory and Economy writes are separate owner-local batches and have
separate append-derived receipts. The exact package exchange transfers one
`item:industrial-facilities:flour@1` lot of quantity `10` from
`organization:district-milling-cooperative` to the acquisition owner, for a
fixed `8 currency:local` minor units. It is terminal and has no compensation,
refund, reversal, market-price, delivery, material-input, or generic-transfer
meaning.

## Immutable Pins

| Field | Fixed value |
| --- | --- |
| package | `package:industrial-facilities:v7`, version `7.0.0`, author/trust `author:repo` / `trust:repo` |
| package outcome | `outcome:industrial-facility-reinforced-mill-flour-output-purchase@1` |
| declaration / binding | `declaration:industrial-facility-reinforced-mill-flour-output-purchase@1` / `binding:industrial-facility-reinforced-mill-flour-output-purchase@1` |
| capability | `capability:package-declared-negotiated-exchange@1` |
| package policy | `policy:industrial-facility-reinforced-mill-flour-output-purchase-price@1`, fixed `8 currency:local` |
| inventory source | `gameplay.inventory.mill_flour_output_received@1`, provider `organization:district-milling-cooperative`, fixed provider container `container:district-milling-cooperative:mill-output`, item definition `item:industrial-facilities:flour@1`, quantity `10` |
| source predicates | `predicate:construction-reinforced-mill-flour-output-certified@1`, then `predicate:inventory-reinforced-mill-flour-custody@1`; subject binding `slot:facility-project@1` |
| Economy owner/vector | existing `EconomyAuthorityService`; fixed debit, credit and `package_declared_negotiated_exchange_settled` batch |
| privacy | Inventory receipt is project scoped; Economy settlement is authority only |
| lifecycle | each certificate may create exactly one custody receipt and one terminal settlement; no reversal, retry-as-new, compensation, fanout or combined receipt |

## Source And Party Derivation

The provider is fixed, not caller supplied. The receiver is the one committed
acquisition owner of the certified facility; its exact current account is
resolved by the existing exact-one-account rule. The package content does not
choose an owner, stream, event, receipt, settlement fragment or descriptor.
The Inventory receipt derives its item id and source holder/container from the
certificate; callers cannot supply those coordinates.

## Zero Write

Reject before mutation for an unknown/inactive/unadmitted package, digest or
binding mismatch, zero/multiple binding, missing/private/stale certification,
wrong provider/receiver/price/currency, missing or multiple accounts, missing
fixed container/capacity, wrong item or quantity, source/project/facility
conflict, changed duplicate, or source/inventory/Economy revision conflict.

## Conflict Matrix

This is `new`. It does not relabel the generic output receipt, INF-2AA
delivery, INF-2AC exchange, public milling service, or a P1 flour fixture. Its
single source partition is the INF-1AM certificate and its immutable v7
outcome is the only admitted Economy consequence.
