# Post-P5 Capability Foundation Specification Tree

Status: `F0 baseline and F1/F2 contract samples verified; mainline work packages remain planned`

Date: `2026-08-12`

This tree is the direct continuation after bounded P1-P5 gameplay slices. It
does not introduce a numbered phase. Its job is to make the unfinished shared
contracts explicit before Phase Six creator operations and Phase Seven research.

## Fixed external order

```text
P1 -> P2 -> P3 -> P4 -> P5
  -> post-P5 capability foundation (F0-F2)
  -> P6 creator control plane
  -> P7 civilization/world-model/robotics research
```

The DG gate confirms opening evidence and internal parallel boundaries. It does
not rename or reorder P6/P7.

## Shared invariants

Every item in this tree must reuse the existing `world_runtime`, ESM,
Character Core, Gameplay authority, `GameplayEventStore.append_batch()`,
outbox/replay, Patch/runtime lifecycle, Siming event path, and scoped mirror.
No item may add a second event store, bus, clock, scheduler, population owner,
NPC truth store, social truth store, or direct client/model/Siming world write.

## Workstreams

| Track | Owns | Primary successor |
| --- | --- | --- |
| F0 | implementation/evidence baseline across embodied, gameplay, social, Siming and ops | all tracks |
| F1A | semantic, rule, dependency, causal and time-request contracts | P6 package validation; P7 proposals |
| F1B | relationship, knowledge, family, perception and privacy projections | P6 authoring scopes; P7 read-only projections |
| F1C | package manifest, capability, revision, activation and rollback contract | P6C/P6D |
| F2 | replay, privacy, denial, zero-write, audit, migration and Harness taxonomy | P6/P7 opening gates |
| DG | opening evidence and internal parallelism decision | P6 then P7 |

## Documents

1. [F0 evidence and gap baseline](2026-08-12-f0-implementation-evidence-and-gap-baseline-design.md), with the [August source ledger](../../../../8月分析/P5后能力基础推进/07-F0八月分析逐文件覆盖台账.md)
2. [F1A semantic/rule/causal gate](2026-08-12-f1a-semantic-rule-and-causal-extension-gate-design.md)
3. [F1B social/knowledge/privacy gate](2026-08-12-f1b-social-knowledge-and-privacy-projection-extension-gate-design.md)
4. [F1C package/revision/activation contract](2026-08-12-f1c-governed-package-revision-and-activation-contract-design.md)
5. [F2 verification taxonomy](2026-08-12-f2-harness-replay-privacy-and-zero-write-gates-design.md)
6. [P6/P7 opening gate](2026-08-12-dg-p6-p7-naming-and-order-decision-record.md)

## Success definition

The foundation is complete only when the mainline work packages in
[the implementation decomposition](2026-08-12-mainline-capability-implementation-decomposition.md)
have code, focused tests, a fresh Harness profile and reviewed evidence. The
existing `*-foundation` and `*-complete` profiles prove contract samples only:
they are not completion gates for generic semantic, time, social, package or
creator capabilities. P6/P7 remain separate product tracks and are not
implemented by this tree.

## Mainline delivery order

1. INF-1 semantic snapshots, entity dossiers and causal trace.
2. INF-2 deterministic scheduled obligations and cross-domain receipts.
3. INF-3 ecology/disaster vertical slice on INF-1/INF-2.
4. INF-4 population simulation and branch replay expansion.
5. SOC-1 social graph, knowledge and privacy projection expansion.
6. GAME-1 action/survival/construction/combat/cultivation expansion.
7. CREATOR-1 package lifecycle and Preview/Production control plane.
8. COST-1 compute, memory reuse and operating-economy accounting.
