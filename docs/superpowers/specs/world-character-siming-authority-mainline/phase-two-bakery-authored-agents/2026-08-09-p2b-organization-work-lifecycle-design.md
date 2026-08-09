# P2B Organization Work Lifecycle

Status: `implemented-and-verified`

## Purpose

扩展既有 `RoleAssignment`，为已存在角色提供组织工作生命周期：shift offer、work order、
attendance/completion evidence、facility slot、inventory reservation 和 worker contribution
references。P2B 不创建 `EmployeeState`、`NpcState` 或 Organization mega-coordinator。

## Dependencies

P2A actor envelope and grant boundary；P1D Organization/Government、Construction/Production、
Inventory、Skill、Survival、Economy contracts；`GameplayEventStore.append_batch()` 的
multi-stream expected revisions、idempotency 和 outbox。

## Matrix

| 类别 | 内容 |
|---|---|
| 已实现 | `Organization`、`RoleAssignment(organization_ref, character_ref, role)`、`OperatingPlan`、facility/recipe/run、inventory reservation、skill/survival projections、multi-stream atomic batch |
| 可复用 | `RoleAssignment` 作为 profile-backed assignment anchor；ProductionRun/reservation/facility owners；P1D failure/replay/mirror contract |
| 正式新增候选 | assignment lifecycle extension、ShiftOffer、WorkOrder、AttendanceEvidence、WorkerContributionRef、facility slot/reservation reference linkage、work lifecycle projection |
| 明确后置 | employee shadow state、offline life、recruitment market、global scheduler/clock、NPC ecosystem |

## Canonical owner matrix

| Owner | Owns | Reads | Must not write |
|---|---|---|---|
| Organization | assignment extension, offers, work orders, attendance, completion evidence refs, window close summary | profile existence, capability summaries, facility/inventory/economy projections | profile identity, facility truth, inventory quantity, production yield, accounts |
| Skill/Survival | qualification and labor-availability result | work refs and actor state | attendance, wages, inventory |
| Production | facility slot, run, worker contribution refs, output evidence | accepted work order, skill/evidence, reservation, permit | wage/account/need |
| Inventory | reservation, consume/receive, custody | production proposal and refs | attendance/run completion/account |
| Economy | wage inputs only in P2C | completed work evidence | shift/attendance/facility truth |
| EventStore/Projection | append-only transaction, stream revision, replay/checkpoint/outbox | settlement plan | domain facts outside batch |

`backend/app/gameplay/settlement_plan.py` 是现有 shared settlement boundary：P2 只允许扩展
现有纯 `SettlementPlan`，使它能携带多个 owner-scoped event proposals 与完整 expected
revision vector；它不拥有任何 domain state、不做 authority decision、也不调用 store。
`GameplayEventStore.append_batch()` 仍是唯一 writer。这个扩展不是新的 coordinator、store、
bus 或 settlement path。

## Candidate data/reference contract

```text
RoleAssignmentExtension:
  assignment_ref, organization_ref, character_ref, permitted_role_ref,
  authorization_revision, status=active|suspended|revoked
ShiftOffer:
  shift_ref, assignment_ref, work_kind, facility_scope, resource_scope,
  operating_window_ref, offered|accepted|declined|expired, expected_revision
WorkOrder:
  work_order_ref, shift_ref, target_refs, required_capabilities,
  evidence_kind, issued|accepted|started|completed|failed|absent|cancelled
AttendanceEvidence:
  evidence_ref, actor_ref, assignment_ref, work_order_ref,
  source_ref, issuer_principal_ref, evidence_kind, observed_at, outcome,
  verification_state, source_digest, pinned_revisions
WorkerContributionRef:
  actor_ref, assignment_ref, work_order_ref, evidence_refs, contribution_digest
```

以上是逻辑候选，不是当前 API。`issuer_principal_ref` 必须是已授权 Gameplay/domain
principal；CharacterAgent 的自然语言、`role_state_hint` 或 actor-declared payload 只能成为
待验证输入，不能直接成为 completed evidence。生产事实应通过 stable reference 扩展现有 `ProductionRun`，
而不是复制 worker、材料或质量 canonical state。

## Lifecycle, command and atomicity

所有来源使用 P2A 生成的版本化 `GameplayCommandEnvelope`。Organization commands 只推进
assignment/offer/work order/attendance；start/finish 需由 Production/Inventory/Skill/Survival
分别提出 typed result，再由 shared settlement boundary 组合纯 `SettlementPlan`。涉及
organization、production、inventory、facility 等 stream 时，batch 必须给出所有
`expected_stream_revisions`，
由 `append_batch()` 一次性提交；任一 validation、reservation、slot、permit 或 revision
失败则所有 stream 零写入。

逻辑事件包括 `shift_offered/accepted/declined/expired`、`work_issued/started/completed/failed/absent`、
`attendance_recorded` 和 contribution reference attach；实际 event type/version 必须先注册。
每个事件携带 command/transaction/causation/correlation、source/evidence refs、visibility 和
pinned revisions。重复 idempotency 返回原 receipt，payload digest 不同则拒绝。

## Permissions and projections

Assignment actor 只能读取自己的 offers/orders/evidence 和必要公开 facility facts；manager 可读
组织工作状态、贡献 refs、预算占用和授权库存/设施摘要；production/inventory 只读解决自身
结算所需 refs。任何 projection 不得泄露角色私有 need/memory、他人薪酬明细或未授权组织秘密。
Godot mirror 只发送 committed scope-filtered snapshot/delta，经现有 mirror subscription grant。

## Failure, recovery and replay

未注册 actor、未授权 assignment、offer stale/expired、insufficient skill/labor、slot/reservation
conflict、invalid evidence、duplicate 和 cross-organization ref 均返回结构化 failure，带 owner、
revisions、retriable、`zero_write_guarantee=true`。失败不删除历史；恢复使用新 offer/window/command，
必要时由 reservation owner release/compensate。full replay 与 checkpoint-tail replay 必须还原
相同 organization/production/inventory/work projection digest。

## Acceptance and Harness evidence

- 现有 `RoleAssignment` 可指向至少两个 registry profile，撤销保留历史；
- 两个角色在一个窗口有独立 accepted work 和 attendance/completion evidence；
- completed evidence 必须能回查 issuer principal、evidence kind、source digest 和 verified
  state；未经 owner 验证的 actor 声明不得触发完成或工资；
- 同一 facility slot/material reservation 争用只有一个 batch commit，失败者零写入；
- start/finish 成功与 absence/skill/slot/stale/duplicate 失败可 replay；
- manager/actor/Godot scope redaction 通过，outbox 仅在 commit 后 delivery；
- `phase2b-organization-work-lifecycle` Harness fresh-green；证据见
  `.harness/verification/phase2b-organization-work-lifecycle-report.{json,md}`，覆盖
  multi-stream revision conflict 与零部分写入。

## Population Simulation handoff gate

Population 只能在不创建第二角色、assignment 或 settlement path 的前提下批量提出 P2B intent，
并先通过 continuity/materialization、batch revision、pause/resume、catch-up 和 scope Harness。
没有这些证据，P2B 不得扩展为 NPC 生态。
