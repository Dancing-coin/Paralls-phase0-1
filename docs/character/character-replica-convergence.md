# CharacterReplica convergence

`CharacterActor` is now the sole active runtime host. All scenes, providers, bridges, player paths, interaction hosts, agents, and verifiers resolve actor capabilities directly. `CharacterReplica` remains only as a transitional compatibility shell pending Task 8 deletion review; it has zero active callers.

This document records the transitional shell during the 2026-09-28 action
foundation migration. June actor plans and pre-convergence descriptions are
historical context; they do not authorize a second controller, animation
owner, Motor, or authority writer.

## Runtime ownership

- `CharacterActor` owns actor identity, backend ingress, intent arbitration, patrol/player command construction, and presentation binding.
- `CharacterMotor` is the only body movement owner. It applies facing, acceleration, gravity, root-motion contribution, collision response, and `move_and_slide()`.
- `RoleAnimationController` adapts imported GLB clips to an external-controller style state machine. It creates `Idle`, `Walk`, `Run`, `Jump`, `Boxing`, and `SwordAttack` states when the package does not already provide an `AnimationTree`, then uses cross-fade transitions.
- `RootMotionSampler` samples `rig/Skeleton3D:root` position tracks and returns each delta once. It never writes a transform.
- `StreetCharacterSkin` binds a real street GLB to those two components, preserves manifest aliases, loops idle/walk/run, and keeps jump/attack one-shot.

## Root-motion rule

StreetDemo currently uses the qualified temporary `root_motion_policy=hold` and
zero-envelope profile. `RootMotionSampler` can discover and consume a root delta
once, but no package is admitted to `drive_locomotion` until direction,
distance, period, envelope, support, wall, slope, and stop/restart calibration
is complete. `CharacterMotor` remains the only consumer, so a future enabled
profile cannot double-apply lease velocity and root contribution.

## Compatibility and rollback

The old files are backed up outside the repository at:

`C:\Users\User\AppData\Local\Temp\paralls-character-replica-backup-20260927`

To roll back manually, copy the backed-up files back over the matching repository paths. The backup includes the original actor script, scene, motor, street skin, demo scene, manifests/descriptors, generic skin, and motion composer.

## Acceptance surface

Use `scenes/phase0/StreetCombatDemo.tscn` with the three imported street
characters for action-foundation acceptance. `UnifiedCharacterActionFoundation.tscn`,
`Unified3DIntegrationValidation.tscn`, and greybox fallbacks are compatibility
or protocol probes only; they are not the animation or action-base quality gate.

The fresh StreetDemo evidence records live environment/collision/navigation,
three qualified character packages, semantic animation recovery, Motor
ownership, Registry fail-closed admission, and Mode B authority outcomes. The
ArchiveDoor shutdown blocker and repository-wide compatibility callers remain
outside the StreetDemo retirement claim.
