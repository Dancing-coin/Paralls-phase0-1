# 十月主线阶段一至三统一验收矩阵

状态：**执行中，整体未完成**。授权：用户 2026-10-20 明确要求整体完成阶段一至三；先收尾管理员生产入口，再扩大目标，后端先行，Godot 最后集中验收。本文件是统一剩余工作索引，不替代原规格或原始证据。

**当前执行目标：整体完成十月主线阶段一至三的实现与验收。** Goal ledger 仍 active；当前工具 `update_goal` 仅支持 status，无法修改 objective，不能以虚报旧目标 complete 的方式替换。本文件及[执行计划](../../superpowers/plans/2026-10-20-october-stages-1-3-implementation-plan.md)承载扩展后的权威执行范围。

**本轮目标扩展确认（2026-10-21）：** 阶段一至三的统一收口同时包含完整 Laya 真实 backend 链路（完整输入与候选、action+target、L4、真实领域 owner、receipt、恢复与回放）以及正式模型质量 Q01–Q04；Godot G-A/G-B/G-C 仍是后端与角色闭环收口后的最后门禁。服务可调用、choice 接纳、合同测试或单 owner slice 均不能替代这些闭环。Goal 保持 active；由于 Goal API 没有 objective 更新参数，扩展目标由本矩阵和执行计划承载，未将旧阶段目标错误标记为完成。

### 2026-10-21 窄恢复复验与证据边界

Settlement 私有 L1 snapshot 的 SQLite close/reopen、exact retry 零重复追加和跨 actor snapshot 拒绝仍由定向选择稳定通过：
`python -m pytest -q -p no:cacheprovider backend/tests/test_character_session_recovery.py -k "settlement_recovery_restores_private_l1_outcome_projection or ready_restores_private_l1_snapshot_from_committed_context_stage"` → **2 passed, 53 deselected**。
生产组合的单进程 slow-goal lifespan dispatch→provider→Character owner terminal receipt 也通过：
`python -m pytest -q -p no:cacheprovider backend/tests/test_character_slow_goal_main.py` → **1 passed**。
这两项只证明已修复的 snapshot projection 和单进程 provider/owner 事务边界；provider_pending 后新进程启动轮询仍因 actor pin/timeline/l1 差异保持未完成，不能升级 R09，也不能替代完整 Laya action+target→L4→多领域 owner、正式 Q01–Q04 或 Godot A/B/C。

### 2026-10-21 无 profile 进程恢复复验

使用无 PowerShell profile 的同一窄入口复验既有真实硬杀恢复合同，排除了本机 profile
在子进程启动前触发的 Conda 初始化错误（该错误曾表现为外层
`GameplayEventStoreSnapshotError`，未进入应用恢复断言）。

- `python -m pytest -q -p no:cacheprovider backend/tests/test_population_process_cognition_recovery.py::test_original_owner_provider_pending_survives_hard_kill_without_reingest[character] --tb=long`
  → **1 passed in 12.80s**。
- `python -m pytest -q -p no:cacheprovider backend/tests/test_population_process_cognition_recovery.py::test_original_owner_provider_pending_survives_hard_kill_without_reingest[character_commit] --tb=short`
  → **1 passed in 12.74s**。
- `python -m pytest -q -p no:cacheprovider backend/tests/test_character_slow_goal_main.py`
  → **1 passed in 4.42s**。

这三项证明普通 Character L2 provider pending、Character commit-started 和单进程生产
slow-goal lifespan 的现有边界；它们没有证明 `goal_proposal` 在新进程启动自动轮询下的
actor pin/timeline/private-L1 一致性，也没有证明慢目标 exact-once recovery、完整 Laya
action+target→L4→多 owner receipt、Q01–Q04 或 Godot G-A/G-B/G-C。R09 仍保持未完成；
stale protection 不放宽。

### 2026-10-21 Soul owner source audit refresh

The current Soul source, anchor, fact, vulnerability and bounded effect owner
selection was rerun against the shared worktree:
`python -m pytest -q -p no:cacheprovider backend/tests/test_soul_anchor_owner.py backend/tests/test_soul_fact_owner.py backend/tests/test_soul_vulnerability.py backend/tests/test_soul_effect_owner.py backend/tests/test_soul_presence_sources.py backend/tests/test_soul_resource_sources.py`.
Result: **97 passed in 20.03s**.

This is a fresh regression result for the existing owner slices only. It does
not promote D10 to production: `app/main.py` still has no trusted Soul package
composition or original-action/L4 caller, `Settings` has no Soul registration
surface, and no production message route issues or consumes Soul facts/effects.
The design requires an explicit trusted composition issuer, real Presence and
Resource source cuts, registered life/mind semantics, and a shared durable
receipt before R14 or the final Godot gates can advance. No fixture-only
registration, accepted choice, or owner unit test is counted as that missing
production boundary. No model evaluation, training, full pytest, Harness all,
or Godot operation was performed in this refresh.

### 2026-10-21 慢目标新进程恢复复现

为验证 Task 3/R09 的新进程恢复，构造了真实 `configure` + SQLite 持久目录：第一进程提交合格 `goal_proposal_trigger` 并冻结 `provider_pending` 请求，第二进程安装 provider 后从同一 admission 继续处理。冻结 `request_json`、admission key 和终态 owner 边界可恢复；重开诊断发现 `actor_pin` 的 `l1`、`last_cognition` 和 `timeline` 不同，安全校验返回 `cognition_provider_stale_pin`，没有新 goal event，拒绝终态仍经原 owner 回执保存。随后 session recovery 已加入 settlement 私有 L1 projection 与 cognition cadence 恢复；这修复了已隔离出的 projection 缺失，但尚未证明真实自动轮询启动时 `actor_pin`/timeline 与 session head 一致。差异仍需在启动轮询前后分段采样，不能假定私有 projection 修复同时解决 timeline。`actor_pin` 在 coordinator prepare 中采集，晚于 trigger 入库，不存在已证实的 pre-trigger 采集问题。测试草稿已撤回，未计为绿色证据。R09 及慢目标 production recovery 保持未完成；下一步隔离启动自动轮询和历史原始输入，复验原 entry/private projection 与 session head，保留 stale 防护。

### 2026-10-21 canonical context 私有快照恢复增量

本轮只验证已提交 session current-state projection 的恢复边界：`character_turn_stage_recorded` 的 canonical `context` stage 现在校验并保存 `private_snapshot`，runtime-state flush 允许保存 `last_cognition_tick`，重开 runtime 时恢复二者。定向命令
`python -m pytest -q -p no:cacheprovider backend/tests/test_character_session_recovery.py backend/tests/test_character_slow_goal_main.py`
结果为 **55 passed, 4 warnings**。

这证明 canonical turn context 的私有 L1 快照和 cognition cadence 可从同一 session 目录恢复；它不证明慢目标生产 worker 的 actor pin、timeline、provider pending 或终态 owner receipt 在自动启动轮询下完整一致。R09、完整 Laya/领域 owner 回执、模型质量和 Godot 门继续未完成。相关 runtime 改动与测试仍混在用户已有 `runtime_loop.py` 历史修改中，本批未形成独立提交；不得将其视为已关闭的生产恢复批次。

**后端**：D10 既有 source/anchor/fact/vulnerability/effect 局部 owner 回归
97 项通过；生产 composition 与 L4 caller 仍未实现。**模型质量**：Q01–Q04
无新增验收。**角色闭环**：R07–R09/R14 未升级。**最终 Godot**：G-A/B/C
未操作，仍为最后门禁。

## 当前优先缺口：完整动作与目标来源审查（2026-10-20）

### 2026-10-21 Laya action/target admission regression refresh

为复用已有实现并确认当前边界，运行了窄范围回归：
`python -m pytest -q -p no:cacheprovider backend/tests/test_dialogue_object_dispatch.py backend/tests/test_character_execution_source_admission.py backend/tests/test_character_candidate_compiler.py`
→ **77 passed in 6.71s**（4 条既有 FastAPI deprecation warnings）。

该选择确认 DialogueSubmit 到对象动作分发、执行来源准入和候选编译的现有 fail-closed 约束仍稳定：缺少有效来源、条件为 blocked/unknown/unavailable 或合同/目标不匹配时不进入执行。它仍是合同与边界回归，不是新的真实 Laya 调用、完整 action+target→L4→领域 owner receipt、恢复/回放或正式 Q01–Q04 证据；没有升级 R07–R09、模型质量或 Godot A/B/C。下一步继续消费真实、来源明确的动作/目标输入，接入尚缺的领域 owner caller 和共享回执，而不重复扩展同一局部 parser/compiler 测试。

### 2026-10-21 combat owner production-ingress audit

The canonical faction/Threat/encounter owners and the durable embodied combat
adapter remain an API and focused-owner slice. `street_combat_attempt` in
`backend/app/main.py` still settles only through the existing embodied owner
and publishes a perception event; it does not construct an authenticated
`CombatSourceContext` or consume the committed hit through the canonical
Threat owner. `CharacterCombatTargetCatalog` therefore keeps combat targets
fail-closed (`supported_intents=[]`, no owner route). This is the correct
boundary until a real L4 contact evidence path and production Presence,
LifeState, and Faction source composition exist; no physics or faction fact is
fabricated to close R07/R08 or D08.

Focused verification of the existing dirty owner slice was rerun with:
`python -m pytest -q -p no:cacheprovider backend/tests/test_combat_durable_adapter.py backend/tests/test_combat_settlement_threat_consumer.py backend/tests/test_street_combat_durable_owner.py`.
After minimally composing the untracked Threat fixture with the production
`ActivationSourceReader` contract, the selection is **20 passed** (adapter 13,
Threat consumer 5, street owner 2). This verifies the controlled backend
owner-to-Threat consumer and durable replay fixture only. It does not prove a
live L4 contact source, production `street_combat_attempt` ingress, Laya choice
or owner receipt, and it remains non-acceptance evidence for R07/R08/D08.
The production ingress is still open; Godot remains deferred to the final A/B/C
gate.

### 2026-10-21 slow-goal stale owner receipt follow-up

Driver stale handling now uses `terminate_goal_proposal` for an existing
goal-proposal stage, preserving the atomic terminal receipt/progress contract.
If activation is temporarily unavailable, progress remains pending for owner
retry rather than becoming a receipt-less terminal. Existing failed/cancelled
terminals are preserved. The focused nine-file slow-goal/driver/admission/trigger
selection passed **78 tests**, exit 0 (9.27s), with `-p no:cacheprovider`.
This worktree test does not prove production expiry/source-revocation cleanup,
real provider dispatch, same-actor fast coexistence, or fresh-process recovery.
No external Harness archive was generated for this narrow regression batch.

**后端**：终态事务接线局部修复，生产闭环仍开放。**模型质量**：Q01–Q04
未新增验收。**角色闭环**：慢目标→Laya→多领域 owner→恢复仍未验收。
**最终 Godot**：A/B/C 未操作，继续最后集中验收。

### 2026-10-21 production slow-goal lifespan composition

The production lifespan composition now has a fresh controlled-provider
regression in `backend/tests/test_character_slow_goal_main.py`. It constructs a
committed actor-private repeated-failure trigger, dispatches through the
production cognition driver while the provider is delayed, then releases the
provider and observes the original Character goal owner commit one
`goal_state_event` at producer timestamp 103 plus the completed terminal
receipt. The test passed **1 passed in 4.54s** with
`python -m pytest -q -p no:cacheprovider backend/tests/test_character_slow_goal_main.py`.

This closes only the production composition/terminal-receipt subitem of the
slow-goal path. The provider is controlled, the model is not scored, and the
run does not prove same-actor fast work under real Laya load, fresh-process
replay, downstream Laya action+target→L4→domain-owner closure, formal Q01–Q04,
or Godot A/B/C. The broader slow-goal selection also passed **138 tests in
13.78s**; its known MindFrame rebinding assertion is excluded from this count
and remains an unrelated pre-existing mismatch when actor and turn are changed
together. No full pytest, Harness all, model evaluation, training, or Godot
operation was performed.

**后端**：慢目标 production lifespan dispatch→Character owner terminal receipt
子项已通过；完整后端闭环仍局部。**模型质量**：Q01–Q04 未新增验收。
**角色闭环**：R01/R07/R08/R09 仍缺真实 Laya 原动作、跨领域 owner、回放与
完整输入质量门。**最终 Godot**：A/B/C 未操作，仍为最后门禁。

### 2026-10-21 same-actor fast admission seam

Added a driver-level regression that leaves a slow goal proposal at
`provider_pending`, confirms its actor activation is released, then advances a
same-actor fast cognition admission through the L2 provider boundary. The
focused selection across slow-goal dispatch/terminal, cognition driver,
coordinator, atomic acceptance, admission and trigger tests passed **71 tests**
(`python -m pytest -q -p no:cacheprovider ...`, exit 0).

This verifies scheduling at the driver seam only. The test uses controlled
coordinator/admission collaborators; it is not evidence of a real delayed
provider running alongside production Laya or of acceptance under unchanged
source pins. Production fast/slow coexistence, provider-result owner receipt
and fresh-process recovery remain open. No model call, formal quality run,
full pytest/Harness all or Godot operation was performed.

**后端**：同 actor fast admission 的 driver seam 已测；生产共存与回执恢复开放。**模型质量**：Q01–Q04 未验收。**角色闭环**：真实慢提案到 Laya、多领域 owner 与恢复未验收。**最终 Godot**：A/B/C 未操作，仍为最后门禁。

### 2026-10-21 slow-goal admission increment

Follow-up wiring repair: the production composition now derives the cognition
policy pin from `CognitionPolicy.revision_pins["policy_revision"]` (the policy
model has no top-level `policy_revision`) and forces the committed trigger event
ref into the admission `evidence_refs`. The focused slow-goal selection is now
**74 passed**. This removes two deterministic admission failures, but it is
still only a production wiring increment: a real backend settlement→provider→
original goal-owner receipt, restart recovery, live Laya action/target closure,
formal Q01–Q04 quality, and Godot A/B/C evidence are still absent.

The runtime hook now has a focused composition-level regression: three committed
actor-private rejected settlements produce one committed trigger source, preserve
the final source ref in `evidence_refs`, and pass the same frozen frame digest to
the admission bridge. The combined selection is **75 passed**. This proves
trigger-source construction and idempotent selection at the runtime seam only;
provider execution, terminal owner receipt, restart recovery, and Laya/Godot
acceptance remain open.

Character slow-goal admissions now have a production-shaped result boundary:
`goal_proposal_trigger` is prepared by its dedicated coordinator path; the driver
routes provider output through source/evidence/context/provider-pin validation and
persists `result_ready`; a later poll performs the existing resumable goal owner
commit. Focused slow-goal driver/coordinator/transition/atomic tests are **37
passed** after activation release, deferred re-acquisition, and provider-failure
termination coverage. This is a local character state-machine seam only. It does not establish
a production trigger producer, complete Laya action+target→L4→domain-owner receipt
and recovery, Q01–Q04 model quality, or Godot A/B/C.

The bounded trigger derivation slice is committed as `5ab38894`: it derives
`repeated_failure` and explicit actor-private failure markers from committed
settlement outcomes and deliberately ignores L2 `goal_hints`. Focused producer
coverage is **2 passed** (10 passed with the behavior-turn recorder selection).
This remains **局部实现**: the runtime hook still needs a turn-bound frozen
MindFrame, and main composition still needs a dedicated
`goal_proposal_trigger` admission/activation branch. Until those are connected
through the existing coordinator/driver and owner receipt path, production slow
goal closure is not claimed.

The proposal context contract also now keeps expiry in the admission wall-clock
domain (`ca1789f3`); event `producer_ts` remains an event-time value and is no
longer compared directly with expiry. The focused contract/coordinator/admission
selection is **68 passed**. This removes a cross-domain validation defect but
does not advance the production-trigger or Laya/Godot acceptance rows.

以下是生产能力的剩余依赖，不把旧的三选项信息诊断包扩充后冒充完整动作集。

| 路径 | 当前实现及来源 | 下一验收依赖 |
|---|---|---|
| ESM inspect/use/finish | `main.py` 将当前 `CharacterObjectExecution.project_character_targets` 绑定到 L1；连接原 ESM descriptor 与同 scope 新鲜、绑定有效的 spatial source；原 owner/state digest 和 receipt/recovery 复用 | 已有位置映射的对象可取得肯定 range，缺失/过期/撤权/跨 scope 为 unknown、远距为 blocked；完整跨目标/连续选择和正式质量仍未验收 |
| 其他目标动作 | `_candidate_records` 已要求显式目录；`_expand_domain_candidates` 只补 use_object/finish_use；生产 resolver 提供 ESM 动作目录及只读 canonical combat 来源；combat 尚不授予动作 | 从各自真实 owner/registry 与私有感知补动作专属目标和版本，不把 attention 或当前玩家转成授权 |
| 战斗/Boss | 复用 `canonical_combat_authority.py` 的 faction/Threat owner 和 `combat_durable_adapter.py` | 正式 faction/target source、角色原合同与 owner caller；physics/contact 留最终 Godot，不用测试事实补造生产来源 |
| 信息/移动/协同 | L3 存在动作字符串与本地合同 | 各自 recipient/空间/协同来源、owner 路由与回执，不能把 ESM 目标共用为所有动作的接收方 |
| 质量准备来源 | 旧 `prepare_character_evaluation.py` 仅 authored observe/ask_probe/defer，owner unassigned，空 envelope/policy；runtime trace exporter 仅真实 ESM 成功边界开发来源 | 新完整 action+target 来源、独立分组与评审，再 calibration/freeze/final/holdout；旧开发或已暴露输入不可补入独立集 |

**已修复的生产候选缺口：** CandidateCompiler 原来只检查 visibility，明确否定的 consent/privacy/contact/range/permission/availability 仍可进入 U/P。本批按现有条件协议拒绝 blocked/unknown/unavailable 和非法单项值，诊断保留 condition；真实 L3 准备→typed snapshot→冻结 provider 输入回归证明拒绝继续传递，合法 observe 保留。既有 `required` 表示延后核验，缺字段兼容也保留；两者都不证明肯定准入，因此不关闭 R05，也不改变规格05要求的最终门槛。旧 v4/v5 描述协议不变；新编译结果的诊断/摘要应以新来源记录，不刷新旧正式来源 hash。

证据根仍为 `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/`。RED `afe42c71c368459b9cd8de9a22757ef4`：30 failed/1 passed；工作树 GREEN `334555a5b3474626a4f5ed006d4c214a`：56 passed。首次隔离 `4adc9e50dbdf48ffa9712754c21ff3c7` 因选入未提交的历史 `test_character_owner_target_projection.py` 而 exit4、零测试，保留失败，不采用该文件。修正为四个已提交选集，精确 HEAD `f4bce4a0` 加本批两文件隔离 **110 passed/4 FastAPI 既有 warnings**，run `db76736909f4435e84d5708c88cf6550`，目录 `candidate-conditions-isolated-fixed/`；均 cleanup passed。未运行全量 pytest/Harness all、模型、训练或 Godot。

backend-contract `b66d4c422df44094b5ef2ffa8708dc07` passed/cleanup passed，导出目录 `candidate-conditions-contract/`。后端仍局部；Q01–Q04 无新增质量通过；角色跨领域完整闭环未通过；Godot G-A/B/C 未操作、未验收。下一项是已有可信空间来源与 ESM 候选 range 的生产映射，继而回到正式 faction/target 与角色 owner caller；不要继续扩展条件编译器测试来替代这些缺口。

## 当前批次：真实 Laya worktable 与原 owner 来源关联

精确 HEAD `0f6bb4a4` 真实 backend/认证 WS→原 L2 local baseline→官方 Laya→原 L4/ESM，run `ab243b0d77a7451d94d4d6d46b32ef5b`，目录 `laya-worktable-current-head-diagnostic/`。第一回合真实选择 use_object:obj_worktable，原 owner 提交 transaction:esm-object:5efe5d357f4378db0475365744a690496317250267f93e6fc161f855e4d8ba90；第二回合候选含 finish，但选择 observe。输入分别6383/7927 tokens，无截断或丢弃。独立新进程重开原 session/gameplay store，两次 exact retry 恢复同一原回执、零新 world 写入，状态 engaged。输入只有 generic visible/available，L2 原输出为 continuity_floor/local_only_stub（interpretation_type 为 cognition_unavailable）、目标 preserve_continuity，没有显式完成任务，因此不把 observe 判作正式质量失败，也不宣称连续 use→finish 通过。空间样本来自认证开发控制器，不是 physics/Godot 证据。

保留原 trace 与 owner JSON 后发现 exporter 重建 request 的 source.system 错用 character_agent，原 L4 实为 character_agent_l4，造成 owner_request_mismatch。修复精确身份，不放宽 owner digest。原 L3→L4→owner 受控 use/finish 回归 RED `3cee9da0928944f3a727f70768cede5c`（1 failed）；精确 HEAD 加本批两文件 GREEN `5a73187d830b42e1a36d8bc99011b032` **88 passed/4既有warnings**，目录 `live-owner-request-green/`。同一 live archive 无新增模型调用重关联：RED `3f88fb4bb7314fc5a60f2007e0e1e80f` accepted0，GREEN `49a420503dab4150b7c13195bfeaa727` accepted1/snapshot_matched，observe 正确为 execution_missing。snapshot_matched 只证明供应资料一致，不证明独立真实性或质量；exporter recovery 仍 unverified，新进程证据单独记录。backend-contract `c5ef2d90976d464fa07eb3777a220ec2` passed；上述 run cleanup passed。证据均在既有仓库外根目录。

后端：原请求关联缺陷修复，领域仍局部。模型：仅 development，Q01–Q04 未关闭。角色：R08 增加当前 live use 原 owner 快照关联，R09 增加该 use 独立进程 exact receipt，连续与多 owner 仍开放。Godot A/B/C 未操作、未验收。未运行全量 pytest/Harness all、训练或正式隔离集；官方模型服务和本轮 backend 已停止，临时副本已回收。下一项从真实任务/目标与 L2 来源补角色输入，不重复模型调用碰运气或扩大 exporter 测试。

## 判定与证据复用

### ESM 候选距离来源接线增量

生产 resolver 现在先取得原 ESM 动作专属 descriptor，再读取当前 actor 的内部 authored scope 与现有 `EmbodiedSpatialSource`。只有同 scope、控制器绑定仍有效且新鲜的来源以及已有 owner 位置映射才能生成 `range=satisfied/blocked`，并保留 spatial event ref；其他情况为 unknown，由原 compiler 拒绝。typed L1 snapshot roundtrip→L3 冻结 provider 请求验证了近距候选保留、远距/过期/撤权/缺失/跨场景候选排除。owner admission digest 继续只表达原 owner/state，执行时仍重新读取 source 并参与原 owner CAS；旧 receipt 恢复顺序未改。source 只证明有界控制器证据接纳，不证明独立服务器 physics/contact。

RED run `7d1e5035224448de802e40fec2cc3056` 为缺少 resolver 方法的6项失败；该次日志导出因 pytest 链接被拒，顶层报告 cleanup failed，不计作完整导出证据。首次 GREEN `a7a30e1040de4d32875e364a8f87a75f` 为43 passed/2 failed：远距测试选了无 inspect policy 的对象、重启测试仍断言旧 resolver；修正为真实移动样本和当前 owner/source 绑定，不放宽产品约束。工作树 `5b33f87284654401aeb5271b09b60355` 102 passed。精确 HEAD `e3a5cf36` 加本批4源码/测试文件隔离 `1ff4684984624fe99ac3638bcc355b27` **102 passed/4既有 FastAPI warnings**，证据 `spatial-candidates-isolated/`，保存源码 SHA256/命令/exit；backend-contract `b4fb9faa545c46cca31deac1a2092b9a` passed，目录 `spatial-candidates-contract/`。后续运行均 cleanup passed，未收编 main.py 其余历史混改。

四组状态：后端仍局部实现，新增上述肯定距离子项；模型 Q01–Q04 无新增验收；角色 R05/R07–R09 的完整动作跨域与连续链仍开放；Godot A/B/C 最后且未操作。未运行全量 pytest/Harness all、模型、训练或 Godot。下一项回到正式 faction/target source 与角色原合同的 owner caller，不重复扩大 compiler 或已验收 worktable recovery 测试。

- **已完成**：仅指该行精确能力与证据边界已满足；不自动关闭所属阶段。
- **局部实现**：已有可复用实现／局部合同，生产接线或剩余语义仍缺。
- **未验证**：实现存在，但所需真实运行／质量证据未取得。
- **未实现**：当前调用链或 owner 能力不存在；不能用新增测试数量代替实现。
- 既有报告仅复用其输入、来源、实现和参与范围仍有效的部分。修改实际依赖后重验相应路径，不为刷新日期重跑无关领域。矩阵中的历史质量统计保留历史身份，不能充当本轮 final。
- 不统计无依据百分比；报告按后端、模型质量、角色闭环、最终 Godot 四组逐行说明。整体完成要求所有在范围必验行满足；明确延期项不偷偷降格为已完成。

## 一、后端与领域

| ID／来源 | 当前状态 | 可复用实现与证据入口 | 剩余工作与验收条件 |
|---|---|---|---|
| D01 时间／迁移；规格09、计划04 Task1 | 局部实现 | `simulation_clock`、temporal mapping/profile、Population cadence；closure 的 Task1 consumer 矩阵 | 逐个实际 consumer 的 source/clock/revision/expiry/grant 与 receipt；保留 world-time 和 operational timeout 分离，不另造 clock |
| D02 管理员 cadence 撤权生产入口 | 局部实现（持久撤权应用链已收编并验证） | credential/verifier、HTTP→spawn child→RuntimeExecution→原 cadence owner 已接线；原回执重开恢复见本轮 D02 增量 | Inventory consumer 原准入关联、撤权读集/CAS 已定向验证；完整时间 grant 与生产投递仍待收口；真正部署 credential/TLS 尚未验证；本行不代表通用 capability/facility grant issuer 完成 |
| D03 SettlementWindow／owner 批次；规格09 | 局部实现 | Population→Inventory custody、Economy tax/calendar、Ecology temporal、Status/Action；[stage3 closure](stage3-closure-20261016.md) | 复核正式启用 consumer 的完整 read-set、cutoff/order/late-input、原子 owner receipt 与重启；不能从一个 consumer 推全域 |
| D04 T07 随机业务；计划04 Task2 | 局部实现 | Economy random owner、版本化 policy、typed self-draw ingress、random replay participant | authenticated lottery/loot/event-choice 实际 producer、公开交付与收据回流；不能把 fixture demand 或 controller binding 当正式业务来源 |
| D05 T09 prediction；计划04 Task2 | 局部实现 | Equipment command/prediction typed ingress、ledger、confirmation、Durable recovery | 正式 demand producer、确认/撤销/冲突与真实 owner receipt；不能把 preview promotion unsupported 改写为通过 |
| D06 资源集中迁移；规格10、计划04 Task3 | 局部实现 | ResourceTemplate materialization、world-time recovery、reservation、modifier interval、v2→v2 migration、conversion；`infra-resource-world-time-recovery` | 正式 capability issuer、Modifier→Resource admission、debt/modifier/conversion 完整生命周期、统一 consumer pins 和集中切换；先复用现有 owner，禁止平行资源真相 |
| D07 状态／效果／装备；规格10 | 局部实现 | Status lifecycle、equipment activation/command、effect/stat projection | 实际角色动作消费的权限/版本/失效链、效果与资源真实 owner 回执及恢复；全领域集中切换不能由装备单例代替 |
| D08 技法／多 owner／物理；规格11、计划04 Task4 | 局部实现（authenticated faction HTTP 来源与进程重启已验证） | 已提交 ESM、street embodied owner、faction owner；Durable combat adapter、canonical Threat/encounter 仍为历史草稿 | target eligibility 与角色合同接线、encounter/Threat 实际 producer；真实 physics/contact 证据在最终 Godot 阶段取得，禁止伪造 |
| D09 LifeState／Presence；规格12、计划04 Task5 | 局部实现（初始 alive 生产组合与重启恢复已验证） | 既有 LifeState/case-death 草稿；本批采用初始 alive owner、显式 grant、绑定 producer 的 RuntimeExecution Activation→Presence→alive、incarnation/replay | 正式场景 source 与角色私有投影/target eligibility、迁移恢复；不从 HP 或 profile 推死亡事实 |
| D10 Soul／identity；规格08/12 | 局部实现（来源、anchor、事实生命周期、vulnerability 与 bind/unbind 四门 CAS） | soul_sources.py、soul_presence_sources.py、soul_runtime.py、soul_fact_runtime.py、soul_vulnerability.py、soul_effect_runtime.py；本轮事实注册快照、版本隔离、原 anchor cut 与重开回执测试见下 | 完成生产 Life/mind 注册语义、其余有限 effect/value operation 与 counterplay、生产四门 admission、正式 schema/composition、checkpoint/common-cut/private projection 和生产角色/L4 接线；当前 issue/revoke 仅为事实生命周期基础，不代表效果执行权限 |
| D11 全域 replay 与故障；计划04 Task6 | 局部实现 | 十领域 shared Durable cut、具名 participant matrix、Task6 fault allowlist | 全部本次正式准入 owner 的同一 global atomic cut，以及恢复/迁移/权限/隐私 parity；42 participant 独立测试不等于共同 cut |

## 二、角色与 Laya 闭环

### 本批新增证据（2026-10-20）

`obj_worktable` 的 `use_object`/`finish_use` 已接入同一私有目录、CandidateCompiler、L4
canonical contract 和 durable ESM owner。ready→engaged→ready 状态循环、动作专属
admission digest、单目标/动作组合校验、owner receipt、旧合同 exact retry 和无写入拒绝
通过当前工作树定向回归 **47 passed**。精确 HEAD＋暂存批次及已提交数据资产隔离
run `675f93eed4f545fc9ecc7d706c02a19c`：本批五文件80项通过；额外旧合同文件共得
**89 passed/1 failed**，失败是 `obj_letter` 未获准仍期待 settlement 的历史预期；
原样 HEAD 复现 run `e39e1dd0a0614e509aed6235cc8505dd`（1 passed/1 failed），不宣称
扩展套件全绿。两次 cleanup passed。先前归档遗漏manifest和Windows路径长度失败只作
隔离脚本诊断，不当产品绿色证据；旧run `c0c28134270c44ce8e21d9a5f9848c93`早于最终修正。Harness
`backend-contract` run `20c68e3bb7144abfa592c2a64939bdb9` 与 `docs` run
`eeb0f37f29c844d2a6ad08e15c86f3c0` 均 passed/cleanup passed。
这只把 R05 的 worktable 动作目标切片从“inspect 输入”扩展为“局部已实现”，并把 R07/R08
标记为仍局部：尚未证明真实 Laya 服务选择、完整输入预算、跨领域 owner、live backend
边界、回放，以及 Godot 可见结果。

| ID／来源 | 当前状态 | 可复用实现与证据入口 | 剩余工作与验收条件 |
|---|---|---|---|
| R01 turn／MindFrame／ThoughtMode；规格01–03、计划01 | 局部实现 | turn coordinator、frame builder、cognition coordinator/driver、frozen session stages | 同一真实 turn 的 source→frame→L2/L3→Laya→执行→owner receipt→writeback；background cognition 继续 commands=[]；资源模板 tuple 进入 L2 缓存破坏 JsonValue frame 的问题已从 profile JSON 序列化入口修复，8 项 frame 回归通过 |
| R02 memory；规格04 | 局部实现 | recall、semantic cards、writeback policy、consistency/recovery tests | 真实 outcome 与 authority receipt 绑定，重复、冲突、重开不重复沉淀；保留隐私与来源 |
| R03 官方 Laya 服务与 choice | 已完成（历史 bounded 链路） | `gateway/laya_provider.py`、gateway、[RW-34](backend-choice-foundations-stage3-20261015.md) | 复用服务及接纳证据；首回合为 cognition_unavailable physiology_hint，第二回合空命令，不能计入动作执行 |
| R04 完整输入与预算；规格05、计划01 Task1C | 局部实现 | 完整 token budget gate、RW-32 修复后 22 条无截断诊断 | 生产 L3 默认完整输入预算门已启用（c3fbbf27）；正式运行 tokenizer/config 冻结、同 request usage/pins 仍待真实模型验证，不能靠静默截断解决 |
| R05 完整 U/P 与动作＋目标 | 局部实现（ESM inspect/worktable 输入） | 私有 visible refs/source/catalog、ESM inspect/worktable policy 只读投影、生产 reset 绑定同一 ESM、原 CandidateCompiler | 已补原生产目录缺口的 inspect 切片及 worktable `use_object`/`finish_use` 局部切片：typed roundtrip、action-specific supported intents、空 visibility 拒绝、scope 隔离与 owner 状态 digest；其余领域动作、完整策略覆盖与执行时 revalidation 仍缺，不得用 attention 或当前玩家猜目标 |
| R06 能力包络／cognition policy；规格05、计划02 Task1–3 | 局部实现（durable Siming、三类同步入口及 background L2/L3 同源合同已验证；stage typed 正文/身份校验增量见下） | stable ability、CapabilityEnvelope、CognitionPolicy；durable Siming 与 background 在 L2 前冻结真实 registry/profile/dynamic 来源，L2/L3/L4 同 turn；background 保持 commands=[] | 冻结召回总条数与既有 token 估算预算已覆盖 L2/L3/gateway；background/dialogue/模型总输入硬预算、真实 memory/input revision、完整 frame/source 对齐仍缺；不能由 digest 一致推断认知差异或模型质量 |
| R07 选择→非 fallback 原动作 L4；规格07 | 局部验证（真实 Laya inspect 与 worktable use 切片） | frozen candidate map/digest、canonical execution contract；run 4f2816ada4884a7dabab3644ff878564 | 实际 Laya 选择的 action+target 与非空原动作合同一致；不能由 fallback physiology_hint 或 accepted ack 替代 |
| R08 L4→owner→反馈 | 局部验证（真实 Laya＋plaque inspect；在线 L2＋Laya worktable use/finish 与新进程恢复）；完整闭环未验证 | `CharacterObjectExecution`、main egress/ingress、ESM shared-store receipt、session dispatch-offered event | 原合同来源、后台派发期限、当前私有目标/scope/digest及空间 read CAS后真实 owner提交并回写；worktable use 已有真实 Laya→L4→owner 回执；新增在线 L2/Laya 的真实 use→finish 连续周期及两份原回执新进程零写恢复；显式任务驱动、生产产出和完整多域仍缺。真实 Laya原动作、多领域权限/生命周期、完整动作和真实 physics仍缺；不以合同测试代替完整纵切 |
| R09 中断／恢复／回放 | 局部验证（真实inspect及在线L2/Laya worktable两动作提交后新进程exact receipt恢复）；完整故障/回放未验证 | durable cognition/session、frozen resume、取消迟到负例 | owner 提交前后中断、新进程重开 exact receipt replay、changed duplicate、旧 worker 迟到零写、writeback 不重复 |
| R10 学习／技能形成；规格06 | 局部实现 | registered learning owner前置39项；owner→冻结能力/旧provider拒绝/生产读取176项；生产inspect个人动作披露与来源owner/consumer回归141项，见下文 | 四学习路线仍缺完整生产source/episode/gate→owner策略、时间/资源/teacher与grant撤销准入、正式mastery语义与共同cut。工程模型训练不产生角色技能事件 |
| R11 regulation／五通道／episode；规格08 | 局部实现 | regulation projection、expression/observation episodes、资源私有投影 | 真实来源/权限/回执与消费接线；无来源 band/formula 继续 unknown，不凭空填生理结论；可见/听见最后验收 |
| R12 协同／短契约；计划03 | 局部实现 | local coordination signal/contract、recipient filtering | 真实 fact consumer 的可信时钟/context revision/participant 状态；双角色实际接收与连续协同回执 |
| R13 SpeechLease／三路径语音 | 局部实现 | lease、dialogue continuation、TTS adapter | preset/catchphrase 目录、三路径 dispatch、取消/迟到；音频生成不等于空间 played/heard，听见证据最后验收 |
| R14 精神资源／Soul 角色回验 | 局部实现 | Resource/L1 private projection 与缺 owner 拒绝 | D06/D10 就绪后回验；不能另造角色私有 Soul truth |

## 三、正式模型质量

| ID | 当前状态 | 已有证据与限制 | 剩余验收 |
|---|---|---|---|
| Q01 诊断与归因 | 未通过（质量）；位置／标签归因已有新增证据 | [calibration repair](calibration-repair-20261014.md)：autonomous 0/8、explicit diagnostic 0/6、role-sensitive 1/8，未达冻结 6/5/6；新增同版官方模型66次已暴露诊断，见文末；不是 final/holdout | 候选反序改变15/22语义选择，循环重标改变12/22；继续核查输入呈现与官方 checkpoint layout，不直接归因为需训练，不择优顺序冒充质量修复 |
| Q02 来源／隔离／冻结 | 局部实现 | evaluation/calibration contracts、prepare/freeze/run/score 工具；four_role_lock_event 只有 dev trajectory，正式 splits 为空 | 审查原始 source drift，登记新版本而非直接刷新 hash；构造有来源的 dev/calibration/final/independent_holdout，trajectory 隔离、threshold/预算/freeze 先于评分 |
| Q03 完整 action+target 质量 | 未验证 | 既有 22 条信息诊断的 runtime legality/owner receipt 分母为 0 | 完整包络后正式动作/目标/U/P 覆盖与角色轨两轨验收；真实 receipt 与质量评分分列 |
| Q04 final／holdout | 未实现（正式数据集与验收） | 旧轮次关闭已由当前授权解除；不能重用暴露 calibration 为独立集 | 独立来源、冻结、无 truth transport、封存后评分；不自动训练/微调，若必要先提出有证据方案 |

## 四、最终 Godot（后端收口后集中执行）

| ID | 状态 | 接口／场景与证据要求 |
|---|---|---|
| G-A 单角色跨情境 | 未验证，暂不操作 | raw/visual fact ingress、character_agent_output/execution、所选 action+target、owner receipt、事件变化后的新 turn、重启；真实 boundary 消息＋可见结果；复用合格 actor/motion assets |
| G-B 单角色连续 Boss | 未验证，暂不操作 | canonical embodied action/physics、LifeState/Presence/Threat/encounter、资源状态持续消耗/恢复、Boss 连续阶段；非脚本伪成功、receipt＋画面 |
| G-C 双角色连续协同 | 未验证，暂不操作 | B 能力＋真实 coordination/contract/接收方 L1/语音取消；两个独立 actor 保留身份，连续协同、失败/恢复；boundary＋各 owner receipt＋可见结果 |

任一必需 boundary、receipt 或 visible evidence 缺失，整体 Goal 不得 complete。后端定向 profile 不替代 A/B/C。

## D06／D10 来源依赖：正式采用静态资源 genesis（2026-10-20）

- 提交 `8af22a6a`：经审查采用已有 authored resource template、三角色资源块、v2 projector／有限 reservation／migration planner 及聚焦测试，未重建第二套 Resource owner。materialization 原 source snapshot 随真实 owner 事务持久化；无当前模板的新进程可恢复原 receipt，changed request、跨 world 重物化、非法 read-set 零写拒绝。修复容量边界、孤立 lock、完整 action 原事务校验及校验后重读 head 的竞态。
- 精确 `77fd4bb`＋13 个源码快照隔离：110 passed，run `70500ea8636946ef8b8d955d6a65071d`；backend-contract `0d23b439fe2647f8a80b5f161de1159e` passed；docs 修正后 `bb056c07e2cf40578f7a855b9c5904c8` passed；均 cleanup passed。证据根 `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/` 下 `resource-genesis-final/`、`resource-genesis-contract/`、`resource-genesis-docs-corrected/`。stage 的归一化源码 SHA 与隔离 manifest 逐项一致。
- 保留真实失败：恢复 RED `00d135e3ef6f48b6b08c192e0603607f` 两项失败；caller/profile/别名 RED `32fc8c045d7040299b669ab2e6aaa60d` 三项失败；owner 审查 RED `584e730c527547268be08b0c14c4eaf0` 七项失败（工作树，非 HEAD 隔离）。首次 docs `7d98ed7c5e9849288e21599eeb1e8d23` 缺同名计划，已添加关联主计划的 Soul 实施计划后通过，不以盲重试消除失败。
- 范围：新 materialization 仅接受无时限静态 authored 模板；registry 深拷贝按服务 composition 冻结，重新部署更换内容，不声称热更新撤权原子性。调用方 tick 不是 confirmed world time；模板内 issuer/publication key 是内容元数据，不能当 publisher receipt 或 Soul grant。actor-global Resource stream 绑定首个 world/timeline，迁移未验收。三种 core 资源不自动代表 life/mind vulnerability。
- D06 仍局部实现：生产 caller、confirmed time、恢复／转换／modifier 等对应独立 owner 与全域共同 cut 仍按原矩阵验收。D10 完整 owner 仍未实现；source/Presence/anchor/fact/vulnerability/bind-unbind 窄片已有独立证据，见 [Soul 设计](../../superpowers/specs/2026-10-20-bounded-soul-owner-design.md)。下一步为生产 composition、真实 life/mind 语义来源、confirmed-time/common-cut/private projection 与角色回验。
- 模型质量：没有新增评分或质量通过证据，Q01–Q04 保持原状态。角色闭环：没有新增完整 Laya／L4／Soul receipt 链，R14 不升级。Godot：未修改、启动或操作，G-A/B/C 均未验证。没有全量 pytest／Harness all、模型调用或训练。历史工作区和 `.harness` 内容保留。

**Soul Resource 来源适配器提交 `0d10856a`：**固定接受已准入 materialization、action settlement、reservation 三类 owner 的原完整事务；核验原事件、schema、receipt、companion、摘要与 world/timeline 绑定，拒绝 probe／fixture、伪造单事件和未支持 producer。读取冻结 canonical head（含空 head0）并返回完整事务证据/cut 上界；资源不存在保持 unavailable，版本不匹配拒绝，不从 stamina/mana 推 life/mind。实际 genesis→action 与 reservation consume、SQLite reopen 均通过；适配器没有 Soul 写入、授权或生产 L4 接线。精确 HEAD＋两源码隔离84 passed，run `764fb9d4323b48da8c0eb19347bbc102`；backend-contract `b026b0f62dbf46789649be6f25b8bd03`、docs `4ebd081316884873a6d6e5b58d265325` passed；均 cleanup passed。外部同根 `soul-resource-sources-final/`、`soul-resource-sources-contract/`、`soul-resource-sources-docs/`。缓存后 membership RED `70855409cd7a4a63b51320d045325ca0`、版本／摘要 RED `e7b12dadb8a643e3b28024da25ffaecc` 已修复；最初缺适配器 RED `2b05aab008ca4952a280a7f7742f8807` 保留。D10 完整 owner 仍未实现；下一项是 Population/Presence anchor source，随后真正的规则事实 owner 与 gate，避免继续扩展此局部测试。

## 排除与保留

阶段四、通用编辑器、AD/Blender、自走棋及明确延期内容继续排除。facility repair 的四项明确 deferred 决策保留，不自动恢复，也不拿它阻塞不依赖它的角色纵切。旧轮次 choice-only／禁止模型评估／只做阶段三等限制不再限制本目标；authority、隐私、来源、隔离与 freeze 规则永久保留。

历史修改和历史证据不删除。当前工作区原有约 429 条 dirty/untracked，提交只按确认的文件/patch 分批组织；提交不代表整工作树已可独立发布。

## 本轮管理员收尾与提交

- 提交 `c2ebb578`：配置、digest verifier、fresh-process secret-redaction 测试，三文件。
- 凭据聚焦 15 passed；Task1 run `f655b7b782f34f22b27b9afef6bc905c`；Task6 run `2d79296173bc41c394a792b334b4c5ef`；docs run `0748fd411fc341a8af79d3aea2ce36ac`。三个 Harness 均 passed/cleanup passed。
- 原始报告：`D:/Users/User/Documents/paralls-evidence/stage3-admin-reviewed-20261020-01/{task1,task6,docs}/`。对应管理员源码修订，后续文档索引修改不要求重跑无关 backend。没有运行全量 pytest/all、模型评估或 Godot。

## 本轮角色输入与执行投影进展

- `bc946612`：L2 registry/loader 两条 profile cache 路线使用 JSON 值，修复阶段三资源 tuple 阻断 durable cognition frame；聚焦 10 passed。
- `fac6a634`：私有视觉身份/source/catalog、scope 清空、只读 ESM inspect 投影及生产 reset 接线；独立测试 3 passed。12 文件 170 passed 的组合证据为 run `1c29eb21a796483aac675bc7433bc1fa`，目录 `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/target-focused/`；cleanup passed。
- 执行投影修复：冻结 choice 的 target、candidate identity/owner route、owner digest、target revision、room/scene/zone 保持到 L4；`inspect_object`＋`action:inspect`映射到注册的 `interact/inspect`，ActionRequest 与 InteractIntent 共享冻结 scope。暂存隔离测试 4 passed（run `b2b503f2b1a94580815bb3724b32b3f3`）；组合回归 75 passed（run `0a932502a9dd40c794b41b9c8127f209`，之后仅增加来源断言与不同 attention 参数）；backend-contract 静态门禁 passed（run `28cedfd8828843cf96e9ab286b281b4a`）。证据分别在同一外部根的 `inspect-staged-unit/`、`inspect-projection-corrected/`、`inspect-backend-contract/`，cleanup passed。
- 独立审查发现暂存版本漏带 candidate identity/owner/target revision，已补齐并由隔离测试核验。第一次隔离尝试的既有集成用例缺少文档夹具；第二次扩大夹具复制遇到 Windows 长路径，导出失败。只清理了本轮隔离副本与失败导出中的副本；后续只隔离所需四项单元用例，未将失败集成用例计为通过。
- R05仍为 inspect 输入切片；R06现已覆盖 durable Siming 的 L2/L3 同源合同；direct/background/dialogue/recall 仍缺。R07无真实 Laya 原动作证据；R08仍缺生产执行准入、实时 owner 重验、领域实际提交与 durable receipt。当前 canonical character interact 路径只 resolve/发布 accepted，不能当成 player interact 路径中的 object transition/commit，更不能据此关闭 R08。
- 未运行全量 pytest/Harness all、真实模型或 Godot；历史 `.harness/verification` 与用户其余 dirty 保留。

## 执行顺序

1. R05/R06：补生产私有目标与同源能力输入，优先复用已有 scene/skill/owner registry；记录 action-specific availability，不能一条 target grant 放行所有动作。
2. R07/R08：选择无需 Godot 的真实 owner 纵切，打通同 turn 的实际 Laya→L4→owner→receipt→writeback；领域缺口转入对应 D 行，完成后返回。
3. R09：沿该纵切完成 durable dispatch/reopen/replay；保留后台零命令与取消隔离。
4. 交错收口 D03–D11、R10–R14；不重复建设已有能力；各 owner 一旦正式准入就加入共同 cut。
5. Q01–Q04：有来源的完整动作/目标开发归因→新 calibration→预算阈值冻结→独立 final/holdout；训练仅经有证据方案单独处理。
6. 后端四组矩阵条件满足后，集中 G-A→G-B→G-C；到此才考虑最终必须的扩大验证，并先说明与用户禁止无意义全量运行的关系。

## 本轮共享认知合同进展

- `2d420aae`：整理并提交稳定技能投影与包络/策略基础；`84f3e668`：提交既有候选编译/Laya 适配基础及 durable Siming 的生产接线。角色、turn、policy revision、source event 和 pair pins 在 L2/L3 网关前共同校验，L4 沿用冻结 turn；旧版 L3 prepared frame 保持恢复兼容。
- 暂存隔离验证：基础 9 passed / 8 deselected，run `d2390709db9640c5a371c9cd36389552`；接线 129 passed，run `96c67549533340c8830d374ba89ea3a8`。均使用 HEAD archive＋暂存后端＋HEAD 角色档案，未混入历史 mind projection 或执行 lifecycle 改动。
- 第一次基础隔离缺少根目录角色档案，配置导入失败，run `936609250ce14ff798177d051e543f80`；随后按真实 loader 路径只补已提交档案，未扩大复制整个 docs。失败不计通过。
- backend-contract 静态门禁 passed，run `855cb5ea59f74891b3ac795707e045e8`。上述证据在外部根 `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/` 的 `cognition-foundation-staged-corrected/`、`durable-cognition-staged/`、`durable-cognition-contract/`；cleanup 均 passed。
- 后端：仅关闭 durable Siming 共享合同子项。模型质量：未运行真实评估、Q01–Q04未关闭。角色闭环：R07–R09仍缺真实原动作、owner提交/回执及端到端恢复。Godot：仍未修改、启动或验收。未跑全量 pytest/Harness all。

- 文档门禁首次因计划文件未用 `-implementation-plan.md` 命名失败（run `6f03d94662194d9c8bb1a158b488e853`）；修正本轮计划名称及链接后 passed，run `8023305d1fd942ebbb991c60609dd9ed`，外部目录 `durable-cognition-docs-corrected/`，cleanup passed。本轮三个临时诊断日志经 run_scope 导出后删除。

## 本轮召回入口与 authority 重验修复

- `10de477f`：perceived-event wrapper 向 L2 传递已有 canonical turn；真实 semantic recall 的 cards/source/revision 进入请求，跨 actor turn 或私有 memory 拒绝。旧 L2 测试 profile stub 同步接受生产已有 JSON dump mode。精确暂存隔离 52 passed（run `e1026efc47b44046a81e8ed90a8896ff`）。
- `4fa9d0ea`：self-body runtime 同样传递 canonical turn；真实 runtime→L2 recall 与相邻恢复回归精确暂存隔离 57 passed（run `609b59d7286b4b2ea1783702b438d13c`）。已有 mappingproxy serializer warnings 仍保留；不据此声明 direct/self-body 的 L2/L3 已共享包络或硬预算。
- `055d5abf`：ESM 的直接执行入口复用既有 policy/state/occupant 检查；未注册对象、非法动作、状态变化及他人占用均拒绝，拒绝结果保留 canonical pins。请求与事件的 actor/scope/target/action 必须一致；canonical idempotency fingerprint 加入 room/scene/zone，拒绝跨场景重复键。12 个新增行为用例先 RED 后 GREEN；与既有 ESM/后果边界用例精确暂存隔离 52 passed（run `f5f7631c131041d9add2b9986391373d`）。工作树中另含 target projection 回归 67 passed，仅作组合兼容证据，不替代隔离结果。
- 原始日志、暂存 patch 和 manifest 分别在外部根 `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/` 的 `perceived-turn-recall-staged/`、`self-body-turn-recall-staged/`、`esm-readmission-staged/`；均 cleanup passed，临时 checkout 已回收。
- 后端：本批补齐 ESM 执行时 policy/state/occupant 重验子项；ESM state 与 settlement cache 仍为内存，缺少 canonical 距离来源时仍不能计作正式动作提交。装备已有真实 durable owner，但调用权限目前绑定 controller，不能直接当角色授权；work intent 仅有合同与事件注册；SocialDelivery 的 delivery receipt 不证明 speech played/heard。R05/R08 保持局部实现，R07/R09 保持未验证。
- 模型质量：本批未运行真实 Laya、calibration/final/holdout，Q01–Q04 未关闭。角色闭环：仍缺完整原动作→真实 owner→receipt→恢复回放。Godot：未修改、启动、操作或验收。没有运行全量 pytest/Harness all；用户历史修改与历史证据保留。

## 三类同步入口共享合同回写

- `19078684`：perceived、self-body、同步 Siming 在 L2 前冻结同一 turn 的 stable ability、CapabilityEnvelope 与 CognitionPolicy，L2/L3 复用一次编译结果；durable Siming 复用同一冻结方法。同步 Siming 同时补齐 L3 所需 background agenda context。turn 以类型对象传递，避免 mappingproxy JSON 序列化失败被 fallback 掩盖。
- 精确暂存隔离四文件 95 passed，保留两条既有 mappingproxy serializer warnings；run `f462954ad3ca4669af07a4b511b61c30`，外部目录 `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/direct-shared-contract-staged/`，含 staged patch、pytest.log 和 manifest，cleanup passed。测试 provider 是本地受控 gateway，不是实际 Laya 证据。
- R06 仍局部实现：background/dialogue/recall 硬预算、canonical 可信输入与 memory revision 未完成；Task1 不关闭。R07–R09 未取得真实模型原动作、owner 提交/回执和端到端恢复证据。Q01–Q04 未关闭，Godot 未操作。
- 上一文档批 docs gate passed/cleanup passed：run `47c5f01bc26546fabe42f9068b891408`，同外部根 `recall-readmission-docs/`。本批不重跑不受影响的后端验证，不运行全量 pytest/Harness all。


## ESM object-only owner 前置能力回写

- `4a18a6f9`：原 ESM 增加显式 opt-in durable settlement，复用共享 GameplayEventStore。范围仅 `obj_plaque/inspect`、`obj_worktable/use/finish_use`；不表示生产、工资或工作完成。环境、body、physics 路由拒绝部分提交。请求/event 的身份、scope、动作、目标与 canonical pins 在原回执查询前绑定；有限坐标是 owner 前置条件，不证明到达或角色授权。
- 写入先于状态投影；scope stream 与 caller read revisions 同批 CAS；exact retry 返回原 result/receipt；SQLite 重开恢复；durable 对象禁止旧内存提交入口绕账。显式事件注册支持 strict store。定向组合工作区 80 passed；精确暂存隔离 73 passed，run `368161ea887f43db890f67b12870cb19`，外部根下 `esm-object-owner-staged/` 含 patch、日志、manifest，cleanup passed。首轮 `6ff8b184002c486fb15e52a137fa6ce3` 测试通过但 pytest 临时链接阻止导出，未用作可留存验收证据；临时根已回收，修正临时数据清理后得到上述有效 run。
- 后端：仅完成 R08 的 bounded owner 前置子项。R08 生产闭环仍未实现；不能把 caller 提供坐标当可信 spatial source。原 session 冻结合同可作为角色执行来源，但 session SQLite 与 world store 独立，不能虚报跨库原子；恢复必须查原 world owner receipt，再幂等补记角色侧。R09 仍端到端未验证。
- 模型质量：未运行真实 Laya 或正式 calibration/final/holdout，Q01–Q04 不关闭。角色闭环：原动作→生产准入→owner→反馈及完整回放未验收。Godot：未修改、启动、操作或验证；最终需绑定真实空间来源并取得 A/B/C 可见结果。
- 前一文档批 `8f85692` docs gate passed/cleanup passed：run `0fbe61ed9eee40b597721b837116605f`，同外部根 `direct-shared-contract-docs/`。本批未运行全量 pytest/Harness all；历史修改与历史证据保留。


## 原 session 执行来源准入回写

- `d13994bd`：生产 canonical execution ingress 在生成 ActionRequest、调用 owner 或记录 settlement 前，必须与原 actor session 的 `character_agent_execution_request` 完整合同一致。兼容同步直接合同与 durable plan 内合同两种既有存储形态；跨 actor、未记录合同、改写动作/目标/source/turn/revision/observation 均拒绝，同键冲突记录不能以第一条合法记录掩盖。只返回来源 event ref，不授予 world authority，不替代权限、时钟、空间及 owner 重验；legacy bundle 兼容入口仍存在。
- 先得到 11 项 RED（包含生产入口错误接纳未记录合同），再修复。工作区两文件组合 38 passed；精确暂存隔离四文件 39 passed，run `c7c05088285f48449c7f8ea923dc34fe`，外部根下 `execution-source-staged-short/` 含 patch、日志、manifest，cleanup passed。四条既有 FastAPI lifecycle deprecation warnings 保留。backend-contract passed/cleanup passed，run `5ab8f46639db41faaf4f7dff299f7047`，目录 `execution-source-contract/`。
- 首次扩大隔离运行 `280ae4dc8784414c99a90efdf2f19734` 为 7 failed / 64 passed：五项缺六个已提交的 production manifest 夹具；两项为 HEAD 已有失败。后一次补夹具时遇到 Windows 长路径，run `87e4a6c4c50d41d5a421f6854de4eace` 未运行测试；自有失败导出中的 checkout/tar 已清理。有效运行改用自有短路径 checkout，并只复制 registry 明列的六个 HEAD manifest，没有引入工作区历史修改。
- 两项 HEAD 基线失败单独复现并保留 baseline.log：`test_character_agent_runtime_player_suggestion_path_uses_continuity_floor_under_local_only_planner`（期望 observe_target，实际 physiology_hint）；`test_character_agent_runtime_feeds_previous_goal_portfolio_back_into_next_model_turn`（缺 execution target_ref）。本批不修改其历史混改；不能声称整个 runtime suite 通过。
- 后端：关闭来源绑定子项，R08 生产完整闭环仍未实现；可信 spatial source、L4 实时准入、真实 owner receipt 与 session 补记仍待完成。角色 R07/R09、模型 Q01–Q04、最终 Godot G-A/B/C 状态均不升级。未运行全量 pytest/Harness all、真实模型或 Godot。
- 前一文档批 `eaeda35` docs gate passed/cleanup passed，run `6fdffc0c5cae4eb095cd73eab159dffc`，同外部根 `esm-object-owner-docs/`。


## 冻结召回预算子项回写

- `cdaff0a2`：冻结 policy 限制跨 memory pools 的总召回条数和既有 token 估算预算；strong/requirements 不能扩容。semantic cards 裁剪同时裁 memory，保留 omission；零预算不查询 graph。L3 在首次召回前冻结/校验 policy，使用 semantic 返回的裁剪后 memory；gateway 二次召回不能突破冻结上限。actor/turn 不一致拒绝。
- 精确暂存五文件隔离 163 passed，10 条既有 mappingproxy serializer warnings；run `84939863833b47b7a4a95367f3806e2a`，外部根 `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/recall-budget-staged-corrected/` 含 patch、日志、manifest。backend-contract passed，run `c0948577424d45fd8d98015f5df71143`，同根 `recall-budget-contract/`；均 cleanup passed。
- 初始 RED run `3e47dde6404646e9ba7cc62ae14d6a63`（10 failed），L3 RED `dff7558d9a4c49f580aea6c833565516`（2 failed）。扩大组合 run `09ff9274a4d947f39ef1bc8b500a6c55` 为 1 failed/140 passed：既有 strong-memory 测试依赖隐式扩容；改为 profile 显式冻结 2400 后维持原长记忆断言。run `261534c9ee5e420399eb812ec42d523d` 因清单含未提交历史测试文件而零测试，已纠正清单取得上述有效隔离结果；不计作通过。诊断目录分别为 `recall-budget-red/`、`recall-budget-l3-red/`、`recall-budget-layers/`、`recall-budget-staged/`，均已清理本轮临时副本。
- R06/Task1 保持局部实现。这里使用既有 JSON 长度估算，不是实际 tokenizer 或整个 prompt 的硬预算；background、dialogue 和可信输入/memory revisions 仍待补齐。R07–R09 未升级：未运行真实 Laya、未打通生产 L4→owner receipt→恢复。Q01–Q04 与 Godot G-A/B/C 均未关闭，Godot 未操作。
- 上一文档批 `ae613868` docs gate passed/cleanup passed，run `410e806999814d49b9ee1132183edf94`，同根 `execution-source-docs/`。本批未运行全量 pytest/Harness all，保留历史修改和证据。


## 可信空间来源前置回写（Task2 保持开放）

- `cdb424d8`：内部 authored scope、真实 controller/epoch 绑定、首样本/重连位置连续、backend 单调时间与 tick 双重限速、bounds/freshness、持久化 provenance、同 world spine read CAS。旧重复请求返回原 receipt，不刷新 freshness；进程重启须新样本。采样和读取只读取当前 head 一条，旧 retry 直接查询原事务。纳入已有 controller 断连/重连撤销实现，防止旧连接继续被接纳。
- 精确暂存隔离 **62 passed**，4 条已有 FastAPI lifespan warnings；run `93614848ee2e446199c8b2cd369ecd27`，外部根 `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/spatial-source-staged-final/`。backend-contract passed run `4693379c1044449c803bc686fc5fd254`，同根 `spatial-source-contract/`。均 cleanup passed。
- 初始 RED `93396480fea54a2eaf9257160336b27e`：16 缺模块与1个测试 context-manager 错误；修正后 SQLite RED `070b10dbb50d48c6b69ce1d618cd16e4` 正确缺模块。局部实现 run `02d58bdc6a6140fd84589b2b43d58bfd` 50 passed。新增有界历史读取 RED `e47d4479ba684dc391d7bb365f56d50b` 1 failed。第一次隔离 `6cd20c5ebdb145b4aefbe1e882feddbf` 3 failed/58 passed：发现未提交 auth 撤销依赖，并缺 production manifests/静态桥文件；补齐后 `5a18bdba6e27496fb6ff76e643e83e93` 1 failed/61 passed，仅还缺 LocalPresentationBus 静态文件。补齐明确 HEAD 夹具才取得上述有效结果；不将失败计为通过。本轮没有修改、启动或操作 Godot；读取已提交静态文本不构成场景验收。
- R08 只补来源前置，生产 composition/消息 ingress、L4 实时准入与 ESM receipt consumer 仍待接。该来源证明有界 controller evidence，不证明 server physics/contact/path clearance。controller auth 是内存状态；撤销与 world append 尚非跨组件原子，不声称全生产准入原子性。R07/R09、Q01–Q04、G-A/B/C 均不升级，未跑真实模型/全量 pytest/Harness all。
- 上一文档批 `58cdc65` docs passed/cleanup passed，run `c70a211dc49144089310ab703cfbbae2`，同根 `recall-budget-docs/`。

- 本批 docs 首跑 `b43940fa31434f0e873872eab9a8fdea` 因门禁要求同名计划缺失而失败；增加链接到统一计划的空间来源 lane 后，`b4f073d817a74d15b796d74cee859a9d` passed/cleanup passed，外部根 `spatial-source-docs-corrected/`。


## 空间生产接线与真实边界子项（Task2 仍未完成）

- `cafeaeed`：内部 `EMBODIED_SPATIAL_SCOPES_JSON` 严格配置、共享 world store/auth 组合、`embodied_spatial_sample` 真实 ingress 和断连接撤权。精确暂存隔离 69 passed，run `61250907b02142a3be805756e75570c9`，`spatial-ingress-staged-final/`；backend-contract passed，run `62f952b0b0094b7fae2ee506a82e4034`，`spatial-ingress-contract/`；两轮 cleanup passed。
- `e7063bcc`：真实网络绑定使用后端 wallclock，禁止默认固定时间绕过已过期 launcher credential；仅内部 direct-handler 测试保留历史兼容时间。回归先 RED（run `14233352e71b43a6bc45ddeb0def9227`，1 failed/7 deselected，`spatial-bind-clock-red/`），再精确暂存隔离 70 passed / 4 既有 FastAPI warnings。
- 真实独立 uvicorn＋HTTP enrollment＋WebSocket bind/sample 验证 passed：首样本得到持久提交 receipt，exact retry 返回原回执，changed duplicate 拒绝。run `2305abd50062465880574e1fc7e281c4`，目录 `spatial-ingress-live/`；manifest 保存原始边界响应和版本 patch。证据根仍为 `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/`。
- 此 live run 清理失败：Windows 文件占用使 checkout/backend 与 backend.log 删除失败。随后进程快照未发现本轮 uvicorn；精确路径 PowerShell 清理被自动审批策略拒绝，未绕过。遗留仅本轮 `C:/Users/User/AppData/Local/Temp/oc-2305abd5` 与 `C:/Users/User/AppData/Local/Temp/paralls-harness-2305abd50062465880574e1fc7e281c4`；保留 cleanup failed，不把此 run 总体记为全绿。
- 后端：空间生产准入子项局部实现，默认内部 scopes 为空，尚无 ESM/L4 consumer。角色闭环：R07–R09 未关闭；历史 dirty L4 方法不等于已提交生产基础，下一批先审阅必要依赖，再接 source→L4→owner receipt/recovery。模型质量：未运行真实 Laya 或正式 splits。Godot：未修改、启动或验收；最终 producer 必须发送内部配置匹配的 actor/scope/scene_instance/revision、绑定 epoch、tick、位置，且仍需 A/B/C 可见结果。未运行全量 pytest/Harness all。

- 本批文档门禁 passed/cleanup passed，run `c6d7ea770733488ca9dc1ff79b06b772`，外部 `spatial-ingress-docs/`。

## 有界对象执行 consumer 与回执恢复（Task2/3 子项）

- 仅 public `obj_plaque inspect` 接到生产 canonical egress/ingress、共享 ESM owner commit 和原 receipt 回写。后台派发单独记原 session event，不污染确定性 L4 合同；重发不续期，新进程不能用旧派发提交。新 request（含 legacy）使旧派发失效。已有原 owner receipt 优先恢复，跨库 writeback 失败可补记一次。
- HEAD＋精准暂存补丁隔离：95 passed，run `12b015bce3814ccfa82c53cfa34d57f6`，`object-staged-isolated/`；backend-contract passed，run `5c881ad557714ce293f8890375f1c21b`，`object-consumer-contract/`。均在本页外部证据根，cleanup passed。工作区组合 run `6bfb422ac68743aa9ac0a99601cf5158` 同为95 passed，但不代替隔离证据。
- 覆盖原 receipt、零写拒绝、重复不续期、跨 service epoch 拒绝、生产处理函数、SQLite 关闭重开补记。fixture 注入私有 snapshot与冻结合同，没有真实模型选择或新网络纵切；不关闭 R07/R08/R09。未跑全量 pytest/all、真实模型或 Godot。
- 后端：有界生产 consumer 和原receipt修复已测试；模型质量：Q01–Q04仍未通过；角色闭环：继续真实 Laya生产纵切，完整生命周期/多领域和full/checkpoint-tail待验；Godot：A/B/C均未执行，仍最后集中验收。既有空间live run清理失败的两条路径保持原记录，本批未尝试绕过审批清理。

## Background 共享认知合同子项

- `22522948`：同步 background 与 durable background 在 L2 前冻结同一 turn 的 CapabilityEnvelope/CognitionPolicy，L2/L3 复用该合同；durable provider-pending 重开读取原冻结请求，source event ref 绑定原 cognition child key。后台仍不产生执行命令。
- HEAD `249a9eed` archive 加精确方法补丁隔离 **58 passed**，run `ae1be16c6a024afd9a625a60cefa9d76`；证据为 `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/background-staged-isolated/` 中 manifest、patch、pytest.log、JUnit。cleanup passed。提交前以独立 Git index 重建证据 tree，与 staged tree `413be97d7a91517b415f8e3ad95bafeda6648639` 完全一致；用户原有 MindFrame projection、frame 参数和 coordinator 重验修改没有并入本批。
- 后端：仅关闭 background 同源合同子项，R06/Task1 仍局部实现；background/dialogue/总输入硬预算及可信 revision 未关闭。模型质量：未运行真实 Laya 或正式 splits。角色闭环：R07–R09 未升级。Godot：未修改、启动或验收，A/B/C 留到后端及模型门完成后。不重复运行无关全量 pytest/Harness all，历史修改和证据保留。

## Laya 生产默认完整输入预算子项

- `c3fbbf27`：L3 生产 Laya request 无论环境变量缺失、空值还是空白，都冻结完整输入预算（默认 max_len=2091、head_max_len=256）；显式配置仍冻结到原 request。复用现有 provider tokenizer gate，缺 pinned tokenizer 或总输入超限在 HTTP 前拒绝。
- RED 5 failed，run `ffc3cc6569954313bf3943a5e61724e0`；HEAD `2cb97f5f` archive＋精确两文件 GREEN/回归 **72 passed**，run `0ed5fd71ca7d4902944c73f41f9f1384`。提交前核对两文件 SHA 与隔离 manifest 一致。backend-contract passed，run `be6de26f061046ec93a3ea9b57925a98`；各 run cleanup passed。证据在既有仓库外根目录的 `laya-default-budget-{red,isolated,contract}/`。
- 后端：只关闭生产默认预算门子项，R04/R06仍局部；4 条既有 mappingproxy serializer warnings保留。模型质量：受控 tokenizer 测试不能替代正式 tokenizer/usage 或 calibration/final/holdout，Q01–Q04未关闭。角色闭环：R07–R09未升级，下一步真实 Laya→L4→ESM receipt纵切。Godot：未修改、启动或验收；没有运行全量 pytest/Harness all。


## Laya 冻结认知输入修复与真实诊断

- `4c4b65e7`：L3 原已准备的 actor-scoped goal frame/tags、current goal、已裁剪 memory/semantic cards、need/dynamic state、supervision/background/tension 通过显式 allowlist 进入 Laya state；不复制整个 context、原始档案或 grading。所有新增输入仍经过既有 pinned tokenizer 总预算门，超限在 HTTP 前拒绝。此批不宣称所有 frame/source 输入已完整。
- 10 项新增输入保留用例先 RED（10 failed）；精确两文件 HEAD 隔离验证 **131 passed**，run `12803a3e4a944604b32fca4cf96d15c7`，外部根下 `laya-frozen-context-isolated/`。backend-contract passed，run `d99751bd2d32491aa7fd6acc671a8937`，目录 `laya-frozen-context-contract/`；均 cleanup passed。
- 修复前真实 backend 诊断 runs `5abeca21340a4cfd8af623044b66044a`、`6f05c7a2b03a4db29fb84184ef9d4016` 各两次 Laya HTTP 成功，均选择合法 observe，未到 owner。前者目录 `laya-object-production-diagnostic-exact-manifests/`，后者 `laya-object-production-diagnostic-action-request/`。缺 manifest 的前次 launcher 失败不计通过。
- 修复后 HEAD 真实 backend WebSocket raw fact→L2 local baseline→official pinned Laya run `f0fe891b98174b5f8936e4d5e69ddc5b`：原冻结三候选顺序不变，选择 `inspect_object:obj_plaque`（0.7819），完整输入 **5844 tokens**，服务 usage 与本地预算完全一致、无截断、无 provider error。目录 `laya-object-production-frozen-context/`，cleanup passed。本次 15 秒观察窗口在 L3 返回附近结束并取消 pending，未形成 L4/owner 闭环；不能把模型选择计为 R07/R08完成。L2 是 continuity baseline，正式 L2质量未验。
- 上述输入只属开发诊断，不能进入 final/holdout；单例选择变化不能证明统计质量或唯一归因。Q01–Q04仍未关闭。Godot未修改、启动或操作。未跑全量 pytest/Harness all；用户历史修改与 `.harness` 产物保留。

- 上述输入修复的 docs gate passed/cleanup passed：run `5e3d1323da2f4d8bb419afc16eb0402e`，目录 `laya-frozen-context-docs/`。
- 延长真实观察窗口后的 run `114fc8b34fc745ae93edb2932f821a44`，目录 `laya-object-production-owner/`，Laya仍选择 inspect，但生产 L3 legacy mapping 把原语义改为 observe_target，而合同保留 action:inspect/candidate pins；没有调用 inspect owner。该 run 是定位证据，不是闭环通过，cleanup passed。开发 controller已绑定，但条件按inspect合同发送的空间sample未触发，不能宣称新鲜空间或owner提交。后续修复必须让正式冻结候选保持原 semantic intent，并从planner一路覆盖到L4。

- `628f05c2`：正式带 candidate_digest/Laya evidence 的冻结选择直接保留 compiler semantic intent，不再套历史表现映射。新回归从真实 planner prepare→受控冻结 choice→decision→L4 contract验证 inspect/action/target/owner pins；未把受控 choice标作真实模型。行为 RED为 observe_target!=inspect_object，修复后精确两文件隔离 **136 passed**、4条既有FastAPI deprecation warnings，run `f115f41572eb4e33b4dfe5161826f274`，目录 `laya-frozen-choice-isolated-corrected/`，cleanup passed。首次隔离 `20602e90a4c64c758039583a1652333d`为1 failed/135 passed（新增用例空revision夹具不合法），修正测试为非空真实形态后重跑；不计前者通过。

- `628f05c2` 的 backend-contract passed/cleanup passed：run `6a86b07f718043d0a81a9ecc6dae104a`，目录 `laya-frozen-choice-contract/`；docs passed/cleanup passed：run `6f6621990c1642c88cab8c8e5eca1fc4`，目录 `laya-frozen-choice-docs/`。
- 真实纵切前 run `0232edbf21964d9195d8ed094eb5517b`（目录 `laya-object-production-owner-original-intent/`）已保持 inspect 原合同，但 launcher 在 app/config 导入后才设置scope环境变量，导致 scope mismatch，零owner写；修正launcher将scope置于所有app导入前，未放宽生产准入。该失败不计通过。
- 有效纵切 run **`4f2816ada4884a7dabab3644ff878564`**（HEAD `628f05c2`，目录 `laya-object-production-owner-configured/`）：真实 WebSocket raw fact→L2 local baseline→官方 Laya `inspect_object:obj_plaque`→同一turn/source/candidate/digest的 L4 inspect/action:inspect→认证开发controller空间sample→原 shared-store ESM owner提交→world_result与角色session settlement outcome。空间receipt位于global sequence 9，ESM receipt位于10；owner transaction为 `transaction:esm-object:5efe5d357f4378db0475365744a690496317250267f93e6fc161f855e4d8ba90`，world_result和session outcome均引用原transaction。服务输入5822 tokens无截断。cleanup passed，本轮Laya服务已正常关闭。
- 该空间sample为认证开发controller报告，**不是Godot/physics/contact证据**；L2是local baseline。仅升级 R07/R08 的公开plaque inspect子项，R09完整恢复/回放、其余动作/owner覆盖与Q01–Q04、G-A/B/C仍开放。不能从此单例推正式模型质量、通用owner admission或整个角色闭环完成。


## 真实 inspect 纵切的新进程恢复子项

- run `e9c21eb2ffa945c18fb95a289d14c8aa`（HEAD `143799c`），外部根下 `laya-object-production-owner-recovery/`。先运行同一真实 backend/Laya/认证开发空间source/ESM owner路径，关闭backend后，新 Python 进程重开原 world SQLite＋原 character session SQLite，以原冻结合同查询执行；没有新模型调用、派发offer或新鲜pose。原 receipt逐字段一致，重复执行不重复提交，改写目标在source校验拒绝。
- `new-process-recovery.json`：世界 global sequence **10→10**，session event count **17→17**，settlement outcome **1条**；changed duplicate错误 `execution_source_mismatch`。recovery exit=0，主backend exit=0，run cleanup passed；本轮Laya进程正常退出，18765/18766无listener。
- R09只完成真实提交后的新进程exact retry/changed duplicate子项。fixture已有的丢writeback修复不等同于该真实模型run经历了提交前后中断；checkpoint＋tail、共同cut、旧worker迟到、多owner和完整角色生命周期仍待验。正式模型Q01–Q04与Godot三项状态不升级。下一批依据D06/D10/R10–R14的实际consumer依赖推进，不为已有inspect子项继续堆叠无新增风险的测试。

- 本批恢复索引 docs gate passed/cleanup passed：run `c5b229b132a9453f98edbf26e49b0da2`，外部根下 `laya-owner-recovery-docs/`。仅精准提交本轮矩阵回写，不提交历史dirty/untracked领域文件。

## R10 registered learning owner 前置

- [设计](../../superpowers/specs/2026-10-20-registered-learning-authority-design.md)与[计划](../../superpowers/plans/2026-10-20-registered-learning-authority-implementation-plan.md)：新增独立 `skills/learning_authority.py`，复用现有 shared GameplayEventStore、技能 registry 和 stable compiler，不依赖历史未提交 episode/settlement 改动。
- 内部对象规则绑定 skill、方法/阶段/operation、来源 owner/type/version、actor/world、最低证据与注册 outcome；每条 evidence 必须有同库原事件、transaction membership 和已提交 receipt。来源 read CAS 与 actor learned stream write CAS 原子校验。原 receipt exact retry 可跨 source advance、rule removal 和 SQLite 重开；changed duplicate、同 actor/object 重复证据与坏 projection 拒绝。
- 受限 `granted/locked` 技能不能被对象注册直接授予；`evolution` operation 和 `evolved` stage 都要求注册 Siming source。补充 RED 先复现受限技能授予、可变 dict 的 bool revision 被 JSON dump 转整数，以及 evolved stage 绕过；改为原 Python 值严格重验并补门禁。两处新增测试曾误读 receipt 顶层 error_code，已按实际 failure 合同修正，不作为产品缺陷。
- 最终隔离 run `060b10b09b334dd7bc372a20bcb6cb69`，HEAD `e23c917a`＋精确两新增后端文件，**39 passed**（owner 29＋既有 service 10），exit=0/cleanup passed；外部根下 `registered-learning-owner-receipt-scope-final/` 有原始日志、JUnit、source 与 SHA256 manifest。覆盖缺来源/错误 subject/principal/outcome/privacy/stale、零写拒绝、前置技能成功链、source 并发变更、写入前故障、提交后丢响应、strict schema opt-in、损坏 projection、SQLite 恢复及 existing compiler 消费。较早36项与38项隔离结果由最终39项取代，不重复计入。最终复核 RED 复现其他 stream 回执被 exact retry 接纳；已补 owner stream/type/version/transaction 作用域门禁。
- backend-contract run `76752ae4862a4223be71c49ca28593b5` passed/cleanup passed，外部根下 `registered-learning-owner-contract/`。这是静态边界门禁，不能代替运行时学习路线。
- **R10仍局部实现**：schema 仅 opt-in，尚无生产 shared-store registration/caller。episode、时间/资源、teacher 可见性、八维 mastery/七维 difficulty、fusion/evolution 图语义、下一回合 capability 刷新和共同 checkpoint cut 均待后续接线。测试 source 为受控提交，非真实角色/Laya学习证据；无正式模型质量或Godot升级。未运行全量 pytest/Harness all，未启动模型训练或Godot。

## R10 owner→冻结能力与生产读取绑定增量

- 在上批前置上新增同次 history read 的 actor/world `LearningStateSnapshot`，包含 learned stream revision、state 与原 learning event refs。runtime 将 learned 与 authored 交给既有 stable compiler，保留既有优先级与 profile。新回合 envelope 冻结学习 snapshot digest；sync 与 durable coordinator 都在 provider handoff 与结果接纳时检查原 pin。冻结和交付之间提交也拒绝；旧结果沿用 `stale_context` requeue，不能续用新能力解释旧选择。原已冻结合同不重新编译。
- 真实 backend lifespan 已将只读 learning owner 绑定到 shared gameplay store、runtime skill registry 和显式 bakery world；该 reader 没有注册学习规则或新增 mutation endpoint。测试中的学习 source仍是受控owner提交，**不是四条生产学习路线或真实Laya学习证据**。旧持久化pending frame若不含学习pin，在新绑定部署后拒绝；已完成owner原receipt仍按原合同恢复。
- 行为 RED先确认snapshot/runtime binding不存在；另单独RED确认真实lifespan未绑定reader。新增用例验证新/旧回合与profile不变、actor/world隔离、sync pending拒绝、freeze→handoff竞态、durable pending重开保留原请求与旧结果拒绝、durable handoff竞态零pending写、真实backend lifespan共享owner。组合工作树57项通过仅作兼容；最终验收使用精确源码隔离。
- 最终隔离 run `9c33cb1d2e5f4c27837ca583005ff547`，HEAD `a801ae8d`＋五份精确源码快照，**176 passed**，exit=0/cleanup passed；外部根下 `learning-cognition-binding-isolated-final/` 有source、规范化SHA256 manifest、JUnit、日志与patch。覆盖owner/service和既有sync/durable合同、completion revision、coordinator回归。较早174项 `c6a2bd321d2d472286a4b752817a5bdd`被最终176项取代；`66f5138bcc274812bba5f45490008e5d`在解包时触发Windows路径长度失败，未执行测试，不计通过；缩短临时目录且只取HEAD必要JSON夹具后修正。暂存五文件内容hash逐项与最终manifest一致，历史runtime/coordinator/main改动均保留在工作树。
- backend-contract run `7ce51c1176ad49ba8d7c7a17f665e836` passed/cleanup passed，外部根下 `learning-cognition-binding-contract/`。R10仍局部实现：实际ESM object receipt为authority_only，nested request/result；不得为复用它直接放宽隐私。下一依赖是owner授权的actor-private学习披露与scene/world归属、episode/time/resource/teacher gate，再接完整四路线。schema生产注册、grant/revocation、mastery/fusion/Siming语义与共同cut仍缺。Q01–Q04、完整角色闭环、Godot A/B/C均未升级；未全量pytest/Harness all，未训练或操作Godot。

## R10 ESM个人动作学习证据披露增量

- ESM owner新增 `publish_learning_disclosure`：必须查原canonical ActionRequest/receipt、成功结果和注册room/scene/zone→world；只披露本人action/target/turn/time、scope/world及原event/transaction/stream provenance，不复制hidden state、完整request或teacher知识。原事件仍authority_only，新事件actor_private。time取原request，调用者不能填accepted或技能数值。新证据source read CAS，exact retry核完整重建transaction/receipt，changed world/actor/receipt拒绝。
- 现有生产 bounded plaque inspect consumer在object owner提交后、session outcome之前生成披露；main只将已注册embodied scope绑定当前显式world。回归实际验证L4 canonical request（含原cause/correlation/source）可披露；披露后session写失败的重试复用原owner/disclosure，不增world seq。SQLite重开、source advance、scope规则移除后原披露仍可恢复。
- 来源owner/type/subject/world/成功条件可由registered learning authority消费，受控策略的ESM→披露→skill owner证明真实事件/回执链；**尚无生产自动晋升caller、完整episode/time/resource/teacher策略或四学习路线**。这不是观察他人/模仿授权，不代表能力mastery。生产store目前非strict schema；新事件提供opt-in schema，未假称全局registry收口。
- HEAD `7b27b5f6`＋四份精确源码隔离 **141 passed**、4条既有FastAPI deprecation warnings，run `666e911afa0c4212a0dee8644feeac2b`，exit=0/cleanup passed，外部根下`esm-personal-learning-disclosure-isolated/`。包含ESM既有服务/真实对象持久结算/readmission、canonical execution、registered learning owner和cognition binding回归。四份暂存规范化源码hash与manifest一致；历史main修改保留。初始RED中测试曾误读不存在的EVENT_SCHEMA并使用非object-only letter夹具，修为既有schema/plaque；正式RED确认disclosure不存在，修复后8项→10项针对性风险验证，不将夹具错误计为产品缺陷。
- backend-contract run `29caab9348704b73a35eb3c5e5c2984e` passed/cleanup passed。没有真实模型/Godot验证升级；R10仍局部实现，下一步补完整学习episode与实际策略准入，再执行真实角色学习纵切。上批初步pytest目录6291/6292/6293的删除被自动审批策略拒绝，保留并记录在ledger；本批早期显式`paralls-owned-esm-disclosure-*20261020`临时测试目录也未报告已删除。正式run_scope隔离副本及Harness根已清理，历史.harness资料未删除。


## Q01/Q02 诊断入口收口与位置／标签归因

- `35282e65` 将原有未提交 evaluation envelope、diagnostic runner/scorer 与预算／独立批准回归纳入可独立验证的提交，并修复 runner 的越界/空/非字符串 choice、畸形 answers、bool-as-zero usage、重复/空题号、相同数量但漏题的准备包、旧封存覆盖。实际发送 request 的候选集是唯一成员校验来源；离线评分同样拒绝缺 request/candidates 或越界 choice。新增首失败即封存/停止、零后续请求和零覆盖回归；不以调用者提供的候选副本代替原请求。manifest 顺序决定执行顺序，execution start 记录真实运行开始时间。
- 先复现 runner 8项失败、scorer 2项失败后修复；早期候选副本草稿已撤下，未作正式证据。测试自身一次使用 pytest 保留参数名 `request` 导致 collection error，改为 `wire_request` 后重跑，未将其计为产品缺陷。HEAD `d3afb8ea`＋精确6份源码隔离 **80 passed**，run `acd15a0771204bb889dba11eaea21c67`，exit=0/cleanup passed；外部根下 `calibration-transport-isolated/` 保留源码、SHA256、日志与JUnit。精准暂存hash与隔离manifest逐项一致；未运行全量pytest/Harness all。
- 真实位置／标签诊断 run `85d3f2dfc5cd4681be53e66391217c63`，外部根下 `exposed-calibration-position-diagnostic/`：读取原已暴露22题 archive（原字节SHA `9da73a0207bfdd3b9e73bfa9ba55a82c41eca1f25cb454d7851886b9d5807e58`），在首个新响应前冻结全部66个请求、顺序、语义标签逆映射、完整token预算及脚本身份。三组为原顺序、只反转criteria插入顺序、保持标签顺序并循环移动描述。保存逐请求有序wire字节SHA，避免canonical排序digest掩盖顺序变化；未更改state、描述内容、checkpoint、tokenizer、CPU、2091/256预算，没有依结果重试、truth读取或训练。
- 同一官方source/checkpoint `68804629.../1720e3...`、原固定tokenizer，合成预检及前后health一致；**66/66**响应在原候选集内、无截断、state dropped=0、实际input tokens逐项匹配预算。原序C3为18/22；反序C3为6/22，语义选择仅7/22与原序一致；循环重标后语义选择10/22与原序一致。说明该呈现下选择对顺序与标签敏感；不能由此选最有利的顺序、修改truth或宣称模型已修好。没有独立批准这些变体的truth，因此只报告不含truth的稳定性归因，不产生新质量分数。
- 本轮官方服务由离线缓存启动，诊断后Ctrl+C结束；随后18765/18766无listener。run_scope诊断及隔离副本cleanup passed。历史用户资料和早期pytest目录保留，未把此前删除审批拒绝改写为已清理；本轮未清理历史`.harness/verification`。
- **后端**：仅诊断封存/评分准入子项完成；**模型质量**：Q01仍未通过、Q02仍局部、Q03/Q04未升级；**角色闭环**：R07–R10及其余领域仍依矩阵开放，本次未取得新owner闭环；**Godot**：A/B/C仍未操作或验证。下一步先检查官方checkpoint声明的option layout与输入/候选描述合同，再决定新开发归因；正式完整动作数据集及独立final/holdout仍缺，不把该信息诊断套件扩充为动作验收。


## R06 frozen policy→实际 provider 输出预算

- `067f69df`：`CharacterModelProvider` 在路由选择前验证已携带的 frozen `CognitionPolicy` digest与actor；L2/L3/dialogue 的任务输出上限分别取同一policy中的对应字段，与原prompt policy上限取min后进入实际HTTP JSON。dialogue SSE同样受约束；零预算、缺digest、篡改、actor错配和非正整数请求预算在调用前拒绝，不能被hybrid/local fallback吞掉。请求对象不被改写，保留原冻结请求/策略的重试身份。已有未携带policy的旧请求仍走原兼容合同，不伪称所有dialogue入口已经冻结同源策略。
- 首轮RED **12 failed, 1 passed**确认实际max_tokens未受约束；补充RED **8 failed**确认无效请求预算被hybrid fallback吞掉，校验移至所有路由前后修复。精确HEAD `9c15be9`＋2份源码隔离 **186 passed**，14条FastAPI/Pydantic warnings，run `5c5fdc666d0a491792846a5dd289e5f6`，exit=0/cleanup passed；外部根下`cognition-output-budget-isolated/`有源码、hash、JUnit和日志。当前组合工作树140项仅作兼容，不替代隔离证据；精准暂存hash与最终manifest相符。
- 这是受控HTTP/SSE传输合同证据，不是新真实模型质量、同源dialogue入口、tokenizer总输入硬预算或Godot证据；R06保持局部实现。下一consumer依赖是`DialogueService`的runtime context provider与canonical dialogue turn/lease来源，不能直接复用上次L2/L3回合的policy当成新对话授权。
- Q01布局静态核查：实际checkpoint config无`option_layout`字段，官方`uses_parallel_layout`默认sequential；源码明确布局属于训练权重合同，不能直接改成parallel。checkpoint默认max_len为1024，此次已完整预算验证的诊断transport为2091；可传输不代表较长输入的质量已验证。该核查不证明所有质量失败由长度或布局造成，不修改模型或输入合同。
- 未运行全量pytest/Harness all，未启动模型训练、Godot或新增真实owner纵切。后端预算子项完成；正式质量、完整角色闭环和最终A/B/C仍开放。

- 本批静态布局来源导出 run `531c12727a7f40d7a6ff5dd1188da796`（`model-layout-source-audit/`，config与官方common源码及各自SHA），cleanup passed。矩阵/计划docs gate run `efd6b023adef48a2bec8f35d34a4fd08`（`cognition-output-budget-docs/`）passed/cleanup passed；上批归因docs gate `4f4ecbe3c9704d019ff024867d2408f0`同样通过。


## R06 对话同角色契约与 assisted 建议增量

- `63739f10`：同一 DialogueCoordinator 续执行冻结并校验 L2/L3 的原包络、策略和 turn；同角色后备 dialogue_generation 沿用该合同，召回和实际 provider 输出预算消费同一 policy。拒绝缺摘要、摘要篡改、错角色/turn与阶段间合同变化。玩家回复的目标改为实际发起者，避免回复上下文指向自己。
- assisted 第三次 L3 建议请求原先缺合同，被现有 learning revision 校验以 `learning_contract_stale` 拒绝；修复三个同步来源及持久化 suggestion 请求的原 turn/contract 传递，不放宽校验。持久化 turn 先还原为 CharacterTurnContext。新回归覆盖实际三个 provider 请求及持久化 frozen context。
- 精确 HEAD `e1f95fac`＋五份源码隔离 **271 passed**，run `e8f8bb4dd7384e9fae31f35238e6ea69`，cleanup passed；外部根下 `dialogue-contract-inheritance-final/` 保留源码、manifest、JUnit、日志。backend-contract run `165c62e3bec2462e9e093e59fe141306` passed/cleanup passed。最初隔离177 passed/3 failed；失败已定位并修复，不计入通过证据。新增 durable 回归发现的 dict turn 错误也已修复。
- **后端**：上述子项完成。主动发话的后备 speaker 可能与 cognition recipient 不同，现明确不继承对方私有合同；自己的新契约及无 cognition job 路径仍缺，R06维持局部。历史 SpeechLease 和其他用户修改未混入本提交。
- **模型质量**：无新真实模型评分，Q01–Q04状态不变。**角色闭环**：本批没有新增领域 owner 或完整动作闭环，R07–R14依原矩阵开放。**Godot**：A/B/C未修改、启动或验证。
- 未运行全量pytest/Harness all；只运行相关对话、认知、provider和持久化检查。run_scope临时副本已清理；早期默认pytest目录及历史证据保留。扩大目标以本矩阵/计划为准；Goal工具只有状态接口，无法修改旧objective文本，保持active，不虚报目标已改或已完成。


## R06 实际 speaker 契约与 lease 竞态收口子项

- `c0d198da`：当 DialogueCoordinator 没有同角色 cognition 合同时，从原 typed DialogueSubmit 和实际发言者当前 profile/skill/learning/dynamic/pins 冻结新合同；完整事件摘要作为 source，记录 session/memory/snapshot revision与context digest。仅准备请求，不发布伪感知或完成canonical turn。无snapshot保持无snapshot；已有snapshot scope不同则拒绝。无旧request_id时沿用完整事件source作为causation/correlation。角色主动发话不会借用接收者私有合同。
- 同角色继承现在包括原effective_profile，避免后备上下文读取不同档案而仍声称沿用原policy。新contract仍通过既有recall和provider输出预算consumer。旧独立DialogueService helper及整体tokenizer/真实memory/input revision完整治理仍未闭合，R06保持局部实现。
- lease竞态：HEAD冲突结果与non-player持有者检查分为两个owner调用，期间background lease释放会错误拒绝对话。审查并采用工作区已有的同命令检查小段，未纳入其他main改动。确定性插入“冲突结果交付后立刻释放”回归在HEAD路径失败；修复后通过，保留player冲突拒绝、原deadline及activation校验。
- 精确HEAD `ac9c07c`＋五份源码隔离 **285 passed**，run `f2c4004dcded42b68897e51cf454c047`，cleanup passed，外部根 `dialogue-own-speaker-lease-final/`。backend-contract `beb333d414fa48eaa90c4c76a4249a62` passed/cleanup passed。先前283项通过快照被新profile回归替代；最终前一快照283 passed/1 failed正确暴露HEAD lease竞态；确定性RED run `a6d39671f00d4b4b96d369b8e0541867`失败1项，不计通过。未盲目重试失败套件。
- **后端**：上述生产对话consumer子项完成。**模型质量**：无新正式模型分数，Q01–Q04不变。**角色闭环**：无新跨领域动作owner验收；依据矩阵转入D10四门真实source/owner依赖，不能从profile vulnerability或调用方bool推导Soul allow。**Godot**：A/B/C仍未操作/验证。未运行全量pytest/Harness all、训练或模型服务。


## D10 Presence依赖：真实activation来源准入

- `2fef3fe9`新增`activation_sources.py`及真实owner回归。composition绑定实际`ProfileActivationAuthority`、精确producer及grant原语深快照；不接受principal前缀作为授权。新准入要求非空grant、当前profile identity及最新有限生命周期；region/pending不充当deactivation。历史`recover`只重建原8字段、command/cause/correlation、schema1、完整builder batch及原new_commit receipt，不消费当前registry/grant。撤除grant后仍可恢复，但不可新准入。
- 读取固定Population head，返回该head供consumer原子CAS。全部索引事件先核原transaction membership，再按type/profile筛选，避免篡改suspend让旧activation复活。独立审查两项发现均先复现再修复；另修复矛盾receipt状态。
- HEAD `91da7f0e`＋两份精确源码隔离**36 passed**、8条既有FastAPI/Pydantic warnings；run `5164b2e1f0a84d19b0a6b0a99131c032`，外部证据根下`activation-sources-final/`。backend-contract `f19b4222cc304791ba44f636c93e8375` passed；两者cleanup passed。首次RED的19项缺adapter失败属预期，另两项旧测试缺manifest是隔离脚本错误，补入HEAD已提交manifest后通过，未当成产品缺陷。恢复RED `78a0cee9474c4c60b7239136384609e0`；索引篡改RED `033e78f271a64cc7929cb3cf6abc75c2`；receipt状态RED `c5526b1bbd704d3cb66dfc63fd1e974c`。
- **后端**：只完成activation来源适配器，尚未接入Presence owner/生产composition，D10完整Soul owner仍未实现。**模型质量**：Q01–Q04不变，无新正式分数。**角色闭环**：R14未升级。**Godot**：A/B/C仍未操作/验证。下一步以该reader替换历史Presence前缀准入，并补合法incarnation历史、原receipt恢复及固定cut写CAS；有任何Life历史时新spawn保持不可用，直到正式Life source adapter存在。
- 本轮没有全量pytest/Harness all、模型调用/训练或Godot。临时副本通过run_scope回收；历史工作区和.harness证据保留。Goal保持active；工具只能修改状态，扩展目标仍以统一矩阵与计划为准，不虚标完成以替换旧标题。


## D10 Presence owner准入依赖

- 已基于上一批真实activation reader实现并审核Presence spawn/despawn owner；本批精确源在`presence-owner-final/`：HEAD `c72f5ee0`＋三份源码隔离**46 passed**，run `ad396f75baa24b408be116b6807ceffc`，cleanup passed。覆盖真实Activation Authority/非空grant、SQLite恢复、双incarnation连续spawn/despawn、原Presence回执exact retry、无写projection checkpoint replay、坏transaction/receipt/index缺失、旧source/historical recover、非法incarnation、变更重复请求、expected-head提前拒绝、activation与Life缺失CAS竞态，以及无Life adapter时dead/alive任意life history fail closed。backend-contract `351c989d07cb4fd4ba9714e51a74ffa3` passed/cleanup passed。最终文件逐项匹配隔离manifest。
- Presence schema为owner局部opt-in schema1两条event；不把独立schema2 LifeState归属并入Presence。activation reader仅作为构造参数；跨store拒绝。新spawn对Population原head、Presence写head与Life absence=0原子CAS。历史receipt可按原activation cut恢复，不重解释当前grant/registry；但若Life历史非空，仍无法断言可重新spawn，明确不可用。
- **后端**：Population/Presence source slice可用但未接生产composition、Soul anchor/grants/protection/four gates未实现，D10开放。**模型质量**：Q01–Q04无变化。**角色闭环**：Laya/L4/R14未升级。**Godot**：A/B/C尚未开始。下一依赖是已注册的Soul anchor/identity binding owner与真实opt-in Life semantics，再实现四门和L4 original action consumer，不把当前Presence接入误报为完整角色准入。
- `presence-owner-red`因尚无adapter预期失败11/43；最终修复了事实索引缺失时KeyError逸出、幂等schema registration、receipt/global cut边界。未运行全量pytest/Harness all、模型或Godot。临时副本已清理，用户已有.harness内容保留。


## D10 Soul Presence 与 anchor source依赖

- 新增 `soul_presence_sources.py` 与真实 owner 测试；固定 Presence head重建并验证完整历史，返回当前 incarnation、spawn/activation refs、不可变来源和 Population/Presence/Life=0 read heads，供后续 Soul append CAS。当前 activation grant/profile/lifecycle单独重验；旧spawn不授权，任何Life历史继续不可用，不推断alive或timeline。
- HEAD `a28eac5b`＋两份精确源码隔离 **48 passed**，run `9c62f6b8f6914426bb16655e7b4806b3`，外部根 `soul-presence-final/`，cleanup passed。RED缺模块9失败/37通过；固定cut竞态、SQLite reopen、旧incarnation、撤grant和坏原receipt均覆盖。独立只读审查无阻断；最初review模型503未产生结论，随后使用可用代理完成。
- **后端**：Presence/Resource来源与anchor provenance局部完成，D10完整Soul owner仍未实现；生产composition、Life adapter、link/grant/protection/four gates与共同cut继续开放。**模型质量**：Q01–Q04无新增评分。**角色闭环**：R14/Laya完整动作验收未升级。**Godot**：A/B/C未操作或验证。
- Anchor最终隔离56 passed，run `ab4eaf39aa294f558d81a5a40d9d36bf`（`soul-anchor-handoff-final/`）；包含 projection 副本隔离与 despawn 后原receipt恢复；此前55项由此结果取代。backend-contract `4b8cc088d2b44d6db7280e91cf2dc2e1` passed；cleanup passed。真实Presence incarnation与Resource cut进入authority-only原子anchor receipt，重开后只恢复原receipt，不授予gate。提交 `03f200ed` 及 `9d25d89b` timeline 内部scope恢复校验。
- 无全量pytest/Harness all、模型调用/训练或Godot；run_scope本轮产物已回收，历史工作区保留。Goal仍active，扩展范围以本矩阵与执行计划为准。Soul link/grant/protection 与四门已有 bounded bind/unbind 窄片，但生产 composition、Life/mind 语义、其余 effect/value、confirmed-time/common-cut、L4 仍开放；缺失Life/mind语义保持fail-closed。
- Soul fact lifecycle基础实现于 `soul_fact_runtime.py`：事件冻结完整注册快照；投影按 world/actor/target/incarnation/package/version/rule 分区；撤销必须匹配原 fact 和完全相同策略快照；完整历史重放验证注册类型、策略键、事务、receipt 与原 anchor source cut。新增 version隔离、策略重部署、伪造快照和缺 anchor cut回归。最终精确隔离 **73 passed**，run `f657afeff55e49809db846799b80bc96`，cleanup passed；外部证据 `soul-fact-review-final/`。RED分别确认缺注册快照/版本混合、伪造自洽注册快照、缺anchor cut；期间错误复验因重复导出目录未执行；最终仅引用新目录绿色结果。
- 本批仍是局部 owner 基础：`operations` 尚未绑定真实 effect/value 转换；Life/mind、四门 admission、counterplay、schema registry/生产 composition、replay participant/common cut 与 L4 未完成。测试使用隔离 `GameplayEventStore`，不作为生产接入证据。未运行 backend-contract/docs/Harness all/全量pytest、模型评估或Godot；本轮 runner cleanup通过，`.harness` 只有历史用户修改，未触碰。


## Worktable 程序能力映射与真实 use 纵切（2026-10-20）

- 根因来自上一 live trace：角色 stable ability 已注册 `procedure`，L3 却将 `use_object`/`finish_use` 归到未准入的 `interaction`，使真实可用动作在包络门被过滤。现映射到已有 procedure domain；没有新增能力或放宽 owner 权限。新回归使用实际 SkillService stable snapshot，有 procedure 才呈现 use，缺能力拒绝，blocked finish 不呈现。前轮 RED 1 failed/1 passed，修复后工作区五文件45 passed；本轮精确 HEAD `45d8f194`＋两源码隔离四文件 **37 passed**，run `b12eb914bdc5423a9a710de987d2357c`（`worktable-procedure-isolated/`），cleanup passed。backend-contract `5d66626c72bc4d17b7044c04eb863076` passed/cleanup passed。
- 真实 backend/WebSocket＋官方 pinned Laya run **`ee14e70f72ef49be88c63e14f8548da6`**（`laya-worktable-procedure-production-20261020/`）：源码为 HEAD＋上述 planner。两次模型成功且无 fallback；第一轮原候选 `observe/use_object:obj_worktable/ask_probe`，Laya 选择 use（0.8347），输入6235 tokens无截断。原动作及目标进入 L4，认证开发 controller 提供空间sample，ESM owner 返回 new_commit，global sequence 10，world_result 引用原transaction并 committed；第二轮候选已切换为 `finish_use`，模型选择 observe（0.7013），输入7817 tokens无截断。该样本不是 Godot/physics 或生产产出证据，L2仍为local baseline。
- 恢复子进程硬编码要求两份回执，实际只有一份，故 recovery_exit=1；后续在已清理路径尝试恢复亦未执行数据库验证。原状态已按 retention 清理，不重建或复写历史证据。修正未来探针按实际匹配回执数量检查，但本run恢复仍失败/未验证，不将 backend exit=0/cleanup passed当闭环全绿。未为补证据重跑模型。服务已停止，18765/18766无listener。
- **后端**：能力映射子项完成；**角色闭环**：仅新增真实 worktable use→ESM receipt 子项，finish连续周期、R09故障/回放及多领域仍开放。**模型质量**：本例不是评分，Q01–Q04不升级；**Godot**：A/B/C均未修改、启动或验证。没有全量pytest/Harness all或训练；历史用户改动保留。下一步返回正式完整动作/目标数据与来源冻结缺口，避免继续追加此切片无新增风险的测试。

### 真实角色轨迹开发来源导出（仅开发，不能晋升质量证据）

- `backend/app/character_agent/evaluation/runtime_trace_export.py` 与 `scripts/verification/export_character_runtime_development.py` 只读接合真实归档：要求以当前 pinned Laya provider/tokenizer 重建完整wire请求、核对原U/P/展示/裁剪/诊断摘要与候选覆盖，关联同turn/actor/action/target/candidate pins的原L4合同和唯一、同scope、committed的边界 world_result；拒绝截断、错序、越界choice、源/合同/身份不匹配及重复冲突边界。归档 source SHA256 和逐行引用可复核；调用者不能直接输入合法布尔值或owner receipt。
- 导出只保留 allowlisted wire、候选、合同摘要与边界结果，不复制原角色上下文或配置环境。artifacts固定 `developer_private`、`development_only`、`formal_eligible=false`、`quality=unscored`、`owner_store_validation=unverified`、`recovery=unverified`。边界 world_result 与同trace的continuity receipt均不证明底层 owner store/恢复。
- 对既有真实归档实际解析1条 use→L4→committed boundary，后续 observe 无可配对执行合同而被拒绝；没有调用模型。该归档原始 SHA256 `dc4ec36430fc7ab2e7d5526a2b7e7ab53e1246cd3c38e6865ff552dd05d22ac6`。这只弥补可审查开发输入来源，不是完整模型质量样本，不改变Q01–Q04。


## 只读 vulnerability 来源计算（2026-10-20）

`soul_vulnerability.py` 实现冻结的显式 life/mind→resource/definition/整数阈值注册、有限 comparator、三值 OR、当前 Presence/anchor 与原 Resource 来源前缀核验，返回当前 read revisions、source refs 及包含注册与投影的确定性摘要。读取不写任何 owner；合法资源结算后仍可验证 anchor 连续性。测试中的 stamina→mind 是显式测试注册，不是产品 life/mind 语义。

精确 HEAD d7fdc2d7 加两份新增源码/测试的隔离 Soul 回归 **67 passed**，run `b024191aa9fe4d11bc7bd38bdc4f62b1`；backend-contract `080e84cf103c4035bcaa843bd5e56a27` passed；均 cleanup passed。外部证据根 `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/` 下 `soul-vulnerability-continuity-red/`（目录名不代表 RED，实际 exit0）及 `soul-vulnerability-contract/`。最初 RED 17 failed/49 passed；首轮实现 1 failed/65 passed 为伪造夹具默认 project visibility 比 owner 白名单更早被拒绝，改为 authority_only 夹具后证明精确 unsupported-owner 拒绝；不削弱源校验。

D10 仍局部：生产 life/mind semantic registry、有限 effect/value owner、四门组合、读集与 effect 写入同一 CAS、schema/composition、checkpoint/common-cut/private projection、L4 均未关闭。Q01–Q04、R07–R09/R14 和 Godot A/B/C 状态不提升。未运行全量 pytest/Harness all、模型或 Godot。下一批回到完整 action+target 质量来源与角色闭环，避免继续扩展 reader 局部测试。


### 开发来源导出验证与状态（2026-10-20）

- 精确HEAD `88f088bc` + exporter/test源快照的隔离回归 **83 passed、3 deselected**，run `55242ea8a22d4be180fa3bca6a79c187`，外部 `runtime-development-source-verified/`，cleanup passed。3项外部calibration/runner测试与本变更无关，不作为本次门禁。该run中额外archive probe失败，不能整体记绿：入口错误强制formal option pin，历史dev请求不具备该pin。修正CLI不再强制formal模式，仍以真实SHA校验的tokenizer执行现有选项与总输入预算校验；不改写归档或补pin。最终CLI run `2e34b24f1c814305b54a863378c5555f`（`runtime-development-source-cli/`）exit0/cleanup passed，导出1条、拒绝1条；artifact digest `sha256:b77a9bd3df495cdfe4b85e5c749f90c6674bd8787f2abd88a799213b523624dd`。
- backend-contract `62bd593267eb4ca8902a099693d466f6`、docs `dd100c6e5f9d4966a4100d69da958db3` 均passed/cleanup passed，外部同名前缀目录。初始RED缺模块，候选从重算摘要的universe中缺失RED在D盘复现后修复。早期隔离缺HEAD profiles及两脚本依赖导致未通过；这些结果不计绿。C盘0空闲导致一次临时目录失败；两次pytest临时链接令证据导出失败，run_scope根实际已清理。后续用D盘自有临时目录并在导出前回收隔离副本/pytest数据，未清理用户历史资料。
- **后端**：新增只读开发来源导出，不写owner或生产准入。**模型质量**：Q01–Q04仍开放，正式完整动作集/独立标签/模型质量未通过。**角色闭环**：这是一条归档use链的字段关联，不新增连续finish/recovery、多领域或A/B/C闭环证明。**Godot**：仍未修改、启动或验证。下一任务按矩阵补实际角色缺少的owner与生产调用，再以冻结输入安排独立开发标注/正式来源；不继续用局部reader或诊断导出测试替代验收。

### Worktable use→finish 跨进程恢复（2026-10-20）

- 新增 `backend/tests/test_worktable_process_recovery.py` 定向回归：真实 `use_object:obj_worktable` 与 `finish_use:obj_worktable` 通过同一 `ESMService` durable object owner，先提交两个原始 owner receipt，再模拟 finish outcome 写回丢失；新 Python 进程只从 SQLite 原回执恢复两个 settlement，补写缺失 session outcome，exact retry 不新增 outcome 或 world event，改变 causation 的合同被拒。工作树 D 盘运行 **1 passed**；精确 HEAD `dc923017` 加新测试的隔离 run `d14ee3c0a3744ad982453ac913eb1171` 也 **1 passed**，cleanup passed，外部 `worktable-process-recovery/`。
- 这只关闭 R09 的 worktable recovery 子项，并证明 owner receipt→角色 outcome 的重开路径；没有提升 R07/R08 的真实 backend/Laya live 证据，也不证明 finish 产出、多领域恢复、模型质量或 Godot A/B/C。


## Soul binding 四门 owner 窄片（2026-10-20）

- 后端：新增 `soul_effect_runtime.py`，仅实现注册的 `bind/unbind`、原 effect ref 反制、真实 link/grant/protection 与目标 vulnerability、完整 incarnation/包版本身份、所有活跃 issuer 的空 fact head0，以及来源读集和 Soul-only 写入同一 CAS。高于或等于 effect 的 protection 阻挡，低于不挡；跨规则保护逐项核验，不以最后一条遮蔽强保护。原 receipt 恢复先于当前 gates，持久化原注册及 vulnerability 摘要，并在原事务前缀中重做 settlement；不宣称 checkpoint/common-cut。
- 验证：双角色 fixture 修复 char_b authored stamina 120 的真实 definition bounds；没有削弱生产校验。effect 文件29 passed，run `e4963d7a5a054d8a93c607943ebbbb61`。另发现4条 effect 的 projection 递归重验15次，新增回归 RED，改为单次同步调用内共享完整 transaction 身份验证集，独立调用重新验证；effect30 passed，run `869d7ae0c0b2497683821cc531109e7f`。精确 HEAD `82cce394` 加本批两文件隔离，Activation/Presence/Soul来源至effect **134 passed**，run `6c71edfa65944337a4e751c9f2937779`；backend-contract `3586c4b5928a46faaf6af66050efb083` passed。以上 scope 均 cleanup passed，外部证据同根下 `soul-effect-fixture-fixed/`、`soul-effect-replay-fixed/`、`soul-effect-isolated-final/`、`soul-effect-contract/`。
- 审查限制：独立 reviewer spawn 因 C 盘空间不足失败，已做作者源码审查，不能记为独立通过。回放仍需逐历史前缀，消除了重复递归，不声称大历史性能已验收。anchor 尚为首 incarnation 单次绑定；重生重新准入仍缺。
- 模型质量：未调用模型、未读取 final/holdout、未训练，Q01–Q04不升级。角色闭环：生产 schema/composition、私有投影、时间/expiry、其他 effect、共同 cut 与 Laya/L4 Soul接线仍缺，D10/R14不关闭。Godot A/B/C未修改、启动、操作或验证。没有运行全量pytest/Harness all，历史修改和证据保留。
- 下一批返回阶段一/二的完整输入与动作目标、真实 owner 回执和正式质量来源，避免继续扩展本局部 owner 测试。Goal保持active；扩展目标由本矩阵与主计划承载，API无法改objective。

## R06 stage 合同正文与身份校验增量

- 精准采用并修复既有 `cognition_frame.py` 草稿，未收编 dirty coordinator/admission/runtime。携带任一合同或摘要字段时，必须有完整 pair 与显式非空原 digest；使用既有 CapabilityEnvelope/CognitionPolicy 重算正文摘要，严格匹配 frame/envelope/policy 的 actor/turn、policy 对 envelope 的完整 revision pins、可选 frame digest/pins/source。无合同字段的旧 frame 保持兼容。validate_frame 无大字段引用时也校验外部 actor；freeze_fields 在写 receipt 前拒绝无效合同。
- 初始 RED：9 个应拒绝输入未抛错；另一写入前拒绝用例到达 Store 缺少 `_json`，不是有效的该项 RED。工作区定向 37 passed，run `ec06efa4d7c940a1ad083ce145f5be2b`。精确 HEAD `bef917e2` 加两份源码/测试与原 committed manifests 隔离 **70 passed / 27 warnings**，run `f41c3ab96e9943279fb9a148b3a892ed`；warnings 为既有 FastAPI lifecycle deprecation 和 Pydantic mappingproxy serialization。backend-contract `de9aa7d371e1401f84068797ca4aa811` passed。外部证据根 `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/` 下 `cognition-frame-green/`、`cognition-frame-isolated-fixed/`、`cognition-frame-contract/`；均 cleanup passed。
- 首次隔离 `3b848fa6de1f42d292c5f9eb645a99da` 为 **16 failed / 54 passed**，副本未带生产 manifests；原报告保留在 `cognition-frame-isolated/`，补齐 HEAD 原资料后同一选集通过。未修改产品逻辑绕过该失败。
- **后端**：本批仅关闭 typed stage 结构自洽校验子项，不是可信来源授权；重算自洽的伪造 pair 仍需 admission/source owner 验证。HEAD coordinator 已携带原合同，现有 admission/session-store 会调用本次校验；额外 source_pins 草稿未采用，不能从结构校验通过声称生产 stage 来源治理完成。**模型质量**：Q01–Q04不变，无模型调用或 sealed split 读取。**角色闭环**：完整 U/P、action+target 与多 owner 生产闭环仍开放，R06不关闭。**Godot**：A/B/C未修改、启动或验证。未运行全量pytest/Harness all、训练；保留历史工作区修改。

补充 HEAD 接线核查与最终恢复验收：HEAD coordinator 已携带原合同，admission/session-store 的 validate_frame 因本批获得 typed 校验；前文已纠正，未采用的是额外 source_pins 草稿。新增真实 pending receipt 篡改 policy 正文并重算 progress digest 的恢复测试，admissions.read_progress 与 coordinator.prepare_l2 均拒绝，SQLite total_changes 不增加。精确 HEAD `60377e33` 加测试增量最终 **71 passed / 27 既有 warnings**，run `68e7ee796ae84f07b51dfa1191bba203`，外部根下 `cognition-frame-resume-final/`，cleanup passed；未扩大测试选集。docs `87fe26980a194cfb84794a467f12cbd0` passed/cleanup。该恢复测试并不验证可自洽重签的外部 source ownership，R06仍局部。


## D09 初始生命周期生产组合（2026-10-20）

- **后端**：采用已有 Activation→Presence→初始 alive 服务与 Life owner 的必要部分；部署通过 `POPULATION_ACTIVATION_GRANTS_JSON` 显式授予版本化身份，默认空 grant 拒绝 spawn；`POPULATION_ACTIVATION_PRODUCER_REF` 精确绑定 producer。main 在同一 durable store 上组合 Activation Authority、可信 ActivationSourceReader、Presence 和初始 Life owner，通过 RuntimeExecution 内部入口串行提交。此入口不是外部认证 API，不证明真实场景 source 已接入。未采用资源时钟 handoff、case-death 或其他历史 main 混改。事件 builder 显式支持 schema2，并将 schema 纳入原 idempotency digest；默认 schema1 保持兼容。
- **验证**：精确 HEAD `8d0955cc` 加暂存源码隔离，初始生命周期/source/Presence **43 passed**，run `9099faa19e5041f59b1d2d7b34e84d4b`；因共享 builder 变更，补入原 settlement recipe/fragment/receipt 兼容选集，最终 **56 passed / 4 既有 FastAPI warnings**，run `e30f1cf4db6e455c881d3e6b587ce16f`。覆盖实际 main 启动、内部 ingress、无 grant/错误 producer/错误包版本零写、原始三条 receipt 的重启复用；模拟 Life 已提交而响应丢失后重开恢复，exact retry 不追加事件。backend-contract `ba2565110552457fb6b9f8302503284c` passed。均 cleanup passed。外部证据根同前，分别 `presence-production-schema2-final/`、`presence-production-compatibility/`、`presence-production-contract/`。
- **失败记录**：隔离 `172b6be6bc2849f0b5e0a4a38ab4f4b5` 5 failed/38 passed，定位历史 ingress 依赖未提交 clock.timeline；收窄暂存组合排除资源时钟。随后 `9ff94013e9e64aa29f50a1169a94096e` 2 failed/41 passed，定位原 builder 不接受 schema_version，采用所需七行 schema/digest 扩展后通过。失败证据保留，不以工作树曾通过替代精确提交证明。
- **模型质量**：Q01–Q04不变；无模型调用、训练或 final/holdout 暴露。**角色闭环**：这是 D08 正式 target/faction 的生命周期前置，仍缺实际 faction producer、角色 action+target caller 与完整 Laya/L4；D09 的 private projection、death/respawn/common cut 未收口，已有 Life history 时无 Life adapter 的 Presence respawn 仍 fail closed。**Godot**：A/B/C未修改、启动或验收。未运行全量 pytest/Harness all。
- **执行与范围**：统一 Goal 继续以本矩阵与主计划的“整体完成十月主线阶段一至三的实现与验收”为准；当前 Goal 工具只能修改 status，无法改 objective，保持 active，不能伪报旧目标完成来替换。下一批推进正式 faction/target 来源与原角色 owner caller，避免继续扩展局部生命周期测试。历史工作树与证据保留，`.harness` status 和实际内容已检查；只清理本轮自有临时副本。

## D08 authenticated faction 来源批次

- 新增 `/admin/combat-faction-relations`，复用已有 world-admin credential verifier、HTTPS/loopback 规则和 RuntimeExecution；初始认证与队列实际执行时再次认证，明确 world 授权并核对当前 backend world。严格规范 actor/target、布尔值和额外字段；调用方不能提交 principal/caller。owner 记录 principal/credential 来源引用，拒绝改变来源、payload、causation/correlation 的相同幂等键，exact retry 恢复原事件。
- 独立 uvicorn backend 进程通过真实 loopback HTTP 提交，停止并重开同一 SQLite 后恢复原 event ID，持久化中仅一条 faction 事件；未授权与改变请求拒绝。另有实际 main runtime 的队列撤权零写与身份替换回归。精确 HEAD `fd48888a`＋本批三文件隔离 **24 passed / 4 既有 FastAPI warnings**，run `5aded566ac5d42bf98b701c3598cfba4`，证据 `faction-admin-process-final/`；backend-contract `103c59e0a50e42ba928086aaf40dfd63` passed；cleanup passed，外部根同上。
- 前轮隔离 `8eb87e5bcbb54cd082ad323873673654` 22 passed/1 failed：测试观察器误认后台提交为目标命令，已按精确 command qualname 修复；修复后 `b1ec915f451143bf9fbd149b80a60b2d` 23 passed。早期重开比较错误已修正：启动可合法追加 cadence，应比较重开后、重试前快照。保留失败记录，不用失败轮次作通过证据。
- 此入口仅授权指定 world 下明确 timeline 的方向性 faction 事实；不授予当前 timeline、encounter、Presence/Life 或 Threat 准入。无外网 TLS 部署证据。此次才将 verifier 的 main composition 纳入提交；此前 `c2ebb578` 仅提交 credential 层，D02 的 cadence 应用路由仍在历史工作树，既有测试部署证据不能推断其已提交。
- **后端**：D08 faction 来源子项完成，完整 target/caller/Threat 仍开放。**模型质量**：Q01–Q04无新增评分。**角色闭环**：完整动作、目标与真实 L4 纵切仍开放。**Godot**：A/B/C 未修改、启动或验证。无全量 pytest/Harness all、模型训练或额外真实模型调用。下一步消费已接通的 Presence/Life/faction 到角色目标准入与执行时 recheck/CAS；禁止仅翻转历史 adapter 常量或伪造 hit。
- docs gate `3c6933d57cf64f208cf81c0a4845d34a` passed/cleanup passed；最终暂存仅整理 faction 模块空行，行为与上述隔离源码一致。

## D01/D08 后端自有 timeline 前置

- 依据规格09 T01/T03、计划04 Task1及本整合计划 Task2，窄采用历史 TemporalProfile/SimulationTimeline/SimulationTime/ClockMapping 与精确 mapping；实际 Population driver 以 `population:<world_ref>` 为 timeline、`population-driver:<world_ref>` 为推进 owner。timeline 来自后端组合，不能由 faction 请求或角色选择覆盖。现有 canonical second/cadence 单位不变；拒绝 raw advance，映射先于 cadence 构建，只有 publisher 确认才推进 timeline。
- Ruling：本批不收编完整时间授权、迁移、跨领域 scheduler 或历史 publisher/main 组合。固定 profile 与 timeline 身份可由实际运行时提供；durable confirmed cursor 仍来自既有 publisher 重开逻辑。timeline 的 authoritative_revision 是本次进程内推进计数，不是持久化 CAS revision；角色执行仍须消费真正 owner source revision。完整时间迁移/授权与 common cut 保持开放。架构、时序、数据流沿用[规格09](../规格/09-通用时间权限投影与领域服务接入规格.md)及其 linked 回写，不新增时间 owner。
- RED `3f575efc252b43338c9583278530e421`：实际 main startup 后无 clock.timeline，1 failed。初次绿色49 passed，run `62c0253b04504cf188034dd6de28608d`；补入错误 unit/revision/timeline 零写、raw advance 拒绝与原 durable cadence recovery 后，精确 HEAD `d37d9c81`＋暂存四文件 **68 passed / 4既有FastAPI warnings**，run `46803e72aad24c43ad2eac68eb274fb7`。三个 scope cleanup passed；证据根同前，目录 `population-timeline-red/`、`population-timeline-green/`、`population-timeline-final/`。覆盖实际 RuntimeExecution、失败发布不推进、真实 cadence 确认推进和 SQLite 重开；不要求启动时没有合法新增 cadence。
- **后端**：仅关闭当前 timeline 来源前置，D01/D08 仍局部；下一项是 Presence/Life/faction 真实 target/caller，而非继续扩展时钟局部测试。**模型质量**：Q01–Q04不变，无模型调用/训练或正式 split 暴露。**角色闭环**：完整动作目标及 Laya/L4/多领域原回执仍开放。**Godot**：A/B/C未修改、启动、操作或验证。未运行全量pytest/Harness all；历史工作树保留，暂存只含四文件必要子集。
- 静态 gate：backend-contract `0eaa92f3a84544e6a5372f83e040463a`、docs `b972a284d5934b65971f9679316686f6` 均passed/cleanup passed（`population-timeline-contract/`、`population-timeline-docs/`）。


## D08／R05 私有 combat 目标来源接线（2026-10-20）

- 后端：从历史 Threat 草稿抽出 `CanonicalCombatTargetReader`，输入仅 actor/target identity，不制造 ActionAttempt 或 physics/contact。实际 main 的原 resolver 保留 ESM，追加显式可见目标的 canonical Presence、当前 Life、方向性 faction 校验；world/timeline 来自当前 backend driver。核验原 owner transaction、activation→presence→life 来源、incarnation、两个历史 Life stream 的最新事实，返回五个原事件、同源 heads 与摘要；只读，不生成领域写入。Threat 草稿的未收编部分保留工作树。
- 边界裁定：来源资格不等于动作权限、范围、contact 或 L4 执行。descriptor 的 supported_intents 为空，affordance 明确 unavailable；后续必须接入注册动作能力、真实执行 owner 的 admission/CAS，不能把本次目录当完整动作菜单。schema2 目前仅正式初始 alive 合同；其他生命周期合同需独立准入。沿用原计划的三张 authority/sequence/data-flow 图，本批仅实现 private perception→owner-scoped target source 的只读边。
- 验证：真实 main startup＋RuntimeExecution，两个显式 grants 的 Activation/Presence/Life、真实认证 faction HTTP、错误 timeline、self/unknown 目标、重开摘要、faction 撤权、Presence 离场及零写。RED `1d92b815c36046aba5eaaa8cd5d76ae3` 正确暴露目录为空。首次 stage script 因 HEAD 模块无预期 __all__ 而未写入 source，随后隔离仍1 failed/34 passed（`f585ff57dae2413daf78c7c7af09b19b`），修正精确采用方式后35 passed（`1c5ed6b8f8c845d59b6ae411a8e4b062`）。补验曾误导入未提交历史测试 helper，collection error（`1daf081cf7f447399bdc43eefd40a756`），已删除该依赖。最终精确 HEAD `fa06649c`＋本批五文件隔离 **90 passed／4既有 FastAPI warnings**，run `02972e53d74343d181cc531155aa22b0`，目录 `combat-target-final2/`；上述 scope 全部 cleanup passed。backend-contract `286460db4d3e4e63a1723b8ea4973b7e` passed／cleanup passed（`combat-target-backend-contract/`）。证据根同前。
- 四组状态：**后端**只关闭目标来源读取子项，D08/R05仍局部；**模型质量**Q01–Q04无新增评分，未读正式 split／未训练；**角色闭环**完整 Laya/action+target/L4/owner receipt 仍开放；**Godot**A/B/C未修改、启动、操作或验证。下一批优先返回无需 physics 的原 ESM Laya→L4→owner 真实链路；combat 动作/Threat caller 后续按其真实能力补齐，避免只继续扩目录局部测试。未运行全量 pytest/Harness all。


## D02 cadence 撤权生产入口收编（2026-10-20）

- 采用历史工作树中经过审查的有限撤权 writer、显式认证 HTTP、排队执行前身份重验，以及 spawn bootstrap 的凭据与原 scheme 传递。原 owner 提交持久事件并绑定认证 principal/credential；exact retry 先查原回执，changed duplicate 零写拒绝。未收编 pinned publication、广泛 temporal grant 或下游 Inventory 撤权逻辑。
- 精确 HEAD `290ce0df`＋六份暂存源码/测试隔离 **62 passed／4既有 FastAPI warnings**，run `bb6eb9bdb65246d098eadda94e62409b`；包括真实 spawn child、HTTP/HTTPS transport metadata、非本机 HTTP 拒绝（伪造 forwarded header 无效）、凭据未配置、排队期间撤权/过期/身份变化、持久事件、新进程原回执恢复。使用 TestClient/ASGI transport，未证明外网 TLS 部署。
- RED `b1a63568b90c46f799cd885df8190d33` 8 failed，暴露 HEAD 路由缺失与 credential JSON 序列化问题；首轮 GREEN `0528309f54254cfb936d63b115b127e1` 60 passed／2 failed，分别为重启可合法追加 cadence 的快照比较与旧测试将结构化凭据替换为字符串；修正 fixture 后重验通过。保留失败证据。外部根下 `cadence-production-red/green/final/`，均 cleanup passed。
- backend-contract run `648c9b3904674815b1dfbcc56d243967` passed／cleanup passed，导出 `cadence-production-contract/`。独立静态审查未发现本批阻断问题，并指出 faction route 尚未加入 spawn HTTP 路由表，下一批直接修复此生产缺口。
- **后端**：D02 只关闭持久撤权应用入口；正式 consumer 取消读集/CAS、完整 grant 生命周期与外网部署仍开放。**模型质量**：Q01–Q04 无新增分数。**角色闭环**：完整动作＋目标／Laya／多领域原回执仍开放。**Godot**：A/B/C 未操作。无全量 pytest、Harness all、模型调用或训练；历史 dirty 与历史证据保留。


## D08 faction 生产 spawn 路由修复（2026-10-20）

原 main handler 与 component HTTP 已存在，但生产 parent 的命名路由白名单遗漏 `record_world_admin_faction_relation`。真实 spawn RED 三项均在认证前404，run `cd31f3617c924337b57601fbbc8d4291`。仅补原路由名；精确 HEAD `aed7164b` 加源码与新增生产测试，定向隔离 **41 passed／4既有 FastAPI warnings**，run `41800777a7484251b45283598a135f93`。包含 actual child PID、loopback HTTP、remote HTTPS scope、remote HTTP即使伪造 forwarded header仍403、无凭据403、原 faction owner durable事件、changed duplicate409、新进程 exact receipt replay与零新增 faction event、child退出和credit归零。ASGI TestClient的scheme/peer不是外网TLS部署证据。外部证据根的 `faction-spawn-red/green/` 均 cleanup passed。

后端 D08 的认证 faction 来源现在覆盖默认生产 spawn host；管理员显式 policy timeline 不授予当前 encounter、action、contact 或 physics。完整 target/action admission、真实角色/Laya/多owner回执仍开放，Q01–Q04与Godot A/B/C状态不变。未运行全量pytest/Harness all、模型或Godot，未改历史草稿。

本批 backend-contract `8f7b5d36776044b1baf17311aae61495` passed／cleanup passed（`faction-spawn-contract/`）。


## R01 MindFrame→L3 实际输入前置修复（2026-10-20）

HEAD的原L3已经读取frame_digest/turn/revision字段，而已提交MindFrame没有对应合同；此前frame=None路径掩盖错误。本批仅采用历史草稿中的turn字段，修复幂等绑定摘要、MappingProxy JSON序列化、正文与当前turn重新校验；未收编regulation/self/external工作区草稿，也未声称输入source authority。冻结前绑定现有CharacterTurnContext，候选与execution_contract携带同一digest/pins；跨actor/branch/input/memory/policy/snapshot及冻结后正文改动拒绝，旧unbound diagnostic保留。

精确HEAD `7835655a` 加三份暂存源码/测试，隔离 **90 passed**，run `96b45e76e6974f879b282745c365e797`，涵盖原frame model/builder和L3；RED11failed `55179ca124d744d6bf782381ff69dbe4`，保留AttributeError及缺少binding的原失败。外部证据 `mind-frame-turn-red/green/`；backend-contract `2205567e73954ed28675703abc9d65cc`（`mind-frame-turn-contract/`）passed；均cleanup passed。本轮faction文档门禁 `9eb027200eb449ff9915c155ef02e56b` passed。

R01/R06仍局部：production runtime尚未把同一MindFrame交给L2/L3，来源/revision及self/external完整字段尚缺。下一批直接补原生产stage同帧输入，不扩大此helper测试作为核心闭环替代。Q01–Q04、完整角色owner闭环、GodotA/B/C不升级。无全量pytest/Harness all、模型调用、训练或Godot。

### R01/R06 durable MindFrame production integration (2026-10-20)

- Existing L2 now builds the original layered frame after semantic recall from its actual private snapshot, effective profile, selected memory and runtime context, binds canonical turn/source pins and serializes plain JSON. Durable Siming/background persist that exact frame and feed it to original L3, including restart from provider-pending. Legacy requests without a frame remain recoverable. Synchronous L3 propagation remains open.
- New actual coordinator/restart tests prove identical L2/L3 frame JSON and candidate/execution frame pins; changed body rejects before provider. Selected-memory test proves excluded memory does not reenter via frame. No raw live-state recomputation is used on resume. This is frozen content consistency, not independent source authentication, full MindFrame semantics or complete Laya/owner closure.
- RED 2 failed: c626a5b9e64f44149cbbc2a65fa11f9b. First integration 88passed/2failed (81bbc2fa7d604c7d8f9f4690380cd0df): error-message regex and missing background mode restoration in the test. Next 90passed/1failed (3530a420ab2f40668926fe941163b338): incomplete private snapshot fixture. Both preserved; production source unchanged after first GREEN implementation. Final exact HEAD fe436ce5 + three staged files: **91 passed**, run **755417df1a9e4482b35193860de065c6**; original durable/shared/runtime contracts, frame builder and L3 regressions included. backend-contract **22788d6f09304cf59019aefe5a0b28d6** passed. All cleanup passed. External evidence root `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/`, prefix `durable-mind-pipeline-`.
- Backend R01/R06 remain partial. Model Q01-Q04 unchanged; character complete action/target/owner/recovery remains open; Godot A/B/C deferred, not run. No full pytest/Harness all, live model or training. Historical modifications and .harness contents preserved. Next wire same-frame through synchronous real role entrypoints, then return to full action/target quality sources and owner dependencies.

### R01/R06 synchronous MindFrame integration (2026-10-20)

- The existing interpretation helper captures prepared L2 JSON into the per-turn context; original perceived/self-body/Siming/background planners restore and validate that frame. L3 sends plain frame JSON across the gateway boundary, avoiding deepcopy of frozen mapping proxies. Pre-L2 contract compilation stays once per turn. No live rebuild at L3.
- Actual four-entry regression RED4failed missing L3 frame, run 2ec739abec844e8dbb967ffe866730d2. Exact HEAD62135cc7 plus three staged files GREEN **102 passed**, run **c161e1b43c8a48d9aeb045b21a4d1524**, cleanup passed. Includes durable restart, excluded memory, boundary/model pins, original L3 and frame builder. Export prefix `sync-mind-pipeline-` at the existing external evidence root. Backend-contract evidence is recorded with this batch below.
- Ruling adjustment: assisted suggestion propagation is a separate open lane; this batch covers only the four ordinary entrypoints tested. Legacy no-frame fallback remains compatible. Complete private/self/external frame semantics, authoritative revision sources, role/owner closure, Q01-Q04 and Godot A/B/C stay open. No broad pytest/all/model/training/Godot. Return next to complete action/target source and formal quality dataset freeze, rather than more local frame tests.

Synchronous batch backend-contract6c03fc98506d436a82e96f52fb827682 passed, cleanup passed.

## Q02 original owner snapshot association (2026-10-20)

- Audit: existing `prepare_character_evaluation.py` authors only observe/ask_probe/defer with unassigned owners and empty envelope/policy. Both it and `prepare_calibration_preclosure.py` call historical `event_inbox`/workspace builder APIs absent from committed HEAD; old source pins also drift. These packages retain their historical diagnostic identity, not a reproducible complete action/target formal dataset. No sealed final/holdout data or labels were read, no source pins refreshed.
- The existing runtime development exporter accepts optional `--owner-snapshot`, reading original Gameplay JSON bytes once, restoring the original store and ESM owner, then checking canonical L4 request identity/pins, original event/transaction/receipt and boundary result. Supplied corrupt snapshots fail rather than degrading to unverified. Only event/receipt digests and identifiers are exported, no authority-only payload. No writable SQLite open or authority execution occurs; snapshot bytes remain unchanged. Without a snapshot, legacy archive consistency stays explicitly unverified.
- Exact HEAD `1e74ec2d` plus three staged source/test files: RED **7 failed/21 passed**, missing optional source API, run `ae27c78b56954c5db4d4834d141f3e12`; GREEN **112 passed**, run `80646d3a89194154b55045f84d824eeb` after tightening wrong same-key action/actor/correlation/boundary/missing-receipt rejection assertions. Durable ESM commits/reopen and existing gateway tests included. First GREEN `22b619cad23744b186b957bc2149fdf9` also 112 passed, but weaker action test superseded. Evidence prefix `owner-source-association-` at the existing external root; all cleanup passed. Backend-contract `b6bf061fc34f4d1283a5f901ec1d3f4d` passed/cleanup passed.
- Backend: source association subitem complete. Model quality: Q01-Q04 remain open; `snapshot_matched` proves consistency of supplied artifacts, not independent authenticity, source reviewer approval or quality. Role closure: synthetic model-choice tests with actual durable owner commits are not new live Laya receipt/recovery proof; R07-R09 stay partial. Existing live run owner DB was cleaned, so no retrospective owner validation is claimed. Godot A/B/C remain unmodified/unstarted/unverified. No full pytest/Harness all, model calls or training.
- Next: return to missing original domain owner/caller dependencies for complete action/target coverage; do not keep expanding trace parser tests or promote exposed diagnostic archives into calibration/final/holdout.


## D02 Inventory 撤权读集与原 owner CAS（2026-10-20）

- 已提交主线缺少下游撤权检查；本批将 `InventoryOutputCustodyOwnerExecutor` 绑定到原 `world_runtime.cadence` 准入回执、事件/事务归属、精确 cadence 和 record digest。缺失、漂移或已撤销准入零写拒绝。读取准入/撤权流版本在校验前完成，传入原 Inventory command 的 read-set CAS；没有新增 authority store 或绕过原认证/内容/holder 校验。
- 正常准入使用实际 `WorldContinuityRuntime`→`RuntimeCadencePublisher`，原生产认证和 Inventory owner；原角色 seed 回归同时保留生产投影 revision pins。测试覆盖新提交与 exact replay、未准入、撤权、changed cadence、内存/SQLite 的“检查后、append 前撤权”零写，以及 SQLite 重开后仍拒绝。
- 精确 HEAD `31df8650`＋本批四份暂存源码/测试隔离 **33 passed／4既有 FastAPI warnings**，run `694911dd6ed94343b699a1cf997dafc3`，导出 `inventory-cadence-commit-green-durable-final/`。RED `a68325d143574715b62a2a4c6b70915e` 为 **4 failed/1 passed**，正确暴露缺失准入/撤权/CAS。首轮测试夹具把 Pydantic mode 当 dataclass（`a8b69160eafa428f8aae97e1ec13f216`）；首轮 GREEN 漏生产投影 pin（`df69ad7927b44bf19108689a06415430`，1 failed/30 passed）；补验持久 owner 时遗漏 registry 参数（`60074b3dcc844fd183a1171190f246dc`，2 failed/31 passed），均已修正且保留诊断。backend-contract `a359f759e5cf42f3988eb4eb5492fe71` passed，目录 `inventory-cadence-commit-contract/`。以上均 cleanup passed；证据根同前。
- **后端**：仅关闭 Inventory 撤权下游与原 CAS 子项；没有采用工作区更广的 temporal-pins、binding freeze 等历史草稿。正式 driver→全部领域投影的投递、完整 grant/cutoff/order 与其他 consumer 仍待完成；未证明外网 TLS 部署。**模型质量**：Q01–Q04 无新增通过。**角色闭环**：受控 capability→原 owner/seed 测试通过，不是 live Laya 或跨领域闭环；R07–R09 保持局部。**最终 Godot**：A/B/C 未修改、启动或验证。
- 工作区按精确 HEAD 补丁暂存，保留三份相关文件中的历史草稿与其余用户改动；未运行全量 pytest、Harness all、模型、训练或 Godot。下一步回到正式角色动作/目标与领域 caller 的缺口，避免继续扩展本地撤权测试代替阶段一、二验收。


### Laya credential routing isolation (2026-10-20)

The original shared provider forwarded the reasoning API key when L3 routed to Laya. RED two cases reproduced missing dedicated key and overridden dedicated key. The fix only permits native provider_kind=laya to use its constructor key; routed Laya uses CHARACTER_LAYA_API_KEY exclusively. Exact HEAD 2ad3d7e1 plus provider/test overrides: GREEN **100 passed**, run bb9318dab4ca4aac9ad720d96ca6eb9f; backend-contract a981e1a7f7a44951af8e76c6c4ebeb65 passed. Cleanup passed for both. External evidence: credential-route-green/ and credential-route-contract/ under the existing evidence root. RED97b88aedeb5b4afda4361d9ed6ecf342 retained.

Backend: credential isolation complete; integrated online L2/Laya not yet proven. Model Q01-Q04: unchanged, no new quality score. Role: live continuous use/finish and complete owner closure remain open. Godot A/B/C: not operated or verified. No broad pytest/Harness all, formal split access, new model calls or training. Next return to sourced task/goal admission and original domain owner dependencies; Godot stays last.


### Real online L2 + Laya worktable cycle (2026-10-20)

Exact HEAD 4895e7be, run d7df5cbf74f046b48f88ceecc92f46a6, export laya-worktable-real-l2-diagnostic/ under the existing external evidence root. Actual component_app/RuntimeExecution, authenticated WS and controller samples, DeepSeek L2 (deepseek-v4-flash, api.deepseek.com, succeeded/no fallback), official CUDA Laya, original L4/ESM. Laya selected use_object:obj_worktable then finish_use:obj_worktable; owner transactions 5efe5d357f4378db0475365744a690496317250267f93e6fc161f855e4d8ba90 and 921c5bcd783aefb99cb5aeff6f0b268cdc3d04bd0d6a5d07c8b957ee930ec52b (transaction:esm-object: prefix). Final state ready. Fresh subprocess reopened original session/gameplay stores and restored both receipts twice with zero new world writes, original sequence509. Input6508/7962 required tokens, no truncation or option loss. Cleanup passed; owned backend and Laya stopped, listeners8765/18766 absent. This adds a live continuous worktable cycle to R08/R09, not complete coverage.

Inputs remain generic object availability and original continuity goal shell, not a sourced completion task. Development-only/unscored, formal_eligible=false, no final/holdout access or training. Full task/goal admission, cross-target/multi-owner role closure, Q01-Q04 remain open. Authenticated development spatial samples do not prove physics. Godot A/B/C not operated.

The live archive exposed a generic evidence defect: the routed provider reported Laya provider_kind with the reasoning host/model. Actual Laya endpoint, pinned checkpoint, call/result and budget were separately captured by the original Laya wrapper. Preserve the original archive and discrepancy; do not rewrite its evidence as corrected. Subsequent minimal fix adds explicit actual endpoint/model overrides to Laya success/failure evidence. RED2failed/4passed run4642d305dce347f88c9db91d394be535; exact HEAD4895e7be plus two changed files GREEN102passed run d9376b7e2ee746f7a627086817838026, cleanup passed. Prefix laya-transport-metadata-. No repeat live model calls solely to refresh metadata. Next sourced player request via original DialogueSubmit cognition ingress and original domain owner dependencies; Godot last.

### Sourced dialogue dispatch repair (2026-10-20)

Original live run `508bccb8d021488f9644017cab4e7e18`, exact HEAD `16357069`, exported as `laya-worktable-sourced-dialogue-diagnostic/`: first raw visual input produced use_object and its original ESM receipt. The second actual wire input was a player DialogueSubmit asking to finish the current worktable operation and stop using it. L2 correctly interpreted that instruction; Laya selected finish_use with the original worktable target and L4 persisted the contract. DialogueCoordinator discarded that non-speech output, so only the first action executed. Final state remained engaged, sequence499; fresh-process retry recovered the original use receipt twice without new world writes. This archive is development-only, unscored and formal_eligible=false. The earlier generic `input` trace row is not the replaced second wire payload; `sourced_task_input` records the actual dialogue source. Preserve the archive unchanged.

Backend repair retains completed cognition commands as frozen JSON, drains existing ESM inspect/use/finish contracts once on the runtime owner, and uses the original egress lease/client echo/L4/owner path. Connection, bound actor scope, activation and context are checked before egress and before each wire frame. Pin capture follows the original dispatch-offer session write, avoiding self-invalidating egress. Direct speech keeps its existing path. Exact HEAD plus only this repair and new test: **88 passed**, run `8af0de7885f240a59ef77d7d30e7c184`, export `dialogue-dispatch-final-authenticated/`; includes authenticated WS receipt, original durable ESM, owner-thread mutation, one-shot drain, cancellation/disconnect/context/actor-scope rejection and adjacent lifecycle/executor tests. Corrected RED `3eca282d592d415ab697ff9cd808975e`: 5 failed/81 passed on missing drain. Initial RED included an invalid command-type fixture; initial GREEN and network diagnostics also exposed test JSON representation/scope mismatches and the repaired offer/pin issue; retain all archives as diagnostics. Backend-contract `511c438a83f04c34b6f831fdc3424e62` passed, export `dialogue-dispatch-contract/`. All run scopes cleaned successfully. No broad pytest/Harness all, model calls, training or Godot in the repair batch.

**Backend:** dialogue ESM dispatch repaired; complete action/target and other domain callers remain partial. **Model quality:** Q01–Q04 unchanged, no new score. **Role closure:** controlled authenticated dialogue→egress→echo→original owner receipt verified; post-fix live sourced Laya cycle and source goal arbitration remain open. L2 goal hints still do not establish authoritative task goals; no direct promotion of model hints. **Godot:** G-A/B/C unstarted and last. Next audit existing goal admission and role/domain dependencies rather than expand local dispatch tests.


### Sourced dialogue post-fix failure and canonical actor authorization (2026-10-21)

Real run `5319ab0490a8491f88cadfc71a3e8006`, exact HEAD `45eae25a`, exported `laya-worktable-sourced-dialogue-postfix/`: online DeepSeek L2 and official CUDA Laya selected use_object then finish_use from the actual player DialogueSubmit. Both cognition completions and the second canonical L4 contract were persisted, but only one execution reached the original ESM owner; final state engaged, sequence515. Fresh-process retries restored only the original use receipt with zero new world writes. Launcher/recovery exit0 and trace errors=[] do not constitute acceptance. Preserve this failed development archive, unscored/formal_eligible=false. Owned backend/Laya stopped and run cleanup passed.

Root cause: DialogueCoordinator compared raw runtime actor ID `char_a` to binding refs `character:char_a`; existing main boundary uses the canonical prefixed ref. Prior authenticated regression accidentally issued raw-ID credentials. Corrected real WS regression RED1failed/87passed (`7c1bc46750204ba49282f75ca513940d`); final focused RED also exposes bare-ID overgrant, 2failed/6passed (`c9069454b58944b9af9ccb2dc863bb41`). One production comparison now uses the canonical ref; test credentials match production, and bare IDs reject. Exact HEAD45eae25a plus clean repair GREEN **89 passed/104 existing warnings**, run `97418c91c32c4d1ca6a7554b1cf66c84`; backend-contract `9b73e5d7247a46c2824091bbc244d485` passed. Exports `dialogue-dispatch-canonical-scope-{red,red-final,green,contract}/`; all cleanup passed. Historical speech-lease changes in the working production file are excluded from this patch.

Slow goal audit: `LayaSystemOneProvider.complete` returns the input active_goal_frame; `prepare_intent_plan` supplies a persisted frame or preserve_continuity shell. Existing goal event/store projection admits and records a proposed frame but does not perform slow model reasoning. Thus there is no independent triggered slow-model goal reorganization on the Laya path. Keep this R01/R07 gap explicit; do not promote L2 goal_hints directly, fake a finish goal, or force every fast turn to await slow reasoning. Next design the bounded asynchronous proposal using existing gateway/coordinator/frozen admission and original goal owner; stale/expired/context-changed proposals must zero-write. No second scheduler/lock/store.

Backend: canonical actor scope defect fixed and controlled WS owner path verified. Model quality: Q01-Q04 open; these are development diagnostics, no quality pass. Role: sourced live post-repair cycle still requires one measurement on the corrected code; multi-domain/slow-goal closure open. Godot G-A/B/C unstarted, last. No broad pytest/Harness all, formal split access or training. Overall objective remains stages1-3; Goal status active, objective-edit API unavailable.


## 修复后 sourced DialogueSubmit 真实闭环（2026-10-21）

- 精确 HEAD `d791d273`，run `4acb2162822c475f80be5c945ee67009`，外部证据根下 `laya-worktable-sourced-dialogue-canonical-scope/`。实际 backend/RuntimeExecution、认证 WS、在线 DeepSeek L2（deepseek-v4-flash，transport_succeeded=true/fallback_used=false）、官方 CUDA Laya、原 L4/ESM。先 use_object，再从真实玩家 DialogueSubmit“完成当前工作台操作并停止使用”选 finish_use；两个原合同 source 分别为 visual_fact:10000:char_a 和 dialogue_submit:11000:player:char_a。
- 原 ESM 提交两条 transaction:esm-object 回执，后缀分别 `5efe5d357f4378db0475365744a690496317250267f93e6fc161f855e4d8ba90`、`63fcff4957fb65ee1bbc710c488aaee214122fd0f32934586776c14c5206c45c`；最终 ready。独立新进程重开原 session/gameplay store，两次 exact retry 恢复原两条回执，sequence514、零新 world 写入，仍 ready。不是仅依据 launcher exit0 判定。
- **后端**：修复后的 sourced worktable dispatch/owner/recovery 子项已验证。**角色闭环**：R08/R09新增这一真实连续子项；完整 action+target、多 owner、慢目标重组、完整回放仍开放。**模型质量**：development-only、formal_eligible=false，Q01–Q04未验收；未读取 final/holdout、未训练。**Godot**：A/B/C未修改、启动或验证；spatial 来源为认证开发控制器，不能证明 physics。
- runner cleanup passed，临时根已不存在，8765/18766无监听。WSL清理命令退出0；外层 subprocess 文本解码出现 UnicodeDecodeError，保留输出，不将其等同产品失败或独立清理证明；最终端口及临时目录检查确认回收。原始失败证据保留，无全量 pytest/Harness all。
- 后续源码核对确认 Soul timeline 审查项已经由 `9d25d89b` 修复；不重复修改或测试该项。下一批处理慢目标重组的冻结提案输入和路由，随后接现有 coordinator/driver 重新准入；单纯请求准备不能关闭R01/R07。


## R01/R07 slow goal proposal contract batch 1 (2026-10-21)

- Backend: explicit `l3_planning` / `goal_proposal:v1` input freezes typed MindFrame, original envelope/policy, permitted evidence and goal revision/expiry. Generative routes only; provider bypasses action coercion. Output is typed goal frame plus permitted evidence, without selected action or model-supplied request identity. This validates data contracts, not lawful source admission or owner commits.
- Independent read-only review identified ambiguous portfolio IDs/references. RED reproduced 5 failures/156 passes; duplicate IDs, dangling references and conflicting preserved/suppressed goals now reject. GREEN **161 passed**, exit 0, run `c6a192ef1b2b48078b7297bf4eded674`, exact HEAD `f5734c9616196b4ec1ff05d95439232c21d34684` plus six owned file overlays (SHA256 in manifest). Existing gateway user hunk excluded from overlay/staging. External evidence root: `D:/Users/User/Documents/paralls-evidence/october-stages-1-3-20261020-01/`, `slow-goal-contract-review-red` and `slow-goal-contract-review-green`; cleanup passed, temporary checkout removed. Earlier intermediate failures remain archived, not counted as passes.
- Static backend-contract passed, run `c710f851b1b240348d192d85a3890710`, export `slow-goal-contract-backend`, cleanup passed. This profile checks general static boundary contracts only. No full pytest/Harness all, live model request, evaluation dataset access, training or Godot work.
- Model quality: Q01–Q04 remain open. Role closure: R01/R07 partial; original action-free goal calculation, durable child receipt/CAS/recovery, fast/slow driver coexistence and live sourced goal→Laya→L4→owner chain remain unimplemented. Existing sourced ESM evidence is reused; no redundant live rerun. Final Godot A/B/C remain deferred and unverified.
- Next dependencies: child plan batch 2 goal calculation/recovery, batch 3 original store/owner lifecycle, batch 4 driver, then batch 5 development live chain. Formal quality remains its separate frozen isolation gate.

Contract commit `063b29a0`; docs first failed (`7dae8ac4ffd64e03a0462d5d6e259412`) because the new plan used `-plan.md` instead of the repository-recognized `-implementation-plan.md`. Renamed only the owned new plan and links; docs passed (`c7c5de36cc144d7b8afd99a70dfde7df`, export `slow-goal-contract-docs-corrected`). Both runs cleaned successfully. Historical `.harness/verification` data and pre-existing registry changes preserved. Goal API remains active with its old objective because available update API only accepts status; this matrix and main plan govern the user-authorized expanded objective.


## R01/R07 original goal transition batch 2 (2026-10-21)

- Backend: commit `4f2dd2bd` extracts the existing goal-frame transition calculation; action decision payload semantics preserved. Proposal planner validates frozen context/output and emits only goal fields plus versioned provenance (original request/turn/source/revision/frame digest/evidence); it writes no event or executable action itself. Original session projection validates provenance, rejects unknown/malformed contracts or action-bearing proposal events, and restores the same goal after SQLite close/reopen. No additional persistence owner.
- Exact HEAD `374ca1fd` plus owned overlays: RED `89c60da603d04c8793293fd8aa94e6b3`, 9 failed/55 passed (8 new missing behavior; 1 pre-existing AST test requiring exactly 31 callsites when HEAD has 32). Replaced brittle callsite count with actual direct-write ownership and pure-planner assertions. Intermediate `e83a88472d54435898b77bdb0cf5431f` 1 failed/63 passed; `00b117f9456140bea3f358fb7ea2f1a1` collection error from wrong test import, corrected. Final `7c8e2eab239a454b90ffa11025709ed4` **64 passed**, exit 0, 35.93s. SHA256/commands in exported manifest; runtime overlay contains only owned helper block, preserving historical worktree changes. Unmodified goal_state_store included as an identical source overlay.
- Backend-contract passed `18597a01002046009e9ce94c98a24e97`. External evidence root unchanged, prefixes `slow-goal-transition-`; all cleanup passed. Four existing FastAPI lifespan deprecation warnings remain. No full pytest/all, live model/network, formal dataset, training or Godot.
- Model quality Q01–Q04 open; role closure R01/R07 partial: durable original owner child admission/terminal receipt/CAS/crash recovery and fast/slow driver coexistence remain unimplemented. This reopen test is projection recovery, not proposal exactly-once recovery. Final Godot A/B/C untouched and unverified. Continue batch 3 on existing session receipt/index transaction, then batch 4 driver and sourced development chain.

## R01/R07 slow proposal durable preparation batch 3 progress (2026-10-21)

- `62d74aa7` adds `goal_proposal` as a durable cognition progress stage, permits its initial `provider_pending` transition, and makes terminal `cancelled`/`failed` states recognizable by the progress schema. A real SQLite close/reopen test confirms the frozen request and progress receipt remain identical. `9c48b5e6` fixes coordinator retry to return this original request without re-running route selection or rebuilding bytes. These are preparation primitives, not proposal acceptance.
- `281b734c` requires trigger source identity to resolve to a committed event in the same actor session; uncommitted or cross-actor sources fail before writes. This proves source existence and actor scoping only, not trigger eligibility or context authenticity.
- `ae3660a4` adds an atomic session-store guard for one pending `goal_proposal_trigger` child per actor; a second slow child is rejected without receipt/index writes, a terminal stale child releases the slot, and an ordinary cognition admission remains allowed. Focused admission evidence: `python -m pytest -q backend/tests/test_character_cognition_admission.py`, 24 passed, exit 0.
- RED for durable transition reproduced the prior schema rejection. Focused admission/coordinator/contract/transition/atomic tests passed 77, exit 0; after adding retry routing regression, admission/coordinator tests passed 24, exit 0. No external Harness run was needed for this narrow backend persistence change; no full pytest/Harness all, model call, formal calibration/final/holdout, training or Godot.
- **后端**：慢目标持久请求准备局部实现；已补每 actor 一个 pending 的原子 admission guard，但合格 trigger 与 frozen frame 绑定、owner 接纳时原始 pins/session head 重验、goal event+terminal receipt+CAS 原子提交、取消/失败/恢复仍未完成。**模型质量**：Q01–Q04 未验收。**角色闭环**：仍缺真实慢提案与完整 Laya action+target→L4→领域 owner 回执/恢复。**最终 Godot**：A/B/C 未操作、未验证，保持最后。
- Goal objective-edit API unavailable; the user-authorized expanded objective remains authoritative in the matrix and main implementation plan, with Goal status active. `.harness` registry/profile modifications and prior evidence remain untouched. Next: derive trigger exclusively from an eligible committed actor outcome and its frozen frame, then implement coordinator terminal acceptance before driver work.

### 2026-10-21 settlement outcome private projection recovery

Settlement events now persist the runtime-derived private L1 snapshot after
recording the outcome projection. Session recovery validates the snapshot
schema and actor identity before restoring it; replay comparison excludes the
derived projection so an exact substantive settlement retry remains
idempotent. Focused recovery regression verifies SQLite close/reopen parity,
exact retry without a duplicate event, and rejection of a cross-actor snapshot.
The combined command
`python -m pytest -q -p no:cacheprovider backend/tests/test_character_session_recovery.py backend/tests/test_character_slow_goal_main.py`
passed **56 tests**, exit 0 (4 existing FastAPI lifespan deprecation warnings).

This closes only settlement-event private snapshot projection recovery. It does
not prove provider-worker recovery, actor-pin/timeline equivalence during
startup polling, slow-goal exactly-once recovery, sourced Laya action+target to
L4/domain receipt, formal Q01–Q04, or Godot G-A/B/C. Backend remains partial;
model quality remains unverified; role closure remains partial; final Godot
acceptance remains untouched. The implementation touches a `runtime_loop.py`
with extensive pre-existing worktree changes, so no path-level commit was made
to avoid staging user changes. No full pytest, Harness all, model evaluation,
training, or Godot operation was run.

## R01/R07 slow proposal source eligibility binding (2026-10-21)

- `cognition_admission` no longer treats any same-actor committed event as sufficient for slow-goal admission. A source event must carry eligible trigger metadata with an allowed kind, frame digest and non-negative goal revision. Caller-supplied `source_contract` and trigger kind must match those committed fields; ineligible, changed or missing metadata rejects before admission/index writes. No production trigger producer currently creates this metadata, so this is a fail-closed admission guard, not a live trigger path.
- `prepare_goal_proposal` performs the same binding check when the original session store can read the source event: the persisted context frame digest and goal revision must match the committed trigger metadata before a provider request is prepared. This is a source/frame authenticity guard, not yet full frozen MindFrame reconstruction or owner acceptance.
- Focused verification: `python -m pytest -q backend/tests/test_character_cognition_admission.py backend/tests/test_character_slow_goal_coordinator.py` → **31 passed**, exit 0. No full pytest/Harness all, model, formal quality split, training or Godot.
- **后端**：慢目标 admission 增加来源 metadata 及 caller mismatch 零写门；生产 trigger producer 尚未接通，仍缺从持久 source/frame 重建完整 `GoalProposalContext`、原始 read-set/pins/session head 重验、goal event+terminal receipt+CAS、取消/失败/恢复和 driver 共存。**模型质量**：Q01–Q04 未验收。**角色闭环**：仍缺完整 Laya action+target→L4→多领域 owner 回执/回放。**最终 Godot**：A/B/C 未操作、未验证。

## R01/R07 source readability fail-closed guard (2026-10-21)

- `prepare_goal_proposal` now requires the original session store to expose a callable `read_event`; a store that cannot read the committed trigger source is rejected with `cognition_goal_proposal_source_unreadable` before progress or provider calls. The coordinator test fake now models the committed source event instead of bypassing source verification.
- Focused verification: `python -m pytest -q backend/tests/test_character_cognition_admission.py backend/tests/test_character_slow_goal_coordinator.py` -> **32 passed**, exit 0. This is a narrow fail-closed guard; it does not create a production trigger producer, reconstruct a frozen MindFrame, or implement owner acceptance/recovery.
- Follow-up verification: the same admission/coordinator focus now passes **33 tests**, exit 0. Coordinator preparation also rejects a persisted source whose `eligible` flag is false or whose trigger kind is outside the registered allowlist, before provider preparation or progress writes. This remains a guard only; no production trigger producer is claimed.
- **后端**：source readability guard completed; R01/R07 remain partial because eligible outcome/frame production, terminal owner receipt/CAS and driver coexistence are open. **模型质量**：Q01–Q04 未验收。**角色闭环**：仍缺完整 Laya action+target→L4→多领域 owner 回执/回放。**最终 Godot**：A/B/C 未操作、未验证。

## R01/R07 slow proposal owner acceptance and terminal receipt (2026-10-21)

- Coordinator now revalidates the frozen trigger contract and expiry at acceptance, checks current actor pins, plans through the original Character goal transition helper, and commits the goal event with terminal child receipt/progress CAS in the existing SQLite session transaction. Stale/cancelled/failed terminal outcomes use the same transaction with zero goal events; terminal exact retry reads the original receipt. Runtime recovery projection is installed after commit.
- Focused RED confirmed the owner acceptance API was absent. GREEN: coordinator + atomic store tests **24 passed**; coordinator + goal transition + admission slow-goal selection **21 passed (22 deselected)**; final coordinator + atomic acceptance **24 passed**. No live model/backend run, formal model evaluation, full pytest/Harness all or Godot operation.
- **后端**：关闭 coordinator/store 原子 owner acceptance implementation 子项；生产 trigger producer/frozen MindFrame reconstruction、driver/fast-loop coexistence、pending worker generation and crash-after-commit end-to-end recovery remain open. **模型质量**：Q01–Q04 未验收。**角色闭环**：完整 live Laya goal→action+target→L4→domain owner receipt/recovery 未通过。**最终 Godot**：A/B/C 未操作、未验证，仍为最后门槛。

### Driver terminal-state guard

慢目标 driver 现将持久终态 `cancelled`、`failed` 与 `stale`、`completed`
统一处理。取消或失败后到达的 provider 结果不会重新取得 actor activation，也
不会再次提交 goal/world 写入；新增 terminal regression 与既有 slow-goal、driver、
admission、owner acceptance、runtime trigger 组合选择共 **77 passed**。
这只是 fail-closed 生命周期边界，不代表同角色快慢并行的真实延迟运行、真实
provider dispatch、完整 Laya/领域 owner 闭环、Q01–Q04 或 Godot A/B/C。

### 2026-10-21 本轮慢目标定向复验

本轮重跑完整慢目标合同、transition、atomic acceptance、coordinator、driver dispatch/terminal、runtime trigger、trigger producer 与生产 lifespan 选择：
`python -m pytest -q -p no:cacheprovider backend/tests/test_character_slow_goal_contract.py backend/tests/test_character_slow_goal_transition.py backend/tests/test_character_slow_goal_atomic_acceptance.py backend/tests/test_character_slow_goal_coordinator.py backend/tests/test_character_slow_goal_driver_dispatch.py backend/tests/test_character_slow_goal_driver_terminal.py backend/tests/test_character_slow_goal_runtime_trigger.py backend/tests/test_slow_goal_trigger_producer.py backend/tests/test_character_slow_goal_main.py`
→ **77 passed in 7.36s**。私有 L1 恢复选择
`python -m pytest -q -p no:cacheprovider backend/tests/test_character_session_recovery.py -k "settlement_recovery_restores_private_l1_outcome_projection or ready_restores_private_l1_snapshot_from_committed_context_stage"`
→ **2 passed, 53 deselected in 0.96s**。

以上是慢目标合同、owner 事务、driver seam、单进程生产 composition 和私有 snapshot reducer 的定向回归；没有重跑 goal-proposal 硬杀恢复复现。因此不能关闭 R09，也不能证明新进程启动自动轮询不改变恢复 pin。下一步应复用已有真实 SQLite crash runner，增加 `goal_proposal` 家族，并分别采集第二进程初始化后、首轮 driver poll 前后、provider dispatch 前的原 request/admission、actor pin 分量、timeline/session head、private snapshot 和 goal terminal receipt。provider request 必须保持原 bytes；若 pin 确有外部更新则继续 stale/零写，不放宽校验。后端完成状态仍为局部实现；Q01–Q04 未验收；角色完整 Laya action+target→L4→领域 owner receipt/recovery 未完成；Godot G-A/B/C 未操作，仍最后集中验收。

### Driver batch 4 diagnostic (2026-10-21)

- 首次尝试在 provider pending 时释放 actor activation，违反现有 driver 的 slot/lease/retry/cancellation 预期，driver suite 为 7 failed/2 passed；撤下该未提交 driver patch 后，同一 suite 仍为 7 failed/2 passed，现有 provider preparation/delivery 根因待独立定位。该结果不作为 fast/slow coexistence 证据，也不改变已通过的 owner 接纳实现状态。
- 根因定位与修复（2026-10-21）：普通 `ingest_siming_output` 的 L2/L3 请求在 gateway 校验前把 `CharacterMindFrame` 提前转成 JSON dict，导致 `gateway requires a frozen mind frame`，provider 未启动。保留 MindFrame 实例到 gateway，交由冻结序列化处理；driver 回归 `python -m pytest -q backend/tests/test_character_cognition_driver.py` 为 **9 passed**，与慢目标 coordinator/store/transition 合并为 **41 passed**。这只恢复 driver 基线，不代表生产 trigger、快慢并行、完整 Laya、正式模型质量或 Godot 已验收。
- 复验 owner 接纳相关范围：`python -m pytest -q backend/tests/test_character_slow_goal_coordinator.py backend/tests/test_character_slow_goal_atomic_acceptance.py backend/tests/test_character_slow_goal_transition.py`，32 passed。无本批运行产物需保留；没有运行全量 pytest、Harness all、真实模型、正式质量拆分、训练或 Godot。
- 矩阵状态：后端 coordinator/store owner acceptance 子项已完成，普通 cognition driver 基线已恢复并通过 9 项回归；生产 trigger、快慢并行与真实 provider dispatch 仍未验收。Q01–Q04 未验收；角色完整慢目标→Laya action+target→L4→domain receipt/recovery 未验证；最终 Godot G-A/B/C 未操作，仍排最后。
