# 远端 main 审查四项修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 修复 7ce40b6d 审查中的运动状态坐标、巡逻误判通过、Windows 子进程依赖优先级、Siming 异步降级四项问题。

**Architecture:** 保持 CharacterMotor 为位移唯一执行者，表现状态取碰撞后的实际速度；巡逻验收消费真实平面位移和目标方向。Python launcher 保留虚拟环境优先级；Siming 同步、continuation、durable accepted-plan 共用降级决策。

**Tech Stack:** Godot 4 GDScript、Python 3.12、pytest、现有 Harness。

**Spec:** 用户已批准执行上轮审查的四项修复。依据 `docs/superpowers/specs/2026-06-12-character-actor-control-and-locomotion-design.md`（正 Y 前进、Motor ownership）、`docs/superpowers/specs/current-project-intelligence-upgrade/2026-08-03-current-project-siming-durable-heavenly-graph-phase2-7-integration-design.md` 第 12–13 节（active 所有权与 no-action）。原始审查：`D:/HarnessEvidence/pop-merge-7ce40b6d-review-20260920.md`。

## Global Constraints

- 用户明确排除 Godot 导入提前退出：不修改 `scripts/verification/common.py` 或其导入参数测试。
- 本机不执行 Godot；所有 Godot 代码标记 `Godot 未验证`，提供外机可执行验证与接续说明。
- 不改变 backend Authority / Godot 表现边界，不加入新依赖、配置开关、兼容层。
- 保留 root `tmp/`、既有 `.harness/verification` 和其他会话产物；只清理本轮拥有内容。
- 在隔离工作树完成、集中提交后 cherry-pick 回 main；本轮不推送。
- 不扩展万人验收，不声称原六项大闭环完成。

## Review Focus

- 碰墙、静止、竖直坠落时不能把 desired velocity 当作实际平面运动；任务 2 的 Godot probe 覆盖实际速度投影和旋转朝向。
- NPC 目标方向与 local/world 转换一致；任务 2 修正同一运动调用链，任务 3 拒绝零位移、反向及缺角色证据。
- user-site 被关闭或有同名旧包时不能覆盖虚拟环境；任务 1 使用真实子进程 import 对照。
- Heavenly timeout/invalid/provider error/graph failure 在 active 所属事件族一律 no-action；任务 4 验证状态树不更新、无第二次 provider、回放幂等。
- shadow/off 与非图谱所属事件族不受图谱故障接管；任务 4 固定这些模式的原 legacy 行为。

## Task 1：Windows Python 子进程依赖

**Files:** `scripts/verification/population_python_process.py`、`backend/tests/test_population_python_process.py`。

**Interfaces:** 保持 `python_process(arguments, environment) -> (command, env)` 和 Windows base executable/PID 契约。

- [x] RED：临时 venv/user 两目录放同名模块，真实 child import 必须取 venv；禁用 user-site 时不得通过 PYTHONPATH 再注入。覆盖 caller env 不变、非 Windows 不变。
- [x] GREEN：按 caller PYTHONPATH、purelib、platlib 顺序构造路径；仅 `site.ENABLE_USER_SITE` 且子环境未设置 `PYTHONNOUSERSITE` 时追加 user-site。

```python
paths = [env.get('PYTHONPATH', '')]
paths.extend(sysconfig.get_path(name) for name in ('purelib', 'platlib'))
if not site.ENABLE_USER_SITE:
    env['PYTHONNOUSERSITE'] = '1'
if site.ENABLE_USER_SITE and not env.get('PYTHONNOUSERSITE'):
    paths.append(site.getusersitepackages())
```

- [x] 检查：`python -m pytest -v backend/tests/test_population_python_process.py`；预期真实 PID 和 FastAPI 路径保留，所有新增回归通过。

## Task 2：运动输入与实际状态的坐标统一

**Files:** `scripts/character/CharacterMotor.gd`、`scripts/character/CharacterReplica.gd`、`scripts/verification/CharacterMotorCoordinatesProbe.gd`、`backend/tests/test_character_locomotion_motor_ownership_guard_static.py`。

**Interfaces:** `apply_physics_command()` 的 `move_local_actual` 保持 Vector2；输入仍正 Y 前进，输出使用碰撞后速度在当前角色轴上的投影。

- [x] RED 静态防回归：禁止将 desired 世界 X/Z 写入本地状态；检查实际速度投影接线及 NPC lease 使用世界 X/Z。此检查不冒充 Godot 执行。
- [x] GREEN：`body.move_and_slide()` 后执行：

```gdscript
var actual_planar := Vector3(body.velocity.x, 0.0, body.velocity.z)
var move_local_actual := Vector2(actual_planar.dot(body.global_basis.x.normalized()), actual_planar.dot(-body.global_basis.z.normalized()))
```

- [x] NPC 保留 proposal 的 normalized local intent，仅 lease 改用 world direction 的 X/Z，避免 local 向量再被当作世界坐标。
- [x] 增加独立 Godot probe：0/90/180 度下前后左右、静止与竖直速度验证；实际 `apply_intent_frame` / `apply_physics_command` 调用，失败退出 1，成功打印结构化结果。不依赖外部角色资产。
- [x] 检查：对应 Python 静态测试通过；外机执行 `godot --headless --path . --script res://scripts/verification/CharacterMotorCoordinatesProbe.gd`，本轮记录为未执行。

## Task 3：巡逻验收以实际目标方向位移为准

**Files:** `scripts/phase0/MainDemoController.gd`、`scripts/character/CharacterReplica.gd`、`backend/app/verification_audit.py`、`backend/tests/test_verification_audit.py`、`scripts/verification/tests/test_phase0_correlated_ack_contract.py`。

**Interfaces:** 在 `npc_patrol_probe` 日志加入 `target_alignment`，`distance` 改为平面位移。保留现有 result ID；Motor fallback 只接受 char_a/char_b 都有合格测量。

- [x] RED：marker 单独存在、distance=0、反向/横向、缺任一角色、不完整/非法字段均不得 proved；两个角色都 distance>0.01 且 target_alignment>0.5 才 proved。
- [x] GREEN：probe 不再以 marker 到达为完成条件；为每个 actor 记录起点/初始目标方向，逐物理帧检查平面位移和方向，达到条件即冻结该角色并记录一次测量，超时记录失败测量。

```gdscript
var displacement := actor.global_position - start_position
displacement.y = 0.0
var distance := displacement.length()
var alignment := displacement.normalized().dot(target_direction) if distance > 0.001 else -1.0
```

- [x] marker 仅在碰撞后平面位移与本帧目标方向一致时发出；移除被测 probe 的全局 marker 等待状态与信号回调。
- [x] parser 逐行绑定 actor/distance/alignment，只有同一行合格才计入角色集合，不拼接不同记录；两角色齐全才通过，旧 root-motion 独立证据路径保留。
- [x] 检查：`python -m pytest -v backend/tests/test_verification_audit.py scripts/verification/tests/test_phase0_correlated_ack_contract.py`。外机另跑 `--profile phase0`，保留本轮实际日志。

## Task 4：Siming 同步与异步统一降级

**Files:** `backend/app/services/siming_runtime.py`、`backend/tests/test_siming_continuation.py`、`backend/tests/test_siming_heavenly_runtime_composition.py`。

**Interfaces:** `_after_heavenly(frame, effects)` 为唯一降级点；保留 staged effects、audit、snapshot、receipt replay 边界，不在 plan 中写 Authority。

- [x] RED：将旧“超时后 candidate”回归改为 completed/no_action，保留 error category 与重复 receipt 断言；增加 durable `plan_accepted` 无 state_tree/narrative 更新、无下一 provider request 的断言。
- [x] RED：active 所属事件族 graph failure 走 `plan_initial` 仍 no_action；shadow/off 与非所属族继续 legacy，防止简单删除 synchronous 条件误伤其它模式。
- [x] GREEN：只对 `prepared.mode == 'active'` 且 `event_family in GRAPH_OWNED_EVENT_FAMILIES` 的 degraded decision 生成原有 no_action；取消同步限定。

```python
if (prepared is not None and prepared.mode == 'active'
        and prepared.event_family in self._heavenly_support.GRAPH_OWNED_EVENT_FAMILIES
        and prepared.degraded_reason):
    # 复用现有 no_action、审计和 observatory 分支。
```

- [x] 检查：`python -m pytest -v backend/tests/test_siming_continuation.py backend/tests/test_siming_heavenly_runtime_composition.py`，再运行全部 Siming 相关回归。

## Task 5：集成、交接与集中提交

- [x] 全量 `python -m pytest -v backend/tests`、Harness 工具测试、`--suite contract`；报告保存在仓库外，失败先诊断，不用历史报告抵消。
- [x] 按用户约定不执行 Godot 或依赖它的 all；在结果表明确 Godot/all 未验证，并提供外机命令。
- [x] 一次独立审查四项完整 diff，修复重要发现；检查 `git diff --check`、`.harness` 实际内容以及 `common.py` 与基线完全一致。
- [x] 将计划各步骤更新为实际状态，记录测试数量/证据路径、Godot 未验证和排除项。
- [x] 一个中文提交包含本轮源码、测试和计划，cherry-pick 回 root main，检查原有 `tmp/` 保留；不推送。

## 执行记录

- 基线：7ce40b6d；上轮后端 6877 passed / 2 skipped / 1 临时目录 teardown error，报错文件单独复跑 16 passed。直接复用已核验基线，不重复整轮基线测试。
- 工作树：`D:/MyConfiguration/TCLXUSER/.codex/worktrees/main-review-fixes/Paralls-phase0-1`。
- Ruling：用户已明确“生成修复计划 开始执行”，不再为计划签核中断；本计划落盘后直接执行。
- Ruling：Godot 由其他机器验证，all 包含 Godot，因此本轮全量 Python + contract，Godot/all 保持未验证。

- Task 1–4：实现与本机定向检查完成。201 项通过；launcher 增加父进程禁用状态继承后 5 项通过。Godot probe 已交付，尚未运行。
- 独立审查：发现巡逻阈值与三位小数输出不一致；先将 distance/alignment 格式化，再按同一文本值决定停止采样，相关 95 项检查 RED→GREEN。
- Ruling：保留原 root-motion 独立证据路径；本轮收紧的是新增 Motor fallback，不扩展斜坡/移动平台语义。
- Harness 工具 421 项通过；初轮 contract 五项通过，精度与交接文档更新后重新执行 contract。


## 本轮最终验证结果

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 全量后端 | 6901 passed、2 skipped，退出 0；临时目录清理通过 | `D:/HarnessEvidence/main-review-fixes-backend-20260920.log` / 同名 `.xml` |
| Harness 工具最终全套 | 421 passed，退出 0；临时目录清理通过 | `D:/HarnessEvidence/main-review-fixes-tools-final-20260920.log` |
| 精度边界修正相关检查 | 95 passed，退出 0 | `D:/HarnessEvidence/main-review-fixes-rounding-20260920.log` |
| contract | 五项通过，退出 0、cleanup passed | `D:/HarnessEvidence/main-review-fixes-contract-commit-ready-20260920` |
| Godot / all | 未执行，Godot 未验证 | 外机步骤见 `docs/verification/2026-09-20-main-review-fixes.md` |

实现与本机验证完成；checkbox 表示本轮约定的实施工作完成，不表示外机 Godot 或原六项总门禁通过。测试过程最后仅调整巡逻日志精度和交接文档，相关静态检查另跑 95 项、Harness 全套另跑 421 项覆盖最终版本。四项运行时 Python 修复在全量后端运行期间未再变动。

独立审查只发现一项重要问题（巡逻日志舍入导致假阴性），已修复；其余三条调用链未发现重要新问题。未修改 Godot import 参数，不新增真实 provider 成功声明。交付采用单个中文提交及 cherry-pick，不执行 push。
