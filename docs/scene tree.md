# Current Scene Tree

This is a current snapshot of the Phase 0 runtime structure after removing the third-party controller.

## MainDemo

```text
MainDemo
├─ PlayerCharacter                 -> CharacterBase.tscn
│  ├─ CameraHolder
│  │  └─ SpringArm3D
│  │     └─ Camera3D
│  ├─ CollisionShape3D
│  ├─ CharacterReplica             -> visible shared actor shell for char_c
│  ├─ Phase0InputBridge            -> scripts/player/Phase0PlayerBridge.gd
│  ├─ CharacterMotor               -> scripts/character/CharacterMotor.gd
│  ├─ Phase0PlayerCommandRelay     -> scripts/player/Phase0PlayerCommandRelay.gd
│  └─ CameraOcclusionFader         -> scripts/player/CameraOcclusionFader.gd
├─ IntentMapper                    -> scripts/player/PlayerIntentMapper.gd
├─ VisualFactEmitter
├─ CharacterA                      -> CharacterReplica.tscn
├─ CharacterB                      -> CharacterReplica.tscn
├─ InteractiveObject
├─ EnvironmentStateNode
└─ ThroneRoomImported
```

`PlayerCharacter` is the current player wrapper scene (`CharacterBase.tscn`). It owns the collision/camera shell, mounts the thin command relay, and nests the visible shared actor shell for `char_c` as `CharacterReplica`. This is still transitional relative to the final-convergence target, but it is the current repo-local runtime truth.

## CharacterReplica

```text
CharacterReplica
├─ VisualRoot
│  ├─ AssetMount
│  │  └─ RotationOffset
│  │     └─ ScaleOffset
│  │        └─ ImportedModel
│  │           └─ RoleAssetRoot
│  │              └─ KnightRoleSkin
│  └─ GreyboxBodyRoot
│     └─ GreyboxHumanoidVisual
├─ SpatialVoiceController
├─ Nameplate
├─ RoleStateFactEmitter
└─ PhysiologyStateFactEmitter
```

`GreyboxHumanoidVisual` remains a fallback visual. Current `MainDemo` character instances use `use_role_asset = true`, so `KnightRoleSkin` is the active visible character asset for A, B, and C.

## KnightRoleSkin

```text
KnightRoleSkin
└─ KnightScene
   ├─ KnightArmature
   │  └─ Skeleton3D
   └─ AnimationPlayer
```

`KnightScene` comes from `res://assets/characters/shared/crusader_knight.glb`. `KnightRoleSkin.gd` owns clip selection, role variants, focus highlighting, root-motion sampling, and local bone-pose refinement.

## Runtime Ownership

```text
PlayerShell          = collision, gravity, jump, camera rig, input action fields
CharacterBase        = current player wrapper scene for PlayerShell + CharacterReplica
Phase0PlayerBridge   = maps local player controls into char_c frame requests
CharacterReplica     = visible shared actor shell and root-motion source
CharacterA/B         = AI-driven replicas using the same role asset stack
BackendBridge        = structured backend protocol boundary
LocalPresentationBus = local presentation event fan-out
```

Root motion now flows from the project role asset path:

```text
KnightRoleSkin.consume_root_motion_delta()
-> CharacterReplica.consume_player_root_motion_request()
-> Phase0PlayerBridge.before_player_shell_move()
-> PlayerShell.velocity
-> PlayerShell.move_and_slide()
```

The earlier `Phase0Embodiment` helper shell has been removed; `CharacterBase.tscn` no longer mounts it, and current player-wrapper runtime truth flows through `CharacterReplica`, `Phase0PlayerBridge`, and `Phase0PlayerCommandRelay`.
