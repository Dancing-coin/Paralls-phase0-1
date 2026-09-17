# 角色动作底座操作手册与文档索引

日期：`2026-09-15`

状态：`导航与执行手册；2026-09-14 动作底座实现尚未开始`

## 用途与范围

本手册覆盖“统一角色身体与 3D 动作底座”所直接依赖的 spec、plan 和
运行时事实文档。它的目标是让执行者能够回答四个问题：

1. 当前应以哪一份设计和计划为准？
2. 某项改动应落在哪个阶段、读取哪些依赖文档？
3. 哪些旧方案只可用于理解迁移原因，不能作为新的实现入口？
4. 每一阶段需要什么验证证据，才能推进到下一阶段？

“相关”采用以下边界：

- **直接相关**：定义或执行 `IntentProposal`、多动作仲裁、Motor、物理
  证据、资产资格化、`ActionAttempt`、CharacterAgent/INF/Siming 输入、或
  Mode B 联网语义动作的文档。
- **直接依赖**：定义既有 ESM/Gameplay 结算、Gameplay mirror、具身动作
  控制器、会话/attestation、事件总线和主线 authority 边界的文档。
- **迁移/历史**：解释当前 `CharacterReplica`、PlayerShell、旧 root-motion、
  早期 CharacterAgent/Siming 桥为何存在的文档。它们不授权新路径。
- **上游业务/参考**：CharacterAgent 的记忆、推理、人格、技能和 Siming 计划，
  以及 INF owner-contract、剧情/经济/社会玩法包与 `docs/phase1` 参考副本。它们
  可决定“为什么提出动作”或“动作要结算什么”，不能定义身体、动画或 authority
  写入路径。

本表的“完整”有明确的可复查边界：所有定义动作底座当前契约、直接运行时边界、
已存在迁移实现或其直接 authority/asset/interaction 依赖的 spec/plan 都会列出具体
文件或可展开的完整文档组；INF 的逐领域 owner row 只通过其树入口索引，因为它们
不是每个角色动作的共同前置条件。不能从表中没有一个具体业务动作，而推断该业务
可以绕过 ESM/Gameplay 或新动作底座。

## 一分钟结论

新工作只按以下顺序判断：

```text
AGENTS.md
  -> 主线 authority 边界
  -> 2026-09-14 统一动作底座主 spec
  -> 四份 2026-09-14 子 spec
  -> 2026-09-14 统一主实施计划（唯一执行顺序）
  -> 对应专题计划的细化测试与文件提示
  -> 当前状态/漂移审计确认实际迁移点
```

以下边界永远优先于历史实现：

- Godot 是本地身体、输入、碰撞与表现 owner；不是世界真相 owner。
- `CharacterMotor` 是唯一 `CharacterBody3D` 位移、速度、重力、碰撞、root
  motion 消费和 `move_and_slide()` owner。
- CharacterAgent、INF、Siming、动画、调试工具只能提交语义 proposal、证据
  或表现提示；不能直接写 Transform、Velocity、伤害、死亡、库存或状态真相。
- ESM/Gameplay 是世界后果 owner。标记和本地碰撞只有证据资格，只有
  `AuthorityResult` 能投影权威结果。
- Phase 1 是本地 kinematic `CharacterBody3D` + Mode B 语义联网；不是
  raw-pose、rollback 或多人刚体物理权威。
- Phase 1 的武器范围是一个 qualified held-item binding、一个 melee
  `ActionAttempt` 闭环和一个 hitscan semantic route fixture；不包含弹药、
  弹道、双持、拼刀或任意道具武器化。

## 文档权威层级

| 优先级 | 文档层 | 发生冲突时的处理 |
| --- | --- | --- |
| 0 | `AGENTS.md` | 运行时 owner、范围和验证约束，必须遵守。 |
| 1 | 主线 master design 与 2026-09-14 统一动作底座 spec/子 spec | 设计真相；覆盖旧 actor、asset、local-damage 解释。 |
| 2 | 2026-09-14 统一主实施计划 | 唯一任务顺序和验收门；不得以专题计划改写顺序。 |
| 3 | 2026-09-14 五份专题计划 | 任务级实现/测试细化，只能补充主计划对应任务。 |
| 4 | current-state、drift audit、migration status、运行时架构文档 | 当前事实、迁移证据和代码定位；不改变设计。 |
| 5 | 六月方案、旧 root-motion、旧原子动作库和 reference 文档 | 迁移背景或已完成窄切片；不得复制为新的并行控制器。 |

## 操作手册

### 0. 开工前：锁定边界和当前事实

1. 阅读 `AGENTS.md`、主线 README、动作底座主 spec、四份子 spec、统一主
   计划的 Global Constraints 与 Fixed-Tick Contract。
2. 阅读 current-state ledger 和 drift audit，确认当前实际缺口：NPC 仍可能
   direct-step、资产尚未完成资格化、ActionAttempt 尚未成为通用链路。这些是
   待迁移事实，不是可复制的设计。
3. 在任何代码编辑前执行主计划 Task 1。登记活跃场景、角色壳、资产绑定、直接
   Transform/Velocity writer、`move_and_slide()` writer 和 backend ingress。
4. 不恢复已移入 archive 或被用户删除的王座厅/骑士场景。只迁移活跃 wrapper
   的引用，并保留用户当前工作区改动。

**本阶段门：** `CharacterMotor` 以外的 actor body writer 必须能被审计发现；
尚不能宣称统一身体或动作底座已运行。

### 1. 先完成共享契约，后触碰动作或动画

执行统一计划 Task 2-3，并以专题 S-01 为测试细化来源：

1. 规范化 `IntentProposal`、`LayerControlProposal`、`CharacterIntentFrame` 和
   `CharacterRuntimeState`。
2. 只接受 namespaced tags；confidence、provenance、revision、privacy、
   causation/correlation 是 metadata，不是状态 tag。
3. 实现 `ContinuousControlLease`、`ActionInstance` 和
   `ResourceClaimScheduler`。移动是可续期 lease；持续/离散动作是独立实例。
4. `ActorActionArbiter` 可在同一 tick 接纳不冲突动作。是否并发由 canonical
   visual + physical claim、locomotion relation、取消窗口和 profile 决定，
   不是“一个角色只能一个动作”。
5. 固化 deterministic key：physics tick、layer priority、source priority、
   source ID、action/lease ID。状态、死亡、抢占、取消都经 arbiter。

**禁止：** 新增按 Combat/Locomotion/Interaction 分别写 body 的 FSM；让 Agent
直接选 clip；让 debug 控件直接篡改私有 runtime state。

### 2. 收敛本地身体和物理

执行 Task 4-5，并以专题 S-02 为字段与失败矩阵来源：

1. 所有来源只产生 `MotionContribution`；composer 在固定 tick 生成唯一
   `PhysicsMotionCommand`。
2. 顺序固定为：lease velocity -> 合法 root/action contribution -> stable
   impulse -> bounded authority correction -> clamp -> Motor collision。
3. Player、NPC、agent、program 都经过 `ControllerPort -> Arbiter -> Frame ->
   Composer -> CharacterMotor`。
4. `CharacterMotor` 收集 `PhysicsContactEvidence`。它是 local/provisional，
   可随 attempt 发送但不能变更世界。
5. root motion 按 `hold`、`bounded_continue`、`reversible_continue` 执行；
   `drive_locomotion` / `replace_locomotion` 只暂停或限制 lease，恢复后按
   revision 续用它。

**必须验证：** wall、slope、step、support loss、root envelope、同 tick impulse
顺序、stale correction、local contact without marker、marker without support。

### 3. 资格化外部角色资产，而不是改写外部动作

执行 Task 6-8，并以专题 S-03 和资产交接文档为准：

1. 外部资源按 GLB、canonical mapping、rest pose、单位/前向、slot、source
   rate、locomotion/action timing sheet、report 入库。
2. 先检查 tracks，再决定 realization：`native_upper_body`、
   `derived_upper_body`、`full_body_exclusive`、`drive_locomotion` 或
   `additive`。
3. 任意 full-body source 都默认不是上半身并发动作。只有 mask/root/pelvis/
   lower body/seam/support/hand-weapon/marker/claim 全部资格化通过，才可作为
   concurrent profile。
4. rejected profile 不能进入 registry；`qualified_with_fallback` 必须把明确
   fallback 告诉 arbiter 和 debug overlay。
5. 第一里程碑需要两个外部角色 package。现有 crusader knight 是 package A；
   package B 位于 `assets/characters/external_character_b/`，交付前保持候选。
6. `atomic_sequence` 必须为 `[]`。它是未来语义原子库预留，不是现有 clip
   播放列表，也不得调用旧 action-atom catalog 绕过 claims。

7. 至少一个 package 必须提供一个合格的握持槽/手部锚点和带阶段 marker 的
   近战动作。hitscan 只要求语义请求、路由和 authority fixture，不要求第一期
   生成弹道、弹药或客户端命中结果。

**禁止：** runtime track surgery、按目录名猜并发、把标记当命中、资产中写伤害/
库存/状态结果、角色模型直接替换 `CharacterReplica` runtime shell。

### 4. 再接 CharacterAgent、INF、Siming 与 authority

执行 Task 9-10：

1. L4、INF 和 Siming 转换为 semantic proposal。Siming 是 catalyst；INF 提供
   goal/evidence/constraint/context；两者都不是 local pose 或 settlement route。
2. action phase marker 产生 `ActionAttempt` candidate；身体证据由 Motor/sensor
   附上。`EmbodiedActionController` 只负责 local phase 与 recovery。
3. 复用既有 `EmbodiedActionRequest`、`ActionWindowIntent` 和 Gameplay command，
   不建立第二个 authority channel。
4. ESM 负责 affordance/range/occupancy/object state；Gameplay 负责 resource/
   status/capability/equipment/body projection；跨两域时必须 atomic batch，
   否则显式 non-atomic reservation/compensation。
5. 使用 `attempt_id`、idempotency key、expected revision vector、causation 和
   correlation。duplicate 返回原结果；same key + different payload 拒绝；
   `unknown` 只能用原 key 查询。

**本阶段门：** pending/rejected/timeout/late result 不得复活 cancelled action，
且 local contact 在无 committed settlement 时世界零写入。

### 5. 接 Mode B，明确不启用 Mode C

执行 Task 11，并以专题 S-05 为协议细化来源：

1. Mode A 是 local embodiment；Mode B 是 Godot 传 semantic control/action/
   attempt，后端回传 authority result 与 Gameplay projection。
2. 每条 control/action 消息携带 session、actor、connection epoch、client
   sequence、physics tick、lease/action revision；authority request 还携带
   idempotency key 与 expected revisions。
3. reconnect 必须增大 `connection_epoch`、清掉 stale lease/prediction、取得
   fresh actor/gameplay snapshot 后再恢复控制。
4. `delivery_sequence`、`facade_revision`、`prediction_id` 是 Gameplay mirror
   字段，不能解释为 body state。
5. Mode C 的 `authority_epoch`、`body_revision`、snapshot/correction schema
   只保留类型和验证；没有明确 PhysicalAuthority、fixed tick、prediction/
   correction budget、interpolation/interest、replay 和 abuse validation 前不得
   启用。

### 6. 用工具、回放和真实场景关门

执行 Task 12-15：

1. debug overlay 只读 immutable post-arbiter/post-Motor snapshot。
2. test panel 只能提交带 `source=debug_fixture` 且会过期的正常 proposal/
   fixture；animation debugger 只能 preview，不能移动 body 或创建 attempt。
3. performance monitor 使用有界 samples，不允许影响 arbitration policy。
4. replay 比较逻辑确定性：frame、admission、command、evidence digest、attempt
   ordering、AuthorityResult 与 final projection；不声称刚体 bitwise replay。
5. 集成场必须使用两个 qualified package，真实 backend 和 Godot runtime，并
   记录截图、probe、trace、Harness 证据。
6. 最后更新 current-state/drift/INDEX/专题计划状态文字，确保 “Mode B” 没有被
   写成多人物理权威。

## 验证命令梯度

| 阶段 | 最低验证 | 何时可推进 |
| --- | --- | --- |
| 基线/共享契约 | 主计划 Task 1-3 的 focused pytest | ingress、claims、arbiter 的静态与逻辑 test 通过。 |
| Motor/物理 | focused pytest + `python scripts/verification/harness.py --profile godot-project` | 没有第二 writer；导入/静态 Godot check 通过。 |
| 资产 | qualification runner + asset focused pytest | report 非 rejected，且 fallback/来源完整。 |
| authority | settlement focused pytest + real backend route | duplicate/revision/zero-write 证据齐全。 |
| Mode B | protocol focused pytest + live bridge probe | reconnect/gap/old-epoch/resync 证据齐全。 |
| 里程碑 | `python -m pytest -v` + `python scripts/verification/harness.py --profile all` + Godot runtime capture | 两角色真实运行证据和报告已落盘。 |

不要用静态测试代替 Godot runtime 里程碑；不要用“动画看起来播放了”代替 authority
结算；不要用 mirror snapshot 代替 body physics replication。

## 索引表

### A. 直接权威 spec（必读）

| ID | 文档 | 角色 | 执行用途 |
| --- | --- | --- | --- |
| D-00 | `AGENTS.md` | 仓库运行边界 | 每次任务先读；定义 Godot/backend owner 与验证规则。 |
| D-01 | `docs/superpowers/specs/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-design.md` | 动作底座总设计 | tag、proposal、arbitration、ownership、tick、验收。 |
| D-02 | `docs/superpowers/specs/2026-09-14-character-physics-motion-and-contact-subspec.md` | 物理子 spec | contribution、Motor、evidence、root policy、failure。 |
| D-03 | `docs/superpowers/specs/2026-09-14-character-esm-action-attempt-settlement-subspec.md` | 结算子 spec | attempt、route、idempotency、atomicity、recovery。 |
| D-04 | `docs/superpowers/specs/2026-09-14-character-connected-action-and-physical-replication-subspec.md` | 联网子 spec | Mode A/B/C、mirror separation、reconnect、future body stream。 |
| D-05 | `docs/superpowers/specs/2026-09-14-character-animation-asset-qualification-and-concurrent-realization-subspec.md` | 动画资产子 spec | import、mapping、realization、full-body fallback、report。 |

### B. 当前唯一实施计划与专题参考

| ID | 文档 | 状态 | 使用规则 |
| --- | --- | --- | --- |
| P-00 | `docs/superpowers/plans/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-implementation-plan.md` | **唯一执行顺序；未实施** | 依 Task 1-15 和 completion gate 推进。 |
| P-01 | `docs/superpowers/plans/2026-09-14-character-shared-contracts-arbitration-and-tools-implementation-plan.md` | 任务级参考 | 只补充 P-00 Task 2-3、12。 |
| P-02 | `docs/superpowers/plans/2026-09-14-character-physics-motion-and-contact-implementation-plan.md` | 任务级参考 | 只补充 P-00 Task 4-5。 |
| P-03 | `docs/superpowers/plans/2026-09-14-character-animation-asset-qualification-and-concurrent-realization-implementation-plan.md` | 任务级参考 | 只补充 P-00 Task 6-8。 |
| P-04 | `docs/superpowers/plans/2026-09-14-character-esm-action-attempt-settlement-implementation-plan.md` | 任务级参考 | 只补充 P-00 Task 10。 |
| P-05 | `docs/superpowers/plans/2026-09-14-character-connected-action-and-physical-replication-implementation-plan.md` | 任务级参考 | 只补充 P-00 Task 11。 |

### C. 当前实现、迁移和资产事实（必查，不改写设计）

| ID | 文档 | 读取时机 | 作用 |
| --- | --- | --- | --- |
| F-01 | `docs/character/character-action-foundation-current-state.md` | 开工、Task 1、Task 14 | 当前实现缺口和第一里程碑事实。 |
| F-02 | `docs/character/character-runtime-design-drift-audit.md` | 设计/实现不一致时 | player/NPC/Agent/action/INF 的 drift 证据。 |
| F-03 | `docs/character/character-control-chain.md` | 改输入、Agent ingress、Motor 时 | 当前 human/agent/program 控制链。 |
| F-04 | `docs/character/character-action-asset-interface.md` | 改 descriptor/registry 时 | 资产字段索引；不得扩展成第二权威契约。 |
| F-05 | `docs/character/character-debug-and-verification.md` | 加工具、跑验证时 | 现有 observatory/debug/Harness 入口。 |
| F-06 | `docs/character/character-actor-architecture.md` | 改角色壳边界时 | shared actor 结构背景。 |
| F-07 | `docs/character/character-actor-final-convergence-target.md` | 迁移 host 时 | `CharacterReplica` lineage 的目标约束。 |
| F-08 | `docs/character/character-actor-final-convergence-gap-report.md` | 评审迁移缺口时 | 历史收敛 gap 对照。 |
| F-09 | `docs/character/character-actor-migration-status.md` | 查旧计划状态时 | actor-substrate 历史 ledger；不取代 D-01/P-00。 |
| F-10 | `docs/character/character-agent-runtime-architecture.md` | 改 L4/Agent 边界时 | 现有 CharacterAgent runtime 事实。 |
| F-11 | `docs/art-asset-qualification-requirements.md` | 接入资源包时 | active/candidate/qualified/approved 流转与普通绑骨底线。 |
| F-12 | `docs/art-resource-swap-workflow.md` | 替换角色/场景时 | Art Pack/adapter/runtime shell/binding profile 分层。 |
| F-13 | `docs/blender-godot-asset-export-convention.md` | DCC 导出时 | Blender 到 Godot 的导出约束。 |
| F-14 | `docs/scene-character-import-runtime-checklist.md` | 导入/碰撞联调时 | visual、collision、controller、camera、anchor 对齐检查。 |
| F-15 | `docs/superpowers/plans/2026-06-10-repository-plan-status-register.md` | 任务开始和收口时 | 计划状态登记；当前结尾摘要与 P-00 状态行存在不一致，Task 15 必须统一。 |
| F-16 | `docs/character/character-asset-integration.md` | 新角色壳、骨骼、装备或动作支持接入时 | 既有 shared actor shell、binding profile 和 fallback 约束。 |
| F-17 | `docs/art-asset-production-repository.md`；`docs/superpowers/plans/2026-09-10-art-asset-production-repository.md` | 美术生产仓、交接、来源和资格门禁变化时 | 外部资产的生产/交付事实；不替代 D-05/P-03。 |
| F-18 | `docs/character/deepseek-dialogue-guidance-and-action-foundation-reconciliation.md` | 吸收 DeepSeek 讨论、评估扩展方向或解释第一期取舍时 | 完整目录 `1-90`、原文级 `113-206` 分析和 ADOPT/CONSTRAIN/RESERVE/DEFER/REJECT 决策；分析记录，不改变 D-01/P-00 权威顺序。 |

### D. 已实现的直接依赖 spec 和 plan（按需读取）

| ID | spec / plan | 何时必须查阅 |
| --- | --- | --- |
| U-01 | `docs/superpowers/specs/world-character-siming-authority-mainline/README.md` | 确认主线 authority 与当前执行目标。 |
| U-02 | `docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-world-character-siming-authority-mainline-master-design.md` | 改跨边界 owner 或主线事件流。 |
| U-03 | `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/README.md` | 改 Gameplay truth、event store、mirror 的前先读。 |
| U-04 | `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-23-event-sourcing-and-authority-settlement-design.md` | Task 10 的 event/atomic/idempotency 设计依赖。 |
| U-05 | `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-23-resource-status-body-and-effective-stats-design.md` | action 消耗资源、状态或身体功能时。 |
| U-06 | `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-23-skill-ability-graph-and-affordance-design.md` | ability/capability/affordance gate 时。 |
| U-07 | `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-23-godot-runtime-mirror-and-prediction-design.md` | Task 10-11 mirror/prediction 边界。 |
| U-08 | `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-31-coupled-event-store-and-authority-bus-design.md` | composite settlement/outbox 时。 |
| U-09 | `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-08-03-websocket-session-identity-and-mirror-scope-design.md` | session identity、scope、reconnect 时。 |
| U-10 | `docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-29-character-gameplay-foundation-implementation-plan.md` | U-03 的实现现状/验证入口。 |
| U-11 | `docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-29-gameplay-foundation-contracts-events-and-harness-plan.md` | Task 10 的 contract/Harness 依赖。 |
| U-12 | `docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-29-resource-status-body-and-effective-stats-plan.md` | 资源、伤势、状态写入时。 |
| U-13 | `docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-29-skill-ability-graph-and-affordance-plan.md` | capability/affordance gate 时。 |
| U-14 | `docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-29-godot-mirror-persistence-and-migration-plan.md` | mirror projection 或 recovery 时。 |
| U-15 | `docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-31-coupled-event-store-and-authority-bus-plan.md` | authority append/outbox 时。 |
| U-16 | `docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/2026-08-03-websocket-reconnect-resync-and-live-mirror-delivery-plan.md` | Task 11 reconnect/resync 时。 |

### E. 具身交互依赖 spec 和 plan（按需读取）

| ID | spec / plan | 何时必须查阅 |
| --- | --- | --- |
| I-01 | `docs/superpowers/specs/world-character-siming-authority-mainline/embodied-interaction-product-foundation/README.md` | Task 5/10 的具身交互总入口。 |
| I-02 | `docs/superpowers/specs/world-character-siming-authority-mainline/embodied-interaction-product-foundation/2026-07-29-embodied-interaction-product-foundation-master-design.md` | 修改具身交互边界时。 |
| I-03 | `docs/superpowers/specs/world-character-siming-authority-mainline/embodied-interaction-product-foundation/2026-07-29-scene-affordance-registry-design.md` | target/affordance 查询时。 |
| I-04 | `docs/superpowers/specs/world-character-siming-authority-mainline/embodied-interaction-product-foundation/2026-07-29-embodied-action-controller-and-local-observation-design.md` | 改 `EmbodiedActionController` 与 local evidence 时。 |
| I-05 | `docs/superpowers/specs/world-character-siming-authority-mainline/embodied-interaction-product-foundation/2026-07-31-execution-transport-and-controller-attestation-design.md` | controller attestation 与执行 transport 时。 |
| I-06 | `docs/superpowers/specs/world-character-siming-authority-mainline/embodied-interaction-product-foundation/2026-07-29-interaction-session-and-authority-settlement-design.md` | action/session/authority settlement 时。 |
| I-07 | `docs/superpowers/specs/world-character-siming-authority-mainline/embodied-interaction-product-foundation/2026-07-29-godot-mirror-observatory-and-replay-evidence-design.md` | replay、Observatory 或 mirror evidence 时。 |
| I-08 | `docs/superpowers/specs/world-character-siming-authority-mainline/embodied-interaction-product-foundation/2026-07-29-boundary-and-acceptance-matrix-design.md` | 评审 owner/验收矩阵时。 |
| I-09 | `docs/superpowers/specs/world-character-siming-authority-mainline/embodied-interaction-product-foundation/2026-08-01-atomic-action-library-and-default-scene-coverage-design.md` | 只在未来原子动作扩展评审时查；Phase 1 不执行 atom expansion。 |
| I-10 | `docs/superpowers/plans/world-character-siming-authority-mainline/embodied-interaction-product-foundation/2026-07-29-embodied-interaction-product-foundation-implementation-plan.md` | 已有 interaction/controller/settlement 代码的验证入口。 |
| I-11 | `docs/superpowers/plans/world-character-siming-authority-mainline/embodied-interaction-product-foundation/2026-08-01-atomic-action-library-and-default-scene-coverage-plan.md` | 原子动作历史与默认场景 coverage；不能取代 P-00。 |

### F. 主线运行时相邻 spec 和 plan（按改动面查阅）

这些文件属于 2026-06-29 主线及其 Gameplay/具身子树。它们不是动作底座的
第二套实现顺序，而是动作底座调用既有世界、感知、执行和结算能力时的上游
契约。若某动作只涉及本地身体与表现，不要为了“完整”把整棵主线业务树搬进
实现；只有命中对应边界时才追读。

| ID | spec | 配套 plan | 触发条件 |
| --- | --- | --- | --- |
| M-01 | `docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-world-runtime-foundation-design.md` | `docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-world-runtime-foundation-implementation-plan.md` | 世界运行时、事实输入、调度 owner 变化。 |
| M-02 | `docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-actor-local-perception-and-fact-production-design.md` | `docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-actor-local-perception-and-fact-production-implementation-plan.md` | 角色局部感知、接触/事实生产或 evidence provenance。 |
| M-03 | `docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-execution-semantics-and-realization-runtime-design.md` | `docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-execution-semantics-and-realization-runtime-implementation-plan.md` | 语义动作到本地 realization、执行窗口或恢复。 |
| M-04 | `docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-authority-and-settlement-runtime-closure-design.md` | `docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-authority-and-settlement-runtime-closure-implementation-plan.md` | authority、事件、revision、幂等和结算投影。 |
| M-05 | `docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-asset-runtime-and-kimodo-adapter-design.md` | `docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-asset-runtime-and-kimodo-adapter-implementation-plan.md` | Art Pack、adapter、资源 provenance 或运行时绑定。 |
| M-06 | `docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-world-runtime-scheduling-and-continuity-design.md` | `docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-world-runtime-scheduling-and-continuity-implementation-plan.md` | actor continuity、调度 tick、跨会话恢复。 |
| M-07 | `docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-autonomous-social-contact-and-exchange-design.md` | `docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-autonomous-social-contact-and-exchange-implementation-plan.md` | NPC/Agent 社交接触动作需要世界交换或关系后果。 |
| M-08 | `docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-mainline-docs-truth-rewrite-design.md` | `docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-mainline-docs-truth-rewrite-implementation-plan.md` | 更新 owner、状态、索引和文档真相。 |

Gameplay Foundation 的完整直接子树入口如下；其中 `README.md` 是目录级索引，
其余文件按动作后果选择，不把 Gameplay 状态反写成动作层状态：

| ID | 入口/文件 | 触发条件 |
| --- | --- | --- |
| M-09 | `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/README.md`；`docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/README.md` | 任何 Gameplay owner 或子域边界变更。 |
| M-10 | `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-23-character-gameplay-foundation-master-design.md`；`docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-29-character-gameplay-foundation-implementation-plan.md` | Gameplay facade、事件和投影总边界。 |
| M-11 | `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-23-event-sourcing-and-authority-settlement-design.md`；`docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-29-gameplay-foundation-contracts-events-and-harness-plan.md` | 事件追加、幂等、Harness 证据。 |
| M-12 | `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-23-resource-status-body-and-effective-stats-design.md`；`docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-29-resource-status-body-and-effective-stats-plan.md` | 资源、伤势、状态、身体有效属性。 |
| M-13 | `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-23-skill-ability-graph-and-affordance-design.md`；`docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-29-skill-ability-graph-and-affordance-plan.md` | capability/affordance/action gate。 |
| M-14 | `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-23-godot-runtime-mirror-and-prediction-design.md`；`docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-29-godot-mirror-persistence-and-migration-plan.md` | Gameplay mirror、prediction 或恢复。 |
| M-15 | `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-31-coupled-event-store-and-authority-bus-design.md`；`docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-31-coupled-event-store-and-authority-bus-plan.md` | 跨 owner atomic batch、outbox、authority bus。 |
| M-16 | `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-08-03-websocket-session-identity-and-mirror-scope-design.md`；`docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/2026-08-03-websocket-session-identity-and-mirror-scope-plan.md`；`docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/2026-08-03-websocket-reconnect-resync-and-live-mirror-delivery-plan.md` | session、connection epoch、reconnect/resync。 |
| M-17 | `docs/superpowers/specs/world-character-siming-authority-mainline/2026-09-04-3d-scripted-mystery-action-platform-design.md`；`docs/superpowers/plans/world-character-siming-authority-mainline/2026-09-04-3d-scripted-mystery-action-platform-implementation-plan.md` | 3D action graph、action window、conflict/recovery 与 replay。 |
| M-18 | `docs/superpowers/specs/world-character-siming-authority-mainline/2026-09-05-stormnight-procedural-low-poly-character-presentation-design.md`；`docs/superpowers/plans/world-character-siming-authority-mainline/2026-09-05-stormnight-procedural-low-poly-character-presentation-implementation-plan.md` | 角色 presentation 试验、内容包和表现验证。 |
| M-19 | `docs/superpowers/specs/2026-06-29-world-character-siming-authority-mainline-design.md`；`docs/superpowers/plans/2026-06-29-world-character-siming-authority-mainline-implementation-plan.md` | 只作为 flat compatibility redirect 查阅；真正主线入口是 U-01/U-02 及其 dedicated tree。 |
| M-20 | `docs/superpowers/specs/world-character-siming-authority-mainline/inf-1/README.md`、`docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/README.md`、`docs/superpowers/specs/world-character-siming-authority-mainline/inf-3/README.md`、`docs/superpowers/specs/world-character-siming-authority-mainline/inf-4/README.md`；对应 `docs/superpowers/plans/world-character-siming-authority-mainline/inf-1/README.md`、`docs/superpowers/plans/world-character-siming-authority-mainline/inf-2/README.md`、`docs/superpowers/plans/world-character-siming-authority-mainline/inf-3/README.md`、`docs/superpowers/plans/world-character-siming-authority-mainline/inf-4/README.md` | 动作后果落到 INF owner row、跨域 obligation 或 population continuity 时；逐条业务文件从 README 进入。 |

### G. 当前项目智能体/感知增量 spec 和 plan（语义上游，按需查阅）

这棵树已经降位为主线之后的增量专题。与动作底座最接近的文件列在下表；
其余 VLA provider、天道图谱、非运行时工具和感知校准文件只在对应数据流变更
时追读。它们只能产出事实、目标、约束或 catalyst，不能取得 Motor 或结算写权限。

| ID | spec | 配套 plan | 触发条件 |
| --- | --- | --- | --- |
| X-01 | `docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-intelligence-upgrade-master-design.md` | `docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-intelligence-upgrade-implementation-plan.md` | 增量专题总边界或主线降位规则变化。 |
| X-02 | `docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-character-multimodal-and-actor-scene-knowledge-design.md` | `docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-character-multimodal-and-actor-scene-knowledge-implementation-plan.md` | 角色场景知识、actor identity 或 multimodal 输入。 |
| X-03 | `docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-embodied-skeletal-state-provider-design.md` | `docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-embodied-skeletal-state-provider-implementation-plan.md` | 骨骼/身体状态 provider、采样与 evidence。 |
| X-04 | `docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-interaction-orchestration-layer-design.md` | `docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-interaction-orchestration-layer-implementation-plan.md` | 交互编排、动作窗口和目标路由。 |
| X-05 | `docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-esm-dual-channel-world-actuation-design.md`；`docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-02-current-project-esm-physical-channel-world-actuation-design.md` | `docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-esm-dual-channel-world-actuation-implementation-plan.md`；`docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-esm-physical-channel-world-actuation-implementation-plan.md` | ESM semantic/physical channel 或证据转世界动作。 |
| X-06 | `docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-02-current-project-actor-scene-knowledge-lifecycle-design.md`；`docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-02-current-project-embodied-skeletal-debug-replay-pipeline-design.md` | `docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-actor-scene-knowledge-lifecycle-implementation-plan.md`；`docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-embodied-skeletal-debug-replay-pipeline-implementation-plan.md` | actor scene 生命周期、骨骼调试、回放证据。 |
| X-07 | `docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-godot-sampling-frontend-and-providers-design.md`；`docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-02-current-project-godot-sampling-production-grade-providers-design.md` | `docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-godot-sampling-frontend-and-providers-implementation-plan.md`；`docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-godot-sampling-production-grade-providers-implementation-plan.md` | Godot 采样/provider 改动；不用于驱动 body。 |

### H. 角色智能体、心智与 Siming 的语义生产 spec 和 plan（按需查阅）

这些文件解决“角色为什么提出某个 proposal”，不是“Godot 如何执行动作”。
它们必须通过 `CharacterControllerPort -> ActorActionArbiter` 进入新底座。

| ID | spec | 配套 plan | 触发条件 |
| --- | --- | --- | --- |
| A-01 | `docs/superpowers/specs/2026-06-24-character-agent-stage2-design.md`；`docs/superpowers/specs/2026-06-15-full-character-agent-runtime-with-llm-design.md` | `docs/superpowers/plans/2026-06-24-character-agent-stage2-implementation-plan.md`；`docs/superpowers/plans/2026-06-15-full-character-agent-runtime-with-llm-implementation-plan.md` | L4 execution、profile、realization metadata 或 Agent ingress。 |
| A-02 | `docs/superpowers/specs/2026-06-29-complete-character-mind-core-design.md`；`docs/superpowers/specs/2026-07-08-character-needs-personality-affect-runtime-design.md` | `docs/superpowers/plans/2026-06-29-mind-core-foundation-implementation-plan.md`；`docs/superpowers/plans/2026-06-29-full-l1-and-memory-implementation-plan.md`；`docs/superpowers/plans/2026-07-08-character-needs-personality-affect-runtime-implementation-plan.md` | needs、affect、memory、L1/L2/L3 对 action proposal 的输入。 |
| A-03 | `docs/superpowers/specs/2026-07-10-character-skill-system-master-design.md`；`docs/superpowers/specs/2026-07-11-layered-character-mind-factor-architecture-design.md` | `docs/superpowers/plans/2026-07-10-character-skill-system-master-implementation-plan.md`；`docs/superpowers/plans/2026-07-11-layered-character-mind-factor-architecture-implementation-plan.md`；`docs/superpowers/plans/2026-07-11-layered-character-mind-factor-phase3-projection-services-plan.md`；`docs/superpowers/plans/2026-07-11-layered-character-mind-factor-phase4-affordances-plan.md`；`docs/superpowers/plans/2026-07-11-layered-character-mind-factor-phase5-delta-ledger-writeback-plan.md`；`docs/superpowers/plans/2026-07-11-layered-character-mind-factor-phase6-graph-projections-plan.md` | skill/capability/affordance 资格与语义决策。 |
| A-04 | `docs/superpowers/specs/2026-06-22-siming-character-agent-minimal-bridge-design.md`；`docs/superpowers/specs/2026-06-17-siming-agent-loop-architecture-design.md` | `docs/superpowers/plans/2026-06-22-siming-character-agent-minimal-bridge-implementation-plan.md`；`docs/superpowers/plans/2026-06-17-siming-agent-loop-architecture-implementation-plan.md` | Siming catalyst、bridge、agent loop；禁止 direct pose/body。 |
| A-05 | 无同名独立 spec；以 A-01 的 Stage 2 spec 和 D-01 的动作边界为准 | `docs/superpowers/plans/2026-06-24-character-l4-scene-expression-implementation-plan.md` | 旧 L4 场景表达实现的事实定位；任何新 cue 仍须走 proposal/claims/presentation adapter。 |
| A-06 | `docs/superpowers/specs/2026-06-21-character-director-observatory-design.md`；`docs/superpowers/specs/2026-06-24-harness-decision-observability-design.md` | `docs/superpowers/plans/2026-06-21-character-director-observatory-implementation-plan.md`；`docs/superpowers/plans/2026-06-22-character-director-observatory-finalization-implementation-plan.md`；`docs/superpowers/plans/2026-06-24-harness-decision-observability-implementation-plan.md` | 调试观察、决策证据和只读投影。 |

### I. 角色智能体与 Siming 的迁移/历史 spec 和 plan（查阅，不执行）

这些文档解释当前兼容层和已完成窄切片。新的动作底座不得按它们增加
`CharacterGoalCommand` 到 raw clip、独立 root-motion writer 或 Siming 直控 body
的路径；所有新实现回到 D-01 至 D-05 与 P-00。

| 文档组 | 路径 |
| --- | --- |
| 早期 actor spec | `docs/superpowers/specs/2026-06-12-character-actor-control-and-locomotion-design.md`、`docs/superpowers/specs/2026-06-12-character-actor-runtime-boundary-design.md`、`docs/superpowers/specs/2026-06-12-character-actor-unification-design.md`。 |
| actor 优化/最终收敛 spec | `docs/superpowers/specs/2026-06-15-character-actor-architecture-optimization-design.md`。 |
| CharacterAgent spec | `docs/superpowers/specs/2026-06-11-character-agent-minimal-runtime-slice-design.md`、`docs/superpowers/specs/2026-06-15-full-character-agent-runtime-with-llm-design.md`、`docs/superpowers/specs/2026-06-24-character-agent-stage2-design.md`。 |
| Siming bridge spec | `docs/superpowers/specs/2026-06-22-siming-character-agent-minimal-bridge-design.md`。 |
| 已执行 root-motion plan | `docs/superpowers/plans/2026-06-05-player-root-motion-locomotion-implementation-plan.md`。它记录旧 player/visible-shell split，不能作为统一 Motor 方案。 |
| actor/agent 历史 plans | `docs/superpowers/plans/2026-06-11-character-agent-minimal-runtime-slice-implementation-plan.md`、`docs/superpowers/plans/2026-06-11-character-base-player-unification-plan.md`、`docs/superpowers/plans/2026-06-12-character-actor-control-and-locomotion-implementation-plan.md`、`docs/superpowers/plans/2026-06-12-character-actor-runtime-boundary-implementation-plan.md`、`docs/superpowers/plans/2026-06-12-character-actor-unification-implementation-plan.md`、`docs/superpowers/plans/2026-06-15-character-actor-architecture-optimization-implementation-plan.md`、`docs/superpowers/plans/2026-06-15-character-actor-near-term-cleanup-implementation-plan.md`、`docs/superpowers/plans/2026-06-15-character-actor-final-convergence-implementation-plan.md`、`docs/superpowers/plans/2026-06-15-full-character-agent-runtime-with-llm-implementation-plan.md`、`docs/superpowers/plans/2026-06-18-character-agent-stage2-closeout-plan.md`、`docs/superpowers/plans/2026-06-19-character-actor-stage2-closeout-implementation-plan.md`、`docs/superpowers/plans/2026-06-22-siming-character-agent-minimal-bridge-implementation-plan.md`、`docs/superpowers/plans/2026-06-24-character-agent-stage2-implementation-plan.md`。 |

除“已实现行为的事实定位”外，这一组不能作为新功能的 task list。遇到旧文档与
D-01 至 D-05 相冲突时，记录 drift 并按当前 spec 修复，不要双轨兼容。

## 变更后必须更新的位置

| 改动类型 | 必须更新 |
| --- | --- |
| 运行时真实路径/未完成 gap | F-01、F-02，必要时 F-03/F-06/F-09。 |
| descriptor、mapping、package 或导入规则 | F-04、F-11 至 F-14 和资产资格 report。 |
| Agent/INF/Siming semantic boundary | F-10，以及 D-01/P-00 对应任务状态。 |
| ESM/Gameplay/Mode B contract | D-03/D-04 对应计划状态、相关 U/I 文档中的事实说明。 |
| 实施阶段/验收完成 | P-00 task checkbox、F-01、F-05、F-15、`docs/INDEX.md`。 |

每次文档更新前先检查 source-of-truth hierarchy；不得把尚未运行的 Godot probe、
backend route 或 Harness profile 写为已验证。
