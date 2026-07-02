# 当前项目 `L1` 世界事实层完整运行时实施计划

> 对应规格：
> [2026-06-29-current-project-l1-world-fact-and-space-foundation-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-l1-world-fact-and-space-foundation-design.md)

> 上游契约切片：
> [2026-06-30-current-project-l1-world-fact-and-space-foundation-implementation-plan.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/current-project-intelligence-upgrade/2026-06-30-current-project-l1-world-fact-and-space-foundation-implementation-plan.md)

**状态：** `runtime-facing-l1-world-fact-subsystem-implemented-and-verified`

**目标：** 不再停留在协议、manifest、静态 provider 或 focused proof。把 `L1` 实现为当前运行链可用的 `System L1 world fact subsystem` / runtime-facing L1 services：从 Godot 场景抽取静态空间底稿，维护动态空间占据层，由统一 `Fact Projection Layer` 从空间/环境底座投影事实，并把这些事实接入现有 `raw_fact_event -> candidate percept -> character/siming runtime` 主链。

**命名与边界回补（2026-07-01）：** 本计划中历史简称 `L1 runtime` 一律按实现收敛为 `System L1 world fact subsystem` 或 `runtime-facing L1 services`。实现落点复用 `backend/app/world_runtime/`、现有 ESM、现有 `raw_fact_event -> candidate -> private percept` 主链、现有 `CharacterAgentRuntime` / `SimingRuntime` 和 Godot runtime probes；不得解释为新增第二套 runtime 主循环、平行事实总线或绕过主链的新事实通道。

**剩余风险收敛（2026-07-02）：** 当前主场景启动链会创建并标记真实 `NavigationRegion3D`（`L1NavigationRegion`）作为 `navigation_lane` 来源；`SceneSpaceModelExtractor` 在存在真实导航区时不再把 floor/walk 节点提升为导航事实证据。`verify_l1_world_fact_runtime.py` 必须检查空间模型 artifact 同时包含 node/runtime refs、collision shape refs 和非 `derived_from_runtime_walkable` 的真实 `navigation_region:` ref；派生 walkable 只保留为无导航区时的 fallback，不能单独满足完整完成口径。

## 0. 范围纠偏

当前已完成内容只覆盖：

- `backend/app/world_runtime/intelligence_upgrade.py` 中的协议和 manifest 对象
- `scripts/character/*Provider.gd` 中的静态采样引用构造器
- `backend/tests/test_current_project_intelligence_upgrade.py` 中的 focused contract tests
- `scripts/verification/verify_current_project_intelligence_upgrade.py` 中的聚合证明

这些内容证明“边界可被描述且不会破坏现有主线”，但没有证明：

- Godot runtime 已真实生成 `PerceptionQueryFrame` artifact，包含真实 camera pose、viewport capture artifact、space/occupancy refs、auditory refs、actor embodied refs。
- `Scene3DSpaceModel` 已从场景、节点、碰撞体/碰撞聚合根、导航/可行走面抽取并落 `.harness/verification/l1-space-model-runtime.json`。
- `SpatialOccupancyField` 已随 actor enter/leave、actor/object proximity enter/clear、temporary blockers、object affordance/rollback、environment field 变化做 dirty-zone 增量更新。
- `FactProjectionLayer` 已从 occupancy / environment field 投影 LOS、reachability、affordance、negative facts。
- 角色和司命 runtime 已通过 `L1RuntimePerceptionBridge` 消费由 projected facts/provider refs 组装的 `CanonicalPerceptBundle`，证据落 `.harness/verification/l1-perception-bridge-backend-contract.json`。

本轮实现补充的 runtime-facing 证据面：

- `backend/app/world_runtime/l1_space_model.py`
- `backend/app/world_runtime/l1_occupancy.py`
- `backend/app/world_runtime/l1_fact_projection.py`
- `backend/app/world_runtime/l1_perception_frame.py`
- `scripts/l1/space/SceneSpaceModelExtractor.gd`
- `scripts/l1/space/RuntimeOccupancySampler.gd`
- `scripts/l1/space/FactProjectionBridge.gd`
- `scripts/verification/L1WorldFactRuntimeProbe.gd`
- `scripts/verification/verify_l1_world_fact_runtime.py`
- `.harness/profiles/l1-world-fact-runtime.json`

如果 Godot executable/editor 当前环境不可用，验证报告必须保持 `godot-runtime-unverified`，不能把 backend-contract proof 写成完整 Godot runtime proof。

本计划的完成标准必须以这些运行时事实为准。

## 1. 当前代码事实

- 当前 L1 fact envelope 入口在 `scripts/l1/facts/FactEnvelopeBuilder.gd` 和 `scripts/l1/facts/RawFactEmitter.gd`。
- 当前 Godot L1 emitters 在 `scripts/l1/facts/emitters/`，例如 `SpatialAccessFactEmitter.gd`、`AuditoryFactEmitter.gd`、`CharacterVisualFactEmitter.gd`。
- 当前 backend raw fact schema 在 `backend/app/models/raw_fact.py`。
- 当前 candidate 编译入口在 `backend/app/services/candidate_percept_service.py`，听觉仍是 targeted actor 白名单策略。
- 当前 per-character filter 在 `backend/app/services/per_character_percept_filter.py`，视觉朝向和距离上下文仍是薄实现。
- 当前角色 L1 私有快照入口在 `backend/app/character_agent/reasoning/l1_perception.py`。
- 当前 ESM 语义结算入口在 `backend/app/services/esm_service.py`，环境场结果已回流到 `SpatialOccupancyService` 并作为 `FactProjectionLayer` 输入。
- 当前 runtime main route 在 `backend/app/main.py`。
- 当前 Godot runtime probes 在 `scripts/verification/`，L1 edge probe 为 `scripts/verification/L1RuntimeProbe.gd` 和 `scripts/verification/verify_l1_runtime_edges.py`。

## 2. 完整验收标准

### 2.1 L1 空间底座

- [x] `Scene3DSpaceModel` 有运行时/离线生成入口，不再只是 Pydantic 对象。
- [x] 至少从当前主场景抽取以下对象族：
  - `zone`
  - `static_obstacle`
  - `occluder`
  - `environment_anchor`
  - `interaction_object`
  - `navigation_lane`
- [x] 抽取来源必须包含至少两类真实来源：
  - Godot node path / group / metadata
  - collision shape 或 navigation region
- [x] 人工字段只允许作为 review override，不能成为主数据来源。
- [x] 生成结果必须落到可检查 artifact，例如 `.harness/verification/l1-space-model-*.json`。

### 2.2 Spatial Occupancy Field runtime state

- [x] `SpatialOccupancyField` 有服务对象，不再只是 data model，也不得成为 runtime host。
- [x] Occupancy field 同时承接：
  - 静态空间底稿引用
  - actor 当前占据
  - object 当前状态
  - 临时阻挡
  - 环境场影响
- [x] 至少实现以下增量更新：
  - actor 进入/离开 zone
  - actor 靠近/离开 object 或 actor
  - environment `smoke_density` / `visibility_level` 改变后影响 visibility/passability 标记
  - object state 改变后影响 affordance 或 occlusion 标记
- [x] 不允许每 tick full-scene rescan；必须有节流、dirty-zone 或 event-driven update 证明。

### 2.3 Environment Field Model 与空间底座合流

- [x] 保留 `backend/app/models/environment_field.py` 和 `ESMService.get_environment_field(...)` 现有环境场。
- [x] L1 subsystem 必须把环境场作为 Fact Projection 输入，不再只停留在 ESM workbench snapshot。
- [x] environment result 回流后必须能更新对应 zone 的 runtime field。

### 2.4 Fact Projection Layer

- [x] `FactProjectionLayer` 有运行时代码，不再只是 manifest。
- [x] 事实来源必须依赖 `Scene3DSpaceModel` / `SpatialOccupancyField` / `EnvironmentFieldState` 中至少一个底座对象。
- [x] 至少新增并验证四类事实：
  - `line_of_sight_blocked`
  - `line_of_sight_restored`
  - `target_unreachable` 或 `path_detour_required`
  - `interaction_affordance_changed`
  - `expected_target_missing` 或 `expected_reachable_but_failed`
- [x] 新事实必须走现有 `raw_fact_event` 或兼容 route，不允许新开平行事实总线。
- [x] 新事实必须能进入 `CandidatePerceptEvent`，除非明确标记为 system-level only。

### 2.5 Godot Provider 真实采样

- [x] `VisualPatchProvider` 至少提供真实 camera pose、viewport/capture ref 或可验证 screenshot artifact ref。
- [x] `SpatialPatchProvider` 至少基于场景/碰撞/导航/zone 状态生成局部 obstacle/occlusion/passability refs。
- [x] `AuditoryContextProvider` 至少从现有 auditory fact 或 local source refs 形成时间窗。
- [x] `EmbodiedStateProvider` 至少从 `PlayerShell` / `CharacterReplica` / `CharacterRuntimeState` 形成姿态、locomotion、grounded、LOS/reachability failure 输入。
- [x] Provider 仍不得执行重推理、重体素化或 full-scene runtime scan。

### 2.6 Perception Query Frame 接线

- [x] Godot runtime 或 backend runtime 至少有一条真实 `PerceptionQueryFrame` 组装路径。
- [x] PQF 必须引用：
  - subject actor
  - time window
  - room / scene / zone
  - provider input refs
  - structured fact refs
  - isolated `character_mm:*` 或 `siming_mm:*` context
- [x] PQF 必须落证据 artifact 或 debug event，不能只在单元测试里构造。

### 2.7 Canonical Percept Bundle 消费

- [x] 至少一条角色 runtime 路径消费 `CanonicalPerceptBundle` 并影响 `CharacterPrivateWorldSnapshot`、working memory 或 L2 structured context。
- [x] 至少一条司命 runtime 路径消费司命版 percept bundle 或等价 global situation bundle，并影响 `FairnessStateSnapshot`、intervention candidate 或 workbench explanation。
- [x] 角色和司命不得共享 patch context、cache namespace、inference history。

### 2.8 与现有主线兼容

- [x] 现有 `raw_fact_event -> candidate -> CharacterPerceivedEvent` 主链不能退化。
- [x] 现有 Phase 0 / mainline Godot runtime proof 不能退化。
- [x] L1 subsystem 可关闭或降级，降级时仍使用现有 structured fact slice。

## 3. 实施阶段

### 阶段 A：L1 subsystem 目录与服务骨架

新增或扩展：

- `backend/app/world_runtime/l1_space_model.py`
- `backend/app/world_runtime/l1_occupancy.py`
- `backend/app/world_runtime/l1_fact_projection.py`
- `backend/app/world_runtime/l1_perception_frame.py`
- `backend/tests/test_l1_world_fact_runtime.py`

要求：

- 从 `intelligence_upgrade.py` 迁出或复用已有契约对象，避免一个文件继续膨胀成总桶。
- `backend/app/world_runtime/__init__.py` 必须导出新服务对象。
- 单元测试覆盖模型创建、dirty update、projection 输出和 downgrade fallback。

### 阶段 B：Godot 场景空间抽取

新增或扩展：

- `scripts/l1/space/SceneSpaceModelExtractor.gd`
- `scripts/l1/space/RuntimeOccupancySampler.gd`
- `scripts/l1/space/FactProjectionBridge.gd`
- `scripts/verification/L1WorldFactRuntimeProbe.gd`

要求：

- 对当前主场景抽取 zone、object、environment anchor 和至少一种 occluder/obstacle。
- 输出 `.harness/verification/l1-space-model-runtime.json` 或通过 backend debug route 回传。
- 不依赖人工逐项手填表；允许节点 group / metadata 作为语义来源。

### 阶段 C：Runtime occupancy 增量更新

扩展：

- `scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd`
- `backend/app/services/fact_handlers/spatial_access_fact_handler.py`
- `backend/app/world_runtime/l1_occupancy.py`
- `backend/app/services/esm_service.py`

要求：

- actor zone entry / nearby / leave 进入 occupancy。
- ESM environment result 更新 zone visibility/noise/thermal/smoke field。
- object result 更新 affordance 或 occlusion 标记。
- 添加 dirty-zone update 证据。

### 阶段 D：FactProjectionLayer 真实投影

新增：

- `backend/app/world_runtime/l1_fact_projection.py`
- `backend/tests/test_l1_fact_projection_runtime.py`

扩展：

- `backend/app/services/candidate_percept_service.py`
- `backend/app/main.py`

要求：

- 从 occupancy / environment field 投影 `line_of_sight_blocked`、`target_unreachable`、`interaction_affordance_changed`、negative fact。
- 投影事实必须沿现有 `raw_fact_event` shape 或兼容 model。
- candidate compiler 明确哪些新事实进入 private percept，哪些保持 system-level only。

### 阶段 E：Provider 真实采样与 PQF 组装

扩展：

- `scripts/character/VisualPatchProvider.gd`
- `scripts/character/SpatialPatchProvider.gd`
- `scripts/character/AuditoryContextProvider.gd`
- `scripts/character/EmbodiedStateProvider.gd`
- `scripts/character/EmbodiedSkeletalStateProvider.gd`
- `backend/app/world_runtime/l1_perception_frame.py`

要求：

- Provider 输出不能只包含 synthetic ref；必须包含真实 runtime source refs。
- 至少一种 provider 生成可检查 artifact ref。
- PQF 由真实 L1 fact refs 和 provider refs 组装。

### 阶段 F：角色与司命消费

扩展：

- `backend/app/character_agent/reasoning/l1_perception.py`
- `backend/app/services/character_agent_runtime.py` 或当前实际 runtime 入口
- `backend/app/services/siming_runtime.py`
- `backend/app/services/siming_read_model.py`

要求：

- 角色消费 `CanonicalPerceptBundle` 后可观察地更新 private snapshot / working memory / L2 structured context。
- 司命消费 global situation bundle 后可观察地更新 fairness/intervention/workbench explanation。
- 添加 context isolation 测试，确保 `character_mm:*` 和 `siming_mm:*` 不共享。

### 阶段 G：Verification 与 harness 接入

新增：

- `scripts/verification/verify_l1_world_fact_runtime.py`
- `backend/tests/test_l1_world_fact_runtime.py`
- `backend/tests/test_l1_fact_projection_runtime.py`
- `backend/tests/test_l1_perception_frame_runtime.py`

扩展：

- `scripts/verification/harness.py`
- `docs/harness.md`
- `docs/INDEX.md`

要求：

- 保留兼容 harness profile：`l1-world-fact-runtime`。这是 runtime verification profile，不是产品 runtime 名称。
- Profile 必须至少证明：
  - scene space model artifact exists
  - occupancy dirty update observed
  - projection facts emitted
  - projected fact enters candidate/private path or marked system-only with reason
  - PQF generated from runtime refs
  - character or Siming consumes bundle
  - mainline profile remains green

## 4. 验证命令

最小完整验收不是单测通过，而是以下命令全部通过：

```powershell
python -m pytest -q backend/tests/test_l1_world_fact_runtime.py backend/tests/test_l1_fact_projection_runtime.py backend/tests/test_l1_perception_frame_runtime.py
python scripts/verification/verify_l1_world_fact_runtime.py
python scripts/verification/harness.py --profile l1-world-fact-runtime
python scripts/verification/harness.py --profile mainline-unified-runtime
python scripts/verification/harness.py --profile docs
```

如 Godot CLI 或 editor runtime 不可用，报告必须标记为：

- `backend-contract-verified`
- `godot-runtime-unverified`

不能写成L1 subsystem integration 已完成。

## 5. 不接受的完成口径

以下情况不得标记为完成：

- 只新增 Pydantic model
- 只新增 manifest
- 只新增静态 provider
- 只新增 focused proof
- 只更新文档勾选
- 只证明“不破坏现有主链”
- 只在单元测试中手工构造 `Scene3DSpaceModel` / `PerceptionQueryFrame`

## 6. 风险与缓解

- 风险：L1 空间底座引入后拖慢 Godot runtime。
  - 缓解：dirty-zone update、节流采样、禁止 full-scene runtime rescan，harness 记录采样次数和耗时。
- 风险：FactProjection 与现有 emitter 形成双写冲突。
  - 缓解：projection 输出走统一 `raw_fact_event` shape；同一 fact key 通过 `FactDeduper` 或 backend dedupe 管理。
- 风险：角色/司命多模态上下文污染。
  - 缓解：继续强制 `character_mm:*` / `siming_mm:*` namespace，新增 runtime-level isolation test。
- 风险：一次实现全量空间系统过大。
  - 缓解：完整目标不降级，但分阶段提交；每阶段都必须产生 runtime proof，最终统一验收。
- 风险：Godot 空间抽取停留在 probe 或 walkable/floor 派生证据，不能代表主场景真实导航底座。
  - 缓解：主场景运行时补齐真实 `NavigationRegion3D`，抽取器优先真实导航区，verification 明确拒绝仅由 `derived_from_runtime_walkable` 导航证据通过。

## 7. 完成定义

本计划完成时，必须可以真实描述为：

> 当前项目 `L1` 已经不是 emitter 集合，而是有运行时空间底稿、动态 occupancy、环境场合流、事实投影、Godot 取样输入、PQF 组装和角色/司命消费证据的世界事实层。

如果任一核心证据缺失，只能描述为：

> `L1` subsystem integration 进行中；已完成契约或局部阶段。
