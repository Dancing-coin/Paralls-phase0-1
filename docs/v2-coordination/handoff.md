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
- Detached exact-commit verification and the current-worktree full suite remain pending. No production Gate values, live Unreal transport, or fully configured siege run were supplied. The Presence receipt contract currently requires an integrity breach event, so a non-breaching hit has no valid Presence source and remains an open derived obligation. M6-5 remains in progress and has not entered integration.
