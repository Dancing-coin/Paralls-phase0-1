# Plan 总入口

## 与 spec 的关系

每个执行计划必须能回指一个规格或明确的阶段级入口，并写清：

- 目标规格路径
- 依赖和执行顺序
- 修改文件范围
- 测试与 Harness 证据
- 未完成项、延期项和阻塞条件

## 当前计划树

| 计划树 | 对应规格树 | 用途 |
|---|---|---|
| [world-character-siming-authority-mainline](world-character-siming-authority-mainline/README.md) | [mainline specs](../specs/world-character-siming-authority-mainline/README.md) | 主线执行 |
| [current-project-intelligence-upgrade](current-project-intelligence-upgrade/README.md) | [incremental specs](../specs/current-project-intelligence-upgrade/README.md) | 增量专题执行 |
| 根目录日期文件 | 根目录历史/专题规格 | 历史计划、执行记录和未归树计划 |

## 计划文档分类

- `implementation-plan`：实现计划。
- `execution-prompt`：阶段级执行提示词。
- `audit / closure / matrix / register / decision`：计划状态、审计和门禁记录。
- `README`：计划树入口和依赖顺序。

计划文件不会自动证明实现完成；完成口径以代码、测试和 Harness 证据为准。
