# Embodied Interaction Product Foundation Spec Tree

Status: `partially-implemented; coverage-expansion-planned`

Date: `2026-07-29`

## Purpose

This tree turns the existing semantic interaction and local presentation seams
into a productizable embodied-interaction foundation. It is deliberately below
character intent selection and above local animation/physics realization.

The tree is a sibling child of `character-gameplay-foundation`. It consumes its
future gameplay-state, event-sourcing, authority-settlement, and Godot mirror
contracts, but does not wait for the adventure/economy reference package to
start the first embodied vertical slice.

## Governing Boundaries

- Backend authority remains the only owner of accepted world truth and
  settlement.
- Godot owns local high-frequency navigation, animation, IK, collision,
  attachment, and physical observation; it does not promote a local result to
  world truth.
- Character mind and LLM select semantic intent, strategy, retry, or abort;
  they do not output per-frame bone or rigid-body control.
- VLA remains a `fast-only` online advisory provider. Its deeper path is
  deferred, parked, and non-blocking. It can propose bindings or uncertainty,
  but cannot control motion, apply impulses, or write ESM/world truth.
- Siming consumes public settlement/evidence projections and emits high-level
  catalysts only. It cannot enter a local controller or overwrite a session.
- TTS, streamed dialogue, visemes, and general presentation quality are
  intentionally outside this delivery tree.

## Reading Order

1. [Master design](2026-07-29-embodied-interaction-product-foundation-master-design.md)
2. [Scene affordance registry](2026-07-29-scene-affordance-registry-design.md)
3. [Embodied action controller and local observation](2026-07-29-embodied-action-controller-and-local-observation-design.md)
4. [Execution transport and controller attestation](2026-07-31-execution-transport-and-controller-attestation-design.md)
5. [Interaction session and authority settlement](2026-07-29-interaction-session-and-authority-settlement-design.md)
6. [Godot mirror, observatory, and replay evidence](2026-07-29-godot-mirror-observatory-and-replay-evidence-design.md)
7. [Boundary and acceptance matrix](2026-07-29-boundary-and-acceptance-matrix-design.md)
8. [Atomic action library and default scene coverage](2026-08-01-atomic-action-library-and-default-scene-coverage-design.md)

## Dependency Order

```text
existing mainline execution / ESM / L1 / VLA contracts
  -> SceneAffordanceRegistry identity and query contract
  -> EmbodiedActionController and local observation contract
  -> authority-confirmed physical settlement and replay ledger
  -> InteractionSession for multi-participant actions
  -> Godot mirror / Observatory / aggregate evidence
  -> grab-carry-handoff, handshake, and advisory VLA expansions
```

The first implementation closure ends after the single-actor physical action
path. `InteractionSession` is specified now because it determines ID,
cancellation, and evidence contracts, but its first executable closure follows
the physical path rather than blocking it.

## Related Truth

- Active mainline master: `../2026-06-29-world-character-siming-authority-mainline-master-design.md`
- Existing semantics transition: `../../../../plans/world-character-siming-authority-mainline/2026-06-29-execution-semantics-and-realization-runtime-implementation-plan.md`
- Gameplay state/settlement design: `../character-gameplay-foundation/2026-07-23-event-sourcing-and-authority-settlement-design.md`
- Gameplay store/bus coupling design: `../character-gameplay-foundation/2026-07-31-coupled-event-store-and-authority-bus-design.md`
- Gameplay Godot mirror design: `../character-gameplay-foundation/2026-07-23-godot-runtime-mirror-and-prediction-design.md`
- Existing grounding truth: `../../../current-project-intelligence-upgrade/2026-07-30-advisory-vla-routing-and-tts-convergence-design.md`
- Current runtime boundaries: `docs/架构/运行时/模块/ESM与交互编排.md` and `docs/架构/运行时/模块/VLA运行时通道.md`

## Planning Gate

The matching execution plan is available at
`docs/superpowers/plans/world-character-siming-authority-mainline/embodied-interaction-product-foundation/`.
The verified controller, registry, settlement, replay, session, carry/handoff,
and action-asset-selection foundations are already implemented as focused
slices. This tree authorizes only incremental work that preserves those
boundaries and adds focused evidence. `obj_letter` is the first Godot-runtime-
verified default-main-scene `inspect/read` fixture. `obj_plaque` is the second
Godot-runtime-verified readable fixed-prop fixture, and `obj_lamp_switch` is
the first authority-gated semantic `press` fixture with `switch: idle ->
activated` evidence. `obj_archive_door` is the stateful authority-gated
`open_close` fixture with `door: closed -> open -> closed` and state-constraint
evidence. `obj_worktable` is the stateful single-actor `use` / `finish_use`
fixture with `work_surface: ready -> engaged -> ready` and state-constraint
evidence. `obj_observation_bench` is the actor-scoped `sit` / `stand` fixture
with owner-only release and `posture: standing -> seated -> standing` evidence;
seated animation, shared occupancy allocation, and session semantics remain
planned. `obj_archive_token` is the first custody-only `grab` fixture: backend
policy resolves the asset/source/actor-hand target and Godot changes the prop
only after an authority-only placement directive. It does not establish
inventory placement or ownership. A subsequent restricted `stow_intent`
reference atomically moves that backend-confirmed custody into a policy-resolved
backpack location and emits an accepted-only presentation marker; it is not a
scene container/retrieve, inventory UI, ownership, or generic pickup/store
closure. The inverse backend-only `retrieve_to_custody` foundation preserves
the item identity while removing its actor-inventory location and occupying a
registered receiver; it has no default-scene transport or client-selected
receiver. Table seating, shared occupancy, ownership, hand animation, and
generic pickup/place coverage remain planned. Broader family coverage remains planned. Every
further family requires
reviewed registry bindings, authority policy, and
success/constraint evidence. Existing legacy documents retain their individual review status; a tree-level partial
implementation status does not claim every specified feature is complete.
