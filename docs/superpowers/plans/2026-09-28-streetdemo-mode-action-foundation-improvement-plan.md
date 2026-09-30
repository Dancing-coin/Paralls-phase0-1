# Streetdemo 驱动的角色动作底座渐进替代实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用已验证的 Streetdemo 动作闭环渐进替代旧角色运行时，在保持旧调用方可回滚的前提下统一 intent、动画 owner、Motor owner、资产准入和 authority evidence。

**Architecture:** Streetdemo 只提供已验证的动作行为来源。正式运行时由 CharacterActor 编排 ControllerPort、CharacterControlIntent、ActorActionArbiter、RoleAnimationController、MotionContributionComposer 和 CharacterMotor。CharacterReplica 保留为只转发的兼容壳，直到所有活动 caller 和证据门关闭。

**Tech Stack:** Godot 4.6 GDScript、CharacterBody3D、AnimationTree/AnimationPlayer、现有 GLB manifest 和 qualification report、Python backend authority、pytest、Godot headless probes、Harness。

**Spec:** docs/superpowers/specs/2026-09-28-character-action-foundation-series-completion-design.md

## 2026-09-29 Execution Status

Tasks 1-8 are implemented and have focused or fresh StreetCombatDemo evidence.
Task 9 has a fresh gate audit, but remains **blocked** rather than `closed`.
The formal acceptance scene is the real
`scenes/phase0/StreetCombatDemo.tscn` with the three qualified packages; the
UnifiedCharacterActionFoundation greybox remains a narrow protocol/authority
probe only. Root motion is still the temporary `hold` / zero-envelope policy.

Fresh closure evidence on 2026-09-29:

- `street-combat`: passed from the real StreetCombatDemo scene with environment,
  collision/navigation, three Registry-qualified packages, player/agent
  authority, duplicate/stale/recovery, and HUD markers.
- `docs` and `change-lifecycle`: passed and exported outside the repository.
- focused action-foundation suite: `27 passed`.
- full `python -m pytest -v`: collection completed (`7671 collected`), then
  `7621 passed, 48 failed, 2 skipped, 103 warnings`; this is a repository-wide
  red result, not a collection blocker.
- declared dependency repair: the interpreter was running `websockets 12.0`
  while `backend/pyproject.toml` requires `>=13.0` and
  `backend/ci-constraints.txt` pins `17.1`; the environment was aligned to
  `17.1`, after which `websockets.asyncio` collected successfully.
- ArchiveDoor is an **external-plan dependency**, not a StreetCombatDemo
  acceptance scene. The earlier live transport timeout came from a test fixture
  placing the actor outside the authority range; its focused regression now
  passes. A separate reversed forced-motion Z conversion prevented the real
  Godot host from reaching the door. After the one-line correction, fresh
  `character-turn-embodied-episode` evidence proves success, distance failure,
  revision failure, and stance failure through the live backend and Godot.
  Export: `D:\Task9Evidence-20260929-08\archive-door`.

## Global Constraints

- CharacterMotor 是唯一的身体位移、重力、朝向、root contribution 消费和 move_and_slide owner。
- RoleAnimationController 是唯一的 AnimationTree/AnimationPlayer 播放、action lock、hold、cancel 和 recovery owner。
- StreetCharacterSkin 在迁移期间只能作为资产和语义动作适配器，不能拥有第二套状态机。
- CharacterReplica 只保留兼容转发，不增加新行为。
- 旧 backend authority、ActionAttempt、幂等、修订和恢复语义保持不变。
- 第一轮 root motion 使用 hold/zero-envelope，生产 root motion 必须单独校准。
- 正式资产运行时只能读取 Registry 已准入的 qualified package。
- 原始 streetdemo.gd 只能作为行为参考，不得直接成为正式角色脚本。
- 每个阶段必须有独立的静态或运行时证据和可回滚边界。

## Review Focus

- 场景或旧 API 直接写 velocity 时，必须失败并指向 CharacterMotor command。
- action lock 到期时，角色必须恢复到当前 locomotion，而不是固定回 idle。
- player、agent、program 对同一 intent 必须得到相同 arbitration 和 Motor 边界。
- root contribution 与 locomotion lease 同 tick 不得重复位移。
- 未准入 package、缺失 clip、缺失 mapping、旧 revision 和 changed duplicate 必须 fail-closed 或 zero-write。

## 文件职责地图

- `scripts/character/CharacterActor.gd`：角色编排、旧 API 适配、intent frame 和 authority correlation。
- `scripts/character/CharacterControlIntent.gd`：player/agent/program 共用的意图结构。
- `scripts/character/CharacterControllerPort.gd`：输入来源边界和 proposal normalization。
- `scripts/character/ActorActionArbiter.gd`：priority、claim、lock、queue、cancel 和同 tick 决策。
- `scripts/character/RoleAnimationController.gd`：唯一动画状态、播放、lock、hold、cancel、recovery。
- `scripts/character/CharacterPresentationRuntime.gd`：资产适配、semantic realization、诊断和 marker observation。
- `scripts/character/CharacterMotor.gd`：唯一身体运动和 contact evidence owner。
- `scripts/character/MotionContributionComposer.gd`：lease、root、impulse 和 correction 去重。
- `scripts/character/CharacterEmbodimentAssetRegistry.gd`：manifest、qualification report 和 semantic profile admission。
- `scripts/street_combat/StreetCharacterSkin.gd`：迁移期间的薄资产适配器。
- `scripts/street_combat/StreetCombatDemo.gd`：输入、相机、目标和 combat coordination，不直接播放动画或写 velocity。
- `scripts/character/CharacterReplica.gd`：只转发旧 API，最后归档。
- `scenes/phase0/CharacterActor.tscn`：正式 actor scene。
- `scripts/verification/tests/test_character_action_foundation_progressive_replacement.py`：阶段性静态契约。
- `scripts/verification/CharacterActionFoundationBaselineProbe.gd`：旧/新行为基线。
- `scripts/verification/CharacterReplicaRetirementProbe.gd`：Replica 退休门。
- `scripts/verification/CharacterActionFoundationRuntimeProbe.gd`：三角色、player/agent、动画、Motor、root 和 recovery 证据。

## Task 1: Freeze baseline and build the caller matrix

**Files:**
- Create: `docs/character/action-foundation-series-baseline-2026-09-28.md`
- Create: `scripts/verification/CharacterActionFoundationBaselineProbe.gd`
- Create: `scripts/verification/tests/test_character_action_foundation_progressive_replacement.py`
- Modify: `backend/tests/test_character_replica_convergence_static.py`

**Interfaces:**
- Probe output fields: `actor_id`, `source_kind`, `state`, `clip`, `velocity_world`, `position`, `action_locked`, `root_policy`, `caller_path`.
- Static test helper: `read_active_callers() -> list[str]`.

- [ ] 扫描 `scenes/`, `scripts/` 和 `backend/` 中的 CharacterReplica 实例、路径查找和旧方法调用。
- [ ] 记录 player、agent、program、perception、interaction、authority 和 probe 的 caller matrix。
- [ ] 运行现有 StreetCombatDemo headless probe，保存 idle/walk/run/jump/boxing/sword、碰撞和 authority baseline。
- [ ] 静态失败条件：活动代码中存在未登记的 `CharacterReplica` caller、第二个 `move_and_slide()` owner 或直接 Skin animation call。
- [ ] 运行：
  `python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py`
- [ ] 只有 baseline 和 caller matrix 生成后才能进入 Task 2。

## Task 2: Add semantic intent without changing old behavior

**Files:**
- Create: `scripts/character/CharacterControlIntent.gd`
- Modify: `scripts/character/CharacterActor.gd`
- Modify: `scripts/character/CharacterControllerPort.gd`
- Modify: `scripts/character/CharacterRuntimeState.gd`
- Modify: `scripts/character/CharacterReplica.gd`
- Test: `scripts/verification/tests/test_character_action_foundation_progressive_replacement.py`

**Interfaces:**
```gdscript
CharacterControlIntent.create(
    move_direction: Vector3,
    wants_run: bool,
    jump_type: StringName,
    action_id: StringName,
    source_kind: StringName,
    target_ref: StringName,
) -> Dictionary

CharacterActor.submit_control_intent(intent: Dictionary) -> void
```

- [ ] 为缺失字段定义 deterministic defaults：idle、none、空 target 和 source_kind=compatibility。
- [ ] 让 `begin_embodied_control_frame()` 和 `apply_embodied_pose_sync()` 只创建 intent，不直接选择 clip。
- [ ] 保留旧返回值和失败语义，新增 source digest、physics tick 和 intent digest。
- [ ] 添加 player、agent、program 三种 source_kind 的 normalization 测试。
- [ ] 运行 focused pytest，确认旧 compatibility caller 仍可调用。

## Task 3: Make animation ownership single-source

**Files:**
- Modify: `scripts/character/RoleAnimationController.gd`
- Modify: `scripts/street_combat/StreetCharacterSkin.gd`
- Create: `scripts/character/CharacterPresentationRuntime.gd`
- Test: `scripts/verification/tests/test_character_action_foundation_progressive_replacement.py`

**Interfaces:**
```gdscript
RoleAnimationController.apply_presentation_state(state: Dictionary) -> Dictionary
CharacterPresentationRuntime.apply_presentation_input(input: Dictionary) -> Dictionary
```

- [ ] 将 action lock、guard hold、cancel、recovery 的唯一状态放入 RoleAnimationController。
- [ ] 删除 Skin 内部重复的 action timer 和 recovery decision；Skin 只能转发 semantic state。
- [ ] 动作结束后根据当前 intent 恢复 idle、walk 或 run。
- [ ] 同一 `state + clip` 不重复 travel。
- [ ] 缺少 AnimationTree、clip 或 descriptor 时返回 idle/fallback 和明确 reason。
- [ ] 添加 interrupted one-shot、guard release 和 action-to-run recovery 测试。
- [ ] 运行 StreetCombatDemo focused Godot probe。

## Task 4: Enforce Motor ownership and remove scene writes

**Files:**
- Modify: `scripts/character/CharacterActor.gd`
- Modify: `scripts/character/CharacterMotor.gd`
- Modify: `scripts/character/MotionContributionComposer.gd`
- Modify: `scripts/street_combat/StreetCombatDemo.gd`
- Modify: active callers found by Task 1
- Test: `backend/tests/test_character_motor_ownership_audit.py`
- Create: `scripts/verification/CharacterMotorOwnershipProbe.gd`

**Interfaces:**
```gdscript
CharacterMotor.apply_physics_command(
    body: CharacterBody3D,
    command: Dictionary,
    delta: float
) -> Dictionary
```

- [ ] 将跳跃 impulse、run speed、facing 和 root contribution 全部放进 PhysicsMotionCommand。
- [ ] 删除 StreetCombatDemo 对 `player.velocity` 的直接写入。
- [ ] 保证 active GDScript 只有 CharacterMotor 调用 `move_and_slide()`。
- [ ] 证明 lease 与 root contribution 同 tick 不重复位移。
- [ ] 运行 Motor ownership static test 和 Godot wall/floor/jump probe。

## Task 5: Route actions through arbiter and preserve authority

**Files:**
- Modify: `scripts/street_combat/StreetCombatCoordinator.gd`
- Modify: `scripts/street_combat/StreetCombatDemo.gd`
- Modify: `scripts/character/ActorActionArbiter.gd`
- Modify: `scripts/character/CharacterRuntimeState.gd`
- Test: `backend/tests/test_character_action_lock_rules.py`
- Create: `scripts/verification/StreetActionAttemptProgressiveProbe.gd`

**Interfaces:**
```gdscript
CharacterActor.submit_action_intent(
    action_id: StringName,
    target_ref: StringName,
    source_kind: StringName
) -> Dictionary
```

- [ ] 将 boxing/sword 请求先转成 semantic action intent，再由 Arbiter admission。
- [ ] 保留现有 ActionAttempt、idempotency、revision 和 recovery payload。
- [ ] authority result 只能改变 projection 和 recovery，不能由本地宣布命中或伤害。
- [ ] 重新验证 committed、duplicate、changed duplicate、stale revision 和 reconnect。
- [ ] 运行 backend authority tests 和 StreetCombatDemo backend probe。

## Task 6: Migrate scenes while keeping the compatibility shell

**Files:**
- Create: `scenes/phase0/CharacterActor.tscn`
- Modify: `scenes/phase0/StreetCombatDemo.tscn`
- Modify: Phase 0 active scenes discovered in Task 1
- Modify: `scripts/verification/CharacterAgentExecutionProbe.gd`
- Modify: `scripts/interaction/ArchiveDoorEmbodiedActionHost.gd`
- Modify: `scripts/character/CharacterReplica.gd`
- Create: `scripts/verification/CharacterReplicaRetirementProbe.gd`

**Interfaces:**
- `CharacterActor.tscn` preserves collision shape, actor properties, runtime feedback, fact emitters and presentation mount paths.
- `CharacterReplica.gd` exposes only forwarding methods listed in `COMPATIBILITY_METHODS`.

- [ ] 先把 StreetCombatDemo 和 probes 迁到 CharacterActor scene。
- [ ] 保留旧节点路径适配，直到所有 caller matrix entries 标记 migrated。
- [ ] 让 Replica compatibility methods call CharacterActor interfaces only。
- [ ] RetirementProbe 统计 active scene instances、script references、node paths 和 concrete behavior callers。
- [ ] 只有 probe 报告全部为零，才归档 Replica 实现。
- [ ] 运行 Phase 0 scene tests、agent probe、ArchiveDoor probe 和 retirement probe。

## Task 7: Enforce Registry admission and package realization

**Files:**
- Modify: `scripts/character/CharacterEmbodimentAssetRegistry.gd`
- Modify: `scripts/character/RolePresentationAdapter.gd`
- Modify: `scripts/street_combat/StreetCharacterSkin.gd`
- Modify: `assets/active/*/manifest.json`
- Create: `scripts/verification/CharacterAssetAdmissionProgressiveProbe.gd`
- Test: `backend/tests/test_character_asset_admission_runtime.py`

**Interfaces:**
```text
resolve(package_id, semantic_action_id, claims) -> qualified realization profile
```

- [ ] 禁止正式 Skin 旁路读取未准入 manifest。
- [ ] 强制 digest、canonical mapping、qualification report、action descriptor 和 root profile。
- [ ] 未知 package、缺失 mapping、错误 digest、缺 clip 和不支持 claims fail-closed。
- [ ] 用 `package_id + semantic_action_id` 替代 raw clip 业务调用。
- [ ] 验证三个街区角色通过同一 Registry 路径完成 idle/walk/run/jump/boxing/sword。

## Task 8: Calibrate root motion and capability boundaries

**Files:**
- Modify: `scripts/character/RootMotionSampler.gd`
- Modify: `scripts/character/MotionContributionComposer.gd`
- Modify: `scripts/character/CharacterMotor.gd`
- Modify: `assets/active/*/manifest.json`
- Create: `scripts/verification/RootMotionQualificationProgressiveProbe.gd`
- Create: `scripts/character/CharacterPresentationCapability.gd`
- Test: `backend/tests/test_root_motion_contract_static.py`

- [ ] 第一轮保持 `root_motion_policy=hold` 和 zero-envelope。
- [ ] 验证采样、清空、消费 token 和 zero-envelope 不位移。
- [ ] 测量 walking/running root track 的方向、距离、周期和 envelope。
- [ ] 只为单一 qualified locomotion profile 开启 `drive_locomotion`。
- [ ] 将 Knight/right-hand/ArchiveDoor 修正注册为 capability，不向通用 Actor 添加 package 分支。
- [ ] 验证 root、lease、wall、slope、lost support 和 stop/restart。

## Task 9: Close gates and publish status

**Files:**
- Modify: `docs/character/character-action-foundation-current-state.md`
- Modify: `docs/character/character-action-foundation-operator-guide-and-index.md`
- Modify: `docs/character/character-replica-convergence.md`
- Modify: `docs/INDEX.md`
- Create: `docs/character/action-foundation-series-status.md`
- Modify: relevant Harness profile metadata

- [ ] 为每个 gate 记录 status、owner、command、fresh evidence 和 remaining risk。
- [ ] 明确区分：pilot landed、runtime migration in progress、Replica retired、asset admission closed、authority closed。
- [ ] 运行：
  - `python -m pytest -v`
  - `python scripts/verification/harness.py --profile change-lifecycle`
  - 相关 StreetCombatDemo Godot probes
  - `git diff --check`
- [ ] 检查 `git status --short -- .harness`，不把临时 raw evidence 写入仓库。
- [ ] 只有所有 gate 都有 fresh evidence，才把状态改为 closed。

## Verification Ladder

1. Baseline and caller inventory.
2. Animation ownership and recovery.
3. Motor ownership and physics command.
4. Semantic intent and arbiter.
5. Authority and ActionAttempt recovery.
6. CharacterActor scene migration and Replica retirement.
7. Registry and asset qualification.
8. Root motion and capability validation.
9. Full pytest, Harness, Godot runtime and documentation audit.

## Completion Criteria

计划完成仅表示：旧系统的活动运行时路径已经被 CharacterActor、RoleAnimationController、CharacterMotor、Registry 和 authority boundary 完整替代，并且 CharacterReplica 只剩归档记录。仅通过 Streetdemo 动画 probe 不能关闭本计划。
