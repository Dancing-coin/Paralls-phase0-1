# Post-P5 Capability Foundation Plan Tree

Status: `F0 baseline and contract samples complete; mainline execution is not complete`

The plan is the direct continuation after P5 and before P6. It is deliberately
not a catch-all implementation phase.

## Execution sequence

```text
First: INF-1 -> INF-2 -> INF-3 -> INF-4
Then: SOC-1 and GAME-1 in dependency-aware lanes
Then: CREATOR-1 -> COST-1
Only then: decide whether P6/P7 can open
```

P6A/P6B preparation may overlap the latter half of F1A/F1B only as design and
test planning. P6C/P6D implementation planning waits for F1C/F2. P7 research
preparation may be read-only, but P7 implementation waits for P6D evidence and
its own research/safety gates.

## Plans

1. [F0 plan](2026-08-12-f0-implementation-evidence-and-gap-baseline-implementation-plan.md)
2. [F1A plan](2026-08-12-f1a-semantic-rule-and-causal-extension-gate-implementation-plan.md)
3. [F1B plan](2026-08-12-f1b-social-knowledge-and-privacy-projection-extension-gate-implementation-plan.md)
4. [F1C plan](2026-08-12-f1c-governed-package-revision-and-activation-contract-implementation-plan.md)
5. [F2 plan](2026-08-12-f2-harness-replay-privacy-and-zero-write-gates-implementation-plan.md)
6. [Opening gate plan](2026-08-12-dg-p6-p7-naming-and-order-review-plan.md)
7. [Foundation execution prompt](2026-08-12-post-p5-capability-foundation-execution-prompt.md)

## Plan-of-record requirements

Before any future implementation plan is approved, it must name the existing
owner and write path, input revision, authorization decision, audit event,
replay set, privacy scope, migration/rollback behavior, Harness profile, and
the condition that keeps the work `planned` or `blocked`.

The `post-p5-f1a-foundation`, `post-p5-f1b-foundation`,
`post-p5-f1c-foundation`, `post-p5-f2-gates`, and current `*-complete` profiles
are contract-sample evidence. They do not complete the mainline. Full execution
requires one focused profile per work package, each with tests that assert its
own capability instead of reusing one shared pass/fail boolean.
