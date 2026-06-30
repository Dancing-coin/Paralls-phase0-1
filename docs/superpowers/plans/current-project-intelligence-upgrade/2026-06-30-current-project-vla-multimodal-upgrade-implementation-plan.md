# 当前项目 VLA 与多模态感知增量实施计划

> 对应规格：
> [2026-06-28-current-project-vla-multimodal-upgrade-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-28-current-project-vla-multimodal-upgrade-design.md)

**目标：** 在不重做主线的前提下，为当前项目接入 VLA 空间视觉理解子链、多模态慢通路和角色/司命各自独立的多模态上下文。

**边界：**

- 不把 `VLA` 变成全局主脑
- 不让 `Godot` 承担重推理
- 不让角色和司命共享多模态运行时上下文

## 任务

- [x] 定义 `VLA` 在当前项目中的职责范围
- [x] 定义角色智能体专属多模态栈的输入窗口
- [x] 定义司命专属多模态栈的输入窗口
- [x] 设计慢通路多模态顾问的触发条件
- [x] 设计多模态能力平台与专属多模态栈的边界
- [x] 设计 focused proof，证明新增链路不会反压主循环

## 产出

- 角色与司命各自的多模态上下文设计
- `VLA` 与慢通路的位置图
- 结构化输出契约清单
- focused verification 设计

## 执行证据

- 落地文件：
  - `backend/app/world_runtime/intelligence_upgrade.py`
  - `backend/tests/test_current_project_intelligence_upgrade.py`
- 验证：
  - `python -m pytest backend/tests/test_current_project_intelligence_upgrade.py::test_vla_multimodal_upgrade_places_vla_as_non_blocking_subchain -v`
  - `python scripts/verification/verify_current_project_intelligence_upgrade.py`
- 剩余风险：
  - 当前未接入真实 VLA provider；只固定 VLA 作为非阻塞空间视觉子链的结构化契约。
