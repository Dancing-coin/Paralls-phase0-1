# Federated Gameplay Extension Platform Design

Status: `design approved; INF-P platform mechanics implemented and verified; package and row gates remain separate`

Date: `2026-08-18`

## Purpose

This document defines the platform boundary that lets an immutable gameplay
package declare content and typed outcome proposals while existing domain
owners retain all committed truth. It is a governing design for a future
platform schema and immutable admission boundary. It does not add manifest
fields, a catalog row, a verifier, a reducer, tests, Harness selectors, or a
write path.

The platform is federated:

```text
immutable package content
-> typed declaration and proposal
-> fixed admitted capability
-> existing owner evidence check
-> existing owner envelope/SettlementPlan/append_batch()
```

The package can describe a possible capability use. It cannot create a truth
owner, select an owner, or choose any append contract.

## Scope And Non-Goals

This is an independent platform-level design task. August INF A-D execution
is paused; no INF row, package freeze, digest calculation, catalog admission,
test, Harness, or runtime implementation is authorized by this document.

The future platform contract covers package identity, immutable revision and
digest, typed definitions, outcome declarations, binding requests, owner-
derived eligibility proofs, admission lifecycle, conflict selection, and
replay/disable/upgrade retention.

It does not provide a generic outcome resolver, transform engine, payment or
transfer API, treasury, market, router, coordinator, registry writer, generic
settlement authority, or second runtime/store/bus/clock/scheduler. The
`GovernedAuthorityContractCatalog` remains immutable and read-only. A package
cannot write to it.

## Terms And Authority Boundary

| Record | Meaning | Authority |
| --- | --- | --- |
| `GameplayPatchManifest` | Canonical immutable package envelope | Existing patch admission path, after platform approval |
| package definition | Namespaced content and constraints | Package content only; never world truth |
| outcome declaration | Typed request to use one approved capability family | Package proposal data; cannot select owner contract fields |
| binding request | Reference to an already admitted capability | Immutable catalog lookup; no registration |
| eligibility proof | Revision/privacy-pinned evidence derived from an owner | Named existing owner only |
| admitted capability | Fixed owner contract for one row/family | Approved owner contract and immutable catalog |
| committed outcome | Domain fact and event vector | Existing domain owner through the existing append spine |

The platform never treats package data, character needs, agent agreements,
Rule IR output, or dossier context as committed domain evidence. Those inputs
may produce a typed proposal only.

## Federated Extension Architecture

The platform is a control-plane contract layered over the existing federated
owners. It has four explicit planes:

```text
content plane
  immutable package definitions, declarations, schemas, dependency refs

admission plane
  canonicalization, trust/dependency checks, conflict selection,
  immutable active-set revision, package-to-capability binding

evidence plane
  typed predicates evaluated against owner-scoped committed projections/events,
  revision/privacy/subject fences, owner-derived proof provenance

execution plane
  existing owner operation descriptor -> GameplayCommandEnvelope /
  SettlementPlan -> GameplayEventStore.append_batch()
```

The package compiler belongs to the admission plane. It is a deterministic,
side-effect-free compiler from one immutable package revision to an admission
artifact. It may validate schemas, normalize canonical records, resolve
already-approved descriptors, and emit typed proposal constraints. It may not
read mutable world state, advance time, create an owner, write a catalog,
construct an event vector, issue a receipt, or call `append_batch()`.

An owner remains the sole authority for its domain facts. The platform can
compile a binding to an owner descriptor, but it cannot merge descriptors,
invent a cross-domain operation, or turn a package declaration into a new
truth owner. Multiple owners may consume the same package definition through
separate fixed descriptors and separate receipts; shared content is never a
shared truth store.

## Proposed Platform Records

The following logical records are proposed for a future approved platform
schema. They are not runtime types yet.

```text
GameplayExtensionPlatformEnvelope
  platform_schema_version
  package_identity
  definitions[]
  outcome_declarations[]
  binding_requests[]
  dependency_and_conflict_refs[]
  replay_reader_refs[]
  verification_profile_refs[]
  canonical_content_digest
```

```text
PackageIdentity
  package_id
  package_version
  package_revision
  manifest_schema_version
  author_or_signer_ref
  trust_policy_ref
  dependency_digest
  schema_digest
  canonical_content_digest
```

```text
PackageDefinition
  definition_ref
  definition_schema_ref
  source_package_revision
  typed_content
```

```text
PackageOutcomeDeclaration
  declaration_ref
  outcome_family_ref
  definition_refs[]
  eligibility_refs[]
  policy_revision_ref
  source_package_revision
  declaration_digest
```

```text
CapabilityBindingRequest
  binding_ref
  capability_ref
  source_package_revision
  declaration_ref
  typed_read_requirements[]
  proposal_effect_types[]
```

```text
OwnerEligibilityProof
  evidence_owner_ref
  evidence_kind
  evidence_revision_pin
  evidence_event_id_or_digest
  subject_bindings[]
  privacy_scope
  package_revision
  policy_revision
  proof_digest
```

The exact field names, schema version, and whether these records are embedded
or adapted into the existing `GameplayPatchManifest` require separate user
approval. This document intentionally does not change that manifest.

## Owner Operation Descriptor Contract

An owner operation descriptor is an immutable, owner-authored contract. It is
the only authority surface that a package declaration may bind to. The
descriptor fixes the operation family and every authority boundary; the
package contributes only the declared content slots explicitly marked as
package-fillable.

```text
OwnerOperationDescriptor
  descriptor_ref
  descriptor_revision
  owner_ref                         # fixed by owner contract
  operation_family_ref              # fixed by owner contract
  accepted_intent_schema_ref        # fixed input shape
  package_content_slots[]           # named, typed, bounded, package-fillable
  fixed_source_event_refs[]         # owner-selected source evidence
  fixed_target_rule_ref             # owner-selected target derivation
  fixed_event_family_refs[]         # owner-selected event vector
  fixed_stream_rule_ref             # owner-selected stream derivation
  fixed_privacy_scope               # owner-selected visibility
  fixed_revision_fence_ref          # owner-selected revision pins
  fixed_receipt_reader_ref          # append-derived receipt reader
  fixed_replay_reader_refs[]        # full and checkpoint-tail readers
  fixed_idempotency_rule_ref        # authority-derived key
  fixed_terminal_rule_ref
  fixed_compensation_rule_ref
  allowed_predicate_family_refs[]   # closed vocabulary only
  allowed_recipe_type_refs[]        # precompiled recipes only
  descriptor_digest
```

`package_content_slots` may contain content identifiers, bounded values,
definition references, policy references, or other fields explicitly admitted
by the descriptor. A package cannot fill an owner field, source event, target
derivation, stream, event family, privacy scope, revision fence, receipt,
replay reader, idempotency rule, terminal/compensation rule, predicate
implementation, or recipe fragment. A caller cannot fill them either.

Descriptor revisions are immutable. Any change to a fixed boundary, allowed
slot, predicate family, or recipe type creates a new descriptor revision and
digest; historical events retain the revision used at admission.

## Restricted Predicate Vocabulary

Predicates are a closed, typed vocabulary selected by the owner descriptor.
The platform may combine approved predicates, but it never executes arbitrary
package code or arbitrary owner lookup.

```text
allowed predicate families (illustrative platform vocabulary)
  exact_event_kind_at_revision
  projection_subject_matches
  projection_value_equals
  projection_value_in_set
  source_revision_is_current
  dependency_revision_is_active
  privacy_scope_allows
  idempotency_key_is_new
  package_slot_satisfies_bound
  recipe_input_is_complete
```

Every predicate reference resolves to an owner-approved predicate family and
an immutable evidence requirement. Predicates may combine with typed `all`,
`any`, and `not` over already-approved operands, subject to a fixed maximum
depth and no short-cut that suppresses required evidence reads. They may not
contain arbitrary code, dynamic function names, network/I/O calls, clocks,
randomness, owner discovery, stream discovery, event-family discovery, or
caller-supplied proof.

Evidence is valid only when it is returned by the named owner with the exact
event/projection kind, subject binding, privacy scope, revision fence, and
proof digest required by the descriptor. A caller-provided event ID, digest,
account, facility, owner reference, or boolean cannot satisfy a predicate.
Unknown, private, stale, ambiguous, or unavailable evidence is a typed
non-success result and causes zero-write.

## Deterministic Selection Grammar

Selection is a pure matching relation over a typed intent and immutable
declarations. It is not priority routing, load-order resolution, or caller
choice.

```text
TypedIntent
  intent_family
  package_revision_pin?              # optional only when descriptor allows it
  content_slot_values
  subject_refs
  requested_effect_type

match(intent, declaration, descriptor) iff
  intent_family == descriptor.accepted_intent_schema
  and declaration.package_revision == active package revision
  and declaration.outcome_family == descriptor.operation_family
  and all required content slots are present and typed
  and all descriptor predicates evaluate to satisfied
  and all subject/privacy/revision fences match
```

The result set is evaluated as a set, then sorted only by canonical identity
for audit output. Selection succeeds only when the set contains exactly one
descriptor/declaration/target/policy tuple. Zero matches, multiple matches,
conflicting declarations, or a target/policy value not derived by the
descriptor are zero-write. No priority, load order, default target, fallback
owner, caller-selected declaration, or tie-breaker is permitted.

The selected tuple is pinned into the admission artifact and idempotency key.
Any later change to package revision, descriptor revision, source evidence,
target derivation, or policy revision produces a changed intent and is not an
exact duplicate.

## Cross-Domain Recipe Boundary

Cross-domain effects may use only a precompiled, owner-bound recipe type that
was separately approved before package binding. A recipe is a fixed
composition contract, not a caller- or package-built event vector.

```text
OwnerBoundRecipeType
  recipe_type_ref
  recipe_revision
  participating_owner_refs[]
  fixed_operation_descriptor_refs[]
  fixed_input/output bindings
  fixed privacy and revision joins
  fixed receipt boundaries       # one receipt per owner append unless contract says otherwise
  fixed compensation semantics
  recipe_digest
```

The package may reference a recipe type and fill only its declared content
slots. It may not add an owner, reorder operations, choose streams/events,
merge receipts, supply fragments, or make an arbitrary multi-owner event
vector. If the recipe is unavailable, ambiguous, privacy-incompatible, or
revision-incompatible, the request is zero-write. A package definition that
mentions multiple domains is still content, not a cross-domain authority.

## Canonicalization And Digest Rules (Proposed, Pending Approval)

The platform should reuse the existing Patch canonical JSON convention:

- UTF-8 JSON with `ensure_ascii=false`;
- sorted object keys and compact separators;
- `sha256:` prefix;
- digest fields excluded while their containing digest is derived;
- set-like arrays sorted and deduplicated before hashing;
- duplicate semantic entries rejected rather than silently normalized;
- references represented in their canonical string form;
- no caller-supplied digest is trusted as evidence.

The platform must define two distinct derived values:

1. `declaration_digest`, derived from one fully validated declaration payload;
2. `canonical_content_digest`, derived from the complete immutable package
   manifest after all definitions, declarations, dependencies, schemas and
   replay references are present.

Neither value is available for `package:industrial-facilities:v1` today. The
user explicitly deferred package freeze and digest confirmation because the
platform schema is not yet approved. A provisional or hand-authored digest
must not unblock INF-1AG.

## Immutable Admission Boundary

The future boundary is a control-plane lifecycle, not a runtime owner:

```text
candidate manifest
  -> schema/trust/dependency/digest validation
  -> immutable candidate record
  -> explicit active patch-set revision
  -> scoped package reads and typed proposals
  -> immutable catalog capability lookup
  -> owner-bound evidence validation
  -> existing owner append_batch()
```

Candidate and active records are immutable. Disable creates lifecycle evidence
that prevents new use; it does not rewrite or delete the package. Upgrade
publishes a new package revision and active-set revision. In-flight commands
retain the package revision selected at admission time.

The catalog only admits capabilities whose complete owner contract is already
approved. A package declaration cannot add a catalog row, alter a row, or
choose a fragment. A caller cannot select a package revision, owner, stream,
event family, revision rule, privacy scope, receipt reader, compensation rule,
target, or settlement fragment.

The compiler output is an immutable admission artifact, not an executable
writer:

```text
AdmissionArtifact
  package_revision
  package_content_digest
  declaration_digest
  descriptor_ref_and_revision
  normalized_content_slot_values
  selected_recipe_type_refs[]
  predicate_refs_and_required_proof_digests[]
  active_set_revision
  dependency_and_conflict_decision
  artifact_digest
```

The artifact can be cached or replayed as control-plane evidence. It cannot
become a second truth store, perform owner lookup, construct an event vector,
or bypass the descriptor's owner-bound operation.

## Declaration Selection And Conflict Rules

Selection must be deterministic and fail closed:

- an inactive, unknown, revoked, or dependency-incompatible package is
  rejected before append;
- an unknown outcome family, capability, definition, policy, or eligibility
  reference is zero-write;
- duplicate declaration identities are rejected;
- two active declarations that could satisfy the same fixed capability with
  different package, policy, target, or digest pins are ambiguous and
  rejected;
- caller-supplied target, owner, stream, event, or policy values are ignored
  for authority selection and rejected if they conflict;
- package upgrade does not reinterpret a previously admitted command;
- a digest mismatch between the active package and a declaration/proof is
  zero-write.

The platform does not invent defaults for missing kinds, eligibility, policy,
privacy, revision, or terminal semantics.

The matching grammar is therefore a closed function over typed intent,
declaration, descriptor, and owner-derived evidence. It never consults
priority, installation order, or caller preference. A set cardinality other
than one is a zero-write result.

## Owner-Bound Eligibility And Privacy

Each capability family names its existing owner, accepted evidence kinds,
revision fence, subject bindings, privacy scope, idempotency rule, receipt
reader, replay reader, and terminal/compensation semantics. The package may
only reference that contract.

An owner derives `OwnerEligibilityProof` from committed event or projection
evidence. A copied event ID, caller assertion, package string, dossier field,
or default account/facility/project is not proof. Facility/project, actor,
account, region, and other subject bindings must be explicit in the approved
row contract.

Unknown, missing, ambiguous, stale, private, cross-scope, forged, or
revision-conflicting evidence is zero-write before `append_batch()`.

## Outcome And Replay Semantics

After admission, the named existing owner constructs its fixed
`GameplayCommandEnvelope` and composition-only `SettlementPlan`, then calls
`GameplayEventStore.append_batch()`. The platform does not assemble event
vectors or receipts.

The append-derived receipt, scoped outbox, projection, full replay, and
checkpoint-tail replay are owned by the admitted owner contract. Replay uses
the committed event's pinned package/revision and retained reader references;
it never reruns changed package rules to reinterpret historical truth. Missing
historical readers fail closed with an auditable replay-readiness error.

Terminal, reversal, retry, and compensation semantics remain row-specific.
The platform cannot add a generic compensation or reopen behavior. A package
disable or upgrade never deletes committed owner events.

## Zero-Write Contract

Before any owner append, the platform/admitted capability must reject:

- unknown or inactive package/schema/revision;
- content or declaration digest mismatch;
- unknown, duplicate, conflicting, or ambiguous declarations;
- unknown outcome/capability/policy/eligibility reference;
- missing, private, stale, forged, or cross-subject owner evidence;
- caller-selected owner, stream, event, privacy, receipt, revision,
  compensation, target, or fragment;
- package upgrade/disable conflicts with the pinned command revision;
- duplicate intent or changed duplicate idempotency key;
- unavailable replay reader or incompatible dependency.

No rejection path may emit a marker-only event, receipt, outbox record, or
partial fragment.

## Migration And Non-Migration Rules

Migration is limited to lossless control-plane representation changes:

- an older package envelope may be read through an approved deterministic,
  read-only adapter when every semantic field, revision pin, dependency,
  descriptor binding, and digest input is preserved;
- an approved schema migration creates a new package revision and canonical
  digest while the old revision remains addressable for historical replay;
- an owner descriptor migration creates a new descriptor revision only when
  compatibility and historical reader obligations are recorded;
- active-set upgrades are forward admissions, never in-place edits;
- disable, revoke, or rollback affects future admissibility only and never
  deletes committed owner events or rewrites historical proofs.

The following migrations are prohibited:

- changing owner, stream, event family, privacy, receipt, replay reader,
  idempotency, terminal, or compensation semantics in place;
- converting package content or a predicate result into committed truth;
- replaying historical events with a newer package rule or descriptor to
  obtain a different outcome;
- silently defaulting missing fields, changing subject bindings, or widening
  privacy during adaptation;
- migrating a declaration into a generic writer, router, registry,
  coordinator, settlement authority, or second runtime;
- using a package upgrade to authorize a previously unadmitted capability.

If lossless preservation cannot be proven, the result is a new incompatible
revision that remains inactive until separately admitted. It is not an
automatic migration.

## Explicit Separation From Generic Facilities And Outcomes

For INF-1AG, the future platform may carry the declaration for
`oven -> kiln`, but only the separately approved Construction owner contract
can fix `facility_transformed@1`, the facility stream, project privacy,
source/revision fences, receipt, replay, and terminal/no-compensation rule.
The platform does not become a generic `facility_kind -> facility_kind`
transform engine. The same boundary applies to INF-2AC and every future
package outcome: package extensibility does not make a generic payment,
transfer, treasury, market, or settlement API.

## Approval Gates

The following approvals are separate and ordered:

1. approve the platform record vocabulary and schema-version boundary;
2. approve canonicalization and digest derivation rules;
3. approve immutable candidate/active admission and disable/upgrade lifecycle;
4. separately approve the read-only package-to-capability binding boundary,
   including descriptor resolution, restricted predicates, deterministic
   selection, and precompiled recipe references;
5. approve each row-specific owner contract and catalog admission;
6. freeze one complete immutable package and derive its canonical digest;
7. only then write RED tests, an independent Harness, and the narrow owner
   vertical through the existing envelope/SettlementPlan/append spine.

Approval of this design alone does not approve any platform schema, package
manifest field, catalog row, verifier, reducer, test, Harness, or runtime.

## Current Independent Task Disposition

The August INF A-D execution lane is paused. INF row selection, package
freezing, canonical digest calculation, catalog admission, RED tests, Harness,
and runtime implementation are outside this independent platform task.

References to `INF-1AG`, `oven -> kiln`, or other rows are non-operative
examples of the boundary only. They do not authorize package freeze, digest
derivation, owner implementation, or any write path. The platform design
has completed its logical schema, compatibility, migration, verification, and
schema-closure design. It is explicitly `design approved and complete`.
Schema implementation, package content freeze/digest, row binding, and INF
runtime remain separate, unapproved tasks.
