# VLA 与多模态链

状态：当前仓库专题架构文档

本文只讲一件事：`VLA` 在当前仓库里到底处于多模态链的什么位置、已经怎么用、还缺什么、
以及角色智能体和 `Siming` 分别如何消费它。

它不是一份理想态论文，而是按当前仓库实现事实写的维护者文档。

## 一句话结论

`VLA` 不是多模态总链本身，而是当前多模态链中的一条
`视觉 / 空间 advisory slow path`。

当前主链是：

```text
Godot providers
-> SampleInputRef
-> PerceptionQueryFrame
-> CanonicalPerceptBundle
-> Character / Siming runtime consumers
```

`VLA` 插在 `PerceptionQueryFrame` 之后：

```text
PerceptionQueryFrame
-> VLAProviderRequest
-> VLAProviderResult
-> VLA percept bridge
-> merge into CanonicalPerceptBundle
```

因此：

- 角色智能体不是“通过 VLA 才有多模态能力”
- `Siming` 也不是“只靠 VLA 才有多模态能力”
- 两者都先有自己的多模态主链
- `VLA` 只是在视觉/空间理解上增强这条主链

## 当前多模态主链

当前仓库已经把多模态主链定义为：

1. `Godot` 采样 provider 产出结构化 ref
2. `PerceptionQueryFrame` 把不同模态收成统一查询
3. `CanonicalPerceptBundle` 作为统一消费对象
4. 角色和 `Siming` 进入各自隔离的运行时上下文

关键代码：

- `backend/app/world_runtime/intelligence_upgrade.py`
- `backend/app/world_runtime/l1_perception_frame.py`
- `backend/app/world_runtime/l1_runtime_perception_bridge.py`

当前 provider kinds 在
`backend/app/world_runtime/intelligence_upgrade.py` 中固定为：

- `visual_patch`
- `spatial_patch`
- `auditory_context`
- `embodied_state`
- `skeletal_state`
- `environment_field`

这说明：

- 多模态输入的第一层是真实采样 ref，不是模型推理结果
- `VLA` 不是“统一多模态脑”
- `VLA` 只是其中一类模型增强能力

## VLA 的当前职责

当前仓库给 `VLA` 的职责边界非常明确：

- 从 `PerceptionQueryFrame`、provider refs、artifact refs、structured fact refs 生成视觉/空间理解结果
- 输出 `VLAProviderResult`
- 结果只能是 advisory-only
- 结果必须通过 bridge 合并回运行时 bundle
- 不能直接写 world truth、ESM authority、actor control

关键代码：

- `backend/app/world_runtime/vla_provider.py`
- `backend/app/world_runtime/vla_cache.py`
- `backend/app/world_runtime/vla_slow_path_scheduler.py`
- `backend/app/world_runtime/vla_model_registry.py`
- `backend/app/world_runtime/vla_percept_bridge.py`

关键边界：

- `VLAProviderRequest` 必须继承 `PQF` 的 `multimodal_context_id` 和 `cache_namespace`
- `VLAProviderResult` 强制 `advisory=True`
- `writes_world_truth / writes_esm_authority / controls_actor` 都必须为 `False`

也就是说，`VLA` 在当前仓库里不是：

- 角色智能体替代品
- `Siming` 替代品
- 全局共享脑
- 交互结算 owner
- 物理控制器

## 可视化架构图

```text
┌──────────────────────────────────── 多模态主链 ───────────────────────────────────┐
│                                                                                  │
│  Godot providers                                                                 │
│  visual / spatial / auditory / embodied / skeletal / environment                 │
│        │                                                                         │
│        v                                                                         │
│  ┌──────────────────────────────────┐                                            │
│  │ SampleInputRef                    │                                            │
│  │ 只记录 ref / freshness / throttle │                                            │
│  └───────────────┬──────────────────┘                                            │
│                  │                                                                │
│                  v                                                                │
│  ┌──────────────────────────────────┐                                            │
│  │ PerceptionQueryFrame              │                                            │
│  │ 时间窗 / 空间参考 / 注意力上下文 │                                            │
│  └───────────────┬──────────────────┘                                            │
│                  │                                                                │
│                  ├────────────── VLA 慢路径支链 ───────────────────────────────┐  │
│                  │                                                            │  │
│                  │   ┌──────────────────────────────┐                         │  │
│                  │   │ VLAProviderRequest            │                         │  │
│                  │   └──────────────┬───────────────┘                         │  │
│                  │                  v                                         │  │
│                  │   ┌──────────────────────────────┐                         │  │
│                  │   │ VLA provider / scheduler      │                         │  │
│                  │   └──────────────┬───────────────┘                         │  │
│                  │                  v                                         │  │
│                  │   ┌──────────────────────────────┐                         │  │
│                  │   │ VLAProviderResult             │                         │  │
│                  │   │ advisory only                 │                         │  │
│                  │   └──────────────┬───────────────┘                         │  │
│                  │                  v                                         │  │
│                  │   ┌──────────────────────────────┐                         │  │
│                  │   │ VLA percept bridge            │                         │  │
│                  │   └──────────────┴───────────────┘                         │  │
│                  │                                                            │  │
│                  v                                                            │  │
│  ┌──────────────────────────────────┐                                         │  │
│  │ CanonicalPerceptBundle            │<────────────────────────────────────────┘  │
│  │ 统一消费对象                      │                                            │
│  └───────────────┬──────────────────┘                                            │
│                  │                                                                │
│         ┌────────┴────────┐                                                       │
│         v                 v                                                       │
│  Character runtime   Siming runtime                                               │
│  character_mm:*      siming_mm:*                                                  │
│                                                                                  │
│  禁止：VLA 直接写 world truth / ESM authority / actor motion                      │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## VLA 对角色智能体的实际应用

对角色智能体，`VLA` 的作用不是替代 `Character L1/L2/L3/L4`，而是增强角色的视觉/空间理解。

当前最直接的应用点有 3 个：

1. 增强 `CanonicalPerceptBundle`
   - `VLA` 结果被 merge 进 bundle 的 `world_hypotheses`
   - 同时写入 `uncertainty["vla_advisory"]`

2. 增强 `Actor Scene Knowledge`
   - 角色会把 bundle 里的 `vla_advisory` 写入自己的场景知识层
   - 但它始终是 `source_kind="vla_advisory"`
   - 不能覆盖 `l1_projected_fact_ref`

3. 支持主动感知
   - 角色在冲突、过期、反复 reachability 失败时
   - 会触发新的 `ActivePerceptionRequest`
   - 重新进入 `PQF -> provider chain -> VLA advisory`

这意味着角色当前的多模态能力是：

- `CharacterPerceivedEvent`
- `SelfBodyPerceivedEvent`
- `PerceptionQueryFrame`
- `CanonicalPerceptBundle`
- `Actor Scene Knowledge`
- memory
- 可选 `VLA` 视觉/空间 advisory

不是：

- “角色 = VLA”

## VLA 对 Siming 的实际应用

`Siming` 的多模态输入范围比 `VLA` 更大。

当前 `SimingGlobalSituationLayer` 组装快照时会消费：

- `l1_projected_facts`
- `authority_events`
- `world_results`
- `environment_events`
- `evidence_events`
- `vla_global_findings`
- `multi_actor_patch`

也就是说，`VLA` 对 `Siming` 的角色是：

- 提供 `vla_global_advisory`
- 增加 `fairness_pressure`
- 参与 `conflict_refs`
- 但不替代 authority/public evidence/main situation inputs

所以 `Siming` 的多模态能力也不是“只靠 VLA”。

更准确地说：

- `Siming` 先有自己的 `siming_mm:*` 上下文
- 有自己的 `PQF / CanonicalPerceptBundle` 消费
- 同时还消费公开 world/authority/evidence 输入
- `VLA` 只是其中的视觉/空间增强证据

## 当前已接入与候选模型

按当前 registry，VLA 候选模型有：

- `qwen3-vl-plus`
- `qwen3-vl-local`
- `seed-vl-advisor`
- `openvla-action-head-research-only`

当前最适合 runtime 接入的，是前三个：

1. `qwen3-vl-plus`
   - 当前默认主目标
   - 适合作为第一条 HTTP VLA 路线

2. `seed-vl-advisor`
   - 适合作为第二条 HTTP 路线
   - 也适合在需要 provider diversity 时接入

3. `qwen3-vl-local`
   - 适合作为本地/离线路线
   - 更适合后续可重复验证和内网环境

当前不应该作为 runtime 主链接入的：

4. `openvla-action-head-research-only`
   - registry 已明确把它标成 research-only
   - 当前仓库禁止把它用于 actor/world/ESM runtime control

## VLA 当前的真实缺陷

如果目标是“尽可能完整地跑起来”，`VLA` 当前还差这些具体收口：

1. 真实 provider 还没 fully live-verified
   - 当前 readiness 主要停在 `blocked_missing_artifacts`、`configured_unverified` 或 contract-ready
   - 这不是没实现，而是 live adapter call 证据还不够

2. 仍然是 advisory-only
   - 这是设计上正确的
   - 但也意味着它还不能直接成为更强 world reasoning owner

3. 视觉/空间增强还没有完全覆盖听觉、身体、环境这些模态
   - 当前 `VLA` 主要还是 `visual_spatial`
   - 它不是全模态融合器

4. `VLA -> Character / Siming` 的作用主要还是 metadata 增强
   - 还不是高密度、长期、多轮的深度视觉记忆系统

5. 真实运行仍依赖 `PQF` 和 artifact refs 质量
   - 如果 provider refs 太弱
   - `VLA` 再强也只能给出低质量 advisory

## 推荐接入顺序

如果你接下来要把 `VLA` 这条线真正推向“更完整可运行”，建议顺序是：

1. 先接 `qwen3-vl-plus`
   - 最符合当前默认配置
   - 最容易和现有 `VLA_PROVIDER_*` 设置对齐

2. 再接 `seed-vl-advisor`
   - 作为第二 provider
   - 便于后续做 provider fallback / comparative trace

3. 最后补 `qwen3-vl-local`
   - 用于本地可重复验证
   - 降低 live provider 依赖

## 和“模型服务通道”的关系

`VLA` 不是模型服务通道本身。

两者关系是：

- `VLA 运行时通道`
  - 负责视觉/空间结果如何进入运行时并被安全消费

- `模型服务通道`
  - 负责 provider readiness、adapter、凭证、timeout、fallback 和真实调用证明

因此：

- `VLA` 文档回答“结果怎么进运行时”
- 模型服务文档回答“模型是不是能真实跑”

## 相关入口

- `docs/架构/运行时/模块/VLA运行时通道.md`
- `docs/架构/运行时/模块/模型服务通道.md`
- `docs/架构/运行时/模块/角色智能体.md`
- `docs/架构/运行时/模块/Siming.md`
- `docs/架构/运行时/图表/整体运行时数据流图.md`
- `backend/app/world_runtime/vla_provider.py`
- `backend/app/world_runtime/vla_percept_bridge.py`
- `backend/app/world_runtime/vla_model_registry.py`
- `backend/app/services/siming_global_situation.py`

## 当前维护结论

当前仓库里关于 `VLA` 最重要的维护心智模型应该是：

- `VLA` 是多模态体系中的视觉/空间增强支链
- 它已经进入 runtime
- 它不拥有 authority
- 它不替代角色脑
- 它不替代 `Siming`
- 它既服务角色，也服务 `Siming`
- 但服务方式都是“增强已有多模态主链”，而不是独立接管推理
