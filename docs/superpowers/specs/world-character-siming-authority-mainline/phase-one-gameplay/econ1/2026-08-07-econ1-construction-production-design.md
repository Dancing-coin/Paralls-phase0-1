# Econ-1 Construction And Production Design

Status: `approved; matching plan authorized by user on 2026-08-07`

Date: `2026-08-07`

## Purpose And Boundary

定义面包店所需的最小建造/生产 authority。它只拥有地块、设施、蓝图、配方和生产 run
进度，不拥有账户余额、库存数量、角色身体、工资或税费。

## Models

```text
Plot
  plot_ref, jurisdiction_ref, ownership_right_ref, zoning_policy_ref, revision

Blueprint
  blueprint_ref, component_defs, material_requirements, labor_requirements,
  duration, capability_refs, schema_revision

Facility
  facility_ref, plot_ref, ownership_right_ref, capability_refs, condition,
  throughput, maintenance_policy, revision

Recipe
  recipe_ref, input_lot_requirements, tool_refs, skill_requirements,
  duration, outputs, byproducts, quality_policy, revision

ConstructionJob / ProductionRun
  run_ref, target_ref, blueprint_or_recipe_ref, reservation_refs,
  start_tick, finish_tick, status, quality_digest, revision
```

## Lifecycle

```text
validate plot/permit/ownership
-> reserve material/tool/facility slot/labor obligation
-> start job or production run
-> scheduled finish obligation
-> revalidate pinned revisions and reservations
-> consume/release reservations
-> append facility/output/maintenance evidence
```

Material and tool custody remains Inventory authority truth. Labor qualification comes from
Skill and optional existing CharacterRecord. Wage posting remains Economy/Organization.

## Failure Semantics

- missing zoning/permit/ownership;
- material/tool reservation unavailable;
- facility slot conflict;
- skill/ability insufficient;
- reservation expired or stale;
- finish obligation duplicated or revision-conflicted。

Any rejection leaves material, account, facility and character projections unchanged. A failed
run may produce explicit loss, release, rework or recovery obligations, but never silently
restores or deletes another domain's facts.

## Acceptance

- one bakery facility can be acquired/constructed;
- one recipe reserves and consumes materials;
- output enters Inventory through typed event mapping;
- finish is idempotent and replayable;
- maintenance/condition can create an obligation without a hidden scheduler;
- Godot sees only committed facility/output projection。
