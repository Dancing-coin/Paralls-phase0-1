# INF Federated Owner Capability Admission Design

Status: `approved architecture decision; no owner row is admitted by this document alone`

## Decision

The INF runtime adopts federated domain ownership with typed, versioned
capabilities. The former no-new-owner rule is a governance gate, not a
permanent ban: a new domain truth owner is permitted only after an approved
Owner-Admission Contract establishes one bounded business truth and its full
event, privacy, replay, and compensation semantics.

This decision does not approve a generic settlement authority, a generic
writer, a caller-selected event or stream, or any currently blocked INF row.
It changes the admission process for a future row; the row remains zero-write
until its own contract, plan, tests, Harness profile, and audit evidence exist.

## Goal

An agent may propose a typed game intent and use an already admitted
capability. It must never obtain a general authority to select a truth owner,
stream, event family, revision, privacy scope, receipt, or compensation rule.

Existing domain authorities remain the only writers of their own facts. A
cross-domain outcome is a named interaction recipe whose participating owners
independently authorize their fragments before the existing append spine is
used:

```text
typed agent intent
-> admitted capability operation
-> existing owner validation and OwnerAuthorizedFragment values
-> GameplayCommandEnvelope / SettlementPlan
-> GameplayEventStore.append_batch()
-> outbox -> scoped projection -> replay
```

`SettlementPlan` is a composition-only planner. It derives one receipt from
the one append result but cannot choose an operation, create a business policy,
construct an arbitrary fragment, or append a batch itself.

## Terms

| Term | Meaning |
| --- | --- |
| `truth owner` | The one authority responsible for one named business fact and its event family. |
| `capability` | A versioned, source-controlled, typed operation with fixed participating owners and evidence requirements. |
| `interaction recipe` | The fixed mapping from an admitted capability to its owner-local fragments and append boundary. |
| `admission` | Pre-append proof that a capability, source, revision, privacy scope, and owner operation are permitted. |
| `agent intent` | A typed request of a game goal. It is not a direct persistence command. |

## Gameplay-Pack And Mod Content Boundary

The core runtime is not expected to enumerate every future game action,
commodity, service, institution, or technology. A trusted gameplay package or
mod may provide those content definitions through the existing immutable
`GameplayPatchManifest` / active patch revision. This is content admission,
not a new truth owner, registry, router, or settlement runtime.

The allowed direction for an otherwise unknown economic/social outcome is:

```text
package/mod definition
-> world/domain eligibility read models
-> character dossier / agent typed intent
-> negotiated proposal
-> existing owner validation
-> Economy or other admitted owner settlement
```

The package/mod may declare the typed item or service, allowed currencies,
technology/social/institution/resource prerequisites, fixed or bounded price
policy, consent rules, and policy revision. It may not write accounts,
ownership, debt, service completion, transaction records, or the event store.
Character occupation, capability, need, relationship, and personality fields
explain why an actor may propose an action; they never establish that the
action happened or that a payment is owed.

When an INF row is blocked because the concrete gameplay is not known, the
repair path is deterministic:

1. Name one `economic_outcome_id` or other single business outcome.
2. State which active package/mod definition makes the outcome possible.
3. Identify the existing source owner and committed evidence kind, or submit a
   separate row-specific Owner-Admission Contract for the missing fact.
4. Pin owner operation, command, stream/event family, revisions, privacy,
   idempotency, receipt, full/checkpoint-tail replay, and terminal/
   compensation semantics.
5. Obtain explicit approval for that row, then write the plan, RED tests,
   independent Harness profile, and runtime vertical in that order.

Until step 5 is complete, unknown content remains a proposal/design gap, not
permission for arbitrary payment, caller-selected price/currency/owner, or a
generic settlement path. Implausible proposals (for example, an item whose
technology, production, institution, or inventory prerequisites are absent)
must reject before `append_batch()` with zero writes.

## Need-Driven Baseline Outcome Families

Character needs are a useful stable starting point for discovering gameplay
outcomes, but a need is motivation rather than a transaction fact. A character
may satisfy the same need by self-production, consuming an owned resource,
receiving aid, exchanging goods, performing service, borrowing, or purchasing.
The canonical chain is:

```text
need state / dossier context
-> typed resolution intent
-> one baseline outcome family
-> package/world eligibility and owner evidence
-> negotiated proposal
-> owner settlement
```

The initial outcome vocabulary is intentionally small and content-neutral:

| Outcome family | Typical need relation | Ownership boundary | Maturity |
| --- | --- | --- | --- |
| `resource_consumption` | hunger, thirst, treatment | Resource/Inventory owner | foundation primitive |
| `fixed_offer_purchase` | acquiring food, tools, services | existing Offer/Ownership/Economy owners | existing bounded primitive |
| `gift_transfer` | care, belonging, reciprocity | Ownership/Economy owners | existing bounded primitive |
| `debt_issue` / `debt_payment` | delayed safety or consumption | Debt/Economy owners | existing bounded primitive |
| `service_contract` / `service_completion_compensation` | labor, care, protection, training | source service owner plus Economy | bounded rows only |
| `barter_exchange` | needs without compatible currency | package-declared item/service owners plus Economy | separate admission required |
| `rent_or_lease` | shelter, tools, workspace | Ownership/contract owner plus Economy | separate admission required |
| `tax_or_fine` | civic obligation or sanction | Government/policy owner plus Economy | tax is narrow; fine is not admitted |

This vocabulary does not authorize every family. Each implemented family still
requires its own owner contract and evidence. Packages/mods provide concrete
items, services, world technology/social/institution/resource prerequisites,
currency choices, consent rules, and fixed or bounded price policies; they do
not create a generic payment owner. A needs-driven intent without a declared
package definition, valid world eligibility, committed source evidence, or a
complete owner contract remains a proposal and must be rejected before append.

## Authority Model

### Domain owners

Each domain authority owns only its stated facts. It validates its own source
evidence, grant, revision, privacy, idempotency, and business invariants before
constructing its fragment. No composition layer may replace that validation.

A new truth owner is allowed only when the business fact has no legitimate
existing owner. It must not be introduced merely to bypass an incomplete
contract in another domain.

### Capabilities and catalog visibility

`GovernedAuthorityContractCatalog` remains immutable, source-controlled, and
read-only. It is not a caller registration API, a generic router, or a
runtime-writable registry.

An agent-facing planner may receive a privacy-filtered description of admitted
capabilities, but it does not receive a catalog entry as an executable write
token. A typed intent is bound by a fixed, owner-controlled operation surface.
The receiving owner resolves its own fixed `contract_ref` immediately before
fragment construction. Unknown, version-mismatched, unauthorized, or
scope-ineligible intents reject before `append_batch()`.

Every capability entry names at least:

1. `capability_ref` and immutable version;
2. typed intent schema and caller eligibility;
3. existing or newly admitted sole owner for every fact;
4. fixed source evidence and permitted target stream/event family;
5. projection and outbox privacy classification;
6. source and target revision rules;
7. canonical idempotency-key shape and duplicate behavior;
8. append-derived receipt source and scoped replay reader; and
9. retry, terminal, and compensation behavior, or an explicit statement that
   none is admitted.

### Cross-domain composition

A cross-domain capability names its participating owners and fixed fragment
types in its source-controlled recipe. Each owner retains ownership of its
own event vector. A designated existing assembly surface may assemble only the
named fragments for that one operation; it acquires no truth ownership.

Atomic operations use one existing `GameplayEventStore.append_batch()` call.
Long-running operations require explicit owner-local lifecycle events and
explicit compensation contracts. This design does not introduce a generic saga
runtime, coordinator, scheduler, or retry worker.

## Owner-Admission Contract

Before implementation, a proposed new owner must have a row-specific design
that answers all of the following without placeholders:

1. What single business fact does this authority own, and which neighboring
   facts does it expressly not own?
2. Why cannot an existing authority own that fact?
3. What canonical command/intent and committed source evidence admit a write?
4. What exact stream, event family, revision vector, and concurrency rule are
   used?
5. What scopes may read the outbox and projections?
6. What idempotency key, duplicate result, stale result, and zero-write
   rejection behavior apply?
7. What receipt is derived from which append result?
8. How do full replay and checkpoint-tail replay reconstruct the same scoped
   result?
9. Which terminal, retry, reversal, and compensation events are valid?
10. Which existing owners or capability recipes consume the fact, and which do
    not gain eligibility from this approval?

The contract must also state the migration boundary. Existing events and
streams are not silently reinterpreted as facts of the new owner.

## Non-Negotiable Prohibitions

The following remain prohibited:

- a generic writer or caller-supplied `OwnerAuthorizedFragment`;
- caller selection of owner, stream, event family, projection scope, or
  compensation rule;
- a generic router, coordinator, or registry that creates business authority;
- a second runtime, event store, bus, clock, scheduler, or branch store; and
- using a branch preview, LLM proposal, client position, dossier fact, or
  opaque external input as a substitute for committed owner evidence.

## Migration of Existing INF Rows

Existing verified finite rows remain valid and need no event-store migration.
They become versioned capabilities only by documenting their existing owner,
operation, privacy, receipt, replay, and rejection boundary. No existing row
becomes generic because it gains a capability reference.

| Area | Existing capability-shaped evidence | Required separate admission |
| --- | --- | --- |
| INF-1 | Survival state rows, Construction maintenance and the bounded facility-repair/compensation row | Every additional Construction transform, repair variant, or payment outcome needs its own owner contract. |
| INF-2 | Fixed Economy, Debt, Government, payroll, and commerce settlement rows | Tax payment needs a canonical treasury/account-holder and tax-payment contract; arbitrary policy/payment remains unadmitted. |
| INF-3 | Fixed Construction, Organization, Economy, and Survival weather consumers | Every unlisted target-owner edge needs its own source/target contract. |
| INF-4 | Fixed Government and Organization promotion rows plus isolated replay | Further promotion requires a branch-domain or population/social owner contract; no generic promotion follows. |

## Required Evidence

Each new capability or owner admission must add focused RED-to-green tests and
an independent Harness profile that proves, where applicable:

- authorized success;
- unknown or unauthorized capability zero-write rejection;
- source and target revision conflict rejection;
- privacy/outbox/projection scope;
- idempotent duplicate and changed-duplicate behavior;
- append-derived receipt;
- full replay; and
- checkpoint-tail replay.

If retry or compensation is admitted, success and failure paths must prove its
event identity, receipt boundary, idempotency, privacy, and replay behavior.

## Adoption and Completion Rule

Before any implementation relies on this decision, update the INF remaining
scope dependency design, the completion audit, the applicable INF plan, and
the continuation checkpoint to distinguish:

- `approved architecture mechanism`;
- `approved owner row`;
- `implemented narrow vertical`;
- `owner-contract blocked`; and
- `unimplemented`.

No August A-D area is complete merely because this admission mechanism is
approved. Completion still requires every required row to be independently
implemented and verified, or to have a formal, auditable blocker disposition.
