# P6B UI, CLI And MCP Authoring Alignment

Status: `design-only; implementation not authorized`

## Contract

UI forms, creator CLI and MCP tools consume the same versioned schema,
capability decision, validation result, draft revision and audit record. They
may differ in ergonomics but not in authorizable operations or authorization
semantics. UI list/select controls serialize the same declared options that a
CLI/MCP agent submits; neither path sends executable source to production.

A response includes decision id, visible field classification, schema/package
revision, validation diagnostics, compatible migration choices and next allowed
actions. The server is the reference behavior; generated clients are adapters.

## Gate

For every reader/editor/admin scenario prove semantic parity, denied-operation
parity, redaction parity, idempotent draft submission and audit parity. No MCP
tool maps directly to internal Python mutation functions.
