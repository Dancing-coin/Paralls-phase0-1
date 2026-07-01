# 当前项目智能体与世界交互增量专题计划树

- 状态：`contract-slice-implemented-l1-subsystem-integration-planned`
- 日期：`2026-06-30`

这份计划树服务于：

- `docs/superpowers/specs/current-project-intelligence-upgrade/`

它不重做已闭合的 dedicated mainline plan tree，而是为 mainline 已闭合之后的增量专题能力提供实现计划。

## 上位规格树

- [specs/current-project-intelligence-upgrade/README.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/README.md)

## 使用方式

1. 先以 `world-character-siming-authority-mainline` 规格树与闭合矩阵作为主线真相。
2. 再从本计划树中挑选需要推进的增量专题能力。
3. 每次执行只应选择一个或少数几个强依赖计划，不要并发推进整棵树。

## 状态口径

当前 `implemented-and-verified` 只适用于 2026-06-30 落地的协议、manifest、静态 provider 和 focused proof 切片。

它不等于完整实现了 `current-project-intelligence-upgrade` 规格树，也不等于 `L1` 已经成为新的 runtime 宿主。

下一步只能推进 `System L1 world fact subsystem` / runtime-facing L1 services 集成：

- [2026-07-01-current-project-l1-world-fact-runtime-full-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-01-current-project-l1-world-fact-runtime-full-implementation-plan.md)

## 计划树

1. [2026-06-30-current-project-intelligence-upgrade-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-intelligence-upgrade-implementation-plan.md)
2. [2026-06-30-current-project-vla-multimodal-upgrade-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-vla-multimodal-upgrade-implementation-plan.md)
3. [2026-06-30-current-project-l1-world-fact-and-space-foundation-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-l1-world-fact-and-space-foundation-implementation-plan.md)
4. [2026-07-01-current-project-l1-world-fact-runtime-full-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-01-current-project-l1-world-fact-runtime-full-implementation-plan.md)
5. [2026-06-30-current-project-perception-query-and-percept-protocol-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-perception-query-and-percept-protocol-implementation-plan.md)
6. [2026-06-30-current-project-character-multimodal-and-actor-scene-knowledge-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-character-multimodal-and-actor-scene-knowledge-implementation-plan.md)
7. [2026-06-30-current-project-siming-multimodal-and-global-situation-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-siming-multimodal-and-global-situation-implementation-plan.md)
8. [2026-06-30-current-project-esm-dual-channel-world-actuation-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-esm-dual-channel-world-actuation-implementation-plan.md)
9. [2026-06-30-current-project-interaction-orchestration-layer-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-interaction-orchestration-layer-implementation-plan.md)
10. [2026-06-30-current-project-godot-sampling-frontend-and-providers-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-godot-sampling-frontend-and-providers-implementation-plan.md)
11. [2026-06-30-current-project-embodied-skeletal-state-provider-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-embodied-skeletal-state-provider-implementation-plan.md)
12. [2026-06-30-current-project-non-runtime-multimodal-tooling-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-non-runtime-multimodal-tooling-implementation-plan.md)

## 一句话收束

这棵计划树的职责不是重新推进主线，而是把 mainline 已闭合之后仍需补强的感知、多模态、协议、具身和工具链能力逐步落地。

## 当前执行证据

- 聚合 focused verifier:
  - `python scripts/verification/verify_current_project_intelligence_upgrade.py`
- 最新证据报告：
  - `.harness/verification/current-project-intelligence-upgrade-report.json`
  - `.harness/verification/current-project-intelligence-upgrade-report.md`
- 主线回归面保持使用：
  - `python scripts/verification/harness.py --profile docs`
  - `python scripts/verification/harness.py --profile mainline-unified-runtime`
- L1 subsystem 集成尚需通过兼容验证入口：
  - `python scripts/verification/harness.py --profile l1-world-fact-runtime`
