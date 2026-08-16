# Post-P5 Capability Foundation Full Execution Prompt

仅在 P5 的前置 profile 为 fresh-green，且本树获得逐轨实现授权时使用。本提示词现在要求把 post-P5 capability foundation 的全部对应 spec 和 plan 实现完毕；不能以文档完成、窄基础 profile 通过或“已有局部 owner”代替完整实现。

```text
你负责 Paralls 的 P5 后续能力基础全量执行。目标是把八月分析中尚未进入 P1-P5 的共享契约真正实现到既有 owner，并完成 F0、F1A、F1B、F1C、F2 和 DG 的全部 spec/plan、代码、测试、Harness 和证据。它不是新建第八阶段；P6/P7 仍然只能在 DG 绿灯后另行执行。

开始前读取：
- AGENTS.md、docs/INDEX.md、docs/harness.md、docs/ai-engineering-workflow.md；
- post-p5-capability-foundation 的 spec/plan README、F0-F2/DG 全部文档；
- docs/8月分析/P5后能力基础推进/ 全部文件，尤其 07-F0八月分析逐文件覆盖台账；
- P1-P5 specs/plans 和对应 fresh Harness reports；
- world_runtime、ESM、Character Core、GameplayEventStore.append_batch()、outbox/replay、Patch/runtime、Siming event path 和 scoped mirror 的既有边界。

开始前先运行：
python scripts/verification/harness.py --profile post-p5-capability-foundation-docs
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile boundaries

然后顺序重跑并记录 P5A/P5B/P5C/P5D predecessor profile。任一失败先修复或将对应轨道标为 blocked，不得继续把后继轨道说成完成。

唯一顺序：F0 -> F1A/F1B/F1C（可并行设计，但实现需各自授权） -> F2 -> DG。

F0：完成并审核逐文件台账、owner map、gap register、claim ledger、evidence manifest。每个非阶段推进的八月分析文件必须有状态、owner、已有证据、缺口、后续轨道和风险。

F1A：实现完整 semantic/entity/effect/rule/dependency/causal/time-request contract，而不是只复用 Patch Rule Runtime。必须有 typed schema、canonical digest、owner/capability/revision pin、依赖图、循环/冲突/过期/未授权拒绝、因果解释投影、时间请求转既有 authority 的 adapter、幂等、full/checkpoint-tail replay 和拒绝零写入。实现必须注册并通过未来 profile `post-p5-f1a-complete`；`post-p5-f1a-foundation` 只能作为前置证据，不能作为完成证据。禁止第二 event store、bus、clock、scheduler 或万能 coordinator。

F1B：实现完整 relationship/identity/reputation/family/knowledge/belief/perception/privacy projection contract，而不是只复用 P5 social authority。必须有 source event、actor/subject/jurisdiction scope、provenance、retention/expiry/forgetting、revision、public projection/actor memory/private evidence 分层、冲突合并、撤销、跨 scope 拒绝、隐私脱敏、幂等、full/checkpoint-tail replay 和拒绝零写入。实现必须注册并通过 `post-p5-f1b-complete`；禁止 social truth store、synthetic NPC state、private memory 直写和 AI reputation writer。

F1C：实现完整 governed package manifest/revision/capability/permission/preview/staging/activation/rollback/audit/migration contract，而不是只复用现有 Patch lifecycle。必须有 immutable manifest digest、schema/dependency validation、reader/editor/admin decision matrix、UI/CLI/MCP 同一授权结果、签名或受信来源验证、stale activation denial、原子激活和回滚、migration failure、audit completeness、幂等、replay 和拒绝零写入。实现必须注册并通过 `post-p5-f1c-complete`；禁止 direct database/event writer、任意 executable plugin、secret/core algorithm 暴露和 production 绕过。

F2：实现统一的跨轨证据 Harness，而不是只写 taxonomy。必须注册 `post-p5-f2-complete`，其断言真实读取 F1A/B/C complete reports，并验证 success、deny-zero-write、idempotency、revision conflict、full/checkpoint-tail replay、deterministic projection hash、privacy filter、permission parity、migration/rollback、audit completeness、evidence freshness，以及 P7 read-only/proposal-result separation 的通用接口。静态文档 profile 只能证明资料存在，绝不能让 F2 变绿。

DG：完成真实 opening checklist，逐项填写 complete profile report path、run ID、commit、owner、freshness、失效条件、rollback target 和后继 profile。只有 F0、F1A-complete、F1B-complete、F1C-complete、F2-complete 全部 fresh-green，DG 才能标记 `green`；否则保持 `planned/blocked`，不得开启 P6/P7。

所有写入必须继续通过既有 authority -> GameplayCommandEnvelope/SettlementPlan -> GameplayEventStore.append_batch() -> outbox/replay -> scoped projection 路径。client、模型和 Siming 只能提议，不能直接写世界。owner、contract/schema、privacy/projection、Harness assertion 或 migration/rollback 变化后，后继证据立即失效并重跑。不得为了通过 profile 把局部实现改名成 complete；complete profile 必须覆盖对应 spec/plan 的每一个 work package。

汇报时分开写：已完整实现并验证、仅局部基础、仅设计/blocked、证据路径、run ID/commit 和未验证范围。只有全量完成条件满足时才可以说“post-P5 全套执行完毕”。任何需要新 runtime、event store、bus、scheduler/clock、NPC/social truth store 或直接 writer 的需求，停止并报告架构冲突；如果某个 spec/plan无法在既有边界内实现，也必须报告为 blocked，而不是缩小实现范围后宣布完成。
```

## Usage Constraint

## Full completion contract

执行结束时必须同时满足：

1. F0-F2/DG 每份 spec 和 plan 的 work package 都有对应代码或明确的已审核删除/不适用决定；
2. `post-p5-f1a-complete`、`post-p5-f1b-complete`、`post-p5-f1c-complete`、`post-p5-f2-complete` 已注册并 fresh-green；
3. complete profiles 的报告包含成功、拒绝零写入、幂等、revision conflict、回放、隐私/授权、迁移/回滚和审计证据；
4. `docs`、`boundaries`、相关 backend tests 和完整 post-P5 Harness 通过；
5. DG 记录实际 run ID/commit，并明确 P6/P7 是否允许开工。

任何只通过 `post-p5-f1a-foundation`、`post-p5-f1b-foundation`、`post-p5-f1c-foundation` 或静态文档 profile 的结果，都只能称为“窄基础/文档门禁通过”，不能称为 post-P5 全套完成。
