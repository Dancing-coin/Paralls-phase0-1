# P5后续能力基础推进：共享前置与 P6/P7 衔接

状态：`F0 基线完成；F1A-F2 全量实现待执行；不授权 P6/P7`

这不是第八阶段，而是第五阶段做完以后必须补齐的一组共享前置。它把八月分析里还没有进入 P1-P5 推进文档的内容，整理成可以交给 formal spec、plan 和 Harness 的工作包。

## 固定路线

```text
P1 -> P2 -> P3 -> P4 -> P5
  -> F0 基线 -> F1A/F1B/F1C 契约 -> F2 证据门 -> 开工证据门
  -> P6 创作者控制面 -> P7 文明/世界模型/机器人研究
```

## 这组文档要解决什么

| 缺口 | 补法 | 进入哪个后续阶段 |
| --- | --- | --- |
| P1-P5 证明范围不清 | F0 逐项证据台账 | 所有后续工作 |
| 世界语义、因果、调度设计没有共同合同 | F1A 提案/版本/因果/时间请求 | P6 包校验、P7 提案 |
| 社会、知识、家庭、隐私设计散落 | F1B 投影/范围/来源/过滤合同 | P6 authoring scope、P7 只读报告 |
| 玩法包发布和闭源边界只停留在设想 | F1C manifest/权限/激活/回滚 | P6C/P6D |
| 后续实现没有统一证明标准 | F2 Harness/回放/拒绝零写入/审计门 | P6/P7 全部 |

## 周计划

| 时间 | 工作 | 结束条件 |
| --- | --- | --- |
| 第 1 周 | F0 证据基线 | 每个设计项有状态、owner、证据和缺口 |
| 第 2-3 周 | F1A、F1B、F1C 并行设计 | 三份合同都绑定已有 owner 和事件路径 |
| 第 4 周 | F2 证明口径 | 每个后续 track 都有 profile 和证据清单 |
| 第 5 周 | P6/P7 开工证据门 | 确认 P6A-D、P7A-D 的开工条件和责任人 |

## 下一阶段怎么接

- P6A/P6B：等待 F0、F1A、F1B 的边界和权限证据；可以提前写适配器设计。
- P6C/P6D：必须等待 F1C、F2，以及激活、回滚、审计、回放证据。
- P7A-D：可以提前准备只读研究材料，但正式工作必须等待 P6D 治理证据，再通过自己的分支回放、可复现和机器人安全门禁。

## 总非目标

不创建第二 runtime、event store、bus、clock、scheduler、NPC truth store 或 social truth store；不允许 client、模型或 Siming 直接写世界；不做任意代码执行、完整文明模拟或完整机器人运行时。

## 导航

1. [F0 实现证据与缺口基线](01-F0实现证据与缺口基线.md)
2. [F0 八月分析逐文件覆盖台账](07-F0八月分析逐文件覆盖台账.md)
3. [F1A 语义规则因果与调度门](02-F1A语义规则因果与调度门.md)
4. [F1B 社会知识隐私投影门](03-F1B社会知识隐私投影门.md)
5. [F1C 玩法包版本激活与闭源边界](04-F1C玩法包版本激活与闭源边界.md)
6. [F2 回放隐私零写入与审计门禁](05-F2回放隐私零写入与审计门禁.md)
7. [P6/P7 开工证据门](06-P6P7命名与顺序决策门.md)

对应 formal spec/plan 见 [post-p5-capability-foundation specification tree](../../superpowers/specs/world-character-siming-authority-mainline/post-p5-capability-foundation/README.md) 和 [plan tree](../../superpowers/plans/world-character-siming-authority-mainline/post-p5-capability-foundation/README.md)。
