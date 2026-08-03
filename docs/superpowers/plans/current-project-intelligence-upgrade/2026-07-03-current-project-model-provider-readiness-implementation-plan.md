# 当前项目大模型 Provider 接入就绪实施计划

状态补充：本计划已完成 readiness layer，但它不是当前项目 LLM 全量闭合计划。readiness 之后仍未完成的 live-provider / contract / default-runtime closure 项统一转入：

- `docs/superpowers/specs/2026-07-23-complete-llm-integration-closure-design.md`
- `docs/superpowers/plans/2026-07-23-complete-llm-integration-closure-implementation-plan.md`

> 上位母规格：
> [2026-06-29-current-project-intelligence-upgrade-master-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-intelligence-upgrade-master-design.md)

> 关联 2026-07-02 后续计划：
> - [2026-07-02-current-project-godot-sampling-production-grade-providers-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-godot-sampling-production-grade-providers-implementation-plan.md)
> - [2026-07-02-current-project-vla-provider-backend-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-vla-provider-backend-implementation-plan.md)
> - [2026-07-02-current-project-actor-scene-knowledge-lifecycle-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-actor-scene-knowledge-lifecycle-implementation-plan.md)
> - [2026-07-02-current-project-siming-global-situation-layer-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-siming-global-situation-layer-implementation-plan.md)
> - [2026-07-02-current-project-non-runtime-production-pipeline-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-02-current-project-non-runtime-production-pipeline-implementation-plan.md)

**状态：** `implemented-and-verified-readiness-layer`

**实际核对：** `model-provider-readiness` harness profile 已通过，报告为 `.harness/verification/model-provider-readiness-report.json`。当前 provider 状态为 character_text `blocked_missing_credentials`、siming_candidate `disabled`、vla_spatial `blocked_missing_artifacts`、production_multimodal `disabled`；因此完成口径是 readiness layer 已验证，不是所有真实模型 provider 已接入。

**目标：** 把当前项目里不同用途的大模型接入点整理成可执行、可验证、可降级的 provider readiness 层。完成后应能清楚回答：哪些模型入口已经能真实接入，哪些还缺凭据或 runtime artifact，哪些绝不能直接控制 world truth。

## 0. 边界

本计划允许：

- 统一梳理角色文本模型、司命 LLM、VLA/多模态 provider、非运行时生产模型的接入状态。
- 补齐 provider 配置、adapter contract、真实 HTTP/local adapter 门槛、trace 和 verification。
- 给每类模型建立 `disabled` / `http` / `local` / `blocked` 等明确模式。
- 把真实模型输出约束为 schema-valid、advisory 或 candidate-level 结果。

本计划禁止：

- 新增全局多模态脑。
- 让任一大模型直接写 `world truth`、ESM authority、object/environment/body state。
- 让 VLA 或 robotics VLA action head 接管角色动作控制。
- 让 Godot 承担大模型推理。
- 让角色和司命共享 private multimodal context、patch cache、inference history。
- 使用 mock provider 作为完成口径。
- 把 contract/static proof 写成真实模型已接入。

## 1. 当前事实

已存在：

- `backend/app/character_agent/gateway/model_gateway.py`
  - 已有角色模型 gateway、prompt policy、router、validator。
- `backend/app/character_agent/gateway/model_provider.py`
  - 已支持 `local`、`deepseek`、`hybrid`，并带 local fallback。
- `backend/app/services/siming_llm_provider.py`
  - 已支持 disabled provider、fake provider、HTTP provider、provider router、OpenAI Responses 风格和 DeepSeek chat completions 风格。
- `backend/app/config.py`
  - 已有 `SIMING_LLM_*` settings。
- `.env.example`
  - 已示例 `SIMING_LLM_MODE=http`、`SIMING_LLM_PROVIDER_ORDER=deepseek_chat`、`SIMING_LLM_ENDPOINT`、`SIMING_LLM_MODEL`。

尚未完成：

- VLA provider backend、model registry、scheduler、cache、trace、真实模型 adapter。
- 非运行时生产链的 VLM/classifier model adapter。
- Godot production-grade provider refs 对 VLA/多模态模型的完整输入供应。
- 模型接入总账，无法一眼判断每个模型入口处于 `disabled/http/local/blocked/configured-unverified/real-verified` 哪个状态。
- 统一的模型 readiness verifier / harness profile。

## 2. 推荐模型选择

本计划优先采用 Qwen 与 Seed / Doubao 系列，不引入 mock provider 路线。

### 2.1 角色文本模型

推荐：

- 主力：`qwen3.7-plus`
- 高质量/困难规划：`qwen3.7-max`
- 备选长链 reasoning：`doubao-seed-2.0-pro` 或当前火山/BytePlus 可用的 Seed2.x Pro 等价模型

理由：

- 角色 L2/L3/对话主要需要稳定文本推理、结构化 JSON、角色一致性和低延迟。
- Qwen Model Studio 已提供 OpenAI-compatible API，和当前 `CharacterModelProvider` 的 chat-completions 风格接近。
- Seed Pro 适合作为复杂长链规划或跨事件推理的高质量备选，不作为默认低延迟路径。

### 2.2 司命候选模型

推荐：

- 主力：`doubao-seed-2.0-pro`
- 成本/速度档：`doubao-seed-2.0-lite`
- 备选：`qwen3.7-max`

理由：

- 司命更像导演层，需要长链、多角色、全局态势和严格指令跟随。
- Seed2.0 官方定位覆盖 Pro/Lite/Mini 三档 Agent 模型，Pro 更适合复杂工作流和长链任务。
- 司命输出必须保持 candidate-level，不能产生 authority mutation、selected path 或 physical success claim。

### 2.3 VLA / 多模态空间模型

推荐：

- 主力：`qwen3-vl-plus` 或当前阿里 Model Studio 可用的 Qwen3-VL 等价视觉理解模型
- 低延迟/低成本：`qwen3-vl-flash` 或当前可用 Qwen VL Flash 等价模型
- 交叉验证/视频态势：`doubao-seed-2.0-pro` / `doubao-seed-2.0-lite`

理由：

- VLA 只做 advisory spatial findings，需要空间、遮挡、位置、grounding、视频/动态理解。
- Qwen3-VL 官方强调 spatial perception、object positions、viewpoints、occlusions、2D/3D grounding，匹配本项目 VLA 需求。
- Seed2.0 官方强调多模态、视觉推理、时序/运动理解，可作为司命全局态势或视频/长上下文补充。

### 2.4 非运行时生产模型

推荐：

- 批处理语义抽取：`doubao-seed-2.0-lite` / `doubao-seed-2.0-mini`
- 高质量审核辅助：`doubao-seed-2.0-pro`
- 图像/视频分类补充：`qwen3.7-plus` 或 Qwen3-VL 等价模型

理由：

- 非运行时生产链允许慢、批量、review gate，适合 Seed Lite/Mini 做吞吐，Seed Pro 做疑难审核。
- 所有输出只能成为 draft/review artifact，不能直接写 runtime truth。

## 3. 模型入口分区

### 3.1 Character Text Model Provider

职责：

- 角色 L2 reasoning
- 角色 L3 planning
- dialogue generation

接入状态：

- 已有 gateway 和 DeepSeek HTTP adapter。
- 已有 local fallback。

本计划只补：

- readiness report
- env 示例补齐
- smoke verification
- timeout/error/invalid-output 口径统一

不重写角色心智核心。

### 3.2 Siming LLM Candidate Provider

职责：

- 生成 candidate-level intervention suggestions
- 增强司命候选，不写 authority，不选最终 path

接入状态：

- 已有 HTTP provider/router/fake provider。
- 已有 timeout/invalid-output error 类型。

本计划补：

- global situation context 接入 readiness check
- provider route readiness report
- strict output schema smoke test

不允许司命 LLM 输出 authority mutation、physical success claim 或低层角色命令。

### 3.3 VLA / Multimodal Spatial Provider

职责：

- 消费 `PerceptionQueryFrame`、visual/spatial/depth/occupancy/structured fact refs
- 输出 advisory spatial findings
- 进入 `ModalityInterpretationResult` / `CrossModalUnderstandingResult` / percept bundle

接入状态：

- 当前只有设计与 2026-07-02 实施计划。
- 真实 provider 尚未 ready。

本计划必须把它推进到真实 provider readiness 层：

- model registry ready
- HTTP/local adapter contract ready
- scheduler/cache/trace ready
- real-provider readiness gate ready

真实模型只有在消费真实或等价 runtime artifact refs、输出 schema-valid advisory result、通过 timeout/degrade 验证后，才能标记为 `real-provider-verified`。

### 3.4 Non-Runtime Production Model Providers

职责：

- scene semantic extraction
- multimodal semantic classification
- affordance candidate classification
- replay/dataset enrichment

接入状态：

- 当前是计划和工具链边界。

本计划补：

- production model adapter contract
- offline batch mode
- review gate integration
- artifact lineage

生产模型输出只能成为 draft/review artifact，不能直接进入 runtime truth。

## 4. Provider Readiness Ledger

新增文件建议：

- `backend/app/world_runtime/model_provider_readiness.py`
- `backend/tests/test_model_provider_readiness.py`
- `.harness/profiles/model-provider-readiness.json`
- `scripts/verification/verify_model_provider_readiness.py`

任务：

- [x] 定义 `ModelProviderKind`
  - `character_text`
  - `siming_candidate`
  - `vla_spatial`
  - `production_multimodal`
- [x] 定义 `ModelProviderMode`
  - `disabled`
  - `http`
  - `local`
  - `blocked`
- [x] 定义 `ModelProviderReadinessStatus`
  - `not_configured`
  - `contract_ready`
  - `http_configured_unverified`
  - `real_provider_verified`
  - `blocked_missing_artifacts`
  - `blocked_missing_credentials`
  - `blocked_model_unavailable`
- [x] 定义 readiness evidence 字段：
  - provider kind
  - mode
  - provider id
  - model id
  - endpoint host redacted
  - schema version
  - required input refs
  - output schema status
  - timeout/degrade status
  - context isolation status
  - world-truth-write status
  - verification commands
- [x] 输出 `.harness/verification/model-provider-readiness-report.json`
- [x] 输出 `.harness/verification/model-provider-readiness-report.md`

验收：

- 每类模型入口都有 readiness row。
- 缺 API key 不算失败，但必须标记 `blocked_missing_credentials`。
- 缺 Godot/PQF/L1 artifact 不算 VLA 完成，必须标记 `blocked_missing_artifacts`。
- contract/static proof 和 real provider 状态不可混淆。
- 不允许出现 `mock_verified` 作为完成状态。

## 5. 阶段 A：角色模型接入就绪

目标文件建议：

- `backend/app/character_agent/gateway/model_provider.py`
- `backend/tests/test_character_model_provider_readiness.py`
- `scripts/verification/verify_model_provider_readiness.py`

任务：

- [x] 将 `CHARACTER_MODEL_*` / `DEEPSEEK_*` 配置纳入 readiness report。
- [x] 新增 `QWEN_*` 或通用 OpenAI-compatible 配置入口：
  - `CHARACTER_MODEL_PROVIDER_KIND=qwen`
  - `CHARACTER_MODEL_ENDPOINT`
  - `CHARACTER_MODEL_API_KEY`
  - `CHARACTER_MODEL_MODEL=qwen3.7-plus`
- [x] 保留 DeepSeek 兼容，但本计划推荐 Qwen 作为新默认文本 provider。
- [x] 增加不泄露 API key 的 endpoint/model 配置摘要。
- [x] 增加 local/qwen/deepseek/hybrid 四种 route 的 readiness 判定。
- [x] 验证 L2/L3 model-led task 在 provider 不可用时不会被错误标记为 real verified。
- [x] 保持 local fallback 只作为 fallback，不宣称真实模型语义完成。

验收：

- `local` route 只能标记为 `contract_ready`，不能标记为真实模型完成。
- `qwen` route 只有在 API key 存在且 smoke call/schema validation 通过时标记 `real_provider_verified`。
- `deepseek` route 作为 legacy/backup，只有在 API key 存在且 smoke call/schema validation 通过时标记 `real_provider_verified`。
- `hybrid` route 必须记录 real call 成功或 fallback reason。

## 6. 阶段 B：司命 LLM 接入就绪

目标文件建议：

- `backend/app/services/siming_llm_provider.py`
- `backend/tests/test_siming_llm_provider_config.py`
- `backend/tests/test_siming_llm_runtime.py`
- `scripts/verification/verify_model_provider_readiness.py`

任务：

- [x] 将 `SIMING_LLM_*` 配置纳入 readiness report。
- [x] 新增 Seed / Doubao 推荐配置：
  - `SIMING_LLM_PROVIDER_ORDER=seed_doubao,qwen`
  - `SIMING_LLM_ENDPOINT`
  - `SIMING_LLM_API_KEY`
  - `SIMING_LLM_MODEL=doubao-seed-2.0-pro`
- [x] 记录 route order、provider type、model、timeout。
- [x] 增加 global situation context 输入是否已接线的 readiness flag。
- [x] 验证 disabled provider、HTTP provider 的状态区分。
- [x] 验证 provider 输出只允许 candidate-level intervention suggestions。

验收：

- `disabled` 不算错误，但状态必须清晰。
- HTTP provider 没有 API key 时为 `blocked_missing_credentials`。
- HTTP provider smoke call 通过且输出 schema-valid 时才是 `real_provider_verified`。
- 司命 LLM 不产生 authority event、selected path、physical success claim、ESM mutation 或 low-level character command。

## 7. 阶段 C：VLA / 多模态 Provider 接入就绪

目标文件建议：

- `backend/app/world_runtime/vla_provider.py`
- `backend/app/world_runtime/vla_model_registry.py`
- `backend/app/world_runtime/vla_slow_path_scheduler.py`
- `backend/app/world_runtime/vla_cache.py`
- `backend/app/world_runtime/vla_percept_bridge.py`
- `backend/tests/test_vla_provider_backend_contract.py`
- `backend/tests/test_vla_provider_backend_adapter.py`
- `backend/tests/test_vla_slow_path_scheduler.py`
- `backend/tests/test_vla_provider_cache_isolation.py`
- `backend/tests/test_vla_percept_bridge.py`

任务：

- [x] 定义 HTTP/local VLA adapter contract。
- [x] 定义 model registry，记录 license/deployment/schema/runtime boundary。
- [x] 在 registry 中登记推荐模型：
  - `qwen3-vl-plus`
  - `qwen3-vl-flash`
  - `doubao-seed-2.0-pro`
  - `doubao-seed-2.0-lite`
- [x] 定义 slow path scheduler：per-owner queue、timeout、degrade、drop trace。
- [x] 定义 cache：context namespace、artifact hash、freshness、no cross-owner hit。
- [x] 定义 VLA result -> modality/cross-modal/percept bridge。
- [x] 定义 `VLA_PROVIDER_*` env config：
  - `VLA_PROVIDER_MODE`
  - `VLA_PROVIDER_ENDPOINT`
  - `VLA_PROVIDER_API_KEY`
  - `VLA_PROVIDER_MODEL`
  - `VLA_PROVIDER_TIMEOUT_SECONDS`
  - `VLA_PROVIDER_MAX_QUEUE_SIZE`
  - `VLA_PROVIDER_CACHE_TTL_SECONDS`
- [x] readiness report 区分 `contract_ready`、`http_configured_unverified`、`blocked_missing_artifacts`、`real_provider_verified`。

验收：

- scheduler 能调用真实 HTTP/local adapter。
- PQF 可转换为 `VLAProviderRequest`。
- result 可转换为 `ModalityInterpretationResult`。
- timeout 不阻塞当前 runtime tick。
- character/siming queue 和 cache namespace 隔离。
- VLA result 不写 L1/world truth/ESM authority。
- 真实模型接入必须消费真实或等价 runtime artifact refs。
- 缺真实模型凭据或缺 runtime artifact 时必须 blocked，不能 fallback 到 mock 完成。

## 8. 阶段 D：非运行时生产模型接入就绪

目标文件建议：

- `tools/production/model_provider.py`
- `tools/production/multimodal_semantic_classifier.py`
- `tools/production/scene_semantic_extractor.py`
- `tools/production/review_workbench.py`
- `backend/tests/test_non_runtime_production_pipeline.py`
- `scripts/verification/verify_model_provider_readiness.py`

任务：

- [x] 定义 production model provider adapter contract。
- [x] 定义 disabled/http/local/offline-batch 模式。
- [x] 在 registry 中登记推荐模型：
  - `doubao-seed-2.0-lite`
  - `doubao-seed-2.0-mini`
  - `doubao-seed-2.0-pro`
  - `qwen3.7-plus`
  - `qwen3-vl-plus`
- [x] 定义 `NON_RUNTIME_MODEL_*` env config：
  - `NON_RUNTIME_MODEL_MODE`
  - `NON_RUNTIME_MODEL_ENDPOINT`
  - `NON_RUNTIME_MODEL_API_KEY`
  - `NON_RUNTIME_MODEL_MODEL`
  - `NON_RUNTIME_MODEL_TIMEOUT_SECONDS`
- [x] classifier 输出只能进入 draft artifact。
- [x] scene semantic extraction 输出必须进入 review gate。
- [x] review approved 前不得作为 L1 seed。
- [x] dataset/replay builder 记录 model id、prompt/schema version、source artifact refs。

验收：

- production model 输出不会进入 runtime private context。
- draft/review/approved/rejected 状态可追踪。
- rejected draft 不进入 L1 seed。
- approved artifact 可被 L1 extractor 或 verifier 消费。

## 9. 阶段 E：统一配置与安全边界

目标文件建议：

- `.env.example`
- `backend/app/config.py`
- `backend/tests/test_model_provider_readiness.py`
- `docs/harness.md`

任务：

- [x] 补齐 `CHARACTER_MODEL_*` 示例配置。
- [x] 补齐 `QWEN_*` / OpenAI-compatible endpoint 示例配置。
- [x] 补齐 Seed / Doubao endpoint 示例配置。
- [x] 补齐 `VLA_PROVIDER_*` 示例配置。
- [x] 补齐 `NON_RUNTIME_MODEL_*` 示例配置。
- [x] 所有 readiness report 必须 redact API key。
- [x] 所有 HTTP provider 记录 endpoint host 而不是完整 secret URL。
- [x] 所有 provider 都有 timeout。
- [x] 所有 provider 都有 disabled mode。
- [x] 所有 provider 都有 invalid-output handling。

验收：

- `.env.example` 不包含真实 secret。
- 缺 key 时系统可启动并报告 blocked/disabled，而不是崩溃。
- provider error 不会写 world truth。

## 10. 阶段 F：Verification 与 Harness

目标文件建议：

- `scripts/verification/verify_model_provider_readiness.py`
- `.harness/profiles/model-provider-readiness.json`
- `docs/harness.md`
- `docs/superpowers/plans/current-project-intelligence-upgrade/README.md`

验证命令：

```powershell
python -m pytest -q backend/tests/test_model_provider_readiness.py
python -m pytest -q backend/tests/test_character_model_provider_readiness.py backend/tests/test_siming_llm_provider_config.py
python -m pytest -q backend/tests/test_vla_provider_backend_contract.py backend/tests/test_vla_provider_backend_adapter.py backend/tests/test_vla_slow_path_scheduler.py backend/tests/test_vla_provider_cache_isolation.py backend/tests/test_vla_percept_bridge.py
python -m pytest -q backend/tests/test_non_runtime_production_pipeline.py
python scripts/verification/verify_model_provider_readiness.py
python scripts/verification/harness.py --profile model-provider-readiness
python scripts/verification/harness.py --profile docs
```

与 2026-07-02 计划联动验证：

```powershell
python scripts/verification/harness.py --profile godot-sampling-production-grade-providers
python scripts/verification/harness.py --profile vla-provider-backend
python scripts/verification/harness.py --profile actor-scene-knowledge-lifecycle
python scripts/verification/harness.py --profile siming-global-situation-layer
python scripts/verification/harness.py --profile non-runtime-production-pipeline
```

验收：

- readiness report 能解释每类 provider 为什么 ready / not ready。
- contract proof、configured-unverified、real provider proof 三者清楚分开。
- 所有 provider failure 都有 timeout/degrade/invalid-output 记录。
- 所有模型输出都不能直接写 world truth。

## 11. 不接受的完成口径

- 只填 API key，没有 readiness report。
- 只跑通角色文本模型，就宣称“各部分大模型都准备好”。
- 使用 mock provider 作为完成证据。
- 只新增 adapter contract，就宣称真实 VLA 已接入。
- 只证明 provider schema 存在，没有 scheduler/cache/trace。
- 生产链模型输出绕过 review gate 直接进入 L1 seed。
- 模型输出直接写 ESM authority、world result、object/environment/body state。
- character 和 siming 共享 private cache 或 inference history。

## 12. 完成定义

完成后应能说：

> 当前项目已具备大模型 provider readiness 层：角色文本模型、司命候选模型、VLA/多模态空间模型和非运行时生产模型都有明确配置、adapter contract、真实 provider 状态、schema validation、timeout/degrade、trace 和 harness 证据。真实模型接入与 contract/configured-unverified 状态被清楚区分，所有模型输出都只能通过既有感知、候选、review 或 advisory 通道进入系统，不能直接写 world truth。

如果 VLA 或生产链真实模型尚未接入，只能说：

> 角色文本/司命 LLM 接入口已具备真实 provider readiness；VLA 或生产链模型仍处于 contract/configured-unverified/blocked 状态，等待 Godot/PQF/L1 artifact 或真实模型 adapter 验证。
## 2026-07-23 Closure Status

Model provider readiness remains a non-live evidence class. It records provider/model identity and configuration readiness, including `verification_run_id`, but it is intentionally not promoted to live proof. The live closure aggregator requires separate Character and Siming live artifacts.
