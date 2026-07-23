# Full Character Agent Runtime With LLM Design

Status note: this spec still defines the broad runtime target, but unresolved live-provider closure work is now tracked by:

- `docs/superpowers/specs/2026-07-23-complete-llm-integration-closure-design.md`
- `docs/superpowers/plans/2026-07-23-complete-llm-integration-closure-implementation-plan.md`

## Problem

The repository has already proven a runnable Phase 0 dramatic loop with:

- `System L1` structured facts and authority settlement
- `ESM` world-truth execution boundaries
- `L6` authority event projection
- minimal `Siming` catalyst output
- Godot-side dialogue, attention, runtime-state, and presentation wiring

It has also established:

- the minimum backend-side `CharacterAgent L1 -> L4` slice
- targeted auditory private-percept support
- green `L1` reconnect / reseed / environment-cycle runtime proof

What is still missing is the actual full character-agent runtime shape defined by the main-project character-agent documents.

The current repo still does not yet provide:

- a full `CharacterAgent L1` private perception system
- a full `CharacterAgent L2` subjective interpretation and belief-update layer
- a full `CharacterAgent L3` planning layer with candidate generation and triple filters
- a full `CharacterAgent L4` five-channel execution coordinator
- persistent memory strong enough to support standard-agent behavior
- a real large-model reasoning loop for character cognition
- a unified treatment of `char_a`, `char_b`, and `char_c` as one role-runtime species with different control modes

The current repository mission also remains Phase 0 validation, not a detached framework exercise.

So the design must:

1. implement a full character-agent runtime in the current single-scene demo first
2. preserve `System L1 / ESM / Siming` authority boundaries
3. connect large-model reasoning where it belongs
4. keep the resulting architecture reusable instead of hardcoding one-off scene glue

## Primary Sources

This design is aligned to the main-project character-agent documents under:

- `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\角色智能体\01-角色智能体总纲.md`
- `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\角色智能体\03-感知链路与角色私有世界模型设计.md`
- `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\角色智能体\06-L3规划层与三重过滤器设计.md`
- `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\角色智能体\07-L4执行层与具身表达总纲.md`

This design also borrows architectural discipline from Hermes Agent:

- one unified runtime loop
- clear provider / context / storage separation
- session storage as a first-class primitive
- layered memory instead of one undifferentiated history bucket
- multi-instance isolation

Hermes ideas are adapted to role-runtime needs. This repo will not copy chat-assistant-specific surfaces such as user-profile markdown memory or generic tool-agent workflow semantics.

This design is also explicitly coupled to the active shared actor-substrate design and its implementation planning:

- `docs/superpowers/specs/2026-06-15-character-actor-architecture-optimization-design.md`
- `docs/superpowers/plans/2026-06-15-character-actor-architecture-optimization-implementation-plan.md`
- `docs/superpowers/plans/2026-06-15-character-actor-near-term-cleanup-implementation-plan.md`

## Goal

Build the first full character-agent runtime for the current Phase 0 demo.

This first full runtime covers:

- `char_a`
- `char_b`
- `char_c`

with these guarantees:

1. all three roles are instances of one unified character-agent architecture
2. `char_a` and `char_b` run as full auto agents
3. `char_c` runs as a full character-agent instance with player-priority assisted control
4. the runtime includes:
   - `CharacterAgent L1`
   - `CharacterAgent L2`
   - `CharacterAgent L3`
   - `CharacterAgent L4`
   - three-layer memory
   - large-model reasoning
   - active `ESM`-routed action requests
5. the implementation proves itself inside the current runnable scene instead of hiding in abstract framework shells

## Non-Goals

This design does not attempt to ship in this first slice:

- the full five-pool memory system from the main-project ideal
- production-grade `FACS/SACS/Binder/Canonical Rig` end-state
- final database deployment topology
- generalized multi-scene narrative orchestration
- direct replacement of `System L1`, `ESM`, or `Siming`
- a detached generic framework built before the current demo integration is proven

## Boundary Clarifications

### `System L1` is not `CharacterAgent L1`

The repository now has mature `System L1` surfaces for:

- raw fact production
- candidate compilation inputs
- authority settlement
- execution-side world result routing

But those surfaces do not mean the character-agent `L1` already exists in full.

`CharacterAgent L1` is the actor-private perception runtime that begins after:

`raw fact -> perceptible compilation -> per-character filtering`

Its responsibility is to construct and maintain the role’s private world entrance.

### `System L1` execution capability is not `CharacterAgent L4`

The repository also already has execution-capable `System L1 / Godot / ESM` paths.

That still does not mean the character-agent `L4` is done.

`CharacterAgent L4` is a multi-channel expression and action-coordination layer. It decides how intent becomes:

- speech
- face
- body
- social-spatial positioning
- physiology

The resulting action requests still route to `System L1 / ESM` for world-truth settlement.

### `CharacterAgent L4` must enter the current shared `CharacterActor` substrate

The repository already has an active shared actor-control substrate documented by the current `CharacterActor` architecture truth.

That substrate includes the current actor-shell / motor / presentation chain rather than separate player-only or NPC-only body species.

So the first full character-agent runtime must not create a parallel local embodiment path.

`CharacterAgent L4` must enter the existing shared actor substrate first.

In practice, that means:

- agent execution output is staged as actor-facing execution plans
- those plans are adapted into the current shared actor execution contracts
- the current shared local actor stack remains the owner of embodied local execution and presentation

The first implementation target is therefore:

- `CharacterIntentFrame`-compatible control adaptation
- `CharacterPresentationInput`-compatible presentation adaptation
- future-compatible `AgentControllerAdapter` / `ControllerPort` style seams

and not:

- direct scene-node imperative control from the agent runtime
- a second agent-only body runtime path
- bypassing the current `CharacterActor` substrate because the command originated from an agent

This rule preserves the repository-wide actor unification work:

- one shared actor substrate
- one local embodiment truth
- multiple control sources entering the same body/runtime stack

### Character agents do not read world truth directly

The character-agent business interface may only consume:

1. role-private perceived events
2. self-body perceived events
3. Siming catalyst messages
4. world / constraint / conversation writeback objects already narrowed to role meaning

It must not directly consume:

- the raw global fact stream as its business input
- hidden authority truth not perceived by that role
- direct Godot local keyboard / mouse / camera noise

## Scope Decision

The first full implementation will cover the current live scene first, not a detached generic framework-first effort.

This is intentional.

The repository needs the architecture proven inside the existing dramatic loop before wider extraction.

Implementation posture:

- scene-first proof
- architecture-true boundaries
- reusable interfaces from the start

This means:

- the runtime is built for `char_a / char_b / char_c` now
- the runtime objects, model gateway, storage schema, and agent loop are designed for later reuse
- generalization happens through stable runtime seams, not by deferring proof

### Final-State Requirement

This design is not defining a transitional truth as the target architecture.

The repository may temporarily reuse transitional files and compatibility shells during implementation, but the architectural target of this change is the final-state role runtime, not the transitional state itself.

That means:

- the design target is one unified final `CharacterAgent` architecture
- the design target is one unified final shared local actor substrate
- the design target is one clean final `L1 -> L2 -> L3 -> L4 -> CharacterActor -> System L1/ESM` execution chain

and not:

- preserving `CharacterBase` vs `CharacterReplica` split as the intended end state
- preserving compatibility wrappers as permanent architecture
- treating current migration seams as the future truth

If an implementation step temporarily lands through a transitional shell, that step must still move the repository closer to the final-state architecture and must not freeze the transition as the new long-term truth.

### Dependency On Shared Actor-Substrate Convergence

The final-state full character-agent runtime depends on the final-state convergence of the shared local actor substrate.

That dependency is architectural, not optional.

`CharacterAgent L4` cannot fully converge to its final-state execution boundary while the shared `CharacterActor` stack is still only documented and implemented as a transitional near-term cleanup target.

So the final-state delivery must be planned in two linked stages:

1. shared actor-substrate convergence plan
2. full character-agent convergence plan

The second stage depends on the first.

This means the character-agent implementation plan must not pretend that final `L4` convergence can be completed independently of the actor-substrate convergence work.

## Runtime Shape

The full runtime is one unified per-actor loop:

`Ingress -> L1 state update -> memory retrieval -> L2 reasoning -> L3 planning -> L4 staging -> settlement/writeback`

Each actor has its own isolated runtime instance.

### Why this shape

This adapts the Hermes-style unified runtime loop to character-agent semantics.

The repo should not grow separate brains for:

- dialogue
- motion reactions
- memory lookup
- player assistance
- Siming response

Those are all expressions of one role-runtime core.

## Per-Actor Runtime Loop

Each role owns one `CharacterAgentRuntimeLoop`.

Inputs include:

- `CharacterPerceivedEvent`
- `SelfBodyPerceivedEvent`
- `Siming` catalyst message
- world / constraint / conversation writeback
- explicit player intent override for `char_c`

The loop stages are:

1. `Ingress`
2. `L1 State Update`
3. `Memory Retrieval`
4. `L2 Reasoning`
5. `L3 Planning`
6. `L4 Staging`
7. `Settlement / Writeback`

### 1. Ingress

Responsibilities:

- normalize inbound event shape
- attach actor scope and lineage ids
- write event into session timeline
- route by current control mode

### 2. `CharacterAgent L1` State Update

Responsibilities:

- update the actor-private snapshot
- update attention state
- update working-memory window
- preserve clarity / certainty and partial / distorted / missed semantics

### 3. Memory Retrieval

Responsibilities:

- query episodic memory
- query relational / factual memory
- return a compact retrieval package for the current event and current tension

### 4. `CharacterAgent L2` Reasoning

Responsibilities:

- interpret current private reality
- update beliefs
- infer social meaning
- synthesize risk / opportunity / tension

### 5. `CharacterAgent L3` Planning

Responsibilities:

- activate goals
- generate candidate actions
- run triple-filter evaluation
- rank and select intent
- or emit a suggestion packet for `char_c`

### 6. `CharacterAgent L4` Staging

Responsibilities:

- split intent into five parallel expression channels
- generate presentation plans
- generate action requests
- generate dialogue acts and utterance requests
- adapt those outputs into the current shared `CharacterActor` substrate rather than directly controlling scene nodes

### 7. Settlement / Writeback

Responsibilities:

- send execution intents to `System L1 / ESM / Godot`
- receive authoritative results
- write the results back into timeline, state, and memory

## `CharacterAgent L1`

`CharacterAgent L1` must be implemented as a full actor-private perception layer.

It is not just a thin wrapper around current system runtime state.

It formalizes the latter half of the main-project perception chain:

- `Per-Character Perception Filter`
- `Private World Snapshot`

### Snapshot Contents

The minimum snapshot includes:

- `visible_entities`
- `audible_entities`
- `unresolved_signals`
- `active_anomalies`
- `current_attention_targets`
- `short_horizon_social_presence`
- `local_spatial_confidence_map`
- `recent_world_changes`
- `recent_constraint_results`
- `body_state_hints`
- `last_siming_catalyst`
- `vigilance_level`
- `distraction_level`
- `bias_tags`
- `clarity_score`
- `certainty_score`

### Perception Quality Requirements

The first full implementation must support:

- `clarity_score`
- `certainty_score`
- `partial_observation`
- `distorted_details`
- `missed_details`

### Sensory Modality Requirements

First full implementation must support:

- vision
- audition
- smell
- heat / atmosphere
- touch / proximity

Current repo maturity does not mean all modalities need identical richness on day one.

But structurally they must all have valid `L1` pathways and snapshot slots.

### Auditory Policy Update

The repo no longer freezes all auditory facts as `L1-only`.

The new first-full-runtime policy is:

- targeted actor-to-actor auditory facts enter the private perception path
- ambient environmental auditory context remains system-level until actor-private hearing attribution is fully designed

This is a deliberate intermediate step that preserves clean growth.

## Three-Layer Memory

The first full implementation uses:

1. `Working Memory`
2. `Episodic Memory`
3. `Relational / Factual Memory`

### Working Memory

Working memory is a short-horizon active context window, not the main persistence layer.

It contains:

- recent perceived events
- recent `ESM` results
- recent `Siming` catalysts
- recent dialogue turns
- current unresolved tensions
- current attention and bodily pressure

It drives immediate `L2/L3` reasoning.

### Episodic Memory

Episodic memory stores structured “what happened” records such as:

- someone approached
- someone lied
- a request failed
- a clue appeared
- the environment changed under specific tension

It is searchable and persistent.

### Relational / Factual Memory

This layer stores the actor’s belief-like persistent claims, such as:

- distrust
- alliance cues
- object ownership suspicions
- role-to-role significance
- world fact beliefs from prior episodes

This is not objective truth.

It is the actor’s current believed social or factual state.

### Persistence Rule

All three memory layers are designed from day one for:

- durable local storage
- future migration to a formal database schema

The first implementation does not treat memory as disposable in-process cache only.

## Session Storage

Memory and session history are separate.

### Event Timeline

The runtime stores a first-class per-actor session/event timeline with:

- ingress events
- `L2` outputs
- `L3` candidates
- selected intents
- `L4` plans
- outbound requests
- settlement results

This timeline exists for:

- debugging
- replay
- evaluation
- lineage tracing

### Derived Memory Store

The memory store persists extracted and consolidated memories derived from the event timeline.

This separation follows the same architectural lesson that Hermes applies to session history versus memory.

The repo should not force one storage layer to act as:

- raw log
- thought trace
- persistent memory
- retrieval index

all at once.

## `CharacterAgent L2`

`L2` is the main large-model subjective reasoning layer.

It is responsible for converting:

- private snapshot
- working-memory window
- retrieved episodic memory
- retrieved relational / factual memory

into:

- subjective interpretation
- belief deltas
- social meaning
- risk and opportunity understanding
- inner-state shift

### Suggested `L2` submodules

1. `Perception Interpreter`
2. `Belief Update Engine`
3. `Social Meaning Inference`
4. `Tension / Anomaly Synthesizer`

### `L2` output object

Minimum fields:

- `interpreted_situation`
- `belief_deltas`
- `social_read`
- `perceived_risk`
- `perceived_opportunity`
- `attention_pressure`
- `inner_state_shift`
- `reasoning_trace_summary`

## `CharacterAgent L3`

`L3` is the action-possibility-space manager.

It is the second large-model reasoning surface.

### Required internal modules

1. `Goal Activator`
2. `Candidate Generator`
3. `Constraint Projector`
4. `Triple Filter Engine`
5. `Priority Ranker`
6. `Intent Selector`

### Candidate action space

The first full implementation must support at least:

- `observe`
- `approach`
- `withdraw`
- `speak_public`
- `speak_private`
- `ask_probe`
- `lie`
- `withhold`
- `share_info`
- `inspect_object`
- `follow_target`
- `seek_private_distance`
- `break_contact`
- `self_protect`

### Triple filter contract

The triple filter remains:

1. `Persona Filter`
2. `Logic Filter`
3. `Gain/Loss Filter`

The model may assist with candidate generation and justification, but final mapped outcomes must remain structured and locally auditable:

- `rejected`
- `weakly_viable`
- `viable`
- `highly_compelling`

### `char_c` suggestion mode

For `char_c`, `L3` normally outputs a `Suggestion Packet` instead of forcing the final action.

That packet includes:

- `recommended_intents`
- `risk_notes`
- `urge_vector`
- `social_read`
- `why_this_now`
- `role_consistency_hint`

## `CharacterAgent L4`

`L4` is not a command enum mapper.

It is a five-channel execution coordinator:

1. `Speech Channel`
2. `Face Channel`
3. `Body Channel`
4. `Social-Spatial Channel`
5. `Physiology Channel`

### `L4` local embodiment boundary

`L4` is only complete when it enters the current shared `CharacterActor` execution substrate.

For this repository, the first full implementation must treat the following as the local embodiment host path:

- shared actor runtime shell
- shared motor / locomotion truth layer
- shared presentation composition layer
- shared post-animation embodiment modification layer

So `L4` must output plans that can be consumed by the current actor-side contracts instead of writing one-off imperative commands directly into:

- `CharacterReplica` internals
- `PlayerShell` internals
- arbitrary Godot nodes

The adapter target for the first implementation is:

- actor-facing control frames
- actor-facing presentation inputs
- shared control-mode aware actor execution packets

This keeps agent-originated execution and player-originated execution on one shared local actor substrate.

### Speech Channel

Produces:

- dialogue act
- utterance generation request
- delivery plan

### Face Channel

Produces:

- structured facial expression plan
- future `FACS`-aligned output contract

### Body Channel

Produces:

- posture
- head / neck / gesture
- weight / gait / motion emphasis plans

### Social-Spatial Channel

Produces:

- approach / withdraw / hold-distance behavior
- private-circle formation attempts
- target-follow or contact-break plans
- `action request` bundles when needed

### Physiology Channel

Produces:

- breath
- tremor
- guarding
- fatigue
- involuntary micro-action plans

This channel must remain active even when the player controls `char_c`.

## Large-Model Integration

### What uses the model

The first full implementation uses large models for:

- `L2`
- `L3`
- dialogue text generation

### What does not use the model directly

The model does not directly:

- consume raw fact streams
- write world-truth state
- bypass `ESM`
- issue low-level Godot execution instructions

### Model input rule

The model consumes structured role-private context built from:

- private snapshot
- working memory
- retrieved episodic memory
- retrieved relational / factual memory
- current control mode
- current action-policy constraints

### Model gateway

The system introduces:

- `CharacterModelGateway`
- `CharacterModelRouter`
- `CharacterContextBuilder`
- `CharacterPromptPolicy`
- `CharacterStructuredOutputValidator`

The default path uses online APIs.

The architecture must also allow:

- local models
- mixed online / local routing

without changing character business logic.

## Unified Control Modes

All roles share one runtime species and differ only by control mode.

### Modes

1. `agent_full_auto`
2. `player_priority_assisted`
3. `away_conservative_takeover`
4. `scripted_override`

### `char_a` and `char_b`

Default mode:

- `agent_full_auto`

### `char_c`

Default mode:

- `player_priority_assisted`

In this mode:

- `L1` and `L2` always run
- `L3` emits suggestions by default
- `L4` keeps automatic physiology and non-invasive micro-expression layers active
- explicit player intent overrides auto-selected intent

### Away conservative takeover

When `char_c` is disconnected, idle, or explicitly switched, it moves to:

- `away_conservative_takeover`

In this mode:

- only low-risk continuity-preserving actions are allowed
- no strong irreversible dramatic escalation is allowed

### Scripted override

Used only for orchestrated scripted moments.

It must still write events into the same runtime timeline.

It is not a replacement for the character runtime.

## Explicit Player Priority Rule

Intent priority is:

1. hard scripted override
2. explicit player intent
3. away conservative auto intent
4. full auto agent intent
5. background physiology / micro-expression

This prevents the agent from competing with the player while preserving role continuity.

## Active Action Requests

Character agents are allowed to initiate action requests.

But every world-relevant action still routes through `System L1 / ESM`.

### Allowed first-full-runtime active request classes

- `approach`
- `withdraw`
- `inspect_object`
- `seek_private_distance`
- `follow_target`
- `speak_public`
- `speak_private`
- `share_info`
- `withhold`
- `break_contact`

### Forbidden direct powers

Character agents may not directly:

- move objects authoritatively
- settle interactions
- rewrite body state truth
- decide environment state changes without `ESM`

## Directory Structure

The design introduces a dedicated backend domain:

- `backend/app/character_agent/`
- `backend/app/character_agent/runtime/`
- `backend/app/character_agent/models/`
- `backend/app/character_agent/memory/`
- `backend/app/character_agent/reasoning/`
- `backend/app/character_agent/planning/`
- `backend/app/character_agent/execution/`
- `backend/app/character_agent/storage/`
- `backend/app/character_agent/gateway/`

This may later map under `backend/app/l2/character_agent/`, but the internal separation still stands.

Godot remains thin and presentation-focused.

## Core Runtime Objects

The first full implementation introduces:

1. `CharacterAgentInstance`
2. `CharacterPrivateWorldSnapshot`
3. `CharacterWorkingMemoryState`
4. `CharacterInterpretationFrame`
5. `CharacterIntentPlan`
6. `CharacterExecutionPlan`
7. `CharacterRuntimeEvent`

These replace the idea that one dictionary or one service class can hold the whole role runtime safely.

## Storage Schema

The first full implementation must define persistent storage objects for:

- `character_runtime_events`
- `character_working_memory_snapshots`
- `character_episodic_memories`
- `character_relational_factual_memories`
- `character_control_mode_state`
- `character_model_runs`

The schema should be local-storage-friendly now and database-migration-friendly later.

## Integration With Current Repo

Current files remain useful anchors:

- `backend/app/services/candidate_percept_service.py`
- `backend/app/services/per_character_percept_filter.py`
- `backend/app/services/character_runtime_state_service.py`
- `backend/app/services/character_agent_runtime.py`
- `backend/app/services/character_agent_l1.py`
- `backend/app/services/character_agent_l2.py`
- `backend/app/services/character_agent_l3.py`
- `backend/app/services/character_agent_l4_adapter.py`
- `backend/app/main.py`
- `scripts/autoload/BackendBridge.gd`
- `scripts/autoload/LocalPresentationBus.gd`
- `scripts/character/CharacterReplica.gd`
- `scripts/phase0/MainDemoController.gd`

Current actor-substrate truth must also be treated as an explicit integration constraint:

- `docs/superpowers/specs/2026-06-15-character-actor-architecture-optimization-design.md`
- `docs/character/character-actor-architecture.md`
- `docs/character/character-control-chain.md`
- `scripts/character/CharacterReplica.gd`
- `scripts/character/CharacterActorSchema.gd`
- `scripts/character/CharacterMotor.gd`
- `scripts/player/PlayerShell.gd`

The new runtime must integrate with these surfaces instead of inventing a second local execution stack for agent-driven roles.

The new runtime does not replace those all at once.

Migration posture:

- introduce the new full runtime in dedicated directories
- keep legacy service names as compatibility shells if needed
- move traffic gradually to the new loop
- only clean up structure after the new behavior is proven

### Final-state integration goal

Current repo files may be used as bridge surfaces during implementation, but the final-state target is explicit:

- all dramatic roles map onto one shared final local actor substrate
- agent-originated execution and player-originated execution enter the same final actor execution chain
- character-agent execution does not permanently depend on a transitional split between player outer shell and replica inner shell

So implementation planning must distinguish:

- temporary bridge surfaces used to keep the demo runnable
- final-state runtime boundaries that must remain after convergence

The plan must not present transitional actor-shell layering as the final architecture.

### Planning dependency rule

The final implementation planning for this spec must explicitly link to the active CharacterActor spec and plans.

It must also split work into:

- a stage that finishes or formalizes the shared actor-substrate final-state convergence plan
- a stage that lands the full character-agent runtime onto that converged substrate

If the actor-substrate side does not yet have a final-state convergence plan, this spec's implementation planning must create or extend that plan first instead of silently assuming it already exists.

## Acceptance Criteria

The first full runtime is accepted when all are true:

1. `char_a / char_b / char_c` all run through one unified character-agent runtime species.
2. `char_a` and `char_b` run in `agent_full_auto`.
3. `char_c` runs in `player_priority_assisted`, with valid switch support to `away_conservative_takeover`.
4. `CharacterAgent L1` is fully implemented as private perception state rather than thin runtime glue.
5. Three-layer memory exists and is persistent:
   - working
   - episodic
   - relational / factual
6. `L2` uses large-model reasoning on role-private structured context.
7. `L3` uses large-model reasoning plus locally auditable triple-filter outputs.
8. Dialogue text generation uses the model but remains policy-constrained.
9. `L4` is split into five channels, even if some downstream mappings remain simplified in Phase 0 presentation.
10. `L4` enters the current shared `CharacterActor` substrate instead of creating a second agent-only embodiment path.
11. Character-originated action requests route through `System L1 / ESM`.
12. No character agent directly rewrites world truth.
13. Session timeline and memory store are both queryable.
14. Model runs are stored with enough metadata for audit and future routing work.
15. Existing Phase 0 authority boundaries remain intact.
16. The delivered architecture converges toward the final shared actor/runtime end state rather than freezing the current transitional shell split as permanent truth.
17. The implementation plan explicitly links and stays aligned with the shared CharacterActor spec and plan state rather than treating actor-substrate convergence as out-of-band work.

## Verification

Minimum required verification for implementation:

- backend unit tests for:
  - `L1` private snapshot updates
  - memory extraction and retrieval
  - `L2` structured reasoning outputs
  - `L3` triple-filter staging and selection mapping
  - control-mode switching for `char_c`
  - action-request routing boundaries
- websocket integration tests for:
  - `char_a / char_b` full-auto outputs
  - `char_c` suggestion packet mode
  - `char_c` away takeover behavior
  - memory writeback after settlement
- static boundary tests proving:
  - no raw-fact bypass into agent business logic
  - no direct world-truth override from agent outputs
- runtime verification showing:
  - character outputs visibly change the scene
  - `ESM` still remains the settlement authority
- `python -m pytest -v`
- `python scripts/verification/verify_phase0.py`
- `python scripts/verification/verify_phase1_slice.py`
- `python scripts/verification/verify_l1_runtime_edges.py`

## Why Hermes Matters Here

The Hermes influence is architectural, not thematic.

The repo should learn from Hermes that a strong agent system needs:

- one clear runtime loop
- provider abstraction
- session storage as a first-class primitive
- layered memory
- isolated agent instances

The repo should not imitate Hermes chat-assistant assumptions.

This system remains a world-embedded role runtime, not a generic helper bot.

## Summary

The first full character-agent implementation for this repository should:

- treat `char_a / char_b / char_c` as one runtime species
- build a real `CharacterAgent L1 -> L4`
- add persistent three-layer memory
- integrate large-model reasoning into `L2`, `L3`, and dialogue generation
- keep `System L1 / ESM / Siming` boundaries intact
- prove itself inside the current Phase 0 scene before broader extraction

This is the shortest path to a true character-agent runtime that is both architecture-correct and demo-real.
## 2026-07-23 Closure Status

The broad character-agent runtime remains larger than provider closure. For LLM live status, do not treat readiness, local continuity output, or partial dialogue success as proof. The approved provider closure requires the existing Character gateway and validator chain to pass dialogue, L2, and L3 live scenarios under one `LLM_CLOSURE_RUN_ID`.
