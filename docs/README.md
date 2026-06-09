# Docs Index

这份索引只做两件事：

- 告诉你从哪里开始看
- 把当前 `docs/` 按用途分组，避免继续把“计划、设计、当前状态、运行手册、参考资料”混着找

---

## 1. 先看哪里

如果你只想快速理解当前仓库状态，按这个顺序看：

1. [system-l1-current-implementation-summary.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/system-l1-current-implementation-summary.md)
   - `System L1` 当前实现总结、案例、时序图、差距、未来方向
2. [superpowers/plans/2026-06-10-repository-plan-status-register.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/2026-06-10-repository-plan-status-register.md)
   - 仓库级 plan 状态总表
3. [phase1-l1-full-scope-checklist.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/phase1-l1-full-scope-checklist.md)
   - 当前仓库 `System L1` 覆盖面清单

---

## 2. 当前状态与总结

- [system-l1-current-implementation-summary.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/system-l1-current-implementation-summary.md)
- [phase1-l1-full-scope-checklist.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/phase1-l1-full-scope-checklist.md)
- [scene tree.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/scene%20tree.md)

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
- [asset-injection-guide.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/asset-injection-guide.md)
- [assets-policy.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/assets-policy.md)
- [blender-godot-asset-export-convention.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/blender-godot-asset-export-convention.md)

---

## 6. 运行与验证

- [demo-script.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/demo-script.md)
- [jeheno-third-person-controller-asset-audit.md](/d:/Users/User/Documents/paralls-phase-0-demo/docs/jeheno-third-person-controller-asset-audit.md)
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
- 用仓库级 register 统一计划状态

如果后续要进一步整理，可以再做第二阶段文档重构：

- 把根目录文档移动到 `docs/current/`、`docs/runtime/`、`docs/assets/`
- 补充每个子目录自己的 `README`
- 统一中英文命名风格
