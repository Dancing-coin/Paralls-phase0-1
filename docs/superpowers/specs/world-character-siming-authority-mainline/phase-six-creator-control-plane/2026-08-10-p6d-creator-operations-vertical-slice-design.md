# P6D Creator Operations Vertical Slice

Status: `design-only; implementation not authorized`

## Acceptance

A reader inspects an authorized public package report; an editor changes an
allowed ruleset parameter in a local preview, validates and submits it; an admin
reviews, stages, activates and rolls back a compatible package revision. UI,
CLI and MCP produce equivalent decision ids and audit results. A remote
production request changes only the approved active revision, never a player's
raw truth.

The slice must demonstrate classification/redaction, denied editor activation,
migration/rollback reporting, committed revision replay and closed-core
non-disclosure. It is not a marketplace or untrusted creator-code platform.
