# Federated Gameplay Extension Platform Schema Decision Implementation Plan

Status: `historical design gate; superseded by verified INF-P schema/P1 implementation; no August completion implied`

Date: `2026-08-18`

This is the historical Phase 1 plan after the Federated Gameplay Extension
Platform contract was approved. It planned the schema decision and its evidence
only. It did not authorize editing `GameplayPatchManifest`, adding fields to
runtime models, changing the patch registry, freezing a package, calculating a
digest, or implementing compiler/catalog/verifier/reducer/runtime behavior at
that design stage. Later explicit INF-P authorization implemented the approved
existing manifest v2 and P1 read-only binding mechanics; this plan remains the
trace of that pre-implementation gate and does not grant a business row.

## Scope

The plan covers:

- compatibility with the existing `GameplayPatchManifest` admission path;
- logical extension field mapping and ownership;
- platform schema versioning and lossless migration;
- validation order and zero-write behavior;
- design-time verification fixtures and acceptance evidence;
- a separate approval gate before any schema implementation.

The plan excludes package content, package identity freeze, canonical digest
calculation for any package, INF row work, tests, Harness, and append/write
paths.

## Ordered Design Work

### 1. Compatibility decision

Document how an optional logical extension envelope is adapted into the
existing manifest without creating a second manifest or lifecycle. Establish
legacy behavior, active-set compatibility, dependency preservation, unknown
field retention, and fail-closed behavior for unsupported major versions.

Deliverable: compatibility matrix and adapter boundary decision.

### 2. Logical field decision

Review the proposed fields:

```text
platform_schema_version
package_identity
package_definitions[]
outcome_declarations[]
capability_binding_requests[]
dependency_and_conflict_refs[]
replay_reader_refs[]
verification_profile_refs[]
```

For each field, record package ownership, adapter-derived values, canonical
representation, required/optional status, namespace, and prohibited authority
meaning. Confirm that owner descriptors, event vectors, streams, privacy,
receipts, predicates, recipes, and compensation rules remain outside package
control.

Deliverable: field ownership and compatibility table.

### 3. Version and migration decision

Define separate `platform_schema_version`, `package_revision`, and
descriptor/recipe revisions. Specify major/minor compatibility, additive
minor rules, semantic-change rejection, legacy read-only adaptation, active
set upgrade, disable/revoke, rollback, and historical replay pin retention.

Deliverable: version matrix and lossless migration/non-migration record.

### 4. Validation and zero-write decision

Specify the validation sequence: parse, version, shape/namespace, dependency/
conflict, reference form, read-only binding handoff, and pre-append rejection.
Enumerate malformed, duplicate, digest-mismatch, unsupported-version,
dropped-field, ambiguous-binding, private/stale-evidence, and unsupported-reader
cases. Every failure must produce no event, receipt, outbox, marker, or partial
fragment.

Deliverable: validation ordering and zero-write decision table.

### 5. Verification plan

Design, but do not execute, evidence for legacy compatibility, extension shape,
version matrix, canonical field ordering, lossless migration, binding
isolation, zero-write rejection, historical reader readiness, and scope guard.
The eventual RED suite and Harness are later gates and remain prohibited in
this phase.

Deliverable: verification fixture inventory and acceptance checklist.

### 6. Separate implementation approval

Present the completed design package for explicit approval. Approval must
state whether the logical field map, compatibility policy, migration policy,
validation order, zero-write rules, and verification plan are accepted.

Only after that approval may a separate implementation plan authorize schema
edits. That later plan must retain all platform prohibitions and still cannot
freeze a package, calculate a digest, add a catalog row, or resume INF work.

## Stop Conditions

Stop at any unresolved field ownership, version compatibility, migration
preservation, canonical representation, privacy/authority boundary, or
zero-write rule. Do not fill gaps with defaults, caller values, implicit
policies, or a new registry/runtime.

## Required Errata Before Implementation Review

The prior plan stopped one review gate too early. Before a schema
implementation plan can be approved, the companion
[schema mapping and migration errata](../../../../specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-08-18-federated-gameplay-extension-platform-schema-mapping-and-migration-errata-design.md)
must be accepted. It must provide the exact mapping from logical extension
fields to manifest paths/types/owners, the integer outer-version and
major.minor inner-version matrix, byte-preserving v1 digest rules, every
array's ordering/set/duplicate/empty/digest contract, non-migration of legacy
`economic_outcomes`, lifecycle/replay pin locations, and concrete rollout
gates. This is documentation-only work; it does not authorize schema edits.

The [schema-closure addendum](../../../../specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-08-18-federated-gameplay-extension-platform-schema-closure-addendum.md)
was the final documentation review surface before planning implementation. It
is approved, including its declaration-digest derivation/normalized-output
boundary. A separate file-by-file schema-v2 implementation plan remains a
future independent artifact and still requires its own approval before any
runtime schema edit.

## Current Status

The platform design is `design approved and complete`. The companion schema
decision design, mapping errata, and closure addendum record approved design
evidence. Schema implementation approval is pending; no implementation action
is authorized. Package-content freeze/digest, row binding, and INF runtime are
also independent and unapproved.
