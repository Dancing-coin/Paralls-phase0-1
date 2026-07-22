# Character Gameplay Foundation Invariants And Domain Boundaries Design

Status: `awaiting-user-review`

Date: `2026-07-23`

## Purpose

定义 `Character Gameplay Foundation` 的共同边界、术语和不可破坏的不变量。后续状态组、事件存储、物品、经济、装备、能力与玩法 patch 规格都必须服从本文件，不能各自创造新的真相源或跨域直写路径。

本规格是既有 `world-character-Siming-authority unified runtime` 的子规格，不替换已经完成的 character mind core，也不把历史 `Phase 0` smoke path 重新提升为仓库主线。

## Scope

本文件覆盖：

- 角色静态档案、心智运行态、游戏运行态和世界真相的分层；
- 后端、Godot、character mind、玩法 patch 与各领域服务的写入权限；
- 跨领域共用的 identity、revision、evidence、privacy 与 error 值对象；
- command、authority settlement、event、projection、façade 和 Godot mirror 的单向数据流；
- 关系图、能力图和司命图谱之间的治理边界；
- 首批实现必须保持的安全、确定性和可解释性约束。

## Non-goals

本文件不定义：

- 完整角色心智核心或 L1-L4 的内部实现；
- 具体物品、经济、装备、能力或关系 schema；
- Rule IR 的语法、解释器或 capability handler；
- 任意第三方代码沙箱；
- 完整事件存储数据库选型；
- 完整修炼、动态市场、生产、建造或任务内容；
- 通用图数据库内核。

## Dependencies

规范依赖按优先级排列：

1. `../2026-06-29-world-character-siming-authority-mainline-master-design.md`
2. `../../2026-06-29-complete-character-mind-core-design.md`
3. `../../../../character/character-mind-core-status.md`
4. `../2026-06-29-authority-and-settlement-runtime-closure-design.md`
5. 本子树的 master design 与 README（由同批规格建立）

实现依赖既有 structured protocol、authority settlement、world runtime identity 和 character mind façade；本规格不允许绕过这些已存在边界建立第二套主线。

## Canonical Layer Model

### Static authored truth

角色档案保存“这个角色长期是谁”，包括身份、出身、人格、背景、初始能力和 authored relationship seed。运行时受伤、背包变化或短期情绪不得反写并伪装为 authored truth。

### Character mind runtime

既有 `CharacterDynamicState`、`NeedTensionState`、目标生态、记忆和 L1-L4 继续由 character mind 领域拥有。游戏状态只通过经过 privacy 与 salience 过滤的投影进入 Mind Frame。

### Character gameplay runtime

资源、身体、状态标签、背包、产权、装备、技能授予和即时能力可用性由独立领域服务与事件流维护。`CharacterGameRuntimeState` 只是这些投影的组合 façade，不是可供模块任意修改的聚合根。

### World truth

世界对象、环境、资产和权威关系的变化仍由 backend authority settlement 裁决。角色游戏领域不能因本地 UI、动画或脚本效果直接改变世界真相。

### Local presentation

Godot 持有带版本的只读镜像，可进行 UI、动画、音频、局部计算和可回滚预测。Godot 可以提交 structured intent 或 state-group enable/disable request，但只有后端确认后才成为权威事实。

## Domain Ownership Matrix

| 数据或行为 | 权威所有者 | 允许写入者 | 主要消费者 |
| --- | --- | --- | --- |
| authored character dossier | dossier/profile service | authoring/migration gate | mind、gameplay façade |
| mental dynamic state | character mind runtime | L2/L3 受控写回 | Mind Frame、受限 façade |
| gameplay domain state | 对应 backend domain service | authority settlement | façade、Godot mirror、mind projection |
| world object/environment truth | world authority | authority settlement | world projection、Godot |
| Godot mirror/prediction | Godot local runtime | mirror applier / predictor | UI、表现、局部反馈 |
| gameplay rules | enabled patch revision | backend patch runtime | settlement、resolver |
| relationship facts | relationship domain | 对应 authority/private writer | 受限组合投影 |
| Siming knowledge | Siming graph runtime | 允许的 ingest path | Siming query/summary |

一个字段只能有一个权威所有者。缓存、快照、façade 和图谱投影均不是第二真相源。

## Shared Value Objects

跨域只共享治理值对象，不共享一个万能领域模型：

```text
EntityRef
  entity_type: actor | item | container | world_asset | account | contract | ...
  entity_id: opaque stable id

AggregateRef
  aggregate_type
  aggregate_id

SourceRef
  source_type
  source_id
  source_revision?

EvidenceRef
  evidence_type
  evidence_id
  source_lineage[]

PrivacyScope
  public | authority | actor_private(actor_id) | restricted(policy_id)

AuthorityScope
  world | actor_gameplay | actor_mind | economy | relationship | siming

RevisionVector
  entries: map<aggregate_ref, non_negative_integer>
```

所有 ID 都是 opaque stable identifier。显示名称、Godot node path 和数组位置不能充当跨边界 identity。

## Canonical Runtime Flow

```text
Structured Intent / Command
  -> identity, permission and schema validation
  -> state-group and domain preconditions
  -> resource/cost reservation proposal
  -> rule, modifier and capability evaluation
  -> authority settlement
  -> atomic append of immutable domain event batch
  -> domain projections
  -> CharacterGameRuntimeState façade
  -> privacy-filtered Mind Frame / Godot snapshot or delta
```

Rule IR 或受信任 handler 只能提出 typed effect proposal，不能直接修改 store、projection、Godot node 或世界对象。

## Interfaces

### Command boundary

所有跨边界写请求至少包含：

```text
command_id
command_type
command_version
actor_ref
payload
idempotency_key
expected_revisions
causation_id
correlation_id
source_ref
requested_at
```

键盘、鼠标、摄像机噪声不能直接进入 backend business command；Godot 必须先编译为 structured intent。

### Projection boundary

投影输出必须标明：

```text
schema_id
schema_version
projection_revision
source_revision_vector
generated_at
privacy_scope
payload
```

读取者不得把缺失字段解释为零值。缺失可以表示未启用、未授权、未物化或 schema 不支持，必须由 group metadata 区分。

### Failure envelope

跨领域统一失败外壳为：

```text
error_code
message
retriable
command_id
transaction_id?
failed_stage
failed_precondition?
expected_revision?
actual_revision?
source_refs[]
recovery_action
```

领域可扩展 `details`，但不得用自由文本代替稳定的 `error_code` 与机器可读字段。

## Authority Invariants

1. 后端事件流是 gameplay 与 world 变化的唯一权威真相；Godot 永远不是权威写入者。
2. `CharacterGameRuntimeState` 是组合 façade，不允许通过修改 façade 反写领域状态。
3. 状态组按世界配置、角色 archetype、玩法包和权限动态装配，不存在所有角色固定拥有的全量状态全集。
4. 每次权威变化必须源于可审计 command、system trigger 或 migration command，并产生不可变事件。
5. 跨域结算必须以单个 `transaction_id` 原子追加事件批次；失败时零提交。
6. checkpoint、缓存、Godot mirror、Mind Frame、能力 affordance 和图谱均为可重建读模型。
7. 心智私有状态不会因为 backend 可访问而自动暴露给 Godot、Siming 或其他角色。
8. `EffectiveStatsProjection` 和其他派生值不能被直接写入。
9. 关系图、能力图和 Siming Perspective/Knowledge Graph 保留独立节点、边、查询与存储；只共享证据、来源、权限、生命周期、冲突和解释协议。
10. actor 始终是 actor；雇佣、监护、租用、坐骑或指挥关系以权利/契约表达，不能把 actor 当作可销毁或可入背包的普通 item。
11. patch disable/upgrade 不改写历史事件，只影响后续 command 使用的规则 revision 与投影解释版本。
12. 任何本地预测都必须可通过 `prediction_id` 确认或回滚，并最终对齐权威 revision。

## Failure Semantics

- schema 或 identity 无效：在业务校验前拒绝，不产生事件。
- 权限不足：返回 `authority_denied`，不得泄露被保护状态是否存在。
- 状态组未启用：返回 `state_group_not_enabled`，不得隐式物化。
- revision 不匹配：返回 `revision_conflict`，要求刷新后显式重试。
- 跨域部分写入风险：整批 settlement 失败，`committed=false`。
- 投影失败：隔离投影并保留事件真相，不能回滚或删除已提交事件。
- privacy 过滤失败：fail closed，不输出未过滤 payload。
- Godot mirror 漏包、乱序或 schema 不兼容：停止应用增量并请求完整 snapshot。
- 未知图谱/领域引用：保留 typed unresolved reference 或拒绝写入，不能猜测映射。

## Acceptance Criteria

1. 所有子规格都明确唯一权威所有者、允许写入者和读模型消费者。
2. 任意 gameplay 变更都能追溯到 command/source、settlement 与 event batch。
3. 代码实现中不存在 Godot 直接写 backend store、projection 反写 store 或 façade 反写领域的路径。
4. 同一角色可因 archetype/world/patch 不同拥有不同状态组，消费者能区分 disabled、unauthorized 和 absent。
5. 私有心智或关系数据在未授权 façade、Godot snapshot 和 Siming ingest 中不可见。
6. 跨域失败证明没有部分事件提交，成功事件共享同一 transaction/causation chain。
7. 从完整事件流可重建所有权威投影，checkpoint 删除不改变最终结果。
8. 关系、能力、Siming 三类图可独立演进且共用治理值对象，没有通用图核心的首批依赖。

## Harness Mapping

### Current review gate

- `python scripts/verification/harness.py --profile docs`
- `python scripts/verification/harness.py --profile all`

在 `awaiting-user-review` 阶段，`docs` profile 只证明文档结构和链接纪律，不证明本规格已实现。

### Required implementation profiles

- `gameplay-foundation-contract`：验证 command/projection/error envelope 与 authority ownership。
- `gameplay-event-replay`：验证事件为唯一真相、checkpoint 非真相。
- `gameplay-state-groups`：验证动态装配和 façade 只读边界。
- `godot-gameplay-mirror`：验证 Godot 只读镜像、预测与回滚。
- `gameplay-foundation-all`：聚合本子树全部实现证据。

这些 profile 在实现计划落地时必须注册到 `.harness/profiles/`、`.harness/rules/` 和 `docs/harness.md`；注册前不得声称为可运行证据。
