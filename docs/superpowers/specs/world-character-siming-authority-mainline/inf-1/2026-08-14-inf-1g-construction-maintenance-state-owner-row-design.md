# INF-1G Construction Maintenance State Owner Row Design

Status: `implemented and verified as one closed Construction owner row; broader August INF-1 closure remains incomplete`

## Scope

INF-1G adds one explicit second-domain row to the closed semantic state/effect
matrix. It does not make `SemanticSettlementAuthority` a generic domain writer.

| Concern | Contract |
| --- | --- |
| Semantic proposer | existing `authority:semantic` only |
| Effect/state | `effect:maintenance_required` -> `state:maintenance_due@1` only |
| Target owner | existing `ConstructionProductionAuthority` / `actor_gameplay.construction_production_domain` |
| Target stream | existing `gameplay:construction_production:{facility_ref}` |
| Owner event | `gameplay.construction_production.maintenance_state_applied` |
| Command path | owner-built `GameplayCommandEnvelope` -> `SettlementPlan` -> the existing `GameplayEventStore.append_batch()` |
| Projection/outbox scope | `project` only |
| Semantic source pin | the closed registry revision vector is exactly `{"semantic": 1}` |
| Lifecycle | existing closed `StateDefinition` evaluation; no expiry obligation, retry, compensation, scheduler, or generic construction lifecycle is admitted |

The semantic authority may validate a proposal and invoke the single named
Construction owner method. The target owner alone evaluates the fixed
`StateDefinition` and creates its event. It must not accept caller-selected
owners, stream patterns, event types, state/effect pairs, visibility, or
definition variants. The Construction event is canonical production-domain
truth; semantic `effect` payloads remain proposals and audit evidence.

## Admission and Rejection

The sole admitted pair uses a fixed definition: `replace`, stack limit `1`,
no expiry, no dispel, and no transform. The owner rejects every effect/state
mismatch, foreign stream/owner, non-project scope, stale semantic snapshot,
revision conflict, altered idempotency payload, or definition change before
append. Exact duplicate submission replays the original owner append only.
The owner independently rechecks the fixed pair and exact semantic pin before
constructing its envelope, and rejects an unacquired facility stream. An
acquired facility does not need an already-started production run: maintenance
state is facility truth, not a run lifecycle event.

For this closed row, freshness is not advisory provenance: the source revision
vector must be exactly `{"semantic": 1}`. A missing, stale, advanced, or
otherwise different semantic vector is rejected before the owner builds its
envelope. This represents the current immutable closed semantic registry
revision; it does not create a semantic event store or a second clock.

The event payload contains the facility, fixed state/effect identities,
effective magnitude, next stack count, resistance revision, and semantic
snapshot digest. Its scoped projector rebuilds the maintenance state from
canonical Construction events; full replay and checkpoint-tail replay must
produce the same project-scoped digest.

## Non-goals

This does not register a generic cross-owner matrix, construction state expiry,
maintenance due policy, a second scheduler, generic selector execution,
arbitrary effect dispatch, or a cross-stream receipt. It does not change the
already admitted Survival rows or enable SOC-1, GAME-1, P6, or P7.

## Completion Evidence

Focused tests and one independent Harness profile must each prove: successful
owner append, exact duplicate replay, changed duplicate zero-write, revision
conflict zero-write, privacy zero-write, mismatched state/effect/owner/stream
and stale semantic-vector zero-write, scoped outbox/projection, and
full/checkpoint-tail replay parity. Every zero-write assertion snapshots event,
outbox, and idempotency surfaces, not event count alone.
The August guidance, root dependency records, INF-1 trees, and Harness guide
must be synchronized only after the evidence exists.

Current automated evidence is
`.harness/verification/infra-construction-maintenance-state-owner-report.json`.
It proves the stated exact row, direct-owner mapping and stale-vector rejection,
unacquired-facility zero-write, acquired-without-run settlement,
changed-duplicate and other rejection zero-write surfaces, project-scoped
outbox/projection, and full/checkpoint-tail replay. Independent review approved
the owner-boundary fixes. It does not by itself close the broader cross-owner
matrix.
