# Mainline Capability Implementation Decomposition

Status: `approved execution decomposition; no work package is complete until its own evidence gate passes`

## Purpose

Turn the August-analysis designs into implementable mainline work without
mistaking existing bounded samples for a generic platform. Every package below
extends the existing `world_runtime`, domain authorities,
`GameplayEventStore.append_batch()`, outbox and replay. None may introduce a
second runtime, event store, bus, scheduler, population owner, NPC truth store
or social truth store.

## Shared completion rule

A package is only `implemented-and-verified` after all five are present:

1. a bounded formal specification and implementation plan;
2. owner-scoped code that uses the existing append/replay path;
3. focused tests for happy path, deterministic replay, idempotency/revision
   rejection, privacy scope and zero write on failure;
4. an independently named Harness profile whose checks map one-to-one to the
   assertions; and
5. an evidence report plus an August-analysis status update naming the code and
   evidence paths.

## Dependency graph

```text
INF-1 semantic/entity/causal
  -> INF-2 time/obligation/receipt
    -> INF-3 ecology/disaster
    -> INF-4 population/branch replay
INF-1 -> SOC-1 social/knowledge/privacy
INF-1 + INF-2 -> GAME-1 gameplay-system expansion
INF-1 + SOC-1 -> CREATOR-1 package/control plane
CREATOR-1 -> COST-1 operating economy
```

## Work packages

| ID | Scope and existing owner | Deliverable boundary | Acceptance evidence |
| --- | --- | --- | --- |
| INF-1 | `semantic_registry`, `shared_contracts`, `GameplayEventStore`, replay | Registered tag definitions/assignments; immutable semantic snapshot with inheritance/conflict rejection; entity/thing/environment/relationship dossiers; append-only causal projection; proposal-only rule output | selector/inheritance/conflict tests; causal-parent query; same input digest/trace; rejected rule produces no events; full vs checkpoint-tail replay |
| INF-2 | `world_runtime/scheduling.py`, existing domain authorities, settlement adapter | Explicit caller-driven `SimulationClock` and bounded due selection are now implemented; obligation lifecycle, activation lock/pending merge and uniform cross-domain receipt remain follow-up work | `infra-time-obligation` proves no background ticking, due ordering, catch-up budget and rewind rejection; remaining cases keep INF-2 partial |
| INF-3 | `frost_farm_runtime` plus INF-1/2 adapters | Region, environmental state, resource node and hazard records; frost vertical slice from scheduled hazard to crop-owner effects and scoped projection | hazard idempotency; resistance; causal trace; budget truncation; public/authority projection; replay |
| INF-4 | `population_continuity`, existing character profiles and event store | Daily/long-cycle planner over existing profiles, family/organization inputs as projections, deterministic branch-preview replay and calibration inputs | no synthetic NPC truth; deterministic shuffled batch; activation lock merge; branch isolated from production; privacy/replay proof |
| SOC-1 | `gameplay/p5/social_knowledge.py` and existing authority/event path | Relationship graph, credentials, typed propositions, belief/disclosure/rumor lifecycle and perception-query projection | source/visibility enforcement; redaction; stale/duplicate rejection; causal explanation and replay |
| GAME-1 | existing action, construction, survival, inventory, equipment and body authorities | Generic action registry, scheduled needs, construction lifecycle, conflict/damage contract, resource/cultivation gates; each remains owner-scoped | one vertical slice per subsystem; resource conservation; fail-closed action/permission; event/replay evidence |
| CREATOR-1 | package manifests, active revisions, patch lifecycle and authorization | Signed package schema, dependency/compatibility/migration validation, Preview vs Production activation and rollback; UI/CLI/MCP merely propose | signature/compatibility denial; activation lock; audit/replay; no creator direct write; independent package Harness |
| COST-1 | model-provider/readiness, memory and audit projections | Metering ledger, budget/lease/preemption decision contracts, consented reuse cache and fairness review projection | budget exhaustion zero write; cache scope isolation; reproducible accounting receipt; audit/privacy checks |

## Cross-cutting implementation constraints

- Definitions are versioned and registry-owned; assignments and state changes
  remain owned by their domain authority.
- Any generic rule or scheduler is deterministic, bounded, caller-driven and
  proposal-only until its owners produce authorized event fragments.
- Godot, LLMs, Siming, creator tools and MCP may submit intent/proposal/evidence
  only. They never append world events directly.
- “Complete profile” is a prohibited label unless all completion-rule evidence
  above exists for that exact package.

## Immediate execution boundary

Begin with INF-1. It is deliberately limited to one semantic/entity/causal
vertical foundation and does not claim to finish all materials, all effects or
all gameplay domains. INF-2 may start only after INF-1 fixes the snapshot and
causal contracts it needs.
