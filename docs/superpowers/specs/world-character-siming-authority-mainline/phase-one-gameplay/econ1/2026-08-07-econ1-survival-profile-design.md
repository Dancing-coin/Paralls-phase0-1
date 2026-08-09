# Econ-1 Survival Profile Design

Status: `approved; matching plan authorized by user on 2026-08-07`

Date: `2026-08-07`

## Purpose And Boundary

定义面包店第一版需要的 Survival Authority contract，并把 Survival 作为可按项目、世界、
角色组启停的核心 state group。它复用 resource/body/status/effective-stats，不替代
Character Mind 的 NeedTensionEngine，也不直接扣款或移动物品。

## Modes

| Mode | Canonical consequence |
| --- | --- |
| `disabled` | 不生成需求衰减、消费、身体惩罚或隐式 obligation |
| `narrative` | 只生成可供剧情读取的张力 projection，不扣资源 |
| `lightweight` | 低频需求数值和软劳动影响，使用显式 tick |
| `simulation` | 完整需求、消费、身体后果、劳动能力反馈和恢复 |

Mode is a ruleset/state-group revision. Existing sessions pin their revision; switching mode
does not rewrite historical hunger, health or stamina events.

## Models

```text
NeedDefinition
  need_ref, decay_curve, satisfaction_sources, thresholds, failure_policy, revision

NeedState
  actor_ref, need_ref, tension, last_tick, source_revision, revision

ConsumptionPlan
  plan_ref, actor_ref, need_ref, source_refs, due_tick, reservation_refs, status

SurvivalPolicy
  profile_ref, mode, tick_interval, recovery_policy, labor_effect_policy, revision
```

第一版只要求一个基础食物需求；住房、疾病、复杂营养、家庭照护和人口模型后置。

## Cross-Domain Flow

```text
tick/obligation
-> decay need
-> propose consumption source
-> Inventory checks custody and reserves item
-> Economy checks payment/quote when needed
-> Ownership checks use right
-> Survival settles need/body projection
-> Skill/Organization consume labor-availability projection
```

Survival 只提出需求和消费意图。Inventory、Economy、Ownership 和 Body 的 owning
authority 负责实际事实提交。

## Acceptance

- all four modes have explicit projections and revision metadata;
- disabled mode produces no hidden tick or penalty;
- narrative mode produces no resource consumption;
- lightweight/simulation repeated tick is idempotent;
- food shortage, unavailable source, stale revision and permission failure are structured;
- full replay reconstructs need/body/labor projections;
- P1D can run both survival-disabled and survival-enabled bakery periods。
