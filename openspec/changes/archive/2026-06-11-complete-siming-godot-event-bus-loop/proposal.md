## Why

The current code proves the legacy Phase 0 Godot observable path (`siming_output` and `world_result`) and a backend-only Siming authority event pipeline, but the authority event bus is not yet the full-system mainline and Siming output event families do not yet have complete downstream consumers. Phase 1 requires Godot to subscribe only to high-level results/read models while Siming remains backend-owned and auditable.

## What Changes

- Add a frontend-safe WebSocket projection for selected Siming authority events, without exposing private Siming reasoning state.
- Extend the Godot `BackendBridge` and `LocalPresentationBus` to route high-level Siming event-bus messages separately from legacy `siming_output`.
- Add Godot-side presentation consumers for at least one Siming event family that is currently backend-only, starting with `siming.visual_observability_request`.
- Make the current limitation explicit in verification: event bus mainline adoption is partial until selected Siming output families have real downstream consumers.
- Preserve existing `siming_output` behavior until the new event-bus path has equivalent runtime evidence.
- Add backend and harness checks that prove the full loop: Godot structured input -> backend authority event bus -> Siming event family -> WebSocket public envelope -> Godot local presentation bus -> observable presentation/audit trace.

## Capabilities

### New Capabilities

- `siming-godot-event-bus-loop`: Defines the public event-bus projection and Godot consumption contract for Siming high-level results.

### Modified Capabilities

- None.

## Impact

- Backend WebSocket message projection in `backend/app/main.py` and related Siming event bus services.
- Godot frontend bridge and local bus under `scripts/autoload/`.
- Godot presentation consumers under `scripts/` and `scenes/phase0/`.
- Verification harness and tests under `backend/tests/` and `scripts/verification/`.
- No new runtime dependency is expected.
