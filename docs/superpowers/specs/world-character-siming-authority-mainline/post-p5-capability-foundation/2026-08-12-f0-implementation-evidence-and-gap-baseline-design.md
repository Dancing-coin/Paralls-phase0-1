# F0 Implementation Evidence And Gap Baseline

Status: `implemented-and-verified; evidence baseline only`

## Objective

Produce one honest baseline for everything P1-P5 can prove and everything the
August analysis still only describes. F0 is a reconciliation artifact, not a
new runtime.

## Inputs and outputs

Inputs are formal P1-P5 specs/plans, code, focused tests, Harness reports,
August analysis, embodied foundation reports, Character Core status, Siming
event evidence, and the staged implementation mapping. Outputs are:

1. a row-level capability ledger;
2. an owner/path map to existing modules;
3. a gap and dependency register for F1A/F1B/F1C/F2;
4. a claim ledger listing what must not be overclaimed;
5. a freshness report identifying missing or future-dated evidence.

The reviewed companion artifacts are the owner map, gap register, claim ledger,
and evidence manifest under `docs/8月分析/P5后能力基础推进/`.

The concrete August-analysis source ledger is
`docs/8月分析/P5后能力基础推进/07-F0八月分析逐文件覆盖台账.md`.
It must retain one row for every non-phase-progression analysis file and route
every partial/planned row to F1A, F1B, F1C, F2, DG, P6, or P7.

## Required ledger dimensions

| Seam | Required review |
| --- | --- |
| embodied/presentation | action library, default scene, mirror, TTS/dialogue/asset exclusions |
| gameplay | action, skill, inventory, ownership, combat, survival, supernatural coverage |
| role/social | relationship, identity, family, knowledge, perception, privacy projections |
| world/Siming | entity, semantic, causal, time request, mode, proposal and event path |
| creator/operations | package, revision, permission, preview, activation, rollback, audit |

Each row is `verified`, `partial`, `planned`, `blocked`, or `not-applicable`,
with evidence, owner, missing contract, risk, and next gate.

## Owner rules

F0 may point to `backend/app/world_runtime/*`, ESM, Character Core, Gameplay
authority, `GameplayEventStore.append_batch()`, Patch/runtime, Siming event
integration, or scoped mirror. It may not invent a registry, scheduler,
population service, social store, creator writer, or research authority.

## Acceptance evidence

- every August design family has a ledger row;
- P1-P5 claims distinguish bounded proof from product completeness;
- every `partial` or `planned` row names a downstream F-track;
- staged audit material is never treated as stronger than executable evidence;
- the concrete source ledger covers world infrastructure, gameplay,
  role/social, creator/operations, VLA/presentation, and cost analysis files;
- docs Harness passes and the ledger has a reviewer.

## Stop conditions and non-goals

Unknown status, contradictory evidence, or a missing owner keeps F0 `blocked`.
F0 does not implement a complete RPG, civilization simulator, creator platform,
world-model runtime, or robotics runtime.
