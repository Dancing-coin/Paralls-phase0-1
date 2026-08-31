# World-Character-Siming-Authority Mainline Plan Tree

Status: `execution-active; current objective: Closed Generic Gameplay Foundation v1`

Date: `2026-06-29`

This folder contains the dedicated implementation-plan tree for the new mainline spec family.

These plans are now the active execution surface for the repository's mainline.

They are no longer draft-only decomposition scaffolds. The current worktree already
contains implementation and verification evidence across the major branches of this tree.

Current INF index: INF-1 through INF-4 contain the exact implemented narrow
verticals listed in the mainline completion audit, each with owner-local
receipt, privacy, idempotency, replay and Harness evidence. Remaining INF rows
retain their own candidate/blocker gates; August INF A-D remains `not complete`.

The current non-INF foundation track is the documentation and implementation
plan [Closed Generic Gameplay Families](2026-08-29-closed-generic-gameplay-families-implementation-plan.md).
It introduces reusable family contracts for package content while retaining
row-specific owner authority. It must not be counted as an August INF business
row or used to bypass owner-admission gates.

Closed Generic Gameplay Foundation v1 currently has `11 generic implementations /
0 bounded adapters / 1 blocked`. Matrix closure and the two-content genericity
gate are verified for every writable family. The blocked custody family and its
exact missing committed facts are tracked in the companion plan and residual
blocker register; no fallback writer or inferred coordinates are allowed.

The shared event-store substrate also has a verified snapshot-integrity
closure: recovery cross-checks ledger events, transaction batches, append
results, idempotency indexes, and outbox references before reopening. This is
foundation evidence reused by INF rows, not an August INF business row.

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
18a. [INF-2AE facility commissioning review exchange plan](inf-2/2026-08-27-inf-2ae-facility-commissioning-review-exchange-plan.md) - implemented exact INF-1AI source -> Contract service -> fixed Economy exchange; generic payment/transfer remains closed
18b. [INF-2AG public-workshop service exchange plan](inf-2/2026-08-27-inf-2ag-public-workshop-service-exchange-plan.md) - implemented exact INF-1AJ source -> Contract service -> fixed v5 Economy exchange; generic payment/service remains closed
18c. [INF-4AH public-workshop notice plan](inf-4/2026-08-27-inf-4ah-public-workshop-notice-plan.md) - implemented exact INF-4AG activity -> Government project notice; generic notification/social remains closed
18d. [INF-4AJ public-project execution plan](inf-4/2026-08-27-inf-4aj-public-project-execution-plan.md) - implemented exact INF-4AG activity + INF-2AI consumed budget -> Organization project execution; generic project lifecycle remains closed
18e. [INF-2AK public-project budget close plan](inf-2/2026-08-28-inf-2ak-public-project-budget-close-plan.md) - implemented exact consumed budget + funded execution -> Economy terminal close marker; generic budget lifecycle remains closed
18f. [INF-4AK public-project execution acknowledgment plan](inf-4/2026-08-28-inf-4ak-public-project-execution-acknowledgment-plan.md) - implemented exact funded execution -> Government authority-only acknowledgment; no generic project lifecycle
18g. [INF-3W weather rain crop recovery plan](inf-3/2026-08-28-inf-3w-weather-rain-crop-recovery-plan.md) - implemented exact unique damaged crop +5 recovery; no generic crop resolver
18h. [INF-1AL mill-reinforced public-use plan](inf-1/2026-08-28-inf-1al-mill-reinforced-public-use-plan.md) - implemented exact Construction existing-row extension; generic facility availability remains blocked
18i. [INF-2AL public milling session plan](inf-2/2026-08-28-inf-2al-public-milling-session-plan.md) - implemented exact Contract -> fixed v6 Economy exchange; generic payment remains blocked
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
# 2026-08-28 Four-Lane Gap Closure Update

INF-1AM, INF-2AM, INF-3 grain harvest/INF-3AB custody, and INF-4AO have implemented plans and
green focused/Harness evidence. These are narrow verticals only; August INF
A-D remains `not complete` and generic owner/payment/transfer/transform/
settlement expansion remains prohibited.

Current continuation: INF-3AB grain-harvest -> Inventory custody is implemented
with fixed holder/container/item-definition evidence; generic routes remain
prohibited.

INF-4AP is the verified Organization follow-on for that custody fact; generic
activity, production, payment, and social routes remain closed.

Residual lane blockers and their minimum next decisions are recorded in the
[INF residual blocker register](../../specs/world-character-siming-authority-mainline/2026-08-29-inf-residual-blocker-register.md).
