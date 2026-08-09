# Gameplay Foundation Shared Contract Closure Implementation Plan

> Backfill 2026-08-09: `implemented-and-verified`. Fresh `gameplay-foundation-contract` and
> focused shared-contract/replay/permission tests pass. `gameplay-foundation-all` remains an
> aggregate verification item and is not silently inferred from this child profile.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 在现有 Gameplay Foundation owner 上收口可被 V0、Econ-1 和后续异质玩法复用的 identity、semantic/meta-rule、action/fact、reservation、settlement、profile、revision、permission 和 replay contract。

**Architecture:** 新增的 contract 只提供严格值对象、注册表和预提交 mapper；写入仍由 owning authority 验证并调用 `GameplayEventStore.append_batch()`。`CharacterGameRuntimeState`、System L6、Godot、Creator Control Plane 都保持投影或边界适配器身份，不能成为 canonical owner。

**Tech Stack:** Python 3, Pydantic strict models, existing `backend/app/gameplay` modules, pytest, Harness JSON profiles。

---

## Requirements Summary

- 保留当前 `GameplayEvent`, `AtomicEventBatch`, idempotency、stream revision、schema registry、upcaster 和 checkpoint 兼容性。
- 为 tag/material/property/effect/resistance/meta-rule 固定 namespace、revision、预算、冲突和解释 trace。
- 让 `ActionIntent -> PhysicalFact/LogicalFact -> typed EffectProposal -> SettlementPlan -> append_batch` 可验证。
- 固定 Reservation/Hold、world profile、active revision、package manifest、reader/editor/admin authorization decision 的边界。
- 完整 replay 不重新执行当前 Rule IR；迁移只能引用闭源核心已注册 upcaster/migrator。

## Acceptance Criteria

1. 未注册 tag/effect/schema/capability、命名冲突、循环、预算超限和 revision conflict 全部 fail closed 且零事件提交。
2. `GameplayCommandEnvelope` 能映射到现有 `AtomicEventBatch`，`stream_ref` 能映射到现有 `stream_id`，重复 idempotency 返回原 receipt。
3. Reservation 的 reserve/consume/release/expire/compensate 每个重复、过期、未知输入均无部分写入。
4. `ActiveWorldRevision` 和 `ActiveSemanticSet` 被写入 command、event、receipt、checkpoint 与 replay evidence。
5. `reader/editor/admin` 只产生项目范围的 `AuthorizationDecision`，没有任何外部入口获得 event-store 或内部 dossier 写权限。
6. full replay 与 checkpoint-plus-tail replay 的 projection hash 相同，upcaster 输入/输出 schema digest 被校验。
7. `python scripts/verification/harness.py --profile gameplay-foundation-contract` 与既有 Gameplay Foundation profiles 全部通过。

## Implementation Steps

### Task 1: Lock failing contract tests

**Files:**
- Create: `backend/tests/test_gameplay_shared_contracts.py`
- Modify: `backend/tests/test_gameplay_event_store_contract.py`

- [x] **Step 1: Write failing tests** for strict model rejection, namespace collision, meta-rule deterministic trace, command-to-batch mapping, authorization scope, and reservation terminal-state rejection.
- [x] **Step 2: Run the focused tests**

Run: `python -m pytest backend/tests/test_gameplay_shared_contracts.py backend/tests/test_gameplay_event_store_contract.py -q`
Expected: FAIL because the shared contract models and mappers do not exist.

### Task 2: Add strict shared contract models and registries

**Files:**
- Create: `backend/app/gameplay/shared_contracts.py`
- Create: `backend/app/gameplay/semantic_registry.py`
- Modify: `backend/app/gameplay/models.py`
- Modify: `backend/app/gameplay/event_schema_registry.py`

- [x] **Step 1: Implement** `EntityRef`, `RevisionVector`, `SemanticSnapshot`, `ActionPrimitiveDefinition`, `ActionIntent`, `PhysicalFact`, `LogicalFact`, `EffectProposal`, `Reservation`, `WorldConsumptionProfile`, `ActiveSemanticSet`, `ActiveWorldRevision`, `GameplayPackageManifest`, `ProjectionEnvelope`, `AuthorizationDecision`, and `StructuredFailure` as `extra="forbid"` Pydantic models with explicit versions and digests.
- [x] **Step 2: Implement** namespaced semantic registration, deterministic priority/conflict validation, bounded meta-rule evaluation trace, and fail-closed unknown definition handling. The registry may return proposals only.
- [x] **Step 3: Preserve** existing `GameplayEvent` field names and add only versioned optional metadata; do not rename `stream_id` or alter current batch idempotency checks.
- [x] **Step 4: Run the focused tests**

Run: `python -m pytest backend/tests/test_gameplay_shared_contracts.py backend/tests/test_gameplay_event_schema_registry.py -q`
Expected: PASS.

### Task 3: Add the settlement and reservation adapters

**Files:**
- Create: `backend/app/gameplay/settlement_plan.py`
- Modify: `backend/app/gameplay/patch_rule_settlement.py`
- Modify: `backend/app/gameplay/event_store.py`
- Modify: `backend/tests/test_gameplay_event_store_contract.py`

- [x] **Step 1: Add** a pure `SettlementPlan` mapper that accepts pinned revisions, typed proposals, expected stream revisions and idempotency data, then returns one `AtomicEventBatch` or a structured zero-write failure.
- [x] **Step 2: Add** reservation lifecycle validation for owner, target aggregate, amount/quantity, expiry and terminal status. Domain owners still append the lifecycle events.
- [x] **Step 3: Add** fast-path/general-path result-equivalence assertions without routing existing bounded authorities through a new coordinator.
- [x] **Step 4: Run** `python -m pytest backend/tests/test_gameplay_event_store_contract.py backend/tests/test_gameplay_patch_rule_settlement.py -q`; expected PASS.

### Task 4: Bind state-group profiles and active revisions

**Files:**
- Create: `backend/app/gameplay/active_world_revision.py`
- Modify: `backend/app/gameplay/state_group_lifecycle_authority.py`
- Modify: `backend/app/gameplay/state_group_views.py`
- Modify: `backend/app/gameplay/runtime_state.py`
- Create: `backend/tests/test_gameplay_active_revision.py`

- [x] **Step 1: Write failing tests** for `disabled`, `narrative`, `lightweight`, and `simulation` activation, no-hidden-effect semantics, activation lock conflict, session pinning, and profile granularity replay equivalence.
- [x] **Step 2: Implement** candidate validation, dependency/conflict checking, activation lock, pending activation, scheduled activation, retirement and forward rollback selection as append-only state transitions.
- [x] **Step 3: Ensure** `CharacterGameRuntimeState` returns explicit missing reasons and never performs activation or background ticks.
- [x] **Step 4: Run** `python -m pytest backend/tests/test_gameplay_active_revision.py backend/tests/test_gameplay_runtime_state.py -q`; expected PASS.

### Task 5: Close replay, checkpoint, package and permission evidence

**Files:**
- Modify: `backend/app/gameplay/replay.py`
- Modify: `backend/app/gameplay/event_upcasters.py`
- Modify: `backend/app/gameplay/event_store.py`
- Create: `backend/tests/test_gameplay_shared_replay_and_permission.py`

- [x] **Step 1: Add** replay context/evidence validation for event ordering, schema/upcaster chain, checkpoint projection hash, active revision digest and idempotency records before write readiness resumes.
- [x] **Step 2: Add** immutable package lifecycle validation: `draft -> validated -> staged -> scheduled -> active -> retired`, with rejected activation and incompatible rollback paths.
- [x] **Step 3: Preserve** three creator tiers as authorization inputs; reject missing/expired/project-mismatched decisions and never expose internal Python imports.
- [x] **Step 4: Run** `python -m pytest backend/tests/test_gameplay_shared_replay_and_permission.py backend/tests/test_gameplay_event_replay.py backend/tests/test_gameplay_event_store_persistence.py -q`; expected PASS.

### Task 6: Add the contract Harness profile and documentation

**Files:**
- Modify: `scripts/verification/verify_gameplay_foundation_contract.py`
- Modify: `scripts/verification/tests/test_gameplay_foundation_contract_verify.py`
- Modify: `.harness/profiles/gameplay-foundation-contract.json`
- Modify: `docs/harness.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-08-07-gameplay-foundation-shared-contract-closure-design.md`

- [x] **Step 1: Add** G1-G3 report sections for semantic/meta-rule, envelope compatibility, reservation, activation/package, permission and replay evidence.
- [x] **Step 2: Add** deterministic JSON, Markdown and NDJSON artifacts under `.harness/verification/` and fail closed when a predecessor report is absent or non-green.
- [x] **Step 3: Run** `python scripts/verification/harness.py --profile gameplay-foundation-contract` and `python scripts/verification/harness.py --profile gameplay-foundation-all`; expected both PASS.

## Risks And Mitigations

- **Risk:** shared models become a second aggregate. **Mitigation:** keep them value objects and require every write to map through existing owner modules and `append_batch`.
- **Risk:** schema extensions break current event snapshots. **Mitigation:** retain current fields, register schema digests, and use continuous trusted upcasters.
- **Risk:** creator authorization leaks runtime-private data. **Mitigation:** preserve data classification and scope in every projection and failure envelope.
- **Risk:** profile/activation introduces a hidden clock. **Mitigation:** store explicit tick commands and obligations; do not add a scheduler owner.

## Verification Steps

1. `python -m pytest backend/tests/test_gameplay_shared_contracts.py backend/tests/test_gameplay_active_revision.py backend/tests/test_gameplay_shared_replay_and_permission.py -q`
2. `python scripts/verification/harness.py --profile gameplay-foundation-contract`
3. `python scripts/verification/harness.py --profile gameplay-foundation-all`
4. `python scripts/verification/harness.py --profile docs`

## Spec Coverage Review

This plan covers every P1A section: existing-owner binding (Tasks 2-5), semantic/meta-rule
(Task 2), command/event/evidence envelope (Tasks 1-3), creator authorization (Task 5),
activation/package lifecycle (Task 4-5), replay/migration (Task 5), and Harness gates (Task 6).
It does not implement Construction, Survival, Economy, Organization, Government, Population
Simulation or Creator Control Plane product APIs; those remain downstream plans.
