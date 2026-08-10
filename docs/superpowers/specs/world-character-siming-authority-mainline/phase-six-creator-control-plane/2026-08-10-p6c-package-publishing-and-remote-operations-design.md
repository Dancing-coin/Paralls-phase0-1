# P6C Package Publishing And Remote Operations

Status: `design-only; implementation not authorized`

## Lifecycle

A package revision moves through draft, validation, review, signed staging,
canary, active, rollback or retired states. It pins dependency versions, schema,
migration, compatibility range, capability manifest, content digest and rollback
class. Preview uses a bounded local authority and isolated draft data; remote
formal run accepts only validated signed revisions through the closed authority.

Activation is a governed proposal. It verifies permissions, compatibility,
migration/replay plan, active-set conflict, canary health and audit requirement
before the existing patch/package lifecycle and authority settlement paths act.
It never permits remote database edits or player-state overwrite.

## Gate

Test signature denial, dependency/schema conflict, migration failure, canary
failure, reversible rollback and rejected lossy rollback. Preserve active
revision replay and auditability.
