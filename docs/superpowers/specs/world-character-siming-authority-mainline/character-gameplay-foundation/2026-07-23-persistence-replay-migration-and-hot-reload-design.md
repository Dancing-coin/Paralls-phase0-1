# Persistence, Replay, Migration And Hot Reload Design

Status: `partially-implemented; broader-closure-planned`

Date: `2026-07-23`

## 2026-08-02 Implementation Status

`GameplayEventStore` now supports a versioned JSON snapshot export/import and
atomic file replacement. Recovery validates event/global ordering, per-stream
revisions, transaction coverage, idempotency outcomes, outbox references, and,
when enabled, the immutable event-schema registry identities required by the
stored history. `DurableGameplayEventStore` can additionally persist every
successful batch and outbox state update, rolling memory back on
snapshot-write failure.

The first migration seam is also implemented: an opt-in `EventSchemaRegistry`
gates writes and is included in the durable snapshot; an in-process trusted
`EventUpcasterRegistry` admits only digest-matched, continuous `vN -> vN+1`
steps. `GameplayProjectionReplay` can use that registry to replay the fixed
`gameplay.session_reserved` v1 fixture as the v2 reader view without mutating
the historical event. Unknown schemas and missing chains fail closed.

The implemented minimum recovery slice also retains projection checkpoints in
the JSON snapshot and, per projector, selects the newest compatible checkpoint
by projector/schema identity plus patch, registry, and world-config revisions.
It validates the checksum, committed-event prefix, and source revision vector;
an invalid or incompatible cache falls back to full replay. The opt-in
`GameplayProjectionStartup` closes its one store's write gate while it rebuilds
that required projection, and reopens it only after successful replay; writes
during a failed bootstrap receive retriable `projection_not_ready`. The first
bounded Patch/state-group data migration is now replay-covered: the typed
resource maximum-reduction fact and exact state-group definition transition
rebuild to the same Phase 3 façade through full and checkpoint-plus-tail
replay. This is not a persistent executable-upcaster manifest, a complete
event-family registration rollout, general patch/state-group migration, global
multi-projector readiness orchestration, or a production startup control plane.

## 2026-08-27 Cross-INF Snapshot Integrity Closure

`GameplayEventStore.from_snapshot()` now treats a durable snapshot as one
atomic ledger image. Recovery compares embedded transaction events with the
canonical event ledger, requires exactly one committed append result per
transaction with matching command, event IDs, stream revisions, global sequence
range and projection hints, and requires each idempotency index entry to match
both its transaction batch and canonical result. Outbox entries must reference
the same committed event transaction and global sequence, with unique IDs.
Duplicate, missing, or conflicting cross-index records fail closed before a
store is returned. This reusable invariant protects replay, duplicate handling
and append-derived receipts for every INF row without adding an owner, store,
writer, or business event; internally consistent v1/v2 snapshots remain
readable. Recovery also requires transaction batches to remain in ascending
global sequence order and each batch's embedded events to be contiguous in the
canonical ledger. This prevents preserving the same event IDs while changing
replay order or checkpoint-tail boundaries.

## Purpose

定义完整事件溯源在持久化、启动恢复、projection rebuild、event schema 演进、checkpoint 加速和 gameplay patch 热加载中的实现约束。目标是保证历史事件永远可解释、当前投影可重建、升级失败可阻断，而不是把“最新 snapshot 能读出来”误认为权威持久化已经成立。

## Scope

- event store、batch、stream、schema registry 和 outbox 的持久化契约；
- checkpoint 的创建、校验、失效和回退；
- 全量与增量 replay、projection rebuild 和一致性校验；
- event version、upcaster、projection version 与 migration manifest；
- state-group/patch install、enable、disable、upgrade、rollback 和 hot reload；
- 活跃事务 pin 旧 revision、新事务切换新 revision 的并发语义；
- 失败门禁、隔离、恢复与 durable verification evidence。

## Non-goals

- 不选定具体数据库、消息队列或部署拓扑；
- 不允许修改、删除或原地重写历史事件；
- 不把 checkpoint、cache 或导出的 façade 当作备份真相；
- 不承诺任意第三方代码热加载；
- 不定义在线零停机分布式 saga；
- 不定义 content authoring editor UI；
- 不允许 hot reload 绕过 schema、dependency、authority 或 verification gate。

## Dependencies

- `2026-07-23-foundation-invariants-and-domain-boundaries-design.md`
- `2026-07-23-state-group-registry-and-runtime-facade-design.md`
- `2026-07-23-event-sourcing-and-authority-settlement-design.md`
- gameplay patch Rule IR/capability 子规格（同一 spec tree）
- `docs/harness.md`

## Durable Store Contract

逻辑存储至少包含：

```text
event_batches
domain_events
stream_heads
idempotency_results
event_schema_registry
projection_checkpoints
outbox
patch_registry_revisions
world_config_revisions
rebuild_jobs
```

这不是物理表结构要求，但实现必须提供等价的事务和查询能力。

### Required event-store interfaces

```text
append_batch(events, expected_revisions, idempotency_result, outbox) -> result
read_stream(stream_id, from_revision=0, to_revision?) -> ordered events
read_transactions(global_position?, limit?) -> ordered batches
get_stream_head(stream_id) -> revision
get_transaction(transaction_id) -> batch/result
get_by_idempotency(principal_ref, key) -> stored result?
register_event_schema(event_type, version, schema_digest)
```

读取必须稳定保留 batch transaction order 与 stream aggregate order。实现可以具有 global position，但不得用物理插入顺序代替明确的 replay order contract。

## Checkpoint Model

```text
ProjectionCheckpoint
  checkpoint_id
  projector_id
  projector_version
  projection_schema_version
  source_revision_vector
  last_global_position?
  active_patch_set_revision
  registry_revision
  payload_location
  payload_checksum
  created_at
  validation_digest
```

checkpoint 只用于加速，不是独立真相源：

- 删除所有 checkpoint 后必须能从事件流恢复同一最终投影；
- checkpoint checksum、projector version、schema、patch set 或 source revision 不匹配时必须丢弃并 replay；
- checkpoint 不得包含其 privacy scope 不允许持久化的数据副本；
- checkpoint 生成失败不影响已经提交的事件；
- checkpoint 不能跨过未知或无法 upcast 的事件。

## Bootstrap And Replay

启动顺序：

```text
1. Load and validate event schema registry
2. Load active registry/world/patch revisions
3. Verify required upcaster chains
4. Select newest compatible checkpoint per projector
5. Verify checkpoint checksum and revision vector
6. Replay later committed batches in canonical order
7. Validate projection invariants and checksums
8. Publish readiness for read traffic
9. Enable write traffic only after required authority projections are ready
```

无法解释历史事件时必须 fail closed。不得跳过未知事件后继续接受写入，否则当前状态与历史真相会永久分叉。

### Replay modes

- `full`：从 genesis event 重建；用于最终验证、迁移门禁和灾难恢复。
- `checkpointed`：从兼容 checkpoint 继续；用于正常启动。
- `targeted`：重建指定 projector/aggregate，不改变 event history。
- `shadow`：新 projector version 并行重放，与当前 projection 比较，不对消费者切流。

所有 mode 对同一 target revision 必须产生相同 canonical projection digest；时间戳等非领域 metadata 应从 digest 中排除或规范化。

## Determinism Contract

projector/upcaster 必须：

- 对同一 ordered events 和 pinned definitions 输出相同结果；
- 不读取当前 wall clock、网络、环境变量或未固化随机源；
- 不依赖 hash/map 未定义遍历顺序；
- 使用 schema 固定的 decimal scale、timezone 与 sorting rules；
- 对重复 event ID 幂等；
- 对 stream revision 缺口、重复或倒序立即失败；
- 记录 projector code/version digest 与 input revision vector。

## Event Versioning

每个 event type 独立版本：

```text
EventSchemaRegistration
  event_type
  event_version
  schema_id
  schema_digest
  introduced_by_patch_revision
  privacy_classification
```

规则：

- 已发布 `event_type + event_version` schema 不可变；
- additive optional field 也需要遵守 schema compatibility policy，不能静默改变 digest；
- semantic change 必须提升 event version；
- 新代码必须能够读取所有仍在 retention 范围内的历史版本；
- writer 只能发 active registry 明确允许的版本。

## Upcaster Model

```text
EventUpcaster
  event_type
  from_version
  to_version
  input_schema_digest
  output_schema_digest
  upcaster_version
  transform(payload, metadata) -> payload
```

upcaster 约束：

- 单步、纯函数、确定性；
- 不查询当前数据库状态或外部服务；
- 不改变 event ID、aggregate revision、transaction/causation/correlation identity；
- 缺少必要历史信息时不得编造；应保留 legacy representation 或要求显式 migration event；
- 每条历史版本到当前 reader version 必须存在唯一连续链；
- 链有缺口、分叉或 schema digest 不匹配时，启动/升级门禁失败。

upcast 是读取解释，不产生新的权威事件。需要改变领域事实时使用 migration command 追加新事件。

## Projection Migration

projection 可以丢弃并 rebuild，因此优先发布新 projector，而不是原地迁移投影数据。

```text
ProjectionMigrationPlan
  projector_id
  from_version
  to_version
  required_event_reader_versions
  checkpoint_compatibility
  shadow_replay_required
  comparison_policy
  cutover_policy
```

cutover 前必须：

1. shadow full replay 完成；
2. invariants 通过；
3. 预期相等字段 digest 一致；
4. 有意变化字段符合 migration fixture；
5. lag 收敛到同一 transaction boundary；
6. 原子切换 consumer projection alias。

旧 projector/checkpoint 保留到 rollback window 结束，但它们仍不是权威真相。

## Gameplay Patch Lifecycle

### Install

`install` 只把 package 放入 candidate registry，必须校验：

- manifest/schema/signature or trusted-source policy；
- dependencies/conflicts；
- state group、command、event、projection 与 Rule IR schema；
- capability allowlist；
- upcaster chain 与 projection migration plan；
- verification profile metadata。

### Enable

enable 创建新的 immutable `active_patch_set_revision`。受影响状态组通过 authority settlement 产生 enable/materialization events；不能通过进程内 mutable flag 作为唯一记录。

### Disable

disable 只影响后续新 command：

- 停止产生该 patch 的新业务 event；
- 按 state-group disable policy 进入 dormant/archive/reject；
- 持续 grant/modifier 需要先原子追加 revoke/compensation events；
- 历史 event schema、upcaster 和 replay definitions 继续可用；
- 不删除 event、item、产权或角色成长历史。

### Upgrade

```text
prepare candidate revision
  -> validate schemas/dependencies/upcasters
  -> shadow replay and migration tests
  -> quiescence/cutover check
  -> atomically activate new patch-set revision
  -> new transactions pin new revision
  -> old active transactions complete on old revision
```

每个 settlement 在开始时固定 patch set、registry、world config 和 policy revision。upgrade 不得中途改变活跃事务的解释器或 modifier rules。

### Rollback

rollback 是激活一个新的 patch-set revision，重新指向兼容的旧规则版本，并按需要追加 compensation/reconfiguration events。它不删除 upgrade 后已经产生的历史事件。

如果旧 reader 无法解释 upgrade 后事件，则旧版本不具备 rollback compatibility；必须发布 forward fix 或兼容 reader，不能强制降级并跳过事件。

## Hot Reload Contract

首批 hot reload 仅支持内部/受信任、已版本化内容：

- 新定义先进入 candidate namespace；
- immutable definition 不允许原位修改；
- schema、dependency、capability、migration 与 harness gate 全部通过后才可激活；
- active patch revision 的 handler code reference 固定，不能替换同一 revision 下的代码；
- 本地 Godot presentation binding 可热刷新，但不得确认 backend 未激活的规则；
- reload 失败保留当前 active revision 并输出结构化诊断。

## Rebuild And Integrity Operations

```text
RequestProjectionRebuild
ProjectionRebuildStarted
ProjectionRebuildCheckpointed
ProjectionRebuildCompleted
ProjectionRebuildFailed
```

这些 operation records 属于运维/审计面，不是 gameplay domain facts。

每次 rebuild 证据至少包含：

```text
job_id
projector_id/version
event range
source revision vector
active definition revisions
input event count
output entity count
projection digest
duration
result
failure location?
```

rebuild 写入 shadow projection，验证通过后再切换；不得先清空在线 projection 后裸跑。

## Authority Invariants

1. event store 是唯一持久权威；checkpoint、projection、façade、Godot mirror 都可丢弃重建。
2. 历史 event bytes/schema identity 不可原地修改。
3. event writer、reader 与 upcaster version 均受 registry revision 约束。
4. 未知 event 或 upcaster gap 阻止 ready/write，不允许跳过。
5. 相同事件、定义与 projector 版本产生相同 projection digest。
6. patch disable/upgrade/rollback 不删除历史事件。
7. 活跃事务始终使用开始时 pinned revisions。
8. hot reload 只激活完整验证的 immutable candidate revision。
9. projection cutover 在同一 transaction boundary 原子发生。
10. privacy classification 在事件、checkpoint、rebuild evidence 和 debug export 全链路保留。

## Failure Semantics

| Error code | 行为 | 权威影响 | 恢复 |
| --- | --- | --- | --- |
| `event_schema_unknown` | readiness fail | events preserved | 安装 reader/schema |
| `upcaster_chain_missing` | startup/upgrade blocked | events preserved | 补充唯一链并重测 |
| `upcaster_digest_mismatch` | replay fail | events preserved | 修复版本注册，不改事件 |
| `checkpoint_invalid` | 丢弃 checkpoint | none | 从更旧 checkpoint/full replay |
| `stream_revision_gap` | replay quarantined | none | 修复存储完整性/恢复备份 |
| `projection_invariant_failed` | 禁止 cutover | events preserved | 修复 projector 后 shadow rebuild |
| `projection_digest_mismatch` | migration blocked | current projection retained | 审查有意/意外差异 |
| `patch_dependency_invalid` | candidate rejected | active revision retained | 修复 manifest |
| `patch_upgrade_verification_failed` | candidate rejected | active revision retained | 修复并重新发布新 candidate |
| `patch_rollback_incompatible` | rollback refused | current revision retained | forward fix/兼容 reader |
| `hot_reload_activation_failed` | no activation | active revision retained | 查看诊断后重试 |

投影失败发生在 event commit 之后时，不得向调用者谎报“交易未提交”。settlement result 应保留 committed 状态，并标记 projection lag/degraded read availability。

## Acceptance Criteria

1. 删除全部 checkpoint 后 full replay 得到与 checkpointed replay 相同的 canonical digest。
2. checkpoint checksum、schema、projector 或 patch revision 不匹配时自动回退 replay。
3. stream 缺口、重复 revision 和乱序都被检测并阻止 readiness。
4. 每个历史 event version 到当前 reader 均有唯一 upcaster chain；缺口测试能阻止升级。
5. upcaster 对固定 fixture 重复执行 byte/canonical-json 等价。
6. 新 projector 通过 shadow full replay、lag catch-up 与原子 cutover。
7. patch upgrade 期间已开始事务使用旧 revision，新事务使用新 revision。
8. patch disable 后不再产生新业务 event，但旧历史仍可完整 replay。
9. rollback 不删除 upgrade 事件；不兼容降级被明确拒绝。
10. hot reload 的 schema、dependency、capability 或 verification 任一失败时，active revision 保持不变。
11. rebuild failure 不破坏在线 projection，修复后可以从记录位置重试。
12. privacy-restricted 事件不会出现在越权 checkpoint/debug evidence 中。
13. adventure-basic 从空 store 重放购剑装备、伤势/资源阻断、储物戒负重、产权/地契分离、赠与/债务/契约五个场景，结果与在线结算一致。

## Harness Mapping

### Current review gate

- `python scripts/verification/harness.py --profile docs`
- `python scripts/verification/harness.py --profile all`

### Required implementation profiles

- `gameplay-event-replay`
  - full/checkpointed/targeted/shadow replay；
  - deterministic digest；
  - corrupt checkpoint 与 stream gap fault injection。
- `gameplay-patch-runtime`
  - install/enable/disable/upgrade/rollback；
  - pinned transaction revisions；
  - failed candidate 保留 active revision。
- `gameplay-state-groups`
  - dormant/archive/rematerialization replay。
- `gameplay-economy-authority`
  - 跨域 transaction replay 与 revision recovery。
- `adventure-basic`
  - 空 store、checkpoint 和 full replay 三条运行路径等价。
- `gameplay-foundation-all`

持久化实现的 Harness 证据必须写入 `.harness/verification/`，包含 run-id archive、replay digest、input revision vector、patch/projector version 和失败注入结果。
