# P6A Creator Capability And Closed-Core Boundary

Status: `design-only; implementation not authorized`

## Boundary

Expose a signed capability manifest, not Python modules or raw YAML loaders.
The manifest classifies schema/projection/report content and maps reader,
editor, admin plus project/package scope to actions: read, draft-write,
validate, preview, submit, approve, activate, rollback and audit-read. Every
request is evaluated server-side with actor, project, environment, object,
revision, intent and expiry.

Closed core includes canonical writers, settlement logic, private character
memory, secrets, signing material, raw event-store ingress and implementation
policy. Read access to authorized public schema or projection is legitimate but
does not imply source, mutation or administration access.

## Audit And Gate

Decisions record principal, capability, target revision, result and reason in an
append-only audit projection. Test confused deputy, scope escalation, expired
grant, editor activation, admin raw-write request, redaction and replay. No
`replace_dossier_layer()`-style importable mutation entry point is authorized.
