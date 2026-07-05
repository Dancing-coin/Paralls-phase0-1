# 当前项目感知身份验证矩阵设计

- 状态：`proposed`
- 日期：`2026-07-05`

## 1. 目标

把“感知 identity 是否正确”从字段存在检查升级为行为矩阵验证。

## 2. 必须覆盖的场景

1. fact 链和 provider 链同拍同物 -> 同一对象
2. fact 链和 provider 链跨拍 -> 不得误判同拍
3. actor A/B 同拍看同物 -> 同对象不同私有属性
4. actor A/B 同拍看近邻不同物 -> 不误合并
5. VLA 后补 advisory -> 标记为后补，不伪装原拍
6. Siming multi-actor 汇总 -> 不丢 object/time identity

## 3. 证据要求

每条验证至少输出：

- `capture_root_id`
- `capture_id`
- `actor_id`
- `world_anchor_id`
- `subject_ref`
- `target_ref`
- `source_ref_lineage`
- `clock_domain`
- `monotonic_tick`
- `result_kind`

## 4. 验证类型

- focused unit tests
- focused verifier
- 聚合 harness profile 扩展
