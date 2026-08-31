# Character Gameplay Foundation Plan Tree

Status: `implemented-and-verified for the scoped Gameplay Foundation closure; broader generic domains remain separately deferred`

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
15. [Package content and cross-domain binding matrix](2026-08-17-package-content-and-cross-domain-binding-matrix-plan.md) `design-only; no package schema or runtime implementation`
16. [Package contract closure and manifest adapter](2026-08-17-package-contract-closure-and-manifest-adapter-plan.md) `design-only; implementation gated`
17. [Federated Gameplay Extension Platform](2026-08-18-federated-gameplay-extension-platform-implementation-plan.md) `INF-P P1 binding sequencing implemented and verified; package and row gates remain separate`
18. [Federated Gameplay Extension Platform approval packet](../../../../specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-08-18-federated-gameplay-extension-platform-approval-packet.md) `platform contract approved; downstream implementation separately gated`
19. [Federated Gameplay Extension Platform approval-readiness audit](../../../../specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-08-18-federated-gameplay-extension-platform-approval-readiness-audit.md) `design approved; INF-P schema/P1 mechanics implemented and verified`
20. [Federated Gameplay Extension Platform schema decision design](../../../../specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-08-18-federated-gameplay-extension-platform-schema-decision-design.md) `historical design gate; superseded by verified INF-P implementation`
21. [Federated Gameplay Extension Platform schema decision implementation plan](2026-08-18-federated-gameplay-extension-platform-schema-decision-implementation-plan.md) `historical gate; superseded by verified INF-P implementation`
22. [Federated Gameplay Extension Platform schema mapping and migration errata](../../../../specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-08-18-federated-gameplay-extension-platform-schema-mapping-and-migration-errata-design.md) `approved mapping; INF-P mechanics implemented and verified`
23. [Federated Gameplay Extension Platform schema-closure addendum](../../../../specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-08-18-federated-gameplay-extension-platform-schema-closure-addendum.md) `approved closure; INF-P mechanics implemented and verified`
24. [INF-4AI P5 actor-private expression implementation plan](2026-08-27-inf-4ai-p5-actor-private-expression-file-plan.md) `implemented and verified narrow vertical; generic social/session expansion remains blocked`

Plans 2-5 are the first minimal closure. Plan 3 is the explicit event-store,
outbox, and authority-bus coupling prerequisite for embodied-interaction Phase
6. Plans 6-11 are prerequisite branches
for the `adventure-basic` pack and must follow their listed dependency order.

Current execution has completed the bounded foundation domains through initial
inventory/encumbrance, equipment placement/activation, fixed-offer purchase,
zero-consideration gift, credential-link/presentation, simple-debt
ownership/economy, registered-terms contracts, and bounded typed
service-completion fulfillment. The strict `adventure-basic` reference closure
now composes those into all five scoped scenarios with authoritative success
and structured failure, atomic events, facade revision/result metadata,
online/full/checkpoint-tail replay equivalence, filtered mirror output,
explanation traces, and real-Godot delivery. It is still not a claim of
generic equipment, ownership, economy, dynamic market, cultivation, or
relationship-graph completion.

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

`adventure-basic` has a governed, digest-validated manifest plus five verified
reference compositions that reuse the existing authorities. Patch activation,
client authority, generic transport durability, and broader domain expansion
remain outside its dedicated closure plan.

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
