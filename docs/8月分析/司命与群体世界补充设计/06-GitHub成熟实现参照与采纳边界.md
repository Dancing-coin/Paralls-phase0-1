# GitHub 成熟实现参照与采纳边界

状态：`research baseline; representative open-source survey completed 2026-08-17; not an adoption decision`

## 方法与结论

本轮按“可运行代码、明确系统边界、与群体模拟/记忆/表现相关”筛选代表性开源实现。它不是对 GitHub 的穷尽性搜索；后续正式 spec 只可引用已经在此记录了适用边界的模式。结论是：Paralls 应借鉴它们的**派生认知、分层调度、agent 组件和观测方法**，但不得借用任何一个项目的单一 sandbox、全局 Game Master、通用数据库 mutation 或自由 agent action 作为生产 truth writer。

| 参照 | 可借鉴模式 | 不可直接引入 | 对应主题 |
| --- | --- | --- | --- |
| [MiroFish](https://github.com/666ghj/MiroFish) | seed -> 图谱/GraphRAG -> persona/environment -> 并行模拟 -> 时间记忆 -> report 的工作流 | 平行数字沙盒的输出直接覆盖真实世界；全局上帝视角写入 | 02、03、05 |
| [OASIS](https://github.com/camel-ai/oasis) | 大规模 agent 分批、离散 action space、信息传播/推荐的分层建模 | 社媒 action 模型充当 3D 世界业务结算；以规模声明替代可回放证据 | 03、05 |
| [Generative Agents](https://github.com/joonspk-research/generative_agents) | memory stream、retrieval、reflection、plan、可回放模拟演示 | 每个 agent 高频 LLM 循环；文件夹存储替代 authority/revision/privacy | 02、03 |
| [Concordia](https://github.com/google-deepmind/concordia) | entity/component/prefab、环境 adjudication、agent intent 与 outcome 分离 | 单一 Game Master 作为所有领域最终裁判 | 01、03 |
| [AI Town](https://github.com/a16z-infra/ai-town) | 实时 presence、反应式前端投影、局部可见状态 | 单一数据库 mutation 作为跨域游戏事实语义 | 04、05 |
| [Sotopia](https://github.com/sotopia-lab/sotopia) | 社交情境采样、交互评估、环境/agent 分离 | Redis/JSON runtime 取代生产 replay truth | 02、03、05 |
| [AgentSociety](https://github.com/tsinghua-fib-lab/AgentSociety) | workspace-bound stateless agent、环境模块、任务分片、JSONL replay、tracing/benchmark | 引入 Ray/Redis/ServiceProxy 作为 Paralls 的第二 runtime、调度器、事件库或通用工具写面 | 03、05、07-11 |
| [KurrentDB](https://github.com/kurrent-io/KurrentDB) | expected revision、event-native stream、订阅读模型 | 新增第二个 event store 或把技术存储当 owner | 01、05 |

## MiroFish 的具体参考

MiroFish 的主流程是：seed extraction、个人/集体记忆注入和 GraphRAG 建图；抽取实体关系并生成 persona/environment；并行 agent simulation 与 temporal memory update；最后由 report agent 解释结果。这对应 Paralls 的三个可采纳点：

1. **图谱先于高成本 agent**：司命先从权威投影构造候选关系、压力和检索索引，再决定是否唤醒角色；
2. **记忆分层**：将长期摘要、局部事件、群体关系和时间更新分开，避免完整聊天历史塞进每个角色；
3. **推演报告与生产隔离**：推演形成 branch report、假设和证据，不直接成为 production event。

MiroFish 的“神视角注入变量”和平行世界设计只适合 Paralls 的隔离 preview branch。生产模式必须由现有 owner 验证并 append，图谱和 report 没有写入生产事实的权利。

## 统一采纳规则

任何外部模式进入设计前必须回答：它的输入是否是 scoped projection？它能否产生未经 owner 验证的事实？其记忆是否区分私有/公共/派生？其回放是否固定 source、revision、seed 与 ruleset？任一答案不满足时，只能作为实验/preview 参考，不能进入生产主链。

## 参照到本包的翻译规则

外部项目提供的是模式证据，不是可直接移植的模块。每次采纳都必须先将模式翻译为本仓库的受控对象，再由 matching formal spec 决定是否准入：

| 外部模式 | 允许翻译为 | 必须补足的 Paralls 合同 | 禁止的捷径 |
| --- | --- | --- | --- |
| MiroFish 的 GraphRAG/temporal memory | `StorylineThread`、`PropagationHypothesis`、派生检索索引 | provenance、双时间、visibility scope、source correction | 让 LLM/graph report 直接 append 生产 event |
| Generative Agents 的 memory/retrieval/reflection/plan | 五池记忆检索策略、行为种子、受控候选 | 私有边界、activation lock、revision merge/requeue | 为每个远场角色常驻完整 LLM |
| OASIS 的离散 action/批量调度 | cohort selector、action taxonomy、固定 budget profile | owner-bound capability、seed、未处理桶审计 | 把聚合模拟结果当库存、人口或关系事实 |
| Concordia 的 intent/outcome 结构 | 司命 candidate 与 owner receipt 的分离、角色壳组件 | owner-specific settlement、receipt、compensation | 复刻一个全局 Game Master |
| AI Town 的 reactive presence | `PresentationView` 局部刷新与临近角色壳 | scoped projection、mapping digest、privacy | 以 UI/database mutation 作为跨域写入协议 |
| KurrentDB 的 event-native 流 | expected revision、订阅和重放观测 | 复用 `GameplayEventStore`、现有 outbox | 为群体系统新增 event database |

**名称澄清：** Stanford 的“小镇”研究是 [Generative Agents](https://github.com/joonspk-research/generative_agents)，常被称为 Smallville；[AI Town](https://github.com/a16z-infra/ai-town) 是 a16z-infra 的另一项实时 AI agent town 实验。两者目标和运行模型不同，因此本包把前者主要用于记忆/计划/回放参考，把后者主要用于局部 presence 与反应式表现参考。

## 2026-08-17 GitHub 复核补充

本轮直接读取了 MiroFish、OASIS、Concordia、Generative Agents、Sotopia 和 AgentSociety 的公开 README/项目说明。以下是对后续群体模拟设计有实际影响的结论：

1. **MiroFish** 将 GraphRAG/seed、persona/environment 注入、并行模拟、时间记忆和 ReportAgent 组成一条研究工作流。Paralls 应把它拆成“派生图谱 -> cohort/agent 提示 -> branch report”，而不是让 report 或 God-view injection 修改 production truth。
2. **OASIS** 的离散 action、time step、推荐和传播机制证明了 action space、budget 和数据集版本必须是一等合同字段；其社媒数据库和百万规模宣传不是 Paralls 的运行时/容量设计。
3. **Generative Agents** 将记忆、检索、reflection、planning 和二维可视化结合，强化了“远场不跑完整 LLM、近场才加载高精度上下文”的三档模型；文件状态不被采用为生产 replay。
4. **Concordia** 的 entity/component/prefab 与 intent/outcome 分离适合行为上下文装配；它的单一环境 adjudicator 不适用于 Paralls 的联邦 owner。
5. **Sotopia** 的 scenario sampler 和 social evaluation 适合建立关系协商测试集、质量指标和回归样本；Redis/local JSON 只能作为实验实现参考。
6. **AgentSociety 2** 的 workspace-bound agent metadata、环境模块、可选推理模式、分布式任务、JSONL replay 和 tracing 说明群体系统需要明确工作单元、实验重放和观测数据。Paralls 只采纳“无状态工作单元 + 固定输入/trace”的方法，继续复用既有 runtime、event store、Harness 和 owner 写链。

这些结论已拆入 07-11：本体、时空推进、行为传播、校准恢复和创作观测。它们仍是分析设计，不构成依赖引入或运行时授权。
