# Character Simulation Memory Seed And Continuity Design

Status: `proposed; design artifact only; no runtime authorization`

Date: `2026-08-22`

## 1. Intent

Define a governed continuity layer that lets population simulation advance a
character's current state and record meaningful simulated experience without
giving Siming or the population planner direct read/write access to the
character's five-pool private memory.

The design must preserve three goals at the same time:

1. behavior continuity: an activated character reflects the latest settled
   state of its offline life;
2. memory continuity: meaningful offline experiences can become subjective
   memory after Character Core validation and materialization;
3. auditability: every accepted change is attributable, replayable, versioned,
   privacy-scoped and correctable.

This document is a contract proposal. It does not authorize a new store, bus,
clock, scheduler, generic writer or generic settlement authority.

## 2. Decision Summary

The "personal seed" is formalized as a **Character Simulation Seed** composed
of an append-only delta ledger and a materialized continuity checkpoint. It is
not a second character, a second truth source, a copy of five-pool memory, or a
free-form JSON mutation surface.

```text
simulation input
  -> SeedDelta
  -> owner-bound world settlement (when applicable)
  -> runtime-state materialization
  -> experience ledger
  -> continuity checkpoint
  -> activation-time five-pool materialization
```

The canonical owners remain split:

| Data | Owner |
| --- | --- |
| objective world/gameplay facts | existing world or domain authority |
| actor-private five-pool memory | Character Core / Character Agent runtime |
| simulation candidate, policy, audit and activation priority | Siming / Population derived layer |
| natural-language interpretation | optional LLM proposal, never the owner |

## 3. Non-Negotiable Invariants

1. Authored dossier truth is never directly overwritten by simulation.
2. Long-term personality change accumulates as a drift candidate and requires
   the existing promotion gate before entering the effective-profile overlay.
3. Siming cannot read raw actor-private memory, private relationship evidence,
   or hidden knowledge state.
4. Siming and population simulation cannot directly append to any five-pool
   store.
5. A world fact does not imply that a character knows, observed or remembers
   that fact.
6. A prediction, branch result or Siming-internal signal cannot become a
   production character memory.
7. State freshness and memory freshness are tracked by separate cursors.
8. Historical records are append-only; correction uses superseding or
   retraction records.
9. Unknown, stale, private, branch-only, duplicate or catalog-mismatched
   inputs produce zero production write and an auditable result.
10. LLM output is an untrusted proposal. Character Core owns validation,
    materialization, persistence and replay semantics.

## 4. Data Model

### 4.1 CharacterSimulationSeed

`CharacterSimulationSeed` is a logical contract. Its implementation must reuse
existing Character Core, population continuity, event-store and replay owners;
it must not introduce a generic seed database.

```text
CharacterSimulationSeed
├── seed_id
├── schema_revision
├── actor_ref
├── world_ref
├── from_tick / to_tick
├── base_checkpoint_ref
├── base_revision_vector
├── source_event_refs
├── source_scope
├── ruleset_revision
├── selector_revision
├── model_revision (optional)
├── deterministic_seed
├── state_deltas
├── memory_candidates
├── drift_candidates
├── activation_hints
├── presentation_seed (optional, discardable)
├── owner_receipt_refs
├── visibility_scope
├── privacy_disposition
├── apply_status
├── cursor_vector
├── result_digest
├── idempotency_key
├── supersedes / superseded_by
└── recorded_at
```

All fields are closed-schema and revisioned. A seed delta is immutable after
recording.

### 4.2 MemoryCandidate

`MemoryCandidate` is a proposed subjective experience, not a five-pool record.

```text
MemoryCandidate
├── candidate_id
├── actor_ref
├── candidate_kind
├── source_event_refs
├── event_valid_at
├── event_recorded_at
├── knowledge_available_at
├── exposure_basis
├── summary
├── subject_ref / target_ref (optional)
├── confidence
├── salience
├── visibility_scope
├── privacy_disposition
├── materialization_policy
├── dedup_key
├── source_revision_vector
├── branch_ref (optional)
├── status
└── provenance_digest
```

`candidate_kind` is closed:

```text
event_experience
perceptual_observation
factual_knowledge
social_impression
higher_order_belief
```

### 4.3 ContinuityCursor

One `last_simulation_tick` is insufficient. The logical cursor is:

```text
ContinuityCursor
├── owner_cursor
├── state_cursor
├── experience_cursor
└── memory_cursor
```

The character can have current state at tick 120 while memory materialization
is complete only through tick 97. This is a valid, observable state and must
not be represented as globally "fully current".

### 4.4 ContinuityCheckpoint

```text
ContinuityCheckpoint
├── actor_ref
├── checkpoint_sequence
├── as_of_tick
├── cursor_vector
├── authored_dossier_ref / revision
├── effective_profile_revision
├── runtime_state_snapshot
├── pending_memory_count
├── open_conflict_refs
├── source_revision_vector
├── ledger_digest
└── recorded_at
```

The checkpoint is a rebuildable acceleration view, not a replacement for the
append-only ledger or production replay.

## 5. Memory Materialization Rules

Character Core performs the final visibility, exposure, temporal and revision
checks before materialization.

| Candidate | May materialize to | Required evidence |
| --- | --- | --- |
| `event_experience` | Event Memory | actor participated, was affected, or received an owner-confirmed consequence |
| `perceptual_observation` | Observation Memory | actor-observable place, time and channel evidence |
| `factual_knowledge` | Knowledge Memory | observed, disclosed or scoped propagation evidence |
| `social_impression` | Social Memory | actor-specific interaction or valid received information |
| `higher_order_belief` | Higher-Order Memory | explicit evidence about another actor's knowledge or belief |

The same world event may produce different candidates for different actors,
or no candidate at all. Objective truth never bypasses actor exposure.

Materialization flow:

```text
SeedDelta
  -> candidate visibility/exposure check
  -> event settlement and time check
  -> dedup/conflict check
  -> typed Character Core writeback candidate
  -> one selected five-pool store
  -> materialization receipt
```

Corrections append a superseding or retraction record. A character's already
formed subjective memory is not silently deleted when world truth is corrected.

## 6. Historical Visibility

Visibility is part of the stored record, not a UI-only filter.

### 6.1 History layers

1. **Simulation Ledger**: batch inputs, rules, source vectors, result digests,
   receipts and statuses. Full provenance is restricted to authorized audit
   readers.
2. **Character Experience Ledger**: actor-scoped simulated experiences and
   pending memory candidates. Character Core may read it; Siming receives only
   an approved redacted projection.
3. **Five-Pool Memory**: private subjective records owned by the character.
4. **Public/Player History Projection**: only public, player-observed or
   explicitly authorized summaries.

### 6.2 Visibility scopes

```text
public
actor_observable
actor_private
authority_only
siming_internal
branch_only
```

Forbidden promotions include:

```text
siming_internal -> character knowledge
branch_only -> production memory
authority_only -> actor social memory
raw actor_private -> Siming
```

Every history record carries `valid_at`, `recorded_at`, `source_owner`,
`redaction_state`, `materialization_status` and causal references.

## 7. Time, Revision and Merge Rules

Every batch pins:

```text
from_tick / to_tick
base_checkpoint_digest
base_revision_vector
ruleset_revision
selector_revision
deterministic_seed
```

If the source or target revision has changed, the result is `stale_read_set`:
no partial merge, preserve the candidate for audit, and requeue a fresh run.

Field-level merge policy is closed and owner-specific:

| Field family | Merge policy |
| --- | --- |
| affect, pressure, fatigue | ordered recompute or CAS replacement |
| counters | idempotent delta keyed by source event |
| sets/tags | provenance-bearing union |
| goals | append transition event and rebuild current view |
| drift | accumulate candidate, then promotion gate |
| memory candidates | dedup by source event and `dedup_key` |
| presentation seed | rebuildable and discardable |

No generic "add every number and append every list" fallback is allowed.

Activation uses the existing lock:

```text
activation lock
  -> catch up owner/state cursors
  -> record experience tail
  -> materialize eligible memory candidates
  -> advance memory cursor
  -> checkpoint
  -> release/requeue
```

## 8. Siming RWEE Matrix

| Capability | Siming may do | Siming may not do |
| --- | --- | --- |
| Read | scoped world projections, public events, redacted seed history, owner receipts | raw five-pool memory, private relationship graph, hidden knowledge state |
| Write | append `SeedDelta`, memory/drift candidates, audit and activation hints | append five-pool records, mutate runtime stores, write world truth |
| Edit | create new ruleset, selector, candidate or explanation revision | edit locked facts, rewrite history, delete receipts |
| Execute | invoke a statically admitted owner capability; request Character Core materialization | choose arbitrary owner/stream/event; directly call memory stores or Godot |

Population simulation uses the same candidate restrictions and cannot expand
Siming's read scope.

## 9. LLM Role

The memory owner is deterministic Character Core/writeback policy, not an LLM.

LLM calls are optional and tiered:

```text
B0 baseline behavior       rules, no LLM
B1 local reaction           rules or small model
B2 relationship negotiation bounded model when needed
B3/player/high-value event  full LLM with scoped context
```

LLM may propose a summary, salience, subjective interpretation or L2 delta.
The output is untrusted until Character Core validates exposure, privacy,
temporal eligibility, schema, deduplication and revision. The model never
owns append, merge, correction, compaction or replay.

The prompt contains only selected retrieval cards:

```text
current runtime state
relevant memory cards
current event
authorized relationship summaries
```

It does not contain the full five-pool history.

## 10. Lifecycle, Checkpoint and Compaction

Seed deltas move through:

```text
generated
-> admitted
-> owner_settled
-> state_materialized
-> experience_recorded
-> memory_pending
-> memory_materialized
-> checkpointed
-> compacted
```

Low-value, fully settled state deltas may be rolled into a checkpoint while
preserving source ranges, before/after state, original digest and causal event
references.

The following cannot be compacted away:

- unmaterialized high-salience memory candidates;
- unresolved conflicts;
- privacy-sensitive history still inside its retention window;
- player-visible or audit-required records;
- branch-referenced records;
- pending drift promotion evidence.

## 11. Failure Semantics

| Failure | Result |
| --- | --- |
| missing exposure proof | `memory_materialization_denied`, zero write |
| future knowledge time | `temporal_knowledge_denied`, zero write |
| private scope mismatch | `privacy_denied`, redacted audit |
| stale base revision | `stale_read_set`, requeue |
| duplicate source/dedup key | idempotent replay, no duplicate memory |
| branch candidate in production | `branch_scope_denied`, zero write |
| owner rejection | preserve receipt/refusal and requeue policy |
| LLM schema or policy failure | discard proposal, keep structured candidate/audit |

## 12. Verification Requirements

Before implementation is authorized, focused tests and an independent Harness
profile must prove:

1. objective world fact does not become actor knowledge without exposure;
2. future or branch-only events cannot materialize into production memory;
3. Siming cannot read raw five-pool memory;
4. each candidate kind maps only to its eligible pool;
5. duplicate simulation is idempotent;
6. stale merge requeues without partial writes;
7. state cursor may advance independently of memory cursor;
8. checkpoint-tail replay equals full replay;
9. correction preserves historical subjective memory and appends supersession;
10. LLM failure never becomes an unvalidated memory write;
11. public/player projections do not leak actor-private history;
12. token-bound retrieval sends only scoped, selected memory cards.

Suggested future profile name:

```text
character-simulation-memory-seed-continuity
```

## 13. Non-Goals

- no generic population truth owner;
- no Siming omniscient character-memory reader;
- no LLM-per-character background loop;
- no automatic authored-dossier mutation;
- no branch-to-production memory promotion without an admitted owner contract;
- no replacement of the existing five-pool memory stores;
- no promise of full population simulation until an owner-bound vertical and
  replay evidence are admitted.
