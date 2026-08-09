# 全域架构导航

状态：`incremental architecture guidance; canonical navigation for August analysis`

本目录不是新的运行时模块。它为 `docs/8月分析` 提供唯一的系统分层、责任和
文档导航，避免把世界本体、角色心智、创作控制面与具体玩法混在一个“玩法系统”
目录中。

## 当前运行时基线

本目录叠加在 [架构总纲](../../架构/整体架构.md)、
[运行时总览](../../架构/运行时/运行时总览.md)、
[运行时覆盖矩阵](../../架构/运行时/运行时覆盖矩阵.md) 与
[Gameplay Foundation 领域结算](../../架构/运行时/模块/GameplayFoundation与领域结算.md)
之上。后四者记录当前代码 owner、已验证范围和现有提交脊柱；本目录只能把未覆盖的
领域标为 `planned`/`discussion` 并给出增量收口方向。

因此，`World Record Authority`、`Settlement/Scheduler Authority`、组织/政府 authority、
动态市场和 `SimulationClock` 不是这里新建的并列 runtime。它们若进入实现，必须扩展
现有 `world_runtime`、ESM、Gameplay authority、`GameplayEventStore` 和受限镜像路径，
并由正式 spec/plan 与 Harness 证据收口。

1. [00-系统边界与责任矩阵.md](00-系统边界与责任矩阵.md)
2. [../世界基础设施增量指导/README.md](../世界基础设施增量指导/README.md)
3. [../角色与社会投影增量指导/README.md](../角色与社会投影增量指导/README.md)
4. [../玩法系统/README.md](../玩法系统/README.md)
5. [../玩法系统/社会与制度玩法/README.md](../玩法系统/社会与制度玩法/README.md)
6. [../创作与运营/README.md](../创作与运营/README.md)
7. [../架构审计/README.md](../架构审计/README.md)

定义权限、发布和闭源边界的规范来源分别是
[10-创作者权限与闭源控制面方案.md](../10-创作者权限与闭源控制面方案.md) 和
[11-全面闭源核心保护与创作者控制面方案.md](../11-全面闭源核心保护与创作者控制面方案.md)；
本目录中的领域文档只能在不冲突的前提下引用它们。
