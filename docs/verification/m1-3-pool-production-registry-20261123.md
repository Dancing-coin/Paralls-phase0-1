# M1-3 Pool 生产 EventSchema 工厂接线

## 范围

提交 `39ecc2bb` 将已有 `register_pool_event_schemas` 接入 `create_stormnight_event_schema_registry`。此前 Pool 事件已在 FactType 图发现，但生产 EventSchema 工厂未登记 `gameplay.pool.*`，由该 factory 创建的受 schema 保护 Store 会拒绝 Pool 写入。本单元没有改 Pool 事件合同、原语逻辑或持久数据。

修改文件为 `backend/app/gameplay/event_schema_registry.py`、`backend/tests/test_gameplay_event_schema_registry.py` 与 `backend/tests/test_pool_runtime.py`。新增 factory 注册断言和使用生产 factory 的 Pool 初始化提交测试。Pool 选集已在 `docs/verification/selection/m1-3-pool.json` 增加该真实写入节点。

## 已验证

环境为 Windows、Python 3.12.2、SQLite 3.43.1。运行前设置 `PYTHONPATH=F:/codex-temp/paralls-v2-thread-a-bond-20261121/backend`，`app.__file__` 为该 worktree 下 `backend/app/__init__.py`。TEMP、TMP、TMPDIR 均位于 `F:/paralls-verification/thread-a/c-39ecc2bb/`。

提交代码后的定向命令覆盖 schema registry、Pool、LifeState、action consequence、action temporal、economy random command 与 Stormnight session/runtime 测试。结果为 `93 passed, 6 warnings in 8.90s`，退出 0。

冻结选集 `ownership`、`modifier`、`equipment`、`inventory` 分别为 24、12、87、56 个节点，合计 179，均 `problems=0 improvements=0`。更新后的 `m1-3-pool` 选集 16 个节点，`problems=0 improvements=0`。原始输出与节点 JSON 在 `F:/paralls-verification/thread-a/c-39ecc2bb/`。

`shared-replay` 的 990 节点比较有两个失败：

- `tests/test_embodied_interaction_session_runner.py::test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage]`
- `tests/test_embodied_interaction_session_runner.py::test_profile_repeated_in_one_run_receives_fresh_events[wall-clock]`

两者阶段均为 `call`，错误签名均为 `RuntimeError: Port 8000 is occupied by an external process without a healthy backend`。在临时 detached worktree `6e7da420` 用相同 Python、节点、端口和运行器复验，两个测试仍失败且错误签名相同。该外部进程未被触碰。shared-replay 选集整体非零退出，不能记为通过。

## 未验证与后续

本提交尚未运行全量测试、`harness.py --profile all`、Morale/Presence/Information 的生产命令或 Godot/UE Demo。Information B writer 仍位于独立 B 分支，未进入本 A worktree 的 integration 基线，故本提交没有导入其 schema 模块，也没有生产 Gateway/L5 接线。

依据 AUTONOMY 的共享机制回归要求，提交后的完整 pytest 已在 `39ecc2bb` 执行，10,564 collected，10,532 passed、28 failed、2 skipped、2 xfailed，239 warnings，用时 1,571.89 秒，退出 1。运行期间 HEAD 和源码固定。相对先前 `6e7da420` 全量报告按节点/阶段/错误类型比较，有 4 个新签名、0 个恢复。

其中两个新失败是上述端口 8000 节点。在同一外部端口占用状态下， detached `6e7da420` 和 `39ecc2bb` 的定向复验都重现相同 RuntimeError。

另两个新签名为 `tests/test_population_process_cognition_recovery.py::test_original_owner_provider_pending_survives_hard_kill_without_reingest[character]` 与 `[character_commit]`，都是 pytest 临时目录中文件读取 `PermissionError`。以 Python 3.12.2 在 detached `6e7da420` 与 `39ecc2bb` 分别定向重跑这两个节点，两边均为 2 passed、退出 0。这不改变全量原始结果，也未能证明间歇失败原因。

因此不能从本次全量得出 G5 零新增失败结论。现有结果把与本代码切片无关的外部端口占用和全量临时文件权限异常分开列出，仍保留 4 个新增失败签名。完整日志、逐节点结果、环境和比较输出位于 `F:/paralls-verification/thread-a/c-39ecc2bb/`。M6 Gateway/L5 生产调度另列为待合同与实现的机制任务。

## 结论等级

Pool schema factory 注册与真实 Pool 初始化提交为定向已验证。Pool 单元选集及四组冻结选集已验证。shared-replay 受外部端口占用而未通过。全量已运行但退出 1，出现上述 4 个新失败签名，其中两项在固定基线复现，另两项定向复验通过但全量期间再次原因未明。不能宣称 G5 通过。M1-3 的其他 U1–U11 缺口沿用既有 [Pool 证据](m1-3-pool-runtime-20261122.md)。
