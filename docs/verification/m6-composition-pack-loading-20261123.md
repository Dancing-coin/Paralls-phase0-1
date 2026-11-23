# M6 组合声明的规则包加载接线

## 范围与合同

加载器现在接受 `reactions` 和 `play_patterns` 内容。Reaction 从本包解析后的命令目录及调用方提供的可信命令输出 FactType 集合编译，整张 Reaction 图一起检查回路。包中的条目 ID 必须与显式声明的 ID 一致。Play pattern 引用本次编译的 Reaction、Pipeline、Workflow，以及已解析的规则包版本。

此切片扩展 `LoadedPack` 返回字段与 `load_pack` 的可选参数，不新增持久事件。旧规则包省略这两类内容时返回空的只读映射。命令输出清单由调用方提供，生产命令登记和提交后的调度仍见 H-A-011 至 H-A-013。

独立验证提交为 `876133edba8a0d8b28a433c7c075ccab3d3d089b`，位于本轮临时 worktree `F:/codex-temp/a-m6-2-8cb4ecca`。

主分支接线提交为 `6e7da420221c8a7ca4f3fb762153b2542e5b004c`。变更为 `backend/app/gameplay/rule_pack_validator.py` 增加 42 行、`backend/tests/test_l5_reaction.py` 增加 69 行。两文件与独立验证提交逐字节一致，Git blob 的 SHA-256 及读取命令原始输出在 `F:/paralls-verification/thread-a/c-2a0a004b/static-evidence.json`。

## 已验证

Python 3.12.2，SQLite 3.43.1。每次运行从对应 worktree 根设置 `PYTHONPATH=<worktree>/backend`，核验 `app.__file__`。TEMP、TMP、TMPDIR 使用 F 盘短路径。

- 实现前新增加载测试为 4 failed。实现后 `python -m pytest -q -p no:cacheprovider backend/tests/test_rule_pack_validator.py backend/tests/test_l5_reaction.py backend/tests/test_l5_play_pattern.py backend/tests/test_l5_workflow.py` 为 133 passed、2 warnings。原始输出在 `F:/paralls-verification/thread-a/c-8cb4ecca/red.txt` 和 `targeted-final.txt`。
- 在上述独立提交使用 `run_baseline.py --repo <worktree> --output <run>/reaction --test tests/test_l5_reaction.py`，14 passed、2 warnings，退出 0。原始输出在 `F:/paralls-verification/thread-a/c-8cb4ecca/reaction.txt`。Reaction 登记选集由本次结果更新，新增四个正常加载与拒绝路径节点。

- 在该独立提交使用 `compare_selection.py --repo <worktree> --selection <selection.json> --output <run>/<selection>` 跑五组冻结选集 1,169 节点和十四组登记选集 119 节点。19 组共 1,288 节点，各组 `problems=0 improvements=0`，全部退出 0。命令编排和原始输出分别在 `F:/paralls-verification/thread-a/c-8cb4ecca/run-selections.py` 和 `F:/paralls-verification/thread-a/s-45fd4db6/`，后者含 `summary.json`。

主分支 `6e7da420` 在对应 worktree 根设置 `PYTHONPATH=F:/codex-temp/paralls-v2-thread-a-bond-20261121/backend`，`app.__file__` 为同一目录下的 `backend/app/__init__.py`。环境核验原文在 `F:/paralls-verification/thread-a/c-2a0a004b/environment.txt`。

使用 `run_baseline.py --repo F:/codex-temp/paralls-v2-thread-a-bond-20261121 --output F:/paralls-verification/thread-a/c-2a0a004b/full --freeze` 串行全量，收集 10,562 节点。原始汇总为 `24 failed, 10534 passed, 2 skipped, 2 xfailed, 239 warnings in 1450.66s (0:24:10)`，退出 1。运行期间 HEAD 和源码哈希固定。G0 JSON 将 xfail 合入 skipped，`counts.skipped=4`，本文分别列出 pytest 原始状态。

按 `(test_name, phase, error_type)` 与 Workflow 的 `9eb80fe9` 比较，新增 0、恢复 0。相对冻结 `3bf3418e` 的 22 项，仍多出两项此前已有的本地失败，分别为 `tests/test_population_cold_ready_gate.py::test_cold_ready` 的 KeyError，以及 `tests/test_population_recovery_measurement.py::test_recovery_owner_probe_measures_original_startup_before_full_oracle` 的 AssertionError。原始日志、JUnit、环境、节点结果、退出码和两份比较文件位于 `F:/paralls-verification/thread-a/c-2a0a004b/`。

SQLite 3.43.1 导致两个要求 SQLite 3.51.3+ 的并发 WAL checkpoint 节点跳过，该环境差异延续冻结基线。两个 xfail 和两个跳过项保留原状态。`harness.py --profile all`、真实 Godot/UE 和 M6 生产执行验收未运行。

## 仅静态与未做

代码核对表明旧包不含新增内容时沿用现有加载流程。生产 Command Gateway 注册、可信命令输出清单来源、提交后异步触发、冷却、目标解析、可见性与 Workflow 的持久重建未做。M6-5 Demo 仍需域事实及命令生产路径，见守城前置核对证据。

| DoD | 状态 |
|---|---|
| U1–U3 | 此切片无域迁移、新 Owner、FactType 或持久事件类型 |
| U4 | 已验证复用规则包解析、命令目录与已有组合编译器 |
| U5 | 生产执行、幂等、义务及重建未做 |
| U6 | 实际包加载有专项测试，生产加载应用接线未做 |
| U7 | 生产可见性未做 |
| U8 | 已验证正常包加载、命令输出缺失、循环与未知组合引用的拒绝 |
| U9 | C3/C6 加载路径有测试，C8 注册和激活、Demo 未做 |
| U10 | 本文件记录范围、兼容性、输入版本与原始证据位置 |
| U11 | Reaction 的 14 节点登记选集含新增四个加载测试 |

## 回退

此加载接线在 Workflow 提交后独立增加。`git revert 6e7da420221c8a7ca4f3fb762153b2542e5b004c` 可移除本次加载接线，依赖判断来自提交 diff 静态检查。实际 revert 实验未执行。Reaction 的选集增加四个加载节点，回退时须同步回退该登记增量。后续生产调用接线尚未实施。

## 清理与保留

临时验证 worktree `F:/codex-temp/a-m6-2-8cb4ecca` 已回收，选集已核对复制回主 worktree。定向、选集、Workflow 全量和本次加载全量的运行临时子目录均已清理。本次 `F:/paralls-verification/thread-a/c-2a0a004b/t` 删除后核验不存在。原始日志、JUnit、JSON 与比较脚本保留在各自的 F 盘证据目录。
