# M6-5 Information 生产接线证据

## 交付范围

- A 提交 `9395181df1d94c2c6faf5363d73ac8858dcb5e17`，基于 A 父提交 `10bcb918a8a770e65ca694874b979566f45b71a1`。
- 已 fetch B 分支 `origin/thread-b/reference-data-20261123`，tip 为 `25674219ae951efcb5915c8293bf0c1a30196b85`。只按依赖使用 `abba3c3c2187b886db5ddb7727be9e8f2dc23162` 的 Information runtime/schema/tests、`6741ab61` 的文件语法修复、`63f41c8b47e7fa14c607c554d473dae2193c5d7c` 的 Reaction 包与更新；未合并 B 分支，也未修改 `integration`。
- Python `3.12.2`，SQLite `3.43.1`。提交验证 worktree 的 `app.__file__` 为 `F:\codex-temp\a-information-9395181d-verify\backend\app\__init__.py`。验证日志和临时目录全部在 `F:\paralls-verification\thread-a\`。

## 接线行为

- `create_stormnight_event_schema_registry()` 注册 SocialDelivery v1/v2 与 Information `knowledge_updated@1`。`FACT_TYPE_REGISTRY` 可发现 Information 输出事件。
- M6-5 生产 runtime 将 `county_siege_information` 的 Reaction、`information.update_knowledge` 命令、`InformationAuthority` 和可信输出 FactType 并入已有 L5 dispatcher/Gateway。Information 和 SocialDelivery 共享 M6-5 的 `GameplayEventStore`。
- 只有 `delivery_recorded@2` 的 source event 同时满足以下条件时才映射到 `fact:information:siege:report`：事件类型列在 `SIEGE_INFORMATION_REPORT_EVENT_TYPES_JSON`，source stream 与 revision 和 delivery 相符，source payload 的 `fact_type` 精确为守城报告 FactType。其它 SocialDelivery，包括政府通知，不触发这条 Reaction。
- handler 读取 `_session_world_clock_tick()`。时钟缺失或无效时抛出 `information_world_clock_unavailable`，现有 `GameplayOutboxDispatcher` 保留 projection refresh 待处理状态，由后续 `dispatch_pending()` 重试。
- `SIEGE_INFORMATION_REPORT_EVENT_TYPES_JSON` 默认空列表，生产环境目前未配置任何报告来源。此时不会产生 Information 知情事件。

## 验证结果

解释器及导入路径在每次 pytest 前核验。精确提交的定向命令为：

```powershell
$env:PYTHONPATH = 'F:\codex-temp\a-information-9395181d-verify\backend'
$env:TEMP = 'F:\paralls-verification\thread-a\information-commit-9395181d-verify-20261124-01\tmp'
$env:TMP = $env:TEMP
$env:TMPDIR = $env:TEMP
& 'D:\Temp\paralls-g0-py312\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider --basetemp 'F:\paralls-verification\thread-a\information-commit-9395181d-verify-20261124-01\pytest' backend/tests/test_information_production_wiring.py backend/tests/test_siege_information_runtime.py backend/tests/test_gameplay_event_schema_registry.py backend/tests/test_p5_social_delivery.py backend/tests/test_social_delivery_caller.py backend/tests/test_l5_dispatch_runtime.py backend/tests/test_l5_reaction.py backend/tests/test_rule_pack_validator.py backend/tests/test_m6_5_siege_runtime.py backend/tests/test_morale_refold_runtime.py backend/tests/test_place_passability_runtime.py
```

原始输出 `F:\paralls-verification\thread-a\information-commit-9395181d-verify-20261124-01\pytest.log`：`208 passed, 6 warnings in 15.16s`。

冻结基线使用 `docs/verification/absorb-main-3bf3418e/compare_selection.py`，精确提交结果如下：

| 选择集 | selected | problems | improvements |
|---|---:|---:|---:|
| ownership | 24 | 0 | 0 |
| modifier | 12 | 0 | 0 |
| equipment | 87 | 0 | 0 |
| inventory | 56 | 0 | 0 |
| shared-replay | 990 | 2 | 0 |
| siege_information | 14 | 0 | 0 |
| m6-5-production-wiring | 6 | 0 | 0 |

原始对照日志位于 `F:\paralls-verification\thread-a\information-commit-9395181d-selections-20261124-01\`。shared-replay 的两项为 `test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage]` 和 `[wall-clock]`，均报 `Port 8000 is occupied by an external process without a healthy backend`。在父提交 `10bcb918a8a770e65ca694874b979566f45b71a1` 上单独重跑同两节点，结果同为 `2 failed`，原始输出在 `F:\paralls-verification\thread-a\information-parent-port-8000-20261124-01\run.log`。未停止或修改占用该端口的进程。

最初从 B 侧组合选择集复制的三个 ReferenceData 节点不属于本次 A 选择范围，在 A worktree 中无法收集。已从 `siege_information.json` 移除这三个节点，并在 A 提交上以 14 节点选择集重跑，结果零差异。生产回归另有 11 个相关测试文件，原始结果包含在上述 208 项测试日志中。

提交后的选择集元数据复核：在 A worktree 的 `9395181df1d94c2c6faf5363d73ac8858dcb5e17` 上使用 Python 3.12.2 重跑更新后的 `siege_information.json`，命令为 `python -B docs/verification/absorb-main-3bf3418e/compare_selection.py --repo <A worktree> --selection docs/verification/selection/siege_information.json --output F:/paralls-verification/thread-a/information-selection-final-9395181d-20261124-01`。运行前 `PYTHONPATH=<A worktree>/backend`，`app.__file__` 为 `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`，TEMP/TMP/TMPDIR 均指向 F 盘本次独立目录。原始输出 `F:\paralls-verification\thread-a\information-selection-final-9395181d-20261124-01.log`：`selected=14 problems=0 improvements=0`。该复核只更新验证选择集元数据，没有修改代码。

P-1：跟踪文件扫描输出 `tracked_model_secret_offender_count=0`，本次暂存新增行凭证模式匹配数为 0。相对 `origin/integration` 的分支新增行扫描有一条宽泛凭证赋值模式命中 `backend/app/gameplay/siege_physical_input_runtime.py:201`，匹配子串 SHA-256 前 8 位为 `18983dda`，在 `origin/main` 和协议起点 `3934bba6` 中均已存在（是），未形成新增暴露。全量 10,392 项未运行。Godot、真实守城报告来源和完整 siege playthrough 未验证。

## 尚缺的生产输入

Formal `02-守城Demo定义.md` 给出 `fact:information:*:report` / `report_delivered` 的 Reaction 示例，`01-内核/05-传播延迟与失真.md` 将报告事实提交归给 Information Owner，但没有给生产 source event type、source writer 或 stream/revision 合同。代码仓库和规则包也没有已提交的守城报告 producer。

当前实现只证明配置已登记的 source event 可以被精确识别和投递，不证明实际守城报告会进入该路径。需要 Information/守城内容事实生产者提供已注册的 event type、实际 source stream/Owner 与 `fact:information:siege:report` payload 约定，并由项目负责人确认生产 `SIEGE_INFORMATION_REPORT_EVENT_TYPES_JSON` 值。收到该输入前保持空配置和零写入。

## 生产来源复核

在推送后的 A 分支再次检索 `backend/app`、`backend/tests` 与 `packs`：`gameplay.social.knowledge_observed` 仅出现在 `backend/tests/test_information_production_wiring.py:15`。该测试在 `_store_with_delivery()` 内直接用 `build_atomic_event_batch()` 构造来源事件，没有调用生产 writer；生产 EventSchema factory 中也没有注册该类型。`fact:information:siege:report` 的代码命中是 M6-5 常量、Reaction 声明和测试，不包含报告生产者。正式 `02-守城Demo定义.md` 只给出 `report_delivered` Reaction 示例，正式 `01-内核/05-传播延迟与失真.md` 明确报告事实由 Information Owner 提交，但没有给 event type 或 payload 字段合同。

因此，Information 14 节点选择集验证了显式 allowlist、source stream/revision 与 FactType 匹配机制，不能作为真实报告来源或生产端到端证据。没有擅自把测试事件提升为生产合同，`SIEGE_INFORMATION_REPORT_EVENT_TYPES_JSON` 继续默认为空。
