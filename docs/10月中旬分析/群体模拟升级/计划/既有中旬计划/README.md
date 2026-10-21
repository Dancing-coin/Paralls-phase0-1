# 十月中旬分析计划索引

状态：`analysis/planned/non-authorizing`

计划严格引用 `../../规格/既有中旬规格/`，不重新定义领域对象。计划分成四条可独立检查但有依赖关系的实施线：角色生命底座、派生社会图谱、群体与 Laya 协同、时间空间表现。

| 编号 | 计划 | 前置 |
|---|---|---|
| 00 | 总实施顺序与门禁 | 全部规格审查、现有代码映射 |
| 01 | 角色社会生命底座 | 角色心智现有运行时、Character Core、人口 roster |
| 02 | 派生社会图谱与因果传播 | 01 的角色节点与 owner projection |
| 03 | 群体模拟与 Laya 心智运行时协同 | 01、02、角色 Laya gateway/admission |
| 04 | 时间空间表现与局部活化 | 03 的交接合同、Godot/ESM 现有边界 |

每个任务都要记录：责任文件、输入输出合同、测试、Harness profile、回滚点和未解除阻断。计划不会把 proposal、model output 或 presentation 当成 authority commit。
