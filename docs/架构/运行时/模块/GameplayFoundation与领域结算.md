# Gameplay Foundation 与领域结算

状态：`current-code-and-evidence baseline; bounded reference closure implemented; broader domains planned`

本文记录当前已落地的 Gameplay Foundation。它把可回放的玩法领域事实放在
`backend/app/gameplay/`，并通过各领域 authority 结算为原子事件批次。本文只陈述
已存在的 owner、代码和 Harness 证据；动态经济、组织经营、政府监管、通用调度和社会
模拟仍是后续增量，不能被本模块的存在提前宣布完成。

## 事实来源与文档关系

当前边界按以下顺序确认：

1. [Character Gameplay Foundation spec tree](../../../superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/README.md)
   与 matching [plan tree](../../../superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/README.md)；
2. `backend/app/gameplay/`、`backend/app/character_agent/skills/`、`backend/app/main.py`
   和相邻 authority service 的实际代码；
3. [Harness 规则](../../../harness.md) 及 `.harness/verification/*-report.json`。

[全域架构责任矩阵](../../../8月分析/全域架构/00-系统边界与责任矩阵.md) 是在此
运行时事实之上叠加的增量 owner 导航；[架构审计](../../../8月分析/架构审计/23-缺漏审计与补强路线.md)
则据此列出尚未收口的补强顺序。两者不创建第二个 Gameplay runtime、event store 或
settlement owner。

## Owner 与非 Owner

| 范围 | 当前 owner | 不能替代什么 |
| --- | --- | --- |
| 玩法领域真相、原子提交、回放和 committed outbox | `GameplayEventStore` 与各 `backend/app/gameplay/*` authority | 不是角色 cognition、世界实体总库或 Godot 状态 |
| 世界对象/环境交互的语义或物理结果 | ESM 与交互编排 | 不拥有账户、库存、装备、产权、债务或合同 stream |
| 跨层 `AuthorityEvent` 路由与前端兼容投影 | System L6 | 不是 Gameplay 的 canonical event log 或交易账本 |
| 私有理解、目标、记忆与角色意图 | CharacterAgent L1-L4 | 不直接写入玩法领域事实 |
| 本地镜像、预测与表现 | Godot/BackendBridge | 不确认交易、背包或状态变更 |

`GameplayEventStore` 是玩法领域的提交后历史来源；checkpoint、facade、镜像和解释
都是可重建或受限投影。System L6 的 `AuthorityEvent` 是跨层消息总线，不取代该历史。
`GameplayOutboxDispatcher` 只会在 commit 后派发，不能把未提交 proposal 变成可见事实。

## 已实现的事件与结算脊柱

```text
typed gameplay command / trusted capability proposal
  -> owning domain authority validates principal, revision, preconditions and costs
  -> AtomicEventBatch
  -> GameplayEventStore.append_batch
  -> committed domain events + idempotency receipt + committed outbox
  -> replay/checkpoint rebuild + filtered mirror/projection + eligible authority-bus delivery
```

这条脊柱已经有原子 batch、乐观 revision、幂等、schema registry、event upcast、replay、
checkpoint 与 commit-after outbox 基础。它不是万能 coordinator：已落地领域各自构造
和验证事件；尚未存在的跨域 adapter 必须先进入正式 spec/plan，再复用该批次提交路径。

## 当前代码与已验证范围

| 子域 | 主要代码 | 已验证的可复用事实 | 明确不等于 |
| --- | --- | --- | --- |
| 事件脊柱 | `event_store.py`, `dispatcher.py`, `replay.py`, `event_schema_registry.py` | 原子 append、idempotency、outbox、replay 与 schema/version 边界 | 外部持久化或所有玩法域已完成 |
| 状态组合 | `runtime_state.py`, `state_group_*.py`, `phase3_state_composer.py` | state group 注册/生命周期、只读 facade、受限消费视图和 revision metadata | 一个可任意写入的角色总对象 |
| 身体与状态 | `resource_body_runtime.py`, `status_tags.py`, `modifier_runtime.py`, `effective_stats.py` | 资源、身体、状态 tag、modifier 与有效属性的 authority/replay 基础 | 完整生存、疾病或时间驱动需求模拟 |
| 背包与装备 | `inventory_runtime.py`, `equipment_runtime.py` | 容器、负重、放置/激活和装备关联的 authority slice | 通用物品经济或全量装备系统 |
| 产权与经济原语 | `ownership_runtime.py`, `land_right_runtime.py`, `economy_runtime.py`, `fixed_offer_purchase.py`, `gift_runtime.py`, `debt_runtime.py`, `contract_runtime.py`, `credential_runtime.py` | 账户转账、固定报价购买、赠与、产权/地契分离、简单债务和已注册条款合同 | 动态市场、工资、税收、企业经营、信用市场或政府监管 |
| 技能与行动门槛 | `character_agent/skills/*`, `ability_runtime.py`, `skill_action_gate.py` | 角色技能定义/评估、能力与当前 affordance、动作门槛的受控接合 | 模型自行确认动作成本或完整战斗系统 |
| Patch 与可信能力 | `patch_runtime.py`, `patch_rule_settlement.py`, `patch_lifecycle_authority.py` | 不可变 manifest、声明式 Rule IR、受信任 capability、受限迁移和生命周期 | 内容包可执行任意 Python/GDScript |
| 镜像与参考包 | `godot_mirror_*.py`, `adventure_basic_*.py` | 过滤镜像、session/read scope、commit 后交付，以及五个 `adventure-basic` 场景 | 通用客户端 authority、完整 transport durability 或任意玩法包发布 |

`gameplay-foundation-all` 的聚合报告当前为通过。它只聚合各子 profile 的明确结论，
不把某个 reference scenario 推广为通用领域完成。`adventure-basic` 的已验证范围是：

- 买剑并装备；
- 受伤或 stamina 不足时拒绝已知剑术动作；
- 储物戒容器与负重约束；
- 地契物品与土地产权分离；
- 赠与、简单债务和受限 typed contract 生命周期。

相应证据为 `.harness/verification/gameplay-foundation-all-report.json`、
`.harness/verification/gameplay-economy-authority-report.json`、
`.harness/verification/godot-gameplay-mirror-report.json` 和
`.harness/verification/adventure-basic-report.json`。最后一项还证明这些受治理场景的
backend、replay、filtered mirror 与 real-Godot delivery；并未证明动态市场或组织模拟。

## 与相邻运行时的接合

```text
Godot / CharacterAgent structured intent
  -> ESM or a Gameplay domain authority, according to the owned fact
  -> authoritative result or GameplayEventStore batch
  -> filtered Gameplay mirror and/or committed outbox
  -> System L6 only for eligible cross-layer AuthorityEvent consumers
  -> Godot presentation, Character writeback, Siming catalyst input
```

- ESM 继续结算对象、环境和物理交互结果；当前没有一个通用的 ESM-to-Gameplay
  coordinator 可接管所有 domain writes。
- Gameplay authority 直接拥有其账户、背包、装备、身体、产权、债务和合同事实；它不应
  把它们塞回 ESM 或 System L6。
- `world_runtime` 提供 L1 facts、perception、scheduling/continuity 辅助和 VLA 慢路径。
  它尚未实现全域实体/语义/时钟 owner，未来扩展只能在既有入口上增量收口。
- CharacterAgent 可以根据技能、affordance、私有感知和需要提出结构化意图；其内部状态
  不绕过 domain authority 直接改余额、库存或状态。
- Godot 只消费被 scope 过滤的 mirror 和 authority result。预测被拒绝时必须回滚本地预测，
  不能反写 canonical event history。

## 后续增量的进入条件

经济、建造、生存、商业组织和政府监管的下一阶段应把本模块作为地基，而不是重新设计：

1. 动态市场、生产设施、需求、组织账本和税费应由各自新 domain authority 拥有事实，
   通过既有 `append_batch` 和 outbox/replay 提交；
2. 时间、调度、实体语义与 Rule IR 的通用能力必须扩展当前 `world_runtime`、Patch 与
   Gameplay authority 路径，不新增平行 scheduler、event bus 或 store；
3. 每一个跨域 vertical slice 必须证明成功、拒绝、幂等、revision 冲突、回放和过滤投影，
   才能把 [8 月增量设计](../../../8月分析/README.md) 的 `planned` 条目上调为 `implemented`。

具体的目标边界与 backlog 在全域架构、玩法系统和架构审计中维护；它们是本运行时
事实基线的后续工作，不是当前模块额外拥有的运行时。
