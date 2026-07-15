# 当前项目事实上抛链路与多模态链路关系设计

- 状态：`design-governance-accepted; covered-by-perception-input-alignment-verification`
- 日期：`2026-07-05`

## 1. 目标

明确当前仓库两条感知链的分工：

- 事实上抛链路
- provider / `PQF` / `CanonicalPerceptBundle` 多模态链路

并明确：

- 事实上抛链路已经存在轻量融合层
- 多模态链路已经存在强融合层
- 新的 identity / alignment 设计是这两条链共享的前置层，而不是第三条并行融合层

## 2. 事实上抛链路定义

事实上抛链路是：

```text
RawFactEvent
-> fact_router
-> CandidatePerceptEvent
-> CharacterPerceivedEvent
```

它的核心职责：

- 处理稳定、离散、已规则化的感知结论
- 作为当前主感知链
- 直接服务 authority/public route 或 actor-private percept

## 3. 事实上抛链路的融合层

事实上抛链路并非“没有融合层”。

它当前已有三层轻量融合：

1. `fact_router`
   - 不同 fact family 的路由归一化
2. `CandidatePerceptEvent`
   - 不同 fact family 的统一候选感知语义
3. `per_character_percept_filter`
   - actor-private 过滤与私有化融合

因此，事实上抛链路应被视为：

- 轻量事件语义融合链

## 4. 多模态链路定义

多模态链路是：

```text
SampleInputRef
-> PerceptionQueryFrame
-> CanonicalPerceptBundle
-> Character / Siming runtime
```

可选增强：

```text
PQF
-> VLAProviderRequest
-> VLAProviderResult
-> VLA percept bridge
-> merge back into CanonicalPerceptBundle
```

它的核心职责：

- 处理 patch / 连续状态 / 不确定材料
- 形成统一多模态 query
- 形成统一 percept bundle
- 为 Character / Siming 提供增强输入

因此，多模态链路应被视为：

- 强融合输入链

## 5. 两条链的关系

它们不是替代关系，也不应该同时被视为对等主链。

推荐定位：

1. 事实上抛链路
   - 主感知链
2. 多模态链路
   - 增强感知链

## 6. 与输入对齐层的关系

新增的输入对齐设计不是第三条链，也不是替代现有融合层。

它的职责是：

- 为事实上抛链路提供共同 capture 身份
- 为多模态链路提供共同 capture 身份
- 为后续 object/time identity reconciliation 提供前置条件

因此：

- identity / alignment 层是现有两条链的前置层
- 不应把它实现成新的并行融合器

## 7. 设计约束

1. 不应把 fact 链和 provider 链直接揉成单一原始链
2. 不应新增一个独立“总融合器”来和 bundle / fact 私有化并行竞争
3. 应先做输入 identity 对齐，再推进两条链的收敛
4. 若未来需要裁剪，应优先保留：
   - fact 链作为主链
   - 多模态链作为视觉/空间优先增强链

## 8. 验收

完整设计应能清楚回答：

- 事实上抛链路是否已有融合层
- 多模态链路是否已有融合层
- 新的 alignment 设计是不是前置层
- 两条链在完整实现里各自扮演什么角色
