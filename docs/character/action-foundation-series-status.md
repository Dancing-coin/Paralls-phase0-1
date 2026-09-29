# Action Foundation Series Status

Date: 2026-09-30

Status: **CharacterReplica retirement is complete; repository-wide Task 9 remains blocked**

The formal acceptance scene for this series is `scenes/phase0/StreetCombatDemo.tscn`
with the three qualified packages `female_bandage_external`, `female_jk_external`,
and `female_t_external`. `UnifiedCharacterActionFoundation.tscn` remains a narrow
protocol/authority probe only and is not an action-foundation acceptance scene.

The series entry point is the design spec
`docs/superpowers/specs/2026-09-28-character-action-foundation-series-completion-design.md`.
The corresponding implementation plan is the only execution order for the
remaining series work. The 2026-09-14 plans remain upstream contract references
and the June plans remain historical or transitional migration records.

## Controlling Documents

| Layer | Document | Status |
|---|---|---|
| Design | `docs/superpowers/specs/2026-09-29-character-replica-retirement-and-global-action-foundation-closure-design.md` | active CharacterReplica retirement and action-foundation closure spec |
| Execution | `docs/superpowers/plans/2026-09-29-character-replica-retirement-and-global-action-foundation-closure-implementation-plan.md` | **Task 8 complete; Task 9 remains blocked by repository-wide and Phase 0 runtime gates** |
| Pilot record | `docs/superpowers/plans/2026-09-28-streetdemo-mode-action-foundation-improvement-plan.md` | historical Task 1-9 implementation record |
| Operator index | `docs/character/character-action-foundation-operator-guide-and-index.md` | synchronized for StreetCombatDemo acceptance |
| Current-state ledger | `docs/character/character-action-foundation-current-state.md` | synchronized with fresh evidence |
| Replica record | `docs/character/character-replica-convergence.md` | CharacterReplica shell and obsolete validation scenes deleted after zero-caller proof |
| Repository index | `docs/INDEX.md` | links and acceptance boundary updated |

## Task 1-10 Matrix

| Task | Status | Owner | Verification command | Fresh evidence | Remaining risk |
|---|---|---|---|---|---|
| 1 baseline/caller matrix | complete | Character runtime | `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py` | focused suite: 32 passed; `docs/character/action-foundation-series-baseline-2026-09-28.md` | non-StreetDemo compatibility callers remain inventoried |
| 2 semantic intent | complete | `CharacterControllerPort` / `CharacterActor` | focused action-foundation pytest | same focused suite, intent normalization and digest assertions | legacy callers still exist outside the migrated street path |
| 3 animation owner | complete | `RoleAnimationController` | `PARALLS_STREET_PROBE=3` on `StreetCombatDemo.tscn` | external temp `paralls-streetdemo-task9-probes-*/probe-3.log`; run/recovery/cancel/guard/fallback all true | imported clips remain package-qualified full-body realizations |
| 4 Motor ownership | complete | `CharacterMotor` | `PARALLS_STREET_PROBE=4` on `StreetCombatDemo.tscn` | external temp `paralls-streetdemo-task9-probes-*/probe-4.log`; floor/wall/jump/airborne/owner all true | universal non-StreetDemo caller audit is still a main-plan concern |
| 5 action authority | complete for StreetDemo | `ActorActionArbiter` + backend authority | `python scripts/verification/harness.py --profile street-combat` | exported run `paralls-streetdemo-task9-final-c0c28c9c23464ef793fa54d2edb26bbe`; player/agent hit, duplicate, stale, recovery, sword all true | generic repository-wide ActionAttempt closure is outside this plan |
| 6 CharacterActor migration | complete for StreetDemo | `CharacterActor` | StreetDemo probes plus `character-agent-execution` profile | `probe-5.log`; exported agent run `paralls-streetdemo-agent-task9-rerun-b7a4621492294aabb074dc093504fab4`; StreetDemo retirement counts all zero; ArchiveDoor external profile `D:\Task9Evidence-20260929-08\archive-door` passed all four scenarios | old compatibility callers remain elsewhere |
| 7 registry admission | complete for StreetDemo | `CharacterEmbodimentAssetRegistry` | `CharacterAssetAdmissionProgressiveProbe.gd` | external temp `paralls-streetdemo-registry-task9-097fdff850e740449d93c8f0cd59e4f7`; 3 packages/6 actions, fail-closed checks true | no claim for unqualified packages outside the three street packages |
| 8 root/capability boundary | complete as temporary policy | `RootMotionSampler` / `MotionContributionComposer` / `CharacterMotor` | `PARALLS_STREET_PROBE=6` on `StreetCombatDemo.tscn` | `probe-6.log`; 3 hold profiles, zero-envelope, drive boundary true | calibration is not complete; `drive_locomotion` remains disabled |
| 9 publish/close gates | **blocked** | runtime owner + Harness | focused pytest, required Harness profiles, full pytest | focused closure suite `38 passed`; `street-combat`, `character-agent-execution`, and `character-replica-retirement` passed with explicit Godot; full pytest `7652 passed / 56 failed / 2 skipped / 103 warnings`; `--profile all` reached `phase0` but its MainDemo autotest remained on repeated `backend_closed` markers without completion | repository-wide suite and Phase 0 aggregate gate remain red |
| 10 documentation reconciliation and publication | **complete, affected by Task 9 external blocker** | documentation owners | documentation link checks, focused tests, Godot headless probe, `git diff --check` | Task 10 checklist completed in the 2026-09-28 implementation plan; current-state, operator guide, replica convergence, index, and status surfaces synchronized | release claim remains constrained by Task 9's repository-wide pytest failures |

## 2026-09-30 CharacterReplica retirement closure

Task 8 deleted the compatibility shell and obsolete validation scenes after a
fresh zero-caller probe. The retirement profile passed with
`active_scene_instances=0`, `runtime_replica_lookups=0`,
`compatibility_call_count=0`, `direct_body_writers_outside_motor=0`, and
`direct_animation_writers_outside_controller=0`. The actor-only source tree
also passes the Godot resource-path check.

Fresh runtime evidence:

- `D:\CurrentActionFoundationEvidence-street-task9-final` — `street-combat` passed.
- `D:\CurrentActionFoundationEvidence-agent-task9-final` — `character-agent-execution` passed.
- `D:\CurrentActionFoundationEvidence-retirement-task9-final` — retirement profile passed; source digest `330e10093158228d41213142f6933a43ef991a2a0b8bbc8f499ba34313ec2f5b`.
- `D:\CurrentActionFoundationEvidence-pytest-final.stdout.log` — full pytest: `7652 passed, 56 failed, 2 skipped, 103 warnings`.

The aggregate `--profile all` run reached `phase0`, where the MainDemo
autotest emitted repeated `backend_closed` markers and never emitted
`phase0_autotest_complete` before the run was stopped. This remains an open
runtime gate. Diagnostic copies are retained in
`D:\CurrentActionFoundationEvidence-all-final5`; StreetCombatDemo success is
not promoted to a repository-wide completion claim.

## 2026-09-29 Ordered Task 1-15 Verification

The 2026-09-14 master plan was rechecked in strict Task 1 → Task 15 order.
Focused contract gates passed for Tasks 1-3 and 6-14; Task 5 retains one
pre-existing static compatibility failure in
`test_character_replica_camera_switch_is_presentation_only`. Task 4's focused
tests passed, while `godot-project` reported missing scene resource paths.
Task 13's unified profile passed with the explicit Godot executable after an
initial environment-blocked invocation without `GODOT_EXE`.

Task 15 release verification passed and confirmed Mode B with Mode C disabled.
The earlier full pytest result and aggregate report remain historical relative
to the fresh 2026-09-30 closure run above.
The final `--profile all` run exported to
`D:\Task1-15Evidence-20260929-final-all-1915` and failed only at
`godot-project: scene_resource_paths_exist=missing`; cleanup passed.

## Remaining gap table

| Remaining issue | Code owner | Spec section | Plan task | Verification command | Completion evidence |
|---|---|---|---|---|---|
| Calibrated root-motion locomotion and universal Motor ownership | `CharacterMotor`, `MotionContributionComposer`, active NPC/agent callers | spec §4 阶段 2、§4 阶段 6、§6.4 | Tasks 3-4 | `RootMotionQualificationProbe.gd`; `CharacterMotorOwnershipProbe.gd`; `python scripts/verification/harness.py --profile godot-project` | measured walking/running profiles, one body writer, and fresh StreetCombatDemo runtime logs |
| CharacterReplica retirement outside StreetCombatDemo | `CharacterActor`, active scenes and bridges | spec §4 阶段 4、§5 | Task 8 | `character-replica-retirement` profile; active-caller inventory test | zero active scene/script callers, shell deletion, and actor-only source tree |
| Descriptor admission and deterministic arbitration | `ActorActionArbiter`, `CharacterActionAssetRegistry`, `CharacterRuntimeState` | spec §3、§4 阶段 3、§6.1-§6.2 | Task 6 | `python -m pytest backend/tests/test_character_action_descriptor_runtime.py -q` | raw clip rejection, claims/lock/cancel/death ordering evidence |
| Generic ActionAttempt authority and Mode B recovery | Street combat coordinator, ESM/Gameplay route, `BackendBridge` | spec §4 阶段 6、§6.3、§6.5 | Task 7 | `StreetActionAttemptProbe.gd`; focused backend authority tests; `street-combat` profile | marker + Motor evidence, idempotency, stale revision zero-write, reconnect epoch/resync evidence |
| Registry-only asset admission and fallback diagnostics | `CharacterEmbodimentAssetRegistry`, active manifests, street skin | spec §4 阶段 5、§6.4 | Task 8 | `CharacterAssetAdmissionProbe.gd`; `python -m pytest backend/tests/test_character_asset_admission_runtime.py -q` | digest/mapping/marker/root-profile admission report and fail-closed cases |
| Deterministic replay evidence and final repository gate | verification probes, Harness metadata, documentation owners | spec §6.5、§8 | Task 9 | `CharacterActionFoundationRuntimeProbe.gd`; `python scripts/verification/harness.py --profile all`; `python -m pytest -v` | fresh replay comparison, exported summaries, and a green aggregate run |

## Runtime Boundary

```text
Player / Agent / Program
  -> CharacterControllerPort
  -> CharacterControlIntent / CharacterActor
  -> ActorActionArbiter
  -> RoleAnimationController + MotionContributionComposer
  -> CharacterMotor (唯一身体运动与 move_and_slide owner)
```

Authority results may update projection and recovery. They do not let local
scene code declare hit, damage, ammo, projectile, inventory, or world truth.
`CharacterActor` is the sole runtime host. The retired `CharacterReplica`
forwarding shell is no longer present and cannot become a second controller,
Motor, animation owner, authority writer, or weapon scheduler.

## Closure blockers

1. **External ArchiveDoor dependency (owner: character-turn continuity plan):**
   resolved for this gate. The live transport test placed the actor outside the
   authority range; correcting its fixture made that regression green. The
   Godot host then proved a reversed forced-motion Z conversion, fixed with a
   red/green contract test. Fresh `character-turn-embodied-episode` evidence
   proves success, distance failure, revision failure, and stance failure.
2. **Full repository pytest (owner: repository maintainers):** the fresh run
   ends `7652 passed, 56 failed, 2 skipped, 103 warnings`. The failures include
   obsolete CharacterReplica contract tests plus unrelated runtime/integration
   regressions; they remain open and are not masked by the green StreetCombatDemo
   profile.
3. Root motion is intentionally `hold` / zero-envelope. This is a temporary
   qualified capability boundary, not calibrated production locomotion.

The StreetCombatDemo runtime profile is fresh green evidence for the StreetDemo
pilot and migration gates; it is not a claim that the entire unified character
action-foundation series is complete. Task 9 remains **blocked** pending the
repository-wide pytest gate and the Phase 0 MainDemo runtime gate.

## Historical and transitional document rule

June actor, agent, root-motion, and pre-convergence documents are retained for
migration context only. They must be read as historical or transitional when
they describe `CharacterReplica`, direct skin movement, or an older execution
order. New work starts at the 2026-09-28 spec and follows its implementation
plan.
