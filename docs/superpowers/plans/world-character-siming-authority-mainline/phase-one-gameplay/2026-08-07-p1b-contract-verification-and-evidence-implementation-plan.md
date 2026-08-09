# P1B Contract Verification And Evidence Implementation Plan

> Backfill 2026-08-09: `implemented-and-verified`. Fresh report has G1-G8 all true, including
> duplicate/payload mismatch, zero-write permission failures, replay, reservation trace,
> revision/package gates and scoped projections.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 用两个结构不同的 contract fixture 和八组 Harness gates 证明 P1A 可以被复用、拒绝、回放、过滤和迁移。

**Architecture:** P1B 只增加验证脚本、fixture builders、报告和 profile 依赖，不创建验证专用 store、bus、scheduler 或测试 NPC。所有 fixture 通过现有 P1A adapter 和 `GameplayEventStore` 产生证据。

**Tech Stack:** Python pytest, existing `scripts/verification/common.py`, Harness profile registry, JSON/Markdown/NDJSON evidence。

---

## Requirements Summary

- G1 contract closure；G2 cross-fixture generality；G3 reliability；G4 replay；G5 reservation；G6 profile/revision；G7 package gate；G8 scope filtering。
- Fixture A 使用 effect/resistance；Fixture B 使用 object/ownership/action。
- 所有失败必须零部分提交，所有报告包含 command/event/receipt/failure/replay digest。

## Acceptance Criteria

1. `gameplay-foundation-phase1b` profile 失败时不会生成绿报告或覆盖前一次证据。
2. 两个 fixture 使用同一个 identity、semantic、action/fact、settlement、time、projection contract，schema diff 中无样板字段进入 core。
3. unknown schema、dependency/capability conflict、stale revision、duplicate payload mismatch、terminal reservation、disabled tick/write 均有稳定 failure code。
4. full replay、checkpoint-tail、upcast 和 projection rebuild 的 digest 一致；scope report 证明 actor/creator/public/Godot 过滤不同。
5. P1C 只需引用 P1A/P1B contract，不定义第二套 event/replay 协议。

## Implementation Steps

### Task 1: Build fixture and report helpers

**Files:**
- Create: `scripts/verification/phase1b_contract_fixtures.py`
- Create: `scripts/verification/phase1b_contract_report.py`
- Create: `scripts/verification/tests/test_phase1b_contract_fixtures.py`

- [x] **Step 1: Write failing tests** for deterministic fixture IDs, pinned revisions, redacted projection payloads and stable report schema.
- [x] **Step 2: Implement** pure builders for Fixture A/B that return typed commands, semantic snapshots, evidence refs and expected owner maps; no direct store mutation outside the authority call.
- [x] **Step 3: Run** `python -m pytest scripts/verification/tests/test_phase1b_contract_fixtures.py -q`; expected PASS.

### Task 2: Implement G1-G3 and failure injection

**Files:**
- Create: `scripts/verification/verify_phase1b_contract.py`
- Create: `scripts/verification/tests/test_verify_phase1b_contract.py`
- Modify: `backend/tests/test_gameplay_shared_contracts.py`

- [x] **Step 1: Add tests** for success, structured rejection, permission, stale revision, duplicate, zero-write, schema conflict, capability conflict and package conflict.
- [x] **Step 2: Implement** profile runner sections G1, G2 and G3 using one fresh store per fixture and explicit event-count snapshots before/after rejected commands.
- [x] **Step 3: Run** `python -m pytest scripts/verification/tests/test_verify_phase1b_contract.py -q`; expected PASS.

### Task 3: Implement replay, reservation, profile and scope gates

**Files:**
- Modify: `scripts/verification/verify_phase1b_contract.py`
- Modify: `scripts/verification/tests/test_verify_phase1b_contract.py`
- Modify: `backend/tests/test_gameplay_event_replay.py`

- [x] **Step 1: Add** G4 replay hashes, G5 reservation lifecycle traces, G6 profile granularity/pinned revision comparison and G8 projection redaction checks.
- [x] **Step 2: Add** explicit G7 manifest dependency/schema/capability/migration fail-closed cases.
- [x] **Step 3: Run** `python -m pytest scripts/verification/tests/test_verify_phase1b_contract.py backend/tests/test_gameplay_event_replay.py -q`; expected PASS.

### Task 4: Register profile and evidence outputs

**Files:**
- Create: `.harness/profiles/phase1b-contract-verification.json`
- Modify: `docs/harness.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/phase-one-gameplay/2026-08-07-p1b-contract-verification-and-evidence-design.md`

- [x] **Step 1: Register** the profile with predecessor `gameplay-foundation-contract`, `gameplay-event-replay`, `gameplay-state-groups`, `gameplay-resource-body`, `gameplay-ownership-authority`, `gameplay-economy-authority` and `godot-gameplay-mirror` checks.
- [x] **Step 2: Write** JSON/MD/NDJSON paths into `.harness/verification/phase1b-contract-verification-*` and document them in `docs/harness.md`.
- [x] **Step 3: Run** `python scripts/verification/harness.py --profile phase1b-contract-verification`; expected PASS.

## Risks And Mitigations

- **Risk:** fixture helpers become hidden domain logic. **Mitigation:** keep all state changes in existing authorities and assert owner matrices in the report.
- **Risk:** a green fixture masks missing predecessor evidence. **Mitigation:** profile runner fails closed on missing/non-green predecessor artifacts.
- **Risk:** reports leak private fixture data. **Mitigation:** use creator-debug redaction and public projection builders for every emitted payload.

## Verification Steps

1. `python -m pytest scripts/verification/tests/test_phase1b_contract_fixtures.py scripts/verification/tests/test_verify_phase1b_contract.py -q`
2. `python scripts/verification/harness.py --profile phase1b-contract-verification`
3. `python scripts/verification/harness.py --profile gameplay-foundation-all`
4. `python scripts/verification/harness.py --profile docs`

## Spec Coverage Review

Tasks 1-3 cover all P1B gates and required failure/replay cases; Task 4 covers profile registration
and evidence retention. No P1C domain behavior, NPC state or new runtime is included.
