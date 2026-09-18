---
name: harness-verification
description: Use when selecting Paralls verification profiles, interpreting failed or stale evidence, or cleaning verification artifacts and owned processes.
---

# Harness 验证与清理

先读 `docs/harness.md` 的命令入口；遇到重复失败或旧报告，按需读 `docs/harness-playbook.md` 对应案例。

1. 根据变更与交付声明选择检查。smoke 证明框架能运行；contract 证明静态契约；Godot、交互及跨边界声明需要实际 runtime 证据。广泛变更仍运行 `--profile all`。
2. 用 runner 统一执行。需要保留原始诊断时，在运行前通过 `--export-evidence` 指定仓库外空目录；默认输出在结束时删除。不要自己创建永久归档。
3. 只接受本次、对应输入版本的结果。非零退出码、本次报告缺失或断言失败均不通过，不能使用旧报告补齐。
4. **`max_attempts` 只是上限，不是重试理由。** 先确定故障类别；仅对配置明确允许、已识别的瞬时进程故障重试。未知失败、缺配置、环境阻塞、断言失败及证据损坏先定位原因，不靠剩余次数盲目重跑。
5. 资源只能由本轮拥有者回收。复用 backend 不等于拥有它；全新实例所需条件不满足时报告 blocked，不能按端口终止用户进程，也不能假定更换端口后契约仍成立。
6. 子任务保留父级尚需消费的证据，顶层完成汇总后再清理。本轮失败先提取最小定位信息，再清理本轮目录；不删除并行任务或用户原有资料。
7. 检查清理结果和目录实际内容，不能只凭 `git status` 判断 ignored 产物不存在。报告分别列出通过、失败/阻塞、未执行和清理失败；不把静态检查或候选格式检查写成运行时/编程效果提升。

一次只提出一个有复现依据的流程改进。更新被测流程时保持验收标准不变；有收益才保留规则，重复说明优先合并到现有手册。

本 Skill 的决策压力测试不证明端到端编程收益；实际效益和限制见 `docs/harness-skill-pilot.md`。
