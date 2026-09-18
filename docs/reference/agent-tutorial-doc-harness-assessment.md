# `agent-tutorial-doc` Harness 参考与当前项目优化建议

## 调研范围

参考仓库：[`zwt0204/agent-tutorial-doc`](https://github.com/zwt0204/agent-tutorial-doc)

本次以 2026-09-15 的提交 [`975c88d`](https://github.com/zwt0204/agent-tutorial-doc/commit/975c88d502be46a31de14f3474e29d7a2776de78) 为准，重点检查：

- [`README.md`](https://github.com/zwt0204/agent-tutorial-doc/blob/975c88d502be46a31de14f3474e29d7a2776de78/README.md)
- [`docs/zh/s20-harness.md`](https://github.com/zwt0204/agent-tutorial-doc/blob/975c88d502be46a31de14f3474e29d7a2776de78/docs/zh/s20-harness.md)
- [`agents/s20_harness.py`](https://github.com/zwt0204/agent-tutorial-doc/blob/975c88d502be46a31de14f3474e29d7a2776de78/agents/s20_harness.py)
- [`agents/base.py`](https://github.com/zwt0204/agent-tutorial-doc/blob/975c88d502be46a31de14f3474e29d7a2776de78/agents/base.py)
- [`tests/test_all.py`](https://github.com/zwt0204/agent-tutorial-doc/blob/975c88d502be46a31de14f3474e29d7a2776de78/tests/test_all.py)
- 权限、Hook、上下文压缩、API 韧性、任务 DAG、异步、Inbox、协议、Worktree、MCP 章节源码和文档。

## 参考项目值得借鉴的结构

### 1. 先固定主循环，再向循环外围增加能力

参考项目把核心循环固定为“请求模型 → 执行工具 → 追加工具结果 → 继续或结束”，权限、Hook、压缩、重试和动态提示都在循环边界上接入。第 20 章明确把“循环不变、逐章累加、工具即接口、安全边界前置”作为组装原则。

这比在每个验证脚本中自行处理状态更容易审计。当前项目可以把同一原则应用到 Harness runner：Profile 只负责声明检查和输出，调度、超时、失败分类、证据收集、清理由 runner 统一负责。

### 2. 生命周期点是最小的横切扩展面

参考项目定义了 `UserPromptSubmit`、`PreToolUse`、`PostToolUse`、`Stop` 四个 Hook。Hook 返回 `False` 可以阻止后续执行，适合输入校验、权限拦截、日志和状态保存。[`docs/zh/s04-hooks.md`](https://github.com/zwt0204/agent-tutorial-doc/blob/975c88d502be46a31de14f3474e29d7a2776de78/docs/zh/s04-hooks.md)

当前 Harness 可采用等价的四个 runner 生命周期：`before_run`、`before_profile`、`after_profile`、`after_run`。这样清理、摘要、失败归因和审计不需要散落到 300 多个 profile 脚本中。

### 3. 权限和审计必须位于副作用之前

参考项目使用 `ALLOW / ASK / DENY / ASK_ONCE` 四态策略，并强调 fail-closed；工具调用会记录工具、参数、权限决策和结果摘要。[`docs/zh/s03-permission.md`](https://github.com/zwt0204/agent-tutorial-doc/blob/975c88d502be46a31de14f3474e29d7a2776de78/docs/zh/s03-permission.md)

当前 Harness 会启动 Python、Godot 和其他 profile 脚本。优化时应在 runner 统一记录“profile、命令、工作目录、超时、退出码、清理结果”，并在配置损坏或未知 profile 时拒绝执行，避免由单个脚本决定安全边界。

### 4. 上下文和证据应分层保留

参考项目的上下文压缩分为三层：每轮静默裁剪旧工具结果、超阈值后保存 transcript 并摘要、模型显式触发 compact。[`docs/zh/s08-context-compact.md`](https://github.com/zwt0204/agent-tutorial-doc/blob/975c88d502be46a31de14f3474e29d7a2776de78/docs/zh/s08-context-compact.md)

对应到当前项目，运行证据也应分三层：

1. 进程内状态：仅供当前 profile 使用；
2. 本次运行摘要：只保留每个 profile 的状态、退出码和失败原因；
3. 原始日志、trace、截图、数据库：默认临时目录，运行结束删除，只有显式保留或失败诊断时才导出。

当前 [`.harness/retention-policy.json`](../../.harness/retention-policy.json) 仍把 latest baseline、diff 和 run archive 作为默认产物；这与“验证完成后只保留必要内容”的目标不一致，应改为显式保留策略。

### 5. 长任务需要可恢复的控制面

参考项目把简单 TODO 和带依赖的 Task DAG 分开：TODO 解决当前会话漂移，Task DAG 持久化任务、依赖、负责人和可执行状态。[`docs/zh/s05-todo.md`](https://github.com/zwt0204/agent-tutorial-doc/blob/975c88d502be46a31de14f3474e29d7a2776de78/docs/zh/s05-todo.md)、[`docs/zh/s12-task-engine.md`](https://github.com/zwt0204/agent-tutorial-doc/blob/975c88d502be46a31de14f3474e29d7a2776de78/docs/zh/s12-task-engine.md)

当前项目已有 Goal、Superpowers、profile registry 和 change lifecycle，不应再复制一套通用 TODO。可借鉴的是：把一次 Harness 运行视为带依赖的任务图，至少能表达“静态检查通过后才允许运行 Godot”“失败 profile 不触发后续集成检查”。

### 6. 失败恢复、异步任务和隔离应是通用能力

参考项目提供指数退避和断路器、后台任务轮询、JSONL Inbox、结构化协议以及 Git Worktree 绑定。[`docs/zh/s11-api-resilience.md`](https://github.com/zwt0204/agent-tutorial-doc/blob/975c88d502be46a31de14f3474e29d7a2776de78/docs/zh/s11-api-resilience.md)、[`docs/zh/s13-async.md`](https://github.com/zwt0204/agent-tutorial-doc/blob/975c88d502be46a31de14f3474e29d7a2776de78/docs/zh/s13-async.md)、[`docs/zh/s15-inbox.md`](https://github.com/zwt0204/agent-tutorial-doc/blob/975c88d502be46a31de14f3474e29d7a2776de78/docs/zh/s15-inbox.md)、[`docs/zh/s16-protocols.md`](https://github.com/zwt0204/agent-tutorial-doc/blob/975c88d502be46a31de14f3474e29d7a2776de78/docs/zh/s16-protocols.md)、[`docs/zh/s18-worktree.md`](https://github.com/zwt0204/agent-tutorial-doc/blob/975c88d502be46a31de14f3474e29d7a2776de78/docs/zh/s18-worktree.md)

当前项目不需要为 Harness 引入完整 Agent 协作运行时。优先只吸收两个边界：profile 超时后的可诊断失败状态，以及运行时验证的隔离工作目录。消息总线、Cron 和 MCP 属于后续需求，不能因为参考项目有章节就加入。

## 参考项目的实现限制

参考仓库是教程，不应直接当作生产实现：

- [`agents/s20_harness.py`](https://github.com/zwt0204/agent-tutorial-doc/blob/975c88d502be46a31de14f3474e29d7a2776de78/agents/s20_harness.py) 实际只组装了权限、Hook、Skill、Memory 和 TaskEngine；第 20 章文档列出的 Inbox、Worktree、Cron、协议和 MCP 并未全部接入同一个实现。
- `tests/test_all.py` 只运行 11 个离线测试，未直接验证 `s20_harness.py` 的完整组合；README 的“11 tests passed”是教程级 smoke check，不是端到端 Harness 证明。
- `agents/base.py` 的 `run_bash` 使用 `shell=True`，`safe_path` 只做工作区路径约束。教程同时声明了权限和沙箱思想，但示例代码仍需要生产级命令白名单、超时、输出上限和错误分类。
- `s19_mcp.py` 的工具发现和调用是占位实现，不能作为真实 MCP 安全边界的依据。

因此，本仓库应借鉴边界和生命周期设计，不应复制教程中的状态存储、MCP、Shell 或 Agent loop 实现。

## 对当前 Harness 的优化优先级

### P0：把证据生命周期改成“默认临时，显式保留”

当前 runner 会无条件写入 `.harness/verification/` 的 latest 报告、baseline、diff、失败 digest 和 `runs/<run-id>/` 归档。建议：

1. 每次运行在系统临时目录创建 evidence root；
2. 结束时只输出一份短摘要和必要的失败定位信息；
3. 成功运行默认删除原始证据；
4. 失败运行默认保留受限的失败摘要，原始证据通过 `--retain-evidence` 或 CI artifact 开关保留；
5. 清理放在统一 `finally` 生命周期中，并检查目标路径必须位于 evidence root；
6. `baseline`、run archive 和截图不再默认作为长期文件。

### P0：把 profile 分成少量验证层级

当前 `.harness/profiles/` 有大量领域 profile。建议保留现有领域 profile，但由 registry 提供四个稳定入口：

| 层级 | 内容 | 目的 |
| --- | --- | --- |
| `smoke` | registry、规则解析、清理、报告序列化 | 秒级确认 Harness 自身没坏 |
| `contract` | docs、boundaries、backend-contract、godot-project | 不启动长运行时 |
| `runtime` | Phase 0、mainline 和按需领域 runtime | 需要进程或 Godot |
| `release` | `contract` + 明确选定的 runtime 集合 | CI/发布门禁 |

`all` 应成为明确的 release 别名或显式确认入口，避免日常任务误触发数百个 profile。

### P1：统一 runner 生命周期和失败分类

将 `before_run → before_profile → execute → after_profile → after_run` 固定在 `scripts/verification/harness.py`，并让每个 profile 返回结构化结果：`passed`、`disposition`、`evidence`、`cleanup`。至少区分：配置错误、环境缺失、断言失败、超时、进程崩溃和未验证环境。这样报告可以直接指导下一步，而不是只显示退出码。

### P1：给 Harness 自身增加离线 smoke 矩阵

参考项目用无 API Key 的 `tests/test_all.py` 快速验证各章节组件。当前项目也应有一个小型、无 Godot、无网络的 runner smoke 集合，覆盖 profile registry、规则加载、结果聚合、失败 digest、临时目录清理和 retention policy。它只证明 Harness 能运行，不替代领域 profile。

### P2：引入最小的运行隔离

运行时 profile 使用临时工作目录或显式 worktree，禁止把日志、SQLite、截图和生成资源写入源码树。需要跨任务并行时再引入 Worktree；单次顺序验证不需要复制完整协作运行时。

### P2：只在真实需求出现时增加 Agent 协作机制

参考项目的 Inbox、Protocol、Cron、MCP、自治 Agent 等章节可作为后续扩展索引，但当前游戏运行验证没有证明这些机制是必需的。先完成证据生命周期、验证层级、失败分类和离线 smoke，再评估是否需要引入。

## 建议的最小落地顺序

1. 修改 retention policy 和 runner 清理生命周期，并补一个成功/失败清理测试。
2. 增加 `smoke`、`contract`、`runtime`、`release` 四个入口，保留原 profile 名称兼容调用。
3. 统一 profile 结果协议和失败 disposition。
4. 将 `.harness/verification/` 改为默认临时输出，文档、AGENTS 和 CI 只保留同一条规则。
5. 运行离线 smoke，再按需运行 runtime；成功后检查 `git status --short -- .harness`，确认没有生成物残留。

这份调研只产生文档，没有修改 Harness 代码，也没有把参考仓库文件复制到当前项目。
