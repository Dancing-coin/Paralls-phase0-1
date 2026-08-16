# INF-4P Durable Isolated Branch Evolution

Status: `implemented bounded and verified`

INF-4P extends the existing `BranchPreviewAuthority` snapshot stream with one
fixed, creator-debug branch evolution event for an already evaluated owner
consequence. It uses the existing `GameplayEventStore` and the existing
`gameplay:branch_preview:{branch_ref}` stream. It is branch evidence only:
the event cannot write Organization, Government, production, population or
social truth and cannot promote a branch.

The only admitted operation is `record_isolated_branch_evolution` for an
existing accepted branch buffer step. It emits
`gameplay.branch_preview.owner_consequence_applied` with redacted consequence
identity and digest, through `GameplayCommandEnvelope -> SettlementPlan ->
GameplayEventStore.append_batch() -> creator_debug outbox`. Durable projection
rebuilds the original snapshot records plus ordered evolution events and
supports checkpoint-tail replay. Missing snapshot, unsupported intent, privacy,
stale revision and changed idempotency are zero-write.

This is real isolated branch event evolution, not production-equivalent branch
promotion or a generic branch writer. Generic promotion and complete group
simulation remain separately blocked/deferred.
