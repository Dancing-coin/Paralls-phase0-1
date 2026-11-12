# Session 提案查找：归因、等价性和 Owner 限制

2026-11-12。优化提交 `38e571198deae2767d0d0e91142cbf2ebccb347a`；没有修改 session Owner、Store、其他调用方或加入缓存。`main.py` 只有 `_session_initiator_event` 的读取参数改变，原有 schema、字段和资格检查保留；pull 与发送前复核共同使用它。

## 修改前归因

修改前 HEAD `ff03bb80`，G0 Windows 11 / Python 3.12.2，复用原测量脚本的 4,096 事件 fixture。直接调用主体检查，预热 5 次、采样 30 次，以 wrapper 计时真实 `read_stream`，另计单个 proposal 投影构造。此处为上一轮诊断的汇总数据，未保存该次逐样本值，不把它当作原始样本归档，也不把直接调用等同于 WebSocket 往返。

| 部分 | n | p50 ms | p95 ms | max ms |
| --- | ---: | ---: | ---: | ---: |
| 整流 read_stream | 30 | 51.8761 | 96.5028 | 98.2368 |
| 主体检查总计 | 30 | 52.5924 | 97.2421 | 99.0005 |
| 单 proposal 投影构造 | 30 | 0.0279 | 0.0324 | 0.0356 |

逐样本读取占比的中位数 98.67%；非读取部分中位数 0.7221 ms。原诊断的 p95 取排序后的 `int(.95*(n-1))` 位置，与 WebSocket 脚本线性插值略有不同，不作精确同口径比值。pull（`backend/app/main.py:6862`）和发送前复核（`:3717`）各执行一次；主要成本为两次整流读取深复制，不是单个投影构造。

代码依据：`backend/app/gameplay/event_store.py:439`–`:454` 先切片/过滤/limit，最后逐事件 `_copy_event_for_read`；`:56` 的 helper 对 payload 含 list 等非标量内容走深复制。原 fixture 的所有历史事件均含列表，因此旧调用会复制整个流。新调用按 event_type 过滤并 limit=1，只复制第一条匹配事件；内存 Store 的类型筛选仍遍历流，未变成 O(1)，不能声称严格没有随流长增长的部分。Durable 的 `:1434`–`:1443` 在 SQL 中过滤、按 revision 排序并 limit；表达式索引定义于 `:951`。

## 等价性范围

原规则是“按 revision 顺序取第一个 proposed，再检查 schema_version==2”，不是“找第一个 v2 proposal”。新读取先过滤相同 event_type，再限一条；后续检查不变。测试 `test_session_pull_selects_first_proposal_across_stream_histories` 分别使用内存及 Durable Store，覆盖空流、只有其他事件、proposal 在 revision 2、追加第二个 proposal 后仍返回同一投影、首条 v1 时拒绝，以及 v1 后有 v2 仍拒绝。完整 session 文件定向结果 26 passed；旧绑定先行测试的 spy 仅适配新增查询参数，不改变断言。

这些行为用例在修改前已有的案例先通过，再在优化后复验；它们是行为保持的特征测试，不声称曾观察到业务断言失败。首条 v1 后再有 v2 的用例在优化后补充通过。没有增加重复实现算法的性能阈值单测。

## Owner 静态推导与独立重开实证

- **静态推导：** `embodied_interaction_session_service.py:46` 的 `_sessions` 是内存字典，`:65` 仅查内存；`:99`–`:117` 提案写一条 proposed，`:606` 用当前 Store head 而非固定 0。因此在正常空流首次提案时 revision 为 1，但非空流上的提案也可在 revision 2 或更后。读取优化不依赖 revision 1。
- **静态推导：** `app/models/embodied_interaction.py:434` 对参与者仅设最少两人，没有固定人数上限。按固定 N 个不同参与者、每个非发起者接受一次、每人终态观察一次的成功路径，事件数为 `1+(N-1)+1+1+N+1 = 2N+3`；双人常见为 7 条。发起者也调用一次 accept 可多一条（accept 幂等键 `:206`）；这是正常路径推导，不是任意 Store 历史或外部恢复下的全局上限。4,096 档是扩展性 fixture，非正常双人生命周期。
- **已实证，结论为否：** “重启后同一 session ID 可能由 Owner 再追加第二个 proposal”不能仅从内存检查推出。独立临时 SQLite 创建提案→关闭→重开→新 Owner 时，`session_state` 为空；同参数精确重试返回 `duplicate_replayed` 和原 event ID，改变 causation 则 `idempotency_key_reused`，最终 proposal 数为 1、revision 为 1。未改 Owner。
- **代码依据：** 提案固定幂等键 `interaction_session:<id>:propose`（`:118`），digest 由 session_id 和 causation_id 计算（`:119`）；Store `_prepare_append`（`event_store.py:285` 起）先比较同键 digest，原收据重放或拒绝。该保证以完整保留幂等记录为前提，不意味着 Owner 已完成状态恢复；在场证据和恢复设计仍独立待办。测试中的第二条 proposal 由独立 Store fixture 用另一幂等键构造，用于保护现有读取行为，不宣称 Owner 能正常产生它。

## 预算口径

**待项目负责人定。** 候选建议：session 流不超过 100 事件时，正向读取 p95 <40 ms；4,096 档仅作扩展性检查，目标是不再随无关事件线性增长。此建议尚非验收结论；当前内存 Store 仍有线性类型扫描，数据只能证明本次 fixture 上的分布，不能证明渐进复杂度已消除。10% 相对增量因无完整旧服务器基线，对本路径不适用；局部历史 handler 比例仅诊断。原候选来自 `../../g2-visibility-budget/report.md` 的早期合成实验，不能直接当作生产 SLO。

原两轮数据和“超出”结论原样保留在 `session-websocket-pull-results.json` 及 README 原表。新代码测量为独立的一轮，不改写旧样本，也不宣布 G2 通过。
