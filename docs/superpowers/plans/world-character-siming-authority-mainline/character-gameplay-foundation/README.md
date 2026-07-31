# Character Gameplay Foundation Plan Tree

Status: `drafted-for-spec-review`

Date: `2026-07-29`

This is the dedicated execution tree for
`specs/world-character-siming-authority-mainline/character-gameplay-foundation/`.
It is intentionally separate from the LLM, dialogue streaming, TTS, and
embodied-interaction product plans.

No plan in this folder authorizes implementation until the matching gameplay
foundation spec tree is approved. The code baseline is recorded in
`2026-07-29-gameplay-foundation-spec-and-runtime-baseline.md` in the spec tree.

## Execution Order

1. [Master implementation plan](2026-07-29-character-gameplay-foundation-implementation-plan.md)
2. [Contracts, event store, and harness](2026-07-29-gameplay-foundation-contracts-events-and-harness-plan.md)
3. [State-group registry and runtime facade](2026-07-29-state-group-registry-and-runtime-facade-plan.md)
4. [Resource, status, body, and effective stats](2026-07-29-resource-status-body-and-effective-stats-plan.md)
5. [Inventory, containers, and encumbrance](2026-07-29-inventory-container-and-encumbrance-plan.md)
6. [Equipment runtime](2026-07-29-equipment-runtime-plan.md)
7. [Ownership, economy, and transactions](2026-07-29-ownership-economy-and-transaction-plan.md)
8. [Skill ability graph and affordance](2026-07-29-skill-ability-graph-and-affordance-plan.md)
9. [Patch Rule IR and capability runtime](2026-07-29-gameplay-patch-rule-ir-and-capabilities-plan.md)
10. [Godot mirror, persistence, and migration](2026-07-29-godot-mirror-persistence-and-migration-plan.md)
11. [Adventure-basic reference closure](2026-07-29-adventure-basic-reference-closure-plan.md)

Plans 2-4 are the first minimal closure. Plans 5-10 are prerequisite branches
for the `adventure-basic` pack and must follow their listed dependency order.

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
