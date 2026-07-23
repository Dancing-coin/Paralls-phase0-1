# Siming Phase 1 LLM Authority Bus Runtime Design

Status: approved

Status note: the architectural boundary remains valid, but unresolved live-provider closure and verification work is now tracked by:

- `docs/superpowers/specs/2026-07-23-complete-llm-integration-closure-design.md`
- `docs/superpowers/plans/2026-07-23-complete-llm-integration-closure-implementation-plan.md`

## Problem

`Phase 1` needs Siming to become a real runtime participant rather than a static catalyst stub, while still following the documented backend authority event bus design.

The repository already has a rule-based Siming runtime path:

- `AuthorityEvent`
- `AuthorityEventBus`
- `SimingEventConsumer`
- `SimingRuntime.tick()`
- `SimingEventProducer`
- replay / audit projections

The missing capability is large-model reasoning inside this path. That reasoning must not become a parallel control channel, direct Godot command path, direct `ESM` mutation path, or direct bus publisher.

## Goal

Add a Phase 1 design for LLM-assisted Siming that keeps the authority event bus as the only cross-system runtime channel.

The LLM should help Siming generate and explain candidate interventions, but the bus, schema, policy, feasibility, audit, and downstream ownership boundaries remain authoritative.

## Non-Goals

- Do not make the LLM publish `siming.*` bus events directly.
- Do not let the LLM write world facts, physical success results, or locked `T2+` truth.
- Do not let the LLM directly control character low-level movement, speech, or psychology.
- Do not let the LLM bypass `ESM` for environment changes.
- Do not introduce a separate Siming private message bus.
- Do not make `siming.dispatch_requested` a formal bus event.
- Do not move `world_ts` or `sim_tick_ts` into the public event envelope.
- Do not require full narrative projection, multi-step dramatic chain search, or persistent world simulation for Phase 1.

## Source Of Truth

This design follows:

- `docs/phase1/core/01-运行时核心/事件总线/01-事件总线总纲.md`
- `docs/phase1/core/01-运行时核心/事件总线/02-后端权威叙事与事实总线设计.md`
- `docs/phase1/core/01-运行时核心/事件总线/05-事件信封与字段分层规范.md`
- `docs/phase1/core/01-运行时核心/司命/07-Siming Orchestrator Interface Contract.md`
- `docs/phase1/core/01-运行时核心/司命/17-司命Canonical Schema与验收对象.md`
- `docs/phase1/core/01-运行时核心/司命/18-司命Phase1测试与验收计划.md`
- `docs/phase1/core/01-运行时核心/司命/19-司命接入事件总线后端设计.md`

## Architecture

The runtime chain is fixed:

```text
L1 / ESM / Character / Visual Fact producers
  -> AuthorityEvent
  -> AuthorityEventBus
  -> SimingEventConsumer
  -> SimingRuntime.tick()
      -> Fact Core / Knowledge Read
      -> FairnessStateSnapshot
      -> LLM Candidate Provider
      -> Intervention Policy Engine
      -> Execution Feasibility Layer
      -> InterventionDecision
      -> Checkpoint / Audit / NarrativeReadModel
  -> SimingEventProducer
  -> AuthorityEventBus
  -> Character / ESM / VisualFact / L3 downstream owners
```

The LLM is an internal collaborator of `SimingRuntime.tick()`. It is not a producer on the authority event bus.

## Components

### `SimingEventConsumer`

Keeps its documented role:

- subscribe to only Siming-allowed event families
- validate public envelope shape
- reject non-authority or non-Siming-visible events
- convert accepted events into `SimingInput`

It must not call the LLM.

### `SimingRuntime`

Owns the orchestration sequence:

1. consume `SimingInput`
2. build or refresh `FairnessStateSnapshot`
3. decide whether LLM assistance is needed
4. request candidate suggestions from `LlmCandidateProvider`
5. normalize suggestions into `InterventionCandidate`
6. run policy mapping and guardrails
7. run execution feasibility
8. produce `InterventionDecision`
9. create checkpoints, audit records, and read model updates

This is the only layer that may invoke LLM-assisted Siming reasoning.

### `LlmCandidateProvider`

A new internal port, not a bus adapter.

Minimum interface:

```python
class LlmCandidateProvider:
    def generate_candidates(
        self,
        *,
        snapshot: FairnessStateSnapshot,
        recent_events: list[AuthorityEvent],
        recent_audit: list[InterventionAuditRecord],
    ) -> list[InterventionCandidate]:
        ...
```

The provider receives structured context only. It does not receive raw Godot state, raw pose streams, private chain-of-thought, or unrestricted world state.

Provider and model choice is handled by a runtime-internal route router. Each route declares its provider type, model, endpoint, credential source, timeout, and enabled state; `SimingRuntime.tick()` still sees only the `LlmCandidateProvider` port and receives canonical candidates. The router may try multiple configured routes, and explicitly configured legacy provider order can be appended as migration fallback, but it remains an internal collaborator and must not publish authority events, bypass policy/feasibility, or create a second bus.

Allowed output:

- `InterventionCandidate`
- candidate explanation fields
- confidence / uncertainty fields
- optional reason tags for audit

Forbidden output:

- `AuthorityEvent`
- `InterventionDecision`
- direct selected bus event family
- physical success result
- character low-level command
- role belief truth
- `ESM` state mutation

### `Intervention Policy Engine`

Turns candidate intent into allowed Phase 1 intervention bands:

- `impulse`
- `opportunity`
- `fact_reveal`
- `environment_request`
- `none`

It rejects candidates that:

- reference unknown facts
- reveal information to an actor who should not know it
- imply a locked truth rewrite
- skip role autonomy
- skip `ESM`
- require a Phase 2+ narrative projection object

### `Execution Feasibility Layer`

Checks whether a candidate can land through a documented path:

- `character_input_path`
- `environment_change_path`
- `visual_fact_path`
- `l3_highlight_path`
- `no_action`

The LLM may explain why a path is desirable, but this layer decides whether it is executable.

### `SimingEventProducer`

Keeps exclusive responsibility for converting accepted Siming domain objects into authority bus events.

Formal output event families include:

- `siming.fairness_snapshot`
- `siming.intervention_candidate`
- `siming.intervention_decision`
- `siming.impulse`
- `siming.opportunity`
- `siming.fact_reveal`
- `siming.environment_request`
- `siming.visual_observability_request`
- `siming.presentation_highlight_request`
- `siming.no_action_recorded`

`siming.dispatch_requested` remains forbidden as a formal bus event.

## Data Flow

### Visual Fact Example

```text
visual_fact_event(light_level_drop)
  -> SimingEventConsumer
  -> FairnessStateSnapshot
  -> LLM Candidate Provider suggests "make established light drop easier for char_b to notice"
  -> Policy Engine maps to fact_reveal candidate
  -> Execution Feasibility chooses visual_fact_path
  -> InterventionDecision
  -> SimingEventProducer emits siming.visual_observability_request
  -> downstream visual / presentation owner handles observability
  -> audit records effective / unknown_effect / ack_timeout
```

### Environment Request Example

```text
esm_result_event or world_fact_event
  -> SimingRuntime sees a stalled clue path
  -> LLM suggests a small environmental catalyst
  -> Policy Engine ensures it does not assert physical success
  -> Execution Feasibility chooses environment_change_path
  -> SimingEventProducer emits siming.environment_request
  -> ESM accepts or rejects
  -> esm_result_event / constraint_state_event returns through AuthorityEventBus
  -> audit is completed or corrected
```

## Error Handling

### LLM Timeout

If the LLM times out:

- no bus event is emitted directly from the failed request
- runtime falls back to rule-generated candidates or `no_action`
- audit records `degraded` or an equivalent internal reason
- read model exposes that LLM assistance was unavailable

### Invalid LLM Output

If LLM output fails schema normalization:

- invalid output is discarded
- no `InterventionCandidate` is created from it
- audit records validation failure
- runtime continues with fallback candidates or `no_action`

### Unsafe Candidate

If the candidate violates policy:

- policy engine rejects it
- `InterventionDecision` becomes `no_action` or a lower-risk alternative
- rejection reason is preserved in audit

### Downstream Rejection

If `ESM`, character runtime, visual fact boundary, or L3 rejects or times out:

- Siming does not rewrite the result as success
- audit transitions to `esm_rejected`, `ack_timeout`, `unknown_effect`, or equivalent status
- late results append correction records rather than overwriting final audit state

## Testing

Minimum verification should extend the documented `siming-phase1` profile with:

1. Schema validation for all Siming canonical objects.
2. Deterministic replay with LLM disabled.
3. Fake LLM adapter returning a valid candidate.
4. Fake LLM adapter returning invalid schema.
5. Fake LLM adapter attempting forbidden bus event output.
6. Fake LLM adapter timeout.
7. Policy rejection when LLM suggests locked-truth rewrite.
8. Feasibility rejection when LLM suggests environment success without `ESM`.
9. Audit coverage for success, no action, timeout, downstream rejection, and late result.
10. Public envelope check that `world_ts` and `sim_tick_ts` do not appear in `AuthorityEvent`.

Runtime tests should prove that all LLM-assisted outputs still pass through `SimingEventProducer` before reaching `AuthorityEventBus`.

## Acceptance

Phase 1 Siming with LLM assistance is acceptable only when:

- every cross-system input and output uses `AuthorityEventBus`
- LLM calls occur only inside `SimingRuntime`
- LLM output cannot publish bus events directly
- all accepted LLM suggestions are normalized into canonical Siming domain objects
- policy and execution feasibility can reject unsafe suggestions
- `environment_request` success can only come from `ESM / L1` result events
- visual fact requests can only amplify established facts
- replay can follow `correlation_id -> causation_id -> event_id`
- audit records both action and no-action branches
- tests cover valid, invalid, timeout, and unsafe LLM outputs

## Open Implementation Notes

- The first implementation should use a fake LLM provider and fixture-driven golden traces before connecting a real provider.
- Real provider configuration should be injected through settings and kept outside domain models.
- Provider choice, API key storage, retry policy, and model selection should be implementation-plan topics, not part of the domain boundary. Model selection should be route-based so one Siming runtime can connect different provider/model routes without changing the authority-bus contract.
- The legacy `SimingService` should remain out of the mainline authority-bus path unless explicitly retired by a later cleanup plan.
## 2026-07-23 Closure Status

Siming live provider proof must use the loaded app settings and the existing `SimingRuntime.tick() -> SimingEventProducer -> AuthorityEventBus` chain. A verifier-created settings object, Character credential reuse, or readiness-only evidence is not completion evidence.
