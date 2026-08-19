# Package Contract Closure And Manifest Adapter Design

Status: `design-only; runtime implementation not authorized`

Date: `2026-08-17`

## Purpose

The package matrix establishes the boundary for extensible gameplay content.
This document closes the remaining contract details needed to apply that
boundary consistently to the executable patch path. It defines how package
definitions, outcome declarations, binding requests, and owner-derived
eligibility proofs are represented inside an immutable
`GameplayPatchManifest` revision.

The goal is an extensible content envelope, not a complete catalog of future
玩法. A package may add new facilities, items, services, social concepts,
physical parameters, and proposal rules when it publishes a new immutable
revision. The backend still requires an existing owner capability contract to
turn any proposal into world truth.

## Governing Rules

```text
fixed package envelope
-> immutable package revision
-> scoped content and proposal reads
-> owner-bound evidence validation
-> existing owner settlement
```

The following remain prohibited:

- a runtime-writable package registry;
- a generic cross-domain resolver, router, writer, coordinator, or settlement
  authority;
- package-selected owner, stream, event family, privacy, receipt, replay,
  compensation, account, or settlement fragment;
- a second package runtime, event store, bus, clock, or scheduler;
- package code directly mutating world, character, inventory, ownership,
  economy, contract, or physical truth.

## Canonical Executable Model

`GameplayPatchManifest` is the only executable package admission model. The
following logical sections are manifest data, not independent runtime stores:

```text
GameplayPatchManifest
  package_identity
  package_definitions[]
  outcome_declarations[]
  binding_requests[]
  rules[]
  requested_capabilities[]
  schemas[]
  replay_reader_refs[]
  verification_profiles[]
```

The existing `GameplayPatchRegistry` remains the control-plane boundary for
candidate installation and active patch-set revision. It stores immutable
candidate manifests and committed lifecycle evidence; it does not interpret
package content as an owner.

`GameplayPackageManifest` in `shared_contracts.py` is a reference/legacy
description until a separate read-only adapter is approved. It must not gain
its own active revision, installation lifecycle, or registry. A future adapter
may translate it into the canonical manifest representation only if the
translation preserves the exact package revision, content digest, schemas,
dependencies, and declared binding requests.

## Package Identity And Revision

Every candidate must provide:

```text
PackageIdentity
  package_id
  package_version
  package_revision_id
  manifest_schema_version
  author_id
  trust_policy_ref
  content_digest
  dependency_digest
  schema_digest
```

`package_revision_id` and `content_digest` identify the complete immutable
content set, including package-local schemas, definitions, rules, outcome
declarations, binding requests, and verification metadata. Any byte or
semantic change creates a new revision. An active revision is never edited in
place.

Package-local schemas are the extensibility mechanism. They may add typed
content fields without changing the foundation envelope, but the schema
identity and digest must be known during candidate validation. An unknown,
ambiguous, or incompatible schema keeps the candidate inactive and cannot
reach settlement.

All derived declaration and proof digests use the existing Patch canonical
digest convention: JSON with `ensure_ascii=false`, sorted keys, compact
separators, UTF-8 encoding, and a `sha256:` prefix. A digest is derived from a
fully validated record with its own digest field excluded; it is not a caller
or package override. Arrays whose semantics are set-like must be sorted and
deduplicated before hashing, while duplicate entries are rejected at schema
validation.

## Canonical Content Records

### PackageDefinition

```text
PackageDefinition
  definition_ref                 # package namespace + local identifier
  definition_schema_ref          # immutable schema identity
  definition_schema_version
  source_package_revision
  content_digest
  typed_content
```

`definition_ref` is namespaced by `source_package_revision`; the same local
name in another package or revision is a different definition. Definitions
describe possible content and constraints. They do not assert that an item,
facility, service, skill, institution, relationship, or physical object
exists in the world.

### PackageOutcomeDeclaration

```text
PackageOutcomeDeclaration
  outcome_ref
  outcome_family_ref
  definition_refs[]
  eligibility_refs[]
  policy_revision_ref
  source_package_revision
  content_digest
```

`outcome_family_ref` must resolve to a separately approved immutable
owner-capability contract. `policy_revision_ref` is a reference to the
contract-approved policy input; it is not a package-created pricing,
compensation, or settlement policy.

An outcome declaration must not contain or override `owner_ref`, stream,
authoritative event family, privacy scope, receipt reader, replay contract,
compensation semantics, account selection, or settlement fragments. Those
values come from the fixed owner contract identified by
`outcome_family_ref`.

### BindingRequest

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

A binding request asks to use an already admitted capability. It is not a
registration and does not grant a capability. The governed contract catalog
must resolve `contract_ref` to one immutable owner contract and verify that
the requested definitions, reads, proposal types, privacy scope, and package
revision are compatible.

There is no generic fallback resolution. An unresolved, ambiguous, stale,
revoked, or privacy-incompatible binding is rejected before any append.

## Owner-Derived Eligibility Proof

An `eligibility_ref` is only a content-side reference. The owner capability
must resolve it to a typed proof using its own committed projection or event
evidence:

```text
EligibilityProof
  evidence_owner_ref
  evidence_kind
  evidence_revision
  evidence_event_id_or_digest
  privacy_scope
  source_policy_revision
  source_package_revision
  proof_digest
```

The proof is valid only when:

1. `evidence_owner_ref` is the owner named by the admitted contract;
2. `evidence_kind` is one of that contract's accepted evidence kinds;
3. `evidence_revision` matches the command's expected revision fence;
4. the caller's scope is authorized for the proof's `privacy_scope`;
5. `proof_digest` is derived from committed evidence, not caller input;
6. the package and policy revisions are still active and compatible.

Unknown, forged, stale, private, duplicate, or ambiguous proofs are
zero-write failures. A package cannot manufacture a proof by copying an
event ID or by declaring a default eligibility value.

## Cross-Domain Binding Semantics

| Producer/consumer | Package contribution | Authority boundary |
|---|---|---|
| Siming | concepts, causal labels, explanation templates | produces scoped catalysts/proposals; never commits facts |
| character mind | needs, roles, skills, affordance meanings | produces typed intent/proposal; need state never creates economy truth |
| ESM/physics | material, placement, contact, and environment definitions | produces owner-scoped physical evidence/projection |
| Construction | facility/transform declarations and accepted eligibility refs | validates evidence and emits fixed Construction events |
| Inventory/Ownership | item/right definitions and source evidence refs | commits item custody and title facts |
| Economy/Contract | admitted exchange/service content and bounded policy refs | commits fixed ledger/transaction/service event vectors |

The same definition may be read by several consumers, but every consumer uses
its own owner contract and privacy scope. Shared content is not shared truth.

## Lifecycle And Replay

```text
candidate install
-> schema/digest/trust/dependency/conflict validation
-> active immutable patch-set revision
-> package reads and typed proposals
-> owner evidence validation
-> owner append_batch()
-> owner projection/outbox/replay
```

Disable prevents new commands from using the inactive package revision. It
does not delete definitions or historical events required to read committed
facts. Upgrade publishes a new package revision and pins each in-flight
command to the revision selected at admission time.

Historical replay consumes committed owner events and the retained schema,
definition, and reader references for the event's source package revision. It
never reruns a changed Rule IR document to reinterpret a past event. If the
reader or definition needed for a historical event is unavailable, replay
fails closed with an auditable replay-readiness error; it does not silently
substitute a newer package revision.

Checkpoint-tail replay uses the same retained package revision and owner
revision fences as full replay. A checkpoint is a cache and cannot become a
second package truth source.

## Approval Gates

This document is design-only. Before any package schema, adapter, resolver,
catalog row, RED test, Harness profile, or runtime behavior is added, the
following gates are required:

1. approve the canonical manifest section names and revision/digest rules;
2. approve each row-specific `outcome_family_ref` and its owner contract;
3. approve the accepted eligibility reference families and proof shape for
   that row;
4. approve owner-specific replay, privacy, receipt, idempotency, and
   compensation semantics;
5. write focused RED tests, then an independent Harness profile, then the
   narrow vertical through the existing envelope/SettlementPlan/
   `append_batch()` spine.

For INF-1AG, the remaining blockers are still row-specific: a canonical
facility declaration schema, declaration identity/selection, the admitted
Construction capability catalog row, and the Construction projector/reducer
that validates owner-derived proofs. This design does not approve a facility
pair and does not un-block INF-1AG by itself.

## Review Checklist

- [ ] canonical executable package path remains `GameplayPatchManifest`;
- [ ] `GameplayPackageManifest` has no independent registry or lifecycle;
- [ ] definitions, outcomes, and bindings carry package revision and digest;
- [ ] outcome declarations cannot choose owner/event/privacy/receipt/replay;
- [ ] eligibility proofs are owner-derived and revision-pinned;
- [ ] Siming, character mind, and ESM outputs remain proposal/evidence inputs;
- [ ] disable, upgrade, full replay, and checkpoint-tail replay are explicit;
- [ ] unknown, stale, private, and duplicate package inputs are zero-write;
- [ ] no generic writer, resolver, router, registry, coordinator, or runtime
      was introduced.
