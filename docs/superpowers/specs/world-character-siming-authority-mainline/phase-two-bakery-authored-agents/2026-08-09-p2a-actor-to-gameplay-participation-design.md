# P2A Actor-to-Gameplay Participation

Status: `implemented-and-verified`

## Purpose

把已注册的 `CharacterProfile`/`CharacterAgent` 接入 Gameplay participation boundary。P2A
只定义 profile-backed actor ref、内容包授权、actor-scoped projection 和 typed work intent
envelope；CharacterAgent adapter 永远不是 canonical writer。

## Dependencies

P1A shared contracts；P1B contract/replay/permission evidence；P1D fresh-green；现有
CharacterProfile registry、L1-L4、`CharacterAgentL4Adapter`、`GameplayCommandEnvelope`、
`SettlementPlan`、`GameplayEventStore` 与 Godot mirror scope registry。

## Matrix

| 类别 | 内容 |
|---|---|
| 已实现 | profile registry、L1-L4、L4 presentation/action adapter、command envelope、append batch、idempotency、replay/checkpoint/outbox、scope-filtered mirror |
| 可复用 | registry lookup、现有 private/public views、authority validation、纯 SettlementPlan、committed mirror delivery |
| 正式新增候选 | `ProfileBackedActorRef`、package actor allowlist、actor-scoped gameplay projection、typed work-intent adapter result、accept/decline/start/finish/absence/break intent contract |
| 明确后置 | 自动唤醒、自动招聘、NPC state、角色账户/家庭生活、Population batch planner、全局时钟 |

候选记录不是 Python schema；实现时必须优先扩展既有 contract/registry/view，而不是平行
record 或 store。

## Canonical owner matrix

| Owner | Owns | Reads | Must not write |
|---|---|---|---|
| Character Profile/Core | profile identity, authored identity, mind/private state | package grant, actor projection, capability bands | organization, production, inventory, economy |
| CharacterAgent L1-L4 | local interpretation, decision, memory writeback | actor-scoped projection | any Gameplay store or authority fact |
| Gameplay package contract | immutable `GameplayPackageManifest` package identity, revision, commands/events/projections/privacy/mirror bindings and digest | profile registry and core compatibility | actor assignment, payroll, private character state |
| P2A adapter | envelope construction and structured rejection | registry, manifest compatibility, package actor grant projection | `append_batch`, CharacterProfile, canonical state |
| Gameplay authorities | organization/production/inventory/economy/survival facts | validated envelope and pinned projections | foreign owner facts |
| Mirror/Projection | committed filtered read views | committed events/outbox | canonical truth |

## Data and reference contract (candidate)

```text
ProfileBackedActorRef:
  actor_ref = character:<profile_id>
  profile_registry_revision
  authored_identity_digest
  package_ref
  package_grant_revision
  permitted_role_refs

ActorWorkIntent:
  intent_kind = respond_shift|start_work|finish_work|report_absence|request_break
  actor_ref, assignment_ref?, shift_ref?, work_order_ref?, operating_window_ref?
  actor_declared_payload (refs only), source_ref, causation_id, correlation_id
```

package authorization 的 canonical input 是现有 `GameplayPackageManifest`
（`backend/app/gameplay/shared_contracts.py`）及其既有 manifest validation/digest 路径；
P2A 只消费已验证 manifest，不创建第二个 package registry。

这些名称是正式设计候选；现有 `GameplayCommandEnvelope` 字段仍是 canonical envelope，
不新增第二种命令入口。`char_a`/`char_b`/`char_c` 可以作为 harness actor ref，但不得
覆盖 authored identity、occupation、memory 或状态。

## Command/event/revision/idempotency

Adapter 先解析 registry 与 package grant，再构造 `GameplayCommandEnvelope`，其中
`command_type` 必须版本化，`actor_ref` 必须为已存在 profile，`expected_revisions` 必须
包含 assignment/offer/work ref 所需 revision，`pinned_revisions` 必须固定 package、policy、
recipe/survival/wage 输入。`idempotency_key` 对同一 intent retry 稳定；payload digest 改变
时拒绝复用。causation/correlation 必须贯穿事件和 receipt。

`finish_work` 的 payload 只能携带待验证 evidence refs；adapter、模型输出和 Harness actor
都不能自证 completed。完成事实必须由 P2B/Production owner 以授权 issuer、evidence kind、
source digest 和 verification state 验证后产生。

Adapter 的结果只有 envelope 或 structured rejection。owning authority 读取 envelope，
构造纯 `SettlementPlan`，以现有 `GameplayEventStore.append_batch()` 进行单/多 stream
提交。跨 stream 的组合只能由既有 shared settlement boundary 生成一个 batch；adapter 不
拥有组合或提交权。事件名、stream 名和 schema version 必须在实际 event schema registry 注册
后才能实现；本文的 intent 名不是现有 API 声明。

## Permissions and projections

Actor scope 只含自身 profile ref、授权 assignment、自己的 shift/work/evidence/wage 状态和
必要的公开 bakery facts。manager scope 可见组织工作状态、evidence refs、预算占用和经授权
组织投影，但不见其他角色 need、memory、emotion 或工资细目。Godot 只消费 committed、
scope-filtered snapshot/delta；未授权 scope、mirror delivery failure 和私有字段泄露均拒绝。
scope grant/subscription 是 session-scoped authorization，不是 replay state；replay 证据必须
先重建 canonical projection，再用同一 manifest/privacy policy 重新 grant scope，最后比较
filtered digest 和 delivery receipt。

## Failure, recovery and replay

未知/合成 profile、package 未授权、跨项目 ref、越权 scope 和 malformed payload 在 envelope
生成或 authority validation 阶段拒绝，`zero_write_guarantee=true`。stale revision、duplicate、
payload mismatch、projection rebuild failure 同样零写入。恢复只能通过新 command/new
correlation 产生新事实；不得编辑旧事件或从 projection 修复 event history。full replay 与
checkpoint-tail replay 必须重建相同 actor/manager/Godot filtered digest。

## Acceptance and Harness evidence

- registry 中三个合法 actor 可被解析；未知、合成和未授权 actor 无事件；
- 五种 intent 都产生同一 envelope contract 的可审计样本，adapter 无 store 依赖；
- accept/decline/start/finish/absence 的 success、stale、duplicate、scope denial 均有
  structured result 和 zero-write trace；
- actor projection、manager projection、Godot mirror 有字段级 redaction/digest 证据；
- full/checkpoint-tail replay hash 一致，causation/correlation/pinned revisions 完整；
- `phase2a-actor-to-gameplay-participation` Harness fresh-green；证据见
  `.harness/verification/phase2a-actor-to-gameplay-participation-report.{json,md}`。

## Population Simulation handoff gate

只有 Population authority 能把批量计划映射为同一 `GameplayCommandEnvelope`，复用同一
profile/record、idempotency、revision、append batch 和 scope filter，并通过 materialization、
continuity、budget、pause/resume、catch-up Harness 后，才可接入人口模拟。P2A 不授予该权限。
