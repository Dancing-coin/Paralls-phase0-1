# 计划 B：角色模块、洪灾样板与领域纵切 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: 执行时使用 superpowers:executing-plans；明确采用子代理方式时使用 superpowers:subagent-driven-development。按复选框逐项执行；甲方合同未交接的依赖任务不能用临时模型绕开。

**Goal:** 人员乙交付农民/老王的共享角色模块、洪灾参与内容、群体压力和玩家交集样板、真实供应承诺与 Character Core 回流，以及受约束洪灾模型模板。

**Architecture:** 模块和编译器只输出候选。原 PopulationPlanner/Siming/capability 选择与治理，领域 Owner 接纳事实，Character Core 接纳连续性；全部消费人员甲维护的一份共享合同与锁。Godot 展示可核验结果。

**Tech Stack:** 现有 Python、Pydantic、pytest、Gameplay Foundation、Character Core、Godot GDScript 与 Harness；首个模型使用固定规则和标准库。

**Spec:** [整合规格](../../specs/world-character-siming-authority-mainline/2026-09-18-character-population-social-causality-integrated-design.md)，组织修订 `2026-09-18-r2`。配套为[计划 A](2026-09-18-population-continuity-runtime-implementation-plan.md)。

**Status:** `planned; implementation_not_started`。本文件是本轮要求的第二份计划。甲、乙为人员角色占位；下列新增函数、类型、文件、测试和 profile 是拟实施内容，不声称已在仓库存在。

**核查基线:** `D:/Paralls-phase0-1`，HEAD `83fa2b33`。执行前核对最终整合提交及 A 的交接版本，保留其他任务的工作区变更。

## Global Constraints

- “同一角色最多一个有效推进者。”B0/B1/B2/B3 改变推进方式，不复制档案或以新角色替代老王。
- “不新增第二套 runtime、clock、scheduler、event store、event bus、万能 router 或 generic settlement coordinator。”
- “模块、模型、Siming、图谱和 Godot 不直接写库存、账户、关系、法律、人口、空间或角色私有记忆。”
- 原型、个体覆盖、情境与确认约束全部交给 A1 的统一参与解析；乙不维护另一套准入结果。
- 个体覆盖首版只收紧或细化；未声明字段默认 individual_only。允许统计不等于允许回填。
- B0 编译器输出只到 cohort/shard/pool/route/process batch；个人允许增量仅由已登记基线分摊规则生成、Character Core 接纳。
- `schedule_gated_supply` 的成功事实是 `gameplay.organization.commerce_commitment_accepted`。它不是已交付粮食、已入住避难所或已完成迁移。
- Character Core 通过现有 `CharacterContinuityService`/runtime 接纳；乙只构造输入和来源关联，不直接访问其状态写入、五池记忆或游标。
- 成功、拒绝、stale、duplicate、requeue 都是正式结果。恢复先复用已确认 Owner receipt，再补连续性，不能重新执行世界操作。
- Godot 只有实际后端、边界消息、场景可见结果齐全才算通过；样板录像/截图必须可关联到当次输入和 receipt。
- 两份 plan 共用 A 第 1–2 节的文件归属、D0/H1–H4/HM 和 G-M/G-E/G-F；不复制一套共同调度表。
- 新 Harness 证据按 [当前指南](../../../harness.md) 导出到仓库外并清理本轮资源，不能沿旧计划把生成报告长期放 `.harness/verification/`。

开源依据沿用[项目与开源对照](../../../reference/2026-09-18-social-simulation-open-source-comparison.md)：B1/B5 借鉴 Generative Agents/Concordia 的历史影响与认知组件；BM1 借鉴 NetworkX/OR-Tools 的有界图/约束算法表达，首版保持标准库固定算子。Concordia 的默认 LLM 结果裁决和 AgentSociety 的 CodeGen 写工具不进入本项目 Owner/纯编译边界；Habitat-Sim 仅用于后继具身测试方法参照。

## 1. 人员乙的文件边界和交接

**乙负责既有文件：** `backend/app/population_continuity/seed_planner.py`、`owner_adapters.py`、`inventory_owner_adapter.py`、`social_owner_adapter.py`、`domain_projection_sources.py`、`vertical.py`；只修改当前任务真实涉及的项，不对后两类 adapter 做顺带重构。

**乙新增窄文件：** `backend/app/population_continuity/character_modules.py`、`flood_scenario.py`、`flood_vertical.py`、`social_model_inputs.py`、`flood_model.py`。下列任务逐项说明用途；并非新 runtime 或事实库。

**乙不直接修改：** A 维护的共享模型、`batch.py`、`activation.py`、`world.py`、Core service/runtime、`main.py`、Siming 入口、world driver、公共 Harness/CI。需要这些文件的业务接线时，乙交付调用要求、真实 fixture 与测试，由甲在 A3/A5/AM1 接入。

**Godot：** B5 由乙负责现有 `scripts/l6/backend_bridge/BackendBridge.gd`、`scripts/l6/local_presentation_bus/LocalPresentationBus.gd`、`scripts/phase0/MainDemoController.gd`、`scenes/phase0/MainDemo.tscn` 中必要部分；先查已有六项生产工程的 presenter 是否已合入，复用其公开投影。autoload 包装文件没有行为缺口时不改。

**交接给甲的固定结果：**

| 任务 | 交接物 | 甲消费位置 |
| --- | --- | --- |
| B1/B2 | 模块定义、字段保护、原型/情境策略及完整样板输入 | A1 参与解析、A2 分片/分摊 |
| B3 | 群体候选与玩家交集输入，不能夹带世界成功状态 | A2/A3/A5 |
| B4 | 原 capability 的真实 Owner 成功/失败回执、原 read-set | A5 公共链路 |
| B5 | seed/continuity 转换、暴露依据与恢复测试；Godot 证据 | A3/A5 Core 接纳和总验收 |
| BM1 | 固定模板、纯计算入口、最小卡输入与行为对照 | AM1 运行/审计、A5 验证接线 |
| G-M | aggregate 操作逐项准入表及已有/缺失能力证据 | 甲核验完整读集与提交边界后共同派生 active 任务 |

## 2. B1：农民简易模块与保护字段

**对应：** C2；AC-03、AC-04。**依赖：** A1/H1；模块规则草案和测试用例可在 D0 后提前准备。

**Files:** Create `backend/app/population_continuity/character_modules.py`；Test `backend/tests/test_character_simulation_modules.py`。共享 ModuleDefinition/ModuleProposal 由 A1 提供，不在本文件重复定义。

**Interfaces — Produces：**

```python
def farmer_module_definitions() -> tuple[ModuleDefinition, ...]: ...

def evaluate_modules(
    frame: CharacterSimulationFrame, *, to_tick: int,
) -> tuple[ModuleProposal, ...]: ...
```

定义固定 identity、needs、schedule、household、supply、situation、affect、behavior 八种职责，放一组受信声明与纯函数中。每个声明填写 spec 6.3 全部字段；state_schema 只能引用已登记固定 schema，禁止从 JSON 生成自由可执行 schema。提议类别固定为 continuity_delta、activity_candidate、action_candidate、upgrade_request、decision_conflict，由甲写入共同类型。

| 模块 | 首个样板规则 | 不得改写 |
| --- | --- | --- |
| identity | 读取同一角色、原型和档案 pins | ID、家庭身份、玩家关系 |
| needs | 消费已声明 fatigue/need_pressure，生成有界连续性候选 | 饥饿死亡、伤害或库存 |
| schedule | 既有时间窗口与已确认承诺决定可参与时段 | 擅自完成/豁免承诺 |
| household | 照护责任冲突提出升级 | 家庭关系、分离和成员去向 |
| supply | 短缺提出供应协议候选 | 已得粮食或药品 |
| situation | 获权洪灾压力、道路风险与有效期 | 未确认淹没、桥塌或道路封锁 |
| affect | 只对声明的公共压力维度生成模块候选 | 角色私有信念与长期记忆 |
| behavior | 生存/照护/承诺约束后选择合法活动；冲突升级 | 任意突破保护字段 |

- [ ] 写家庭义务与普通劳动冲突的行为测试，并加入普通成员可继续活动的对照。

```python
def test_care_obligation_prevents_b0_routine_override(module_case):
    frame = module_case.frame(tier="B0", care_obligation=True)
    proposals = evaluate_modules(frame, to_tick=3600)
    assert any(p.proposal_kind == "upgrade_request" for p in proposals)
    assert all("household.members" not in p.typed_payload for p in proposals)
    assert module_case.world_snapshot() == module_case.initial_world_snapshot
```

`module_case` 在测试文件中定义，使用 A1 builder 和 B2 受信规则创建真实帧；frame 参数只改变获权规则输入，world_snapshot 读取真实测试 store，模块不能持有该 store。

- [ ] 运行 `python -m pytest tests/test_character_simulation_modules.py -v`，先确认规则违反会失败。
- [ ] 最小实现按已固定优先顺序处理硬约束；采用 `advance_b0_row` 既有数值规则需要由甲在 batch 接线，乙不得重写一套疲劳积分器。无法裁决返回显式冲突。

```python
if protected_conflict:
    return (upgrade_proposal,)
return tuple(sorted(allowed_proposals, key=lambda proposal: proposal.proposal_ref))
```

示例中的候选由本任务固定 schema 构造，包含原 frame_digest/read_dependencies/expiry；不使用任意 dict 作为 Owner 写请求。

- [ ] 对同一初始帧分别调用 B0/B1/B2/B3 可用模块，验证保护字段与身份一致；B3 复用状态，不能重置 fatigue 或未决承诺。检查输入未被原地修改。
- [ ] `git diff --check`；提交边界为“农民模块与保护规则”，交付 A1/A2 的 H1 消费测试。

## 3. B2：原型、老王覆盖与洪灾情境

**对应：** C1/C2；AC-03。**依赖：** D0 后可准备内容，运行接入等 A1。

**Files:** Create `backend/app/population_continuity/flood_scenario.py`、`backend/tests/fixtures/population_flood_v1.json`、`backend/tests/test_population_flood_participation.py`。真实档案解析复用 `assets/characters/profiles/` 和现有 registry；不为样板新增第二档案服务。

**Interfaces:** `flood_participation_policies(*, actor_ref: str, scenario_revision: str) -> tuple[ParticipationPolicy, ...]`；`flood_module_states(*, actor_ref: str) -> Mapping[str, Mapping[str, object]]` 只返回受信样板模块初值，事实字段通过 Owner 读侧装配。两个接口供 A1/B3 使用。

样板中“老王”是显示名。测试可用既有已登记 `character:char_a`，在隔离 fixture 配置农民原型和保护声明，不能更改用户默认档案。照护、关键种子与旧识规则通过 protected refs 表达；凡声称拥有物品、关系成立或承诺已确认，必须在 fixture 中通过相应已有合法 Owner/档案初始化得到来源，不能仅在 JSON 中写成硬事实。

固定数据至少有普通农民、照护农民老王、仅允许个人推进的成员；时间窗 0→3600→7200；规则 `flood:v1`、seed `flood:20260918`。没有情境时，重要角色不默认进入 B0；洪灾结束只撤销情境规则，保留 Core 已确认状态和未决承诺。

- [ ] 写同原型不同保护条件的对照，以及个体请求放宽 B0 的拒绝测试。

```python
def test_individual_override_cannot_relax_household_protection(participation_case):
    resolved = resolve_participation(
        policies=participation_case.policies(request_b0=True, care_obligation=True),
        tick=3600,
    )
    assert "B0" not in resolved.allowed_tiers
    assert "household.members" in resolved.forbidden_dimensions
```

`participation_case.policies` 调用本任务的固定内容装配，并使用甲定义的 ParticipationPolicy 构造输入；保护责任同时返回可核验 source refs。

- [ ] 运行 `python -m pytest tests/test_population_flood_participation.py -v`，确认放宽/退场重置用例先失败。
- [ ] 最小内容实现使用独立规则 pins；不通过在 JSON 填新的 Owner、capability 或 stream 来扩展权限。

```python
policies = (archetype_policy, individual_policy, flood_policy, confirmed_obligation_policy)
resolution = resolve_participation(policies=policies, tick=current_tick)
```

- [ ] 验证洪灾前/中/后同一身份；保护字段仍保留；state cursor 前进不等于 memory cursor 前进。
- [ ] `git diff --check`；提交边界为“洪灾参与内容与老王保护样板”，交付 H1/H2。

## 4. B3：洪灾群体压力与玩家交集

**对应：** C3/C4；AC-04–AC-06。**依赖：** B1/B2、A2；接管测试等 A3。

**Files:** Create `backend/app/population_continuity/flood_vertical.py`、`backend/tests/test_population_flood_cohort.py`；消费现有 `vertical.py` 样板装配机制，不把旧 bakery 场景改名成洪灾运行时。

**Interfaces:** `FloodPopulationFixture.create() -> FloodPopulationFixture`、`run_window(*, from_tick: int, to_tick: int, player_actor_ref: str | None = None) -> PopulationCycleResult`。fixture 暴露只读检查方法 `identity_digest(actor_ref)`、`member_state(actor_ref)`、`business_events()`，以及实际 `store` 和 `character_runtime`；生产流程仍调用原 Siming 入口。群体计算消费 A2 ledger，交集消费 A3 IntersectionPacket。

固定样板：初始疲劳 0.2、食物压力 0.1；道路风险来自获权情境或确认卡并保留其证据状态。整体统计只使用许可字段；家庭/种子/旧识只能驱动保护与升级，不进入平均分摊。B0 不输出每人损失、获救或死亡列表。

- [ ] 验证同样板/seed/输入次序打乱后统计和分片一致；玩家接近只对目标触发交接，不强制唤醒全村。

```python
def test_player_intersection_keeps_identity_without_fake_rescue():
    fixture = FloodPopulationFixture.create()
    actor = "character:char_a"
    before = fixture.identity_digest(actor)
    fixture.run_window(from_tick=0, to_tick=3600)
    fixture.run_window(from_tick=3600, to_tick=7200, player_actor_ref=actor)
    assert fixture.identity_digest(actor) == before
    assert fixture.member_state(actor) in {"handoff", "exited"}
    assert not any(e.event_type == "flood_rescue_completed" for e in fixture.business_events())
```

`flood_rescue_completed` 是禁止伪造的样板结果标记，不注册该事件。真实 GameplayEvent 的字段是 event_type；另外枚举当前样板已准入事件族，未知或越界世界效果均让测试失败，避免仅匹配一个禁用名称。

- [ ] 运行 `python -m pytest tests/test_population_flood_cohort.py -v`，先确认无交接/错误身份/假成功能被检测。
- [ ] 最小实现：从 B1 候选生成现有 PopulationProjection，携带原 pins，经 A 的统一选择/交接路径推进；允许分摊交由 A2 的消费接口和 Core 接纳，不由 fixture 修改状态。

```python
if player_actor_ref is not None:
    intersection_triggers = (player_actor_ref,)
else:
    intersection_triggers = ()
```

- [ ] 运行 A2/A3 消费者测试；增加一成员规则冲突、一个成员已 handoff、预算不足 requeue 的混合窗口，无重复推进或全局假完成。
- [ ] `git diff --check`；提交边界为“洪灾群体与玩家交集纵切”，交付 H3。

## 5. B4：真实供应承诺与完整读依赖

**对应：** C5；AC-07、AC-11 的基础机制。**依赖：** A1，必要的受控读取依 A4；对既有操作的回归可提前执行，群体集成等 A2。

**Files:** Modify `backend/app/population_continuity/owner_adapters.py`、`seed_planner.py`；Create `backend/tests/test_population_flood_supply_owner.py`；消费 `backend/app/population_continuity/batch.py` 的修改由甲承担。现有对照为 `test_siming_population_domain_owner_runtime.py`、`test_siming_led_population_seed_continuity.py`。

**固定准入行：**

| 项 | 值/要求 |
| --- | --- |
| behavior / capability | schedule_gated_supply / population:schedule-gated-supply:v1 |
| 既有 contract | inf:weather-front-organization-supply@1；执行前对照 capability catalog 的实际绑定 |
| 接纳者 | ScheduleGatedSupplyOwnerExecutor → 既有 ContinuityMergeAuthority/Organization 路径 |
| Owner / fact family | actor_gameplay.organization_domain / gameplay.organization.commerce_commitment_accepted |
| 输入来源 | 已确认 social、household、organization schedule 投影及 policy/package pins |
| read-set | 原请求冻结的合法来源 revisions 全程保留，包含只读依赖；不能从调用者自由指定流 |
| reservation | 本操作不假设床位或库存 reservation；existing pending/released schedule 生命周期保持原义 |
| 结果 | 供应承诺接纳、拒绝、stale 或 duplicate 的真实 PopulationOwnerReceipt |
| 写入上限 | 仅准入的组织承诺效果；不附带 Inventory/Economy/避难伪效果 |

**Interfaces — Consumes/Produces：** 原 `ScheduleGatedSupplyOwnerExecutor.submit(intent: BatchIntentCandidate, *, read_set: PopulationReadSet) -> PopulationOwnerReceipt` 保持。乙将必要源向量交给甲维护的 merge 路径，使其在 append 前按 GameplayEventStore 的 `read_stream_revisions` 校验。现有 legacy adapter 的“当前 head”语义不直接套给新 frozen 请求。

- [ ] 用真实 Owner 准入与初始化构造 `supply_case`；测试冻结后仅改变合法只读 schedule 来源，旧请求不能被接纳。

```python
def test_read_dependency_change_rejects_frozen_supply(supply_case):
    intent, read_set = supply_case.freeze_request()
    supply_case.change_schedule_via_owner()
    before = supply_case.business_event_count()
    receipt = supply_case.executor.submit(intent, read_set=read_set)
    assert not receipt.committed
    assert receipt.zero_write
    assert supply_case.business_event_count() == before
```

`supply_case` 在新测试文件中复用 SimingLedPopulationFixture 的合法 setup，freeze_request 返回真实 typed intent/read-set；change_schedule_via_owner 经 Organization 操作改变其 stream，不直接篡改 revision。

- [ ] 运行 `python -m pytest tests/test_population_flood_supply_owner.py -v`，让旧 read-set 未完整传递的回归先红。新增成功、无权、private/cross-actor、branch、重复键同/异载荷用例。
- [ ] 最小实现保持原冻结值；传递 read_dependencies 到既有提交检查，不只做 adapter 入口预检，避免检查后事实变化仍提交。

```python
expected_read_revisions = dict(read_set.cadence.base_revision_vector)
for projection in read_set.projections:
    for stream, revision in projection.revision_vector.items():
        if stream in expected_read_revisions and expected_read_revisions[stream] != revision:
            raise ValueError("stale_input")
        expected_read_revisions[stream] = revision
```

这段只处理已由来源准入验证的向量；不授予请求方任意读流权限。实际 append 参数由甲的 merge 修改消费，禁止静默读取新 head 覆盖旧值。

- [ ] 验证成功出现正确组织事件族；duplicate 返回原 receipt 且业务事件数不变；审计记录不混入 zero-write 业务计数。运行新测试及原两组回归。
- [ ] `git diff --check`；提交边界为“洪灾供应承诺与冻结读集接纳”，将 batch 公共改动需求作为 H4 交接交给甲。

## 6. B5：receipt 回流、记忆暴露与可见样板

**对应：** C4/C5；AC-08、AC-19、AC-20。**依赖：** B3/B4 与 A3、A5 的公共接线交付，不等待 A5 最终总验收。乙先按下述原 derive/continuity 合同提交转换接口与测试，甲完成接线后乙完成真实样板，最后由甲验收。

**Files:** Modify `backend/app/population_continuity/seed_planner.py`、`flood_vertical.py`；Create `backend/tests/test_population_flood_character_writeback.py`；Godot 必要修改使用第 1 节文件，必要时 Create `scripts/phase0/PopulationContinuityPresenter.gd`；Create `scripts/verification/verify_population_flood_scene.py` 与 `.harness/profiles/population-flood-scene.json` 的注册由甲集成。

**Interfaces:** 保持原 `CharacterSeedPlanner.derive(read_set, accepted_owner_receipts, *, owner_receipt_associations=None) -> tuple[CharacterSimulationSeedCandidate, ...]`。关联表必须来自实际请求→receipt 的对应关系，不能因列表里存在任意成功 receipt 就接纳另一角色的世界效果。Core 仍消费既有 CharacterContinuityCommand/Receipt。

- [ ] 对成功承诺产生 objective seed；无暴露者不产生 memory candidate；未成功请求不产生“已完成”状态；同 actor 无关 receipt 也不能冒认。

```python
def test_confirmed_owner_result_survives_writeback_retry(writeback_case):
    receipt = writeback_case.commit_supply()
    writeback_case.fail_first_core_acceptance()
    writeback_case.deliver(receipt)
    before = writeback_case.business_event_count()
    writeback_case.restart_and_redeliver(receipt)
    assert writeback_case.business_event_count() == before
    assert writeback_case.confirmed_state_updates == 1
    assert writeback_case.memory_candidates_for_unexposed_actor == ()
```

`writeback_case` 以 B4 真实 fixture 构造 Owner 提交，故障注入仅阻断第一次 Core 调用，restart 从实际持久状态恢复；计数从事件/receipt 读取，不在测试 helper 自增假装实现。

- [ ] 运行 `python -m pytest tests/test_population_flood_character_writeback.py -v`，确认无恢复、错关联或重复消费会失败。
- [ ] 最小转换只将对应成功 receipt 传给原 seed planner；失败返回正式拒绝/重入队投影；world-effect seed 的 owner refs 不得为空。是否物化长期记忆由 Core 当前 materialization policy 决定，不将辅助参考的“激活前绝不写记忆”扩大为覆盖所有既有合法路径。

```python
accepted_refs = tuple(r.receipt_ref for r in owner_receipts if r.committed)
seeds = seed_planner.derive(
    read_set, accepted_refs, owner_receipt_associations=verified_associations,
)
```

- [ ] 增加 state/memory cursors 分离、洪灾退场不重置角色、B0→B3→B0 同身份、交接中断后恢复测试；甲运行 Core/锁回归，乙运行新测试。
- [ ] 接入现有公开投影和 Godot 输入：玩家接近 → 同角色展开 → 请求供应 → 显示“供应承诺已接受”或明确拒绝。未接纳时只能显示候选/处理中，不能出现“已得粮食/已获救”。允许局部预测但必须与确认状态可区分。

```gdscript
if receipt_status == "committed":
    status_label.text = "供应承诺已接受"
elif receipt_status == "rejected":
    status_label.text = rejection_text
else:
    status_label.text = "处理中"
```

字段通过现有类型化镜像 payload 映射，禁止客户端自行设置 committed。新 presenter 只在已有公开表现组件不足时增加，不能另起 population scene runtime。

- [ ] 实际启动后端和项目，通过真实边界输入运行成功/拒绝两条路径，记录 source revision、请求/receipt correlation、角色身份、消息及可见状态。环境缺失即标 godot_unverified；headless 协议检查不当作画面证据。
- [ ] 乙提交 focused tests 和场景 probe，由甲注册 requires_godot=true 的 `population-flood-scene` profile。通过 runner：`python scripts/verification/harness.py --profile population-flood-scene`；报告失败必须传递非零退出码。
- [ ] `git diff --check`；提交可按“领域到角色连续性回流”和“洪灾可见样板”两个独立审查结果组织；交付 H4，所有测试原始产物按当前 retention 规则清理。

## 7. BM1：受信洪灾模板、领域卡与纯计算

**对应：** M shadow/advisory；AC-10、AC-13；AC-12 仅覆盖 B0 无逐人分配部分。**依赖：** B1/B2、A4 与 AM1 接口；不反向阻塞 C0–C7。

**Files:** Create `backend/app/population_continuity/social_model_inputs.py`、`flood_model.py`、`backend/tests/test_social_model_flood_template.py`、`test_social_model_owner_cards.py`；共享 `backend/app/models/social_model.py` 由甲维护；固定样板数据扩展 B2 的 fixture 文件。

**Interfaces：**

```python
def flood_template() -> SocialModelTemplate: ...

def read_flood_cards(
    *, read_set: PopulationReadSet, grant: ModelRunGrant,
    read_fact: Callable[[str, ModelRunGrant], FactCard],
) -> tuple[FactCard, ...]: ...

def compile_flood_model(
    *, template: SocialModelTemplate, inputs: FrozenModelInput,
    seed: str, budget_units: int,
) -> ModelComputation: ...
```

`read_flood_cards` 消费来源已验证的 Owner 投影，只以它定位固定模板声明的 card refs，再调用 read_fact 回查。read_fact 由现有 runtime 注入获权 Owner 读侧，输入是获准 card_ref 和 grant，输出是 Owner 签发 FactCard；请求方不能提供 callback、任意 stream 或执行代码。projection 本身不能自签 proof，缺签发来源返回 owner_unavailable/context_insufficient。Proof/CodebookReadReceipt 由 A4/既有 Owner 读取返回。`ModelComputation` 由 AM1 定义，包含 status、candidates、work_units、diagnostics；AM1 补运行授权、输入/输出 digest、cache 和审计 receipt。

模板名称固定为 `flood-resource-pressure@1`，类别限八类目录内的资源流量、空间可达性、约束与分配、风险与聚合组合。首版纯算子只做获权总量汇总、短缺区间、已确认可达边筛选和有限分片候选排序；不因八类 taxonomy 就提前建设八套求解平台。

输入最少为确认 resource-pool 总量、群体需求区间、道路能力/风险、参与摘要和模板 policy pins。缺需求/容量等必要输入返回 context_insufficient；未知值不能当成 0。未确认具身观察只影响风险或复核建议，不删除确认道路边。B0 输出不得含 actor 分配表、个人伤亡或 custody owner 变更。

- [ ] 一组固定输入：获权总量 100、需求区间 [120,140]，输出短缺 [20,40]；相同参数/seed/digest 的结果一致，不写任何 store。

```python
def test_flood_model_reports_aggregate_shortage_without_assigning_people(model_case):
    result = compile_flood_model(
        template=flood_template(),
        inputs=model_case.frozen_inputs(stock=100, demand_min=120, demand_max=140),
        seed="flood:20260918", budget_units=100,
    )
    assert result.status == "ok"
    assert model_case.shortage_interval(result) == (20, 40)
    assert not model_case.contains_individual_allocation(result)
    assert model_case.business_event_count() == 0
```

`model_case` 在本测试中创建符合 AM1 schema 的真实冻结卡和向量，shortage_interval/contains_individual_allocation 仅读取 CandidateEnvelope typed payload；不得修改运行结果使断言通过。

- [ ] `python -m pytest tests/test_social_model_flood_template.py tests/test_social_model_owner_cards.py -v`，确认空实现、把未知当 0、未确认道路当阻断或逐人输出都会失败。
- [ ] 最小实现：固定 IR 和算子顺序，确定性工作单位截断；预算不够返回 budget_exhausted，不能偷跑完毕或输出假精确解。

```python
shortage_min = max(0, demand_min - confirmed_stock)
shortage_max = max(0, demand_max - confirmed_stock)
```

- [ ] 增加 privacy denial、expiry、graph unavailable/degraded、source changed、缓存旧向量和未确认具身风险用例；图谱发现的关系必须回查来源 Owner。AM1 审计保留 read receipts、pins、预算和拒绝状态。
- [ ] 对“有照护责任/无责任”“道路确认关闭前/后”做固定输入对照；与简单总量启发式比较约束违反率和计算工作量。不把模型结果自然语言更长作为行为效果改进。
- [ ] 交付 HM 给甲运行 `social-model-compiler-contract`；`git diff --check`。提交边界为“洪灾受信模型与纯候选计算”，模式保持 shadow/advisory。

## 8. G-M：真实 aggregate 操作准入与 active 出口

本节是准入交付，不是让执行者直接编造资源操作的代码任务。**乙主责**填写下表，**甲复核**跨层 read-set、锁和恢复；没有实际合法操作则 active 保持 blocked，不影响已完成 shadow/advisory 的独立声明。

| 准入项 | 必须给出的具体证据 |
| --- | --- |
| 业务结果 | 明确是已确认资源消耗/容量占用中的哪一种 aggregate 效果，不是供应承诺 |
| 能力与 Owner | source-controlled capability、contract、Owner、精确事件族与来源目录 |
| 输入与权限 | reader/purpose/scope、卡种类、事实来源、读写流映射、数量/对象的唯一权威 |
| 生命周期 | reservation（若有）的创建、到期、取消与确认；冲突、重复和幂等规则 |
| 闭环 | 模型候选 → 原推进者 → 既有 intent → Owner receipt → Core/群体确认结果 |
| 验收 | 一项真实 aggregate 成功、容量不足和 stale 硬拒绝、重复无双写、full/checkpoint-tail replay |

当前 `InventoryOutputCustodyOwnerExecutor` 已有认证产物入库用途，数量和保管目标来自认证/不可变绑定。不能直接把洪灾模型计算出的任意粮食数量塞入该入口。若新增合法 family/content 足够，按既有准入完成；需要新原子事实或操作时，先补 spec 的该行 Owner 合同，再在两份计划中追加 active 实施任务。

## 9. 后继人员分工与最终交付

| 后继 | 人员乙职责 | 人员甲职责与启动条件 |
| --- | --- | --- |
| E 低/中影响具身交互 | 既有门/搬运操作证据、Owner 确认和 Godot 可见结果 | G-E 后接入版本依赖/impact；不是现在提前改兼容路径 |
| E 高影响环境变化 | 明确道路/桥梁/设施操作、可信来源与矛盾证据规则 | 同一事实链、旧候选提交拒绝、有界反应和断线恢复 |
| F 双阵营四主体 | 每方人类玩家+Character Core、各自 cohort、信息投影、确定性领域冲突样板 | G-F 后接通共享可见性/恢复，保持同一世界和 Owner |

原始七个具身领域案例分别经过实际操作准入，不为了任务完整率一次性铺满玩法。以上目前只分配责任和门禁，不生成可执行 E/F 代码任务；门禁满足后更新本 A/B 两份文件。

**乙交付清单：** B1–B5 focused tests、真实供应 Owner receipt 与失败证据、Core 回流/重试/暴露证据、同身份玩家交集、Godot 成功/拒绝可见证据、BM1 纯计算与行为对照、G-M 准入状态。每项附当前修订，不将历史 backend-only 报告当 Godot 或 active 完成。

**共同完成标准：** A5 表中的 C0–C7 能逐项对应证据；供应承诺、角色接纳和 Godot 展示三种结果分别可核验；M-shadow/advisory 与 M-active 分别列状态；E/F/P 按自身门禁报告。执行未开始时保留所有复选框未勾选。
