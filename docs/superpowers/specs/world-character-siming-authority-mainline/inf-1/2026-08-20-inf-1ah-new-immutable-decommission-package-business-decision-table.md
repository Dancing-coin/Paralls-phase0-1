# INF-1AH New Immutable Decommission Package Business Decision Table

Status: `historical literal-decision record; lifecycle vertical implemented and verified on 2026-08-21`

## Scope And Authority Boundary

This table recorded the business approval surface for one package-local outcome:

```text
committed facility_acquired(mill)
  + committed frozen v2 mill -> mill_reinforced source vector
  -> facility_decommissioned@1
```

The existing `ConstructionProductionAuthority` remains the sole owner of the
facility lifecycle fact. Package content may describe only the typed source
and target definitions and the row-local policy/dependency declarations. It
may not select the owner, stream, event family, privacy, revision fence,
idempotency key, receipt, replay reader, compensation rule, or append
fragment.

The frozen `package:industrial-facilities:v2` is an already-fixed source
evidence constraint. It is not part of this approval set, must not be
modified, copied as the new package, recalculated, overwritten, or reused as
the decommission package. At the time of this table, no manifest bytes were
authored and no digest was calculated. The approved literals subsequently
produced the frozen v3 record; this table does not change or recalculate it.

## Fixed Contract Facts

The following facts are already fixed and are not business decisions for this
table:

- lifecycle transition is exactly `active -> decommissioned`;
- `facility_kind` remains exactly `mill_reinforced` before and after the event;
- target owner is `ConstructionProductionAuthority`;
- target stream is `gameplay:construction_production:{facility_ref}`;
- target event family is exactly
  `gameplay.construction_production.facility_decommissioned@1`;
- target and source visibility is `project`;
- subject binding is committed `facility_ref` plus
  `project_ref=facility_acquired.plot_ref`;
- the source proof requires one exact project-visible acquisition event and one
  exact project-visible frozen-v2 reinforcement event on the same facility
  stream;
- the owner must pin the exact acquisition event revision, exact
  reinforcement event revision, current facility revision, facility stream
  head, and the source-event revision values carried by the reinforcement
  event;
- idempotency is authority-derived and an exact duplicate may replay only the
  original append-derived receipt; a changed duplicate is zero-write;
- receipt is derived only from the target owner's
  `GameplayEventStore.append_batch()` result;
- full replay and checkpoint-tail replay use the existing Construction replay
  boundary and must agree on lifecycle status, facility revision, unchanged
  kind, project binding, and source revision vector;
- the row is v1 terminal: no reactivation, reversal, retry-as-new, fanout,
  compensation, payment, material, inventory, output, maintenance, or
  cross-domain consequence;
- any committed `ProductionRun` for the same facility with `status=started`
  is a pre-append zero-write rejection, with no cancellation, reservation
  release, output disposal, refund, compensation, or substitute event.

### Required Revision-Pin Vector

The following pins are exact owner-derived inputs for a future row-specific
admission. They are not package literals, are not caller-selectable, and do
not become additional business approvals:

```text
acquisition_event_id
acquisition_event_revision
reinforcement_event_id
reinforcement_event_revision
prior_facility_revision        = current projected facility revision
expected_stream_revision       = current facility stream head
reinforcement_source_revisions = source-event revision values carried by the
                                 committed frozen-v2 reinforcement event
```

The append envelope must carry the complete vector and reject any missing,
private, stale, ambiguous, binding-conflicting, or revision-conflicting
member before append. The frozen source evidence remains pinned exactly as:

```text
source_package_revision = package:industrial-facilities:v2
source_declaration_ref  = declaration:industrial-facilities-mill-to-mill-reinforced@1
source_descriptor_ref   = descriptor:construction-facility-mill-reinforcement@1
source_policy_revision  = policy:industrial-facilities:mill-to-mill-reinforced@1
```

Its existing content and declaration digests are read-only evidence from the
frozen v2 record; this table neither recalculates nor reuses them for the new
package.

## Business Decision Table

`Contract uniquely fixed` means the existing INF-1AH contract already fixes
the value. `Mechanically derivable` means the value is derived after the
business literals in this table are approved; it is not an additional user
approval. `Missing business decision` means the user must choose one literal.
Candidate values below were recommendations only at authoring time. They are
now historical evidence of literals explicitly approved and frozen; the table
is not an authority to amend v3.

| Package field | Classification | Candidate value / source | Business impact and recommendation |
| --- | --- | --- | --- |
| `package_identity.package_id` | Missing business decision | `package:industrial-facilities`; existing facility package lineage | Keeps the row in the named industrial-facilities lineage while requiring a distinct immutable revision. Recommend retaining the lineage, subject to business approval. |
| `package_identity.package_revision` / `patch_revision_id` | Mechanically derivable | Derive a new revision from the approved package identity/version, e.g. `package:industrial-facilities:v3`; never equal to frozen v2 | Creates the immutable package boundary. Do not approve a literal revision independently from the package/version decision. |
| `package_identity.package_version` | Missing business decision | `3.0.0`; next version after the frozen v2 package | Determines the new package version and participates in derived revision identity. Recommend `3.0.0`, subject to approval. |
| `patch_version` | Missing business decision | `3.0.0`; must equal `package_identity.package_version` | Keeps outer patch metadata and package metadata byte-consistent. Recommend the same approved package version. |
| `author_id` | Missing business decision | `author:repo`; existing v2 author identity as continuity source | Assigns accountable content authorship. Recommend continuity only if the business authority accepts the same author identity. |
| `trust_policy_ref` | Missing business decision | `trust:repo`; existing v2 trust-policy lineage | Selects package admission trust, not runtime authority. Recommend continuity only with explicit approval. |
| source `definition_ref` | Missing business decision | `definition:industrial-facilities-mill@1`; existing source-kind semantic | Makes the package-local committed source kind explicit. This is newly authored v3 content, not copied v2 bytes. Recommend this literal. |
| target `definition_ref` | Missing business decision | `definition:industrial-facilities-mill-reinforced@1`; retained-kind semantic | Makes the package-local retained target kind explicit. It must not assert lifecycle status or an external consequence. Recommend this literal. |
| source `definition_schema_ref` | Missing business decision | `schema:industrial-facilities-facility@1`; existing typed facility schema shape | Keeps source content within the established facility schema. Recommend only with approval of the associated source typed content. |
| target `definition_schema_ref` | Missing business decision | `schema:industrial-facilities-facility@1`; existing typed facility schema shape | Keeps target content within the same established facility schema. Recommend only with approval of the associated target typed content. |
| source `typed_content` | Missing business decision | `{ "facility_kind": "mill" }`; committed source-kind fact | Declares only the package-local source kind. Recommend exactly this typed content, without lifecycle or external-domain fields. |
| target `typed_content` | Missing business decision | `{ "facility_kind": "mill_reinforced" }`; retained-kind boundary | Declares only the retained facility kind. Recommend exactly this typed content, without lifecycle status or external effects. |
| `declaration_ref` | Mechanically derivable | `declaration:industrial-facilities-mill-reinforced-decommission@1`; derived from the approved row identity | Names the one row-local declaration. It is not a separate business approval. |
| `binding_ref` | Mechanically derivable | `binding:industrial-facilities-mill-reinforced-decommission@1`; derived from the approved row identity | Names the one future exact-one read-only binding. It is not a separate business approval. |
| `policy_ref` | Missing business decision | `policy:industrial-facilities:mill-reinforced-decommission@1`; exact lifecycle-only policy identity | Names the policy whose semantics are already constrained to terminal no-compensation decommission. Recommend this row-local policy identity, subject to approval. |
| `policy_revision` / `policy_revision_ref` | Mechanically derivable after policy approval | The approved policy identity's immutable `@1` revision | Pins the approved policy without introducing a second policy choice. No generic transform/decommission policy is permitted. |
| `capability_ref` | Mechanically derivable | `capability:construction-facility-mill-decommission@1`; derived from the exact approved operation | Must later match the exact immutable descriptor capability. It is not a separate business approval and is not installed here. |
| `outcome_family_ref` | Mechanically derivable | `outcome:construction-facility-mill-decommission@1`; derived from the exact approved operation | Names the lifecycle-only outcome and cannot widen into a generic transform family. It is not a separate business approval. |
| `requirement_ref` | Mechanically derivable | `requirement:construction-facility-mill-reinforced@1`; derived from the fixed eligibility family | Keeps the typed read requirement aligned with owner-derived source proof. It is not caller-selectable. |
| `predicate_family_ref` | Mechanically derivable | `predicate:construction-facility-mill-reinforced@1`; derived from the fixed eligibility family | Permits only Construction-derived proof facts. It is not an additional business choice. |
| `subject_slot_ref` | Contract uniquely fixed | `slot:facility-project@1`; fixed by the source/target subject binding | Requires the same committed facility and project binding. Caller or agent cannot replace it. |
| `proposal_effect_types` | Mechanically derivable | `["effect:construction-facility-mill-decommission@1"]`; derived from the exact row | Proposal metadata only; the owner/descriptor must validate the fixed effect. It is not a separate business approval. |
| `dependencies` | Missing business decision | `[]`; existing v2 manifest precedent and frozen v2-as-evidence rule | An empty list prevents the new package from selecting v2 as an activation dependency or importing unrelated ordering semantics. Recommend explicit `[]`. |
| `dependency_and_conflict_refs` / conflict refs | Missing business decision | `[]`; existing row-local package precedent | An empty list prevents package-level conflict/order authority. Recommend explicit `[]`; no implicit dependency or conflict may be inferred. |
| `replay_reader_refs` | Contract uniquely fixed | `[]`; replay is owned by the existing Construction projector/replay boundary | Package content cannot select or add a replay reader. Full/checkpoint-tail replay remains an owner contract. |
| `verification_profile_refs` | Contract uniquely fixed | `[]`; verification is later implementation evidence | A future Harness/profile is not package-controlled content and is not part of business approval. |

## Minimum One-Time Business Approval

The only fields requiring one-time business approval are:

1. package identity and version: `package_id` and `package_version`;
2. `author_id`;
3. `trust_policy_ref`;
4. source definition: `definition_ref`, `definition_schema_ref`, and exact
   typed content;
5. target definition: `definition_ref`, `definition_schema_ref`, and exact
   typed content;
6. the lifecycle-only `policy_ref`; and
7. explicit `dependencies=[]` and explicit `dependency_and_conflict_refs=[]`.

`package_revision`/`patch_revision_id`, `declaration_ref`, `binding_ref`,
`policy_revision`, `capability_ref`, `outcome_family_ref`, `requirement_ref`,
`predicate_family_ref`, and `proposal_effect_types` are mechanically derived
from those decisions and the already fixed INF-1AH contract. They must not be
re-raised as duplicate business blockers.

## Superseded Package Gate And Current Blocker

The minimum literal set above was approved, then authored, adapter-validated,
and frozen as v3. The remaining gates are procedural and independent:

```text
exact descriptor/catalog approval
-> exact-one read-only activation binding
-> separate row-specific runtime approval
```

No historical step in this table authorizes descriptor/catalog installation,
runtime, tests, Harness, or an append path.
All unknown, multiple, unadmitted, digest-mismatched, missing/private/stale,
binding-conflicting, revision-conflicting, duplicate, and changed-duplicate
inputs remain zero-write before any future append.
