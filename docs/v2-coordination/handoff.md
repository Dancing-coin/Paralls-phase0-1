# 线程交接文件（只追加，不改旧条目）

- 取代版本 1 的 `requests/thread-b.md` 与 `responses/thread-a.md`（旧文件保留作历史，不再追加）。规则见 PROTOCOL.md 第三节。
- B 写 `H-B-nnn`（需求或问题）；A 写 `H-A-nnn`（回应或"机制已可用"通告）；项目负责人决定由线程代抄，格式"项目负责人决定：……（日期）"。

## 条目格式

```
## H-B-001 | 日期 YYYY-MM-DD
- 域 / 机制：
- 阻塞程度：阻塞 / 不阻塞但有绕路
- 现状证据：文件:行号，或命令与原始输出
- 期望的接口或行为：
- 为什么 B 不能本地解决：
- 等待期间 B 做什么：
- 验收：

## H-A-001 | 回应 H-B-001 | 决定：接受 / 拒绝 / 换方案 / 推迟 | 日期
- 提交：SHA（若已实现）
- 何时可用于 B：合并日期（以 integration 标签为准）
- 说明：
```

## 条目

### 承接自版本 1 的已完成事项（只作历史摘要，原文见 `responses/thread-a.md`）

- A 队列 0（Owner 登记泛化）与 0.5（图可见性发现机制）：已完成，合并 SHA `3d6c72095fdcd2cbc9e0e4484e70a6010e7cdc87`，随 `integration-2026-11-21` 可用。
- 完整 Bond 的 scope、term、attributes 与撤销/到期/supersede 生命周期：线程 A 进行中（未提交）；对应迁移计划任务 M1-1。

### 项目负责人决定：S-5、S-6（2026-11-22）

- S-5：Process 归并（8 个模块）纳入迁移范围，排在域迁移之后，先做 Demo 需要的过程类型。
- S-6：枢纽（inventory、economy、organization_government、resource_body、patch）纳入迁移，排最后一波，进入前须有前序波次的回归证据。
- Combat 的分类（S-1）：先盘点代码，再裁定；盘点任务为迁移计划 M0-1。

### H-A-003 | M0 结论收到；新增前置 M0.5，B 暂无可开工域 | 2026-11-22
- M0 按"输入"接收：`a7a66301`、`c4a53e75`，7 份文档，只读，未跑测试。不作为迁移验收。
- **硬前置（新）：`REGISTERED_OWNER_IDS` 只有 3 项**（`fact_type_registry.py:11`：Credential、Ownership、Economy / Market），`rule_pack_validator.py:177` 对名单外的 Owner 一律 `facttype_owner_unknown`。因此除这三个 Owner 外任何域的规则包都加载不了，B 的"无合格首域"结论由此而来，不是筛选过严。
- 处理：迁移计划新增 **M0.5 Owner 登记名单扩展**（A 执行）：名单扩到 22 个（Combat 等 S-1），只加名字不设计注册流程，D5 门槛不变；用一次性 fixture 包验证"名单内可通过、名单外被拒"，fixture 不进 `packs/`。
- B 在 M0.5 完成前：只做只读设计，从 M0-6 第 1 波候选里挑 2–3 个（`life_state`、`action_consequence`、`reference_data` 之类），各写一份设计与读取方清单，不写规则包、不改代码。`life_state` 我核对过只有 1 个导入者（`population_continuity/activation_presence.py:8`），可优先。
- 文档一致性更正：S-8 在规格里是"已决定按事实域拆分"，计划里此前仍写"待裁定"，已改为一致。**以规格为准。**
- M0-1 里对债务/合同事件的注册表抽查用的是推测名称（`gameplay.debt.created` 等）；后续按 P-3 核对时须用源码里的实际事件常量，不用推测名。

### 项目负责人决定：M1-1 Bond 必须分片提交（2026-11-22）

- 背景：线程 A 当前工作区未提交改动约 1,400 行（`ownership_runtime.py` 一项 +842），混了四种性质，只有定向测试与两组选集证据，未提交、未跑全量。
- 决定：先拆成可独立回退的提交，再继续新工作；不新写功能。
- 分片（顺序 1 → 2 → 3）：

| 片 | 名称 | 主要文件 | 性质 |
|---|---|---|---|
| 1 | Bond 原语：生命周期 + 多权利投影 | `ownership_runtime.py`、`ownership_event_schema.py`、`test_ownership_bond_lifecycle.py`、`test_ownership_runtime.py` | 新增能力（L1） |
| 2 | credential v3 引用迁移到 `bond_ref` 及消费方 | `credential_runtime.py`、`credential_reference_chain.py`、`credential_v2_event_schema.py`、`land_right_runtime.py`、`adventure_basic_closure.py`、`packs/credential_reference/models/credential_command.yaml`、对应测试 | 跨域读向量与持久事件字段变更 |
| 3 | 属性白名单移除 + Decimal 属性定点规范化 | `ownership_runtime.py`、对应测试 | 行为改变 |

- 前置闸门：A 先产出 hunk 映射表（文件 / hunk / 归哪片 / 能否独立 / 理由），经项目负责人确认后才执行提交。同一函数内交织的改动不得硬拆；做不到独立就合并成一片并写明"不能独立回退"。
- 每片须**单独验证**：临时 worktree 检出该提交，跑该片定向测试与 ownership（24 节点）、shared-replay（990 节点）两组冻结选集，记录实际 `problems` / `improvements`。
- 片 2 须枚举 `bond_ref` 全部读写方并给出行号，写明旧 v1 事件兼容策略。片 3 须写明旧行为、新行为、旧数据与重试路径兼容性。
- 全量 10,392 节点只在三片提交完后于分支 tip 跑一次；未跑就写"未运行"。
- 证据写入 `docs/verification/m1-1-bond-slices-20261122.md`。
- 允许创建本地提交；**不允许推送**，推送须单独放行。
- 停止条件：映射表出现无法独立的 hunk、中间提交测试不过、需要改测试断言（先按 P-2 登记 claim）、需要触碰存储核心或共同禁区、`fixed_offer_purchase.py` 因片 2 失败、发现新第二真相、发现密钥。
- 任务卡在仓库外 `D:\Temp\v2-thread-a-slice-prompt.md`，不纳入代码提交。

### 项目负责人决定：S-8、S-9（2026-11-22）

- S-8：通用 Contract runtime 的 Owner 归属按事实域拆分，不新建 Owner——政府评估 → Government，设施验收 → Production/Facility，工坊与服务 → Economy/Production；Contract runtime 退为跨域编排（L5 workflow）或声明层。具体拆分清单以 M0-1 的事实清单为准。
- S-9：B 工作区里两份未跟踪文件（`debt_contract_event_schema.py` 与其测试）移到 `D:\Temp` 下独立目录保存，不作为迁移起点；日后复用须按 M4 流程重走（设计文档 + P-3 断言 + P-4 归属说明）。
- 执行者：项目负责人或线程 B 在下一轮开工时执行；执行后在 `daily/` 或提交说明里写明去向。

### 项目负责人决定：M0 盘点交给线程 B（2026-11-22）

- 迁移计划的 M0 全部任务（M0-1 至 M0-6）由线程 B 执行，纯只读：不改代码、不改测试、不改规则包，不跑全量或选集。
- 任务卡在仓库外 `D:\Temp\v2-thread-b-m0-prompt.md`，内容属于任务派发，不纳入代码提交。
- 产出写入代码仓库 `docs/verification/m0-inventory-20261122/`（README 加 m0-1 至 m0-6 共 7 个文件）；只暂存这 7 个路径，提交与推送须项目负责人单独放行。
- 线程 B 工作区里未提交的 `debt_contract_event_schema.py` 与测试保持原样，本轮不提交；`commerce` 事件归属问题（见 H-A-001）不因 M0 解阻。
- M0 期间不合并、不 rebase 到新 `integration`：`6576071a` 相对 `0e67fe81` 仅改文档，新协议用 `git show origin/integration:<path>` 只读。
- 线程 A 同期继续 M1-1（Bond），两者文件不相交。
- M0 结论是输入，不是验收；S-1（Combat）只出事实，由项目负责人裁定。

### H-A-002 | 通告 B：debt 移到第 3 波，contract 待裁定 | 2026-11-22
- 依据：B 汇报核实 debt 的正式 Owner 是 `Economy / Market`（与 `REGISTERED_OWNER_IDS` 一致），Economy 是导入者最多的枢纽，`economy_runtime.py` 属共同禁区；23 个事件类型里 5 个 `gameplay.commerce.*` 由 economy 侧写入。原波次表把 debt 排第 1 波是只看 `debt_runtime.py` 自身导入者数，口径错了。
- 决定：debt 移到第 3 波（迁移计划 M0-6 复核后可再调）；contract 暂不排波次，等项目负责人裁定通用 Contract runtime 的 Owner 归属（规格决定项 S-8）。
- 对 B 的影响：B 的首个迁移域不由计划预设，等 M0-6 波次表出来后由项目负责人指定。在此之前 B 只做 M0 与只读核对。
- B 工作区里两份未跟踪文件（`debt_contract_event_schema.py` 与其测试）：处置见规格 S-9，裁定前保持原样、不提交、不作为迁移起点。

### H-A-001 | 提示 B：P-4 适用于 debt/contract 的 `commerce` 事件 | 2026-11-22
- 说明：线程 B 工作区未提交的 `debt_contract_event_schema.py` 列了 5 个 `gameplay.commerce.*` 事件。提交前请在本文件追加 `H-B-nnn`，说明这些事件的写入者、读取方与归属，等项目负责人确认（PROTOCOL.md P-4）。

### H-A-004 | M0.5 Owner 登记名单扩展完成 | 2026-11-22
- M0.5 指 Owner 登记名单扩展，不是历史队列 0.5 的图可见性发现机制；历史队列 0.5 已随 `3d6c72095fdcd2cbc9e0e4484e70a6010e7cdc87` 完成。
- 规范 `owner_id` 使用 Architecture v2 的短名单词。文档别名映射与校验结果见 `docs/verification/m0.5-owner-registry-20261122.md`。
- 22 个 Architecture v2 Owner 作为规范名称登记；`Credential` 仅为旧规则包兼容条目，不构成新 Owner。`Combat` 暂不登记，等待 S-1。
- `Economy / Market` 只在旧常量和测试生成的临时包中出现，未发现于持久事件、receipt、checkpoint 或黄金数据；规范名称为 `Economy`，旧别名被拒绝。
- M0.5 代码与测试提交：`4b876f3d4dd92deba72aa2b49685fa4c39920ce2`。定向 validator 测试：37 passed，2 warnings；不是 Owner 迁移完成声明。
- M1-1 已在 M0.5 之前形成两笔代码提交：`b700f8c8`（Bond 生命周期 + 多权利 + 属性行为，同一 `_bond_attributes` 函数不能跨提交拆分）与 `ae7d650e`（Credential v3）。详见 `docs/verification/m1-1-bond-slices-20261122.md`。两笔各自 detached 定向测试与 ownership/shared-replay 选集通过；分支 tip 全量为 24 failed、10,389 passed、2 skipped、2 xfailed，退出码 1，不能称全量通过。

### H-A-005 | M2-2 `read_as` 前置缺口 | 2026-11-22
- 状态：阻塞。依据 Architecture v2《可见性强制》与迁移计划 M2-2，`read_as(principal, scope, as_of_tick, fact_types)` 需按主体资格过滤可见性、基于 `event_time` 计算 `known_time`，对缺少授权证据的读取明确拒绝，并返回来源与时间投影。
- 静态证据：`backend/app/gameplay/models.py:80` 的 `GameplayEvent` 无 `event_time` 字段；`credential_runtime.py` 与 `ownership_runtime.py` 的生产事件构造均使用 `visibility_policy="authority_only"`；`rg -n "read_as" backend/app` 未发现 gameplay 读取入口；`packs/credential_reference/fact_types/credential_link.yaml` 的 `learnable_by` 为 `role:credential_authority`，`known_deviations.visibility_selector` 明确记为 `unbound_role_placeholder`；`backend/app/gameplay/fact_type_registry.py` 只保存 FactType visibility，当前没有生产 event_type→FactType→Owner visibility 解析链；Architecture v2 尚无已完成域迁移，M2-2 计划要求的首批已迁移域读取消费者不存在。
- 影响：仅按现存 `visibility_policy` 写通用 API 会把 `authority_only` 规则误当作主体授权，也不能计算 `known_time` 或满足来源投影；不具备正式合同要求的安全依据。没有修改存储核心、Owner runtime、事件或已有读取合同。
- 继续条件：Owner/FactType 与 event type 的解析来源、principal selector/资格解析机制、event_time 来源及首个可迁移域面向主体读取点明确后，继续建立读取层并按 M2-2 接入；不得把 `authority_only` 解释为普通 principal 可读。

### H-A-006 | M1-2 Holdings 事件与守恒账本缺口 | 2026-11-22
- 状态：阻塞。上位规格 `02-六原语规格.md` §三与 `04-事件schema规格.md` §4.3 定义 H1–H5 及 lot_created/reserved/transferred/consumed/split/merged/lost 字段，但不足以唯一实现其中关键不变量。
- 具体缺口：无 reservation release/settlement 事件，`consumed` 不带 `reservation_ref`，无法确定性释放或结算某一预留；`transferred` 没有 reservation 关联，无法验证 H2 的预留与转移原子性；H1 的 `total`、`reserved`、`in_transit` 来源与消费/损失后的账本关系未定义；H4 容量约束的声明来源和作用域未定义；H5 单位/规格兼容性没有事件字段或注册表接口合同。
- 影响：依据现有字段只能选择多种互不等价的 reducer 语义；增加持久事件或字段会扩展已定义 schema，定义消费/损失是否改总量也会确定事实合同。未改代码、事件类型、Owner 或共享存储。
- 继续条件：明确 reservation release/settlement 与 transfer 的事件合同、守恒总量账本口径、capacity 与 unit/spec 的来源后，再实现 Holdings projector/command fragments 和固定向量；质量继续按规范归 Pool。

### H-A-007 | M0.5 集成引用核对 | 2026-11-22

- 名单扩展交付 `4b876f3d`，合并提交 `9e0ff06c`。本地 `integration` 与标签 `integration-2026-11-22-8` 指向 `94d4aa20`，包含该合并。线程 B 的 LifeState 分支以该提交为祖先。
- `git fetch origin` 后 `origin/integration` 为 `f635fff2`，对应注册表仍是三个旧条目。合并执行者需核对集成分支发布状态。详细名单与 37 条定向测试见 `docs/verification/m0.5-owner-registry-20261122.md`。

### H-A-008 | M2-5 设计交付与 M2-6 实施前置 | 2026-11-22

- `docs/verification/g2-visibility-budget/b4-handoff-design-20261122.md` 给出冻结受理与投递、交接恢复切面、`pending / reconcile / activate`、双 writer 证据和首流 publisher 接线方案。
- 按迁移计划由负责人确定首个生产流。当前设计候选是 `population-cadence:<world_ref>`。实施还需明确交接状态与 Store 原子事务边界，会涉及共同边界 `event_store.py`，按协议登记后继续。

### H-A-009 | M5-1 剩余声明的契约输入 | 2026-11-22

- `command_catalog` 的命令名前缀须来自已登记 L3 Owner 的 `domain`。当前 `REGISTERED_OWNER_IDS` 只登记 ID，现有 `fact:credential:*:link` 的写主是 `Ownership`，无法从前缀或短名推断权威映射。发布命令目录前需提供 Owner domain 登记以及 payload schema 解析边界。
- `temporal_effects` 与 M1-5 Process 归并有关。《六原语规格》列出实例的 `tick_policy`、`next_tick`、`exit_condition` 与幂等键。尚缺效果定义条目的可用 tick 策略、退出谓词及向 Pool Owner 发请求的引用结构。待定义形状确定后接入加载校验。
- 两项不妨碍 M5-2 的离线包校验工作。已接入的五种声明及 M5-5 规则盘点见 board。

### H-A-010 | M5-2 离线交付与 M5-3、M5-4 生产前置 | 2026-11-22

- `4747acaf` 返回父到子的解析链和内容哈希，`eebd34e5` 可读取可信调用方提供的 Owner domain 来加载命令目录。命令名与处理 Owner 仍需生产登记接线。H-A-009 中的命令目录声明校验已离线交付。
- M5-2 存档接线和 M5-3 生产迁移为阻塞项。请确定包版本权威归属及可执行迁移的写入方。现有 `world_config_revision` 只保存单一引用，域 schema 的图发现筛选 `gameplay.`，详见 `docs/verification/m5-3-pack-migration-preflight-20261122.md`。
- M5-4 已有加载器 `running=True` 拒绝证据。应用进入运行态时的调用入口及切换动作需在上述生命周期接线中核实。

### H-A-011 | M6-1 Reaction 生产接线前置 | 2026-11-23

- `7b0d69bf` 可离线验证命令引用、直接写入、循环及相同触发声明的优先级。编译结果保留触发值、条件和命令参数。证据见 [M6-1](../verification/m6-1-reaction-20261123.md)。
- 生产登记需要由命令处理方提供可信的输出 FactType 映射。提交后的 receipt 才可触发新命令，命令需通过 Gateway。三值条件、目标解析、冷却和幂等重试仍待生产接线。
- 守城 Demo 使用的触发简写以及重叠模式对同一事件的排序需在运行接线前验证。

### H-A-012 | M6-2 Pipeline 生产接线前置 | 2026-11-23

- `abfe1443` 的加载器校验明确的原子或义务模式。原子路径检查跨宿主、跨 scope 和共享 revision vector，义务模式要求声明恢复动作。定向与选集证据见 [M6-2](../verification/m6-2-pipeline-20261123.md)。
- 生产路径需要 Gateway 和 Owner 的目标绑定及授权片段，让 `AppendDerivedSettlementRecipe` 沿既有 EventStore 路径校验并提交。义务路径还需按步骤 receipt 判断继续、查询原结算结果和恢复。

### H-A-013 | M6-3 Workflow 重建前置 | 2026-11-23

- Workflow 编译器已校验登记命令、依赖关系与义务恢复策略。生产入口须提供固定的工作流版本、实例及步骤身份，并将这些身份关联到既有命令回执。
- `GameplayEventStore.get_by_idempotency` 可查提交结果。拒绝、超时、宿主不可达仍需要 Gateway 审计或已有权威义务证据，才能在投影丢失后区分尚未执行、结算未知和可重试。需明确其归属及查询接口。
- 《组合总纲》的补给示例给 `reserve` 继承超时开放义务策略，但恢复表只列 `transport` 和 `deliver`。当前按《跨域结算》为每个可打开义务的步骤要求显式恢复声明。补给包接线时需为 `reserve` 声明其恢复策略或覆盖超时动作。

### H-A-014 | M6 组合声明加载与守城生产前置 | 2026-11-23

- `9eb80fe9` 提供 Workflow 编译及正常规则包加载。`6e7da420` 将 Reaction 和 play pattern 接入同一 `load_pack` 入口，可信命令输出由调用方提供，按包内有效命令目录过滤。后者在独立提交 `876133ed` 上的 19 组选集共 1,288 节点，全部零差异，主分支全量正在运行。最终证据追加到 [加载接线记录](../verification/m6-composition-pack-loading-20261123.md)。
- M6-5 仅做前置核对，未实施生产 Demo。当前 A 分支找到 LifeState 真实 writer，但未找到守城所需 Morale 重算、Presence 通行性重评及 Information 报告送达命令的生产入口。需要 B 交付对应域 FactType、命令处理方与可信输出集合，再由已提交 receipt 接入 Gateway。具体静态范围见 [守城前置核对](../verification/m6-5-siege-preflight-20261123.md)。
- H-A-011 至 H-A-013 所列生产调度、目标授权、结算未知查询和义务耐久归属仍待接入。声明编译和包加载已有测试，M6 运行时与 Demo 尚有上述前置。

### H-A-015 | H-A-014 全量结果与剩余接入条件 | 2026-11-23

- `6e7da420221c8a7ca4f3fb762153b2542e5b004c` 的串行全量已结束，10,562 collected，10,534 passed、24 failed、2 skipped、2 xfailed，退出 1。运行期间 HEAD 与源码固定。相对 `9eb80fe9` 的失败签名新增 0、恢复 0；相对冻结 22 项仍多两项既有本地失败，详见 [加载证据](../verification/m6-composition-pack-loading-20261123.md)。独立提交定向 133 passed，19 组选集 1,288 节点各组零差异。
- M6 声明加载单元记为待门禁。生产执行接入需要确认 Gateway 的处理方及可信命令输出登记、Workflow 步骤与回执的耐久关联和义务归属。M6-5 还需要 B 的 Morale、Presence、Information 对应域事实及命令交付，前置静态核对见 [守城记录](../verification/m6-5-siege-preflight-20261123.md)。M6 总任务记为阻塞。
- A 其余队列的继续条件沿用 H-A-005/006/008/009/010，分别为读取时间与主体资格来源、Holdings 预留与守恒合同、首条 epoch 生产流及存储边界、效果定义条目合同、包版本写入归属。Place 在第 3 波后，Process 归并在域迁移后；S-2 至 S-4 仍待负责人裁定。已交付部分按各单元证据和账本状态供门禁消费。

### H-A-016 | 回应 H-B-004：Pool schema factory 与三条守城机制分工 | 2026-11-23

- A 已将 `register_pool_event_schemas` 接入 `create_stormnight_event_schema_registry`，提交 `39ecc2bb`。Pool factory 下的持久初始化、93 项定向回归及 Pool 16 节点选集通过。证据见 `docs/verification/m1-3-pool-production-registry-20261123.md`。shared-replay 因外部端口 8000 不健康占用有两项失败，同一失败在 detached `6e7da420` 复现；没有停止或修改该进程。新提交的全量对照正在执行。
- 项目负责人于 2026-11-23 确认 D8 先采用守城限定的 `morale_refold@1` 窄规则：对 Organization 提供的权威守军名单，按死亡事件提交位置读取成员身份和 LifeState，重算存活比例；四人全员存活为 100，一人死亡后为 75。缺少有效 roster 或任一成员生死事实时结果为 unknown，不写 Pool。军旗与指挥不纳入本版输入，待事实源和规则到位后升模型版本。该决定不把候选 Organization delegation 或 population roster 自动视为守军权威名单。
- Morale 的生产 writer 仍由 B 实现，须消费 Organization 可回放成员事实及 revision，并传入死亡事实与 Morale Pool stream 的 revision 向量。A 提供的 Pool primitive 和生产 schema factory 已在 A 分支；Gateway/L5 异步调度及 Morale 命令可信输出仍是待实施机制。
- Presence 继续等待 Facility/Production 提供已提交的 breach 事件、FactType、payload、stream revision 和 source owner。没有该事实时不从维修、环境状态或几何推导破口。输入交付后 B 写 Presence 独立通行性 resolver，A 接 Gateway/L5 与输出登记。
- Information 的 writer 提交 `abba3c3c` 在 `origin/thread-b/reference-data-20261123`，尚未进入 A 的代码基线。合入共同基线后，A 接 `register_information_event_schemas` 到生产 factory，并登记 delivery v2 触发、`information.update_knowledge` 命令及精确输出。当前 writer 按 recipient 单独存流，事件 `visibility_policy` 与 outbox audience 都是 `actor:<recipient>`。建议 FactType scope 与 `actor:<recipient>` 私有读取一致，不能把该输出登记成 faction 可见的汇总士气或公共报告事实。该建议依据 B 的 writer 与 FactType 可见性合同，未代替 U2 的 Owner/FactType 声明与 `read_as` 读取授权。
- M6 Gateway/L5 不存在于当前 A 的生产执行路径。现有 Reaction 仅离线编译，`create_stormnight_event_schema_registry` 只是 EventSchema factory；不能声称已有命令 Gateway。A 需另建受信任命令处理登记与已提交 receipt 驱动的异步分发，并在每个命令登记精确输出 FactType。目标授权、条件三值求值、冷却、幂等、失败审计及 Workflow 义务重建依 H-A-011 至 H-A-013 单独落实。
- 下一步需 Organization Owner 交付具有效时点、成员身份、来源 stream/revision 的守军编制事实合同；Facility/Production Owner 交付已提交完整度破口事件及 revision。两项输入分别是 Morale 和 Presence 的硬前置。Information 接线只待 B writer 进入共享代码基线和 Gateway 命令入口合同。

### H-A-017 | 更正 H-A-016：Pool 全量最终结果 | 2026-11-23

- `39ecc2bb13a8fe5d694c4a5efadd3a5e78928091` 的合并状态全量已结束：10,564 collected，10,532 passed、28 failed、2 skipped、2 xfailed，239 warnings，1,571.89 秒，退出 1。相较 `6e7da420` 的全量报告新增 4 个失败签名、恢复 0，故 G5 未通过。
- 两个端口 8000 失败在 detached `6e7da420` 复现；另两个 Population recovery 全量节点报 pytest 临时文件 `PermissionError`，在旧基线和 `39ecc2bb` 的定向复验各自 2 passed，但根因仍未明，不能从全量失败中扣除。没有停止或修改外部进程。
- 此结果仅代表合并状态全量，不计入任何单个切片验证。逐片证据、冻结选集结果、原始输出和未覆盖项分别记录在 [Pool 生产 factory 增量证据](../verification/m1-3-pool-production-registry-20261123.md) 与 `F:/paralls-verification/thread-a/c-39ecc2bb/`。

### H-A-018 | D8 casualty 触发已加入 Pool refold | 2026-11-23

- 项目负责人已确认守城限定的 `morale_refold@1` 规则后，A 在 `84d12a87f8bdc3ba05324f992c0d157aeafdd695` 将 `casualty` 加入 Pool distribution refold 的触发集合。TDD 首次失败为 `pool_refold_trigger_invalid`，修复后 Pool 定向 17 passed。证据见 [casualty refold 单元记录](../verification/m1-3-casualty-refold-trigger-20261123.md)。
- Pool 17 项、冻结 ownership/modifier/equipment/inventory 179 项和其他已登记选集 104 项零差异。shared-replay 990 项有两个端口 8000 `RuntimeError`，其余 988 项匹配。此子单元全量未运行，不能替代上一单元合并状态全量失败结果或计作 G5 通过。
- 该提交仅允许 Pool refold 接收死亡触发并核对其 revision vector；Morale Resolver、权威守军 roster 查询、存活比例计算及 Gateway/L5 生产分发未实现。B 的 Organization roster 输入合同仍需其 Owner 提供，不应以 Organization delegation 或 population roster 直接推断守军编制。

### H-A-019 | 回应 B 对 Morale 与 Presence 阻塞条件的核对 | 2026-11-23

- 复核分支：`origin/integration` 为 `810a46c1249918c09b42fa1fe0c12d7d784579d2`，A 分支为 `025ef31de77294fe683d08223c521067b4308373`，B 分支为 `8b37e3ce49ff241625102bea857cc82215216503`。`origin/integration` 尚无 `backend/app/gameplay/pool_runtime.py`，因此 A 已推送的 Pool 与 `casualty` trigger 不能在 B 当前共同基线上验证。不要通过复制 B 代码或改写 B 的域文件绕过共同基线门槛。
- Morale D8 已由项目负责人裁定为守城限定的 `morale_refold@1` 存活比例规则，但可回放的权威守军名单及其有效时点、成员身份、来源 stream/revision 仍未交付。B 当前账本是此前版本，仍将 D8 记为待决；B 更新账本时应记录该裁定，同时继续将 Morale 标为阻塞，直到 Organization 输入与共同 Pool 基线可用。
- Presence 继续阻塞：尚无已提交 Facility/Production breach 事实及其 FactType、payload、source stream/revision、source Owner，也无可由该输入重算的 Presence 通行性合同。不得以维修、普通 condition 变化、环境几何或手造事件代替。
- A 已交付给共同基线候选的机制范围仅包括 Pool runtime/schema factory、Pool 的 `casualty` refold trigger 和已存在的 L5 离线声明编译。生产 Gateway、提交后 receipt 调度、目标/条件求值、可信命令输出登记及 Workflow 义务恢复尚未实现。A 的 Morale/Presence 生产接线须分别等到域命令与可信输出合同可消费后推进。
- 当前准确状态是 Morale 和 Presence 均阻塞；D8 机制决策已解除，域输入与共享基线门槛未解除。此记录不表示任一 writer 或守城端到端验证完成。

### H-A-020 | Morale/Presence 输入合同建议 | 2026-11-23

- **Morale roster 建议复用 Organization 成员委派事件**：为守城建立明确的 `organization_ref`，由有效 Organization capability binding 限定该组织与版本化的 `role_ref`（守军成员角色），只把其已提交 `delegation_state=active` 成员纳入 roster。现有 `OrganizationMembershipDelegationIntent` 包含 `organization_ref`、`member_ref`、`role_ref`、`delegation_state`，Organization 按 `gameplay:organization:{organization_ref}` 持久写入并递增 stream revision。来源代码为 `backend/app/gameplay/organization_government_social_platform_runtime.py:94` 与 `backend/app/gameplay/organization_government_runtime.py:6921-6986`。
- roster 的历史有效点定义为 Organization 成员变更的 EventStore `global_sequence`。处理死亡时，只回放 `global_sequence <= death_event.global_sequence` 的指定 Organization stream，并取每个 member 的最新状态。这样禁止事后补记改变死亡时名单，也不需要用人口 roster 或工作班表推断守军。每个纳入成员的 LifeState 读取也截断到死亡事件位置；任一成员缺少可确认的初始存活状态、成员状态不唯一或 roster 为空均返回 unknown，不提交 Pool。输入 revision vector 必须包含 Organization stream 与逐成员 LifeState stream 的读取 revision。
- 该路线要求 Organization Owner 提供已注册的守军 `organization_ref` 和角色定义/绑定，并保证成员变更事件是该组织唯一的成员事实源。若产品需要回溯生效或将来生效的成员任命，现有事件没有 `effective_from`，必须由 Organization Owner 扩展其合同；在此之前以提交序号作为生效点。当前 A 不修改第四波 Organization/Government 枢纽代码。
- **Presence breach 输入建议复用 Facility integrity Pool 阈值事件**：正式 FactType 为 `fact:facility:<gate>:integrity`，Owner Production/Facility，原语 Pool；Facility 定义名为 `breach` 的 `PoolThreshold`。A 的 Pool projector 已持久生成 `gameplay.pool.threshold_crossed`，其 payload 携带 `fact_type` 和 `threshold_ref`，生产 EventSchema factory 已注册 Pool schemas。触发筛选为指定 gate integrity FactType 且 `threshold_ref=breach`。阈值上下界由 Facility Owner 在该事实配置中给出，不能从维修量或普通 condition 变化推导。
- Presence 收到已提交阈值越界后，仍须按自己的通行性合同重算并提交 `place:<gate>:passability` 独立状态；gate breach 不直接写 Presence。B 需交付 Facility integrity Pool writer/threshold configuration 以及 Presence resolver/写入合同，A 随后登记精确命令输出并接生产 Gateway。
- 以上复用方案不新增 Owner 或共用事实写权。实现顺序为共同基线先吸收 A 的 Pool schemas/runtime，Organization 与 Facility/Presence 域各自提交真实 writer，再由 A 完成 Gateway/L5 生产接线。直到这些提交各自具备定向、回放、revision conflict 与 P-3 证据，Morale 和 Presence 仍标阻塞。

### H-A-021 | 项目负责人授权 A 跨域补齐 Morale/Presence 输入 | 2026-11-23

- 项目负责人明确答复“授权 A 跨域实现”，授权范围是为 Architecture v2 M6-5 补齐守城 Morale 与 Presence 所需的权威输入 writer 和机制接线。A 依 H-A-020 的 Organization membership 与 Facility integrity Pool 方案实施，按可独立回退单元提交、逐单元验证，并保持 L5 只发命令、各 Owner 独立写入事实。
- 本授权解除线程原有域文件归属对这些 M6-5 输入单元的限制，不授权修改存储核心、共同禁区、对方独占文件或 Architecture v2 之外的角色智能体路径。每项仍须保持单一事实源、旧事件可回放、拒绝零写入和事件可见性证据。
- 实施计划为 `docs/verification/m6-5-authoritative-input-plan-20261123.md`。当前先做 Organization roster 历史快照，只读取 Organization 已有提交事件，不新增事件类型或 Writer。
- Organization 输入子单元已提交 `9cb0cbd5af691911a2b11e5e1be9e8e10d1bcba0`：`organization_garrison_roster_at` 按死亡事件 global sequence 读取指定 organization/role 的最新成员状态，验证 Organization Owner 事务归属，返回成员集合和截至该位置的 stream revision；空名单或无效历史为 unknown。三项专用测试 passed，永久选集 3 节点 problems=0、improvements=0，既有成员事件 P-3 为 registered/domain=organization。证据见 `docs/verification/m6-5-organization-roster-20261123.md`。这完成的是 Morale 的 roster 输入查询，不包含 D8 重算 writer 或 Gateway 调度。
- Facility 完整度事实仍需继续实施。当前代码搜索已确认一般设施 condition/维修事件不是守城 gate breach 输入；因此不能从该事件推导 integrity。后续需先确定已提交的影响事实能否提供 gate 目标及伤害数据，再接 Pool 阈值事件。`Facility.condition` 与 gate integrity 的语义保持区分，不新增并行 condition 副本。
- Facility integrity 输入单元已提交 `34d7e7342afb12ff308a807e6a03b6639ca90797`，并在 detached worktree 独立验证：五个永久选择节点 problems=0、定向 49 passed。`FacilityIntegrityAuthority` 将 `fact:facility:<gate>:integrity` 写到 Pool 原语并使用 Production/Facility transaction principal；配置缺少 `breach` threshold 时拒绝初始化，越阈生成 Pool 已提交事件，不写 Presence。现有一般 `Facility.condition` 与 repair 事件继续作为各自投影输入。证据见 `docs/verification/m6-5-facility-integrity-20261123.md`。
- 尚未找到已提交的 gate impact 事件或生产 writer 同时提供门目标和伤害数值，故新 Pool writer 当前没有从 Combat/impact command source 接入。不要以 repair/condition 更新、手工事件或未经 Owner 验证的观察代替。下一步需将 integrity writer 接到经信任的生产命令输入，并完成 Morale/Presence resolver 与提交后 L5 调度；M6-5 仍进行中。

### H-A-022 | Historical Pool input revision pin contract | 2026-11-23

- `da8fa3b82eadc0bcd33d4c7dd32bbcf838b1a56d` adds separate historical input pins and current CAS read heads to Pool adjustments. This permits Morale to calculate from Organization and LifeState history at a casualty event's global sequence without pretending those historical revisions are current stream heads. Calls that omit `read_stream_revisions` retain the original behavior.
- Detached-commit verification: targeted Pool, Organization, Facility, and LifeState tests 51 passed; ownership frozen selection `selected=24 problems=0 improvements=0`. Shared-replay selection `selected=990 problems=2 improvements=0`; both mismatches are the embodied interaction runner parameterizations and reproduce an external Port 8000 listener failure. The full suite was not run. Evidence and retained raw logs are linked from `docs/verification/m6-5-pool-historical-revisions-20261123.md` and `F:/paralls-verification/thread-a/m6-5-pool-historical-revisions-20261123-01/`.
- Pool historical pin plumbing is now available to the Morale writer. The writer currently under implementation consumes the Organization snapshot and LifeState histories and writes only the Morale Pool. It has not yet been committed or independently verified. Presence passability remains a separate Presence-owned commit; the official siege definition requires that independent evaluation and does not specify a condition formula that maps breach directly to passable.
- M6-5 remains in progress. No production Gateway/L5 dispatcher has been connected, and the Facility integrity Pool still lacks a trusted gate-impact command source.

### H-A-023 | Morale casualty refold component | 2026-11-23

- Commit `7ff3a3cb` adds `MoraleRefoldAuthority` over the existing Organization and LifeState event streams. At a committed LifeState death event's `global_sequence`, it resolves the configured Organization/role roster, validates each member's Owner-authored LifeState chain at that cut, computes living members divided by roster size, and submits one `morale_refold@1` Pool adjustment under the Morale principal. It never writes Organization, LifeState, or Presence facts.
- Missing/invalid roster or member LifeState returns `morale_input_unknown` with zero Pool writes. Source revision pins use historical revisions while current Organization and LifeState heads participate in the Pool commit CAS. The casualty event determines the stable idempotency key, so a retry after later source changes replays the original receipt.
- Detached validation on `7ff3a3cb`: targeted 49 passed, ownership selection `selected=24 problems=0 improvements=0`, shared-replay `selected=990 problems=2 improvements=0`. Both shared-replay failures are the embodied interaction runner tests blocked by an external listener on Port 8000. Full suite not run. Evidence `docs/verification/m6-5-morale-refold-20261123.md`; raw output `F:/paralls-verification/thread-a/m6-5-morale-refold-20261123-01/`.
- This closes only the Morale domain component. Morale FactType U2 registration/scope and authorized visibility remain unverified; the production L5 dispatcher and command trusted-output registration remain pending. Presence also remains pending because the formal contract requires its own passability decision and does not state a breach-to-passability formula. The Facility integrity writer still lacks a trusted gate-impact command source.

### H-A-024 | Presence passability assessment component | 2026-11-24

- 项目负责人选择“可信 Presence 决策输入，缺依据则 unknown”。A 在 `d7ae1d38c8217ca76da42a4654efe76bb4fabca4` 增加 Presence-owned `place:<gate>:passability` assessment writer。它只接受 Production/Facility Owner 已提交的 `gameplay.pool.threshold_crossed@1` breach 和 trusted resolver 给出的独立决定；决定需引用至少一个额外已提交证据事件。每个证据事件都校验来源 Owner transaction、visibility 和 revision，且来源 stream 当前 head 必须仍等于评估 revision。缺 resolver/独立证据返回 `place_assessment_unknown`，stale source 返回 `place_assessment_source_stale`，两者零写入。breach 本身不映射成 passability。
- 事件 `gameplay.presence.place_passability_changed@1` 已接入 Stormnight production EventSchema factory，`gameplay_schema_event_types()`/`FACT_TYPE_REGISTRY` 可见，domain=`presence`。写入方与读取方枚举及 DoD 状态见 `docs/verification/m6-5-presence-passability-20261124.md`。
- 独立 worktree `F:\codex-temp\a-m6-5-place-verify-20261124` 定向 12 passed；P-3 断言通过；ownership 选集 `24/24 problems=0 improvements=0`。shared-replay `selected=990 problems=2 improvements=0`，两项 embodied interaction runner 测试在父 SHA `5d7cc0da` 以同一外部 Port 8000 错误复现；未终止或修改该外部进程。Presence 自有 selection `selected=6 problems=0 improvements=0`。原始日志位于 `F:\paralls-verification\thread-a\m6-5-presence-shared-replay-20261124-02\`、`m6-5-presence-parent-diff-20261124-01\`、`m6-5-presence-selection-20261124-01\`。全量未运行。
- 未完成项：L2 FactType 完整 schema/Owner declaration、U7 可见性与 `read_as`、规则包 Resolver 注册、Gateway/L5 提交后 dispatch、端到端触发和全量。现有 `project` visibility 是运行时值，尚未由 v2 FactType contract 证明。此提交不等于 M6-5 完成或 M1-4 Place 原语完成。
- Combined-worktree full suite at this SHA completed with `10,543 passed, 35 failed, 2 skipped, 2 xfailed, 239 warnings` and exit code 1. The 35 failed test cases were identical in two runs at the same SHA. The earlier longer-temp-path run had 12 additional path-sensitive failures. Raw short-path output is retained at `F:\paralls-verification\thread-a\m6-5-presence-full-short-20261124-01\full\`; no clean full-suite pass is claimed.

### H-A-025 | M6-1 L5 committed reaction dispatch component | 2026-11-24

- Commit `dabb7f4e0756d8bdfa61207ad808e98055623978` adds `TrustedGameplayCommandGateway` and `L5ReactionDispatcher`. It matches committed transactions, submits stable per-reaction/event command keys, requires explicit trusted FactType outputs for each handler, and rejects unresolved condition references. It does not append facts.
- Verification at `90af2255`: six focused L5/rule/schema test files, 148 passed; 19 registered selections, 141 nodes, zero differences; frozen selections 1,169 nodes with two shared-replay failures caused by external Port 8000 listener state. Full suite not run for this component. Evidence is `docs/verification/m6-1-l5-dispatch-runtime-20261124.md`, raw output is `F:/paralls-verification/thread-a/m6-5-l5-gateway-20261124-02/`.
- Production `main.py` registration and M6-5 domain handlers remain pending. The repository has a Facility integrity Owner writer but no committed gate-impact producer carrying both gate identity and impact quantity. A Presence resolver still requires an injected trusted decision plus committed evidence; the selected policy returns unknown with zero writes when that evidence is absent. The pending user question proposes a trusted simulation-host command as the source for these inputs, with each Owner committing its own facts. No end-to-end production claim is made.

### H-A-026 | Place machine IDs in L5 trusted outputs | 2026-11-24

- 项目负责人确认 Presence 的通行性决定来自可信输入，缺少依据时返回 `unknown`。这没有定义 Facility gate-impact 命令的可信来源。A 已单独询问该来源应采用经认证的模拟宿主输入还是等待 Combat Owner 事件，当前等待答复。
- 正式守城 Demo 将 Presence 输出标识为 `place:gate-03:passability`。原 L5 输出校验只接受 `fact:`，无法登记正式 Place machine。提交 `4023c182158a7d90185b72e17acfeedf1c7d3c0f` 使 reaction compiler 与 trusted output gateway 接受精确 `place:` 标识，仍拒绝通配符和空白；L5 只派发命令，不写 Owner 事实。
- 验证：Python 3.12.2，`app.__file__` 在当前 A worktree；L5 两文件定向 `20 passed`、Place 输出永久选择 `selected=3 problems=0 improvements=0`、冻结 ownership `24/24 problems=0`。shared-replay `990` 节点中两项失败是 `test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage]` 与 `[wall-clock]`，原始日志报 Port 8000 被外部无健康服务占用；未终止或修改该进程。全量未运行。证据和原始输出见 `docs/verification/m6-5-place-machine-output-type-20261124.md` 与 `F:/paralls-verification/thread-a/m6-5-place-output-types-selections-20261124-01/`。
- 未完成：`main.py` 生产 dispatcher/handler 注册、真实 Morale/Presence command handler、county siege rule pack、Morale 与 Place 的 v2 FactType/read_as 注册、Presence trusted resolver 和 gate-impact 输入源仍未完成。本提交只解决 L5 无法表达 Place trusted output 的类型兼容问题，不代表 M6-5 或 Architecture v2 完成。

### H-A-027 | M6-5 production Morale and Presence wiring | 2026-11-24

- 项目负责人确认 Presence 的规则是可信决策输入，缺少依据时返回 `unknown`。A 的生产接线提交 `4506d9071f7f5779bdd46100419417aa8a30d4e8` 已在 `main.py` 注册提交后 reaction dispatcher、Morale/Presence Owner handlers 和 county siege rule pack。生产 Morale 首次有效 casualty 会从配置基线初始化同一个 Morale Pool，再以事件位置 roster/LifeState 历史重算；Presence handler 在无 resolver/evidence 时安全返回 unknown 且零写入。
- Detached 验证：定向 80 passed；新永久选集 4 节点 `problems=0 improvements=0`；ownership 24 节点零差异。shared-replay 990 项有两个 Port 8000 外部监听失败，与父基线记录的失败类别相同。全量未在该提交运行。详细状态、U1–U11 和原始输出目录见 [M6-5 production wiring evidence](../verification/m6-5-production-wiring-20261124.md)。
- 缺少的仍是可信 Facility gate-impact 生产事件，以及能够独立给出 `blocked/passable`、证据事件和 revision 的 Presence 输入。现有 Combat settlement 只接受单个角色目标并依赖角色 Presence/LifeState/Faction，不可代表攻门输入。不能把 breach、维修、condition 或普通观察转成 Presence 决策。A 已向项目负责人提出以可信模拟宿主提交独立 impact 与 Presence 决策证据的合同方案；在输入合同确定前，生产 Presence 保持 unknown、零写入。M6-5 继续进行中。

### H-A-028 | M6-5 输入来源按正式 impact_gate 规格复核 | 2026-11-24

- 正式文档 `docs/architecture-v2/07-玩法组合/02-守城Demo定义.md` 将 `impact_gate` 定义为四层 `obligation`，说明 UE 碰撞证据经 Gateway 形成 `Command(impact)`；`docs/architecture-v2/05-规则包/02-受击剖面.md` 规定门完整度与 Presence 通行性分开结算，不能按 breach 自动映射。A 已撤回上一条“宿主直接提交 damage 数值”的宽泛建议，按正式路径应由 Gateway 验证碰撞证据、服务端已注册 impact profile 解析，Facility Owner 提交 integrity，Presence Owner 再提交独立评估。
- 当前代码的 `backend/app/gameplay/l5_pipeline.py` 只有 profile 编译与输入 revision vector 校验，没有 impact resolver 执行器。`PhysicsContactReceiptAuthority` 能持久化签名碰撞证据，但 `main.py` 当前入口是 street-combat 角色 encounter 路径；它未接 gate 目标或 `impact_gate`，也不含 gate 的伤害解析。正式文档未给出城门 Profile 数值/Resolver 参数，代码包中也未发现相应 gate profile。没有擅自补造 damage 值。
- UE 到 Presence 的评估回执协议也未发现。负责人已确认“可信 Presence 决策输入，缺依据时 unknown”，因此已知决策语义；仍需定义该 trusted input 如何从 UE/Gateway 进入 Evidence Store 并携带来源事件/revision。A 已提请负责人确认是否授权起草 M6-5 固定 profile 参数与 UE Presence 回执合同。答复前继续保留 unknown、零写入行为，不宣称 `impact_gate` 或 M6-5 完成。

### H-A-029 | M6-5 signed physical input evidence slice | 2026-11-24

- 项目负责人选择可信 Presence 决策输入，缺依据时 unknown，并授权 A 跨域实现。A 提交 `22bf06158969c4b7419a93a17654408a1c6b58ab`、`6cf4ea8613a2d8626c83371a020b5f890d2ca60d`，持久化独立签名 Gate impact / Presence assessment 回执，注册 EventSchema 与 checkpoint replay participant。Detached 定向 13 passed，ownership 24 节点零差异；shared-replay 990 中两项 Port 8000 外部服务失败，原始输出位于 `F:/paralls-verification/thread-a/m6-5-input-slice1-6cf4ea86/`。证据见 `docs/verification/m6-5-siege-physical-inputs-plan-20261124.md`。
- 后续实现增加 Facility profile 驱动 Pool writer、Presence 消费 assessment 并写 Place、以及主应用 HTTP 输入 route，当前定向 20 passed，仍待独立提交和 selection 验证。生产启动已接现有 `physics_contact_authority_secrets` 验签配置。
- 正式文档与当前规则包未提供生产 Gate impact delta 和 integrity 初始/阈值配置。缺内容时 Gateway 持久化已验签的输入 evidence，但报告 Facility `not_configured`，不写测试数字。该配置是端到端 Gate 生产写入的剩余数据依赖；不得用 breach 自动推断 Presence。

### H-A-030 | M6-5 domain input and HTTP Gateway slice | 2026-11-24

- A 提交 `4349081644991ae896f15263861c5fb09096f046`：main HTTP Gateway 接收两个独立签名输入；Gate path 由 Facility resolver 消费 server profile 并经 Pool 写 integrity，Presence path 将签名 assessment 及其 source event/revision 交给 Presence 写 Place。验证还覆盖精确重试、未知 profile / stale revision 零写入及真实 HTTP Gate endpoint。代码职责和调用路径见 `docs/verification/m6-5-siege-physical-inputs-plan-20261124.md`。
- 该 SHA 的 detached 定向 20 passed，ownership `selected=24 problems=0 improvements=0`；shared-replay `selected=990 problems=2 improvements=0`，两项是 Port 8000 外部服务占用失败；全量未运行。原始输出在 `F:/paralls-verification/thread-a/m6-5-owner-inputs-slice2-43490816/`。
- main 启动接入现有 `physics_contact_authority_secrets`。但生产没有权威 Gate 初始值、threshold 和 impact delta 配置，main 尚无 Facility authority 实例可交给 Gateway；因此 HTTP Gate path 在该状态明确为 `not_configured`，实际生产 Pool 写入仍待该内容配置。测试中的 `-20` 仅是测试 fixture，不是生产值。不得把测试数据升级为事实。

### H-A-031 | M6-5 optional Gate config and formal obligation gap | 2026-11-24

- A 提交 `55161d47d43a43cdf9074f725053b380e5739d29`，通过 `SIEGE_FACILITY_GATE_PROFILES_JSON` 将权威 per-gate lower/upper/initial、breach threshold/reset threshold 与 impact-kind delta 配置接入 main 启动。空列表 fail-closed，完全不创建 Facility writer；没有默认数值。该 SHA detached 定向 49 passed，ownership `24/24 problems=0`；shared-replay `990` 两项 Port 8000 外部服务失败，见 `F:/paralls-verification/thread-a/m6-5-configured-gate-slice3-55161d47/`。
- 尚未收到生产 gate profile 的实际数值，不能验证真实城门输入和 threshold 触发。通过内容配置即可启用 Facility writer，但本地和生产环境当前都未完成数值装载验证。
- 正式 `impact_gate` 要求的耐久 obligation 运行时尚未接入。当前已验签 HTTP Gateway 持久化 evidence 后直接调用 Facility Owner；现有 L5 dispatcher 负责 casualty 到 Morale 与 breach 到 Presence，不负责 Gate impact 的 obligation 生命周期/恢复。因此 M6-5 仍不是完整正式 `impact_gate` 流程，也未做全量或完整 siege playthrough。

### H-A-032 | M6-5 test fixture credential cleanup | 2026-11-24

- Two test-only HMAC fixture literals that resembled credentials were replaced with the explicit placeholder `fixture-key` in `test_m6_5_siege_runtime.py` and `test_siege_physical_input_runtime.py`. The inputs and assertions are unchanged.
- Focused verification at the A worktree: Python 3.12.2, `app.__file__` under the A worktree, `PYTHONPATH` set to its `backend`; both test files reported 14 passed with 6 existing deprecation warnings. Raw output is in `F:/paralls-verification/thread-a/m6-5-fixture-refresh-20261124-050542836/`.
- P-1 scan of additions relative to `origin/integration` found zero credential-pattern matches after excluding explicitly named test-fixture values. No secret value was emitted or stored by the scan.
- This cleanup does not change M6-5 status. The `impact_gate` durable obligation executor/recovery, authoritative production Gate profile values, and a fully configured siege run remain unverified as described in H-A-031.

### H-A-033 | M6-5 durable input obligation recovery | 2026-11-24

- Commit `102e4380f2bbc3e85700e4332bfeae1ea01d69f3` scans durable signed Gate-impact and Presence-assessment input events at application runtime assembly. The same Facility and Presence Owner handlers reconcile each input, and their existing idempotency receipts prevent duplicate facts. No workflow-state event stream was introduced.
- Exact-commit detached verification: four focused files, 26 passed; M6-5 selection 6 nodes zero differences; ownership 24 nodes zero differences. Shared-replay 990 has two Port 8000 failures. Re-running those exact nodes at parent `8227e94c` produced the same two failures. Full suite not run. Evidence and raw output are in `docs/verification/m6-5-obligation-recovery-20261124.md` and `F:/paralls-verification/thread-a/m6-5-obligation-verify-102e4380/`.
- Remaining: restart against a durable database file is not tested. Production Gate numeric profiles remain unsupplied. The formal four-layer `impact_gate` also specifies separate door-leaf and latch durability stages, for which this branch has no authoritative input contracts or writers. M6-5 remains incomplete.

### H-A-034 | M6-5 Information production wiring | 2026-11-24

- A fetched `origin/thread-b/reference-data-20261123` at `25674219ae951efcb5915c8293bf0c1a30196b85` and selectively integrated the Information runtime/schema/tests from `abba3c3c`, its syntax repair from `6741ab61`, and the Information reaction pack/update from `63f41c8b`. No B branch merge and no `integration` change. A code commit is `9395181df1d94c2c6faf5363d73ac8858dcb5e17`.
- `create_stormnight_event_schema_registry()` now registers SocialDelivery v1/v2 and Information `knowledge_updated@1`. M6-5 loads `county_siege_information` into the existing L5 dispatcher and trusted Gateway, using the same GameplayEventStore and Information owner handler. `main.py` passes the authoritative world tick and the source-event allowlist setting.
- A delivery only maps to `fact:information:siege:report` when its source event type is explicitly allowlisted, stream and revision match the committed delivery, and its payload `fact_type` is exactly the siege-report FactType. Missing world tick raises a retryable callback failure so existing pending projection refresh processing can retry. The environment key is `SIEGE_INFORMATION_REPORT_EVENT_TYPES_JSON`, defaulting to an empty list.
- Exact detached verification at `9395181d`: Python 3.12.2, SQLite 3.43.1, `app.__file__` under the detached A worktree; 11 related test files, 208 passed. Frozen ownership/modifier/equipment/inventory groups had zero problems across 179 nodes; the 14-node Information selection and 6-node M6-5 selection had zero problems. Shared-replay 990 had two Port 8000 failures. The same exact two nodes failed on parent `10bcb918` with the same “occupied by an external process without a healthy backend” error. Full suite was not run. Evidence and raw outputs are in `docs/verification/m6-5-information-production-wiring-20261124.md` and `F:/paralls-verification/thread-a/information-commit-9395181d-*`.
- Formal `02-守城Demo定义.md` uses `fact:information:*:report` / `report_delivered` as a reaction example. `01-内核/05-传播延迟与失真.md` assigns submission of the report fact to Information Owner. Neither those documents, the A code, nor the B delivery pack identifies an actual production report source event or writer. The source allowlist is therefore empty and real report delivery is not verified. Information/守城内容事实生产者 must provide the registered source event type, Owner/stream/revision contract and payload FactType. The project lead must confirm the production allowlist value. M6-5 remains in progress.

### H-A-035 | M6-5 Information source producer audit | 2026-11-24

- Follow-up search confirms the only `gameplay.social.knowledge_observed` source is `backend/tests/test_information_production_wiring.py:15`; the test constructs it directly with `build_atomic_event_batch()`. It has no production EventSchema registration or writer. `fact:information:siege:report` appears in the Information reaction, runtime constant, and tests, with no report producer in `backend/app` or `packs`.
- The formal siege definition gives a `report_delivered` Reaction example. The Information delay/distortion specification assigns report-fact submission to Information Owner but does not specify an event type, payload fields, or producer contract. The configured-source L5 test therefore does not identify a real source or prove report delivery end to end.
- `SocialDeliveryAuthority._source_visible()` accepts public sources or sources already visible to the recipient, while the formal visibility model requires finite knowledge before arrival. The project lead selected creating a recipient-scoped source event at publication time. A's proposed contract is documented in `docs/superpowers/specs/2026-11-24-m6-5-information-report-source-design.md` and awaits design review before code changes. The source allowlist remains empty pending implementation and verification.
- Detailed search evidence is in `docs/verification/m6-5-information-production-wiring-20261124.md`.

### H-A-036 | Information-owned siege report source delivered | 2026-11-24

- The project lead approved the A-owned report source design and selected creation of a recipient-scoped source event at publication time. A implemented `gameplay.information.siege_report_published@1`, the Information report FactType and publication command, dedicated signing configuration, `POST /api/v2/siege/information/report-publication-input`, SocialDelivery dispatch and L5 source recognition bound to the committed Information Owner transaction.
- A selectively used B commits `abba3c3c`, `6741ab61`, and `63f41c8b`. A implementation commits are `0fd74b4c`, `f442c1f9`, and `3fe50ca5`. No B branch merge or integration change was made.
- Exact-tip focused verification: 199 passed, 6 warnings. The new 25-node Information report selection had `problems=0 improvements=0`. Frozen shared-replay had two Port 8000 external-service failures reproduced on parent `f442c1f9`. Full merged-worktree suite exited 1 with 10,603 passed, 21 failed, 2 skipped, and 2 xfailed. Failures include missing `tokenizers`, Port 8000 availability, and Godot parse/type-resolution errors. They were not rerun on the parent SHA and are not classified as baseline failures. Full raw output: `F:/paralls-verification/thread-a/information-report-full-3fe50ca5-20261124-03/full.log`.
- Detailed evidence: `docs/verification/m6-5-information-report-source-20261124.md`. M6-5 remains in progress. The formal `impact_gate` obligation, production Gate profile values, and fully configured end-to-end siege playthrough remain unverified.

### H-A-037 | M6-5 layered impact_gate and derived obligation progress | 2026-11-24

- No new B delivery was needed. This A slice adds signed v2 Gate impact with a pinned door/latch/integrity revision vector, ordered Facility Pool damage, latch Machine reconciliation, optional configured profiles and the production HTTP route. Information remains the previously selected B delivery in A history.
- The project lead selected continued Presence evaluation without rollback of committed physical damage. A rebuildable obligation projection now uses the signed input, Facility transaction, Presence assessment input and Place output as step receipts. It stores no duplicate workflow state. Open obligations remain open until a committed Place decision exists.
- Root-cause review found that startup attempted to initialize an already existing integrity stream and failed on revision conflict. Layered startup now validates and reuses that stream while creating missing layer streams. The review also found door-leaf-only damage could produce a latch transition without a latch Pool revision. Latch transitions now require latch-durability change in the same Facility commit.
- Focused command covered layered Facility, M6-5 Gateway/runtime, signed physical inputs, Facility integrity, rule pack validation and real checkpoint cut/tail. Result: 164 passed, 6 warnings. M6-5 layered selection 16, Information selection 25 and frozen ownership/modifier/equipment/inventory selections 179 nodes had zero problems and improvements. Shared-replay 990 had two external Port 8000 failures, reproduced on parent 7601189a. Raw outputs are in `F:/paralls-verification/thread-a/m65g-obl-projection-01/`, `m65g-layered-selection-final-02/`, `m65g-information-final-01/`, `m65g-shared-replay-final-01/`, `m65g-narrow-ownership-02/`, `m65g-modifier-20261124-01/`, `m65g-equipment-20261124-01/`, and `m65g-inventory-20261124-01/`.
- Exact commit a9f5385a focused verification passed 164 tests. M6-5 16, Information 25 and the frozen ownership/modifier/equipment/inventory groups all had zero problems. The exact commit full suite had 10,630 passed, 12 failed, 2 skipped, 2 xfailed; all 12 failed nodes reproduced at parent 7601189a. Shared-replay had two Port 8000 external-process failures also reproduced at parent. P-1 scan found zero credential-pattern hits in staged additions. No production Gate values, live Unreal transport, or fully configured siege run were supplied. At this point the Presence receipt contract still required a breach event; that limitation is superseded by H-A-038 below. M6-5 remains in progress and has not entered integration.

### H-A-038 | Every layered Gate impact can settle an independent Presence assessment | 2026-11-24

- A implementation commit `e246f2c08734ebc358bf81f3bc5637d29f869280` adds `PresenceAssessmentReceiptV2` to the production EventSchema factory and existing HTTP route. The independently signed Presence assessment references a committed layered Gate impact, matching gate incarnation, all three current Facility revisions, and current Place revision. A breach event is optional. The Place output read vector also pins the signed impact input stream.
- Historical v1 breach-bound receipt/event readers and recovery behavior remain intact. Same-state Place evaluation commits a private Presence confirmation event so the derived impact obligation receives a durable Presence step receipt without a Place state transition. The obligation projection reconstructs status from the immutable Gate input, Facility Owner transaction, signed Presence input, and Place transition/confirmation. Unknown Presence still makes no Place decision and leaves the obligation open.
- Checkpoint cut/tail coverage now includes both signed v2 impact and Presence assessment input receipts. The production schema factory is asserted in tests. The implementation added no production Gate values.
- The first read-vector regression run failed because the committed Place output omitted the impact input stream. After pinning that stream, focused verification passed 169 tests with 6 warnings. M6-5 selection 21, Information 25, siege Information 25, ownership 24, modifier 12, equipment 87, inventory 56 and shared-replay 990 all returned zero problems and improvements.
- Exact backend suite at `e246f2c0`: 10,628 passed, 19 failed, 2 skipped, 2 xfailed. All 19 failed node IDs were rerun at parent `9b46742ee5a4c709e166ff247b5161101d4cd1f1` and failed there too, with identical node sets. Root pytest collection also has a separate missing `jsonschema` dependency in `scripts/verification/tests`; backend full suite was run with explicit `backend/tests` from the repository root. Evidence and raw output are in `docs/verification/m6-5-presence-impact-followup-20261124.md` and `F:/paralls-verification/thread-a/m65-presence-*`.
- The unchanged configured-test profile is a simulation only. Production Gate values, a live Unreal assessment transport and a configured full siege run remain unverified. M6-5 remains in progress and is not merged to `integration`.

### H-A-039 | 项目负责人决定：生产 Gate 配置与 integration 边界 | 2026-11-24

- 项目负责人采纳建议：生产 Gate profile 继续保持未配置，等待权威生产数值或配置来源；规则包中明确标为演练的数值仅用于演练，不提升为生产参数。
- 项目负责人采纳建议：保持 A 分支工作，不合入或修改 `integration`。当前 A 分支包含多项尚未合入的任务，不能把它当作单独的 Gate 配置变更合入。
- 现有 `SIEGE_FACILITY_GATE_PROFILES_JSON` 配置入口继续作为权威 profile 的接入方式。为空时 Gateway 保持 fail-closed，不提交 Facility 数值事实。
- 后续只有在负责人提供生产配置来源/数值或明确指定演练环境，并重新说明目标分支范围后，才变更对应配置或集成目标。

### H-A-040 | M1-3 Pool 正式规格静态审计 | 2026-11-24

- A 对正式六原语规格 Pool 专节与当前 `pool_runtime.py`、测试和已有 M1-3 证据作了只读对照，结果见 `docs/verification/m1-3-pool-spec-audit-20261124.md`。本次没有改代码、事件合同或运行 pytest。
- Pool 已有显式 ticks 的 `integrate` 和 `window_ref` 幂等，阈值转换也与调整原子提交。静态调用点搜索没有找到生产代码调用 `integrate`，因此尚无生产调度把 `SimulationDriver.current_tick` 接入 Pool streams，或在 revision/threshold/pause/handoff/version 边界驱动结算。`SimulationClock` / `SimulationDriver.current_tick` 是现有候选权威时钟；后续实现可按各域 Pool stream 接入，不必先新增全局时钟。
- 固定 `rate_per_tick` 分段结算可沿用现有 `integrate` 命令和 window 幂等键。只有需要在同一分段内表达非恒定 rate、且中途达到零后恢复时，才需扩展事件以保存轨迹或最低值。当前没有已迁移生产 Pool 定义要求该语义，本轮不新增事件字段。Pool 的 U1/U2/U5/U7/U8 与 G5 缺口仍依赖域归属、M2-2、Resolver 合同和门禁证据。
- 审计后在当前 A tip `5e7b7eeb97bdc2216065f67bdf36546be56a8d69` 单独运行 Pool 定向回归：Python 3.12.2、`app.__file__` 位于当前 A worktree，`backend/tests/test_pool_runtime.py` 为 `19 passed, 2 warnings`。冻结选集和全量未运行，原全量失败记录不变。
- M1-3 继续为 `待门禁`。该定向回归不消除上述事件语义缺口，也不构成 G5 通过。

### H-A-041 | M5-5 FactType distribution refold 缺失校验 | 2026-11-25

- Architecture v2《03-校验器规则》定义 `facttype_refold_missing` 为 `aggregation=distribution` 而缺 `refold_model_ref`。此前规则包聚合模型自身要求 refold Resolver，但 FactType 未执行该条规则。
- A 在 `FactTypeRegistry.compile` 增加编译期拒绝，并加入使用现有 Facility Pool FactType 的回归测试。TDD 红例为 `load_pack` 未抛 `RegistrationRejected`；修复后的规则包和 Pool 定向共 `120 passed`。证据、选择集与原始输出见 `docs/verification/m5-5-facttype-refold-20261125.md`、`docs/verification/selection/m5-5-facttype-refold.json` 和 `F:/paralls-verification/thread-a/m5-5-facttype-refold-20261125-01/`。
- 这是 M5-5 的一个拒绝规则，不覆盖其它未实现的 Validator 规则。持久事件未改。代码提交 `f0c9108dc715869f73b6a919e3fd674f87292b4c`。

### H-A-042 | M5-5 规则验证与临时目录迁移 | 2026-11-25

- 冻结五组选集共 1,169 节点、登记 25 组选集共 222 节点。逐项对照 selection manifests 与本次保留的 batch `results.json`，均为 `problems=0 improvements=0`。原始批次和退出码见 `F:/paralls-verification/thread-a/m5-5-refold-gates-20261125-01/`。
- 在 `f0c9108d` 的 backend 全量收集 10,652 节点，结果 `10,624 passed, 24 failed, 2 skipped, 2 xfailed`，退出码 1。只在父提交 `f5cc3632` 重跑这 24 个失败节点，当前与父提交失败节点集合、阶段和错误类型一致，`new=0 parent_extra=0`。父提交复跑不是全量。全量与父复跑原始输出分别位于 `F:/paralls-verification/thread-a/m5-5-facttype-refold-full-20261125-f0c9108d/` 和 `F:/paralls-verification/thread-a/m5-5-facttype-refold-parent-20261125-03/`。这表示该单元没有增加所比较的失败，不表示全量通过。
- 运行时环境为 Python 3.12.2，`app.__file__` 指向 A worktree，SQLite 3.43.1。证据列出 U1–U11 状态和未覆盖的 M5 工作；M5 与 Architecture v2 均未完成。
- 本轮 pytest 临时数据从 `D:/codex-temp/user-temp/pytest-of-User/pytest-2026` 搬到 `F:/paralls-verification/thread-a/pytest-scratch-m5-5-f0c9108d`，共 8,176 个文件、937,244,243 bytes。D 源目录目前无普通文件，留有 1,446 个指向 F 盘本轮 scratch 的目录符号链接；没有删除这些链接，也没有触碰 `pytest-2027`。

### H-A-043 | M5-5 FactType scope 缺失拒绝码与全量复验 | 2026-11-25

- 依据正式《03-校验器规则》，`facttype_scope_missing` 与 `facttype_naming_invalid` 是两个独立拒绝码。提交 `3907d4eb45b93cc95d4d5e866b25cd92a5e6f74a` 将省略 scope 的 `fact:credential:link` 和空 scope 的 `fact:credential::link` 分别映射到专用拒绝码。两条测试先红后绿；`test_rule_pack_validator.py` 与 `test_pool_runtime.py` 共 `122 passed, 2 warnings`。
- 使用 `docs/verification/absorb-main-3bf3418e/compare_selection.py` 和修正路径的 F 盘临时配置重跑冻结及全部登记集：冻结 5 组、1,169 节点；登记 25 组、224 节点；所有组均 `problems=0 improvements=0`。原始批次在 `F:/paralls-verification/thread-a/m5-5-scope-gates-corrected-20261125-3907d4eb/`。
- 修正环境下 full suite 收集 10,654 节点，`10,623 passed, 27 failed, 2 skipped, 2 xfailed`，退出码 1。24 个失败节点、阶段和错误类型与 `f0c9108d` 全量结果一致；新增的两个 `test_embodied_interaction_session_runner` 失败均报告外部 `D:\cl-laya` 占用 Port 8000。另有一项 outbox hard-kill recovery 的 `PermissionError` 在从 worktree 根目录单测重跑后 `1 passed`。全量原始输出为 `F:/paralls-verification/thread-a/m5-5-scope-full-corrected-20261125-3907d4eb/`，单测重跑为 `F:/paralls-verification/thread-a/m5-5-outbox-recheck-20261125-3907d4eb/pytest.log`。full suite 仍未通过，不能记作全量通过。
- 初始尝试将 Windows 反斜杠路径写入 `PYTEST_ADDOPTS`，pytest 将反斜杠按转义解析，使临时目录错误地进入 `backend` 并产生 48 项失败。该轮明确作废，两个本轮临时树已移到 `F:/paralls-verification/thread-a/pytest-scratch-m5-5-scope-full-3907d4eb-misparsed` 与 `pytest-scratch-m5-5-scope-gates-3907d4eb-misparsed`。之后统一在 `PYTEST_ADDOPTS` 使用正斜杠，并从 A worktree 根启动测试。
- M5-5 的这两条拒绝规则已实现并有回归，但其它 Validator 规则、M5-3/M5-4 及 Architecture v2 总体验收仍未完成。

### H-A-044 | M5-5 FactType primitive 缺失拒绝码与全量复验 | 2026-11-25

- 提交 `a5823c4b08265954ebdf0f7bc03b95864b9cbd1e` 让缺少 `primitive` 的 FactType 通过 pack shape 检查到 `FactTypeRegistry.compile`，由编译器发出 `primitive_missing`。不支持的非空原语仍在 shape 层拒绝。回归测试先红后绿，Validator、Pool 与 FactType 定向共 `126 passed`。
- 冻结 5 组选集 1,169 节点及登记 25 组选集 225 节点均 `problems=0 improvements=0`。新增 M5-5 登记选择现有 4 个回归节点，`selected=4 problems=0 improvements=0`。
- 清理继承的 `GIT_CONFIG_*` 后全量 backend suite 为 `10,647 passed, 4 failed, 2 skipped, 2 xfailed`，退出码 1。四个失败节点是 calibration budget、Task45 Godot probe、population cold-ready 和 Task8 Godot probe。在父提交 `735e283f` 上同样四项失败。首次未清理环境的尝试另有一个 population recovery 子进程受空 `GIT_CONFIG_VALUE_0` 影响；清理该环境后该节点在父提交与当前代码均通过。全量结果不是通过。
- 环境为 Python 3.12.2、pytest 9.1.1、SQLite 3.43.1，`app.__file__` 指向 A worktree。原始验证输出位于 `F:/paralls-verification/thread-a/m5-5-primitive-focused-clean-6bc5e6dd5fb8444aad830cba322c14a7/`、`m5-5-primitive-gates-de033677e0964158a3a151394aa1ddb6/`、`m5-5-primitive-regression-exact-6ae3c9e3fc734133aa7b808f4d9d8368/`、`m5-5-primitive-full-clean-69d67f5380614bcba373828e38ea4c2d/`。
- 此提交只完成 M5-5 的一项拒绝规则。其它 Validator 规则、M5-3/M5-4 和 Architecture v2 总体验收仍未完成。

### H-A-045 | M5-5 pack_defines_primitive 与全量复验 | 2026-11-25

- 提交 `553c35bd139fa6bf4dd0b0d2e7adea046931b626` 在 `pack.yaml` 顶层或 `contents` 区段出现 `primitives` 时发出专用 `pack_defines_primitive`，不再静默接受或降为通用 schema 错误。TDD 两个红例在父提交 `a5823c4b` 复现。实现后 Validator、Pool 与 FactType 定向 `128 passed`。
- 冻结五组选集共 1,169 节点、全部登记 25 组选集共 227 节点均 `problems=0 improvements=0`。M5-5 自有回归选集目前 6 节点，`selected=6 problems=0 improvements=0`。
- 清洁环境 backend 全量为 `10,648 passed, 5 failed, 2 skipped, 2 xfailed`，退出码 1。四个失败在父提交 `a5823c4b` 复现。第五个 `test_original_owner_provider_pending_survives_hard_kill_without_reingest[character]` 在父提交及当前提交的定向重跑均通过，记录为单次全量失败，不能由此宣称全量通过。
- 环境 Python 3.12.2、pytest 9.1.1、SQLite 3.43.1，`app.__file__` 在 A worktree；验证输出保留于 `F:/paralls-verification/thread-a/m5-5-pack-defines-primitive-red-repro-20261125-confirmed.log`、`m5-5-pack-defines-primitive-focused-clean-dd5abc0da5b04e629ae45aeb27904ea2/`、`m5-5-pack-defines-primitive-selection-d089cad043ff490baa822cf2a2a152d3/`、`m5-5-pack-defines-primitive-gates-d49ba160907842178acef60d67841bbc/`、`m5-5-pack-defines-primitive-full-46dda022c3cc4a9486bc221b28103e0e/`、`m5-5-pack-defines-primitive-parent-failures-20261125.log` 和 `m5-5-pack-defines-primitive-current-failure-recheck-20261125.log`。
- 本提交只覆盖规则包不得定义原语这一项规则。其余 Validator 目录、M5-3/M5-4 和 Architecture v2 总体验收仍未完成。

### H-A-046 | M5-5 primitive_unknown 专用诊断与全量复验 | 2026-11-25

- 提交 `888ec615d9ac87480905ae661fbf51d2931a5670` 让规则包 loader 将六种已登记原语之外的值归为 `primitive_unknown`。这是注册期校验，不改变已持久事实或运行时。已知但尚未实现的 Bond、Holdings、Process、Place 与六种之外的未知值区分；当前 FactType 编译仍只支持 Machine 与 Pool。
- 未知原语回归先红后绿。FactType、RulePack Validator 和 Pool 定向共 `129 passed`。冻结五组选集 1,169 节点及登记 25 组选集 228 节点均 `problems=0 improvements=0`。M5-5 七节点回归选择 `selected=7 problems=0 improvements=0`。
- 清洁环境 backend 全量 `10,650 passed, 4 failed, 2 skipped, 2 xfailed`，退出码 1。四个失败均为前几轮确认的 baseline/environment failures：calibration budget assertion、Task45 Godot probe、population cold-ready report、Task8 Godot probe；同四项已在父提交 `a5823c4b` 的 M5-5 failure comparison 中复现。此处不宣称全量通过。
- 环境 Python 3.12.2、pytest 9.1.1、SQLite 3.43.1，`app.__file__` 位于 A worktree；原始验证输出在 `F:/paralls-verification/thread-a/m5-5-primitive-unknown-red-20261125/`、`m5-5-primitive-unknown-focused-9178ee71d16d453e89a72eacbbb20295/`、`m5-5-primitive-unknown-selection-8283035f75c54a5a918f5817b2ef1479/`、`m5-5-primitive-unknown-gates-53116699456140fb923dcd3f56c1664e/`、`m5-5-primitive-unknown-full-9bd3859f809244019c3c8b23ed37cccf/`。
- 该提交只完成 `primitive_unknown` 诊断。其余 Validator 规则、Bond/Holdings/Process/Place 编译与 M5-3/M5-4、Architecture v2 总体验收仍未完成。

### H-A-047 | FactType primitive 登记集合收敛 | 2026-11-25

- 提交 `cbee0c6cf8c436ff7fbfa00373c655b3131d2ed3` 将六个 primitive ID 放到 `fact_type_registry.py` 的 `REGISTERED_FACT_TYPE_PRIMITIVES`，规则包 shape validator 引用同一集合，删除重复硬编码。这是行为保持的维护提交。
- 定向 FactType、Validator、Pool 测试 `129 passed`。冻结 1,169 节点和登记 25 组选集 228 节点均 `problems=0 improvements=0`。复用紧邻提交的清洁全量 `10,650 passed, 4 failed, 2 skipped, 2 xfailed`，不重复长测；本维护提交没有单独全量结果。
- 环境 Python 3.12.2、pytest 9.1.1、SQLite 3.43.1，`app.__file__` 在 A worktree。原始输出为 `F:/paralls-verification/thread-a/m5-5-primitive-registry-focused-f584e2521bbd40209ee6f0ae4c6d0431/pytest.log` 与 `m5-5-primitive-registry-gates-bb88817fca714eb29b09c96e134a253d/gate-run.log`。
### H-A-048 | primitive_count_exceeded 结构性保证 | 2026-11-25

- M5-5 回归测试提交 1fb14ba45df0ebd3f9ff9448de9d754b40122c40 固定 REGISTERED_FACT_TYPE_PRIMITIVES 恰为六项。结合包不能定义原语且运行态 registry 不可变，primitive_count_exceeded 由结构性约束覆盖；它不是可由包输入触发的动态拒绝路径。
- 定向 FactType/RulePack Validator 111 passed, 2 warnings。冻结五组选集 1,169 节点与全部登记 25 组选集 229 节点，各组均 problems=0 improvements=0。M5-5 自有选择集为 8 个节点。原始 gate 日志在 F:/paralls-verification/thread-a/m5-5-primitive-count-gates-74182d4414634f6cb3dc6e0020cba46e/gate-run.log。
- 当前提交只新增测试。未在 1fb14ba4 重跑全量；最近前序全量仍为 10,650 passed, 4 failed, 2 skipped, 2 xfailed、退出 1，不视作当前提交全量验证。Python 3.12.2、pytest 9.1.1、SQLite 3.43.1；app.__file__ 指向 A worktree。
- 验证命令的三组 pytest 临时目录共 2,105,631 bytes，已移至上述 F 盘 pytest-temp/。D 盘只保留 pytest 管理的空目录及指向 F 盘副本的链接。本条对应的证据和选择集更新在 M5-5 evidence 与 m5-5-facttype-refold.json。

### H-A-049 | FactType ID naming limits and full-suite parent comparison | 2026-11-25

- Commit `3a0e35b6bf9d02ce7f34e3a9e43010946c49005f` enforces the formal FactType domain, name, and total-ID length constraints in `fact_type_registry.py`. Six malformed identifier regressions were added. Focused Validator tests: `117 passed, 2 warnings`. Frozen selections: 1,169 nodes. Registered selections: 25 manifests, 235 nodes. All selection comparisons returned `problems=0 improvements=0`.
- Exact-commit backend suite: `10,637 passed, 24 failed, 2 skipped, 2 xfailed`, exit 1. Parent `aa1f2507`: `10,631 passed, 24 failed, 2 skipped, 2 xfailed`, exit 1. Twenty-three failures matched by node, phase, and error data. The sole swapped failures were `test_recovery_owner_probe_measures_original_startup_before_full_oracle` on the current full run and `test_original_owner_outbox_recovers_after_hard_kill[domain]` on the parent full run; both tests passed when rerun alone at both commits. No persistent new failure was observed, and neither full-suite run is green.
- Runtime checks used Python 3.12.2, pytest 9.1.1, SQLite 3.43.1, and worktree-local `PYTHONPATH`; `app.__file__` resolved inside each A verification worktree. Raw logs and result manifests are referenced in `docs/verification/m5-5-facttype-refold-20261125.md` and retained under `F:/paralls-verification/thread-a/`.
- Remaining M5-5 gap: formal examples use schema references such as `pool@v1` and `machine@v1`, while the runtime registry is keyed by event type and version and the existing Credential pack uses a legacy symbolic reference. The validator has no registered `event_schema_ref` namespace or explicit alias-to-registration contract. Do not infer a mapping from primitive names or event types; resolve this as a separate schema-registry unit. This does not block independent M5-5 work.

### H-A-050 | FactType `process_kind` registration rejection | 2026-11-25

- Commit `d02e8c736a9b9f9e36e661d65f96f046fe89371f` adds `facttype_process_kind_invalid` when a non-Process FactType declares `process_kind`. A TDD regression first failed because the pack loaded without rejection. Focused FactType/Validator tests: `118 passed, 2 warnings`; frozen selections: 1,169 nodes; registered selections: 25 manifests, 236 nodes; all selections returned zero problems and improvements.
- Exact backend full suite: `10,639 passed, 23 failed, 2 skipped, 2 xfailed`, exit 1. Against parent `3a0e35b6`, all 23 failures match by node, phase and error data. The parent's one additional intermittent failure passed at the current commit. The new regression passed in the full suite. Full result remains non-green.
- Environment: Python 3.12.2, pytest 9.1.1, SQLite 3.43.1, with `app.__file__` in the A worktree. Detailed results and F-drive raw outputs are in `docs/verification/m5-5-facttype-refold-20261125.md`.
- This is a Validator rule only. It does not implement Process primitive runtime, `event_schema_ref` resolution, or broader M5/Architecture v2 requirements.

### H-A-051 | Owner-ordered FactType resolution follow-up | 2026-11-25

- Commit `64421f00a6049a4598d642a1a0736dd409db7cf9` changes topological ready-node ordering to `(owner_ref, fact_type_id)`, matching the formal resolution-order contract. Corrected regression coverage distinguishes Owner ordering from FactType ID ordering.
- Focused FactType, Validator and Information-reader tests: `136 passed, 6 warnings`. Registered selections: 25 manifests, 237 nodes, zero problems/improvements. Frozen ownership, modifier, equipment and inventory selections: 179 nodes, zero differences.
- Frozen shared-replay remains incomplete after 400 batch nodes and five isolated nodes returned zero differences. The sixth isolated websocket-session probe exceeded 12 minutes without a result and was interrupted. Full backend suite was interrupted around 31% after 53 minutes with no final summary, JUnit or exit code. Neither run is a pass.
- Detailed evidence and raw-output paths are in `docs/verification/m5-5-facttype-refold-20261125.md`; the M5-5 selection manifest points at the exact commit. Python 3.12.2 and SQLite 3.43.1 were used, with `app.__file__` in the A worktree. Only this run's two pytest temporary directories were moved from D to `F:/paralls-verification/thread-a/pytest-temp-recovery-20261125-01/`.
- M5-5 remains in progress. This change does not implement Process support, `event_schema_ref` resolution, remaining package lifecycle requirements, or Architecture v2 completion.

### H-A-052 | Exact M5-5 selection rerun | 2026-11-25

- Re-ran the 16-node M5-5 selection at implementation commit `64421f00a6049a4598d642a1a0736dd409db7cf9` after recording the unit evidence. Result: `selected=16 problems=0 improvements=0`. The import check resolved `app.__file__` to the A worktree backend. Raw output is under `F:/paralls-verification/thread-a/m5-5-owner-order-exact-selection-20261125-01/`.

### H-A-053 | Local M6-5 Gate profile configured run | 2026-11-25

- Per the project lead's accepted recommendation, the A worktree root `.env` now configures `gate-03` with three 0–100 durability layers, initial values 100, integrity breach enter/reset thresholds 40/45, and battering-ram impact delta -20. The file is Git-ignored and was not committed or distributed as a production deployment configuration.
- With Python 3.12.2 and `app.__file__` in the A worktree, the configured smoke processed 14 signed and revision-pinned Gate impacts, emitted one breach-enter event at integrity 20, depleted door and latch durability, and emitted no Place facts. This preserves the separate Presence decision path.
- Focused tests: `184 passed, 6 warnings`. Exact M6-5 selection: `selected=21 problems=0 improvements=0`. Full backend suite, shared-replay, production deployment and real Unreal transport were not rerun. Raw evidence paths are recorded in `docs/verification/m6-5-impact-gate-layered-execution-20261124.md`.

### H-A-054 | M5-5 Resolver rejection regression coverage | 2026-11-25

- Test-only commit `964cc5e4f3d58093deae61ab9de7993da1c61f50` adds witnesses for `resolver_writes_undeclared` when a layer output is absent from the model write set, and `resolver_missing_determinism` when randomness is not fixed to `none`.
- Focused FactType registry/rejection tests: `12 passed, 2 warnings`. Exact M5-5 selection: `selected=18 problems=0 improvements=0`. The `m5-5-facttype-refold.json` manifest records the two nodes at the exact commit.
- No runtime behavior changed. Full backend suite and shared-replay were not run for this test-only commit. Evidence is in `docs/verification/m5-5-facttype-refold-20261125.md`.


### H-A-055 | M6-5 configured Gate→Presence runtime closure | 2026-11-25

- 使用 A worktree 本地 `.env` 的 `gate-03` profile，Python 3.12.2 / SQLite 3.43.1 / A worktree `app.__file__`。14 次独立签名 Gate impacts 产生一个 breach-enter；随后对 impact 14 提交独立签名 Presence assessment。实际输出为 integrity `20`、Place commit `1`、passability `passable`、`impact_gate` obligation `settled`。损伤未回滚。
- 原始输出 `F:/paralls-verification/thread-a/m6-5-gate-presence-obligation-20261125-01/runtime.log`。这补齐本地 Gate→Presence→obligation 运行链，不构成生产部署、UE 实机传输或完整 siege playthrough 证据；M6-5 仍进行中。

### H-A-056 | M1-2 Holdings additive event contract ruling | 2026-11-25

- 为解除 H-A-006 中缺少 release/settlement 与 reservation-transfer 关联的机制阻塞，本轮按项目负责人此前授予的“线 A 全权授权”采用最小追加合同，不修改 Architecture v2 文档仓库。
- v1 正式事件 `lot_created`、`reserved`、`transferred`、`consumed`、`split`、`merged`、`lost` 保留类型名与既有字段。Projector 读取正式 v1 字段；`lot_created.quality` 可选但仅校验格式，质量仍由 Pool 管理。
- 为使 H2 可验证，新增首版事件 `reservation_released`、`reservation_settled`、`reservation_transferred`。后者将活动 reservation_ref 从源 lot 移至目标 lot，并与转移一同提交；新事件不改变既有 v1 事件语义。
- 投影定义 `lot.quantity` 为未预留可用量，reservation 单列；`total_quantity = available + reserved`。当前 transfer 是同一 FactType stream 内即时转移，`in_transit` 固定为零且不声称覆盖异步运输。capacity 按该 FactType stream 的可用量与预留量总和校验。拆分/合并要求没有活动 reservation；合并要求单位、规格兼容且容器一致。
- 在代码、测试、脚本中枚举 `gameplay.holdings.*` 的读取方，只有本轮 Holdings runtime/schema 与对应测试；未发现既有生产消费者或历史 Holdings 写入方。正式 v1 payload 的投影重建由 `test_formal_v1_holdings_events_rebuild_with_quality_kept_out_of_quantity` 验证。
- 当前定向验证已通过 58 项相关测试与 14 项 FactType/Validator 测试。M1-2 仍未完成： checkpoint 恢复、完整聚合/Resolver、完整 R1/R2/R3、U1–U11、冻结选集、所有登记选集及全量验证待完成。不得据此宣称 Holdings 或 v2 已完成。

### H-A-057 | M1-2 checkpoint 回放增量与验证状态 | 2026-11-25

- `HoldingsProjector.rebuild` 增加 `checkpoint_at`，按既有 `OwnershipProjector` 的全局序号边界合同先重建前缀，再从投影状态继续回放后缀。投影保留关闭 lot 引用，避免 checkpoint 后丢失 split/merge 生命周期状态。新增 checkpoint 后缀等价、关闭 lot 保留和负边界拒绝测试。
- `HoldingsProjection.sum_by_item` 汇总多 lot 的 available/reserved/total quantity，并附带 item definition 的 unit/spec，保持不同物料各自聚合。依据正式聚合规格，这是 `sum` 型守恒总量，**不是**不守恒的 `distribution` refold。固定向量覆盖同物料多 lot 与不同 unit/spec 的隔离。
- 当前 Holdings 与 FactType 定向测试为 22 passed、2 warnings，Python 3.12.2 / SQLite 3.43.1，`app.__file__` 位于 A worktree。完整命令和逐项证据见 `docs/verification/m1-2-holdings-runtime-20261125.md`。
- 新增 22 节点选集 `docs/verification/selection/m1-2-holdings.json` 并对当前工作区运行冻结比较器，原始结果 `selected=22 problems=0 improvements=0`。
- 19 个非 shared-replay 登记选择集共 304 项通过。shared-replay 前 10 批共 400 项通过，第 11 批停在既有 `test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage]`，没有最终结果或退出码；该测试单独复跑也停在该用例后被本线程中断。完整 shared-replay 选择集和全量未验证。
- 此实现是事件流边界的 checkpoint 重建，不定义或存储持久化快照格式。Resolver 消费接线及 U1–U11 证据仍待核对，M1-2 继续进行中。

### H-A-058 | M1-2 shared-replay 验证恢复 | 2026-11-25

- 更正 H-A-057 的 shared-replay 未完成状态：在同一未提交工作区重新运行 frozen ownership/modifier/equipment/inventory、M1-2 Holdings 和 shared-replay selections，共 1,191 节点，均 `problems=0 improvements=0`。完整 990 节点 shared-replay 本次通过。
- Windows PowerShell 空闲端口 listener 查询在该环境下未返回。验证目录内临时 shim 仅响应 `Get-NetTCPConnection -LocalPort 8000 -State Listen` 并报告当时已由 `netstat -ano -p tcp` 确认的空闲状态；没有修改仓库 Harness 或测试代码。此前一次 full selection 运行中本线程自己的临时 backend 占用了端口并导致两节点失败，停止后单测复跑 2 passed，随后完整选择集通过。
- 全量 backend suite 未运行。生产 Resolver 消费、持久化 checkpoint 编码及 U1–U11 其余未完成项仍未完成，M1-2 继续进行中。

### H-A-059 | M1-2 FactType/规则包增补与 G5 阻塞 | 2026-11-25

- 在 A worktree 9f565d69c446ba11a752cdce6c7964d0eda6b775 的未提交工作区中，rule_pack_validator.py 改为读取 REGISTERED_FACT_TYPE_PRIMITIVES，避免新 primitive 只被 FactType 编译器接受、却被规则包入口拒绝。新增 holdings 规则包加载测试，并将 M1-2 登记选集从 22 项扩至 24 项。
- 复核发现原有缺失事件重试测试假设 replay_duplicate 会读取每个 committed_event_id 对应事件。实际共享 helper 只读取幂等记录和持久化 receipt，未调用 get_event。测试改为验证 helper 已声明的“幂等记录存在但结果 receipt 缺失”拒绝路径，未更改生产重试行为。
- 定向测试 24 passed、2 warnings，原始日志 F:/paralls-verification/thread-a/m1-2-holdings-final-20261125-04/pytest.log。M1-2 选集 selected=24 problems=0 improvements=0，M5-5 FactType 选集 selected=18 problems=0 improvements=0。
- G5 首次尝试在 frozen shared-replay 第 11 批停于 test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage]。此前四组选集 equipment 87、inventory 56、modifier 12、ownership 24 均零差异，shared-replay 批次 0–9 共 400 项完成且通过。第 11 批无最终结果文件，日志显示该节点之前 5 项通过后停住。
- 第二次在临时目录 F:/paralls-verification/thread-a/m1-2-holdings-gates-20261125-02/ 重跑，使用只响应 8000 端口查询的 powershell.cmd 后仍停在同一节点。直接运行 powershell.exe -NoProfile -NonInteractive 查询命令 10 秒无输出后中断。紧邻重跑前 netstat -ano -p tcp 没有 LISTEN 记录。shim 无法替代 Python subprocess 启动的 PowerShell 进程。没有修改 Harness 源码，没有终止其他进程。
- G5 冻结五组选集共 1,169 节点未完成，26 组已登记选择集未启动，全量 backend suite 未运行。完整记录在 docs/verification/m1-2-holdings-runtime-20261125.md。连续两次门禁运行停在同一环境检查，M1-2 依 AUTONOMY §二转为阻塞。
- 正式 Owner 定义表将 Inventory/Resource 列为 stewarded。代码中尚无 Inventory Owner 声明或 Resolver 消费者。M1-2 的 Owner 声明、Resolver 消费接线、读取主体分类与其余 U1–U11 状态未改变。

### H-A-060 | M1-2 G5 冻结选集恢复 | 2026-11-25

- 更正 H-A-059 的 G5 阻塞：在未提交 M1-2 工作区重新运行 ownership 24、inventory 56、equipment 87、modifier 12 与 shared-replay 990 节点，全部 `problems=0 improvements=0`。shared-replay 的第 11 批（包含此前卡住的 `test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage]`）40 项通过。
- 原因是 PowerShell 子进程在此环境中连最小退出命令也不返回。运行前由 `netstat -ano -p tcp` 确认 8000 没有 listener，运行后也没有 listener。本轮临时将 Python 3.12.2 可执行文件放在 F 盘验证目录并命名为 `powershell.exe`，使该空闲端口查询返回空 stdout。这个替身没有验证“端口已被其他进程占用”时的读取路径；未修改仓库测试或 Harness 源码，也未终止其他进程。准确命令摘要与原始 batch 输出位于 `F:/paralls-verification/thread-a/m1-2-holdings-g5-resume-20261125-03/`。
- M1-2 的 G5 冻结选集门禁已恢复，账本回到 `进行中`。26 组登记选择集、全量 backend suite、Inventory Owner 声明、生产 Resolver 消费与 U1–U11 其余证据仍未完成。

### H-A-061 | M1-2 Inventory 生产接线共同边界 | 2026-11-25

- 正式承接映射要求 `inventory_runtime.py` 保留为 Inventory Owner 领域规则层，其 FactType 声明指向 Holdings 与 Pool。当前旧 Inventory 命令消费仍直接调用该 runtime；A 侧 Holdings 原语虽能独立写入/重建，尚未接管该生产调用链。
- `docs/v2-coordination/BOUNDARIES.md` 将 `inventory_runtime.py` 列为 A/B 共同边界，禁止线程 A 单方面修改。将旧命令切换到 Holdings/Pool 会改变该边界文件及相关生产消费者，不能以新增并行 Inventory writer 代替，因为那会留下两套数量事实源。
- M1-2 已完成原语和 G5 冻结选择集验证，生产迁移暂标阻塞。后续需由共同边界负责人决定接线归属与调用面，再完成 Owner 声明、Resolver 消费及完整 U1–U11 证据。未修改 `inventory_runtime.py`、外部文档仓库或 `integration`。

### H-A-062 | M5-5 event_schema_ref 注册解析增量 | 2026-11-25

- 当前未提交工作区实现了显式 `event_schema_ref` 的生产注册解析。支持 `pool@v1`、`gameplay.pool@1`、`holdings@v1`、`gameplay.holdings@1`、`machine@v1`、Information 报告与 reaction 两个事件引用，并保留 `credential_link_legacy_v1` 历史兼容符号。未注册引用由 RulePack Validator 返回 `facttype_schema_unknown`。
- Holdings 规则包已加入 `holdings@v1` 引用，新增未知 schema 拒绝和注册加载回归。定向 Validator/Information/Holdings 测试 `130 passed, 6 warnings`。M5-5 18 节点和 M1-2 24 节点选集，以及 ownership 24、modifier 12、equipment 87、inventory 56 冻结选集均 `problems=0 improvements=0`。
- shared-replay 在 websocket-session 批次的 backend 启动路径停住，没有最终结果文件，不能记为通过。全量 backend suite 未运行。验证原始输出位于 `F:/paralls-verification/thread-a/m5-5-event-schema-ref-20261125-02/`。
- 本增量不改变持久事件 payload，不移除 Credential 历史符号，也不接管 `inventory_runtime.py`。M1-2 生产迁移仍受 H-A-061 的共同边界阻塞。生产 Gate 数值仍未配置到生产环境，本地 `.env` 仅为 A worktree 演示配置。

### H-A-063 | M5-5 event_schema_ref follow-up verification | 2026-11-25

- 提交 `76a2c155` 记录了 `16ad9b9c` 的独立回归验证，未混入 M1-2 工作区文件。Validator、Information production wiring、Holdings FactType registry 和 Credential schema compatibility 定向测试为 `138 passed, 6 warnings`。
- 原始输出位于 `F:/paralls-verification/thread-a/m5-5-event-schema-ref-20261125-03/pytest.log`，证据文件为 `docs/verification/m5-5-event-schema-ref-followup-20261125.md`。本轮未运行全量 backend suite，也未重跑冻结选择集。
- M5-5 仍有 package lifecycle、生产注册和 M5-3/M5-4 未完成项。M1-2 仍因共同 `inventory_runtime.py` 边界阻塞。生产 Gate 数值仍未配置，不能将本地 `.env` 视为生产部署。
### H-A-064 | M5-5 verification resume at `e1de1090` | 2026-11-25

- Revalidated the committed `event_schema_ref` increment at exact A tip `e1de1090f3070b3dcdb073e86423ae0af00bc3a7`. Focused RulePack Validator, Information production, Holdings registry, and Credential schema tests: `138 passed, 6 warnings`.
- Frozen M5-5 18, ownership 24, modifier 12, equipment 87 and inventory 56 selections, plus registered M1-2 Holdings 24 selection, each returned `problems=0 improvements=0`.
- Frozen shared-replay did not complete. Batches 0–9 passed. Batch 10 reached collection/environment metadata but produced no test log or results because the pre-test backend listener check stalled at PowerShell `Get-NetTCPConnection`. A direct listener query also failed to return. The runner was interrupted, with no unrelated process terminated. This is incomplete evidence, not a pass.
- Environment recorded Python 3.12.2, pytest 9.1.1, A worktree `PYTHONPATH`, backend as pytest rootdir, and no source/worktree changes. Earlier A evidence records SQLite 3.43.1; it was not independently queried during this rerun. `TEMP/TMP` resolved under D, so pytest temporary data from this run may remain in the shared D temp root. No move was attempted because that root contains concurrent processes' data. Raw retained outputs: `F:/paralls-verification/thread-a/m5-5-resume-20261125-01/`.
- M5-5 remains in progress. Full suite was not run. Remaining items include `temporal_effects`, production command registration, package-version write boundary and M5-3/M5-4. M1-2 production consumption remains blocked by the shared `inventory_runtime.py` boundary. Detailed results are recorded in `docs/verification/m5-5-facttype-refold-20261125.md`.
- Formal-source audit of `temporal_effects`: the migration plan requires validation and rejection codes, while the package format only names a directory and two example IDs (`bleeding`, `burning`). The formal validator catalog contains no temporal-effect schema or diagnostics. No implementation or consumer was found under A `backend/app`, tests, or packs. Required input is the item field schema, reference namespace, validity rules, rejection codes, and intended consumer. Do not infer these from the non-normative combat analysis document. The precise gap is in the M5-5 verification evidence.

### H-A-065 | M5-5 shared-replay selection recovery | 2026-11-25

- Re-ran the frozen shared-replay selection using the existing F-drive Python executable as a temporary `powershell.exe` name mapping for the harness listener query. `netstat -ano -p tcp` showed no LISTENING socket on port 8000 immediately before the run. The selection manifest contains no other tests that invoke PowerShell.
- `TEMP`, `TMP`, `PYTEST_ADDOPTS=--basetemp=...`, `PYTHONPATH`, and `PATH` were set for this process only. Pytest temp data and raw outputs were directed to `F:/paralls-verification/thread-a/m5-5-resume-20261125-01/`.
- Result: `selected=990 problems=0 improvements=0`, all 25 serial batches completed. This supersedes the incomplete shared-replay attempt recorded under H-A-064. It does not establish full backend suite success.
- The shim only maps the exact runner-side listener query to an empty output after the independent port check; no repository Harness code or user process was changed or terminated.
- Correction: pytest's option parser treated backslashes in `PYTEST_ADDOPTS=--basetemp=F:\...` as escapes and created `backend/paralls-verificationthread-am5-5-resume-20261125-01pytest-temp-shared/`. Confirmed 119 entries (12,606,316 bytes), this exact run-owned folder was relocated to `F:/paralls-verification/thread-a/m5-5-resume-20261125-01/pytest-temp-shared-recovered/`; `backend/` no longer contains it. Pytest `current` convenience symlinks may retain the original absolute targets. Use forward slashes in this option. `TEMP`/`TMP` were already set to F; the misparsed option overrode them for pytest's base temp.

### H-A-066 | M5-5 Resolver determinism policy | 2026-11-25

- Commit `14f4fbd70579ab902665faefcdde417638c242d3` aligns FactType registry validation with the Resolver contract. It accepts `float64` and seeded randomness only with `world_tick` or `command_id`; missing or unsupported seed sources remain rejected.
- The focused Validator, Information, Holdings and Credential/Resolver tests returned `150 passed, 6 warnings`. The M5-5 22-node selection, M1-2 Holdings 24-node selection and frozen ownership/modifier/equipment/inventory selections (24/12/87/56) returned zero problems and improvements.
- Python 3.12.2 and pytest 9.1.1 were used. `app.__file__` resolved inside the A worktree. Pytest temporary paths and retained output were directed to the unique F-drive run directory. The interpreter itself remains at its existing D-drive location. SQLite was not queried independently. Full backend suite and shared-replay were not rerun for this increment; the latest shared-replay result remains H-A-065.
- M5-5 remains in progress. `temporal_effects`, production command registration, package-version write boundary and M5-3 remain open. M5-4's loader-level runtime guard is implemented and tested, while production load wiring remains absent. Production Gate values remain unconfigured; the ignored A worktree `.env` is only a local demo profile. Evidence is in `docs/verification/m5-5-facttype-refold-20261125.md` and raw output is under `F:/paralls-verification/thread-a/m5-5-resolver-policy-20261125-02/`.

### H-A-067 | M5-3 package migration ownership and replay boundary | 2026-11-25

- The formal migration event specifies `from`, `to`, `migration_ref`, and `affected_fact_types`, with replay using the old package before the event and the new package after it. The codebase has no `pack.migrated` producer or consumer, and application code has no production call to `load_pack`.
- `LoadedPack` retains package/version/hash pins and the loader resolves explicit parent paths. The production package-version archive and event-stream initial package pin are not implemented. The migration event changes replay interpretation, so its authority needs a defined owner.
- The registered gameplay Owner list contains no RuleSet/Package Owner. Per the A boundary rule, A will not add an Owner or assign this event to an existing domain without classification. Recommended handling is an L4 platform control-plane lifecycle event, outside gameplay FactTypes, with an explicit platform migration authority and replay pin resolver. Awaiting project lead decision. M5-3 remains blocked.
- M5-4 is implemented at loader level. `running=True` returns `pack_runtime_reload_forbidden`, and a regression assertion exists in `test_rule_pack_validator.py`. No production code calls `load_pack`, so production lifecycle enforcement remains unverified.

### H-A-068 | M5-3 platform control event approval and implementation | 2026-11-26

- The project lead approved treating `pack.migrated` as an L4 platform control-plane lifecycle event, with no new gameplay Owner. This resolves the authority classification raised in H-A-067.
- A implemented the `pack.migrated@1` schema registration, immutable archive lookup requiring trusted content-hash pins, one-world migration authority, duplicate replay before active-source validation, zero-write source/revision/archive rejection, and replay by global sequence. The event stays outside gameplay FactType discovery and is written with `authority_only` visibility through the existing event store API.
- Tests cover normal and durable commits, duplicate retry after reopening, changed duplicate rejection, stale source pins, revision conflicts, missing archive identities, changed archive hashes, malformed history, and package resolution before/at/after the migration sequence.
- Implementation commit is `aa8711683068ae220c3602e89f3da0a871f7f284`. Final targeted results and the M5-3/Ownership/shared-replay selections (16/24/990 nodes) are recorded in `docs/verification/m5-3-package-migration-20261126.md`; raw output is under `F:\paralls-verification\thread-a\m5-3-package-migration-20261126-final\`.
- The production archive bootstrap must provide the trusted immutable hash manifest. No production v2 `load_pack` consumer exists, so production bootstrap and startup wiring remain deferred and are not claimed as verified. The backend full suite was not run for this unit.

### H-A-069 | M5-3 trusted archive bootstrap API | 2026-11-26

- Commit `2a5d66402aaf566bb8414ec61d51aa5cb5999b45` adds `load_package_archive`. Callers provide explicit `PackageRef` to directory mappings and a trusted `PackageRef` to content-hash mapping. The loader resolves parent directories, validates loaded identities, and `PackageArchive` rejects missing or mismatched pins.
- Focused package migration, schema, and rule-pack validator tests returned 148 passed. M5-3 selection (20 nodes) and Ownership (24 nodes) reported zero problems and improvements.
- The shared-replay selection did not complete. Ten 40-node batches passed, then the next batch stalled at `test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage]` without log progress for over ten minutes. The comparator was interrupted and produced no aggregate result. Cause remains unclassified. No unidentified process was terminated. The full backend suite was not run.
- This API does not parse or authenticate a deployment manifest and does not settle cross-language canonical serialization. The caller must supply trusted pins from a deployment-controlled source. No production v2 package consumer or startup wiring exists. Production Gate values remain unconfigured; `integration` was not modified.

### H-A-070 | M5-3 shared-replay verification resumed | 2026-11-26

- Revalidated current A code state `24b369c0`; the M5-3 runtime source is unchanged from `2a5d6640`. Frozen shared-replay completed with `selected=990 problems=0 improvements=0`, superseding the incomplete comparison in H-A-069.
- Root cause of the earlier stall was the runner's PowerShell `Get-NetTCPConnection` listener query hanging in `subprocess.communicate()`. A fresh `netstat -ano -p tcp` check showed port 8000 unbound before rerun. A temporary F-drive `powershell.exe` name shim was applied only to that lookup; no external process was stopped.
- Python `3.12.2`, SQLite `3.43.1`, A worktree import path verified. Raw output: `F:/paralls-verification/thread-a/m5-3-shared-replay-complete-20261126-01/shared-replay/`. Full backend suite remains unrun. Deployment manifest loading and package startup wiring remain open.

### H-A-071 | M6-5 tracked Gate profile template | 2026-11-26

- Commit `24b369c0` adds the exercised `gate-03` profile to tracked `.env.example`. Its JSON parsed through `FacilityGateProfileSettings`; focused config and M6-5 runtime tests returned 52 passed, 6 warnings.
- This provides version-controlled deployment input, not evidence that a production server has loaded it. No deployment target or server manifest exists in this repository. Raw output: `F:/paralls-verification/thread-a/m6-5-gate-profile-template-20261126-02/pytest.log`.

### H-A-072 | M6-5 versioned Gate profile input contract | 2026-11-26

- Commit `d693686b` adds a schema-versioned `FacilityGateProfileSettings` contract. Missing version remains compatible as v1; unsupported versions, unknown fields, non-finite or float/bool decimal inputs, invalid thresholds, non-negative impact deltas, and invalid layered bounds reject.
- The tracked `.env.example` values are marked demonstration-only. Production Gate values remain unset per H-A-039; no deployment target, production config, or `integration` change was made.
- Python `3.12.2`, SQLite `3.43.1`, the A worktree `app.__file__`, and F-drive temp paths were verified. Focused tests returned `71 passed, 6 warnings`; the registered profile contract selection returned `selected=19 problems=0 improvements=0`. P-1 staged-line credential-pattern scan reported zero hits.
- The backend full-suite attempt reached approximately 31% after about 40 minutes and was interrupted. A `pytest -x` probe identified the first failure as `test_all_22_repaired_budgets_equal_fixed_official_usage`, caused by missing `tokenizers`; the same node failed identically at parent `6d31a831`, confirming it as a baseline environment failure. The second marker from the interrupted run remains unclassified. Raw output is under `F:/paralls-verification/thread-a/m6-5-gate-profile-contract-full-20261126-01/`, `F:/paralls-verification/thread-a/m6-5-profile-first-failure-20261126-01/`, and `F:/paralls-verification/thread-a/m6-5-profile-parent-failure-20261126-01/`; focused evidence is `docs/verification/m6-5-gate-profile-contract-20261126.md`.

### H-A-073 | M6-5 interrupted full-suite failures classified; M5-3 production inputs | 2026-11-26

- The second visible failure in the interrupted M6-5 full suite was node 2308, `test_task45_headless_probe_observes_shared_path_and_contact_contract`. It failed at current `cdf99158` and parent `6d31a831` with matching Godot 4.6.3 `CharacterMotor` parse errors and downstream type-inference errors. Both visible suite failures are now reproduced at the parent. The suite remains incomplete and is not a pass. Evidence and exact outputs are recorded in `docs/verification/m6-5-gate-profile-contract-20261126.md` and `F:/paralls-verification/thread-a/m6-5-full-failure-triage-20261126-01/`.
- M5-3 code has the platform control event and trusted archive API, and frozen shared-replay is verified at 990 nodes. Production manifest loading and startup consumption still lack an upstream contract. Before production wiring can be verified, the deployment/release owner must identify the trusted manifest source and authentication boundary, initial package identities per world/runtime, and the consumer entry point that binds loaded package registries to domain commands and resolvers. Cross-language package hash canonicalization also needs a platform-wide algorithm decision because `load_pack` currently hashes parsed YAML structures with Python `json.dumps`. The formal migration plan specifies the migration event fields and old/new historical interpretation, but does not specify these deployment contracts. No manifest format or production trust source has been invented in this unit.
- Production Gate values remain unconfigured under H-A-039. The tracked `.env.example` profile is for demonstration only.

### H-A-074 | M1-3 Pool production scheduling and M2-1 read-path refresh | 2026-11-26

- Static search at A branch tip `3aa0ea31` found the `PoolAuthorityService.integrate` definition but no production call site. The only pack-authored Pool definitions are the three `county_siege_facility/pool_defs/*.yaml` entries, all declare `integration: {mode: "none"}`. Runtime M6-5 morale, Facility, and Presence Pool definitions also use the default zero rate. `_validate_pool_definition` constructs a validated `PoolDefinition` but the current production package startup does not load pool definitions into a scheduler registry.
- Therefore the current code has no domain Pool for which a production integration tick may be scheduled. Adding a cadence callback now would emit no-op persisted adjustment events or require inventing a domain rate, both contrary to the package declarations and migration scope. The missing prerequisite is a production package consumer that supplies active, version-pinned Pool definitions and a domain-authored non-zero rate where time integration is intended. After that contract exists, A can wire confirmed world windows and lifecycle cut boundaries. No changes were made to `main.py`, runtime files, persisted events, or integration.
- Updated M1-3 status remains `待门禁`; its previous test evidence is unchanged and does not cover production scheduling. No tests ran for this static audit.
- M2-1 now includes the M6-5 Information, Morale, and Presence read paths at `3aa0ea31`. They are classified as trusted authority/recovery or test-only queries. The Morale projection and Presence state methods have no backend/app call sites; current matches are tests. No production subject-facing reader was found for these outputs, so M2-2 `read_as` remains a separate unresolved prerequisite.
- Evidence: `docs/verification/m1-3-pool-spec-audit-20261124.md`, `docs/verification/m1-3-pool-runtime-20261122.md`, `docs/verification/g2-visibility-budget/m2-1-ownership-credential-read-paths-20261122.md`, source searches in `pool_runtime.py`, `rule_pack_validator.py`, `main.py`, and `packs/county_siege_facility/pool_defs/`.

### H-A-075 | M5-3 production package consumer world scope audit | 2026-11-26

- Source evidence at A tip `514da66f`: `main.py:1970` constructs one global `M6_5SiegeRuntime` using the shared `gameplay_event_store`, without a `world_ref`. `m6_5_siege_runtime.py:309,318` directly calls `load_pack` for the Morale/Presence and Information directories. A source search found no production call to `load_package_archive` or `PackageMigrationAuthority`; migration API calls are currently in tests.
- The approved M5-3 authority is world-scoped (`platform:rule-packs:<world_ref>`), and historical resolution requires that world's initial package refs. The scenario identifier `county_siege_day_03` in the play-pattern documents is a `world_mode_ref`, not evidence of a `world_ref`. Wiring the singleton consumer to one migration stream would misapply package versions to other worlds if they share this store/dispatcher.
- Production wiring therefore needs the platform/runtime contract that binds dispatched gameplay events to a `world_ref`, plus the trusted initial package refs and hashes for that world. The current M6-5 event consumer does not expose that context. Do not infer it from the scenario name or silently use an empty package set. No production code or persisted event was changed in this audit.
- The focused M5-3 tests on this tip returned `32 passed, 2 warnings`; frozen Ownership returned `selected=24 problems=0 improvements=0`. The current shared-replay rerun stopped at the known PowerShell listener lookup stall before aggregate output. H-A-070's `selected=990 problems=0 improvements=0` remains evidence for code state `24b369c0`, not for this exact tip. Full backend suite not run. Current-turn logs are under `F:/paralls-verification/thread-a/m5-3-current-20261126-02/`.
- Formal M5-3 plan requires the migration event and old/new package replay interpretation but does not define the deployment manifest or world-routing contract. M5-5 `temporal_effects` likewise remains underspecified in the formal rule-pack file format, which gives only the directory and example IDs.

### H-A-076 | M5-3 world-pinned M6-5 package consumer mechanism | 2026-11-26
- 提交：`29492189`。
- `build_m6_5_siege_runtime` now accepts a `PackageArchive` plus explicit `PackageRef` entries for the Morale/Presence and Information packages. When supplied, both packages are resolved from the same immutable archive. A missing archive/ref pair or either required pin raises an explicit configuration error before the gateway is built.
- Tests use the real package directories to build an archive with trusted content hashes, then monkeypatch the legacy `load_pack` path to prove the factory consumes the archive. The incomplete configuration path is also covered. Combined migration/schema/M6-5 targeted result: `66 passed, 6 warnings`.
- This is a consumer mechanism, not a deployment claim. `main.py` still needs a deployment-provided single-world `world_ref`, initial package refs, archive directory mapping, and trusted hash manifest before startup can call this path. No `integration` change was made.
- Exact-tip frozen comparisons: M5-3 registered selection `selected=22 problems=0 improvements=0`; Ownership `selected=24 problems=0 improvements=0`. Shared-replay 990 produced no output for about three minutes and was interrupted at the known PowerShell listener lookup stall. It is incomplete evidence for this commit, not a pass. No external process was stopped.

### H-A-077 | M5-3 deployment contract and startup archive wiring | 2026-11-26
- A added an optional `RulePackDeploymentSettings` contract driven by `SIEGE_RULE_PACK_WORLD_REF`, `SIEGE_RULE_PACK_INITIAL_REFS_JSON`, `SIEGE_RULE_PACK_ARCHIVE_DIRECTORIES_JSON`, and `SIEGE_RULE_PACK_TRUSTED_HASHES_JSON`. All four inputs are required together. When absent, the existing local `load_pack` compatibility path remains active. Partial or mismatched manifests fail before the M6-5 gateway is built.
- `load_deployment_package_archive` parses canonical `pack_id@pack_version` keys, resolves relative directories under the repository root, and delegates content validation to the existing trusted hash bootstrap. The M6-5 startup path now passes the loaded immutable archive, the `morale_presence` and `information` refs, and the configured single-world `world_ref` to the consumer.
- Exact-tip targeted tests returned `58 passed, 6 warnings`, including both real county siege package directories, complete manifest loading, partial manifest rejection, and the world-pinned runtime field. `git diff --check` and Python 3.12.2 compile checks passed. No production server, deployment manifest, trusted external manifest source, cross-language hash canonicalization, or UE transport was available, so those remain unverified. `integration` was not modified.

### H-A-078 | M5-3 startup contract exact-tip verification | 2026-11-26
- At exact tip `45480fb2`, the targeted package/schema/M6-5 command returned `71 passed, 6 warnings`. M5-3 registration selection returned `selected=22 problems=0 improvements=0`; Ownership returned `selected=24 problems=0 improvements=0`.
- Frozen shared-replay 990 was started at the same tip. Batches 0000-0009 completed, then batch 0010 stopped at the known PowerShell listener lookup stall. The runner was interrupted after about four minutes without aggregate output. It is not a pass. Raw output is under `F:/paralls-verification/thread-a/m5-3-startup-contract-20261126-01/`.
- Evidence is `docs/verification/m5-3-startup-contract-20261126.md`. No external process was stopped. Production manifest source, Gate values, full backend regression, production server startup, cross-language hash canonicalization, and UE transport remain unverified.

### H-A-079 | M5-5 temporal_effects formal contract audit | 2026-11-26
- The external Architecture v2 sources specify `temporal_effect` as `primitive: process` with `process_kind: temporal`, and the temporal-process abstract fields `tick_policy`, `next_tick`, `exit_condition`, plus idempotency `process_id + scheduled_world_tick`.
- The formal rule-pack format only declares the `temporal_effects/` directory and example IDs `bleeding` and `burning`. It does not define entry fields, reference namespaces, validation/rejection codes, a production scheduler/consumer, or package-version and persistence boundaries. A-tip code and pack search found no temporal-effect entries or consumer.
- Evidence: `docs/verification/m5-5-temporal-effects-contract-audit-20261126.md`. This is static-only. M5-5 remains blocked on the formal input contract, and no temporal-effect code or package content was added.

### H-A-080 | M5-3 shared-replay current-tip attempt | 2026-11-26
- At `bd02be3cbf3949742113c2e79d5216a7c23c20d1`, the frozen 990-node shared-replay runner completed batches 0000-0009 (400 nodes) and logged five passing tests in batch 0010 before pausing at `test_embodied_interaction_session_runner.py::test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage]`.
- The current runner was interrupted after no progress; it produced no aggregate `selected/problems/improvements` result. This is incomplete, not a pass. Raw output and exact environment are recorded in `docs/verification/m5-3-shared-replay-current-tip-20261126.md` and `F:/paralls-verification/thread-a/m5-3-shared-replay-exact-tip-20261126-02/`.
- Python 3.12.2 and the A worktree `app.__file__` were verified. SQLite was 3.43.1. Port 8000 had no listener before or after the run. No external process was stopped.

### H-A-081 | M5-3 shared-replay listener inspection repair | 2026-11-26
- Commit `4d366b9e7e7c9d542f15b1dba0ad9c7ffeb96aea` replaces the unbounded PowerShell listener lookup with a bounded `netstat` TCP listener query. The exact-commit `test_harness_processes.py` run returned `15 passed in 4.59s`.
- At that commit the frozen shared-replay comparison returned `selected=990 problems=0 improvements=0`. The previously stalled batch-0010 WebSocket cases passed. Exact environment, commands, and raw-output paths are in `docs/verification/m5-3-shared-replay-netstat-20261126.md` and `F:/paralls-verification/thread-a/m5-3-shared-replay-netstat-20261126-01/`.
- Python 3.12.2, A worktree `app.__file__`, and SQLite 3.43.1 were verified. `head_after` matched the tested commit, source hashes were unchanged, and no external process was stopped. Full backend regression and production deployment were not run.

### H-A-082 | M6-5 production assembly static audit | 2026-11-26
- At A commit `195c2795`, static call-site inspection confirms `main.py` constructs the M6-5 runtime, registers all three trusted command outputs, and dispatches committed transactions to its L5 dispatcher. The runtime constructs Morale, Presence, and Information handlers, binds `facility_breach@1`, loads/resolves both rule packs, and recovers durable signed physical inputs.
- `impact_gate_obligations()` rebuilds a projection, but no production caller executes or settles the formal durable obligation lifecycle. Existing recovery reconciles physical inputs and Owner writes only. Thus the old board statement that main registration, domain handlers, pack/condition loading, and physical-input recovery were all unimplemented was stale; the durable obligation executor/restart recovery remains a real gap.
- Static-only evidence is `docs/verification/m6-5-production-assembly-audit-20261126.md`. No tests were run for this audit. Production Gate configuration, server deployment, UE transport, and a complete siege run remain unverified.
