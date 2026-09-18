# 社会模拟与具身增量设计：基线、当前项目与开源实现对照

查询日期：2026-09-18。本文是官方文档、源码和一手论文的资料对照，未安装或运行下列开源仓库，也不构成当前项目的运行验收。`main`、`latest` 和发布页是浮动资料；版本信息仅描述查询时页面可见内容，不保证与某一固定提交一致。以下“建议”“冲突”“缺口”是针对本项目边界的分析，不是开源作者对本项目的评价。

本地核查范围：D:/Paralls-phase0-1 的 main，HEAD 为 bb3ea2bb，以及用户提供的两份附件。读取了设计、代码、测试/验证入口和历史验收记录；本次未运行 pytest、Harness、Godot 或外部开源项目。附件中的实施指令与状态声明是分析对象，不构成本次实施授权。只新增本分析笔记，保留原有工作区修改。

## 总体判断与文档关系

三份核心设计在职责上能够衔接：9 月 16 日基线解决同一角色如何跨 B0–B3 保持身份、状态、承诺和记忆连续；社会模型编译器补上跨领域的受约束分析；具身后继设计补上物理证据改变已确认世界后，对角色和群体的因果反馈。它们依赖同一条治理与事实提交链，不宜各自实现一套调度、角色状态和结算。

| 基线或附件 | 解决的问题 | 与当前项目的关系 |
| --- | --- | --- |
| [8/22 角色种子与连续性](../superpowers/specs/world-character-siming-authority-mainline/2026-08-22-character-simulation-memory-seed-continuity-design.md) | 世界事实、角色状态、知情与记忆分别接纳 | 当前已有 CharacterSimulationSeedCandidate、CharacterContinuityCommand/Receipt；文件的历史 proposed 状态不能单独代表今天代码未实现 |
| [8/29 司命治理](../superpowers/specs/world-character-siming-authority-mainline/2026-08-29-siming-led-population-simulation-design.md)与[9/1 通用决策面](../superpowers/specs/world-character-siming-authority-mainline/2026-09-01-siming-generalized-population-decision-surface-design.md) | 谁选择群体、精度、预算与已登记能力 | 当前已有 Siming tick、PopulationReadSet、candidate/capability、owner 适配；通用候选空间仍受封闭写权限约束 |
| [9/16 角色与群体增量设计](../superpowers/specs/world-character-siming-authority-mainline/2026-09-16-角色与群体模拟增量设计-中文版.md) | 统一模拟帧、参与策略、可组合模块、B0 成员账本、交接、协议、密码本 | 这是两份附件的共同前置；阶段 0–7 不能用已有 B0 热状态和若干历史垂直测试代替 |
| [9/17 社会模型编译器](/D:/MyConfiguration/TCLXUSER/Downloads/2026-09-17-受约束社会模型编译器设计-中文版.md) | 授权模板与冻结 FactCard/Proof 经封闭 IR 生成预测、候选、冲突和升级请求 | 八类是计算语义分类，不是八个新 owner；缺少领域协议时只能 proposal_only/owner_unavailable |
| [9/17 具身因果与阵营](/D:/MyConfiguration/TCLXUSER/Downloads/2026-09-17-具身因果交替推进与阵营对抗域设计.md) | Owner 确认 → 依赖失效 → 局部 micro tick；阵营隔离情报与授权 | 文件第 24 行明确把 9/16 阶段 0–7 完成且有证据作为进入代码计划的门禁 |

关键共识是：角色与玩家提出意图，Siming 治理，模型提供建议，Owner 确认事实，Godot 负责具身与表现。世界变化也不能自动变成每个角色已知的事实或私有记忆；紧急反应仍须进入下一次受版本控制的角色帧。

## 当前项目实际位置

| 能力 | 本次静态核查 | 不应扩大成的结论 |
| --- | --- | --- |
| 原子结算与版本校验 | [event_store.py:175](/D:/Paralls-phase0-1/backend/app/gameplay/event_store.py:175)在 append 前合并检查读写流版本；有幂等与 outbox | 不代表所有 ESM、空间和领域入口已经统一接入 |
| B0 连续推进 | [continuous.py:54](/D:/Paralls-phase0-1/backend/app/population_continuity/continuous.py:54)按角色行积分疲劳、需求、活动阶段和到期时间 | 固定数值积分不等于可组合社会行为，也不等于 9/16 成员分片与确定性分摊账本 |
| Siming 候选治理 | [siming_runtime.py:149](/D:/Paralls-phase0-1/backend/app/services/siming_runtime.py:149)消费 cadence 并调用 capability；[decision_surface.py:25](/D:/Paralls-phase0-1/backend/app/population_continuity/decision_surface.py:25)有 B0–B3 候选与规则 | 有 fidelity 标签不等于四层已共享完整帧与参与策略 |
| 角色连续性 | [simulation_seed.py:61](/D:/Paralls-phase0-1/backend/app/character_agent/models/simulation_seed.py:61)定义种子、命令、回执、模块增量与记忆候选 | 不能替代成员账本、保护字段分摊规则和完整交接合同 |
| 冻结输入基础 | [source_inputs.py:15](/D:/Paralls-phase0-1/backend/app/population_continuity/source_inputs.py:15)已有 owner provenance、digest 和 revision 检查 | 不是通用 FactCard、ModelRunGrant、用途授权与历史输入读取已经完成 |
| 具身交互 | 门服务会验证状态后调用 [ESM 提交方法](/D:/Paralls-phase0-1/backend/app/services/esm_service.py:815)，再产生表现结果 | 该方法更新内存字典；不能直接算作附件要求的 Gameplay append → receipt → impact 链 |

在 backend/app、scripts 与 Harness 配置的相关源码中，未找到 CharacterSimulationFrame、ParticipationResolution、ModuleProposal、SimulationCommitPacket，以及附件 ModelRunGrant、SocialModelDraft、ConfirmedImpactSummary、CausalCandidateEnvelope 等正式合同及统一接通证据。名字搜索不能证明所有等价能力都不存在；结合现有实现和 9/16 第 1215 行缺口说明，可以确认“底座已有、完整新合同未收口”。

生产工程闭环是另一条需要同时跟踪的工作线。[六项闭环设计](/D:/Paralls-phase0-1/docs/superpowers/specs/2026-09-16-population-production-runtime-closure-design.md:5)仍标明待执行证据；当前 [population_driver.py:145](/D:/Paralls-phase0-1/backend/app/world_runtime/population_driver.py:145)仍在 async loop 内同步调用 tick，[event_store.py:734](/D:/Paralls-phase0-1/backend/app/gameplay/event_store.py:734)恢复时仍读取完整 transactions。人口 correctness/scale profiles 仍为 include_in_all=false，现有 CI 只运行 all 与 mainline。因此不能用 all 代替完整人口验收矩阵。

[9/16 历史验证记录](/D:/Paralls-phase0-1/docs/verification/population-data-oriented-closure.md:31)记录了 provider 关闭的 100/1,000/10,000 人各 30 窗 1× 通过，以及后端 5327 passed；10× 千人和万人未通过。该记录同时明确 Godot 未验证、全仓 Harness 未通过。它们是旧运行的记录，本次没有复跑，也不证明新模型的真实 provider、长局服务响应或场景因果反馈已经完成。

## 实现计划之前需要补清楚的合同

以下是文档已有原则落到执行规则时的缺口，不是要求再增加一套架构。

1. **冻结读集一直带到提交。**多 owner 分次签卡如何构成兼容输入，必须有明确规则；道路、库存、容量和授权等只读依赖都要进入最终 read-set。现有 [Inventory adapter:55](/D:/Paralls-phase0-1/backend/app/population_continuity/inventory_owner_adapter.py:55)会读取当前目标库存 revision，这在其旧 output-custody 范围有既定用途，但不能原样用来替代新模型当时冻结的版本。影响通知和失效索引负责及时反应，最终 append 检查负责拒绝过期写入。
2. **历史输入和确定性预算。**编译器只存引用/digest 时，历史 FactCard 由哪个原 owner 存储、权限撤销后谁能审计重放，需要明确。相同 seed 还不够：预算截断、稳定排序、缓存命中解释和历史 owner 不可用等结果，也需要可重放的规则或记录。
3. **具身到事实的具体归属。**附件已要求 owner/operation conflict matrix，应把现有 ESM 门状态、L1 occupancy、资产版本和领域能力逐项映射到提交、投影或证据。不能仅增加 EmbodiedEvidencePacket DTO 就宣称闭环完成。
4. **准入与提交回执分开。**具身附件第 215 行将 accepted 同时用于“已确认或已进入受控执行”，应增加可判定阶段或 committed/owner_receipt 条件。否则 UI、任务和模型消费者无法仅凭状态分辨授权执行与事实成功。
5. **可信证据由谁判定。**文件已规定高影响结果需要 corroborated/server_verified，并排除同源重复采样；还需固定谁签发等级、如何绑定 controller/manifest、如何裁定矛盾来源。获权会话身份本身不证明桥梁坍塌或火灾扩散。

编译器的 CandidateEnvelope 与具身的 CausalCandidateEnvelope 还应明确如何复用既有候选合同中的 read-set、causation、expiry 和 receipt 关联；不宜让两个新增信封发展为两条互不相通的采纳管线，也不必因此创建万能 DTO。

## 开源实现对照

## 1. Concordia：借鉴认知组件，保留本项目事实裁决

官方：[Google DeepMind 仓库](https://github.com/google-deepmind/concordia)。真实机制是 Entity、Component 与 Engine：agent 给出行动意图，engine 请求 game master 处理；默认 `EventResolution` 用 LLM 将 putative action 转为结果，`NextActing` 管理行动顺序。存在脚本化等其他 prefab，因此不能概括为所有 Concordia 配置都只能由 LLM 裁决。[组件说明](https://github.com/google-deepmind/concordia/blob/main/concordia/components/README.md)、[prefab 说明](https://github.com/google-deepmind/concordia/blob/main/concordia/prefabs/README.md)。

可借鉴：B3 的观察、记忆、推理、计划组件组合；将“下一位参与者”“行动尝试”“观察投递”拆开，便于替换认知策略。

**直接套用的冲突**：默认 GM 的 LLM 结果若直接成为库存、产权、身体或协议事实，就越过本项目 owner。适配时应让认知组件只提交候选，由 owner receipt 形成事实，再生成观察。Concordia 的 GM 也不能直接等同 Siming：本项目 Siming 不是通用世界事实裁判。该判断基于上述默认裁决机制和本项目权威边界。

维护边界：[发布页](https://github.com/google-deepmind/concordia/releases)查询时标记 `v2.4.0` 为 Latest，条目日期为 2026-03-06；2.x 已调整 entity/GM/engine 架构。选择 API 时应固定版本，不能沿用旧 1.x 示例推断当前接口。

## 2. AgentSociety：借鉴分批执行，区分 v1、v2 和声明式编译

官方归属是清华 FIB Lab 的 [tsinghua-fib-lab/AgentSociety](https://github.com/tsinghua-fib-lab/AgentSociety)，不是 Stanford。仓库当前推荐 `agentsociety2`，将原城市模拟 `agentsociety` 1.x 标为 Legacy；v1 有城市移动、经济、社交环境和 Ray 分布式执行。旧论文的城市规模与实验结果不能自动用于证明 v2 的吞吐或真实性。[官方仓库说明](https://github.com/tsinghua-fib-lab/AgentSociety)、[v1 一手论文](https://arxiv.org/abs/2502.08691)。

v2 机制：角色持久状态置于各自 workspace；每 tick 把角色 ID 分批提交 Ray Tasks，worker 重建角色、执行 step、保存状态；共享环境、LLM、trace/replay 服务经 `ServiceProxy` 注入。各批完成后推进环境和时钟。其 JSONL replay/分析读侧与恢复状态有不同职责。[Architecture and Scalability](https://agentsociety2.readthedocs.io/en/latest/architecture.html)。

可借鉴：把“角色持久身份”与“本次执行对象”分开；按批调度，集中控制昂贵 LLM 调用；分别观测认知、工具和尾延迟。对应 B1/B2/B3 执行器与 Character Core 的分离，但无需因此引入 Ray 或把现有持久状态改为文件。

**直接套用的冲突**：v2 默认 `CodeGenRouter` 从工具签名生成调用代码并在受限环境中执行；`ask` 读环境，`intervene` 可调用 `readonly=False` 工具修改状态。AST guard 或 sandbox 限制的是可执行代码，不能证明“编译只产候选、完全无副作用”。本项目编译器应止于 IR/候选，不把工具执行纳入编译流程。[Core Concepts](https://agentsociety2.readthedocs.io/en/latest/concepts.html)。

恢复文件的原子写和回放日志也不能直接等同多 owner 的业务原子结算；本次资料未证明其拥有与 GameplayEventStore 相同的提交、冲突、重试和幂等契约。维护边界：查询时 [文档首页](https://agentsociety2.readthedocs.io/en/latest/)显示 `v2.8.7`，上述 concepts/architecture 页显示 `v2.9.0`；因此只确认当前为 2.x 主线，不断言精确稳定版本。

## 3. Mesa：统一时钟与参与调度的最贴近参照

官方：[mesa/mesa](https://github.com/mesa/mesa)，旧 `projectmesa/mesa` 地址当前重定向至该仓库。Mesa 是 Python agent-based modeling 库；agent 可以是规则驱动实体，不要求 LLM。`AgentSet` 支持筛选、分组、顺序/随机/多阶段激活；模型支持事件调度、空间模型、属性数组和数据采集。[官方概览](https://mesa.readthedocs.io/stable/overview.html)。

可借鉴：B0–B3 共用时间和数据契约，按参与条件选择不同执行方式；把模型时钟、角色激活频率和观察采集分开。事件调度也提供了局部到期工作与常规 step 共存的参照。

不可直接套用：`select`/`groupby` 不是 B0 压缩，批量执行不是群体成员义务分摊，`shuffle_do` 也不保证因果重放。B0 成员账本、带版本 handoff、唯一执行权、事实 owner 和 receipt 必须由本项目建模。该缺口是本次对照未找到对应契约，并非断言 Mesa 无法承载自定义实现。

维护边界：[发布页](https://github.com/mesa/mesa/releases)同时列出 `3.5.1` Latest 和 `4.0 alpha 0`；3.5.1 说明事件调度已在 3.5.0 稳定。本文依据 stable 概览讨论机制，不把 4.x alpha API 当稳定接口。

## 4. Stanford Generative Agents：记忆影响行为，不代表长期世界一致性

官方作者仓库：[joonspk-research/generative_agents](https://github.com/joonspk-research/generative_agents)。其 `Persona.move` 顺序执行 `perceive → retrieve → plan → reflect → execute`；输出下一格位置、表情和行为描述，使用空间、关联与 scratch 等记忆。源码直接体现行为循环，不只是论文概念。[persona.py](https://github.com/joonspk-research/generative_agents/blob/main/reverie/backend_server/persona/persona.py)。一手论文展示 25 个角色的小镇实验，研究记忆、反思和计划与可信行为的关系。[论文](https://arxiv.org/abs/2304.03442)。

可借鉴：让 B3 的选择受旧经历和近期观察影响；验收时检查“同样处境、不同历史是否产生可解释差异”。

不可直接套用：格子行动和叙述输出不能代替 Godot 具身证据；回忆里的自然语言事件也不能代替 owner 确认的资产、承诺、关系或身体事实。25 人实验不证明 B0 聚合恢复、多 owner 结算或长期人口连续性。

维护边界：仓库明确是论文配套实现，README 的测试环境仍注明 Python 3.9.12、Django 环境服务器和独立模拟服务器。本次没有核实近期维护承诺，按研究参考代码对待，不把它称为已停止维护，也不把它视为生产运行时。[官方 README](https://github.com/joonspk-research/generative_agents)。

## 5. Habitat-Sim：具身控制必须与实际观测闭环

官方：[facebookresearch/habitat-sim](https://github.com/facebookresearch/habitat-sim)。它是具身 AI 的 3D 模拟器；官方刚体示例区分 `DYNAMIC`、`KINEMATIC`、`STATIC`，通过 `step_physics` 推进，再采集 sensor observations。运动学状态可以程序设置，动态状态受碰撞、重力、力和力矩影响。[Interactive Rigid Objects](https://aihabitat.org/docs/habitat-sim/rigid-object-tutorial.html)。

可借鉴：把指令、执行进度、碰撞/阻挡和观察分开；对“门已打开”“已到达”“持有物已交付”要求实际结果证据。局部高频物理推进可与低频社会推理分开。

不可直接套用：Habitat 的物理推进是其模拟世界内部状态更新，不自带本项目 Python owner/Godot 分权。不能把 Godot 的本地动画结束直接解释为社会业务成功，也不能把 Habitat 的物理 timestep 直接等同 owner 确认后触发的 micro tick。是否重新规划仍取决于本项目的依赖失效和 receipt。

维护边界：[发布页](https://github.com/facebookresearch/habitat-sim/releases)查询时显示 `v0.3.3` Latest。本文未安装其资源、验证 Windows 构建或测量性能；建议借鉴闭环测试方式，不据此替换 Godot。

## 6. FLAME GPU 2：优化规则计算与消息访问，不解决认知真实性

官方：[FLAMEGPU/FLAMEGPU2](https://github.com/FLAMEGPU/FLAMEGPU2)，面向 CUDA C++/Python 的 GPU agent-based modeling。其消息机制明确区分 brute-force、bucket、spatial 和 array；角色函数输出消息，后续函数按所选策略读取。[消息定义](https://docs.flamegpu.com/guide/defining-messages-communication/index.html)、[Agent Communication](https://docs.flamegpu.com/guide/agent-functions/agent-communication.html)。

可借鉴：B1 规则计算的批处理、局部邻域/分桶消息访问、减少全人口两两扫描；DOD 优化先让固定字段和计算阶段明确，再判断是否值得 GPU 化。

不可直接套用：GPU 中的 agent 不等于 LLM agent，数值吞吐不能推导社会智能；稠密批处理也不会自动提供 B0 的个体连续性、认知记忆或跨 owner 事务。若瓶颈是 LLM、数据库或跨边界等待，搬迁规则算子未必降低端到端延迟。本次未做 FLAME GPU 与本项目的对比基准；项目历史 native/GPU gate 记录的纯积分占比约 4.87%，当时决策是 continue_python，不能据人口数量直接建议迁移 GPU。[历史规模记录](/D:/Paralls-phase0-1/docs/verification/population-data-oriented-closure.md:48)

维护边界：[发布页](https://github.com/FLAMEGPU/FLAMEGPU2/releases)查询时可见 `2.0.0-rc.4`，明确标为 Pre-release，不能称正式稳定 2.0；发布说明也记录了许可和工具链变化。本文不据旧版本安装说明做当前集成承诺。

## 7. NetworkX 与 OR-Tools：社会编译器更直接的算法参照

NetworkX 提供最短路与网络流算法，可作为空间可达性、资源流量和冲突分析中的算法候选。[Shortest Paths](https://networkx.org/documentation/stable/reference/algorithms/shortest_paths.html)、[Flows](https://networkx.org/documentation/stable/reference/algorithms/flow.html)。OR-Tools 提供约束求解，以及带容量、取送货和时间窗口的路径问题示例，可用于有限资源分配与时间表模板。[Constraint Optimization](https://developers.google.com/optimization/cp)、[官方示例](https://developers.google.com/optimization/examples)。

适配建议属于本次推论：以固定模板和已登记纯算子封装必要算法，只接受冻结输入，固定求解器版本、预算、排序与输出 schema；求解结果仍为候选，不能预留资源或挑选业务赢家。任意公式、运行时生成代码和自由工具写入都不属于附件的 V1 编译合同。首个小模板若用项目现有 helper/标准库即可表达，应先用最小实现；这份对照不是现在安装两项依赖的建议。

算法可行不等于社会政策合理。优化目标、家庭保护、权利限制和公平性约束必须来自已批准的玩法规则与参与策略，不能由求解器自行决定。

## 对本项目的落点

| 本项目设计问题 | 最有用的外部参照 | 仍需本项目验证的契约 |
| --- | --- | --- |
| B0–B3 统一模拟帧与参与策略 | Mesa 的时钟、激活和事件调度；AgentSociety 2 的批执行 | 各层共享输入版本；角色不能重复执行；到期义务不能因低保真丢失 |
| Character Core 与 B0 成员账本 | Generative Agents 的历史影响；AgentSociety 的状态/执行对象分离 | 降级再升级后身份、关系、资产、承诺、未决动作可对应原记录 |
| 冻结事实编译器 | NetworkX/OR-Tools 的固定算法；AgentSociety 2 是权限边界对照 | 仅编译不写世界；未知 IR 拒绝；过期 proof 不能通过执行前校验 |
| Siming 与事实 owner | Concordia 可借认知组件，默认 GM 不可直接充当 owner | Siming 建议拒绝或失败后没有伪成功事实 |
| 具身与局部 micro tick | Habitat 的执行/观测闭环；Mesa 的局部调度 | owner 确认后只使有关依赖失效；Godot 阻挡、超时、失败回到权威链 |
| 规则模拟性能 | FLAME GPU 消息策略与批处理 | 在真实分布下测总耗时、候选数量和存储成本，再决定是否迁移计算 |

三条有直接机制证据的冲突最值得保留：**Concordia 默认 LLM 裁决不等于 domain owner；AgentSociety CodeGen 执行不等于无副作用 IR 编译；Habitat/小镇场景状态推进不等于跨 Python/Godot 的业务确认。** 对这些项目借鉴组件和调度机制，比直接替换权威链更贴合当前设计。

本次资料对照没有找到可直接交付本项目完整组合的现成契约：B0 个体账本与可逆 handoff、共享 codebook 的版本治理、GameplayEventStore 原子结算、未来阵营对抗中的多 owner 协议。这些应保持为本项目明确的设计与验收责任；“未找到”不是对全部生态的不存在证明。

## 评估建议：同时验证工程正确性与行为有效性

以下是对照后的工程推论。replay、权限隔离、编译零写入能说明系统按契约运行；还要区分语义正确性、行为有效性与现实社会校准，不能把三者混成一个通过标记。先补齐的语义正确性指标包括：

- 约束满足：候选是否遵守技能、时间、位置、资源、参与策略和承诺约束；记录拒绝原因与违反率。
- 资源守恒：每次结算及批处理前后可核对库存、资金与成员分摊；合法的产出、消耗和销毁必须有明确来源。
- 跨保真连续性：同一角色经历 B3 → B0 → B3 后，相同保护字段及未决义务保持一致；允许变化的字段能追溯至 owner receipt。
- 扰动局部性：只改变一个已确认事件时，受其依赖影响的候选改变，无关候选保持；固定随机种子、输入版本和决胜顺序后再比较。

行为有效性还应有场景对照：相同资源和道路条件下，有照护承诺的角色与无照护承诺的角色应产生规则允许且可解释的差异；道路关闭后方案需要实质改变；与一个简单确定性启发式相比，新模型应在预先指定的成功率、约束违反率、计算成本或解释质量指标上证明价值。不要仅用自然语言“看起来合理”验收。

这些指标仍不等于真实社会模型已经校准。社会可信度、宏观分布和人类行为预测需要另设数据、对照与适用范围，不能由测试通过或角色叙述自然推导出来。

## 建议推进顺序与完成证据

1. **先把 9/16 的合同闭环做实。**围绕农民—村庄—洪灾的一条流程接通帧、参与策略、模块、成员账本、交接与社会协议；补足密码本和对应 DOD 阶段证据。热状态优化已经存在，不代表这套新合同的阶段 7 自动完成。
2. **编译器分级进入。**合同与固定纯算子的 shadow 可以作为独立验证切片；B0 advisory 需要参与策略与群体/个人边界；active 需要真实协议、完整冻结读集重验和 owner receipt。先证明一项成功、一项容量拒绝、一项 stale 拒绝，再增加模板。不要把首条社会协议闭环反过来依赖完整八类求解平台。
3. **具身后继按既定门禁进入。**9/16 阶段 0–7 有证据后，从现有门交互对齐 ESM/事实提交链，再加入一个高影响环境变化。证明确认、outbox、依赖过期拒绝、局部反应、断线恢复和 Godot 可见结果。
4. **阵营最后接入。**先跑通协作洪灾，再扩展双方共享世界、独立情报与确定性冲突窗口。阵营数、职业数和群体精度不能成为复制世界或另起 Siming 裁判的理由。
5. **生产工程作为并行验收线。**执行隔离、长局恢复、真实 provider 混合负载、表现 LOD、网络搬运和 CI 门禁分别取证。不能用历史 provider-disabled 的短窗规模数据替代。

建议最终使用同一条可观察的因果验收：Godot 上报道路阻断证据 → Owner 确认道路版本变化 → 即使反应队列尚未处理，旧运输候选也在提交时被拒绝 → 受影响分片重新计算 → 受保护家庭请求 B3 交接 → 新协议结算 → 场景展示确认或失败结果。它可以同时暴露三份设计之间的缺口，比先铺满战争贸易模板更有判别力。

本报告交付为静态分析与外部资料研究；未声称当前项目已完成上述运行闭环，也未实施这些建议。
