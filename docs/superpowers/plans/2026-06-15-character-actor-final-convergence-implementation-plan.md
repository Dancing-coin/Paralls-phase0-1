# Character Actor Final Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Converge the shared `CharacterActor` stack from the current near-term transitional state to the final local actor-substrate target required by the full character-agent runtime.

**Architecture:** This is the second-stage actor-control plan that follows the completed near-term cleanup pass. It does not redo near-term cleanup. It turns the existing actor architecture target into executable convergence work so the full character-agent runtime can enter one final shared local embodiment host instead of a permanent transitional shell split.

**Tech Stack:** Godot 4.6 scenes, GDScript, current player/actor runtime, shared control contracts, pytest static/runtime verification, existing actor architecture docs, current migration-status docs, and Phase 0 harness verification.

---

## Relationship To Existing Actor Plans

This plan is not a replacement for the earlier 2026-06-15 plans.

It sits above them in the actor-control sequence:

1. `docs/superpowers/plans/2026-06-15-character-actor-architecture-optimization-implementation-plan.md`
   - broad optimization and architecture documentation
2. `docs/superpowers/plans/2026-06-15-character-actor-near-term-cleanup-implementation-plan.md`
   - demo-safe cleanup and transition slimming
3. `docs/superpowers/plans/2026-06-15-character-actor-final-convergence-implementation-plan.md`
   - final-state actor-substrate convergence

This plan also exists as the explicit Stage A dependency of:

- `docs/superpowers/plans/2026-06-15-full-character-agent-runtime-with-llm-implementation-plan.md`

---

## Final Target

The final local embodiment host target is:

```text
CharacterActor
-> ControllerPort
-> CharacterMotor
-> CharacterRuntimeState
-> CharacterPresentationInput
-> KnightRoleSkin
-> post-animation embodiment modifier stack
```

The target guarantees:

- one shared actor substrate for player, agent, and program control
- one shared actor execution chain
- one shared presentation boundary
- no permanent dependence on a player-only outer shell plus nested replica split
- no permanent dependence on `CharacterReplica` as an overgrown transitional owner

---

## Scope

This plan covers:

- final actor ingress seam
- final shared actor scene/runtime target
- final local runtime host extraction from the current `CharacterReplica` transition point
- final `ControllerPort` / adapter-family planning and first implementation seam
- final player/agent/program control unification
- final presentation-boundary strengthening
- final alignment with full character-agent `L4` ingress expectations

This plan does not cover:

- full character cognition
- memory
- LLM reasoning
- `ESM` semantic action generation
- dialogue content generation

Those are handled by the full character-agent plan.

---

## Task 1: Freeze The Final Actor-Convergence Truth In Docs

**Files:**
- Create: `docs/character/character-actor-final-convergence-target.md`
- Modify: `docs/INDEX.md`
- Modify: `docs/character/character-actor-migration-status.md`

- [ ] **Step 1.1: Write the final actor-convergence target doc**

The doc must explicitly freeze:

```text
- final CharacterActor host shape
- final ControllerPort role
- final CharacterRuntimeState role
- final CharacterIntentFrame ingress
- final CharacterPresentationInput egress
- final player/agent/program shared execution chain
- removal target for the long-term CharacterBase/CharacterReplica split
```

- [ ] **Step 1.2: Update `docs/INDEX.md` so this final-convergence target is discoverable beside the active actor architecture docs**

- [ ] **Step 1.3: Update migration status to distinguish**

```text
- near-term cleanup completed
- final convergence planned
- final convergence not yet fully landed
```

- [ ] **Step 1.4: Run docs verification**

Run:

```powershell
python scripts/verification/harness.py --profile docs
```

---

## Task 2: Introduce The Explicit `ControllerPort` And Adapter Family

**Files:**
- Create:
  - `scripts/character/CharacterControllerPort.gd`
  - `scripts/character/HumanControllerAdapter.gd`
  - `scripts/character/AgentControllerAdapter.gd`
  - `scripts/character/ProgramControllerAdapter.gd`
- Tests:
  - `backend/tests/test_character_controller_port_static.py`

- [ ] **Step 2.1: Write failing tests for the controller-port family**

The tests must require:

```text
- a shared CharacterControllerPort abstraction
- human/agent/program adapters
- adapter outputs normalized into one actor-facing intent/control shape
```

- [ ] **Step 2.2: Implement the minimal shared `ControllerPort` abstraction**

The first implementation may be narrow, but it must clearly separate:

- control source
- control adaptation
- actor runtime ingress

- [ ] **Step 2.3: Implement human / agent / program adapters**

They do not need full feature parity yet, but they must prove:

- one shared ingress family
- no separate player-only or agent-only body path

- [ ] **Step 2.4: Run focused tests**

Run:

```powershell
python -m pytest -q backend\tests\test_character_controller_port_static.py
```

---

## Task 3: Extract Final `CharacterRuntimeState` State Object From The Transitional `CharacterReplica` Shell

**Files:**
- Create:
  - `scripts/character/CharacterRuntimeState.gd`
- Modify:
  - `scripts/character/CharacterReplica.gd`
- Tests:
  - `backend/tests/test_character_runtime_state_extraction_static.py`

- [ ] **Step 3.1: Write failing tests for runtime-state extraction**

The tests must prove:

```text
- CharacterReplica no longer owns all actor-runtime state directly
- CharacterRuntimeState exists as the extracted final state object
- command status, focus/runtime state, and presentation aggregation are routed through that state object
```

- [ ] **Step 3.2: Implement the extracted runtime-state object**

First convergence target:

- command status
- focus/runtime state
- nearby refs / interaction feasibility state
- presentation input assembly state

- [ ] **Step 3.3: Shrink `CharacterReplica` into a thinner actor shell**

Expected posture:

```text
CharacterReplica
- host node and scene-local orchestration shell
- runtime-state owner reference
- control-port integration
- motor and presentation host wiring
```

- [ ] **Step 3.4: Run focused tests**

---

## Task 4: Converge Player, Agent, And Program Paths Onto The Same Actor Ingress

**Files:**
- Modify:
  - `scripts/player/PlayerShell.gd`
  - `scripts/player/Phase0PlayerBridge.gd`
  - actor adapter files from Task 2
  - actor runtime shell files
- Tests:
  - `backend/tests/test_character_shared_ingress_static.py`

- [ ] **Step 4.1: Write failing tests that prove all control sources enter the same actor-side ingress family**

- [ ] **Step 4.2: Route the player path through the new human adapter**

- [ ] **Step 4.3: Route agent-originated execution through the new agent adapter seam**

- [ ] **Step 4.4: Route harness/program control through the program adapter seam**

- [ ] **Step 4.5: Run focused tests**

---

## Task 5: Strengthen Final `CharacterIntentFrame` / `CharacterPresentationInput` Seams

**Files:**
- Modify:
  - `scripts/character/CharacterActorSchema.gd`
  - `scripts/character/CharacterPresentationInput.gd`
  - `scripts/character/KnightRoleSkin.gd`
  - actor-side adapter/runtime files
- Tests:
  - `backend/tests/test_character_final_actor_contracts_static.py`

- [ ] **Step 5.1: Write failing tests for final actor-side contract usage**

The tests must prove:

```text
- CharacterIntentFrame is the shared actor ingress contract
- CharacterPresentationInput is the shared presentation egress contract
- actor-side code stops relying on arbitrary transitional side-channel payload mutation where the formal contracts should be used
```

- [ ] **Step 5.2: Expand or harden the shared schema/contracts as needed**

- [ ] **Step 5.3: Update actor-side consumers to use the formal seams more directly**

- [ ] **Step 5.4: Run focused tests**

---

## Task 6: Converge The Shared Actor Scene/Runtime Target

**Files:**
- Modify:
  - `scenes/phase0/CharacterBase.tscn`
  - `scenes/phase0/CharacterReplica.tscn`
  - any final shared actor scene introduced during convergence
- Tests:
  - `backend/tests/test_character_actor_scene_convergence_static.py`

- [ ] **Step 6.1: Write failing tests for the final shared actor scene/runtime target**

The tests must answer:

```text
- what is the final shared actor scene/runtime host
- how char_c maps onto it
- how char_a/char_b map onto it
- whether the current CharacterBase -> nested CharacterReplica split remains permanent or has been converged away
```

- [ ] **Step 6.2: Land the final shared actor scene/runtime shape**

This may take one of two valid forms:

```text
A. CharacterBase converges into the final CharacterActor host
or
B. CharacterReplica converges into the final CharacterActor host and CharacterBase is reduced to a temporary player shell wrapper that no longer defines architecture truth
```

The implementation must choose one and document it clearly.

- [ ] **Step 6.3: Update migration docs to mark the old transitional layering as resolved or explicitly narrowed**

- [ ] **Step 6.4: Run focused tests**

---

## Task 7: Final Actor-Convergence Verification And Handoff To Character-Agent Stage B

**Files:**
- Modify if needed:
  - `docs/character/character-actor-migration-status.md`
  - `docs/character/character-control-chain.md`
  - `docs/character/character-actor-final-convergence-target.md`
  - `docs/superpowers/plans/2026-06-15-full-character-agent-runtime-with-llm-implementation-plan.md`

- [ ] **Step 7.1: Run verification**

Run:

```powershell
python -m pytest -v
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile godot-project
python scripts/verification/harness.py --profile phase0
```

- [ ] **Step 7.2: Update docs to record that actor final convergence planning and prerequisite convergence work are complete enough for Character-Agent Stage B**

- [ ] **Step 7.3: Update the full character-agent plan if Stage A dependency wording needs tightening after real convergence work**

---

## Exit Conditions

This plan is complete when:

1. the repository has an explicit final actor-convergence target doc
2. the repository has a real `ControllerPort` / adapter-family ingress seam
3. player, agent, and program paths enter one shared actor-side ingress family
4. `CharacterRuntimeState` has been extracted enough that `CharacterReplica` is no longer the unbounded transitional owner
5. `CharacterIntentFrame` and `CharacterPresentationInput` are the active shared actor contracts
6. the final shared actor scene/runtime target is documented and implemented clearly enough for downstream character-agent work
7. Phase 0 verification remains green

---

## Handoff Rule

Only after this plan is sufficiently completed may the full character-agent plan honestly claim final-state `L4` convergence.

Before that point, character-agent work may:

- scaffold against current actor bridges
- validate upstream cognition, memory, and planning

but it must not declare final `L4 -> CharacterActor` convergence complete.
