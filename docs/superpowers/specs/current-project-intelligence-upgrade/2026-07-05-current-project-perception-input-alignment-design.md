# 当前项目感知输入对齐层设计

- 状态：`implemented-and-focused-verified-parent-spec`
- 日期：`2026-07-05`

## 1. 背景

当前仓库并行存在两条感知输入链：

1. 上抛器 / 事实上抛器主链  
   `RawFactEvent -> fact_router -> CandidatePerceptEvent -> CharacterPerceivedEvent`
2. provider / `PerceptionQueryFrame` / `CanonicalPerceptBundle` 多模态链  
   `SampleInputRef -> PQF -> CanonicalPerceptBundle -> Character / Siming runtime`

这两条链当前都能工作，但共享输入基准的能力不足：

- 没有统一 `capture_id`
- 没有统一“同一拍”的时间身份
- 没有统一 actor/camera/listener 视角引用
- 没有统一 target / focus 上下文

这会导致：

- 同一对象在 fact 链和 provider 链中的结果难以判断是否来自同一拍
- 多角色并行私有感知无法严格证明“同一世界状态、不同主体视角”
- `VLA`、主动感知、冲突重查和 `Siming` 全局态势容易出现伪冲突

## 2. 设计目标

本设计不要求立刻合并两条链，而是要求：

1. 让两条链在输入阶段共享统一时空 envelope
2. 让多角色私有感知建立在视角一致基础上
3. 保持 `character_mm:*` 与 `siming_mm:*` 上下文隔离
4. 让后续裁剪 provider 或裁剪 fact 路线有一致证据

## 3. 非目标

本设计不直接解决：

- `CharacterAgent L4 -> CharacterActor` 最终单一路径收口
- 真实 `VLA` provider live proof
- 完整 actor-private hearing attribution
- 真实 TTS provider
- authority event bus 改造

## 4. 核心判断

### 4.1 两条链暂时并存是允许的

当前代码事实下，两条链并非完全重复：

- fact 链擅长稳定、离散、结构化结论
- provider 链擅长局部 patch、连续状态、不确定输入和多模态增强

因此当前不建议直接删除其中一条。

### 4.2 当前最关键缺口不是删链，而是输入对齐

如果没有统一输入 capture：

- fact `t0` 与 provider `t0+delta` 的结果会被误判成同拍冲突
- `char_a` 与 `char_b` 会共享 zone/time 但不共享真正视角锚点
- `VLA` advisory 与 `CharacterPerceivedEvent` 很难证明是否是同一次观察

因此收口顺序必须是：

1. 先做输入对齐
2. 再做链路收敛

## 5. 统一输入对象

建议新增一层轻量输入对象：

- `PerceptionInputFrame`
  或兼容别名
- `PerceptionCaptureFrame`

推荐正式名：`PerceptionInputFrame`

### 5.1 最小字段

```text
capture_id
consumer_scope
subject_id
started_at / ended_at
room_id / scene_id / zone_id
actor_frame_ref
camera_frame_ref
listener_frame_ref
target_actor_ids
target_object_ids
target_environment_ids
reason_tags
source_fact_refs
source_provider_refs
```

### 5.2 语义

`PerceptionInputFrame` 不是：

- authority 事件
- 最终 percept bundle
- model output

它只定义：

- 同一主体在同一时间窗中的感知输入坐标系

## 6. 与现有两条链的关系

### 6.1 fact 链

fact emitter 继续保留，但要让以下对象显式引用同一 `capture_id`：

- `RawFactEvent`
- `CandidatePerceptEvent`
- `CharacterPerceivedEvent`

这样 fact 链仍是主流感知链，但不再脱离统一 capture 身份。

### 6.2 provider 链

provider 链继续保留，但要让以下对象显式继承同一 `capture_id`：

- `SampleInputRef.runtime_source_refs`
- `PerceptionQueryFrame`
- `CanonicalPerceptBundle`

这样 provider 链会从“并行主链”收敛成“共享同一输入基准的增强链”。

## 7. 多角色私有视角要求

当前 `L1RuntimePerceptionBridge` 只以单个 `actor_id` 为入口，不足以证明多角色同拍私有分发。

后续收口必须满足：

1. 同一世界状态可被多个角色引用同一 `capture window`
2. 每个角色仍保留自己的：
   - `actor_frame_ref`
   - `camera_frame_ref`
   - `listener_frame_ref`
   - `character_mm:*` context
3. `Siming` 使用独立 `siming_mm:*` context

因此，未来多角色输入不应只是“对不同 actor 重复调用 bridge”，而应是：

```text
shared world-time capture
-> per-actor PerceptionInputFrame
-> per-actor fact/provider projection
-> per-actor Character bundle
```

## 8. 对 VLA 的影响

`VLA` 不应直接读取共享世界，而应继续：

- 继承 `PQF`
- 继承对应 `context_id`
- 继承 `cache_namespace`

新增 `capture_id` 后，`VLAProviderRequest` 也应显式绑定该 capture。

这样可判断：

- 这个 `VLAProviderResult` 是否对应同一拍观察
- 与 fact 链的关系是“同拍补充”还是“后续重查”

## 9. 对 Siming 的影响

`Siming` 不直接读取角色私有输入。

但它可以读取：

- 同一 capture window 下的公共 evidence
- 对应的 `siming_mm:*` provider / bundle 输入
- 对应的 `VLA global advisory`

因此它也需要统一 capture 身份，但不能复用角色私有 context。

## 10. 对运行时复杂度的判断

这个设计的目的不是扩复杂度，而是防止复杂度无序增长。

如果继续允许双链并行而不做输入对齐：

- 复杂度会持续上升
- 冲突解释成本会越来越高

如果先做输入对齐：

- 双链仍可暂存
- 但后续裁剪 provider / fact 都会有统一基准

## 11. 推荐实施顺序

1. 新增 `PerceptionInputFrame`
2. 让 fact emitter 输入写入 `capture_id`
3. 让 provider refs 继承 `capture_id`
4. 扩展 `PerceptionQueryFrame` 保留 `capture_id`
5. 扩展 `CanonicalPerceptBundle` 保留 `capture_id`
6. 扩展 `L1RuntimePerceptionBridge`，从“单 actor assembler”升级为“按 capture + actor 组装”
7. 让 `VLAProviderRequest / Result`、主动感知、ASK、`SimingGlobalSituation` 读取这一身份

## 12. 最终判断

当前最值得推进的不是再增加新的 provider 或新的事实 family，而是：

- 先让两条链共享统一输入对齐层

这会成为后续所有感知收口、主动感知、VLA 对齐和多角色私有视角分发的前提。
