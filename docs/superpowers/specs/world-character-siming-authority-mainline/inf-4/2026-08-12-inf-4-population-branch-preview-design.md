# INF-4 Population And Branch Preview Design

Status: `implemented-and-verified for the documented population branch-preview vertical; broader simulation remains planned`

## Purpose And Truth Boundaries

INF-4 extends existing `CharacterProfile` identity and `population_continuity`
with deterministic batch planning, projection-derived family/organization
inputs, calibration inputs, and isolated branch previews. It does not invent a
population owner, NPC truth store, family truth store, social truth store, or
second production event store.

Character identity remains registry-owned. The verified family/organization
input is a caller-provided digest-bearing preview input; the current preview
authority validates profile identity but does not verify source revision, scope,
or digest against a source authority. The planner is pure and proposes
`GameplayCommandEnvelope`s; existing owners validate and settle them through
the canonical append/outbox/replay path.

## Branch And Calibration Contracts

`ReferenceDataset` has provenance, declared license metadata, schema revision,
digest, classification, and approved usage scope. Its `license_ref` is not an
authority-verified license read: no existing license owner, stream or scoped
projection is mapped for that claim. `CalibrationInput` pins a dataset,
mapping revision, world snapshot/ruleset revisions, seed, and preview scope.
Neither can directly overwrite a profile, asset, relationship, or production
event.

`PopulationBatchPlan` carries deterministic ordering and candidate expected
revisions. The verified `BranchPreviewRequest` pins a digest of current event
history, seed, calibration ref, and branch ID; it does not yet identify a fixed
checkpoint boundary or verify active revisions. A branch has an ephemeral
`BranchEventBuffer` and projections only; its events are never passed to
production `GameplayEventStore.append_batch()`.

Production event types include `population.batch_planned`, `intent_deferred`,
`pending_change_recorded`, and owner settlement events. Preview report records
are non-production artifacts with base digest, branch digest, assumptions,
redactions, and replay hash; no branch outcome is a world truth event.

## Consistency, Privacy, And Recovery

Plans sort by stable priority/profile/intent keys; deterministic seed and all
input digests are fixed. Duplicate production commands return original
receipts. Invalid identity, unauthorized family/org input, lock conflict,
stale projection revision, calibration scope mismatch, branch/base mismatch,
or privacy denial produces zero production writes.

The verified preview returns a redacted public report and checks dataset allowed
scope. It does not yet provide organization/creator/authority filtering,
source-projection enforcement, a fixed checkpoint base, or migration readers.
Production full/checkpoint-tail replay is separately proven for the store;
branch replay is repeatable from its isolated buffer and current-event digest.
A branch is deleted by discarding its buffer; no production rollback is
required. Production compensation remains owner-specific future work.

## Harness And Completion

`infra-population-branch-preview` must separately prove profile identity reuse,
deterministic shuffled batch ordering, family/org projection scope enforcement,
activation pending merge, duplicate idempotency, revision conflict zero-write,
dataset scope/privacy denial, branch/production isolation, branch replay,
production full/checkpoint-tail replay, and redacted preview report.

Supersession: authoritative reference-data license admission is now supplied by
the separately verified INF-4Z-A `ReferenceDataAuthority` contract. This base
document's caller-supplied `license_ref` path remains non-authoritative and is
retained only for compatibility. The later frozen source revision/digest and
calibration-admission constraints in INF-4Z/INF-4Z-A supersede this document's
earlier missing-license and incomplete-fixed-base statements.

This base vertical is superseded for source/revision/digest/calibration admission
by INF-4Z and INF-4Z-A. It remains incomplete for replayable branch event/
projection evolution, real branch scenario progression, promotion (which must
remain zero-write), and full group simulation. Civilization authority, generated
population truth, full social graph, external dataset ingestion, and P6/P7 are
explicit non-goals.
