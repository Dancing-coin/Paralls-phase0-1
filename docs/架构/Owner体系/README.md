# Owner 体系

状态：`current implementation mapping + planned architecture closure`

本目录整理 Owner、角色智能体、规则结算、UE 高频实现以及 Workflow/WRK 的统一边界。它回答四个问题：

1. 哪个模块拥有哪类世界事实？
2. 公式、阈值和状态效果由谁计算与提交？
3. 多个 Owner 如何协作而不产生第二套真相账？
4. 角色的静态档案、权威动态状态和主观心智如何接入同一条命令—结算—投影链？

## 文件导航

| 文件 | 内容 | 状态 |
| --- | --- | --- |
| [01-Owner分类、注册与当前实现对照](01-Owner分类、注册与当前实现对照.md) | Foundation/Atomic/Composite 分类、当前 Paralls authority 对照和缺口 | current + planned |
| [02-角色档案、状态与Owner对接](02-角色档案、状态与Owner对接.md) | 静态档案、权威动态事实、角色私有心智状态和两类需求的接入 | current + planned |
| [03-规则结算、跨Owner协作与UE-WRK边界](03-规则结算、跨Owner协作与UE-WRK边界.md) | 公式/条件模型、原子批次、开放义务、UE 适配和 Workflow/WRK | current + planned + deferred |

## 共同结算脊柱

```text
玩家 / 角色智能体 / 群体模拟 / 脚本
  -> typed Command 或受限 proposal
  -> 目标 Owner 校验公式输入、前置条件和 revision
  -> AtomicEventBatch
  -> GameplayEventStore
  -> committed events + receipt + outbox
  -> replay/checkpoint + filtered projection
  -> 角色智能体、群体模拟、UE 表现和其他合法消费者
```

`GameplayEventStore` 是提交后历史来源，不是万能玩法 Owner；`CharacterAgent` 是意图和心智运行时，不是世界真相 Owner；`WRK` 是时间、预算、调度、交接和恢复组织，不是超级写入器。

## 阅读与证据边界

- 当前实现总基线：[GameplayFoundation 与领域结算](../运行时/模块/GameplayFoundation与领域结算.md)。
- 角色心智边界：[角色智能体](../运行时/模块/角色智能体.md)。
- 当前自身状态投影仍有计划项：[自身状态感知与具身反馈设计](../../10月分析/角色/06-自身状态感知与具身反馈设计.md)。
- WRK 目标边界：[前后架构差异与世界运行内核规格](../../10月中旬分析/群体模拟升级/规格/06-前后架构差异与世界运行内核规格.md)。
