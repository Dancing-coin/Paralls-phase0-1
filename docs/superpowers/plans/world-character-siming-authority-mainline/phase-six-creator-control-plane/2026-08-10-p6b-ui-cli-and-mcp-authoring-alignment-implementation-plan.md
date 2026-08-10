# P6B UI, CLI And MCP Authoring Alignment Implementation Plan

Status: `design-only; implementation not authorized`

1. Lock P6A evidence and create contract fixtures shared by UI, CLI and MCP.
2. Implement adapters only against the server decision/validation contract;
   preserve schema version and decision ids end-to-end.
3. Test equivalent success, denial, redaction, malformed input and stale-draft
   results across all three interfaces.
4. Add audit correlation and preview-only write tests.

Do not fork policy into front-end state, CLI flags or MCP prompt instructions.
