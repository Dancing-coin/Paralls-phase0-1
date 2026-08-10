# Phase Six Creator Control Plane Execution Prompt

仅在 P6 套件整体获得实现授权、P5D fresh-green 且完成安全评审后使用。

```text
你负责 Paralls Phase Six Creator Control Plane 的完整执行套件。目标是让 reader/editor/admin
通过 UI、CLI、MCP 使用同一 server-side capability、draft、validation、package lifecycle 和
audit contract，同时保护 closed core。P6 不是 gameplay authority、不是开放 marketplace，也
不是让创作者直接改生产数据库。

开始前读取：
- AGENTS.md、docs/INDEX.md、docs/harness.md、docs/ai-engineering-workflow.md；
- P1D-P5D specs/plans、最新 reports，尤其 P5D；
- phase-six-creator-control-plane spec/plan README；
- P6A-P6D specs 与 matching plans；
- docs/8月分析/第六阶段推进全部文件；
- Character Gameplay Foundation Patch/manifest/capability、authorization/audit、event/replay、
  GameplayCommandEnvelope、SettlementPlan、GameplayEventStore、Godot mirror owners。

前置门禁：运行 P5D、P4、P3、P2、P1D predecessor profiles；先完成 security/threat review。

唯一顺序：
P6A capability/closed-core boundary
  -> P6B UI/CLI/MCP semantic alignment
  -> P6C package staging/activation/rollback
  -> P6D creator operations vertical slice

P6A：
- 先测 reader/editor/admin、project/environment/package scope、classification、expiry/revocation、
  confused deputy、cross-project escalation、editor activation denial、admin raw-write denial、
  private memory/secret redaction；
- capability decision 必须 server-side、signed/审计；不得暴露 Python mutation import、raw YAML
  loader、private memory、keys、raw event ingress 或 closed algorithm。

P6B：
- UI list/select、CLI、MCP 必须共享 versioned schema、decision id、validation diagnostics、
  draft revision、visible classification、audit correlation；
- 先测 success/deny/redaction/malformed/stale draft/idempotency parity；
- 客户端只能调用 decision/validation adapter，不能复制 policy 或映射内部 mutation 函数。

P6C：
- 先测 digest/signature、dependency/schema conflict、migration、canary、active-set conflict、
  reversible/lossy rollback、player-fact overwrite denial；
- local preview 使用隔离 draft data；remote formal run 只能提交 signed revision；
- package/Patch activation 沿用现有 lifecycle 和 authority；任何 gameplay consequence 仍走
  GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()；
- 禁止 arbitrary code、untrusted migration、raw admin write、silent rollback。

P6D：
- 完整验证 reader 读授权公开报告、editor 修改允许参数并 preview/submit、admin review/stage/
  canary/activate/rollback；
- UI/CLI/MCP 必须产生语义一致的 decision/audit；
- 只能使用一个明确允许且可回滚的规则参数和隔离 preview fixture；
- 验证 active revision replay、redaction、editor activation denial、zero raw-fact write。

每阶段必须先 failing tests，再 focused/security Harness、全部 predecessor Harness、docs/
mainline；汇报 capability matrix、decision IDs、audit digest、manifest/revision、migration/
rollback、replay 和 redaction。若要把 creator/client/model 变成 canonical writer，立即停止。
只有 P6A-P6D 全绿后才能请求 P7 研究授权。
```

## Usage Constraint

这份提示词对应整个 P6 plan set；三档创作者能力不等于闭源 core 访问权。
