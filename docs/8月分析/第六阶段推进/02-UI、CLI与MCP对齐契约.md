# UI、CLI 与 MCP 对齐契约

状态：`incremental design; P6B formal spec required before implementation`

创作者 UI 的 list 勾选/选择和编程智能体的 CLI/MCP 调整必须是同一控制面 API 的不同
transport。不能各自解析 YAML、各自写数据库或各自定义权限。

## 1. 统一工作流

```text
read authorized projection
-> create/patch draft
-> validate schema + capability + dependency
-> preview/simulate
-> produce diff + trace + warnings
-> editor submits review
-> admin approves/signs
-> stage/canary
-> activate at explicit revision boundary
```

UI 和 CLI/MCP 必须共享：

- command/schema version；
- project/content scope；
- expected revision 和 conflict response；
- validation error codes；
- preview result digest；
- audit and authorization decision。

## 2. 不同 transport 的允许差异

| 能力 | UI | CLI/MCP |
| --- | --- | --- |
| 列出可编辑字段 | server-filtered form/list | schema/field query |
| 修改草案 | typed form mutation | typed command/proposal |
| 运行验证 | preview/Harness button | verify/preview command |
| 查看 diff | scoped visual diff | machine-readable diff |
| 提交审批 | review action | review command |
| 激活/回滚 | admin-only action | admin-only command |

差异只在交互方式和输出格式，不能产生不同的 domain semantics。MCP tool 不是隐藏的
Python import 入口；它必须调用受治理的控制面能力。

## 3. 冲突和权限

同一 draft 的并发修改使用 expected revision。冲突返回可合并的 diff 或拒绝，禁止静默
覆盖。reader 的读取也必须经过 data classification；editor 不能因使用 CLI/MCP 获得
比 UI 更高权限。
