# G2 三切片收口记录

2026-11-12。本文根据文档仓库 `docs/superpowers/specs/2026-11-09-architecture-v2-execution-spec.md` 的 G2 退出条件和 2026-11-11 负责人选定的三切片口径，记录已有证据及不足；不宣布 G2 已通过。性能候选阈值尚非已批准的生产 SLO。

## 逐项状态

1. **读取边界清单：满足清单记录要求，不等于全部授权。** [read-path-inventory.md](../g2-visibility-budget/read-path-inventory.md) 以 `1177f1e0` 的 AST 盘点 987 个调用点、113 个文件：可信权威/恢复 67、面向主体 49、未判定 871。未判定明确不默认可信；名称盘点不覆盖动态别名，统计不是当前 HEAD 重新盘点。当前切片的接入点另有标注。
2. **可见性切片：限定范围满足已有正反行为证据。** 仅已绑定发起者读取自己的 v2 proposal；未绑定、错误主体、未知或已知无权 session 等拒绝；发送前复核、旧事件不投影、伪造 bus 消息不投影及重放证据见 `backend/tests/test_embodied_interaction_session.py` 和 [session 证据](../g2-session-visibility-denial/README.md)、[读取清单](../g2-visibility-budget/read-path-inventory.md)。本轮测量也实际收到允许字段的正向响应，但不替代全部权限测试。参与者、观察者、送达者路径未完成，其他参与者正向路径阻塞于同 tick 在场证据的权威来源。按 [PRD 核查](closure-checks.md)，PRD 未要求双角色 session 握手；按负责人授权，本次不纳入 Demo/G2 新增范围，后续独立处理。一般命令送达和面对面体验要求并未取消。
3. **known_time：满足已选有限切片的记录和测试口径，不能宣称完整读取过滤。** 社交送达 Owner 提交事件记录世界 tick，领域视图按获知时间处理并保留旧事件兼容与回放；证据为 [社交送达记录](../g2-social-delivery-known-time/README.md)。session proposal 由 Owner 在写入时记录世界 tick，绑定发起者投影携带该值；无时钟时写 v1 且不投影，见 `backend/tests/test_embodied_interaction_session.py` 和 [session 全量归档](paralls-session-slice-20261111-corrected-postcommit/results.json)。其他 session 受众的读取侧 known_time 过滤未做；网络到达不是本项，`presented_time` 属 G5。
4. **authority epoch：存储层限定切片有正反及兼容证据，生产覆盖不满足。** `e8c430b2` 引入登记/快照，`56ac6eb5` 在 Store 实现栅栏；测试入口为 `backend/tests/test_authority_epoch_snapshot.py`、`backend/tests/test_authority_epoch_fence.py`，全量结果见 [registry 归档](paralls-epoch-registry-postcommit-20261111/results.json)、[fence 归档](paralls-epoch-fence-postcommit-20261111/results.json)。默认不启用，当前无生产流受保护；在实际 Store 数据库事务边界的测试不证明生产 publisher、在线 handoff 或 UE 本地权威。首流 publisher 接线、受理冻结、恢复证据及在线交接等移至 B4 前置设计。旧快照兼容样本为派生 fixture，非历史生产归档，见 `backend/tests/fixtures/authority_epoch_legacy/README.md`。
5. **相较改动前路径的性能测量：执行过局部历史 handler 对照，但完整旧服务器的相对开销无可比基线；候选绝对目标不满足。** [测量方法与两轮完整结果](perf/README.md)和[原始数据](perf/session-websocket-pull-results.json)：真实回环 WebSocket、当前 component app、已绑定发起者、单进程内存 Store；4,096 事件当前路径 p95 160.28 / 160.62 ms，均超候选 `<40 ms`，分类“超出”。历史 handler 共享当前 Store 与发送门、旧协议和事件版本也不同，无法证明完整版本相对增量 ≤10%。当前测试并非生产 spawn host、持久库或远程网络。未加缓存、未改变运行时、未测第三轮；性能是否可以作为收口依据仍需负责人决定。
6. **缺证据时明确拒绝：所选切片正反行为有测试证据；未外推到清单其他调用点。** 上述 session 否定响应为明确错误码；epoch 对缺失或不匹配上下文拒绝，精确重试和同键异 digest 按既有合同处理。证据范围同上，不证明所有 871 个未判定调用点满足此要求。
7. **已知与未知 session 的响应和游标：内容有覆盖，时序未验证。** 相关测试见 `backend/tests/test_embodied_interaction_session.py`；这不能证明时序不可区分。远程身份接入前须复查时序及真实凭证边界。
8. **Godot / 基线 / 未决项：未作为 G2 全链路验收。** `scripts/verification/EmbodiedInteractionSessionProbe.gd`、`EmbodiedHandoffProbe.gd`、`EmbodiedCarryPlaceProbe.gd` 的旧 live 成功预期与当前拒绝不兼容，本轮未运行 Godot live probe；session 需要受信绑定后才能验证允许读取，handoff/carry-place 仍需各自可信披露与授权证据，不能仅补绑定就放行。`D2–D10` 仍 OPEN。三次[归档与 G0 的机器可读比较](archive-verification.json)中，既有节点阶段结果不变，39 个失败经约定归一化后签名不变；这是原始运行归档对照，非本轮全量复跑。
9. **记录完整性：已纠正运行归属，不补造证据。** [数字与 PRD 核查](closure-checks.md)将 `0b587890` 的 `10,044/10,001` 与对应 zip 对上；copy-loop 的 `10,034/9,991` 对应 `3985e986`，不能证明优化提交 `59084f36` 的全量运行。文档仓库状态页的公开 origin 勘误仅提交本轮新增段，保留原有未提交内容。

## 结论和负责人表态

**G2 以三条切片收口的前提条件目前不具备：正向 session 读取的两轮候选绝对性能均超限，完整旧服务器相对测量无可比证据；是否接受该缺口属于负责人决策。G2 通过不改变任何生产流的保护状态。**

需要项目负责人表态：

- 如何处理两轮超出候选 40 ms 的正向读取性能，以及无完整旧服务器相对基线的事实；若继续优化，另定范围和验收。
- 在上述性能缺口及各有限切片边界下，是否接受 G2 收口；本记录不代为宣布通过。
- 后续何时为实际需要的 session 参与者建立同 tick 在场的可信来源并接入，及何时安排 B4 publisher、在线 handoff 与恢复设计。
- 远程身份接入前的时序侧信道复查、Godot live 授权与各 probe 的后续验证计划。
- 代码 origin 目前公开且本地归档含用户名路径；对仓库可见性、未来公开或拆分产物中的这些文件按既有决定自行处理。本文不推送、不变更可见性。
