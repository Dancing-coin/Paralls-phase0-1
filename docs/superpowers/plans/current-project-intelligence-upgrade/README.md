# 当前项目智能体与世界交互增量专题计划树

- 状态：`incremental-plan-tree-implemented-and-profile-verified`
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

## 母规格执行门槛

母规格：

- [2026-06-29-current-project-intelligence-upgrade-master-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-intelligence-upgrade-master-design.md)

定义了本计划树的上位分层、非目标和上下文隔离规则。执行 2026-07-02 后续计划时必须先核对这些门槛：

1. `world-character-siming-authority-mainline` 仍是主线真相；本树只补 mainline 闭合后的增量能力。
2. `L1` / `Scene3DSpaceModel` / `SpatialOccupancyField` / `PerceptionQueryFrame` 是 VLA、ASK、司命态势和 Godot provider 的上游底座，不能被任一 2026-07-02 计划重定义为新 runtime。
3. Godot 只能作为具身表现宿主和取样前端；任何 Godot provider 计划都不得引入重推理、重体素化或 full-scene runtime rescan。
4. 角色与司命只能共享世界事实、公共接口和模型调度基础设施；不得共享多模态 runtime context、private patch session、inference history 或中间 cache。
5. 语义驱动和物理驱动必须通过 `Interaction Orchestration Layer` 与统一 result family 管理；不得形成两套平行 world result。
6. 非运行时生产链只能产出 reviewable artifact / seed / dataset；不得在 runtime 直接写 world truth 或读取角色/司命私有上下文。

## 2026-07-02 计划依赖顺序

为满足母规格分层，2026-07-02 计划推荐按以下顺序推进：

1. [2026-07-02-current-project-godot-sampling-production-grade-providers-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-godot-sampling-production-grade-providers-implementation-plan.md)
2. [2026-07-02-current-project-embodied-skeletal-debug-replay-pipeline-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-embodied-skeletal-debug-replay-pipeline-implementation-plan.md)
3. [2026-07-02-current-project-vla-provider-backend-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-vla-provider-backend-implementation-plan.md)
4. [2026-07-02-current-project-actor-scene-knowledge-lifecycle-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-actor-scene-knowledge-lifecycle-implementation-plan.md)
5. [2026-07-02-current-project-siming-global-situation-layer-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-siming-global-situation-layer-implementation-plan.md)
6. [2026-07-02-current-project-interaction-orchestration-service-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-interaction-orchestration-service-implementation-plan.md)
7. [2026-07-02-current-project-esm-physical-channel-world-actuation-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-esm-physical-channel-world-actuation-implementation-plan.md)
8. [2026-07-02-current-project-non-runtime-production-pipeline-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-non-runtime-production-pipeline-implementation-plan.md)

执行例外：

- 非运行时生产链可独立推进，但其输出只能作为 reviewed seed / replay dataset，不能作为 runtime completion proof。
- VLA、ASK 和司命态势依赖 `PerceptionQueryFrame`、provider refs 和 L1 projected facts；如果这些上游证据不可用，完成口径必须降级为 contract/mock/static proof。
- ESM physical channel 依赖 Interaction Orchestration Service 的 structured intent route、channel plan 和 unified result merge；否则只能宣称 isolated physical channel contract/probe。

## 状态口径

当前 `implemented-and-verified` 覆盖 2026-06-30 协议/manifest/focused proof、2026-07-01 L1 runtime-facing subsystem、2026-07-02 增量能力计划、2026-07-03 provider readiness，以及 2026-07-05 perception identity 收口计划。

它仍不表示 `L1` 已成为新的 runtime 宿主，也不表示真实外部模型 provider 均已接入。真实 provider 状态以 `model-provider-readiness` 和各 provider report 为准。

当前项目若要继续推进角色 / 司命真实大模型闭合，不再分散从旧 plan 中各自收尾；请优先使用：

- `docs/superpowers/specs/2026-07-23-complete-llm-integration-closure-design.md`
- `docs/superpowers/plans/2026-07-23-complete-llm-integration-closure-implementation-plan.md`

## 待用户补齐：真实模型 key / endpoint

当前模型接入层已经准备好 provider 边界、配置入口和 live proof 验收位，但真实模型调用仍等待外部平台凭证。这里不要填写真实 secret，只记录需要准备的项。

- `API key` 是模型平台给的调用令牌。
- `endpoint` 是后端要发 HTTP 请求的模型服务地址。
- `model` 是这条路由要调用的具体模型名。

司命 live proof 当前保留 DeepSeek，并可追加 Qwen 与 Seed/Doubao：

```env
SIMING_LLM_DEEPSEEK_API_KEY=<real DeepSeek key>
SIMING_LLM_DEEPSEEK_ENDPOINT=https://api.deepseek.com/chat/completions
SIMING_LLM_DEEPSEEK_MODEL=deepseek-chat

SIMING_LLM_QWEN_API_KEY=<real Qwen/DashScope key>
SIMING_LLM_QWEN_ENDPOINT=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
SIMING_LLM_QWEN_MODEL=qwen3.7-plus

SIMING_LLM_SEED_DOUBAO_API_KEY=<real Seed/Doubao key>
SIMING_LLM_SEED_DOUBAO_ENDPOINT=<real Seed/Doubao chat-completions endpoint>
SIMING_LLM_SEED_DOUBAO_MODEL=doubao-seed-2.0-pro
```

拿到凭证后，运行：

```powershell
python scripts/verification/verify_siming_backend_chain.py --live-provider deepseek_chat --live-provider qwen --live-provider seed_doubao
```

运行时多路由配置可用 `SIMING_LLM_ROUTES_JSON` 声明 `deepseek_chat`、`qwen`、`seed_doubao` 多个 route；route-level API key 不应写入文档或提交到版本库。

`System L1 world fact subsystem` / runtime-facing L1 services 集成已完成 focused/runtime 验证：

- [2026-07-01-current-project-l1-world-fact-runtime-full-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-01-current-project-l1-world-fact-runtime-full-implementation-plan.md)

当前核对过的专题 profile 证据包括：

- `python scripts/verification/harness.py --profile godot-sampling-production-grade-providers`
- `python scripts/verification/harness.py --profile embodied-skeletal-debug-replay`
- `python scripts/verification/harness.py --profile vla-provider-backend`
- `python scripts/verification/harness.py --profile actor-scene-knowledge-lifecycle`
- `python scripts/verification/harness.py --profile siming-global-situation-layer`
- `python scripts/verification/harness.py --profile interaction-orchestration-service`
- `python scripts/verification/harness.py --profile esm-physical-channel-world-actuation`
- `python scripts/verification/harness.py --profile non-runtime-production-pipeline`
- `python scripts/verification/harness.py --profile model-provider-readiness`
- `python scripts/verification/harness.py --profile perception-input-alignment`

## 后续风险记录

2026-07-02 后续计划已完成 backend/harness/Godot runtime proof 后，仍保留两个不适合在同一执行切片内顺手解决的后续风险：

1. `ActorSceneKnowledgeStore` 当前是第一阶段内存 store。后续若要落持久化，需要单独设计 actor/session/scene 分区、TTL、revision compaction、trace retention、迁移和隐私隔离验证；不应在 lifecycle contract 切片中直接引入存储层。
2. `ESM Physical Channel World Actuation` 已验证受控 physical channel、Godot runtime contact/body/object/environment refs、constraint gating 和 orchestration unified merge。它仍不是完整生产级连续物理玩法 rollout；后续若要扩展，需要单独计划 Godot 局部物理执行、连续接触采样频率、权威回流、L1/ESM feedback 稳定性和可重复 runtime 验收。

这两个风险不阻塞当前 2026-07-02 计划交付；它们应作为后续增量计划拆分，而不是并入本次已验证切片。

## 计划树

1. [2026-06-30-current-project-intelligence-upgrade-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-intelligence-upgrade-implementation-plan.md)
2. [2026-06-30-current-project-vla-multimodal-upgrade-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-vla-multimodal-upgrade-implementation-plan.md)
3. [2026-06-30-current-project-l1-world-fact-and-space-foundation-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-l1-world-fact-and-space-foundation-implementation-plan.md)
4. [2026-07-01-current-project-l1-world-fact-runtime-full-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-01-current-project-l1-world-fact-runtime-full-implementation-plan.md)
5. [2026-07-02-current-project-vla-provider-backend-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-vla-provider-backend-implementation-plan.md)
6. [2026-07-02-current-project-actor-scene-knowledge-lifecycle-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-actor-scene-knowledge-lifecycle-implementation-plan.md)
7. [2026-07-02-current-project-siming-global-situation-layer-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-siming-global-situation-layer-implementation-plan.md)
8. [2026-07-02-current-project-interaction-orchestration-service-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-interaction-orchestration-service-implementation-plan.md)
9. [2026-07-02-current-project-esm-physical-channel-world-actuation-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-esm-physical-channel-world-actuation-implementation-plan.md)
10. [2026-07-02-current-project-embodied-skeletal-debug-replay-pipeline-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-embodied-skeletal-debug-replay-pipeline-implementation-plan.md)
11. [2026-07-02-current-project-non-runtime-production-pipeline-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-non-runtime-production-pipeline-implementation-plan.md)
12. [2026-07-02-current-project-godot-sampling-production-grade-providers-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-godot-sampling-production-grade-providers-implementation-plan.md)
13. [2026-07-03-current-project-model-provider-readiness-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-03-current-project-model-provider-readiness-implementation-plan.md)
14. [2026-07-05-current-project-perception-input-alignment-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-05-current-project-perception-input-alignment-implementation-plan.md)
15. [2026-07-05-current-project-perception-alignment-closure-and-gating-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-05-current-project-perception-alignment-closure-and-gating-plan.md)
16. [2026-07-05-current-project-perception-capture-clock-contract-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-05-current-project-perception-capture-clock-contract-implementation-plan.md)
17. [2026-07-05-current-project-cross-modal-object-anchor-and-reference-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-05-current-project-cross-modal-object-anchor-and-reference-implementation-plan.md)
18. [2026-07-05-current-project-multi-actor-private-perspective-reconciliation-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-05-current-project-multi-actor-private-perspective-reconciliation-implementation-plan.md)
19. [2026-07-05-current-project-perception-identity-verification-matrix-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-05-current-project-perception-identity-verification-matrix-implementation-plan.md)
20. [2026-06-30-current-project-perception-query-and-percept-protocol-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-perception-query-and-percept-protocol-implementation-plan.md)
21. [2026-06-30-current-project-character-multimodal-and-actor-scene-knowledge-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-character-multimodal-and-actor-scene-knowledge-implementation-plan.md)
22. [2026-06-30-current-project-siming-multimodal-and-global-situation-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-siming-multimodal-and-global-situation-implementation-plan.md)
23. [2026-06-30-current-project-esm-dual-channel-world-actuation-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-esm-dual-channel-world-actuation-implementation-plan.md)
24. [2026-06-30-current-project-interaction-orchestration-layer-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-interaction-orchestration-layer-implementation-plan.md)
25. [2026-06-30-current-project-godot-sampling-frontend-and-providers-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-godot-sampling-frontend-and-providers-implementation-plan.md)
26. [2026-06-30-current-project-embodied-skeletal-state-provider-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-embodied-skeletal-state-provider-implementation-plan.md)
27. [2026-06-30-current-project-non-runtime-multimodal-tooling-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-non-runtime-multimodal-tooling-implementation-plan.md)
28. [2026-07-29-vla-real-provider-adapter-live-proof-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-29-vla-real-provider-adapter-live-proof-implementation-plan.md)
29. [2026-07-30-advisory-vla-routing-and-tts-convergence-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-30-advisory-vla-routing-and-tts-convergence-implementation-plan.md)

## 一句话收束

这棵计划树的职责不是重新推进主线，而是把 mainline 已闭合之后仍需补强的感知、多模态、协议、具身和工具链能力逐步落地。

## 2026-08-03 司命持久天道图谱 Phase 1.1-7

已批准设计的依赖门禁式实施入口：

1. [Program dependency index](2026-08-03-current-project-siming-durable-heavenly-graph-program-plan.md)
2. [Phase 1.1 Durable Graph Hardening](2026-08-03-phase1-1-durable-graph-hardening-implementation-plan.md)
3. [Phase 2 Siming Six-Domain Memory](2026-08-03-phase2-siming-six-domain-memory-implementation-plan.md)
4. [Phase 3 Actor Five-Pool Graph Memory](2026-08-03-phase3-actor-five-pool-graph-memory-implementation-plan.md)
5. [Phase 4 Storyline Obligation and Attractor](2026-08-03-phase4-storyline-obligation-attractor-implementation-plan.md)
6. [Phase 5 Resource Capability and Staging](2026-08-03-phase5-resource-capability-staging-implementation-plan.md)
7. [Phase 6 Adaptive Bridge](2026-08-03-phase6-adaptive-bridge-implementation-plan.md)
8. [Phase 7 Full Runtime Integration](2026-08-03-phase7-full-runtime-integration-implementation-plan.md)

严格按 1.1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 执行；前一 dedicated Harness profile 未通过时，不进入后续实现。

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
## 2026-07-23 Closure Status

Current model-provider readiness is only one input to LLM integration closure. The actual closure claim requires `model-provider-readiness`, `character-model-live`, `siming-backend-chain`, and `llm-integration-closure` artifacts from the same `LLM_CLOSURE_RUN_ID`.
