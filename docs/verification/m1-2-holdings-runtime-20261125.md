# M1-2 Holdings 原语进度证据（2026-11-25）

## 基线与环境

- A worktree：`F:\codex-temp\paralls-v2-thread-a-bond-20261121`，分支 `thread-a/ownership-bond-followup-20261121`。
- 本次验证起始代码 HEAD：`88d1903f19f18a1869f3b0a0e4d905bd4f6507e1`。验证时工作区有未提交的 M1-2 代码与文档改动，因此结果对应该工作区状态，不对应单个提交。
- Python：`D:\Temp\paralls-g0-py312\Scripts\python.exe`，`3.12.2 (tags/v3.12.2:6abddd9, Feb  6 2024, 21:26:36) [MSC v.1937 64 bit (AMD64)]`。
- SQLite：`3.43.1`。
- `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`；`app.__file__=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`。
- 本次定向及重放验证的 `TEMP`、`TMP` 指向各自独立的 `F:\paralls-verification\thread-a\m1-2-holdings-*` 目录。解释器仍按既定环境使用 D 盘上的 Python 安装路径。

## 已验证

- `backend/tests/test_holdings_runtime.py` 与 `backend/tests/test_holdings_fact_type_registry.py`：最终当前代码集合 22 passed，2 warnings。日志：`F:\paralls-verification\thread-a\m1-2-holdings-final-20261125-02\pytest.log`。
- M1-2 新增固定选集 `docs/verification/selection/m1-2-holdings.json`，以登记时基线 HEAD `88d1903f19f18a1869f3b0a0e4d905bd4f6507e1`、22 项全通过结果登记。对改动后的当前工作区运行冻结比较器：`D:\Temp\paralls-g0-py312\Scripts\python.exe -B docs\verification\absorb-main-3bf3418e\compare_selection.py --repo F:\codex-temp\paralls-v2-thread-a-bond-20261121 --selection F:\codex-temp\paralls-v2-thread-a-bond-20261121\docs\verification\selection\m1-2-holdings.json --output F:\paralls-verification\thread-a\m1-2-holdings-postselection-20261125-01`。原始输出：`selected=22 problems=0 improvements=0`。
- 新增 checkpoint 回放行为先以缺少 `checkpoint_at` 参数的 `TypeError` 失败，随后通过。覆盖 checkpoint 后继续回放、保留 reservation、保留 split 关闭 lot 状态，以及拒绝负 checkpoint。新增 distribution 向量先因投影缺少 `distribution_by_item` 而失败，随后通过，验证同物料多 lot 汇总并隔离不同物料的 unit/spec。
- Python 导入路径与 SQLite/Python 版本分别通过独立命令核验，原始输出见上节。
- 当前登记选择集输出目录：`F:\paralls-verification\thread-a\m1-2-holdings-all-selections-20261125-01`。19 个非 shared-replay 选择集均以 exit code 0 完成，共 304 项通过。shared-replay 已完成前 10 批、400 项通过。第 11 批收集 40 项，其中日志记录前 5 项通过后停在 `test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage]`，没有最终结果文件或退出码。该选择集运行发生在本证据所述 checkpoint 代码改动之前，不能算作 checkpoint 改动后的选择集回归。
- 对上述卡点的单测复跑日志：`F:\paralls-verification\thread-a\m1-2-holdings-shared-replay-probe-20261125-03\pytest.log`。该 runner 需要本机 8000 端口上的 backend 并在端口未占用时调用 PowerShell listener 查询。本次单测复跑超过 70 秒仍停在同一用例，之后由本线程中断。其余并行 pytest 进程未触碰。该卡点不是 Holdings 测试失败，shared-replay 全集仍属未完成。

## 静态检查与未覆盖

- Holdings 当前生产 schema factory 已注册新增事件。FactType 编译器接受 `holdings` primitive，并拒绝 machine state-set 引用。实现含 lot 创建、预留及生命周期、同 stream 转移、消耗/损失、拆分/合并、容量校验，以及按 item 汇总 available/reserved/total quantity 并关联 unit/spec 的 `sum_by_item`。正式聚合规格将这种守恒总量定义为 `sum`，不称作不守恒的 `distribution` refold。
- 正式 v1 事件读取保持原事件类型与字段。`lot_created.quality` 仅验证为有限 Decimal，不并入数量。v1 重建、精确幂等重试、revision 冲突拒绝和拒绝零写入由定向测试覆盖。
- 定向证据没有验证规则包 Resolver 完整消费、跨 Owner 聚合、生产命令入口、持久化 Owner checkpoint 存储格式或 U1–U11 全部要求。
- shared-replay 990 节点全集没有完成。全量 backend suite 未运行。未验证生产部署或实际消费方。

## 状态

M1-2 继续进行中。checkpoint 按现有 Ownership 的 `checkpoint_at` 全局序号边界合同实现为前缀投影加后缀重放，不引入新的持久化快照格式。该选择和部分验证不足以满足 M1-2 的完整 DoD，也不代表 Architecture v2 完成或可合并。

## 2026-11-25 恢复验证补记

- 本次使用同一未提交工作区状态，未启动本地 backend。冻结 selections 仍通过 `docs/verification/absorb-main-3bf3418e/compare_selection.py` 串行分批执行。Windows PowerShell 在空闲端口 listener 查询中不返回，因此验证目录中的临时 `powershell.cmd` 只接受该条 `Get-NetTCPConnection -LocalPort 8000 -State Listen` 查询，并返回无 listener。运行前后均以 `netstat -ano -p tcp` 确认端口 8000 无监听；未改仓库测试或 Harness 代码。
- 重新验证 ownership 24、modifier 12、equipment 87、inventory 56、M1-2 Holdings 22 和 shared-replay 990 节点。各组输出分别为 `selected=24 problems=0 improvements=0`、`selected=12 problems=0 improvements=0`、`selected=87 problems=0 improvements=0`、`selected=56 problems=0 improvements=0`、`selected=22 problems=0 improvements=0`、`selected=990 problems=0 improvements=0`。原始日志与逐批结果位于 `F:\paralls-verification\thread-a\m1-2-holdings-resume-20261125-01\`。
- 卡点节点定向复跑 `backend/tests/test_embodied_interaction_session_runner.py`：`2 passed, 6 warnings in 21.63s`。此前两项失败批次来自本轮临时 backend 占用端口；停止该自有服务后，重跑完整选集无差异。它们不是 Holdings 断言失败。
- 本次覆盖冻结五组选集中的四个非 shared-replay 选择集和 shared-replay，以及 Holdings 自有选集。此前 19 个其它登记选择集的 304 项结果发生在 checkpoint 改动前，不纳入本次代码集合回归结论。全量 backend suite 未运行。
- 所有验证输出、临时数据库与 shim 均在 F 盘。SQLite 3.43.1、Python 3.12.2，`PYTHONPATH` 指向当前 A worktree backend；导入路径见基线环境节。临时 backend 已关闭。

## 单元 DoD 状态

| 项 | 状态 | 证据 / 缺口 |
|---|---|---|
| U1 Owner 声明与分类 | 仅静态 | 当前 FactType 使用 `Inventory` Owner ID；尚未在本单元核实其 native/stewarded 分类决定。 |
| U2 FactType 声明 | 部分 | `holdings` primitive 已登记并可编译；生产规则包中的 Holdings FactType 声明未接入。 |
| U3 事件 schema 与图可见性 | 已验证 | schema factory 注册 Holdings 事件；定向测试断言事件进入图可见注册表。 |
| U4 共享机制 | 已验证 | `OwnerCommitBuilder` 与 `replay_duplicate` 已用于 Owner 写入路径，定向覆盖提交与重试。 |
| U5 R1/R2/R3 | 部分 | revision 连续性、幂等重放、checkpoint 边界重建有专项测试；尚无持久化 Holdings checkpoint 格式。 |
| U6 读取方清单与专项测试 | 部分 | 静态读取方为 schema registry、Holdings projector 及其命令服务/测试；没有生产 Resolver 消费者。 |
| U7 面向主体读取分类 | 未做 | 事件目前为 `authority_only`；`read_as` 和主体可见性读取点未接通。 |
| U8 规则包与 Resolver | 未做 | 尚无生产 Holdings 规则包、Resolver 注册或真实消费调用点。 |
| U9 探针与基线对照 | 部分 | 定向 22 passed；本补记所列 1,191 个冻结/登记选集节点零差异；全量 backend suite 未运行。 |
| U10 文件与证据等级 | 已验证 | 本文件列出实现、测试与选择集状态；完整改动路径见下表。 |
| U11 单元选择集登记 | 已验证 | `docs/verification/selection/m1-2-holdings.json` 已登记 22 个节点。 |

本工作区的单元相关路径为 `backend/app/gameplay/event_schema_registry.py`、`backend/app/gameplay/fact_type_registry.py`、`backend/app/gameplay/holdings_event_schema.py`、`backend/app/gameplay/holdings_runtime.py`、`backend/tests/test_holdings_fact_type_registry.py`、`backend/tests/test_holdings_runtime.py`、`docs/verification/selection/m1-2-holdings.json`、本证据文件，以及 `docs/v2-coordination/board.md`、`docs/v2-coordination/handoff.md` 和 `docs/v2-coordination/daily/2026-11-25.md`。其中前三个既有文件为修改，Holdings 模块、测试、选择集和证据为新增，协作文档是状态记录。
