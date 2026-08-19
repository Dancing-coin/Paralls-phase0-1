# INF-1AG Industrial Facilities V1 Non-Admitted Manifest Draft And Freeze Checklist

Status: `historical authoring draft; superseded by the 2026-08-19 frozen immutable manifest record`

Date: `2026-08-18`

## Historical Boundary

This is an audit worksheet for the one approved INF-1AG semantic row. It is
not a `GameplayPatchManifest` instance, candidate, active package, descriptor,
catalog row, digest input, test fixture, Harness profile, or Construction
command. Angle-bracket values are deliberately unresolved text, not JSON
values accepted by the runtime.

No `content_digest` or `declaration_digest` is derived, claimed, compared, or
confirmed here. The first executable candidate, if separately approved, must
be a complete immutable v2 manifest with no placeholders. It must not be an
empty-binding placeholder or a later edit of the same revision.

The fixed row semantics are:

```text
package_id       = package:industrial-facilities
package_revision = package:industrial-facilities:v1
outcome_family   = construction_facility_package_declared_transform@1
capability_ref   = capability:construction-facility-package-declared-transform@1
source_kind      = oven
target_kind      = kiln
policy_revision  = policy:industrial-facilities:oven-to-kiln@1
eligibility_refs = [construction:facility-acquired@1]
project_binding  = construction_plot_as_project@1
privacy          = project
terminal          = v1 terminal/no compensation
```

`project_binding`, privacy, terminal semantics, owner, stream, event family,
receipt, replay, and compensation are fixed by the approved Construction row
contract. They are not author fields and must not be inserted into
`typed_content`, a declaration, or a binding request.

## Current Evidence Audit

| Required item | Result | Evidence / consequence |
| --- | --- | --- |
| v2 platform pair | determined | `(manifest_schema_version=2, platform_schema_version="1.0")` is the only supported extension pair. |
| package identity and revision | determined | `patch_id`/`package_id` must be `package:industrial-facilities`; `patch_revision_id`/`package_revision` must be `package:industrial-facilities:v1`. |
| `oven` source kind | semantic only | `Facility.facility_kind` is a free string. No committed package definition or existing source fixture defines `oven`. |
| `kiln` target kind | semantic only | No committed package definition, schema record, or Construction projection fixture defines `kiln`. |
| source/target definition refs | missing | No existing `definition:` record for either kind was found. They cannot be invented from the kind literals. |
| source/target definition schema refs | missing | No existing `schema:` record defines facility-package content for `oven` or `kiln`. |
| declaration ref and outcome-family ref | missing mapping | The approved semantic family is not itself a schema-valid `outcome:` reference. A canonical, immutable mapping must be supplied. |
| binding ref | missing | No existing `binding:` identity is admitted for this row. |
| predicate family and subject slot | missing | The row fixes `construction:facility-acquired@1`, but no approved `predicate:`/`slot:` vocabulary maps that evidence to a package binding. |
| proposal effect types | missing | The later immutable descriptor must own this allow-list. An empty list would be a new policy choice, not a safe default. |
| package-level dependencies/conflicts | missing | No exact dependency revision or conflict set is approved. The binding capability alone does not choose a dependency revision. |
| package-owned event schemas | determined empty | This row may not author `facility_transformed@1`; that is the existing Construction event family. No package-owned event schema is identified, so the only non-expansive value is `[]`. |
| replay reader refs | missing | The owner contract names `ConstructionProductionAuthority.projector`, but no immutable `reader:` ref/revision pair exists for full and checkpoint-tail package content. |
| verification profile refs | missing | No immutable `verification:` ref exists for this unimplemented row. A future Harness profile cannot be backfilled into this revision without an explicit pre-freeze choice. |
| declaration/content digests | intentionally unresolved | Both must derive only from finalized canonical author bytes; this document contains placeholders and is not input. |

The generic Construction acquisition path proves only that an authority can
commit a facility with an arbitrary non-empty kind. Current committed
Construction fixtures use `bakery` / `bakery_reinforced`, not `oven` / `kiln`.
That is insufficient evidence for package definitions, schema identities, or
binding vocabulary.

## Non-Admitted Manifest Draft

The following shows every required v2 field and preserves the fixed values.
It is intentionally invalid and must never be passed to
`GameplayPatchManifest.model_validate()`, canonicalized, or installed.

```json
{
  "manifest_schema_version": 2,
  "patch_id": "package:industrial-facilities",
  "patch_version": "<MISSING: exact immutable package version>",
  "patch_revision_id": "package:industrial-facilities:v1",
  "content_digest": "<UNRESOLVED: derive only after final canonical bytes>",
  "author_id": "<MISSING: trusted immutable package author>",
  "trust_policy_ref": "<MISSING: approved immutable trust policy>",
  "dependencies": "<MISSING: exact package dependencies or approved empty set>",
  "state_group_ids": [],
  "state_group_migrations": [],
  "event_schemas": [],
  "rules": [],
  "requested_capabilities": [],
  "economic_outcomes": [],
  "granted_effect_types": [],
  "verification_profiles": [],
  "platform_extension": {
    "platform_schema_version": "1.0",
    "package_identity": {
      "package_id": "package:industrial-facilities",
      "package_version": "<MISSING: must equal patch_version>",
      "package_revision": "package:industrial-facilities:v1"
    },
    "package_definitions": [
      {
        "definition_ref": "<MISSING: exact oven definition:...@...>",
        "definition_schema_ref": "<MISSING: exact oven schema:...@...>",
        "source_package_revision": "package:industrial-facilities:v1",
        "typed_content": "<MISSING: schema-valid oven content declaring facility_kind=oven>"
      },
      {
        "definition_ref": "<MISSING: exact kiln definition:...@...>",
        "definition_schema_ref": "<MISSING: exact kiln schema:...@...>",
        "source_package_revision": "package:industrial-facilities:v1",
        "typed_content": "<MISSING: schema-valid kiln content declaring facility_kind=kiln>"
      }
    ],
    "outcome_declarations": [
      {
        "declaration_ref": "<MISSING: declaration:...@...>",
        "outcome_family_ref": "<MISSING: outcome:...@... mapping for construction_facility_package_declared_transform@1>",
        "definition_refs": "<MISSING: canonical ordered exact oven/kiln definition refs>",
        "eligibility_refs": ["construction:facility-acquired@1"],
        "policy_revision_ref": "policy:industrial-facilities:oven-to-kiln@1",
        "source_package_revision": "package:industrial-facilities:v1",
        "declaration_digest": "<UNRESOLVED: required untrusted claim derived after final declaration bytes>"
      }
    ],
    "capability_binding_requests": [
      {
        "binding_ref": "<MISSING: binding:...@...>",
        "capability_ref": "capability:construction-facility-package-declared-transform@1",
        "source_package_revision": "package:industrial-facilities:v1",
        "declaration_ref": "<MISSING: must exactly equal outcome declaration ref>",
        "typed_read_requirements": [
          {
            "requirement_ref": "<MISSING: requirement:...@...>",
            "predicate_family_ref": "<MISSING: predicate:...@... for construction:facility-acquired@1>",
            "subject_slot_ref": "<MISSING: slot:... bound to facility_ref and project_ref>"
          }
        ],
        "proposal_effect_types": "<MISSING: exact immutable descriptor-owned ordered allow-list>"
      }
    ],
    "dependency_and_conflict_refs": "<MISSING: exact ordered records or approved empty set>",
    "replay_reader_refs": "<MISSING: exact full and checkpoint-tail reader: refs/revisions>",
    "verification_profile_refs": "<MISSING: exact ordered verification: refs or approved empty set>"
  }
}
```

The two definition objects above are not an assertion that a definition schema
uses `facility_kind`; they state the minimum semantic content that a future
approved schema must make representable. Their object order must be changed to
the lexicographic order of the finalized `definition_ref` values, never sorted
silently by admission.

## Freeze Checklist

All items must be true before a final manifest byte sequence is submitted for
separate freeze approval.

1. Provide real immutable `definition:` and `schema:` identities for both
   `oven` and `kiln`, with schema-valid, non-authority-shaped content. Confirm
   the canonical ordered `definition_refs` array.
2. Supply the exact `patch_version`, trusted `author_id`, and
   `trust_policy_ref`; ensure both package identity fields exactly equal the
   outer values.
3. Supply a canonical `declaration_ref` and the exact `outcome:` reference
   mapping for the approved outcome family. This mapping must not change the
   fixed source/target semantics or admit a generic transform.
4. Supply a canonical `binding_ref`, `requirement_ref`, `predicate:` family,
   and `slot:` binding vocabulary. The vocabulary must prove the existing
   Construction-owned `facility_acquired@1` fact, bind both `facility_ref` and
   `facility_acquired.plot_ref` under `construction_plot_as_project@1`, and
   must not be caller-supplied proof.
5. Obtain the descriptor-owned, exact ordered `proposal_effect_types`. Do not
   assume an empty vector, create an effect type, or derive an event vector.
6. Resolve whether `dependencies` and
   `dependency_and_conflict_refs` are intentionally empty or provide their
   exact immutable ref/revision records. No load-order or floating revision is
   valid.
7. Provide immutable full and checkpoint-tail `reader:` refs/revisions, or
   explicitly approve their absence as compatible with the approved row replay
   contract. `ConstructionProductionAuthority.projector` is not itself a
   schema-valid `reader:` ref.
8. Provide immutable `verification:` refs, or explicitly approve an empty set
   before freeze. A future test or Harness name cannot be silently inserted
   into the frozen revision.
9. Confirm every collection's author order, set semantics, duplicate rejection,
   and non-null encoding against the v2 schema. In particular: definition,
   declaration, binding, requirement, dependency/conflict, replay-reader, and
   verification arrays must already be canonical; admission must not rewrite
   them.
10. Only after items 1-9 are complete, construct the final bytes. The author
    must include a declaration-digest claim for each declaration; the adapter
    derives and compares it, stores only the derived value, then derives the
    outer content digest. Missing, malformed, mismatched, or conflicting
    digest claims are zero-write. No draft value in this document may be used.
11. Submit the exact final manifest bytes and derived values for user approval.
    Only that approval may authorize candidate installation. Descriptor/catalog
    admission, RED tests, Harness, verifier/reducer work, and Construction
    append remain later independent gates.

## Superseding Disposition

The user separately approved `patch_version = 1.0.0`, with exact equality to
the already approved inner `package_version = 1.0.0`. The real placeholder-free
canonical v2 bytes and verified claims are now frozen in
[the freeze record](2026-08-19-inf-1ag-industrial-facilities-v1-freeze-record.md).
This document remains historical evidence of why no value was inferred before
that explicit approval.

## Historical Disposition

`package-content pending`. The determined row semantics do not make this draft
freezable: the missing identities, binding vocabulary, descriptor-owned effect
allow-list, replay/verification references, and final author metadata prevent
canonical bytes from existing. This is an authoring/evidence gap, not a reason
to add a default target, implicit policy, generic registry, or new authority.
