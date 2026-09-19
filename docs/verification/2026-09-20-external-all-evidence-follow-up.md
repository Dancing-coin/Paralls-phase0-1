# 2026-09-20 外机 all 证据核对与 InteractionSession 修复交接

状态：外机原 `all` 失败；本轮修复只完成后端复现和回归，**修复后的 Godot runtime 未验证**。不关闭群体模拟六项总验收，不改变待确认的激活回执契约。

## 原始证据与源码身份

- 用户提供：`D:/HarnessEvidence/paralls-current-all.zip`，SHA256 `b9716a055e8c5d91b262a5827c1dcf572897ff3d06c0111085902684ddb07137`。只读核对，未改包内报告或执行其中的脚本。
- 最终运行目录：包内 `paralls-current-all-after-import/`；run_id `a5347573033741f1a52d696aee3a2870`。
- 外机 revision：`83fa2b339c95e30ca3a96af0133adc4d37f129f7+dirty:cade5df45804b31b8473d76fa134682daab8aad11407be9d4886ad7aac8abb0a`。
- schema 2 汇总与manifest一致：52 passed、1 failed、0 blocked、25未执行，cleanup passed。53个profile-result的身份/状态和39份已引用报告的SHA256均与汇总一致。这是包内一致性核对，不是用本地源码复验全部运行结果。
- 本地修复基线：隔离分支`codex/population-backend-closure`的`c9e7aeacac255dc45f60af930bec262228ee69c0`，工作树`D:/MyConfiguration/TCLXUSER/.codex/worktrees/pop/Paralls-phase0-1`。根main仍为`0644996c`，不可把外机dirty版本等同于本地版本。

包内最终all的Siming为17/17 proved，provider为`deepseek_chat`、model为`deepseek-flash`，本次latency为**14,816ms**。用户另外提供的`paralls-current-siming-30`运行是**17,256ms**；独立目录不在zip中，不能将两个延迟混作同一条证据。30秒provider实例配置和Python3.13.9属于外机记录；本地回归使用Python3.12.14。

## 已复现的失败链

1. `harness-embodied-task`先调用`verify_embodied_interaction_session.py`，包内该profile确有成功的Godot JSON，live_backend收到4条事件并到达realizing。
2. 同一all稍后再直接执行`embodied-interaction-session`。两个调用都使用固定的`session:handshake:godot-websocket`，原runner虽要求新backend进程，却继承相同`PARALLS_HEAVENLY_GRAPH_PATH`，复用本轮权威存档。
3. 用原Uvicorn/owner进程、真实WebSocket两次启动本地复现：首次得到ACK和proposed/accepted/authorized/realizing四条事件；重启后第二次只有ACK。幂等的已提交事务不重新发布新事件，Godot新consumer等不到本次事件。
4. 原runner同时使用`--quit-after 120`。该参数按迭代次数退出，不能充当120秒期限；探针还在5秒接收等待中时，进程可能先退出0，因而没有运行报告。官方语义见[Godot命令行参考](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html)。没有本地引擎复跑，不能把提前退出的具体时间说成已实测。

诊断日志：`D:/HarnessEvidence/interaction-session-duplicate-diagnostic-20260920.log`；同名前缀目录保留本轮后端原始日志。没有借用较早profile的成功JSON补齐后面的失败报告。

## 最小修复与验证边界

- 仅修改`verify_embodied_interaction_session.py`的采集生命周期：每次调用使用独立系统短临时目录中的存档；先停止本次拥有的backend及其子进程，再回收存档。日志与报告继续进入原run_scope，其他profile的存档不动。
- 移除按帧/迭代数退出，保留GDScript原3秒连接与5秒接收期限；runner使用30秒真实时间兜底。成功仍要求真实运行JSON、正确状态、路由与live_backend accepted，缺报告不能通过。
- 新回归`backend/tests/test_embodied_interaction_session_runner.py`在同一run内按原两profile顺序运行两次，用真实Uvicorn、owner进程和WebSocket检查各自收到完整会话事件；同时检查独立存档已清理，以及父级Harness上下文不被覆盖。
- 回归中Python客户端代替Godot，合成前端报告只用于检查runner流程，**不能当作Godot证据**。生产session ID、幂等键、事件总线和slot consumer未改。
- 两个新增回归先失败；补齐清理/父上下文检查后，InteractionSession、Harness任务、进程所有权和run_scope相关回归最终**37项通过**，27.09秒。独立审查无重要问题，`git diff --check`通过。原始日志/XML见`D:/HarnessEvidence/interaction-session-fix-regression-20260920`，本轮临时目录已回收。

## 外机接续步骤

在包含此修复的同一源码版本上执行。保留外机30秒provider配置和已导入的原Godot工程，输出目录每次使用新名字：

```powershell
python scripts/verification/harness.py --profile embodied-interaction-session --godot-exe 'D:/godot/Godot_v4.6.3-stable_win64_console.exe' --export-evidence 'D:/HarnessEvidence/interaction-session-fixed-001'
python scripts/verification/harness.py --profile all --godot-exe 'D:/godot/Godot_v4.6.3-stable_win64_console.exe' --export-evidence 'D:/HarnessEvidence/paralls-all-fixed-001'
```

先核对独立profile本次attempt确有Godot runtime JSON、`live_backend.received_event_count >= 4`、`consumer_state=realizing`、`accepted=true`及完整退出；再运行all，以覆盖同轮先后两次调用。任一非零、缺报告、身份变化或未执行仍如实保留。后续fail-fast缺项应依据下一次实际结果处理，不预先标通过。

Archive Door仍缺获批准的`char_c`绑定及`right_upper_arm → right_forearm → right_hand`骨链；不可使用rejected的`external_character_b`或其他角色冒充批准。VLA真实凭据仍按用户外机记录为readiness blocked。二者与本次验证器隔离修复分开；本轮不修改绑定、密钥、promotion或effectiveness结论。
