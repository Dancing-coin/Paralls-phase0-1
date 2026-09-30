# 人口热路径优化实施计划

计划文件按仓库 `*-implementation-plan.md` 契约与同名设计配对。

> 执行：沿测试先行流程逐项实施；独立任务由 native subagents 负责，主代理集成及统一验收。

**Goal:** 实现已确认的四项局部优化并保存可复验的效果证据。
**Spec:** `docs/superpowers/specs/2026-10-01-population-hotpath-optimization-design.md`
**Architecture:** 保持原 owner、事务及恢复边界，只减少内部重复工作；未知长尾先测量。
**Tech Stack:** Python 3.13.9、SQLite 3.53.4、Pydantic、pytest、原 harness。

## 检查重点

动态 schema 注册和分组回滚；记忆重复 ID/相同排序键与 required refs；输入和别名隔离；JSON 验证与摘要等价；损坏 checkpoint 与重启恢复；诊断开销及源码冻结。

## 任务

- [x] 1. 独立证据目录、身份/硬件/依赖快照及前后基准已保存；冻结前扫描 282 个文件，未匹配项目真实凭据。
- [x] 2. registry JSON 缓存及 append 重复深拷贝优化完成；动态注册、输入/跨字段隔离、回滚及 durable 重开回归通过。registry 65 项、append 82 项 GREEN，前后输出摘要一致。
- [x] 3. 修改 `memory_recall.py`；RED/GREEN、196 项相关回归、400 组旧版等价检查及独占前后基准完成。
- [x] 4. 修改 `runtime_publication.py`；JSON/Python 严格拒绝语义一致，78 项相关回归及前后基准完成。普通检查点约减少 0.011ms，完整检查点未证明收益。
- [ ] 5. 对四局慢窗口拆分测量，保留原 thresholds；可复现证据确认某阶段后写回归和最小优化，否则继续归因并明确剩余不确定性。
- [ ] 6. 集成差异审查；全量 pytest、人口 correctness/recovery、change-lifecycle、all，记录 blocked/not run。
- [ ] 7. 冻结源码后原合同真实 provider short、soak/10×、2/4 局容量；记录源身份、完整窗口和离线复验。微基准收益不能替代正式通过。
- [ ] 8. 完整报告、清理本轮资源、diff/check/status；验证及报告完整后中文提交并推送 main，确认本地/远端 SHA，达成目标才将 Goal complete。

## 已获得的容量诊断

本轮四局各完整 600 秒诊断的 integrity/performance 复算均满足原门槛，但源码未提交，不能作为正式通过。p95 为 193.6--196.1ms、max lag 为 0.849--0.874、final backlog 为 0。最慢 tick 300 含 100 条 due_peak 与 28 条 regular_due；未复现旧 tick 371 的同步原生 SQLite 长尾。ETW 因 0x80070005 未启动；系统磁盘计数不能归因到进程或单次 flush。因此不新增未经证实的 checkpoint/I/O 策略。

慢 SQL 回调异常隔离及 shutdown 最终边界通过后，将在独立本地候选提交冻结源码。正式矩阵要求提交身份，最终合入 main 和推送仍以完整验证/报告为前提。
