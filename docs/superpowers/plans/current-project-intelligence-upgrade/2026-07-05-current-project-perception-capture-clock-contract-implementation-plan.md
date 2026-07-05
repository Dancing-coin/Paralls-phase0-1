# 当前项目感知 capture 时钟契约实施计划

- 状态：`proposed`
- 日期：`2026-07-05`

上位设计：

- [2026-07-05-current-project-perception-capture-clock-contract-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-05-current-project-perception-capture-clock-contract-design.md)

## 1. 目标

把当前感知链从“近似时间窗”升级到“有根 capture 身份 + 单调时钟 + 派生规则”的可验证时序契约。

## 2. 实施范围

- `backend/app/models/raw_fact.py`
- `backend/app/world_runtime/intelligence_upgrade.py`
- `backend/app/world_runtime/l1_perception_frame.py`
- `backend/app/world_runtime/l1_runtime_perception_bridge.py`
- `backend/app/world_runtime/vla_provider.py`
- `scripts/verification/*perception*`
- 相应 backend tests

## 3. 实施步骤

1. 新增 `capture_root_id / capture_id / clock_domain / monotonic_tick / source_frame_index`
2. 扩展 `RawFactEvent`、`SampleInputRef`、`PerceptionQueryFrame`、`CanonicalPerceptBundle`
3. 扩展 VLA request/result trace，标注“原拍”还是“后补 advisory”
4. 定义 active perception / recheck 派生规则
5. 补 focused tests 与 verifier

## 4. 验收

- [ ] `capture_root_id` 是同拍判定主身份
- [ ] `monotonic_tick` 是顺序判定主时钟
- [ ] wall clock 仅用于证据，不用于同拍判定
- [ ] VLA 慢路径跨拍返回时不会伪装成原拍
- [ ] 日志能回溯完整 identity lineage
