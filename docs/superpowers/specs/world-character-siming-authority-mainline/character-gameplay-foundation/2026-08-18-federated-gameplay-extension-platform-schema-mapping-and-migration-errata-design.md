# Federated Gameplay Extension Platform Schema Mapping And Migration Errata

Status: `design approved; INF-P schema mechanics implemented and verified; package and row gates remain separate`

Date: `2026-08-18`

This errata corrects the previous schema-decision design. The platform
contract remains approved, but the schema decision is not complete until the
logical extension fields, exact manifest paths, canonical array rules,
legacy-digest preservation, lifecycle/replay pin locations, and rollout gates
below are accepted. This document does not edit `GameplayPatchManifest`, add a
manifest field, freeze a package, calculate a digest, or authorize compiler,
catalog, verifier, reducer, test, Harness, or runtime work.

## Governing Version Boundary

The conservative first schema is deliberately split:

```text
manifest_schema_version = 1
  existing manifest only; byte-for-byte legacy digest semantics are frozen

manifest_schema_version = 2
  existing manifest fields plus one extension object at /platform_extension
  platform_schema_version must be exactly "1.0"
```

The integer `manifest_schema_version` is the outer manifest contract. The
string `platform_schema_version` is the inner federated-platform contract.
They are not aliases and one cannot be inferred from the other.

| Outer value | Extension object | Inner value | Disposition |
| --- | --- | --- | --- |
| `1` | absent only | absent | legacy reader; preserve existing semantics and digest |
| `1` | present | any | zero-write; v1 is frozen and cannot contain extension fields |
| `2` | required exactly once | `"1.0"` | candidate for schema validation, subject to later implementation approval |
| `2` | missing, duplicated, or malformed | any | zero-write |
| `2` | present | unknown major or minor, including `"1.1"` | zero-write in v1 platform implementation |
| `0`, negative, non-integer, or `>2` | any | any | zero-write until a separately approved outer schema exists |

No adapter silently upgrades a v1 manifest to v2. A v2 manifest is a new
immutable manifest revision with its own complete canonical digest. A read-only
inspection view may expose an empty logical extension for v1, but it must not
serialize that view, activate it, or use it as a declaration.

## Exact Manifest Mapping

The following is the proposed v2 mapping into the existing
`GameplayPatchManifest` shape. Paths beginning with `/` are canonical JSON
paths. The names are design commitments for the next schema decision, not
runtime fields today.

### Existing outer fields

| Logical value | Manifest path | Type | Requiredness | Owner | Canonical rule |
| --- | --- | --- | --- | --- | --- |
| outer schema | `/manifest_schema_version` | integer | required | patch admission boundary | exact integer, no coercion |
| package id | `/patch_id` | non-empty string | required | package, validated by adapter | existing path and encoding |
| package version | `/patch_version` | non-empty string | required | package | existing path and encoding |
| package revision | `/patch_revision_id` | non-empty string | required | package, immutable identity | existing path and encoding |
| content digest | `/content_digest` | `sha256:` string | required | adapter derives and validates | excluded only while deriving the complete digest |
| author | `/author_id` | non-empty string | required | package signer/author | existing trust boundary |
| trust policy | `/trust_policy_ref` | non-empty string | required | platform policy | existing path and encoding |
| legacy dependencies | `/dependencies` | array of dependency objects | optional, default encoded as `[]` only for new serialization | package, validated by adapter | legacy array rules below |
| legacy state groups | `/state_group_ids` | array of strings | optional, default `[]` only for new serialization | package | v2 input must already be lexicographically sorted and unique; v1 order is frozen |
| legacy migrations | `/state_group_migrations` | array of migration objects | optional | package, bounded by existing runtime | ordered by existing canonical payload; duplicates rejected |
| legacy event schemas | `/event_schemas` | array of event-schema objects | optional | package, validated by patch boundary | ordered by `(event_type, schema_version)` only for v2; v1 order is frozen |
| legacy rules | `/rules` | array of rule objects | optional | package, proposal-only | ordered by `rule_id` only for v2; v1 order is frozen |
| legacy requested capabilities | `/requested_capabilities` | array of capability refs | optional | package request only | v2 input must already be ordered by `(capability_id, capability_version)` |
| legacy economic outcomes | `/economic_outcomes` | array of legacy economic-outcome objects | optional | package request to existing Economy owner | never migrated into extension declarations |
| legacy granted effects | `/granted_effect_types` | array of strings | optional | package declaration, existing capability boundary | v2 input must already be lexicographically sorted and unique |
| legacy verification profiles | `/verification_profiles` | array of strings | optional | package metadata | v2 input must already be lexicographically sorted and unique |

### v2 extension object

For `manifest_schema_version == 2`, exactly one object is required at
`/platform_extension`. The object is owned by the package only for the slots
listed as package-fillable; all authority coordinates are adapter- or
descriptor-derived.

| Logical field | Manifest path | Type | Requiredness | Package ownership | Canonical path/rule |
| --- | --- | --- | --- | --- | --- |
| platform schema | `/platform_extension/platform_schema_version` | string | required | package declares version token | exact string `"1.0"` |
| package identity pin | `/platform_extension/package_identity` | object | required | package supplies identity references; adapter cross-checks outer fields | object keys sorted; values must equal `/patch_id`, `/patch_version`, `/patch_revision_id` |
| definitions | `/platform_extension/package_definitions` | array of objects | required, possibly empty | package content slots only | set-like by `definition_ref`; duplicate refs zero-write |
| outcome declarations | `/platform_extension/outcome_declarations` | array of author declaration inputs | required, possibly empty | package content slots only | ordered by `declaration_ref`; each required digest is an untrusted claim and the normalized record retains only the adapter-derived value |
| binding requests | `/platform_extension/capability_binding_requests` | array of objects | required, possibly empty | package references only | set-like by `binding_ref`; duplicate refs zero-write |
| dependency/conflict refs | `/platform_extension/dependency_and_conflict_refs` | array of objects | required, possibly empty | package declarations | canonical identity `(relation, ref, revision)` |
| replay readers | `/platform_extension/replay_reader_refs` | array of objects | required, possibly empty | package references retained readers | set-like by `(reader_ref, reader_revision)` |
| verification profiles | `/platform_extension/verification_profile_refs` | array of strings | required, possibly empty | package metadata only | input must already be lexicographically sorted; duplicate or non-canonical order zero-write |

`package_identity` may repeat only the non-authority identity pins. A mismatch
between the repeated values and the outer fields is zero-write; the extension
cannot override the outer identity. The extension cannot contain owner,
stream, event-family, privacy, receipt, compensation, predicate code, recipe
fragment, or caller proof fields. Those values remain fixed by the approved
descriptor/catalog boundary.

## Canonical Array And Empty-Value Contract

The existing canonical JSON bytes remain UTF-8 with `ensure_ascii=false`,
sorted object keys, and compact separators. Array semantics are explicit:

| Array | v1 handling | v2 handling | Empty/null encoding | Digest behavior |
| --- | --- | --- | --- | --- |
| `dependencies` | preserve serialized order exactly; reject duplicate semantic identities | must already be ordered by `(dependency_kind, target_ref, version_range, required, reason)`; duplicate or non-canonical order zero-write | absent legacy field and `[]` are distinct only at raw-input level; canonical v1 behavior remains unchanged; v2 uses `[]` | included |
| `state_group_ids` | preserve order exactly | must already be lexicographically sorted by string; duplicate or non-canonical order zero-write | `[]`; `null` zero-write | included |
| `state_group_migrations` | preserve order exactly | must already be ordered by `group_id`; duplicate or non-canonical order zero-write | `[]`; `null` zero-write | included |
| `event_schemas` | preserve order exactly | must already be ordered by `(event_type, schema_version)`; duplicate or non-canonical order zero-write | `[]`; `null` zero-write | included |
| `rules` | preserve order exactly | must already be ordered by `rule_id`; duplicate or non-canonical order zero-write | `[]`; `null` zero-write | included |
| `requested_capabilities` | preserve order exactly | must already be ordered by `(capability_id, capability_version)`; duplicate or non-canonical order zero-write | `[]`; `null` zero-write | included |
| `economic_outcomes` | preserve order exactly; empty field is omitted by the existing digest serializer | must already be ordered by `outcome_ref`; legacy semantics remain opaque and no extension conversion occurs; duplicate or non-canonical order zero-write | v1 empty is omitted by existing serializer; `null` zero-write | included when non-empty; omitted only under existing v1 rule |
| `granted_effect_types` | preserve order exactly | must already be lexicographically sorted; duplicate or non-canonical order zero-write | `[]`; `null` zero-write | included |
| `verification_profiles` | preserve order exactly | must already be lexicographically sorted; duplicate or non-canonical order zero-write | `[]`; `null` zero-write | included |
| `package_definitions` | not present | must already be ordered by `definition_ref`; duplicate or non-canonical order zero-write | required `[]`; `null` zero-write | included |
| `outcome_declarations` | not present | must already be ordered by `declaration_ref`; duplicate or non-canonical order zero-write | required `[]`; `null` zero-write | included |
| `capability_binding_requests` | not present | must already be ordered by `binding_ref`; duplicate or non-canonical order zero-write | required `[]`; `null` zero-write | included |
| `dependency_and_conflict_refs` | not present | must already be ordered by `(relation, ref, revision)`; duplicate or non-canonical order zero-write | required `[]`; `null` zero-write | included |
| `replay_reader_refs` | not present | must already be ordered by `(replay_mode, reader_ref, reader_revision)`; duplicate or non-canonical order zero-write | required `[]`; `null` zero-write | included |
| `verification_profile_refs` | not present | must already be lexicographically sorted; duplicate or non-canonical order zero-write | required `[]`; `null` zero-write | included |

No array is silently sorted, deduplicated, or rewritten. A duplicate or
non-canonical v2 order is a validation failure. An unknown array element,
unknown object key, wrong scalar type, or ambiguous sort key is zero-write.
`null` is never an implicit empty value. The digest
exclusion set contains only the containing digest field currently being
derived (`/content_digest`, and later any separately derived declaration
digest); no extension array is excluded merely because it is metadata.

## Declaration Digest Input And Normalized Output

The author declaration has a required `declaration_digest` claim, but that
claim is not trusted or copied into immutable admission state. The future
adapter removes only that field, canonicalizes the remaining declaration
payload without sorting/rewrite, derives `expected_declaration_digest`, and
requires exact equality with the author claim. Only the normalized immutable
declaration contains the derived digest.

Missing, malformed, wrong, or conflicting digest claims are zero-write; the
adapter must not silently add, replace, or repair them. The complete v2
manifest record is assembled only after every declaration is normalized.
`content_digest` is then derived from the full canonical v2 record containing
those derived declaration digests, with only `/content_digest` excluded. This
is a future validation/derivation sequence, not authorization to freeze or
calculate a package digest in this phase.

## Legacy v1 Byte-Level Digest Preservation

For `manifest_schema_version == 1`, the digest contract is the existing
`GameplayPatchManifest.expected_content_digest()` contract, not a new adapter
serializer. The digest input bytes are exactly:

```text
json.dumps(payload, ensure_ascii=False, sort_keys=True,
           separators=(",", ":")).encode("utf-8")
```

where `payload` is the existing model dump with only `/content_digest`
excluded, and the existing serializer removes `/economic_outcomes` when that
tuple is empty. Therefore:

- object-key order is canonicalized by the existing `sort_keys=True` rule;
- every array keeps the input order represented by the existing model dump;
- absent and empty `economic_outcomes` have the same v1 digest input because
  the existing empty-field omission rule applies;
- non-empty `economic_outcomes` remains in the digest input in its historical
  order and shape;
- UTF-8 bytes, `ensure_ascii=false`, compact separators, and the `sha256:`
  prefix are unchanged;
- a v1 reader must validate the supplied digest against those exact bytes and
  retain the validated canonical bytes/digest identity for replay; it must not
  normalize arrays, inject `/platform_extension`, rewrite empty values,
  reinterpret legacy outcomes, or recompute the digest with v2 rules.

Any adapter output whose canonical bytes differ is either a read-only view
with no digest authority or a new manifest revision. It may never reuse the
v1 `content_digest`.

## Legacy `economic_outcomes` Compatibility

`/economic_outcomes` remains the historical `GameplayPatchManifest` field used
by the existing `package_declared_negotiated_exchange` Economy path. It is not
an alias for `/platform_extension/outcome_declarations`.

- A v1 manifest with `economic_outcomes` replays through the existing Economy
  owner and its existing event/receipt/revision/privacy rules.
- A v2 manifest may retain legacy `economic_outcomes` only as an opaque,
  separately validated legacy section. The extension reader must not copy,
  reinterpret, or bind those entries as platform declarations.
- No automatic migration, backfill, renaming, or digest reuse is allowed.
- A declaration that claims the legacy entry and a platform declaration are
  the same outcome is ambiguous and zero-write unless a future row-specific
  contract explicitly defines both paths; this errata does not do so.
- Historical replay uses the original manifest schema, package revision,
  content digest, and legacy reader pin. A new platform reader cannot rerun
  the legacy entry under a newer descriptor or policy.

## Lifecycle, Pin Storage, And Validation Locations

The schema decision reuses existing control-plane and replay boundaries. It
does not create a second store or registry.

| Concern | Durable location | Validation owner/boundary |
| --- | --- | --- |
| candidate manifest | existing `GameplayPatchRegistry` candidate record and its existing lifecycle candidate evidence | patch admission/lifecycle authority validates outer schema, digest, dependencies, and extension shape |
| active manifest | existing active-set record/snapshot selected by the patch lifecycle authority | active-set validation checks immutable manifest identity and active-set revision |
| disable/revoke | existing patch lifecycle disable/revoke evidence | lifecycle authority blocks new selection; it never deletes or rewrites the candidate |
| upgrade | existing new candidate plus new active-set revision | lifecycle authority requires a new package revision/digest; no in-place mutation |
| package schema pin | manifest `/manifest_schema_version` plus v2 `/platform_extension/platform_schema_version` | schema boundary validates exact `(1, absent)` or `(2, 1.0)` pairing; `(1, 1.0)` is zero-write |
| descriptor pin | immutable `AdmissionArtifact.descriptor_ref_and_revision`, derived from the read-only catalog binding | binding/compiler boundary verifies descriptor availability and exact revision |
| reader pin | v2 `/platform_extension/replay_reader_refs`, copied into the immutable admission artifact and retained in committed event/replay metadata where the owner contract requires it | full and checkpoint-tail readers require the exact pinned reader revision or fail closed |
| package revision/digest pin | outer `/patch_revision_id` and `/content_digest`, repeated only for equality in `package_identity` | patch admission and replay identity checks |
| full replay | existing event store/replay reader for each owner stream, using the committed package/descriptor/reader pins | replay refuses semantic reinterpretation and reports missing/unknown pins audibly |
| checkpoint-tail replay | existing checkpoint metadata plus tail boundary, with the same package/descriptor/reader pins as full replay | checkpoint compatibility is checked before applying tail events |

The manifest and admission artifact are control-plane records. They are not
world truth and do not replace owner event metadata. A committed owner event
must retain the pins required by its already approved owner contract; if a
future descriptor does not define a durable pin location, that is an
`admission-evidence pending` blocker, not a reason to invent one here.

## Migration And Non-Migration Rules

1. v1 manifests are read as v1, with no extension injection and no digest
   recomputation.
2. v1 to v2 is a new manifest revision and new content digest. It is not an
   in-place migration and cannot preserve the old digest by assertion.
3. The first platform inner version supports only exact `1.0`; additive minor
   migration is not enabled until a later compatibility contract proves
   unknown-field retention and canonical byte preservation.
4. A re-serialization that changes any canonical byte, array order, omitted
   field, empty encoding, or legacy economic-outcome representation creates a
   new revision or is rejected; it never reuses a v1 digest.
5. Disable affects future candidate selection only. Upgrade creates a new
   immutable package and active-set revision. Historical events remain pinned
   to their original schema, package, descriptor, policy, and reader values.
6. Full replay and checkpoint-tail replay must use the same historical pins;
   a newer reader may decode losslessly but may not rerun new package rules.
7. If a required historical reader, descriptor, or schema pin is unavailable,
   replay fails closed with an auditable readiness error and writes nothing.

## Verification Matrix And Rollout Gates

This is a design-time matrix only. No tests or Harness are authorized by this
errata.

| Gate | Evidence to prepare later | Pass condition |
| --- | --- | --- |
| field mapping | v1/v2 fixture table with exact JSON paths, types, requiredness, and owner labels | every logical field has one path and one owner; no authority field is package-fillable |
| version compatibility | outer-int/inner-major.minor matrix | only v1 legacy and exact v2/`1.0` are accepted; unknown values zero-write |
| legacy byte preservation | canonical UTF-8 byte fixtures for existing v1 manifests, including empty/non-empty economic outcomes | validated v1 digest and canonical bytes remain unchanged |
| array semantics | pre-ordered and non-canonical fixtures, duplicate/null/empty and sort-key cases for every array | non-canonical v2 order is zero-write; no silent reorder/dedupe/default; digest inputs are exact |
| legacy economic isolation | replay fixtures with v1 and v2 manifests carrying legacy `economic_outcomes` | no automatic migration or reinterpretation through platform declarations |
| lifecycle pins | candidate, active, disable, upgrade, full replay, and checkpoint-tail pin fixtures | all locations and validators retain exact schema/package/descriptor/reader pins |
| zero-write | unknown schema, malformed extension, digest mismatch, duplicate, ambiguous binding, stale/private reader | no append, receipt, outbox, marker, or partial artifact |
| scope/rollout | diff inspection plus existing documentation gate | no runtime/schema/catalog/compiler/verifier/reducer/tests/Harness/package freeze changes |

## Future Implementation Touchpoints (Not Authorized)

When a later schema implementation plan is separately approved, the planned
touchpoints are limited to the existing spine and its evidence surfaces:

| Concern | File or artifact to review later | Current action |
| --- | --- | --- |
| manifest model and canonical digest | `backend/app/gameplay/patch_runtime.py` | no edit; schema decision only |
| candidate/active/disable/upgrade lifecycle | `backend/app/gameplay/patch_lifecycle_authority.py` and existing patch registry surfaces | no edit; lifecycle pin mapping only |
| legacy compatibility fixtures | existing `backend/tests/test_gameplay_patch_runtime.py` and `backend/tests/test_gameplay_patch_lifecycle_authority.py` | no tests added |
| extension field/version matrix | a future focused schema test module beside existing patch tests | not created |
| legacy economic-outcome isolation | existing `backend/tests/test_infra_package_declared_negotiated_exchange.py` plus future replay fixtures | no test changes |
| Harness evidence | a future independent profile under `.harness/profiles/` and report under `.harness/verification/` | no Harness added |
| documentation gate | this errata, schema decision plan, approval packet, readiness audit, taxonomy, README, and checkpoint | updated documentation only |

The future implementation must preserve the existing
`GameplayPatchRegistry`/patch-lifecycle ownership and existing event-store
replay readers. A new schema file, registry, compiler store, generic writer,
or second runtime is not an allowed touchpoint.

This was the pre-implementation gate. Later explicit INF-P authorization
implemented the approved schema-v2 and P1 mechanics with focused tests and an
independent Harness. Package content freeze/digest, row binding, and every
business runtime remain independently governed, but INF rows are no longer
globally paused: only their own row-specific contracts and source facts decide
whether they can advance.

## Current Disposition

```text
platform design: approved and complete
INF-P schema/P1 mechanics: implemented and verified
package freeze/digest: row-specific and independently governed
August INF A-D: active; not complete
```

This errata is approved design evidence. It does not itself claim a business
descriptor/catalog row, package, or INF runtime path; those later facts must
be read from their row-specific contracts and verification evidence.
