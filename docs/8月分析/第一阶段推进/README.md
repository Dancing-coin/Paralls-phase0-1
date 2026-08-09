# 第一阶段推进：通用基础契约收口

状态：`phase-one workbench; incremental guidance; non-authorizing until formal spec/plan`

本目录用于推进第一阶段，不建立新的 runtime、event store、scheduler 或 authority。
它把当前 Gameplay Foundation 的实现基础收口为可跨玩法复用的稳定契约，并用少量
异质样板验证泛化能力。这里的“最小”指最小稳定通用契约集，不是面向某一个农田、
商店或生存玩法的最小实现集。

第一阶段依赖的共享底座规格是 [Gameplay Foundation Shared Contract Closure](../../superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-08-07-gameplay-foundation-shared-contract-closure-design.md)，在第一阶段中承担 P1A 角色。该草案当前为 `awaiting-user-review`，未完成审阅和 matching plan 前，本目录仍不授权运行时实现。
第一阶段基建的筛选依据见 [核心基建范围与依赖矩阵](06-第一阶段核心基建范围与依赖矩阵.md)；它把跨玩法 contract 与领域实现、Creator Control Plane 和 Population Simulation 分开。
第一阶段完整正式 spec tree 见 [Phase One Gameplay Specification Tree](../../superpowers/specs/world-character-siming-authority-mainline/phase-one-gameplay/README.md)。

```text
Phase 1A 通用基础契约冻结
  -> Phase 1B 通用契约 Harness/回放证明
  -> Phase 1C V0 内部契约测试样板
  -> Phase 1D Econ-1 面包店完整参考游戏
  -> Phase 1E 第二个异质样板泛化门禁
```

群体模拟不在上述第一阶段执行链内。第一阶段的 Econ-1 默认使用单玩家角色与聚合
需求；已有的多智能体角色只有在正式 `CharacterRecord` 已存在时才能接入。员工、
顾客、供应商和监管人员的 NPC 生活推进，必须等待独立的 Population Simulation
Authority 收口后再进入正式 plan。

## 当前基线

可复用基础已经包括：

- `GameplayEventStore.append_batch`、幂等、revision、replay、checkpoint 和 committed outbox；
- resource/body/status/effective-stats 与可组合 state group；
- inventory/container/encumbrance、equipment、ownership、fixed-offer、gift、simple-debt、
  typed-contract；
- skill/ability/affordance、Patch Rule IR/capability、Godot gameplay mirror；
- 已通过 Harness 的有界 `adventure-basic` 五场景参考闭环。

当前仍需收口的通用能力包括 identity/reference、Entity/Thing/Environment/
Relationship/CausalEvent 记录、标签/材料/性质/effect/resistance registry、
selector/query、ActionPrimitive/ActionIntent/PhysicalFact/LogicalFact、Rule IR、effect application、
Reservation/Hold、trace、冲突与迁移 contract、通用 `SettlementPlan` adapter，以及
tick/obligation/calendar/world profile/ActiveWorldRevision/state-group activation 和
GameplayPackageManifest compatibility contract。这些能力必须扩展现有 owner，不能复制已有基础。

建造生产、生存需求、组织经营、政府监管和动态报价属于领域实现；第一阶段只用样板
验证它们能组合到通用契约上，不把它们本身当作共享底座边界。

## 三层范围

### A. 必须泛化的核心契约

- identity、reference、实体/事物/环境/关系生命周期；
- 标签、性质、材料、状态、effect、resistance 和 selector/query；
- 确定性 Rule IR、effect application、结构化失败、trace 和 capability 边界；
- Action/fact、reservation、结算/交易、义务、时间调度、world profile、revision、replay、
  migration、package compatibility、projection/permission；
- 扩展点必须允许新领域增加 schema、authority 和 package，但不新增 store、bus 或 runtime。

### B. 第一阶段交付的完整参考游戏

- V0：霜冻农田或火焰橡木门，只作为通用契约的内部测试，不单独宣称为完整玩法；
- Econ-1：面包店，作为第一款可完整运行的参考游戏，覆盖开店、采购、建造、生产、
  员工、销售、顾客、生存需求、工资、税费、许可证、经营周期、成功/失败和回放；
- 第二个异质样板：在面包店完成后再选择调查/冲突、合同/债务或权限型物理交互，
  用来证明底座不是为经济生产玩法特制的。

### C. 明确后置

- 完整动态市场、订单簿、拍卖、跨区贸易和宏观价格模型；
- 完整公司制、金融信用、法院/政治军事和文明级群体模拟；
- 任意内容包脚本执行和创作者产品化控制面；
- 反事实推演、全生态模拟和大规模 NPC 群体优化。

## 阅读与权威顺序

1. [当前架构总纲](../../架构/整体架构.md)
2. [Gameplay Foundation 与领域结算](../../架构/运行时/模块/GameplayFoundation与领域结算.md)
3. [通用基础契约收口](01-通用基础契约收口.md)
4. [V0 共享结算样板](02-V0共享结算样板.md)
5. [Econ-1 跨域垂直闭环](03-Econ-1跨域垂直闭环.md)
6. [Econ-1 商业生态与多角色经营实现方案](05-Econ-1商业生态与多角色经营实现方案.md)
7. [阶段门禁与证据矩阵](04-阶段门禁与证据矩阵.md)
8. [核心基建范围与依赖矩阵](06-第一阶段核心基建范围与依赖矩阵.md)

正式 spec 对应关系：

- P1B：`phase-one-gameplay/2026-08-07-p1b-contract-verification-and-evidence-design.md`
- P1C：`phase-one-gameplay/2026-08-07-p1c-frost-farm-contract-sample-design.md`
- P1D：`phase-one-gameplay/2026-08-07-p1d-econ1-bakery-reference-game-design.md`
- Econ-1 domain：`phase-one-gameplay/econ1/`
- P1E：`phase-one-gameplay/2026-08-07-p1e-generalization-gate-design.md`

发生冲突时，以当前线程指令、正式 spec/plan、代码、测试和 `.harness/verification/`
证据为准。本目录的完成状态不能单独授权实现。

## 对“最小共享基础设施”的直接回答

如果“最小共享基础设施”指针对一个狭小玩法样板的最小代码，它不够，也不是本项目
的目标。第一阶段要收口的是“最小稳定通用契约集”：它只覆盖跨领域必须稳定的
identity、语义、因果、结算、时间、回放、迁移和权限边界，不声称一次性完成所有
经济、社会、生存或文明模拟。

泛化能力不能靠清单宣称，必须通过异质样板证明。V0 和 Econ-1 只是前两个验证样板，
至少再用一个结构不同的样板复用同一契约，才能关闭第一阶段的泛化门禁。

## 第一阶段非目标

- 不实现完整动态市场、订单簿、拍卖、跨区贸易或宏观经济；
- 不把完整商业组织、政府监管、金融信用或文明模拟误称为通用基础设施；
- 不把 Survival Authority、SimulationClock 或 Creator Control Plane 设计成新 runtime；
- 不把 `SettlementPlan` 当作第二个 event store 或万能 coordinator；
- 不把 `adventure-basic` 的五个场景升级为通用经济/生存/建造完成声明；
- 不把面包店做成大而全的市场、金融或文明模拟，完整指的是一个小范围但闭环可玩的游戏。
