# siming-godot-event-bus-loop Specification

## Purpose
Define the first frontend-safe Siming authority event return path from backend event bus publication through WebSocket delivery into Godot local presentation.

## Requirements

### Requirement: Backend projects frontend-safe Siming authority events
The backend SHALL project whitelisted Siming `AuthorityEvent` families into WebSocket messages that use the public frontend envelope and exclude Siming private reasoning state.

#### Scenario: Visual observability request is projected
- **WHEN** a `visual_fact_event` causes Siming to publish `siming.visual_observability_request`
- **THEN** the backend sends a WebSocket message containing the event type, event ID, causation ID, correlation ID, routing metadata, durability, and frontend-safe payload

#### Scenario: Non-frontend audit event is not projected
- **WHEN** Siming publishes an audit-only event such as `siming.audit_recorded`
- **THEN** the backend stores or audits the event without sending it to the Godot frontend

### Requirement: Godot bridge routes Siming event-bus projections
The Godot `BackendBridge` SHALL parse projected Siming event-bus messages and route them through `LocalPresentationBus` without requiring Godot scripts to understand backend Python classes.

#### Scenario: Projected event reaches local presentation bus
- **WHEN** `BackendBridge` receives a projected `siming.visual_observability_request` message
- **THEN** it emits a local presentation bus signal or generic authority-event signal that includes the frontend-safe payload

#### Scenario: Unknown projected family remains observable
- **WHEN** `BackendBridge` receives a projected event family that has no dedicated Godot consumer
- **THEN** it logs the event type through the local debug bus instead of dropping it silently

### Requirement: Godot applies visual observability as local presentation only
Godot SHALL handle `siming.visual_observability_request` as a local observability or debug presentation request and MUST NOT treat it as new world truth or direct Siming control of character/physics state.

#### Scenario: Established visual fact is highlighted
- **WHEN** Godot receives a visual observability request with an established fact ID and presentation hint
- **THEN** it applies an observable local highlight, debug trace, or presentation marker linked to that established fact

#### Scenario: Missing established fact ID is rejected
- **WHEN** Godot receives a visual observability request without an established fact ID
- **THEN** it logs a rejection and does not apply a presentation marker

### Requirement: Harness proves the full Godot event-bus loop
Verification SHALL prove the complete path from Godot structured input through backend authority bus and back to Godot local presentation.

#### Scenario: Phase runtime evidence includes event-bus return path
- **WHEN** the phase runtime harness runs the visual fact scenario
- **THEN** the report includes evidence for backend authority bus publication, Siming projected event emission, WebSocket receipt, Godot local bus dispatch, and observable presentation trace

#### Scenario: Legacy path remains available during migration
- **WHEN** the new event-bus projection is enabled
- **THEN** existing `siming_output` and `world_result` Phase 0 harness checks continue to pass until a later change explicitly removes them
