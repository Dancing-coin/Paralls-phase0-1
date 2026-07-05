# 当前项目 capture-aware bridge 与下游传播实施计划

- 状态：`implemented-and-focused-verified`
- 日期：`2026-07-05`

上位计划：

- [2026-07-05-current-project-perception-alignment-closure-and-gating-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-05-current-project-perception-alignment-closure-and-gating-plan.md)
- [2026-07-05-current-project-perception-input-alignment-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-05-current-project-perception-input-alignment-implementation-plan.md)

## 1. 目标

在不新增第三条融合链、不把 `capture_id` 改成 authority event bus 公共事实主身份的前提下，让 bridge 消费后的角色与司命下游表面继续保留感知 identity。

## 2. 实施范围

- `backend/app/models/character_agent_runtime.py`
- `backend/app/character_agent/reasoning/l1_perception.py`
- `backend/app/services/siming_read_model.py`
- `backend/app/services/siming_runtime.py`
- `backend/tests/test_l1_perception_frame_runtime.py`
- `scripts/verification/verify_perception_downstream_identity_propagation.py`

## 3. 实施步骤

1. 在角色私有 snapshot 中保留最近一次感知 identity
2. 让角色 working memory 通过 private snapshot 暴露同一 identity
3. 让司命 bundle read model 保留 `perception_identity`
4. 让司命输出与 debug payload 保留同一 identity
5. 补 focused verifier，证明下游传播且不污染 authority event identity

## 4. 验收

- [x] Character private snapshot 可追踪 `capture_root_id` 与 `world_anchor_id`
- [x] Character working memory 可通过 private snapshot 追踪同一 identity
- [x] Siming read model 可追踪 `capture_root_id`、`capture_id`、`clock_domain`、`monotonic_tick` 与 `world_anchor_id`
- [x] Siming output/debug payload 保留同一 `perception_identity`
- [x] bundle ingestion 路径不向 authority event bus 发布以 `capture_id` 为事件身份的公共事实

## 5. 验证证据

- `python -m pytest -q backend/tests/test_l1_perception_frame_runtime.py backend/tests/test_siming_global_situation_runtime.py`
- `python scripts/verification/verify_perception_downstream_identity_propagation.py`
- `.harness/verification/perception-downstream-identity-propagation-report.json`
- `.harness/verification/perception-downstream-identity-propagation-report.md`
