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

### H-A-083 | M2-2 `read_as` contract audit | 2026-11-26

- A branch `945953db` static audit confirms the gameplay `GameplayEvent` model has no persisted `event_time`; the event schema registry carries only event type, schema version, and digest; and the FactType registry currently maps event types to domains rather than v2 visibility declarations.
- No common gameplay `read_as` or principal-selector interpreter exists. `learnable_by` appears in rule-pack validation only for compatibility-preservation checks. A has statically enumerated Ownership/Credential `read_events()`/`read_stream()` call sites, but still needs to classify trusted Owner/recovery reads versus principal-facing reads before wiring.
- Implementing M2-2's required time semantics currently requires changing the persisted event/time contract in `models.py`/`event_store.py`, which the coordination boundary reserves for escalation. A will not substitute sequence, caller input, or payload conventions for authoritative world time.
- Required inputs are project-owner approval and cross-thread coordination for an additive, replay-compatible event-time source; a principal qualification source plus selector grammar; a production event-to-FactType/visibility mapping; and reader classification. Static evidence is `docs/verification/m2-2-read-as-contract-audit-20261126.md`. M2-2 remains blocked; no runtime code or event contract was changed.

### H-A-084 | M6-5 obligation audit correction | 2026-11-26

- Correction to H-A-082: startup does invoke `recover_physical_input_obligations()` in `main.py:2396`; the runtime replays persisted signed Gate/Presence inputs and Owner writes, and the existing durable-store restart test verifies idempotent recovery without repeated damage. It was inaccurate to say restart recovery was unimplemented.
- The actual gap is the formal L5 obligation lifecycle shape. `ImpactGateObligation` currently contains only ID, gate ref, open/settled status, and durable step receipt IDs. It has no pipeline ref, completed/pending steps, pending reason, responsible Owner refs, recovery action, or deadline tick. The runtime does not consume a compiled `Pipeline` for this flow.
- Reusing event-derived receipts and startup reconciliation remains the selected direction because the formal contract says Workflow state is rebuildable and is not a second domain fact ledger. The missing fields need a package/runtime contract, especially a source for deadline and failure classification. Do not invent production deadlines or treat the demo Gate profile as production values.
- Corrected static evidence is `docs/verification/m6-5-production-assembly-audit-20261126.md`. This correction did not rerun tests and does not claim M6-5 complete.

### H-A-085 | M6-5 obligation recovery exact-tip test | 2026-11-26

- At A tip `9b77738d`, Python 3.12.2, SQLite 3.43.1, and the A worktree `app.__file__` were verified. `test_m6_5_siege_runtime.py` plus `test_facility_gate_layered_runtime.py` returned `51 passed, 6 warnings in 1.59s`, exit 0. This includes durable-store restart and idempotent Owner receipt recovery.
- Raw output is `F:/paralls-verification/thread-a/m6-5-obligation-current-tip-20261126-03/pytest.log`; pytest temporary data is under the same F-drive run root. Failed command-line quoting attempts are separately retained in run IDs `...-01` and `...-02`; neither reached pytest.
- No frozen selection or full backend suite was run. The result verifies the focused recovery path only; it does not verify full L5 obligation metadata, production deployment, or UE transport.

### H-A-086 | M2-1 Ownership/Credential caller classification current-tip update | 2026-11-26

- At A tip `299767446515338576a615c36c6fccfa03cacda5`, static classification of the listed Ownership/Credential reads is recorded in `docs/verification/g2-visibility-budget/m2-1-ownership-credential-read-paths-20261122.md` and appended to `docs/verification/m2-2-read-as-contract-audit-20261126.md`.
- The inspected paths are trusted Owner preconditions, resolver snapshots, idempotent recovery, sample/debug projections, or replay/checkpoint verification. `CredentialPresentationValidator.verify_right_holder_presentation` has no production caller in the inspected application call graph. No production subject-facing Ownership/Credential projection route was identified.
- This completes only the static classification of the enumerated A-side callers. It does not establish absence of readers outside the inspected tree and does not provide `read_as` enforcement. Newly migrated readers still require classification. M2-2 remains blocked on persisted event-time semantics, principal qualification/selector semantics, and the event-to-FactType visibility contract. No code or test behavior changed; no tests were run.

### H-A-087 | M5-3 `pack.migrated` ownership decision recorded | 2026-11-26

- 项目负责人决定：`pack.migrated` 按平台控制面事件处理，不新增玩法 Owner。
- Current implementation evidence: `PackageMigrationAuthority.PRINCIPAL_REF` is `authority:platform:rule-pack-migration`; the per-world stream is `platform:rule-packs:<world_ref>`; schema v1 is registered for `pack.migrated`. The replay resolver validates and applies the persisted migration chain by global sequence.
- Existing tests cover durable reopen and historical sequence resolution, exact idempotent retry, changed-payload rejection, stale-source rejection, and rejected-command zero-write behavior. At exact tip `299767446515338576a615c36c6fccfa03cacda5`, `test_package_migration_runtime.py` returned `21 passed, 2 warnings in 0.46s`. Python 3.12.2, SQLite 3.43.1, and `app.__file__` under the A worktree were verified. Raw output: `F:/paralls-verification/thread-a/m5-3-platform-event-20261126-02/pytest.log`. This verifies the migration runtime tests, not production deployment or external manifest supply.

### H-A-088 | M6-5 exact-tip focused recovery verification | 2026-11-26

- At A tip `f9ed782d690f4796dbc1ae517bbc105fa8fddbbe`, the documentation-only follow-up was verified with `test_m6_5_siege_runtime.py` and `test_facility_gate_layered_runtime.py`: `51 passed, 6 warnings in 1.96s`, exit 0.
- Python 3.12.2, SQLite 3.43.1, and A-worktree `app.__file__` were verified. Raw output: `F:/paralls-verification/thread-a/m6-5-current-tip-20261126-04/pytest.log`.
- This is focused runtime evidence only. Formal obligation metadata, production Gate configuration, deployment, UE transport, frozen selections, and full backend regression remain unverified.

### H-A-089 | M6-5 obligation formal shape cross-check | 2026-11-26

- The external settlement contract now confirms the obligation fields and enums: `pipeline_ref`, `completed_steps`, `pending_steps`, `pending_reason` (`rejected | unknown | timeout | host_unavailable`), `owner_refs`, `recovery_action` (`retry | reconcile | manual | compensate`), and `deadline_world_tick`, alongside `obligation_id`.
- The same contract requires original-idempotency lookup before retrying unknown results, no automatic rollback on timeout, and append-only compensation events.
- This removes ambiguity about field names and allowed values. It does not provide M6-5-specific pipeline identity, Owner mapping, or deadline source. The runtime will not invent those values. `impact_gate_obligation.py` remains incomplete and no code was changed.

### H-A-090 | M6-5 obligation implementation dependencies narrowed | 2026-11-26

- M6-2 evidence confirms `l5_pipeline.py` currently compiles and binds versioned impact profiles, but production host resolution, committed obligation step receipts, and query-failure handling are not connected. The county siege packs contain no pipeline declaration that can supply an `impact_gate` pipeline identity.
- Before implementation, three concrete inputs are required: a versioned pipeline declaration/ref for the Gate impact to Facility integrity to Presence passability path; the authoritative Owner refs for each pending step; and a world-tick/deadline policy with its source and unknown behavior.
- The existing evidence can map durable receipts to completed steps (`impact`, `facility`, `presence_input`, `passability`) and known principals, but it cannot derive the missing pipeline/deadline contract. No placeholder values or runtime fields were added.

### H-A-091 | M6-5 rebuildable obligation metadata implemented | 2026-11-26

- `ImpactGateObligation` now exposes the formal metadata from the existing durable receipt projection. `pipeline_ref="impact_gate"`; completed and pending steps derive from `impact`, `facility`, `presence_input`, and `passability` receipts. Pending Owner refs are `Production` for facility work and `Presence` for presence/passability work. Open state uses `pending_reason="unknown"` and `recovery_action="reconcile"`; settled state has no pending fields.
- `deadline_world_tick` is explicitly `None` because no M6-5 deadline policy or authoritative tick source exists. No value is inferred from physics ticks, global sequence, or the demo profile.
- Focused M6-5 tests returned `51 passed, 6 warnings in 1.74s`. Raw output: `F:/paralls-verification/thread-a/m6-5-obligation-metadata-full-20261126-01/pytest.log`.
- This is a rebuildable projection over existing receipts. No new persisted event or workflow ledger was introduced. Production deployment, authoritative Gate values, UE transport, frozen selections, and full backend regression remain unverified.

### H-A-092 | M6-5 obligation metadata selection verification | 2026-11-26

- At exact tip `20c67b18`, `m6-5-impact-gate-layered-execution.json` returned `selected=21 problems=0 improvements=0` and `m6-5-production-wiring.json` returned `selected=6 problems=0 improvements=0`.
- Raw outputs are under `F:/paralls-verification/thread-a/m6-5-obligation-selection-20261126-01/`. This is registered-selection evidence only; full backend regression, production deployment, Gate values, and UE transport remain unverified.

### H-A-093 | M6-5 all registered selection verification | 2026-11-26

- At exact tip `20c67b18`, the remaining M6-5 registered selections returned: facility-integrity `5/0/0`, gate-profile-contract `19/0/0`, information-report-source `25/0/0`, organization-roster `3/0/0`, place-output-types `3/0/0`, presence-passability `6/0/0` (`selected/problems/improvements`).
- Combined with H-A-092, M6-5 registered coverage is `81 selected, 0 problems, 0 improvements`. Raw outputs: `F:/paralls-verification/thread-a/m6-5-all-selections-20261126-01/`.
- This does not establish production deployment, authoritative Gate values, UE transport, or full backend regression.

### H-A-094 | M6-5 selection count and revision correction | 2026-11-26

- Raw `results.json` reports confirm that the six H-A-093 groups ran at `a294fce4` and cover 61 nodes. The two H-A-092 groups ran at `20c67b18` and cover 27 nodes. The eight groups cover 88 unique nodes with zero problems and zero improvements. The intermediate commit changed only documentation.

### H-A-095 | M5-3 historical package replay across multiple migrations | 2026-11-26

- Commit `c9a22c53` fixes historical replay after two or more committed migrations. The chain validator advances through every migration, while the returned package set advances through the requested sequence. The v1 event schema and write path are unchanged.
- The regression failed with `package_migration_from_chain_invalid` before the fix. Package migration and schema registry tests returned 35 passed and two warnings with Python 3.12.2, SQLite 3.43.1, and the A worktree app import.
- At `c9a22c53`, the 23-node M5-3 selection and the five frozen groups (24, 12, 87, 56, 990) each reported zero problems and improvements. Logs are under `F:/paralls-verification/thread-a/m5-3-history-20261126-01/`. Other registered groups, full backend regression, and production deployment were not run for this fix.

### H-A-096 | M5-3 historical replay registered selection follow-up | 2026-11-26

- The 27 registered groups run at `83d1dd12` returned 286 selections, zero problems and zero improvements. With the 23-node M5-3 group at `c9a22c53`, this is 28 groups and 309 selections, counting a shared node once per group. The commits differ only in evidence documentation.
- The per-group table is in `docs/verification/m5-3-package-migration-20261126.md`. The full backend run is queued behind B's full run. Production deployment remains unverified.

### H-A-097 | A full backend regression at current tip | 2026-11-26

- At `7ab4d72e08ed2afa17db4deb8d1cac262f5dd50b`, the frozen G0 backend suite collected 10,745 nodes and exited 1: 10,718 passed, 23 failed, 4 skipped including 2 xfailed, 239 warnings, in approximately 1,332.86 seconds. Python 3.12.2 and the A worktree import path were verified. Twenty-two failed node IDs match the frozen README table and one additional ID is absent. This is not a zero-difference result. Evidence: `docs/verification/m5-3-full-backend-20261126.md`.
- Registered selection evidence remains 28 groups, 309 node selections, zero problems and zero improvements.

### H-A-100 | M5-5 FactType identity and scope contract increment | 2026-11-26

- 提交：`177765ba300a26f6aebfc77bcdb291e58da480ad`。`fact_type_registry.py` 现在拒绝缺失或未知 `identity`，并强制 `singleton` 只配 `global`、其他三种 identity 不配 `global`。直接编译的 credential test fixture 已声明 `entity_ref`。
- 证据：`docs/verification/m5-5-facttype-identity-20261126.md`。定向 `124 passed, 2 warnings`；M5-5 选集 `selected=27 problems=0 improvements=0`；ownership/modifier/equipment/inventory/shared-replay 分别 `24/0/0`、`12/0/0`、`87/0/0`、`56/0/0`、`990/0/0`。
- 该增量只完成 FactType identity/schema 一致性，M5-5 规则目录中需要正式 Resolver、Owner 或 temporal_effects 合同的项目仍未完成。全量 10,745 节点未因本增量重跑。

### H-A-101 | M5-5 resolution-order regression assertion | 2026-11-26

- 提交：`7690df59deb49f5af179dcca92f552a1caaf890f`。在已有 credential registry 测试中补充 resolution order 唯一性与从 10 开始连续性的回归断言。定向节点 `1 passed, 2 warnings`，原始输出在 `F:/paralls-verification/thread-a/m5-5-order-contract-20261126-01/focused.log`。
- 该断言只验证编译器已实现的结构性保证，未新增规则包语义或 Owner。

### H-A-102 | M5-5 identity enum positive coverage | 2026-11-26

- 提交：`38a1ccd0`。补充 `collection_ref` 和 `region_ref` 合法 identity 的规则包正例，四种正式 identity 均有运行覆盖。完整 validator 定向 `123 passed, 2 warnings`；M5-5 选择集 `29/0/0`。原始输出在 `F:/paralls-verification/thread-a/m5-5-identity-enum-20261126-02/focused.log` 与 `F:/paralls-verification/thread-a/m5-5-identity-enum-selection-20261126-01/`。
- 该测试增量仍只验证现有 FactType schema，不新增 Owner 或持久事件语义。

### H-A-103 | M3-1 OwnerCommitBuilder current-tip revalidation | 2026-11-26

- At current A tip `9cee2f25911dcc6221c43e89b9b42ace38ae3d06`, focused OwnerCommitBuilder/Ownership/Credential tests returned 23 passed, 2 warnings. Frozen selections returned ownership 24/0/0 and shared-replay 990/0/0. Python 3.12.2 and current A worktree `app.__file__` were verified.
- Raw evidence is under `F:/paralls-verification/thread-a/m3-1-current-tip-20261126-01/`. Full backend suite was not rerun. M3-1 remains `待门禁`.

### H-A-098 | Additional full-suite failure scope classification | 2026-11-26

- The additional node is `tests/test_population_cold_ready_gate.py::test_cold_ready`; it fails because `report["resource_bounds"]["passed"]` is false. The test, its `scripts/verification/verify_population_long_session_recovery.py` runner, and `backend/app/population/` have no changes relative to `origin/integration`. This lies outside the Architecture v2 A scope, so no code change was made. Detailed result is in `docs/verification/m5-3-full-backend-20261126.md`.

### H-A-099 | M5-5 formal Validator rule catalog coverage | 2026-11-26

- Cross-checked every code in the formal Validator rule directory against the current A implementation, tests, and supported pack sections. Evidence is docs/verification/m5-5-rule-catalog-coverage-20261126.md.
- FactType resolution-order duplicates and gaps are prevented by enumerating a topological ordering from 10, though direct assertions are absent. primitive_count_exceeded is prevented by the fixed six-value registry and package primitive rejection. Owner-set rules, executable-invariant validation, Resolver purity attestation, and impact-profile cycle validation have no corresponding package declaration or graph contract in the current loader. No such package fields or semantics were invented. M5-5 remains incomplete. Static-only; no tests were run.

### H-A-104 | M5-5 FactType primitive field contract increment | 2026-11-26

- The package validator now rejects primitive-incompatible `aggregation`, `refold_model_ref`, `state_set_ref`, `bond_types`, and `place_kind` fields. The registry accepts the registered `holdings`, `bond`, `process`, and `place` primitives as well as existing `machine` and `pool` primitives. No new primitive was registered.
- Focused validator/registry tests: `134 passed, 2 warnings`. M5-5 selection: `36/0/0`; frozen selections ownership/modifier/equipment/inventory/shared-replay: `24/0/0`, `12/0/0`, `87/0/0`, `56/0/0`, `990/0/0`. Evidence: `docs/verification/m5-5-facttype-primitives-20261126.md` and raw outputs under `F:/paralls-verification/thread-a/`.
- The full backend run at `1be69ba3` collected 10,759 and exited 1 with `10,693 passed, 62 failed, 2 skipped, 2 xfailed, 236 warnings`. Failures were not compared against parent or frozen baseline and remain unclassified. `source_unchanged=true`. A run-created malformed pytest temp directory was moved intact from the A backend to the run evidence directory on F: after pytest exited.
- M5-5 remains in progress; this increment does not establish full-suite success or complete the rule catalog.

### H-A-105 | M5-5 primitive field regression coverage completion | 2026-11-26

- The regression suite now exercises incompatible values for all five fields in `_FACT_TYPE_FIELD_PRIMITIVES`. The `state_set_ref` negative case is tested directly through `FactTypeRegistry.compile`, because package parsing already rejects the field shape before registry compilation for non-machine primitives.
- At pushed tip `30c4bf5051ebf789e7e724a3fbd19ba793da6d29`, focused validator/registry tests returned `136 passed, 2 warnings`; the updated M5-5 selection returned `38/0/0`. Both exact-tip outputs and F-drive temporary data are under `F:/paralls-verification/thread-a/m5-5-field-coverage-exacttip-20261126-01/`.
- The earlier full run at `1be69ba3` used the same production implementation but preceded these test-only changes. Its `62` failures remain unclassified; the full suite was not rerun after the additional tests.

### H-A-106 | M5-5 full-suite failure triage and Holdings fixture alignment | 2026-11-26

- Commit `955fd258` adds the required `identity: entity_ref` to the M1-2 Holdings test fixtures and updates the expected rejection for `state_set_ref` on a Holdings primitive to `facttype_field_primitive_invalid`.
- The original 62 full-suite failure node IDs were rerun with an F-drive basetemp. Result: `57 passed, 5 failed`. The five remaining node IDs reproduced at parent `9cee2f25`; this sampled comparison is not the frozen G0 baseline comparison. Focused validator/registry/Holdings tests returned `139 passed, 2 warnings`; M5-5 selection returned `38/0/0`.
- The prior full-suite run was at commit `1be69ba3` with uncommitted M5-5 source and test changes. Its backslash-form pytest temp setting produced 32 `FileNotFoundError` failures and a malformed temp tree under `backend`. The run-owned tree remains preserved with the F-drive evidence. Full backend suite at exact tip `955fd258` has not been run.
- Evidence: `docs/verification/m5-5-facttype-primitives-20261126.md`. Raw triage output: `F:/paralls-verification/thread-a/m5-5-failure-triage-20261126-03/`, `m5-5-failure-triage-parent-20261126-01/`, and `m5-5-holdings-fixture-20261126-02/`.

### H-A-107 | M5-5 exact-tip backend full-suite result | 2026-11-26

- At pushed tip `8febee38542567246a18f28700d2abc313ba20aa`, `backend/tests` returned `10,750 passed, 7 failed, 2 skipped, 2 xfailed, 227 warnings` in `1,242.66s`, exit 1. Three failed nodes match the frozen G0 failure table. `test_cold_ready` is the previously documented out-of-scope failure H-A-098. `test_recovery_owner_probe_measures_original_startup_before_full_oracle` also fails at parent `c0f85969`.
- The two `test_profile_repeated_in_one_run_receives_fresh_events` variants failed because Port 8000 was occupied by the existing backend at `D:\cl-laya`. A left that process untouched. No new M5-5 failure was identified; the run is not a zero-failure pass.
- Python 3.12.2, SQLite 3.43.1, and the A-worktree app import path were verified. `PYTHONPATH` referenced the A worktree backend, `PYTEST_ADDOPTS` was cleared, and pytest temporary paths were directed to F:. Raw output: `F:/paralls-verification/thread-a/m5-5-current-tip-backend-full-20261126-01/full.log`.

### H-A-108 | M5-5 rule-catalog current-tip correction | 2026-11-26

- The H-A-099 audit was static at an earlier tip. Commits `7690df59` and `38a1ccd0` subsequently added explicit resolution-order uniqueness/density assertions and positive coverage for all four FactType identity values. The updated static audit is `docs/verification/m5-5-rule-catalog-coverage-20261126.md`.
- At A tip `27c2aaa0`, command `D:\Temp\paralls-g0-py312\Scripts\python.exe -m pytest -q backend\tests\test_credential_fact_type_registry.py backend\tests\test_rule_pack_validator.py --basetemp=F:\paralls-verification\thread-a\m5-5-rule-catalog-current-tip-20261126-01\pytest-tmp-raw` returned `136 passed, 2 warnings in 3.32s`, exit 0. Raw output is `F:/paralls-verification/thread-a/m5-5-rule-catalog-current-tip-20261126-01/focused.log`. Python 3.12.2, SQLite 3.43.1, and `app.__file__ = F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py` were verified with `PYTHONPATH` set to that worktree's `backend`.
- Remaining M5-5 gaps require formal Owner, Resolver-purity, and invariant-expression contracts; impact-profile cycles are not representable by the current flat layer format. `temporal_effects` remains blocked on its formal package and runtime-consumer contract. No code behavior changed. M5-5 remains in progress.

### H-A-109 | M2-1 current-tip M6-5 read-path classification | 2026-11-26

- At A tip `ad6ef57cc575ff87b0daa86cfec1552d93a51942`, the Information, Morale, and Presence reads added by M6-5 were statically classified in `docs/verification/g2-visibility-budget/m2-1-ownership-credential-read-paths-20261122.md`.
- Information report publication and recipient-knowledge updates are trusted signed or post-delivery Owner writes. Morale reads roster/LifeState history at the committed casualty sequence before its Pool write. Presence validates breach/impact evidence and pinned revisions before writing Place. The HTTP routes accept authority inputs and return command results. No subject-facing production query route was found in the inspected A call graph.
- This is static-only evidence. It does not implement `read_as` or establish absence of external readers. Principal qualification, visibility-to-FactType mapping, and `known_time` remain M2-2 dependencies. No code behavior changed and no tests ran.

### H-A-110 | M5-5 Owner and invariant contract scope correction | 2026-11-26

- The formal Owner definition already specifies declaration fields (`kind`, `domain`, `writes`, `denies`, `invariants`, `commands`, `resolvers`, `reads`, and related metadata). The gap is in implementation: A code has only an Owner ID allowlist, with no machine-readable declaration registry/compiler or complete code-consumable declaration set for migrated Owners. Package files intentionally do not own these declarations.
- The invariant document requires a restricted expression and gives examples, but no complete grammar/operator registry was found. Resolver purity is required by the Resolver contract, but the package format has no consumed code-capability or side-effect attestation. M5-5 cannot safely implement those checks by inventing syntax or declarations.
- Updated static catalog evidence: `docs/verification/m5-5-rule-catalog-coverage-20261126.md`. No code or tests changed. The audit is static-only and does not complete M5-5.

### H-A-111 | M6-5 production pipeline and Gate configuration status | 2026-11-26

- Current A-tip static search confirms `packs/county_siege_morale_presence/play_patterns/play_pattern.yaml` declares `pipelines: []`; no package declares an impact pipeline, and no production caller in `backend/app/gameplay` or `backend/app/main.py` invokes or consumes a compiled `Pipeline`. `l5_pipeline.py` currently provides declaration compilation and input binding only. This is a real M6-5 production integration gap, separate from the receipt-based recovery and obligation metadata projection completed in H-A-091.
- `SIEGE_FACILITY_GATE_PROFILES_JSON` is parsed by `backend/app/config.py` and passed into the M6-5 runtime. The tracked `.env.example` labels its `gate-03` profile as demonstration-only and requires authorized values before deployment. Static repository search found no deployment manifest or target that supplies authoritative Gate durability, breach thresholds, or impact deltas. No values were promoted from the demo profile to production configuration.
- No source code, tests, integration branch, or production configuration changed in this audit. This is static-only evidence. To close the production pipeline gap, M6-5 needs an approved impact-profile and pipeline declaration for the Facility-to-Presence flow, including the resolver/step contract. To verify deployment, the production owner must supply the target and authoritative per-Gate values. Deadline policy/source remains unspecified, so `deadline_world_tick` continues to be unknown.

### H-A-112 | M6-5 four-layer Pipeline execution contract gap | 2026-11-26

- The formal `02-守城Demo定义.md` specifies four ordered `impact_gate` layers: door durability, latch durability, integrity, and passability; the pipeline is an obligation because the final step is a separate Presence commit. The current `FacilityGateLayeredAuthority` commits its three Production pool layers together. `PlacePassabilityAuthority._commit_impact_assessment` consumes the later Presence receipt's post-Facility layer revisions as its current read set. In contrast, `Pipeline.bind_inputs` requires all four steps to receive exactly the same revision vector.
- The county siege package still has `pipelines: []` and declares no impact profile. The M6-5 production path has no compiled-Pipeline consumer. `main.py` calls `load_deployment_package_archive(..., handlers={})`, while FactTypeRegistry requires a registered handler for each declared code Resolver, so adding resolver-backed package content also requires production handler registration.
- Proposed implementation preserving formal H10: reconstruct and pin the original shared pipeline input vector from the signed Gate input and its event-sequence snapshot, keep each Owner's current CAS/read set separate, and derive obligation progress from existing durable receipts. This must be tested against the existing no-auto-passability rule and restart replay. The production handler registration touches shared `backend/app/main.py`; BOUNDARIES requires A/B coordination before editing it.
- No code or tests changed in this audit. Static-only evidence. Production Gate values and target remain unavailable as recorded in H-A-111.

### H-A-113 | M6-5 shared input revision snapshot projection | 2026-11-26

- Commit `4cf77e5d3f59ff1c1203808dac1bbb8a93a7ee0c` adds a rebuildable four-stream `input_revision_vector` to each v2 Gate obligation. It derives the door durability, latch durability, integrity, and Place passability revisions from events preceding the authenticated impact input's `global_sequence`; a durable-store reopen test confirms later Facility and Presence writes do not change the vector.
- This preserves the distinction raised in H-A-112: the pipeline vector is the original shared snapshot, while Facility and Presence retain their own current CAS/read sets. No persisted event field or Owner write contract changed.
- Verification: 52 focused tests passed; the registered impact-gate selection passed 22 nodes; frozen ownership and shared-replay selections passed 24 and 990 nodes with zero problems and improvements. Evidence and raw outputs are recorded in `docs/verification/m6-5-shared-pipeline-input-vector-20261126.md` and `F:\paralls-verification\thread-a\m6-5-vector-final-20261126-01\` / `F:\paralls-verification\thread-a\m6-5-vector-selections-20261126-01\`.
- The projection is not yet consumed by a compiled production `Pipeline`. The county siege pack still lacks its Pipeline declaration, production Resolver handlers remain unregistered, and `main.py` requires A/B coordination before wiring. M6-5 remains incomplete; full backend regression, live deployment, authoritative Gate values, UE transport, and a complete siege run are not verified.

### H-A-114 | M6-5 Place FactType schema reference | 2026-11-26

- Commit `2e6cc2ee` makes `require_event_schema_ref` resolve `place@v1` through the existing `PLACE_EVENT_SCHEMAS` registrations. Before the change, the regression test failed with `event_schema_unregistered`; after the change, the schema-registry and rule-pack-validator tests returned `141 passed, 2 warnings`.
- At the worktree containing this increment, the registered impact-gate selection returned `23/0/0`; frozen ownership and shared-replay returned `24/0/0` and `990/0/0`. Raw output is under `F:/paralls-verification/thread-a/m6-5-place-schema-contract-20261126-01/` and `m6-5-place-schema-exacttip-20261126-01/`.
- This only makes the existing Place event schemas referable from a FactType declaration. It does not declare a package Place FactType, satisfy U2/U3, add a Pipeline, or consume a compiled Pipeline. M6-5 remains in progress; the full backend suite was not run.
- Commits `2e6cc2ee` and `8f5dd7de` are local. The SSH push stalled without returning; GitHub API recheck still showed remote branch tip `dc71c554`, so this increment and its comms notice have not reached B's remote branch.

### H-A-115 | M6-5 versioned impact Pipeline production consumer | 2026-11-27

- Current worktree adds `impact_gate` to `county_siege_morale_presence@1.0.1`, retaining `1.0.0` for historical package pins. Startup registers its code Resolver handlers. The runtime binds each step to the four-stream revision snapshot reconstructed from the signed input sequence; Facility and Presence Owners validate Resolver output against their signed source and reject mismatches without writing their facts.
- Focused tests: `197 passed, 6 warnings`. M6-5 registered selection: `26/0/0`; frozen Ownership: `24/0/0`; frozen shared-replay: `990/0/0`. Python 3.12.2, SQLite 3.43.1, A worktree import path; raw outputs are under `F:/paralls-verification/thread-a/m6-5-impact-pipeline-20261127-01/`. Evidence: `docs/verification/m6-5-impact-gate-pipeline-20261127.md`.
- Implementation commit `3c003e42` is on the A branch. The full backend suite was not run. M6-5 remains in progress because authoritative production Gate values and a deployment target are unavailable; `.env.example` remains demo-only. UE transport and a complete siege run were not verified. `deadline_world_tick` remains unknown.

### H-A-116 | M2-1 M6-5 impact Pipeline read-path classification | 2026-11-27

- Static caller review at A tip `2a46df6303228993161ccb9f02e1f789083b4134` classifies Pipeline vector reconstruction and both Resolver reads as trusted inputs to Facility/Presence settlement. Their production callers are the signed-input command path and startup recovery; both Owners validate the resolved plan against signed evidence before fact writes.
- `impact_gate_obligations()` has no production caller in the inspected `backend/app` call graph; matches are tests. The Gateway routes accept signed command receipts and return their own command result, with no general Pipeline/obligation query route found.
- No production principal-facing query path was found by the inspected searches. This is static-only evidence and does not prove the absence of external callers. It does not satisfy M2-2 `read_as`, principal qualification, visibility mapping, or `known_time`. Evidence is appended to `docs/verification/g2-visibility-budget/m2-1-ownership-credential-read-paths-20261122.md`. No tests ran.

### H-A-117 | M2-2 optional persisted event_time foundation | 2026-11-27

- Project-owner authorization for the A thread covers this storage-core increment. `GameplayEvent.event_time` is now an optional strict nonnegative integer. Legacy events without the field load as unknown and keep their prior serialized shape. No sequence-based fallback is used.
- Exact implementation code is in the current A worktree after `6bea7490`; it is not committed yet. Tests cover durable reopen, snapshot round-trip, legacy snapshot compatibility, and invalid bool rejection.
- Focused event-store/persistence/replay tests: 50 passed. Frozen selections: ownership 24/0/0, modifier 12/0/0, equipment 87/0/0, inventory 56/0/0, shared-replay 990/0/0. All 28 registered selections had zero problems.
- Full backend suite: 10,761 passed, 5 failed, 2 skipped, 2 xfailed, exit 1. Four failures reproduced on parent `6bea7490`; the recovery-measurement node passed on both parent and current after clearing malformed process Git-config override state.
- Evidence: `docs/verification/m2-2-read-as-contract-audit-20261126.md`; raw outputs: `F:/paralls-verification/thread-a/m2-2-event-time-20261127-01/`.
- M2-2 remains blocked. There is still no authoritative event-time producer, shared principal selector interpreter, or production event-type to FactType/visibility mapping. This increment does not implement `read_as` or satisfy U7.

### H-A-118 | M2-2 Information report event-time producer | 2026-11-27

- Commit `583cf8df` writes the validated publication `world_now` to the top-level `GameplayEvent.event_time` for Information report facts. The existing `published_at_world_tick` payload, event identity, visibility, and retry contract remain unchanged. Legacy events remain unknown.
- TDD evidence: before the implementation, `test_information_owner_publishes_signed_report_and_replays_after_window` failed because `report.event_time` was `None`; after implementation the Information runtime file returned 12 passed and the event persistence file returned 26 passed.
- Frozen results: Information report selection `25/0/0`, Ownership `24/0/0`, shared-replay `990/0/0`. Python 3.12.2, SQLite 3.43.1, `app.__file__` inside the A worktree. Raw outputs are under `F:/paralls-verification/thread-a/m2-2-information-event-time-20261127-02/`.
- This provides a producer for this Information event only. M2-2 remains blocked and U7 remains unmet pending principal qualification and selector semantics, event-type-to-FactType visibility mapping, and a subject-facing reader. Full backend suite was not run for this increment.

### H-A-119 | M2-2 Information event-time full verification | 2026-11-27

- The full backend suite at A tip `2b9e81bb` was run with Python 3.12.2, `PYTHONPATH` pointing to the A worktree, `GIT_CONFIG_COUNT=0`, and all pytest temporary paths on F drive. Result: `10,744 passed, 22 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1, 1377.68 seconds.
- Twenty-one failures in the calibration, Godot/external-engine, cold-ready, population harness/capacity/recovery, and role-presentation files reproduced at parent `207dd8d7` in a focused parent run. The remaining full-run runtime-process-transport failure passed when isolated on both parent and current tip, indicating an order/environment-sensitive full-run failure. No Information report test failed. This is not a full-suite pass and does not change M2-2's blocked status.
- The first interrupted attempt created a D-drive pytest directory because the inherited `TEMP/TMP` values pointed there. That owned run's regular files were moved to `F:/paralls-verification/thread-a/m2-2-information-event-time-full-20261127-01/`; the completed rerun used F drive for all temporary paths. No unrelated D-drive directories were changed.

### H-A-120 | M5-3/M6-5 current-tip focused verification | 2026-11-27

- At the current A tip `d98d442f`, the focused M5-3 package migration/control-plane tests, M6-5 siege assembly, Morale refold, Presence admission, and Information production wiring tests returned `128 passed, 6 warnings` in `8.77s` with Python 3.12.2. `PYTHONPATH` resolved to the A worktree backend and pytest temporary data was directed to `F:/paralls-verification/thread-a/m5-m6-current-tip-20261127/`.
- This verifies the existing platform `pack.migrated` replay path and the current Morale/Presence/Information wiring. It does not provide production Gate values, a deployment target, UE transport, a subject-facing `read_as` route, or a formal `temporal_effects` contract.
- Morale production writes currently flow through the shared Pool commit path, which has no trusted `world_now` input. Presence code inspected in this pass is a source reader/admission path, not an event-time producer. Adding event-time fields there would require a new shared Pool or source-event contract, so no code was changed in this pass.

### H-A-121 | M2-2 Morale event-time producer | 2026-11-27

- The Morale refold path now passes a casualty event's optional strict nonnegative `event_time` through the Pool adjustment commit. The value is included in the idempotency digest. Legacy callers omit it and preserve the prior event shape. Code and tests are in the current A worktree.
- TDD evidence: the new propagation test first failed with `adjusted.event_time is None`; after the minimal Pool/Morale change, Pool + Morale returned `22 passed, 2 warnings`. The broader M5-3/M6-5/Morale/Presence/Information + Pool set returned `147 passed, 6 warnings`.
- This is one additional event-time producer. It does not implement `read_as`, selector qualification, event-to-FactType visibility mapping, or a Presence event-time producer. Full backend verification was not run.
- The two direct regression nodes are registered in `docs/verification/selection/m2-2-morale-event-time.json`. Frozen-baseline comparison: `selected=2 problems=0 improvements=0`; raw output is under `F:/paralls-verification/thread-a/m2-2-morale-event-time-selection-20261127-01/`.
### H-A-122 | M5-3/M6-5 current-tip regression follow-up | 2026-11-27

- At A tip `e99de108`, the focused package migration/control-plane, schema registry, Information production wiring, siege runtime, Morale refold, Pool runtime, and siege Information tests returned `119 passed, 6 warnings` with Python 3.12.2. `app.__file__` was resolved from the A worktree and pytest temporary paths were directed to `F:`.
- This is current-tip focused evidence. It does not verify production Gate values, a deployment target, UE transport, a complete siege run, subject-facing `read_as`, or the full backend suite.
- The approved M5-3 ownership decision remains in force. `pack.migrated` is an L4 platform control-plane event and does not add a gameplay Owner.
### H-A-123 | M1-4 Place contract audit | 2026-11-27

- Static audit recorded in `docs/verification/m1-4-place-contract-audit-20261127.md`.
- The formal Place primitive requires general occupancy/movement semantics, revisioned path and occupancy facts, independent passability commits, and a space-registry reference. Current A code only provides Presence-specific passability assessment and Place event schema entries for that path.
- No general Place runtime or space registry was found in the inspected A code and tests. Reusing Presence would conflate authorities, so no code was changed. M1-4 remains queued pending the space-registry, Owner mapping, persistence-event, and producer/reader contracts.

### H-A-124 | A current-tip frozen selection recheck | 2026-11-27

- After the M1-4 audit, the current A tip was rechecked with the frozen comparator. Ownership returned `selected=24 problems=0 improvements=0`; shared-replay returned `selected=990 problems=0 improvements=0`.
- Raw outputs are under `F:/paralls-verification/thread-a/tip-20261127-01/`. This is selection evidence only and does not close M1-4, M2-2, production deployment, Gate configuration, UE transport, or the full backend suite.

### H-A-125 | M5-5 validator current-tip check | 2026-11-27

- Current A-tip validator coverage passed `144 tests, 2 warnings` across `test_rule_pack_validator.py`, `test_fact_type_registry.py`, and `test_gameplay_event_schema_registry.py` under Python 3.12.2 with the A-worktree import path. Temporary paths were directed to `F:/paralls-verification/thread-a/m5-5-validator-20261127-01/`.
- This is verification of the existing contract only. M5-5 remains open because the formal machine-readable Owner declaration registry, invariant expression grammar, Resolver capability/side-effect attestation, and `temporal_effects` package/runtime contract are still unspecified.
### H-A-126 | M6-4 L5 composition current-tip check | 2026-11-27

- The valid current-tip focused L5 command returned `32 passed, 2 warnings` across play-pattern compilation, reaction validation, and dispatch runtime tests under Python 3.12.2 and the A-worktree import path.
- An initial command included nonexistent `backend/tests/test_l5_pipeline.py` and exited during collection. No test or source file was changed, and the corrected command produced the result above.
- This verifies existing offline composition and dispatch behavior. Application registration/activation and production package dispatch remain unverified, so M6-4 stays pending gate.
### H-A-127 | M6-1 to M6-4 current-tip composition regression | 2026-11-27

- The current A tip passed the combined L5 declaration and loading regression: `test_rule_pack_validator.py`, `test_l5_reaction.py`, `test_l5_play_pattern.py`, and `test_l5_workflow.py` returned `162 passed, 2 warnings` with Python 3.12.2 and the A-worktree import path.
- This verifies offline reaction, pipeline/workflow/play-pattern contracts and rule-pack loading. Production application activation, deployment package dispatch, UE transport, and a complete siege run remain unverified.
### H-A-128 | M6-5 startup and runtime current-tip verification | 2026-11-27

- The current A tip passed `test_m6_5_siege_runtime.py` and `test_runtime_asgi.py`: `55 passed, 6 warnings` with Python 3.12.2 and the A-worktree import path.
- The tests cover package-consumer construction, startup assembly, dispatch/recovery paths, and ASGI lifecycle behavior. Production deployment, authoritative Gate values, UE transport, and a complete external siege run remain unverified.
### H-A-129 | Current A-tip full backend suite | 2026-11-27

- Full `backend/tests` run at current A tip with Python 3.12.2 and all pytest temporary paths on F: returned `10,761 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings`, exit code 1, after about 22 minutes.
- The five failures were external or pre-existing environment/runtime families: missing `tokenizers`, Godot headless parse errors, population cold-ready report schema, recovery probe Git configuration, and a role-presentation Godot headless probe. This run does not establish a full-suite pass and does not identify an Architecture v2 M5/M6 focused-path failure.
- The result is recorded as merge-state full-suite evidence only, separate from individual slice verification.
- Environment difference: one pytest `tmp_path` diagnostic resolved under inherited `D:\codex-temp\user-temp` despite F-drive `TEMP/TMP`; no unrelated D-drive content was moved or deleted. A future rerun must pass an explicit F-drive `--basetemp`.
### H-A-130 | M6-5 explicit F-drive pytest basetemp recheck | 2026-11-27

- M6-5 siege runtime and ASGI tests returned `55 passed, 6 warnings` under Python 3.12.2 with explicit F-drive `TEMP`, `TMP`, `PYTHONPYCACHEPREFIX`, and `--basetemp`.
- Raw pytest temporary data is under `F:/paralls-verification/thread-a/m6-basetemp-20261127-01/`. This closes the prior focused-test environment difference only. Production deployment, Gate values, UE transport, and full siege execution remain unverified.
### H-A-131 | Verification temp migration follow-up | 2026-11-27

- Files from the A full-run pytest directory `D:/codex-temp/user-temp/pytest-of-User/pytest-3354` were moved to `F:/paralls-verification/thread-a/migrated-pytest-3354/`. The source was verified file-empty afterward.
- Deleting only the empty source directory was attempted but rejected by execution policy. No other D-drive content was touched.

### H-A-132 | M3-1 current-tip revalidation | 2026-11-27

- At A tip `3978f4f9ecc02990e2be8d09681a3beaed40ad58`, `OwnerCommitBuilder` focused tests returned `23 passed, 2 warnings`. Frozen ownership selection returned `selected=24 problems=0 improvements=0`; frozen shared-replay returned `selected=990 problems=0 improvements=0`.
- Raw outputs are retained under `F:/paralls-verification/thread-a/m3-1-current-tip-20261127-02/`. This is slice-level current-tip evidence. The latest full backend suite remains a merge-state result with `10,761 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings`, exit code 1, and is not attributed to M3-1.
- M3-1 remains `待门禁`; no integration or main branch was modified.

### H-A-133 | M3-2 current-tip revalidation | 2026-11-27

- At A tip `259314e2`, the `StoreReadSnapshot` focused tests returned `34 passed, 2 warnings`. Its registered selection returned `selected=7 problems=0 improvements=0`. Frozen ownership, modifier, equipment, inventory and shared-replay returned `24/0/0`, `12/0/0`, `87/0/0`, `56/0/0` and `990/0/0` respectively.
- Raw outputs are retained under `F:/paralls-verification/thread-a/m3-2-current-tip-20261127-01/`. This is current-tip mechanism evidence only. The current-tip full backend suite was not rerun for M3-2.
- M3-2 remains `待门禁`; no integration or main branch was modified.

### H-A-134 | M2-1 shared-mechanism read-path update | 2026-11-27

- Static inspection at A tip `bc639342` enumerated `OwnerCommitBuilder.build` production callers in Credential, Holdings, Ownership and Pool, plus `StoreReadSnapshot` callers in Credential and LandRight.
- These are trusted append-envelope and validation snapshot helpers. No subject-facing production query or `read_as(principal)` route was found. The evidence was appended to `docs/verification/g2-visibility-budget/m2-1-ownership-credential-read-paths-20261122.md`.
- This increment ran no tests and does not resolve M2-2 principal qualification, selector semantics, FactType visibility mapping or `known_time`.

### H-A-135 | M2-4 current-tip replay/startup revalidation | 2026-11-27

- At A tip `74a291c4`, `test_gameplay_event_replay.py` and `test_gameplay_projection_startup.py` returned `15 passed, 2 warnings` with explicit F-drive pytest basetemp.
- This is a mechanism-focused revalidation. It covers cursor/tail replay, stream revision continuity, failure without partial installation, checkpoint-free rebuild and checkpoint-plus-tail digest equality. No code changed and no current-tip full suite was run.
- Raw output is under `F:/paralls-verification/thread-a/m2-4-current-tip-20261127-01/`; M2-4 remains `待门禁`.

### H-A-136 | M6-1 current-tip Reaction revalidation | 2026-11-27

- At A tip `1e318bb5`, focused Reaction, Play Pattern and RulePack Validator tests returned `154 passed, 2 warnings`. The Reaction registered selection returned `selected=14 problems=0 improvements=0`; L5 dispatch runtime returned `selected=5 problems=0 improvements=0`.
- This is offline declaration/loader evidence only. Production asynchronous trigger scheduling, target authorization, cooldown/idempotency dispatch, UE transport and a complete siege run remain unverified. M6-1 remains `待门禁`.

### H-A-137 | M6-2 current-tip Pipeline revalidation | 2026-11-27

- At A tip `9f4cfd82`, focused RulePack Validator, Reaction and Play Pattern tests returned `154 passed, 2 warnings`. Pipeline selection returned `8/0/0`, ownership `24/0/0`, and shared-replay `990/0/0`.
- This confirms offline declaration and input-binding behavior. Production settlement, durable obligation execution/recovery and application activation remain unverified. M6-2 remains `待门禁`.

### H-A-138 | M6-3 current-tip Workflow revalidation | 2026-11-27

- At A tip `8ff452c7`, focused Workflow, RulePack Validator, Reaction and Play Pattern tests returned `162 passed, 2 warnings`. Workflow selection returned `8/0/0`, ownership `24/0/0`, and shared-replay `990/0/0`.
- This verifies offline declaration and package loading. Production workflow execution, durable obligation recovery and Gateway activation remain unverified. M6-3 remains `待门禁`.

### H-A-139 | M6-4 current-tip Play Pattern revalidation | 2026-11-27

- At A tip `90e72a67`, focused Play Pattern, RulePack Validator, Reaction and Workflow tests returned `162 passed, 2 warnings`. Play Pattern selection returned `12/0/0`, ownership `24/0/0`, and shared-replay `990/0/0`.
- This verifies offline declaration and package-loading behavior. Production application activation and combined pattern execution remain unverified. M6-4 remains `待门禁`.

### H-A-140 | M6-5 current-tip production-path regression | 2026-11-27

- At A tip `cd1b1c9b`, eight focused M6-5 test files returned `228 passed, 6 warnings`. Layered impact, production wiring and Information selections returned `26/0/0`, `6/0/0` and `25/0/0`; frozen Ownership and shared-replay returned `24/0/0` and `990/0/0`.
- This verifies local tested startup, command, Owner and replay paths. No production Gate values, deployment target, UE transport or complete external siege execution were supplied. `deadline_world_tick` remains unknown. The full backend suite was not rerun.
- Raw outputs are under `F:/paralls-verification/thread-a/m6-5-current-tip-20261127-01/`. M6-5 remains in progress.

### H-A-141 | M5-5 current-tip validator and registry revalidation | 2026-11-27

- At A tip `e002eb24`, five focused validator/registry/EventSchema files returned `165 passed, 2 warnings`. M5-5 selection returned `38/0/0`; frozen Ownership/modifier/equipment/inventory/shared-replay returned `24/12/87/56/990`, all zero differences.
- The first invocation did not reach test execution because the explicit F-drive `--basetemp` parent directory was absent. After creating that run-owned directory, the identical test command passed.
- Raw outputs are under `F:/paralls-verification/thread-a/m5-5-current-tip-20261127-01/`. Formal Owner registry/compiler, invariant grammar, Resolver capability attestation, and `temporal_effects` remain unresolved; M5-5 remains in progress.

### H-A-142 | M5-3 current-tip package migration and archive revalidation | 2026-11-27

- At A tip `e09bcf1a`, package migration, EventSchema registry and M6-5 runtime focused tests returned `74 passed, 6 warnings`. Current M5-3 selection returned `23/0/0`, Ownership `24/0/0`, and shared-replay `990/0/0`.
- The M5-3 selection file now contains 23 nodes; this supersedes the older 22-node count in prior evidence. Production manifest trust source, cross-language hash canonicalization, production deployment, Gate values, UE transport and complete siege execution remain unverified.
- Raw outputs are under `F:/paralls-verification/thread-a/m5-3-current-tip-20261127-01/`. M5-3 remains in progress pending deployment inputs.

### H-A-143 | M2-2 event-time producer audit | 2026-11-27

- Static `rg -n event_time backend/app/gameplay backend/app/main.py` inventory and M6-5 call-path trace are recorded in `docs/verification/m2-2-event-time-producer-audit-20261127.md`.
- The only source-time producer is Information report publication. Morale propagates time only when the casualty source event already has one. The M6-5 Presence route does not pass a world tick, and signed physical receipts persist `physics_tick` without an established mapping to the session world-tick epoch. Facility and Presence source-time producers remain absent.
- This was static-only. No code or tests changed. M2-2 remains blocked on the shared principal/selector and FactType visibility contracts, subject-facing `read_as`, and authoritative event-time sources for the other domains.

### H-A-144 | M3-3 shared Owner replay receipt validation | 2026-11-27

- `owner_runtime_base.replay_duplicate` now validates committed result/transaction identity, idempotency record identity, committed event count and uniqueness, event resolution and exact transaction membership, optional expected event types, global sequence range, and resulting stream revisions before returning a duplicate receipt. Credential's duplicate path uses this shared validation with its existing event-type and error-code expectations.
- Code commit: `78fa4548` (`feat-owner-replay-validation`).
- Three failing-first Ownership tests proved absent validation for a missing event, event count mismatch, and missing transaction. Current focused shared/primary-domain tests returned `112 passed, 2 warnings`; tests for other helper callers returned `87 passed, 6 warnings`. The new M3-3 selection returned `9/0/0`; frozen Ownership/Modifier/Equipment/Inventory/shared-replay returned `24/12/87/56/990`, all zero differences.
- Evidence: `docs/verification/m3-3-shared-owner-replay-validation-20261127.md`. Full backend suite was not run. Replay paths bypassing `replay_duplicate` and remaining domain R2 promotions are not covered; M3-3 remains in progress.

### H-A-145 | M5-5 principal selector registration | 2026-11-27

- The current A worktree validates FactType `learnable_by` selector syntax at registration and rejects nested `group_of` selectors with `facttype_selector_nesting_invalid`. Existing Information `recipient_of(subject)` declarations remain accepted.
- This is schema registration only. It does not implement principal qualification sources, runtime selector evaluation, event-to-FactType visibility mapping, or `read_as`.
- Evidence: `docs/verification/m5-5-selector-registration-20261127.md`. Focused tests returned `218 passed, 6 warnings`; new selection `6/0/0`; 30 existing registered selections and frozen Ownership/Modifier/Equipment/Inventory/shared-replay selections all returned zero differences. Full backend suite was not run.
- M2-2 remains blocked and M5-5 remains in progress.

### H-A-146 | M3-3 R2 replay path audit | 2026-11-27

- Static `rg` inventory at A tip `ea3c727f` confirms A-owned Credential, Ownership, LandRight, Holdings, Pool and package migration command paths use shared `replay_duplicate`.
- Repository-wide direct idempotency and custom duplicate paths remain in other domains and shared/forbidden files. `event_store.py`, `models.py`, `economy_runtime.py`, and `inventory_runtime.py` were not edited.
- Evidence: `docs/verification/m3-3-r2-replay-path-audit-20261127.md`. No tests ran. M3-3 remains in progress and is not globally R2-complete.

### H-A-147 | M2-2 compiled FactType event-schema reference retention | 2026-11-27

- The compiled immutable FactType now retains the optional `event_schema_ref` already validated by RulePack loading. Legacy/direct declarations without the field retain `None`.
- This gives a future visibility projection a read-only schema reference. It does not implement event-to-FactType mapping, principal qualification, selector evaluation, or `read_as`.
- Evidence: `docs/verification/m2-2-event-schema-ref-retention-20261127.md`. Registry/validator/EventSchema tests returned `168 passed, 2 warnings`; related package tests returned `44 passed, 6 warnings`; new selection `1/0/0`. M2-2 remains blocked.

### H-A-148 | M2-2 FactType event-schema reverse index | 2026-11-27

- `FactTypeRegistry` now exposes an immutable exact-reference index from validated `event_schema_ref` values to compiled FactTypes. It does not canonicalize aliases or infer event types.
- Evidence: `docs/verification/m2-2-event-schema-index-20261127.md`. Registry/RulePack/FactType/EventSchema tests returned `169 passed, 2 warnings`; related package tests returned `44 passed, 6 warnings`; new selection `1/0/0`.
- This remains a mapping input only. Principal qualification, visibility projection, `read_as`, and event-time producer gaps remain. M2-2 is blocked.

### H-A-149 | A tip full backend regression | 2026-11-27

- Current A tip `c821c558` full backend suite: `10,783 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1.
- The five failing node IDs were rerun at parent `e8c9f841` and all five failed there with the same failure families. No failure was attributed to the M2-2 FactType schema-ref retention or reverse-index changes.
- Evidence: `docs/verification/a-tip-full-backend-20261127.md`. This is merge-state regression evidence, not a full-suite pass. M2-2 remains blocked.
### H-A-150 | M3-3 A-owned current-tip replay audit | 2026-11-27

- At A tip `684b4b1f`, the A-owned migrated command paths use the shared `replay_duplicate` helper. The municipal drought assessment certificate path remains a special settlement-plan flow. Its durable payload digest derives from the complete `GameplayCommandEnvelope`, and its duplicate check validates the committed certificate against advisory, causation, and correlation fields after admission. No behavior was changed without a path-specific contract.
- Focused municipal certificate and shared-helper tests returned `17 passed, 2 warnings` under Python 3.12.2 with F-drive temporary data. Evidence: `docs/verification/m3-3-a-owned-current-tip-audit-20261127.md`.
- M3-3 remains in progress. Repository-wide R2 completion and the special path's contract-specific migration remain unverified.

### H-A-151 | M3-3 municipal certificate replay validation | 2026-11-27

- Commit `7ba82daf` routes municipal certificate retries through shared `replay_duplicate`, using the complete expected `GameplayCommandEnvelope` digest and explicit command, transaction, and event-type expectations. The retry check remains before current revision checks, preserving replay after the original commit advances source streams. Helper failures retain the path's rejected-result shape.
- TDD red exposed that an incomplete committed-event receipt returned generic `idempotency_key_reused`; the new path returns `ownership_replay_event_count_mismatch` without appending transactions or events. Final focused tests: `18 passed, 2 warnings`; new M3-3 selection `1/0/0`; frozen Ownership/Modifier/Equipment/Inventory/shared-replay selections total `1,169/0/0`.
- Evidence and raw logs: `docs/verification/m3-3-municipal-certificate-replay-20261127.md`; `F:/paralls-verification/thread-a/m3-3-municipal-final-20261127-01/` and `F:/paralls-verification/thread-a/m3-3-municipal-frozen-20261127-01/`. Full backend suite was not run. M3-3 remains in progress because repository-wide direct/custom replay paths are not fully audited.

### H-A-152 | M3-3 Morale refold replay validation | 2026-11-27

- Commits `11fd1754` and `2d0ef9c6` route Morale casualty refold retries through shared `replay_duplicate`. The stored Pool digest is retained for retries because historical roster/life-state reads can advance after the original commit. Durable transaction, event count, event references, event type, sequence and resulting revisions are still validated.
- TDD red exposed that an incomplete committed-event receipt returned `morale_idempotency_key_reused`; the new path returns `morale_replay_event_count_mismatch` without writes. Focused tests: `27 passed, 2 warnings`; new selection `1/0/0`; frozen selections total `1,169/0/0`.
- Evidence and raw logs: `docs/verification/m3-3-morale-refold-replay-20261127.md`; `F:/paralls-verification/thread-a/m3-3-morale-r2-20261127-01/` and `F:/paralls-verification/thread-a/m3-3-morale-frozen-20261127-01/`. Full backend suite was not run. M3-3 remains in progress because repository-wide direct/custom replay paths are not fully audited.

### H-A-153 | M3-3 Facility and Presence replay validation | 2026-11-27

- Commit `32373b52` routes Facility layered impact, legacy Presence assessment, and signed-impact Presence retries through shared `replay_duplicate` validation. Presence accepts the two committed event shapes only on their corresponding streams and checks the original source-event relationship. Rejected damaged receipts leave the store snapshot unchanged.
- TDD red reproduced a committed Facility result with a truncated multi-event receipt and an `IndexError` on damaged Presence receipts. The four-node selection returned `4/0/0`. Facility/Presence/physical-input/M6-5 focused tests returned `76 passed, 6 warnings`; frozen Ownership/Modifier/Equipment/Inventory/shared-replay returned `24/12/87/56/990`, all with zero differences.
- Evidence: `docs/verification/m3-3-facility-presence-replay-20261127.md`. Raw outputs are under `F:/paralls-verification/thread-a/m3-3-facility-presence-red-20261127-01/`, `m3-3-facility-presence-focused-20261127-01/`, `m3-3-presence-legacy-red-20261127-01/`, `m3-3-facility-presence-integration-20261127-01/`, and `m3-3-facility-presence-selections-20261127-01/`.
- Full backend suite was not run. M3-3 remains in progress because other direct/custom replay paths remain. Production Gate values remain unconfigured pending an authoritative deployment profile.

### H-A-154 | M3-3 Information report replay validation | 2026-11-27

- Commit `094669f1` routes the Information siege-report publication retry through shared `replay_duplicate` validation before follow-on delivery. Existing report-content matching remains, and recovery still publishes delivery using the original report's committed world tick.
- TDD red showed an empty committed-event receipt returning generic `information_report_idempotency_key_reused`. The new path returns `information_report_replay_event_count_mismatch` without changing the store snapshot. Information/M6-5 focused tests returned `51 passed, 6 warnings`; the new M3-3 selection returned `1/0/0`; the existing M6-5 Information selection returned `25/0/0`; frozen five selections returned `24/12/87/56/990`, all with zero differences.
- Evidence: `docs/verification/m3-3-information-report-replay-20261127.md`. Raw output: `F:/paralls-verification/thread-a/m3-3-information-report-red-20261127-01/`, `m3-3-information-report-focused-20261127-01/`, and `m3-3-information-report-selections-20261127-01/`.
- This does not cover Information knowledge-update or signed physical-input retries. Full backend suite not run; M3-3 remains in progress. Production Gate values remain unconfigured pending an authoritative deployment profile.

### H-A-155 | M3-3 signed physical-input replay validation | 2026-11-27

- Commit `81e047e0` routes signed physical-input retries through shared `replay_duplicate` before returning an existing receipt. It retains the v1/v2 event-type expectation, verifies the receipt-derived stream and payload, and keeps duplicate lookup ahead of v2 Presence source freshness checks.
- TDD red showed an empty committed-event list returning generic `siege_input_receipt_conflict`. The new path returns `siege_input_replay_event_count_mismatch` without changing the store snapshot. Focused physical-input/Facility/Presence/M6-5 tests returned `77 passed, 6 warnings`; M3-3 selection `1/0/0`; M6-5 impact-gate selection `26/0/0`; frozen five selections `24/12/87/56/990`, all with zero differences.
- Evidence: `docs/verification/m3-3-physical-input-replay-20261127.md`. Raw outputs: `F:/paralls-verification/thread-a/m3-3-physical-input-red-20261127-01/`, `m3-3-physical-input-focused-20261127-01/`, and `m3-3-physical-input-selections-20261127-01/`.
- This does not complete M3-3 or the full backend suite. Other direct/custom replay paths remain; production Gate values remain unconfigured pending an authoritative deployment profile.

### H-A-156 | M3-3 Information knowledge replay and B checkpoint-tail delivery | 2026-11-27

- A commit `33a1c38a` routes Information knowledge-update retries through shared `replay_duplicate` validation. A damaged receipt is rejected without changing the durable snapshot. B commits `a61c93ad` and `a1719826` were selectively cherry-picked as A commits `07db5404` and `400d4ff9`; the knowledge event now persists its existing top-level `event_time`, and durable checkpoint-plus-tail replay is covered by a new test. B's selection update in `e185cfa8` was already present on A and required no duplicate commit.
- After the selective integration, Information/M6-5/checkpoint focused tests returned `53 passed, 6 warnings`; M3-3 knowledge selection `1/0/0`; B `siege_information` selection `26/0/0`; M6-5 Information report selection `25/0/0`; frozen Ownership/Modifier/Equipment/Inventory/shared-replay selections returned `24/12/87/56/990`, all with zero differences.
- Evidence: `docs/verification/m3-3-information-knowledge-replay-20261127.md`; raw output `F:/paralls-verification/thread-a/information-b-replay-a-tip-20261127-01/`. Python 3.12.2 and A-worktree import path were verified; all temporary paths were on F:.
- `integration` was not modified. M3-3 remains in progress because other direct/custom replay paths remain. M6-5 remains in progress because production Gate values, deployment target, live Unreal transport and complete siege execution remain unverified; `deadline_world_tick` is unknown.
### H-B-010 | Information durable checkpoint-tail replay verification | 2026-11-27

- B verified on A baseline `99c7be5f5b290e82f4f2f4d70ea0ac40d7499851` that the recipient-private report and SocialDelivery state can be checkpointed, an Information knowledge event can be appended as tail, and durable reopen preserves a checkpoint-plus-tail projection equal to full replay.
- Snapshot restoration rejects a missing report event and a report event ID changed while its committed transaction still refers to the original ID. Report, delivery and knowledge transaction principals and the knowledge input revision vector are asserted.
- Focused Information replay/runtime/production-wiring tests returned `24 passed, 6 warnings`. The L5-generated knowledge event now stores the existing top-level `event_time`; event type and payload schema are unchanged.
- Full backend regression returned `10,769 passed, 22 failed, 2 skipped, 2 xfailed`, exit 1. Seventeen failing nodes reproduced on the unchanged A parent. Five others passed when isolated on both parent and current worktrees after failing only in the full-suite run context. No full-suite pass is claimed. Details and logs are in `docs/verification/information-replay-20261127/evidence.md` and `F:/paralls-verification/thread-b/information-replay-20261127-a99c7b/`.
- This evidence does not cover `read_as`, full visibility semantics, production Gate values, live Unreal input or complete siege execution. The Information unit remains pending gate.

### H-A-157 | M2-2 event-schema reference resolution increment | 2026-11-27

- Commit `c55b009fa601f0334345741f1fcb3d8dc5e08948` exposes exact `(event_type, schema_version)` keys for explicitly registered schema references. `require_event_schema_ref` reuses the mapping, preserves registry checks, and retains the legacy Credential reference behavior. This gives a future FactType projection reader a stable mapping input; no inference or visibility policy was added.
- EventSchema, RulePack, FactType, and Holdings focused tests returned `174 passed, 2 warnings`. All 40 registered selections and all five frozen selections returned zero problems and improvements. The frozen set covered 1,169 nodes. Full backend at the commit returned `10,794 passed, 6 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1.
- Four full-suite failures reproduced at the parent: unavailable `tokenizers`, two Godot parser failures, and a population readiness report missing `resource_bounds`. The recovery subprocess failure was caused by inherited malformed `GIT_CONFIG_COUNT` values and passed on the parent with `GIT_CONFIG_COUNT=0`. The full-suite ASGI timeout passed on both parent and current commit when isolated. No full-suite pass is claimed.
- Evidence: `docs/verification/m2-2-event-schema-ref-resolution-20261127.md`; new U11 selection `docs/verification/selection/m2-2-event-schema-ref-resolution.json`; raw output under `F:/paralls-verification/thread-a/m2-2-event-schema-resolution-20261127-01/` through `...-07/`.
- M2-2 remains blocked. The runtime event-to-FactType/visibility consumer, principal qualification and selector execution, reader classification, subject-facing `read_as`, and cross-domain authoritative event-time producers remain incomplete. U7 is not complete.

### H-A-158 | M2-2 Facility and Presence event-time producers | 2026-11-27

- Commit `35cf812a88ae970ac899e43bae734a507c0de87f` reads the trusted M6-5 `world_tick_provider` only for a new signed input. Physical input events persist that time; Facility and Presence derived facts reuse the persisted input time. Exact retries do not call the provider again. Legacy inputs without `event_time` remain readable and retain unknown time.
- TDD red showed that an exact retry consumed a second tick. Focused M6-5/Facility/Presence/physical-input tests returned `83 passed, 6 warnings`. New selection returned `2/0/0`; frozen Ownership/Modifier/Equipment/Inventory/shared-replay selections returned `24/12/87/56/990`, all with zero problems or improvements.
- Current full backend returned `10,797 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1. Parent `357cbdea` comparison under `GIT_CONFIG_COUNT=0` reproduced four failures among five selected nodes. The remaining recovery node passed under clean Git configuration and also passed alone on current. `cold_ready` failed its resource bound in isolation, while the full run reported `KeyError: resource_bounds`. This is not a full-suite pass.
- Evidence: `docs/verification/m2-2-facility-presence-event-time-20261127.md`; raw outputs under `F:/paralls-verification/thread-a/m2-2-event-time-owner-producers-20261127-08/` through `...-13/` and `F:/paralls-verification/thread-a/m2-2-facility-presence-event-time-20261127-01/`.
- M2-2 remains blocked on principal qualification and selector evaluation, the runtime event-type-to-FactType/visibility consumer, reader classification, the subject-facing `read_as` entry point, and inventory of other migrated-domain event-time sources. U7 is not complete.

### H-A-159 | M2-2 exact event-schema to FactType candidate index | 2026-11-27

- Commit `b42a1c2420f7c808944243120ec50a27663e9ac6` adds an immutable exact `(event_type, schema_version)` index over compiled FactType schema references. Shared schema references retain all candidates, and the legacy Credential alias resolves.
- Focused registry/RulePack/FactType/EventSchema/Holdings/selector tests returned `147 passed, 2 warnings`; the new selection returned `2/0/0`; related schema selections returned `2/0/0`, `1/0/0`, and `1/0/0`; principal-selector registration returned `6/0/0`. Frozen Ownership/Modifier/Equipment/Inventory/shared-replay selections returned `24/12/87/56/990` with zero differences.
- Evidence: `docs/verification/m2-2-facttype-event-mapping-20261127.md`; raw outputs under `F:/paralls-verification/thread-a/m2-2-facttype-event-mapping-focused-20261127-01/` and `F:/paralls-verification/thread-a/m2-2-facttype-event-mapping-20261127-01/`.
- This index returns candidates only. It does not establish instance FactType attribution, visibility, selector evaluation, or subject-facing `read_as`. M2-2 remains blocked and U7 remains incomplete. Full backend suite was not run for this increment.

### H-A-160 | M2-2 migrated-domain event-time source inventory | 2026-11-27

- Static repository search found event-time writes in Information report/knowledge publication and M6-5 signed physical input; derived Facility, Presence, and Morale events preserve their committed source event time. Ownership/Credential have no `GameplayEvent.event_time` producer in their runtimes. Their Bond/Credential `world_tick` fields are for term/expiry semantics and cannot substitute for event occurrence time.
- Legacy inputs and casualty events without time remain unknown. No time was inferred from global sequence, stream revision, or Bond expiry ticks. `embodied_interaction_session_service.py` has a separate `known_time` payload field and is not part of the `GameplayEvent.event_time` producer set.
- Evidence: `docs/verification/m2-2-event-time-source-audit-20261127.md`. Static only; no tests ran.
- The current A-side source inventory is recorded. M2-2 remains blocked on trusted principal qualification/selector execution, FactType/visibility enforcement, classifying future migrated readers, and subject-facing `read_as`. U7 is incomplete.

### H-A-161 | M2-2 authenticated principal source and bounded read recommendation | 2026-11-27

- Static tracing found `WebSocketSessionAuthService` binding a deployment-verified or trusted-loopback `principal_ref` and fixed `allowed_actor_refs` into backend-held connection state. Existing session projection checks resolve the current binding before authorizing an actor scope.
- This supplies a potential trusted identity root for a recipient-private read. It does not supply faction, role, group, `owner_of`, or `holder_of` qualifications, and it is not itself the gameplay `read_as` mechanism.
- Recommendation: first implement a narrow recipient-private read using the authenticated binding and explicit actor scope. Add other selectors only when their owning fact sources can resolve historical qualifications. Do not accept qualifications from request payloads. Measure a bounded query under D6 before expanding event history reads.
- Evidence: the authenticated principal source follow-up in `docs/verification/m2-2-read-as-contract-audit-20261126.md`. Static only; no tests ran. M2-2 remains blocked and U7 is incomplete.

### H-A-162 | M2-2 Information recipient-private read slice | 2026-11-27

- A adds an Information-only report read and a `information_report_read` WebSocket message. The current backend-issued binding must authorize the requested actor, the current server world clock bounds `as_of_tick`, and the client cannot supply a principal or selector qualification.
- The read verifies the deterministic Information report and SocialDelivery streams, Owner transaction principals, recipient visibility, source revision, event time, known time, delivery window, expiry, and revocation. Missing/unknown or malformed evidence returns unavailable. The result includes FactType, Information Owner, source revision, event_time, known_time, and freshness.
- Revocation lookup is event-type filtered because the existing P5 revocation contract has no recipient/source index. It may scan all matching revocation events. No event-store/storage-core change or persistent event contract change was made.
- Focused Information/checkpoint/wiring/WebSocket tests returned `41 passed, 6 warnings`; new selection `5/0/0`; frozen five selections returned `24/12/87/56/990` with zero differences. Full backend suite was not run.
- D6's existing durable fixture scan ran in two independent processes. Both 4,096-event rows exceeded the provisional 40 ms p95; run 2 also exceeded the provisional 1.10 ratio for one 256-event and one 1,024-event row. This diagnostic does not measure the new authorization path or a production workload and does not pass D6. One first-run fixture accidentally landed on D and was moved to F; the D source directory is absent.
- Evidence: `docs/verification/m2-2-information-report-read-20261127.md`; exact-commit focused output is in `F:/paralls-verification/thread-a/m2-2-information-read-20261127-13/`, independent WebSocket rerun in `...-12/`, frozen selections in `...-08/`, and P-1 scan in `...-11/`; D6 results are in `F:/paralls-verification/thread-a/m2-2-d6-durable-visibility-20261127-01/` and `...-02/`.
- M2-2 remains blocked. This narrow Information route is not generic `read_as` and does not complete U7. Generic selector qualification, FactType/visibility enforcement, broader owner-backed reads, revocation lookup cost, and real workload D6 evidence remain open.
- Code commit: `8faeab2331187b3e13f3c2583fb8c3f6087dd090`. The registered 5-node selection points to this exact code commit. P-1 five-family scan of staged code additions reported zero credential-pattern hits.

### H-A-163 | M2-2 compiled FactType identity metadata | 2026-11-27

- Commit `57d8f4f4b21f985282f472633e6e193a8641e6a8` retains the validated FactType `identity` field in compiled runtime metadata. The new assertion failed first with `AttributeError`; the full RulePack validator module then returned `132 passed, 2 warnings`.
- The registered selection returned `1/0/0`; frozen Ownership/Modifier/Equipment/Inventory/shared-replay selections returned `24/12/87/56/990`, all with zero problems and improvements.
- The full backend suite returned `10,790 passed, 20 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1. Fourteen nested evidence cases failed under the deeply nested F-drive TEMP path, and the recovery measurement inherited an empty `GIT_CONFIG_VALUE_0`. A short-TEMP, process-clean rerun of the evidence test module, recovery measurement and runtime-process node returned `42 passed, 2 warnings`. Four other environment/known failure families remain in the full-suite log. This is not a full-suite pass.
- Evidence: `docs/verification/m2-2-facttype-identity-20261127.md`; full-suite raw output is under `F:/paralls-verification/thread-a/m2-2-facttype-identity-20261127-02/full-backend/`; corrected rerun is under `F:/paralls-verification/thread-a/m2-2-facttype-identity-20261127-03/`.
- This only preserves schema metadata. Event-to-instance mapping, historical principal qualification, selector evaluation, runtime visibility enforcement and generic `read_as` remain incomplete. M2-2 remains blocked and U7 is not complete.

### H-A-164 | M2-2 FactType instance resolution | 2026-11-27

- Commits `9520808e0a67919663d1d167efa389b2fdffb431` and `244a120920fc197ef9721bac34992226255e959b` add `FactTypeRegistry.resolve_event_fact_type` and reject an explicitly null payload `fact_type`. Resolution requires an exact event type/version candidate and a FactType-ID `stream_id`; registered wildcard scopes resolve to the concrete stream reference. A present payload `fact_type` must agree with the stream. Legacy domain stream IDs, unknown or ambiguous candidates, and conflicts return `None`.
- This follows the formal event envelope (`stream_id = FactType ID`) and does not change persisted events or existing callers. It resolves formal Pool-shaped events, including a shared schema where payload `fact_type` selects one of several candidate FactTypes.
- Focused resolver tests returned `5 passed`; RulePack/FactType rejection/Holdings registry modules returned `178 passed, 2 warnings`. Registered selection `5/0/0`; frozen ownership/modifier/equipment/inventory/shared-replay selections `24/12/87/56/990`, all zero differences. Full backend suite not run for this increment.
- Evidence: `docs/verification/m2-2-facttype-instance-20261127.md`; raw runs under `F:/paralls-verification/thread-a/m2-2-facttype-instance-20261127-01/` through `-08/` and `F:/paralls-verification/thread-a/m2-2-facttype-null-20261127-01/` through `-02/`.
- Information and legacy Credential events with domain-specific stream IDs do not resolve through this contract. Historical selector qualification, runtime visibility enforcement, and generic `read_as` remain open; M2-2 remains blocked and U7 incomplete.

### H-A-165 | Information checkpoint-tail current-tip recheck | 2026-11-27

- At A tip `a3e9bc3fcc3ee9aa6af17c99b635f86dc976a9c5`, Information replay/runtime/production-wiring tests returned `30 passed, 6 warnings`, exit 0. The registered `siege_information` selection returned `selected=26 problems=0 improvements=0`.
- Python `3.12.2` was run from `F:\codex-temp\thread-a-python312\Scripts\python.exe`; SQLite `3.43.1`; `app.__file__` resolved to this A worktree. `PYTHONPATH`, all temporary/cache paths, and outputs were on F:.
- The tested B checkpoint-tail contribution was already present in A through prior selective commits; no duplicate cherry-pick or code change was needed. This recheck did not rerun the frozen five selections or the full backend suite.
- Evidence and raw logs: `docs/verification/m3-3-information-knowledge-replay-20261127.md` and `F:/paralls-verification/thread-a/information-replay-current-tip-20261127-01/`. M2-2/U7 and M3-3 remain open. `integration` was not modified.

### H-A-166 | M2-2 Information knowledge recipient read | 2026-11-27

- Commit `ebb28f737840f5786c3c5789d68d7c5458f57847` adds the recipient-private `information_knowledge_read` WebSocket message and its Information-owned reader. Access is anchored to the active bound session actor and server world clock. The reader validates the report, recipient-private delivery, knowledge transaction, causation relationship and source revision vector before returning `report_knowledge` with `event_time`, `known_time` and freshness.
- Exact-tip focused Information runtime, checkpoint-tail replay, production-wiring and WebSocket tests returned `42 passed, 6 warnings`. The existing five-node Information recipient-read frozen selection returned `selected=5 problems=0 improvements=0`. Frozen Ownership/Modifier/Equipment/Inventory/shared-replay selections returned `24/12/87/56/990`, all zero differences. Python 3.12.2 and the A-worktree import path were verified; temporary paths were on F:.
- Evidence and raw output: `docs/verification/m2-2-information-knowledge-read-20261127.md` and `F:/paralls-verification/thread-a/m2-2-information-knowledge-read-20261127-04/`.
- This adds a bounded Information consumer only. Generic `read_as`, historical selector qualification, FactType-wide visibility execution, legacy stream attribution, U7 and full backend regression remain unverified. M2-2 stays blocked. `integration` was not modified.

### H-A-167 | M2-2 Information `read_as` wiring | 2026-11-27

- Commit `97c21f06b2e00e69926e6e77515aa967bae4c805` adds `GameplayReadAs` and routes the report and report-knowledge WebSocket reads through it. It accepts only the two registered Information FactTypes with private visibility and `recipient_of(subject)`, exact scope keys, the session-bound character, and the server world tick. The Information authority validates the recipient-private source chain and revision evidence.
- Focused Information runtime, checkpoint-tail, production-wiring, WebSocket, and M6-5 tests returned `81 passed, 6 warnings`; the new 3-node selection returned `3/0/0`; frozen five selections returned `24/12/87/56/990`, all zero differences. Python `3.12.2`, SQLite `3.43.1`, and A-worktree `app.__file__` were verified. All temporary/output paths were on F:.
- Evidence: `docs/verification/m2-2-information-read-as-20261127.md`; raw outputs under `F:/paralls-verification/thread-a/m2-2-read-as-info-20261127-01/`.
- This does not implement historical qualification for other selectors, FactType-wide visibility execution, legacy domain-stream attribution, or full U7. The full backend suite was not run. M2-2 remains blocked; `integration` was not modified.

### H-A-168 | M2-2 reject unsupported visibility models | 2026-11-27

- Commit `e941b91b` rejects non-null `delay`, `delay_model`, `distortion`, and `distortion_model` declarations when the registered Information reader has no executor for them.
- TDD red showed an Information FactType with a distortion declaration still returned a projection. After the guard, focused Information/checkpoint/wiring/WebSocket/M6-5 tests returned `81 passed, 6 warnings`; the Information selection returned `3/0/0`; frozen five selections totaled `1,169/0/0`.
- Evidence is appended to `docs/verification/m2-2-information-read-as-20261127.md`; raw output is under `F:/paralls-verification/thread-a/m2-2-read-as-info-20261127-02/` and `...-03/`.
- Delay/distortion models remain unimplemented. M2-2 remains blocked and U7 incomplete; the full backend suite was not run.

### H-A-169 | M2-2 explicit secret/debug visibility denial | 2026-11-27

- Commit `76a55dd2169b2834de9bbc53693f2a24bc3ea503` makes `secret` and `debug_only` visibility return the explicit `read_as_visibility_forbidden` error before invoking an Information reader.
- TDD red showed these classes already failed closed but were classified as generic qualification failures. The new assertions require the explicit visibility-denial code for both classes.
- Focused tests returned `81 passed, 6 warnings`; Information selection `3/0/0`; frozen five selections totaled `1,169/0/0`. Python `3.12.2`, SQLite `3.43.1`, and A-worktree `app.__file__` were verified.
- Evidence is in `docs/verification/m2-2-information-read-as-20261127.md`; raw outputs are under `F:/paralls-verification/thread-a/m2-2-information-class-denial-20261127-01/` and `...-02/`.
- No debug access path or other selector qualification was added. M2-2 remains blocked and U7 incomplete; full backend suite not run.

### H-A-170 | M2-1 Information subject-read classification | 2026-11-27

- At A tip `805ec421`, static call-path inspection confirmed that `information_report_read` and `information_knowledge_read` are principal-facing WebSocket reads through `GameplayReadAs`. Both enforce active session binding, allowed actor membership, live lease and server world-clock bounds before requesting recipient-private Information FactTypes; the Information authority checks the committed recipient/report/delivery/knowledge chain.
- The current classification is appended to `docs/verification/g2-visibility-budget/m2-1-ownership-credential-read-paths-20261122.md`. This corrects earlier snapshots that predated the reader wiring. No tests were run for this static documentation update.
- This narrow Information reader does not complete generic selector qualification, FactType-wide visibility enforcement, legacy stream attribution, other-domain reader classification, or U7. M2-2 remains blocked; `integration` was not modified.

### H-A-171 | M6-5 production Gate input audit | 2026-11-27

- Static inspection of the read-only formal siege demo definition and PRD found the four-layer `impact_gate` order and `gate-03` target, but no authoritative numeric durability, breach, reset, or impact-delta values. The searched PRD also supplied no numeric profile.
- The tracked `.env.example` profile uses the locally exercised `gate-03` values but labels them demonstration-only. `SIEGE_FACILITY_GATE_PROFILES_JSON` is already parsed by settings; an empty profile leaves Facility unconfigured. No production target or manifest was found. Evidence: `docs/verification/m6-5-gate-production-input-audit-20261127.md`.
- No source code, production config, or tests changed. Production Gate configuration remains open pending an authorized per-Gate parameter table and the deployment target that loads it. The demo values were not promoted. M6-5 remains in progress; `integration` was not modified.

### H-A-172 | M3-1 current-tip revalidation | 2026-11-27

- At A tip `caa062aa`, the `OwnerCommitBuilder`, Ownership, and Credential focused tests returned `23 passed, 2 warnings`. The frozen Ownership selection returned `24/0/0`; shared-replay returned `990/0/0`.
- Python `3.12.2`, SQLite `3.43.1`, and A-worktree `app.__file__` were verified. Pytest temp and raw output are under `F:/paralls-verification/thread-a/m3-1-current-tip-20261127-03/`.
- This is M3-1 slice-level evidence. The full backend suite was not run; M3-1 remains `待门禁`, and `integration` was not modified.

### H-A-173 | Current A-tip full backend regression | 2026-11-27

- At A tip `3e87cadb`, `backend/tests` returned `10,806 passed, 11 failed, 2 skipped, 2 xfailed, 227 warnings` in `1494.01s`, exit 1. Python `3.12.2`, SQLite `3.43.1`, and the A-worktree import path were verified. All temp and raw output paths were on F:. The raw full log is `F:/paralls-verification/thread-a/a-tip-backend-full-20261127-01/full.log`.
- Seven nested `test_population_harness_evidence.py::test_nested_gameplay_evidence[...]` failures were `FileNotFoundError` under the long F-drive temp root. The exact seven-node family passed with short temp root `F:/paralls-verification/thread-a/p3/` (`7 passed, 33 deselected, 2 warnings`). The full run itself remains exit 1.
- The remaining four failures are missing optional `tokenizers`, the existing Task45 and Task8 Godot parser/type-resolution probes, and the previously recorded out-of-scope `test_cold_ready` resource-bound failure. Prior parent evidence for these failure families is recorded under H-A-129/H-A-098; this follow-up did not rerun them on a parent.
- Evidence: `docs/verification/a-tip-full-backend-20261127.md`. No full-suite pass is claimed; `integration` was not modified.

### H-A-174 | M2-1 Holdings and Pool read-path classification | 2026-11-27

- At A tip `a3d347ff`, static call tracing classified Holdings and Pool reads. Holdings `_read` and Pool `_read` are internal Owner-command preconditions; `HoldingsAuthorityService.project` has no production caller in `backend/app`. Facility and Morale `PoolProjector` uses are trusted settlement/rebuild inputs, and no subject-facing Holdings/Pool query route was found in `main.py`.
- The current-tip classification is appended to `docs/verification/g2-visibility-budget/m2-1-ownership-credential-read-paths-20261122.md`. This is static-only and does not establish absence of callers outside the inspected application tree. No tests ran.
- M2-2 generic `read_as`, selector qualification, FactType-wide visibility enforcement, legacy stream attribution, and U7 remain incomplete. M2-1 stays open for newly migrated reads; `integration` was not modified.

### H-A-175 | M3-3 current-tip Information replay and remaining SocialDelivery paths | 2026-11-27

- Refreshed `origin/thread-b/information-replay-20261127` at `e185cfa8a97bac5c8336eff9d15fd7f7fac9f5d9`. Its `event_time` write and checkpoint-tail test are already present on A through `07db5404` and `400d4ff9`; the `e185cfa8` selection content is already equivalent on A. No B commits were newly applied.
- At A tip `9ee5c74a`, current-tip focused Information/checkpoint/wiring/M6-5 tests returned `70 passed, 6 warnings`; M3-3 Information knowledge selection returned `1/0/0`; `siege_information` returned `26/0/0`. Python 3.12.2, SQLite 3.43.1 and the A-worktree import path were verified. Full backend suite and frozen five selections were not rerun. Evidence and raw output are recorded in `docs/verification/m3-3-information-knowledge-replay-20261127.md` and `F:/paralls-verification/thread-a/a-continuation-20261127-02/`.
- Static inspection found direct retry handling in `SocialDeliveryAuthority.record_delivery` and `expire_delivery` (`backend/app/gameplay/p5/social_delivery.py:94-110,199-212`). These paths do not use `replay_duplicate`; the delivery path does not validate the durable transaction/event set before returning the prior receipt. The expiry path checks selected event fields and transaction ID but does not validate the transaction's committed event references. `BOUNDARIES.md` does not assign this file to A, so A has not changed it. M3-3 still needs this file's owner to confirm responsibility and add R2 coverage.
- `integration` was not modified.

### H-A-176 | M3-3 SocialDelivery replay validation | 2026-11-28

- Under the user's continuing full authorization, A took the two unassigned paths in `backend/app/gameplay/p5/social_delivery.py` and routed `record_delivery` and `expire_delivery` duplicate handling through `replay_duplicate`. The shared helper now validates transaction identity, committed event references, count, sequence and revisions before replay returns. Existing semantic payload checks and legacy/current recorded event support remain.
- TDD red reproduced both paths accepting a receipt whose durable transaction `command_id` disagreed with the result. Focused SocialDelivery/caller/Information tests returned `69 passed, 6 warnings`; the new selection returned `2/0/0`; frozen five selections returned `1,169/0/0`; all 47 registered selections completed with zero differences.
- Current-tip focused rerun at documentation commit `617e965a` returned `80 passed, 6 warnings` across SocialDelivery, its caller, and Information production/siege readers. Raw output: `F:/paralls-verification/thread-a/m3-3-social-delivery-followup-20261128-01/focused.log`.
- Full backend suite returned `10,805 passed, 14 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1. Ten failed cases passed isolated short-path/clean-environment reruns. Four failure families match the prior A-tip record. A parent full-suite comparison was not run. Evidence: `docs/verification/m3-3-social-delivery-replay-20261128.md`; raw output under `F:/paralls-verification/thread-a/m3-3-social-delivery-20261127-04/` through `...-08/`.
- P-1 final supplemental scan checked the 6 documentation lines added after the 155-line branch scan, with zero hits for assignment-shaped secrets, AWS access keys, GitHub tokens, JWTs and private-key headers. Raw output: `F:/paralls-verification/thread-a/m3-3-social-delivery-followup-20261128-04/p1-scan.log`.
- M3-3 remains in progress because other direct/custom replay paths need ownership and contract review. `BOUNDARIES.md` and `integration` were not modified.

### H-A-177 | M2-1 SocialDelivery / Information read-path classification | 2026-11-28

- At A tip `1c41fb5c`, static tracing found `SocialDeliveryAuthority.view_for` is consumed by `InformationAuthority.update_knowledge` to validate a recipient's committed delivery and by the scoped checkpoint/tail participant to reconstruct a recipient projection. No production transport route exposes the generic SocialDelivery projection directly.
- Principal-facing Information report and knowledge reads remain behind the registered Information FactTypes and session-bound `GameplayReadAs` WebSocket handlers. The SocialDelivery projection is an internal validation/reconstruction input, not a second query authority.
- Evidence: `docs/verification/g2-visibility-budget/m2-1-ownership-credential-read-paths-20261122.md`. Static-only; no tests ran. M2-2's generic selector qualification, FactType-wide visibility enforcement, legacy attribution, and U7 remain open. `integration` was not modified.
- P-1 scan of this documentation increment found zero hits in all five credential-pattern families. Raw output: `F:/paralls-verification/thread-a/m2-1-read-path-20261128-01/p1-scan.log`.

### H-A-178 | M3-1 current-tip revalidation | 2026-11-28

- At A tip `a1be4c25`, OwnerCommitBuilder/Ownership/Credential tests returned `23 passed, 2 warnings`; frozen ownership and shared-replay selections returned `24/0/0` and `990/0/0`. Python `3.12.2`, SQLite `3.43.1`, and the A-worktree import path were verified.
- Full backend suite was not rerun. M3-1 remains `待门禁`; this is current-tip focused and frozen-selection evidence only.
- Evidence and raw logs: `docs/verification/m3-1-owner-commit-builder-20261122.md` and `F:/paralls-verification/thread-a/m3-1-current-tip-20261128-01/`.
- P-1 scan of the staged M3-1 evidence increment found zero hits across all five credential-pattern families. Raw output: `F:/paralls-verification/thread-a/m3-1-current-tip-20261128-03/p1-scan.log`.

### H-A-179 | M2-2 visibility denial ordering | 2026-11-28

- Code commit `95a56461b7502f9c9d681c9c8429c3c6575d51ed` moves unsupported delay/distortion and `secret`/`debug_only` checks before domain reader dispatch. TDD RED reproduced `read_as_fact_type_reader_unavailable` masking the required `read_as_visibility_forbidden`; GREEN related tests returned `32 passed, 6 warnings`.
- All 47 registered selections and frozen five (1,169 nodes) returned zero problems and improvements. Full backend run returned `10,813 passed, 6 failed, 2 skipped, 2 xfailed`; all six failed node IDs reproduced at parent `f709f82eb041affad7e99f39e5e33c3f479ba914`. The full suite is not green.
- Evidence: `docs/verification/m2-2-visibility-denial-order-20261128.md`; raw output under `F:/paralls-verification/thread-a/m2-2-read-as-metadata-order-20261128-03/` through `...-08/`.
- M2-2 remains blocked on historical selector qualification, FactType-wide visibility filtering, legacy domain stream attribution, broader Owner-backed readers, and U7. No integration change.

### H-A-180 | M3-3 SocialFactAuthority public-milling acknowledgment replay | 2026-11-28

- Under the user's continuing full authorization, A updated the unassigned `backend/app/gameplay/p5/social_knowledge.py` public-milling acknowledgment retry path to call shared `replay_duplicate`. No `BOUNDARIES.md` change was made. Code commit: `93aa11274730e09830171ea59746f3abb623349b`.
- TDD RED reproduced an invalid successful retry after the durable transaction's `command_id` diverged from the receipt. GREEN focused tests returned `30 passed, 2 warnings`; unit selection `1/0/0`; frozen five selections `1,169/0/0`. The 48 manifests present during the registered-selection sweep returned zero differences; the added one-node selection was run separately and also returned `1/0/0`.
- Full backend suite returned `10,800 passed, 20 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1. Fourteen nested gameplay-evidence failures passed with short F-drive TEMP (`14 passed, 2 warnings`). Six other failures remain: optional `tokenizers`, Task45 Godot probe, `test_cold_ready`, process outbox recovery `[before_done]`, recovery measurement, and Task8 Godot probe. No parent full-suite comparison was run. Full raw output: `F:/paralls-verification/thread-a/m3-3-social-knowledge-20261128-04/full-backend.log`.
- Evidence: `docs/verification/m3-3-social-knowledge-public-milling-replay-20261128.md`. M3-3 remains in progress; this increment closes only this retry path. No push or integration modification.

### H-A-181 | M3-3 SocialFactAuthority completed-handshake replay | 2026-11-28

- Under the user's continuing full authorization, A updated the unassigned `backend/app/gameplay/p5/social_knowledge.py` completed-handshake retry path to validate its durable transaction and event references through `replay_duplicate`. No `BOUNDARIES.md` change was made. Code commit: `f431c8969025ebc0b409183c5ff769251fc19246`.
- TDD RED reproduced an invalid successful retry when the durable transaction `command_id` diverged from the receipt. GREEN focused tests returned `39 passed, 6 warnings`; the registered unit selection returned `1/0/0`.
- Full backend suite returned `10,802 passed, 19 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1. Fourteen nested gameplay-evidence nodes passed with short F-drive TEMP (`14 passed, 2 warnings`). Five other failures remain: missing optional `tokenizers`, Task45 Godot probe, `test_cold_ready`, recovery measurement, and Task8 Godot probe. The outbox `[before_done]` failure from the prior run passed in this run. No parent full-suite comparison was run. Raw output: `F:/paralls-verification/thread-a/m3-3-social-handshake-20261128-04/full-backend.log`.
- Evidence: `docs/verification/m3-3-social-handshake-replay-20261128.md`. M3-3 remains in progress; this closes only the handshake retry path. No push or integration modification.

### H-A-182 | M3-3 SocialFactAuthority resolve replay | 2026-11-28

- Under the user's continuing authorization, A updated the unassigned `backend/app/gameplay/p5/social_knowledge.py` direct `resolve` duplicate path to validate its durable transaction, command/transaction IDs, event references, and event types through shared `replay_duplicate`. The existing `idempotency_key_reused` zero-write rejection is preserved. Code commit: `8b75524073978f8608ebd229002b37844b65be00`; no boundary file changed.
- TDD RED reproduced a corrupted durable transaction returning `committed_success`. GREEN focused P5 social knowledge tests returned `22 passed, 2 warnings`; new unit selection `1/0/0`; frozen five selections `1,169/0/0`.
- Full backend suite returned `10,817 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1. The five failures were missing optional `tokenizers`, Task45 Godot parser errors, `test_cold_ready` missing `resource_bounds`, recovery measurement missing `GIT_CONFIG_VALUE_0`, and Task8 Godot parser errors. All five reproduced at parent `f34dd3a6` in a targeted five-node run; this was not a parent full-suite run.
- Evidence: `docs/verification/m3-3-social-resolve-replay-20261128.md`; raw logs under `F:/paralls-verification/thread-a/m3-3-social-resolve-20261128-01/`. M3-3 remains in progress because other direct/custom replay paths remain. No push or `integration` change.

### H-A-183 | M3-3 private follow-on replay | 2026-11-28

- Under the user's continuing authorization, A routed the legacy milling and package-generic workshop private follow-on retry branches through durable receipt validation in `backend/app/gameplay/p5/social_knowledge.py`. The existing two actor-private event contract and `private_follow_on_idempotency_key_reused` zero-write rejection remain. Code commit: `c48503c196b1617d5383ec3be83500aae2414f60`; no boundary file changed.
- TDD RED reproduced both branches returning `committed_success` after the durable transaction `command_id` diverged from the receipt. GREEN focused tests returned `44 passed, 2 warnings`; new unit selection `2/0/0`; frozen five selections `1,169/0/0`.
- Full backend suite returned `10,819 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1. The five failures were missing optional `tokenizers`, Task45 Godot parser errors, `test_cold_ready` missing `resource_bounds`, recovery measurement missing `GIT_CONFIG_VALUE_0`, and Task8 Godot parser errors. All five reproduced at direct parent `8b755240` in a targeted five-node run; this was not a parent full-suite run.
- Evidence: `docs/verification/m3-3-social-private-follow-on-replay-20261128.md`; raw logs under `F:/paralls-verification/thread-a/m3-3-private-follow-on-20261128-01/`. M3-3 remains in progress because other direct/custom replay paths remain. No push or `integration` change.

### H-A-184 | M3-3 scripted mystery case phase/outcome replay | 2026-11-28

- Under the user's continuing authorization, A updated `backend/app/gameplay/p5/scripted_mystery_case_runtime.py` so `_append_phase` and `resolve_outcome` validate duplicate receipts through shared `replay_duplicate`, then verify request payload identity and causal metadata. Corrupt transaction metadata and changed retry payloads return `idempotency_key_reused` without writes. Code commits `b6ca607d` and `8e6d70df`; no boundary file changed.
- TDD RED reproduced both paths returning `committed=True` after the append result `command_id` diverged from the durable transaction. Final-tip focused Stormnight tests returned `26 passed, 2 warnings`; the registered selection returned `2/0/0`; frozen five selections returned `1,169/0/0`.
- Full backend at `b6ca607d` returned `10,821 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1. The five failed nodes were calibration repair contract, Task45 Godot probe, `test_cold_ready`, recovery measurement, and Task8 Godot probe. All five reproduced with the same node IDs and failure types at direct parent `15a25e07`; this was not a parent full-suite run. Final context refinement `8e6d70df` was not covered by a full backend rerun.
- P-1 branch-addition scan found zero credential hits after excluding three explicit test-fixture placeholders; the scan reported their hashes and `public=no` without emitting matched values. Evidence: `docs/verification/m3-3-scripted-mystery-case-replay-20261128.md` and `F:/paralls-verification/thread-a/m3-3-scripted-mystery-case-replay-20261128-01/p1-scan-branch-delta.log`. M3-3 remains in progress. `integration` unchanged.

### H-A-185 | M3-3 action-window durable replay | 2026-11-28

- Under the user's continuing authorization, A updated the unassigned `backend/app/gameplay/p5/investigation_conflict.py` `resolve_action_window` duplicate path to validate its durable receipt through shared `replay_duplicate`. It now verifies the transaction identity and complete ordered four-event set before the existing intent, command, role, and caller-digest checks. Code commit `4409b6fe`; no storage core or event contract changed.
- TDD RED reproduced a corrupted append result command ID being returned as `duplicate_replayed`. One first focused run had three temporary-directory setup errors because the basetemp parent did not exist; after creating the F-drive parent, the focused suite returned `54 passed, 6 warnings`. The registered selection returned `1/0/0`; frozen five returned `1,169/0/0`.
- Full backend suite returned `10,822 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1. The same five node IDs and failure types reproduced at direct parent `d96317a4` in a targeted run. The first parent command had a misspelled Task8 node and failed collection; the corrected command produced the comparison.
- Evidence: `docs/verification/m3-3-action-window-replay-20261128.md`; raw logs under `F:/paralls-verification/thread-a/m3-3-action-window-replay-20261128-01/`. M3-3 remains in progress. `integration` unchanged.
- P-1 branch-addition scan found zero credential hits after excluding three explicit test-fixture placeholders, with their hashes and `public=no` recorded without emitting matched values. Raw output: `F:/paralls-verification/thread-a/m3-3-action-window-replay-20261128-01/p1-scan-branch-delta.log`.

### H-A-186 | M3-3 InvestigationConflictAuthority resolve durable replay | 2026-11-28

- `InvestigationConflictAuthority.resolve` now routes direct duplicate retries through shared `replay_duplicate`, validating transaction identity, event references, and expected command/transaction IDs. Integrity failures retain `idempotency_key_reused` and make no writes. Code commit `0bb4b9e7`; no event contract or storage-core change.
- TDD RED reproduced a corrupted committed receipt being returned as `committed_success`. Focused P5/bakery/action-window/scripted-mystery tests returned `39 passed, 2 warnings`; registered selection `1/0/0`; frozen five selections `1,169/0/0`.
- Full backend returned `10,823 passed, 5 failed, 2 skipped, 2 xfailed`, exit 1. The same five node IDs and failure types reproduced at direct parent `1127b431` in a targeted run. Evidence: `docs/verification/m3-3-investigation-conflict-replay-20261128.md`; raw logs under `F:/paralls-verification/thread-a/m3-3-investigation-conflict-replay-20261128-01/`.
- P-1 scanned the added code and documentation lines across five credential-pattern families and found zero hits. Raw output: `F:/paralls-verification/thread-a/m3-3-investigation-conflict-replay-20261128-01/p1-scan.log`.
- M3-3 remains in progress; other direct/custom replay paths remain to inventory. `integration` unchanged. This increment does not configure production Gate numeric thresholds.

### H-A-187 | M3-3 QuestEvidenceAuthority resolve durable replay | 2026-11-28

- `QuestEvidenceAuthority.resolve` now routes direct duplicate retries through shared `replay_duplicate`, validating transaction identity, committed event references, and expected command/transaction IDs. Integrity failures retain `idempotency_key_reused` and make no writes. Code commit `9ee8eb23`; no event contract or storage-core change.
- TDD RED reproduced a corrupted committed receipt being returned as `committed_success`. Focused Quest Evidence/P5 bakery/InvestigationConflict tests returned `49 passed, 2 warnings`; registered selection `1/0/0`; frozen five selections `1,169/0/0`.
- Full backend returned `10,824 passed, 5 failed, 2 skipped, 2 xfailed`, exit 1. The same five node IDs and failure types reproduced at direct parent `0bb4b9e7` in a targeted run. Evidence: `docs/verification/m3-3-quest-evidence-replay-20261128.md`; raw logs under `F:/paralls-verification/thread-a/m3-3-quest-evidence-replay-20261128-01/`.
- P-1 scan of added code and documentation lines found zero hits across five credential-pattern families. M3-3 remains in progress; the `confirm_world_death` custom receipt path and other direct/custom replay paths remain to inventory. `integration` unchanged. Production Gate numeric thresholds remain unconfigured.

### H-A-188 | M3-3 world-death confirmation durable replay | 2026-11-28

- `InvestigationConflictAuthority.confirm_world_death` now routes duplicate retries through shared `replay_duplicate`, validating the durable transaction, event references, expected decision event type, and command/transaction identities. Existing intent payload, command, transaction, causation, and correlation checks remain. Integrity failures retain `world_death_idempotency_reused` and make no writes. Code commit `36d589c4`; no event contract or storage-core change.
- TDD RED reproduced a corrupted receipt being returned as `duplicate_replayed`. Focused ActionConsequence/LifeState caller/ActionWindow/P5 tests returned `55 passed, 2 warnings`; registered selection `1/0/0`; frozen five selections `1,169/0/0`.
- Full backend returned `10,825 passed, 5 failed, 2 skipped, 2 xfailed`, exit 1. The same five node IDs and failure types reproduced at direct parent `335e85be` in a targeted run. Evidence: `docs/verification/m3-3-world-death-replay-20261128.md`; raw logs under `F:/paralls-verification/thread-a/m3-3-world-death-replay-20261128-01/`.
- M3-3 remains in progress; other direct/custom replay paths remain to inventory. `integration` unchanged. Production Gate numeric thresholds remain unconfigured.

### H-A-189 | M3-3 Stormnight legacy-compatible action replay | 2026-11-28

- `StormnightRealtimeSessionService._replay_action` now validates the durable transaction, ordered action-window event set, sequence, and stream revisions through `replay_duplicate` before examining frozen or process-local legacy caller data. Corrupt receipts return `stormnight_player_idempotency_reused` without writes. Code commit `20934a37`; no event contract or storage-core change.
- TDD RED reproduced a corrupted `command_id` being accepted as `duplicate_replayed`. Focused Stormnight realtime/action-window/world-death/P5 tests returned `56 passed, 6 warnings`; registered selection `1/0/0`; frozen five selections `1,169/0/0`.
- Full backend returned `10,826 passed, 5 failed, 2 skipped, 2 xfailed`, exit 1. The same five node IDs and failure types reproduced at direct parent `5e178aeb` in a targeted run. Evidence: `docs/verification/m3-3-stormnight-legacy-replay-20261128.md`; raw logs under `F:/paralls-verification/thread-a/m3-3-stormnight-replay-20261128-02/`.
- P-1 scanned the code and test additions across five credential-pattern families and found zero hits. M3-3 remains in progress; this closes only the legacy-compatible realtime adapter path. `integration` unchanged.

### H-A-190 | M3-3 P5 current-tip replay lookup audit | 2026-11-28

- AST inventory at A tip `4e71754f` found four P5 methods that read durable idempotency records without directly calling `replay_duplicate`. Manual call tracing confirmed each only gates or normalizes a result, then forwards duplicate handling to an Owner/helper path that validates the receipt. The P5 adapter path audit is recorded in `docs/verification/m3-3-p5-replay-path-audit-20261128.md`; raw inventory is under `F:/paralls-verification/thread-a/m3-3-p5-current-tip-audit-20261128/`.
- All P5 direct replay-result paths inspected now route through the shared helper. A-owned migrated Owner paths also use it; the municipal certificate's special settlement-plan path has separate validation evidence.
- This is static call-path evidence, not global runtime proof. Shared storage, B/other-domain and remaining repository-wide direct/custom paths have not been qualified here. M3-3 remains in progress; `integration` unchanged.

### H-A-191 | B Information delivery and M2-2 reader boundary recheck | 2026-11-28

- Refreshed `origin/thread-b/information-replay-20261127` at `e185cfa8a97bac5c8336eff9d15fd7f7fac9f5d9`. Its three commits are not all ancestors of A, but their effective code/test changes already exist at A tip `51d88a4c47e9b92bc8cb24080d540034eecf30b3`: `a61c93ad` and `e185cfa8` are patch-equivalent, while the checkpoint-tail test file has identical blob `3203a1693227420eb76fa6ae6deff80a84808c02` to A's `400d4ff9`. `a1719826` therefore needs no duplicate cherry-pick. No changes were made to `integration`.
- On A tip, Python `3.12.2`, `app.__file__` under the A worktree, and SQLite `3.43.1` were verified. Information checkpoint/runtime/wiring tests returned `32 passed, 6 warnings`; the 26-node `siege_information` selection returned `selected=26 problems=0 improvements=0`. Raw output: `F:/paralls-verification/thread-a/information-b-recheck-20261128-01/`. Full backend and frozen five selections were not run in this recheck.
- M2-2 contract review found the current recipient-private Information reader has authoritative recipient, delivery, report, and knowledge inputs. No authoritative historical membership source or generic FactType reader mapping was identified for faction/role or other selector families. Those reads remain unavailable/unknown until their source domain supplies replayable qualification facts and revision semantics. No code or tests changed for this static classification; M2-2 remains blocked/incomplete.

### H-A-192 | M1-3 Pool current-tip regression recheck | 2026-11-28

- At exact A HEAD `72082ffd8d7bb5143fc0b2acda2e5faf7eb354ba`, Python `3.12.2`, A-worktree `app.__file__`, and SQLite `3.43.1` were verified. Pool/Facility integrity/Morale Pool focused tests returned `27 passed, 2 warnings`. Registered M1-3 Pool and domain-owner selections returned `17/0/0` and `1/0/0`; frozen ownership, modifier, equipment, inventory and shared-replay selections returned `24/12/87/56/990` nodes with zero problems and improvements. Raw output: `F:/paralls-verification/thread-a/m1-3-current-tip-20261128-01/`.
- Full backend suite was not run. M1-3 remains `待门禁`; this recheck does not close U1/U2/U5/U7/U8, production Pool scheduling, non-zero rate-bearing Pool content, or domain Resolver registration. No runtime code changed and `integration` was not modified.

### H-A-193 | M2-2 Organization temporal qualification input | 2026-11-28

- Follow-up to H-A-191: current code does contain replayable Organization membership/delegation history, resolved at a supplied `global_sequence` by `organization_garrison_roster_at`. The event payload contains organization, member, role, and delegation state but no effective world tick; the writer does not set `event_time`. Its semantics are delegation records, not an established complete roster or faction membership contract.
- `GameplayReadAs` qualifies facts at `as_of_tick`, so the existing sequence-position snapshot cannot safely establish whether a principal held a role at that tick. Required external input is an Organization-owned, replayable qualification contract with effective world-time and revision semantics, plus an explicit mapping for which `role:` and `faction:` selectors it supports. A can then implement the time-aware qualification reader and keep unsupported selectors denied. Static evidence: `docs/verification/m2-2-selector-qualification-source-audit-20261128.md`; no tests ran. M2-2 remains incomplete.

### H-A-194 | M3-3 Contract public-milling fulfillment replay integrity finding | 2026-11-28

- At A tip `5709368f1bf24b69289ced61d9a3e0a0547fad5a`, static inspection and a prior runtime reproduction found that `ContractAuthorityService.fulfill_public_milling_session_by_policy` validates only the first event in a two-event durable receipt before returning `duplicate_replayed`. Replacing the second event ID with a missing ID still returned `committed=True`, `duplicate_replayed`; raw output is `F:/paralls-verification/thread-a/m3-3-contract-r2-static-repro-20261128-01/repro.log`.
- `backend/app/gameplay/contract_runtime.py` and its domain tests are B-exclusive under `BOUNDARIES.md`; A made no code changes. B needs to validate the transaction and both ordered event references before replay success. The adjacent facility-commissioning path already loads both references, so the finding is limited to public-milling fulfillment.
- Evidence: `docs/verification/m3-3-contract-fulfillment-replay-audit-20261128.md`. No tests ran in this audit. M3-3 remains in progress pending the owning thread's fix and verification.

### H-A-195 | M6-5 production Gate numeric source audit | 2026-11-28

- Formal Architecture v2 siege-demo materials specify the `breach` meaning and four-step `impact_gate` order, but do not provide production integrity bounds, breach/reset values, or impact deltas. Test values `40` / `45` are fixtures only.
- Runtime accepts a versioned profile through `SIEGE_FACILITY_GATE_PROFILES_JSON`; the setting defaults to an empty list and validates the profile's ranges. A did not invent or configure production values. The gameplay/deployment authority must provide the target world's profile before production deployment or live siege verification.
- Static evidence: `docs/verification/m6-5-production-gate-profile-source-audit-20261128.md`. No tests ran; `integration` and deployment configuration were not changed.

### H-A-196 | M1-1 Bond formal delta and expiry scheduler audit | 2026-11-28

- Formal Bond spec §4 defines per-type closed attribute keys; the authorized M1-1 task card requested removal of that key whitelist. Current `_bond_attributes` accepts arbitrary string keys up to eight entries, so implementation follows the task card but differs from the read-only formal spec. No behavior was changed in this audit.
- The formal spec requires world-clock expiry to append `bond.expired`. `expire_bond` exists, but `rg` found no production caller; `active_bonds` filters expired terms only when queried at a supplied tick. This leaves durable scheduled expiry unverified and awaiting an owned Process/world-tick scheduler path.
- Static evidence: `docs/verification/m1-1-bond-formal-delta-audit-20261128.md`. No tests ran. M1-1 remains pending gate review; this audit does not claim the Bond lifecycle is complete.

### H-A-197 | B Information checkpoint-tail delivery rechecked on current A | 2026-11-28

- The commits on `origin/thread-b/information-replay-20261127` (`a61c93ad`, `a1719826`, `e185cfa8`) already have effective equivalents in A history. The durable knowledge `event_time` change and 26-node selection are patch-equivalent; the checkpoint-tail test has the same blob. No cherry-pick or branch merge was needed.
- After A's Population startup change, the Information checkpoint, siege runtime and production-wiring test files returned `32 passed, 6 warnings`; `siege_information` returned `selected=26 problems=0 improvements=0`. Raw output: `F:/paralls-verification/thread-a/bond-expiry-information-recheck-20261128-15/`.
- This recheck covers B's delivered Information persistence and checkpoint-tail behavior only. It does not close `read_as`, complete visibility semantics, production Gate inputs, Unreal transport or full siege execution.

### H-A-198 | M1-1 Population-confirmed Bond expiry scheduler | 2026-11-28

- A added `OwnershipBondExpiryConsumer` and wired the existing Ownership expiry authority to confirmed Population cadence pins. The bounded `ownership` temporal grant is verified before expiry processing. Legacy cadence pins are accepted only when that grant alone is absent; other pin mismatches continue to reject. Code commit `aba7dea902a7eb757aaff23b2b4f01334bac1673`; regression-test correction `616d9815053e9309e996cd81998c1c47fc2906e2`.
- A late callback records the actual confirmed processing tick, uses `term_expires_at` for due selection and stable idempotency identity, and does not backdate the event. This is an application Population-cadence verification, not live Unreal clock evidence.
- TDD comparison on parent `6276757f` produced 6 expected missing-consumer failures; current consumer tests returned 6 passed, and focused Ownership/Population/temporal tests returned 106 passed, 6 warnings. Registered Bond-expiry selection returned 10/0/0. Frozen five selections returned 1,169 nodes with zero problems/improvements. Full backend returned 10,835 passed, 6 failed, 2 skipped, 2 xfailed, exit 1. Five of the six full-run failures reproduced on the parent targeted comparison. Character recovery failed only in the current full run and passed isolated reruns on both parent and current code; its full-suite PermissionError remains unclassified. Evidence: `docs/verification/m1-1-bond-slices-20261122.md`; raw outputs under `F:/paralls-verification/thread-a/ownership-bond-expiry-*`.
- M1-1 remains pending gate review. The formal closed Bond-attribute set and the task-card-requested open key behavior still differ (H-A-196). No claim of completed Bond migration or Architecture v2 is made.

### H-A-199 | B Information checkpoint-tail current-tip recheck | 2026-11-28

- B branch `origin/thread-b/information-replay-20261127` at `e185cfa8` was compared with A. The checkpoint-tail test blob and registered selection are identical; the event-time and selection code commits are patch-equivalent in A history. The checkpoint-test commit also contains B-only documentation, so no complete B commit was cherry-picked.
- At A documentation HEAD `58f5efd8` and backend code tip `616d9815`, focused Information checkpoint/runtime/production-wiring tests returned `32 passed, 6 warnings`; `siege_information` returned `selected=26 problems=0 improvements=0`. Python `3.12.2`, SQLite `3.43.1`, A-worktree import path verified. Raw output: `F:/paralls-verification/thread-a/information-current-tip-20261128-02/`.
- Frozen five selections and the full backend suite were not run. This verifies the delivered Information persistence and checkpoint-tail path only; M2-2/U7, production Gate values, live Unreal transport, and complete siege execution remain open. `integration` was not modified.

### H-A-200 | M1-3 Pool regression recheck after Bond expiry code | 2026-11-28

- At documentation HEAD `6f84de9e` and backend tip `616d9815`, focused Pool/Facility integrity/Morale Pool tests returned `27 passed, 2 warnings`. The registered Pool/domain-owner selections returned `17/0/0` and `1/0/0`; frozen ownership/modifier/equipment/inventory/shared-replay selections returned `24/12/87/56/990`, all zero differences. Python `3.12.2`, SQLite `3.43.1`, and A-worktree `app.__file__` were verified.
- The first frozen-selection loop pointed to `docs/verification/selection/` and stopped because the frozen manifests are located in `docs/verification/absorb-main-3bf3418e/`. It ran no affected test nodes. The corrected run used the frozen baseline directory; its logs and the initial path error are retained in `F:/paralls-verification/thread-a/m1-3-current-tip-20261128-02/`.
- Full backend suite was not run. M1-3 remains `待门禁`; this recheck does not close production scheduling, non-zero rate-bearing content, domain declarations/Resolver, R1/R2/R3, or subject-facing reads. `integration` was not modified.

### H-A-201 | M3-3 Organization admitted-membership replay integrity | 2026-11-28

- Code commit `f1f6b30b`: `OrganizationAuthority.record_admitted_platform_organization_membership` now uses shared `replay_duplicate` to validate the durable transaction and committed event set before returning an exact retry. Corrupt transaction references retain `ogs_organization_membership_idempotency_reused` and produce zero additional writes. No event contract or storage-core code changed.
- Focused Organization descriptor/platform and Morale refold tests returned `25 passed, 3 warnings`; the registered selection returned `1/0/0`; frozen five selections returned 1,169 nodes with zero differences.
- Full backend returned `10,836 passed, 5 failed, 2 skipped, 2 xfailed`, exit 1. All five failed nodes reproduced on clean parent `60d206d4` in a targeted run. Evidence: `docs/verification/m3-3-organization-membership-replay-20261128.md`; raw outputs: `F:/paralls-verification/thread-a/organization-membership-replay-20261128-01/` through `-04/`.
- M3-3 remains in progress; this closes only the admitted Organization membership custom replay path. `integration` was not modified.

### H-A-202 | M1-1 Bond formal attribute contract convergence | 2026-11-28

- Code commit `8bdf01dc4539b3f67898a9c4276fa941be90bdda` restricts newly granted/superseded Bond attributes to the formal per-type key sets. Historical event projection still accepts prior extension keys, preserving old event/snapshot rebuild. Mutable obligation amount remains outside Bond attributes.
- TDD RED reproduced acceptance of `outstanding_amount` on obligation Bond. Focused Ownership/Bond/expiry/Credential tests returned `37 passed, 6 warnings`; updated M1-1 selection returned `12/0/0`; frozen five selections returned 1,169 nodes with zero differences.
- Full backend returned `10,837 passed, 5 failed, 2 skipped, 2 xfailed`, exit 1. All five failures reproduced on code parent `dbaae2c7` in a targeted run. Evidence and raw logs: `docs/verification/m1-1-bond-slices-20261122.md` and `F:/paralls-verification/thread-a/bond-closed-attributes-20261128-01/` through `-05/`.
- This follows the formal Architecture v2 attribute contract and differs from the prior M1-1 task-card instruction to remove the whitelist. M1-1 remains pending gate review; no event schema changed and `integration` was not modified.

### H-A-203 | M3-1 current-tip registered selection revalidation | 2026-11-28

- At documentation HEAD `e62ce9d8`, all 59 registered selections plus the five frozen selections completed serially: 64 invocations, 1,575 summed selected nodes including overlap, all `problems=0 improvements=0`. The source tree matches code commit `8bdf01dc`; raw outputs are under `F:/paralls-verification/thread-a/m3-1-current-tip-a5e32538/`.
- The exact source tree full backend result is separately recorded in M1-1 evidence as `10,837 passed, 5 failed, 2 skipped, 2 xfailed`, exit 1; all five failures reproduced on code parent `dbaae2c7` in targeted comparisons. This does not make the full suite green.
- M3-1 stays `待门禁`; `integration` was not modified. The B Information delivery at `e185cfa8` already has effective equivalents in A and was revalidated under H-A-191/H-A-199, so no B commits were cherry-picked.

### H-A-204 | M1-3 Morale D8 narrow rule package and M6-5 assembly | 2026-11-28

- Code commit `f76089a4` adds immutable `county_siege_morale_presence@1.0.2`, declaring the Morale Pool FactType, bounds/initial value, `casualty` distribution refold trigger, and registered `morale_refold@1`. The approved rule uses the replayable garrison living-member percentage at the casualty sequence; missing roster or LifeState remains unknown and causes no write. The package pins two decimal places with half-up rounding.
- M6-5 derives the Pool definition from the selected locked package and evaluates its registered Resolver. Existing `1.0.0` and `1.0.1` package pins remain readable, with legacy Decimal division precision preserved. The `1.0.2` content hash is `sha256:4e294533b2f45f43980a502c1d0350bca821f9541046f1620c1c7108b553674c`.
- Python `3.12.2`, SQLite `3.43.1`, and A-worktree `app.__file__` were verified. Focused M6-5/Morale/Pool/RulePack tests returned `200 passed, 6 warnings`. The updated M1-3 U11 selection has 26 nodes and returned `26/0/0`; seven other registered selections plus frozen five completed serially, for 13 comparisons and 1,259 summed selected nodes including overlap, all zero problems/improvements. Evidence: `docs/verification/m1-3-morale-rulepack-20261128.md`; raw output under `F:/paralls-verification/thread-a/m1-3-morale-package-final-20261128-02/`, `m1-3-morale-package-final-selections-20261128-02/`, and `m1-3-morale-selection-20261128-01/`.
- U1 is partial because complete Morale Owner declaration/classification was not audited; U2 and U8 are verified for this package; U3 is partial because full P-3 was not run; U4 shared mechanism use is verified on the tested path; U5 is partial with R3 open; U6 reader inventory is partial; U7 lacks a Morale `read_as` reader; U9 probe is not verified; U10 evidence is recorded; U11 selection is registered. This is not completion of M1-3. Pool integration scheduling, non-zero rate-bearing production content, full backend regression, production Gate values, live Unreal transport, and complete siege execution remain open or unverified. `integration` and deployment configuration were not changed.

### H-A-205 | M1-3 Pool event graph-projection P-3 coverage | 2026-11-28

- Code/test commit `2cbe48d5` adds seven `gameplay.pool.*` event cases to `test_domain_schema_events_are_discovered_and_projected`. Each case confirms registry discovery, `pool` domain mapping and one graph node from `HeavenlyAuthorityEventProjector`. `main.py` startup's subscription over every registered `gameplay.*` type was statically checked.
- Python `3.12.2`, SQLite `3.43.1`, and A-worktree import path were verified. Focused pytest returned `7 passed, 26 deselected, 6 warnings`. The updated M1-3 U11 selection returned `33/0/0`; frozen five returned `24/12/87/56/990`, all zero differences. Six comparisons covered 1,202 summed nodes including overlap. Raw outputs: `F:/paralls-verification/thread-a/m1-3-p3-20261128-01/`.
- U3 is verified for Pool event schema discovery and graph projection. M1-3 remains in progress: full L3 Owner declaration, R3, downstream read inventory, subject-facing reader, post-freeze declaration probe, production Pool scheduler/content and production Gate profile remain open or unverified. Full backend suite was not run; `integration` was not modified.
- Follow-up verification at backend/test tip `2cbe48d5`: the backend full suite returned `10,839 passed, 12 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1. All 12 failure IDs and categories reproduced at parent `6816a2ee`. Repository-root pytest stopped during collection because Python 3.12.2 lacks `jsonschema`; no dependency files were changed. Raw logs are recorded in the M1-3 evidence file. The full suite does not pass, and `integration` remains unchanged.

### H-A-206 | M1-3 Pool/Morale A-side reader inventory | 2026-11-28

- Static search at code/test commit `2cbe48d5` enumerated Pool stream rebuild, Morale historical-input/Pool reads, Facility integrity/Gate settlement, Pool threshold consumers in Impact obligations, Place passability and signed siege-breach validation, plus the startup graph projector subscription to registered `gameplay.*` types. Paths and read classifications are in `docs/verification/m1-3-morale-rulepack-20261128.md`.
- No subject-facing Pool or Morale query route was found in the inspected `backend/app` call graph. This is bounded static evidence; it does not establish absence of consumers outside this repository. M1-3 U6 remains partial, U7 remains open, and no runtime code or tests changed in this update.

### H-A-207 | M1-3 Pool tick integration dependency audit | 2026-11-28

- Formal RulePack/primitive provisions define tick-triggered Pool integration through `temporal_process`; the performance contract requires Pool integration and Process ticks to share one compiled loop. Current Facility Gate integrity/durability/latch and Morale packages all use `integration: none`. `PoolAuthorityService.integrate` exists but has no production caller tied to `PopulationDriver.current_tick`.
- Production integration is therefore an M1-5 Process-path dependency plus authored nonzero rate-bearing content. Existing demo/test values were not promoted or inferred. This is static-only; no runtime code or tests changed, and M1-3 remains in progress.

### H-A-208 | M3-3 Government policy registration replay receipt validation | 2026-11-28

- Code commit `dff057516187091f916519b222546036dae5d49a` replaces the custom duplicate path in `GovernmentAuthority.register_commercial_inspection_policy` with shared `replay_duplicate` validation. A corrupted transaction reference now rejects as `idempotency_key_reused`; the test asserts persisted events, outbox, and idempotency state remain unchanged after fault injection. Existing changed-policy retry rejection is preserved.
- Python `3.12.2`, SQLite `3.43.1`, and the A-worktree import path were verified. Focused policy-registration tests returned `10 passed, 2 warnings`; registered M3-3 selection `1/0/0`; frozen five selections `24/12/87/56/990`, all with zero differences. Full backend suite was not run.
- Evidence: `docs/verification/m3-3-government-policy-registration-replay-20261128.md`; raw outputs: `F:/paralls-verification/thread-a/m3-3-government-policy-replay-20261128-01/`. This closes one custom replay path only; M3-3 remains in progress and `integration` is unchanged.
- P-1 scan of 76 final staged added lines returned `patterns-scanned=5 credential-pattern-hits=0`; raw output is `F:/paralls-verification/thread-a/m3-3-government-policy-replay-20261128-01/p1-scan-final.log`.

### H-A-209 | M3-3 Government drought advisory replay receipt validation | 2026-11-28

- Code commit `e2d44b667e8c264786054c18c1780742024351b4` replaces the custom duplicate path in `GovernmentAuthority.issue_drought_advisory` with shared `replay_duplicate` validation. A corrupted transaction reference now rejects as `idempotency_key_reused`; source, causation, and correlation checks remain. The test asserts no writes after corruption injection.
- Python `3.12.2`, SQLite `3.43.1`, and the A-worktree import path were verified. Focused advisory/assessment/closed-loop tests returned `13 passed, 2 warnings`; registered M3-3 selection `1/0/0`; frozen selections `24/12/87/56/990`, all with zero differences. Exact retry after Ecology source advancement remains covered. Full backend suite was not run.
- Evidence: `docs/verification/m3-3-government-drought-advisory-replay-20261128.md`; raw outputs: `F:/paralls-verification/thread-a/m3-3-government-drought-advisory-replay-20261128-01/`. This closes one custom replay path only; M3-3 remains in progress and `integration` is unchanged.
- P-1 scan of 75 final staged added lines returned `patterns-scanned=5 credential-pattern-hits=0`; raw output is `F:/paralls-verification/thread-a/m3-3-government-drought-advisory-replay-20261128-01/p1-scan-final.log`.

### H-A-210 | M3-3 Government public workshop notice replay receipt validation | 2026-11-28

- Code commit `e1b520d17af37112239ea93c0c35695dfe66186b` replaces the custom duplicate path in `GovernmentAuthority.record_public_workshop_notice` with shared `replay_duplicate` validation. A corrupted transaction reference now rejects with the existing `public_workshop_notice_idempotency_key_reused` domain code; source activity, causation, and correlation checks remain. The regression asserts zero writes after fault injection.
- Python `3.12.2`, SQLite `3.43.1`, and the A-worktree import path were verified. Focused public notice/private follow-on tests returned `17 passed, 2 warnings`; registered M3-3 selection `1/0/0`; frozen selections `24/12/87/56/990`, all with zero differences. Full backend suite was not run.
- Evidence: `docs/verification/m3-3-government-public-notice-replay-20261128.md`; raw outputs: `F:/paralls-verification/thread-a/m3-3-government-public-notice-replay-20261128-01/`. This closes one custom replay path only; M3-3 remains in progress and `integration` is unchanged.
- P-1 scan of 75 final staged added lines returned `patterns-scanned=5 credential-pattern-hits=0`; raw output is `F:/paralls-verification/thread-a/m3-3-government-public-notice-replay-20261128-01/p1-scan-final.log`.

### H-A-211 | M3-3 Government public milling notice replay receipt validation | 2026-11-28

- Code commit `5f823c51fb34beede353acb8d9bf419df8b2f40f` replaces the custom duplicate path in `GovernmentAuthority.record_public_milling_notice` with shared `replay_duplicate` validation. A corrupted transaction reference now rejects with the existing `public_milling_notice_idempotency_key_reused` domain code; command, source activity, validity window, causation, and correlation checks remain. The regression asserts zero writes after fault injection.
- Python `3.12.2`, SQLite `3.43.1`, and the A-worktree import path were verified. Focused milling/acknowledgement/private follow-on tests returned `26 passed, 2 warnings`; registered M3-3 selection `1/0/0`; frozen selections `24/12/87/56/990`, all with zero differences. Full backend suite was not run.
- Evidence: `docs/verification/m3-3-government-public-milling-replay-20261128.md`; raw outputs: `F:/paralls-verification/thread-a/m3-3-government-public-milling-replay-20261128-01/`. This closes one custom replay path only; M3-3 remains in progress and `integration` is unchanged.
- P-1 scan of 75 final staged added lines returned `patterns-scanned=5 credential-pattern-hits=0`; raw output is `F:/paralls-verification/thread-a/m3-3-government-public-milling-replay-20261128-01/p1-scan-final.log`.

### H-A-212 | M3-3 Public project execution acknowledgment replay receipt validation | 2026-11-28

- Code commit `a47dacd0386d458cd37b7f1d3a22bed326079c55` replaces the custom duplicate path in `GovernmentAuthority.acknowledge_public_project_execution` with shared `replay_duplicate` validation. A corrupted transaction reference now rejects with the existing `public_project_execution_acknowledgment_idempotency_key_reused` domain code; execution source/revision, causation, and correlation checks remain. The regression asserts zero writes after fault injection.
- Python `3.12.2`, SQLite `3.43.1`, and the A-worktree import path were verified. Focused acknowledgment/execution/workshop tests returned `16 passed, 2 warnings`; registered M3-3 selection `1/0/0`; frozen selections `24/12/87/56/990`, all with zero differences. Full backend suite was not run.
- Evidence: `docs/verification/m3-3-public-project-ack-replay-20261128.md`; raw outputs: `F:/paralls-verification/thread-a/m3-3-public-project-ack-replay-20261128-01/`. This closes one custom replay path only; M3-3 remains in progress and `integration` is unchanged.
- P-1 scan of 75 final staged added lines returned `patterns-scanned=5 credential-pattern-hits=0`; raw output is `F:/paralls-verification/thread-a/m3-3-public-project-ack-replay-20261128-01/p1-scan-final.log`.

### H-A-213 | B Information replay delivery current-A-tip recheck and next boundary | 2026-11-28

- Fetched `origin/thread-b/information-replay-20261127` at `e185cfa8a97bac5c8336eff9d15fd7f7fac9f5d9`. A already contains the Information knowledge `event_time` writer, checkpoint-tail test, and selection through A commits `07db5404`, `400d4ff9`, and `0c3173f2`. The B branch was not merged and no duplicate cherry-pick was needed.
- At A tip `66bb91166871fb323197bf7a27016d73ddf1aa52`, Python `3.12.2`, SQLite `3.43.1`, and the A-worktree import path were verified. Focused Information tests returned `32 passed, 6 warnings`; `siege_information` returned `26/0/0`; frozen selections Ownership/Modifier/Equipment/Inventory/shared-replay returned `24/12/87/56/990`, all with zero differences. The full backend suite was not run. Evidence and raw outputs are in `docs/verification/m3-3-information-knowledge-replay-20261127.md` and `F:/paralls-verification/thread-a/information-b-delivery-current-20261128-01/`.
- Static inspection identified `OrganizationAuthority.record_public_project_execution` as a potential remaining custom retry path. It resides in `organization_government_runtime.py`, which `BOUNDARIES.md` lists as a shared fourth-wave ban. A did not modify it. The municipal certificate path in A-owned `ownership_runtime.py` already calls `replay_duplicate`; M3-3 remains in progress for other-owner and shared paths.
- P-1 scanned the added coordination and evidence lines across five credential-pattern families: `patterns-scanned=5 credential-pattern-hits=0`; raw output is `F:/paralls-verification/thread-a/information-b-delivery-current-20261128-01/p1-scan.log`.

### H-A-214 | M1-3 Pool checkpoint-free state digest recheck | 2026-11-28

- Test commits `d9f1206aad287fcc7672374a649abde53b3eb5c6` and `b398cddf3c7a784c2560e28880642619b5485afc` update the Pool rebuild regression. It checks the durable snapshot has no projection checkpoints, closes/reopens the existing SQLite event ledger, fully rebuilds Pool state, and compares a canonical state digest.
- Python `3.12.2`, SQLite `3.43.1`, and A-worktree `app.__file__` were verified. Pool tests returned `19 passed, 2 warnings`; M1-3 Pool selection `33/0/0`; frozen selections Ownership/Modifier/Equipment/Inventory/shared-replay `24/12/87/56/990`, all zero differences. Full backend suite was not run.
- This verifies Pool's checkpoint-free reconstruction path. No Pool checkpoint existed to physically delete; checkpoint deletion for other M1-3 consumers remains unverified, so U5 remains partial and M1-3 stays in progress. Evidence: `docs/verification/m1-3-pool-r3-checkpoint-free-20261128.md`; raw outputs: `F:/paralls-verification/thread-a/m1-3-pool-r3-checkpoint-free-20261128-02/`. `integration` was not modified.
- P-1 scanned both test commits across five credential-pattern families; each returned `patterns-scanned=5 credential-pattern-hits=0`. Raw outputs: `F:/paralls-verification/thread-a/m1-3-pool-r3-checkpoint-free-20261128-01/p1-code-scan.log` and `F:/paralls-verification/thread-a/m1-3-pool-r3-checkpoint-free-20261128-02/p1-code-scan.log`.
