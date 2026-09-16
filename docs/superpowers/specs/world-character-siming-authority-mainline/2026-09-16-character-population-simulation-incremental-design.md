# Character and Population Simulation Incremental Design

Status: `approved design discussion; implementation not authorized`

Date: `2026-09-16`

This document records the agreed incremental direction for combining
Siming-governed population continuity, script-driven simple mind/behavior
models, and Character Agent cognition. It adds small composable contracts and
pure helpers to existing population-continuity, scheduling, intent,
protocol, event/replay and projection paths. It does not replace those paths,
create a second runtime, or claim that INF-4 complete population simulation is
implemented.

## 1. Decision Summary

NPCs remain individual, persistent characters. Population simulation is a
temporary compression and scheduling mode selected by Siming for bounded
contexts such as war, disaster, migration, or other shared pressures. A
population has no independent truth, will, or general settlement authority.

The same character can move through these fidelity tiers:

```text
B0  temporary population compression
B1  script-driven simple mind and behavior
B2  enhanced simple model near the player or in a local event
B3  full Character Agent cognition
```

The tier changes the propulsion method, not the identity or the underlying
character state. B0-B3 consume and produce the same versioned shared data
contracts. `Character Core` remains the continuity owner; committed world
facts remain with the existing INF fact/protocol substrate; Siming remains the
governance and selection subject.

The intended direction is:

```text
character state and situation
  -> simple modules or Character Agent
  -> structured intent / continuity proposal
  -> admitted protocol
  -> atomic fact owners and append/replay spine
  -> confirmed receipt and projection
  -> Character Core, population summary and presentation
```

## 2. Architectural Boundary

The final INF platform is layered rather than a collection of unrelated
narrow business owners and rather than one mega-owner.

### 2.1 Atomic fact layer

Only atomic fact owners have final write authority. The target fact families
are:

```text
character continuity
resource custody and capacity
accounts and ledger postings
rights, relationships and authorization
commitments, obligations and contracts
rules and procedures
space and environment
events, outbox and projections
```

The exact implementation may retain compatibility facades, but every write
must identify its final fact owner. Inventory does not own title; Economy does
not own production output; Organization does not own a member's private mind;
Population owns no world truth.

### 2.2 Generic atomic operations

Fact owners expose a small, stable operation vocabulary such as:

```text
resource: reserve, transfer, consume, produce
ledger: hold, post, obligate, clear
relation: relate, assign, grant, revoke
commitment: propose, approve, fulfill, breach
rule: evaluate, authorize, reject, expire
space: move, occupy, release, restrict
continuity: apply_delta, advance_cursor, materialize
```

### 2.3 Precompiled protocols

Social behavior is a versioned composition of atomic operations. Examples are
trade, employment, rent, credit, insurance, tax, rationing, shelter admission,
organization voting and military supply. A protocol declares participants,
inputs, permissions, rules, operation order, success/failure events,
compensation or retry behavior, and receipt shape.

Current INF rows such as `supply`, `inspection`, `work` and `grain_intake`
remain verified compatibility protocols. They are not the final taxonomy for
the social system and must not become a reason to create a new owner for every
gameplay verb.

### 2.4 Models and projections

Economy, organization, government, household, army, market and disaster are
higher-level models assembled from facts and protocols. Prices, supply,
employment, social pressure and disaster risk are derived projections. A model
or projection may guide a character proposal, but cannot silently write an
atomic fact or express an independent will.

## 3. Shared Simulation Medium

The existing runtime paths exchange a read-only `CharacterSimulationFrame`,
not natural language and not a second NPC database:

```text
authored identity and archetype summary
character continuity and module state
authorized domain fact projections/references
current situation and local environment
ParticipationResolution
recent committed events and owner receipts
codebook references
source revisions, cursors and activation lock
```

Each field declares:

```text
schema and version
source owner
read scopes
write owner
aggregation policy
distribution policy
privacy class
expiry policy
```

The shared medium has three complementary forms:

1. `CharacterSimulationFrame`: current read-only input.
2. `ModuleProposal`: module suggestions for state deltas, action candidates,
   upgrades and required context.
3. `SimulationCommitPacket`: selected intent, Character Core delta, expected
   revisions, source frame digest and idempotency identity.

None of these is a world fact. Character Core or an admitted protocol must
return a receipt before the result is treated as committed.

## 4. Participation Policy

Participation is an authored, versioned contract in the character profile.
It is not a free-form Siming prompt and not a Boolean `in_population` flag.

The resolution formula is:

```text
archetype default
  + individual profile override
  + active situation preset
  + current commitments, locks and confirmed state
  = ParticipationResolution
```

The default direction is restrictive. An individual override may tighten an
archetype rule. A package may explicitly widen a rule only with a declared
reason, version and migration path. Missing configuration never silently
widens access.

The resolution contains at least:

```text
allowed fidelity tiers
current recommended tier
allowed modules and dimensions
forbidden dimensions
mandatory upgrade triggers
can_enter_b0 / can_exit_b0
maximum B0 duration and review tick
policy revision
```

Example archetype defaults for an ordinary farmer:

```text
normal tier: B1
B0 allowed: routine work, commuting, ordinary consumption, shared disaster pressure
B0 forbidden: family separation, important property, contracts, player relations
B2 trigger: local danger or player focus
B3 trigger: dialogue, negotiation, conflict or unresolved long-term choice
```

An individual such as Wang may restrict B0 for sick-spouse care, a unique
seed item, a player relationship and a story obligation. A disaster preset may
allow fatigue, route risk and ordinary migration pressure while preserving
those individual restrictions.

Siming and the Character Agent consume the same resolved contract:

```text
Siming: population scope, exceptional individuals, catalyst and timing
Character Agent: personal restrictions, unresolved commitments and upgrade request
Program: hard-boundary merge and unique activation/handoff lock
```

If either consumer supplies a hard restriction, the stricter result wins.
Neither consumer can widen an authored prohibition.

## 5. Simple Mind and Behavior Modules

Simple models are script-driven modules covering mind and behavior together.
They are package-extensible and do not require a new simulation runtime per
game.

An archetype such as farmer may bind:

```text
identity, needs, schedule, household care, supply capability,
situation response, affect and daily behavior
```

A module definition declares:

```text
module_ref and definition_version
category
input selectors
state schema
supported tiers
proposal kinds
aggregation/distribution policy
capability or protocol references
upgrade triggers
codebook references
```

The package definition is static. Character Core stores the running module
state. Each execution returns a `ModuleProposal`; it cannot write a world
fact, call another module to mutate state, or invent a new settlement path.

Module proposals contain:

```text
state deltas
action candidates
priority and reason codes
upgrade signals
required context references
frame revision and expiry
deterministic seed
```

B0 runs only aggregatable or distributable portions. B1 runs the same modules
as a batch script. B2 adds local environment and interaction inputs. B3 reads
the same module state, hard constraints and proposals, then adds language,
memory, long-term planning and conflict resolution. B3 is not a replacement
NPC; it is a more capable propulsion method for the same record.

Modules are combined by a pure character-local arbitration step, not a new
cross-domain router:

```text
legal/safety constraints
  -> existing commitments
  -> survival/health
  -> household duties
  -> organization duties
  -> work/production
  -> habits and preferences
```

The result is one of a Character Core delta, an `ActionIntent`, an upgrade
request, or a wait/defer result. Irreducible conflicts become a B3 request or
a bounded Siming exception question; they are not resolved by random module
order.

## 6. B0 Member Ledger

B0 maintains a lightweight, revisioned member ledger. It is an index and
replay proof, not a population truth store.

### 6.1 Group record

```text
group and situation references
member source query and revision
situation/ruleset/aggregation revisions
deterministic seed
checkpoint and tick cursor
group lifecycle
```

### 6.2 Member record

```text
actor_ref
Character Core revision at admission
ParticipationResolution summary and revision
allowed aggregatable dimensions
protected/individual-only references
last consumed result cursor
partition and status
```

### 6.3 Tick proof

```text
input source vectors
group aggregate summary
partition rules and seed
individual result cursor changes
owner and Character Core receipts
ruleset/selector/aggregation digests
```

Fields use explicit policies:

```text
aggregatable       -> statistics may be calculated
distributable      -> deterministic personal allocation is allowed
individual_only    -> never enters B0 aggregation
group_summary_only -> remains a safe group summary
```

If no policy is declared, the field is `individual_only`.

The same input, revisions and seed must produce the same result in full replay
and checkpoint-plus-tail replay. A group result is a candidate until the
applicable fact/protocol owner returns a receipt.

## 7. Handoff and Interaction Alignment

One actor has one active propulsion lock at a time. The following events can
trigger handoff:

```text
player proximity or interaction
Siming selects an exceptional actor
task, legal, organization or household intersection
group result requires an individual fact
module conflict or character upgrade request
multiple situations affect one actor
```

The handoff sequence is:

```text
detect intersection
-> acquire activation lock
-> freeze B0 cursor
-> build minimal intersection packet
-> apply confirmed and permitted group results
-> expand authorized context
-> start B1/B2/B3
-> submit intent or continuity proposal
-> settle through protocol/fact owner
-> Character Core accepts continuity result
-> return a safe group summary
```

The intersection packet contains actor identity, last confirmed tick,
continuity revision, source vector, hard constraints, unresolved proposals,
required codebook references and target tier. It never becomes a second
character store.

On exit, B3 cannot discard unresolved obligations. It must return confirmed
state changes, pending commitments, upgrade conditions and the Character Core
receipt. The actor may return to B2, B1 or B0 only when the resolved policy and
unresolved-fact checks permit it.

## 8. Universal Codebook

The codebook is a generic INF context-location and controlled-expansion
facility. It is not a character-only, Siming-only or population-only store,
and it does not own the source fact.

An entry contains:

```text
code_ref, source_ref, source_type, source_revision, content_digest
codec_version, encryption_key_ref, visibility_scope, reader_roles
safe_summary, expansion_levels, expiry
```

Sources can be character state, event slices, relationship graphs,
organization rules, economic contracts, inventory projections, law, situation
snapshots, package rules or Siming context. The codebook remains business
semantic-neutral: source owners interpret the expanded data.

All readers use the same conceptual operation:

```text
resolve(code_ref, reader, purpose, requested_level)
```

The program checks identity, purpose, scope, revision and digest; decrypts and
decompresses; filters to the minimum sufficient fields; and returns an
expansion receipt. Models never receive a universal key or unfiltered source.

Expansion levels are progressive:

```text
L0 safe summary
L1 filtered fact card
L2 authorized exact content or projection
```

Siming commonly receives group risks, exception candidates and conflict
summaries. Character Agents may receive their authorized private facts.
Population B0 normally receives only L0. The same `code_ref` may therefore
yield different legal projections without changing the underlying fact.

The context rule is:

> Information that can be prefetched, mapped, deterministically calculated,
> queried, or expanded by the codebook does not occupy permanent Siming or
> Character Agent context. Permanent context contains only the current
> summary, constraints, conflicts, candidates and receipts.

## 9. Social Facts and Protocol Flow

Organizations, markets, governments and households have no independent
character-like will. Their behavior is produced by roles, memberships,
authorizations, procedures, contracts and automatic consequences of already
effective rules.

The common flow is:

```text
character/module/agent proposal
-> ActionIntent
-> admitted precompiled protocol
-> relation/permission checks
-> resource/ledger/commitment/rule/space operations
-> one atomic event batch
-> owner receipts and projections
-> Character Core, group summary and presentation
```

Automatic expiry, account posting, reservation release or other consequences
are allowed only when a contract or effective rule already authorizes them.
They do not represent an organization developing a new intention.

Economy is explicitly layered:

```text
atomic resources, custody, accounts and obligations
-> payment, quote, order, employment and contract protocols
-> market, finance, tax and organization combinations
-> price, supply, employment and macro projections
```

The current Economy, Inventory, Organization, Government and Social platform
classes can remain compatibility facades while each operation is classified as
an atomic fact, protocol step, projection or compatibility adapter. New
features must not expand a facade without declaring that layer.

## 10. Truth, Character Core and Presentation

The world truth layer accepts confirmed facts only. Population simulation,
simple models, Character Agents and Siming submit proposals or intents.

`Character Core` owns actor identity continuity, shared module state, cursor
advancement and memory/materialization gates. Domain facts remain with the INF
fact/protocol substrate. The codebook only locates and filters content.

Godot owns local embodiment and presentation. It may show a rebuildable local
prediction while waiting for a result, but it cannot create a transaction,
grant a permit, assign a role, move inventory or declare an NPC rescued. Only
confirmed backend events may become durable world presentation.

## 11. Reference Vertical: Farmer, Village and Flood

The first complete validation sample is a composition test, not a flood
special case.

The package provides farmer modules for identity, needs, schedule, household
care, supply, affect and behavior. Wang is an ordinary farmer archetype with
profile overrides: a sick spouse, a unique seed item, a player relationship
and a no-family-separation restriction.

The flood situation supplies water level, route risk, damaged fields, reduced
routes, shelter capacity and food pressure. The situation preset allows B0 to
process fatigue, fear, route pressure and basic consumption, but forbids family
separation, unique property, personal contracts, player relations and key
tasks.

The flow is:

```text
normal B1 village life
-> Siming admits bounded flood cadence
-> B0 groups eligible villagers and preserves protected fields
-> deterministic fatigue/route pressure distribution
-> player meets Wang
-> handoff lock and minimal context expansion
-> B2/B3 chooses household shelter intent
-> shelter, capacity, medicine, route and authorization protocols settle
-> confirmed facts return to Character Core and projections
```

If a shelter has no capacity, the system records a failed request and keeps
Wang's fatigue, fear and obligations. It must not display that he entered.
If grain is sold, the character proposes a trade, the protocol reserves grain
and funds, checks rules, commits resource and ledger facts, and only then
updates economic projections.

## 12. Implementation Phases

The design is intentionally staged. Every phase extends an existing
continuity, scheduling, intent, protocol, event/replay or projection path;
none constructs a parallel population-simulation runtime:

1. classify current classes as fact authority, protocol authority, projection
   or compatibility adapter; do not change behavior;
2. freeze `CharacterSimulationFrame`, `ParticipationResolution`,
   `ModuleProposal` and `SimulationCommitPacket` contracts;
3. add package-defined simple modules and two-level archetype/profile binding;
4. implement the B0 member ledger, deterministic distribution and cursor rules;
5. implement the intersection packet and B0/B1/B2/B3 handoff;
6. connect character intents to admitted generic protocols;
7. make the universal codebook available to all authorized consumers;
8. optimize the existing DOD hot state and batch execution only after
   correctness evidence.

The INF platform may continue its own generic fact/protocol work in parallel.
Population simulation may consume only already admitted capabilities. A new
objective population behavior remains zero-write until its source, capability,
protocol, owner receipt, Character Core mapping, privacy and replay evidence
are admitted.

## 13. Verification Invariants

Any implementation plan derived from this design must prove:

1. `SimingRuntime.tick(...)` remains the sole Siming decision/dispatch path.
2. No Population Truth Owner, second runtime, clock, event store or generic
   settlement/router is introduced.
3. Character identity and continuity remain single-sourced in Character Core.
4. Participation policy is consumed identically by Siming and Character Agent.
5. A character has at most one active propulsion lock.
6. B0 full replay and checkpoint-tail replay are equivalent.
7. Individual-only fields never enter group aggregation.
8. Objective effects require an admitted protocol and owner receipt.
9. Module and Character Agent proposals remain untrusted until settled.
10. Codebook expansion is permissioned, revision-pinned, minimal and audited.
11. Presentation never turns prediction into a durable fact.
12. The farmer/village/flood vertical preserves identity across B0-B3 and
    proves at least one success and one fail-closed social protocol outcome.

## 14. Non-Goals

This design does not authorize:

```text
complete civilization simulation
free-running full-LLM NPC loops
a population/social truth owner
an organization or economy with independent will
a generic cross-domain router or settlement coordinator
direct model writes to inventory, accounts, law or memory
automatic branch promotion
full INF-4 completion claims
```

The current INF-4 implementation remains a bounded population-continuity and
owner-adaptation slice. This design defines the path toward the final generic
platform while preserving that status until each missing contract has its own
implementation and replay evidence.
