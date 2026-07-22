# Event Sourcing And Authority Settlement Design

Status: `awaiting-user-review`

Date: `2026-07-23`

## Purpose

定义 Character Gameplay Foundation 的权威写入协议：所有 gameplay 真相以不可变领域事件表达，所有跨域变化由一次 authority settlement 形成原子事件批次，所有当前状态、façade、Godot mirror 和图谱输入均为可重建投影。

本规格深化既有 authority/settlement 主线，不建立平行 authority service。

## Scope

- command envelope、幂等与 optimistic concurrency；
- domain stream、event envelope 和 event schema registry；
- typed effect proposal 与 authority settlement pipeline；
- 单次事务中跨多个 aggregate stream 的原子事件批次；
- settlement success/failure contract；
- event append 后的 projection/outbox 触发；
- 审计、causation、correlation 与解释链；
- 跨资源、背包、产权、装备和经济的典型事务语义。

## Non-goals

- 不指定 PostgreSQL、SQLite 或其他具体数据库产品；
- 不采用 saga 或最终一致性作为首批单后端结算模型；
- 不允许从 projection 或 checkpoint 直接修正事件历史；
- 不定义 Rule IR 语法或 capability handler 内部实现；
- 不定义领域 event payload 的全部字段；
- 不把完整事件流无过滤地发送给 Godot。

## Dependencies

- `2026-07-23-foundation-invariants-and-domain-boundaries-design.md`
- `2026-07-23-state-group-registry-and-runtime-facade-design.md`
- `2026-07-23-persistence-replay-migration-and-hot-reload-design.md`
- `../2026-06-29-authority-and-settlement-runtime-closure-design.md`
- inventory/economy/equipment/patch 子规格（同一 spec tree）

## Command Model

```text
CommandEnvelope
  command_id: globally unique id
  command_type: namespaced stable id
  command_version: positive integer
  idempotency_key: caller-scoped stable key
  principal_ref
  actor_ref?
  target_refs[]
  expected_revisions: map<AggregateRef, integer>
  causation_id
  correlation_id
  source_ref
  submitted_at
  payload
```

### Command rules

- `command_id` 标识一次命令实例；`idempotency_key` 标识调用者希望“至多结算一次”的业务意图。
- 相同 principal + idempotency key + canonical payload hash 必须返回原 settlement result。
- 相同 key 但 payload hash 不同返回 `idempotency_key_reused`，不能猜测调用者意图。
- 每个将被写入的 aggregate 必须有 `expected_revisions`；缺失时是否允许 `create-only` 由 command schema 明确声明。
- 时间、随机、外部服务结果必须先作为显式 input/evidence 固化，settlement 不能读取不受控的隐式全局状态。

## Domain Stream Model

一个 stream 对应一个有明确 owner 的 aggregate：

```text
StreamId
  aggregate_type
  aggregate_id

StreamState
  stream_id
  current_revision
  event_count
  archived: boolean
```

角色可以拥有多个 stream，例如 resource、body、inventory、equipment；账户、容器、物权和 world asset 也有独立 stream。`CharacterGameRuntimeState` 不拥有一条“全角色万能 stream”。

## Event Envelope

```text
DomainEventEnvelope
  event_id
  event_type
  event_version
  aggregate_ref
  aggregate_revision
  transaction_id
  transaction_sequence
  causation_id
  correlation_id
  command_id
  occurred_at
  recorded_at
  source_ref
  authority_scope
  privacy_scope
  payload
  metadata
```

必需约束：

- `event_id` 全局唯一；
- `aggregate_revision` 在单 stream 内严格连续；
- `transaction_sequence` 在 batch 内从 0 连续递增，用于确定性 replay；
- `event_type + event_version` 唯一确定 payload schema；
- `occurred_at` 是领域发生时间，`recorded_at` 是权威存储接收时间；两者不可替换；
- metadata 不得隐藏本应进入 typed payload 的业务字段。

## Effect Proposal

Rule IR、领域服务或受信任 capability handler 只能产生：

```text
EffectProposal
  proposal_id
  effect_type
  effect_version
  target_aggregate_ref
  required_state_groups[]
  preconditions[]
  proposed_events[]
  cost_reservations[]
  evidence_refs[]
  source_rule_ref
  source_patch_revision
```

proposal 不是结果，也不能被投影消费。只有 settlement 将其验证并提交为 event batch 后才产生权威变化。

## Authority Settlement Pipeline

```text
1. Decode and schema-validate command
2. Resolve idempotency record
3. Authenticate principal and authorize scope
4. Pin registry/world/patch/policy revisions
5. Load all required streams at expected revisions
6. Evaluate state-group availability and domain preconditions
7. Produce typed effect proposals
8. Resolve costs, modifiers, grants and conflicts
9. Validate complete candidate event batch
10. Atomically compare revisions + append all events + store result/outbox record
11. Publish committed event batch to projections
12. Return structured settlement result
```

步骤 4 固定整个事务使用的规则版本。事务运行期间发生 patch upgrade 时，当前事务继续使用 pinned revision，新事务才使用新 revision。

## Atomic Event Batch

```text
AtomicEventBatch
  transaction_id
  command_id
  pinned_revisions
  expected_stream_revisions
  events[]
  result_digest
  idempotency_record
  outbox_entries[]
```

event store 必须提供逻辑等价接口：

```text
append_batch(
  events,
  expected_stream_revisions,
  idempotency_record,
  outbox_entries
) -> AppendBatchResult
```

该调用只有两种可观察结果：

- `committed=true`：所有 events、idempotency result 和 required outbox entries 均持久化；
- `committed=false`：上述内容均未持久化。

不得返回“部分 stream 已提交”。若底层存储不能保证此原子性，则不符合首批 authority store 要求。

### Example: buying and equipping a sword

一次购买可同时产生：

```text
CurrencyDebited
ItemInstanceCreated
ItemPlacedInContainer
OwnershipRightGranted
EconomicTransactionRecorded
```

随后独立的装备 command 可原子产生：

```text
ItemRemovedFromContainer
EquipmentSlotOccupied
EquipmentGrantActivated
EncumbranceInputsChanged
PresentationBindingRequested
```

余额不足、库存 revision 冲突、容器容量不足或槽位不可用时，对应批次必须零提交。不能先扣款再异步发物，也不能先装备再补 grant。

## Settlement Result

成功：

```text
SettlementSuccess
  outcome: committed
  command_id
  transaction_id
  committed_event_ids[]
  resulting_revisions
  projection_refresh_hints[]
  confirmed_prediction_id?
  explanation
```

失败：

```text
SettlementFailure
  outcome: rejected | not_committed
  error_code
  message
  retriable
  command_id
  transaction_id?
  failed_stage
  failed_precondition?
  expected_revision?
  actual_revision?
  source_refs[]
  recovery_action
  rejected_prediction_id?
```

失败 result 也必须保存为可审计的 idempotency outcome，但不能伪装成 domain event。安全审计记录与 gameplay event stream 分开治理。

## Projection Dispatch

- event batch commit 是权威完成点，不等待所有 projection 同步完成才算提交；
- required outbox entry 与 event batch 同事务保存，确保 committed batch 最终可被投影消费；
- projector 按 transaction sequence 与 aggregate revision 幂等消费；
- projector 已应用 event ID 必须可检测，重复投递不得重复效果；
- façade 只发布已达到一致 transaction boundary 的 group projections，不能展示半个交易；
- projection lag 必须可观测，并允许 consumer 请求 `min_source_revision_vector`。

首批单后端仍允许 projection 同进程执行，但接口不能依赖“函数调用永不失败”的假设。

## Concurrency And Idempotency

- optimistic concurrency 以每个 aggregate expected revision 比较；
- 任一 stream revision 不匹配，整批返回 `revision_conflict`；
- server 不自动以最新数据重放有副作用 command，调用方刷新后用新 command/idempotency key 显式提交；
- 重复网络请求返回原 transaction ID、event IDs 和 result digest；
- command handler 不得用 wall-clock、无 seed random 或 map iteration order 产生不确定 batch；
- 所有随机结果应由 `RandomDecisionRecorded` 或命令 evidence 固化。

## Authority Invariants

1. event stream 是唯一权威 gameplay truth；projection 与 checkpoint 不可直接写回。
2. 已提交 event envelope 和 payload 不可修改、删除或重新排序。
3. 一个 command 至多提交一个 transaction batch。
4. 一个 transaction batch 要么全部提交，要么零提交。
5. 所有跨域 event 共享 transaction、causation 和 correlation chain。
6. settlement 前置条件只读取 pinned revisions；不可混用事务中途的新 patch/config revision。
7. effect proposal 不具有权威性，未提交 proposal 不得外发为成功状态。
8. correction 通过新 command/event 表达，不改写旧事件。
9. event payload 只记录领域事实；consumer-specific UI 文案属于 projection。
10. event 的 privacy scope 约束所有 downstream projection，不能因进入 outbox 而丢失。

## Failure Semantics

| Error code | Failed stage | Commit | Recovery |
| --- | --- | --- | --- |
| `command_schema_invalid` | decode | none | 修正请求 |
| `idempotency_key_reused` | idempotency | none | 使用新 key 或原 payload |
| `authority_denied` | authorization | none | 获取权限；响应须脱敏 |
| `revision_conflict` | load/append | none | 刷新相关 stream 后重提 |
| `precondition_failed` | domain validation | none | 按 blocked reason 修正状态 |
| `effect_proposal_invalid` | proposal validation | none | 修正规则/handler |
| `atomic_append_failed` | persistence | none/unknown until verified | 查询 transaction ID，禁止盲重试新 key |
| `event_schema_unregistered` | batch validation | none | 注册 schema/迁移后重试 |
| `projection_apply_failed` | post-commit projection | events remain committed | 隔离并 replay projector |
| `outbox_dispatch_failed` | post-commit dispatch | events remain committed | 幂等重投 outbox |

若 append 客户端因网络中断无法判断提交结果，返回/记录 `commit_status_unknown`，调用方必须用原 idempotency key 查询，不得新建 key 重试。

## Acceptance Criteria

1. 单 stream 与多 stream command 均检查 expected revisions。
2. 买剑事务在任何校验点失败时，余额、物品、产权和交易 stream 均无新事件。
3. 成功跨域事务的所有 event 共享 transaction ID 且 transaction sequence 连续。
4. 同一 idempotency key 重放返回相同 result，不增加 event count。
5. key 相同而 payload 不同被稳定拒绝。
6. 两个并发 command 竞争同一 revision 时至多一个提交。
7. projector 重复消费同一 batch 不改变最终 projection。
8. outbox 失败后重投可恢复 projection，且不产生新 domain event。
9. correction 与 rollback 通过新事件表达，历史 checksum 保持不变。
10. Rule IR/handler 无法访问 append API，只能返回 typed proposal。
11. fault injection 覆盖 batch 第一个、中间和最后一个 event 的持久化失败，并证明零部分提交。
12. settlement explanation 能指出规则、modifier、权限和 precondition 来源。

## Harness Mapping

### Current review gate

- `python scripts/verification/harness.py --profile docs`

### Required implementation profiles

- `gameplay-foundation-contract`
  - command/event/result schema；
  - unknown-field 与 version rejection。
- `gameplay-event-replay`
  - event ordering、幂等 projector、完整 replay；
  - correction 不改写历史。
- `gameplay-economy-authority`
  - 多 stream 原子买卖、赠与、产权转移；
  - 余额不足与 revision conflict 零提交。
- `gameplay-patch-runtime`
  - proposal-only handler 边界；
  - pinned patch revision。
- `adventure-basic`
  - 购买并装备长剑纵向闭环。
- `gameplay-foundation-all`

实现证据必须包含 fault-injection、并发和重复请求测试；只跑 happy path 不满足本规格。
