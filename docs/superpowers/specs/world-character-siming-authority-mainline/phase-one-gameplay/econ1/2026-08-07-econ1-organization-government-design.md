# Econ-1 Organization And Government Design

Status: `approved; matching plan authorized by user on 2026-08-07`

Date: `2026-08-07`

## Purpose And Boundary

定义面包店所需的最小商业组织和政府监管事实。Organization Authority 拥有组织、岗位、
预算、经营计划和 period close；Government Authority 拥有辖区、许可证、税制、检查和
政策 revision。两者都不能复制角色、账户、库存、设施或身体真相。

## Models

```text
Organization
  organization_ref, kind, jurisdiction_ref, account_refs, asset_refs, status, revision

RoleAssignment
  assignment_ref, organization_ref, character_ref, role_ref,
  authority_scope, schedule_ref, status, revision

OperatingPlan
  plan_ref, organization_ref, period_ref, budget_ref, procurement_targets,
  production_targets, pricing_policy_ref, approval_refs, revision

Permit
  permit_ref, holder_org_ref, jurisdiction_ref, scope, policy_revision,
  effective_tick, expires_at_tick, status

Inspection
  inspection_ref, permit_ref, inspector_authority_ref, criteria_revision,
  result, remediation_refs, evidence_refs

TaxAssessment
  assessment_ref, holder_org_ref, period_ref, tax_kind, taxable_base,
  amount, due_tick, policy_revision, status
```

## First-Phase Rules

- one bakery organization and one jurisdiction;
- one operating permit and one inspection result;
- one sales tax policy, one rent/license policy and optional debt primitive;
- owner/manager may act directly in `bakery-single-owner`;
- employee role assignments only reference existing CharacterRecords;
- inspector, landlord and debt collector are organizations/policies, not injected NPCs;
- public competitor profiles cannot read private bakery budget, inventory or role state。

## Cross-Domain Responsibilities

Organization schedules procurement, production and period targets, but does not own their
progress. Government validates permit/policy/inspection, but does not delete assets or mutate
private character state. Economy posts money and obligations; Inventory/Construction/Survival
keep their own facts.

## Acceptance

- bakery cannot perform public sale before permit activation;
- permit expiry rejects sale without partial payment or inventory mutation;
- tax assessment is reproducible from period and policy revisions;
- inspection failure creates explicit remediation, fine or pause obligation;
- organization period close references account/inventory/facility projections without copying
  them;
- role/employee paths distinguish existing CharacterRecord from population-simulation NPC;
- all policy, permit, organization and period events replay and filter by scope。
