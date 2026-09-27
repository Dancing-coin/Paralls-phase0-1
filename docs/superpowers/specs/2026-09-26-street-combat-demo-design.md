# Street Combat Demo 设计规格

## 状态

已获用户确认，2026-09-26 开始实施。

## 目标

把当前使用体素占位角色和室内灰盒环境的默认可玩入口，扩展为一个真实街区战斗纵切片：

- 使用 `paralls-art-assets` 的街区环境资产；
- 使用用户提供并已在 Godot 仓库中完成 qualification 的三个角色版本；
- 让三个角色都接入共享 `CharacterReplica` / action foundation；
- 让玩家控制其中一个角色，另外两个角色由 character-agent runtime 驱动；
- 让玩家与两个 agent 角色进行经过后端 authority 结算的战斗交互；
- 提供可读的战斗和角色智能体 UI；
- 保留既有 Phase 0 `MainDemo.tscn` 作为回归场景。

## 明确资产边界

### 环境

环境只使用 `paralls-art-assets` 中的街区导出：

- `citystreets_209` environment export；
- 对应 collision export；
- 对应 navigation export。

优先接入 `citystreets_209/0.3.0`，并保留 art 仓库 manifest、scene-binding 和 export-report 中定义的 pack/version 元数据。

`citystreets_mall_composite` 是候选组合描述，不假设存在合并 GLB。第一阶段只实现街区环境；商场入口和 portal 不作为本纵切片的必需依赖。

### 角色

角色只使用 Godot 仓库中已经提供的三个版本：

- `female_jk_external`；
- `female_t_external`；
- `female_bandage_external`。

art 仓库中随街区或 trio 场景附带的角色模型视为损坏或不合格，禁止实例化、复制或作为 fallback。

不修改 `.blend` 源文件，不修改既有 Task 8 qualification 或 `session_store`。

## 场景结构

新增 `StreetCombatDemo.tscn`，不替换 `scenes/phase0/MainDemo.tscn`。

推荐结构：

```text
StreetCombatDemo
├── CityStreetsEnvironment
│   ├── EnvironmentVisual
│   ├── EnvironmentCollision
│   └── EnvironmentNavigation
├── PlayerCharacter
│   └── CharacterReplica
│       └── female_bandage_external
├── AgentCharacterJK
│   └── CharacterReplica
│       └── female_jk_external
├── AgentCharacterT
│   └── CharacterReplica
│       └── female_t_external
├── CombatInteractionLayer
├── StreetCombatHUD
└── BackendBridge
```

三个人物都必须保留相同的外层 actor substrate：

```text
CharacterReplica
→ RolePresentationAdapter
→ skeleton binding profile
→ imported GLB
→ CharacterActionAssetDescriptor
```

导入模型根节点不承载业务逻辑。脚本、输入、感知、动作状态和 authority 结果继续位于角色壳及其适配器层。

## 运行时职责

### Godot

- 玩家输入采集和 structured intent 发送；
- 本地 CharacterReplica motor、朝向、root motion 消费和动画播放；
- 角色模型、骨架、动作 clip 和受击表现；
- 目标锁定、距离提示和 HUD；
- 接收 backend result 并更新可见状态。

### Python backend

- character-agent runtime 的感知、意图和动作建议；
- ESM/Gameplay authority 的攻击有效性、距离、命中和状态结算；
- action request/result lineage；
- 角色和世界状态事件；
- duplicate、stale、拒绝和恢复语义。

不得新增第二 scheduler、authority writer 或 raw clip 跨边界；Siming 仍只发高层 catalyst。

## 角色控制和战斗流程

### 玩家角色

玩家控制一个 `CharacterReplica`，保留现有 player shell 和 structured intent 路径。至少支持：

- 移动和转向；
- 目标锁定；
- 近战攻击；
- 防御或受击反馈；
- 与两个 agent 角色交互。

### Agent 角色

另外两个 `CharacterReplica` 由 character-agent runtime 驱动：

- 感知附近角色和环境；
- 产生移动、观察、追击、防御或攻击意图；
- 通过既有 execution contract 进入本地 actor adapter；
- 通过 structured action request 进入 backend authority；
- 根据 authority result 播放接受、拒绝、受击或恢复表现。

### 战斗 authority

战斗请求必须遵循：

```text
input / agent intent
→ structured action request
→ ESM or Gameplay authority
→ action/world result
→ Godot presentation
```

本地动画不能自行宣布命中或伤害。至少要覆盖：

- 合法近战命中；
- 超距或不可见目标拒绝；
- stale revision 拒绝；
- duplicate replay 不重复结算；
- 恢复后再次成功。

## UI

第一阶段 UI 只呈现能帮助玩家判断战斗和角色状态的信息：

- 玩家生命、体力、当前动作和受击/硬直状态；
- 当前目标卡、距离和可攻击状态；
- 三个角色的状态条和当前动作；
- 锁定、攻击、防御、超距和拒绝提示；
- 战斗事件 feed，显示请求、命中、拒绝和恢复；
- agent 角色的当前意图、目标和动作状态。

UI 读取 runtime state、authority result 和 character-agent execution payload，不直接写入世界 authority。

## 骨架和动作要求

每个角色必须留下明确的 binding 证据，至少包括：

- pelvis/hips；
- spine；
- neck/head；
- 双臂到手；
- 双腿到脚。

每个角色至少验证：

- idle；
- walk/root motion；
- attack；
- hit or recoil；
- dialogue/attention presentation。

角色动作差异通过 binding profile 和 action asset descriptor 表达，不为单一模型创建新的 runtime species。

## 验收证据

新增 `street-combat` runtime verification profile，至少证明：

1. 街区 environment、collision 和 navigation 真实加载；
2. 三个指定 GLB 真实可见，场景不再使用体素角色作为可玩角色；
3. 三个 skeleton binding 通过；
4. 三个角色均产生 idle/walk/attack/hit runtime marker；
5. 玩家可以控制其中一个角色；
6. 两个 agent 角色由 character-agent execution contract 驱动；
7. 玩家攻击和 agent 攻击都产生 backend authority result；
8. 命中、拒绝、duplicate、stale/recovery 均保留 request lineage；
9. HUD 显示真实角色和战斗状态；
10. 原有 Phase 0 fresh verification 继续通过。

最终验证命令：

```powershell
python scripts/verification/verify_street_combat.py \
  --godot-exe D:\\godot\\Godot_v4.6.3-stable_win64.exe \
  --python-exe C:\\Anaconda3\\python.exe

python scripts/verification/harness.py --profile phase0
python scripts/verification/harness.py --profile street-combat
python scripts/verification/harness.py --profile all
```

## 非目标

- 不删除或重写 `MainDemo.tscn`；
- 不把 art 仓库自带的损坏角色带入 runtime；
- 不修改 `.blend`、Task 8 qualification 或 `session_store`；
- 不实现完整开放世界、商场 portal 或 Phase 1 architecture cleanup；
- 不新增 authority writer、第二 scheduler、raw clip 跨边界或 Mode C；
- 不把本地动画状态当成世界真相。

## 分阶段实施

1. **Asset staging**：将街区 environment/collision/navigation 和三个指定角色以稳定版本 staged 到 Godot 仓库，建立 manifest/binding 记录。
2. **Scene shell**：创建 `StreetCombatDemo.tscn`、碰撞、导航、出生点、相机和基础 lighting。
3. **Character integration**：为三个角色完成 skeleton/action binding，接入共享 `CharacterReplica` 和角色智能体 execution consumer。
4. **Combat vertical slice**：接入玩家/agent structured combat requests、authority results、受击和恢复。
5. **HUD**：实现状态、目标、战斗 feed 和 agent intent UI。
6. **Verification**：先红后绿的 runtime tests、street-combat profile、Phase 0 回归和最终 all harness。
