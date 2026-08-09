# Econ-1 Organization And Government Implementation Plan

> Backfill 2026-08-09: `implemented-and-verified` for permit verification, tax assessment,
> inspection obligations, role boundary and scoped replay evidence. Government remains a policy
> authority and does not own account, inventory, facility or character state.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 为面包店实现最小 Organization 与 Government authority：组织/角色/经营计划/period close，以及辖区/permit/tax/inspection/policy revision，且不复制角色、账户、库存、设施或身体真相。

**Architecture:** Organization 维护组织治理和经营目标，Government 维护监管事实和政策。它们只读取其他 domain 的版本化 projection；实际余额、inventory、facility、body 和 paid posting 仍留在原 authority。监管者、房东、债权人是 policy/organization refs，不是注入 NPC。

**Tech Stack:** Python/Pydantic, existing ownership/economy/contract/credential runtimes, P1A active revisions and scope projections, pytest, Harness。

---

## Acceptance Criteria

1. public sale 需要 active permit；permit expiry 在 payment/inventory 发生前拒绝。
2. TaxAssessment 可由 period + policy revision 重建；inspection failure 创建 remediation/fine/pause obligation。
3. Organization period close 仅引用 account/inventory/facility projections，不能复制它们为 mutable fields。
4. RoleAssignment 只接受既有 CharacterRecord；synthetic population actor、inspector NPC 和私有 competitor read 均被拒绝。
5. policy/permit/organization/period events 可 replay，并按 actor/creator/public/Godot scope 过滤。

## Implementation Steps

### Task 1: Add organization and government aggregate models

**Files:**
- Create: `backend/app/gameplay/organization_government_runtime.py`
- Create: `backend/tests/test_organization_government_models.py`
- Modify: `backend/app/gameplay/models.py`

- [x] **Step 1: Write tests** for `Organization`, `RoleAssignment`, `OperatingPlan`, `Permit`, `Inspection`, `TaxAssessment`, strict scope/revision fields and forbidden shadow account/inventory/facility/body fields.
- [x] **Step 2: Implement** strict aggregates/events/projections and package schema registration.
- [x] **Step 3: Run** `python -m pytest backend/tests/test_organization_government_models.py -q`; expected PASS.

### Task 2: Implement permit, inspection and tax-policy decisions

**Files:**
- Modify: `backend/app/gameplay/organization_government_runtime.py`
- Modify: `backend/app/gameplay/econ1_economy_runtime.py`
- Modify: `backend/app/gameplay/settlement_plan.py`
- Create: `backend/tests/test_organization_government_regulation.py`

- [x] **Step 1: Add tests** for permit activation, missing/expired permit, policy revision unavailable, inspection pass/fail and deterministic tax assessment.
- [x] **Step 2: Implement** Government validation as typed decisions/proposals and map accepted tax/fine/pause outcomes to their owning authority batches.
- [x] **Step 3: Run** `python -m pytest backend/tests/test_organization_government_regulation.py -q`; expected PASS.

### Task 3: Implement operating plan, roles and period-close references

**Files:**
- Modify: `backend/app/gameplay/organization_government_runtime.py`
- Modify: `backend/app/gameplay/skill_action_gate.py`
- Modify: `backend/app/gameplay/econ1_economy_runtime.py`
- Create: `backend/tests/test_organization_government_operations.py`

- [x] **Step 1: Write tests** for owner-manager direct action, existing CharacterRecord employee assignment, rejected synthetic employee, procurement/production target and period close references.
- [x] **Step 2: Implement** read-only projection references with expected revisions; no Organization method may append account, inventory, facility or body events.
- [x] **Step 3: Run** `python -m pytest backend/tests/test_organization_government_operations.py -q`; expected PASS.

### Task 4: Add scope, replay and Harness evidence

**Files:**
- Create: `scripts/verification/verify_econ1_organization_government.py`
- Create: `.harness/profiles/econ1-organization-government.json`
- Modify: `docs/harness.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/phase-one-gameplay/econ1/2026-08-07-econ1-organization-government-design.md`

- [x] **Step 1: Verify** permit/sale failure zero-write, tax replay, inspection obligations, role boundary, competitor privacy and scoped projection samples.
- [x] **Step 2: Run** `python scripts/verification/harness.py --profile econ1-organization-government`; expected PASS.

## Risks And Mitigations

- **Risk:** government gains a universal admin write path. **Mitigation:** policy decisions only yield typed proposals; forbidden owner tests inspect all target streams.
- **Risk:** role assignment materializes NPCs. **Mitigation:** validate CharacterRecord existence through the existing identity path and reject synthetic seed IDs.
- **Risk:** public competitor profiles leak private business state. **Mitigation:** only public digest inputs pass the projection classifier.

## Verification Steps

1. `python -m pytest backend/tests/test_organization_government_models.py backend/tests/test_organization_government_regulation.py backend/tests/test_organization_government_operations.py -q`
2. `python scripts/verification/harness.py --profile econ1-organization-government`
3. `python scripts/verification/harness.py --profile econ1-economy-period-settlement`
