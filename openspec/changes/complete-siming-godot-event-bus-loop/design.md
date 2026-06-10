## Context

Current code has two separate truths:

- The legacy Phase 0 frontend path is runtime-proved. Godot sends structured input through `BackendBridge`, receives `world_result` and `siming_output`, and applies visible presentation through `LocalPresentationBus` consumers.
- The new Siming authority event pipeline exists in backend memory. `visual_fact_event`, selected `raw_fact_event` visual facts, and ESM `world_result` objects are adapted into `AuthorityEvent`, consumed by `SimingEventPipeline`, and republished as event families such as `siming.visual_observability_request`.
- The authority event bus is not yet the full-system mainline. Siming output events are published back into the backend bus, but most target systems (`visual_fact`, `esm`, `character_runtime`, `presentation`, and Godot) do not yet subscribe to and act on those event families.

The missing part is the Phase 1 boundary described by the Siming and event bus docs: Godot should subscribe to public high-level Siming results/read models over the WebSocket public envelope. Today those new `siming.*` authority events remain backend-only; Godot does not have local bus signals or presentation consumers for them.

## Goals / Non-Goals

**Goals:**

- Deliver selected Siming authority event families to Godot through a frontend-safe WebSocket envelope.
- Keep Godot as a high-frequency local presentation executor, not a Siming truth host.
- Prove at least one full event-bus loop with runtime evidence: visual fact -> authority bus -> Siming event family -> WebSocket -> Godot local bus -> observable local presentation.
- Establish the first downstream consumer path for a Siming output event family, while keeping remaining unconsumed families explicitly marked as not yet mainline-complete.
- Preserve the existing `siming_output` path until the new event-bus projection has equivalent test and harness coverage.

**Non-Goals:**

- Implement the full Phase 1 Siming brain, fairness model, or long-lived read model store.
- Replace all legacy Phase 0 websocket messages in this change.
- Let Siming directly control Godot bones, physics, character decisions, or ESM settlement truth.
- Expose Siming private reasoning, internal cache keys, or non-public audit state to Godot.

## Decisions

1. Project only selected high-level authority events to WebSocket.

   The backend bus may contain audit, fairness, and orchestration events that are useful internally but not appropriate for the frontend. A projection layer should whitelist event families such as `siming.visual_observability_request`, `siming.presentation_highlight_request`, `siming.impulse`, `siming.opportunity`, `siming.fact_reveal`, and frontend-safe read model updates. This avoids turning the in-memory bus into a raw frontend feed.

   Rejected alternative: expose every `AuthorityEvent` to Godot. That leaks internal audit/orchestration details and conflicts with the Phase 1 rule that Godot consumes high-level results only.

2. Use a public websocket envelope, not a private Siming frontend protocol.

   The projected message should keep the existing `message_type`/`payload` outer shape used by `BackendBridge`, with `message_type` set to a stable public value such as `authority_event` or a specific projected family. The payload should preserve public event identity, event type, causation/correlation IDs, routing hints, durability, and frontend-safe payload data.

   Rejected alternative: add a second websocket channel just for Siming. That would hide the path from existing runtime trace and harness checks.

3. Add Godot local bus signals by capability, not by backend implementation class.

   `BackendBridge` should parse the public envelope and emit typed local signals such as `siming_visual_observability_requested(payload)` or a generic `authority_event_received(payload)` plus family-specific convenience signals. Godot scenes should not know about Python `AuthorityEvent` classes.

   Rejected alternative: make Godot understand the full backend event bus object model. That couples frontend presentation to backend internals.

4. Treat `siming.visual_observability_request` as the first runtime proof.

   This is the smallest current backend event family with clear Phase 1 semantics: Siming asks to increase observability for an already established visual fact. Godot can prove the loop by applying a local highlight/debug presentation and emitting a trace line without inventing new world truth.

   Rejected alternative: start with `environment_request`. That requires ESM settlement and has a larger authority boundary.

## Risks / Trade-offs

- Projected event shape drifts from `AuthorityEvent` -> Keep backend tests that compare required public fields and reject private fields.
- Godot presentation implies new truth -> Limit first consumer to local observability/debug presentation and require source established fact IDs.
- Dual-write lasts too long -> Add explicit tasks to keep old `siming_output` until equivalent harness evidence exists, then plan a later removal.
- Runtime trace passes but no visible effect occurs -> Harness must assert both WebSocket receipt and a Godot local bus/presentation trace.

## Migration Plan

1. Add backend projection and tests without changing existing outbound message order for legacy paths.
2. Add Godot local bus signals and a minimal presentation consumer.
3. Extend runtime trace/harness to prove the new event-bus loop.
4. Keep `siming_output` until the new path proves equivalent demo behavior.
5. In a later change, remove or narrow legacy `siming_output` only after downstream coverage is explicit.

## Open Questions

- Should the public websocket `message_type` be a generic `authority_event` or family-specific values such as `siming_visual_observability_request`?
- Which Siming event families beyond visual observability should be included in the first frontend whitelist?
- Should projected events be persisted in a small read model before being emitted, or is in-memory projection sufficient for Phase 0/Phase 1 slice validation?
