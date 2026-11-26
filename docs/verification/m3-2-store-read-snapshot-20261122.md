# M3-2 StoreReadSnapshot

代码提交 `7c24d136080f5a030b87f30ffe145f92d8feb893`，测量基点 `cd1d1e5b3afbf797d5a6610bdfdfba7b838d8db8`。代码可用 `git revert 7c24d136` 整体回退。

| 读取路径 | 基点实测 `read_events()` | 改动后 | 验证方式 |
|---|---:|---:|---|
| Credential supersede | 2 | 1 | 真实命令提交，统计该次调用的全量读取 |
| LandRight transfer（v1 `right_id`） | 2 | 1 | Adventure Basic Scenario 4 提交，统计该次调用的全量读取 |
| LandRight transfer（v3 `bond_ref`） | 3（静态） | 2（静态） | presentation 复用 transfer 的事件元组。Ownership fragment builder 保留自己的事件读取和版本校验。Bond transfer 已跑功能测试，读取次数未实测 |
| Ownership 独立命令 | 1（静态） | 1（静态） | 每个调用点已读取一次，未接入 |

Credential supersede 校验凭证和替换物品时共用一个快照。提交的版本取自该快照，避免用较新的库存 head 提交基于旧库存的决定。新增测试在快照读取后提交一笔库存更新，验证 supersede 返回 `revision_conflict` 且不写凭证。LandRight transfer 将同一份事件传给内部 presentation 检查，公开 presentation 入口继续直接读取自己的 store。

快照从元组最后一条事件取得 `global_sequence`，同 head 复用，head 变化后重读。事件及 payload 仍为现有模型类型，只给经过检查的只读投影器供数。基点与新版的命令读取次数是小型内存夹具结果。另用现有 G2 fixture 做交替采样，每种读取各 100 次，计时止于函数返回。400 条事件时全量读取与同 head 命中的中位耗时为 925.600 µs / 0.750 µs，4,096 条时为 11,052.550 µs / 1.650 µs。该测量只覆盖内存 store 的取数开销。

## 验证环境与定向结果

- Worktree `F:\codex-temp\paralls-v2-thread-a-bond-20261121`。Python 3.12.2 来自 `D:\Temp\paralls-g0-py312\Scripts\python.exe`，SQLite 3.43.1。`PYTHONPATH` 指向 worktree 的 `backend`，`app.__file__` 核验为 `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`。
- 已验证，`python -m pytest -q -p no:cacheprovider` 定向运行 `test_owner_runtime_base.py`、`test_credential_runtime.py`、`test_adventure_basic_scenario4.py`、`test_credential_v2_land_right_revision_vector.py`、`test_credential_declared_presentation.py`、`test_credential_reference_chain.py`，结果 `33 passed, 2 warnings in 1.28s`。原始控制台与 JUnit 位于 `F:\paralls-verification\thread-a\m3-2-targeted-20261123-003`。
- 原始读开销输出位于 `F:\paralls-verification\thread-a\m3-2-7c24d136\read-microbenchmark-isolated.txt`。
- 已验证，SQLite 两连接探针从 head 0 的空快照开始，第二个连接正常提交产权事件后，第一个连接读到 head 1，同 head 重读复用同一元组。原始输出位于同目录的 `durable-snapshot-check.txt`。

## 冻结选集

在代码提交 `7c24d136` 上串行运行 `compare_selection.py --repo <worktree> --selection <选集 JSON> --output <新目录>`。控制台和各批的原始结果位于 `F:\paralls-verification\thread-a\m3-2-7c24d136`。

| 选集 | selected | problems | improvements |
|---|---:|---:|---:|
| ownership | 24 | 0 | 0 |
| modifier | 12 | 0 | 0 |
| equipment | 87 | 0 | 0 |
| inventory | 56 | 0 | 0 |
| shared-replay | 990 | 0 | 0 |

## Current-tip revalidation, 2026-11-27

At A tip `259314e2`, the focused M3-2 command returned **34 passed, 2 warnings** under Python 3.12.2 with `PYTHONPATH` pointing to the A worktree backend and explicit F-drive pytest basetemp.

| Selection | Current-tip result | Raw output |
|---|---|---|
| M3-2 registered selection, 7 nodes | `selected=7 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m3-2-current-tip-20261127-01\m3-2\` |
| ownership, 24 nodes | `selected=24 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m3-2-current-tip-20261127-01\ownership\` |
| modifier, 12 nodes | `selected=12 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m3-2-current-tip-20261127-01\modifier\` |
| equipment, 87 nodes | `selected=87 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m3-2-current-tip-20261127-01\equipment\` |
| inventory, 56 nodes | `selected=56 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m3-2-current-tip-20261127-01\inventory\` |
| shared-replay, 990 nodes | `selected=990 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m3-2-current-tip-20261127-01\shared-replay\` |

The current-tip full backend suite was not rerun for this M3-2 check. The latest recorded full suite remains a non-green merge-state result and is not attributed to this mechanism slice. M3-2 remains `待门禁`.
| M1-3 Pool | 15 | 0 | 0 |
| M3-2 StoreReadSnapshot | 7 | 0 | 0 |

## 后端全量

使用 `docs/verification/g0-939c6746/run_baseline.py --freeze --repo <worktree> --output <run>/full` 串行测试 `7c24d136`。runner 确认代码 SHA 和源码在运行期间一致。采集 10,465 节点，原始结果为 `24 failed, 10437 passed, 2 skipped, 2 xfailed, 239 warnings in 1240.13s`，退出码 1，收集错误 0。

按节点、阶段、错误类型比较，与 M1-3 全量 `022f1772` 的 24 个失败完全一致，新增 0、消失 0。与正式 22 个失败的冻结基线对照还有两个已在 M1-3 全量出现的失败，分别为 `test_population_cold_ready_gate.py::test_cold_ready`（call / KeyError）以及 `test_population_recovery_measurement.py::test_recovery_owner_probe_measures_original_startup_before_full_oracle`（call / AssertionError）。保留冻结基线。

首次从仓库根直接收集额外脚本测试，因缺少 `jsonschema` 退出 2。第二次附加 F 盘临时依赖后手动停止。正式后端运行使用原 Python 环境，控制台 `full-console.txt`、对照 `full-comparison.json`、冻结清单、JUnit 与原始失败均在 `F:\paralls-verification\thread-a\m3-2-7c24d136`。

## 覆盖范围

本单元改动生产文件 `owner_runtime_base.py`、`credential_runtime.py`、`land_right_runtime.py`，新增或修改定向测试 `test_owner_runtime_base.py`、`test_credential_runtime.py`、`test_adventure_basic_scenario4.py`。没有规则包或事件 schema 变更。

U4 已验证于上表两条命令路径。U5 的现有重放与版本冲突有定向证据，域级 R1–R3 验收未做。U6 的接入调用图已查并有定向测试，其他域的接入未做。U10 见本文件，U11 登记在 `docs/verification/selection/m3-2-store-read-snapshot.json`。U1、U2、U3、U7、U8 属域迁移交付，本机制单元未做。U9 的声明探针未做，回归结果单列。持久 SQLite store 的快照性能、不同事件规模的端到端命令延迟以及其他 Owner 的推广未覆盖。
