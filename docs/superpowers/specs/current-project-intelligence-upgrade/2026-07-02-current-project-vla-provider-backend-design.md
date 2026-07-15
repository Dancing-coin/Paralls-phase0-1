# 当前项目 VLA Provider Backend 子规格

- 日期：`2026-07-02`
- 状态：`implemented-and-verified-contract-ready-real-provider-blocked`
- 上位规格：
  - [2026-06-28-current-project-vla-multimodal-upgrade-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-28-current-project-vla-multimodal-upgrade-design.md)
  - [2026-06-29-current-project-intelligence-upgrade-master-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-intelligence-upgrade-master-design.md)

## 1. 目标

把当前项目中的 `VLA` 从“位置已固定的非阻塞空间视觉子链契约”补全为可实施的 provider backend 方案。

本子规格只定义：

- VLA provider 后端接口
- 开源多模态/VLA 能力的接入边界
- 慢通路调度、缓存、失败和 trace 语义
- VLA advisory 结果如何进入统一感知协议

它不定义新的产品级 runtime。

## 2. 核心定位

当前项目中的 `VLA Provider Backend` 是：

- 多模态慢通路里的空间视觉理解 provider
- 角色/司命私有多模态栈的能力来源之一
- 基于 `Perception Query Frame` 和 artifact refs 的按需推理接口
- advisory result producer

它不是：

- `VLA Runtime`
- 全局多模态脑
- `L1` 替代品
- `ESM` 替代品
- authority owner
- 角色动作控制器
- 司命主脑

## 3. 开源方案使用原则

开源模型可以作为 provider backend 使用，但不能直接成为当前项目 runtime。

### 3.1 可直接接入的能力

可作为第一阶段后端的能力类型：

- open-source VLM / grounding model
- visual spatial understanding model
- depth estimation model
- region/object grounding model
- structured JSON output capable multimodal model

这类模型负责把截图、局部视觉 patch、BEV/occupancy/depth refs 和结构化事实 refs 转换为结构化空间视觉发现。

### 3.2 只能借鉴或二阶段研究的能力

真正 robotics VLA 模型可以研究，但第一阶段不直接接入动作输出。

原因：

- robotics VLA 通常输出 robot action token 或连续控制动作
- 当前项目的动作选择属于 `CharacterAgentRuntime`
- 世界结算属于 ESM / authority backend
- Godot 本地表现只执行已批准的结构化结果

因此，OpenVLA 类模型如果使用，只能作为：

- 视觉-语言空间理解后端
- 架构参考
- 后续 fine-tuning 研究对象

不得把 action head 接入当前 world truth 或 actor control 链。

### 3.3 模型选择门槛

每个候选 backend 必须通过以下门槛：

- license 可用于当前项目目标
- 支持本地或受控服务部署
- 支持结构化输出或可稳定后处理为结构化输出
- 可在慢通路 timeout 预算内完成，或支持异步延迟结果
- 不需要持久共享 hidden state
- 不要求上传不可接受的 raw artifact
- 可记录 model id、version、prompt/schema version 和 trace ref

## 4. 输入边界

VLA provider 只能消费现有 runtime 产出的 artifact/ref，不直接读取或重建世界。

允许输入：

- `PerceptionQueryFrame`
- `L1` projected fact refs
- `Scene3DSpaceModel` refs
- `SpatialOccupancyField` / BEV / occupancy refs
- `VisualPatchProvider` viewport/camera artifact refs
- depth artifact refs
- `AuditoryContextProvider` refs
- `EmbodiedStateProvider` refs
- `EmbodiedSkeletalStateProvider` high/mid-level refs
- attention context

禁止输入：

- 其他角色私有 patch cache
- 司命私有 cache 给角色使用
- 角色私有 cache 给司命使用
- 长期 hidden state
- 未授权 raw full-scene dump
- 低层全骨骼快照进入主感知链

## 5. Provider Request

建议定义统一请求对象：

```text
VLAProviderRequest
  request_id
  query_id
  consumer_kind
  subject_id
  multimodal_context_id
  cache_namespace
  time_window
  spatial_reference
  attention_context
  visual_artifact_refs
  depth_artifact_refs
  spatial_artifact_refs
  auditory_artifact_refs
  embodied_artifact_refs
  skeletal_artifact_refs
  structured_fact_refs
  scene_space_model_refs
  occupancy_refs
  requested_outputs
  timeout_ms
  output_schema_version
```

`multimodal_context_id` 和 `cache_namespace` 必须继承 `PerceptionQueryFrame` 的隔离规则。

## 6. Provider Result

建议定义统一结果对象：

```text
VLAProviderResult
  result_id
  request_id
  query_id
  provider_id
  model_id
  model_version
  advisory
  status
  findings
  grounded_refs
  spatial_claims
  confidence
  uncertainty
  missing_inputs
  conflicts_with_l1
  conflict_refs
  expires_at
  cache_key
  trace_ref
```

其中：

- `advisory` 必须为 `true`
- `status` 至少支持 `ok`、`timeout`、`provider_unavailable`、`artifact_missing`、`artifact_expired`、`low_confidence`、`schema_invalid`
- `spatial_claims` 只能表达假设或解释，不能表达 authority decision
- `conflicts_with_l1` 必须被显式保留，不能覆盖 L1 事实

## 7. 输出落点

VLA provider result 不直接给角色或司命主循环。

正确落点：

1. `VLAProviderResult`
2. `ModalityInterpretationResult(modality = visual_spatial)`
3. `CrossModalUnderstandingResult`
4. 角色专属 `CanonicalPerceptBundle` 或司命专属 percept bundle
5. 现有 `CharacterAgentRuntime` / `SimingRuntime`

角色消费结果时可以更新：

- local spatial state
- target state
- attention state
- Actor Scene Knowledge
- active perception requests

司命消费结果时可以更新：

- global situation interpretation
- fairness explanation
- intervention candidates
- minimal catalyst path inputs

二者不得共享私有上下文、缓存隐状态或推理历史。

## 8. 慢通路调度

VLA provider 只在触发条件成立时进入慢通路。

触发条件：

- high ambiguity
- cross modal conflict
- low confidence global situation
- expected target missing
- expected reachable but failed
- line of sight conflict
- active perception request
- Siming global situation review window

调度规则：

- per-owner queue
- character queue 和 siming queue 分离
- 同一 artifact fingerprint 去重
- 同一 query window 只保留最新有效请求
- timeout 后降级为 L1 structured facts
- 慢通路结果只影响下一拍或后续注意力，不影响当前 tick
- 队列满时丢弃最低优先级或最旧请求，并记录 trace

## 9. Cache 与去重

cache key 至少由以下内容组成：

- consumer kind
- subject id
- multimodal context id
- query time window
- spatial reference
- artifact refs hash
- structured fact refs hash
- provider id
- model version
- output schema version

禁止：

- 角色和司命共享 cache namespace
- 多角色共享私有 patch cache
- provider 保存跨主体 hidden state
- 用 cache 命中结果覆盖更新鲜的 L1 truth

## 10. 不确定性、过期和冲突

VLA 结果必须显式表达：

- 置信度
- 缺失模态
- 缺失 artifact
- artifact freshness
- TTL / expires_at
- 与 L1 冲突
- 与其他模态冲突
- 是否需要主动感知补查

当 VLA 与 L1 冲突时：

- L1 / authority 保持优先
- VLA 结果进入 uncertainty 和 conflict refs
- fusion 可以产生 active perception request
- 不得直接修改 world truth

## 11. Trace 与 Replay

每次 VLA provider 调用必须记录：

- request id
- query id
- consumer kind
- context id
- provider id
- model id/version
- input artifact refs
- structured fact refs
- cache hit/miss
- timeout/degrade reason
- result status
- output schema version
- consumed bundle id

trace 必须足以证明：

- VLA 没有阻塞主循环
- VLA 没有写 authority
- 角色和司命上下文隔离
- provider 只消费 artifact refs
- 失败可以降级
- advisory 结果进入了统一感知协议

## 12. Verification 要求

完整实现不得只证明 schema 存在。

至少要证明：

- 真实或 mock provider 被 scheduler 调用
- `PerceptionQueryFrame` 被转换为 `VLAProviderRequest`
- provider result 被转换为 `ModalityInterpretationResult`
- advisory/conflict/freshness 字段保留到最终 bundle
- timeout 不影响当前 tick
- cache namespace 隔离
- 角色和司命不会共享私有 context/cache/history
- ESM / L1 / world truth 未被 VLA 覆盖

## 13. 一句话收束

当前项目可以使用开源多模态/VLA 能力，但只能把它们包进 VLA provider backend：它产出受控、可追踪、可降级的 advisory 空间视觉理解结果，并通过现有统一感知协议进入角色和司命私有多模态栈。
