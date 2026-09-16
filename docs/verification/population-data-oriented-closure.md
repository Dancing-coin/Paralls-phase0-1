# 群体数据导向优化：缺陷补齐与续验交接

日期：2026-09-16。实现起点：`0554517b5d650a3e2bf1d1772ec1eedd08c43d43`。

**Godot 状态：`godot_unverified`。** 后端结果不代表场景、帧时间、音频或可见变化已经验证。本轮从 PATH 与项目默认位置未找到可用 Godot；没有提交未经验证的 MultiMesh/LOD 场景改动。

## 本轮修复与边界

| 阶段 | 修复内容 | 验证入口 |
| --- | --- | --- |
| 1：增量持久化 | Session 追加作为提交锚点；派生内存/图谱失败可恢复；损坏日志尾截断、重复事件冲突拒绝；同角色快照刷新串行；Gameplay 使用 SQLite 增量事务，避免每窗重写历史；失败撤销本批内存索引 | `population-data-oriented-persistence` |
| 2：增量读取 | 正式授权 publisher 读取 checkpoint + 原始 tail；先检查全局序号再按可见性过滤；来源撤销、版本/作用域/摘要冲突拒绝；checkpoint 随 store 重开恢复 | `population-data-oriented-incremental-read` |
| 3：连续推进 | 仿真时间与 source revision 分离；B0 纯积分输出客观增量和展示种子，不调用 Owner/Core/LLM；B1/B2 独立预算；持久 cadence + outbox 恢复；规则漂移拒绝恢复 | `population-continuous-runtime` |
| 4：热状态与批次 | 生产 world 接入热字段；版本和槽位代次校验；跨时段积分与到期集合；Owner 多流单次原子提交，逐项幂等/冲突/重排队；串并行结果等价 | `population-hot-state-equivalence`、Owner 批次测试 |
| 5：实测门禁 | 正式 100/1,000/10,000 人、各 30 窗口的 1× 与 10×；真实 SQLite、Siming、行为审计、Owner 和重启校验；按纯 kernel 占比决定原生/GPU 准入 | `population-runtime-scale`、`population-native-gpu-gate` |

热表仍是 `list[dict]` 基线接口，并非 SoA。默认串行执行；线程并行只保留显式入口和等价性验证。B0 常驻状态不是 Character Core 私有记忆，展示种子不是领域事实。

## 持久化与重启

应用启动从 `PARALLS_HEAVENLY_GRAPH_PATH` 所指定文件的同目录恢复 Gameplay store，文件名为 `<graph 文件名>.gameplay.json`。为保持已有部署路径，扩展名保留；内容采用 SQLite。首次打开旧 JSON 快照时，先完整验证，在同目录构造数据库后原子替换；失败保留旧文件。显式 `save_snapshot(other_path)` 仍导出 JSON，禁止导出覆盖正在使用的数据库。

同批重复事件或 outbox ID 在写入前拒绝。Durable 写入的校验、内存提交、SQLite 事务和失败撤销共用存储实例锁，读取也取得该锁，避免并发失败撤销另一批已确认事件或泄漏未提交事实。角色 graph 刷新使用每角色锁覆盖快照捕获与 checkpoint/current 提交，避免较旧游标晚于新状态写回。Session 迁移临时文件使用同目录短名，避免 Windows 深目录下额外拼接长文件名失败。

`population-cadence:<world_ref>` 流记录紧凑窗口、固定名单摘要、规则和投影摘要，outbox 记录交付结果。万人 B0 数组由已确认窗口重新计算，不逐窗落入该事实流。进程在追加后退出时，重开重投 pending；已交付窗口只重建热表。恢复先比较完整投影摘要，规则改变不能静默篡改既有状态。

同一存档重启要求名单、world mode、规则一致。修改居民名单不等于迁移存档；不一致返回 `population_roster_mismatch`。不得删除旧存档来绕过冲突，应使用新存档路径开始新局或另行设计显式迁移。

内存 bus 的历史限制仅影响常驻展示事件保留，不承担跨进程事实恢复。持久 store、Owner 幂等与行为审计仍是相应事实的恢复依据。

## 验收口径

规模测量的每个窗口推进 **1 秒仿真时间**：1× 墙钟预算 1 秒、10× 墙钟预算 0.1 秒。每档连续 30 窗口，包含生产同构 B0 publisher、Siming pipeline、SQLite 图谱/行为审计、稀疏 Owner 批次和重启结果核对；provider 禁用，不把远端 LLM 延迟混入 B0 容量。

1× 必须三档全部满足 p95 ≤ 80% 墙钟预算、backlog 不持续增长、最大推进延迟 ≤ 1 窗口。10× 完整执行并独立报告，失败不伪装成通过，也不反向否定已经通过的 1×。只有 **1× 失败且纯计算 kernel 占比 ≥ 60%** 才允许升级原生/SoA/GPU；协议、复制或持久化热点应先修复。

正式规模矩阵于 2026-09-16 通过，Harness run：`run-20260916-132337-944214`。每格均为真实连续 30 窗口，provider 关闭；以下为本机测量结果：

| 倍速 | 人口 | p50 / p95（ms） | 最大延迟（窗口） | backlog | 性能门槛 |
| --- | ---: | ---: | ---: | --- | --- |
| 1× | 100 | 16.20 / 32.72 | 0 | 不增长 | 通过 |
| 1× | 1,000 | 65.04 / 87.65 | 0 | 不增长 | 通过 |
| 1× | 10,000 | 726.30 / 758.45 | 0 | 不增长 | 通过 |
| 10× | 100 | 16.11 / 20.64 | 0 | 不增长 | 通过 |
| 10× | 1,000 | 66.45 / 89.31 | 0 | 不增长 | 未通过：p95 超过 80ms |
| 10× | 10,000 | 716.95 / 766.74 | 185 | 增长 | 未通过 |

运行环境为 Windows 11 build 26100、Python 3.12.14、Intel64 Family 6 Model 183。源码指纹为 `sha256:132cce46038c0999817614424278857187bd97dd39f20ec5b3d71ff13d6bd571`；指纹覆盖 `backend/app/` 与 `scripts/verification/` 下的 Python 文件，按文本规范化换行，可核对 cherry-pick 后相同实现。三档 1× 全部通过，10× 保持独立压测结论；native/GPU gate 的验收通过，决策为 `continue_python`、原生/GPU 准入为 false，纯积分占总耗时约 4.87%。

万人 1× 的 30 窗口内部事件 JSON 编码总量为 238,769,421 字节（约 7.59 MiB/窗口），Gameplay SQLite 文件为 241,664 字节，图谱及其日志约 3.74 MiB；实际 Godot 网络流量待联调测量。测量进程的峰值 RSS 最大约 292.5 MiB，属于整套顺序矩阵的累计峰值。六个场景均验证串并行等价、角色注册、B0 游标、30 次行为审计、Owner 批次、持久化及重启 hash 一致；每个窗口另有五类标识、名单摘要及规则版本证据。

万人 30 窗口的重启重建约 8.76 秒，单独计量，不纳入稳定窗口处理 p95。当前热状态从已交付 cadence 前缀重建，恢复成本随已确认窗口数增加；本轮容量证据覆盖 30 窗口，不代表任意长存档的恢复时限。生产 `main` 当前使用 86,400 秒窗口；本次以 1 秒窗口验证更密集的 B0 负载。

本轮保留了失败复跑：`run-20260916-130712-550031` 的万人 1× p95 为 1,204.40ms，`_write_delta` 整段耗时出现最高 528ms 尖峰；后续细分连接、DML、提交和关闭的探针未复现，不能断言是 SQLite journal 缺陷。未修改数据库同步级别、未禁用 GC、未放宽门槛。失败原始报告保存在 `population-closure/scale-io-tail-failure.json`。

最终实现删除了读集合中逐值 Python JSON 等价扫描，复用既有批量序列化器；新窗口计算前释放确已有确认 receipt 的旧预览，避免两窗万人对象同时存活。摘要差分测试保留特殊类型、Unicode 和排序语义；失败重试仍保留未确认预览。上表来自这两项修正之后的完整矩阵，本机性能不能保证其他机器或任意 I/O 干扰下仍满足同一门槛。

阶段一正式 profile 已通过：100/1,000/10,000 图节点各更新 30 次，每批 undo 为 1 项、SQL 变更为 3 行，无全图快照或 DELETE；重开分别可见 130/1,030/10,030 个节点版本。Session 单条追加为 274/278/282 字节，current 最大约 19.5 KB。全量 checkpoint 仍是低频开销：一万条历史约 2.2 MB，未将其描述为常数成本。恢复后的角色 revision 均为 30。

阶段二正式 profile 中，历史从 1,000 增至 50,000、人口固定 100 时，每个窗口实际只读取 10 条 tail 和 1 条授权来源事件；增量输出摘要与全量 oracle 一致。热状态等价 profile 比较了 54/100/1,000/10,000 人的原始布局、串行及线程批次，状态、候选、Owner 输入与回放摘要一致。

## 最终验证记录

- 后端全量：`5327 passed, 7 warnings`，80.78 秒。包含 SQLite 事务失败/并发读写、会话迁移、checkpoint/current 恢复、同角色并发快照、Owner 原子批次、事件数值类型冲突和消费者隔离。
- 持久化、增量读取、连续运行、热状态等价四个 Harness profile 全部通过；run 分别为 `run-20260916-132707-662424`、`run-20260916-132723-822186`、`run-20260916-132732-299881`、`run-20260916-132743-215987`。
- 规模矩阵与 native/GPU 判定通过，最终源码指纹和三档结果见上表。低频重复事件用 canonical JSON 判定相同输入，区分 `1`、`true`、`1.0`，新事件路径不增加摘要计算。
- 全仓 `--profile all`：`docs`、`boundaries`、`drift`、`backend-contract`、`godot-project` 五个静态 profile 通过；在 `character-agent-execution` 因缺 Godot 停止，`overall_harness_passed=false`。run：`run-20260916-132749-098814`。
- Godot 表现脚本返回 `godot_unverified`，CPU/GPU 帧时间、真实消息到场景可见效果、近远景 LOD 仍没有运行证据。

原始 JSON 报告位于 `.harness/verification/population-*-report.json`；本轮命令日志及全仓失败原因保存在 `.harness/verification/population-closure/`。集成后复制到主工作区同路径，后续任务可直接读取。

## 复验命令

在仓库根目录，使用安装了项目依赖的 Python：

```powershell
$env:PYTHONPATH=(Get-Location).Path + ';' + (Join-Path (Get-Location).Path 'backend')
$env:PARALLS_HEAVENLY_GRAPH_PATH=':memory:'
python -m pytest -q backend/tests --basetemp .harness/verification/p
python scripts/verification/harness.py --profile population-data-oriented-persistence
python scripts/verification/harness.py --profile population-data-oriented-incremental-read
python scripts/verification/harness.py --profile population-continuous-runtime
python scripts/verification/harness.py --profile population-hot-state-equivalence
python scripts/verification/harness.py --profile population-runtime-scale
python scripts/verification/verify_population_native_gpu_gate.py --scale-report .harness/verification/population-runtime-scale-report.json
python scripts/verification/harness.py --profile all
git diff --check
```

正式计时期间不要并发运行 pytest、其他 benchmark 或构建。规模和 native gate 报告必须来自同一实现；改代码后不能复用旧性能证据。`.harness/verification/` 是本地原始证据目录，不纳入版本控制；本文件保留可跨工作树/任务读取的结论与复验入口。

## Godot 继续验证

当前尝试过 PATH、`D:/godot/Godot_v4.6.3-stable_win64.exe` 和既有 `E:/下载/...` 默认位置，均无可用引擎。全仓 Harness 在静态门禁之后因缺 Godot 停止，这不等于全仓通过。

获得可用 Godot 后执行：

```powershell
python scripts/verification/verify_population_presentation_lod.py --godot-exe <实际 Godot 路径>
python scripts/verification/harness.py --profile all
```

该脚本只记录编辑器导入及待验证项，**不会把导入成功提升为表现完成**。后续任务仍须证明真实后端展示消息进入场景并产生可见变化，记录近景/远景/不可见数量、CPU/GPU 帧时间、网络和资源加载成本，并检查三组切换不改变 Owner receipt、actor revision 或 replay hash。只有重复远景实例确为热点时才实施 MultiMesh，并验证整组可见性限制。
