# 人口 runtime 并发方案：官方机制与本轮实测边界

查询日期：2026-10-09。结论：成熟的线程池、进程池可以复用，但本轮按原批次执行的压缩线程实验明显变慢；没有证据支持通过增加线程、计算进程或 SQLite writer 解决当前千人 10× 吞吐缺口。

本文只记录资料研究、当前源码核查和已经完成的诊断实验，不构成完整 soak、10× 或多局容量验收。保留原 owner、FULL、CAS、返回隔离、损坏拒绝、恢复语义，以及每窗 28 人 fixture 和 16 个事务分组；未改变阈值、输入或 Python 版本。

## 基线和证据时间

- 当前工作树：`D:/MyConfiguration/TCLXUSER/.codex/worktrees/population-hotpath/Paralls-phase0-1`。
- AU 生产源码标识：`sha256:47035eeb471730b67e5f5927a98f30c514f5cbc2df83ee32ffac704e7a13210c`。
- 当前验收环境：CPython 3.13.9、SQLite 3.53.4、python-zlib-ng 1.0.0、pydantic-core 2.46.5。实际检查 `sys._is_gil_enabled()=True`、`sys.thread_info.name='nt'`；已安装扩展 wheel 为普通 `cp313`，本文不假设启用 free-threaded Python。
- AU 证据：`D:/ParallsEvidence/paralls-owner-serialization-20261009T073358Z`。`analysis.json` 和 `compression-threads.json` 均标记 `diagnostic_only=true`、`formal_acceptance=false`。
- AU 于 `2026-10-09T15:58:10.601079+08:00` 封存；`seal.json` SHA256 为 `33cbcf22be0301a7dd1c5882e736d4aa07b1cdf3f2d4562598e607fb55c78cda`。
- 本文在上述封存之后新增。AU 的原 1,995 个源码快照、2,154 个封存绑定及其历史输入未追加本文，也未重新解释为含本文的新候选。研究阶段未运行测试或负载、安装依赖、读取 `.env`，未修改已封存证据。

## 官方机制与适用范围

| 机制 | 核查结论 | 本项目含义 |
| --- | --- | --- |
| CPython 3.13 普通线程 | GIL 限制 Python 字节码并行；等待 I/O 或明确释放 GIL 的扩展可重叠 | 不能仅给 Python 循环或模型序列化增加线程就声称多核加速 |
| python-zlib-ng 1.0.0 | `zlib_compress_impl` 的 `zng_deflate` 段明确使用 `Py_BEGIN_ALLOW_THREADS` | 独立、不可变 bytes 的原生压缩可以并行；UTF-8、分配和 Python 包装不等于该段 |
| pydantic-core 2.46.5 | `SchemaSerializer.to_json → to_json_bytes` 持有 Python token 和 `Bound` 对象；选中路径未 detach，custom serializer 直接调用 Python | Rust 实现不自动意味着释放 GIL；不能将完整 `model_dump_json` 当纯原生线程任务 |
| SQLite WAL | 单个 WAL 同时只有一个 writer；FULL 每次 commit 同步 WAL | 多连接、多写线程仍竞争同一提交点，不能借此省去原持久化工作 |
| CPython SQLite 调用 | `sqlite3_step` 释放 GIL；Python 参数绑定转换在其外部 | 可与独立工作重叠 native I/O，但不能跨越依赖提交结果的下一步 |

来源：[CPython 3.13 threading](https://docs.python.org/3.13/library/threading.html)、[zlib-ng v1.0.0 固定源码](https://github.com/pycompression/python-zlib-ng/blob/v1.0.0/src/zlib_ng/zlib_ngmodule.c#L185)、[SQLite WAL](https://www.sqlite.org/wal.html#concurrency)、[CPython v3.13.9 SQLite cursor](https://github.com/python/cpython/blob/v3.13.9/Modules/_sqlite/cursor.c#L493)。

pydantic-core 的版本与路径通过 [Pydantic v2.13.5 Cargo.toml](https://github.com/pydantic/pydantic/blob/v2.13.5/pydantic-core/Cargo.toml) 固定为 2.46.5；核查了 [SchemaSerializer](https://github.com/pydantic/pydantic/blob/v2.13.5/pydantic-core/src/serializers/mod.rs#L132)、[to_json_bytes](https://github.com/pydantic/pydantic/blob/v2.13.5/pydantic-core/src/serializers/shared.rs#L535) 和 [custom serializer 调用](https://github.com/pydantic/pydantic/blob/v2.13.5/pydantic-core/src/serializers/type_serializers/function.rs#L132)。这只约束所核查的普通序列化路径；某个自定义 hook 自行释放 GIL 不代表整个遍历都能并行。[PyO3 v0.28.2 并行说明](https://github.com/PyO3/pyo3/blob/v0.28.2/guide/src/parallelism.md)也要求显式 detach。

## 已有可选入口与真实启用路径

`backend/app/population_continuity/hot_state.py:236` 的 `map_readonly` 已有 `workers` 参数，默认值为 1。只有 `workers > 1` 且存在多个 batch 时，才在该次调用中创建 `ThreadPoolExecutor`；单 worker 或单 batch 直接串行计算。只读快照计算完成后，原 owner 仍检查 actor revision 和 generation，拒绝失效结果。

`world.py:285` 的 `build_population_projections` 同样默认 `workers=1`。实际 `runtime_publication.py:390/444` 和 `world.py:420` 的发布、重建与确认调用没有传入 `workers`，因此当前 runtime 使用串行路径。已有可选线程入口不能记成当前已启用多线程。

传入的 evaluator 是捕获窗口参数的局部 lambda，输入及 B0 返回值包含 `MappingProxyType`。直接将现有线程池换成 `ProcessPoolExecutor` 不满足其 picklable 约束；需要顶层纯函数和明确的 primitive DTO，并保留 owner 的版本复核、排序及确认。当前证据没有证明这样的改造具有足够收益。

## AU 序列化诊断

两轮均使用原 collector、HTTP/WS/spawn 和千人 30 个完整窗口。下表是选中阶段每窗均值，包含观察开销；exclusive 只排除了选中子调用，不等于生产净耗时或可删除工作。两轮 `actual_provider_calls=0`，不能据此签真实 provider 通过。

| 选中工作 | 每窗调用量 | 第一轮 ms | 第二轮 ms | 限制 |
| --- | ---: | ---: | ---: | --- |
| event 独立 JSON 序列化 | 197 | 1.3098 | 1.5622 | 与 batch JSON 可能重复表达值，但 custom hook 次数和顺序仍可观察 |
| outbox JSON 序列化 | 200 | 1.0306 | 1.2241 | 包含 delivery update，不能将全部费用算作插入时冗余 |
| 全部 codec 独占之和 | — | 5.5198 | 6.5772 | 包含 UTF-8 和封装，不是纯 GIL-free 压缩 |

只识别顶层原生 serializer 不能证明嵌套 payload 没有自定义模型或 serializer。不能因值相等就删除第二次 hook，也不能将上述费用全部记成缓存或并行净收益。

## 原压缩的两线程只读实验

`compression-threads.json` 从真实账本读取最新 128 个事务组：862 个输入，总计 1,549,541 bytes，输入中位数 943 bytes。原 owner 的模型序列化和 UTF-8 已提前完成，未计入任何线程收益。使用预热的 2 worker，最多 2 个 pending task，输入预算 8 MiB；两组固定 ABBA/BAAB 各 16 次，合计 32 次，每个模式 8 次，全部输出字节精确相等。

| 调度对照 | 串行均值 ms | 两线程均值 ms | 可据此做出的判断 |
| --- | ---: | ---: | --- |
| 按原 batch 边界调度 | 6.1881 | 27.9714 | 慢约 4.52 倍，拒绝进入当前生产路径 |
| 全 corpus 粗分块 | 4.9847 | 3.8013 | 仅省约 1.1834ms/整份 corpus，不能当每窗收益 |

粗分块实验忽略了原 SQL 与 hook 顺序，只是乐观批处理参照，不具备生产等价资格。账本最终 outbox 也可能已被 delivery 更新，不能替代插入时原输入。submit、分块与有序收集已计入比较，公共的输出相等检查不计入比较。

线程池启动 1.4632ms、关闭 0.1701ms；关闭后所属线程为 0，数据库/WAL/SHM 哈希未改变。这些证明只读实验完成且字节等价，不证明原整窗变快、RSS 长时稳定或真实 owner 故障语义已验证。此次按批实验已否定这条实现，不应再据“压缩释放 GIL”直接增加生产线程。

## 安全边界与标准库复用条件

**压缩线程**：如将来输入粒度改变且成本重新量化，只能给 worker 不可变 bytes 和纯压缩函数。`event_store.py:1159` 的 append 持有 store 锁，`_encode_json:991` 又调用 `_remember_json_text:971`；将完整 `_encode_json` 交给线程并让 owner 持锁等待会死锁。缓存、SQL、CAS 和 FULL 仍由 owner 操作。精确原生模型、嵌套 payload、str 子类 `encode` 和 custom hook 的资格必须分别证明；未满足时保留旧调用路径。每次 submit 后立刻等待没有并行收益。

**计算进程**：标准库进程池绕开 GIL，但 Windows spawn 启动、双向 pickle、额外解释器 RSS 和失败回收均有成本。若以后发现足够大的纯计算叶子，可复用固定小池、粗 shard、primitive DTO；worker 不拥有数据库、authority 或提交权限，owner 保留源版本复核和确定性合并。当前 runtime 子进程不是 daemon，技术上允许创建子进程，但 owner 硬退出不会自动杀掉这些后代；新增池必须先证明 parent-death、停止、BrokenProcessPool 和硬退出恢复，不能仅验证正常计算结果。[CPython multiprocessing](https://docs.python.org/3.13/library/multiprocessing.html)、[v3.13.9 process pool 实现](https://github.com/python/cpython/blob/v3.13.9/Lib/concurrent/futures/process.py)。

**I/O 线程**：现有 `runtime_process.py` 已用 `asyncio.to_thread` 等待 queue、join 和 stop，provider 也有 `DialogueProviderSlots` 的 semaphore 限流与实际完成后释放资源的模式。可复用该资源生命周期思想；新增线程不会减少 owner 的必需 CPU 工作。SQLite serialized 模式只保证安全串行访问，不使同库成为多 writer；修改 `check_same_thread` 也不能提高这一提交点的并行度。[SQLite threading modes](https://www.sqlite.org/threadsafe.html)、[asyncio.to_thread](https://docs.python.org/3.13/library/asyncio-task.html#asyncio.to_thread)。

池的 `max_workers` 不等于队列上限：3.13.9 ThreadPool 使用 `SimpleQueue`，ProcessPool 也可持续增加 pending work；`Executor.map` 会立即提交输入。应显式约束任务数和保留的 bytes，失败后停止新提交，取消尚未运行的任务，并等待已经运行的实际工作结束。`Future.result(timeout)` 和 `cancel_futures=True` 不会停止运行中的任务，线程退出也必须等其完成。[v3.13.9 thread pool](https://github.com/python/cpython/blob/v3.13.9/Lib/concurrent/futures/thread.py)、[v3.13.9 Executor.map](https://github.com/python/cpython/blob/v3.13.9/Lib/concurrent/futures/_base.py)、[Executor/Future 官方语义](https://docs.python.org/3.13/library/concurrent.futures.html)。

当前 `/3.13/` 文档已经对应 3.13.16，明确注明 `max_tasks_per_child` 的排队回收死锁到 **3.13.15** 才修复；不能把该修复视为本机 3.13.9 已具备能力。本文不建议使用该参数盲目回收 worker，也不建议依赖 3.14 的 `buffersize`、`InterpreterPoolExecutor`、`terminate_workers` 或 `kill_workers`。[版本说明](https://docs.python.org/3.13/library/concurrent.futures.html#concurrent.futures.ProcessPoolExecutor)。

## 下一量化点

继续寻找实质减少的串行工作，而非先增加线程。下一次诊断应在同一原窗口内分开统计：模型 JSON、`json.dumps`、UTF-8、原生压缩、缓存记账、参数绑定、SQL 执行和 commit；报告调用链、input bytes 分布、独占计时及观察开销。尤其要先量化真正未重复的开销，不能把 codec 全段、outbox update 或 inclusive 累积当收益。

具体入口优先沿 `event_store._write_delta → _index_events` 检查同一 batch 与独立 event/outbox 的序列化，记录可安全复用的精确次数和原生资格；再沿 Organization fixture、domain dispatch 和 pipeline 的选中串行段找至少约 5–10ms/窗的明确重复工作。没有该量级的可辩护成本，就不进入新的线程或进程架构改造。

任何后续生产候选均须单变量对照：先证明 custom hooks、返回隔离、CAS、损坏拒绝、失败回滚及恢复等价，再用原 native 完整窗口 ABBA 比较真实吞吐和尾延迟，同时检查峰值 RSS、排队 bytes、正常退出与 parent-death。长时窗口仍按原合同执行；本轮没有宣称千人 10×、完整 2 小时 soak 或原机器性能问题已解决。
