# Harness Reliability

## Evidence Retention

`.harness/retention-policy.json` 定义 schema 2：`system-temp`、默认 `delete`、`explicit-export`，导出必须位于仓库外。`run_scope` 执行目录所有权与清理；静态 checker 通过仅证明配置有效。

顶层创建唯一 `run_id` 和系统临时目录，嵌套调用复用上下文。每个 profile attempt 使用独立子目录；聚合完成后由顶层统一清理。失败、超时和可捕获取消走同一清理路径，清理失败必须出现在最终摘要中。不可捕获的强制终止可能留下系统临时目录。

默认运行没有永久 latest、baseline 或 runs 归档。需要诊断或发布原始证据时使用 `--export-evidence`，目的目录必须在仓库外且不存在或为空。CI 上传方设置 7 天有效期并清理导出副本；本地导出由调用方明确管理。经审查的经验进入 `docs/harness-playbook.md`，最小复现输入进入测试夹具或 `.harness/evolution/`。

## Result Identity

结果与当前 `run_id`、profile、attempt、revision 绑定；声明报告缺失、退出码非零、旧轮次报告、旧 attempt 或执行中源码变化都不能判定成功。缺少 Godot/backend 的结果是 blocked 或明确的环境失败，不能用静态通过代替 runtime 验收。

## Local And Hosted CI

`.harness/ci/local-ci-gate.ps1` 保留 focused tests、编译、完整 `all` 和 `mainline-unified-runtime` 范围，并逐条传播原生命令失败。缓存位于本轮系统临时目录。

`.github/workflows/harness.yml` 的 hosted 工作只提供 smoke/contract 静态覆盖，明确没有 Godot/backend runtime 与 release 验收覆盖。配置存在不等于 hosted 执行已验证；本地执行和 hosted 执行应分别报告。

## Clean State

使用 `.harness/clean-state-checklist.md` 检查运行摘要、文件与进程清理及静态输入可提交性。`.harness/quality-document.md` 与 features 台账描述实现能力，不缓存实时通过状态。删除原始证据后，文字摘要只记录结论，复核需要重新运行或读取显式导出的原始证据。

## Reference Coverage

新增工具、权限或验证边界时读取 `.harness/templates/HARNESS_CHECKLIST.md`。`harness-reference` 检查 reference coverage，即 `.harness/references/awesome-harness-engineering.json` 的来源映射；引用材料不自动成为项目执行指令。
