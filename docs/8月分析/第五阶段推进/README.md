# 第五阶段推进：RPG 与社会玩法域扩展

状态：`phase-five workbench; incremental guidance; non-authorizing until formal spec/plan`

第五阶段把前四阶段的角色、社会投影、经济和世界运行能力扩展为可玩的 RPG/剧本杀闭环。
它不是重新实现 Character Core、ESM 或 Gameplay Foundation，而是补齐任务、证据、关系、
知识、调查、潜行和冲突等领域 owner。

```text
P4 commercial ecosystem
  -> P5A quest/objective/evidence
  -> P5B relationship/reputation/knowledge projection
  -> P5C action/perception/stealth/conflict
  -> P5D RPG investigation vertical slice
  -> P6 creator control plane and package publishing
```

## 1. 可复用与缺口

| 可复用基础 | 当前缺口 | P5 增量 |
| --- | --- | --- |
| Character Core L1-L4、memory、needs/affect/goal、privacy projection | 通用任务目标、证据链、阶段推进 | Quest/Story authority 与 evidence projection |
| action intent、affordance、skill/ability、structured failure | 关系/声望/身份/知识在玩法中的正式结算 | Social/Knowledge projection contracts |
| 物品、产权、状态、effect/resistance、mirror/replay | 调查、潜行、冲突的跨域事实链 | bounded action/conflict adapters 和 RPG vertical slice |

## 2. 非目标

- 不把 CharacterAgent 输出直接当作任务完成、关系变化或伤害结果；
- 不创建第二个任务/社会 event store；
- 不在 P5 解决文明政治、宏观金融或世界模型生成；
- 不把 Godot 表现节点作为证据、战斗或潜行真相；
- 不强迫所有玩法开启 Survival、关系或冲突模块，继续使用可关闭的 mode/ruleset profile。

## 3. 正式化路径

建议建立 P5A quest/evidence、P5B social/knowledge、P5C action/conflict、P5D RPG vertical
spec 与对应 Harness profile。每个 domain 只扩展已有 owner，跨域使用 typed proposal、
revision pinning、atomic settlement 和 scope-filtered mirror。

文档导航：

1. [01-第五阶段范围与玩法层边界.md](01-第五阶段范围与玩法层边界.md)
2. [02-任务、证据、关系与知识协作契约.md](02-任务、证据、关系与知识协作契约.md)
3. [03-调查、潜行与冲突结算契约.md](03-调查、潜行与冲突结算契约.md)
4. [04-RPG参考包与第五阶段门禁.md](04-RPG参考包与第五阶段门禁.md)

正式 SDD 入口：
[Phase Five RPG And Social Gameplay Specification Tree](../../superpowers/specs/world-character-siming-authority-mainline/phase-five-rpg-social-gameplay/README.md)
；对应实施计划见同名 plan tree。当前仍为 `design-only; implementation not authorized`。
