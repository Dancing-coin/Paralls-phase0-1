# CharacterReplica convergence

`CharacterReplica` remains in the scene only as a compatibility host. The runtime implementation now lives in `CharacterActor.gd`, while the legacy script forwards the public methods used by Phase 0, player shell sync, embodied interaction, and probes.

## Runtime ownership

- `CharacterActor` owns actor identity, backend ingress, intent arbitration, patrol/player command construction, and presentation binding.
- `CharacterMotor` is the only body movement owner. It applies facing, acceleration, gravity, root-motion contribution, collision response, and `move_and_slide()`.
- `RoleAnimationController` adapts imported GLB clips to an external-controller style state machine. It creates `Idle`, `Walk`, `Run`, `Jump`, `Boxing`, and `SwordAttack` states when the package does not already provide an `AnimationTree`, then uses cross-fade transitions.
- `RootMotionSampler` samples `rig/Skeleton3D:root` position tracks and returns each delta once. It never writes a transform.
- `StreetCharacterSkin` binds a real street GLB to those two components, preserves manifest aliases, loops idle/walk/run, and keeps jump/attack one-shot.

## Root-motion rule

Street locomotion defaults to in-place clips and physics velocity. When a qualified clip provides a root delta, the actor marks the command `root_motion_exclusive`; `CharacterMotor` suppresses equivalent locomotion velocity and applies the sampled delta once. This prevents the old failure where the body moved after the first walk cycle while the animation stopped or where velocity and root motion doubled each other.

## Compatibility and rollback

The old files are backed up outside the repository at:

`C:\Users\User\AppData\Local\Temp\paralls-character-replica-backup-20260927`

To roll back manually, copy the backed-up files back over the matching repository paths. The backup includes the original actor script, scene, motor, street skin, demo scene, manifests/descriptors, generic skin, and motion composer.

## Acceptance surface

Use `scenes/phase0/StreetCombatDemo.tscn` with the three imported street characters. `Unified3DIntegrationValidation.tscn` and the greybox fallback are compatibility probes only; they are not the animation quality gate.
