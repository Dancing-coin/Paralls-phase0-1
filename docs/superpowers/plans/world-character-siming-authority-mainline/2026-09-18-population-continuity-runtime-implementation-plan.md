# 计划 A：运行时连续性与共享基础 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: 执行时使用 superpowers:executing-plans；明确采用子代理方式时使用 superpowers:subagent-driven-development。按复选框逐项取证，不因计划已写完而勾选实施任务。

**Goal:** 人员甲交付同一角色跨 B0–B3 的共享合同、连续性账本、安全交接、受控读取，并为一个日供给分片计算器提供最小冻结/模式/审计合同；负责公共入口集成与共同验收。

**Architecture:** 扩展现有 Character Core、population_continuity、world_runtime、Siming 与 GameplayEventStore。纯计算与事实提交分离；复用现有 CharacterContinuityService、activation lock、读写 revision、幂等和 replay。人员乙通过明确接口提交模块与领域结果。

**Tech Stack:** 项目现有 Python、Pydantic、pytest、SQLite、Harness；不增加调度框架、求解器、Ray 或 GPU 依赖。

**Spec:** [整合规格](../../specs/world-character-siming-authority-mainline/2026-09-18-character-population-social-causality-integrated-design.md)，组织修订 `2026-09-18-r3`。配套为[计划 B](2026-09-18-character-simulation-domain-vertical-implementation-plan.md)。

**Status:** `planned; implementation_not_started`。用户已要求生成两份 plan 和人员分工；这不表示本稿中的新 API 已存在或代码已获验收。甲、乙是人员角色占位，不是假定已有具体姓名。

**核查基线:** `D:/Paralls-phase0-1`，本轮复审 HEAD `d9b810f3`。实施先核对最终整合提交和工作区，再建立 `codex/` 工作树；本轮计划不复用或覆盖其他任务的未完成变更。

## Global Constraints

- “同一角色最多一个有效推进者。”角色身份、档案、状态和记忆不因精度切换复制。
- “不新增第二套 runtime、clock、scheduler、event store、event bus、万能 router 或 generic settlement coordinator。”
- “模块、模型、Siming、图谱和 Godot 不直接写库存、账户、关系、法律、人口、空间或角色私有记忆。”
- 仿真 tick、来源 revision、角色 revision、状态游标和记忆游标分别校验；新增窗口使用 `(from_tick, to_tick]`。
- Owner 在实际提交点重验完整 read-set；通知失效和读取最新 head 不能替代旧 expected revision 校验。
- `schedule_gated_supply` 只证明组织供应承诺；实际粮食、药品、床位与迁移各需真实能力和 receipt。
- C0–C7 仍是连续性基线跟踪范围；本轮不实现群体报告到个人的分摊。AM1/BM1 是单个日供给分片计算器，shadow 和 advisory 分阶段验收；M-active 可选且须 G-M 准入，E/F 保留原 spec 前置门禁。
- 当前 advance_b0_row 是按 actor 连续积分，不能作为安全群体聚合/分摊已完成的证据。A2 首期仅锚点、分片、明确 actor 结果消费与交接；模型报告不更新个人状态或游标。
- 保留现有历史合同，新增严格校验不能追溯改义旧事件。Pydantic `frozen=True` 不等于嵌套字典已隔离，帧及计算输入必须做嵌套不可变或防御复制验证。
- 六项生产工程沿用[既有计划](../2026-09-16-population-production-runtime-closure-implementation-plan.md)，新任务不得复制其执行隔离、恢复或表现框架。该旧计划的证据路径和文档提交表述如与当前 AGENTS.md 不一致，以当前仓库规则为准。
- 执行时按 [Harness 指南](../../../harness.md) 和项目 harness-verification skill 选入口、导出和清理。本轮只写文档，不运行性能或 Godot 验收。

开源依据沿用[项目与开源对照](../../../reference/2026-09-18-social-simulation-open-source-comparison.md)：A1/A3 借鉴 Mesa 的激活/事件机制，A5 借鉴状态与执行对象分离；不引入另一套 Model runtime。性能优化以当前瓶颈和等价证据为准，不因人口数增加迁入 Ray/FLAME GPU。

## 1. 两人责任与文件所有权

| 责任 | 人员甲 | 人员乙 |
| --- | --- | --- |
| 共享 schema、参与解析、连续性与锁 | 主责，维护唯一合同 | 提供玩法约束，评审真实消费者 |
| 角色模块、原型、洪灾与领域协议 | 提供接纳端口，评审越权与重复提交 | 主责，维护规则和 Owner 映射 |
| Character Core | 独占公共接纳与运行循环修改 | seed_planner 中构造输入；不得直接写 Core 状态/记忆 |
| 首个计算器 | 最小 grant、冻结/失效、模式隔离、报告与审计合同 | 固定日供给语义、现有 Owner 输入适配和纯计算 |
| 验收 | 公共 Harness、回放、集成与汇总 | 模块/领域 focused tests、洪灾与 Godot 样板 |
| 后继 E/F | 依赖版本、impact 调度接入、通用隔离合同 | 操作证据、领域确认、Godot 与阵营场景；门禁满足后细化 |

**甲单一编辑的现有文件：** `backend/app/population_continuity/models.py`、`siming_contracts.py`、`batch.py`、`continuous.py`、`hot_state.py`、`world.py`、`activation.py`、`activation_policy.py`（前述缩写均在同一 population_continuity 目录）；`backend/app/world_runtime/population_driver.py`、`simulation_clock.py`；`backend/app/character_agent/models/simulation_seed.py`、`services/character_continuity.py`、`runtime/runtime_loop.py`；`backend/app/main.py`、`backend/app/services/siming_runtime.py`、`siming_population_capability.py`。

甲拥有共享 profile、验证脚本和 CI 接线修改责任。`GameplayEventStore` 当前已有 read-set 重验；默认消费其接口，不为本任务重写 store。若查出实际缺口，由甲在对应任务中以复现测试做最小修复。

乙拥有 `seed_planner.py`、`owner_adapters.py`、`inventory_owner_adapter.py`、`social_owner_adapter.py`、`domain_projection_sources.py` 及其新增角色模块、洪灾/日供给计算文件。`vertical.py` 是既有大型样板文件，乙只提取必要复用，新增洪灾场景放独立窄文件。`social_input.py` 和 `source_inputs.py` 首期作为共同只读依赖；必要读取补验放乙的窄输入适配，不能两人分别改造。详细文件清单见 B。

**并行规则：** 两人不同时修改相同公共文件。乙提交接口需求、领域代码和 focused tests 后，由甲顺序接线。若既有 P 生产工程仍在修改同一入口，先取得其接口/提交交接再接线，不平行替换其实现。一个变更若影响共享合同，先更新 spec、A 的接口记录及 B 的消费者，再实现；不私加字段。工作树以 cherry-pick 集成，提交按可独立审查的交付组织，中文说明，不使用全仓 `git add .`。

## 2. 交接批次与依赖

| 批次 | 甲交付 | 乙交付 | 下一批的硬门 |
| --- | --- | --- | --- |
| D0 | 确认本稿共享接口、文件归属、源码基线 | 确认模块字段策略、样板事实范围 | 双方使用同一 spec 修订；每个跨人接口有唯一生产者 |
| H1 | A1 帧/参与/建议合同与 Core 接纳规则 | B1 模块声明、B2 原型/情境 | H1 接口与 focused tests 通过后才写依赖生产代码 |
| H2 | A2 账本，A4 受控读取可独立推进 | B1/B2 行为测试、B4 现有 Owner 窄闭环 | 账本 replay 只证明锚点和已确认 actor 结果消费，不授权群体均值回填 |
| H3 | A3 交接 | B3 洪灾群体与玩家交集 | 唯一推进权、身份连续、旧执行者拒绝 |
| H4 | A5 公共接线、DOD 等价与总验收 | B4/B5 receipt 回流与可见样板 | C0–C7 对应证据齐全；Godot 单独标记 |
| HM0 | AM1 最小输入/报告/预算/权限合同 | BM1 固定场景与八维算例 | 纯计算先过；不依赖 A1–A4 全部实现 |
| HM1 | AM1 shadow 旁路和重验审计 | BM1 真实 Owner 窄读取、与既有 planner 同输入对照 | 不投递候选、不改 planner 选择、不调用 Owner/Core 写入 |
| HM2 | AM1 advisory 只读可见入口 | BM1 覆盖率、阻塞和复核/升级类别报告 | HM1 通过后打开；无自动执行/交接；active 可长期关闭 |

依赖不是简单的 A 完成后才做 B：B1/B2 的内容可在 D0 后与 A1 合同实现并行；B4 对既有供应操作的回归可提前；AM1/BM1 的 HM0→HM1→HM2 可以先做，不要求先建完角色帧、成员账本或通用密码本。最小来源授权/版本/内容/时间验证不可省略，A4 后续复用这些合同而不是另造版本。B3 的真实交接等 A2/A3。H4 明确拆为 A5 公共接线 → B5 完成真实回流/场景 → A5 总验收。

每次交接附：提交 ID、改动文件、接口修订、通过与失败命令、对应 AC、仍关闭的 gate。接收方先运行消费者测试再集成，不把对方口头“完成”作为运行证据。

## 3. A1：共享帧、参与解析和提交合同

**对应：** C0/C1；AC-01、AC-02、AC-03。**依赖：** D0；乙提供 B1 字段策略和 B2 规则内容。

**Files**

- Create: `backend/app/population_continuity/simulation_contracts.py`、`simulation_frame.py`。
- Modify: `backend/app/population_continuity/activation_policy.py`、`backend/app/character_agent/models/simulation_seed.py`、`backend/app/character_agent/services/character_continuity.py`、`backend/app/character_agent/runtime/runtime_loop.py`。
- Test: `backend/tests/test_character_simulation_frame.py`、`test_character_participation_resolution.py`、`test_character_agent_seed_continuity.py`。

**Interfaces — Produces（新接口，不声称当前存在）：**

```python
def resolve_participation(
    *, policies: tuple[ParticipationPolicy, ...], tick: int,
) -> ParticipationResolution: ...

def build_simulation_frame(
    *, actor_ref: str, profile_ref: str, profile_revision: str,
    character_revision: int, tick_cursor: int,
    read_set: PopulationReadSet,
    module_states: Mapping[str, Mapping[str, object]],
    participation: ParticipationResolution,
    codebook_refs: tuple[str, ...], activation_lock_ref: str | None,
) -> CharacterSimulationFrame: ...
```

`ParticipationPolicy` 是本任务新增严格输入：`policy_ref`、`revision`、`allowed_tiers`、`allowed_modules`、`forbidden_dimensions`、`upgrade_triggers`、`b0_expiry_tick`、`review_tick`。策略来源固定为原型、个体、情境和确认约束；首版仅交集/收紧，不实现任意策略插件。无合法层级时 resolution 的 recommended_tier 为空、status=defer；调用者 requeue。

`CharacterSimulationFrame`、`ParticipationResolution`、`ModuleProposal`、`SimulationCommitPacket`、`IntersectionPacket` 的字段使用 spec 第 6 节；本文件定义全部共享类型，乙仅 import。`ModuleDefinition` 同处声明，字段按 spec 6.3；字段策略限定为 aggregatable/distributable/individual_only/group_summary_only 的显式组合，不能从统计许可推导回填许可。

**Consumes：** 既有 PopulationReadSet 和 Character Core 读取；乙的 ModuleDefinition。Core 接纳复用 `CharacterAgentRuntime.apply_character_continuity_command(command: CharacterContinuityCommand) -> CharacterContinuityReceipt`，不复制第二个 service。

- [ ] 在新测试文件建立最小两来源策略数据，证明推荐层级属于交集、缺省保护、到期 B0 被去除；构造帧后修改原 module_states，帧 digest 和内容保持不变。

```python
def test_late_input_mutation_cannot_change_frame(frame_case):
    frame, original_states = frame_case.build()
    before = frame.frame_digest
    original_states["needs"]["fatigue"] = 1.0
    assert frame.module_states["needs"]["fatigue"] == 0.2
    assert frame.frame_digest == before
```

`frame_case` 在同文件定义，仅组装真实 PopulationReadSet 和上述 build 函数；`build()` 返回 `(CharacterSimulationFrame, 原始输入字典)`，不 mock 输出。

- [ ] 在 backend 运行 `python -m pytest tests/test_character_simulation_frame.py tests/test_character_participation_resolution.py -v`，先确认新行为失败；导入失败仅是初始红灯，接入后必须看到语义断言能捕获浅拷贝/策略放宽。
- [ ] 最小实现：严格模型、规范 digest、输入隔离、策略交集；Core 运行时依据当前 revision/锁拒绝 stale。schema 只判格式，不在 model validator 中查询世界或“证明版本新鲜”。

```python
allowed = set(policies[0].allowed_tiers)
for policy in policies[1:]:
    allowed.intersection_update(policy.allowed_tiers)
if any(tick >= p.b0_expiry_tick for p in policies):
    allowed.discard("B0")
```

- [ ] 运行以上新测试与 `tests/test_character_agent_seed_continuity.py`，覆盖额外字段、非有限数、跨 actor、旧 revision、重复键不同载荷；拒绝前后业务事件和角色 revision 不变。
- [ ] `git diff --check`，交付 H1；提交边界为“共享帧与参与约束接入角色连续性”，不包含乙的模块算法。

## 4. A2：B0 成员账本、分片与消费游标

**对应：** C3；AC-04、AC-05。**依赖：** A1 与 B1 字段策略；B2 可提供样板身份。

**Files:** Create `backend/app/population_continuity/member_ledger.py`；Modify `backend/app/population_continuity/world.py`、`hot_state.py`；Test `backend/tests/test_population_member_ledger.py`、`test_population_member_ledger_replay.py`。

**Interfaces — Produces：** `PopulationMemberLedger`/`MemberEntry`（spec 7）、`partition_members(ledger: PopulationMemberLedger, *, seed: str, partition_revision: str) -> PopulationMemberLedger`、`pending_member_results(ledger: PopulationMemberLedger, *, actor_ref: str) -> tuple[str, ...]`。成员 entry 保存 actor_ref、entry_character_revision、policy pins、shard_ref、保护引用、last_consumed_result_cursor 与生命周期。

pending_member_results 只返回来源已明确关联该 actor 的真实确认结果；分片总量 receipt 或模型报告不满足这一条件。首期 distribution_policy=none。报告可作为临时读取/审计引用，但不能进入待物化个人增量或推动 group/individual 的业务消费游标。甲负责原 actor 确认结果的幂等消费，乙不提供“群体均值分摊器”。

- [ ] 构造 3 人账本：普通成员、照护成员、individual_only 成员；打乱输入顺序、相同 seed 分片结果不变；保护字段不进入聚合输出。

```python
def test_replay_preserves_unconsumed_member_results(ledger_case):
    ledger_case.commit_actor_result("character:ordinary", "result:1")
    ledger_case.commit_actor_result("character:carer", "result:2")
    ledger_case.consume_for("character:ordinary", "result:1")
    full = ledger_case.restore_full()
    tail = ledger_case.restore_checkpoint_tail()
    assert full == tail
    assert pending_member_results(full, actor_ref="character:carer") == ("result:2",)
    assert pending_member_results(full, actor_ref="character:ordinary") == ()
```

`ledger_case` 在测试文件定义，封装真实 store/world 的 append、checkpoint 和恢复；commit_actor_result 走原已准入按 actor 连续性/Owner 链，consume_for 只有该 actor 的 Core receipt 成功后记录消费，两个 restore 返回重建账本，不得仅复制当前内存对象。另输入一份 BM1 覆盖率报告，断言全部 actor 状态、记忆和消费游标不变。

- [ ] 运行 `python -m pytest tests/test_population_member_ledger.py tests/test_population_member_ledger_replay.py -v`，验证消费重复/崩溃点、顺序敏感和保护字段断言在未实现时失败。
- [ ] 最小实现：复用既有持久化/回放链保存锚点与按 actor 结果消费凭据；新增事件载荷如不可由当前 schema 表达，先在原 Owner 下登记明确 schema、迁移和 replay，不用任意 payload 绕过注册。分片只读取许可字段；没有可按 actor 归因的来源返回 unknown/升级，不能按人数除出个人效果。

```python
ordered_members = sorted(ledger.member_entries, key=lambda item: item.actor_ref)
unconsumed = tuple(ref for ref in confirmed_refs if ref not in consumed_refs)
```

- [ ] 运行新测试及 `tests/test_population_checkpoint_closure.py tests/test_population_persistence_regression.py`；在 Owner 已提交/Core 未接纳、Core 已接纳/消费标记未写两个断点重启，均不重复世界效果。
- [ ] `git diff --check`，交付 H2；提交边界为“成员账本与确认结果消费回放”。不把账本做成另一份个人库存或记忆库。

## 5. A3：唯一推进权与 B0–B3 交接

**对应：** C4；AC-06、AC-08。**依赖：** A1/A2；消费 H1 已冻结的触发/连续性输入合同。B3/B5 的真实消费者联调在 H3/H4 完成，A3 不等待 B5 整体验收。

**Files:** Create `backend/app/population_continuity/handoff.py`；Modify `backend/app/population_continuity/activation.py`、`activation_policy.py`、`backend/app/character_agent/runtime/runtime_loop.py`；Test `backend/tests/test_population_handoff_continuity.py`，保留 `test_character_agent_activation_handoff.py`。

**Interfaces:** `prepare_intersection(*, frame: CharacterSimulationFrame, ledger: PopulationMemberLedger, trigger_kind: str, target_fidelity: str, lock: ActivationLock) -> IntersectionPacket`。此函数纯构包；锁取得、释放、pending、Core 接纳均调用既有 authority/runtime。甲新增只读公共接口 `ProfileActivationAuthority.active_lock(*, world_ref: str, profile_ref: str) -> ActivationLock | None`，返回隔离后的凭据，避免消费者访问 `_locks`。甲在原 activation 合同中补足可在提交时验证的锁代次/凭据；乙不得另造锁管理器。

- [ ] 测试覆盖旧 B0 执行者晚到、重复 handoff、释放前超时、重启后重入队；断言同一 actor identity digest 和未决义务保留。

```python
def test_old_b0_writer_cannot_commit_after_handoff(handoff_case):
    old = handoff_case.capture_b0_command()
    identity = handoff_case.identity_digest()
    handoff_case.to_tier("B3")
    before = handoff_case.business_event_count()
    receipt = handoff_case.submit(old)
    assert receipt.status == "rejected"
    assert handoff_case.business_event_count() == before
    assert handoff_case.identity_digest() == identity
```

`handoff_case` 在测试中使用真实 ProfileActivationAuthority、CharacterAgentRuntime、A2 账本；这些方法仅包装原公共调用，不能直接改 `_locks` 或伪造 receipt。

- [ ] 运行 `python -m pytest tests/test_population_handoff_continuity.py tests/test_character_agent_activation_handoff.py -v`，确认新旧执行者竞争测试先红。
- [ ] 最小实现顺序固定为：取得凭据 → 固化最后确认游标 → 接纳原按 actor 合法连续性 → 构包 → 接管；不从 cohort 压力均值还原个人状态。旧提交同时检查 character revision 和凭据。拒绝保持原正式结果，不将超时当自动成功。

```python
if command_lock_ref != current_lock.lock_ref or command_lock_revision != current_lock.held_revision:
    return self._continuity_refusal(command, revision, "handoff_lock_stale")
```

该拒绝沿原运行循环返回 CharacterContinuityReceipt，不新增并行拒绝模型；无 active_lock 同样按正式 stale/锁冲突拒绝。

- [ ] 新测试及 `tests/test_population_activation_policy.py tests/test_character_agent_seed_continuity.py` 全过；证明交接中收到的新世界事件只进入下一帧。
- [ ] `git diff --check`，交付 H3；提交边界为“交接凭据与旧推进提交隔离”。

## 6. A4：通用密码本与历史读取

**对应：** C6；AC-09、AC-13 的输入前置。**依赖：** A1 合同；消费乙的领域读侧来源。

**Files:** Create `backend/app/models/codebook.py`、`backend/app/services/codebook.py`；Test `backend/tests/test_codebook_authorized_expansion.py`、`test_codebook_historical_replay.py`。沿现有来源读取接口接入，不建立 population 专属私有内容库。

**Interfaces:** `CodebookEntry`、`CodebookReadReceipt` 使用 spec 6.1；新增 `CodebookReadRequest(reader_ref, code_ref, requested_level, purpose, scope, expected_revision, expected_digest, at_tick)`。`expand_codebook(request: CodebookReadRequest, *, entry: CodebookEntry, source_projection: Mapping[str, object], current_policy: Mapping[str, object]) -> tuple[Mapping[str, object], CodebookReadReceipt]` 只做封闭 policy schema 的过滤/验证；来源装配由原 Owner 完成，调用者不能自签 current_policy。

- [ ] 表驱动测试 reader/purpose/scope/expiry/revision/digest 任一不匹配不得返回隐藏字段；拒绝也有脱敏读取回执。

```python
def test_expired_normal_grant_does_not_block_authorized_history(codebook_case):
    denied = codebook_case.read_current(at_tick=101)
    audit = codebook_case.read_history(at_tick=101, audit_grant=True)
    assert denied.receipt.status == "expired"
    assert denied.content == {}
    assert audit.receipt.source_revision == codebook_case.original_revision
    assert audit.content_digest == codebook_case.original_digest
```

`codebook_case` 创建 expiry=100 的原读取授权、仍保留的历史版本及独立有效审计授权；两个 read 方法调用本任务展开函数并以命名结果暴露 receipt/content/content_digest。另删去历史输入验证 replay_input_unavailable，不以最新内容代替。

- [ ] 运行 `python -m pytest tests/test_codebook_authorized_expansion.py tests/test_codebook_historical_replay.py -v`，确认越权泄露、历史回退断言先失败。
- [ ] 最小实现按 L0/L1/L2 声明选择字段；内容留在原 store，entry/receipt 只存 refs/digests。历史审计单独验证当前审计权限。

```python
visible = {name: source_projection[name] for name in granted_fields if name in source_projection}
```

- [ ] 所有拒绝 case 断言 content 为空、无角色/业务写入；缺历史与无权限状态可区分。运行新测试，`git diff --check`。
- [ ] 提交边界为“通用受控展开与历史输入审计”，交付给 B4/BM1/AM1。

## 7. A5：公共接线、语义 oracle 与基线验收台账

**对应：** C5/C7；AC-01–AC-09、AC-18–AC-20。**依赖：** 公共接线依赖 A1–A4、B1–B4 与 B5 已冻结的转换接口；公共接线交付后乙完成 B5，最终总验收再等待 B5 的真实结果。

**Files:** Modify `backend/app/main.py`、`backend/app/services/siming_runtime.py`、`siming_population_capability.py`、`backend/app/world_runtime/population_driver.py`、`backend/app/population_continuity/batch.py`、`continuous.py`、`hot_state.py`；Create `backend/tests/test_character_population_integrated_loop.py`、`scripts/verification/verify_character_population_integrated_loop.py`、`.harness/profiles/character-population-integrated-loop.json`；相关现有测试/profile 按实际影响更新。

**Interfaces:** 消费乙的 `evaluate_modules`、`FloodPopulationFixture`、原 `CharacterSeedPlanner.derive` 和真实 `PopulationOwnerReceipt`；公共入口仍为 `SimingRuntime.tick(inputs: list[SimingInput]) -> SimingTickResult`，世界时间仍由已有 driver/clock 管理。输出 report 使用 `overall_passed` 和明确的 backend/godot 状态，不将新模式默认套到所有旧场景。

- [ ] 新集成测试从真实已准入 cadence/投影进入公共入口，验证不经 fixture 私有 shortcut；同样本的标量 oracle 和热状态执行比较候选、Owner receipts、Core 状态、游标与 replay digest。

```python
def test_scalar_and_batch_preserve_same_authority_results(integrated_case):
    scalar = integrated_case.run(execution="scalar")
    batch = integrated_case.run(execution="batch")
    assert scalar.owner_receipts == batch.owner_receipts
    assert scalar.character_states == batch.character_states
    assert scalar.replay_digest == batch.replay_digest
```

`integrated_case.run` 在同一初始快照、固定规则/seed 上分别创建新 runtime，并收集真实提交结果；标量模式使用 B 模块纯规则，batch 消费同一规则，不能用同一实现运行两次冒充 oracle。

- [ ] `python -m pytest tests/test_character_population_integrated_loop.py -v` 先验证尚未接线或保护字段损坏会失败。
- [ ] 最小接线到现有 cadence、capability、Core 端口；先跑通标量语义，随后仅扩展已有列式热状态，避免为 DOD 创建第二模型。失败保持 requeue/receipt，不吞错误继续报完成。

```python
if owner_receipt.committed:
    continuity_receipt = continuity_port.apply_command(command)
    # 只有接纳成功后才确认角色消费游标；重试复用同一 command 身份。
```

- [ ] 在 backend 运行 `python -m pytest -v`；仓库根通过 runner 运行新增 `character-population-integrated-loop` 及下表 profile。规模测试单独顺序运行，记录 100/1000/10000、1×/10×、窗口数、p95、最大推进延迟和积压；不把旧报告当新证据。生产阈值沿既有 P 计划。

| 验收范围 | 显式 profile |
| --- | --- |
| 原链路与 Owner | phase3-population-continuity、siming-led-population-seed-continuity、siming-population-domain-owner-adaptation |
| 连续推进与 DOD | population-continuous-runtime、population-hot-state-equivalence、population-data-oriented-persistence、population-data-oriented-incremental-read |
| 规模 | population-runtime-scale |
| 全仓与主线 | all、mainline-unified-runtime |

命令格式为 `python scripts/verification/harness.py --profile <上表单个实际名称>`；尖括号用于说明选项，不是要求执行的占位命令。典型完整调用：

```powershell
python scripts/verification/harness.py --profile character-population-integrated-loop
python scripts/verification/harness.py --profile population-hot-state-equivalence
python scripts/verification/harness.py --profile population-runtime-scale
python scripts/verification/harness.py --profile all
```

- [ ] 乙交付 B5 Godot 证据后由甲核对同一后端修订、边界消息与可见结果；缺失时 C backend 可分别记录通过，整体 C 保留 godot_unverified，E gate 不打开。C3 原基线要求的安全分摊若尚无独立任务/证据，则标为 deferred，不将本轮“只读汇总+按 actor 回放”替代它，C0–C7 整体门禁仍不通过。
- [ ] 检查本轮 Harness 退出码、证据输入版本及清理结果；`git diff --check`，提交边界为“共享推进与洪灾纵切集成验收”。不在本提交混入既有六项生产工程重构。

## 8. AM1：日供给计算的最小冻结、模式和审计合同

**对应：** M shadow/advisory；AC-10、AC-11 输入部分、AC-13、AC-21/22。**依赖：** D0 后与 BM1 冻结最小接口；直接复用现有社会/领域读侧，不等待 A1–A4 全部实现。消费者保持一份合同，A4 完成后复用相同读取结果与权限语义。

**Files:** Create `backend/app/models/social_model.py`、`backend/app/services/social_model_execution.py`；Modify `backend/app/services/siming_population_capability.py`（先只读旁路），`siming_runtime.py` 仅有 grant 接线缺口时修改；Test `backend/tests/test_social_model_execution_contract.py`、`test_social_model_replay.py`、`test_daily_supply_shadow_comparison.py`；Create `scripts/verification/verify_social_model_compiler_contract.py`、`.harness/profiles/social-model-compiler-contract.json`。不修改 graph projector 或建立实体关系图服务。

**合同范围：** spec 10.2 的名称是逻辑职责，不要求九个全功能框架。甲在单个 social_model.py 中用严格模型/既有类型组合表达这一固定调用，字段如下；BM1 仅 import。SocialModelDraft 的 V1 参数只允许 shard_ref、window、template_ref 和 correlation，禁止请求体携带任意 IR、事实数值或 callable。

| 新类型 | 固定字段/限制 |
| --- | --- |
| SocialModelTemplate | template_ref=`daily-shard-supply@1`、definition/operator pins、固定八维目录、max_analysis_window、输入/输出声明；不支持自由模板图 |
| ModelRunGrant | reader_ref、purpose、scope、mode、template pins、issued_tick、expiry_tick、预算与单日窗口；由既有治理入口签发 |
| InputVersionVector | 相关来源与查询/分片版本、projection/content digests、policy/template/operator pins、observed_at、from_tick/to_tick、expiry_tick、input_digest |
| FrozenModelInput | 获权 cards、vector、固定分片/单资源/单路线输入；以现有 FrozenSocialPlanningInput、HouseholdScheduleInput、OrganizationScheduleInput 作来源，不复制社会事实库 |
| DailySupplyReport | shard_ref、from_tick/to_tick、demand_units、confirmed_supply_units、reachable_supply_units、coverage_bps、blocking_reasons、upgrade_categories、input_digest/source revisions、expiry_tick；没有 actor allocations |
| ModelComputation | status、report（DailySupplyReport 或空）、work_units、diagnostics；正式失败不返回伪完整报告 |
| ModelRunReceipt | 输入/输出摘要、mode、grant、读取 refs、预算/降级、source validation、correlation；沿现有获权审计路径保存 |

数量区间用有界整数二元组；coverage_bps 范围 0–10000，已确认零需求时为空并在原因中标 not_required。FactCard/Proof 只包装原来源、授权和过滤后内容；CandidateEnvelope/ModelProjection 的只读内容引用同一 report，不建立第二报告 schema。报告不写世界或成员账本。

```python
def validate_model_run(
    *, template: SocialModelTemplate, grant: ModelRunGrant,
    inputs: FrozenModelInput, tick: int,
) -> None: ...
```

### AM1.1 / HM0：最小纯计算准入

- [ ] 新测试拒绝未知模板、额外字段、动态代码、超窗/预算、错误 reader/scope、错 digest；构造后修改原嵌套字典不改变输入/报告。固定来源版本、观察时刻、规则和输入顺序得到同一摘要。
- [ ] 运行 `python -m pytest tests/test_social_model_execution_contract.py tests/test_social_model_replay.py -v`，先红后实现最小校验；status 使用 spec 10.4 集合，缺必需上下文与无权分别返回 context_insufficient/policy_denied。

```python
if inputs.vector.to_tick - inputs.vector.from_tick > template.max_analysis_window:
    raise ValueError("policy_denied")
if tick >= min(grant.expiry_tick, inputs.vector.expiry_tick):
    raise ValueError("stale_input")
```

- [ ] 与乙对齐 BM1 的精确数值算例和固定求值顺序。先无缓存，不实现模板编排、通用 IR 解释器、片段失效或后台重算队列。交付 HM0 后双方可独立写语义/模式测试。

### AM1.2 / HM1：真实冻结输入与 shadow 对照

- [ ] 在同一 Owner 读边界取得乙的窄读集，完成来源/内容/recipient/时间/名单 pins 校验；off 不读取。保持现有 planner 输入与输出不变，shadow 只追加脱敏审计；对照不另跑一遍写入流程。

```python
def test_shadow_observes_same_input_without_changing_planner(shadow_case):
    frozen = shadow_case.freeze_once()
    baseline = shadow_case.plan(frozen, mode="off")
    observed = shadow_case.plan(frozen, mode="shadow")
    assert observed.planner_selected_refs == baseline.planner_selected_refs
    assert observed.planner_input_digest == baseline.planner_input_digest
    assert observed.model_receipt.input_digest == frozen.vector.input_digest
    assert observed.owner_submit_calls == baseline.owner_submit_calls == 0
    assert observed.core_apply_calls == 0
```

`shadow_case` 用 BM1 真实输入适配与现有 PopulationPlanner 的只读选择方法，关闭模式间用同一不可变输入、同一初始快照；记录差异但不强迫计算器报告等于 planner 的语义。两者可对不同问题给不同建议；禁止用改 planner 规则“对齐”结果。

- [ ] 执行 `python -m pytest tests/test_daily_supply_shadow_comparison.py tests/test_social_model_execution_contract.py tests/test_social_model_replay.py -v`。覆盖正常供给、路线受限、期限不足、保护义务、缺权限/必要卡；拒绝和降级必须可审计。
- [ ] 对每一项声明依赖分别通过合法 Owner 改 revision，再次取用旧报告必须返回 stale_input；同样测试授权撤销、分片名单版本和时间到期。仅审计历史读取可保持旧报告，其标记不能成为 current。未来 active 仍须在 append 点再验；没有变化通知不影响正确性。
- [ ] 测试图谱缺失且 Owner 输入齐全可继续、receipt 标 graph_degraded；必需来源不可得时不产完整覆盖率；不会自动补建关系图。验证被冻结内容的 digest 不匹配、浅层可变、观察时刻变化不能沿用原报告。
- [ ] 历史原输入保留/可重建时重算同一报告；缺失返回 context_insufficient 并记录 replay_input_unavailable 原因。观测到的知识置信度依赖 observed_at，不能只以 stream revision 当缓存键。HM1 取证前不得打开 advisory。

### AM1.3 / HM2：advisory 只读入口

- [ ] 消费者只在当前获权 scope 内看到 report、阻塞和复核/升级类别；不进入自动调度、handoff 或 capability submit 分支。

```python
def test_advisory_report_cannot_change_any_authority(advisory_case):
    before = advisory_case.authority_snapshot()
    result = advisory_case.run(mode="advisory")
    assert result.receipt.status == "ok"
    assert result.report.coverage_bps == (3428, 5167)
    assert advisory_case.authority_snapshot() == before
    assert advisory_case.owner_submit_calls == 0
    assert advisory_case.core_apply_calls == 0
    assert advisory_case.handoff_calls == 0
```

该 fixture 使用 BM1 实际固定输入和真实 store/Core 状态；只包装写入口计数，不以 mock Owner 证明 active 成功。snapshot 包含角色/成员游标与记忆，审计记录另计。

- [ ] 验证取用前重验和脱敏，再执行上述三个测试文件与 `python scripts/verification/harness.py --profile social-model-compiler-contract`。profile 分列 HM0/HM1/HM2，不将纯计算通过写成真实 Owner 输入或 active 通过。
- [ ] `git diff --check`。提交按“最小冻结合同”“shadow 对照”“advisory 可见”独立审查结果组织；精确缓存仅在重复计算需求成立后追加，不能阻塞首个结果或绕过重验。

## 9. 覆盖、后继与共同完成条件

| Spec 验收 | 甲责任 | 乙责任/依赖 |
| --- | --- | --- |
| AC-01–03 | A1/A5 | B1/B2 真实消费者 |
| AC-04–06 | A2/A3/A5 | B3 洪灾与交集 |
| AC-07–08 | A3/A5 Core 接纳与恢复 | B4/B5 真实 Owner 和 receipt 转换 |
| AC-09 | A4 | B4/BM1 最小领域读侧 |
| AC-10–13、AC-21/22 | AM1 的 HM0/HM1/HM2 | BM1；AC-12 的真实 aggregate 提交及 AC-11 提交部分等 G-M |
| AC-14–17 | G-E/G-F 满足后，甲负责共享版本和影响调度 | 乙负责领域证据与场景；当前不生成可执行代码任务 |
| AC-18–20 | A5 汇总，与既有 P 计划分别列证据 | B5 Godot 和领域样板 |

**G-M：** 乙出具 spec 8.2 的已有真实 aggregate 操作准入表，甲核验冻结读集能够到提交点；缺合法能力保持 proposal_only/capability_unavailable，可以长期以 advisory 交付。不为打开 active 顺手新增通用供给/分配协议。出现另行批准的业务操作后，才在本 A/B 两份计划补充 active 任务。

**G-E：** 原 C0–C7、replay、privacy、zero-write、handoff 和 Godot 确认投影证据全部满足后，甲补依赖索引/有界反应接线，乙补低/中影响交互和高影响环境变化任务。本轮推迟安全分摊后，不能将收窄的 A2 验收当原 C3 全完成；缺失项继续关闭门禁。现在只记录责任，不提前设计新的 writer。

**G-F：** E 的真实回流成立、领域冲突窗口和可见性合同确定后，甲补共享隔离/恢复，乙补双阵营四主体场景。门禁解除后仍在这两份计划追加任务，保持一份共享合同。

共同退出报告分别标 C、M-shadow/advisory、M-active、E、F、P。计划 A 不是独立业务上线声明；必须与 B 的结果共同证明第一条连续性闭环。代码完成、后端通过、Godot 通过和生产门槛分别记录，不能互相替代。
