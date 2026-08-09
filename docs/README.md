# 文档索引

这份索引只做两件事：

- 告诉你从哪里开始看
- 把当前 `docs/` 按用途分组，避免继续把“计划、设计、当前状态、运行手册、参考资料”混着找

---

## 1. 先看哪里

如果你只想快速理解当前仓库状态，按这个顺序看：

1. [INDEX.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/INDEX.md)
   - 当前主线入口：`world-character-Siming-authority unified runtime`
2. [STRUCTURE.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/STRUCTURE.md)
   - 文档目录建设方案、命名规则和维护规则
3. [架构/整体架构.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/整体架构.md)
   - 仓库级整体架构总纲，内含手绘式 Markdown 架构图：Godot、后端、世界运行时、System L6 事件总线、角色智能体、ESM、Siming、模型服务、Harness、非运行时支撑面
4. [架构/运行时/运行时总览.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/运行时总览.md)
   - 整体运行时架构、整体时序和整体数据流总入口
5. [架构/运行时/运行时覆盖矩阵.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/运行时覆盖矩阵.md)
   - 当前运行时覆盖矩阵：领域、代码负责人、数据契约、验证证据和缺口
6. [架构/运行时/模块/世界运行时.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/模块/世界运行时.md)
   - `backend/app/world_runtime/` 大类：L1、PQF、VLA、模型 readiness、调度和 continuity
7. [架构/运行时/图表/整体运行时时序图.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/图表/整体运行时时序图.md)
   - 当前运行时时序图：对话、交互成功/失败、Siming 催化、角色执行投递、provider 到 PQF
8. [架构/运行时/图表/整体运行时数据流图.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/图表/整体运行时数据流图.md)
   - 当前运行时数据流图：L1/PQF、ESM 合并、角色智能体、Siming 投影、VLA 运行时、模型服务边界
9. [架构/运行时/模块/SystemL1.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/模块/SystemL1.md)
   - `System L1` 配套运行时文档：事实、provider、PQF、ESM/交互边界
10. [架构/运行时/模块/SystemL6事件总线.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/模块/SystemL6事件总线.md)
   - `System L6` 跨层基础设施：authority event bus、路由、投影、回放和审计辅助边界
11. [架构/运行时/模块/角色智能体.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/模块/角色智能体.md)
   - 角色智能体配套运行时文档：L1/L2/L3/L4、记忆、投递、兼容边界
12. [架构/运行时/模块/ESM与交互编排.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/模块/ESM与交互编排.md)
   - ESM、交互编排和物理通道边界
13. [架构/运行时/模块/Godot表现与角色入口.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/模块/Godot表现与角色入口.md)
   - Godot 输入、表现、provider 和角色入口边界
14. [架构/运行时/模块/VLA运行时通道.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/模块/VLA运行时通道.md)
   - 已实现的 VLA 视觉/空间运行时慢路径和无直接 authority 写权限边界
15. [架构/运行时/模块/模型服务通道.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/模块/模型服务通道.md)
   - 模型 provider readiness、adapter 和真实调用证明边界
16. [架构/运行时/模块/Harness验证证据.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/模块/Harness验证证据.md)
   - Harness profile 和验证证据产物边界
17. [system-l1-current-implementation-summary.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/system-l1-current-implementation-summary.md)
   - `System L1` 当前实现总结、案例、时序图、差距、未来方向
18. [superpowers/plans/2026-06-10-repository-plan-status-register.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/2026-06-10-repository-plan-status-register.md)
   - 仓库级计划状态总表
19. [phase1-l1-full-scope-checklist.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/phase1-l1-full-scope-checklist.md)
   - 当前仓库 `System L1` 覆盖面清单

---

## 2. 当前状态与总结

- [system-l1-current-implementation-summary.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/system-l1-current-implementation-summary.md)
- [STRUCTURE.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/STRUCTURE.md)
- [架构/整体架构.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/整体架构.md)
- [架构/运行时/运行时总览.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/运行时总览.md)
- [架构/运行时/运行时覆盖矩阵.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/运行时覆盖矩阵.md)
- [架构/运行时/模块/世界运行时.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/模块/世界运行时.md)
- [架构/运行时/图表/整体运行时时序图.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/图表/整体运行时时序图.md)
- [架构/运行时/图表/整体运行时数据流图.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/图表/整体运行时数据流图.md)
- [架构/运行时/模块/SystemL1.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/模块/SystemL1.md)
- [架构/运行时/模块/SystemL6事件总线.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/模块/SystemL6事件总线.md)
- [架构/运行时/模块/角色智能体.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/模块/角色智能体.md)
- [架构/运行时/模块/ESM与交互编排.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/模块/ESM与交互编排.md)
- [架构/运行时/模块/Godot表现与角色入口.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/模块/Godot表现与角色入口.md)
- [架构/运行时/模块/VLA运行时通道.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/模块/VLA运行时通道.md)
- [架构/运行时/模块/模型服务通道.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/模块/模型服务通道.md)
- [架构/运行时/模块/Harness验证证据.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/架构/运行时/模块/Harness验证证据.md)
- [phase1-l1-full-scope-checklist.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/phase1-l1-full-scope-checklist.md)
- [scene tree.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/scene%20tree.md)
- [7月分析/](/d:/Users/User/Documents/paralls-phase-0-demo/docs/7月分析/README.md)
  - 历史分析与修复方案（分析性质，带状态头，不作为实现事实声明）
  - 当前收录：角色智能体断点分析、七月 spec 需求分析与具身/VLA 差距分析

---

## 3. 执行计划

目录：

- [docs/superpowers/plans/](./superpowers/plans/)

最重要的几个：

- [2026-06-10-repository-plan-status-register.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/2026-06-10-repository-plan-status-register.md)
- [2026-06-08-system-l1-full-phase1-implementation-plan.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/2026-06-08-system-l1-full-phase1-implementation-plan.md)
- [2026-06-08-system-l1-esm-full-domain-implementation-plan.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/2026-06-08-system-l1-esm-full-domain-implementation-plan.md)
- [2026-06-08-system-l1-visual-fact-system-implementation-plan.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/2026-06-08-system-l1-visual-fact-system-implementation-plan.md)
- [2026-06-08-system-l1-client-interaction-implementation-plan.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/2026-06-08-system-l1-client-interaction-implementation-plan.md)

---

## 4. 设计规范

目录：

- [docs/superpowers/specs/](./superpowers/specs/)

当前最值得读的：

- [2026-06-08-system-l1-esm-full-domain-design.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/2026-06-08-system-l1-esm-full-domain-design.md)
- [2026-06-08-system-l1-visual-fact-system-design.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/2026-06-08-system-l1-visual-fact-system-design.md)
- [2026-06-08-system-l1-to-l2-interface-design.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/2026-06-08-system-l1-to-l2-interface-design.md)
- [2026-06-02-phase05-runtime-alignment-design.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/2026-06-02-phase05-runtime-alignment-design.md)

---

## 5. 场景 / 角色 / 资产说明

- [sample-scene-setup.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/sample-scene-setup.md)
- [phase05-scene-zones.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/phase05-scene-zones.md)
- [character-execution-notes.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/character-execution-notes.md)
- [mixabridge-character-pipeline.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/mixabridge-character-pipeline.md)
- [homebuilder-scene-pipeline.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/homebuilder-scene-pipeline.md)
- [art-resource-swap-workflow.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/art-resource-swap-workflow.md)
- [asset-injection-guide.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/asset-injection-guide.md)
- [assets-policy.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/assets-policy.md)
- [blender-godot-asset-export-convention.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/blender-godot-asset-export-convention.md)

---

## 6. 运行与验证

- [demo-script.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/demo-script.md)
- [scene-character-import-runtime-checklist.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/scene-character-import-runtime-checklist.md)

---

## 7. 参考设计搬运

目录：

- [docs/reference/phase1-character-agent/](./reference/phase1-character-agent/)
- [docs/reference/phase1-event-bus/](./reference/phase1-event-bus/)
- [docs/reference/phase1-siming/](./reference/phase1-siming/)

这些不是当前仓库已经实现的事实，而是主项目参考资料。

阅读时要区分：

- `reference/`：参考与理想态
- `superpowers/plans` / `superpowers/specs`：本仓库执行与设计面
- `system-l1-current-implementation-summary.md`：当前仓库现实总结

---

## 8. 当前整理原则

这次没有大规模移动 `docs/` 下已有文件，原因是：

- 现有计划、规范、代码引用较多
- 大搬运容易把历史链接和引用打断

当前采用的是：

- 增加总索引
- 增加当前实现总结
- 增加 `docs/STRUCTURE.md` 作为目录建设方案
- 将仓库级和运行时级架构文档收敛到 `docs/架构/`
- 用仓库级登记表统一计划状态

如果后续要进一步整理，可以再做第二阶段文档重构：

- 把根目录文档移动到 `docs/概览/`、`docs/运行/`、`docs/验证/`、`docs/资产/`
- 补充每个子目录自己的 `README`
- 统一中文可读文件名，保留必要技术标识
