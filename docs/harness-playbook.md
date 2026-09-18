# Harness 操作手册

按失败现象读取对应案例。运行方法与当前证据契约以 [Harness 指南](harness.md) 为准；这里仅保留经源码和回归确认的根因、边界与复现方法。来源基线为 `bb3ea2bb96c5e082400c1e935cc30119df367caa`，修复记录对应本次 Harness 工作流变更；基线本身不包含修复。

2026-09-18 本次工作树的清理、执行结果、evolution 与相关静态门禁组合回归已通过 76 项。下面两个案例的对应测试包含在该次运行中；这个记录不代表之后 revision 已验证，也不证明 Skill 效果。

## 案例一：验证结束后保留了运行产物

- **触发场景：** 重复执行 Harness，或对子 profile 完成后立即清理其目录。
- **失败现象：** 固定 latest/baseline/runs 目录持续积累；清理旧输出后历史分析没有输入，或提前删除父级聚合需要的报告。
- **确认的根因：** 基线 `common.verification_dir` 固定写入仓库目录，`harness._write_harness_report` 同时创建固定归档；文档要求删除产物，而 lifecycle checker 又要求保留归档。各脚本没有共享的目录所有权和顶层清理责任。
- **最小修复：** `run_scope` 创建本轮系统临时根，子调用复用；所有消费者完成后顶层 `finally` 清理。必要证据在清理前显式导出到仓库外；演化分析仅消费显式输入。
- **适用范围：** Harness 生成的报告、日志、缓存、隔离副本及拥有的进程。用户已有文件、复用 backend、静态配置和业务持久化不属于清理目标。
- **验证命令：** `python -m pytest -q -p no:cacheprovider scripts/verification/tests/test_run_context.py`。
- **验证结论：** 该组回归检查嵌套不提前删除、异常后清理、保留无关文件、显式导出和危险路径拒绝；具体本轮结果见交付摘要，不能把本条静态记录当作以后 revision 的实时通过证明。
- **失效条件：** 新入口绕过 run_scope、引入新产物位置、或消费者跨进程传递协议变化时，重新审查生命周期并补充回归。

## 案例二：旧成功报告影响当前结果判断

- **触发场景：** 仓库存在上一轮成功报告；本轮脚本没有生成声明报告、退出码非零，或下一次 retry 沿用上一 attempt 文件。
- **失败现象：** 基线 retry 判断读取固定路径中的第一个 `overall_*` 布尔值，无法证明它来自当前实际执行。该缺陷影响重试判断；基线仍返回失败退出码，不能据此声称它已经把失败最终改成成功。
- **确认的根因：** `_result_artifact_exists` 没有 run/attempt 身份边界；固定目录允许陈旧报告被查到。旧 dirty revision 摘要仅使用 Git 状态文字，同一个脏文件再次编辑可得到相同标识。
- **最小修复：** 每个 attempt 使用独立目录，报告与退出码同时决定结果；按 run_id、profile、attempt、revision 绑定本轮证据，使用内容身份检测执行中源码变化。依赖报告通过本轮索引引用。
- **适用范围：** 自动重试、聚合、结果归一化和 evolution 引用校验。格式通过不证明真实 provider/Godot 成功，也不证明 Skill 效果。
- **验证命令：** `python -m pytest -q -p no:cacheprovider scripts/verification/tests/test_harness_execution.py scripts/verification/tests/test_harness_evolution.py`。
- **验证结论：** 回归覆盖旧仓库报告不被复用、退出码与声明结果不一致、缺少 Godot、内容 revision 改变，以及缺失/篡改/身份不符的评估拒绝；具体本轮结果见交付摘要。
- **失效条件：** 成功字段、报告 schema、revision 算法或 replay set 变化时，重新运行相关用例并重新审查评估集合摘要。

## 使用经验与提出改进

先确认根因，再保留一条短规则或最小回归。失败频率只说明需要调查。每次只提出一项候选改动，保持验收标准独立；候选无独立评估时保持 `effectiveness=not_evaluated`。拒绝候选保留简短原因与来源 revision，不保留完整执行轨迹。
