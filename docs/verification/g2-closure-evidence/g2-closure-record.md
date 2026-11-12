# G2 三切片收口记录

2026-11-12。本文根据文档仓库 `docs/superpowers/specs/2026-11-09-architecture-v2-execution-spec.md` 的 G2 退出条件和 2026-11-11 负责人选定的三切片口径，记录已有证据及不足；不宣布 G2 已通过。性能候选阈值尚非已批准的生产 SLO。

## 逐项状态

1. **读取边界清单：满足清单记录要求，不等于全部授权。** [read-path-inventory.md](../g2-visibility-budget/read-path-inventory.md) 以 `1177f1e0` 的 AST 盘点 987 个调用点、113 个文件：可信权威/恢复 67、面向主体 49、未判定 871。未判定明确不默认可信；名称盘点不覆盖动态别名，统计不是当前 HEAD 重新盘点。当前切片的接入点另有标注。
2. **可见性切片：限定范围满足已有正反行为证据。** 仅已绑定发起者读取自己的 v2 proposal；未绑定、错误主体、未知或已知无权 session 等拒绝；发送前复核、旧事件不投影、伪造 bus 消息不投影及重放证据见 `backend/tests/test_embodied_interaction_session.py` 和 [session 证据](../g2-session-visibility-denial/README.md)、[读取清单](../g2-visibility-budget/read-path-inventory.md)。本轮测量也实际收到允许字段的正向响应，但不替代全部权限测试。参与者、观察者、送达者路径未完成，其他参与者正向路径阻塞于同 tick 在场证据的权威来源。按 [PRD 核查](closure-checks.md)，PRD 未要求双角色 session 握手；按负责人授权，本次不纳入 Demo/G2 新增范围，后续独立处理。一般命令送达和面对面体验要求并未取消。
3. **known_time：满足已选有限切片的记录和测试口径，不能宣称完整读取过滤。** 社交送达 Owner 提交事件记录世界 tick，领域视图按获知时间处理并保留旧事件兼容与回放；证据为 [社交送达记录](../g2-social-delivery-known-time/README.md)。session proposal 由 Owner 在写入时记录世界 tick，绑定发起者投影携带该值；无时钟时写 v1 且不投影，见 `backend/tests/test_embodied_interaction_session.py` 和 [session 全量归档](paralls-session-slice-20261111-corrected-postcommit/results.json)。其他 session 受众的读取侧 known_time 过滤未做；网络到达不是本项，`presented_time` 属 G5。
4. **authority epoch：存储层限定切片有正反及兼容证据，生产覆盖不满足。** `e8c430b2` 引入登记/快照，`56ac6eb5` 在 Store 实现栅栏；测试入口为 `backend/tests/test_authority_epoch_snapshot.py`、`backend/tests/test_authority_epoch_fence.py`，全量结果见 [registry 归档](paralls-epoch-registry-postcommit-20261111/results.json)、[fence 归档](paralls-epoch-fence-postcommit-20261111/results.json)。默认不启用，当前无生产流受保护；在实际 Store 数据库事务边界的测试不证明生产 publisher、在线 handoff 或 UE 本地权威。首流 publisher 接线、受理冻结、恢复证据及在线交接等移至 B4 前置设计。旧快照兼容样本为派生 fixture，非历史生产归档，见 `backend/tests/fixtures/authority_epoch_legacy/README.md`。
5. **性能：原两轮“超出”保留；优化后补测已完成，预算待项目负责人定。** 原两轮 4,096 事件 WebSocket p95 为 160.28 / 160.62 ms，原始样本和结论不删改。修改前分解中整流读取占主体检查耗时中位数的 98.67%，读取 p95 96.50 ms。`38e57119` 只在主体检查中按 proposed 类型过滤并 limit=1，不加缓存、不改 Owner/Store 或投影语义；新代码第 1 轮在 10/20/100/4,096 档的正向 WebSocket p95 为 0.3810/0.4296/0.4966/1.0291 ms，4,096 档主体检查 p95 为 0.2148 ms。全部分布、原始样本、环境和版本见 [性能记录](perf/README.md)、[新原始数据](perf/session-websocket-pull-post-filter-round1.json)及[原因与等价性](perf/proposal-filter-analysis.md)。仅作候选建议：session 流 ≤100 事件时正向读取 p95 <40 ms；4,096 档作扩展性检查，目标是不再随无关事件线性增长。当前内存 Store 仍线性筛选，不能凭单轮或速度改善声称渐进成本消失。相对基线只有局部旧 handler，完整旧服务器无可比基线，10% 相对增量对本路径不适用。早期 10%/40 ms 来自合成实验，不是生产 SLO。小规模本次样本虽低于建议绝对值，也不代替预算决策；本测试仍是单进程内存 Store/真实回环 TCP，不是生产 spawn host、持久库或远程网络。
6. **缺证据时明确拒绝：所选切片正反行为有测试证据；未外推到清单其他调用点。** 上述 session 否定响应为明确错误码；epoch 对缺失或不匹配上下文拒绝，精确重试和同键异 digest 按既有合同处理。证据范围同上，不证明所有 871 个未判定调用点满足此要求。
7. **已知与未知 session 的响应和游标：内容有覆盖，时序未验证。** 相关测试见 `backend/tests/test_embodied_interaction_session.py`；这不能证明时序不可区分。远程身份接入前须复查时序及真实凭证边界。
8. **Godot / 基线 / 未决项：未作为 G2 全链路验收。** `scripts/verification/EmbodiedInteractionSessionProbe.gd`、`EmbodiedHandoffProbe.gd`、`EmbodiedCarryPlaceProbe.gd` 的旧 live 成功预期与当前拒绝不兼容，本轮未运行 Godot live probe；session 需要受信绑定后才能验证允许读取，handoff/carry-place 仍需各自可信披露与授权证据，不能仅补绑定就放行。`D2–D10` 仍 OPEN。三次[归档与 G0 的机器可读比较](archive-verification.json)中，既有节点阶段结果不变，39 个失败经约定归一化后签名不变；这是原始运行归档对照，非本轮全量复跑。 本轮另在 `38e57119` 提交树执行全量：10,079 收集、10,036 passed、39 failed、4 skipped（含 2 xfailed）；相对 G0 及 `56ac6eb5` 原节点和阶段均无变化，新增 2 项通过，见[提交后全量记录](paralls-session-proposal-filter-postcommit-20261112/README.md)和[比较](paralls-session-proposal-filter-postcommit-20261112/comparison.json)。
9. **记录完整性：已纠正运行归属，不补造证据。** [数字与 PRD 核查](closure-checks.md)将 `0b587890` 的 `10,044/10,001` 与对应 zip 对上；copy-loop 的 `10,034/9,991` 对应 `3985e986`，不能证明优化提交 `59084f36` 的全量运行。文档仓库状态页的公开 origin 勘误仅提交本轮新增段，保留原有未提交内容。

## 结论和负责人表态

**三条选定功能切片及本次等价性/全量证据已有记录；性能收口预算待项目负责人定，扩展性仍有线性筛选限制，不能据新样本自行宣布 G2 通过。原两轮“超出”保持有效历史记录。G2 通过不改变任何生产流的保护状态。**

需要项目负责人表态：

- 确定本路径性能预算：是否采用 ≤100 事件 p95 <40 ms 的建议，以及如何处理 4,096 档仍存在的线性类型筛选；10% 相对增量对本路径不适用，不把局部旧 handler 当完整旧服务器基线。
- 在预算决策和上述有限切片边界下，是否接受 G2 收口；本记录不代为宣布通过。
- 后续何时为实际需要的 session 参与者建立同 tick 在场的可信来源并接入，及何时安排 B4 publisher、在线 handoff 与恢复设计。
- 远程身份接入前的时序侧信道复查、Godot live 授权与各 probe 的后续验证计划。
- 代码 origin 目前公开且本地归档含用户名路径；对仓库可见性、未来公开或拆分产物中的这些文件按既有决定自行处理。本文不推送、不变更可见性。

## 待办 / 限制：session Owner 重启存在性核查

Owner 的 `_sessions` 仅在内存初始化（`backend/app/services/embodied_interaction_session_service.py:46`），`propose:65` 仅查该字典；重启后状态恢复仍是独立限制。但“因此可追加第二个 proposal”经核实不成立：提案固定幂等键（`:118`）及 Store 的持久重试检查（`backend/app/gameplay/event_store.py:285` 起）仍生效。独立 Durable Store 创建提案、关闭重开及新 Owner 实证：同 digest 返回原 receipt（`duplicate_replayed`），不同 causation/digest 返回 `idempotency_key_reused`，最终一条 proposal、revision 1。不能把内存存在性缺失直接写成重复提案漏洞；这也不证明 Owner 已有完整状态恢复。未修改 Owner。非空流初次提案可以不是 revision 1，读取必须继续选择首个 proposed；两条 proposal 的等价性 fixture 并非 Owner 正常产生它们的证据。详见 [核查记录](perf/proposal-filter-analysis.md)。
