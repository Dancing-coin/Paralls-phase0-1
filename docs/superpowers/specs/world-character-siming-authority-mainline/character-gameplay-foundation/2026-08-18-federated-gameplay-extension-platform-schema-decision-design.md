# Federated Gameplay Extension Platform Schema Decision Design

Status: `design approved and complete; schema implementation approval pending`

Date: `2026-08-18`

This document is the next design phase after approval of the Federated
Gameplay Extension Platform semantics. It defines a compatible logical schema
decision, field ownership, version migration, and verification plan. It does
not edit `GameplayPatchManifest`, add a manifest field, change a registry,
create a compiler, or add tests/Harness/runtime behavior.

## Governing Constraints

- The existing `GameplayPatchManifest` and patch admission path remain the
  only future executable package boundary.
- No second manifest, package registry, runtime, store, bus, clock, or
  scheduler is introduced.
- `GovernedAuthorityContractCatalog` remains immutable/read-only.
- Schema content is not world truth and cannot select owner coordinates.
- Package freeze and canonical package digest calculation remain out of scope.
- August INF A-D and all row-specific implementation remain paused.

## Compatibility Decision

The preferred design is a logical extension envelope adapted into the existing
`GameplayPatchManifest`. It is not a parallel manifest type or an independent
installation lifecycle.

```text
existing GameplayPatchManifest
  -> optional logical extension envelope
  -> existing patch candidate/active-set admission
  -> read-only package binding artifact
```

Legacy manifests without the extension envelope remain valid and retain their
current semantics. An extension-aware reader must preserve all legacy fields,
dependencies, active-set behavior, and digest inputs. A package that cannot be
represented without semantic loss is not adapted automatically; it requires a
new schema/revision decision.

## Logical Field Set

The following is a design-time field map, not a code change:

```text
GameplayExtensionEnvelope
  platform_schema_version
  package_identity
  package_definitions[]
  outcome_declarations[]
  capability_binding_requests[]
  dependency_and_conflict_refs[]
  replay_reader_refs[]
  verification_profile_refs[]
```

| Field | Package may supply | Adapter/authority responsibility | Prohibited meaning |
| --- | --- | --- | --- |
| `platform_schema_version` | declared version token | validate supported compatibility range | selecting a runtime or owner |
| `package_identity` | identity, revision, author/trust refs, declared dependency/schema refs | derive/verify canonical digests and active-set pins | activation or truth ownership |
| `package_definitions[]` | immutable typed content | validate definition schema and namespace | asserting an instance exists |
| `outcome_declarations[]` | content slots, approved outcome family reference, policy/eligibility references | resolve only approved descriptors and proofs | choosing owner/stream/event/privacy/receipt |
| `capability_binding_requests[]` | reference to an existing capability family and typed read requirements | perform read-only descriptor/recipe binding | registration or capability creation |
| `dependency_and_conflict_refs[]` | explicit package dependency/conflict declarations | deterministic validation and active-set decision | load-order priority or implicit replacement |
| `replay_reader_refs[]` | references to retained readers required by declared content | verify reader availability and historical pinning | changing historical interpretation |
| `verification_profile_refs[]` | descriptive verification metadata | retain as control-plane metadata | granting authority or bypassing proof |

The adapter must not accept package-supplied owner descriptors, event vectors,
stream IDs, privacy scopes, receipt rules, compensation rules, arbitrary
predicate code, or recipe fragments. Those values come from already approved
owner contracts and read-only binding.

## Version Model

Three version axes remain distinct:

```text
platform_schema_version   # shape/validation compatibility
package_revision           # immutable package content identity
descriptor/recipe revision # immutable owner operation contract identity
```

Recommended platform schema syntax is `major.minor`:

- unknown major versions are inactive and fail closed;
- a higher minor version is accepted only when an approved compatibility rule
  proves additive, lossless fields and preserves unknown fields in canonical
  form;
- removed, retyped, or semantically changed fields require a new major
  version;
- a package revision and digest are never changed in place by a schema
  adapter;
- descriptor and recipe revisions are pinned independently of platform
  schema version.

No version fallback may silently drop fields, invent defaults, widen privacy,
or reinterpret owner coordinates.

## Version Migration Rules

### Legacy manifest to extension-aware reader

The adapter may expose a legacy manifest as an empty extension envelope for
read-only inspection, but it must not manufacture declarations, bindings,
predicates, recipes, or capability rows. If the serialized representation or
canonical digest changes, the result is a new package revision; no digest is
reused or guessed.

### Additive minor migration

An additive minor migration is allowed only when all of the following hold:

1. old required fields retain their exact meaning and canonical encoding;
2. new fields are optional or have an explicitly encoded absence value;
3. unknown fields are preserved for digest/replay purposes;
4. owner descriptor, predicate, evidence, privacy, receipt, replay, and
   compensation semantics are unchanged;
5. the migration is deterministic and side-effect-free.

Otherwise the package remains inactive until a new major schema/revision is
approved.

### Historical replay

Historical events retain their original package revision, platform schema
version, descriptor/recipe revisions, and replay-reader references. A newer
schema reader may decode them through a lossless adapter, but may not rerun
new package rules or alter the committed outcome. If the required reader is
unavailable, replay fails closed with an auditable readiness error.

### Disable, upgrade, and rollback

Disable/revoke blocks new admission only. Upgrade publishes a new immutable
package revision and active-set revision. Rollback selects a prior compatible
revision for future proposals; it never rewrites historical package data or
owner events.

## Validation Order And Zero-Write Rules

The future schema boundary must validate in this order:

1. parse the existing manifest envelope and identify the extension schema;
2. validate schema version and preserve unknown fields according to the
   approved compatibility rule;
3. validate identity, dependency, conflict, namespace, and canonical field
   shapes;
4. validate declaration and binding references without resolving arbitrary
   owners;
5. hand the normalized immutable record to the approved read-only binding
   boundary;
6. reject before any owner append when any step fails.

Unknown version, malformed field, duplicate identity, digest mismatch,
dependency conflict, dropped field, ambiguous binding, caller-selected
authority coordinate, private/stale evidence, or unsupported reader is
zero-write. The schema layer emits no marker-only event, receipt, outbox, or
partial fragment.

## Verification Plan (Design-Only)

Before schema implementation approval, the following verification artifacts
must be designed, but not yet executed as tests:

| Verification family | Planned evidence |
| --- | --- |
| Legacy compatibility | unchanged legacy manifest interpretation and active-set behavior |
| Extension shape | every logical field accepts only its declared type and owner boundary |
| Version matrix | supported major/minor combinations, unknown-major rejection, additive-minor proof |
| Canonicalization | stable canonical ordering, duplicate rejection, digest-field exclusion, preserved unknown fields |
| Migration | lossless adapter fixtures, semantic-change rejection, historical reader pin retention |
| Binding isolation | package cannot create/select owner descriptor, recipe, stream, event, privacy, receipt, or fragment |
| Zero-write | malformed, stale, ambiguous, private, conflicting, and unsupported inputs produce no append artifacts |
| Replay readiness | old package/schema/descriptor/reader pins remain addressable or fail closed audibly |
| Scope guard | no manifest code, compiler, catalog, runtime, tests, Harness, package freeze, or INF row changes |

The eventual RED tests and Harness are separate implementation gates and are
not authorized by this design.

## Approval Gates For This Phase

1. Approve this logical field map and compatibility policy.
2. Approve the version/migration rules and historical replay behavior.
3. Approve the validation order, zero-write rules, and verification plan.
4. Only after those approvals may a separate schema implementation plan be
   approved. That later plan must still not freeze a package or implement any
   owner/compiler/catalog/runtime behavior without its own approval.

## Superseding Mapping Errata

The earlier logical decision is not approval-ready because it did not bind
every logical field to an exact manifest path and type, define byte-level v1
digest preservation, settle every array's ordering/empty/duplicate contract,
isolate legacy `economic_outcomes`, or name the durable lifecycle/replay pin
locations. Those gaps are recorded in the documentation-only
[schema mapping and migration errata](2026-08-18-federated-gameplay-extension-platform-schema-mapping-and-migration-errata-design.md).

The approved errata supersedes any earlier incomplete schema-decision
statement. It fixes outer manifest v1 freeze, extension-only manifest v2, and
exact inner platform version `1.0`; unknown major/minor values are zero-write.
Schema implementation approval remains pending.

The [schema-closure addendum](2026-08-18-federated-gameplay-extension-platform-schema-closure-addendum.md)
closed the final review surface. It fixes strict nested object schemas with
`extra=forbid`, namespace and authority-shaped-payload rules, author-ordered
v2 arrays, exact replay pairings, and the existing candidate-snapshot replay
precondition. It also fixes untrusted declaration-digest claims, normalized
immutable declaration output, and the complete-v2 `content_digest` input.
Its approval does not approve implementation; a separate file-by-file
schema-v2 implementation plan is a future independently approved task.

## Current Status

The platform design is `design approved and complete`. No manifest schema or
implementation change has been made. Schema implementation, package freeze,
canonical digest calculation, catalog/compiler/verifier/reducer work,
tests/Harness, row binding, and INF runtime recovery remain independent and
unapproved.
