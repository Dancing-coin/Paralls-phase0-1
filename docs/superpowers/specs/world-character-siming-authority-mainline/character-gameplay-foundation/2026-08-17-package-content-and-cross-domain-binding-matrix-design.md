# Package Content And Cross-Domain Binding Matrix

Status: `design baseline; runtime implementation not authorized`

Date: `2026-08-17`

## Purpose

This document defines what an extensible gameplay package may declare and how
that content binds to Siming, character-agent mind models, ESM/physics, and
existing domain owners. It is a content and binding boundary, not a second
runtime, event store, owner registry, router, coordinator, or settlement
authority.

The foundation must not enumerate every future building, recipe, skill,
institution, social rule, or physical affordance. It must freeze the stable
package envelope, typed evidence references, capability binding rules,
revision/replay behavior, and owner authority boundary so future packages can
add content without adding an ungoverned truth writer.

## Governing Principle

```text
package content is extensible
package revisions are immutable
package rules produce proposals
evidence comes from existing owners
owner contracts produce world truth
```

A package may describe a possible outcome. The relevant existing owner must
validate committed evidence and append its own fixed event vector. A package is
not a source of committed inventory, ownership, account, character-mind,
physical, social, or world facts.

## Canonical Package Boundary

`GameplayPatchManifest` and `GameplayPatchRegistry` are the current executable
patch admission path. They provide immutable candidate installation,
trusted-author checks, content digests, dependency/schema checks, and active
patch-set revisions. New executable package declarations must attach to this
path.

`GameplayPackageManifest` in `shared_contracts.py` remains a
reference/domain package description until an explicit read-only adapter
contract is approved. It must not become a second executable package registry
or active revision system. New facility, recipe, outcome, or binding fields
must not be added independently to both models.

The record-level closure for this boundary is specified in
[Package Contract Closure And Manifest Adapter](2026-08-17-package-contract-closure-and-manifest-adapter-design.md).
That document does not add runtime behavior; it fixes the logical manifest
sections and proof/replay invariants that later row-specific contracts must
reference.

## Package Content Matrix

| Package section | Package may declare | Package may not decide |
| --- | --- | --- |
| identity/trust | id, version, revision, digest, author, trust policy, core compatibility | activation truth or owner authority |
| dependencies/conflicts | required dependencies and explicit conflict intent | load-order precedence or implicit replacement |
| definitions | facilities, items, recipes, services, technologies, skills, institutions, social concepts, physical parameters | that an instance exists or that a definition is committed world truth |
| eligibility | typed references to existing owner evidence and policy revisions | evidence truth, owner selection, or default qualification |
| rules/Rule IR | deterministic reads, conditions, proposals, explanations, bounded capability requests | direct append, state mutation, clock advancement, or hidden I/O |
| outcomes | content values bound to an approved fixed outcome family | owner, stream, event, privacy, receipt, replay, fragment, or compensation override |
| capabilities | requests for fixed catalog capabilities and call sites | capability grant, new handler, new owner, or generic writer |
| schemas | package definitions, proposals, diagnostics, or non-authoritative content events | new domain-authoritative event families without a separate owner contract |
| lifecycle/verification | migration refs, disable/rollback intent, replay readers, verification profiles | deletion of historical truth or replay bypass |

## Extensible Definitions And Outcomes

Future definitions use immutable, namespaced references and versioned schemas:

```text
PackageDefinition
  definition_ref
  definition_schema_ref
  source_package_revision
  content_digest
  typed_content
```

An outcome declaration follows the same boundary:

```text
PackageOutcomeDeclaration
  outcome_ref
  outcome_family_ref
  definition_refs[]
  eligibility_refs[]
  policy_revision
  source_package_revision
  content_digest
```

`outcome_family_ref` must resolve to a separately approved immutable
owner-capability contract. The declaration cannot contain `owner_ref`,
`stream_id`, `event_type`, `privacy_scope`, `receipt_reader_ref`,
`settlement_fragment`, `compensation_policy`, router, or coordinator fields.

For INF-1AG, the package-owned portion is conceptually:

```text
outcome_ref = facility:oven-to-kiln
outcome_family_ref = construction_facility_package_declared_transform@1
source_kind = oven
target_kind = kiln
eligibility_refs = [blueprint:kiln, capability:ceramic-firing]
policy_revision = building-policy:v3
```

This is illustrative content, not an admitted gameplay row. Construction still
fixes the facility stream, `facility_transformed@1` event, project privacy,
idempotency, append receipt, replay readers, and v1 terminal/no-compensation
semantics.

## Typed Evidence References

An `eligibility_ref` is not proof merely because a package contains a string.
Each allowed reference family must be tied to an existing owner and return a
typed, owner-derived proof containing:

```text
evidence_owner_ref
evidence_kind
event_or_projection_revision
evidence_event_id_or_digest
privacy_scope
source_package_or_policy_revision
```

The resolver surface is not a generic cross-domain registry. Each admitted
owner capability contract enumerates the evidence kinds it accepts and the
existing owner that supplies them. Unknown, ambiguous, stale, revoked,
private, forged, or scope-incompatible evidence is zero-write before
`GameplayEventStore.append_batch()`.

## Cross-Domain Binding Matrix

| Consumer/owner | Package supplies | Consumer reads | Consumer may produce | Package may not do |
| --- | --- | --- | --- | --- |
| Siming | concepts, causal meanings, constraints, explanation templates | scoped definitions and committed projections | high-level typed proposal/catalyst | write world, character, account, or physical truth |
| character mind | needs, roles, skills, affordances, social vocabulary, goal meanings | package definitions and actor-scoped projections | typed intent, plan, or proposal | grant skill, turn need state into economic fact, or settle action |
| ESM/physics | physical parameters, placement constraints, material/affordance definitions | package physical definitions and current world inputs | owner-scoped physical evidence/projection | declare contact, placement, collision, or environment truth directly |
| Construction | facility definitions, transform declarations, eligibility references | facility stream, source revisions, resolved evidence, ESM evidence when admitted | fixed Construction event batch and receipt | choose owner/event/privacy or write material/payment truth |
| Inventory/Ownership | item/right definitions and source-evidence references | custody/title projections and revisions | owner-local custody/title events | create item, title, account, or transfer truth in package code |
| Economy/Contract | fixed outcome content, service or price-policy declarations | source, account, and contract projections | fixed ledger/transaction/service event vector | create generic payment, market, treasury, or settlement authority |

The same definition may be read by several consumers, but each consumer uses
its own fixed contract and privacy scope. A shared definition is not a shared
truth store.

## Binding Request

A package-to-runtime binding is a request for an existing capability, not a
runtime registration:

```text
BindingRequest
  binding_ref
  contract_ref
  source_package_revision
  definition_refs[]
  typed_read_requirements[]
  proposal_effect_types[]
  verification_profile_refs[]
```

The immutable governed catalog resolves `contract_ref` only when that contract
already exists and is compatible with the package. The package cannot supply a
new owner, handler, event family, stream, receipt, or settlement fragment.

## Lifecycle And Replay

```text
candidate package
-> schema/digest/trust/dependency/conflict validation
-> active immutable patch-set revision
-> scoped package reads and typed proposals
-> existing owner validation and append_batch()
-> owner projection/outbox/replay
```

Package upgrade creates a new package and active-set revision. Disable does not
delete historical events or definitions required by historical replay. New
commands cannot use an inactive declaration; historical readers retain the
definition or return an auditable replay-readiness failure. Historical replay
replays committed events and never reruns a changed package rule to reinterpret
the past.

## Safety Rules

- Package definitions are immutable data, not executable authority code.
- Rule IR is deterministic, bounded, proposal-only, and side-effect free.
- Untrusted packages cannot execute backend scripts in the first closure.
- Package requests cannot grant themselves capabilities.
- Package-local schemas cannot become domain-authoritative events without a
  separate row-specific Owner-Admission Contract.
- Package conflicts are explicit; load order and last-write-wins are invalid.
- Package privacy declarations may narrow a fixed owner scope but cannot widen
  it or expose authority-only evidence.
- Unknown package content, definition, binding, evidence, revision, or policy
  is zero-write when an authoritative outcome is attempted.

## INF-1AG Consequence

INF-1AG uses this matrix as its package boundary. The package may provide the
literal facility source/target and eligibility references, while Construction
fixes owner, stream, event, privacy, idempotency, receipt, replay, and terminal
semantics. Before RED tests or runtime code, the following remain separate
design/approval obligations:

1. canonical facility declaration schema and declaration identity rule;
2. allowed eligibility reference families and owner-derived proof shape;
3. immutable catalog row for the fixed Construction capability family;
4. declaration-validated Construction projector/reducer behavior.

This document does not approve any facility pair, package schema change,
resolver, catalog entry, or runtime writer.

## Design-Closed Constraints

- [x] `GameplayPatchManifest` is the canonical executable model and the
      reference-manifest relationship is documented;
- [x] package definitions, outcome declarations, and binding requests have
      revision/digest-pinned logical record shapes;
- [x] Siming and character mind outputs remain proposals, while ESM produces
      physical evidence/projections only;
- [x] owner event/stream/privacy/receipt/replay/compensation rules are not
      package inputs;
- [x] inactive, unknown, stale, privacy-incompatible, or revision-conflicting
      authoritative inputs are specified as zero-write;
- [x] disable, upgrade, full replay, and checkpoint-tail replay retention are
      explicitly bounded;
- [x] no generic writer, resolver, router, registry, coordinator, or second
      runtime is admitted by this design.

## Remaining Approval And Implementation Gates

- [ ] approve concrete executable manifest field names and schemas;
- [ ] approve every `outcome_family_ref` as a fixed row-specific owner
      capability contract;
- [ ] implement each owner-specific eligibility-proof reader without adding a
      generic resolver;
- [ ] prove focused zero-write, privacy, revision, idempotency, receipt, full
      replay, and checkpoint-tail replay behavior for each admitted row;
- [ ] approve a read-only `GameplayPackageManifest` adapter, if one is needed;
- [ ] admit and implement INF-1AG's separate facility declaration, catalog,
      and Construction reducer gates.
