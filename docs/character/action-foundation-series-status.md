# Action Foundation Series Status

Date: 2026-09-28

Status: pilot landed; completion series open

## Controlling Documents

| Layer | Document | Status |
|---|---|---|
| Design | docs/superpowers/specs/2026-09-28-character-action-foundation-series-completion-design.md | awaiting user review |
| Execution | docs/superpowers/plans/2026-09-28-character-action-foundation-series-completion-implementation-plan.md | draft for the reviewed spec |
| Operator index | docs/character/character-action-foundation-operator-guide-and-index.md | updated |
| Current-state ledger | docs/character/character-action-foundation-current-state.md | updated |
| Repository index | docs/INDEX.md | updated |

## Gate Matrix

| Gate | Evidence already present | Remaining closure |
|---|---|---|
| Animation | StreetCombatDemo headless probe: 3 active AnimationTrees, valid bindings, full state catalog, action recovery | keep semantic interface and interruption behavior typed |
| Motion | CharacterMotor is the movement owner in the target street path; root track discovery works | calibrate non-zero root profiles, universalize NPC/agent routing, prove single contribution consumption |
| Replica | CharacterActor extraction and CharacterReplica compatibility shell landed | remove remaining concrete implementation dependencies and update stale source-text contracts |
| Assets | three qualified street manifests and imported Skeleton3D/action clips | enforce registry admission and reject malformed or stale packages |
| Arbitration | compatibility action and controller paths exist | require descriptors, claims, locomotion relation, root policy, markers, cancel windows, and deterministic arbitration |
| Authority | street combat and compatibility authority routes exist | universal ActionAttempt closure, idempotency, revisions, zero-write failure, and Mode B reconnect evidence |
| Documentation | new completion spec/plan and updated index/current-state/operator guide | keep status documents synchronized as implementation gates close |

## What Is Landed

- Three real StreetCombatDemo characters use the external-controller-style AnimationTree.
- States idle, walk, run, jump, boxing, and sword_attack are available.
- Punch and sword use separate state-machine states.
- Guard pose is held through controller-owned playback.
- CharacterMotor remains the target path's movement owner.
- RootMotionSampler exists and is wired to the street skin.
- CharacterReplica has a compatibility-shell migration seam.
- A real-scene convergence probe exists and is part of focused verification.

## What Is Not Yet Complete

- Street manifests still describe root motion as hold with zero distance envelopes.
- Root tracks are sampled, but calibrated root-motion locomotion is not yet enabled as a production movement policy.
- Legacy player/NPC/agent paths still require an ownership audit before the one-Motor claim can be universal.
- Some tests still encode pre-convergence implementation placement inside CharacterReplica.
- Action descriptors and claims are not yet enforced at every runtime ingress.
- The final generic ActionAttempt to authority result path is not yet universal.
- Registry admission and fallback diagnostics are not yet the single mandatory package gate.
- Documentation before 2026-09-28 contains historical and transitional statements that must not be treated as current design.

## Required Evidence Before Series Completion

1. Focused static ownership and descriptor tests.
2. Godot StreetCombatDemo runtime proof for all three characters.
3. Root-motion qualification and contribution-consumption proof.
4. Player/NPC/agent Motor ownership proof.
5. Real backend ActionAttempt, duplicate, stale-revision, zero-write, and reconnect proof.
6. Fresh documentation/index audit and relevant Harness profiles.

## Historical Document Rule

Older June designs and pre-convergence CharacterReplica descriptions explain migration history. They do not authorize a second controller, direct skin transform writes, a second Motor, or local authority settlement.
