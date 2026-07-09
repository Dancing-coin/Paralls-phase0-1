# Paralls 主线仓库索引

这是当前仓库主线的智能体可读地图：

- `world-character-Siming-authority unified runtime`

保留的 `Phase 0` demo 仍然是重要的冒烟兼容表面，但已经不是仓库的顶层目标。

## 从这里开始

- `AGENTS.md`：运行契约、任务边界、验证规则和非目标。
- `docs/ai-engineering-workflow.md`：OpenSpec、Superpowers、Harness、Goal 和原生子智能体工作流。
- `docs/STRUCTURE.md`：文档目录建设方案、命名规则、迁移阶段和维护规则。
- `PHASE0_README.md`：工作区简要说明和验证入口。
- `docs/character/character-mind-core-status.md`：用中文定义“完整 character mind core”在当前仓库中的含义，并区分 authored profile truth、runtime state 与 long-term drift。
- `docs/harness.md`：可重复验证的 Harness Engineering 命令面。
- `docs/架构/运行时/运行时命名边界审计.md`：运行时命名边界审计和迁移表。
- `docs/架构/整体架构.md`：仓库级整体架构总纲，内含手绘式 Markdown 架构图，覆盖 Godot、后端、世界运行时、System L6 事件总线、角色智能体、ESM、Siming、模型服务、Harness 和非运行时支撑面。
- `docs/架构/感知输入对齐层.md`：双感知链并存时的统一时空 envelope 设计，定义 fact 链和 provider/PQF 链如何在输入阶段对齐。
- `docs/架构/事实上抛链路与多模态链路.md`：梳理事实上抛链路与 provider/PQF 多模态链路的职责分工，并说明两条链各自已经存在的融合层。
- `docs/架构/VLA与多模态链.md`：VLA 在多模态主链中的位置、对角色与 Siming 的应用、当前缺陷和模型接入建议。
- `docs/架构/运行时/运行时总览.md`：整体架构、整体运行时时序和整体数据流总入口。
- `docs/架构/运行时/运行时覆盖矩阵.md`：当前运行时覆盖矩阵，包含领域、契约、代码负责人和 harness 证据。
- `docs/架构/运行时/模块/世界运行时.md`：`backend/app/world_runtime/` 大类文档，覆盖 L1、PQF、VLA、模型 readiness、调度和 continuity。
- `docs/架构/运行时/图表/整体运行时时序图.md`：可渲染 Mermaid 时序图，覆盖对话、交互、Siming、角色投递和 provider 流程。
- `docs/架构/运行时/图表/整体运行时数据流图.md`：可渲染 Mermaid 数据流图，覆盖 L1/PQF、交互结果合并、角色智能体投递、Siming 投影、VLA 运行时和模型服务边界。
- `docs/架构/运行时/模块/SystemL1.md`：System L1 模块文档，覆盖事实、provider、PQF 和结算边界。
- `docs/架构/运行时/模块/SystemL6事件总线.md`：System L6 模块文档，覆盖 authority event bus、路由、投影、回放和审计辅助边界。
- `docs/架构/运行时/模块/角色智能体.md`：角色智能体模块文档，覆盖 L1/L2/L3/L4、记忆、投递、needs/affect runtime 分层，以及 `L1RuntimePerceptionBridge` / `System L6` / `ESM` 的边界。
- `docs/架构/运行时/模块/ESM与交互编排.md`：ESM、交互编排和物理通道模块文档。
- `docs/架构/运行时/模块/Godot表现与角色入口.md`：Godot 表现、输入、provider 和角色入口模块文档。
- `docs/架构/运行时/模块/VLA运行时通道.md`：已实现的 VLA 视觉/空间运行时慢路径和无直接 authority 写权限边界。
- `docs/架构/运行时/模块/模型服务通道.md`：模型 provider readiness、adapter 和真实调用证明边界。
- `docs/架构/运行时/模块/Harness验证证据.md`：Harness profile 与证据产物模块文档。
- `docs/demo-script.md`：预期 demo 节拍和可观察证明路径。

## 活跃设计与计划

- `docs/superpowers/specs/world-character-siming-authority-mainline/README.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-world-character-siming-authority-mainline-master-design.md`
- `docs/superpowers/plans/world-character-siming-authority-mainline/README.md`
- `docs/superpowers/specs/2026-06-29-complete-character-mind-core-design.md`
- `docs/superpowers/plans/2026-06-29-mind-core-foundation-implementation-plan.md`
- `docs/superpowers/plans/2026-06-29-full-l1-and-memory-implementation-plan.md`
- `docs/superpowers/plans/2026-06-29-full-l2-and-l3-implementation-plan.md`
- `docs/superpowers/plans/2026-06-29-execution-preservation-and-readiness-implementation-plan.md`
- `docs/superpowers/plans/2026-06-29-mind-core-closure-implementation-plan.md`
- `docs/superpowers/specs/2026-06-21-character-director-observatory-design.md`
- `docs/superpowers/plans/2026-06-21-character-director-observatory-implementation-plan.md`
- `docs/superpowers/plans/2026-06-22-character-director-observatory-finalization-implementation-plan.md`
- `docs/superpowers/specs/2026-06-19-deepseek-character-model-gateway-design.md`
- `docs/superpowers/plans/2026-06-19-deepseek-character-model-gateway-implementation-plan.md`
- `docs/superpowers/plans/2026-06-19-character-actor-stage2-closeout-implementation-plan.md`
- `docs/superpowers/specs/2026-06-15-character-actor-architecture-optimization-design.md`
- `docs/superpowers/plans/2026-06-15-character-actor-architecture-optimization-implementation-plan.md`
- `docs/superpowers/plans/2026-06-15-character-actor-near-term-cleanup-implementation-plan.md`
- `docs/superpowers/plans/2026-06-15-character-actor-final-convergence-implementation-plan.md`
- `docs/superpowers/specs/2026-06-15-full-character-agent-runtime-with-llm-design.md`
- `docs/superpowers/plans/2026-06-15-full-character-agent-runtime-with-llm-implementation-plan.md`
- `docs/superpowers/specs/2026-06-12-character-actor-unification-design.md`
- `docs/superpowers/specs/2026-06-12-character-actor-runtime-boundary-design.md`
- `docs/superpowers/specs/2026-06-12-character-actor-control-and-locomotion-design.md`
- `docs/superpowers/plans/2026-06-12-character-actor-unification-implementation-plan.md`
- `docs/superpowers/plans/2026-06-12-character-actor-runtime-boundary-implementation-plan.md`
- `docs/superpowers/plans/2026-06-12-character-actor-control-and-locomotion-implementation-plan.md`
- `docs/superpowers/specs/2026-06-11-character-agent-minimal-runtime-slice-design.md`
- `docs/superpowers/plans/2026-06-11-character-agent-minimal-runtime-slice-implementation-plan.md`
- `docs/superpowers/specs/2026-06-03-harness-engineering-design.md`
- `docs/superpowers/plans/2026-06-03-harness-engineering-implementation-plan.md`
- `docs/superpowers/specs/2026-06-10-ai-engineering-workflow-integration-design.md`
- `docs/superpowers/plans/2026-06-10-ai-engineering-workflow-integration-implementation-plan.md`
- `docs/superpowers/plans/2026-06-10-siming-event-bus-final-merge-retrospective.md`
- `docs/superpowers/specs/2026-06-02-phase05-runtime-alignment-design.md`
- `docs/superpowers/plans/2026-06-02-phase05-runtime-alignment-implementation-plan.md`

## 运行时区域

- `backend/`：FastAPI authority 后端、Pydantic 模型、服务和 pytest 覆盖。
- `docs/架构/`：仓库级和运行时级架构文档。
- `docs/架构/运行时/`：运行时总纲、覆盖矩阵、图表和模块文档。
- `docs/character/`：角色架构、控制链、资产集成和后续 action asset interface 文档。
- `scripts/autoload/`：Godot 后端桥接和本地表现总线。
- `scripts/phase0/`：Phase 0 demo 编排。
- `scripts/player/`：玩家意图和具身路径。
- `scripts/visual/`：视觉事实发射路径。
- `scripts/verification/`：本地验证和 harness 脚本。
- `scenes/phase0/`：Phase 0 Godot 场景。
- `.harness/profiles/`：版本化 harness profile manifest。
- `.harness/rules/`：版本化规则到证据 manifest。
- `.harness/references/`：适配后的外部 Harness Engineering 参考分类。
- `.harness/templates/`：后续正式模块 profile 的起始模板。
- `.harness/ci/`：发布门禁元数据。
- `.harness/features.json`：带证据的 harness feature ledger。
- `.harness/retention-policy.json`：生成的证据保留和差异策略。
- `.github/workflows/harness.yml`：完整 harness 执行的 CI 入口。

## 验证配置

使用 `python scripts/verification/harness.py --profile <name>`。

- `docs`：文档新鲜度和索引检查。
- `boundaries`：静态 Harness Engineering 边界检查。
- `drift`：清理状态和本地产物漂移检查。
- `backend-contract`：后端协议模型和 WebSocket 契约检查。
- `godot-project`：Godot 主场景、autoload 和 `res://` 静态完整性检查。
- `release-gate`：CI 工作流和发布门禁元数据检查。
- `harness-lifecycle`：生命周期台账、本地 CI、保留策略、模板、质量和交接检查。
- `change-lifecycle`：OpenSpec、Superpowers、Harness、Goal 和原生子智能体工作流检查。
- `harness-reference`：适配外部 Harness Engineering 分类、模板和参考覆盖检查。
- `phase0`：严格 Phase 0 后端加 Godot 运行时验证。
- `phase1-slice`：当前 Phase1 形态运行时切片验证。
- `l1-world-fact-runtime`：System L1 world fact subsystem 的兼容运行时验证 profile。名称是历史遗留；它证明面向运行时的 L1 服务和集成，不代表产品级 L1 运行时。
- `mainline-unified-runtime`：仓库主线聚合证明，覆盖 world runtime、actor-local perception、autonomous social contact、execution ingress、settlement writeback、asset-runtime/Kimodo contracts 和 scheduling/continuity evidence。
- `model-provider-readiness`：character text、Siming candidate、VLA spatial 和非运行时 production model 入口的脱敏 model provider readiness 台账。
- `godot-sampling-production-grade-providers`：Godot 运行时与后端证明，证明 visual、spatial、auditory、embodied、skeletal 和 environment provider refs 进入 PQF。
- `embodied-skeletal-debug-replay`：Godot 运行时与后端证明，证明 `CharacterReplica` / `Skeleton3D` binding、high/mid-level skeletal refs 和 debug-only full bone replay artifacts。
- `vla-provider-backend`：后端证明，覆盖无直接 authority 写权限的 VLA provider request/result contracts、model registry、scheduler、cache isolation、percept bridge、运行时消费和 real-provider readiness status。
- `actor-scene-knowledge-lifecycle`：后端证明，覆盖 actor-private ASK store isolation、revision/conflict/freshness/expiry lifecycle，以及 active perception 回到 PQF/provider refs。
- `siming-global-situation-layer`：后端证明，覆盖 Siming global situation snapshots，来源为 public L1/world/authority/evidence/参考性 refs，并保持 `siming_mm:*` context isolation。
- `interaction-orchestration-service`：后端证明，覆盖 structured interaction policies、semantic ESM path、physical seam、degrade paths 和 unified result merge。
- `esm-physical-channel-world-actuation`：后端与 Godot 运行时证明，覆盖 physical effect refs、contact/body/object/environment observations、constraint gating 和 orchestration merge。
- `non-runtime-production-pipeline`：离线生产证明，覆盖 scene semantic extraction、spatial baking、multimodal classification readiness、review gating 和 approved replay dataset artifacts。
- `perception-input-alignment`：后端证明，覆盖感知 identity 行为矩阵，包括同拍/跨拍、同物/异物、多 actor 私有视角、VLA late advisory 和 Siming 汇总 identity。
- `all`：按顺序运行全部 profile。

运行时验证脚本和聚合证明脚本：

- `python scripts/verification/verify_actor_local_perception.py`
- `python scripts/verification/verify_autonomous_social_contact.py`
- `python scripts/verification/verify_character_agent_execution.py`
- `python scripts/verification/verify_l1_world_fact_runtime.py`
- `python scripts/verification/verify_mainline_unified_runtime.py`
- `python scripts/verification/verify_model_provider_readiness.py`
- `python scripts/verification/verify_godot_sampling_production_grade_providers.py`
- `python scripts/verification/verify_embodied_skeletal_debug_replay_pipeline.py`
- `python scripts/verification/verify_vla_provider_backend.py`
- `python scripts/verification/verify_perception_input_alignment.py`
- `python scripts/verification/verify_actor_scene_knowledge_runtime.py`
- `python scripts/verification/verify_siming_global_situation_runtime.py`
- `python scripts/verification/verify_interaction_orchestration_runtime_service.py`
- `python scripts/verification/verify_esm_physical_channel_runtime.py`
- `python scripts/verification/verify_non_runtime_production_pipeline.py`
- `python scripts/verification/verify_character_director_observatory.py`
- `python scripts/verification/verify_phase1_slice.py`
- `python scripts/verification/verify_phase0.py`

角色 needs / affect / drift 聚焦验证：

- `pytest backend/tests/test_character_profile_needs_schema.py -v`
- `pytest backend/tests/test_need_tension_engine.py -v`
- `pytest backend/tests/test_affect_engine.py -v`
- `pytest backend/tests/test_character_runtime_needs_affect_flow.py -v`
- `pytest backend/tests/test_personality_drift_gate.py -v`

报告写入 `.harness/verification/`。

主线聚合证明报告：

- `.harness/verification/mainline-unified-runtime-report.json`
- `.harness/verification/mainline-unified-runtime-report.md`

Harness profile 和规则 manifest 是项目输入：

- `.harness/profiles/`：profile 顺序、脚本分发和 Godot requirements。
- `.harness/rules/`：docs、boundaries 和 drift 检查的机械不变量 manifest。
- `.harness/references/`：映射到当前项目 artifacts 的 reference taxonomies。

Run-id 证据归档写入 `.harness/verification/runs/`。
Latest run manifest、baseline 和 diff artifacts 写入 `.harness/verification/`。

## Harness Lifecycle 文档

- `docs/harness-architecture.md`
- `docs/ai-engineering-workflow.md`
- `docs/harness-reliability.md`
- `.harness/clean-state-checklist.md`
- `.harness/session-handoff.md`
- `.harness/evaluator-rubric.md`
- `.harness/quality-document.md`
- `.harness/templates/PLAN.md`
- `.harness/templates/IMPLEMENT.md`
- `.harness/templates/HARNESS_CHECKLIST.md`
- `.harness/templates/AGENTS.md`

## 参考资料

- `docs/phase1/`
- `docs/reference/phase1-event-bus/`
- `docs/reference/phase1-character-agent/`
- `docs/reference/phase1-siming/`

## 角色文档

- `docs/character/character-actor-architecture.md`
- `docs/character/character-mind-core-status.md`
- `docs/character/character-agent-runtime-architecture.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/README.md`
- `docs/character/character-control-chain.md`
- `docs/character/character-asset-integration.md`
- `docs/character/character-action-asset-interface.md`
- `docs/character/character-actor-migration-status.md`
- `docs/character/character-actor-final-convergence-target.md`
- `docs/character/character-actor-final-convergence-gap-report.md`
- `docs/character/character-debug-and-verification.md`

Reference docs 只是支持上下文。当前任务真相仍以 `AGENTS.md` 和活跃 specs/plans 为准。
