# Facility/Lifecycle/Maintenance Implementation Plan

Add policy-validated facility content and projection branches for maintenance
and lifecycle while preserving `active/decommissioned` compatibility. RED tests
cover policy omission, active-run conflict, revision/privacy mismatch,
terminal transitions and full/tail replay. Gate: Construction owner evidence
and legacy replay green; rollback by withholding the new binding.

Maintenance-obligation provenance is now implemented as an additive owner
branch: facility/project/revision/policy pins are emitted when the facility is
known and replay rejects tampering. Legacy no-pin events remain compatible.

The maintenance obligation adapter now returns `duplicate_replayed` only for
an exact request and rejects changed reuse of the idempotency key.

Replay also converts missing or empty obligation references into the stable
domain rejection instead of exposing an internal key lookup error.

Its event schema is now source-controlled and explicitly registered through
the existing event-schema registry; no second registry is introduced.

Maintenance-state replay now maps malformed numeric/ref payloads to a stable
domain error instead of leaking model-construction exceptions.
