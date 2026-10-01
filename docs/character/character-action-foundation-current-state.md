# Character Action Foundation Current State

Date: `2026-10-01`

Status: `CharacterReplica retired; Task 9 remains blocked by strict Phase 0 runtime`

The 2026-09-28 pilot is landed as a StreetCombatDemo result. This ledger keeps
the pilot evidence separate from the remaining series gates. The 2026-09-29
retirement/closure spec is the series entry point and its implementation plan is the only
execution order for the open tasks; June and pre-convergence passages below are
historical or transitional when explicitly marked.

## 2026-09-29 StreetCombatDemo acceptance reconciliation

The formal action-foundation acceptance scene is now the real
`scenes/phase0/StreetCombatDemo.tscn` street environment. The accepted runtime
packages are `female_bandage_external`, `female_jk_external`, and
`female_t_external`, all admitted through `CharacterEmbodimentAssetRegistry`.
`UnifiedCharacterActionFoundation.tscn` is retained only as a narrow
protocol/authority probe and is not an acceptance basis.

Tasks 1-8 have fresh focused or runtime evidence. Task 9 has a fresh gate
matrix and Harness audit. The StreetCombatDemo profile is green with live
backend evidence for player and agent authority, duplicate replay, stale
revision rejection, recovery, and sword action. The StreetDemo animation,
Motor, Replica retirement, Registry, and root capability probes are also fresh
green. Root motion remains the temporary `hold` / zero-envelope policy; it is
not calibrated production locomotion.

The external ArchiveDoor dependency now has fresh success, distance, revision,
and stance evidence from live backend and Godot. The current full verification
is `7741 passed, 2 skipped, 104 warnings`. Fresh street, agent, and retirement
profiles pass. The latest aggregate run
`D:\HarnessEvidence\paralls-20261001-8c5631-all` passed every profile except
strict `phase0`; cleanup passed. The strict Phase 0 gate still lacks dialogue,
transport, interaction, voice, repeatable-run, and five Observatory Siming
markers: state payloads, selected-actor summary, bottom strip, timeline, and
ledger pressure. Player root-motion and forward-direction probes are proved,
but root motion remains hold/zero-envelope pending real calibration.

### Final boundary

`Player`, `Agent`, and `Program` proposals enter through
`CharacterControllerPort`, normalize into `CharacterControlIntent`, and pass
through `CharacterActor` and `ActorActionArbiter`. Presentation and motion are
then owned by `RoleAnimationController` and `MotionContributionComposer`, with
`CharacterMotor` as the only body movement, collision, root-consumption, and
`move_and_slide()` owner. Authority results can update projection and recovery;
local callers cannot declare hit, damage, ammo, projectile, inventory, or world
truth. `CharacterActor` is the sole active runtime host. The zero-caller gate passed
and the `CharacterReplica` compatibility shell plus obsolete validation scenes
were deleted in Task 8.

The generic ActionAttempt authority route and Mode B recovery remain bounded/open
outside the StreetCombatDemo pilot. Pilot evidence is retained as an acceptance
slice and does not establish repository-wide authority closure.

## 2026-09-28 Series Reconciliation

The StreetCombatDemo pilot is now a landed animation-layer result: all three
real street packages bind to the external-controller-style AnimationTree and
pass idle/walk/run/jump/boxing/sword state and recovery checks. This closes the
animation pilot only. It does not claim calibrated root-motion locomotion,
universal NPC/agent Motor routing, final ActionAttempt authority closure, or
complete registry admission.

The controlling completion documents are:

- `docs/superpowers/specs/2026-09-29-character-replica-retirement-and-global-action-foundation-closure-design.md`
- `docs/superpowers/plans/2026-09-29-character-replica-retirement-and-global-action-foundation-closure-implementation-plan.md`
- `docs/character/action-foundation-series-status.md`

The external controller is the animation implementation layer. It is not a
replacement for the actor runtime, action arbiter, Motor, or authority owner.

For the broader cross-document reconciliation and source-of-truth hierarchy,
see `docs/character/character-runtime-design-drift-audit.md`.

## Executive Finding

Release-gate boundary: Godot owns local embodiment/presentation through one
`CharacterMotor`; backend ESM/Gameplay/composite owns semantic authority and
committed `ActionAttempt` results. The connected transport is Mode B only;
Mode C body streaming, rollback, raw-pose replication, and authoritative
multiplayer physics remain disabled.

### Historical mainline runtime evidence (not the current task counter)

The following Task 14 evidence belongs to the earlier unified mainline record;
it is retained for dependency context and does not close the current series:

- `.harness/verification/unified-character-action-foundation-runtime.json`
- `.harness/verification/unified-character-action-foundation-runtime-verifier.json`
- `.harness/verification/unified-character-action-foundation-godot.log`

The run starts a real backend and Godot headless scene, mounts
`female_jk_external` and `female_t_external`, moves both actors through their
`CharacterMotor`, and records Agent/INF semantic intent, ESM melee commit,
Gameplay semantic hitscan commit, duplicate replay, stale revision rejection,
and client-truth rejection. It proves Mode B only; it does not claim
rollback, raw-pose replication, or authoritative multiplayer physics.

The repository has a formally correct shared-actor direction, but the action
foundation is not yet a single coherent runtime. Player locomotion already
uses `CharacterControllerPort -> CharacterMotor`; NPC embodiment still has a
direct-coordinate path, and action/presentation state is partly model-specific.

## 2026-09-23 Character-Turn Prerequisite Gate

The character-turn continuity implementation has closed its two latest
continuity regressions, but its dependency gate is currently **conditional**:
the fresh archive-door success scenario and repository-wide verification remain
red. It does **not** mean that the unified action-foundation Tasks 1-15 are
already implemented or that the repository has a globally green aggregate run.
The controlling plan and its consumer order are:

- `docs/superpowers/plans/2026-09-23-character-turn-continuity-and-embodied-episode-implementation-plan.md`
- `docs/superpowers/plans/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-implementation-plan.md`

`CharacterTurnContext` is the canonical live turn from before L1 through
settlement, evaluation, policy, and checkpoint/recovery. Completed behavior-turn
records are completed audit/projection evidence; current behavior-turn records
are views of that active context; legacy behavior-turn records remain read-only
compatibility inputs and cannot start, dispatch, or settle a live turn.

The action-foundation consumers are fixed: `CharacterExecutionContract` feeds
Task 9 semantic ingress; `turn_id`, revision, causation/correlation, and
idempotency feed Task 10 `ActionAttempt`/`AuthorityResult`; typed recovery feeds
the local and transport recovery work and, together with local/authority/
post-observation episode evidence, feeds Tasks 13 and 14 replay and runtime
proof.

`CharacterAgentL4Adapter` remains a one-way legacy compatibility translator,
not an execution or settlement owner. VLA/provider output remains advisory; it
can nominate an actor intent candidate but cannot control a body, Motor, pose,
or authority/world truth. Likewise, an episode is not authority truth: only
ESM, Gameplay, or a registered Composite owner can commit the corresponding
world state.

### Gate evidence and remaining exclusions

The complete archive-door physical-embodiment proof was run with:

```powershell
python scripts/verification/verify_obj_archive_door_physical_embodiment.py `
  --godot-exe 'D:\godot\Godot_v4.6.3-stable_win64.exe' `
  --python-exe 'C:\Anaconda3\python.exe'
```

It passed all four live-boundary scenarios (`success`, `distance_failure`,
`revision_failure`, and `stance_failure`). The primary result is
`.harness/verification/obj-archive-door-physical-embodiment-report.json`; the
linked runtime, backend-settlement, replay, screenshot, and Godot-log evidence
is stored beside it under `.harness/verification/`.

The designated predecessor profile was then run with:

```powershell
python scripts/verification/verify_character_turn_embodied_episode.py
```

The preceding designated run returned `overall_passed=True`, but the fresh
2026-09-24 rerun returned `overall_passed=False`: the archive-door `success`
scenario has `wrong_scene`, missing live-backend/replay evidence, and no open
settlement. Its parent report is
`.harness/verification/character-turn-embodied-episode-report.json`. This is
an active blocker, so the former successful report is historical evidence only.

The focused continuity-contract suite was:

```powershell
python -m pytest backend/tests/test_character_turn_context.py backend/tests/test_character_turn_coordinator.py backend/tests/test_character_turn_recovery.py backend/tests/test_behavior_policy_lifecycle.py backend/tests/test_character_behavior_evaluation.py backend/tests/test_character_semantic_recall.py backend/tests/test_character_execution_contract.py backend/tests/test_embodied_episode_service.py backend/tests/test_vla_percept_bridge.py backend/tests/test_vla_runtime_consumption.py backend/tests/test_character_turn_embodied_episode.py -q
```

It returned `82 passed`. Together with the designated profile, this is the
evidence for the checked predecessor completion checklist; it is not a claim
that an unrelated full-repository regression is green.

The focused follow-up was:

```powershell
C:\Anaconda3\python.exe -m pytest backend/tests/test_obj_archive_door_embodied_local_static.py scripts/verification/tests/test_verify_obj_archive_door_physical_embodiment.py -q
D:\godot\Godot_v4.6.3-stable_win64.exe --headless --path . --editor --quit --rendering-method gl_compatibility
```

Both passed at this gate. A live external VLA provider credential is not
required for this evidence: the covered VLA/provider path is advisory-boundary
validation, while the door proof uses real local embodiment plus authority
settlement. External-asset qualification remains pending: the preserved knight
resources and the two external character packages still need the separate
qualified Skeleton3D/AnimationPlayer/action-clip evidence before the later
two-character foundation milestone can be claimed.

### Aggregate status recorded for Task 10

Task 10 documentation reconciliation is complete. Its checklist and status
surfaces are synchronized with the landed StreetCombatDemo pilot, the 2026-09-14
master-plan dependency map, and the remaining gap table. Task 9 remains blocked
by strict Phase 0 runtime evidence; that release blocker constrains the overall
action-foundation claim but does not reopen Task 10 documentation work.

The ordered Task 1 → Task 15 verification was rerun on 2026-09-29. Release
verification passed with Mode B and Mode C disabled. An older 2026-09-29 full pytest gate
completed with `7671 collected, 7621 passed, 48 failed, 2 skipped, 103
warnings`; that result is historical. The final Harness
`--profile all` export is `D:\Task1-15Evidence-20260929-final-all-1915`; docs,
boundaries, drift, and backend-contract passed, while `godot-project` failed
because `scene_resource_paths_exist=missing`. Harness cleanup passed.

The fresh required `python -m pytest -v` run is recorded in
`D:\CurrentActionFoundationEvidence-pytest-final2-20260930.stdout.log` and ended
with the prior baseline `7720 passed, 2 skipped, 103 warnings`; the current full
pytest verification is `7736 passed, 2 skipped, 104 warnings`. `git diff --check` is rerun after
the Task 9 documentation update below.

Accordingly, the dependency gate remains conditional on the strict Phase 0
aggregate runtime. It does not authorize a first-milestone completion claim
until that fresh runtime gate is green.

### Asset qualification clarification (2026-09-24)

The external-asset contract has been corrected to distinguish an authoring rig
from its deform skeleton and runtime canonical mapping. A source `.blend` may
contain controller, IK/FK, pole, twist, and reference bones. A T-pose is not
required, and deform-bone count is not a quality gate. Qualification instead
requires a reproducible declared rest pose, identified deform bones, complete
deform-to-canonical mapping, and a stable export/retarget boundary. This
clarification does not by itself qualify any package for runtime admission.

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

1. Non-StreetDemo compatibility callers still require migration audit. The
   pre-convergence baseline recorded direct `CharacterReplica` movement; the
   current StreetCombatDemo path has moved that behavior behind `CharacterActor`
   and `CharacterMotor`.
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
- `scripts/character/CharacterActor.gd` is the sole actor runtime host. The
  former `CharacterReplica` shell and validation scenes are deleted after the
  zero-caller proof; any remaining mentions in older documents are historical.
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

This ledger records the historical baseline before the unified action-foundation
Tasks 1-5 migration. `migrate` means the reference remains present only until
its listed owner consumes it; it does not authorize a second world-motion
writer. Current Task 1-9 status is maintained in
`docs/character/action-foundation-series-status.md`.

| reference | kind | status | migration_owner | notes |
| --- | --- | --- | --- | --- |
| `scripts/character/CharacterMotor.gd` | active writer | retain | `CharacterMotor` | Existing PlayerShell velocity, gravity, facing, collision and slide owner. |
| `scripts/player/PlayerShell.gd` | actor scene host | retain | `CharacterMotor` | Human input ingress; it must not write body motion. |
| `scripts/character/CharacterActor.gd` | active actor host | retain | `ActorActionArbiter -> MotionContributionComposer -> CharacterMotor` | Sole runtime host after the Task 8 zero-caller gate; historical CharacterReplica shell was deleted. |
| `scenes/phase0/PlayerShell.tscn` | active scene | retain | `CharacterMotor` | One CharacterBody3D and one Motor mount. |
| `scenes/phase0/CharacterActor.tscn` | active scene | retain | `CharacterMotor` | Actor-only scene with one CharacterBody3D control path. |
| `GenericRoleSkin` / `KnightRoleSkin` | presentation binding | retain | `RolePresentationAdapter` (future task) | Clip/root sampling is presentation input only. |
| `backend/app/services/embodied_execution_ingress.py` | backend embodiment route | retain | `ESM/Gameplay/Composite` | Compatibility route remains outside local world-truth settlement. |
