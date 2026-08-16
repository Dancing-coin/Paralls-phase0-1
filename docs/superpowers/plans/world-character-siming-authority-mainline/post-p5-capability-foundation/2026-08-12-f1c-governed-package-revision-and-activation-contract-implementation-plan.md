# F1C Governed Package Revision And Activation Contract Plan

Status: `completed; complete profile fresh-green`

## Work packages

1. Define immutable package manifest, digest, schema, dependency, capability,
   migration and rollback fields.
2. Define reader/editor/admin decisions once and expose the same result to UI,
   CLI and MCP; include denial and redaction responses.
3. Define draft/preview/staging/active/rejected/withdrawn/rolled-back lifecycle
   and approval/audit transitions.
4. Bind activation proposals to existing Gameplay authority and event-store
   settlement; explicitly forbid direct database/event writes.
5. Define stale activation, signature failure, digest mismatch, migration
   failure, atomic rollback, replay and zero-write tests.

## Verification plan

P6C/P6D cannot start until the focused governance profile is green, rollback
target is named, audit evidence is complete, and all three surfaces show equal
authorization results. F1A revision rules and F1B visibility scopes are hard
inputs.

## Done/blocked

Done means package lifecycle and evidence manifest are reviewed. Missing closed-
core owner, rollback semantics, or denial parity keeps F1C blocked and P6C/P6D
planned.
