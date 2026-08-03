# Character Gameplay Foundation Plan Tree

Status: `execution-active-for-foundation-core`

Date: `2026-07-29`

This is the dedicated execution tree for
`specs/world-character-siming-authority-mainline/character-gameplay-foundation/`.
It is intentionally separate from the LLM, dialogue streaming, TTS, and
embodied-interaction product plans.

The event-store/replay/outbox spine and the minimum read-only runtime-state
core are implemented and verified. This tree authorizes continued foundation-
core implementation in dependency order, but does not claim or authorize the
complete façade, gameplay domains, persistence, or Godot mirror without their
own plan phases and evidence. The current code boundary is recorded in
`2026-07-29-gameplay-foundation-spec-and-runtime-baseline.md`.

## Execution Order

1. [Master implementation plan](2026-07-29-character-gameplay-foundation-implementation-plan.md)
2. [Contracts, event store, and harness](2026-07-29-gameplay-foundation-contracts-events-and-harness-plan.md)
3. [Coupled event store and authority bus](2026-07-31-coupled-event-store-and-authority-bus-plan.md)
4. [State-group registry and runtime facade](2026-07-29-state-group-registry-and-runtime-facade-plan.md)
5. [Resource, status, body, and effective stats](2026-07-29-resource-status-body-and-effective-stats-plan.md)
6. [Inventory, containers, and encumbrance](2026-07-29-inventory-container-and-encumbrance-plan.md)
7. [Equipment runtime](2026-07-29-equipment-runtime-plan.md)
8. [Ownership, economy, and transactions](2026-07-29-ownership-economy-and-transaction-plan.md)
9. [Skill ability graph and affordance](2026-07-29-skill-ability-graph-and-affordance-plan.md)
10. [Patch Rule IR and capability runtime](2026-07-29-gameplay-patch-rule-ir-and-capabilities-plan.md)
11. [Stateful Patch data migration](2026-08-02-stateful-patch-data-migration-plan.md)
12. [Godot mirror, persistence, and migration](2026-07-29-godot-mirror-persistence-and-migration-plan.md)
13. [WebSocket session identity and mirror scope](2026-08-03-websocket-session-identity-and-mirror-scope-plan.md)
14. [Adventure-basic reference closure](2026-07-29-adventure-basic-reference-closure-plan.md)

Plans 2-5 are the first minimal closure. Plan 3 is the explicit event-store,
outbox, and authority-bus coupling prerequisite for embodied-interaction Phase
6. Plans 6-11 are prerequisite branches
for the `adventure-basic` pack and must follow their listed dependency order.

Current execution has completed bounded foundations through the initial
inventory/encumbrance, equipment placement/activation, fixed-offer purchase,
zero-consideration gift, credential-link/presentation, and simple-debt
ownership/economy slices plus registered-terms contract records and bounded
typed service-completion fulfillment. This is not a complete equipment,
ownership, economy, or adventure closure; those phases retain their own
dependency and evidence gates.

The Patch Rule IR/capability phase has an implemented minimum governed runtime:
trusted immutable candidate manifests, dependency/schema gates, active-set
selection, deterministic proposal-only rules, side-effect-free capability
registration, JSON candidate/active-set snapshot recovery, and a ledger-backed
install/enable/disable control-plane slice plus a constrained `resource.consume`
settlement mapping. Rule-only same-patch upgrade/rollback and its fail-closed
lifecycle replay are also implemented. A bounded explicit-actor state-group
enable/disable joins those lifecycle events to the active-set cutover in one
batch. Compatible same-patch identity-rebind upgrade/rollback is also atomic;
the first `core.resources` typed maximum-reduction data-transform upgrade is
also atomic and shadow-replay checked. It retains old/new definitions, rejects
reservations/stale inputs, writes explicit loss, and rejects its lossy rollback;
domain-effect revocation, compensation, additional data-transform stateful
migration, general settlement conversion, durable registry, and delivery work
remain planned.

`adventure-basic` now has a governed, digest-validated manifest plus a
Scenario 1 backend composition that reuses the existing fixed-offer and
equipment authorities. It is not a scenario closure: Patch activation, replay
comparison, mirror delivery, Godot evidence, and every remaining scenario stay
planned under its dedicated plan.

## Global Controls

- Preserve Godot as presentation/prediction host; backend settlement remains
  authoritative.
- Preserve ESM, Siming, and CharacterAgent ownership boundaries.
- Reuse current typed protocol and harness patterns; add no dependency without
  explicit approval.
- Add failing focused tests before each implementation behavior.
- Retain fresh evidence under `.harness/verification/`; no static-only claim
  counts as an integration result.
- Every plan phase runs its focused profile, all predecessor profiles, and the
  appropriate existing mainline regression profile before advancing.
