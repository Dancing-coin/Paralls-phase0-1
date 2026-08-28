# Generative Agents 对群体模拟的参考评估

状态：`research note; primary-source review 2026-08-28; analysis only; no runtime authorization`

本笔记评估 Stanford/Smallville 项目 [Generative Agents: Interactive Simulacra of Human Behavior](https://github.com/joonspk-research/generative_agents) 对本仓库“司命受控群体模拟”的参考价值。结论先行：**有参考意义，但主要是角色认知与小规模社会涌现的实验参照，不是 PopulationPlanner、世界真相结算或生产调度器的可移植实现。**

## 一手事实

### 运行闭环

- `Persona.move(...)` 明确串起 `perceive -> retrieve -> plan -> reflect -> execute`；移动函数先更新当前时间/位置，再调用五个认知阶段，最后返回下一格、表情和动作描述（源码：[persona.py#L185-L231](https://github.com/joonspk-research/generative_agents/blob/fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4/reverie/backend_server/persona/persona.py#L185-L231)）。
- `ReverieServer.start_server(...)` 等待前端写入当前 step 的 JSON 环境文件，读取后更新后端 tile map，逐个调用 persona，再把 movement JSON 写回前端并将 `step` 与游戏时间推进（源码：[reverie.py#L279-L412](https://github.com/joonspk-research/generative_agents/blob/fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4/reverie/backend_server/reverie.py#L279-L412)）。论文将同一机制描述为每个 sandbox time step 的环境 JSON 交换循环（论文：[§5，Sandbox Environment Implementation](https://arxiv.org/abs/2304.03442)）。
- README 要求并发运行 Django 环境服务器和 agent simulation server；`run <step-count>` 每步代表游戏内 10 秒，并支持保存、fork、replay（README：[运行与回放](https://github.com/joonspk-research/generative_agents/blob/fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4/README.md#running-a-simulation)）。

### Memory stream（记忆流）、检索与反思

- 论文定义 memory stream 为带自然语言描述、创建时间和最近访问时间的经验记录；检索把 `recency`、`importance`、`relevance` 归一化后加权，并只把适合上下文窗口的高分记忆交给语言模型（论文：[§4.1 Memory and Retrieval](https://arxiv.org/abs/2304.03442)）。实现中的 `new_retrieve(...)` 对事件/思绪按最近访问时间、重要性和 embedding 余弦相似度打分，归一化后取前 `n_count` 条（源码：[retrieve.py#L132-L271](https://github.com/joonspk-research/generative_agents/blob/fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4/reverie/backend_server/persona/cognitive_modules/retrieve.py#L132-L271)）。
- 观察仅来自当前视野半径内、同一 arena 的事件，并受 `att_bandwidth` 和 `retention` 限制；新事件才写入关联记忆（源码：[perceive.py#L25-L181](https://github.com/joonspk-research/generative_agents/blob/fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4/reverie/backend_server/persona/cognitive_modules/perceive.py#L25-L181)；参数定义：[scratch.py#L14-L24](https://github.com/joonspk-research/generative_agents/blob/fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4/reverie/backend_server/persona/memory_structures/scratch.py#L14-L24)）。
- 反思不是每步都生成：实现以重要性计数耗尽为触发条件，抽取焦点问题、检索证据、生成带证据节点指针的高层 thought，再回写记忆流（源码：[reflect.py#L99-L185](https://github.com/joonspk-research/generative_agents/blob/fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4/reverie/backend_server/persona/cognitive_modules/reflect.py#L99-L185)）。论文报告实现阈值为 150，约每日反思 2-3 次（论文：[§4.2 Reflection](https://arxiv.org/abs/2304.03442)）。
- 关联记忆使用 JSON 节点、embedding 和关键词索引，并以本地文件夹保存/加载（源码：[associative_memory.py#L50-L79](https://github.com/joonspk-research/generative_agents/blob/fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4/reverie/backend_server/persona/memory_structures/associative_memory.py#L50-L79)、[L153-L240](https://github.com/joonspk-research/generative_agents/blob/fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4/reverie/backend_server/persona/memory_structures/associative_memory.py#L153-L240)）。这证明了“记忆作为派生认知层”的实验可行性，但不提供本仓库要求的 owner、privacy、revision、receipt 或 replay contract。

### Planning（计划）、schedule（计划表）与社会交互

- 论文的计划采用 top-down 递归细化：先生成一天的粗粒度 agenda，再细化到小时和 5-15 分钟动作；计划、反思和观察一起进入检索，计划也会根据新事件中途重生成（论文：[§4.3 Planning and Reacting](https://arxiv.org/abs/2304.03442)）。实现只在新的一天生成 wake-up hour、daily plan 和 hourly schedule，并把计划作为 thought 加入记忆（源码：[plan.py#L461-L513](https://github.com/joonspk-research/generative_agents/blob/fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4/reverie/backend_server/persona/cognitive_modules/plan.py#L461-L513)；总入口：[plan.py#L931-L1000](https://github.com/joonspk-research/generative_agents/blob/fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4/reverie/backend_server/persona/cognitive_modules/plan.py#L931-L1000)）。
- 社会交互以近场观察触发：系统先判断是否对另一 persona 说话或反应，再以双方关系摘要、相关记忆和最近对话生成 utterance；对话结果写回双方记忆（源码：[converse.py#L76-L179](https://github.com/joonspk-research/generative_agents/blob/fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4/reverie/backend_server/persona/cognitive_modules/converse.py#L76-L179)、[L257-L291](https://github.com/joonspk-research/generative_agents/blob/fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4/reverie/backend_server/persona/cognitive_modules/converse.py#L257-L291)）。论文的端到端指标覆盖 information diffusion、relationship formation 和 coordination（论文：[§7.1 Emergent Social Behaviors](https://arxiv.org/abs/2304.03442)）。
- 结构化环境与自然语言之间有双向翻译：agent 只维护自己见过的环境树子图，按视野更新；动作位置通过树遍历选出，再用传统寻路执行，物体状态由动作描述映射更新（论文：[§5.1 From Structured World Environments to Natural Language, and Back Again](https://arxiv.org/abs/2304.03442)）。

## 规模、性能和证据边界

- README 提供的基线是 `base_the_ville_n25`（25 agents）和 3-agent 版本（README：[Customization](https://github.com/joonspk-research/generative_agents/blob/fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4/README.md#customization)）；论文的群体实验是 25 agents 连续运行两个完整游戏日（论文：[§7 End-to-End Evaluation](https://arxiv.org/abs/2304.03442)）。这证明小镇级交互演示，不证明大规模人口模拟吞吐。
- 该端到端实验确实观察到可量化的社会涌现：论文报告两天后 mayor 信息知晓率约从 4% 到 32%、party 信息约从 4% 到 52%，关系网络密度从 0.167 到 0.74，12 名受邀者中 5 人到场（论文：[§7.1.2 Results](https://arxiv.org/abs/2304.03442)）。这些数字适合作为 branch/preview 的传播、关系和协调回归样本，不是生产人口事实或规模承诺。
- 论文明确记载：25 agents、两天的实验花费数千美元 token credits，并耗时数天；作者把并行化和专用模型列为后续性能方向（论文：[§8.2 Future Work and Limitations](https://arxiv.org/abs/2304.03442)）。README 也提示 API 限流可能导致挂起，建议频繁保存，且 agent 较多时成本较高（README：[Tips](https://github.com/joonspk-research/generative_agents/blob/fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4/README.md#tips)）。
- 论文报告的错误包括检索失败、记忆 embellishment（虚构性补写）、地点/物理规则误判、过度正式或过度合作；长时间运行还会因记忆和地点集合变大而更难检索与选址（论文：[§7.2 Boundaries and Errors](https://arxiv.org/abs/2304.03442)）。这些是把 LLM agent 结果当生产事实前必须保留的风险证据。

## 对本仓库的可采纳翻译

### 可采纳

1. **认知层检索策略**：把三因素检索、视野/带宽/保留窗口和反思证据链翻译为 Character Core 的五池记忆检索、`presentation_seed` 和近场 activation 上下文。对应 [12-角色模拟记忆种子与连续性设计](12-角色模拟记忆种子与连续性设计.md#L47-L61) 与 [03-群体模拟与角色分级连续性](03-群体模拟与角色分级连续性.md#L31-L43)。
2. **层级计划与升级**：把日程的粗到细分解翻译为 B0/B1 的行为种子；只有关系协商、重大冲突等高价值时刻才升级 B2/B3 近场 agent，并携带固定 budget、scope、source revision。对应 [03-群体模拟与角色分级连续性](03-群体模拟与角色分级连续性.md#L60-L66) 与 [09-行为分层与信息传播](09-行为分层与信息传播.md#L14-L18)。
3. **社会传播测试集**：用 party/information diffusion、关系形成和 coordination 作为 branch/preview 的可观测回归场景；指标只能验证传播假设和角色表现，不能代替领域 Owner 的业务结算。对应 [09-行为分层与信息传播](09-行为分层与信息传播.md#L26-L35) 与 [11-创作工具与观测闭环](11-创作工具与观测闭环.md)。
4. **可回放实验方法**：固定 step、seed、source revision、ruleset 和 trace，保留完整 replay/checkpoint-tail 证据；复用现有 `GameplayEventStore`、outbox 和 Harness。对应 [05-性能回放观测与渐进交付](05-性能回放观测与渐进交付.md#L41-L64) 与 [08-时间空间与推进内核](08-时间空间与推进内核.md#L15-L18)。

### 不可直接采用

- 不把每个远场角色接成每步 `perceive -> retrieve -> plan -> reflect -> execute` 的常驻 LLM 循环；论文自己的成本与时长已经说明这不能作为群体生产基线。远场应使用 PopulationPlanner 的确定性 B0/B1 cohort 计算，中场预热同一 `CharacterRecord`，近场才持 activation lock。
- 不把本项目文件夹/JSON/SQLite 状态当作 Paralls 的 truth store、event store 或记忆 owner。这里的 `ReverieServer` 由前端 JSON 驱动并直接回写 movement/object 状态（源码：[reverie.py#L311-L412](https://github.com/joonspk-research/generative_agents/blob/fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4/reverie/backend_server/reverie.py#L311-L412)），而 Paralls 要求领域 Owner 结算 world event、Character Core 结算角色连续性。
- 不把自然语言动作、模型反思或传播结果直接转成生产 world event；它们只能形成 `presentation_seed`、`activation_candidate` 或等待司命审阅的 `owner_bound_intent`。最终链路仍遵守 [01-司命受控能力面](01-司命受控能力面.md) 和 [13-群体模拟生产纵切与推进闭环设计](13-群体模拟生产纵切与推进闭环设计.md)。
- 不把 25-agent/两天的演示结果外推为规模、性能或文明演进证据；扩展前必须有固定输入、预算、未处理桶、公平性、失败回退和重放 Harness。

## 最终判断

Generative Agents 对本仓库最有价值的贡献是：**证明“局部观察 -> 派生记忆 -> 加权检索 -> 周期反思 -> 分层计划 -> 社会交互”能够在小规模 sandbox 中产生可观察的个体连续性和社会涌现。**它可以为 `PopulationPlanner` 的行为种子、近场 activation、传播回归样本和 Character Core 检索合同提供模式证据。

但它没有解决本仓库的生产边界：多领域 owner、受治理提交、revision/隐私、receipt、零写拒绝、可审计 catch-up 和大规模确定性调度。因此在 Paralls 中，它是 **SGC-2/SGC-3 的认知与实验参照**，不是新的 runtime、scheduler、event store、truth writer，也不能改变“司命统辖策略/准入/提交，PopulationPlanner 批量计算，领域 Owner 结算世界真相，Character Core 结算角色连续性”的设计。

## 主要来源

- 项目 README（运行、步长、25-agent 基线、保存/回放、成本提示）：<https://github.com/joonspk-research/generative_agents/blob/fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4/README.md>
- 论文全文（架构、社会实验、边界与限制）：<https://arxiv.org/abs/2304.03442>
- 固定源码版本：`fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4`（2026-08-28 `main`）。
- 核心源码目录：<https://github.com/joonspk-research/generative_agents/tree/fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4/reverie/backend_server/persona>
