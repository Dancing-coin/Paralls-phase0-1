# 当前项目跨感知对象锚点与指代统一实施计划

- 状态：`implemented-and-focused-verified`
- 日期：`2026-07-05`

上位设计：

- [2026-07-05-current-project-cross-modal-object-anchor-and-reference-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-05-current-project-cross-modal-object-anchor-and-reference-design.md)

## 1. 目标

把对象 identity 从当前零散的 `target_object_id / subject_ref / target_ref / object_state` 提升为统一锚点体系。

## 2. 实施范围

- `backend/app/character_agent/reasoning/actor_scene_knowledge.py`
- `backend/app/world_runtime/l1_runtime_perception_bridge.py`
- `backend/app/world_runtime/vla_percept_bridge.py`
- `backend/app/world_runtime/vla_provider.py`
- `backend/app/services/siming_global_situation.py`
- 相关 model / tests / verification

## 3. 实施步骤

1. 定义 `world_anchor_id / target_ref / source_ref_lineage`
2. 扩展 bundle target_state 和 VLA findings
3. 统一 ASK 的 `subject_ref` 与 world truth marker 写法
4. 扩展 Siming evidence chain，显式保留 object anchor
5. 补 object reconciliation tests

## 4. 验收

- [x] 同物跨链统一到同一 `world_anchor_id`
- [x] 同名/近邻对象不会误合并
- [x] advisory 不能越权写 world truth anchor
- [x] ASK / Siming / VLA 的对象身份可追溯

## 5. 验证证据

- `python scripts/verification/verify_perception_object_anchor_contract.py`
- `.harness/verification/perception-object-anchor-contract-report.json`
- `.harness/verification/perception-object-anchor-contract-report.md`
