# INF-2O Economy Dynamic Quote Formal Spine Design

Status: `implemented bounded and verified`

`EconomyAuthorityService.publish_dynamic_quote()` is an existing Economy-owned
event family on the canonical `gameplay:economy` stream, but currently reaches
the store through the legacy raw `_append()` helper. INF-2O migrates only that
operation to the existing `GameplayCommandEnvelope -> SettlementPlan ->
GameplayEventStore.append_batch()` path.

| Concern | Contract |
| --- | --- |
| Sole writer | existing `EconomyAuthorityService` / `actor_gameplay.economy_domain` |
| Stream/event | `gameplay:economy` / existing `gameplay.economy.dynamic_quote_published` |
| Input | validated existing quote payload, caller-pinned or current Economy revision, fixed command fields |
| Privacy | project-scoped redacted quote projection; account/payment fields are never admitted |
| Receipt/replay | sole append result and existing `EconomyProjector` full/checkpoint-tail replay |

The method proves exact duplicate replay, changed duplicate zero-write,
explicit revision conflict, invalid quote, account/payment-field privacy
rejection and full/checkpoint-tail replay. It remains an Economy-local write
and does not itself admit Ecology input, dynamic orders, payment or generic
settlement. INF-3J separately consumes this closed target through a fixed
opaque Ecology admission; that does not widen INF-2O itself.
