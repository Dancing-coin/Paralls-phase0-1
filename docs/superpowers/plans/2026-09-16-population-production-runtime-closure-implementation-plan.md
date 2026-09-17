# 群体模拟剩余六项完整闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 局部任务通过只允许更新内部台账，不允许将整个目标标为完成。

**Goal:** 完整补齐服务响应隔离、长局持久化恢复、Godot 真实表现、混合长时负载、协议与序列化优化、CI 回归门禁六项，并取得同一实现版本的全部必过验收证据；任一项未过则总体未完成。

**Architecture:** 保持现有 Backend Authority／Domain Owner／Character Core／Godot 职责边界与混合数据导向布局。使用每局单一 runtime 执行域、SQLite 索引查询与有界恢复、现有 session/mirror 传递公开表现。先消除实际阻塞和历史扫描，再按实测减少对象物化，不提前引入新引擎、分布式框架或 GPU。

**Tech Stack:** Python 3.11+（固定性能基线先使用 3.12.14）、FastAPI、asyncio、stdlib queue/threading/concurrent.futures/sqlite3、Pydantic、pytest、现有 Harness、Godot 4.6 项目与 CI 中固定的 4.6.3 引擎。

**Spec:** [六项闭环设计](../specs/2026-09-16-population-production-runtime-closure-design.md)；继承 [前序五阶段计划](2026-09-15-population-data-oriented-optimization-implementation-plan.md)、[mainline 设计入口](../specs/world-character-siming-authority-mainline/README.md)、[恢复和 B0 边界 ADR](../../adr/0001-population-continuity-recovery-and-b0-boundary.md)。

**Status:** `execution_in_progress; godot_unverified; godot_runtime_on_external_machine`。用户于2026-09-16指定 Godot 在另一台机器验证。本机只做后端、协议与静态检查；真实渲染门禁等待该机器导出的证据。本文件完整覆盖六项；勾选只依据执行证据，最终 G0—G9 门禁未全过前，总目标始终未完成。执行工作树为 `.worktrees/population-runtime-closure`；持久进度见该工作树 `.harness/verification/population-runtime-closure/progress.json`。

## Global Constraints

- 当前分析基线为 `fb85b81516f383c2ad768a990cf06c21e2d642ec`。执行开始先核对 HEAD 和工作区，不覆盖其他任务修改。
- 世界事实仍只经现有 append/Owner 链提交；B0 不绕过激活去写角色记忆或 Owner 事实。Godot LOD 不反向改变模拟精度与世界真相。
- 保留 scope、权限、source/actor revision、read-set digest、幂等键、receipt 和 replay hash；不同 tick、stream revision、global sequence 不互换。
- append 成功是事实锚点。publish、delivery 标记、热表确认、checkpoint 是不同故障边界；禁止将失败后的部分内存状态当作已完成窗口。
- 所有外部输入保留 Pydantic 校验；内部复用已验证数据不得降低可变对象隔离。pickle 只用于进程内可信对象，不能接收客户端 pickle。
- 不删除权威历史、旧幂等结果或 pending outbox 换取性能；只淘汰可重建缓存。
- 不额外创建 Godot project，不让万人后台人口自动变成万个全功能 Godot 节点；复用现有 main scene、autoload、session 与 mirror。
- 使用既有 Python/SQLite/WebSocket 工具，不增加任务调度平台、通用 repository 抽象或新的事件总线。
- 1× 三档 p95 ≤ 800 ms、30 窗不持续积压、最大推进延迟 ≤ 1 窗为必过；10× 运行完整且如实报告，性能结果独立。
- 无真实 Godot runtime 与可见变化证据时仍为 `godot_unverified`；editor import 和 headless 协议检查不足以证明渲染帧时间。
- `docs/superpowers/` 本地保留，不提交；工作树回主分支用 cherry-pick。按完整交付边界合并提交，中文 commit，不能用大范围 add 带入无关文件。
- 执行范围不包含动态换 roster、在线热升级旧规则、跨机器共享同局多 writer。遇到 roster/kernel/context 漂移继续 fail closed。

## 0. 当前事实、范围与执行顺序

### 已有证据只作基线

基线交接入口为 [population-data-oriented-closure.md](../../verification/population-data-oriented-closure.md)。现有 5,327 个后端测试和三档 1× 报告属于前序版本；万人 1× p95 为 758.45 ms，10× 万人失败，30 窗恢复约 8.76 秒。约 7.59 MiB/window 是内部 JSON 计数，尚非实际网络流量。保留历史 I/O 尾延迟失败报告，不把后续一次通过解释成 I/O 根因已完全消除。

### 六项对应的真实缺口

| 项 | 当前入口与缺口 | 必须交付 |
|---|---|---|
| 1 | `PopulationCadenceDriver.run_forever()` 直接同步 `tick()`；WS、HTTP、现有 `to_thread` 共享 runtime | 单 writer、provider 分阶段、loop 安全投递、真实并发响应证明 |
| 2 | Durable `_load_database()` 全量装载；publisher 全历史 replay；dispatcher 全扫描；receipt/driver 集合增长 | SQLite 索引事实访问、checkpoint+tail、有限缓存、迁移和故障恢复证明 |
| 3 | `verify_population_presentation_lod.py` 当前只输出未验证；没有人口专用场景闭环 | 授权公开表现 snapshot/delta、Godot 消费、真实渲染采样与 LOD 等价性 |
| 4 | 现有规模脚本 provider disabled、稀疏 Owner、单局、虚拟 backlog | 真墙钟混合到达率、due 波峰、真实模型样本、故障与长测、多局容量 |
| 5 | 大量 projection/Pydantic/JSON/pickle 转换；公开视图与内部事件成本未分开 | 分段画像、共享编码结果、授权可见增量、真实字节与前后对照 |
| 6 | 人口 profiles 未进入 `all`；CI 未安装 backend 依赖、Godot 路径假定已存在 | 显式 correctness CI、可重建环境、固定机器性能/Godot证据、总门禁 |

执行顺序：**T0 前置 → 第1项 → 第2项 → 第3项基础闭环 → 第5项 → 第4项最终负载 → 第6项和总验收**。保留六项原编号；第5项先于第4项最终长测，避免为优化前版本重复跑小时级验收。CI 环境准备在 T0 提前做，最终接线在第6项。

并行只用于只读审计或无冲突文件的实现；`main.py`、event store、runtime loop 的集成由一个负责人顺序完成。所有性能场景顺序执行，不能与其他基准竞争 CPU/磁盘。

### 文件地图

| 范围 | 修改的现有文件 | 新增的最少文件 |
|---|---|---|
| 执行隔离 | `backend/app/main.py`、`world_runtime/population_driver.py`、`debug_stream.py`、`character_agent/runtime/runtime_loop.py`、`character_agent/gateway/model_gateway.py`、`services/siming_runtime.py`、`services/siming_event_pipeline.py` | `backend/app/services/runtime_execution.py`；对应执行域、transport、completion 回归测试 |
| 恢复 | `backend/app/gameplay/event_store.py`、`gameplay/dispatcher.py`、`population_continuity/runtime_publication.py`、`population_continuity/world.py`、`population_continuity/hot_state.py` | `backend/app/population_continuity/recovery.py`；lazy restore 和 long-session 测试 |
| 表现 | 现有 gameplay mirror projection/delivery/session access、`BackendBridge.gd`、`LocalPresentationBus.gd`、`MainDemo.tscn` | 一个 population presentation adapter、一个 GDScript population presenter 与一个 runtime probe scene/script |
| 性能与故障 | `scripts/verification/population_benchmark_metrics.py`、现有 population scale/presentation/native gate 脚本 | service-isolation、long-session-recovery、mixed-soak、aggregate-closure 四个验证脚本 |
| 验收接线 | `.github/workflows/harness.yml`、`docs/harness.md`、`docs/INDEX.md`、版本化验证交接文档 | 对应新 profiles；环境安装脚本及固定机器验收 workflow |

上述 `backend/app/` 后的缩写路径均相对该目录；各任务下面列出完整路径。新类型/方法是本计划要实现的接口，不是当前仓库已有 API。

### T0：前置条件与证据目录

**Consumes:** 当前 HEAD、[设计的验收默认值](../specs/2026-09-16-population-production-runtime-closure-design.md)、现有 Harness。
**Produces:** `.harness/verification/population-runtime-closure/preflight.json`、`progress.json`，以及实际可用的 Python/Godot/provider/性能机器清单。

- [ ] 核对 `git status --short`、`git rev-parse HEAD`，从干净基线建立 `codex/` 隔离工作树；保留原 `.worktrees/pop-fix/.harness/t/`，不再次尝试清理先前被策略拒绝的目录。
- [ ] 在隔离环境安装 `python -m pip install -e './backend[dev]'`，记录 Python、SQLite、依赖版本和 CPU/RAM/OS。配置值只记录存在性及脱敏 provider/model 名称，不打印 key。
- [ ] 检查 `GODOT_EXE` 与引擎 `--version`；缺失则从 Godot 官方发行获取固定 4.6.3，校验发布摘要、解压到工具目录，不提交二进制。执行真实场景之前先做 `--headless --path . --editor --quit` 导入。
- [ ] 本机不再安排 Godot 渲染性能运行。检查真实 Character/Siming provider 配置、CI 身份与固定性能 runner，记录另一台 Godot 机器的验收交接需求。把缺失项立即记为 blocker；完成不依赖它的工作，但不伪造 Godot/provider/CI 通过。
- [ ] 记录所有验收新增默认阈值。执行器不得为了绿灯自动增加 800 ms、缩短长测、关闭 provider 或改用小名单。
- [ ] 初始化进度文件，六项全为 `not_started`；每项记录 `tasks_done`、`tests`、`run_ids`、`blockers`、`next_command`。总状态仅允许 `not_started/running/blocked/passed`，没有“部分完成即通过”。

```json
{"schema_version":1,"base_commit":"fb85b81516f383c2ad768a990cf06c21e2d642ec","overall_status":"not_started","godot_status":"godot_unverified","items":{"1":"not_started","2":"not_started","3":"not_started","4":"not_started","5":"not_started","6":"not_started"}}
```

检查：执行 `python -m pytest backend/tests/test_population_runtime_lifecycle.py -q` 建立启动基线；这不代替后续完整验收。

## 1. 服务响应与单局执行隔离

### T1.1：统一 runtime 写入执行域

**Files:** 新建 `backend/app/services/runtime_execution.py`、`backend/tests/test_runtime_execution.py`；修改 `backend/app/main.py`、`backend/app/world_runtime/population_driver.py`。

**Interfaces:**
- `RuntimeExecution(max_pending: int = 128)`：每实例一个专用线程，只允许一局一个实例。
- `submit(fn: Callable[[], T]) -> concurrent.futures.Future[T]`：线程内递归提交立即执行，线程外入有界队列；满时抛 `RuntimeQueueFull`，停止后抛 `RuntimeStopped`。
- `stop(*, timeout_seconds: float = 10.0) -> bool`：停止接收新任务、排空已经接纳的任务；超时返回 false 并保持实例引用及 unhealthy，禁止启动第二 writer。
- `snapshot() -> dict[str, object]`：状态、queue_depth、queue_wait_ms、service_ms、failure；指标不得含角色私有输入。
- async 调用固定写法为 `await asyncio.wrap_future(execution.submit(command))`，不得在 ASGI loop 调 `.result()`。

- [ ] 写失败测试：FIFO、同一 owner thread、递归 Bus callback 无死锁、队列满拒收、异常进入 Future、stop 后拒收、重复 start 不增加 writer。

```python
from threading import get_ident
from app.services.runtime_execution import RuntimeExecution

def test_one_owner_and_reentrant_submit():
    execution = RuntimeExecution(max_pending=2)
    try:
        owner = execution.submit(get_ident).result(timeout=1)
        assert owner != get_ident()
        nested = execution.submit(lambda: execution.submit(get_ident).result()).result(timeout=1)
        assert nested == owner
    finally:
        assert execution.stop(timeout_seconds=2)
```

- [ ] RED：`python -m pytest backend/tests/test_runtime_execution.py -q`，当前应因模块缺失失败。随后用 `queue.Queue(maxsize=128)`、一个 `threading.Thread`、`Future.set_running_or_notify_cancel()` 实现；异常必须 `set_exception`，每次 `get` 对应 `task_done`。
- [ ] 启动/关闭在同一个实例生命周期内完成 runtime 装配、reset、数据库 close。审核 `main.py` 的 `health`、debug read model、structured interaction、WS envelope、dialogue、raw-fact followup、trusted probe、revoke/reset 入口；共享状态读取也在执行域内返回复制快照。
- [ ] 将 driver 改成一次调度一个完整窗口，在窗间检查 stop/pause 与队列，保留 catch-up_limit 和原窗口顺序。一次失败不得推进确认游标；下次从 publisher.confirmed_tick 继续。暂停只在窗边界生效，resume 默认从确认 tick 继续，不把暂停墙钟当作必须追赶的模拟时间。
- [ ] 保留窗口不可分割的提交过程；如果其服务时间影响命令延迟，先通过数据搬运优化降低窗口时长，不让两个窗口并行修改 authority。
- [ ] GREEN：执行域测试加 `test_population_runtime_driver.py`、`test_population_runtime_lifecycle.py`、`test_population_durable_cadence_recovery.py`；验证异常路径会使 health 显示 unhealthy，而不是固定 `ok`。

### T1.2：provider 等待与版本提交分开

**Files:** 修改 `backend/app/character_agent/runtime/runtime_loop.py`、`backend/app/character_agent/gateway/model_gateway.py`、`backend/app/main.py`、`backend/app/services/siming_runtime.py`；新建 `backend/tests/test_cognition_completion_revision.py`。

**Consumes:** T1.1 的执行域；现有 `CharacterModelGateway.prepare_run_request(...)`、provider、validator、activation authority。
**Produces:** 在现有 runtime 中增加 `prepare_cognition_job(...) -> PreparedCognitionJob` 与 `commit_cognition_result(job: PreparedCognitionJob, output: dict[str, object]) -> dict[str, object]`；不新增第二个 Character runtime。

`PreparedCognitionJob` 是冻结记录，包含 `job_id/task_kind/actor_id/request_json/actor_revision/source_revision_vector/read_set_digest/idempotency_key/activation_lock_ref/activation_token/deadline_monotonic`。`request_json` 为不可变 UTF-8 bytes；worker 不持 runtime、store 或 actor 对象。Siming 使用同样的冻结输入与 completion 检查模式，提交仍回到原 `SimingRuntime.tick`/dispatch 入口。

- [ ] RED 用阻塞 provider 测试：模型尚未返回时另一个 B0 窗口和 health 仍可执行；完成前 actor revision 前进、锁 token 失效、超时取消分别返回 `requeued/zero_write`，不能写 session/Owner/behavior。
- [ ] prepare 在执行域内做上下文、memory recall、scope/readset 校验和 activation 锁获取，调用现有 `prepare_run_request`；worker 只做 provider I/O 与纯输出校验。流式 delta 可送客户端，最终事实与 session 写入必须等 completion admission。
- [ ] 将当前包住整个网络回调的 `activate_actor(... cognition_callback=...)` 拆成显式开始/结束激活；同角色忙时 requeue，不重入私有状态。完成、异常、超时与 shutdown 都提交一次受 token 保护的 release，不能释放后续任务的新锁。
- [ ] commit 先核对全部 pin 和幂等键，再使用原有内存、session、行为审计和 Owner 入口。重复同 key/同 payload 返回原结果；同 key/异 payload 拒绝；过期结果 zero-write 后按现有预算 requeue。

```python
# 下述顺序是必须保留的执行边界；prepared 字段在本任务上文定义。
prepared = await asyncio.wrap_future(execution.submit(prepare))
output = await asyncio.to_thread(provider.complete, json.loads(prepared.request_json))
receipt = await asyncio.wrap_future(
    execution.submit(lambda: runtime.commit_cognition_result(prepared, output))
)
```

- [ ] 使用有界并发（验收值 4），忙时保留 due/deferred 记录；不得 `asyncio.create_task` 无界积累请求。断开 WS 可以拒收未完成文本，不撤销已经提交事实。
- [ ] GREEN：新增 completion 测试、原 dialogue streaming/activation/Character continuity/Siming provider 测试全过；测试须核对具体新增事件和 session 次数，不只检查返回状态。

#### T1.2 执行拆分与完成语义（源码审计补充）

T1.2 依次实现以下五个可审查单元，全部通过才算本任务通过；不能只改对话入口。

| 单元 | 准确修改面与复用点 | 必测边界 |
|---|---|---|
| T1.2a | `gateway/model_gateway.py` 的 prepared provider I/O；`reasoning/l2_reasoner.py` 复用 prepare_reasoning_request/map_reasoning_output；`planning/l3_planner.py` 提取 prepare intent / finish plan / decision_from_plan / suggestion_from_plan | frozen request 深隔离；L3 behavior policy consume仍在owner；同步入口复用相同阶段代码，不复制整段业务 |
| T1.2b | `runtime/runtime_loop.py` 感知、自体、Siming输入、background四入口分阶段continuation | L2→L3→辅助模式第三次L3都覆盖；L2提交后建立新L3 pin，不被自身更新拒绝；不重放感知记录与need_delta |
| T1.2c | `activate_actor`提取begin/finish，`main.py`与`services/dialogue_service.py`冻结上下文与stream完成提交 | token跨网络等待持有；取消/revoke/timeout/reset release一次；晚到completed不得写正式session；同步callback仍保留兼容 |
| T1.2d | `services/siming_runtime.py` candidate 路径与 `services/siming_heavenly_runtime_support.py`adaptive bridge路径；`siming_event_pipeline.py`提取finish_result | 每turn显式保存event/prepared上下文，不能共用_active_turn_*导致串台；bridge validate/commit回owner |
| T1.2e | 复用现有dispatch/recovery ledger记录async admission/completion，接回Bus/outbox | 内存ticket排队不等于delivered；只有可恢复admission写盘后才确认入站，崩溃重启恢复provider待处理项且不重复Owner事实 |

- 每阶段 pin 包含 runtime generation、turn/stage token、相关 actor 的 cognition epoch/上下文摘要、memory与continuity revision、控制/监督范围、相关 read-set；禁止只用只覆盖continuity命令的旧revision，禁止把无关全局人口revision作为所有job的失效条件。
- L2前的合法感知记录不回滚；stale只终止本次continuation并保留一次requeue原因，不重新ingest同一事件。provider错误的continuity floor仍回owner按旧语义运行；stale/cancelled不是fallback理由。
- 最多4个provider槽；completion遇到runtime queue full采用有界重试/明确取消并释放锁，不丢完成结果让pending永久占位。
- 强杀验证必须覆盖provider等待阶段。若现有ledger不能表达必要的可恢复待处理状态，扩展当前持久化记录，不能悄悄引入第二事实库或把内存create_task当成功交付。

### T1.3：transport 线程边界与真实响应门禁

**Files:** 修改 `backend/app/debug_stream.py`、`backend/app/main.py`、`backend/app/gameplay/godot_mirror_delivery.py`；新建 `backend/tests/test_runtime_execution_transport.py`、`scripts/verification/verify_population_service_isolation.py`、`.harness/profiles/population-service-isolation.json`。

**Consumes:** T1.1/T1.2；现有 `/ws`、`/debug/ws`、health 与 mirror 连接注册。
**Produces:** `verify_population_service_isolation.py --population 10000 --seconds 120`；报告 `.harness/verification/population-service-isolation-report.json`，包括真墙钟 latency 与单 writer 证明。

- [ ] RED：在 `PYTHONASYNCIODEBUG=1` 下从 owner 触发 debug、mirror、controlled close，并同时断连/退订；断言所有 queue、WS send/close、connection map 修改发生于原 loop。
- [ ] loop 负责订阅和连接；owner 传递独立快照，使用 `loop.call_soon_threadsafe(deliver, payload)` 投递。订阅加历史快照需要执行域屏障和一个明确切点，避免 snapshot→subscribe 之间漏消息。
- [ ] 慢消费者达到现有上限后按已有 gap/resync/controlled-close 处理；一个慢客户端不得阻塞其他订阅或 authority 提交。
- [ ] 启动真实 Uvicorn 子进程，三档分别运行 120 秒；每 10 ms 测 loop heartbeat，每秒 20 次 health、5 个 WS 入队请求、2 个结构化事实命令，模型请求采用有界慢 provider 作故障测试。accepted 只证实接纳，不冒充业务成功。
- [ ] 通过条件：health/accepted p95≤100ms、loop p99≤50ms、非模型事实命令完成 p95≤1,500ms，队列≤128、无跨线程错误、同局最多一个 writer、后台窗口达到原 1× 门槛。
- [ ] 若线程方案在固定机器同种子两次仍因 GIL/GC 违反 loop 门槛，执行**限定升级分支**：在 `runtime_execution.py` 用一个 `multiprocessing` spawn 子进程拥有整局装配；IPC 命令只含版本化命令名/关联 ID/JSON 参数，结果与 notification 分开、有界。迁移 prepare/commit 操作表，禁止发送 callable 或 runtime 对象；ASGI 仍只拥有连接。增加子进程退出、IPC 断开、重复请求及重启 outbox 测试，再重新跑本门禁。不能同时保留两个可选生产执行模式。
- [ ] 项1出口：以上三任务和本 profile 全绿，记录所选线程/进程模式与理由；仍不代表六项总完成。

## 2. 长局持久化、恢复和缓存边界

### T2.1：Durable event store 使用索引查询，不在启动全量构建内存账本

**Files:** 修改 `backend/app/gameplay/event_store.py`、`backend/app/gameplay/dispatcher.py`；新建 `backend/tests/test_gameplay_event_store_lazy_restore.py`，扩展 `backend/tests/test_population_persistence_regression.py`。

**Consumes:** 现有 `AtomicEventBatch/AppendBatchResult/GameplayEvent/GameplayOutboxEntry/ProjectionCheckpoint`。
**Produces:** 内存实现与 Durable 实现对齐的下列 API；已有调用不传新参数时保留原行为：

```python
read_stream(stream_id: str, *, from_revision: int = 1,
            to_revision: int | None = None, limit: int | None = None) -> list[GameplayEvent]
get_transaction(transaction_id: str) -> AtomicEventBatch | None
list_outbox(*, include_delivered: bool = True, topic: str | None = None,
            transaction_id: str | None = None, after_cursor: tuple[int, str] | None = None,
            limit: int | None = None) -> list[GameplayOutboxEntry]
list_projection_checkpoints(*, projector_id: str | None = None,
                            limit: int | None = None) -> list[ProjectionCheckpoint]
```

- [ ] RED：用现有 batch 工厂生成 1,000／10,000 条历史，关闭并 reopen；在 SQLite execute/fetch 和模型构造处计数，固定查询不得读取全部历史。另测旧幂等键 exact replay、异 payload conflict、事务内多个 stream revision 竞争、失败后其他 reader 看不到半批事实。
- [ ] schema 2 保留原 transaction/result 数据，建立 events 索引（global_sequence、event_id、stream_id/revision、transaction_id）、stream_heads、幂等键索引、transaction_id 唯一索引；outbox 增加 state/topic/sequence/transaction_id/event_id 查询列与 pending 索引；checkpoint 增加 projector/sequence 索引。过滤、排序、LIMIT 必须在 SQL 中执行；outbox 使用 ORDER BY global_sequence,outbox_id 和二元游标 `(global_sequence, outbox_id)`，测试同一 event 的多个 outbox 跨页不能丢失。checkpoint 列表按 global_sequence/checkpoint_id 稳定排序，显式取最近两代。

```sql
CREATE UNIQUE INDEX IF NOT EXISTS events_stream_revision
ON events(stream_id, stream_revision);
CREATE INDEX IF NOT EXISTS outbox_pending_topic_sequence
ON outbox(delivery_state, topic, global_sequence);
-- 从 checkpoint 后读取尾部，不能先 SELECT 全部再 Python 切片。
SELECT value FROM events
WHERE stream_id = ? AND stream_revision >= ?
ORDER BY stream_revision LIMIT ?;
```

- [ ] 抽出当前 append 的纯验证/结果构建，保留错误优先级；Durable 在同一 SQLite 写事务中查相关 revision/幂等、分配 global sequence、插入事实/result/index/outbox。不要再调用会永久增长 `_events/_transactions` 的 `super().append_batch()`。内存实现继续作为契约 oracle。
- [ ] `_load_database` 只读 schema/registry/high-water 元数据；正常启动不调用 `from_snapshot`。显式 export/read-all 保留 O(H) 能力，但不得从启动、tick、dispatcher 中隐式调用。
- [ ] dispatcher 改用 `get_transaction`、transaction scoped outbox 查询；无 outbox 的 projection refresh hint 改成持久 pending refresh 查询及成功标记，失败保持可重试。移除随历史增长的 `_notified_transaction_ids`；以 refresh ID/transaction ID 保证重复投影幂等。
- [ ] 一次性 schema1/JSON 迁移：先验证旧事实，再批量建立新索引；schema 版本最后在事务中提交。迁移中断必须可重试，原事实不删除。增加显式 `audit` 路径校验完整历史；正常恢复只验证 checkpoint/tail，不能宣称每次启动仍深验所有旧 payload。
- [ ] GREEN：`python -m pytest backend/tests/test_gameplay_event_store_lazy_restore.py backend/tests/test_population_persistence_regression.py -q`，并运行现有 event-store、outbox、Owner batch 契约全集；验收 append 热路径不读写完整旧库。

### T2.2：持久 checkpoint、精确恢复游标与有限 receipt 缓存

**Files:** 新建 `backend/app/population_continuity/recovery.py`、`backend/tests/test_population_long_session_recovery.py`；修改 `backend/app/population_continuity/runtime_publication.py`、`backend/app/population_continuity/world.py`、`backend/app/population_continuity/hot_state.py`、`backend/app/world_runtime/population_driver.py`、`backend/app/gameplay/event_store.py`。

**Consumes:** T2.1 索引查询、当前 HOT_FIELDS、due heap、确认 receipt。
**Produces:** `PopulationRecoveryCheckpoint` strict Pydantic 模型；`WorldContinuityRuntime.export_recovery_state() -> dict[str, object]` 与 `restore_recovery_state(state: dict[str, object]) -> None`；store 的 `save_projection_checkpoints_atomic(checkpoints: list[ProjectionCheckpoint]) -> None` 与 `get_projection_checkpoint(checkpoint_id: str) -> ProjectionCheckpoint | None`。

| checkpoint 字段 | 内容与校验 |
|---|---|
| `schema_version/context_digest` | schema=1；world/mode/roster/policy/selector/ruleset/scope 全部 pin |
| `kernel_digest/canonical_version` | 对 B0 kernel、hot field 规则、cadence 规则相关实现与配置作稳定摘要；不能仅信可不变的版本字符串 |
| `cadence_id/event_id/record_digest` | 精确已追加事件与原 compact admission record；对应 outbox 必须 delivered |
| `cadence_stream_revision/global_sequence/confirmed_tick` | 分别保存和比较，禁止混用 |
| `actors` | 按稳定 actor_id 排序；六个 HOT_FIELDS 和 actor revision；不保存槽号作为身份 |
| `due_entries` | 所有仍有效 due 项；清除 stale heap 节点，不遗漏同 actor 不同任务键 |
| `last_receipt/last_fingerprint/state_digest` | 最新确认结果和整个快照摘要；不保存全部历史 receipts |

- [ ] RED：checkpoint 恢复结果与完整 replay oracle 的 hot rows/due/cursor/receipt/Owner 事实相同；新 checkpoint 损坏回退上一代，两个都坏 fail closed；规则实现变了但 ruleset 字符串未变也拒绝恢复。
- [ ] 每16个确认窗口生成完整 checkpoint，保留两个固定代次；每个成功窗口保存小 receipt，稳定键为 `population-receipt:<world>:<cadence_id>`。当窗 receipt 与需要写入的完整 checkpoint 用同一 SQLite 事务保存，旧 receipt 可索引读取，不能只靠最近缓存去重。
- [ ] latest checkpoint 锚点必须在 store 存在且 payload/hash 匹配、outbox delivered，验证通过才安装热状态。读取 `stream_revision+1` 之后的 tail；delivered tail 只修复派生态，不重新触发 Owner/Siming；首个 pending 保持未确认，不能跳过到后面的 delivered 窗口。
- [ ] checkpoint 写失败后暂停该局后续窗口，重试当前确认状态；不能让 tail 不断增长。已有 committed fact 不回滚，恢复按 durable receipt 与 admission 状态重新确定确认边界。
- [ ] publisher record 和 world receipt/fingerprint 热缓存各最多2窗，projection/preview最多1个在途窗；driver 以已确认连续 tick/stream cursor 代替无限 `_published_cadence_ids/_runtime_history`。旧 cadence 重试从持久 receipt 查 exact result，异 fingerprint 拒绝。
- [ ] 增加6个独立强杀/故障切点：append后、publish后delivery失败、delivered后hot失败、hot后receipt/checkpoint失败、checkpoint后退出、pending后出现delivered gap。核验无跳窗、无重复Owner/行为写入、pending不丢。
- [ ] GREEN：现有 `test_population_durable_cadence_recovery.py`、`test_population_checkpoint_closure.py`、`test_population_cadence_cache.py` 加新增 long-session 测试；必须从真实 `main` 装配 reopen，不只独立测试热表。

### T2.3：长历史恢复基准与离线维护

**Files:** 新建 `scripts/verification/verify_population_long_session_recovery.py`、`.harness/profiles/population-long-session-recovery.json`；修改 `scripts/verification/population_benchmark_metrics.py`、`docs/verification/population-data-oriented-closure.md`。

**Produces:** `--population 10000 --histories 1000 10000 --tail-windows 8 --repeats 5`；同一脚本提供 `--audit-store PATH` 和 `--rebuild-checkpoint PATH` 显式离线操作。维护操作要求没有运行中 writer，备份原数据库后才替换派生 checkpoint；不修改原 authority 事件。

- [ ] 历史 H 指 checkpoint 前的完整窗口前缀（1,000/10,000），其后再添加8窗固定 tail；允许 fixture 显式创建合法 checkpoint，并记录与生产每16窗周期的区别。创建真实 compact cadence 历史与合法 checkpoint fixture；fixture 生成耗时独立记录，不能把伪造 hash 或重复同一事务当不同窗口。固定人口和tail，对比两种 H。
- [ ] 记录 `startup_sql_rows/model_decodes/replayed_windows/restore_ms/checkpoint_bytes/rss/cache_peak/pending_before/pending_after`；测完整 runtime ready 而不是只有 World 构造。普通恢复≤16窗、上一代≤32窗；固定tail读取量不得随 H 增长。
- [ ] 验收：五次冷进程恢复 p95≤15秒、10k/1k时间比≤1.5、状态oracle完全相同；SQLite/OS page cache条件写入报告。数据库增长是保留历史的正常结果，不能把它与内存泄漏混为一谈。
- [ ] 在文档给出 migrate/audit/rebuild 命令、备份/恢复步骤、规则漂移拒绝原因；明确完整 audit/rebuild 是显式 O(H) 操作，不算正常启动门槛。
- [ ] 项2出口：索引、全部故障切点、跨重启幂等、长历史有界恢复与缓存计数全部通过。

## 3. Godot 真实公开表现闭环（保持 `godot_unverified` 直到实机证据）

### T3.1：定义最小人口公开表现投影

**Files:** 修改 `backend/app/gameplay/godot_mirror_projection.py`、`backend/app/gameplay/godot_mirror_delivery.py`、`backend/app/services/gameplay_mirror_session_access_service.py`；新建 `backend/app/population_continuity/presentation.py`、`backend/tests/test_population_presentation_projection.py`。

**Interfaces 与授权选择：**
- `build_population_actor_view(world, *, actor_id: str) -> CharacterGameRuntimeStateView`：复用既有每 actor 的 Godot state group 契约，新增 `population_public` group；不新增独立 world observation 权限，也不将一人的授权扩为全人口授权。
- `actor_ref` 固定为 `character:<actor_id>`；每个 actor 仍由当前 session binding.allowed_actor_refs 检查。批量展示是客户端聚合多个已获授权的 actor mirror，不是绕过 scope 的全人口接口。可信测试启动装配可配置完整 roster 授权，普通客户端不可自行提交授权名单。
- group 仅包含 `actor_id/confirmed_tick/presentation_position/animation_tag/public_digest`。roster/hot table 没有真实空间坐标，`presentation_position` 是稳定 actor ID 对应的探针展示布局，明确不代表权威空间位置；rotation 为表现常量，visibility_band 留在 Godot。
- animation_tag 只取已确认 cadence 的公开 presentation seed 白名单；没有公开 seed 则用 `idle`，禁止从私有 fatigue/need/memory 推导。public_digest 只计算这些公开字段。
- 沿用 `gameplay_mirror_delivery` 的 connection_epoch/delivery_sequence、facade_revision/source_revision_vector/groups/checksum 和既有 snapshot/delta 结构；不引入第二套人口 revision。adapter 在本地按 actor_ref 合并视图。删除/撤权/renewal/重连清除对应 delta base 后请求 full snapshot。

- [ ] **RED：** 为三档 roster 构造 actor view，断言字段白名单、稳定 ID 布局、公开 digest；相同公开内容但不同私有 hot row 必须 digest 相同；未授权 actor、已撤销 binding、无订阅 snapshot 拒绝。
- [ ] **GREEN：** source 注册到既有 projection publisher；仅对已订阅的最多160个 near/far actor 制备可见消息，10,000人的 B0 仍全量推进。首次订阅通过执行域屏障建立切点，轮换需先 unsubscribe/remove 再订阅新成员。
- [ ] **回归：** 运行 `python -m pytest backend/tests/test_population_presentation_projection.py backend/tests/test_godot_gameplay_mirror_projection.py backend/tests/test_godot_gameplay_mirror_delivery.py backend/tests/test_gameplay_mirror_session_access_service.py -q`；增加 scope 缩小、重连和 revision gap 测试。任何权限或 gap/resync 失败都阻止进入 Godot 验收。

### T3.2：Godot 消费、重连与距离分档

**Files:** 修改 `scripts/l6/backend_bridge/BackendBridge.gd`、`scripts/l6/local_presentation_bus/LocalPresentationBus.gd`、`scenes/phase0/MainDemo.tscn`；新建 `scripts/phase0/PopulationPresentationAdapter.gd`、`scripts/phase0/PopulationPresenter.gd`、`scenes/phase0/PopulationProbe.tscn`、`scripts/phase0/PopulationProbe.gd`。

**Interfaces:**
- `PopulationPresentationAdapter.apply_snapshot(payload: Dictionary) -> void`。
- `PopulationPresentationAdapter.apply_delta(payload: Dictionary) -> void`：base revision 不匹配时只请求 resync，不本地猜测补洞。
- `PopulationPresenter.set_population(snapshot_or_delta: Dictionary) -> void`：接收每 actor 的既有 mirror payload，维护 near/far 节点池；invisible 无节点、取消订阅；人数来自已授权测试 roster，不能枚举未授权 actor。节点池容量由表现阈值决定，不改变 backend population count。

- [ ] **RED：** 在 GDScript 单元/协议 probe 中覆盖首次 snapshot、连续 delta、gap、resync、controlled close、重复 revision、未知字段；断言重复消息幂等、错误消息不改变当前显示。
- [ ] **GREEN：** 将适配器挂到既有 MainDemo autoload/session；用真实 WebSocket 消息驱动 `PopulationProbe.tscn`，每次 upsert/remove 更新可见 marker、计数和最近 revision；不得通过本地 timer 伪造成功。
- [ ] **LOD：** 固定 1280×720、VSync off、固定 renderer；三档 near/far/invisible 分别为 32/68/0、32/128/840、32/128/9840，轮换 actor 检查节点释放和重建；LOD 只影响 presenter 节点，不影响 backend snapshot、receipt、replay hash。
- [ ] **验证命令：** `godot --headless --path . --editor --quit` 只作为导入检查；随后用 `godot --path . --editor` 或固定渲染机运行 `PopulationProbe.tscn`，保存窗口录制/截图、日志、frame-time CSV 和消息 trace。

### T3.3：Godot 实机门禁

**Files:** 新建 `scripts/verification/verify_population_godot_runtime.py`、`.harness/profiles/population-godot-runtime.json`；修改 `docs/harness.md` 与 `docs/verification/population-data-oriented-closure.md`。

- [ ] 由用户指定的另一台机器启动真实 backend 和 Godot 场景，记录 backend commit、Godot `--version`、renderer、分辨率、VSync、场景路径；断开重连一次，确认 resync 后 revision 连续。
- [ ] 每档热身 10 秒、采样 60 秒，记录 frame p50/p95/p99/max、CPU/GPU、stutter、near/far/invisible、snapshot/delta bytes；frame p95 ≤33.3ms 才能通过。
- [ ] 证据必须含一条真实 backend 消息导致场景可见状态变化和一条失败/gap 后的结构化恢复；静态脚本检查、editor import、headless 无渲染设备均只能写 `godot_unverified`。
- [ ] 项3出口：后端投影测试、三档实机场景和重连证据齐全，报告 `status=passed`；缺渲染设备时报告 `blocked`，不升级为通过。

## 4. 混合长时负载、故障和多局容量

### T4.1：真实到达率与事件混合器

**Files:** 修改 `scripts/verification/population_benchmark_metrics.py`、`scripts/verification/verify_population_runtime_scale.py`；新建 `scripts/verification/population_mixed_load.py`、`backend/tests/test_population_mixed_load_schedule.py`。

**Interfaces:**
- `MixedLoadSchedule(population: int, seed: int, mode: str)`：产生固定 1×/10× 的窗口、B0/B1/B2、due peak、Owner contention、dialogue 和 disconnect 事件。
- `MixedLoadRunner.run(duration_seconds: int, schedule: MixedLoadSchedule) -> MixedLoadReport`：外部业务请求通过真实 HTTP/WS，受控 fixture 和故障适配器仅在服务测试启动装配注入；禁止新增无鉴权测试后门。报告 wall-clock、accepted、completed、failed、backlog、queue、owner conflicts、provider counts 和 disconnect recovery。

**时间与负载合同：** 生产保持 86,400 tick 窗兼容；专用 benchmark 启动 profile 设置 `simulation_tick_unit=second/window_ticks=1/wall_period_seconds=1/speed=1|10`，仍使用 main 的完整 owner/runtime 装配。不得把86,400 tick压成一秒再称1×。monotonic 截止时间与实际 confirmed cursor 推导 backlog/lag；checkpoint context pin全部窗口语义。

| 输入 | 固定配方与来源 |
|---|---|
| B0 | 每窗更新全部 roster 的客观热字段 |
| B1/B2 | 每窗最多32/4个有到期任务的角色；由合法初始 state/due fixture 形成，走既有预算和激活，不由客户端直接指定层级 |
| due 波峰 | 每300窗将 min(N/10,100) 个合法 due 项排到同一窗；超过预算必须保留 deferred |
| 常规请求 | health 2次/秒、已鉴权 WS read 1次/秒、结构化事实1次/2秒、交互1次/5秒，分别统计 accepted 与 committed |
| Owner 竞争 | 每60窗同一资源2个合法并发意图，记录一个成功/另一个结构化拒绝或规则允许的串行结果，绝不双花 |
| 模型 | 每60秒各一个 Character/Siming 任务；每次长测前3个任务要求真实 provider成功且 fallback=false，后续可重放已验证响应，明确 live/replay计数，真实网络样本不纳入800ms cadence CPU预算 |
| 故障 | 第5/10/15分钟分别注入provider timeout、慢WS消费者、WS断连；第20分钟SQLite busy 2秒；2小时场景每30分钟重复。短窗口场景用独立故障用例覆盖，不能缩短长测冒充 |

- [ ] **RED：** 固定 seed 断言事件数量、到达时间、due peak 位置、断连顺序可重放；不同 seed 不能复用同一 transaction/idempotency key。
- [ ] **GREEN：** provider 使用可记录的真实接口适配器；live成功样本走真实请求/响应，故障样本只在 provider boundary 注入 timeout/5xx/disconnect，不能把 provider disabled 当通过。
- [ ] 负载生成器的等待使用墙钟 `time.monotonic()`，不直接调用 driver.tick；每局只开一个 writer；请求发送、accepted、事实提交、客户端投影分别计时。

### T4.2：三档 30 分钟和万人 2 小时

**Files:** 新建 `.harness/profiles/population-mixed-soak.json`、`scripts/verification/verify_population_mixed_soak.py`；修改 `docs/verification/population-data-oriented-closure.md`。

- [ ] 三档各运行 30 分钟 1× 混合负载；每 10 秒写一次 heartbeat，每窗口写 backlog、confirmed tick、max advance lag、RSS、SQLite WAL、queue depth。1× 稳态 cadence（不含外部模型网络等待）门槛为 p95≤800ms、30 窗 backlog 不持续增长、最大推进延迟≤1窗；故障窗口单列恢复时间与 drain 成功，不能删掉故障记录。
- [ ] 三档各运行 30 窗 10×，预算 80ms p95；必须完整运行并报告通过/失败，不因 10× 失败否决 1×，也不能删掉失败样本。
- [ ] 万人再运行 2 小时；最后 30 分钟 RSS 中位数相对最初 30 分钟增长≤max(32MiB,10%)；receipt、projection、publisher、driver 集合大小必须匹配计划上限。
- [ ] 运行期间按固定点注入模型 timeout、Owner conflict、单客户端慢消费者、WS 断连重连、SQLite 临时 busy；每个故障点必须证明无重复事实、无跳窗、pending 最终可重试。
- [ ] 项4.2出口：每个 profile 生成带 seed、环境、原始样本和摘要的 JSON；任何数据缺失、虚拟 clock、provider disabled 或 status unknown 均为失败。

### T4.3：2/4 独立局容量探测

**Files:** 新建 `scripts/verification/verify_population_multi_game_capacity.py`、`.harness/profiles/population-multi-game-capacity.json`。

- [ ] 在同一固定 runner 启动 2 局、4 局独立进程，每局固定 10,000 人、10 分钟 1×；每局独立 SQLite、端口、provider correlation id 和输出目录。
- [ ] 报告每局 p95、backlog、RSS、CPU、SQLite I/O、writer count；只有所有局都满足 1× 门槛才记录该并发度 `passed`，否则保留实测容量与失败原因，不预设四局必过。
- [ ] 项4出口：三档 soak、10×、万人 2 小时、故障注入和多局容量均有新鲜报告；不要用单局短测替代长测。

## 5. 协议、序列化和数据搬运优化

### T5.1：建立分段画像基线

**Files:** 修改 `scripts/verification/population_benchmark_metrics.py`、`backend/app/population_continuity/world.py`、`backend/app/gameplay/godot_mirror_projection.py`；新建 `backend/tests/test_population_transport_metrics.py`。

**Interfaces:**
- `TransportMetrics` 字段固定为 `materialize_ms/validate_ms/json_encode_ms/json_decode_ms/pickle_ms/hash_ms/sqlite_ms/application_payload_bytes/ws_frame_bytes/handshake_bytes/alloc_bytes`（按 message kind 分行）。
- `measure_population_transport(command, *, scope, audience) -> TransportMetrics`：同一输入分别测内部 command、事件 payload、公开 snapshot/delta、SQLite 和真实 WS，不把估算字节写成网络字节。

- [ ] **RED：** 对同一 seed、同一窗口重复三次，断言 canonical JSON/hash、scope/audience 结果稳定；检查内部 payload 和公开 payload 不共享可变引用。
- [ ] **GREEN：** 在一次 boundary 完成校验后复用 canonical bytes/hash；命令内部继续使用已验证对象，公开投影只构造授权字段；pickle 只用于可信进程内基准，测试传入客户端 pickle 必须拒绝。
- [ ] 为 full snapshot 与 delta 分别记录 actor 数、字段数、对象构造次数和 bytes；当 delta base revision 不匹配时走 resync，不拼接非法增量。

### T5.2：真实 WebSocket 字节与持久化对照

**Files:** 修改 `backend/app/debug_stream.py`、`backend/app/gameplay/godot_mirror_delivery.py`、`backend/app/gameplay/event_store.py`；新建 `scripts/verification/verify_population_transport_cost.py`。

- [ ] 在真实 Uvicorn/WS 客户端上统计实际发送的 application_payload_bytes；用测试侧 TCP 计数代理统计 ws_frame_bytes/handshake_bytes（固定 loopback 明文且关闭 compression，记录 compression=disabled），不把 IP/TCP 头声称为已测。发送次数、排队字节、resync 次数单列。
- [ ] 对同一窗口比较 full、authorized delta、内部 event、SQLite page/WAL 文件增量（不冒称OS实际磁盘写入）；记录 p50/p95/max，不把内部 7.59MiB/window 直接当网络流量。
- [ ] 只有画像显示瓶颈后才采用最小改变：优先复用编码结果和减少重复物化；不得用关闭 hash、放宽 Pydantic、共享可变对象或删除 receipt 来换吞吐。
- [ ] 优化前后使用同一 seed、roster、provider 响应和独立的相同初始数据库副本；运行 correctness oracle，确认 Owner 事实、replay hash、session 次数、公开结果完全一致。

### T5.3：优化出口

- [ ] 输出 `transport-before.json`、`transport-after.json` 和差异表，包含每个阶段的中位数/p95、实际 WS bytes、SQLite bytes、RSS 和错误数。
- [ ] 同机五次独立重复：至少一个已测阶段中位数降低10%且差异超过两组样本MAD，或实际字节/物化次数确定性降低20%；所有 correctness/1×短回归通过，才合入优化；没有改善的实验回滚，不保留“以后可能有用”的分支。
- [ ] 项5出口：画像、实现、回归、真实字节证据全部齐全；仅减少 Python 对象数量但未证明端到端收益，不算通过。

## 6. CI 回归门禁与总验收

### T6.1：可重建环境和显式 profile

**Files:** 修改 `.github/workflows/harness.yml`、`docs/harness.md`、`docs/INDEX.md`、`scripts/verification/harness.py`；新建 `.harness/profiles/population-runtime-closure.json`、`scripts/verification/aggregate_population_closure.py`。

- [ ] CI 明确安装 `backend[dev]`，打印 Python、SQLite、OS、CPU、Godot 版本；provider secret 只检查存在性并脱敏，缺少真实 provider 或渲染 runner 时标记对应 profile `blocked`，不伪造 pass。
- [ ] `population-runtime-correctness` profile 运行四个已有 correctness profile 加 T1/T2/T5 新测试；固定 pytest 命令、并发度和超时，失败保留完整日志。
- [ ] `population-performance-fixed-runner` 只在标签固定的 runner 运行 1× 三档、10× 三档、万人 2 小时、多局容量；CI 普通 runner 不得以短测冒充。
- [ ] `population-godot-runtime` 使用固定 Godot 4.6.3、1280×720、VSync off、固定 renderer；无设备返回 `blocked/godot_unverified`，阻止总完成。
- [ ] 所有 profile 输出 `.harness/verification/<run-id>/manifest.json`，列出 base commit、source SHA256、环境、seed、命令、开始/结束时间、原始文件路径和 status。

### T6.2：总报告聚合器

**Interfaces:** `aggregate_population_closure.py --root RUN_DIR --expected-items 1,2,3,4,5,6 --require-godot-runtime --require-fresh-commit SHA`。

- [ ] **RED：** 为缺 profile、旧 commit、`not_run`、`blocked`、`static_only`、`godot_unverified`、缺原始 CSV、阈值不一致分别建立 fixture；聚合器必须非零退出并列出缺口。
- [ ] **GREEN：** 聚合器逐项读取 schema 版本、source SHA、profile status、thresholds、raw artifacts、summary metrics；不得只信人工编辑的 summary 字段。
- [ ] 同时验证三档 1× 必过、10× 结果完整、T1/T2/T3/T4/T5/T6 各自 `passed`、mainline/change-lifecycle/all fresh evidence；任何一个条件失败，总状态为 `incomplete`。
- [ ] 聚合器生成 `closure-report.json`、`closure-report.md`、JUnit 结果和失败定位；报告分别列出“实现/后端验证/Godot验证/阻塞”，不能把静态完成变成运行完成。

### T6.3：文档、交接和执行出口

**Files:** 修改 `docs/verification/population-data-oriented-closure.md`、`docs/harness.md`、`docs/INDEX.md`；不提交 `docs/superpowers/`。

- [ ] 更新运行手册：依赖安装、Godot 4.6.3 获取与摘要校验、provider 配置存在性、固定 runner、启动/停止命令、故障注入、产物目录、失败后重跑和离线 audit/rebuild；不写入 secret。
- [ ] 同一实现提交中只包含代码、测试、脚本、CI 和版本化验证文档；`git diff --check`、`git status --short`、目标文件清单核对后再提交，排除 worktree、XLSX、临时数据库和 `.harness/t/`。
- [ ] 项6出口：可重建 CI、总聚合器、运行手册、fresh evidence 全部通过；没有总报告则六项保持 `incomplete`。

## G0—G9 最终门禁（必须按顺序执行）

每个门禁完成后把命令、run id、commit SHA、status 和产物路径写入 `progress.json`。门禁失败时停止宣称完成，只修复失败项并从该门禁重跑。

- [ ] **G0 基线与范围：** 开工时 HEAD 为记录的 base commit；最终版本必须以该基线为祖先，所有证据匹配实际实现 commit/source SHA；工作区只含本目标文件；`python -m pytest -q` 通过；无未记录的配置或 secret。
- [ ] **G1 服务隔离：** T1 profile 真实 Uvicorn、线程/进程 writer 证明、loop p99、accepted p95、队列上限、provider completion pin 和异常 health 全部满足。
- [ ] **G2 恢复：** T2 schema/index、六故障切点、两代 checkpoint、exact receipt、1k/10k 五次冷恢复和固定 tail 比率全部满足。
- [ ] **G3 Godot：** T3 profile 为 `runtime_verified`；真实 backend→WS→Godot 消息导致可见变化；三档 frame p95、LOD counts、gap/resync 证据齐全。否则总体保持 `godot_unverified`。
- [ ] **G4 1× 短验收：** 100/1,000/10,000 30 窗与 p95≤800ms、无持续 backlog、最大推进≤1窗。
- [ ] **G5 10× 独立压测：** 三档 30 窗真实完成，80ms 预算结果如实记录，允许失败但不能缺报告或改门槛。
- [ ] **G6 长测：** 三档 30 分钟、万人 2 小时、故障注入、RSS 和缓存上限满足；SQLite page/WAL 与 provider 状态齐全。
- [ ] **G7 数据搬运：** before/after 画像、实际 WS bytes、SQLite bytes、canonical hash 和 correctness oracle 一致；至少一个已测瓶颈改善。
- [ ] **G8 多局与 CI：** 2/4 局容量结果齐全（性能失败作为观测容量允许，不预设四局通过；缺记录不允许）；correctness/performance/Godot profiles 在可重建环境运行，固定 runner 证据新鲜。
- [ ] **G9 总聚合：** `aggregate_population_closure.py` 返回 0，六项均为 `passed`，Godot 为 `runtime_verified`，mainline/change-lifecycle/all 通过；然后才允许写“六项完成”。

## Godot 跨机器验收交接

- 在 `docs/verification/population-runtime-closure.md` 给出最终 commit/source SHA、Python/Godot 固定版本、依赖安装、backend 与 PopulationProbe 启动命令；配置只含变量名，不包含密钥。
- `verify_population_godot_runtime.py` 在另一台机器从相同代码启动真实 backend/Godot，生成 manifest、message trace、frame CSV、截图和原始日志。
- 证据包保留 renderer、分辨率、VSync、CPU/GPU/OS、roster/seed/授权范围；使用内容摘要校验完整性，支持复制到主工作区 `.harness/verification/` 后由总聚合器验证。
- 本机可完成脚本实现和静态检查，但 T3 的 runtime gate 只能由外部真实报告通过；等待期间 Godot 状态保持 `godot_unverified`，不因引擎已安装或 import 无错误升级为通过。

## 执行记录规则与提交边界

- 每个 T1—T6 只在该项出口通过后把对应项从 `running` 改为 `passed`；局部测试通过只能写入 `tests`，不能改变 item status。
- 失败记录原始命令、退出码、环境、seed、最近一次有效产物和恢复命令；不要覆盖失败报告或删除旧证据。
- 代码提交按可回滚边界组织：T1、T2、T3、T5、T4、T6 各自经过测试和 review 后提交；`docs/superpowers/` 始终保持本地未跟踪/未提交，主分支整合使用 cherry-pick。
- 最终反馈必须只从 G9 总报告读取状态，并分开列出“已实现且验证”“已实现但 Godot 未验证”“阻塞”；G9 未通过时，反馈只能说明未完成及下一条可执行恢复命令。
