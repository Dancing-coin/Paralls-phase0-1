# Character Action Foundation Current State

Date: `2026-09-14`

Status: `current-state ledger; implementation gap remains`

For the broader cross-document reconciliation and source-of-truth hierarchy,
see `docs/character/character-runtime-design-drift-audit.md`.

## Executive Finding

The repository has a formally correct shared-actor direction, but the action
foundation is not yet a single coherent runtime. Player locomotion already
uses `CharacterControllerPort -> CharacterMotor`; NPC embodiment still has a
direct-coordinate path, and action/presentation state is partly model-specific.

The latest unified target is defined in:

- `docs/superpowers/specs/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-design.md`
- `docs/superpowers/plans/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-implementation-plan.md`

Runtime asset packages use `assets/active/<package_id>/`; character authoring
guidance, manifests, reports, and provenance may remain under
`assets/characters/`, but that directory is not a second runtime package root.

Its final child boundaries are:

- `2026-09-14-character-physics-motion-and-contact-subspec.md`
- `2026-09-14-character-esm-action-attempt-settlement-subspec.md`
- `2026-09-14-character-connected-action-and-physical-replication-subspec.md`
- `2026-09-14-character-animation-asset-qualification-and-concurrent-realization-subspec.md`

## What Exists

### Final design scope clarification

The final design distinguishes three claims that were previously easy to
conflate:

- Godot `CharacterBody3D`/Motor is the first milestone's local kinematic
  movement and collision executor;
- ESM/Gameplay or a registered Composite coordinator is the semantic/world
  consequence authority and must validate local physical evidence before
  settlement; INF is a proposal/context source and projection consumer, not a
  generic settlement writer;
- the existing Gameplay mirror is a projection/prediction transport, not a
  completed multiplayer physical replication system.

The repository therefore does not currently claim server-authoritative rigid
body simulation, raw-pose networking, or rollback netcode.

### Shared actor seams

- `CharacterControllerPort` exists as the intended ingress seam.
- Human, agent, and program adapters exist and normalize intent-like payloads.
- `CharacterRuntimeState` and `CharacterPresentationInput` exist as transitional shared contracts.
- `CharacterMotor` owns the current player movement call to `move_and_slide()`.

### Action and presentation fragments

- `EmbodiedActionController` already models target acquisition, navigation,
  alignment, preparation, contact, and recovery.
- `KnightRoleSkin` and `KnightCombatModifier` provide model-specific
  presentation and post-animation combat correction.
- `character-action-asset-interface.md` already proposes tag-based action
  descriptors, but the contract is not yet enforced by runtime validation.
- The animation asset qualification child specification now defines the missing
  import boundary for external full-body clips: canonical mapping, build-time
  derived upper-body realizations, explicit full-body fallbacks, root-motion
  provenance, and machine-readable qualification reports. This is a design
  contract; the repository does not yet claim the compiler or runtime registry
  is complete.

### INF/CharacterAgent fragments

- CharacterAgent L1-L4 produces goals, evidence, planning, execution metadata,
  and presentation-shaped packets.
- Gameplay Foundation already owns resource/body/status/ability projections and
  authority event settlement.
- Siming delivery is catalyst-level and reaches the character runtime through
  the merged bridge path. It cannot emit `AuthorityResult`; it may only carry
  `goal:*`, `constraint:*`, `evidence:*`, presentation hints, and metadata such
  as `reason_codes`.

The current backend implementation is consistent with this boundary: the
governed INF catalog is a read-only admission/catalog surface, and the L4
adapter builds an envelope while gameplay authorities retain write authority.
The embodied settlement path remains a Phase 0 compatibility path
(`esm_compatibility_adapter` / `gameplay_event_batch_writer`); it is not yet
the final canonical `ActionAttempt -> route resolver -> ESM/Gameplay/Composite`
pipeline described by the 2026-09-14 specs.

## Confirmed Breaks

1. `CharacterReplica` still contains direct `global_position +=` movement,
   creating a second locomotion truth beside `CharacterMotor`.
2. The parallel-state concept has no single coordinator defining priority,
   occupancy, cancellation, death override, or same-frame write order.
3. Existing actions are partly direct strings, clip names, timers, and node
   paths; descriptors and namespaces are not enforced.
4. `KnightRoleSkin` can sample root motion, but a complete Motor-consumption
   loop is not yet the universal action path.
5. Local action metadata can be confused with Gameplay/ESM/Composite authority
   unless the descriptor explicitly excludes damage/effect settlement and
   `authority_route_ref` is restricted to `esm|gameplay|composite`.
6. Multiple tag families exist (`active_goal_tags`, `evidence_tags`,
   `primitive_action_tags`, `status_tags`, `expression:*`, `semantic_tags`) but
   their ownership, lifecycle, and conversion direction are not centralized.
7. Imported asset qualification is incomplete; the preserved knight resources
   currently lack the verified Skeleton3D/AnimationPlayer/action-clip chain
   required for runtime admission.
8. External full-body animation does not automatically qualify for locomotion
   coexistence. Until a native or derived concurrent realization passes the
   qualification report, the honest runtime mode is full-body exclusive,
   explicit queue/reject, or presentation-only fallback.
9. The repository has no complete weapon runtime. Equipment/inventory
   authority fragments and `KnightCombatModifier` do not yet provide a generic
   equipment binding, weapon action profile, melee `ActionAttempt` route, or
   hitscan semantic route.

## Evidence Boundaries

- `scripts/character/CharacterMotor.gd` contains the current canonical `move_and_slide()` path.
- `scripts/character/CharacterReplica.gd` still contains direct coordinate
  stepping that must be removed or isolated behind the Motor contract.
- `character_presentation_bindings.json` is currently empty for the default
  runtime binding set.
- `.harness/verification/character-asset-qualification-report.json` does not
  qualify the preserved knight resources for runtime use.

## Tag Relationship Decision

INF metadata is not a second character state machine. The legal conversion is:

```text
INF facts / evidence / goals / constraints
-> CharacterAgent intent proposal
-> actor layer arbitration
-> action/presentation tags
-> contact/request event
-> ESM/Gameplay/Composite settlement
-> committed authority result
-> state/status projection consumed by CharacterAgent/INF
```

The canonical `ActionAttempt` schema is shared by the parent spec, ESM child
spec, and plans. `submitted_at` is audit-only and excluded from
`canonical_payload()`. Payload and evidence limits are part of the contract,
and marker observations are joined with same-tick Motor evidence before a
contact-dependent attempt is emitted. Phase B uses `runtime_correction`; the
future physical stream reserves `body_correction` for Mode C only.

The canonical namespaces and write ownership are frozen by the new design spec.

## First-Milestone Definition

The foundation is not complete until at least two externally supplied,
qualified characters can share the Actor/Motor/action path and complete:

- Idle/Walk/Run/Jump/Turn;
- one attack or interaction action with contact timing and recovery;
- real CharacterAgent/INF intent and committed authority-projection delivery;
- visible Godot result with no non-Motor world displacement.
- one qualified held-item slot/hand anchor and one standard melee action whose
  marker reaches ESM/Gameplay through `ActionAttempt`;
- one semantic hitscan request/authority fixture without client damage,
  ammunition, or ballistic truth.

## Deferred Items

Animation authoring, complete weapon/combat content (ammo, projectiles,
dual-wield, parry/clash, arbitrary prop weaponization), runtime hot-plugging,
netfox, plugin-owned movement, and local damage truth remain explicitly
deferred.

## Migration Ledger

This ledger records the baseline before the unified action-foundation Tasks
1-5 migration. `migrate` means the reference remains present only until its
listed owner consumes it; it does not authorize a second world-motion writer.

| reference | kind | status | migration_owner | notes |
| --- | --- | --- | --- | --- |
| `scripts/character/CharacterMotor.gd` | active writer | retain | `CharacterMotor` | Existing PlayerShell velocity, gravity, facing, collision and slide owner. |
| `scripts/player/PlayerShell.gd` | actor scene host | retain | `CharacterMotor` | Human input ingress; it must not write body motion. |
| `scripts/character/CharacterReplica.gd` | legacy writer / actor host | migrate | `ActorActionArbiter -> MotionContributionComposer -> CharacterMotor` | Baseline contains direct `global_position` patrol and pose-sync writes; Task 4 removes them. |
| `scenes/phase0/PlayerShell.tscn` | active scene | retain | `CharacterMotor` | One CharacterBody3D and one Motor mount. |
| `scenes/phase0/CharacterReplica.tscn` | active scene | migrate | `CharacterMotor` | Converted to one CharacterBody3D control path in Task 4. |
| `GenericRoleSkin` / `KnightRoleSkin` | presentation binding | retain | `RolePresentationAdapter` (future task) | Clip/root sampling is presentation input only. |
| `backend/app/services/embodied_execution_ingress.py` | backend embodiment route | retain | `ESM/Gameplay/Composite` | Compatibility route remains outside local world-truth settlement. |
