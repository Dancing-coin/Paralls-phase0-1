# INF-1AH Mill Reinforced Decommission Implementation Plan

Status: `implemented and verified: frozen v3, exact descriptor/catalog admission, and the one lifecycle runtime vertical`

## Preconditions

- Keep `package:industrial-facilities:v2` frozen and use it only as committed
  source-evidence pins.
- Keep frozen `package:industrial-facilities:v3` immutable. Its exact
  descriptor/catalog row is resolved only through the existing read-only
  binding path.
- Do not use a default lifecycle status or derive a decommission package from
  the frozen reinforcement package.

## Ordered Future Gates

1. Record the approved lifecycle-only contract: exactly
   `active -> decommissioned`, the fixed event, project privacy, terminal/no-
   compensation boundary, and `started`-run zero-write rejection with no run
   cancellation, reservation release, output discard, or substitute event.
2. Historical completed gate: package literals were approved, adapter-validated,
   and frozen as the distinct v3 record in the
   [freeze record](../../../specs/world-character-siming-authority-mainline/inf-1/2026-08-20-inf-1ah-industrial-facilities-v3-decommission-freeze-record.md).
   It may not supply authority coordinates or be installed/activated before
   separate descriptor/catalog admission.
3. Completed gate: the exact immutable descriptor/catalog row in the
   [admission packet](../../../specs/world-character-siming-authority-mainline/inf-1/2026-08-20-inf-1ah-construction-owner-operation-descriptor-catalog-admission-packet.md)
   was approved and installed; the existing registry resolves exactly one
   read-only binding and retains all source/new-package/descriptor/active-set
   pins.
4. Completed admission gate: focused tests and the independent admission
   Harness cover exact-one resolution, pins, snapshot replay, and admission
   zero-write. Write lifecycle RED tests only after separate runtime approval.
5. Completed: focused RED tests cover exact-source proof, zero-write conditions,
   privacy, revision fences, exact/changed idempotency, append receipt, full
   replay, checkpoint-tail replay, and terminal/no-compensation behavior.
6. Completed: add the independent lifecycle Harness.
7. Completed: implement only the owner-bound verifier, fixed projector/reducer branch,
   and one-event append vertical through `GameplayCommandEnvelope ->
   SettlementPlan -> GameplayEventStore.append_batch()`.
8. Completed: focused tests, the independent Harness, descriptor-admission
   Harness, and a repository-local full pytest probe pass. Synchronize durable
   evidence without declaring August INF A-D complete.

## Stop Conditions

Stop before implementation when the new package fields are not literal and
approved; current lifecycle status cannot be represented and replayed exactly;
source evidence cannot satisfy the stated pins; or the path would introduce
any prohibited generic/cross-domain fact.
