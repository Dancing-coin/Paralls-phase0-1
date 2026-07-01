# 当前项目 `Perception Query Frame` 与感知结果协议实施计划

> 对应规格：
> [2026-06-29-current-project-perception-query-and-percept-protocol-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-perception-query-and-percept-protocol-design.md)

**目标：** 建立当前项目多模态链的统一取样协议与统一感知结果协议。

## 任务

- [x] 定义 `Perception Query Frame` 的字段、时间窗和空间参考系
- [x] 定义 `Modality Interpretation Result`
- [x] 定义 `Cross-Modal Understanding Result`
- [x] 定义 `Canonical Percept Bundle`
- [x] 设计角色与司命共享协议但不共享上下文的规则
- [x] 设计 focused tests / verifier，保证协议落地后不破坏现有主链

## 产出

- 统一多模态输入协议
- 统一三层感知结果协议
- 上下文隔离规则

## 执行证据

- 落地文件：
  - `backend/app/world_runtime/intelligence_upgrade.py`
  - `backend/tests/test_current_project_intelligence_upgrade.py`
- 验证：
  - `python -m pytest backend/tests/test_current_project_intelligence_upgrade.py::test_perception_query_frame_and_percept_protocol_enforce_context_isolation -v`
  - `python scripts/verification/verify_current_project_intelligence_upgrade.py`
- 剩余风险：
  - 当前落地为结构化协议与 focused proof，未接入真实重多模态模型。
