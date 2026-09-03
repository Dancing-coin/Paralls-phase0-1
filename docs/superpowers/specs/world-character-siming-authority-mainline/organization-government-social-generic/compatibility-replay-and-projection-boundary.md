# Compatibility, Replay And Projection Boundary

Status: `implementation-authorized`

Date: `2026-09-03`

This family preserves compatibility for existing narrow Organization,
Government and Social rows while the generic platform rolls out. The state
machine is `baseline -> compatible -> verified -> retired`.

Read-only baselines remain read-only. Full replay and checkpoint-tail replay
must match, projection redaction must remain stable, and no narrowed row may
be silently widened or rewritten.

