## 1. Backend Projection

- [x] 1.1 Add a frontend projection port/service for whitelisted Siming authority event families.
- [x] 1.2 Project `siming.visual_observability_request` into a public WebSocket envelope with event identity, causation, correlation, routing, durability, and safe payload fields.
- [x] 1.3 Ensure audit-only or private Siming events are not sent to Godot.
- [x] 1.4 Document which Siming output event families still lack downstream consumers and keep them out of "mainline complete" claims.
- [x] 1.5 Add backend tests for projected and non-projected Siming event families.

## 2. Godot Bridge And Local Bus

- [x] 2.1 Extend `BackendBridge.gd` to dispatch projected Siming event-bus messages.
- [x] 2.2 Add `LocalPresentationBus` signals for generic authority events and the visual observability request path.
- [x] 2.3 Add debug logging for unknown projected event families so they remain observable.
- [x] 2.4 Add or update Godot-facing static checks for the new bridge and bus signals.

## 3. Presentation Consumer

- [x] 3.1 Add a minimal Godot consumer for `siming.visual_observability_request`.
- [x] 3.2 Require an established fact ID before applying any local presentation marker.
- [x] 3.3 Emit a runtime trace line when the visual observability marker is applied or rejected.
- [x] 3.4 Keep the existing `siming_output` consumer active during this migration.

## 4. Verification

- [x] 4.1 Add backend regression coverage for the complete projected-message path.
- [x] 4.2 Extend runtime trace extraction to recognize the event-bus return path.
- [x] 4.3 Extend `phase0` or `phase1-slice` harness checks to prove backend bus publication, WebSocket receipt, Godot local dispatch, and presentation trace.
- [x] 4.4 Add a verification note that the event bus is still not the full-system mainline until all selected Siming output families have downstream consumers.
- [x] 4.5 Run `python -m pytest -q`.
- [x] 4.6 Run `python scripts/verification/harness.py --profile phase0`.
- [x] 4.7 Run `python scripts/verification/harness.py --profile phase1-slice`.

## Verification Note

This change proves only the first frontend-safe return path: `siming.visual_observability_request` is projected through the existing WebSocket envelope and consumed by Godot local presentation. Other Siming output families, including `siming.environment_request`, `siming.impulse`, `siming.opportunity`, and `siming.fact_reveal`, remain out of the frontend projection whitelist until each has an explicit downstream consumer and harness proof. The event bus should not be described as the full-system mainline yet.
