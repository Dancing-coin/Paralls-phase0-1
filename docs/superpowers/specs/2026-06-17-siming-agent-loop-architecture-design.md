# Siming Agent Loop Architecture Design

Status: awaiting-user-review

## Problem

The current Siming documentation set contains two complementary views:

- `docs/phase1/core/01-运行时核心/司命设计文档.md` defines the full Siming identity: a global L2 narrative intelligence with five core subsystems, high-level catalysis, four intervention principles, priority governance, and a runtime loop.
- `docs/phase1/core/01-运行时核心/司命/02-Phase1公平裁判型司命增强方案.md`, `04-Intervention Policy Engine 规则表.md`, `05-Godot Execution Feasibility Layer 接口契约.md`, and `19-司命接入事件总线后端设计.md` narrow that identity into engineering slices that can be implemented, tested, replayed, and connected to the authority event bus.

The next design step is to make the full Siming identity explicit as an Agent Loop architecture without reducing it to a passive event handler or an unconstrained LLM tool agent.

## Goal

Design Siming as a goal-driven, event-driven, policy-guarded, multi-agent narrative orchestration loop.

The design covers the full future-state single-room / single-session Siming loop and reserves explicit interfaces for cross-session memory, destiny seeds, and long-term evolution. It does not require those reserved capabilities to be implemented immediately.

## Non-Goals

- Do not design a generic LangChain-style autonomous tool agent.
- Do not let an LLM directly publish authority events or call ESM, Character, L3, or Godot APIs.
- Do not replace ESM physical authority, Character autonomy, Visual Fact boundaries, or AuthorityEventBus.
- Do not make read models, dashboards, memories, or model outputs authoritative world truth.
- Do not expand this spec into an implementation plan.
- Do not require cross-session evolution in the first implementation slice.

## Source Of Truth

Primary source:

- `docs/phase1/core/01-运行时核心/司命设计文档.md`

Engineering slices:

- `docs/phase1/core/01-运行时核心/司命/02-Phase1公平裁判型司命增强方案.md`
- `docs/phase1/core/01-运行时核心/司命/04-Intervention Policy Engine 规则表.md`
- `docs/phase1/core/01-运行时核心/司命/05-Godot Execution Feasibility Layer 接口契约.md`
- `docs/phase1/core/01-运行时核心/司命/19-司命接入事件总线后端设计.md`
- `docs/superpowers/specs/2026-06-15-siming-phase1-llm-authority-bus-runtime-design.md`

## Architecture Choice

Use `SimingOrchestrator + five subsystem ports + engineering guardrail ports`.

Rejected alternatives:

- Single monolithic `SimingAgentLoop`: simpler initially, but it would collapse observe, state, planning, guardrails, dispatch, model routing, and audit into one large unit.
- Immediate multi-agent runtime: closer to a future distributed Siming, but too early before the domain objects and lifecycle are stable.

The orchestrator owns loop scheduling and lifecycle. Subsystems own domain-specific reasoning. Guardrail ports own deterministic boundaries.

## Core Identity

Siming is a narrative runtime director, not a direct executor.

Its loop is:

```text
Observe
  -> State
  -> Reason / Plan
  -> Guard
  -> Act
  -> Observe Result
  -> Loop
```

In domain terms:

```text
AuthorityEvent / ESM / Character / L1 / L3 inputs
  -> ObservePipeline
  -> FactCore / KnowledgeGraph / BalanceSystem / NarrativeState
  -> GoalStack + ConflictGenerator + ModelRouter
  -> InterventionCandidate
  -> Fact veto + PolicyGuard + ExecutionFeasibility
  -> InterventionDecision
  -> InterventionExecutor
  -> siming.* high-level events
  -> downstream results
  -> Audit / Replay / State correction
```

## Goal Stack

Siming uses a hierarchical goal stack. Higher layers constrain lower layers:

1. Destiny theme / core session tension.
2. Dramatic progression / prevent stagnation.
3. Fair play / preserve player and character participation windows.
4. Minimal intervention / prefer natural, local, weaker catalysis.
5. Auditability and replayability / every action and no-action must be explainable.

This makes Siming neither drama-maximizing nor fairness-only. It can actively reason about how to influence the story, but every action is judged against the full stack.

## Components

### `SimingOrchestrator`

Responsibilities:

- Drive the Agent Loop.
- Manage event-triggered, scheduled, and phase ticks.
- Route work into priority lanes.
- Invoke subsystem ports.
- Compose decisions from subsystem outputs.
- Never directly mutate world truth, ESM state, Character state, or Godot presentation state.

Status: required.

### `GoalStack`

Responsibilities:

- Represent session destiny theme, dramatic pressure, fair-play needs, intervention minimality, and audit requirements.
- Provide priority ordering when goals conflict.
- Produce goal weights for planning, not direct actions.

Status: required for the complete design; can begin as a fixed configuration in an implementation slice.

### `ObservePipeline`

Responsibilities:

- Consume events Siming is allowed to observe.
- Normalize raw and structured events into Siming input objects.
- Preserve source, causation, correlation, phase, and timing metadata.
- Reject or ignore events outside Siming visibility.

Inputs include:

- world facts
- ESM results
- constraint state
- visual facts
- character behavior results
- knowledge propagation changes
- room phase signals

Status: required.

### `FactCorePort`

Responsibilities:

- Maintain T0-T3 fact boundaries.
- Track established, rejected, and locked facts.
- Detect contradictions.
- Veto candidates that reveal unknown information or rewrite locked truth.

It guards truth. It does not optimize drama.

Status: required; may start with a narrow fact-lock model.

### `KnowledgeGraphPort`

Responsibilities:

- Track who knows what.
- Track who knows that others know.
- Model conversation access, eavesdropping, sharing, misunderstanding, privacy risk, and membership state.
- Expose structured knowledge summaries to planning and guards.

It infers social and knowledge state from L1 / ESM / event facts. It must not invent raw spatial or acoustic facts.

Status: reserved-to-required. The interface must exist early; full graph depth can be incremental.

### `BalanceSystemPort`

Responsibilities:

- Detect information monopoly.
- Detect participation starvation.
- Detect private-channel lock.
- Detect suspicion runaway.
- Detect evidence bottlenecks.
- Produce pressure signals that planning can act on.

Status: required.

### `ConflictGeneratorPort`

Responsibilities:

- Enumerate conflict opportunities.
- Identify secondary event candidates.
- Identify environmental catalysis windows.
- Identify phase closure and ending opportunities.
- Estimate narrative value and risks.

Status: required for full Siming; can start as a bounded candidate generator.

### `ModelRouterPort`

Responsibilities:

- Route reasoning tasks to rules, small models, large models, or specialist sub-agents.
- Enforce latency budgets and priority lanes.
- Return candidate-level outputs only.

Routes include:

- rule route for hard boundaries and deterministic filters
- small-model route for classification and fast scoring
- large-model route for complex narrative reasoning
- specialist route for future Fact Auditor, Conflict Scout, Knowledge Agent, Narrative Planner, and Ending Agent

Status: required as a port. Concrete routes may be added gradually.

### `InterventionPlanner`

Responsibilities:

- Convert opportunities and model outputs into `InterventionCandidate` objects.
- Select proposed intervention bands:
  - `impulse`
  - `opportunity`
  - `fact_reveal`
  - `environment_request`
  - `none`
- Preserve candidate reasoning, expected narrative effect, risk tags, and required downstream path.

Status: required.

### `PolicyGuard`

Responsibilities:

- Enforce indirectness, invisibility, logical consistency, and fairness.
- Protect Character autonomy.
- Prevent locked-truth rewrite.
- Prevent ESM bypass.
- Downgrade or reject unsafe candidates.

Status: required.

### `ExecutionFeasibilityPort`

Responsibilities:

- Decide whether a candidate can naturally land in the current engine and room state.
- Select one path:
  - `character_input_path`
  - `environment_change_path`
  - `visual_fact_path`
  - `l3_highlight_path`
  - `no_action`
- Return deterministic decisions for the same candidate and context.

Status: required.

### `InterventionExecutorPort`

Responsibilities:

- Publish high-level `siming.*` events through the authority event bus.
- Never publish physical success facts.
- Never call ESM, Character, L3, or Godot directly.
- Preserve causation, correlation, idempotency, TTL, priority, and audit references.

Status: required.

### `AuditReplayPort`

Responsibilities:

- Record observations, candidates, vetoes, downgrades, dispatches, acknowledgements, timeouts, rejections, no-actions, and corrections.
- Support replay by `correlation_id`, `causation_id`, and `event_id`.
- Explain why Siming acted and why it did not choose alternatives.

Status: required.

### `LongTermMemoryPort`

Responsibilities:

- Reserve cross-session player style profile.
- Reserve recurring theme memory.
- Reserve destiny seed library.
- Reserve unresolved archetype patterns.
- Reserve preferred pacing profile.
- Reserve cross-session safety notes.

Long-term memory may influence new-session theme suggestions, conflict seed selection, pacing preferences, and safety constraints. It must never overwrite current-session locked facts, physical results, Character immediate psychology, or ESM success facts.

Status: reserved port.

## Priority Lanes

Siming work is not one FIFO queue.

```text
P0 Hard Guard Lane
  fact conflict, locked truth, critical safety, immediate veto
  rule-only, no LLM wait

P1 State Maintenance Lane
  fact ingestion, knowledge updates, ESM / Character / VisualFact result handling
  fast, replayable, concurrent

P2 Deliberation Lane
  dramatic progression, conflict opportunity, customized catalysis
  may call model router

P3 Atmosphere / Optional Lane
  low-value hints, ambience, delayed enhancements
  degradable, droppable, deferrable
```

P0 and P1 must not be blocked by P2 model calls. P3 can be dropped under load.

## Tick Triggers

Siming has three tick types:

- Event-triggered tick: important AuthorityEvent, ESM result, Character behavior, VisualFact, or constraint change.
- Scheduled tick: periodic pacing, participation, information bottleneck, and cooldown checks.
- Phase tick: phase transition, case escalation, ending approach, or room closure.

The loop is event-driven but can still perform scheduled and phase-level deliberation.

## Action Boundaries

Allowed high-level outputs:

- `siming.impulse`
- `siming.opportunity`
- `siming.fact_reveal`
- `siming.environment_request`
- `siming.visual_observability_request`
- `siming.presentation_highlight_request`
- `siming.no_action_recorded`

Forbidden outputs:

- direct `world_fact` success
- direct ESM state mutation
- direct Character movement, dialogue, or psychological truth
- direct Godot animation, transform, or bone command
- direct creation of an unestablished fact
- direct bus bypass

## Downstream Collaboration

### Character Runtime

Receives `impulse`, `opportunity`, and `fact_reveal`.

Character remains autonomous and returns ack, result, ignore, reject, or behavior events. Siming may observe and re-plan, but it must not force execution.

### ESM

Receives `environment_request`.

ESM decides whether physical, spatial, and rule constraints allow the request. ESM returns accept, reject, constraint, or world fact result. Siming must not rewrite rejection as success.

### VisualFact / Perception Boundary

Receives `visual_observability_request`.

It can amplify established facts. It must not create facts.

### L3 / Godot Presentation

Receives `presentation_highlight_request`.

It chooses presentation strategy and degradation. It is not world truth authority.

### AuthorityEventBus

All cross-system inputs and outputs go through the bus. The bus preserves causation, correlation, priority, TTL, durability, and replay chain.

## Model And Sub-Agent Output Contract

Model and sub-agent outputs must be normalized before they affect the loop.

Input shape:

```text
SimingReasoningContext
  room_id
  phase
  goal_stack
  fact_state_summary
  knowledge_state_summary
  balance_state
  narrative_pressure
  recent_events
  recent_interventions
  forbidden_actions
  available_paths
  latency_budget
  priority_lane
```

Output shape:

```text
InterventionCandidate
  candidate_id
  reason
  proposed_band
  target_actor_ids
  target_object_ids
  target_environment_ids
  established_fact_refs
  expected_narrative_effect
  risk_tags
  confidence
  required_downstream_path
```

Forbidden model outputs:

- authority event
- selected final decision
- physical success claim
- Character belief truth
- ESM mutation
- Godot command

All model outputs pass through:

```text
CandidateNormalizer
  -> FactCorePort
  -> PolicyGuard
  -> ExecutionFeasibilityPort
  -> AuditReplayPort
```

## State Model

### Working State

Per tick:

- current event batch
- state snapshot
- reasoning context
- candidate set
- decision set
- dispatch plan

### Runtime State

Per room / session:

- fact state
- knowledge state
- balance state
- narrative state
- intervention state
- priority lane state
- audit cursor

### Read Models

Read models explain the loop. They do not become authority.

- Siming dashboard read model
- Narrative read model
- Audit replay model

Principle:

```text
Memory informs planning.
Memory never overwrites truth.
Read models explain decisions.
Read models never become authority.
```

## Error Handling And Degradation

| Condition | Behavior |
| --- | --- |
| LLM timeout | Use rule candidates, small-model candidates, or `no_action`; audit `llm_timeout` / `degraded`. |
| Invalid model output | Reject during normalization; do not act; audit `invalid_candidate`. |
| Fact conflict | FactCore veto; audit `fact_veto`. |
| Policy violation | Reject or downgrade; audit `policy_rejected` / `downgraded`. |
| Execution infeasible | Select fallback path or `no_action`; audit `feasibility_rejected`. |
| ESM rejection | Do not rewrite as success; re-plan or `no_action`; audit `esm_rejected`. |
| Character ignored impulse | Treat as natural feedback; do not force; audit `character_ignored`. |
| Queue overload | Preserve P0/P1, degrade P2, drop or delay P3; audit `load_shed` / `delayed`. |

## Testing And Acceptance

### Model And Schema Tests

- goal stack
- state snapshot
- intervention candidate
- intervention decision
- audit record

### Loop Unit Tests

- event batch to state update
- state to candidate generation
- candidate to policy decision
- decision to dispatch event
- result event to audit correction

### Boundary Tests

- LLM cannot publish events.
- Siming cannot write world fact success.
- `environment_request` success can only come from ESM.
- Character input cannot force belief or dialogue.
- Visual path can only reference established facts.

### Replay Tests

- Same event chain yields the same class of decision.
- `no_action` has audit.
- Late result appends correction.
- Duplicate dispatch is suppressed.

### Load And Priority Tests

- P0 is not blocked by P2.
- P3 can be dropped.
- LLM timeout does not block FactCore.
- Concurrent events preserve deterministic ordering.

### Narrative Scenario Tests

- information monopoly -> `fact_reveal` / `opportunity`
- participation starvation -> `opportunity`
- private channel lock -> `environment_request` / `opportunity`
- suspicion runaway -> low `impulse` / `fact_reveal`
- balanced state -> `no_action`

## Acceptance Criteria

The full Siming Agent Loop architecture is satisfied when the system can prove:

1. It continuously consumes authorized authority events.
2. It maintains queryable runtime state.
3. It generates candidates from the goal stack and current state.
4. It reviews every candidate through fact, policy, feasibility, and audit guards.
5. It influences Character, ESM, VisualFact, and L3 only through high-level events.
6. It handles rejection, timeout, no-action, duplicate, and late-result paths.
7. It can replay why it acted and why it did not act.
8. It exposes stable ports for currently unimplemented subsystems without requiring the main loop to be rewritten.

## Open Implementation Notes

- The first implementation plan should not attempt the whole future state at once.
- `SimingOrchestrator`, `GoalStack`, `ObservePipeline`, `FactCorePort`, `BalanceSystemPort`, `ModelRouterPort`, `PolicyGuard`, `ExecutionFeasibilityPort`, `InterventionExecutorPort`, and `AuditReplayPort` should be treated as the primary skeleton.
- `KnowledgeGraphPort`, `ConflictGeneratorPort`, specialist sub-agents, P0-P3 distributed scheduling, and `LongTermMemoryPort` should be defined as stable ports even if initially backed by deterministic or stub implementations.
- The current LLM route router fits under `ModelRouterPort`.
- Existing Phase 1 engineering slice documents should constrain implementation safety, but this spec remains the higher-level Siming Agent Loop architecture blueprint.
