# 角色、群体与社会因果运行时整合规格

日期：2026-09-18。

组织修订：`2026-09-18-r2`。本轮按用户要求生成两份实施计划及人员分工；模块与事实所有权仍由本规格定义。

状态：`draft_for_review`。本文件是本次文档整合产生的主 spec 草案，不是实现完成记录，不授权运行时代码变更，也不自动取代原有已确认基线。正文中“必须”表示拟议验收合同；新增裁决在第 18 节单独列出，不能当作用户此前已批准的决定。

核查工作区：D:/Paralls-phase0-1；原整合分析基准为 main / bb3ea2bb，生成两份计划时补查 HEAD 83fa2b33。本次核查为静态文档和代码检查，未运行 pytest、Harness、Godot 或开源参照项目。

## 1. 文档权威与生成方式

主 spec 以系统目标、事实所有权、共享合同和因果闭环组织内容。实施计划按模块依赖与可验证结果派生；本轮采用用户要求的两份 plan，由人员甲、乙分别负责运行时连续性基础和角色模块/领域纵切。人员分工不反向改变架构。两份计划引用同一份共享合同，不得另写一套模拟帧、角色游标、Owner 回执或 Character Core 接纳语义。

本次先生成独立整合草案，原因是范围同时包含 9/16 连续性基线、社会模型编译器、具身因果及阵营后继。草案通过设计评审后，文档整合时选定一个唯一入口：将本稿并回 9/16 中文主文档，或将本稿定为新主 spec 并把原文标成历史基线；不得把两个相互覆盖的文件同时标为有效主规格。

原 9/16 英文文档保持其历史范围；本中文整合稿不声称英文版已同步。分工参考中的旧工作区绝对路径只用于识别材料，实际实现路径以当前仓库为准。

### 1.1 来源登记

| 编号 | 来源 | 本稿用途 |
| --- | --- | --- |
| S1 | [角色与群体模拟增量设计（中文）](2026-09-16-角色与群体模拟增量设计-中文版.md)及[英文基线](2026-09-16-character-population-simulation-incremental-design.md) | B0–B3、参与策略、模块、成员账本、交接、协议、密码本及阶段 0–7 |
| S2 | [受约束社会模型编译器附件](/D:/MyConfiguration/TCLXUSER/Downloads/2026-09-17-受约束社会模型编译器设计-中文版.md) | 受信模板、授权、冻结输入、封闭 IR、候选、回放与分级启用 |
| S3 | [具身因果与阵营附件](/D:/MyConfiguration/TCLXUSER/Downloads/2026-09-17-具身因果交替推进与阵营对抗域设计.md) | 证据确认、影响摘要、旧候选失效、局部反应与阵营隔离 |
| S4 | [用户提供的拆分参考](/D:/MyConfiguration/TCLXUSER/.codex/attachments/1f6964a0-5072-4f31-8e4a-2f7e97319aa6/pasted-text.txt) | 本轮两份 plan 与甲乙职责的组织参考；架构、合同与事实范围仍按原设计和当前源码校准 |
| S5 | [主线总设计](2026-06-29-world-character-siming-authority-mainline-master-design.md)、[角色种子与连续性](2026-08-22-character-simulation-memory-seed-continuity-design.md)、[司命治理](2026-08-29-siming-led-population-simulation-design.md)、[通用群体决策面](2026-09-01-siming-generalized-population-decision-surface-design.md) | 保留主线权威边界、现有连续性、候选治理与单一司命入口 |
| S6 | [事实上抛与多模态链路](../../../架构/事实上抛链路与多模态链路.md)、[Owner operation 基线](2026-08-26-owner-operation-conflict-matrix-baseline.md) | 复用感知 identity 和能力准入，不发明通用事实写入口 |
| S7 | [本次项目及开源对照](../../../reference/2026-09-18-social-simulation-open-source-comparison.md) | 区分现有实现、待补合同与算法借鉴 |
| S8 | [六项生产工程闭环](../2026-09-16-population-production-runtime-closure-design.md) | 既有生产化依赖，避免与本稿重复建执行隔离、恢复、性能或 CI 任务 |

S2、S3、S4 为本机附件，跨机器交接时必须一起提供可核对的原文。生成实施计划时以本稿的已确认修订为共享合同，不把附件中的执行指令直接当成实施授权。

来源取舍遵循：当前用户要求与仓库运行边界优先；S1/S5 定义连续性基础，S2/S3 在各自范围扩展；当前源码用于识别已有能力与迁移缺口，不把现状局限误写成最终目标；开源实现用于验证机制与复用机会，不替代本项目的业务规则；S4 仅是组织和验收表达的辅助参考。

### 1.2 整合方法

1. 先把来源中的要求映射到目标、合同、状态机和验收编号，去掉重复描述。
2. 用当前源码校正“已有”“可复用”“缺失”和旧适配器的真实结算范围。
3. 对冲突给出明确的拟议裁决，保留来源与理由，不通过拼接原文掩盖差异。
4. 用一个贯穿样板验证所有接口能衔接，按合同依赖定义扩展阶段；人员分工在计划层再确定。
5. 每条要求关联来源、负责模块和验收编号，确认覆盖与冲突后派生可执行 plan；后继章节保留实施门禁，不提前生成其代码任务。

## 2. 目标、范围与非目标

### 2.1 目标

在现有 world-character-Siming-authority 主线上，让同一角色以 B0 群体压缩、B1 简易模型、B2 局部增强和 B3 角色智能体四种方式连续推进。角色或玩家提出意图，社会模型提供受约束候选，领域协议与 Owner 确认结果，Character Core 接纳连续性，Godot 展示结果并提供获权具身证据。

首个贯穿样板固定为：农民 → 村庄 → 洪灾压力 → 玩家接近 → 同一角色交接 → 供应或避难相关协议 → 回执与角色连续性。不同阶段对“协议已完成”的声明必须精确到实际确认的事实。

### 2.2 里程碑边界

| 范围 | 交付含义 | 不可提前宣称 |
| --- | --- | --- |
| C：9/16 基线阶段 0–7 | 帧、参与策略、模块、账本、交接、协议、密码本及批量优化具备独立证据 | 完整社会或文明模拟 |
| M：社会编译器 | 固定模板对冻结输入做纯计算，按 shadow/advisory/active 接入既有推进者 | 任意社会规则、动态代码或新领域写权限 |
| E：具身因果后继 | 具身证据经 Owner 确认后，拒绝旧依赖并触发局部反应 | 客户端物理直接成为世界事实 |
| F：阵营对抗后继 | 同一世界内按授权隔离情报、目标和决策，使用共享领域裁决 | 每阵营一套世界、时钟或通用裁判 |
| P：生产工程 | 复用 S8 的执行隔离、恢复、真实负载、Godot、搬运和 CI 验收 | 用后端短窗数据证明产品整体完成 |

E 的代码计划必须等待 C 的阶段 0–7 全部完成且有独立证据。这是 S3 的既有门禁，本稿不将它降为“部分合同存在即可”。E 不额外强制依赖完整 M：直接结构化意图也可走具身路径。

### 2.3 非目标

- 不新增 Population Truth Owner、Situation Truth Owner 或文明真相库。
- 不新增第二套 runtime、clock、scheduler、event store、event bus、万能 router 或 generic settlement coordinator。
- 模块、模型、Siming、图谱和 Godot 不直接写库存、账户、关系、法律、人口、空间或角色私有记忆。
- 组织、市场和政府不因此获得角色式独立意志；新增目标仍需角色、代表、表决、规则或有效授权来源。
- 不让所有 NPC 后台持续运行完整 LLM，不用性能优化复制角色真相。
- 不运行玩法包携带的动态 Python、自由公式 DSL、动态 schema 或未登记可执行插件。
- 不把职业、家庭、地区、普通意见分歧、LOD 或一次遭遇自动解释为新阵营。
- 不扩大到完整战争经济、多场景叙事或文明模拟，也不宣称 INF-4 整体完成。

## 3. 当前实现与复用边界

| 当前实现 | 可复用内容 | 本稿要求补齐 |
| --- | --- | --- |
| [GameplayEventStore](../../../../backend/app/gameplay/event_store.py) | 原子 batch、读写 revision、幂等、outbox、回放 | 确保新候选的完整读依赖到达提交点 |
| [SimingRuntime](../../../../backend/app/services/siming_runtime.py)与[群体能力](../../../../backend/app/services/siming_population_capability.py) | cadence 消费、候选治理、能力目录、回执 | 消费同一参与策略，接入获权模型运行及后继 impact |
| [连续积分](../../../../backend/app/population_continuity/continuous.py)与[热状态](../../../../backend/app/population_continuity/hot_state.py) | 有界数值推进、版本化读取、到期索引 | 模块聚合规则、成员保护、分片、个人安全物化 |
| [角色种子合同](../../../../backend/app/character_agent/models/simulation_seed.py) | 连续性命令、模块增量、记忆候选和回执 | 统一模拟帧、交接与新模块接纳 |
| [冻结来源](../../../../backend/app/population_continuity/source_inputs.py) | provenance、digest、revision 校验 | 统一用途授权、FactCard/Proof 和历史审计读取 |
| [激活](../../../../backend/app/population_continuity/activation.py) | 已有锁、pending、release 与回执 | 四层推进的交接过程、旧执行者失效和恢复 |
| [具身授权与结算](../../../../backend/app/services/embodied_authority_settlement_service.py)及[证据账本](../../../../backend/app/services/embodied_evidence_ledger.py) | 执行 grant、上报验证、具身过程证据 | 按操作接到确认事实、影响摘要和完整依赖检查 |
| [Archive Door 路径](../../../../backend/app/services/default_scene_archive_door_embodied_service.py)与[ESM](../../../../backend/app/services/esm_service.py) | 门接触验证、ESM 状态与表现结果 | 该兼容路径需明确事实流、revision、receipt 和 impact 映射 |

这些复用点不代表新合同已完成。本稿中的逻辑合同名也不要求机械地创建同名新类；plan 应说明如何扩展或组合现有类型，避免平行 DTO 与重复校验。

## 4. 唯一所有权与推进入口

| 数据或操作 | 唯一接纳职责 | 其他模块允许行为 |
| --- | --- | --- |
| 身份、连续性、模块状态、角色状态游标 | Character Core；档案仍按既有 profile 规则管理 | 读取获权投影，提交带版本候选 |
| 私有记忆及物化游标 | Character Core 私有记忆链 | 提交有暴露依据的 memory candidate |
| 库存、账户、关系、组织、法律、空间、环境事实 | 对应已登记 Domain Owner | 通过能力和协议提出请求 |
| 群体计算 | PopulationPlanner/受信纯算子 | 计算统计、分片、候选与风险 |
| 成员账本 | 既有连续性链保存的索引、锚点与消费凭据 | 定位成员，不能成为新的个人事实接纳者 |
| 仿真时间与常规 cadence | 现有 world_runtime、SimulationClock、PopulationCadenceDriver | 消费时间窗口，不能另起时钟 |
| 司命决策、预算治理与派发 | SimingRuntime.tick() | 其他调用者提供结构化输入 |
| 本地具身、输入与表现 | Godot | 提交证据，消费确认或明确标注的预测 |

“SimingRuntime.tick() 是唯一入口”仅指司命决策与派发，不把 world runtime 的时间推进职责迁给 Siming。B3 仍有自己的既有角色认知路径；共享参与策略与锁不意味着每次角色思考都新增一次 Siming 调用。

## 5. 统一推进链与一致性

```text
Character Core + 获权领域投影
  -> CharacterSimulationFrame + ParticipationResolution
  -> B0/B1/B2 模块或 B3 角色智能体
       -> 可选：获权社会模型计算，返回候选
  -> 原推进主体选择 ModuleProposal / ActionIntent
  -> SimulationCommitPacket / 已登记协议
  -> Owner 校验完整读依赖并原子提交
  -> OwnerReceipt -> CharacterContinuityCommand/Receipt
  -> 投影、账本消费记录、下一帧、Godot

后继具身路径：
已准入尝试 -> 执行 grant -> Godot 证据
  -> Owner 确认 -> 同一事实链
  -> ConfirmedImpactSummary -> 旧候选不可提交 + 有界局部反应
```

### 5.1 时间与版本

- simulation tick、Owner stream revision、Character Core revision、状态游标、记忆游标分别表示不同事实，不得相互代用。
- 新的连续推进合同使用 `(from_tick, to_tick]`：前边界已消费，后边界到期事项属于本次窗口。跨窗重复由游标与幂等身份拒绝；旧事件的区间语义不追溯修改。
- source_revision_vector 保存所读来源版本；simulation_tick_cursor 表示角色已接纳到哪里。推进时间不自动使来源 revision 增长。
- 候选引用的道路、容量、库存、规则和授权等依赖必须映射到实际可校验的来源，不能只检查即将写入的目标流。

### 5.2 冻结输入与提交重验

在既有串行写入执行域或已登记一致性读取边界组装输入：签卡后重新核验全部必需来源 pins，拒绝拼接互不相容的来源。编译在不可变输入上运行。原推进主体采纳时，仍携带原 read-set；Owner 在 append 前重验所有影响请求合法性的来源版本。

不得以“重新读取当前 head”替换旧 expected revision 后继续提交原候选。当前 [Inventory output-custody adapter](../../../../backend/app/population_continuity/inventory_owner_adapter.py)读取目标当前 revision 的既有用法必须按原场景保留边界，不能直接复制为新模型的冻结输入语义。

impact 索引、失效通知与缓存作废用于及时反应。即使通知延迟、断线或反应预算耗尽，提交重验仍须保证旧依赖不能写入。历史权限的摘要 pin 也不能替代当前动作权限校验。

### 5.3 原子性、重试与零写入

- 每个原子 batch 内，读依赖检查、写入和幂等结果按既有 store 合同生效。
- 多阶段社会协议分别保留已确认阶段；后续被拒不能抹除前阶段事实，补偿只能是已登记操作。
- `zero_write` 指本次被拒操作未产生新的权威业务效果；允许保留获权审计。它不声称整个历史流程从未写入。
- 同主体、同操作、同幂等键、同规范载荷返回原回执，不重复事实；同键不同载荷硬拒绝。
- Owner 成功而 Character Core 尚未接纳时，保留原 receipt 并通过既有恢复路径补交连续性，不再次执行世界操作，不提前更新角色完成状态。

## 6. 共享合同目录

以下是逻辑最小字段与约束。字段可映射到既有类型；一份版本化合同只能有一个负责定义的工作包。引用字段必须能追到已准入来源，不能接受调用者任意指定 stream 或 event family。

新合同公共约束：明确 schema/definition version；scope、purpose、来源 pins 和幂等身份可验证；拒绝未声明字段；数值必须有限并满足字段范围；规范化排序与 digest 规则固定版本。字符串标识不应擅自改写现有 actor/profile ID 语法。

### 6.1 基线合同

| 合同 | 最小字段 | 生产者 → 消费者及不变量 |
| --- | --- | --- |
| CharacterSimulationFrame | actor_ref、profile_ref/profile_revision、character_core_revision、simulation_tick_cursor、source_revision_vector、module_states、domain_fact_refs、situation_ref、participation_resolution、codebook_refs、activation_lock_ref、frame_digest | 既有读取装配路径 → 模块/角色/获权 Siming；只读输入，不持有完整私有记忆副本 |
| ParticipationResolution | allowed_tiers、recommended_tier、allowed_modules、forbidden_dimensions、upgrade_triggers、b0_expiry_tick、review_tick、policy_revision、来源策略 pins、status | 统一策略解析 → 所有推进主体；status=resolved 时推荐精度在允许范围；无合法精度时 status=defer 且 recommended_tier 为空；冲突取更严格硬边界 |
| ModuleProposal | proposal_ref、actor/cohort_ref、module_ref/definition_version、frame_digest、proposal_kind、typed_payload、read_dependencies、required_fidelity、expiry、来源与幂等身份 | 模块 → 原推进主体；只允许声明的字段和输出，不直接调用 Owner |
| SimulationCommitPacket | actor/cohort_ref、from_tick/to_tick、expected_character_revision（个人路径）、source_revision_vector、proposal_refs、owner_intent_refs、lock_ref（个人推进）、scope、幂等身份 | 原推进主体 → 既有提交链；是请求组合与校验信息，不是新结算协调器 |
| PopulationMemberLedger | cohort_ref、成员来源与版本、situation/ruleset/partition/distribution pins、seed、group_cursor/checkpoint、member_entries、receipt_refs | 既有连续性链 → 聚合与交接；仅保存锚点、保护引用和消费凭据 |
| IntersectionPacket | intersection_ref、actor_ref、trigger_kind、group_ref、last_confirmed_tick、continuity_revision、source_revision_vector、hard_constraints、unresolved_proposals、required_code_refs、target_fidelity、lock_ref | 交接路径 → 下一推进者；复用同一身份，不创建第二角色 |
| CodebookEntry | code_ref、source_ref/type/revision、content_digest、scope/visibility、reader_roles、purpose_policy_ref、codec_version、encryption_key_ref（适用时）、safe_summary、expansion_levels、expiry | 获权索引 → 受控展开；来源 Owner 继续解释和保存原事实 |
| CodebookReadReceipt | reader_ref、code_ref、source_revision、requested_level、purpose、granted_fields、policy_revision、issued_at/expiry、结果状态 | 展开路径 → 审计/调用者；不包含完整原文，不授予后续世界写权限 |

`module_states` 使用已登记模块 schema；`typed_payload` 必须受版本化 proposal schema 限定，不能成为自由 JSON 写入口。群体请求只引用获权聚合帧/分片输入，不能为了使用共享帧而在每个 B0 窗口展开所有个人档案。

### 6.2 参与策略

原型默认 + 个体覆盖 + 情境预设 + 已确认承诺与锁 → 一份 ParticipationResolution。个体覆盖默认只能收紧或细化；放宽需要明确、获批的玩法规则和迁移版本。Siming 与角色智能体消费同一结果，不能各自解释另一份进入/退出规则。

无适用预设时，不默认把重要角色送入 B0。返回保护摘要、允许维度和升级候选。无合法精度时 defer/requeue，不能忽略硬限制。超出 B0 期限先完成受控交接；不能因为某个反应队列繁忙而继续越期推进。

### 6.3 模块合同与建议合并

每个受信模块声明 module_ref、definition_version、category、input_selectors、state_schema、supported_tiers、proposal_kinds、aggregation_policy、distribution_policy、upgrade_triggers、capability/protocol refs、codebook refs。

首批样板维度为 identity、needs、schedule、household、supply、situation、affect、behavior。它们是玩法模块职责，不要求建立八个新运行时或八个永久服务。

字段必须显式声明 aggregatable、distributable、individual_only、group_summary_only 的适用规则；允许统计不能推导出允许回填。未声明默认 individual_only。秘密、家庭承诺、关键财产、玩家关系和个人权利不得平均化。

先检查法律/安全、已有承诺、生存/健康、家庭责任、组织职责等硬约束，再按版本化玩法策略选择偏好；疲劳叠加、标签合并和互斥行为分别使用已登记规则。规则无法裁决时产生 decision_conflict 和 required_fidelity，不能由遍历顺序或未经固定的随机数决定。

## 7. B0 成员账本、分摊与交接

### 7.1 成员记录

每条 member entry 至少保存 actor_ref、entry_character_revision、participation policy pins、shard_ref、aggregatable field refs、protected code refs、last_consumed_result_cursor，以及 active/handoff/excluded/exited 状态。

成员账本不保存另一份库存、死亡、受伤、位置、关系和私有记忆。group_cursor 记录已确认群体结果；member consumption cursor 记录哪些获权结果已消费；二者都不能直接覆盖 Character Core 的 simulation_tick_cursor。

### 7.2 分摊边界

基线模块可按已登记 distribution policy 提出允许字段的个人连续性增量，最终由 Character Core 接纳。S2 编译器的 B0 输出则限定为 cohort/shard/pool/route/process batch 总量、区间和风险，不能直接输出逐人分配表。

角色退出 B0 时，交接路径使用入组锚点、保护约束、确认 aggregate receipt 和版本化规则构造最小上下文。无法安全归因到个人的结果返回 unknown 或升级请求，不能把群体平均值写成个人损失、获救或记忆事实。

### 7.3 交接过程

```text
触发交集
  -> 取得现有 activation/handoff 锁与版本凭据
  -> 停止该角色旧推进提交，固化已确认 B0 游标
  -> 接纳允许回填的连续性结果
  -> 构造 IntersectionPacket 与下一帧
  -> 按权限展开上下文
  -> 交由 B1/B2/B3 接管
  -> 回传可见摘要，完成或重新入队
```

同一角色最多一个有效推进者。外部事件只能进入下一版本帧，不直接修改在途推进者内部状态。旧执行者即使晚到，也必须因锁/版本凭据失效而不能提交。

交接被拒、重复请求、执行者中断和恢复必须各有正式结果。超时不能直接启动第二推进者；先通过现有锁生命周期解除旧权限，再基于最后确认状态恢复。世界已确认事实不因交接失败而回滚。

重新进入 B0 必须重新解析参与策略、承诺和未决工作，不能复用已过期入组决定。

## 8. 领域纵切与 Character Core

### 8.1 首个可复用协议的准确含义

首个回归纵切使用现有 schedule_gated_supply。当前 [ScheduleGatedSupplyOwnerExecutor](../../../../backend/app/population_continuity/owner_adapters.py)对应 Organization 的 gameplay.organization.commerce_commitment_accepted，能力绑定见 [PopulationCapabilityCatalog](../../../../backend/app/population_continuity/decision_surface.py)。

它证明供应承诺接纳及回执链，不自动证明已交付粮食、发生账户付款、获得药品、入住避难所或完成迁移。Inventory、Economy、容量/避难结果必须分别有已登记操作和自己的真实 receipt。

因此验收分为：

- 基线回归结果：供应承诺成功/被拒、角色连续性及玩家交接。
- 新模型 active 结果：至少一个真实 aggregate 资源或容量操作成功，以及 stale/capacity 拒绝。不得用供应承诺 receipt 替代该资源结果。
- 后继具身结果：确认证据改变实际领域能力，旧依赖被拒并触发局部反应。

### 8.2 新操作准入表

任何新增供应、避难、修桥或战区操作，在写实现计划之前必须给出：operation_ref、实际 source-controlled capability/contract、唯一 Owner、事实族、合法来源、读依赖映射、写流、权限、reservation 生命周期（适用时）、冲突窗口、成功/失败 receipt、幂等与 full/checkpoint-tail replay 合同。

未找到既有合法操作时，标记 capability_unavailable，并明确候选停留为 proposal_only；不得用泛化名称虚构其已存在。新增原子操作仍归对应领域 Owner，经逐项准入后才能进入计划。

### 8.3 连续性与记忆

Owner receipt → CharacterContinuityCommand → Character Core 校验与接纳 → SeedDelta/runtime state → 下一投影。无客观世界效果的合法连续性变化不强制伪造 Owner receipt；有世界效果的变化必须关联实际结果。

暴露依据、source refs、scope、时间和版本决定能否生成 memory candidate。确认世界变化不自动表示角色知情；角色知情不自动等于写入长期记忆。群体和 Siming 不写五池记忆；激活时及其他已准入物化路径均由 Character Core 执行，不新增绕过既有 materialization policy 的后台入口。

## 9. 通用密码本、隐私与历史读取

密码本是跨角色、群体、Siming 与领域协议的定位和受控展开合同，不能因为由群体相关任务引入就被绑定为 population 私有基础设施。

- L0：安全摘要；L1：过滤后的事实卡；L2：授权精确内容或投影。
- 每次展开校验 reader、purpose、scope、source revision、digest、expiry 和允许字段，并产生读取回执。
- context_insufficient 可以要求具体 code_refs 和 level，不能请求全部背景或用猜测填补拒绝内容。
- 明文留在原获权存储，索引和 receipt 不形成全局私有内容镜像。

历史回放必须能从原有事件/连续性/获权证据存储重建当时输入，并核对来源 digest。grant 或内容已失效时，普通运行读取失败；历史审计由当前有效的专用审计权限读取已保留历史，不把旧授权自动恢复给普通消费者。历史内容确实缺失时返回 replay_input_unavailable，不得声称精确重放成功。

不为模型新增独立事件库。必要的只读审计输入和运行决定沿既有获权持久化路径保存；如果该路径无法满足保留合同，相关模板不能通过回放验收。

## 10. 社会模型编译器

### 10.1 固定职责

获权草案 + 不可变受信模板 + owner FactCard/Proof → 冻结输入 → 有界声明式 IR 纯计算 → 候选与 ModelRunReceipt。

编译器不能采纳自己的候选、获取角色推进锁、预留资源、调用写工具、结算事实或拥有重试队列。原推进主体选择候选，继续走原有 ModuleProposal、ActionIntent 和协议路径。

八类固定为：实体关系图、资源保管与流量网、空间可达性图、流程/状态机、承诺与时间表、约束与分配、风险与传播、聚合与分摊。新类别、新节点或算子语义变化需新的准入与回放版本；场景模板名称不成为新事实 Owner。

### 10.2 最小合同

| 合同 | 必需内容 |
| --- | --- |
| SocialModelTemplate | package/template/version/active-set pins、类别、固定 IR 与算子/profile refs、必需/可选卡种类、允许主体/purpose/scope/privacy、输出与目标能力、适用精度、时间/计算上限、降级表 |
| ModelRunGrant | Siming tick/correlation、模板 pins、请求主体、用途/权限、有效区间、analysis_window、频率/节点/边/情景/候选/上下文预算、模式、revision/digest；只能收紧模板 |
| SocialModelDraft | template pins、提议者与用途、获权参与/情境引用、受限类型参数、情景数、输出类别、correlation/idempotency；不携带任意事实值或自由 IR |
| FactCard/Proof | card_ref、source owner/fact kind、reader/purpose/scope/privacy、revision/digest、valid_at/recorded_at/expiry、source events、rule/package pins；具身卡另含证据来源与确认状态 |
| InputVersionVector | 所有模板/授权/算子 pins、卡引用与 digest、codebook receipts、graph back-check proofs、时间窗、规范参数顺序与 seed |
| CandidateEnvelope | candidate_ref、受限输出类别与 typed payload、目标 capability/protocol、input digest、expected revisions、proof refs、expiry、risk/confidence、scope/redaction、来源/幂等身份 |
| ModelRunReceipt | run/status、模板/grant/input/seed/output digests、算子版本、读取/回查回执、预算截断、稳定排序、cache reuse、诊断与 correlation |
| ModelProjection | receipt 来源、获权摘要、输入身份、scope、expiry/invalidation；可重建读投影，永不提升为世界或图谱事实 |

CandidateEnvelope 允许的输出为 prediction、action_candidate、continuity_or_state_delta_candidate、conflict、risk、expansion_request、protocol_call_request。连续性候选使用已登记 ModuleProposal schema，且受 ParticipationResolution 约束。

ModelRunGrant 由司命在既有 tick 中按获权范围签发。B0 由已批准群体策略选择是否采纳；B1/B2 由既有脚本规则选择；B3 由角色智能体在合法私有上下文内选择。Owner 收到协议请求后只按领域规则验证和结算，不因接到模型候选而获得一般角色决策权。

### 10.3 图谱、预算与确定性

Heavenly Graph 只发现候选关系、参与者和路径。成为硬约束前必须回查 source owner，在兼容冻结版本取得 FactCard/Proof。图谱缺失时，若 direct owner read 已满足模板可继续；否则按明确降级返回，不能用图边或缓存猜测。

模板预编译固定 IR，运行只绑定获权输入与受限参数；拒绝动态派发、未登记节点、未 pin 算子和不具合法有限求值顺序的结构。

预算按确定性工作单位扣减，并在固定检查点截断。墙钟超时可以中断执行，但要记录为执行失败，不宣称其机器相关的部分输出是可确定重算结果。稳定排序、数值规范、种子、算子版本与历史失败/缓存决定一起进入回放合同。

认识不足不随机化。仅在模板允许的情景分析中使用固定 seed；预测情景不绑定未来 Owner 必须提交相同随机结果。首个版本只允许精确输入向量缓存，fragment 失效优化须另有等价证据。

### 10.4 模式与失败

| 模式 | 行为 |
| --- | --- |
| off | 不读取模型输入、不计算 |
| shadow | 执行并审计，不向推进主体投递候选 |
| advisory | 获权消费者可见候选，禁止采纳 |
| active | 原推进主体可选择采纳，Owner 仍独立校验 |

正式状态保留 ok、unknown、context_insufficient、proposal_only、graph_unavailable、graph_degraded、owner_unavailable、stale_input、budget_exhausted、policy_denied、conflict_detected、error。每次已准入运行，包括空结果和失败，都有最小脱敏 receipt；编译器不自旋重试。

### 10.5 上下文精度与分析窗口

| 消费者 | 可读取的模型上下文 | 升级或展开边界 |
| --- | --- | --- |
| B0 | 获权 L0、群体/有限分片卡、参与摘要和聚合投影 | 个人权利、家庭分离、关键财产、死亡/伤害或不安全物化必须升级 |
| B1 | 原型/情境、模块状态及常规局部或分片摘要 | 保护字段、无法裁决的规则冲突及局部异常 |
| B2 | 事件局部的空间、流程、关系和资源卡及有限角色 | 玩家交集、个人合同/家庭冲突或范围溢出 |
| B3 | 最小获权个人卡、共享模块状态及受控密码本展开 | 仍受参与策略和私有上下文权限约束，不自动获得全局信息 |
| Siming | 公开或司命可见的 Owner 摘要、脱敏投影、grant 状态 | 个人或私有裁决只能请求合法展开，不能直接读取角色私有记忆 |

编译器只提出 required_fidelity/expansion_request，实际交接由参与解析和既有锁完成。玩家消费获权局部投影、发送交互 intent；玩家邻近本身不解除读取或提交限制。

模板规定有限 analysis_window，grant 只能缩短。超出窗口需在新的世界时间重新读取和编译，不能以延长 expiry 复用旧候选。B0 游戏日/灾害 cadence、B1 小时级、B2 局部事件级是来源设计的分层方向，具体周期由玩法和既有调度合同决定；周级结果仅为宏观 ModelProjection。编译器不逐帧运行，不推进世界时间。

## 11. 具身因果后继

本节只有在第 2.2 节的 E 门禁满足后才能派生代码计划。现阶段定义合同和验证边界，不提前建立新 writer。

### 11.1 从证据到确认

原结构化意图 → Owner 预检/可选 reservation → execution grant → Godot 局部执行 → 结构化证据 → Owner 规则与来源校验 → 事实提交 → receipt/impact → 确认投影和局部反应。

EmbodimentManifest 引用资产/manifest digest、collision/support/nav/material profiles、interaction anchors、允许 probes 和项目阶段。作者发布资产能力描述，不能据此宣布资产已建成、已损坏或已通行。

| 合同 | 最小内容及限制 |
| --- | --- |
| EmbodiedEvidencePacket | attempt/grant/session/actor、target/anchor refs、asset digest、expected revisions、observed tick、capture identity、归一化观察、artifact refs、trust class/独立来源组、有效期、causation/幂等身份 |
| ConfirmedImpactSummary | owner_receipt/committed events、revision vector、effective tick、affected anchors/capabilities/scopes、invalidated dependency refs、reaction class、可见性、projection refs、replay digest |
| CausalCandidateEnvelope | source kind、actor/cohort/faction/domain refs、read-set、knowledge basis、belief refs、requested effect、required evidence、conflict window、capability/policy、causation/幂等身份 |
| SituationBeliefProjection | actor_private/faction_scoped/siming_scoped、命题、prior/posterior band、支持与反证 refs、review/expiry、来源和策略；不改确认事实 |

这些合同扩展既有 RawFact、candidate、result、projection 和 receipt，不要求创建万能 DTO。CandidateEnvelope 的模型来源可以成为 CausalCandidateEnvelope 的候选来源信息；二者复用同一 read-set/causation/expiry 校验语义，最终均回到已登记 intent，不产生两个结算入口。

### 11.2 证据可信度

presentation_only 永远不可确认世界；admissible_session 仅用于已准入的低/中影响操作；高影响、不可逆或跨战区操作必须满足相应操作声明的 corroborated 或 server_verified 条件。

信任等级由后端既有授权/操作验证链判定，不能由客户端填写枚举自我授予。同源重复采样不算独立证据。操作准入表必须指明可信来源、独立性判定、manifest/场景 pins、矛盾处理与保留规则。没有满足条件的验证来源时，保持 pending_verification 或拒绝。

### 11.3 回执阶段与局部反应

逻辑上区分 admitted、executing、pending_verification、committed、rejected、stale_world_context、conflict_lost；传输 accepted 仅表示请求被接收，不能单独驱动事实投影。只有 committed 且可核验 Owner receipt/事件引用才产生 ConfirmedImpactSummary。visibility_restricted 是投影访问结果，不替代实际结算状态。

具体 wire 枚举由 plan 按兼容要求映射，旧 accepted/applied 字段不得在无迁移的情况下改义。reservation 超时或取消走相应 Owner 的既有生命周期。

impact 从已提交事实派生，可重建；通过已有 cadence 的有界优先处理能力选择受影响 actor/cohort。优先级由 reaction class、安全风险、不可逆风险、玩家邻近和到期义务的版本化规则决定，同级使用固定顺序。预算不足返回 requeue 与积压指标，不绕过手中的角色推进锁，不把未反应显示为完成。

逐帧姿态、ragdoll、粒子、镜头和预测动画不进入群体硬约束。原始物理只保留受控调试或证据引用。

## 12. 阵营与对抗域后继

默认 world:cooperative。只有持续独立决策、资源/动员权限、目标及需要保护的情报边界经既有 authority 确认后，才形成阵营上下文。

- FactionContext：faction_ref、controllers/representation、objective/resource/membership/cohort refs、knowledge/belief scope、diplomacy refs、policy pins、active contest refs。
- ContestDomain：domain_ref、mode policy、参与阵营、地理/对象/目标范围、start revision、conflict-window policy、结束条件、visibility/projection policy。

它们组合已确认组织、关系和授权事实，不接管成员、库存、领土、伤亡、建筑或战果。双方共用一个世界时间、事实链和领域 Owner。私有计划、未报告观察与成员内心不能自动上交阵营或 Siming。

在对抗实施计划形成前，领域冲突合同必须固定窗口开启/关闭规则、合法参与者、证据截止、确定性排序与裁决、迟到/重复处理和可见失败原因；不能靠网络到达顺序或 LLM 临场描述选赢家。

首个后继顺序为协作洪灾，再到两阵营、四个高层主体的受限战区。后者每方一名人类玩家与一名扮演玩家的 Character Core，协作指挥守军/工兵/后勤 cohort，争夺同一桥梁、城门和补给线；它们仍通过各领域 Owner 结算。没有前者真实因果回流证据，不以扩展参与者数量代替验证。

S3 的开门、搬运、命中受伤、登船、持续火灾、塌方/城墙破坏、粮车倾覆与建造修复，是操作准入的领域案例集合。主 spec 保留其统一要求：每项都明确“具身证据 → Owner 确认事实 → 受影响能力/候选”，未完成具体准入的案例不因列入该集合而视为可实施或已实现。

## 13. 模块边界与实施计划的派生原则

本节按数据所有权、接口依赖和独立验收划定设计边界，不按人员或预设计划数量拆系统。下表是能力边界，不要求一行对应一个新包、服务或实施计划；能够复用既有实现的部分直接扩展原入口。

### 13.1 能力及其输入输出

| 能力边界 | 消费 | 产生与独立验收 |
| --- | --- | --- |
| 共享推进合同 | 既有角色身份、世界时间、参与规则和 Owner 版本 | 不可变帧、参与解析、proposal/commit 语义；格式和 stale 错误可区分 |
| 角色模块与规则内容 | 帧、保护字段、原型及个体覆盖 | 可解释的模块建议、升级请求和规则版本；四种精度共享约束 |
| 群体连续性与交接 | 合法参与解析、模块建议、成员和推进权 | 账本、游标、分片及 IntersectionPacket；同一身份、唯一推进者、确定性恢复 |
| 领域协议与角色回流 | 结构化 intent、冻结 read-set、领域准入规则 | Owner 事实/失败 receipt，再由 Character Core 接纳状态和记忆候选；分别验证两个提交阶段 |
| 通用授权读取 | Owner 读侧合同、reader/purpose/scope 与版本 | 获权展开、FactCard/Proof、读取回执和历史取回；不依附某个群体模块 |
| 社会模型编译器 | 受信模板、封闭算子、grant、冻结输入向量 | 无副作用的 CandidateEnvelope 和 ModelRunReceipt；候选必须经原协议接纳 |
| 具身确认与局部反应 | execution grant、manifest、具身证据及领域验证规则 | 已提交事实的 impact、失效依赖和有界反应；局部观察不能直接成为世界真相 |
| 阵营与对抗规则 | 已确认组织/资源权限、情报范围及具身因果闭环 | FactionContext、ContestDomain 和确定性冲突结果；共用既有世界与 Owner |
| 生产运行支撑 | 上述能力的负载和恢复需求、S8 的既有计划 | 执行隔离、恢复、保留和规模证据；复用既有工程主线 |

这些边界共享第 5–6 节的一致性合同。模块、编译器和具身处理即使分别实现，也不能拥有各自的推进锁、事实提交规则或幂等解释。

### 13.2 从 spec 到 plan

实施计划从一个可验证结果及其依赖闭包生成。每个计划说明消费哪些已稳定合同、补齐哪个实现缺口、通过哪些 AC、在哪里与现有主线集成。紧耦合的 schema 与首次真实消费者放在同一交付中；拥有稳定接口且能独立验收的后继能力可分开。

本轮实施组织固定为以下两份计划，任务内部按依赖安排：

| 计划 | 负责人 | 主责 |
| --- | --- | --- |
| [计划 A：运行时连续性与共享基础](../../plans/world-character-siming-authority-mainline/2026-09-18-population-continuity-runtime-implementation-plan.md) | 人员甲 | 共享模型、参与解析、账本、锁、Core 接纳、通用读取、编译运行合同及公共集成 |
| [计划 B：角色模块、洪灾样板与领域纵切](../../plans/world-character-siming-authority-mainline/2026-09-18-character-simulation-domain-vertical-implementation-plan.md) | 人员乙 | 模块、原型/情境、洪灾群体、真实 Owner 协议、回流转换、模型模板及 Godot 样板 |

共享接口和文件归属以计划 A 的共同协作表为唯一记录，计划 B 引用并消费。两份计划先覆盖 C0–C7 与 M shadow/advisory；M-active 等真实 aggregate 操作准入，E/F 等原门禁，只分配后继责任。达到条件后在这两份文件追加相应实施任务，不复制第三套公共合同。

### 13.3 共享文件与集成约束

实施计划必须检查实际调用链后列出文件，而不是直接采用辅助参考中的预设路径。backend/app/main.py、Siming 入口、Character Core 运行循环、共享 schema 和 Harness 注册等公共位置，在同一实施批次明确一个修改责任方；其他任务通过稳定接口接入，避免并行覆盖。

领域算法、模块内容和 owner adapter 按其业务边界组织。是否需要新增文件，以现有代码能否保持清晰职责为准。共享字段变更同步更新本 spec 和关联 AC，并检查所有消费者，不增加临时字段维持两套解释。

代码编辑责任不改变事实所有权。使用独立工作树时按仓库约定 cherry-pick 集成；提交以可独立审查的结果组织。

## 14. 阶段依赖与共同出口

### 14.1 与 9/16 阶段 0–7 对齐

| 基线阶段 | 必要产出与依赖 | 独立出口 |
| --- | --- | --- |
| C0 层级标记 | 当前入口、数据所有权与真实操作清单 | 当前入口明确属于事实/协议/投影/适配；无新万能 writer |
| C1 共享帧 | 消费 C0，定义帧、参与解析及首个消费者 | 帧、参与策略、proposal/commit 合同一致；格式拒绝与运行时 stale 拒绝分别验证 |
| C2 简易模块 | 消费 C1，补齐农民模块、原型/个体规则和接纳行为 | 四层复用模块定义；受保护字段与冲突升级有效 |
| C3 成员账本 | 消费 C1/C2 的参与和字段策略，接入洪灾分片样板 | 入/出组、分片、确定性分摊、完整/尾部回放一致 |
| C4 交接 | 消费 C3 的成员记录及唯一推进权，接入玩家邻近触发 | 同一身份、唯一推进权、中断恢复、无重复消费 |
| C5 社会协议 | 消费共享提交合同及相应读取能力，连通 Owner 与 Character Core | 实际 Owner 成功/拒绝与 Character Core 回流，明确事实范围 |
| C6 密码本 | 消费授权与 Owner 读侧合同，统一展开、回执及历史读取 | 按用途授权展开与审计回执；历史重放可取回原输入 |
| C7 DOD | 消费稳定的语义 oracle 与相关连续性/协议样板 | 批量优化前后候选、回执、角色状态与 replay digest 等价，并有对应新鲜规模证据 |

全局优先级为 P0 合同/层级/样板，P1 帧/模块/账本，P2 交接/领域闭环，P3 通用读取及扩展协议，P4 优化。优先级不代替硬依赖：凡需要受控展开的任务必须先消费最小 Codebook 合同，不能等到 P3 才临时补权限。

### 14.2 并行与后继

共享合同稳定后，模块规则内容与通用读取可以在明确接口上独立推进；成员账本先消费参与和字段策略，交接再消费账本与推进权。已有合法领域操作可先证明最小协议闭环，再纳入群体和交接样板。C0–C7 是与来源基线对齐的能力阶段，不表示所有工作必须按编号串行；具体依赖由上表和实际读写合同决定。成功事实验收必须走真实 Owner，不能由 mock 或自然语言替代。

M-shadow 可在共享合同冻结后用受控 fixture 单独证明纯计算；接真实卡需相应读取与历史合同；M-active 必须具备参与策略、账本/交接、协议接纳、受控读取和真实目标 capability。shadow 成功不得提升为 active 完成。

E 的代码计划在 C0–C7 独立证据齐备后才生成。E 先做一个低/中影响交互，再做一个高影响环境变化；F 在 E 因果闭环、情报隔离与冲突合同成立后进入。

S8 六项生产工程使用原计划与原门槛，作为现有外部依赖按需对接。新能力的计划只补充其接口和验证需求，不复制另一套执行隔离、恢复或保留机制。

## 15. 贯穿样板与验收编号

### 15.1 样板固定内容

老王是同一份角色档案，有照护家庭成员、保护关键种子和玩家旧识等限制。洪灾带来疲劳、食物和道路压力。B0 只能统计允许字段并生成候选；玩家接近时，同一角色通过锁与 IntersectionPacket 进入 B2/B3。

基线样板先确认供应承诺的真实成功与拒绝。涉及实际资源、床位或搬迁时必须使用相应已准入操作；缺能力时展示未完成，不以叙述补成获救。洪灾退出后保留已确认经历、允许变化及未完承诺，不重建角色。

后继样板增加：Godot 上报道路变化证据 → Owner 确认 revision → 即使反应队列没处理，旧运输方案也被拒绝 → 受影响分片重算 → 家庭例外升级 → 新协议结算 → 场景显示确认或失败。

### 15.2 验收矩阵

| 编号 | 必须证明 | 对应能力/阶段 |
| --- | --- | --- |
| AC-01 | 没有第二 runtime/clock/store/bus/万能 router；Siming 入口职责准确 | C0 与整体集成 |
| AC-02 | 帧不可变、来源/策略 pins 可验证；格式错误与 stale 运行错误分别拒绝 | C1 共享推进合同 |
| AC-03 | B0/B1/B2/B3 使用同一身份和参与规则；个体覆盖不暗中放宽 | C1/C2 参与解析与模块 |
| AC-04 | individual_only 不聚合；统计许可不自动允许回填；成员不丢失 | C3 成员账本 |
| AC-05 | 相同输入、规则、seed 的分片/分摊及 full/checkpoint-tail 回放等价 | C3/C7 连续性与回放 |
| AC-06 | 同角色唯一有效推进者；旧锁执行者、重复/中断交接不能重复提交 | C4 交接 |
| AC-07 | 供应承诺成功/拒绝有真实 receipt；失败无新增业务事实；重复不双写 | C5 领域协议 |
| AC-08 | 世界提交与连续性中断后可恢复；state/memory cursors 分离，无暴露不记忆 | C4/C5 Character Core 回流 |
| AC-09 | Codebook reader/purpose/scope/revision/digest/expiry 校验与读取回执 | C6 通用授权读取 |
| AC-10 | 受信模板和封闭 IR 拒绝动态代码、未知类别与越权参数；shadow/advisory 不采纳 | M 编译与准入 |
| AC-11 | 冻结输入完整带到 Owner 提交；道路等只读依赖变化也拒绝；不得静默重 pin | M/E 输入版本与 Owner 接纳 |
| AC-12 | 编译器 B0 无逐人分配；一个真实 aggregate 资源/容量成功及 stale/capacity 失败 | M 与真实领域 capability |
| AC-13 | 模型历史输入、预算截断、降级/缓存解释可审计重放；缺输入不伪称通过 | M 与 C6 审计读取 |
| AC-14 | grant/accepted 与 committed 可区分；impact 只来自已提交事实 | E 具身确认 |
| AC-15 | 高影响操作证据等级由后端验证；同源重复、矛盾来源、旧 manifest 被正确处理 | E 领域证据验证 |
| AC-16 | 通知延迟/丢失或预算耗尽时旧候选仍被提交检查拒绝；局部反应可重建 | E 影响传播与提交重验 |
| AC-17 | 阵营共享世界而私有情报隔离；冲突窗口固定，迟到/重复结果确定 | F 阵营与对抗规则 |
| AC-18 | 优化前后权威结果等价，规模、延迟、积压和网络口径可复验 | C7 与 S8 生产工程 |
| AC-19 | Godot 有运行后端、真实边界消息及场景中确认/拒绝可见结果 | 对应 C/E/F 的集成样板 |
| AC-20 | 全后端、相关专用 profiles 与全仓 Harness 有对应修订的新鲜记录 | 各实际变更范围的总验收 |

零写入测试覆盖 stale、无权、private/cross-actor、branch-only、未知 schema、错误 Owner、重复键不同载荷、预算不足及锁冲突。各测试明确观察哪类业务事件、角色 revision 与 receipt；审计记录不混入“业务事件必须为零”的计数。

### 15.3 行为有效性

语义正确性包括资源守恒、权限、保护字段连续性和扰动局部性。行为有效性另作对照：相同处境下有照护责任与无照护责任者的选择差异可解释；道路关闭使依赖该道路的方案改变；与简单确定性启发式相比，在预先声明的成功率、约束违反率、计算成本或解释质量上证明新模型价值。

固定条件下，无关输入不应无故改变无依赖候选；共享资源或全局预算造成的间接影响必须在依赖合同中说明。以上不等于真实社会行为已经校准，也不以 LLM 描述自然作为成功标准。

## 16. 验证、证据保留与完成声明

后续实施计划的每个任务必须列 Files、Interfaces（Consumes/Produces）、关联 AC 编号、预期失败及有意义的测试、最小实现、focused verification、提交边界。先验证应失败，再完成行为；不以只检查类型存在的测试替代运行约束验证。纯文档/机械变更按风险检查，不机械制造测试。

后端标准入口为在 backend 目录运行 `python -m pytest -v`。广泛变更还需在仓库根运行 `python scripts/verification/harness.py --profile all`，并显式执行受影响的人口专用 profiles；当前多个 population profile 的 include_in_all=false，all 不能替代它们。

沿用现有 population-continuous-runtime、population-hot-state-equivalence、population-data-oriented-persistence、population-data-oriented-incremental-read、population-runtime-scale，以及相关 seed/Siming/具身 profiles；新增合同没有对应验证入口时，在相应能力的实施任务中补齐，不用相近名字声称覆盖。

证据记录源码身份、环境、命令、结果、数据/规则版本和范围。正式性能计时不并发其他基准。历史 1× 三档短窗通过、provider 关闭、10× 部分失败及 Godot 未验证仅为历史记录，不自动继承为新修订结果。

遵守当前 AGENTS.md 与 [Harness 指南](../../../harness.md)：运行产物由 run_scope 放入本轮系统临时目录，顶层消费者完成后清理本轮目录和拥有的进程。必要原始诊断在清理前通过 `--export-evidence` 显式导出到仓库外空目录；不删除并行任务或用户已有资料。不提交报告、日志、数据库、截图、缓存或复制工作树；`.harness/` 只保留可评审静态输入。旧文档中的 `.harness/verification/` 路径不应被恢复为永久输出位置。

完成声明按 C/M/E/F/P 分别列出。C 的后端证据不等于 Godot 完成；没有实际编辑器/运行证据时保持 godot_unverified。新行为只有静态检查时保持 static_only。基线供应承诺成功不等于资源/避难或完整社会模拟完成。

## 17. 开源借鉴与依赖决策

当前资料与一手来源见 S7。该分析已查询官方文档，但没有运行外部代码或完成集成选型。

| 参照 | 可借鉴 | 本稿明确保留的边界 |
| --- | --- | --- |
| Mesa | 分组/激活、统一时间与事件调度 | 不引入第二个 Model runtime；按既有 cadence 实现必要机制 |
| Concordia / Generative Agents | 认知模块与历史影响行为 | LLM 输出保持候选，GM 不替代 Siming/Owner |
| AgentSociety 2 | 状态与执行对象分离、批任务和模型预算观测 | CodeGen/写工具不进入封闭 IR；不因参照而引入 Ray |
| NetworkX / OR-Tools | 固定路径、流量、约束与分配算法 | 算法由受信算子封装；目标和保护规则来自玩法合同 |
| Habitat-Sim | 动作—执行—观测闭环 | 不替换 Godot，不把局部物理时间等同世界提交 |
| FLAME GPU | 规则批计算、邻域与分桶 | 只有端到端瓶颈证据支持时再决策，人口数本身不构成迁移理由 |

首个模板优先复用项目 helper 和标准库；没有具体算法缺口与收益证据，不增加求解器或分布式依赖。后续若引入算法库，必须固定版本、数值与预算语义，并完成旧 oracle/新实现等价或已批准差异验证。

## 18. 本次整合的裁决与评审重点

以下裁决来自原始设计之间的语义对齐和当前实现核查。辅助参考只用于发现遗漏或歧义；除来源已明示的原则外，具体补充仍是本稿拟议决定。

| 编号 | 拟议裁决 | 理由与来源 |
| --- | --- | --- |
| D-01 | 以事实所有权、共享合同和因果闭环组织 spec；本轮按用户要求生成 A/B 两份计划及甲乙分工 | S1/S2/S3 决定能力目标，S4 辅助实施组织；人数与计划数量不改变架构 |
| D-02 | Siming 唯一入口限定为司命决策/派发，world runtime 继续推进时间 | 修正 S4 的“唯一调度入口”过宽表述，保持 S1/S5 的已有职责 |
| D-03 | schedule_gated_supply 验收精确到组织供应承诺；资源/容量另需真实能力 | 当前 capability 与事件族不支持把承诺等同已交付或已避难 |
| D-04 | Character Core 独占角色状态接纳；领域层只提供已确认结果到连续性输入的映射 | 按业务所有权收口模块接口；共享文件的修改责任留给实施计划 |
| D-05 | 基线允许字段的个人物化，与编译器 B0 禁逐人分配分别处理 | 保留 S1 分摊能力，同时遵守 S2 更窄的编译器职责 |
| D-06 | 完整 read-set 提交重验兜底；失效通知不承担唯一正确性保证 | 明确 S2/S3 的 stale 拒绝如何落到已有 store |
| D-07 | accepted/获准执行与 committed 分阶段；审计历史输入和确定性预算有正式失败 | 收口附件中回执歧义及精确 replay 的实际依赖 |
| D-08 | 生产工程沿用 S8；DOD 已有实现不自动等于新基线阶段 7 完成 | 不复制工程计划，也不以旧性能报告解除 S3 前置门禁 |

### 18.1 来源覆盖检查

| 主要依据 | 在本稿中的落实 |
| --- | --- |
| S1 角色与群体基线 | 第 5–9 节共享推进与连续性；第 14 节阶段 0–7；AC-01–AC-09 |
| S2 受约束社会模型编译器 | 第 10 节封闭计算、权限、输入与输出；AC-10–AC-13 |
| S3 具身因果与阵营对抗 | 第 11–12 节证据确认、影响回流和阵营边界；E/F 前置门禁；AC-14–AC-17 |
| S5/S6 权威与边界基线，加第 3 节当前代码证据 | 第 3–4 节复用与所有权；第 8 节真实操作范围；第 16 节验证口径 |
| S7 开源一手资料 | 第 17 节可借鉴机制、适用边界与暂不引入的依赖 |
| S8 既有生产闭合设计 | 第 14、16 节已有工程依赖；AC-18 与相应生产验收 |
| S4 拆分参考 | 第 13.2 节两份计划及甲乙主责；修正原参考中的过宽调度、资源结算与记忆物化表述 |

主 spec 的评审出口是：事实和状态的唯一写入责任清楚，D-01–D-08 无未处理冲突，新增操作范围可准确命名，AC-01–AC-20 能映射到能力模块或既有生产工程，并明确尚未满足的阶段门禁。本轮 A/B 计划草案已生成；设计、计划文档齐备不等于代码已授权实施或已实现。
