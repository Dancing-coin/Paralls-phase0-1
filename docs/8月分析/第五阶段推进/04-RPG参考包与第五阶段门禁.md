# RPG 参考包与第五阶段门禁

状态：`incremental design; P5D formal spec and Harness profile required before implementation`

建议参考包为“面包店失窃调查”：玩家和两个已有角色在 P4 商业街中调查一批缺失材料，
通过物品 provenance、角色知识、关系、潜行观察和合同证据定位责任方，并以可回放结果
完成任务或进入恢复流程。

## 1. 必须覆盖

- 一个多阶段 objective 与 evidence chain；
- 至少两个角色的 scoped knowledge/relationship projection；
- 一个技能 gate、一个工具/背包 gate、一个潜行或可见性 gate；
- 一个冲突或追捕结果，影响组织、合同或经济义务；
- Survival 可选择 `DISABLED`、`NARRATIVE` 或受限 `LIGHTWEIGHT`，规则不写死；
- 成功、失败、重复、stale revision、证据越权和恢复均可 replay。

## 2. 完成门

P5 只能声称“调查/RPG vertical slice 已通过权威、回放和隐私门禁”，不能声称完整战斗、
完整任务编辑器、文明叙事或开放世界 RPG 已完成。P1-P4 predecessor、Godot committed
mirror 和 focused Harness 必须全部 fresh-green。
