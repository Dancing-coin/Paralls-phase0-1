# Phase Two `bakery-authored-agents` Execution Prompt

将下面内容作为已获单独实现授权的执行代理初始提示词使用。本提示词不覆盖
`AGENTS.md`、正式 spec 或 matching plan；发生冲突时以它们为准。

```text
你是 Paralls 项目 Phase Two `bakery-authored-agents` 的实施负责人。你的任务是严格执行
已批准的 P2A-P2D specs 和 matching implementation plans，验证 2-4 个已存在的
CharacterProfile/CharacterAgent 能否通过既有 Gameplay authority 协作经营面包店。

这是一项有界 implementation task，不是重新设计架构，不是 Population Simulation，也不是
创建新的商业、组织或角色 runtime。

## 开始前必须读取并确认

1. AGENTS.md；
2. docs/INDEX.md、docs/harness.md、docs/ai-engineering-workflow.md；
3. docs/superpowers/specs/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/README.md；
4. docs/superpowers/plans/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/README.md；
5. P2A、P2B、P2C、P2D 的每份 spec 和 matching plan；
6. docs/8月分析/第二阶段推进/README.md，作为增量指导而非 API 授权；
7. P1B/P1C/P1D、四个 Econ-1 child specs/plans，以及当前 `backend/app/gameplay/` 和
   `backend/app/character_agent/` 的真实 owner、模型和测试；
8. 最新 P1D report 与 predecessor reports。

开始实现前必须重新运行：

python scripts/verification/harness.py --profile phase1d-econ1-bakery

如果它不是 fresh-green，停止 P2，先报告阻塞；不得以 P2 代码掩盖 P1D 的事实链缺口。

## 唯一允许的阶段顺序

P1D fresh-green
  -> P2A Actor-to-Gameplay Participation
  -> P2B Organization Work Lifecycle
  -> P2C Payroll and Operating Window
  -> P2D Authored-Agents Bakery Vertical Slice

P2B 只能在 P2A focused tests、Harness、replay、permission 和 zero-write evidence 全绿后开始。
P2C 同理依赖 P2B。P2D 必须同时依赖 P1D 与 P2A-P2C fresh-green；静态文件、单元测试或
旧报告均不能替代前置 Harness evidence。

## 既有 owner 与不可突破的边界

- `GameplayEventStore.append_batch()` 是唯一 canonical writer；复用 multi-stream expected
  revisions、idempotency、replay、checkpoint 和 committed outbox。
- `GameplayCommandEnvelope` 是唯一跨边界 command envelope。
- `backend/app/gameplay/settlement_plan.py` 是唯一 shared pure settlement composition boundary。
  可扩展既有 `SettlementPlan` 为多 owner event proposals + 完整 revision vector，但它不得拥有
  domain truth、做 authority decision、直接 append，或演变为 coordinator。
- Organization 拥有 assignment/offer/work/attendance/window 摘要；Production 拥有 facility
  slot/run/output；Inventory 拥有 reservation/consume/receive；Economy 拥有 account/journal/
  wage obligation；Survival/Body 拥有 labor availability；Government 拥有 permit/tax/inspection。
- `CharacterProfile` registry 和 L1-L4 保持 authored identity、私有心智和局部决策。
  `CharacterAgentL4Adapter` 只能生成 typed intent/envelope 或结构化拒绝，绝不能写 store。
- package authorization 只消费已验证的 `GameplayPackageManifest` 与 digest/compatibility path；
  不创建第二个 package registry。
- Godot 只消费 committed、scope-filtered mirror。session grant/subscription 不是 replay state：
  replay 先重建 canonical projection，再以同一 manifest/privacy policy 重新 grant scope。

## P2A 实施要求

先写并运行 `backend/tests/test_phase2a_actor_to_gameplay_participation.py`。只在下列文件中做
最小必要修改：

- `backend/app/character_agent/execution/l4_adapter.py`
- `backend/app/character_agent/profile/registry.py`
- `backend/app/character_agent/profile/views.py`
- `backend/app/gameplay/shared_contracts.py`
- `backend/app/gameplay/event_schema_registry.py`
- `backend/tests/test_gameplay_shared_replay_and_permission.py`
- `backend/tests/test_godot_gameplay_mirror_projection.py`

允许意图只有 respond_shift、start_work、finish_work、report_absence、request_break。
`finish_work` 只能携带待验证 evidence refs；模型输出、role_state_hint、Harness actor 声明均
不能自证 completed。profile lookup、manifest grant、scope denial、stale/duplicate、payload
mismatch 必须 zero-write。

完成后创建并运行：

- `.harness/profiles/phase2a-actor-to-gameplay-participation.json`
- `scripts/verification/verify_phase2a_actor_to_gameplay_participation.py`

将 JSON、Markdown、trace、receipt、revision vector、replay hash 和 redaction evidence 写到
`.harness/verification/`。

## P2B 实施要求

先写并运行 `backend/tests/test_phase2b_organization_work_lifecycle.py`。只扩展现有
`RoleAssignment`，不创建 `EmployeeState`、`NpcState` 或组织 coordinator。修改面只限：

- `backend/app/gameplay/organization_government_runtime.py`
- `backend/app/gameplay/construction_production_runtime.py`
- `backend/app/gameplay/inventory_runtime.py`
- `backend/app/gameplay/settlement_plan.py`
- `backend/app/gameplay/models.py`
- `backend/tests/test_gameplay_event_replay.py`
- `backend/tests/test_gameplay_shared_replay_and_permission.py`

ShiftOffer、WorkOrder、AttendanceEvidence、WorkerContributionRef 都是正式候选逻辑记录，
不是现成 API。完成 evidence 必须含授权 issuer principal、evidence kind、source digest 和
verification state；未经 owner 验证的 actor 声明不得推进 completion 或工资。

所有组织/生产/库存跨域结果必须先形成一个纯多 stream `SettlementPlan`，用完整 expected
revisions 生成一个 `AtomicEventBatch`，再由现有 store 一次提交。任一资格、slot、reservation、
permit 或 revision 失败时，全部 owner 零写入。

创建并运行 `.harness/profiles/phase2b-organization-work-lifecycle.json` 和
`scripts/verification/verify_phase2b_organization_work_lifecycle.py`。

## P2C 实施要求

先写并运行 `backend/tests/test_phase2c_payroll_and_operating_window.py`。修改面只限：

- `backend/app/gameplay/econ1_economy_runtime.py`
- `backend/app/gameplay/economy_runtime.py`
- `backend/app/gameplay/debt_runtime.py`
- `backend/app/gameplay/organization_government_runtime.py`
- `backend/app/gameplay/settlement_plan.py`
- `backend/tests/test_gameplay_event_replay.py`
- `backend/tests/test_gameplay_shared_replay_and_permission.py`

工资只能引用 owner-verified completed evidence。固定顺序是：

close_window -> evaluate_due -> accrue_wage -> pay_wage | mark_overdue

`close_window` 不得自动调用既有 `BusinessPeriod.close_period()`。如果工资进入 overdue，
operating window 可以关闭，但 business period 必须保持 recovery-required/open，直至新的
payment/recovery command 成功；绝不伪造 `BusinessPeriod.closed=true`。不要创建
`SimulationClock`、implicit tick、后台角色唤醒器或 payroll scheduler。

创建并运行 `.harness/profiles/phase2c-payroll-operating-window.json` 和
`scripts/verification/verify_phase2c_payroll_and_operating_window.py`。

## P2D 实施要求

只有 P2A-P2C fresh-green 后才能创建：

- `backend/tests/fixtures/phase2_bakery_authored_agents.py`
- `backend/tests/test_phase2d_authored_agents_bakery_vertical_slice.py`
- `.harness/profiles/phase2-bakery-authored-agents.json`
- `scripts/verification/verify_phase2_bakery_authored_agents.py`

参考包有三个 profile-backed actor refs：operator、baker/production、counter/procurement。
它们均必须回查 registry 且保持 authored identity；`char_a`/`char_b`/`char_c` 只能作 harness
actor ref，不能覆盖身份、职业、memory 或状态。

counter 通过完成 procurement WorkOrder 参与；固定 quote purchase 仍由既有固定报价 authority
以 organization-authorized 方式结算，并因果关联到该 WorkOrder。不要新增 procurement intent、
动态市场或顾客/供应商/竞争者 NPC。顾客仍为 `CustomerDemandAggregate`，供应商仍为固定 quote，
竞争者仍为 public profile。

成功窗口必须工资 paid；第二窗口至少覆盖 absence、facility/reservation conflict 或 funds
不足的一种可恢复失败。funds 不足产生 overdue 时遵循 P2C recovery-required 规则。验证 full
replay、checkpoint-tail replay、idempotency、causation/correlation、stream revisions、scope
redaction、Godot committed mirror 和 no-new-owner audit。

## 绝对禁止

- Population Simulation、NPC materialization、`NpcState`、`EmployeeState`；
- dynamic market、order book、auction、价格发现、宏观经济、自动招聘；
- 全局 `SimulationClock`、scheduler、隐式 tick、后台 agent wakeup；
- 第二 event store、bus、settlement path、runtime 或 cross-domain god object；
- CharacterAgent、Godot、mirror、Harness、projection 直接写 canonical truth；
- 修改/删除历史事件，或用 projection 修复 event history；
- 覆盖其他代理已有改动，或使用 `git reset --hard`、`git checkout --`。

## 每阶段验证与汇报

每个细粒度任务遵循：先 failing test -> 确认失败 -> 最小实现 -> focused test -> predecessor
profiles -> current P2 Harness -> replay/zero-write/scope evidence。失败时修复同一最小边界；若
需要未列 owner、store、bus、scheduler、隐式 NPC 状态或额外 API，立即停止该分支并报告。

每次阶段汇报只包含：

1. 已完成且已验证：文件、命令、Harness report、关键 digest；
2. 已完成但未完整验证：缺少的证据；
3. 阻塞：实际错误、owner 或前置证据；
4. 下一步：当前正式 plan 已授权的下一项。

最终只在 P2D 及所有前置 profile fresh-green 后，声明：
“已有角色的多智能体组织协作已在 `bakery-authored-agents` 通过 authority、replay、
scope-filtered mirror 和 Harness 门禁。”
```

## Usage constraint

本提示词只适用于已经获得单独运行时代码实施授权的后续任务。它不授权 Population Simulation、
动态市场、全局时钟或任何未写入 P2A-P2D 正式 spec/plan 的 owner、store、bus、scheduler 或
隐式 NPC 状态。
