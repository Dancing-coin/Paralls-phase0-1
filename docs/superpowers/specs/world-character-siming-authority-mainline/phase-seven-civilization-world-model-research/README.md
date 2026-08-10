# Phase Seven Civilization, World Model And Robotics Research Specification Tree

Status: `design-only; implementation not authorized`

Date: `2026-08-10`

## Purpose

P7 formalizes `docs/8月分析/第七阶段推进/` as long-horizon research and
product design. It does not claim that civilization simulation, counterfactual
branches, world models or robotics exist in the current runtime, and none may
become a world-truth writer.

## Baseline

P7 consumes P1-P6 committed events, checkpoints, revisions, permission policies,
package activation history and scoped projections. Character Core, Economy,
Government, Organization and Gameplay authority retain their owners. A branch,
prediction, model output or robot controller is an explicitly classified
proposal, report or sandbox artifact.

P7 is read-only with respect to gameplay truth: it may consume replay/checkpoint
readers and emit proposal/report artifacts, but it never calls
`GameplayEventStore.append_batch()` or accepts a `SettlementPlan` as a direct
write request.

## Dependency Order

```text
P6D governance evidence -> P7A civilization projection -> P7B branch/replay
                         -> P7C world-model proposal -> P7D robotics safety slice
```

The hard predecessor is [P6D creator operations](../phase-six-creator-control-plane/2026-08-10-p6d-creator-operations-vertical-slice-design.md).

## Documents

1. [P7A civilization and cross-jurisdiction projection](2026-08-10-p7a-civilization-and-cross-jurisdiction-projection-design.md)
2. [P7B branch replay and counterfactual calibration](2026-08-10-p7b-branch-replay-and-counterfactual-calibration-design.md)
3. [P7C world-model proposal boundary](2026-08-10-p7c-world-model-proposal-boundary-design.md)
4. [P7D robotics safety research slice](2026-08-10-p7d-robotics-safety-research-slice-design.md)

Matching plans: [P7A](../../../plans/world-character-siming-authority-mainline/phase-seven-civilization-world-model-research/2026-08-10-p7a-civilization-and-cross-jurisdiction-projection-implementation-plan.md),
[P7B](../../../plans/world-character-siming-authority-mainline/phase-seven-civilization-world-model-research/2026-08-10-p7b-branch-replay-and-counterfactual-calibration-implementation-plan.md),
[P7C](../../../plans/world-character-siming-authority-mainline/phase-seven-civilization-world-model-research/2026-08-10-p7c-world-model-proposal-boundary-implementation-plan.md),
[P7D](../../../plans/world-character-siming-authority-mainline/phase-seven-civilization-world-model-research/2026-08-10-p7d-robotics-safety-research-slice-implementation-plan.md).
