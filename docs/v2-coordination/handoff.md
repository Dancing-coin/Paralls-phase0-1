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
- 规范 `owner_id` 使用 Architecture v2 的短名单词。22 个 Architecture v2 Owner 作为规范名称登记；`Credential` 仅为旧规则包兼容条目，不构成新 Owner；`Combat` 暂不登记，等待 S-1；`Economy / Market` 被拒绝，规范名称为 `Economy`。
- 申报代码与测试 SHA：`4b876f3d4dd92deba72aa2b49685fa4c39920ce2`；M0.5 本轮按路径提取，排除 Bond/Credential runtime 与 M1-1 内容。定向 validator 测试：37 passed，2 warnings；不是 Owner 迁移完成声明。
- M0.5 合入 SHA：`9e0ff06c`；最终 integration tip 与标签记录在 `daily/2026-11-22.md`。

### H-B-001 | 回应 H-A-015 的守城域依赖 | 2026-11-23

- 在 B 的 `2d6c2511` 与 A 的 `691792c7` 分别核对。B 已合入的 LifeState 提供 `gameplay.character.life_state_changed`（`backend/app/gameplay/life_state_runtime.py:19,25`）。守城仍需要可信队伍目标解析与 Morale 的 `recompute_morale` 处理方。现有 `backend/app/gameplay/relationship_private_estimate.py:29,43,81` 处理角色私有估计，队伍 Morale 的生产写入和可信输出映射未交付。
- Presence 已有角色 spawn/despawn（`backend/app/population_continuity/presence_runtime.py:88,118,169`）。`rg -n '(^|\.)presence_runtime import' backend/app` 命中 4 个文件：`main.py:165`、`population_continuity/activation_presence.py:15`、`population_continuity/identity_continuity.py:15`、`gameplay/soul_presence_sources.py:9`。当前门闩/设施破口触发所需的 `reevaluate_passability` 命令未找到。环境占用层已有区域通行性推导，见 `backend/app/world_runtime/l1_occupancy.py:169,294`，守城仍缺 Facility 破口提交至 Presence 命令回执的链路。
- Information 的 ReferenceData 单元为数据集许可与生命周期（实现 `e8c13651`，待门禁），见 [证据](../verification/reference-data-20261123/evidence.md)。已定位的相邻能力是 SocialDelivery 的 `gameplay.social.delivery_recorded@2` 与收件人查询（`backend/app/gameplay/p5/social_delivery.py:23,73,246`）。现有生产调用方围绕政府公共磨坊通知（`backend/app/gameplay/p5/social_delivery_caller.py:23,27,63`）。Information 报告送达、收件人知情变化与 `update_knowledge` 可信输出尚未交付。复用这条路径前须核对 Social 与 Information 的事实归属及历史事件兼容性。
- 在当前 B 源码和包中，`rg -n 'recompute_morale|reevaluate_passability|report_delivered|update_knowledge' backend/app packs` 返回 1，零匹配。该检查覆盖字面名称，邻近能力见上。三个守城目标均未形成可按现有条件直接开工的独立迁移单元。Morale 和 Information 尚需明确现有可迁移的写入切片，Presence 的现有候选超出两个生产导入者。生产 Gateway 处理方及可信输出登记和 Workflow 持久义务仍依 H-A-015 确定。

### H-B-002 | 交付守城 LifeState 触发合同，登记生产域前置 | 2026-11-23

- A 可用集成提交 `94c979998803bf52d24d8a8a8288caebdf1f4db4` 中的 LifeState。`casualty_to_morale` 的声明触发条件可采用 `on: {fact_type_pattern: "fact:character:*:lifestate", transition_to: dead}`。A 的 `691792c7:backend/app/gameplay/l5_reaction.py:69–75` 对 `event_type` 与 `transition_to` 二选一。生产绑定可在已提交的 `gameplay.character.life_state_changed` v2 上读取 `to_state == "dead"`，据 `actor_ref` 寻找队伍。死亡 payload 另含 `from_state`、`source_confirmation_event_id` 和 `source_confirmation_revision`。见 [`life_state_runtime.py:19`](../../backend/app/gameplay/life_state_runtime.py#L19)、[`life_state_runtime.py:214`](../../backend/app/gameplay/life_state_runtime.py#L214)。
- 可信来源可从已提交的 `AppendBatchResult.committed_event_ids` 在同一 EventStore 取回。outbox 向权威总线发布时，`event_type` 取 outbox topic，`event_id` 在事件头及 `payload` 中，`stream_id`、`stream_revision`、`transaction_id` 和 `global_sequence` 在 `payload` 外层，域字段在 `payload["committed_payload"]`。这条 outbox 的 audience 为 `project`，routing 为 `authority`。见 [`life_state_runtime.py:367`](../../backend/app/gameplay/life_state_runtime.py#L367)、[`dispatcher.py:102`](../../backend/app/gameplay/dispatcher.py#L102)。A 负责在 Gateway 和 L5 对接中登记命令处理方及可信输出来源。
- 定向验证用 Python 3.12.2，`app.__file__` 在 B worktree。在 `af3d7523` 执行 `python -m pytest backend/tests/test_life_state_case_death_caller.py::test_committed_life_state_event_reaches_registered_graph_projector`，结果 `1 passed, 2 warnings in 0.65s`。测试覆盖死亡提交、FactType 事件登记、持久 outbox、内存总线与图投影。对 `origin/integration` 比较对应 runtime、dispatcher、包和测试，无路径差异。原始日志在 `F:/paralls-verification/thread-b/siege-life-state-07694846/pytest.log`。生产 Gateway 至 Morale 写入与守城端到端探针尚待接线验证。

| 守城路径 | B 可交付的域合同 | 生产实现的前置 |
|---|---|---|
| `casualty_to_morale` | `Morale` 的 `recompute_morale` 处理方、`fact:unit:*:morale` 候选事实和可复核的提交回执。 | 《守城 Demo 的组合定义》§二.1 要求 `morale_relevant_casualty@1` 与 `group_of(subject)`。需确定死亡发生时读取的权威队伍成员事实及 revision，并落实《聚合与精度》§Morale 的 `distribution` 与 refold 重算规则。现有 `relationship_private_estimate.py:29,43,81` 保存的是角色私有估计。 |
| `gate_breach_to_presence_reeval` | `Presence` 的 `reevaluate_passability` 处理方、独立的通行性提交与回执。 | 《守城 Demo 的组合定义》§二.2 以 Facility 已提交的完整度破口为输入。需确定源 FactType、事件及 revision 边界，并确认现有 `l1_occupancy.py:169,294` 通行性推导如何供 Presence 使用。现有 Presence spawn/despawn 有四个生产导入者，落点见 H-B-001。 |
| `report_arrival_to_knowledge_update` | `Information` 的送达事实、按收件人隔离的知情变化以及 `update_knowledge` 处理方。 | 《守城 Demo 的组合定义》§二.6 要求送达后才进入收件人投影。`p5/social_delivery.py:23,73,246` 可供核对现有收件人读取及 `gameplay.social.delivery_recorded` v2。需确定 SocialDelivery 与 Information 的报送边界及历史兼容合同。 |

- 提请负责人把守城 Morale 的最小生产合同列为 B 的下一单元。验收样本覆盖已提交死亡、权威队伍定位、一次 `recompute_morale`、重复投递无重复写入和回放结果一致。当前迁移规格的范围条款排除变更领域规则，队伍权威来源与数值规则需据已有合同确定，若需新增玩法规则则由负责人裁定。Facility 与 Information 可在各自前置合同确定后独立推进。M6 Gateway、可信命令输出登记和 Workflow 持久义务仍见 H-A-015。

### H-B-003 | 守城 Morale 声明探针与生产依赖 | 2026-11-23

- A 可从 [Morale 域合同](../verification/siege-morale-20261123/design.md) 读取反应声明、可信输出样例和域侧回执设计。B 用 A 的 `691792c7` 编译器和 B 已提交的 LifeState 死亡事件验证。定向共 4 passed，含实际 outbox 和图投影。样例准备好供 A 测试登记与触发字段接线，生产队伍事实和 Morale writer 待落实。
- 请 A 核对 Gateway 的可信输出登记与生产 `Morale` domain 映射。`aggregate_pool_values` 的 `casualty` 触发实测拒绝，B 另验证可用现有 `PoolAuthorityService.adjust` 承接域内重算结果，提交时校验源 revision，原样重试返回原提交。Pool 定向 2 passed，生产域 Resolver 和写入入口仍依 D8。
- B 的生产侧等待两项领域依据。Organization 可重放的守军队伍成员来源，以及 D8 的士气重算规则。现有班表成员事件没有守军编制合同。设计已给出只用于守城评审的伤亡比例样本和固定测试向量。

### H-B-004 | 守城三条域路径进展及 A 接线请求 | 2026-11-23

- 三路径核查与证据见 [设计和状态](../verification/siege-three-paths-20261123/design.md)。board.md 已拆成 Morale、Presence、Information 三项。B 未把共享 Gateway 或不存在的上游事件伪装成已交付。
- **Information 已实现 B 域 writer**：新增 backend/app/gameplay/information_runtime.py、information_event_schema.py 和 backend/tests/test_siege_information_runtime.py。输入严格校验 SocialDelivery 的已提交 gameplay.social.delivery_recorded@2，recipient、当前可见性、撤销、delivery 交易/idempotency receipt。输出 gameplay.information.knowledge_updated@1 带 recipient 可见性；CAS 同时读 delivery/source stream，精确重试不重复写。用真实 outbox 到 Heavenly Graph 投影器验证。Python 3.12.2 下新测试 5 passed；连同两条 SocialDelivery 行为测试 6 passed。日志在 F:/paralls-verification/thread-b/siege-three-paths-preflight-20261123/information-green2.log。
- 请 A 在共享 event_schema_registry.py 的生产 EventSchema factory 注册 register_information_event_schemas。gameplay_schema_event_types() 已可扫描该域 schema 模块；测试只证明本地工厂和图投影路径，不证明生产 factory 已接通。Gateway/L5 触发候选是 Social delivery v2 event，命令候选 information.update_knowledge；输入须绑定 delivery_event_id、recipient、known tick、目标 revision。输出候选 fact:information:<report-scope>:report，其精确 scope 和目录由 A 按正式 FactType 与命令域映射接线。此 handoff 是 A 修改独占文件前的同步，不授权 B 改该文件。
- **Morale 未完成**：LifeState 触发链已核验；A Pool 适配在 origin/thread-a/ownership-bond-followup-20261121，当前 B integration 无 pool_runtime.py。Organization 的 membership_delegation_recorded@1 是守军名单候选，但没有守军编制与角色定义。D8 的 refold 算法也未裁定。四人名单 1 人死亡得 75 仅是评审向量，不是已采用规则。A 可先读既有 [Morale 候选与 Pool 探针](../verification/siege-morale-20261123/design.md)。
- **Presence 未完成**：B 当前代码与 schema 未找到设施 integrity breach 事件或生产 writer；Construction Production 的可见 condition 变化是 acquisition/repair，repair 增加 condition。M6-5 不能据此触发。请 Facility/生产源 Owner 提供已提交 breach FactType/event/payload/revision，Presence 才能独立评估与提交通行性。
- A 接 Information 后若需要 A 或 B 合并作验证，合并执行者先核对申报 SHA、claims、P-1 和门禁。当前 Information 没有新增生产 Gateway 接线、U11 选择集比较、全量回归或 M6-5 端到端验收声明。

### H-B-005 | Information writer 验证完成，Morale/Presence 输入未具备 | 2026-11-23

- Information 本地提交候选在本分支 `155d496c7d26ab0b8f49f67805a2cce728a29692` 之后的未提交工作区中，包含 `information_runtime.py`、`information_event_schema.py` 与域测试。U1–U11 状态、精确命令、测试结果、选择集、全量覆盖与缺项见 [证据](../verification/siege-three-paths-20261123/evidence.md)。当前修改尚未提交，因此交 A 时先等 B 推送后读取具体 SHA。
- 定向 pytest：`50 passed, 2 warnings`。冻结五组选集 24/12/87/56/990，LifeState 12、ReferenceData 15、Information 10 节点均 `problems=0`。U11 P-3 参数化节点现以三个真实事件 ID 登记。
- 全量单次 G0 runner 未产生最终 `results.json`，不计全量通过。本轮随后按冻结的 1,069 个测试文件清单串行分 11 批，覆盖 10,448 个唯一节点；24 failed、4 skipped。24 个失败均为 22 个冻结基线失败及 `test_cold_ready`、`test_recovery_owner_probe_measures_original_startup_before_full_oracle` 两个已在 integration 基线重现的失败。本次没有观察到新增失败。日志和每批结果位于 `F:/paralls-verification/thread-b/siege-three-paths-20261123/`。P-1 输出 `tracked_model_secret_offender_count=0`。
- A 接线清单：在生产 EventSchema factory 调用 `register_information_event_schemas`；按 A 的 Gateway/L5 约定，将已提交 SocialDelivery v2 送达事件触发 `information.update_knowledge`；把命令可信输出映射到经规范确认的 Information FactType，并保留 recipient scope。域声明实现和 projector 测试不表示生产 factory/Gateway 已接通。
- Morale 仍需 Organization Owner 给出可回放的守军成员事实和 D8 重算合同。Presence 仍需 Facility Owner 给出已提交 breach FactType、事件 payload 与 source revision。收到这些输入后 B 才能完成对应域 writer。此条不宣称三条守城生产路径完成。

### H-B-006 | G5 因外部进程凭据停止 | 2026-11-23

- 按 F 盘临时目录重跑冻结选择集时，`shared-replay` 中两个节点因 `127.0.0.1:8000` 被未健康的外部进程占用而失败。监听进程 PID `23536`，映像为 `F:\Epic\UE_5.9\Engine\Binaries\Win64\UnrealEditor.exe`。没有终止或修改该进程。
- 检查占用端口的进程命令行时发现认证凭据参数。凭据值未复制到仓库或本记录；来源为外部进程命令行，具体凭据公开状态未核实。按 `AUTONOMY.md` §二凭据发现停止条件，B 停止进一步扫描、提交和推送。项目负责人需处理凭据并释放/协调端口占用后，再恢复 G5。
- 之前使用默认 `TMPDIR=D:\codex-temp\user-temp` 的 pytest/G5 输出仅作诊断，不作为本单元门禁证据。本轮已确认的 F 盘 TMPDIR 定向测试为 `50 passed, 2 warnings`；F 盘 TMPDIR 的 shared-replay 比较未通过，其他尚未执行的选择集不记通过。对应目录见 `F:/paralls-verification/thread-b/siege-three-paths-20261123/verified-f-temp/`。
- 单元代码仍未提交。不要将本条当作已交付 A 的实现 SHA。

### H-B-007 | Information 域 writer 已推送供 A 接线 | 2026-11-23

- 项目负责人要求继续推进后，B 完成并推送自己的分支 `thread-b/reference-data-20261123`。可用最终树 SHA：`6741ab6115d5c280390aaba162fa1e109f6064e3`；远端分支已核验为同一 SHA。**请 A/合并执行者读取分支最终树或该 SHA，不要单独消费中间提交 `abba3c3c2187b886db5ddb7727be9e8f2dc23162`**，该中间树的事件 schema 文件末尾曾有语法错误，后续 `6741ab61` 已修复并复验。
- 定向测试在最终代码内容下使用 F 盘 `TEMP`/`TMP`/`TMPDIR`：`50 passed, 2 warnings`。Information U11：`selected=10 problems=0 improvements=0`。P-1 tracked scan：`tracked_model_secret_offender_count=0`。相应命令与输出见 [证据](../verification/siege-three-paths-20261123/evidence.md)。
- 请 A 接入 `register_information_event_schemas` 到生产 EventSchema factory；以 `gameplay.social.delivery_recorded@2` 触发 Gateway/L5 命令 `information.update_knowledge`；确认 recipient-scoped 输出 FactType 的精确 scope、visibility 和可信输出映射。B 没有改 A 独占的 registry、Gateway、L5 或 `main.py`。
- 冻结五组选集尚未全过：F 盘 TMPDIR 的 `shared-replay` 两例因外部 UnrealEditor 占用本地端口 8000 失败。全量门禁未完成。合并执行者不要据此条声明 G5 通过。
- Morale 和 Presence 尚无可交付 writer。Morale 等待可回放的守军成员事实及 D8 重算合同；Presence 等待 Facility 已提交 breach 事件与 source revision。A 当前可接 Information，不能据此宣称完整 M6-5 守城路径完成。
- 本轮在 shared-replay 端口诊断中确认外部 UnrealEditor 命令行含认证凭据，值未记录、公开状态未核实；未改动该进程。项目负责人继续处理该环境事项。此信息不属于仓库或分支内容。

### H-B-008 | 更正 B 分支最终 tip | 2026-11-23

- H-B-007 中 `6741ab6115d5c280390aaba162fa1e109f6064e3` 是 Information 代码修复提交；之后还有交接与证据文档提交，因此该 SHA 之后的文档提交会继续移动分支 tip。
- A 使用 `git fetch origin` 后，读取当时的 `origin/thread-b/reference-data-20261123` 最新树即可。该分支包含 Information 代码修复和本 handoff；合并/验收沿用 AUTONOMY G1–G7。B 没有合入 integration。
