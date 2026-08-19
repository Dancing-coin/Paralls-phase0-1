# World-Character-Siming-Authority Mainline Spec Tree

Status: `execution-active`

Date: `2026-06-29`

This folder contains the dedicated spec tree for the repository’s new mainline:

- **world-character-Siming-authority unified runtime**

Use this folder rather than the old flat-file entrypoint for all follow-on architecture work.

## Current Truth

- This spec tree is now active repository truth for the mainline runtime direction.
- Implementation and verification evidence already exist in the matching plan tree and
  the `mainline-unified-runtime` harness profile.

## Unknown Gameplay-Pack/Mod Rows

The mainline does not need to hard-code every future game activity. Trusted
gameplay packages/mods may declare typed content and its world, technology,
social, institutional, resource, production, consent, and price constraints
through the existing patch-manifest and active-revision contracts. Character
profiles and agent agreement remain proposal inputs only; they never become
payment, ownership, account, or world truth.

When a future row is missing concrete gameplay, use this repair order:

```text
business outcome
-> package/mod definition
-> source owner/evidence
-> complete row-specific owner contract
-> explicit approval
-> plan -> RED -> Harness -> runtime
```

Until then, label the row `owner-contract blocked` or `unimplemented`. Do not
invent a generic payment owner, default account, implicit technology, caller-
selected price/currency/event, router, registry, coordinator, or second
runtime. The canonical details are in
[INF federated owner capability admission design](2026-08-17-inf-federated-owner-capability-admission-design.md),
[INF completion audit](2026-08-15-inf-mainline-completion-audit.md), and
[INF remaining-scope dependency design](2026-08-12-inf-remaining-scope-dependency-design.md).

## Current Proof Aggregate

The current unified proof aggregate records direct evidence for:

- world runtime foundation
- actor-local perception
- autonomous social contact
- shared actor execution ingress
- authority settlement writeback
- asset-runtime and Kimodo contracts
- scheduling / continuity observability and replay surfaces

Primary commands:

- `python scripts/verification/verify_mainline_unified_runtime.py`
- `python scripts/verification/harness.py --profile mainline-unified-runtime`

## Entry Points

- Master spec:
  - [2026-06-29-world-character-siming-authority-mainline-master-design.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-world-character-siming-authority-mainline-master-design.md>)
- Matching plan tree:
  - [plans/world-character-siming-authority-mainline/README.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/plans/world-character-siming-authority-mainline/README.md>)

## INF Naming

- [INF mainline and substrate mapping guide](2026-08-17-inf-mainline-substrate-mapping-guide.md) - explains the `INF-1..4` domain axis and `INF-C1..5` reusable-contract axis
- [INF federated owner capability admission design](2026-08-17-inf-federated-owner-capability-admission-design.md) - approved mechanism for adding bounded, typed owner capabilities without admitting a generic writer or settlement authority
- [Package content and cross-domain binding matrix](character-gameplay-foundation/2026-08-17-package-content-and-cross-domain-binding-matrix-design.md) - design baseline for extensible package definitions and typed bindings to Siming, character-agent mind models, ESM/physics, and existing owners
- [Package contract closure and manifest adapter](character-gameplay-foundation/2026-08-17-package-contract-closure-and-manifest-adapter-design.md) - design-only closure for manifest sections, immutable package revisions, owner-derived eligibility proofs, and replay retention
- [INF-1AG package/binding sequencing design](inf-1/2026-08-18-inf-1ag-package-content-readonly-binding-sequencing-design.md) - historical P1 resolution of the binding-before-candidate ordering conflict; it enabled only the exact frozen industrial package and descriptor path now verified by INF-1AG
- [INF-1AG industrial facilities v1 freeze record](inf-1/2026-08-19-inf-1ag-industrial-facilities-v1-freeze-record.md) - canonical immutable package bytes and verified digest evidence; it does not install a candidate or admit a business descriptor
- [INF-1AG Construction descriptor/catalog admission packet](inf-1/2026-08-19-inf-1ag-construction-owner-operation-descriptor-admission-packet.md) - frozen package resolves the approved exact immutable descriptor; the separately approved Construction narrow vertical is implemented and verified without admitting a generic transform

## Spec Tree

1. [2026-06-29-world-character-siming-authority-mainline-master-design.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-world-character-siming-authority-mainline-master-design.md>)
2. [character-gameplay-foundation/README.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/README.md>)
3. [embodied-interaction-product-foundation/README.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/embodied-interaction-product-foundation/README.md>)
4. [phase-two-bakery-authored-agents/README.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/phase-two-bakery-authored-agents/README.md>)
5. [phase-three-population-continuity/README.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/phase-three-population-continuity/README.md>)
6. [phase-four-dynamic-economy-institutions/README.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/phase-four-dynamic-economy-institutions/README.md>)
7. [phase-five-rpg-social-gameplay/README.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/phase-five-rpg-social-gameplay/README.md>)
8. [phase-six-creator-control-plane/README.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/phase-six-creator-control-plane/README.md>)
9. [phase-seven-civilization-world-model-research/README.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/phase-seven-civilization-world-model-research/README.md>)
10. [post-p5-capability-foundation/README.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/post-p5-capability-foundation/README.md>) - unnumbered prerequisite and P6/P7 decision gate
11. [INF-1 continuation](inf-1/README.md) - verified vertical plus planned semantic/cross-domain expansion
12. [INF reusable contract substrate](2026-08-16-inf-reusable-contract-substrate-design.md) - prioritized reusable, owner-bound planning/admission/replay layers before further broad INF row expansion
13. [INF-C4 ecology consumer admission contract](2026-08-16-inf-c4-ecology-consumer-admission-contract-design.md) - verified finite read-only pre-fragment checks reused by existing Construction and Organization owners
14. [INF-C5 (INF-4) fixed-base branch replay contract](inf-4/2026-08-17-inf-c5-fixed-base-branch-replay-contract-design.md) - verified deterministic isolated replay inputs and fixed Organization admission contract
12. [INF-2 continuation](inf-2/README.md) - verified vertical plus planned multi-domain obligation policies
13. [INF-3 continuation](inf-3/README.md) - verified frost/crop vertical and one canonical frost -> construction edge; further regional propagation remains planned
14. [INF-4 continuation](inf-4/README.md) - verified branch-preview vertical plus planned population world-mode interface
15. [INF remaining-scope dependency design](2026-08-12-inf-remaining-scope-dependency-design.md) - R verticals plus X/Y/Z closure packages and owner blockers
11. [2026-06-29-world-runtime-foundation-design.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-world-runtime-foundation-design.md>)
6. [2026-06-29-actor-local-perception-and-fact-production-design.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-actor-local-perception-and-fact-production-design.md>)
7. [2026-06-29-autonomous-social-contact-and-exchange-design.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-autonomous-social-contact-and-exchange-design.md>)
8. [2026-06-29-authority-and-settlement-runtime-closure-design.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-authority-and-settlement-runtime-closure-design.md>)
9. [2026-06-29-execution-semantics-and-realization-runtime-design.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-execution-semantics-and-realization-runtime-design.md>)
10. [2026-06-29-asset-runtime-and-kimodo-adapter-design.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-asset-runtime-and-kimodo-adapter-design.md>)
11. [2026-06-29-world-runtime-scheduling-and-continuity-design.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-world-runtime-scheduling-and-continuity-design.md>)
12. [2026-06-29-mainline-docs-truth-rewrite-design.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-mainline-docs-truth-rewrite-design.md>)
13. [2026-07-29-character-dialogue-streaming-design.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/2026-07-29-character-dialogue-streaming-design.md>)
14. [2026-07-29-real-tts-provider-presentation-design.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/2026-07-29-real-tts-provider-presentation-design.md>)
15. [2026-07-31-tts-voice-profile-adapter-design.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/2026-07-31-tts-voice-profile-adapter-design.md>)

## Notes

- The character mind core is already completed repository truth.
- This tree is for the runtime organism around that completed core.
- Execution realization must target future asset-library and Kimodo integration, not freeze the current light Godot path as final truth.
- Remaining work should now prefer direct-evidence closure over re-framing the mainline.
- Incremental follow-on design topics now live in:
  - [current-project-intelligence-upgrade/README.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/current-project-intelligence-upgrade/README.md)
  - [character-gameplay-foundation/README.md](D:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/README.md)
