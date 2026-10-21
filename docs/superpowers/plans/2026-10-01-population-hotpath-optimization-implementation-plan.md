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
- [x] 5. 四局正式长尾拆分：tick 172 native commit 等待与物理盘排队重叠，provider 交集为 0；唯一底层原因未确定，不修改 FULL、checkpoint、fixture 和 thresholds。
- [x] 6. 第一轮集成审查与完整验证：全量 7507 passed / 2 skipped，人口 correctness、原 CLI recovery、change-lifecycle 通过；all 在 Godot 缺失处 blocked，其后 73 项 not run。注册 recovery profile 的夹具生成 900 秒超时失败保留，完整原 CLI 另行通过。
- [x] 7. 第一轮冻结 e26d0e19，真实 provider short、完整 soak/10× 和 2/4 局容量及原离线复验全部执行。两局通过；四局、10×、两小时未通过，原始失败证据完整保留。
- [x] 7a. 第二轮新库索引 43 项、TLS 定向 102 项回归通过，独立审查未发现重大问题。索引相同快照少 3 页，wall 仅下降 0.35%，不声称显著提速；TLS 32 请求由 96 个 context 降至 1，临时 Client/pool 全关闭。短基准不证明正式性能通过。
- [x] 7b. WS 发送恢复 RED 2 failed / 6 passed、GREEN 26 passed；精确 code/reason、新 epoch 实际基线与健康 cutoff 证明保持，错误关闭继续失败。
- [ ] 7c. 第二轮全量 7532 passed / 2 skipped / 19 warnings，退出 0；主仓镜像与候选源码/导入身份一致。必要 profiles 和冻结新 SHA 下的完整正式窗口待执行；第一轮结果不能代替最新提交结果。
- [ ] 8. 完整报告、清理本轮资源、diff/check/status；验证及报告完整后中文提交并推送 main，确认本地/远端 SHA，达成目标才将 Goal complete。

## 已获得的容量诊断

此前未提交源码的四局 600 秒诊断满足门槛，第一轮正式 e26 四局则失败，两份记录均保留。正式最差 tick 172 的提交等待约 455--480ms，与物理盘平均写延迟约 36ms、队列 26 重叠；未达到 provider 触发点。ETW 因 0x80070005 未启动，物理计数不能唯一归因到进程、文件或单次 flush。因此不新增未经证实的 checkpoint/I/O 策略。

第二轮改动在独立候选中验证；正式矩阵要求提交身份，最终合入 main 和推送仍以完整验证/报告为前提。证据保存在仓库外，文档完成状态不替代 verifier 结果。
