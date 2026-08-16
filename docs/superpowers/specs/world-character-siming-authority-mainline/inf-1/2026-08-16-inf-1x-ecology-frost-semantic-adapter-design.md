# INF-1X Ecology Frost Semantic Adapter

Status: `implemented and verified closed Ecology owner row; generic adapter remains incomplete`

## Closed Input

`SemanticEcologyFrostCommand` is the only proposed input. It fixes
`effect_ref=effect:frost`, `state_ref=state:frosted@1`, project scope,
`hazard_ref`, `crop_ref`, `region_ref`, expected ecology stream revision,
semantic snapshot digest, magnitude, due tick and resistance revision. It does
not accept owner, stream, event type, visibility override or callback.

## Authority Mapping

`SemanticSettlementAuthority` checks the semantic snapshot targets `crop_ref`,
derives `gameplay:ecology:{region_ref}`, and builds an Ecology-principal
`GameplayCommandEnvelope`. `EcologyHazardAuthority.apply_crop_state()` then
rebuilds and validates the committed hazard/crop/region relation, source
privacy, state/effect contract, revision and idempotency before its one
`GameplayEventStore.append_batch()` call. A proposal-supplied region cannot
redirect the write: the owner derives the actual ecology stream from the
committed hazard/crop relation and rejects a mismatched expected stream
revision without a write. Receipt, outbox and replay remain Ecology-owned.

## Required RED Evidence

- committed project-visible hazard/crop/region success;
- cross-region, absent/authority-only hazard and forged source relation zero write;
- exact/changed duplicate, stale revision and non-project privacy zero write;
- full/checkpoint-tail replay and scoped outbox;
- direct client/LLM-shaped Ecology envelope rejection.

## Non-goals

No generic ecology semantic adapter, new ecology state row, caller-selected
stream/event/owner, second store or direct semantic append.

## Verification Evidence

`infra-semantic-ecology-frost-adapter` independently proves strict closed
input, Ecology-owner append, revision/snapshot/idempotency zero write, source
privacy zero write, forged-region relation zero write, and Ecology
checkpoint-tail replay. The current report is
`.harness/verification/infra-semantic-ecology-frost-adapter-report.json`.
