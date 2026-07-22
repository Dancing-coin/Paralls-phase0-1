# Gameplay Domain Extension Catalog Design

Status: `awaiting-user-review`

Date: `2026-07-23`

## Purpose

给 Character Gameplay Foundation 建立完整但有实施分层的玩法领域目录，说明每类玩法如何通过状态组、Rule IR、受信任 capability、authority settlement、事件和 Godot binding 接入，而不是不断扩张一个固定角色 schema。

本目录区分：

- foundation 必须提供的公共机制；
- `adventure-basic` 首批实现的纵向闭环；
- 已冻结扩展契约但不在首批实现的领域；
- 尚需独立设计、不得提前硬编码的生产级领域。

## Scope

- 玩法领域分类、依赖层级和 ownership 边界。
- 每类扩展必须声明的 manifest、状态、命令、事件、投影、权限和验证面。
- 首批与后续范围的明确切割。
- 战斗、修炼、经济市场、制作、建造、任务、生存、社交、组织等扩展目录。
- 跨领域组合规则和禁止耦合方式。

## Non-goals

- 不在本文穷举每个游戏内容、数值表、配方、功法或任务。
- 不把目录中的“后续”领域视为已批准实现。
- 不引入任意第三方 Python/GDScript 执行。
- 不定义通用万能 DSL 来复制完整编程语言。
- 不重做现有 character mind core、L1-L4、authority 或 Siming runtime。
- 不实现动态市场、修炼闭环、完整战斗、制作、建造或任务系统。

## Dependencies

- `2026-07-23-foundation-invariants-and-domain-boundaries-design.md`
- `2026-07-23-state-group-registry-and-runtime-facade-design.md`
- `2026-07-23-event-sourcing-and-authority-settlement-design.md`
- `2026-07-23-gameplay-patch-rule-ir-and-capabilities-design.md`
- `2026-07-23-resource-status-body-and-effective-stats-design.md`
- `2026-07-23-inventory-container-and-encumbrance-design.md`
- `2026-07-23-ownership-economy-and-transaction-design.md`
- `2026-07-23-equipment-runtime-design.md`
- `2026-07-23-skill-ability-graph-and-affordance-design.md`
- `2026-07-23-godot-runtime-mirror-and-prediction-design.md`

## Extension Maturity Levels

| Level | Meaning | Completion claim allowed |
|---|---|---|
| `foundation` | 公共运行机制，首批必须实现 | 可按 foundation harness 声称实现 |
| `reference` | `adventure-basic` 中的最小真实玩法闭环 | 只能声称参考闭环，不是生产内容系统 |
| `contract-frozen` | schema、边界和接入点已定义 | 只能声称接口冻结，不能声称 runtime 已实现 |
| `future-design` | 仅登记领域与依赖，仍需独立 spec | 不能开始实现核心规则 |

目录状态必须出现在 patch manifest、README 依赖矩阵和 harness report 中，避免“有接口”等同“已完成”。

## Standard Domain Extension Contract

每个领域扩展必须提供：

```text
domain_id / domain_version / maturity_level
owned_aggregates
registered_state_groups
commands
events and event versions
projection schemas
Rule IR definitions
requested trusted capabilities
authority policies
privacy policies
Mind Frame projections
Godot bindings
dependencies / conflicts
install / enable / disable / upgrade behavior
upcasters / rebuild policy
failure codes
harness profile
```

### Ownership Rule

一个字段只能有一个 canonical domain owner。其他领域通过 ID、projection 或 settlement proposal 引用，不复制真相。例如：

- 市场报价归 market projection；货币余额归 economy account。
- 修炼动作可消耗 spirit resource，但 resource current 归 ResourceState。
- 战斗造成伤势 proposal，Body Runtime settlement 产出伤势事件。
- 任务奖励提出 item/currency/right effect，实际写入归 inventory/economy authority。

### Composition Rule

跨域组合必须遵循：

```text
command
-> typed read set + expected revisions
-> Rule IR / trusted capability proposal
-> one authority settlement
-> atomic event batch
-> independent domain projections
```

禁止：

- 玩法包直接写 store 或 Godot 节点。
- 用加载顺序决定 modifier 胜负。
- 为方便查询把其他领域完整状态复制进自己的 aggregate。
- patch disable 时删除历史事件。
- 后续领域扩展不得默认获得 actor-private 或 world authority 权限。

## Foundation Catalog

| Domain | Maturity | Canonical ownership | Required proof |
|---|---|---|---|
| state-group registry/runtime façade | `foundation` | 动态组装、schema、revision vector | 按 actor/world/patch 装配与重建 |
| event sourcing/settlement | `foundation` | 事件流、原子批次、幂等 | 完整重放、冲突、零部分提交 |
| resources/status/body/stats | `foundation` | 资源、tag、身体状态、有效属性投影 | modifier 可解释、阻断可复现 |
| inventory/container/encumbrance | `foundation` | 物品位置、容器、负重 | 普通容器与忽略传播容器 |
| ownership/economy primitive | `foundation` | 余额、产权、债务、契约、交易 | 买卖/赠与/转权原子性 |
| equipment | `foundation` | 槽位、装备 grant 生命周期 | 装卸授予与撤销一致 |
| skill/ability/affordance | `foundation` | 稳定能力与即时可用性 | 已学会与当前受阻分离 |
| gameplay patch/Rule IR | `foundation` | 注册、规则、capability、生命周期 | install/enable/upgrade/rebuild |
| Godot runtime mirror | `foundation` | 前端只读镜像和预测 overlay | 路由、重连、回滚、隐私 |

## Reference Domain: `adventure-basic`

Maturity: `reference`。

它组合 foundation，而不取得 foundation aggregate 所有权，覆盖：

- health、stamina 等最小资源。
- arm injury、fatigue、overloaded 等身体/状态约束。
- sword skill 与 swing affordance。
- backpack、长剑、地契、实体或抽象货币。
- storage ring 特殊容器与装备槽。
- 固定报价的买卖/赠与/产权转移事务。
- Godot 状态条、背包、装备和失败反馈镜像。

明确不包含：修炼、动态价格、供需、税费、生产链和完整战斗 AI。

## Combat Domain

Maturity: `contract-frozen`，首批只通过剑术动作约束验证接口。

建议拥有：

```text
CombatEncounterState
CombatantRuntimeProjection
threat / stance / guard / stagger / opening
combat action policies
damage and defense proposals
```

依赖：Resource、Body、Status、Equipment、Ability、Authority。

边界：

- damage calculation 可以由 combat rule 提 proposal；health 与 injury 的最终事件由所属领域写入。
- 仇恨、战斗回合/实时窗口归 combat；长期敌意归 actor-private relationship。
- 命中动画不是命中事实，Godot contact 只能作为受验证输入。
- 完整战斗节奏、AI、网络同步和伤害模型需要独立 spec。

## Cultivation Domain

Maturity: `contract-frozen`；不进入首批实现。

冻结的扩展对象：

```text
CultivationState
  realm_id
  stage_id
  cultivation_progress
  bottleneck_state
  deviation_risk
TechniqueDefinition / TechniqueGrant
CultivationSession
BreakthroughAttempt
```

典型依赖：

- spirit/qi 作为注册的 ResourceDefinition，而非硬编码核心字段。
- 功法作为稳定 grant/knowledge source，与装备临时 grant 区分。
- 境界和瓶颈由 cultivation event stream 持有。
- 突破通过 command -> condition/cost -> settlement -> event batch。
- 走火入魔可提出 Body/Status effect，但不能直接写身体 store。

冻结命令/事件命名面：

```text
cultivation.start_session
cultivation.complete_session
cultivation.attempt_breakthrough
cultivation.session_completed
cultivation.progress_gained
cultivation.breakthrough_succeeded
cultivation.breakthrough_rejected
cultivation.deviation_triggered
```

具体境界表、修炼公式、功法冲突和突破概率仍需独立设计。

## Market Economy Domain

Maturity: `future-design`；首批只有固定交易与物权基础。

未来拥有：

```text
MarketState
MerchantOfferBook
regional supply/demand projection
price formation policy
tax/tariff policy
production/consumption signals
```

边界：

- market 生成报价，Economy Authority 仍负责扣款、转权和交易记录。
- 商人库存是真实 Inventory/Container projection，不是报价表里的虚构数量。
- 动态价格不能追溯改写已成交交易。
- 税费是同一原子 settlement 中的独立 ledger event。

## Crafting And Production Domain

Maturity: `future-design`。

预计包含 recipe、workstation、input reservation、work progress、quality proposal 和 output settlement。材料消耗与产物创建必须同一原子批次；长耗时制作需另行决定 reservation 与中断语义，不能直接套用瞬时交易。

## Building And World Asset Domain

Maturity: `future-design`。

预计包含 blueprint、construction site、world placement constraints、construction progress 和 completed asset。地产所有权归 Ownership，物理占位与环境变化归 World Authority，建造玩法只协调 proposal。

## Quest And Narrative Objective Domain

Maturity: `future-design`。

预计包含 objective graph、acceptance visibility、progress evidence、reward proposal 和 failure/expiry。任务进度不能通过客户端按钮直接设置；必须消费 authority/world evidence。它与 Siming StoryBeat 相邻但不同：任务是玩法契约，StoryBeat 是司命态势读模型。

## Survival Domain

Maturity: `contract-frozen`，首批只使用 fatigue/body/resource 的最小切片。

未来可注册 hunger、thirst、temperature、sleep 和 disease rules。它们复用 Resource/Body/Status，不另建一套生命条；环境暴露经 world fact/authority 输入，周期更新由世界调度器驱动。

## Social Gameplay Domain

Maturity: `contract-frozen`，关系图 runtime 后续实施。

未来包含 persuasion、reputation、faction permission、promise/obligation gameplay。客观契约归 authority relationship/economy，主观信任归 actor-private relationship，dialogue 文本本身不构成 settlement。

## Organization And Governance Domain

Maturity: `future-design`。

预计包含 membership、role、treasury permission、collective asset rights、policy vote 和 delegated authority。组织不是普通 actor 背包；组织资产使用独立 owner ref 和账户/容器，角色只有被授予的访问或代表权。

## Companion, Pet And Mount Extensions

Maturity: `contract-frozen`。

- 随从、仆从、宠物和坐骑始终是独立 `Actor`。
- Ownership/Relationship 只记录雇佣、监护、租用、指挥或世界设定允许的权利。
- 不能将 actor 作为 `ItemInstance` 放入容器、销毁或直接转移本体。
- 坐骑装备、货物容器和角色契约分别由 Equipment、Inventory 和 Relationship/Ownership 管理。

## Domain Dependency Order

```text
identity / event / authority / governance
-> state registry + resource/body/status
-> inventory + ownership
-> equipment + ability + modifier
-> patch/Rule IR + Godot mirror
-> adventure-basic reference
-> combat / cultivation / survival / social contracts
-> market / crafting / building / quest / organization future designs
```

下游领域可以依赖上游稳定接口；上游 foundation 不得反向依赖某个具体玩法包。

## Authority And Privacy Invariants

1. 每个 canonical 状态只有一个 domain owner。
2. 所有跨域写入经 authority settlement 和原子事件批次。
3. patch 只能请求 manifest 已声明且系统授权的 capability。
4. actor-private 数据按最小权限投影，不因某玩法“需要关系”而自动开放。
5. Godot binding 只能消费投影并提交请求，不能实现权威规则。
6. 后续领域默认无 world write、经济 write 或 private read 权限。
7. 目录的成熟度是 completion claim 的硬门禁。

## Failure Semantics

| Failure | Required result |
|---|---|
| undeclared domain dependency | patch install rejected |
| duplicate canonical ownership | `domain_state_ownership_conflict` |
| missing required capability | patch remains disabled |
| cross-domain direct write | settlement rejects and security trace records |
| maturity level overstated | harness/docs contract fails |
| future event version unknown | rebuild gate fails closed |
| domain disable with live transaction | transaction pins old version; disable waits or rejects |
| actor modeled as item | schema/contract validation rejects |

## Acceptance Criteria

1. 每个领域都有明确 maturity、canonical ownership、依赖和非目标。
2. `adventure-basic` 只组合 foundation，不创建平行资源、背包、物权或装备 store。
3. 修炼接口被冻结但没有被首批 harness 当作 runtime 功能。
4. 动态市场、制作、建造、任务和组织明确要求后续独立 spec。
5. 战斗伤害、修炼副作用、任务奖励等跨域结果都只能形成 proposal，再由所属领域结算。
6. companion/pet/mount fixture 证明 actor 与支配权分离。
7. manifest validation 能拒绝未声明依赖、capability 和重复 domain ownership。
8. foundation 不反向 import `adventure-basic` 或任何后续玩法包。

## Harness Mapping

- `gameplay-foundation-contract`：目录 schema、maturity、依赖、ownership lint。
- `gameplay-patch-runtime`：manifest/capability/生命周期验证。
- `adventure-basic`：唯一首批 reference 玩法闭环。
- `gameplay-foundation-all`：聚合并检查未实现领域没有虚假完成声明。

后续领域启用时必须新增独立 harness profile，不能仅通过 `gameplay-foundation-all` 中的 schema fixture 声称 runtime 完成。
