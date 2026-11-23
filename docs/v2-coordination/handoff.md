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
