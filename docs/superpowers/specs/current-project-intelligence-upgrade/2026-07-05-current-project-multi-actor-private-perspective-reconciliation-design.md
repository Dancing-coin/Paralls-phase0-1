# 当前项目多角色私有视角分发与协调设计

- 状态：`proposed`
- 日期：`2026-07-05`

## 1. 目标

把当前单 actor 入口的感知 bridge 升级为支持：

- 同一世界 capture
- 多个 actor 私有投影
- 各自独立视角
- 同时又不混淆对象与时序

## 2. 当前问题

`L1RuntimePerceptionBridge.consume_projected_facts(...)` 现在直接接单个 `actor_id`。

这足以做单 actor bundle 装配，不足以证明：

- 同拍多 actor
- 同世界状态
- 不同主体视角
- 同对象不同视角冲突

## 3. 目标结构

```text
shared world capture
-> actor A projection
-> actor B projection
-> actor C projection
```

每个 actor projection 必须保留：

- `actor_frame_ref`
- `camera_frame_ref`
- `listener_frame_ref`
- `capture_id`
- `character_mm:*`

## 4. 规则

1. 允许共享 `capture_root_id`
2. 不允许共享 actor-private context
3. 允许同物在不同 actor 下形成不同属性判断
4. 但必须能证明它们仍指向同一 `world_anchor_id`

## 5. Siming 的位置

`Siming` 不直接复用任何 actor 私有视角输入。

它应消费：

- 同一 world capture 的公共证据
- multi-actor patch 汇总
- `siming_mm:*` 独立输入

## 6. 验证要求

至少覆盖：

- actor A/B 同拍看同物但视角不同
- actor A/B 同拍看近邻不同物
- actor A/B 私有 context 不混
- Siming 汇总 multi-actor patch 时不丢对象身份
