# 统一动作库与角色骨架适配阶段 1–3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 `humanoid.v1` 骨架标准、中央六状态 `AnimationLibrary`、三个 Street 角色的共享库运行时接入，以及可审查的构建时/缓存式重定向基础。

**Architecture:** 阶段 1 先建立版本化骨架和动作库契约，并从现有 `female_jk_external` 动作生成独立中央库；阶段 2 由 `CharacterEmbodimentAssetRegistry` 解析语义动作，把同一中央库挂载到三个 `StreetCharacterSkin`，GLB 内动作仅作为显式 fallback；阶段 3 使用 Godot headless 构建确定性的 `retargeted_library`，记录输入 digest、目标骨架、BodyProfile、CalibrationProfile、IKProfile 和 solver 版本，再交给同一 Registry。

**Tech Stack:** Godot 4.6.3 GDScript、Godot `AnimationLibrary`/`AnimationPlayer`/`AnimationTree`、Python 3 标准库、现有 GLB 解析脚本、pytest、Godot headless probes、Harness profiles。

**Spec:** `docs/superpowers/specs/2026-10-02-unified-motion-library-skeleton-adaptation-stages-1-3-design.md`

## Global Constraints

- 业务调用使用稳定的 `semantic_action_id`，不直接使用 raw clip 名称。
- 骨架兼容由 `SkeletonProfile`、轨道路径、rest pose、单位和轴向共同证明。
- `CharacterActor` 只接收语义动作请求；`AnimationTree` 负责姿态表现；`CharacterMotor` 是身体位移和碰撞的唯一写入点。
- 动作库只产生表现和 marker 观察，不能写世界真相、伤害、库存、最终 Transform 或 Velocity。
- 过渡阶段允许 fallback，但 fallback 必须在 manifest 中显式声明并可回滚。
- 阶段 3 只做构建时或缓存式 `retargeted_library`，不在游戏关键帧中生成未经验证的轨道。
- 不新增第三方依赖；GLB、manifest 和报告使用现有项目格式与标准库。
- 不修改原 `StreetCombatDemo` 的控制行为；共享库接入必须保留现有 CharacterActor、Motor、AnimationTree 和三角色切换证据。

## Review Focus

- **中央资源身份**：三个角色必须引用同一份 `AnimationLibrary` 实例或同一不可变资源路径，不能只因为 clip 名称相同就通过；由阶段 2 的共享资源身份 probe 覆盖。
- **轨道路径兼容**：缺少 canonical bone、错误 NodePath 或 68 根轨道不完整时，中央库和重定向结果必须拒绝；由阶段 1/3 的轨道完整性测试覆盖。
- **fallback 越权**：Registry 不得读取 `incoming/`、`review/` 或未经资格化的 raw clip；由阶段 1/2 的 rejected admission 和 fallback probe 覆盖。
- **root motion 双重消费**：动画表现层只能发布 root contribution，Motor 每个物理帧只消费一次；由阶段 2 的运动探针覆盖。
- **重定向可重复性和接触质量**：同样输入必须产生同一 cache key 和输出摘要，脚、手、武器、marker 和 root motion 不通过时不得注册；由阶段 3 的 deterministic retarget 和 qualification probe 覆盖。

---

### Task 1: 建立骨架标准和动作库 manifest 契约

**Files:**
- Create: `assets/validation/schemas/skeleton-profile.v1.json`
- Create: `assets/validation/schemas/motion-library-manifest.v1.json`
- Create: `assets/skeleton_profiles/humanoid.v1.json`
- Create: `assets/motion_library/approved/humanoid.v1/street_locomotion.manifest.json`
- Modify: `assets/validation/schemas/character-action-asset-manifest.v1.json`（增加 `motion_library_id`、`skeleton_profile_id` 和 `realization_mode` 的兼容字段）
- Test: `scripts/verification/tests/test_motion_library_contract.py`

**Interfaces:**
- Produces `SkeletonProfile` fields: `skeleton_profile_id`, `version`, `canonical_bones`, `hierarchy_digest`, `rest_pose`, `unit_scale`, `forward_axis`, `root_motion_policy`, `socket_profile`。
- Produces `MotionLibraryManifest` fields: `motion_library_id`, `skeleton_profile_id`, `animation_library_ref`, `clips`, `semantic_actions`, `source_digest`, `qualification_report_ref`, `qualification_status`。
- `clips` 中的每项必须包含 `clip_ref`、`duration_seconds`、`track_count`、`canonical_bone_ids` 和 `loop_mode`。

- [ ] **Step 1: 写失败的 manifest 合同测试**

```python
def test_humanoid_v1_manifest_declares_six_canonical_states():
    manifest = load_json(ROOT / "assets/motion_library/approved/humanoid.v1/street_locomotion.manifest.json")
    assert manifest["motion_library_id"] == "motionlib:humanoid.v1.core@1"
    assert manifest["skeleton_profile_id"] == "humanoid.v1"
    assert manifest["semantic_actions"]["action:locomotion.walk"]["clip_ref"] == "walking2"
    assert set(manifest["semantic_actions"]) == {
        "action:locomotion.idle",
        "action:locomotion.walk",
        "action:locomotion.run",
        "action:locomotion.jump",
        "action:melee.boxing",
        "action:melee.sword_attack",
    }
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest scripts/verification/tests/test_motion_library_contract.py -q`

Expected: FAIL because the schema and central manifest do not exist.

- [ ] **Step 3: 写最小 schema 和 `humanoid.v1` profile**

在 `skeleton-profile.v1.json` 中要求 canonical bone、rest pose、单位、前向轴和 root motion policy；在 `motion-library-manifest.v1.json` 中要求不可变 library ID、骨架 profile、六状态语义索引、clip metadata 和 qualification reference。`humanoid.v1.json` 使用当前三角色共同的 68 根 deform bone 名称映射，不把 Blender 控制器骨骼纳入运行时边界。

- [ ] **Step 4: 写中央动作库 manifest**

将 `idle`、`walking2`、`running`、`jump`、`boxing`、`sword_attack` 登记为六个语义实现，并声明：

```json
{
  "motion_library_id": "motionlib:humanoid.v1.core@1",
  "skeleton_profile_id": "humanoid.v1",
  "animation_library_ref": "res://assets/motion_library/approved/humanoid.v1/street_locomotion.tres",
  "semantic_actions": {
    "action:locomotion.walk": {
      "clip_ref": "walking2",
      "realization_mode": "shared_library",
      "loop_mode": "linear"
    }
  },
  "qualification_status": "candidate"
}
```

- [ ] **Step 5: 更新旧动作 manifest 的兼容字段**

为三个 Street 角色的 manifest 增加中央库 ID 和当前 fallback realization，保持现有 `clip_aliases.walk_forward = walking2` 不变，确保旧 Registry 仍可读取。

- [ ] **Step 6: 运行测试确认通过**

Run: `pytest scripts/verification/tests/test_motion_library_contract.py -q`

Expected: PASS，且测试验证六个 semantic action、`humanoid.v1`、`walking2`、不可变 library ID 和完整骨架字段。

- [ ] **Step 7: Commit**

```bash
git add assets/validation/schemas/skeleton-profile.v1.json assets/validation/schemas/motion-library-manifest.v1.json assets/skeleton_profiles/humanoid.v1.json assets/motion_library/approved/humanoid.v1/street_locomotion.manifest.json assets/validation/schemas/character-action-asset-manifest.v1.json scripts/verification/tests/test_motion_library_contract.py
git commit -m "feat: define skeleton and motion library contracts"
```

### Task 2: 从现有 GLB 构建独立中央 AnimationLibrary

**Files:**
- Create: `scripts/qualification/MotionLibraryBuilder.gd`
- Create: `scenes/qualification/MotionLibraryBuilder.tscn`
- Create: `assets/motion_library/approved/humanoid.v1/street_locomotion.tres`
- Modify: `assets/motion_library/approved/humanoid.v1/street_locomotion.manifest.json`
- Test: `scripts/verification/tests/test_motion_library_builder.gd`

**Interfaces:**
- `MotionLibraryBuilder.build_from_scene(source_scene_path: String, clip_names: PackedStringArray, output_path: String, library_id: StringName, skeleton_profile_id: StringName) -> Dictionary`
- Return keys: `accepted: bool`, `library_id: String`, `clip_refs: PackedStringArray`, `track_counts: Dictionary`, `duration_seconds: Dictionary`, `rejection_reason: String`。
- The builder reads the imported `female_jk_external` scene, duplicates only the six approved `Animation` resources into a new `AnimationLibrary`, and never edits the source GLB.

- [ ] **Step 1: 写失败的 Godot builder test**

```gdscript
func test_builder_exports_six_clips_without_mutating_source() -> void:
    var result := MotionLibraryBuilder.new().build_from_scene(
        "res://assets/active/female_jk_external/female_jk_external.glb",
        PackedStringArray(["idle", "walking2", "running", "jump", "boxing", "sword_attack"]),
        "res://assets/motion_library/approved/humanoid.v1/street_locomotion.tres",
        &"motionlib:humanoid.v1.core@1",
        &"humanoid.v1"
    )
    assert_true(result["accepted"])
    assert_eq(result["clip_refs"].size(), 6)
    assert_eq(result["track_counts"]["walking2"], 204)
```

- [ ] **Step 2: 运行 headless test 确认失败**

Run: `godot --headless --path . --script res://scripts/verification/tests/test_motion_library_builder.gd`

Expected: FAIL because `MotionLibraryBuilder` and the `.tres` resource do not exist.

- [ ] **Step 3: 实现 builder 的 AnimationLibrary 提取**

加载源场景，找到 `AnimationPlayer`，读取默认 library，按传入 clip 列表复制 `Animation` 资源，拒绝缺失 clip、空轨道、非 `humanoid.v1` canonical bone path 和重复语义动作。保存到独立 `.tres`，返回每个 clip 的轨道数和时长。

- [ ] **Step 4: 生成中央库和 manifest 元数据**

运行 builder 生成 `street_locomotion.tres`，把真实 clip 数量、时长、68 根骨骼通道数量、source digest 和 report reference 写回 manifest。`walking2` 必须拥有 204 条通道，时长约 `0.566666667s`。

- [ ] **Step 5: 运行 headless test 确认通过**

Run: `godot --headless --path . --script res://scripts/verification/tests/test_motion_library_builder.gd`

Expected: PASS，且源 GLB digest 未改变、中央 `.tres` 可加载、六个 clip 全部可见。

- [ ] **Step 6: Commit**

```bash
git add scripts/qualification/MotionLibraryBuilder.gd scenes/qualification/MotionLibraryBuilder.tscn assets/motion_library/approved/humanoid.v1/street_locomotion.tres assets/motion_library/approved/humanoid.v1/street_locomotion.manifest.json scripts/verification/tests/test_motion_library_builder.gd
git commit -m "feat: build canonical street motion library"
```

### Task 3: 扩展 Registry 的中央库注册和 realization 解析

**Files:**
- Modify: `scripts/character/CharacterEmbodimentAssetRegistry.gd`
- Modify: `assets/active/female_jk_external/manifest.json`
- Modify: `assets/active/female_t_external/manifest.json`
- Modify: `assets/active/female_bandage_external/manifest.json`
- Create: `scripts/verification/tests/test_motion_library_registry.gd`

**Interfaces:**
- Add `register_motion_library(library_id: StringName, manifest: Dictionary, library: AnimationLibrary) -> bool`.
- Add `resolve_motion_realization(package_id: StringName, action_id: StringName, claims: Array[StringName]) -> Dictionary`.
- Add `inventory_motion_libraries() -> Array[Dictionary]`.
- `resolve_motion_realization` returns `{accepted, motion_library_id, realization_mode, clip_ref, animation_library, fallback_applied, reason}` and rejects unqualified packages, mismatched skeleton profiles, rejected manifests, and `incoming/review` refs.

- [ ] **Step 1: 写失败的 Registry test**

```gdscript
func test_registry_resolves_shared_walk_without_raw_clip_lookup() -> void:
    var registry := CharacterEmbodimentAssetRegistry.new()
    var result := registry.resolve_motion_realization(&"female_t_external", &"action:locomotion.walk", [])
    assert_true(result["accepted"])
    assert_eq(result["motion_library_id"], "motionlib:humanoid.v1.core@1")
    assert_eq(result["realization_mode"], "shared_library")
    assert_eq(result["clip_ref"], "walking2")
```

- [ ] **Step 2: 写拒绝测试**

覆盖三种拒绝：manifest `qualification_status = rejected`、skeleton profile 不匹配、传入 `raw_clip_lookup = "walking2"`。每种结果都必须返回稳定的 `reason`，不能静默 fallback 到未经审核资源。

- [ ] **Step 3: 运行测试确认失败**

Run: `godot --headless --path . --script res://scripts/verification/tests/test_motion_library_registry.gd`

Expected: FAIL because Registry 尚未登记中央库和 realization。

- [ ] **Step 4: 实现中央库 inventory 和 resolve**

Registry 启动时读取三个 package manifest 和中央 motion manifest，验证 package digest、qualification report、skeleton profile 和 library resource path。解析顺序固定为 `shared_library -> retargeted_library -> package_native -> declared fallback`，并把来源写入 admission log。

- [ ] **Step 5: 运行测试确认通过**

Run: `godot --headless --path . --script res://scripts/verification/tests/test_motion_library_registry.gd`

Expected: PASS，且 `inventory_motion_libraries()` 返回唯一的 `motionlib:humanoid.v1.core@1`。

- [ ] **Step 6: Commit**

```bash
git add scripts/character/CharacterEmbodimentAssetRegistry.gd assets/active/female_jk_external/manifest.json assets/active/female_t_external/manifest.json assets/active/female_bandage_external/manifest.json scripts/verification/tests/test_motion_library_registry.gd
git commit -m "feat: resolve shared motion library realizations"
```

### Task 4: 把中央 AnimationLibrary 挂载到 StreetCharacterSkin

**Files:**
- Modify: `scripts/street_combat/StreetCharacterSkin.gd`
- Modify: `scripts/character/RoleAnimationController.gd`
- Modify: `scenes/phase0/StreetCombatDemo.tscn`
- Modify: `scenes/phase0/StreetCombatActorDemo.tscn`
- Create: `scripts/verification/tests/test_shared_animation_library_runtime.gd`

**Interfaces:**
- Add `StreetCharacterSkin.mount_motion_library(library: AnimationLibrary, library_id: StringName) -> bool`.
- Add `StreetCharacterSkin.get_mounted_motion_library_id() -> String`.
- Add `StreetCharacterSkin.uses_shared_motion_library() -> bool`.
- `RoleAnimationController` must resolve animation names from the mounted library before checking package-local GLB libraries, while preserving `play_state`, `play_action`, `hold_state`, `restore` and `is_locked` signatures.

- [ ] **Step 1: 写失败的 scene probe**

```gdscript
func test_three_street_skins_mount_same_library() -> void:
    var skins := find_street_skins()
    var library_ids: Array[String] = []
    for skin in skins:
        assert_true(skin.uses_shared_motion_library())
        library_ids.append(skin.get_mounted_motion_library_id())
        assert_eq(skin.get_mounted_motion_library_id(), "motionlib:humanoid.v1.core@1")
    assert_eq(library_ids.size(), 3)
```

- [ ] **Step 2: 运行 Godot probe 确认失败**

Run: `godot --headless --path . --scene res://scenes/phase0/StreetCombatActorDemo.tscn --quit-after 3`

Expected: FAIL or probe assertion because `StreetCharacterSkin` 目前只搜索 GLB 内部 AnimationLibrary。

- [ ] **Step 3: 实现 mount 方法**

在 `_ready()` 读取 package manifest 的 `motion_library_id`，从 Registry 取得中央 `AnimationLibrary`，调用 `AnimationPlayer.add_animation_library("central", library)`，记录 library ID，并在挂载失败时保留 local GLB library 作为 declared fallback。

- [ ] **Step 4: 调整 clip resolution 优先级**

`_resolve_animation()` 先尝试 `central/clip_name`，再尝试已有 library names 和 local clip；返回的 `_current_clip` 保留完整 library path 以便诊断，但 semantic action 仍来自 Registry。

- [ ] **Step 5: 保持六状态和动作锁行为**

让 `RoleAnimationController.state_name_for_clip()` 识别 `central/walking2`、`central/running` 等路径；验证 boxing/sword_attack 的 lock、cancel、recovery 不因 library namespace 改变。

- [ ] **Step 6: 运行 probe 确认通过**

Run: `godot --headless --path . --script res://scripts/verification/tests/test_shared_animation_library_runtime.gd`

Expected: PASS，三个角色的 library ID 相同，六状态全部解析，AnimationTree active，GLB local library 仍可作为 fallback。

- [ ] **Step 7: Commit**

```bash
git add scripts/street_combat/StreetCharacterSkin.gd scripts/character/RoleAnimationController.gd scenes/phase0/StreetCombatDemo.tscn scenes/phase0/StreetCombatActorDemo.tscn scripts/verification/tests/test_shared_animation_library_runtime.gd
git commit -m "feat: mount central animation library in street skins"
```

### Task 5: 完成阶段 2 的控制、fallback 和 root motion 集成证据

**Files:**
- Modify: `scripts/character/CharacterActor.gd`（仅把动作调用接到 semantic realization，不改变 Motor owner）
- Modify: `scripts/street_combat/StreetCharacterSkin.gd`
- Create: `scripts/verification/street_shared_motion_library_probe.gd`
- Create: `scripts/verification/tests/test_shared_motion_library_probe.py`
- Modify: `.harness/profiles/street-combat.json`
- Modify: `docs/character/street-combat-animation-trees.md`

**Interfaces:**
- `CharacterActor` sends semantic actions to `resolve_motion_realization` and never passes a raw clip to the Registry.
- Probe output fields: `shared_library_identity`, `six_states`, `animation_tree_active`, `motor_motion_owner`, `root_motion_single_consume`, `fallback_reason`。

- [ ] **Step 1: 写失败的 integration probe test**

```python
import subprocess

def test_probe_proves_shared_library_and_motor_ownership() -> None:
    result = subprocess.run(
        ["godot", "--headless", "--path", ".", "--script", "res://scripts/verification/street_shared_motion_library_probe.gd"],
        check=True, capture_output=True, text=True,
    )
    probe_output = result.stdout
    assert "shared_library_identity=true" in probe_output
    assert "six_states=true" in probe_output
    assert "animation_tree_active=true" in probe_output
    assert "motor_motion_owner=true" in probe_output
    assert "root_motion_single_consume=true" in probe_output
```

- [ ] **Step 2: 运行原 StreetCombat 和副本场景确认缺证据**

Run: `godot --headless --path . --scene res://scenes/phase0/StreetCombatDemo.tscn --quit-after 4` and `godot --headless --path . --scene res://scenes/phase0/StreetCombatActorDemo.tscn --quit-after 4`。

Expected: 场景可启动，但 probe 字段尚未全部出现中央库身份和单次 root motion 证据。

- [ ] **Step 3: 接入 semantic action 和显式 fallback**

让 Actor 只传 `action:locomotion.walk`、`action:locomotion.run`、`action:melee.boxing` 等语义 ID；若中央库不存在，Skin 只能使用 manifest 中声明的 local fallback，并把 `fallback_applied=true` 和原因写入诊断。

- [ ] **Step 4: 固定 Motor root contribution owner**

确认 `CharacterActor` 不直接调用 `move_and_slide()`，`StreetCharacterSkin` 不写 actor velocity；每个物理 tick 只调用一次 `consume_root_motion_delta()`，由 `MotionContributionComposer` 交给 `CharacterMotor`。

- [ ] **Step 5: 运行 probe 和现有测试**

Run:

```powershell
godot --headless --path . --script res://scripts/verification/street_shared_motion_library_probe.gd
pytest backend/tests/test_character_locomotion_motor_ownership_guard_static.py -v
pytest scripts/verification/tests/test_shared_walking2.py -v
```

Expected: probe 输出五个 true 字段；现有 Motor ownership 和 walking2 测试保持 PASS。

- [ ] **Step 6: 更新运行时文档和 Harness profile**

在 `docs/character/street-combat-animation-trees.md` 记录中央库 ID、六状态、fallback 和证据命令；profile 只声明新鲜 probe 产物，不复用旧报告。

- [ ] **Step 7: Commit**

```bash
git add scripts/character/CharacterActor.gd scripts/street_combat/StreetCharacterSkin.gd scripts/verification/street_shared_motion_library_probe.gd scripts/verification/tests/test_shared_motion_library_probe.py .harness/profiles/street-combat.json docs/character/street-combat-animation-trees.md
git commit -m "test: prove shared motion library runtime path"
```

### Task 6: 建立 BodyProfile、CalibrationProfile 和 IKProfile 契约

**Files:**
- Create: `assets/validation/schemas/body-profile.v1.json`
- Create: `assets/validation/schemas/calibration-profile.v1.json`
- Create: `assets/validation/schemas/ik-profile.v1.json`
- Create: `assets/characters/profiles/body/female_jk.default.json`
- Create: `assets/characters/profiles/body/female_t.default.json`
- Create: `assets/characters/profiles/body/female_bandage.default.json`
- Create: `assets/characters/profiles/calibration/humanoid.v1.street.default.json`
- Create: `assets/characters/profiles/ik/humanoid.v1.default.json`
- Modify: `assets/active/female_jk_external/manifest.json`
- Modify: `assets/active/female_t_external/manifest.json`
- Modify: `assets/active/female_bandage_external/manifest.json`
- Test: `scripts/verification/tests/test_motion_profile_contract.py`

**Interfaces:**
- `BodyProfile`: `profile_id`, `height_scale`, `leg_length_ratio`, `arm_length_ratio`, `mass_class`, `gait_scale`, `reach_scale`。
- `CalibrationProfile`: `profile_id`, `pelvis_offset`, `foot_contact_tolerance`, `root_motion_scale`, `socket_offsets`, `collision_scale`。
- `IKProfile`: `profile_id`, `foot_ik_enabled`, `hand_ik_enabled`, `weapon_anchor_policy`, `contact_tolerance`。

- [ ] **Step 1: 写失败的 profile schema test**

```python
def test_three_packages_declare_separate_body_and_shared_ik_profiles():
    manifests = [load_manifest(package_id) for package_id in STREET_PACKAGES]
    assert {m["body_profile_id"] for m in manifests} == {
        "body:female_jk.default", "body:female_t.default", "body:female_bandage.default"
    }
    assert {m["ik_profile_id"] for m in manifests} == {"ik:humanoid.v1.default"}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest scripts/verification/tests/test_motion_profile_contract.py -q`

Expected: FAIL because the profile schemas and manifest fields do not exist.

- [ ] **Step 3: 写三个 schema 和 profile 文件**

为三个角色填写实际身材比例和保守校准值；不把 `mass_class` 直接转换成关键帧修改。IK profile 只描述能力和容差，不宣称当前 GLB 已拥有运行时 IK。

- [ ] **Step 4: 更新角色 manifest**

给三个 manifest 加入 `body_profile_id`、`calibration_profile_id` 和 `ik_profile_id`，并保持原有 canonical mapping、digest 和 qualification report 引用不变。

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest scripts/verification/tests/test_motion_profile_contract.py -q`

Expected: PASS，并拒绝缺少 ratio、tolerance、socket 或 IK policy 的 profile。

- [ ] **Step 6: Commit**

```bash
git add assets/validation/schemas/body-profile.v1.json assets/validation/schemas/calibration-profile.v1.json assets/validation/schemas/ik-profile.v1.json assets/characters/profiles assets/active/female_jk_external/manifest.json assets/active/female_t_external/manifest.json assets/active/female_bandage_external/manifest.json scripts/verification/tests/test_motion_profile_contract.py
git commit -m "feat: add body calibration and ik profiles"
```

### Task 7: 实现确定性的构建时 retargeted_library 和缓存 manifest

**Files:**
- Create: `scripts/character/MotionRetargeter.gd`
- Create: `scripts/qualification/MotionRetargetBuildRunner.gd`
- Create: `scenes/qualification/MotionRetargetBuild.tscn`
- Create: `assets/motion_library/generated/.gitkeep`
- Create: `scripts/verification/tests/test_motion_retargeter.gd`
- Modify: `assets/validation/schemas/motion-library-manifest.v1.json`

**Interfaces:**
- `MotionRetargeter.build_library(source_library: AnimationLibrary, source_profile: Dictionary, target_profile: Dictionary, body_profile: Dictionary, calibration_profile: Dictionary, output_path: String) -> Dictionary`。
- `MotionRetargeter.compute_cache_key(source_library_id: String, source_digest: String, target_profile_id: String, target_profile_digest: String, body_profile_id: String, calibration_profile_id: String, solver_version: String) -> String`。
- Return keys: `accepted`, `realization_mode`, `output_library_ref`, `cache_key`, `clip_reports`, `rejection_reason`。
- `MotionRetargetBuildRunner` 负责 headless 参数读取、调用 retargeter、保存 `.tres` 和生成 report；它不修改 actor 或场景运行时状态。

- [ ] **Step 1: 写失败的 deterministic cache test**

```gdscript
func test_same_inputs_produce_same_cache_key() -> void:
    var retargeter := MotionRetargeter.new()
    var first := retargeter.compute_cache_key("motionlib:humanoid.v1.core@1", "SRC", "humanoid.v2", "DST", "body:female_t.default", "calibration:humanoid.v1.street.default", "retargeter.v1")
    var second := retargeter.compute_cache_key("motionlib:humanoid.v1.core@1", "SRC", "humanoid.v2", "DST", "body:female_t.default", "calibration:humanoid.v1.street.default", "retargeter.v1")
    assert_eq(first, second)
```

- [ ] **Step 2: 写失败的 mapping rejection test**

提供缺少 `right_hand` 或左右方向冲突的 target profile，要求 `build_library()` 返回 `accepted=false` 和稳定的 `missing_canonical_bone` 或 `axis_mismatch`。

- [ ] **Step 3: 运行 test 确认失败**

Run: `godot --headless --path . --script res://scripts/verification/tests/test_motion_retargeter.gd`

Expected: FAIL because retargeter and cache key implementation do not exist.

- [ ] **Step 4: 实现 canonical track remap**

按 source/target `canonical_bones` 将 Animation track 的 NodePath 替换为目标路径；只复制六状态中已批准的 clip；缺少骨骼、轴向、rest pose 或 track target 时 fail closed。对同一 `humanoid.v1` 拓扑先支持确定性的 name/path remap，不为未知拓扑假装完成通用重定向。

- [ ] **Step 5: 加入 BodyProfile 和 CalibrationProfile 参数**

只在允许的参数上应用相对步幅、root motion scale、pelvis offset 和 socket offsets；不直接修改 mass class 对应的关键帧。将每个 clip 的脚、手、武器槽、root motion 和 marker 结果写入 `clip_reports`。

- [ ] **Step 6: 保存输出和缓存 manifest**

输出到 `assets/motion_library/generated/cache-key/`（实际目录名使用计算出的 cache key），包含 `.tres`、manifest 和 qualification report。manifest 必须记录 source library ID/digest、target profile ID/digest、body/calibration/IK profile、solver version 和输出 digest。

- [ ] **Step 7: 运行 test 确认通过**

Run: `godot --headless --path . --script res://scripts/verification/tests/test_motion_retargeter.gd`

Expected: PASS，成功输入生成稳定 cache key 和六状态输出，缺骨骼/轴向/轨道时拒绝，重复运行输出 digest 一致。

- [ ] **Step 8: Commit**

```bash
git add scripts/character/MotionRetargeter.gd scripts/qualification/MotionRetargetBuildRunner.gd scenes/qualification/MotionRetargetBuild.tscn assets/motion_library/generated assets/validation/schemas/motion-library-manifest.v1.json scripts/verification/tests/test_motion_retargeter.gd
git commit -m "feat: add deterministic motion retarget build"
```

### Task 8: 将 retargeted_library 接入 Registry 并完成阶段 3 验收

**Files:**
- Modify: `scripts/character/CharacterEmbodimentAssetRegistry.gd`
- Modify: `scripts/street_combat/StreetCharacterSkin.gd`
- Create: `scripts/verification/motion_retarget_runtime_probe.gd`
- Create: `scripts/verification/tests/test_motion_retarget_runtime_probe.py`
- Create: `.harness/profiles/motion-library-qualification.json`
- Modify: `.harness/profiles/street-combat.json`
- Modify: `.harness/profiles/unified-character-action-foundation.json`
- Modify: `docs/character/street-combat-animation-trees.md`
- Modify: `docs/character/character-action-foundation-current-state.md`

**Interfaces:**
- Registry accepts only retarget manifests with `qualification_status = approved` and `realization_mode = retargeted_library`。
- Probe output fields: `cache_key_stable`, `target_tracks_valid`, `six_states_valid`, `foot_contact_valid`, `hand_socket_valid`, `root_motion_single_consume`, `rejected_output_blocked`。

- [ ] **Step 1: 写失败的 retarget runtime probe test**

```python
import subprocess

def test_retarget_runtime_probe_requires_all_gates() -> None:
    result = subprocess.run(
        ["godot", "--headless", "--path", ".", "--script", "res://scripts/verification/motion_retarget_runtime_probe.gd"],
        check=True, capture_output=True, text=True,
    )
    probe_output = result.stdout
    for field in (
        "cache_key_stable", "target_tracks_valid", "six_states_valid",
        "foot_contact_valid", "hand_socket_valid", "root_motion_single_consume",
        "rejected_output_blocked",
    ):
        assert f"{field}=true" in probe_output
```

- [ ] **Step 2: 接入 Registry admission**

拒绝缺失 source/target digest、solver version、profile references、clip report 或输出 digest 的生成库；对 rejected/quarantined 目录永不注册。

- [ ] **Step 3: 让 Skin 选择 retarget realization**

当目标角色 package manifest 指向 `retargeted_library` 时，Skin 使用 Registry 返回的目标 `.tres`；如果 retarget 资源缺失，按 manifest 顺序回退到 shared 或 package native，不读取未审核文件。

- [ ] **Step 4: 实现脚、手、武器和 root motion probe**

在目标角色上播放 walk/run/boxing/sword_attack，检查脚接触容差、手部 socket、武器挂点、marker timing、root motion policy 和 Motor 单次消费。失败字段必须带出 package、cache key 和 clip_ref。

- [ ] **Step 5: 运行阶段 3 验证**

Run:

```powershell
godot --headless --path . --script res://scripts/verification/motion_retarget_runtime_probe.gd
pytest scripts/verification/tests/test_motion_retarget_runtime_probe.py -v
python scripts/verification/harness.py --profile motion-library-qualification
```

Expected: 所有 probe 字段为 true；故意篡改 digest、删除 canonical bone 或标记 rejected 的输出均被阻止。

- [ ] **Step 6: 更新状态文档**

记录中央库 ID、retarget solver 版本、三个角色的 realization mode、fresh evidence 路径和未完成能力；不把当前构建时 remap 写成完美快速重定向或通用运行时 IK。

- [ ] **Step 7: Commit**

```bash
git add scripts/character/CharacterEmbodimentAssetRegistry.gd scripts/street_combat/StreetCharacterSkin.gd scripts/verification/motion_retarget_runtime_probe.gd scripts/verification/tests/test_motion_retarget_runtime_probe.py .harness/profiles/street-combat.json .harness/profiles/unified-character-action-foundation.json docs/character/street-combat-animation-trees.md docs/character/character-action-foundation-current-state.md
git commit -m "test: close motion retarget realization gates"
```

### Task 9: 全量回归和文档收口

**Files:**
- Modify: `docs/9月分析/2026-09-28-统一动作库与角色骨架适配讨论.md`
- Modify: `docs/character/character-action-asset-interface.md`
- Modify: `docs/character/character-asset-integration.md`
- Modify: `docs/INDEX.md`
- Test: `backend/tests/test_character_asset_qualification_contract.py`
- Test: `scripts/verification/tests/test_shared_walking2.py`

**Interfaces:**
- 文档必须引用本 spec 和 plan，说明中央库当前状态、三个 realization mode 和阶段 1–3 的证据入口。
- 不修改后端 authority 合同；动作资源仍是本地表现和候选 marker。

- [ ] **Step 1: 搜索文档漂移**

Run: `rg -n "每个骨架自己的|中央 AnimationLibrary|walking2|retargeted_library|humanoid.v1" docs assets scripts`

Expected: 找出仍把 GLB 复制描述成中央库、或把当前阶段描述成完美重定向的旧表述。

- [ ] **Step 2: 统一当前状态表述**

把分析文档、角色资产接口、角色资产集成和 INDEX 的入口指向本 spec/plan；明确阶段 1/2/3 的完成条件，保留现有 fallback 和不宣称项。

- [ ] **Step 3: 运行针对性回归**

Run:

```powershell
pytest backend/tests/test_character_asset_qualification_contract.py -v
pytest scripts/verification/tests/test_shared_walking2.py -v
pytest backend/tests/test_character_locomotion_motor_ownership_guard_static.py -v
git diff --check
```

Expected: 所有针对性测试通过，文档无空白错误。

- [ ] **Step 4: 运行完整 Harness**

Run: `python scripts/verification/harness.py --profile all`

Expected: 相关动作资产、Godot runtime 和 motor ownership profiles 使用本轮 fresh evidence 通过；如果外机 Godot 未可用，保留明确的 static-only 结果，不把它写成运行时完成。

- [ ] **Step 5: Commit**

```bash
git add docs/9月分析/2026-09-28-统一动作库与角色骨架适配讨论.md docs/character/character-action-asset-interface.md docs/character/character-asset-integration.md docs/INDEX.md
git commit -m "docs: close unified motion library stages 1-3"
```

## Dependency Order

```text
Task 1 -> Task 2 -> Task 3 -> Task 4 -> Task 5
                                  |
                                  v
                             Task 6 -> Task 7 -> Task 8 -> Task 9
```

Task 1–5 必须先证明同一骨架标准下的中央库共享；Task 6–8 才能引入 profile 参数和重定向结果。Task 9 只在阶段证据 fresh 后执行。

## Completion Gate

阶段 1 完成：中央 `humanoid.v1` manifest、六状态 `.tres`、源 digest 和静态资格化证据齐全。

阶段 2 完成：三个角色由同一中央 `AnimationLibrary` 驱动，六状态、CharacterActor 控制、Motor 位移、AnimationTree active、fallback 和 root motion 单次消费均有 fresh Godot 证据。

阶段 3 完成：至少一个目标 realization 通过 deterministic cache、canonical track、脚/手/武器接触、root motion、六状态和 rejected-output gate；输出已由 Registry 接纳。

全部阶段完成：针对性测试、Godot probes、相关 Harness profile 和文档状态一致；没有把 package-native fallback、构建时 remap 或静态证据描述成完美快速重定向。

