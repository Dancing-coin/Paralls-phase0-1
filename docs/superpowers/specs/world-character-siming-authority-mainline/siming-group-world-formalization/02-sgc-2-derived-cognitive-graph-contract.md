# SGC-2 Derived Cognitive Graph Contract

Status: `proposed; scoped source reader and correction policy required`

## Scope

This package defines the derived HeavenlyGraph bridge between committed
authority projections, Siming reasoning and character-readable summaries. It
does not own facts, replace five-pool character memory or write production
events.

## Contract

Graph writes are accepted only from a fixed authority-event projection. Each
node/relation contains `fact_ref`, `derivation_kind`, `source_event_vector`,
`policy_revision`, `graph_revision`, `visibility_scope`, `valid_from/to` and
redaction state. Each read supplies `(reader_principal, visibility_scope,
valid_at, recorded_at)`.

Correction is append-only at the derived layer: source compensation,
supersession, privacy reduction or policy changes create a new derivation and
invalidate dependent cache/checkpoint/summary references. Historical source
events remain replayable; they are not deleted.

`StorylineThread`, `NarrativeFollowUp`, `ActivationHint` and
`PropagationHypothesis` are derived records. They can influence retrieval or
activation priority but cannot assert a domain outcome or mutate character
beliefs already deposited in private memory.

## Evidence contract

Focused tests cover source allowlist, privacy redaction, dual-time query,
correction, cache invalidation, checkpoint rebuild, branch isolation and
character-summary non-mutation. The Harness selector proves graph full/tail
replay equivalence and no production append from graph-only input.

## Dependencies and non-goals

Depends on an approved scoped authority projection and existing graph port.
No graph database, generic graph writer, global memory store or production
fact promotion is admitted by this contract.
