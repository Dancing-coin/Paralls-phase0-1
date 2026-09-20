# 群体运行时补齐与外机 Godot 验证交接

当前整体状态：**进行中，Godot 未验证（godot_unverified）**。本文件不是六项验收通过声明。2026-09-19 用户要求先忽略 Godot 表现，继续其余缺口；当前仍只验收100／1,000人，保留万人参数。最新后端续作分支为 `codex/population-final-closure-20260920`，短路径工作树为 `D:/MyConfiguration/TCLXUSER/.codex/worktrees/pfc/Paralls-phase0-1`；不要将静态测试或合成证据测试记为引擎通过。

## 2026-09-20 持续 Goal 执行

用户已要求持续执行到完成，当前 Goal 为 active；实施补充见[最终执行计划](../superpowers/plans/2026-09-20-population-final-closure-implementation-plan.md)。在 `c23d879e` 基础上执行激活证据分离；下文旧的“等待答复”属于历史记录，已由本轮继续执行指令解除。

- 运行时回执仅保留原提交事件、revision 和 global_sequence_range，明确为 commit，replay_hash 为空；`audit_receipt` 显式按原提交截面计算原全历史 hash，不保留全局历史缓存。phase3a 验证入口显式调用审计。
- 缓存指标补充实际激活历史对象及最多32条的完成回执；混合和冷恢复复验器拒绝缺失指标。独立审查发现的内部序号损坏/重复event ID误判已增加反例检查，未改重放算法。
- 当前定向174项通过，短路径完整后端回归为6,909 passed／2 skipped（Godot），清理成功；Harness工具421项和phase3a显式审计profile通过。首次长路径完整回归因260字符文件无法读取失败，仅保留诊断。正式性能及总门禁仍待同版证据，不用后端测试代替。
- 新台账：`.superpowers/sdd/2026-09-20-population-final-closure-implementation-plan/progress.md`；本轮仓库外证据根为 `D:/HarnessEvidence/pop-final-20260920`。Godot 引擎未在本机执行，外机同版门禁仍欠缺。
- `9b74197f` 的两档120秒服务隔离及离线复验通过，千人窗口p95=84.8ms；真实模型short千人通过，100人因L3返回未声明的非法目标状态pending而失败。已将原目标模型JSON Schema加入L3提示词，131项回归和原失败请求的真实模型诊断通过；必须冻结修复后重采正式证据，旧版不混用。远端CI静态通过，harness/change-lifecycle及correctness失败的具体日志仍待取得；六项总体保持进行中。

## 2026-09-19 后端续作边界

2026-09-20 合并 main 后的四项审查修复及外机接续步骤见[main 审查修复交接](2026-09-20-main-review-fixes.md)。Godot 导入提前退出暂不处理；四项修复不构成六项总闭环或 Godot 运行通过。

2026-09-20 外机返回的all证据已核对，版本与本地不同；InteractionSession的共享存档/重复session复现与最小修复、外机重跑步骤见[外机all续作交接](2026-09-20-external-all-evidence-follow-up.md)。外机Siming通过不能代替人口表现或六项同版本总验收，修复后的Godot仍未验证。

- CI 已修复重复 job key、清理后上传旧路径和嵌套子任务覆盖报告。四个证据任务使用本次 job 的 `RUNNER_TEMP` 独立目录；只有对应 artifact 上传成功才清理该目录，上传失败保留原包。广泛验收包装器只接受新导出的 schema 2 报告与各次真实 attempt，旧 `runs/<id>` 归档不能替代。采集必须显式传入仓库外、尚不存在的 `--output`，拒绝时不先创建目录。
- 冷恢复相关109项、激活/认知恢复相关109项、混合启动相关23项定向回归通过；Harness工具完整回归396项通过。首次后端全套为6,861 passed／3 failed／2 skipped，其中两项为已知Godot绑定清单和外部资产工作副本断言；第三项暴露了下面的本地探针配置缺陷，修复后相关30项回归通过。最终提交后的完整回归、真实封存复验结果另记于本轮执行台账；这些结果没有证明小时级性能或远端 Actions/固定 runner 可用。
- `population_mixed_backend.configure` 已修复启动配置引用分裂：原先替换 `config.settings` 后，提前导入的模型模块仍持有旧对象，`local_probe` 可能调用本机真实模型。现在在既有fresh-process边界内统一更新原配置对象；本地探针与真实模型模式分别检查，真实模式的在线要求不能被旧引用绕过。
- 后续完整复验确认本地探针失败消失，但暴露已有SQLite首写竞争：两个独立store首次把DELETE库切换到WAL时，40次诊断有4次出现`database is locked`。现在新库/JSON迁移和旧库装配先准备WAL/FULL，原事务内版本检查及lazy连接保留；三类首次业务访问前WAL回归通过，修复后40次首写均为一次提交与一次版本冲突。恢复相关回归通过；读取计数只多一个WAL控制行，不增加历史扫描。这不证明旧长时I/O峰已解决。
- 正式正确性采集另外发现Windows嵌套自测路径过长：1,626项通过，14项门禁自测在隔离旧报告时失败。本轮已将pytest临时数据库移至独立系统短临时目录，退出由其拥有者回收；合成仓库自测也独立使用短目录，日志/XML仍保存在原run_scope证据包，未删除用例或放宽校验。失败包保留，须按最终提交重新采集。
- 短路径修复后的提交`837fed5f`已通过四个原正确性producer、1,640项focused回归及离线复验，Harness临时目录清理通过。其后服务采集还发现默认目录重复profile名和时间戳，使角色存档迁移临时文件超出Windows路径长度；现直接使用唯一attempt下的`service/`，不改变负载或阈值，相关22项测试通过。后续提交的正式证据以台账为准，不跨版本借用通过状态。
- 已定位激活回执的历史增长：`continue_replay` 虽只读新尾部，仍复制完整投影、事件ID并计算完整hash，`ProfileActivationAuthority` 还缓存全部重放结果。100人320秒诊断中单次回执最高228.63ms；本轮SQLite计时未捕获20ms以上的execute/commit，不能声称旧I/O尖峰已经解决。该诊断有插桩与并行源码变化，仅用于定位。
- 回执契约调整尚待用户决定，见[具体提案](../superpowers/specs/2026-09-19-activation-receipt-evidence-cost-design.md)。原计划要求保留完整 `replay_hash`；建议运行时改为明确的持久提交证据，完整hash留在显式审计。收到答复前不实施该调整，也不通过放宽阈值关闭长局门禁。
- 独立剩余工作仍包括最终版本的服务隔离、千人长历史恢复、传输五配对、真实模型短测/长测及2／4局容量。它们须使用同一实现版本的新证据；Godot及依赖引擎的mainline/all仍在外机验证。暂停Godot不等于六项整体通过。

本轮台账：`.superpowers/sdd/2026-09-16-population-production-runtime-closure-implementation-plan/backend-continuation-ledger.md`；本机诊断与审查记录位于 `D:/HarnessEvidence/pop-*-20260919*`。较长的 `population-backend-closure` 工作树已停用，仅为本轮未清理副本；不要在那里继续实现。原工作树及用户已有数据不得清理。

## 2026-09-20 后端收口续作

- 修正两项资源静态回归：绑定表校验候选、批准与拒绝状态及资格报告摘要；交付副本校验仓库内 active/archive 的来源隔离和 SHA256/LFS OID，不再硬编码另一台机器的美术仓库路径。真实二进制、外部 working-copy 和批准的 `char_c` 仍需独立证据；静态通过不改变资源资格。
- 独立审查补齐资格报告与包清单的摘要一致性，错误的 source/provenance 摘要均被拒绝。CI scope 元数据同步实际已配置的静态与运行入口，拒绝旧声明和 `release-verified` 夸大声明；`runtime_release_verified` 保持 false。
- Character 对话/L2/L3 真实 DeepSeek 预检与 Siming 真实后端链预检均通过，未使用 fallback；本轮两个 provider 的进程配置采用30秒超时。这只是模型前置可用性，不替代千人 mixed/soak。证据位于 `D:/HarnessEvidence/pop-character-live-preflight-20260920` 和 `D:/HarnessEvidence/pop-siming-live-preflight-20260920`。
- 已通过浏览器核对远端 main `0644996c` 的 [Actions run 35433821744](https://github.com/Dancing-coin/Paralls-phase0-1/actions/runs/35433821744)：实际报 `population-performance-fixed-runner is already defined`，没有执行 jobs。对应修复随 `07ace433` 及其前置提交推送到main；该版本的 [run 35459883293](https://github.com/Dancing-coin/Paralls-phase0-1/actions/runs/35459883293) 进一步暴露四个 job.env 不允许使用 runner.temp。依据 [GitHub context availability](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#context-availability)，改为各 job 的第一个步骤从 RUNNER_TEMP 初始化并写入 GITHUB_ENV，导出/上传/清理仍使用原唯一目录。新增四档实际PowerShell回归先4failed，修复后相关25项通过；actionlint 1.7.7在声明既有两条固定机器label后通过。
- SSH仓库访问正常；本轮没有可用的 Actions API 身份，匿名API限流，浏览器未登录。可以读取公开CI摘要，但固定 runner 的配置及手动dispatch仍无法由当前身份核实。
- `20df046f` 的 [run 35460310983](https://github.com/Dancing-coin/Paralls-phase0-1/actions/runs/35460310983) 已启动 jobs，静态门禁通过；两个 hosted runtime jobs 在安装 Python 时失败：GitHub `setup-python` 的 Windows 清单没有3.12.14。四个运行时入口改用固定SHA的 `setup-uv` v10.1.0与uv0.12.17，保留3.12.14及依赖约束，虚拟环境放在runner临时目录并激活。显式安装pip以支持已有外机依赖快照采集。相关19项测试和actionlint通过；修复后的远端结果须单独核对。
- 全后端回归 **6,871 passed、2 skipped**（原有两项引擎检查未执行），Harness 工具回归 **398 passed**；日志分别为 `D:/HarnessEvidence/pop-backend-closure-full-20260920.log` 与 `D:/HarnessEvidence/pop-harness-closure-full-20260920.log`。后端 pytest 本身通过，但外层 TemporaryDirectory 清理因 Windows 长路径失败，后续清理被自动审批拒绝；该包装命令退出1，不能记为清理通过。Harness 工具临时目录已回收。受影响本轮临时目录及两处CI测试目录在台账记录保留。
- 激活回执契约仍待答复。最终 recovery、transport、short、soak、capacity 须在该决定实施并冻结源码后按原阈值串行采集；本节不关闭六项总验收。

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

最新隔离工作树：`D:/MyConfiguration/TCLXUSER/.codex/worktrees/pfc/Paralls-phase0-1`。`D:/Paralls-phase0-1/.worktrees/population-runtime-closure`仅保留旧进度和可复用Python环境，不能用其中的旧报告替代本轮证据。

- 计划：`docs/superpowers/plans/2026-09-16-population-production-runtime-closure-implementation-plan.md`（按用户要求随代码提交）。
- 最新过程台账：`.superpowers/sdd/2026-09-16-population-production-runtime-closure-implementation-plan/backend-continuation-ledger.md`。
- 最新验收结果：由run_scope生成，使用`--export-evidence`显式导出至仓库外。本轮目录见文首；旧`.harness/verification/`不是当前证据入口。
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

### 完整面板记忆摘要索引

千人长历史造档发现，轻量角色每次结算生成面板摘要都重新折叠完整session历史。修复使用`character_session_memory_summary`派生索引，保留完整摘要、五类池顺序、同命题更新顺序和记忆修正；摘要文本的完整输出仍有与长度相应的成本。原完整记忆和审计接口保留，重量角色仍从图谱执行原scope/branch/valid-time过滤。

本变更将`recovery_version`从2升级为3（ASK内容格式仍为2）。沿既有SQLite backup流程保留升级前备份；首次升级按原事件顺序构建摘要索引，索引与版本同事务提交，失败回滚。正常追加将摘要、session event和current同事务提交；普通reopen不重新折叠历史，缺表拒绝启动。旧binary不支持版本3，不能直接降级写入。无持久库的兼容模式继续从既有内存时间线生成摘要。

本轮`de309bb3`的长历史运行在正式冷恢复采样前因该性能缺陷停止；其证据保留诊断，不算通过。修复后的完整backend、同版正式恢复和其它门禁须重新验收；Godot仍为外机未验证。
