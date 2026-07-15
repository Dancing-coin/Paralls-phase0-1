# 当前项目 Siming Global Situation Layer 子规格

- 日期：`2026-07-02`
- 状态：`implemented-and-verified`
- 上位规格：[2026-06-29-current-project-siming-multimodal-and-global-situation-design.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/2026-06-29-current-project-siming-multimodal-and-global-situation-design.md)

## 1. 目标

把司命现有 L1 bundle ingestion、read model 和 intervention candidate 扩展为完整的全局态势 layer。

该层服务 `SimingRuntime`，但不替代司命主循环。

## 2. 定位

`SimingGlobalSituationLayer` 是司命私有态势层，不是新的司命 runtime 宿主。

它消费：

- authority events
- `world_result`
- L1 projected facts
- Siming percept bundle
- VLA advisory global findings
- multi-actor spatial patches
- environment and evidence events

它输出：

- global situation snapshot
- fairness pressure signals
- visibility imbalance
- intervention candidate enrichment
- minimal catalyst path inputs
- workbench explanation updates

它不得：

- 读取角色私有多模态 cache
- 替角色选择最终行为
- 直接控制低层动作
- 写 world truth

## 3. 全局 Patch

司命 patch 与角色 patch 不同：

- 时间窗更宽
- 空间范围更大
- 关注多角色分布
- 关注信息不对称
- 关注暴露链、证据链、参与窗口

Siming global patch 只能引用公共事实、authority/world results 和司命私有多模态上下文。

## 4. Fusion

建议分层：

1. event aggregation
2. multi-actor spatial patch assembly
3. global multimodal interpretation
4. fairness/situation fusion
5. intervention candidate enrichment

fusion 输出必须保留：

- source refs
- uncertainty
- conflicts
- freshness
- advisory marker
- reason tags

## 5. 状态生命周期

global situation snapshot 支持：

- open situation
- update situation
- escalate pressure
- mark stale
- resolve
- archive trace

## 6. Verification 要求

必须证明：

- 多角色公共 patch 可形成 Siming global situation
- 司命上下文与角色上下文隔离
- VLA advisory 只增强态势判断
- intervention candidate 能携带 situation evidence
- 司命不写 world truth

## 7. 一句话收束

`SimingGlobalSituationLayer` 是司命的私有全局态势层：它从公共事实、authority 事件、世界结果和 advisory 多模态线索中形成可追踪的导演视角态势，而不是共享角色脑或改写世界。
