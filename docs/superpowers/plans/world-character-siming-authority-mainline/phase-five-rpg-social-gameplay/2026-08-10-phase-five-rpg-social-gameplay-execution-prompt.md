# Phase Five RPG And Social Gameplay Execution Prompt

仅在 P5 套件整体获得实现授权且 P4D fresh-green 后使用。

```text
你负责 Paralls Phase Five RPG And Social Gameplay 的完整执行套件。目标是在 P1-P4
Character Core、Gameplay authority、经济/组织和连续世界证据上增加任务、证据、关系、
知识、调查、潜行和 bounded conflict。P5 不是重建 Character Core、第二 quest store、
完整战斗引擎或 Godot truth runtime。

开始前读取：
- AGENTS.md、docs/INDEX.md、docs/harness.md、docs/ai-engineering-workflow.md；
- P1D、P2D、P3D、P4D specs/plans 与 fresh reports；
- phase-five-rpg-social-gameplay spec/plan README；
- P5A-P5D specs 与 matching plans；
- docs/8月分析/第五阶段推进全部文件；
- Character Core L1-L4/memory/affect/goal、action intent/affordance、skill/ability、
  perception/evidence、relationship/knowledge、status/body/resource/effect/resistance、
  ownership/economy、GameplayCommandEnvelope、SettlementPlan、event/replay/mirror owners。

前置门禁：运行 P4D、P3、P2、P1D predecessor profiles；任一非 fresh-green 则停止。

唯一顺序：
P5A quest/objective/evidence
  -> P5B relationship/reputation/knowledge
  -> P5C investigation/stealth/bounded conflict
  -> P5D RPG investigation vertical slice

P5A：
- 先测 evidence provenance、wrong subject、visibility/expiry、duplicate、stale objective、
  reward rejection、zero-write；
- quest package 只定义 objective/prerequisite/evidence/transition/reward proposal；
- CharacterAgent、Godot、叙事文本不能自证完成；奖励必须由既有 skill/inventory/economy/relation
  owners 通过 authority settlement。

P5B：
- 先测 public/private redaction、conflicting observation、confidence/decay、revoked visibility、
  stale revision、zero-write；
- objective relationship facts 与 actor-private beliefs 分离；Character Core 继续拥有 private
  memory/affect/goal；
- 禁止 universal graph coordinator、private memory direct mutation、AI reputation writer。

P5C：
- 先测 perception evidence、skill gate、resistance、status revision、alarm、nonlethal effect、
  structured failure、atomicity、privacy；
- action envelope pin actor/target/affordance/skill/perception/effect/status/risk/expected revisions；
- authority revalidate 后才通过 GameplayCommandEnvelope -> SettlementPlan -> append_batch() 调用
  body/resource/status/effect/ownership/relation owners；
- 禁止实时战斗、animation hit truth、second conflict store、direct health/status write。

P5D：
- 只构造 bounded investigation：private clue、public relation、skill observation、stealth/alarm、
  nonlethal consequence、quest transition；
- Survival 必须由 ruleset profile 可关闭或 narrative-only；
- 覆盖 success/hidden-clue reject/structured failure/public-private mirror/full/checkpoint-tail replay；
- 禁止完整 RPG、开放式剧情、实时战斗、fixture truth。

每阶段遵循 failing test -> minimal implementation -> focused Harness -> predecessor Harness ->
docs/mainline。汇报 evidence provenance、permission/redaction、decision/receipt、replay hash、
failure zero-write 和未验证项。若需要新任务/社会/冲突 authority 或 Godot writer，停止报告。
只有 P5A-P5D 全绿后才能请求 P6。
```

## Usage Constraint

这份提示词对应整个 P5 plan set；P5D 通过不等于通用 RPG 完成。
