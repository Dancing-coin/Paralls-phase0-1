# Current Scene Tree

This is a current snapshot of the Phase 0 runtime structure after removing the third-party controller.

## MainDemo

```text
MainDemo
├─ Player                          -> project-owned PlayerShell.tscn
│  ├─ VisualRoot                   -> hidden local shell marker
│  ├─ CameraHolder
│  │  └─ SpringArm3D
│  │     └─ Camera3D
│  ├─ CollisionShape3D
│  ├─ Phase0InputBridge            -> scripts/player/Phase0PlayerBridge.gd
│  ├─ Phase0Embodiment             -> scripts/player/Phase0PlayerEmbodiment.gd
│  └─ CameraOcclusionFader         -> scripts/player/CameraOcclusionFader.gd
├─ IntentMapper                    -> scripts/player/PlayerIntentMapper.gd
├─ VisualFactEmitter
├─ CharacterA                      -> CharacterReplica.tscn
├─ CharacterB                      -> CharacterReplica.tscn
├─ CharacterC                      -> CharacterReplica.tscn
├─ InteractiveObject
├─ EnvironmentStateNode
└─ ThroneRoomImported
```

`Player` is now a small project-owned `CharacterBody3D` collision/camera shell. It no longer carries a bundled animation state machine, HUD, or plugin skin. `CharacterC` remains the visible player role shell.

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
Phase0PlayerBridge   = maps local player controls into CharacterC frame requests
CharacterC           = visible player role shell and root-motion source
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
