# 群体运行时补齐与外机 Godot 验证交接

当前整体状态：**进行中，Godot 未验证（godot_unverified）**。本文件不是六项验收通过声明。其他会话从本文和隔离分支 `codex/population-runtime-closure` 的本地执行台账继续；不要将静态测试或合成证据测试记为引擎通过。

## 后端 WebSocket 启动

当前验证依赖为 Uvicorn 0.52.4 / websockets 17.1。正式 CLI 与采集器均显式使用 `websockets` 实现，不使用 `auto`：0.52.4 默认 sansio 在 peer Close 已收到、TCP 清理尚未回调时，服务 shutdown 会重复发送 Close 并抛 `InvalidState`。退出错误仍按失败保留，不能忽略。手工启动也须保持同一实现：

```powershell
$env:PYTHONPATH = 'backend'
python -m uvicorn app.main:app --ws websockets --host 127.0.0.1 --port 8000
```

该实现已标记为上游弃用，未来别名可能转回 sansio，因此依赖暂限制 Uvicorn `<0.53`。升级须先通过 `test_runtime_websocket_shutdown.py` 的真实 TCP 关闭交错回归，再重跑原服务/镜像退出门禁；不把变更默认实现当作无行为变化的依赖升级。

## 外机准备

使用包含本文及 `scripts/verification/verify_population_godot_runtime.py` 最新改动的同一代码版本。保持原仓库/原 Godot project，执行 `git lfs pull`，不要另建项目。真实验证机需要 Python **3.12.14**、Godot **4.6.3 stable**、支持 Vulkan Forward+ 的 GPU，以及可见桌面。机器可保持离线模型配置：本 profile 显式使用 local fixture，不调用真实模型，真实 Character/Siming 模型验收属于另一项门禁。

```powershell
python -m venv .runtime/godot-verification-venv
.runtime/godot-verification-venv/Scripts/python.exe -m pip install -c backend/ci-constraints.txt -e './backend[dev]'
.runtime/godot-verification-venv/Scripts/python.exe scripts/verification/verify_population_godot_runtime.py --collect .harness/verification/population-godot-external-001 --godot-exe 'D:/tools/Godot_v4.6.3-stable_win64_console.exe'
```

替换 Godot 可执行文件路径。输出目录必须不存在，每次重跑使用新目录。本轮运行100／1,000人两档；每档热身至少10秒、真实渲染采样至少60秒，再验证 LOD、断连重绑和全量恢复。`--headless --editor --quit` 只用于前置导入，正式采样必须有窗口。固定1280×720、Forward+、Vulkan、VSync关闭，frame p95≤33.3ms。

也可在外机用显式 profile 自动分配全新的证据目录：

```powershell
.runtime/godot-verification-venv/Scripts/python.exe scripts/verification/harness.py --profile population-godot-runtime --godot-exe 'D:/tools/Godot_v4.6.3-stable_win64_console.exe'
```

`population-godot-runtime` 不随本机 `all` 或 correctness 自动运行。最新入口报告为 `.harness/verification/population-godot-runtime-report.json`，其中 `manifest` 指向本次独立证据目录；原始报告仍由 collector 复验，不用入口摘要代替。

GitHub Actions 的 Harness 手动入口提供 `run_population_godot`，默认关闭。启用前必须在外机配置标签 `self-hosted / Windows / X64 / paralls-godot-4-6-3`，设置该 runner 的 `GODOT_EXE`，并以可访问可见桌面的交互用户运行 runner。机器需符合上文版本和 Vulkan 要求；普通无桌面的 Windows service 不构成渲染设备。该 job 使用 LFS 和固定依赖，失败时也上传已有证据。未注册 runner 时任务只会等待，不代表验证通过；尚未取得远端 CI 运行证据。

脚本为每档启动独立的原 `app.main` Uvicorn 后端，使用操作系统分配的空闲本地端口和临时存档，并由后端签发只用于本次的 opaque credential。不会关闭已有后端/编辑器进程。launcher secret 只存在父进程和本次 backend 环境，重连 credential 和 SQLite 在本次私有临时目录，不进入证据目录。不要复制 `.env` 或私有存档给下一会话。

## 证据判定与复验

单独的 `godot-capture.json status=captured` 不代表通过。Python runner 还要校验逐帧 CSV、原始 WS application packets、checksum/基底/序号、实际 marker 更新与截图锚点、完整 PNG 容器、权威摘要，以及进程退出。

- 初始全量快照，随后至少一条已应用 delta；主动丢一次更新后 gap→完整快照恢复；断连后新 epoch 和全量恢复。
- 常驻 near=32，near+far≤160，其他人口不可见；B0 receipt.advanced_count 必须等于全 N。
- 采样之后暂停同一 driver 的调度，不写 world.pause/resume 事实。真实轮换可见成员/摄像机前后，核对同一确认点的 receipt/checkpoint、全部人口热态与 revision、已物化 Character 当前态、Owner 收据、完整与checkpoint-tail replay hash均相同。然后恢复同一 driver，再进行断连重连。
- PNG 只接受真实采样的1280×720图片，并与消息 trace 的 marker/tick相连。两张图必须不同；人工仍应查看图像，确认渲染内容。
- 应用层字节来自 WebSocketPeer 收到的 UTF-8 packet。`ws_frame_bytes` 保持 null，此 profile 不声称已测 TCP/framing；相关传输成本由 T5 单独测量。

完整目录保留 roster、manifest、依赖版本、帧 CSV、消息/观察 JSONL、PNG、LOD/authority摘要、进程与原始日志。`manifest.json` 记录代码内容 SHA256（含 Python、GDScript、scene、project）、commit、dirty source路径、引擎binary hash、软硬件版本及每个 artifact 的摘要。移动整个目录后，在**相同源代码**上复验，无需运行 Godot：

```powershell
.runtime/godot-verification-venv/Scripts/python.exe scripts/verification/verify_population_godot_runtime.py --verify-artifacts 'D:/verification/population-godot-external-001'
```

返回0且总 `godot_status=runtime_verified` 才能更新 Godot 门禁；缺任一档、错误版本、缺原始文件、帧超预算、authority变化、无恢复链或进程异常均返回2，保持未验证。不要用旧成功结果补本次缺失文件，不要改 CSV 或删除慢帧。

## 继续执行的入口

隔离工作树当前路径：`D:/Paralls-phase0-1/.worktrees/population-runtime-closure`。

- 计划：`docs/superpowers/plans/2026-09-16-population-production-runtime-closure-implementation-plan.md`（本地过程文档，不提交）。
- 过程台账：`.superpowers/sdd/2026-09-16-population-production-runtime-closure-implementation-plan/progress.md`。
- 机器状态：`.harness/verification/population-runtime-closure/progress.json`。
- 每个子包有实现报告、固定commit差异和独立审查报告。局部PASS不能关闭整项；六项和总聚合门禁仍须分别完成。

本机仅跑 backend、静态检查和验证器控制测试，没有执行 Godot 引擎。外机结果到齐前继续保留 godot_unverified；完整 backend/harness 和真实长时负载也必须在最终版本重新验收。

本版本另行核对同一 probe 启动时钟的 `ready_elapsed_us`、`sample_start_elapsed_us`、`sample_end_elapsed_us`、`capture_end_elapsed_us`：热身与采样差值必须分别等于记录时长和 CSV 末 elapsed；before 截图在 ready 至采样开始之间，after 在采样结束至 LOD-before 之间。每帧的确认 tick 还须与该绝对时刻已经记录的 marker 更新一致。截图可有真实绘制延迟，但不能用短时截图/trace 搭配另一段 60 秒 CSV。

source pin 与 dirty 清单还包括根目录 `assets/characters/profiles` 以及 production registry 的六个 `_APPROVED_MANIFESTS` JSON；不扫描其他设计文档或 `.env`。合法 `gameplay_mirror_resync_required` 控制包单独计入应用层字节、只清对应 actor 的验证基底，不消费全局序号；该 actor 的 delta 必须等完整快照恢复后才能验证。

## 传输成本证据复验

T5 插桩成本实验使用 `manual_window_cost`：每个原 owner 窗口完成后，等待全部订阅角色的真实 WebSocket 帧校验完成，才推进下一窗。端到端时间仍从原 tick 开始到最后一帧校验；同 seed、30 窗、5 配对、160 角色范围及所有授权/队列错误门禁不变。此排程不证明实时 1×；未插桩 service 的连续时钟与响应门槛独立保留。manifest、owner-ready 与离线校验明确绑定该排程和逐窗完整接收确认。

正式 T5 采集目录可在相同源代码上离线复验：

```powershell
python scripts/verification/verify_population_transport_cost.py --verify-artifacts 'D:/verification/transport-cost-run' --require-fresh-commit '<完整提交SHA>'
```

该命令不启动 Godot 或后端。它要求1,000人、30窗、五次对照，检查源码与产物摘要，重放公开 WS 原包并从逐窗样本重算改善结论；旧提交、缺文件、修改摘要或不完整窗口均失败。真实 TCP 计数沿用原采集值并校验各方向加总；不是再次嗅探。即使此步通过，未插桩1×短验收与外机Godot仍需单独通过，不能据此关闭总目标。

## 服务隔离证据复验

每档至少120秒的服务隔离目录可离线复验；100／1,000两档必须各自通过：

```powershell
python scripts/verification/verify_population_service_isolation.py --verify-artifacts 'D:/verification/service-run/1000' --require-fresh-commit '<完整提交SHA>'
```

复验会从发送/应答时序重算客户端耗时，核对后台完整10ms心跳序列、连续窗口覆盖、实际写入线程、provider等待线程及原门槛。短smoke、缺尾部、压缩采样区间、旧源代码或修改后的摘要均不能通过。这里使用受控慢provider，仍不证明真实模型可用；该命令不启动任何后端或Godot进程。

## 混合负载、并行容量与固定机器 CI

以下入口必须在确定的同一性能机器、同一干净提交运行。需要在本机配置真实 Character/Siming provider；不要将密钥写入报告或命令参数。当前只有工具功能与控制测试证据，正式长测尚未通过。

```powershell
python scripts/verification/population_mixed_matrix.py --kind short --output 'D:/verification/closure/realtime-short' --require-fresh-commit '<完整提交SHA>'
python scripts/verification/population_mixed_matrix.py --kind soak --output 'D:/verification/closure/mixed-soak' --require-fresh-commit '<完整提交SHA>'
python scripts/verification/verify_population_multi_game_capacity.py --output 'D:/verification/closure/multi-game' --require-fresh-commit '<完整提交SHA>'
```

short 为100／1,000人各 30 秒 1×；soak 为100／1,000人各 30 分钟 1×、各 30 窗 10×、另加1,000人 2 小时。所有 1× 必须通过，10× 必须完整且数据一致，其性能结果单列。容量入口分别同时运行 2／4 个独立1,000人后端，每组共同测量 600 秒；`capacity_passed` 记录该并发度是否满足性能，容量不足仍保留原报告，但缺失/不一致的证据不能通过。容量诊断额外启用 SQLite 逻辑读行、返回字节、语句及原 writer 调用计数；`physical_disk_bytes_measured=false`，不是物理磁盘吞吐。CPU 与该 I/O 区间包含尾部排空，普通 short/soak 不启用这个计数器。

将上述命令的 `--output` 替换为 `--verify-artifacts`，保留 kind 和完整 SHA，即可只读复验完整目录；不启动后端、模型或 Godot。输出目录必须不存在，不能裁剪人口、时长或失败样本。

Harness 手动入口的 `run_population_performance` 默认关闭。`population-performance-fixed-runner` 使用 `self-hosted / Windows / X64 / paralls-population-performance` 标签与独占 concurrency group；应只给确定的性能机器配置这个专用标签。该 job 顺序执行服务隔离、长历史恢复、传输成本、short、soak 和多局容量；前一项失败仍收集后续项，最终保留失败状态与原证据。上传排除运行存档和恢复库副本，保留独立导出证明、原日志与可离线复验的 manifests。

配置 repository Variables：`CHARACTER_MODEL_PROVIDER_KIND`、`CHARACTER_MODEL_ENDPOINT`、`CHARACTER_MODEL_MODEL`、`SIMING_LLM_ENDPOINT`、`SIMING_LLM_MODEL`；Secrets：`CHARACTER_MODEL_API_KEY`、`SIMING_LLM_API_KEY`。缺少配置时采集会失败，不自动沿用本地模型。专用 runner 的注册、认证及远端运行尚未验证；job 写入不代表 CI 已通过。Godot 继续使用单独外机入口。

## 长历史图存储的升级边界

图schema 6增加可重建的当前时间索引，正常写入与原事实使用同一事务；旧schema首次打开时一次性回填。旧库升级前按离线维护流程备份，失败会回滚；当前schema缺表或索引时拒绝打开，不自动按空图继续。正常查询只读取当前最大时间所需的两行，分支维护、迁移和完整历史审计仍有全量成本。

索引保留原MAX_TIME有效版本、撤回、关闭和分支规则，不替代完整存档审计。绕过原写入接口直接修改历史JSON后，应执行离线审计；普通当前时间查询不再逐次反序列化所有历史实体。

## 六项证据汇总

将各次完整采集目录复制到一个验收根目录，在根目录创建 `evidence.json`。它只记录相对目录，不接受手填通过状态：

```json
{
  "schema_version": 1,
  "profiles": {
    "service-100": "service/100",
    "service-1000": "service/1000",
    "recovery": "recovery",
    "godot": "godot",
    "mixed-soak": "mixed-soak",
    "multi-game": "multi-game",
    "transport-cost": "transport-cost",
    "realtime-short": "realtime-short",
    "correctness": "correctness",
    "mainline": "mainline",
    "change-lifecycle": "change-lifecycle",
    "all": "all"
  }
}
```

```powershell
python scripts/verification/aggregate_population_closure.py --root 'D:/verification/closure' --expected-items 1,2,3,4,5,6 --require-godot-runtime --require-fresh-commit '<完整提交SHA>'
```

命令不启动 Godot、backend 或 provider。每个目录须包含同一提交与源摘要的 manifest，且通过对应的原始证据复验；目录缺失、跨目录复用、静态结果、旧源、摘要不匹配或缺专用复验入口均输出 `incomplete` 并返回2。结果写入根目录的 `closure-report.json`、`closure-report.md` 和 `closure-report.xml`。省略 Godot 参数也不能跳过真实 Godot 要求。显式 harness profile `population-runtime-closure` 使用本地台账目录与当前提交，不随 `all` 自动执行。

当前各项聚合分发与专用离线入口已写入；混合负载和多局仍须完成原始长测验收，不能据此宣布 T6 或整体通过。长恢复旧 `report.json` 不能代替带原始证据的 manifest。正确性目录可单独使用 `verify_population_runtime_correctness.py --verify-artifacts <目录> --require-fresh-commit <SHA>` 复验，不重新执行测试。

长恢复复验使用本轮 `evidence-<UTC>` 目录：

```powershell
python scripts/verification/verify_population_long_session_recovery.py --verify-artifacts 'D:/verification/recovery/evidence-<UTC>' --require-fresh-commit '<完整提交SHA>'
```

复验不打开 SQLite：从真实父进程收到 ready marker 的时刻重算启动耗时，比较 child 完整捕获状态与 fixture oracle，校验人口 state 内嵌摘要，再重算读取量、历史规模比率与缓存上限。它验证已捕获状态的等价，不冒称再次重放未随包携带的全部 authority 事件；完整存档 audit 仍独立进行。正式门槛保持1,000人、1,000/10,000 历史窗、8窗 tail、每档至少5次、p95≤15秒及比率≤1.5。失败和超时保留本轮原始日志；正常 SQLite 恢复导致数据库/WAL 字节变化不会被误判为事实变化。

广泛 harness 使用下列封存入口，实际调用原 `harness.py` 并保留原注册 profile、命令、尝试次数、退出码和新生成的报告。每次使用不存在的输出目录；它不会删除或借用既有绿色报告。

```powershell
python scripts/verification/verify_population_harness_evidence.py --profile change-lifecycle --output 'D:/verification/closure/change-lifecycle'
# 以下两条在准备验证 Godot 的机器执行，显式填写该机的引擎路径。
python scripts/verification/verify_population_harness_evidence.py --profile mainline-unified-runtime --godot-exe 'D:/tools/Godot_v4.6.3-stable_win64_console.exe' --output 'D:/verification/closure/mainline'
python scripts/verification/verify_population_harness_evidence.py --profile all --godot-exe 'D:/tools/Godot_v4.6.3-stable_win64_console.exe' --output 'D:/verification/closure/all'
python scripts/verification/verify_population_harness_evidence.py --profile all --verify-artifacts 'D:/verification/closure/all' --require-fresh-commit '<完整提交SHA>'
```

`mainline`/`all` 不会根据本机环境自动寻找引擎；必须显式提供 `--godot-exe`。最后一条仅离线复验。原始日志与本轮 JSON/XML/文本/图片保存在 `artifacts/`，不封存数据库、WAL 或密钥。manifest 同时记录实际读取的仓库文档/规则/场景摘要，另一机器需准备同一版本的输入，包括验证依赖的本地文档；复制证据后无需保留原机器绝对目录。广泛 harness 的通过不替代 T3 的100/1,000人真实渲染与帧时间证据，受控模型模式也不替代真实 provider 验收。

### Windows 实时进程 QoS

生产 ASGI parent 与原 owner 子进程在其生命周期内使用 Windows 原生 HighQoS：仅设置 `PROCESS_POWER_THROTTLING_EXECUTION_SPEED` 的 control bit 为 1、state bit 为 0。未更改 CPU affinity、进程 priority、机器电源计划或注册表；非 Windows 为 no-op，没有额外用户配置。同进程交叠生命周期共用计数，最后退出才恢复进入前的 speed 位；恢复前重新读取当前策略，保留其他调用方修改的非拥有位。原生设置或恢复失败仍报错，不视作成功退出。

service、mixed、transport cost、cold recovery、multi-game 和外机 Godot 性能生成器复用同一生命周期。长恢复 fixture 真实生成与冷恢复采样均启用；fixture manifest 的 `generation` 记录实际生成时长与策略。采集目录的 `collector-qos.json`、parent/owner 对应策略记录保留 before/applied/restored 读回值并纳原始文件摘要；多局共享生成器的最终恢复记录位于 group 的 `collector-qos.json`，matrix manifest 绑定其摘要。并发单局先退出时记录的 restored 可仍为空，必须结合最后 group 退出记录理解，不能据此前一局尚未恢复推断恢复失败。

QoS 只声明实时执行需求，不保证指定核、窗口耗时或性能通过。原 800ms 窗口、1500ms 事实、流量与退出门槛不变。正式证据仍须固定源版本、原始流量与实际资源记录；诊断对照不能替代完整矩阵。已有证据目录拒绝复用，拒绝时不得改写原 manifest 或策略记录。

原生依据：[SetProcessInformation](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-setprocessinformation) 和 [Windows Quality of Service](https://learn.microsoft.com/en-us/windows/win32/procthread/quality-of-service)。

### ASK 长历史格式与交接

ASK 恢复格式从 `recovery_version=1` 升为 `2`。首次打开旧库在同一事务内迁移当前 head、按原 ordinal 排列的 revision/conflict 和共享来源冻结前缀；失败回滚原数据与版本。升级前须通过既有 SQLite backup 流程保留完整备份。首次迁移仍需逐 entry 物化旧 JSON 大行，须预留内存与时间；已升级后的正常 reopen 只核 schema，不全扫历史。旧 binary 会拒绝版本 2，不支持直接降级写入。公共完整读取、主动感知和一致性审计仍有与历史规模相应的成本，不能把自动投影热写改善理解为所有 ASK 操作恒定成本。

长恢复 fixture 和证据 manifest 同步升级为 schema 2。交接时完整携带 fixture 的 `ask-char_a.jsonl`、`ask-char_b.jsonl`，以及每次恢复的 `result.owner-ask-char_a.jsonl`、`result.owner-ask-char_b.jsonl`；文件缺失或部分生成失败不能视作完整证据。它们保存全部有序来源、revision、conflict（包括已解决记录和合法重复值/ID），离线复验逐项验证并按原公共模型的规范化语义重新散列全部逻辑内容，再与两侧 oracle 比较，不能仅凭 owner 摘要通过。文件 hash 另外覆盖原始字节。旧 schema 1 证据不能混入本版正式验收。正常 ready 后才运行完整审计，原冷恢复时间、SQL 和 RSS 门槛不变。

本次 ASK 后端变更没有执行 Godot，仍为 `godot_unverified`；正式1,000人长历史、真实 provider 与外机 Godot 的完成状态以各自同提交原始门禁为准。

### 当前图候选索引升级

图库 schema 从 6 升为 7，在原迁移事务内建立 `graph_nodes_candidates`（scope、类型、节点 ID、revision）；6→7不重建其他投影，失败回滚版本与索引，正常 reopen 验证必要索引。升级前沿原 SQLite backup 流程保留完整备份；首次建索引需读取原节点数据，不能将其算作已升级库正常冷恢复成本。

有限 limit 的当前节点查询按类型取得有序候选，并以同 ID 原双时间条件排除更优 recorded/revision 版本；新类型、撤回与脱敏版本仍遮盖旧候选。多个类型去重后各取原前 K 再按原全局顺序合并，SQLite 参数或复合查询上限不适用时回退原查询。关系、显式历史和无界 limit 保留原路径，facade 权限/来源过滤位置不变。此优化减少已验证热查询的无关历史扫描，不承诺任意失效候选密度下均为 O(K)，也不改变任何正式性能或 Godot 验收门槛。
