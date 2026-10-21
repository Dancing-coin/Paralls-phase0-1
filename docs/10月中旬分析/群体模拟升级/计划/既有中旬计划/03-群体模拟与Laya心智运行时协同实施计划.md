# 群体模拟与 Laya 心智运行时协同实施计划

状态：`analysis/planned/non-authorizing`

**Spec：** [规格 01](../../规格/既有中旬规格/01-Laya心智快循环与群体模拟协同规格.md)、[规格 03](../../规格/既有中旬规格/03-群体模拟B0-B1与角色智能体B2-B3交接规格.md)、[规格 04](../../规格/既有中旬规格/04-司命调度自主焦点与世界因果规格.md)。

**来源：** 十月角色 01/02/05/08/09/10/11/13；Laya 部署和质量决策见 `docs/10月分析/角色/01-角色心智模型与模型驱动运行时设计.md` 与 `02-Laya快循环与快慢思考战斗设计.md`；十月实现审查 03/04/08。

## 1. 目标

让 B0/B1 的低成本候选可以安全交给角色智能体；激活后完整运行 L1-L4，以 Laya 连续做当前决策，Slow/Deep 只在升级条件出现时重规划，随后重新交回 Laya。通过同一个 actor lock、frame revision、Owner receipt 和 Character Core receipt 闭环。

## 2. 前置条件

- Plan 01 的 actor identity、cursor、continuity 和 memory admission 已通过 Gate 1。
- Plan 02 至少提供带 scope/source/revision 的候选图谱查询，或消费者能够显式运行 graph-degraded direct read。
- 角色 01/02/05/08/11/13 的原设计已被对应 implementation spec/plan 覆盖和审核。
- Laya 的 provider adapter、候选 compiler 和 admission 必须以十月计划的正式实现顺序核验；裸 `/v1/systemone` 服务探针不能代替后端集成。

## 3. 预期文件责任

| 区域 | 责任 |
|---|---|
| `backend/app/character_agent/gateway/` | 专用 Laya adapter、provider capability 和调用证据 |
| `backend/app/character_agent/services/cognition_admission.py`、`cognition_coordinator.py` | 持久 stage prepare/accept/freeze/resume/cancel/recovery |
| `backend/app/character_agent/mind/` | MindFrame/ThoughtMode/candidate 与 envelope/policy 的受控消费 |
| `backend/app/character_agent/planning/` | L3 语义最终选择由模型合同承接，本地只做硬校验 |
| `backend/app/character_agent/execution/l4_executor.py`、`l4_adapter.py` | typed intent 到执行契约的既有边界 |
| `backend/app/services/siming_runtime.py`、`siming_population_capability.py` | 候选/预算/activation dispatch，不转成 Laya owner |
| `backend/tests/test_character_laya_provider.py` 等 | adapter、候选、gate、恢复和真实边界证据 |

当前工作树已有未提交角色 runtime/Laya 相关改动；实施前必须基于最新 worktree 逐文件核对，不能覆盖用户修改，也不能假设它们已通过验收。

## 4. 任务序列

### Task 1：统一决策来源和精度标签

为 B0/B1 modules、Laya、Slow/Deep、脚本和人类控制输出定义 source/fidelity/revision metadata。来源类型须让调试、回放、评估和表现层区分 approximation 与真实模型 choice。

**测试：** 来源标记贯穿 stage receipt、L4 contract、owner receipt 和 observability；不能在任一 adapter 中被擦除或混淆。

### Task 2：角色智能体 Laya decision window

1. 按已存在 `CharacterTurnContext` 冻结 L1/MindFrame、active ThoughtMode、goal portfolio、profile/dossier、能力来源和 source revisions。
2. 从 action registry/target/affordance/execution contract 构造完整候选宇宙 `U` 和可审计的呈现集 `P`。
3. 固定官方 Laya multilingual checkpoint 和真实 `/v1/systemone` 请求 schema；输入只使用冻结角色帧及候选。
4. 调用专用 Laya adapter，并让 provider response 通过角色 admission 和 output gate。
5. Laya 选择 `action + target`；choice 不生成领域事实、运动轨迹或自由执行参数。
6. L4 二次校验 action commitment、stop/fallback/expiry；Owner 再校验权限、资源、版本和物理证据。

**验证：** provider contract、candidate coverage、choice quality、latency、cancellation、late result、stale frame、Owner settlement 和 visible result 各用独立证据。

### Task 3：ThoughtMode 输入合并与主动感知

1. 同一个心智模型接收多个 ThoughtMode 的 scoped input，不创建多个 agent brains。
2. Laya 对当前唯一 intent 作选择；后台目标和未胜出 mode 留作 goal/context，不静默删除。
3. 信息不足时可输出 typed `information_request`；L1 通过感知/行动路径获取结果。
4. 未知/过期/冲突信息带 freshness/conflict/revision；不能直接查完整世界数据库。
5. 观察、询问、试探和回想遵循角色 10 的 memory boundary。

### Task 4：Slow/Deep 的异步重规划

1. 严格使用十月确定的路由：先检测本地是否有可用 LLM，没有/不可用时使用 API；此路由不改变 Laya 模型。
2. Slow/Deep 输入携带原 actor/frame revision、触发原因、scope、预算、expiry 和 cancel handle。
3. 输出仅能更新 goals/modes/short plan/information needs/uncertainty；不能创建 Owner intent success。
4. 新 frame 通过 revision 校验后交回 Laya 再选当前动作。
5. 取消、过期、停机、迟到和 provider 失败都保留可回放状态。

### Task 5：群体候选 handoff 与唯一推进权

1. 复用 activation/handoff lock；取得 lock 后 freeze B0 cursor。
2. 按 Plan 01/02 的 input pins 建交接包，不把图谱全文或 population report 送给 Laya。
3. L1 根据 actor scope 重建私有 MindFrame；Laya 对当前动作重新决策。
4. 激活期间 cadence due 保留在队列，不推进同一 actor。
5. Owner receipt → Character Core continuity receipt → private memory materialization → graph projection 分别结算/恢复。
6. 释放 lock 后从最后接纳 cursor 恢复低精度推进。

### Task 6：司命与自主焦点

1. 候选来源统一接入 world event、due、relationship spread、region、organization duty、player interaction、fairness seed、narrative obligation。
2. Planner 保持纯提议，Siming 按 scope/policy/budget 作治理决定。
3. fairness seed 必须可重放、受限、不主动制造戏剧事实；以长期未处理/覆盖缺口作为补偿来源。
4. 记录 deferred age、区域覆盖、焦点来源分布、玩家交互占比和 starvation max。
5. 叙事义务影响 priority，但不重写角色的 profile、记忆、能力或选择。

### Task 7：Laya 质量门禁

严格沿用十月规格 05 和审查 03/04 的路线：

- 注册动作/目标/affordance/执行合同建立完整 `U`，实测受控呈现集 `P`；
- 使用结构化可接受动作集合，而非单一 teacher answer；
- 基础选择质量轨关闭受控失误，角色表现轨按 fixed seed 开启；
- 训练/开发/校准/final 留出按 scenario trajectory 隔离；
- 题目错误、候选缺陷、模型选错、adapter/admission、Owner execution 和 Godot presentation 分开归因；
- 输入与题集正确但官方模型关键决策未达冻结阈值时，本批才触发必要领域微调；Slow/Deep 回退不得算 Laya 通过。

### Task 8：B/C 真实场景

B 单角色连续 Boss 和 C 双角色连续协同为必验。使用隔离新 Godot 场景；动作底座仅使用 `StreetCombatActorDemo` 已验证 Actor/action library/Motor/authority/qualification；不复用 `StreetCombatDemo` 场景语义。通过 A 或 provider 探针不代表 B/C 完成。

## 5. 测试与证据

复用角色 `test_character_cognition_*`、`test_character_mind_frame_*`、`test_character_laya_provider.py`、`test_character_output_admission_gate.py`、`test_character_runtime_projection_integration.py`、`test_character_agent_activation_handoff.py`、`test_siming_population_capability.py`、`test_siming_generalized_population_decision.py`、`test_siming_story_graph_runtime.py` 和 `test_siming_story_obligation_runtime.py`。

每阶段 fresh evidence 要求：

1. Laya provider 真实请求/响应和 adapter schema。
2. 完整 U/P candidate coverage 与模型质量两轨数据。
3. cancel/expiry/stale/recovery 的真实 stage receipt/replay。
4. Owner settlement 与 Character Core receipt 分别存在。
5. B/C Godot 场景可见结果与 backend evidence 对齐。

命令以 `docs/harness.md` 对应 profile 为准；Broad integration 完成后执行 `python scripts/verification/harness.py --profile all`。

## 6. 回滚点

- Laya provider 关闭后将角色转入已批准 continuity floor 或 requeue，不改变模型选择质量统计。
- Slow/Deep queue 关闭后 Laya 继续执行允许的局部循环。
- 新 ThoughtMode 停用不删除 profile/goal/memory，只撤销该输入投影。
- autonomous focus 停用时保留 due/fairness cursor；恢复后不重复结算。
- 每个 B/C scene 可隔离回滚，不影响已有 `StreetCombatActorDemo` 验证底座。

## 7. 阻断

- Candidate compiler/admission 未有真实注册来源前，不运行正式 Laya quality claim。
- provider service 成功不能替代 backend adapter、actor admission、L4/Owner/replay。
- 样本、阈值和硬件成本未冻结前，不决定模型质量达标或启动微调。
- B/C Godot 未获真实边界证据前不宣称战斗智能体闭环完成。
