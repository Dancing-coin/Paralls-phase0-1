# Character Runtime Design Drift Audit

Date: `2026-09-14`

Status: `audit baseline; runtime convergence incomplete`

## Executive Verdict

The repository's target architecture is internally coherent, but the current
runtime is not yet a single action-foundation path. The design can satisfy the
product requirement—external rigged assets become playable by player, NPC,
CharacterAgent, and INF-connected flows—only after the actor host, action
arbitration, and authority-result projection are converged in code.

The current implementation is best described as:

```text
player: CharacterBody3D -> CharacterMotor -> visual replica
NPC:    CharacterReplica(Node3D) -> direct coordinate stepping
agent:  L4 execution plan -> compatibility command -> CharacterReplica
action: reviewed asset registry + local controller phases + model-specific skin
INF:    backend contracts/projections plus proposal metadata, not a world-truth writer
```

The INF ownership question is therefore a contract interpretation issue, not
evidence of a second implemented writer: `GovernedAuthorityContractCatalog`
admits/reads registered contracts, while the L4 adapter explicitly builds an
envelope and leaves writes to gameplay authorities. The existing embodied
settlement service is still a compatibility path until the canonical
`ActionAttempt` route is implemented.

This is a real, tested transitional runtime—not a finished unified action
substrate.

## Ownership And Contract Closure (Document Revision)

The review found a documentation-level ambiguity rather than an implemented
INF writer: `inf:<contract_ref>` is a governed contract namespace/catalog
reference, not a generic authority route. The canonical Phase 1 consequence
owners are ESM, Gameplay, and registered Composite coordinators. CharacterAgent,
INF, and Siming can emit proposals, context, evidence, constraints, catalysts,
and metadata, and can consume committed projections; they cannot emit an
`AuthorityResult` or settle world facts.

The following contract corrections are now normative across the 2026-09-14
spec/plan set:

- `ActionAttempt` has one shared field set, with audit-only `submitted_at`
  excluded from `canonical_payload()` and server-issued `owner_contract_ref`.
- Marker observation precedes Motor execution; same-tick
  `PhysicsContactEvidence(T)` is joined before a contact-dependent
  `ActionAttempt(T)` is emitted.
- `ActionAttempt` and evidence arrays have explicit size/count limits and
  reject with `payload_limit_exceeded` rather than truncating.
- Canonical resource IDs use `world_motion`, `pelvis`, `upper_body`, and the
  declared arm/leg/hand descendants. Legacy aliases such as `movement` and
  `*_chain` are not runtime claim IDs.
- Mode B is named `runtime_correction`; Mode C reserves `body_correction` for a
  separately owned `PhysicalAuthority` stream.
- The shared-contract plan owns tags, claims, arbitration, Motor composition,
  and tools. The unified plan alone owns the CharacterAgent/INF/Siming bridge.
  Existing runtime paths are named by their real files; planned new services
  are explicitly marked `Create`.
- Runtime asset packages use `assets/active/<package_id>/`; `assets/characters/`
  is authoring/provenance/report space only.

## Requirement Fit

| Requirement | Design fit | Current implementation | Blocking gap |
| --- | --- | --- | --- |
| Import external rigged model and animations | Yes | Partial | Qualification and retargeted runtime admission are incomplete; default bindings are empty and preserved knight assets are not qualified. |
| Same body for player and NPC | Yes | No | Player is `CharacterBody3D`; `CharacterReplica` is `Node3D` and still directly changes `global_position`. |
| Same body for CharacterAgent | Yes | Partial | Agent reaches `CharacterReplica`, but movement still follows its autonomous direct-step path rather than the shared Motor path. |
| Action state and locomotion arbitration | Yes | Partial | `EmbodiedActionController` exists, but no single coordinator owns parallel layers, priority, occupancy, cancellation, and death override. |
| Phase 1 weapon slice | Yes | No | Equipment/inventory fragments and `KnightCombatModifier` do not yet provide a generic held-item binding, melee `ActionAttempt` route, or hitscan semantic route. |
| Animation drives visible action | Yes | Partial | Knight clip map/timers and reviewed atom playback exist; generic skin is a fallback and external clip contract is not enforced. |
| Root motion remains safe | Yes | No | Knight samples root motion, but `CharacterReplica` applies deltas directly; Motor is not the universal consumer. |
| INF/Agent semantic intent reaches action runtime | Yes | Partial | L4 emits plans, channels, and realization metadata; adapter still maps many intents to legacy commands and no namespaced tag contract is enforced. |
| INF/Gameplay owns hit/damage/death | Yes, with corrected ownership | Mostly | ESM/Gameplay/Composite own settlement; INF only proposes/consumes projections. No universal local action-attempt settlement path is implemented yet. |
| Multiple assets share action library | Yes | Not proven | Existing descriptor/registry is narrow and model-specific mappings remain; two qualified external characters are not verified. |
| Physics contribution and contact boundary | Yes, after the 2026-09-14 revision | No | Root motion and direct NPC stepping are not yet normalized into a collision-aware Motor command; local contact evidence is not yet a universal ESM validation input. |
| Connected action authority | Partial | Partial | Gameplay mirror/prediction transport exists, but action-attempt transport and a physical body snapshot/correction stream are not yet implemented. |
| Multiplayer physical authority | Deferred by design | No | No fixed-tick physical authority owner has been selected; the current backend ESM authority is not a rigid-body simulation server. |

## Runtime Evidence Map

### Godot actor and movement

- `scenes/phase0/PlayerShell.tscn` is a `CharacterBody3D` with a
  `CharacterMotor` child.
- `scripts/character/CharacterMotor.gd` owns the current player
  `move_and_slide()` call and reads normalized intent fields.
- `scenes/phase0/CharacterReplica.tscn` is a `Node3D`, not a
  `CharacterBody3D`; it contains a Motor node but its autonomous path remains
  in `CharacterReplica.gd`.
- `scripts/character/CharacterReplica.gd` still contains direct
  `global_position +=` steps and runs that path from `_process`, not a unified
  Motor tick.
- Player visual synchronization still writes the replica transform from the
  outer shell, so the player body and visible actor are not yet one physical
  host.

### CharacterAgent L4

- `CharacterAgentL4Executor` produces five-channel presentation data,
  `actor_control_frames`, `action_request_bundle`, composite action proposals,
  and skill realization metadata.
- `CharacterAgentL4Adapter` converts execution plans into compatibility
  `CharacterGoalCommand` values and legacy command types such as `approach`,
  `speak`, and `observe`.
- `AgentControllerAdapter` can normalize a candidate into an actor intent
  frame, but the live `CharacterReplica` execution handler still resolves
  targets and calls `set_move_target`/`set_look_target`, which enter the direct
  movement path.
- The current L4 path is therefore execution-plan-first in backend semantics,
  but not yet single-path in local embodiment.

### Action assets and animation

- `CharacterActionAssetDescriptor.gd` currently normalizes a small descriptor:
  `action_tag`, `animation_clip_ref`, root-motion profile, modifier profile,
  equipment override, required slots, and compatibility level.
- `CharacterEmbodimentAssetRegistry.gd` resolves reviewed action atoms and
  missing-asset failures; it is a valid transitional registry, not yet a full
  imported-asset qualification pipeline.
- `EmbodiedActionController` owns local target/navigation/alignment/contact/
  recovery phases and does not settle authority results.
- `KnightRoleSkin.gd` uses hardcoded clip maps, timer-driven sword/shield
  overlays, skeleton-name resolution, and root-motion sampling.
- `GenericRoleSkin.gd` is a greybox fallback; its reviewed-action method
  changes state but does not play imported animation clips.

### INF, Gameplay, and status

- Gameplay already has bounded authority/replay implementations for body
  resources, status tags, effective stats, abilities, and skill-action gates.
- `StatusTagRegistry` and related projectors are backend-owned and replayable;
  they are not the same thing as local `action:*` or `phase:*` tags.
- CharacterAgent already carries goals, evidence, primitive action tags,
  realization metadata, and Siming catalyst inputs.
- There is no single typed contract that maps these backend semantic values to
  actor-layer tags, occupancy, action phase, and presentation cues.

## Design Contradictions And Drift Risks

1. **Host contradiction:** actor docs describe one shared actor substrate,
   while `CharacterReplica` remains `Node3D` and direct-steps.
2. **L4 contradiction:** agent docs describe shared actor ingress, while live
   agent execution still enters a legacy target/movement path.
3. **Action descriptor drift:** the 2026-09-14 contract requires clips,
   cancel windows, contact markers, and root-motion policy, while the current
   GDScript descriptor only normalizes a narrower legacy shape.
4. **State-machine drift:** `EmbodiedActionController` is a real interaction
   FSM, but the proposed parallel-layer coordinator is not implemented; adding
   another independent FSM would create conflicting action truth.
5. **Tag drift:** `active_goal_tags`, `evidence_tags`,
   `primitive_action_tags`, `status_tags`, `expression:*`, and `semantic_tags`
   exist without one enforced namespace/source/lifecycle contract.
6. **Authority drift risk:** local action timing and root motion are available,
   but contact-to-authority-result projection is not a universal runtime path.
7. **Asset-readiness drift:** asset integration docs describe binding profiles,
   but the default binding manifest and qualification evidence do not yet prove
   multiple playable external characters.
8. **Physics-contract gap:** the target now names Motor as the sole local
   collision executor, but the runtime still mixes CharacterBody3D movement,
   CharacterReplica direct stepping, and sampled root-motion paths. There is no
   universal `MotionContribution -> PhysicsMotionCommand -> Motor` contract,
   nor a typed separation between local `PhysicsContactEvidence` and a semantic
   ESM/Gameplay consequence.
9. **ESM settlement gap:** ESM/Gameplay authority, idempotency, revisions, and
   mirror projection exist in bounded domains, but the canonical `ActionAttempt`
   bridge is not yet implemented universally. The new contract now fixes its
   fields, idempotency treatment of `submitted_at`, owner-bound route, and
   evidence limits. A local contact or animation marker must not be treated as
   a settled world action.
10. **Network physical-authority gap:** the repository has Gameplay mirror
    snapshot/delta, prediction, delivery sequence, connection epoch, and
    resync primitives. These are not a multiplayer body replication protocol.
    No fixed-tick physical authority, body revision, correction stream, or
    owner has been selected; therefore the current design supports connected
    semantic authority plus local embodiment, not completed multiplayer
    authoritative physics.
11. **Weapon-slice gap:** the design now requires only a bounded equipment /
    melee / hitscan seam in Phase 1, but no runtime implementation or evidence
    currently proves that seam. Complete weapon gameplay must remain deferred.

## Canonical Document Hierarchy

To prevent further drift, use this ownership order:

1. `docs/superpowers/specs/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-design.md`
   owns cross-cutting action, tag, asset, Motor, and INF/Agent contracts.
2. `docs/character/character-actor-final-convergence-target.md` and
   `docs/superpowers/specs/2026-06-15-character-actor-architecture-optimization-design.md`
   own shared actor-host and presentation-layer boundaries.
3. `docs/superpowers/specs/2026-06-24-character-agent-stage2-design.md` and
   the CharacterAgent plans own cognition, profile, memory, L2/L3, and L4
   semantic planning—not Godot movement.
4. Gameplay/INF module docs and their focused specs own status, capability,
   affordance, consequence, event-store, revision, privacy, and replay truth.
5. `2026-08-01-atomic-action-library-and-default-scene-coverage-*` owns
   reviewed interaction atoms and scene affordance coverage.
6. Plans describe execution order only. They must link to the controlling spec
   and must not redefine ownership in prose.
7. This audit and `character-action-foundation-current-state.md` record current
   facts and blockers; they never promote planned work to implemented status.

## Required Reconciliation Order

1. Convert `CharacterReplica` into the shared physical Actor host or replace
   it with an equivalent `CharacterBody3D`; remove direct autonomous
   coordinate stepping.
2. Make every CharacterAgent/INF/program output enter the same coordinator and
   `CharacterIntentFrame` path; retain compatibility commands only at the
   boundary.
3. Preserve `EmbodiedActionController` as the phase executor and add one
   arbitration owner rather than a second action FSM.
4. Expand the existing descriptor/registry in place to validate imported clips,
   slots, markers, cancellation, and root-motion requirements.
5. Route root-motion deltas through Motor and project authority results back to
   runtime state.
6. Separate local physics contact evidence from ESM/Gameplay settlement and
   map `ActionAttempt` to existing embodied, action-window, and Gameplay
   authority commands with idempotency and revision checks.
7. Define the connected body-stream contract separately from Gameplay mirror;
   do not enable multiplayer physics until a fixed-tick physical authority is
   chosen and verified.
8. Qualify at least two external characters and record real Godot + backend
   evidence.
9. Add the bounded weapon slice on the same claims/Motor/ActionAttempt path;
   do not introduce a parallel weapon scheduler.
10. Only then mark final actor/L4 convergence complete in migration ledgers.

## Current Conclusion

The design is sufficient as a target, but not sufficient as a claim about the
current runtime. The project should not start another feature layer or plugin
integration until the reconciliation order above is reflected consistently in
code, focused specs, plans, and Harness evidence.

## Task 1 Baseline (2026-09-15)

Before this implementation pass, `CharacterActionAssetDescriptor` preserves
the reserved `atomic_sequence` field but the runtime has no unified
tag/proposal/arbitration/Motor/authority contract. Existing local playback is
presentation-only until it enters the shared action path. The baseline writer
audit records `CharacterReplica` direct coordinate stepping as `migrate`; it
must be removed by Task 4 rather than treated as an approved compatibility
writer.
