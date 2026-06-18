# Character Agent Runtime Architecture

This document describes the current in-repo character-agent runtime as it actually exists in code.

It is intentionally narrower than the long-term design docs.

Use this file when you need to answer:

- what the current backend character-agent stack is
- how it reaches Godot runtime consumers
- which parts are already main-path truth
- which parts are still compatibility or transitional layers

## Current Status In One Sentence

The repository now has a real `CharacterAgentRuntime` path that goes from private perception through memory, interpretation, planning, execution staging, websocket delivery, and shared actor ingress, but it is not yet a final single-path `L4 -> CharacterActor` convergence.

## Runtime Shape

Current runtime chain:

```text
CharacterPerceivedEvent / SelfBodyPerceivedEvent / siming_output
-> CharacterAgentRuntime
-> CharacterAgent L1 private snapshot
-> session timeline + memory writeback
-> CharacterAgent L2 interpretation
-> CharacterAgent L3 intent planning
-> CharacterAgent L4 execution plan
-> thin legacy command compatibility
-> websocket message delivery
-> BackendBridge / LocalPresentationBus
-> CharacterReplica shared actor ingress
-> CharacterRuntimeState / CharacterPresentationInput
-> KnightRoleSkin local embodiment
```

## Main Backend Owner

Primary runtime owner:

- `backend/app/character_agent/runtime/runtime_loop.py`

This runtime currently orchestrates:

- supported actors: `char_a`, `char_b`, `char_c`
- control modes:
  - `char_a` -> `agent_full_auto`
  - `char_b` -> `agent_full_auto`
  - `char_c` -> `player_priority_assisted`
- intake of:
  - `CharacterPerceivedEvent`
  - `SelfBodyPerceivedEvent`
  - `siming_output`
- session timeline writeback
- memory-store writeback
- `L2` reasoning request assembly
- `L2` interpretation
- `L3` intent selection
- `L4` execution-plan staging
- `char_c` suggestion packet staging instead of forced autonomous execution

## Character-Agent Internal Layers

### L1 Private Perception

Main file:

- `backend/app/character_agent/reasoning/l1_perception.py`

Current private snapshot host:

- `backend/app/character_agent/models/private_world_snapshot.py`

Current `L1` stores actor-private state such as:

- `visible_entities`
- `audible_entities`
- `unresolved_signals`
- `active_anomalies`
- `attention_targets`
- `current_attention_targets`
- `short_horizon_social_presence`
- `local_spatial_confidence_map`
- `body_state_hints`
- `clarity_score`
- `certainty_score`
- `vigilance_level`
- `distraction_level`
- `recent_constraint_results`
- `recent_world_changes`
- `last_siming_catalyst`

Current reality:

- visual perceived events populate `visible_entities`
- auditory perceived events populate `audible_entities`
- low-clarity or low-certainty unresolved signals elevate anomaly/distraction state
- self-body events populate `body_state_hints`
- Siming output can elevate `vigilance_level`

### Timeline And Memory

Main files:

- `backend/app/character_agent/storage/session_store.py`
- `backend/app/character_agent/storage/memory_store.py`
- `backend/app/character_agent/memory/working_memory.py`
- `backend/app/character_agent/memory/episodic_memory.py`
- `backend/app/character_agent/memory/relational_memory.py`

Current memory layers:

- working memory
- episodic memory
- relational memory

Current timeline writes include:

- `character_perceived_event`
- `self_body_perceived_event`
- `siming_output_event`
- `relational_belief_event`
- `l2_reasoning_request`
- `character_interpretation_event`
- `character_agent_execution_request`
- `character_agent_settlement_result`
- `character_agent_dialogue_response`
- `character_agent_suggestion_packet`

Current memory extraction truth:

- perceived events write episodic summaries
- settlement results write episodic summaries using `change_summary`, `constraint_summary`, `stable_state_summary`, then `result_type`
- dialogue responses write episodic summaries as `dialogue_response:<content>`
- relational belief events write relational memory entries

### L2 Interpretation

Main file:

- `backend/app/character_agent/reasoning/l2_reasoner.py`

Gateway path:

- `backend/app/character_agent/gateway/model_gateway.py`

`L2` currently turns private snapshot plus event context into `CharacterInterpretation`.

Current output fields include:

- `interpreted_summary`
- `interpretation_type`
- `salience_score`
- `ambiguity_level`
- `risk_level`
- `opportunity_level`
- `attention_target`
- `inner_prompt_candidate`

Current repo truth:

- `L2` already uses the model gateway as its runtime path
- local fallback behavior still exists
- guarded relational memory can elevate risk interpretation for the current attention target

### L3 Planning

Main file:

- `backend/app/character_agent/planning/l3_planner.py`

`L3` currently handles:

- candidate intent generation
- triple-filter evaluation
- selected intent mapping
- `char_c` player-priority suggestion packets

Current planner truth:

- model output and local candidate/filter logic are merged
- guarded relational memory can bias planning toward more defensive intent
- recent world changes, constraints, vigilance, and distraction can change recommendation ordering
- `char_c` suggestion packets are written into timeline and memory rather than staying frontend-only

### L4 Execution

Main files:

- `backend/app/character_agent/execution/l4_executor.py`
- `backend/app/character_agent/execution/l4_adapter.py`

Current `L4Executor` is the real execution-semantics owner.

It produces:

- `speech_channel`
- `face_channel`
- `body_channel`
- `social_spatial_channel`
- `physiology_channel`

It also stages:

- `actor_control_frames`
- `presentation_plan`
- `action_request_bundle`

Current execution semantics already use snapshot-side context such as:

- `recent_constraint_results`
- `recent_world_changes`
- `body_state_hints`
- `vigilance_level`

This affects posture, guarding, spacing, breath, and expression.

## Model Gateway Surface

Main files:

- `backend/app/character_agent/gateway/model_gateway.py`
- `backend/app/character_agent/gateway/model_provider.py`
- `backend/app/character_agent/gateway/model_router.py`
- `backend/app/character_agent/gateway/context_builder.py`
- `backend/app/character_agent/gateway/prompt_policy.py`
- `backend/app/character_agent/gateway/output_validator.py`

Current gateway responsibilities:

- build structured context from snapshot + memory + control mode
- build prompt and policy
- resolve route
- call provider
- validate structured output

Current repo boundary:

- the provider surface is still a single endpoint plus offline fallback shape
- this is not a new multi-provider runtime
- current character logic is not allowed to be described as completed multi-provider convergence

## Godot Delivery Path

Backend-side message source:

- `backend/app/main.py`

Godot-side bridge path:

- `scripts/autoload/BackendBridge.gd`
- `scripts/autoload/LocalPresentationBus.gd`

Current delivery shape:

```text
backend character-agent output
-> websocket message `character_agent_execution`
-> BackendBridge
-> LocalPresentationBus.character_agent_execution_received
-> CharacterReplica._on_character_agent_execution_received(...)
```

Current runtime proof truth:

- `character_agent_execution` is the runtime delivery path
- `character_agent_output(command_type)` is not the runtime main path
- `character_agent_output` remains compatibility-only on the bridge/bus side

## Shared Actor Ingress

Main files:

- `scripts/character/CharacterReplica.gd`
- `scripts/character/CharacterRuntimeState.gd`
- `scripts/character/CharacterPresentationInput.gd`
- `scripts/character/AgentControllerAdapter.gd`
- `scripts/character/CharacterControllerPort.gd`

Current actor-side handling is:

```text
character_agent_execution payload
-> AgentControllerAdapter
-> CharacterControllerPort.normalize_intent_frame(...)
-> CharacterRuntimeState.stage_agent_execution(...)
-> CharacterRuntimeState side-effect plan
-> CharacterPresentationInput-shaped runtime data
-> KnightRoleSkin.apply_presentation_input(...)
```

Current actor-side side effects include:

- focus target lookup
- physiology hint emission
- role-state effect triggering

This is why current repo truth should be described as:

- shared actor ingress is real
- shared actor presentation boundary is real
- final actor convergence is still incomplete

## Control-Mode Split

Current runtime behavior differs by control mode:

- `agent_full_auto`
  - runtime can proceed through `L4`
  - compat commands can be emitted
- `player_priority_assisted`
  - runtime still performs perception, reasoning, and planning
  - autonomous compat commands are suppressed
  - structured suggestion packets are emitted and stored
- `away_conservative_takeover`
  - only a narrow allowed command subset is permitted

This means `char_c` is already inside the same runtime species, but with assisted-control arbitration.

## Compatibility Layers That Still Exist

Current important transitional facts:

- `CharacterAgentL4Adapter` still exists as a thin compatibility shell
- legacy `CharacterGoalCommand` still exists as an outward compatibility shape
- `CharacterReplica` is still the actor runtime shell
- full final `L4 -> CharacterActor` convergence must not be claimed yet

The honest current statement is:

```text
L4Executor is the execution-plan-first path.
L4Adapter is a thin compatibility path derived from that plan.
```

## What Is Already Main-Path Truth

Current main-path truths:

- private actor perception is real
- timeline and memory writeback are real
- `L2` and `L3` run through the model gateway surface
- `L4Executor` is the real execution-plan owner
- `character_agent_execution` is the Godot runtime ingress path
- `CharacterReplica` consumes execution through the shared actor ingress family
- `char_c` player-priority assisted suggestion mode is real runtime behavior

## What Is Not Yet Honest To Claim

Current repo truth does not support claiming:

- Stage B complete
- full `CharacterAgent` runtime complete
- final single-path `L4 -> CharacterActor` convergence complete
- full actor-side Stage 2 closeout complete

## Related Docs

- `docs/character/character-actor-architecture.md`
- `docs/character/character-control-chain.md`
- `docs/character/character-actor-migration-status.md`
- `docs/character/character-actor-final-convergence-target.md`
- `docs/superpowers/plans/2026-06-15-character-actor-final-convergence-implementation-plan.md`
- `docs/superpowers/plans/2026-06-15-full-character-agent-runtime-with-llm-implementation-plan.md`
