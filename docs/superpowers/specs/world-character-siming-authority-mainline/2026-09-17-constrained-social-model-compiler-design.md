# Constrained Social Model Compiler Design

Status: `approved design; implementation not authorized`

Date: `2026-09-17`

Related baseline: [Character and Population Simulation Incremental Design](2026-09-16-character-population-simulation-incremental-design.md)

Chinese counterpart: [受约束社会模型编译器设计（中文版）](2026-09-17-受约束社会模型编译器设计-中文版.md)

## 1. Decision Summary

This design adds a **constrained social model compiler** to the social-model
layer defined by the population incremental design. It is not a second world
runtime, population truth owner, event store, clock, scheduler, settlement
router, or cross-domain read database.

The compiler turns a permitted, structured request into a temporary model over
a frozen vector of owner-signed read inputs. It can calculate predictions,
candidate actions, conflicts, risks, expansion requests, and protocol-call
requests. Every result remains a proposal. Existing propulsion subjects choose
whether to adopt a result; existing fact owners and admitted protocols alone
decide whether a world fact is committed.

```text
existing proposer + valid ModelRunGrant
  -> SocialModelDraft
  -> static-template and permission admission
  -> graph candidate discovery + owner FactCard/Proof reads
  -> frozen InputVersionVector
  -> temporary declarative IR execution
  -> CandidateEnvelope[] + ModelRunReceipt
  -> existing B0/B1/B2/B3 propulsion subject may adopt
  -> existing ModuleProposal / ActionIntent / protocol request
  -> existing owner revalidation, settlement, receipt and projection
```

This design extends, and is subordinate to, the existing layered direction:

```text
atomic facts and atomic operations
  -> admitted precompiled protocols
  -> social models
  -> derived projections
```

It does not change the ownership of atomic facts, Character Core continuity,
`ParticipationResolution`, the activation/handoff lock, or
`SimingRuntime.tick(...)` as the Siming decision and dispatch path.

## 2. Scope and Hard Boundaries

### 2.1 In scope

- A declarative, finite-category model compiler that performs pure,
  snapshot-bound social analysis.
- Static, immutable, trusted gameplay-package templates and parameter profiles.
- Owner-issued minimal read inputs, graph-assisted discovery, deterministic or
  seeded scenario analysis, candidate output, read-side projections, and
  replay evidence.
- B0 aggregate and limited-shard analysis; B1/B2 local and batch analysis; B3
  minimal authorized individual-context analysis.
- Siming-governed computation grants and staged rollout from shadow to active
  advisory use.

### 2.2 Out of scope

This design does not authorize:

- a generic social, population, market, organization, or war truth owner;
- an independent will, goal, or personality for an organization, market,
  household, army, or the compiler;
- direct inventory, account, right, relationship, population, space, legal,
  memory, or process writes by a model, graph, LLM, Siming, or presentation;
- dynamic Python, package scripts, a formula DSL, dynamic schemas, or arbitrary
  executable plugins;
- a compiler-owned queue, retry loop, clock, scheduler, event store, lock, or
  settlement coordinator;
- a shadow NPC database, per-person B0 allocation table, or a global social
  snapshot database;
- a claim that full population simulation, war trade, diplomacy, or any
  unadmitted owner capability is currently implemented.

## 3. Closed Model Taxonomy

Version 1 has exactly eight model categories. A template declares every
category it uses. Trusted packages may combine and parameterize registered
nodes, operators, and data profiles inside these categories only. A ninth
category, a new IR node, or a semantic change to an operator requires a
separate architecture admission and replay contract.

| Category | Typical question | Examples | Compiler responsibility and output ceiling |
| --- | --- | --- | --- |
| Entity-relationship graph | Who is related, belongs, or is authorized? | families, members, offices, hostility, alliances, debts | discover feasible participants, relationship conflicts, authorization gaps, and expansion requests; never grant, revoke, or create a relationship |
| Resource custody and flow network | What resource is where, held by whom, movable how, and when exhausted? | food, funds, weapons, medicine, warehouses, convoys | calculate shortages, candidate flows, custody/capacity conflicts; never consume, reserve, transfer, or create a resource fact |
| Space-accessibility graph | Can people or goods pass, how long, and at what risk? | roads, ports, checkpoints, fire zones, snow, fronts | calculate route candidates, time and risk; unconfirmed physical evidence may only raise risk |
| Process/state machine | Which step is a social matter in? | quote/order/load/transport/accept/pay; recruit/muster/supply/fight/rest | report valid next-step candidates and blockers; never advance a process |
| Commitments and timetable | What has been promised, when is it due, and what is at risk? | contracts, wages, rations, debt, treaties, tasks | report deadlines, breach risk and fulfilment candidates; never create, fulfil, forgive, or breach a commitment |
| Constraint and allocation model | How do finite resources compete and where is the conflict? | shelter beds, rations, workshop capacity, military supplies, budgets | compare feasible aggregate or shard allocations and conflict sets; B0 never emits a per-person allocation table |
| Risk and propagation model | How does pressure spread across relations and space? | famine, rumors, disease, desertion, fire, panic | emit intervals, scenario branches, warnings and verification requests; predictions are not events |
| Aggregation and distribution model | How is a group safely compressed and later reconnected to an individual? | B0 morale, fatigue, food pressure, migration risk, casualty candidates | emit group/shard indicators and distributions, plus upgrade requests; never overwrite protected or `individual_only` fields |

Family, organization, market, migration, disaster, and war logistics are names
for combinations of these eight categories. They are not additional categories,
runtime hosts, or independent actors.

## 4. Authority Model

### 4.1 Existing subjects retain their roles

| Subject | May do | May not do |
| --- | --- | --- |
| Siming | issue scoped `ModelRunGrant`s through its existing tick, choose global cadence and catalysts, consume redacted summaries | read private character memory, directly settle facts, or give a model write authority |
| B0/B1/B2/B3 propulsion subjects | propose drafts, receive candidates, and decide whether to adopt candidates through their existing paths | treat a candidate as a fact or bypass the activation/handoff lock |
| Character Agent / LLM | select an activated template, fill bounded parameters, state an objective or anomaly, explain a result | invent types, facts, rules, code, schemas, or settlement paths |
| Compiler | validate, assemble, calculate, detect conflicts, and record a run receipt | submit a protocol, select a winner, acquire a lock, reserve a resource, or commit a fact |
| Fact/protocol owner | issue filtered FactCards, revalidate a selected request, settle its own facts, issue receipts | trust stale model input or delegate ownership to the compiler |
| Heavenly Graph | discover indexed candidates and expose source-pinned derived context | become a fact owner or replace owner reads |
| Godot / presentation | emit embodied observations and show confirmed results or rebuildable predictions | change durable truth because an animation, collision, sound, or UI suggests success |

### 4.2 Candidate adoption

The original propulsion subject is the only subject that may adopt a compiler
candidate:

- B0 uses the Siming-approved group policy.
- B1/B2 use their existing scripted propulsion rules.
- B3 uses the Character Agent within its authorized private context.

The compiler, an organization, a market, and a fact owner do not acquire a
general decision-making role by receiving a candidate. Adoption only turns a
candidate into an existing `ModuleProposal`, `ActionIntent`, or typed protocol
request. The target owner must still check its current facts and expected
revisions.

## 5. Data Contracts

The names below describe target contracts. They are not claims that the
contracts have been implemented.

### 5.1 `SocialModelTemplate`

An immutable declaration supplied by an admitted gameplay package. It contains:

```text
package_ref, package_digest, template_ref, template_version, active_set_digest
taxonomy_categories, IR node declarations, fixed operator/profile references
required and optional FactCard kinds
permitted proposer kinds, consumer scopes, privacy ceiling and purposes
permitted output kinds and target capability/protocol references
per-tier B0/B1/B2/B3 eligibility and aggregation restrictions
maximum analysis_window, frequency, scenario count and compute/context budgets
declared fallback table and redaction policy
```

It contains no executable code, dynamic query, free-form schema, authority
coordinate, or write permission.

### 5.2 `ModelRunGrant`

Siming issues a temporary, immutable computation authorization in an existing
Siming tick. A grant can narrow, never widen, template limits:

```text
grant_ref, issuer and Siming tick/correlation reference
template/package/active-set pins
requester and permitted proposer kinds
purpose, scope, privacy ceiling and reader roles
valid time interval, analysis_window ceiling and run-frequency ceiling
context, node/edge, scenario, candidate and execution budgets
run mode: off | shadow | advisory | active
grant revision and digest
```

It is neither a protocol authorization nor a resource reservation.

### 5.3 `SocialModelDraft`

Existing proposers create this bounded request:

```text
template_ref and expected package/active-set pins
proposer identity and purpose
participant, situation, and context references
bounded, typed parameters and requested scenario count
requested output categories and correlation/idempotency identity
```

The draft may not carry a free-form IR, factual values, executable text, owner
commands, a scheduling instruction, or unbounded context.

### 5.4 `FactCard` and `Proof`

Only the source owner can issue a read input for a hard model constraint. Every
card or proof includes at least:

```text
card_ref, fact family and source owner
authorized purpose, scope, privacy class and consumer/reader constraints
revision, digest, valid_at, recorded_at, expiry and source event references
provenance and any required rule/package/policy pins
```

Embodied and environmental evidence additionally includes source identity,
object/space version, confidence, validity interval, and confirmation state.
The compiler reads filtered cards, never an owner's private database or
internal projection.

### 5.5 `InputVersionVector`

The compiler freezes all inputs before evaluating a draft:

```text
template, package, active-set, operator-profile and grant pins
FactCard/Proof references with owner, revision and digest
codebook expansion receipts
graph candidate references and successful owner back-check proofs
time anchor, analysis_window, typed parameters, deterministic ordering and seed
```

Required cards must all be present and valid. An optional-card omission can
only take the template's declared conservative fallback. The compiler never
fills a hole with an old cache entry or a guessed value.

### 5.6 `CandidateEnvelope`

Every output uses one restricted envelope:

```text
candidate_ref, correlation/idempotency identity and output kind
semantic payload validated by the fixed template schema
target registered capability/protocol reference, if applicable
input vector digest, expected owner revisions and supporting proof references
risk/confidence bounds, scenario seed/reference and expiry
affected scope, privacy/redaction labels and budget consumption
```

The only output kinds are:

```text
prediction
action_candidate
continuity_or_state_delta_candidate
conflict
risk
expansion_request
protocol_call_request
```

No envelope is a command or fact. A continuity candidate must reuse the
existing versioned `ModuleProposal`/continuity contract and can only name
fields allowed by the active module and `ParticipationResolution`.

### 5.7 `ModelRunReceipt` and `ModelProjection`

Every admitted run, including an empty, degraded, rejected, truncated, or
errored run, creates a minimal redacted receipt:

```text
run_ref, status, correlation, template/grant/input-vector/seed digests
codebook read receipts and graph back-check outcome
operator/profile versions, deterministic ordering and budget result
candidate/output digest, cache reuse reference, timing and redaction metadata
```

`ModelProjection` is a derived, expiring, scope-filtered read projection
created from a receipt. It may expose a prediction, risk, shortage interval,
or conflict summary to a later authorized consumer. It never becomes a fact,
does not become a Heavenly Graph fact node, and is invalid once its declared
inputs, authority, privacy, or time window no longer hold.

## 6. Compilation and Sandbox

### 6.1 Static admission and precompilation

When an immutable gameplay package is activated, the system validates the
template category declarations, fixed nodes, operator/profile pins, declared
read-set, output permission, budgets, LOD constraints, and fallback table. A
validated template skeleton may be precompiled into a static IR execution
graph. The skeleton contains no live world state.

The fixed operator directory contains pure, versioned implementations only.
Packages provide data profiles such as thresholds, routing-cost weights,
propagation attenuation, allocation objective selection, state-transition
conditions, and aggregate curves. A profile cannot alter operator semantics,
load code, create an output kind, or address a new owner operation.

### 6.2 Runtime compilation

```text
verify grant, proposer, template pins, purpose, scope, privacy and budget
-> validate bounded draft parameters
-> discover graph candidates within authorized scope
-> back-check every hard candidate against its source owner
-> request required/optional FactCards and codebook expansions
-> freeze the InputVersionVector
-> bind references and parameters to the static IR skeleton
-> run pure hard-constraint pruning
-> run resource, space, process, commitment and allocation calculations
-> run a bounded number of risk/scenario branches last
-> emit envelopes, projection candidates and ModelRunReceipt
```

The compiler rejects undeclared nodes, cycles where the template has not
declared an admissible acyclic evaluation order, dynamic dispatch, unpinned
operators, invalid numeric domains, and any attempt to acquire a world-side
resource or write handle.

### 6.3 Uncertainty

The compiler uses two distinct channels:

1. Missing knowledge is never randomized. Missing, stale, unauthorized, or
   contradictory information produces an explicit degraded status.
2. A valid template may calculate deterministic bounds and a finite number of
   scenario branches using a frozen seed. A branch is a comparison tool, not a
   pre-committed future world outcome. Actual stochastic outcomes remain in
   the relevant owner protocol and evidence path.

## 7. Input, Graph, Privacy, and Context Rules

### 7.1 Heavenly Graph

The Heavenly Graph remains a derived index with scope, time, revision, privacy,
consistency-audit, source-event, and provenance metadata. It may discover
candidate participants, relations, paths, dependencies, or causal context.

A graph edge becomes a hard model constraint only after the compiler:

1. checks its visibility, freshness, revision, audit state, and provenance;
2. obtains the edge's source-event and source-owner references;
3. receives an owner-issued FactCard/Proof that confirms the relation at a
   compatible frozen revision.

If this process fails, the edge is not substituted with a graph guess. The
template returns `graph_degraded`, `context_insufficient`, or a declared
conditional risk result. Operational facts such as custody, rights, balances,
capacity, membership, and process state always require owner cards.

### 7.2 Privacy and codebook expansion

Every run is bound to requester identity, purpose, scope, and privacy ceiling.
Cross-domain models exchange only owner-signed minimal cards, aggregates, or
proofs. Codebook expansion follows the existing L0/L1/L2 permissioned path
and records an expansion receipt. The compiler stores references and digests,
not a universal plaintext copy.

Siming receives public or explicitly Siming-visible summaries. B0 normally
receives L0-safe summaries. B3 may receive authorized private cards only for
the relevant actor and purpose. Outputs are filtered again for each consumer.

## 8. Truth Update and Embodied Evidence

### 8.1 Truth-update rule

| Apparent change | Model may emit | Only committed fact and confirmer | Required basis; unknown behavior |
| --- | --- | --- | --- |
| inventory decrease | consumption/ration candidate, shortage prediction | Inventory custody/capacity owner | custody, availability, purpose, protocol receipt; no evidence means no decrease |
| migration or death | risk, migration/rescue intent, B2/B3 request | Character Core continuity plus applicable life/space/environment owner | identity, location, confirmed evidence and rules; group casualty statistics never assert individual death |
| wealth/value change | supply/price interval | market price is a projection; account balance is Economy ledger truth | real quotes/orders/trades/rules; a forecast cannot create value or a posting |
| account balance | payment/hold candidate | Economy/account ledger owner | authority, counterparties, balance, contract and atomic receipt |
| character right | authorization gap or application candidate | existing Rule/Organization/Government owner | effective procedure, qualification, representation and receipt |
| organization membership | eligibility/conflict candidate | Organization owner | identity, charter/procedure/vote/appointment evidence |
| road/building damage | route/repair candidate and raised risk | Space/Construction/environment owner | confirmed object/space/versioned evidence; presentation alone is insufficient |
| market price | risk/price projection | Economy/market projection derived from facts | committed trade/order/rule data; no forecast writes a formal price |
| military morale | group pressure and continuity candidate | allowed Character Core receipt or admitted domain owner | confirmed events and allowed module rules; B0 does not write soldier-by-soldier state |

At adoption, a target owner compares the request's expected revision with its
current source. Any mismatch is a hard `stale_input` or `conflict` rejection
with zero write. The owner does not locally repair quantities, route choices,
or participants from an old model result.

### 8.2 Evidence classification

| Evidence type | Model status before owner confirmation | Path to a hard constraint |
| --- | --- | --- |
| pure semantic event | intent, proposal, catalyst, or candidate; never fact | admitted protocol/rule and owner receipt |
| embodied action event | time-limited risk input with source and confidence | fact emitter evidence -> object/space/authority/causality validation -> confirmed FactCard |
| continuous environment event | time-limited risk input with region/version/confidence | environment/space owner confirmation -> confirmed FactCard |
| pure presentation event | never a model fact or hard constraint | none; it remains rebuildable local presentation |

For example, a door-contact and completed-animation observation can make a
model request verification or avoid a risky path. It cannot assert that the
door is open until the relevant object/space/permission owner confirms it.

## 9. LOD, Scheduling, and Performance

### 9.1 Context LOD

| Context layer | Legal inputs and computation | May propose | Mandatory upgrade triggers |
| --- | --- | --- | --- |
| player-local | confirmed local projections, authorized object/actor state, rebuildable prediction | player input and interaction intent | player interaction enters existing handoff judgment |
| B3 key actor | minimum private FactCards, authorized codebook expansion, shared module state and local model result | ModuleProposal, ActionIntent, draft, explanation | dialogue, negotiation, long-term conflict, protected field, non-scriptable decision |
| B2 local event | event-local space/process/relation/resource cards and limited actors | local candidates, draft, upgrade request | player intersection, individual right/contract/family conflict, scope escape |
| B1 ordinary life | archetype/profile/situation, B1 modules, ordinary local/shard summaries | batched ordinary proposals and intents | unresolvable rule conflict, protected field, local anomaly |
| B0 compression | L0 summary, group/limited-shard cards, ParticipationResolution summary, aggregate model projections | aggregate indicators, curves, risk, total candidates, upgrade request | `individual_only`, family separation, key property, contract/right, player relation, death/injury, unsafe materialization |
| Siming global summary | public/Siming-visible owner summaries, redacted projections, graph discovery and grant state | grant, catalyst, exception choice and cadence proposal | private or individual decision requires a permissioned expansion request |

The compiler may only emit `required_fidelity` or `expansion_request`. The
existing `ParticipationResolution` and activation/handoff lock decide and
perform a handoff. Character Core remains the only continuity/materialization
acceptor.

### 9.2 B0 aggregate rule

B0 is intentionally coarse:

```text
B0 member ledger
  = identity anchors, shards, admission revisions, policy summaries,
    protected references and cursors
  != per-person allocation, resource, casualty, or location table

B0 model
  = cohort/shard/resource-pool/route/process-batch analysis
  -> totals, ratios/curves, shortage intervals, risk intervals, seed and expiry
  != individual actor state updates, custody assignments, or trades
```

An owner may confirm group or shard totals such as consumed food, occupied bed
capacity, used convoy capacity, and a statistical distribution descriptor.
When an actor exits B0, the existing handoff path uses the actor's anchor,
protected constraints, confirmed aggregate receipts, and template rule to
create the smallest safe context. It either produces an allowed continuity
candidate or reports `unknown`/requires B1/B2/B3. It never assigns an average
as an unverified personal fact.

### 9.3 Cadence and analysis window

The compiler never runs per frame or advances world time. A template declares
a maximum bounded `analysis_window`; a grant may shorten it but cannot expand
it. Longer analysis requires a later read and recompilation.

| Frequency | Owner |
| --- | --- |
| per-frame/realtime | Godot local presentation and physical sampling only |
| local physical or process event | relevant owner evidence confirmation; confirmed events may invalidate affected model scope |
| B2 minute-scale or local-event cadence | existing local propulsion path under grant |
| B1 hour-scale cadence | existing scripted propulsion path under grant |
| B0 game-day or authorized disaster cadence | Siming-governed group path |
| weekly | derived macro `ModelProjection` only |
| confirmed major event | invalidates affected models; existing path decides whether to recompile |

### 9.4 Performance and cache rules

The target is precompile once, execute in batches, and expand context on
demand:

1. Cache static template skeletons by package/template/active-set/IR/operator
   digest.
2. In the first implementation stage, cache a model result only for an exact
   complete input-vector, parameter, grant, and seed match.
3. Later, add owner-card fragment invalidation only after independent proof;
   never reuse an approximately matching old world result.
4. Operate B0 on cohorts, shards, pools, routes, and process batches rather
   than individual NPC nodes. Apply hard constraints before expensive scenario
   work.
5. Pure non-overlapping scopes may execute in parallel. They share no mutable
   world state; owner settlement remains independently version-checked.

A cache hit records `reused_from` in the receipt. No cache becomes a copy of
NPC truth or a global latest-social-state database.

## 10. Failure, Degradation, and Run Modes

The compiler owns no automatic retry queue. It returns a status and receipt;
the existing grant/cadence/event path decides whether a later window retries.

| Status | Required behavior |
| --- | --- |
| `ok` | valid candidates were produced; they remain untrusted proposals |
| `unknown` | no legal conclusion; preserve the unresolved condition |
| `context_insufficient` | required card or expansion absent; wait, request expansion, or upgrade under existing policy |
| `proposal_only` | analysis is useful but no admitted target capability/protocol can receive it |
| `graph_unavailable` | skip graph discovery; run only if direct owner reads suffice |
| `graph_degraded` | graph candidate failed audit/freshness/provenance/back-check; do not use it as a hard constraint |
| `owner_unavailable` | required owner cannot issue a card; zero write and defer |
| `stale_input` | input or adoption revision changed; hard reject and recompile on a new vector |
| `budget_exhausted` | return only safe completed summary or proposal-only result; never spin or silently weaken policy |
| `policy_denied` | grant/template/proposer/privacy/LOD constraint failed; zero write |
| `conflict_detected` | report the conflict set and evidence; do not choose a winner |
| `zero_write` / `error` | retain redacted diagnostic receipt and no durable effect |

Run modes are:

```text
off       no model compilation or model reads
shadow    compile and compare; no candidate/projection reaches a propulsion subject
advisory  authorized consumers receive candidates/projections but cannot adopt them
active    existing propulsion subjects may adopt candidates through existing paths
```

## 11. Replay, Audit, and Projection Verification

Every admitted run must support both full replay and checkpoint-plus-tail
replay. Replaying a run pins template/package/active-set, operator profile,
grant, input cards, codebook read receipts, graph back-check results, ordered
parameters, time anchor, analysis window, budget, and seed.

The replay must reproduce the same status, output digest, degradation reason,
and cache explanation. It does not force future owner randomness to match a
scenario prediction. Every later adoption and owner receipt retains the source
`ModelRunReceipt` correlation so audit can distinguish:

- a model that suggested a candidate;
- a propulsion subject that adopted or ignored it;
- an owner that accepted or hard-rejected it;
- a projection that expired without world effect.

Model receipts and projections are read-side/audit artifacts. They may be
projected into authorized existing observability surfaces, but they cannot
append world facts or be reclassified as graph facts.

## 12. Reference Case A: Flood Village Food Allocation

This is the first intended verification vertical, not an implementation claim.
Siming issues a game-day flood grant for a village, its north/south
non-sensitive shards, and a bounded day window. The
`flood_village_rationing@v1` template combines family/authorization relations,
grain custody, convoy and shelter capacity, damaged routes, ration process
state, existing ration commitments, aggregate allocation, risk, and B0
compression.

The graph can discover village/family/road/shelter candidates. Organization,
Character Core, Inventory, Space/Environment, and Rule owners provide the
corresponding cards. An unconfirmed report that rubble may block the south
road is a temporary risk input only; an owner-confirmed road closure is a hard
constraint.

The model can report, for example:

```text
north shard: 82% daily demand coverage candidate
south shard: 48-62% coverage interval because route risk is unresolved
shelter: 16 confirmed aggregate beds remaining
outputs: aggregate ration/transport protocol requests, road-verification
request, and fidelity requests for protected households/player-near actors
```

It cannot state that Wang received a particular food quantity or that a named
person is already sheltered.

| Perspective | Role |
| --- | --- |
| Player | sees confirmed road, storage, and shelter results plus rebuildable evaluation feedback; may submit structured escort, clearing, or delivery intent |
| Siming | sees group risk/exception summaries and grant budget; chooses cadence and catalyst, not individual food distribution |
| Character Agent | after legitimate B2/B3 handoff, reads minimum authorized household constraints and proposes a household-safe intent |
| Compiler | compares aggregate demand, routes, capacity, commitments, and risks; emits candidates and upgrade requests |
| Fact owners | revalidate storage, vehicles, road, authorization, and capacity; settle admitted protocol facts or reject |
| Presentation/physics | observes loading, contact, route, and door conditions; submits evidence but never declares delivery, shelter admission, or food transfer |

Success is an owner-confirmed aggregate inventory/capacity receipt and
authorized continuity feedback. If capacity or revisions conflict, the owner
hard-rejects with zero write; Wang retains his confirmed fatigue, fear,
obligations, and unresolved request rather than being falsely shown as safe.

## 13. Reference Case B: Winter War Trade Between States

This is a complete design example, not a statement that all required owner
capabilities exist. `winter_embargo_supply_risk@v1` combines all eight
categories across a bounded winter window:

- public representatives, merchant organizations, convoys, army logistics,
  alliances, hostility, and confirmed authority relations;
- food, fuel, medicine, weapons, storage, convoy, and supply-pool cards;
- ports, roads, checkpoints, snow, fronts, and confirmed restrictions;
- quote/order/load/transport/accept/pay and recruit/muster/supply/fight/rest
  process states;
- embargoes, contracts, delivery dates, debts, and treaty obligations;
- allocation among civilian market, medical, military, and strategic stock;
- panic, smuggling, desertion, disease, and route disruption risk;
- limited aggregate shards for non-key convoy labor, military logistics
  pressure, and civilian demand.

It may predict a military supply coverage interval, report vehicle/time-window
conflicts, propose an existing transport/ration/diplomatic-review protocol,
request port verification, or request B3 for a key negotiator. It may compare
frozen-seed scenarios such as continued versus partial port closure. It may not
implement an embargo, move a convoy, post an account entry, identify a spy,
grant a smuggling right, start a war, or sign a treaty.

| Perspective | Role |
| --- | --- |
| Player | receives only authorized public market, route, and embargo effects; may escort, negotiate, scout, or submit typed intents |
| Siming | governs grants and global risk/catalyst summaries; does not decide state intentions or alter diplomacy |
| Character Agent | merchants, officers, diplomats, and civilians use their own authorized commitments and constraints to propose actions |
| Compiler | compares frozen relation, custody, route, process, deadline, allocation, and risk constraints |
| Fact owners | Inventory/transport, Economy, Organization, Government/Rule, Contract, and Space/Environment independently revalidate and settle their facts |
| Presentation/physics | shows confirmed checkpoints, snow, convoy movement, loading, and arrival; provides evidence without confirming title, acceptance, or payment |

If a required embargo, treaty, transport, or account capability has no admitted
owner-bound protocol, the result is `proposal_only` or `owner_unavailable`.
The compiler may not bridge the gap by creating a general war-trade authority.

## 14. Delivery Sequence and Acceptance Evidence

Each phase remains separately reviewable and proves a bounded extension of
existing paths.

1. **Foundation classification and contracts.** Freeze the taxonomy, contracts,
   redaction, statuses, and non-goals. Prove unknown categories, dynamic code,
   free fields, and forbidden authority paths fail closed.
2. **Static template admission and shadow compiler.** Add immutable template
   skeletons, fixed pure operator directory, grants, and `off`/`shadow`
   operation. Prove zero fact writes and deterministic output digests.
3. **FactCard and version-vector reads.** Supply minimal cards for the flood
   vertical and graph back-check. Prove expiry, unavailable owners, privacy
   denial, graph degradation, and checkpoint-tail replay.
4. **Flood B0 advisory.** Build aggregate/shard food, route, storage, shelter,
   risk, and fidelity candidates. Prove no per-person B0 allocation or hidden
   population truth.
5. **Existing-path adoption.** Permit only existing propulsion subjects to
   create existing intents/proposals; prove one successful aggregate receipt
   and one stale/capacity hard rejection.
6. **Read projection and exact cache.** Add expiring `ModelProjection`,
   redacted audit receipts, static skeleton cache, and exact-vector result
   cache. Prove no private plaintext or NPC mirror is retained.
7. **Proven extension.** Add fragment invalidation only after evidence, then
   add migration, organization, market, and war-trade templates only where
   their owner capabilities have separate admission.

Cross-phase verification must cover contract admission/rejection, privacy and
codebook receipts, budget exhaustion, closed taxonomy, graph back-check,
embodied evidence classification, B0 aggregate restrictions, LOD handoff,
candidate conflict reporting, stale-input hard rejection, all degradation
states, full/checkpoint-tail replay, owner receipt correlation, and Godot
presentation that never promotes prediction to truth.
