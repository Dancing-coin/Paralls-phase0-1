## 1. Backend Projection

- [ ] 1.1 Add a frontend projection port/service for whitelisted Siming authority event families.
- [ ] 1.2 Project `siming.visual_observability_request` into a public WebSocket envelope with event identity, causation, correlation, routing, durability, and safe payload fields.
- [ ] 1.3 Ensure audit-only or private Siming events are not sent to Godot.
- [ ] 1.4 Document which Siming output event families still lack downstream consumers and keep them out of "mainline complete" claims.
- [ ] 1.5 Add backend tests for projected and non-projected Siming event families.

## 2. Godot Bridge And Local Bus

- [ ] 2.1 Extend `BackendBridge.gd` to dispatch projected Siming event-bus messages.
- [ ] 2.2 Add `LocalPresentationBus` signals for generic authority events and the visual observability request path.
- [ ] 2.3 Add debug logging for unknown projected event families so they remain observable.
- [ ] 2.4 Add or update Godot-facing static checks for the new bridge and bus signals.

## 3. Presentation Consumer

- [ ] 3.1 Add a minimal Godot consumer for `siming.visual_observability_request`.
- [ ] 3.2 Require an established fact ID before applying any local presentation marker.
- [ ] 3.3 Emit a runtime trace line when the visual observability marker is applied or rejected.
- [ ] 3.4 Keep the existing `siming_output` consumer active during this migration.

## 4. Verification

- [ ] 4.1 Add backend regression coverage for the complete projected-message path.
- [ ] 4.2 Extend runtime trace extraction to recognize the event-bus return path.
- [ ] 4.3 Extend `phase0` or `phase1-slice` harness checks to prove backend bus publication, WebSocket receipt, Godot local dispatch, and presentation trace.
- [ ] 4.4 Add a verification note that the event bus is still not the full-system mainline until all selected Siming output families have downstream consumers.
- [ ] 4.5 Run `python -m pytest -q`.
- [ ] 4.6 Run `python scripts/verification/harness.py --profile phase0`.
- [ ] 4.7 Run `python scripts/verification/harness.py --profile phase1-slice`.
