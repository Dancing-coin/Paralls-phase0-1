# SGC Siming Group World Formalization Program Design

Status: `proposed; contract drafting only; no capability or owner row admitted`

## Decision

The future Siming/group-world program is split into five independently
admitted packages: SGC-1 governed Siming capability, SGC-2 derived cognitive
graph, SGC-3 population fidelity continuity, SGC-4 presentation projection,
and SGC-5 performance/replay evidence. A package may proceed only when its
own contract and evidence gates are satisfied. Approval of this program does
not approve any package or any production write.

## Existing Anchors

| Concern | Existing anchor | Required use |
| --- | --- | --- |
| capability admission | `backend/app/gameplay/governed_contract_catalog.py:GovernedAuthorityContractCatalog` | immutable, source-controlled entry only |
| production commit | `backend/app/gameplay/settlement_plan.py`, `backend/app/gameplay/event_store.py` | `GameplayCommandEnvelope -> SettlementPlan -> append_batch()` only |
| Siming read/audit | `backend/app/services/siming_read_model.py`, `siming_audit_writer.py`, `siming_intervention_guardrails.py` | scoped read, candidate and audit only until a row is admitted |
| derived graph | `backend/app/models/siming_heavenly_graph.py`, `services/in_memory_heavenly_graph.py` | provenance-aware derived state only |
| continuity | `backend/app/population_continuity/activation.py`, `batch.py`, `world.py` | same CharacterRecord and existing activation lock |
| presentation | `backend/app/world_runtime/projection.py`, `backend/app/gameplay/godot_mirror_projection.py` | scoped projection consumed by local presentation |

## Global Invariants

1. Domain owners alone settle production business facts.
2. No caller, agent, graph, branch, client or projection selects an owner,
   stream, event family, privacy scope or compensation rule.
3. `GovernedAuthorityContractCatalog` remains the only catalog; there is no
   `GovernedSimingCapability` registry or runtime registration API.
4. All admitted writes use the one existing append spine and append-derived
   receipt. Unknown, stale, private or catalog-mismatched input is zero-write.
5. The graph, continuity planner, presentation view and renderer are derived
   consumers. Their checkpoints/caches never replace production replay.
6. No new runtime, store, bus, clock, scheduler, generic writer, generic
   router, generic coordinator, or generic settlement authority is permitted.

## SGC-1: Governed Siming Capability

An admitted capability is one immutable catalog entry with `capability_ref`,
version, typed intent schema, caller eligibility, reader scope, fixed source
evidence, fixed owner fragment/event family, expected revision rule, privacy
scope, idempotency shape, receipt reader, and retry/compensation disposition.

The guarded path is `scoped read-set -> candidate -> fixed capability check ->
owner-local validation -> SettlementPlan -> append_batch -> receipt/audit`.
The catalog rejects before plan construction if the ref, version, schema,
source, target fragment, event family, scope, revision or idempotency domain
does not match. No-action, privacy denial, stale read-set and owner rejection
are durable audit outcomes, not implicit fallback to a different owner.

**Admission gate:** choose one existing owner operation with a complete
contract. If no such row exists, only document `owner-contract blocked`; do
not create an execute path.

## SGC-2: Derived Cognitive Graph

Every graph relation carries `fact_ref`, derivation kind, source event vector,
policy revision, visibility scope, validity interval and redaction state. A
reader supplies `(principal, scope, valid_at, recorded_at)`; it receives only
relations derivable from its scoped projections. Graph content is never a
replacement for a character's five-pool memory or a domain fact.

Source compensation, correction, policy change or scope restriction appends a
superseding/retracted/redacted derivation. Caches and checkpoints are keyed by
source vector, scope digest and policy revision. They invalidate on any source
change; an already consumed character summary remains subjective memory and is
not silently rewritten.

`StorylineThread`, `NarrativeFollowUp`, `ActivationHint` and
`PropagationHypothesis` are derived records only. They may request a scoped
read or propose an admitted capability; none is a domain obligation or an
executed business outcome.

## SGC-3: Population Fidelity Continuity

One `CharacterRecord` transitions among `dormant`, `batch_planned`, `prewarm`,
`active` and `pending_merge`. Far batch planning and mid prewarm never load
private memory or create a second identity. Near activation obtains the
existing activation lock before it loads permitted private memory; stale or
conflicting candidate output is discarded/requeued.

Each batch pins world-mode ref/revision, cadence source ref/revision, scoped
source vector, policy/ruleset revision, deterministic seed, selector revision,
budget and report scope. The cadence source is an existing committed
world-mode/activation/schedule projection, never wall-clock time or a new
scheduler. Missing or stale cadence produces no-op/requeue.

Outputs are limited to a discardable `presentation_seed`, an activation
candidate, or an owner-bound intent. A presentation seed is a scoped,
rebuildable PresentationView input and not an event stream. Only the third
output can reach an already admitted owner capability.

## SGC-4: Presentation Projection

`PresentationView` is a scoped projection with `basis_event_vector`,
`scope_digest`, `asset_manifest_revision`, `mapping_revision`, semantic layers
and fallbacks. Every semantic layer carries source reference, layer visibility,
redaction disposition and identity policy. Crowd bands must obey the approved
aggregation threshold. Behavior seeds can reference only an already visible
CharacterRecord and must not encode private relations, hidden locations or
unsettled outcomes.

The same basis vector, scope, manifest and mapping revision reconstruct the
same semantic digest in full and checkpoint-tail replay. Renderer-local device
budget, frame rate, missing resources and LOD may only choose documented
fallbacks; they do not change the view digest, reveal more information, or
write world truth. Godot observations remain evidence candidates.

## SGC-5: Performance and Replay Evidence

The program claims neither global real-time nor scale until measured. Each
Harness profile fixes hardware/runtime label, synthetic-data version and size,
world-mode/cadence/source vectors, policy/mapping revision, seed, budget,
warm-up/repeat counts and statistical outputs (median/high percentile).

The minimum measurements are plan size, owner append count, projection
latency, agent activation count and full/tail replay time. Each profile names
its selector, regression threshold and failure disposition. Over-budget work
may enter a documented lower-fidelity/no-op/requeue path, but cannot omit
auditing, weaken privacy, drop receipts or fabricate a business result.

## Required Evidence Per Admitted Vertical

Focused RED-to-green tests and an independent Harness selector must prove:
authorized success; unknown/catalog mismatch zero-write; stale source/target
revision zero-write; privacy/redaction; exact and changed duplicate behavior;
append-derived receipt; full replay; checkpoint-tail replay; and the declared
no-action/compensation path. SGC-5 additionally proves its fixed benchmark
inputs and load-shedding audit.

## Explicit Non-Goals

This program does not authorize generic simulation settlement, social or
population truth, arbitrary LLM action, branch promotion, a general graph
writer, a simulation database, cross-device world state, or a universal Game
Master. It preserves all completed INF evidence and replaces only unexecuted
broad design claims after the corresponding package is admitted and verified.
