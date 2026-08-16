# World-Character-Siming-Authority Mainline Plan Tree

Status: `execution-active`

Date: `2026-06-29`

This folder contains the dedicated implementation-plan tree for the new mainline spec family.

These plans are now the active execution surface for the repository's mainline.

They are no longer draft-only decomposition scaffolds. The current worktree already
contains implementation and verification evidence across the major branches of this tree.

## Current Execution State

- The docs truth rewrite branch is active and already reflected in repository entry docs.
- World-runtime, perception, social contact, authority/settlement, execution semantics,
  asset-runtime/Kimodo contracts, and scheduling/continuity all have direct evidence in
  code and focused verification.
- A stricter closure audit now exists at:
  - `docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-30-mainline-plan-closure-matrix.md`
- The current top-level proof aggregate is:
  - `python scripts/verification/verify_mainline_unified_runtime.py`
  - `python scripts/verification/harness.py --profile mainline-unified-runtime`

## Parent Spec Tree

- [specs/world-character-siming-authority-mainline/README.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/README.md>)
- [INF mainline and substrate mapping guide](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-17-inf-mainline-substrate-mapping-guide.md>)

## Plan Tree

1. [2026-06-29-world-runtime-foundation-implementation-plan.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-world-runtime-foundation-implementation-plan.md>)
2. [2026-06-29-actor-local-perception-and-fact-production-implementation-plan.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-actor-local-perception-and-fact-production-implementation-plan.md>)
3. [2026-06-29-autonomous-social-contact-and-exchange-implementation-plan.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-autonomous-social-contact-and-exchange-implementation-plan.md>)
4. [2026-06-29-authority-and-settlement-runtime-closure-implementation-plan.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-authority-and-settlement-runtime-closure-implementation-plan.md>)
5. [2026-06-29-execution-semantics-and-realization-runtime-implementation-plan.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-execution-semantics-and-realization-runtime-implementation-plan.md>)
6. [2026-06-29-asset-runtime-and-kimodo-adapter-implementation-plan.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-asset-runtime-and-kimodo-adapter-implementation-plan.md>)
7. [2026-06-29-world-runtime-scheduling-and-continuity-implementation-plan.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-world-runtime-scheduling-and-continuity-implementation-plan.md>)
8. [2026-06-29-mainline-docs-truth-rewrite-implementation-plan.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-mainline-docs-truth-rewrite-implementation-plan.md>)
9. [embodied-interaction-product-foundation/README.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/embodied-interaction-product-foundation/README.md>)
10. [phase-two-bakery-authored-agents/README.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/README.md>)
11. [phase-three-population-continuity/README.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/phase-three-population-continuity/README.md>)
12. [phase-four-dynamic-economy-institutions/README.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/phase-four-dynamic-economy-institutions/README.md>)
13. [phase-five-rpg-social-gameplay/README.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/phase-five-rpg-social-gameplay/README.md>)
14. [phase-six-creator-control-plane/README.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/phase-six-creator-control-plane/README.md>)
15. [phase-seven-civilization-world-model-research/README.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/phase-seven-civilization-world-model-research/README.md>)
16. [post-p5-capability-foundation/README.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/post-p5-capability-foundation/README.md>) - unnumbered prerequisite and P6/P7 decision gate
17. [INF-1 continuation](inf-1/README.md) - semantic/cross-domain expansion is planned only
18. [INF reusable contract substrate plan](2026-08-16-inf-reusable-contract-substrate-implementation-plan.md) - prioritized shared owner-bound abstractions before further broad INF row expansion
19. [INF-C4 ecology consumer admission contract plan](2026-08-16-inf-c4-ecology-consumer-admission-contract-implementation-plan.md) - verified finite read-only pre-fragment checks reused by existing Construction and Organization owners
20. [INF-C5 (INF-4) fixed-base branch replay contract plan](inf-4/2026-08-17-inf-c5-fixed-base-branch-replay-contract-plan.md) - verified deterministic isolated replay inputs and fixed Organization admission contract
18. [INF-2 continuation](inf-2/README.md) - multi-domain obligation policy expansion is planned only
19. [INF-3 continuation](inf-3/README.md) - one canonical frost -> construction edge is verified; all further ecology propagation remains planned
20. [INF-4 continuation](inf-4/README.md) - population world-mode interface expansion is planned only
21. [INF remaining-scope dependency implementation plan](2026-08-12-inf-remaining-scope-dependency-implementation-plan.md) - ordered R/X/Y/Z execution gates
17. [2026-07-29-character-dialogue-streaming-implementation-plan.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/2026-07-29-character-dialogue-streaming-implementation-plan.md>)
12. [2026-07-29-real-tts-provider-presentation-implementation-plan.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/2026-07-29-real-tts-provider-presentation-implementation-plan.md>)
13. [2026-07-31-tts-voice-profile-adapter-implementation-plan.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/2026-07-31-tts-voice-profile-adapter-implementation-plan.md>)
14. [2026-08-03-tts-voice-profile-adapter-closure-implementation-plan.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/2026-08-03-tts-voice-profile-adapter-closure-implementation-plan.md>)
