# INF-1AH Minimum Business Decision And Admission Closure Packet

Status: `historical approval record; lifecycle vertical implemented and verified on 2026-08-21`

## Purpose And Non-Authority

This packet isolates the last package-local business choices for the exact
INF-1AH operation:

```text
committed facility_acquired(mill)
  + exact frozen mill -> mill_reinforced source vector
  -> facility_decommissioned@1
```

It is not package bytes, a candidate installation, a digest calculation, a
descriptor/catalog row, a test, a Harness, or a Construction write path. It
does not authorize a generic decommission or transform operation, a new owner,
router, registry, writer, settlement authority, or a cross-domain event.

The fixed source package is evidence only and remains permanently read-only:

```text
package_revision   = package:industrial-facilities:v2
declaration_digest = sha256:73d3313283bf584254281a2ca1b60d888585f6ba89e6370a30d622e4529b1bc8
content_digest     = sha256:8deea88c5e49c2aa06f30bbf1bd78ed103e26d8fb31769fe5564dbb7cc279896
```

It must not be modified, recalculated, overwritten, or reused as the new
decommission package. Any newly approved record is a distinct immutable
revision and must be authored, normalized, digested, and frozen independently.

## Already Fixed Contract Boundary

The following values are not business choices for package authors. They are
fixed by the approved INF-1AH Owner-Admission and projection/replay contracts:

```text
owner                         = ConstructionProductionAuthority
source                        = committed project-visible facility_acquired(mill)
                                + exact frozen v2 mill -> mill_reinforced event
target stream                 = gameplay:construction_production:{facility_ref}
target event family           = gameplay.construction_production.facility_decommissioned@1
privacy                       = project
transition                    = active -> decommissioned
facility_kind                 = mill_reinforced before and after the event
eligibility_ref               = construction:facility-mill-reinforced@1
subject binding               = committed facility_ref + project_ref=acquisition.plot_ref
revision fence                = acquisition event, reinforcement event, current facility,
                                facility-stream head, and source-vector revisions
receipt                       = GameplayEventStore.append_batch() append-derived receipt
replay                        = existing Construction full and checkpoint-tail readers
lifecycle                     = v1 terminal; no reactivation, downgrade, retry-as-new,
                                compensation, or fanout
started ProductionRun         = pre-append zero-write rejection; no cancellation,
                                reservation release, output disposal, refund, or substitute event
```

No package field may weaken, replace, or select any value above.

## Literal Decision Table

`Contract fixed` means the approved row determines the value. `Mechanical`
means the value is deterministically derived only after the listed business
literal is approved. `Missing business decision` means a user must approve one
literal value; the candidate and recommendation are not facts and are not
package content.

| Field | Classification | Candidate value / source | Business effect and recommendation |
| --- | --- | --- | --- |
| `manifest_schema_version` / `platform_schema_version` | Contract fixed | `2` / `"1.0"`; existing approved INF-P v2 pair | Required exact schema pair. Keep these values. |
| `patch_id` and `package_identity.package_id` | Missing business decision | `package:industrial-facilities`; existing v1/v2 package lineage | Keeps the new content in the same named facility package while creating a distinct revision. Recommended. |
| `patch_revision_id` and `package_identity.package_revision` | Mechanical after package-id/version approval | `package:industrial-facilities:v3`; existing revision pattern | Creates a new immutable revision distinct from frozen v2. Recommended with `package_version=3.0.0`. |
| `patch_version` and `package_identity.package_version` | Missing business decision | `3.0.0`; next semantic version in the existing package lineage | Both fields must be byte-identical. Recommended only with the v3 revision candidate. |
| `author_id` | Missing business decision | `author:repo`; frozen v2 author identity | Identifies the accountable content author. Recommend continuity only if the approving business authority accepts it. |
| `trust_policy_ref` | Missing business decision | `trust:repo`; frozen v2 trust policy | Selects content admission trust, not a runtime authority. Recommend continuity only if explicitly approved. |
| source package revision on every platform definition/declaration/binding | Mechanical after package revision approval | `package:industrial-facilities:v3` | The v2 schema requires each local record to pin its own immutable package revision. |
| source and target definition set | Missing business decision | `definition:industrial-facilities-mill@1` and `definition:industrial-facilities-mill-reinforced@1`; frozen source semantics | Makes both the committed source kind and retained terminal kind explicit. Recommend this exact two-definition set, but do not treat v2 records as copied/frozen v3 content. |
| each `definition_schema_ref` | Missing business decision | `schema:industrial-facilities-facility@1`; frozen v2 definition shape | Keeps typed content in the existing facility schema. Recommend it only with explicit approval of the associated typed content. |
| source typed content | Missing business decision | `{ "facility_kind": "mill" }`; approved source fact | Declares the package-local source-kind content. Recommend exactly this value. |
| target typed content | Missing business decision | `{ "facility_kind": "mill_reinforced" }`; approved retained-kind boundary | Declares the package-local retained facility identity; it must not assert a lifecycle result or any external effect. Recommend exactly this value. |
| `declaration_ref` | Mechanical after package identity approval | `declaration:industrial-facilities-mill-reinforced-decommission@1`; existing row naming pattern | Names exactly one declaration for this row. |
| `outcome_family_ref` | Mechanical from the approved exact operation | `outcome:construction-facility-mill-decommission@1`; candidate in the approved contract | Names the lifecycle-only outcome; it cannot become a generic transform family. |
| `policy_revision_ref` | Missing business decision | `policy:industrial-facilities:mill-reinforced-decommission@1`; exact-row naming pattern | Pins the terminal lifecycle policy. Recommend this literal only with the approved no-compensation semantics. |
| `binding_ref` | Mechanical after package identity approval | `binding:industrial-facilities-mill-reinforced-decommission@1`; existing binding naming pattern | Permits one future exact-one read-only binding only. |
| `capability_ref` | Mechanical from the approved exact operation | `capability:construction-facility-mill-decommission@1`; candidate in the approved contract | Must later equal the separately approved immutable descriptor capability. This packet installs neither. |
| `eligibility_refs` | Contract fixed | `["construction:facility-mill-reinforced@1"]` | Non-empty owner-derived evidence family. No alternate eligibility may be substituted. |
| `requirement_ref` | Mechanical from the fixed eligibility family | `requirement:construction-facility-mill-reinforced@1`; approved naming pattern | Keeps one typed read requirement aligned with the closed source proof. |
| `predicate_family_ref` | Mechanical from the fixed eligibility family | `predicate:construction-facility-mill-reinforced@1`; approved naming pattern | Allows only Construction-derived proof facts, never caller proof or arbitrary lookup. |
| `subject_slot_ref` | Contract fixed | `slot:facility-project@1` | Requires the same committed facility and project binding. |
| `proposal_effect_types` | Mechanical from the approved exact operation | `["effect:construction-facility-mill-decommission@1"]`; effect naming pattern | A proposal label only; the later descriptor must own and exactly validate it. |
| `dependencies` | Missing business decision | `[]`; v2 manifest precedent | Recommended empty: frozen v2 is verification evidence, not a package-selected dependency or activation authority. Explicit approval is still required. |
| `dependency_and_conflict_refs` | Missing business decision | `[]`; v2 manifest precedent | Recommended empty: this row must not add package-level conflict/ordering semantics. Explicit approval is still required. |
| `event_schemas` | Contract fixed | `[]` | The event family is owner/descriptor fixed; package content cannot declare or choose it. |
| `replay_reader_refs` | Contract fixed | `[]` | Full/checkpoint-tail readers are Construction-owned and descriptor-bound; a package may not select them. |
| `verification_profile_refs` | Contract fixed | `[]` | A future independent Harness is implementation evidence, not package-controlled content. |
| `state_group_ids`, `state_group_migrations`, `rules` | Contract fixed | `[]`, `[]`, `[]` | This row declares no state-group, migration, or package rule authority. |
| `requested_capabilities`, `economic_outcomes`, `granted_effect_types`, `verification_profiles` | Contract fixed | `[]`, `[]`, `[]`, `[]` | The one typed binding request is inside `platform_extension`; no legacy capability, economic, effect grant, or profile payload is admitted. |
| author `declaration_digest` claim | Derived later, not a business literal | no value in this packet | The author claim is required only after every literal above is approved. The adapter excludes the claim, derives the expected digest, and rejects missing/malformed/mismatched/conflicting claims with zero writes. |
| outer `content_digest` claim | Derived later, not a business literal | no value in this packet | Derived only after all declarations are normalized with derived declaration digests; exclude only `content_digest`. Missing/malformed/mismatched/conflicting claims are zero-write. |

## One-Shot Approval Payload

The minimum approving decision is the set of all rows marked `Missing business
decision`, including explicit approval of both recommended empty arrays. The
approval must also confirm that the two proposed facility definition records
are newly authored v3 content and do not modify, recalculate, or reuse frozen
v2 bytes.

The approved literals were authored into the complete v3 record, validated
through the existing adapter, and frozen with its derived pins in the
[v3 decommission freeze record](2026-08-20-inf-1ah-industrial-facilities-v3-decommission-freeze-record.md).
Exact descriptor/catalog admission remains a separate gate.

## Rejection And Gate Preservation

Before those approvals, unknown or inactive package requests, digest mismatch,
multiple or unadmitted binding, missing/private/stale source evidence,
facility/project mismatch, revision conflict, active `ProductionRun`, and
duplicate/changed-duplicate intent remain zero-write. No default package,
implicit policy, caller-selected authority coordinate, or inferred lifecycle
state is permitted.

This packet leaves the frozen v2 source pins, all generic-operation prohibitions,
and the separate runtime/test/Harness gates unchanged.
