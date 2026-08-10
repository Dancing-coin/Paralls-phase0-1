# Phase Three Population Continuity Execution Prompt

将以下内容作为已获 P3 套件整体实现授权的实施代理初始提示词使用。本提示词不覆盖
`AGENTS.md`、P3 specs 或 matching plans；冲突时以它们为准。

```text
你负责 Paralls Phase Three Population Continuity 的完整执行套件。P3 只在 P2
bakery-authored-agents fresh-green 后启动，目标是让已有 CharacterProfile 角色在
受治理的持续世界模式中激活、产生批量 intent 并完成面包店街区垂直样板。P3
不是新 NPC runtime、不是影子角色系统、不是动态市场。

开始前必须读取：
- AGENTS.md、docs/INDEX.md、docs/harness.md、docs/ai-engineering-workflow.md；
- P1D 与 P2D 的 spec/plan、最新 predecessor Harness reports；
- phase-three-population-continuity spec/plan README；
- P3A、P3B、P3C、P3D 每份 spec 与 matching implementation plan；
- docs/8月分析/第三阶段推进全部文件；
- 真实 CharacterProfile registry、Character Core L1-L4、world_runtime、
  RuntimePopulationPolicy、Organization/Production/Inventory/Economy/Survival/Government、
  GameplayCommandEnvelope、SettlementPlan、GameplayEventStore/replay/checkpoint/outbox owners。

前置门禁：先运行 P2、P1D predecessor profiles。任一不是 fresh-green，停止 P3。

唯一实施顺序：
P3A profile activation/identity
  -> P3B world mode/cadence/obligation continuity
  -> P3C batch intent/continuity merge
  -> P3D bakery district population vertical slice

P3A：
- 先写 profile resolution、package/scope grant、stale/duplicate、suspend/requeue、
  zero-write tests；
- 使用同一 CharacterRecord/CharacterProfile，activation 只能是 proposal，经 authority
  形成 committed lifecycle fact；
- 禁止 NpcState、synthetic identity、shadow body/inventory/account、profile writer。

P3B：
- 先写 pause/resume、mode revision、Survival disabled/narrative/simulation、budget、
  degradation、catch-up、overdue 和 zero-write tests；
- 只扩展既有 world_runtime/policy entry point，catch-up 必须由 checkpoint + committed tail
  确定性重建；
- 禁止 SimulationClock、implicit tick、后台 wakeup、scheduler 直接结算任何 domain。

P3C：
- 先写 shuffled-order determinism、duplicate batch、stale stream、contention、
  defer/requeue、privacy denial 和 atomic failure tests；
- planner 只能生成 profile-scoped GameplayCommandEnvelope，包含 policy/package revision、
  expected revisions、idempotency/correlation 和 claim refs；
- authority 才能构造 SettlementPlan，并由 GameplayEventStore.append_batch() 唯一提交；
- 禁止 planner persistence、planner append、second transaction path、浮点随机 merge。

P3D：
- 只使用既有 registered profile、organization、facility、inventory、quote、government facts
  构造 bakery district fixture；
- 覆盖 activation/suspend/requeue、work/supply/inspection、contention rejection、due
  obligation、pause/catch-up、public/private mirror 和 full/checkpoint-tail replay；
- customer demand、supplier quote、competitor profile 在 P4 前保持受限；
- 禁止 fixture-only owner、order book、auction、价格发现、跨区贸易、宏观经济。

每个阶段都必须：先 failing test -> 最小实现 -> focused tests -> predecessor Harness ->
当前阶段 Harness -> docs/mainline Harness；输出 receipt、revision vector、replay hash、
scope/redaction、zero-write 和 stop reason 证据。若任何阶段需要新 store/bus/scheduler/
settlement owner 或 CharacterAgent/PopulationPlanner/Godot/model canonical write，立即停止并报告。

最终只有 P3A-P3D 全部 fresh-green 后，才能汇报 P3 完成并请求 P4 授权。
```

## Usage Constraint

这份提示词对应整个 P3 plan set，不应与 P3A-P3D 子 plan 分开并行执行。
