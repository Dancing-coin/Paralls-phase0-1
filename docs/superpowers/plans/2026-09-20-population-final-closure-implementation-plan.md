# 千人六项闭环最终执行补充

Status: execution_in_progress; godot_unverified; current_population_ceiling_1000

承接 `2026-09-16-population-production-runtime-closure-implementation-plan.md` 的六项范围、阈值和 G0—G9；不得以本补充的一项完成代替总目标。设计依据：`../specs/2026-09-19-activation-receipt-evidence-cost-design.md`。起点 `c23d879e0d27d4ad7ef023d3edcc24aae2a9ef8d`。执行工作树为 `D:/MyConfiguration/TCLXUSER/.codex/worktrees/pfc/Paralls-phase0-1`。

## Task 1: 激活证据分离

- 修改 `backend/app/population_continuity/models.py` 的 ActivationReceipt：证据类型区分 none/commit/full_replay；提交证据记录原 AppendBatchResult.global_sequence_range，replay_hash 为空；拒绝不携带提交证据。
- 修改 `activation.py`：删除全局 ReplayResult 缓存，成功回执仅消费已提交结果；新增显式 `audit_receipt`，读取该回执提交序号截面并使用原 full_replay 算法。后续其他 Owner 写入不得改变旧截面的审计结果。失败审计不能包装成成功。
- `test_population_continuity.py` 先更新旧隐式审计测试并新增跨 Owner / 非字典序事件 / 持久化重开 / 重复请求 / 无写入拒绝 / 审计失败测试。运行时禁止 read_events 和 full_replay/continue_replay，显式审计仍核对原 hash、事件和 revision。
- 修改 `verify_phase3a_profile_activation.py` 在审计边界显式取证；运行时其他消费者继续使用 commit 证据。
- 扩展混合负载和恢复 cache 指标及复验器，覆盖 activation receipts 与历史投影缓存；不得将缺失字段当作零。历史投影必须为零，已定义的 receipt 限额仍为32。
- 检查：先观察新增测试失败，再运行激活、continuation、持久化恢复、混合指标和验证器回归；所有失败先定位，不放松现有门槛。

## Task 2: 正确性、审查与源码冻结

- 一次 fresh-context 全分支审查，核对运行时提交与显式审计语义、失败原子性、证据消费兼容及指标真实性；修复重要问题并回归。
- 运行完整 backend、相关工具测试、population-runtime-correctness、change-lifecycle；禁止在本机调用 Godot。mainline/all 需要外机真实证据，继续标记未验证。
- 固定 Python3.12.14 和 ci-constraints，记录运行环境；仅使用本地 .env，禁止输出/提交密钥。
- 冻结实现提交后才进入正式性能采集。任何源码修复都使不匹配的旧证据失效。

## Task 3: 同版后端正式验收

- 串行采集服务隔离：100/1000 人各120秒，真实 WebSocket 时序、10ms心跳、单 writer 和 provider 等待分离。
- 千人长历史：1000/10000个历史窗口、tail8、各5次独立冷恢复；保留真实造档和恢复原始结果。
- 传输：1000人、30窗、5配对、manual_window_cost；核对 WS 原包、逻辑SQLite字节、同 seed/hash/oracle及改善判定。
- mixed short：100/1000人各30窗1×；soak：两档各30分钟、各30窗10×、千人另2小时。1×必须满足既定800ms/积压/lag门槛；10×完整保留性能结论。
- 多局：2/4个独立千人后端，各600秒；容量不足保留实际测量，证据缺失不可当作容量不足而通过。
- 每个采集入口使用新的仓库外证据目录；完成后用同源码对应复验器核对。不可并行运行无关基准、裁短、删除故障窗口或复用旧版本成功结果。

## Task 4: CI、外机交接与总聚合

- 核对可重建 CI 和当前提交远端运行；沿用会话的提交推送授权，按 cherry-pick 合回 main，保护用户 tmp/。
- 整理同版外机命令及 evidence.json；population Godot、InteractionSession runtime JSON、mainline/all、Archive Door批准绑定、VLA真实凭据缺项分别列出。Godot导入提前退出按用户决定暂缓。
- 运行六项聚合器，只接受原始证据复验。更新主计划/交接文档为真实结果和精确阻塞。只有所有必要门禁通过才将 Goal 标为 complete；外部阻塞不能伪造闭环。

## 正式短验收暴露的 L3 提示词缺陷

- `9b74197f` 的100/1000人服务隔离及导出复验通过。真实模型short中千人档通过；100人档性能通过，但L3返回`goal_portfolio.status=pending`，原validator拒绝后Character作业stale，矩阵失败，不能用千人档通过代替整矩阵。
- 根因：提示词只说明goal_portfolio是目标列表，没有提供其状态枚举等嵌套合同。由原`CharacterGoalPortfolioEntry.model_json_schema()`直接生成提示词约束，保持validator严格拒绝pending；不映射状态、不放宽stale门禁、不添加自动成功回退。
- 回归先观察提示词缺合同失败，再核对提示词中各合法状态均能被原validator接受，以及实测非法pending仍被拒绝。模型gateway/provider/L3共131项通过；使用原失败请求及新提示词的真实DeepSeek诊断通过且无fallback。这不是正式矩阵证据。
- 重新冻结此修复后重采service、short及其余性能证据；旧`9b74197f`证据保留诊断，不混入新版本总聚合。远端run35487905677的harness/change-lifecycle及correctness失败尚缺具体日志，本地同版两项通过不替代远端结论。

## Review Focus

检查非激活 Owner 历史增长、重复回执晚于其他写入时的截面、未提交结果、损坏/截断事件和持久库重开；不得以局部digest冒充full_replay。审查指标是否实际观察缓存及所有复验入口是否拒绝缺字段；不修改Godot导入、耐久性、事务与权限契约。
