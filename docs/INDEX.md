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
- `docs/架构/整体架构.md`：仓库级整体架构总纲，内含手绘式 Markdown 架构图，覆盖 Godot、后端、世界运行时、Gameplay Foundation、System L6 事件总线、角色智能体、ESM、Siming、模型服务、Harness 和非运行时支撑面。
- `docs/架构/感知输入对齐层.md`：双感知链并存时的统一时空 envelope 设计，定义 fact 链和 provider/PQF 链如何在输入阶段对齐。
- `docs/架构/事实上抛链路与多模态链路.md`：梳理事实上抛链路与 provider/PQF 多模态链路的职责分工，并说明两条链各自已经存在的融合层。
- `docs/架构/VLA与多模态链.md`：VLA 在多模态主链中的位置、对角色与 Siming 的应用、当前缺陷和模型接入建议。
- `docs/架构/运行时/运行时总览.md`：整体架构、整体运行时时序和整体数据流总入口。
- `docs/架构/运行时/运行时覆盖矩阵.md`：当前运行时覆盖矩阵，包含领域、契约、代码负责人和 harness 证据。
- `docs/架构/运行时/模块/GameplayFoundation与领域结算.md`：`backend/app/gameplay/` 的事件溯源、领域 authority、状态组合、镜像与受限参考闭环边界；明确它与 ESM、System L6、角色智能体和 Godot 的分工。
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
- `docs/8月分析/README.md`：基于当前实现、正式 spec/plan 与 Harness 证据的增量设计指导；其中第二阶段推进目录定义已有角色的多智能体协作边界。
- `docs/8月分析/第二阶段推进/README.md`：`bakery-authored-agents` 的增量指导入口；正式 SDD/plan 见下方 Phase Two tree。
- `docs/art-resource-swap-workflow.md`：美术资源替换与更新工作流手册，定义 art pack、adapter scene、runtime shell 和 binding profile 的接入方式。
- `docs/demo-script.md`：预期 demo 节拍和可观察证明路径。
- `docs/production-readiness.md`：生产级在线 provider、图谱连续性、Authority 与 Godot 发布门禁。

## 活跃设计与计划

- `docs/superpowers/specs/world-character-siming-authority-mainline/README.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-world-character-siming-authority-mainline-master-design.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/README.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-31-coupled-event-store-and-authority-bus-design.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-08-03-websocket-session-identity-and-mirror-scope-design.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/README.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/2026-08-09-p2a-actor-to-gameplay-participation-design.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/2026-08-09-p2b-organization-work-lifecycle-design.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/2026-08-09-p2c-payroll-and-operating-window-design.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/2026-08-09-p2d-authored-agents-bakery-vertical-slice-design.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/embodied-interaction-product-foundation/README.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/embodied-interaction-product-foundation/2026-08-01-atomic-action-library-and-default-scene-coverage-design.md`
- `docs/superpowers/plans/world-character-siming-authority-mainline/README.md`
- `docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-31-coupled-event-store-and-authority-bus-plan.md`
- `docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/2026-08-02-stateful-patch-data-migration-plan.md`
- `docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/2026-08-03-websocket-session-identity-and-mirror-scope-plan.md`
- `docs/superpowers/plans/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/README.md`
- `docs/superpowers/plans/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/2026-08-09-p2a-actor-to-gameplay-participation-implementation-plan.md`
- `docs/superpowers/plans/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/2026-08-09-p2b-organization-work-lifecycle-implementation-plan.md`
- `docs/superpowers/plans/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/2026-08-09-p2c-payroll-and-operating-window-implementation-plan.md`
- `docs/superpowers/plans/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/2026-08-09-p2d-authored-agents-bakery-vertical-slice-implementation-plan.md`
- `docs/superpowers/plans/world-character-siming-authority-mainline/embodied-interaction-product-foundation/2026-08-01-atomic-action-library-and-default-scene-coverage-plan.md`
- `docs/superpowers/plans/world-character-siming-authority-mainline/embodied-interaction-product-foundation/2026-08-04-obj-archive-door-physical-embodiment-vertical-slice-plan.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/2026-07-29-character-dialogue-streaming-design.md`
- `docs/superpowers/plans/world-character-siming-authority-mainline/2026-07-29-character-dialogue-streaming-implementation-plan.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/2026-07-29-real-tts-provider-presentation-design.md`
- `docs/superpowers/plans/world-character-siming-authority-mainline/2026-07-29-real-tts-provider-presentation-implementation-plan.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/2026-07-31-tts-voice-profile-adapter-design.md`
- `docs/superpowers/plans/world-character-siming-authority-mainline/2026-07-31-tts-voice-profile-adapter-implementation-plan.md`
- `docs/superpowers/plans/world-character-siming-authority-mainline/2026-08-03-tts-voice-profile-adapter-closure-implementation-plan.md`
- `scripts/verification/verify_tts_voice_profile_adapter.py` (presentation-only voice-profile/catalog verification)
- `docs/superpowers/specs/2026-06-29-complete-character-mind-core-design.md`
- `docs/superpowers/specs/2026-07-08-character-needs-personality-affect-runtime-design.md`
- `docs/superpowers/plans/2026-07-08-character-needs-personality-affect-runtime-implementation-plan.md`
- `docs/superpowers/specs/2026-07-10-character-skill-system-master-design.md`
- `docs/superpowers/specs/2026-07-11-layered-character-mind-factor-architecture-design.md`
- `docs/superpowers/plans/2026-07-11-layered-character-mind-factor-architecture-implementation-plan.md`
- `docs/superpowers/plans/2026-06-29-mind-core-foundation-implementation-plan.md`
- `docs/superpowers/plans/2026-06-29-full-l1-and-memory-implementation-plan.md`
- `docs/superpowers/plans/2026-06-29-full-l2-and-l3-implementation-plan.md`
- `docs/superpowers/plans/2026-06-29-execution-preservation-and-readiness-implementation-plan.md`
- `docs/superpowers/plans/2026-06-29-mind-core-closure-implementation-plan.md`
- `docs/superpowers/specs/2026-06-21-character-director-observatory-design.md`
- `docs/superpowers/plans/2026-06-21-character-director-observatory-implementation-plan.md`
- `docs/superpowers/plans/2026-06-22-character-director-observatory-finalization-implementation-plan.md`
- `docs/superpowers/specs/2026-07-23-complete-llm-integration-closure-design.md`
- `docs/superpowers/plans/2026-07-23-complete-llm-integration-closure-implementation-plan.md`
- `docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-29-vla-real-provider-adapter-live-proof-design.md`
- `docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-29-vla-real-provider-adapter-live-proof-implementation-plan.md`
- `docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-30-advisory-vla-routing-and-tts-convergence-design.md`
- `docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-30-advisory-vla-routing-and-tts-convergence-implementation-plan.md`
- `docs/superpowers/specs/current-project-intelligence-upgrade/2026-08-03-current-project-siming-durable-heavenly-graph-phase2-7-integration-design.md`
- `docs/superpowers/plans/current-project-intelligence-upgrade/2026-08-03-current-project-siming-durable-heavenly-graph-program-plan.md`
- `docs/superpowers/plans/current-project-intelligence-upgrade/2026-08-03-phase3-actor-five-pool-graph-memory-implementation-plan.md`
- `docs/superpowers/plans/current-project-intelligence-upgrade/2026-08-03-phase5-resource-capability-staging-implementation-plan.md`
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
- `docs/7月分析/`：历史分析与修复方案工作区（分析性质，不作为实现事实声明）。
- `docs/art-resource-swap-workflow.md`：场景、角色、道具和环境状态资源的可替换化工作流与接入手册。
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

The `siming-heavenly-runtime` profile is the Godot-required live acceptance
profile for the durable Siming heavenly graph. Run its secret-safe preflight
before invoking the harness profile; live acceptance never downgrades to a
fake or disabled provider.

使用 `python scripts/verification/harness.py --profile <name>`。

- `heavenly-graph-semantic-foundation`：graph-only backend profile，使用 verifier-owned temporary SQLite，证明语义 metadata、adapter parity、scope denial、bounded results、stale-write rejection、correction chain、branch isolation 和 checkpoint replay digest；不采纳 role、Siming runtime、LLM 或 Godot 证据。

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
- `character-model-live`：explicit-only Character 大模型 live proof，分别证明 dialogue、L2 reasoning 和 L3 planning 真实 provider 路径，且不能使用 fallback。
- `llm-integration-closure`：explicit-only 聚合证明，要求 readiness、Character 三项 live proof 和 Siming DeepSeek live proof 共享同一个 `LLM_CLOSURE_RUN_ID`；readiness 不会被升级为 live proof。
- `godot-sampling-production-grade-providers`：Godot 运行时与后端证明，证明 visual、spatial、auditory、embodied、skeletal 和 environment provider refs 进入 PQF。
- `embodied-skeletal-debug-replay`：Godot 运行时与后端证明，证明 `CharacterReplica` / `Skeleton3D` binding、high/mid-level skeletal refs 和 debug-only full bone replay artifacts。
- `vla-provider-backend`：后端证明，覆盖无直接 authority 写权限的 VLA provider request/result contracts、model registry、scheduler、cache isolation、percept bridge、运行时消费和 real-provider readiness status。
- `actor-scene-knowledge-lifecycle`：后端证明，覆盖 actor-private ASK store isolation、revision/conflict/freshness/expiry lifecycle，以及 active perception 回到 PQF/provider refs。
- `siming-global-situation-layer`：后端证明，覆盖 Siming global situation snapshots，来源为 public L1/world/authority/evidence/参考性 refs，并保持 `siming_mm:*` context isolation。
- `siming-story-runtime`：后端图谱证明，覆盖 authored possibility 与 branch runtime story node 分离、Authority-confirmed 的终局玩家关闭、O2 到 O6 的义务转换、以及新因果基础的替代吸引子路径；不宣称它已绕过 `SimingRuntime.tick(...)` 发布决策。
- `siming-adaptive-bridge`：后端确定性证明，覆盖 typed proposal 对既有事实、`char_b` 五池观察、开放 O6 和资源包的约束；拒绝终局路径复活，不写角色私有记忆，只提交 latent runtime node；不宣称已完成在线 LLM 调用。
- `behavior-turn-runtime`：后端角色纵切证明，覆盖共享 typed behavior turn（行为回合）的八阶段链、accepted/rejected Authority 结果投影、actor-private scope 隔离和幂等 replay；不宣称角色重启连续性、司命接入、六域 Authority 投影、在线 LLM 或 Godot 已完成。
- `character-continuity-recovery`：后端角色连续性证明，覆盖 graph-backed dynamic state、need/tension、goal、supervision/continuity、working memory 与 session next-input 在旧 session 文件丢失后的重建；不宣称司命、六域 Authority、在线 LLM 或 Godot 已完成。
- `authority-graph-projection`：后端 Authority 投影证明，覆盖 ESM/world、Inventory、Ownership、Economy、Survival/body、资源/场景六类 committed event 到 Heavenly Graph 的 owner/source vector/settlement/replay 投影；不宣称在线 LLM 或 Godot 已完成。
- `siming-behavior-turn-runtime`：后端司命行为回合证明，覆盖 `SimingRuntime.tick(...)` 在唯一决策路径记录共享八阶段链；不宣称在线 LLM 或 Godot 已完成。
- `interaction-orchestration-service`：后端证明，覆盖 structured interaction policies、semantic ESM path、physical seam、degrade paths 和 unified result merge。
- `esm-physical-channel-world-actuation`：后端与 Godot 运行时证明，覆盖 physical effect refs、contact/body/object/environment observations、constraint gating 和 orchestration merge。
- `non-runtime-production-pipeline`：离线生产证明，覆盖 scene semantic extraction、spatial baking、multimodal classification readiness、review gating 和 approved replay dataset artifacts。
- `perception-input-alignment`：后端证明，覆盖感知 identity 行为矩阵，包括同拍/跨拍、同物/异物、多 actor 私有视角、VLA late advisory 和 Siming 汇总 identity。
- `embodied-interaction-contracts`：后端 Phase 0 契约证明，覆盖 embodied request/outcome schema、writer 选择、route 二选一、attestation 字段、evidence sequence 和字段级 projection 过滤；不声明 Godot runtime 完成。
- `embodied-affordance-registry`：后端与 Godot runtime 证明，覆盖 `chair_01` catalog-backed binding、revision pinning、occupancy freshness、filtered views 和 VLA conflict；也覆盖默认主场景 Godot-runtime-verified `obj_letter` 与 `obj_plaque` 的 reviewed `inspect/read` binding、`obj_lamp_switch` 的 `press` binding 与 `switch: idle -> activated` settlement、`obj_archive_door` 的 stateful `open_close` binding 与 `door: closed -> open -> closed` settlement、`obj_worktable` 的 single-actor `use` / `finish_use` binding 与 `work_surface: ready -> engaged -> ready` settlement、`obj_observation_bench` 的 actor-scoped `sit` / `stand` binding、owner-only release 与 `posture: standing -> seated -> standing` result，以及 `obj_archive_token` 的 backend-resolved custody-only `grab` 和受限 `stow_intent` 表现消费；该 stow 路径只在后端 policy 解析后以原子事件提交 location，并由 Godot 接受 `authority_only` 指令后标记本地 `carried -> stowed`。它不宣称 scene container/retrieve、inventory UI、ownership、hand animation 或泛化存取已完成。
- `embodied-bridge-attestation`：后端与 Godot runtime 证明，覆盖 `trusted_local_launch`、controller binding、connection epoch、grant、nonce/sequence/revocation/idempotency、route gate 和 dedicated bridge routes。
- `embodied-action-controller`：Godot runtime 证明，覆盖 `EmbodiedActionController` state machine、grant-gated route、terminal observations、failure recovery，以及 raw bone/physics transport 排除。
- `embodied-authority-settlement`：后端证明，覆盖 attested local outcome validation、revision/policy checks、idempotent consume、`esm_compatibility_adapter` 单对象结算，以及 gameplay writer fail-closed。
- `embodied-interaction-replay`：后端与 Godot runtime 证明，覆盖 `kick-chair` visible settlement、后台 `server_ledger_sequence` replay、source sequence idempotency/gap 拒绝，以及 public Observatory projection 过滤。
- `gameplay-foundation-contract`：后端证明，覆盖 Gameplay authority event store、atomic `append_batch`、idempotency、expected stream revisions、typed failure 和 committed outbox 原子写入。
- `gameplay-state-groups`：后端证明，覆盖 `StateGroupRegistry` 的依赖/冲突校验、版本化 eligibility catalog 到 explicit-context authority lifecycle batch、lifecycle event 只读投影、仅 enabled groups 的 `CharacterGameRuntimeState` 组合快照、policy-filtered authority/Godot/mind/debug views，以及 checksummed full snapshot / exact-base delta reconstruction；不声明 policy catalog activation loading、persistent replay rebuild、consumer capability negotiation、transport delivery、client prediction 或 Godot mirror delivery 已完成。
- `gameplay-resource-body`：后端证明，覆盖既有 skill path 的只读 gate、事件重建的整数资源、reservation 和伤势派生身体功能、skill/右臂功能/耐力不足时的零事件拒绝、恢复后重试，以及资源消耗与动作结算的原子 batch；不声明 reservation timeout、status tag、effective stats、skill-state write/grant、传输或 Godot mirror 已完成。
- `gameplay-effective-stats`：后端证明，覆盖 Decimal baseline 和 modifier 的确定性解析、条件拒绝、stacking policy、冲突 fail-closed、explanation digest，以及 registered equipment modifier source 的 event-derived activation/deactivation replay；不声明 generic environment source lifecycle、状态组投影、传输或 Godot mirror 已完成。
- `gameplay-status-tags`：后端证明，覆盖 status tag registry、显式 apply/remove/expire event、stack-count 上限、exclusivity 拒绝、backend principal / receipt replay 保护、active declarative modifier source 移除与确定性 replay；不声明 refresh/duration/dispel、传输或 Godot mirror 已完成。
- `gameplay-ability-affordance`：后端证明，覆盖 event-derived learned skill truth、版本化 definition/path、与身体和资源投影组合的只读当前 affordance；不声明 promotion、装备/库存/环境/权限 predicates、持久化、传输或 Godot mirror 已完成。
- `gameplay-inventory`：后端证明，覆盖物品定义、容器创建、event-derived 单一位置、sealed/capacity 拒绝、原子移动与平坦携带容器的负重读投影；不声明嵌套、递归负重、ownership、equipment、传输或 Godot mirror 已完成。
- `gameplay-possession-equipment`：后端证明，覆盖一个物品从已验证 inventory placement 到兼容且可用的 equipment slot、以及卸装返回合法容器时，inventory placement、equipment activation/deactivation、activation-scoped ability path grant 和 registered modifier source 的单一原子 batch；也覆盖一个 activation 的多槽占用和次要槽冲突零提交，以及旧 activation 撤销、旧物回收与新物多槽激活的原子 swap；grant 与 modifier 都只进入各自 projection，不创建 learned skill truth；不声明 generic modifier source、container access/propagation、ownership/control、Godot presentation 或 replay/checkpoint 已完成。
- `gameplay-ownership-authority`：后端证明，覆盖 exclusive full-title right 的 event-derived 初始授予、独立 transfer、holder 拒绝和 idempotent replay，以及 credential link 的 issue/revoke/supersede；issue/supersede 会验证声明 holder 当前 inventory 中的 item、pin revision，并把 holder/revision 作为不可变签发留痕；credential 仍只保留 right reference，不能改变 holder，签发留痕也不是当前 custody/title 真相；read-only presentation 需同时满足当前 item presence 与 right-holder identity；不声明 custody write、account/ledger、offer、debt、contract、privacy、checkpoint 或 Godot delivery 已完成。
- `gameplay-economy-authority`：后端证明，覆盖 event-derived account balance、同币种原子 debit/credit transfer、固定报价购买、零对价 gift，以及 simple-debt 的本金交付、部分/完全偿付、policy cancellation、claim/contract lifecycle 和 transaction record 单一原子 batch；单笔 payment record 可由 policy authority 通过追加式、幂等的反向资金结算与 outstanding 恢复进行一次纠正。若原付款已使 debt/contract 完全结清，纠正会在同一批中明确重开 satisfied claim 与 fulfilled simple-debt contract；取消后的债务只能经独立 policy cancellation reversal 依据原 cancellation record 固定的 outstanding 重开，且不产生账户变动；registered `simple_service` term 的 completion evidence kind 与提交证据匹配时，可在同一批中记录证据并 fulfill contract，但不结算其他 domain；backend query 仅允许 account owner、debt party 或 configured authority principal 读取对应投影，第三方 fail closed，并可按配置的 audience allowlist 输出字段裁剪 payload；不声明 credential settlement、任意或跨域 contract terms execution、transport authorization、persistence、checkpoint 或 Godot delivery 已完成。
- `godot-gameplay-mirror`：后端与真实本地 Godot 证明，覆盖 policy-filtered envelope、backend-configured Phase3 committed-event source、backend-granted session/actor subscription scope、`/ws` trusted-local bind/subscribe snapshot、fresh enrollment reconnect/narrowed scope、gap/resync、bounded queue/backpressure recovery、authority-issued prediction confirmation/rejection rollback，以及 presentation-only consumer 的断连清理；不声明 production identity、production command routing、persistence 或 migration 已完成。
- `adventure-basic`：受治理参考玩法包，覆盖严格 schema/content digest 校验，以及 Scenario 1 购买/装备、Scenario 2 身体/资源约束、Scenario 3 equipment-gated 储物戒、Scenario 4 physical deed 与 land-title 分离和 Scenario 5 gift/debt/typed-contract 生命周期。五个场景各自要求 authoritative facade 的 revision/result metadata、online/full/checkpoint-tail canonical replay hash、过滤后的 backend mirror source，以及 canonical authority commit 后到 fresh trusted-local Godot mirror 的真实交付；不声明 Patch activation、client authority、production identity、通用 transport durability、persistence 或 migration 已完成。
- `gameplay-foundation-all`：按 Gameplay Foundation 依赖顺序运行 contracts、replay、event spine、state/resource/status/ability/inventory/equipment/ownership/economy、Patch、Godot mirror 和 adventure-basic。每个子 profile 必须自身退出成功且报告为绿；聚合不把子 profile 的明确非目标提升为完成声明。
- `gameplay-event-replay`：后端证明，覆盖 Gameplay full replay、checkpoint-plus-tail 等价、deterministic projection hash、stream gap、opt-in schema registry snapshot recovery、已注册连续单步 trusted upcaster 的历史事件 replay，以及 checkpoint 持久化、按 projector/schema/patch/registry/world-config 兼容性与 event-prefix/revision-vector 选择最新 cache、无效 cache 回退 full replay、单 store startup 期间 write gate；同时覆盖首个有界资源 Patch 迁移在 full 与 checkpoint-plus-tail 重放中形成相同的 versioned `CharacterGameRuntimeState` façade；不声明通用 patch migration、可持久化 executable upcaster manifest、全局 multi-projector readiness 或 production startup control plane 已完成。
- `gameplay-foundation-event-spine`：后端聚合证明，覆盖 store-first/bus-second settlement spine、committed outbox after-commit dispatcher、bus retry 和 store-backed gap resync。
- `gameplay-patch-runtime`：后端证明，覆盖受信任 immutable manifest 的 digest、依赖/cycle/schema 冲突 gate、显式 active set、candidate/active-set JSON snapshot recovery 的篡改拒绝、deterministic proposal-only Rule IR、无 I/O capability 的 manifest/call-site/effect 授权和预算/handler failure 的 pre-settlement 拒绝、authority-ledger 的 candidate install / complete-active-set enable/disable、显式可信 actor context 的 patch-owned state-group enable/disable 与 active-set cutover 同一原子 batch（disable 仅允许当前 source revision、唯一所有权并只改变 lifecycle state）、同 patch compatible identity-rebind revision 的 upgrade/rollback 与 fail-closed lifecycle replay、唯一允许的 `resource.consume` proposal 到资源扣减/`gameplay.patch.rule_settled` 原子 batch 映射，以及首个受限 `core.resources` maximum-reduction data-transform upgrade：typed domain fact、state-group definition/source transition 与 Patch cutover 同批原子提交，reserved/stale/digest/schema 异常 fail closed，且有损策略 rollback 明确拒绝；不声明 database-backed registry/handler artifact、完整 Rule IR、其他 effect 的通用 settlement、state-group domain-effect revocation、grant/modifier lifecycle、其他 data-transform、跨版本 reader/rollback compatibility、privacy view 或 Godot delivery 已完成。
- `embodied-interaction-session`：后端与 Godot runtime Phase 6 证明，覆盖 `InteractionSession` handshake lifecycle、Gameplay `append_batch`/outbox/bus 路径、WebSocket `embodied_interaction_session_event` 投影、Godot `BackendBridge` live backend 接收、refusal/departure/third-party interruption、双参与者 terminal observation、同一 evidence ledger、privacy-filtered projection，以及 Godot local slot consumer 的 slot/reservation/terminal observation 处理。
- `embodied-handoff-authority`：后端与 Godot runtime Phase 7 窄 handoff 证明，覆盖一个 Gameplay atomic batch 中同时提交 session terminal observations、`inventory.custody_changed`、`ownership.right_transferred`、`embodied.handoff.settled` 和 session commit，WebSocket `embodied_handoff_event` 投影，以及 Godot `BackendBridge` live backend 接收后由 `HandoffMirrorConsumer` 只做 authority-only presentation attachment。
- `embodied-grab-carry-place-authority`：后端与 Godot runtime Phase 7 grab-carry-place 证明，覆盖一个 Gameplay atomic batch 中同时提交 session terminal observations、`inventory.custody_changed`、`embodied.carry.started`、`scene.occupancy.changed`、`embodied.place.settled` 和 session commit，WebSocket `embodied_carry_place_event` 投影，以及 Godot `BackendBridge` live backend 接收后由 `CarryPlaceMirrorConsumer` 只做 authority-only presentation placement；同一 profile 还覆盖默认场景受限 `stow_intent`，以及一个 policy-resolved `obj_archive_storage_chest` `retrieve_intent`：服务端决定 asset/definition/backpack/hand receiver，分别以原子 custody/inventory/occupancy evidence 结算，Godot 只消费 authority-only marker。它不证明通用场景容器、inventory UI、ownership 或泛化存取已完成。
- `embodied-interaction-foundation-all`：按 Phase 0-7 依赖顺序聚合 `embodied-interaction-*` focused profiles；Phase 6 session 在 `gameplay-foundation-event-spine` gate 通过后运行，Phase 7 handoff 和 grab-carry-place 在 session profile 之后运行。
- `all`：按顺序运行全部 profile。

运行时验证脚本和聚合证明脚本：

- `python scripts/verification/verify_actor_local_perception.py`
- `python scripts/verification/verify_autonomous_social_contact.py`
- `python scripts/verification/verify_character_agent_execution.py`
- `python scripts/verification/verify_l1_world_fact_runtime.py`
- `python scripts/verification/verify_mainline_unified_runtime.py`
- `python scripts/verification/verify_model_provider_readiness.py`
- `python scripts/verification/verify_heavenly_graph_semantic_foundation.py`
- `python scripts/verification/verify_character_model_live.py`
- `python scripts/verification/verify_llm_integration_closure.py`
- `python scripts/verification/verify_godot_sampling_production_grade_providers.py`
- `python scripts/verification/verify_embodied_skeletal_debug_replay_pipeline.py`
- `python scripts/verification/verify_vla_provider_backend.py`
- `python scripts/verification/verify_vla_provider_live.py --allow-live-call --run-id <run-id>`
- `python scripts/verification/verify_vla_provider_live.py --allow-live-call --use-godot-runtime-capture --run-id <run-id>`
- `python scripts/verification/benchmark_vla_advisory_routes.py --allow-live-call --samples 3`（默认仅 `advisory-fast`；深度路线只在显式 `--route advisory-deep` 比较时运行）
- `python scripts/verification/benchmark_vla_advisory_routes.py --allow-live-call --annotation-sample-id throne-hall-walk-preview-001 --samples 3`
- `python scripts/verification/verify_vla_replay_annotations.py`
- `python scripts/verification/verify_vla_replay_second_scene_capture.py --godot-exe <Godot-console-exe>`
- `python scripts/verification/verify_tts_provider_live.py --allow-live-call --evidence-run-id <opaque-run-id> --actor-id <approved-actor-id>`
- `python scripts/verification/verify_tts_godot_playback.py --allow-live-call --evidence-run-id <same-opaque-run-id> --actor-id <approved-actor-id>`
- `python scripts/verification/verify_perception_input_alignment.py`
- `python scripts/verification/verify_actor_scene_knowledge_runtime.py`
- `python scripts/verification/verify_siming_global_situation_runtime.py`
- `python scripts/verification/verify_interaction_orchestration_runtime_service.py`
- `python scripts/verification/verify_esm_physical_channel_runtime.py`
- `python scripts/verification/verify_non_runtime_production_pipeline.py`
- `python scripts/verification/verify_character_director_observatory.py`
- `python scripts/verification/verify_embodied_interaction_contracts.py`
- `python scripts/verification/verify_embodied_affordance_registry.py`
- `python scripts/verification/verify_embodied_bridge_attestation.py`
- `python scripts/verification/verify_embodied_action_controller.py`
- `python scripts/verification/verify_embodied_authority_settlement.py`
- `python scripts/verification/verify_embodied_interaction_replay.py`
- `python scripts/verification/verify_gameplay_foundation_contract.py`
- `python scripts/verification/verify_gameplay_event_replay.py`
- `python scripts/verification/verify_gameplay_foundation_event_spine.py`
- `python scripts/verification/verify_gameplay_state_groups.py`
- `python scripts/verification/verify_gameplay_resource_body.py`
- `python scripts/verification/verify_gameplay_effective_stats.py`
- `python scripts/verification/verify_gameplay_status_tags.py`
- `python scripts/verification/verify_gameplay_ability_affordance.py`
- `python scripts/verification/verify_godot_gameplay_mirror.py`
- `python scripts/verification/verify_embodied_interaction_session.py`
- `python scripts/verification/verify_embodied_handoff_authority.py`
- `python scripts/verification/verify_embodied_grab_carry_place_authority.py`
- `python scripts/verification/verify_embodied_interaction_foundation_all.py`
- `python scripts/verification/verify_phase1_slice.py`
- `python scripts/verification/verify_phase0.py`

角色 needs / affect / drift 聚焦验证：

- `pytest backend/tests/test_character_profile_needs_schema.py -v`
- `pytest backend/tests/test_need_tension_engine.py -v`
- `pytest backend/tests/test_affect_engine.py -v`
- `pytest backend/tests/test_character_runtime_needs_affect_flow.py -v`
- `pytest backend/tests/test_personality_drift_gate.py -v`
- `pytest backend/tests/test_character_agent_l3_planning.py -v`

报告写入 `.harness/verification/`。

主线聚合证明报告：

- `.harness/verification/mainline-unified-runtime-report.json`
- `.harness/verification/mainline-unified-runtime-report.md`
- `.harness/verification/heavenly-graph-semantic-foundation-report.json`
- `.harness/verification/heavenly-graph-semantic-foundation-report.md`

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
- `docs/art-resource-swap-workflow.md`
- `docs/character/character-action-asset-interface.md`
- `docs/character/character-actor-migration-status.md`
- `docs/character/character-actor-final-convergence-target.md`
- `docs/character/character-actor-final-convergence-gap-report.md`
- `docs/character/character-debug-and-verification.md`

Reference docs 只是支持上下文。当前任务真相仍以 `AGENTS.md` 和活跃 specs/plans 为准。
