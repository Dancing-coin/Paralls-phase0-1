# INF-1AG Construction Candidate Owner-Admission Design

Status: `implemented and verified: exact frozen package-declared oven-to-kiln narrow vertical; generic transforms remain owner-contract blocked`

## Purpose And Boundary

This is the approved INF-1AG row contract after the terminal existing-owner
audits. It reads only committed Construction facts already owned by
`ConstructionProductionAuthority`; it is not a fourth discovery audit and its
implementation is limited to the exact frozen descriptor, package, and
owner-bound `oven -> kiln` vertical documented below.

The required candidate shape is:

```text
one committed source event or state -> one exact Construction outcome
```

The result now defines one fixed outcome family whose concrete source and target
are resolved only from an active immutable gameplay-package declaration. A
package declaration is data admitted with the package revision and content
digest; it is not a runtime registry, caller-selected transform, or writer.
No default source kind, target kind, eligibility, policy, event, scope, receipt,
fragment, or compensation rule is inferred below.

## Existing Construction Fact Boundary

`ConstructionProductionAuthority` already owns the canonical
`gameplay:construction_production:{facility_ref}` stream and projects only:

- `facility_acquired` into immutable facility identity, plot binding, kind,
  condition, and facility revision;
- `run_started` / `run_finished` into a production run and its committed recipe
  snapshot;
- maintenance state and obligation lifecycle facts; and
- the fixed `facility_repaired` / compensation and
  `facility_transformed(bakery -> bakery_reinforced)` outcomes.

It does not own plot title, permits, blueprints, materials, payments, inventory
output, work compensation, package policy registration, a clock, or a generic
facility-action vocabulary. The existing authority is the only possible owner
for a future owner-local facility or run outcome; none of the reviewed paths
requires a new owner. That fact does not make a new outcome admissible.

## Concrete Facility Transform Candidate List

These are the only three source kinds found in committed
`facility_acquired@1` fixtures and the corresponding facility projection.
Their acquisition event ids are instance-specific and must be read from the
store; no caller-supplied id is a candidate fact. Every row reuses the existing
Construction owner, stream pattern
`gameplay:construction_production:{facility_ref}`, and project-scoped facility
projection boundary. Those reusable boundaries do not admit a write.

| Candidate | Existing source kind | Target kind | Committed source/projection | Eligibility or policy evidence | Reusable owner / stream / privacy | Existing-row overlap | Terminal/reversal/compensation choice | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C-1 | `bakery` | `bakery_reinforced` | `gameplay.construction_production.facility_acquired@1` plus `ConstructionProductionProjection.facilities` | immutable `inf:construction-facility-bakery-reinforcement@1` and `policy:construction_bakery_reinforcement` | `ConstructionProductionAuthority`; `gameplay:construction_production:{facility_ref}`; project-scoped facility projection | exactly INF-1AF; must not be a new row | already terminal; no reversal, compensation, retry, or fanout | `duplicate/closed` |
| C-2 | `oven` | `kiln` | committed `facility_acquired@1` plus `ConstructionProductionProjection.facilities`; source kind and plot binding are read from the committed event/projection | approved row-specific `construction:facility-acquired@1` proof owned by `ConstructionProductionAuthority`; package policy `policy:industrial-facilities:oven-to-kiln@1` says committed `oven` acquisition is sufficient for this row only | `ConstructionProductionAuthority`; `gameplay:construction_production:{facility_ref}`; project-scoped facility projection | not INF-1AE, INF-1AF, due-finish, or work-completion evidence; no generic transform | target/policy/package/eligibility values are fixed by the approved row; canonical `content_digest` and declaration digest are frozen; v1 terminal/no-compensation is fixed | `implemented and verified` |
| C-3 | `mill` | `mill_reinforced`, frozen by the exact active v2 package | committed project-visible `facility_acquired@1` plus the same facility projection | immutable acquisition eligibility and policy are frozen for this row only | `ConstructionProductionAuthority`; `gameplay:construction_production:{facility_ref}`; project-scoped facility projection | not INF-1AE, INF-1AF, due-finish, or work-completion evidence; existing weather-to-maintenance rows are not transforms | exact v2 declaration, descriptor, digest, and v1 terminal/no-compensation only | `implemented narrow vertical` |

The `mill` row remains a candidate-only observation, not a contract. The
`oven -> kiln` row is now implemented only through its frozen package,
descriptor, and owner-bound runtime below. `facility_kind` remains a free
string on the acquisition model, and naming any other target by analogy would
create gameplay semantics not present in an approved package.

## 2026-08-19 Remaining Construction Candidate Revalidation

Status: `no new exact Owner-Admission candidate; one source observation remains design pending`

This is a documentation-only revalidation of the known
`ConstructionProductionAuthority` facts. It is not a fourth existing-owner
discovery audit. The audit checks whether an already committed source can be
paired with one exact, non-duplicate Construction outcome without inferring
business semantics. The result is **zero** new design-ready contracts.

| Reviewed path | Source and fences | Exact outcome / contract status | Required fixed operational boundary | Disposition and minimum business choice |
| --- | --- | --- | --- | --- |
| R-1 `mill` transform observation | committed project-visible `gameplay.construction_production.facility_acquired@1`, exact acquisition event stream revision, current `ConstructionProductionProjection.facilities[facility_ref]` revision, matching facility stream head and `facility_ref -> plot_ref` project binding | Historical pre-contract observation, now closed by the exact frozen `mill -> mill_reinforced` row. | The fixed owner, stream, event family, project privacy, authority-derived idempotency/receipt, and full/checkpoint-tail replay are implemented only for the v2 pins. Unknown package/kind/policy/evidence, stale/private evidence, binding/revision conflict, duplicate/multiple match, or caller authority coordinates remain zero-write. | No further action for this row; a new facility pair needs a new literal contract. Status: `implemented narrow vertical`. |
| R-2 due production completion | committed `run_started` plus the projected run/recipe snapshot and the owner-owned due obligation/revision fence | `gameplay.construction_production.run_finished` is already the exact completed-run outcome of `ConstructionDueCompletionPolicy` and existing due-finish fragments. | Existing Construction facility stream, project privacy, owner-derived idempotency, append-derived receipt, and full/checkpoint-tail replay already apply. A caller tick/run/recipe remains zero-write. | `duplicate/closed`; no business choice is requested because a new contract would duplicate an existing row and risks introducing a second scheduler path. |
| R-3 maintenance-state dispel | committed project-scoped `maintenance_state_applied` state plus its exact open maintenance obligation and stream/revision pins | `maintenance_state_dispelled` plus exact `maintenance_state_obligation_cancelled` is the existing INF-1P fixed action vector. | Existing Construction facility stream, project privacy, one owner append receipt, full/checkpoint-tail replay, and explicit cancellation semantics already apply. Arbitrary state/effect, stream, cancellation reason, compensation, or retry is zero-write. | `duplicate/closed`; no business choice is requested because INF-1P already owns this fixed state-action consequence. |

`R-1` is intentionally a source observation rather than a candidate carrying a
placeholder outcome id. A capability or outcome identifier would claim an
exact target fact that the existing projection, immutable packages, and formal
specifications do not define. It cannot advance to RED tests, a catalog row,
manifest content, Harness, or runtime until the minimum business choice above
is approved as one exact Owner-Admission Contract.

## 2026-08-20 Mill Row-Specific Pre-Contract Gate

Status: `design-stage active; contract approval pending; no runtime admission`

This section narrows the next INF-1AG candidate without treating an incomplete
row as approved. It uses the fixed source and Construction boundary supplied
for this design stage. It does **not** infer a target kind, target semantic,
package identity, policy, eligibility, capability id, outcome id, descriptor,
or catalog row.

### Fixed base, not business choices

```text
source_kind       = mill
source_event      = gameplay.construction_production.facility_acquired@1
source_visibility = project
owner             = ConstructionProductionAuthority
target_stream     = gameplay:construction_production:{facility_ref}
event_family      = gameplay.construction_production.facility_transformed@1
privacy           = project
```

The source must be an exact committed `facility_acquired` event on the fixed
facility stream, whose `facility_ref`, `plot_ref`/project binding and
`facility_kind=mill` agree with the current Construction projection. Its
committed acquisition-event stream revision, current facility revision, and
facility stream head are the required pre-append revision fences. These pins
are derived by the owner; the proposal cannot supply an alternate event,
stream, revision, privacy, receipt, or fragment.

The existing Construction contract fixes the append-derived
`GameplayEventStore.append_batch()` receipt and the Construction projector for
full and checkpoint-tail replay. The idempotency **shape** is authority-derived
from the eventual immutable package/declaration/content pins plus facility,
acquisition-event and prior-facility-revision pins. It cannot be finalized
until the missing immutable identity fields below exist, and it cannot be
caller-selected.

### Exact missing fields and minimum business choices

| Missing field or decision | Why existing facts do not determine it | Minimum business choice required for a later exact contract |
| --- | --- | --- |
| `target_kind` | `Facility.facility_kind` is an unconstrained string and the current projector has no `mill` successor rule. | One literal target `facility_kind`, not a pattern, default, or caller input. |
| target semantic | A different kind name alone does not establish what Construction fact changes or what remains outside it. | State that the row changes only the Construction facility-kind identity from `mill` to the named target, and enumerate any excluded facts. Any material, payment, output, permit, technology, or inventory meaning must remain excluded unless separately admitted. |
| `capability_ref` and `outcome_family_ref` | These ids would assert a concrete admitted operation before the target semantics exist. | One exact capability id and one exact outcome id bound solely to this literal source/target row, not a generic transform family. |
| immutable package identity | No active package currently declares a `mill` transform. | `package_id`, immutable `package_revision`, `patch_version`, `package_version`, and the schema/platform version pair. |
| declaration identity and normalized pins | There is no declaration to bind to a target and policy. | `declaration_ref`, author-supplied `declaration_digest` claim, adapter-derived declaration digest, and normalized record membership for the content digest. |
| content identity | A digest cannot be inferred from a proposed or partial declaration. | Frozen canonical manifest bytes and adapter-derived/validated `content_digest` after all normalized declarations exist. |
| policy identity | No existing policy says why a committed mill qualifies for a particular target. | One fixed `policy_ref` and `policy_revision`, with no caller policy selection. |
| eligibility contract | Acquisition proves only facility identity, kind, project binding, and revision; it does not imply permits, technology, materials, payment, or another eligibility fact. | Non-empty `eligibility_refs` and their approved predicate/evidence mapping. For each ref: existing owner, committed event/projection kind, exact revision-pin rule, project privacy rule, and proof binding to both `facility_ref` and `project_ref`. |
| descriptor and read-only binding pins | The existing oven descriptor cannot be reused for a different package declaration or target. | Exact immutable `OwnerOperationDescriptor` id/revision and one governed catalog row, admitted only after the package content is frozen and separately approved. |
| terminal/reversal/compensation semantics | Existing repair compensation cannot define transform semantics; no `mill` transform exists. | Explicitly choose `v1 terminal/no-compensation`, or define an alternative exact lifecycle before approval. Reversal, downgrade, retry-as-new-transform, compensation, fanout, and combined receipt remain prohibited unless separately admitted. |

### Fail-closed rule before approval

Until every field above has an approved literal value, `mill` requests have no
admitted capability or outcome and must perform zero writes. In particular,
unknown or inactive package, absent/invalid/mismatched digest claim, unknown
target, missing/ambiguous/stale/private eligibility evidence, facility/project
binding conflict, acquisition/facility/stream revision conflict, duplicate or
multiple declaration match, and caller-selected authority coordinates remain
zero-write before `GameplayEventStore.append_batch()`.

This pre-contract gate authorizes no manifest freeze, descriptor/catalog
admission, verifier, reducer, event, RED test, Harness, or runtime path. The
next user action is approval of one complete literal `mill -> target_kind`
Owner-Admission Contract containing the choices above.

## 2026-08-20 Mill Reinforcement Owner-Admission Contract (Approved)

Status: `implemented narrow vertical: exact frozen mill-to-mill_reinforced row verified`

This is the approved contract for the user-confirmed literal
`mill -> mill_reinforced` row. Its separately authorized package, descriptor,
read-only binding, verifier, reducer, test, Harness, and append gates are now
implemented only for this exact row.

### Identity and authority boundary

```text
capability_id        = capability:construction-facility-mill-reinforcement@1
outcome_family       = construction_facility_mill_reinforcement@1
outcome_family_ref   = outcome:construction-facility-mill-reinforcement@1
declaration_ref      = declaration:industrial-facilities-mill-to-mill-reinforced@1
binding_ref          = binding:industrial-facilities-mill-to-mill-reinforced@1
policy_ref           = policy:industrial-facilities:mill-to-mill-reinforced
policy_revision      = policy:industrial-facilities:mill-to-mill-reinforced@1
descriptor_id        = descriptor:construction-facility-mill-reinforcement@1
descriptor_revision  = descriptor:construction-facility-mill-reinforcement@1
catalog_contract_ref = inf:construction-facility-mill-reinforcement@1
proposal_effect_type = effect:construction-facility-mill-reinforcement@1
package_id           = package:industrial-facilities
package_revision     = package:industrial-facilities:v2
```

Every identifier above is an **approved exact contract literal**. They are not
yet package content, catalog data, or runtime coordinates: the later
content/freeze and descriptor/catalog gates remain independent. Neither caller,
agent, package author nor runtime can select an alternative owner, stream,
event, revision, privacy, receipt, replay reader, compensation rule, or
settlement fragment.

Construction owns exactly one fact: the terminal facility identity transition
from `mill` to `mill_reinforced`, including the one facility revision advance,
on the existing facility stream. It does not own or create weather immunity,
maintenance state/obligation/result, materials, inventory, payment, production
output, recipe, permit, technology, license, or another-domain fact.

### Fixed source, proof, event and replay contract

```text
source_event          = gameplay.construction_production.facility_acquired@1
source_kind           = mill
target_kind           = mill_reinforced
project_binding       = construction_plot_as_project@1
target_stream         = gameplay:construction_production:{facility_ref}
event_family          = gameplay.construction_production.facility_transformed@1
privacy               = project
eligibility_ref       = construction:facility-acquired@1
predicate_family_ref  = predicate:construction-facility-acquired@1
requirement_ref       = requirement:construction-facility-acquired@1
subject_slot_ref      = slot:facility-project@1
```

The sole owner-derived eligibility proof is non-empty and maps only to the
existing `ConstructionProductionAuthority` source event. It binds
`facility_ref` to committed `facility_acquired.facility_ref` and `project_ref`
to committed `facility_acquired.plot_ref`; it pins the exact acquisition-event
stream revision, current projected facility revision, and target facility-stream
head. The event and proof must both be project-visible. It cannot assert a
permit, technology, payment, material, weather, maintenance or other fact.

The fixed one-event vector is:

```text
gameplay.construction_production.facility_transformed@1 {
  facility_ref,
  project_ref,
  prior_kind = mill,
  next_kind = mill_reinforced,
  acquisition_event_id,
  acquisition_event_revision,
  expected_stream_revision,
  prior_facility_revision,
  facility_revision = prior_facility_revision + 1,
  capability_id,
  outcome_family_ref,
  package_revision,
  content_digest,
  declaration_ref,
  declaration_digest,
  policy_ref,
  policy_revision,
  descriptor_id,
  descriptor_revision,
  active_set_revision
}
```

All payload values are authority-derived from the active normalized package,
read-only binding, source proof or current projection. There is exactly one
project-scoped outbox projection and exactly one receipt: the append-derived
result from `GameplayEventStore.append_batch()`. Full replay and
checkpoint-tail replay use the existing Construction projector; its future
branch must accept only this complete pinned vector and must not turn
`facility_transformed` into arbitrary kind-to-kind handling.

The proposed authority-derived idempotency key is fixed as:

```text
construction:facility-mill-reinforcement:
  package:industrial-facilities:v2:content_digest:declaration_digest:
  descriptor_revision:facility_ref:acquisition_event_id:
  acquisition_event_revision:prior_facility_revision
```

Its literal digest and revision components come only from normalized/active
state. A supplied, changed, or partially derived key is not accepted as an
alternative authority coordinate.

### Digest and activation-pin order

1. The v2 author input includes untrusted `declaration_digest` and
   `content_digest` claims; it contains the proposed exact declaration and
   binding, not authority-shaped fields.
2. The existing adapter canonicalizes the declaration payload with only its
   `declaration_digest` excluded, derives the expected digest, compares the
   claim exactly, and stores only the derived normalized declaration digest.
3. After all declarations normalize, the adapter derives the outer content
   digest from the complete v2 record with only `content_digest` excluded and
   compares its claim exactly. Missing, malformed, mismatched or conflicting
   claims are zero-write.
4. Candidate validation checks structure and both derived pins without
   mutation. The later existing `compose_active_set()/activate()` path resolves
   exactly one approved immutable descriptor and persists the package revision,
   content digest, declaration digest, descriptor id/revision and active-set
   revision.
5. Only a later approved Construction verifier may combine those activation
   pins with the source proof, facility/project binding and revision fences
   before building the fixed one-event owner fragment.

`package:industrial-facilities:v1` and its frozen bytes/digests are expressly
unrelated to this v2 candidate and must not be modified.

### Terminal and fail-closed semantics

V1 is terminal and has no reversal, downgrade, reopen, retry-as-new-transform,
compensation, fanout, combined receipt, payment, material, production-output,
weather or maintenance semantics. A retry may only be the exact idempotent
replay of the same committed result; a changed duplicate is zero-write.

Before candidate/active mutation or owner append, all of the following are
zero-write: unknown or inactive package; missing/malformed/mismatched digest;
unknown or non-`mill` kind; zero, multiple, mismatched or unadmitted binding;
missing, private, forged, ambiguous or stale eligibility evidence; facility/
project binding conflict; acquisition/facility/stream revision conflict;
duplicate declaration; already transformed facility; and any caller-selected
authority coordinate, target, policy, event, privacy, receipt, fragment,
compensation or additional domain payload.

### Explicit implementation hold

The implementation scope remains one fixed row. No manifest schema change,
other package revision, generic transform, catalog writer, router,
coordinator, settlement authority, or additional Construction outcome is
authorized by this section.

### Minimum User Decisions (Historical)

For C-1, no further decision is requested: it is already closed by INF-1AF and
must not be reopened as INF-1AG. C-2 is implemented and verified as the exact
frozen `package:industrial-facilities:v1` `oven -> kiln` row. C-3's formerly
required package declaration and row-specific approval are now closed by the
frozen v2 mill row. Its former minimum fields were:

1. one declaration inside an active immutable package revision containing the
   literal `source_kind`, literal `target_kind`, and `eligibility_refs`;
2. the package `policy_revision`, `package_revision`, and canonical
   `content_digest`, with eligibility references resolving to committed facts;
3. confirmation that the source is `facility_acquired@1` plus the current
   facility projection/revision fence, unless a separately approved source
   projection is named; and
4. no caller-selected owner/stream/event/privacy/receipt/fragment and no
   compensation override; v1 terminal/no-compensation semantics are fixed.

The C-3 declaration and eligibility references now exist in the frozen v2
record. C-2 and C-3 each retain their separate catalog entries, RED tests,
Harnesses, and fixed runtime writes; neither generalizes the other.

## Package-Declared Facility Transform Contract (Design Only)

This design is subordinate to the foundation
[Package Content And Cross-Domain Binding Matrix](../../character-gameplay-foundation/2026-08-17-package-content-and-cross-domain-binding-matrix-design.md).
The manifest record shapes and legacy-model boundary are further closed by
[Package Contract Closure And Manifest Adapter](../../character-gameplay-foundation/2026-08-17-package-contract-closure-and-manifest-adapter-design.md).
The matrix defines which declaration data may come from a package and which
owner/replay/privacy fields remain fixed by Construction. INF-1AG does not
create a second package schema or a generic package binding registry.

The design-only author workflow is captured in the separate
[Facility-Transform Content-Authoring Packet](2026-08-18-inf-1ag-facility-transform-content-authoring-packet-design.md).
It may prepare an auditable candidate, but it cannot admit a package row or
replace the later row-specific approval gate.

The fixed capability/outcome family is
`capability:construction-facility-package-declared-transform@1` /
`construction_facility_package_declared_transform@1`. It is one owner-local
outcome family, not a generic `facility_kind -> facility_kind` API. The active
immutable package revision supplies the finite declaration below; the caller
cannot supply or alter any of these values:

```text
FacilityTransformDeclaration
  source_kind
  target_kind
  eligibility_refs[]
  policy_revision
  package_revision
  content_digest
```

The declaration is validated as part of the immutable package/active-revision
boundary. It is not runtime-writable, does not select an owner or stream, and
does not contain executable code, a router, a registry, a settlement fragment,
or compensation instructions.

The declaration schema must reject `owner_ref`, `stream_id`, `event_type`,
`privacy_scope`, `receipt_reader_ref`, `compensation_policy`,
`settlement_fragment`, and router/coordinator fields. Those values are fixed by
this owner contract or derived from the existing authority; they are never
package or caller inputs.

### Canonical declaration schema and digest (design closure)

The six package-declared fields are the complete declaration payload. The
package does not add a caller-visible declaration id or digest field:

```text
FacilityTransformDeclarationPayload
  source_kind: non-empty UTF-8 string
  target_kind: non-empty UTF-8 string
  eligibility_refs: sorted, unique non-empty reference strings
  policy_revision: immutable policy reference
  package_revision: exact active GameplayPatchManifest.patch_revision_id
  content_digest: exact active GameplayPatchManifest.content_digest
```

The `eligibility_refs` order is canonicalized lexicographically and duplicate
references are invalid. `source_kind == target_kind` is invalid, and the
already closed `bakery -> bakery_reinforced` pair cannot be admitted again by
INF-1AG.

The authority derives, rather than accepts, the declaration digest:

```text
declaration_digest = sha256:<hex>
canonical input = {
  "content_digest": content_digest,
  "eligibility_refs": sorted(eligibility_refs),
  "package_revision": package_revision,
  "policy_revision": policy_revision,
  "source_kind": source_kind,
  "target_kind": target_kind
}
```

The canonical encoding is the existing Patch convention: JSON with
`ensure_ascii=false`, sorted keys, no insignificant whitespace, encoded as
UTF-8, and prefixed with `sha256:`. `declaration_digest` may be retained in a
typed proposal, receipt, and authority event as derived evidence, but it is
never caller-selected or independently package-authored.

An active patch-set may contain at most one declaration for a given
`(source_kind, target_kind)` pair. Two declarations with that pair but
different eligibility or policy payloads are an activation conflict, not a
load-order choice. A declaration duplicated with the same canonical payload
is rejected as a duplicate. Across active packages there is likewise no
last-write-wins rule; an ambiguous match is zero-write.

The direct Construction intent contains only the facility identity and normal
causation/correlation context. It does not contain a target kind, package
revision, content digest, declaration digest, owner, stream, event, privacy,
receipt, or policy. A package-originated typed proposal may carry the derived
`declaration_digest`; Construction must re-derive it from the active manifest
before accepting the proposal.

### Row-specific eligibility proof contract (design closure)

`eligibility_refs[]` remain opaque until a separately admitted Construction row
names the accepted reference families and their existing owners. The
row-specific verifier returns this proof shape; it is not a generic registry
or cross-domain resolver:

```text
FacilityTransformEligibilityProof
  eligibility_ref
  facility_ref
  project_ref
  evidence_owner_ref
  evidence_kind
  evidence_event_id_or_digest
  evidence_revision
  privacy_scope
  source_policy_revision
  source_package_revision
  proof_digest
```

`proof_digest` is derived from the other fields with the same canonical digest
algorithm. The verifier must enforce that the owner and accepted event kind
are fixed by the row-specific contract; that the proof is about the requested
facility and project; that the evidence revision is the expected committed
revision; that the package and policy revisions match the declaration; and
that the returned privacy scope is project-visible and authorized for this
command. The caller supplies none of those authority coordinates.

The verifier rejects an unknown reference family, missing or revoked evidence,
owner/event mismatch, subject mismatch, stale revision, policy/package digest
mismatch, private-scope conflict, duplicate reference, or forged digest before
`append_batch()`. Construction consumes the proof but does not become the
owner of the referenced fact. Until a concrete package chooses an accepted
reference family and its existing owner/event revision, this proof contract is
specified but not implementable.

`eligibility_refs[]` are opaque references, not caller or package-selected
authority coordinates. A later approved resolver must map each reference to an
existing owner's committed evidence and return its owner-derived event kind,
event/projection revision, privacy scope and evidence digest. Missing,
ambiguous, stale, revoked or scope-incompatible resolution is zero-write;
Construction only consumes the resolved proof and never becomes its owner.

| Contract field | Fixed design rule |
| --- | --- |
| owned facts | Construction owns facility kind, facility revision, acquisition binding, and the terminal transform event on the facility stream |
| non-owned facts | package activation/digest, permits, blueprints, materials, payment, inventory output, plot title, clocks, and compensation truth remain outside Construction; opaque eligibility refs must resolve to already committed owner facts with owner-derived event/revision/privacy/digest pins |
| command surface | typed facility transform intent identifies only the facility and correlation/idempotency context; active package revision is resolved by authority context, never selected by caller |
| source | committed `gameplay.construction_production.facility_acquired@1` and current `ConstructionProductionProjection.facilities` entry; acquisition event id/revision is read from the store |
| source revision fence | acquisition event revision, current facility revision, and current facility-stream head must all match the pre-append projection; source kind must equal the package declaration |
| target stream | `gameplay:construction_production:{facility_ref}` fixed by Construction owner |
| event family | `gameplay.construction_production.facility_transformed@1` fixed; payload carries resolved prior/next kinds, source event id/revision, facility revisions, policy/package revision and content digest |
| write revision | one atomic append at expected stream head; facility revision advances by exactly one |
| privacy | source, event, authority receipt and project projection are `project`; no broader or caller-selected scope is admitted |
| idempotency | `construction:facility-transform:{package_revision}:{content_digest}:{facility_ref}:{acquisition_event_id}:{prior_facility_revision}`; all components are authority-derived |
| receipt | append-derived `GameplayEventStore.append_batch()` receipt containing committed event ids and revisions; outbox exposes only the fixed project-safe facility fields |
| replay | full replay rebuilds the facility projection from all committed events; checkpoint-tail replay starts from an authority-created checkpoint and applies only the remaining committed tail, with package/digest and event payload pins revalidated |
| terminal semantics | one successful declaration is terminal for v1; no retry-as-new-transform, downgrade, reopen, reversal, compensation, fanout, or combined receipt |
| zero-write | unknown/inactive package revision, digest mismatch, unknown source or target kind, missing/unresolvable eligibility ref, stale source/facility/stream revision, privacy conflict, malformed declaration, caller-selected owner/stream/event/policy, or duplicate intent rejects before `append_batch()` |

The exact package source/target pair is therefore not pre-fixed by the
Construction base. It is fixed per active immutable declaration and becomes
admissible only when all references resolve to committed facts and the
authority's source/revision/privacy fences pass. A package with no declaration
for a facility kind remains zero-write; no default kind or implicit policy is
allowed.

### Current design blockers

1. The runtime `GameplayPatchManifest` currently has no
   `facility_transform_declarations` field or declaration digest validator;
   this document now fixes the design shape and canonical digest, but the
   runtime schema remains absent.
2. No existing immutable eligibility-reference verifier is defined for the
   Construction owner; this document now fixes the accepted
   `construction:facility-acquired@1` family, owner, committed event and
   revision/binding pins for C-2, but no verifier exists and implementation is
   gated on the manifest digest freeze.
3. The Construction projector currently accepts only the committed bakery
   pair, so package-resolved non-bakery kinds have no admitted reducer rule.
4. No package-specific immutable catalog admission row exists for this family;
   this design stage intentionally does not create one.
5. The row-specific `package:industrial-facilities:v1` design is now approved,
   but its complete immutable manifest and canonical `content_digest` are not
   yet frozen or user-reconfirmed. The only executable package manifest
   currently present is `package:frost-farm` at `package:frost-farm:v1` with
   digest `sha256:frost-farm-v1`, and it declares no facility transform. The
   former foundation `oven -> kiln` example is superseded by the exact row
   contract below, but it is not executable content until the industrial
   manifest digest gate is closed.

These are formal blockers, not permission to add a generic registry, writer,
router, or runtime owner. They must be closed in the later approved plan before
RED tests or implementation.

## Reviewed Paths

### 1. Package-Declared Facility Transform

The event relationship is fixed as a design family; literal kind values remain
package data and are intentionally not hard-coded by the Construction base:

```text
committed facility_acquired(facility_kind)
  -> facility_transformed(prior_kind, next_kind)
```

The current projector rejects every transform other than committed
`bakery -> bakery_reinforced`. A future implementation must add a declaration-
validated reducer branch, not loosen that check into a generic transform. The
package supplies the pair, while the base still fixes owner, stream, event
family, privacy, receipt, replay and terminal boundaries.

| Required contract field | Current fact | Missing, non-inferable decision |
| --- | --- | --- |
| capability id and owned fact | Construction owns facility kind/revision | package declaration schema and declaration digest |
| non-owned facts | plot title, permits, blueprint, materials, payment, and production output are outside Construction | whether any of those facts are a required committed eligibility source, and their existing owner/event pins |
| committed source and source revision | `facility_acquired` records a generic string kind on the facility stream | active package declaration, source event id/revision and current facility revision fence |
| target stream and write revision | the facility stream and its head/revision are known | fixed facility stream, one append at expected head, facility revision +1 |
| fixed event vector and privacy | project scope and one `facility_transformed` event exist for bakery reinforcement | package-resolved payload under fixed `facility_transformed@1` and project scope |
| idempotency | bakery reinforcement has a pair-specific key | authority-derived package/content/source digest key |
| receipt and replay | current receipt/projector reconstruct only the bakery pair | append-derived receipt plus declaration-pinned full/checkpoint-tail replay |
| terminal/reversal/compensation | bakery reinforcement is terminal; repair compensation affects only condition | v1 terminal/no-compensation is fixed; no caller override |

Minimum package admission choice: declare one literal source/target pair,
eligibility references, policy revision, package revision and content digest in
an active immutable package, then provide the owner/revision-pinned resolver
for each eligibility reference. The base contract fields above do not vary by
package and cannot be caller-selected.

### 2. Due Production Completion

Potential shape:

```text
committed run_started(finish_tick, recipe snapshot)
  -> gameplay.construction_production.run_finished
```

This is not a new candidate. `ConstructionDueCompletionPolicy` and the
existing due-finish fragments already own the fixed completed-run outcome; the
frost consumer contracts reuse that owner-local result without changing it.
The direct helper accepts run, recipe, and tick inputs, so treating it as a new
agent-facing capability would require a canonical time trigger and fixed
selection rule. No clock or scheduler may be introduced, and an unpinned
caller-supplied tick, run, or recipe is not admissible.

The source, target stream, `run_finished` event family, project privacy,
idempotency, append receipt, full replay, checkpoint-tail replay, and terminal
completed-run semantics are already owned by the existing fixed row. A new
contract would duplicate that row rather than discharge an INF-1 blocker.

### 3. Completed Worker Evidence

Potential shape:

```text
committed run_finished + committed worker contribution from run_started
  -> gameplay.construction_production.work_completion_evidence_recorded
```

This is not a new candidate. The existing INF-4Z source contract already pins
the finished event, contribution digest, same production stream revision, and
actor-only projection. It has the fixed append-derived receipt and full/
checkpoint-tail replay reader consumed by the approved INF-4T wage vertical.
Re-designing it under INF-1 would duplicate an implemented Construction outcome
and would not produce a new facility action.

## Required Zero-Write Boundary

Until the declaration schema, eligibility resolver and reducer admission are
approved and implemented, all of the following
remain zero-write before `GameplayEventStore.append_batch()`:

- a caller-selected facility source/target kind, stream, event family,
  revision, privacy scope, receipt, fragment, policy, retry, reversal, or
  compensation rule;
- a non-bakery use of `facility_transformed` without a validated active package
  declaration and admitted reducer;
- a `run_started` completion request that supplies a tick, run, or recipe as a
  replacement for an admitted due-completion trigger; and
- a second work-evidence contract or an attempt to use work evidence as a
  generic action/transform source.

This preserves the isolation from generic Construction actions and transforms:
`SettlementPlan` remains composition-only, and neither the catalog nor any
new helper may become a writer, router, registry, coordinator, or settlement
authority.

## Next Admission Condition (Historical Pre-Implementation Gate)

The row-specific contract was initially approved for design only. The complete
manifest freeze, digest verification, descriptor admission, RED-to-green tests,
Harness, verifier, reducer, and runtime gates were subsequently completed for
the frozen `oven -> kiln` row. Any other package declaration still requires a
new package-local freeze and separate row-specific approval.

## Approved INF-1AG Row-Specific Contract (Historical Design Record)

The following exact row was approved as a design contract before its separate
manifest, descriptor, test, Harness, and runtime gates. The current status is
recorded at the top of this document and applies only to the frozen row.

### Fixed row identity and owned fact

```text
outcome_family  = construction_facility_package_declared_transform@1
capability_ref  = capability:construction-facility-package-declared-transform@1
package_id      = package:industrial-facilities
package_revision= package:industrial-facilities:v1
source_kind     = oven
target_kind     = kiln
policy_ref      = policy:industrial-facilities:oven-to-kiln
policy_revision = policy:industrial-facilities:oven-to-kiln@1
```

The target semantic is a one-time high-temperature production-facility
identity upgrade from `oven` to `kiln`. Construction owns only the facility
kind transition and its committed facility revision. This row creates no
material, inventory, payment, production output, permit, technology, license,
or other-domain fact. The package policy says that a committed acquisition of
the declared `oven` is sufficient for this row; it is not a permit,
technology, material, payment, or generic eligibility assertion.

### Package declaration and digest gate

The active immutable `GameplayPatchManifest` must contain the exact declaration
for the six package fields already fixed by this design:

```text
source_kind      = oven
target_kind      = kiln
eligibility_refs = [construction:facility-acquired@1]
policy_revision  = policy:industrial-facilities:oven-to-kiln@1
package_revision= package:industrial-facilities:v1
content_digest   = <derived from the complete immutable manifest canonical JSON>
```

`content_digest` is intentionally not filled by this document. It must be
derived by the existing `GameplayPatchManifest` canonical JSON rules after the
complete immutable `package:industrial-facilities:v1` manifest is frozen. A
caller, package author, agent, or this design may not invent or select it.
The resulting digest must be recorded in the row-specific implementation
evidence and reconfirmed by the user before any runtime implementation gate
opens. A digest mismatch, missing digest, inactive revision, or declaration
canonicalization conflict is zero-write.

### Existing-owner eligibility and project binding

```text
eligibility_ref_family = construction:facility-acquired@1
eligibility_refs       = [construction:facility-acquired@1]
existing_owner         = ConstructionProductionAuthority
evidence_kind          = gameplay.construction_production.facility_acquired@1
project_binding_rule   = construction_plot_as_project@1
project_ref            = committed facility_acquired.plot_ref
facility_ref           = committed facility_acquired.facility_ref
privacy                = project-scoped
```

The owner-derived proof must bind the same `facility_ref` and `project_ref`,
with source `facility_kind=oven`. Its revision vector must exactly pin the
committed acquisition-event stream revision, current facility revision, and
facility stream head. The facility reference, plot/project binding, and source
kind must all agree with the current Construction projection. This row-specific
plot binding is not a global project model and cannot be selected by caller,
package, or agent.

### Fixed write and evidence contract

The existing Construction owner fixes every authority coordinate:

```text
owner          = ConstructionProductionAuthority
target_stream  = gameplay:construction_production:{facility_ref}
event_family   = gameplay.construction_production.facility_transformed@1
privacy_scope  = project-scoped
write_revision = one append at the expected facility-stream head; facility revision +1
```

The event vector contains one `facility_transformed@1` event whose prior kind
is `oven`, next kind is `kiln`, and whose payload carries only authority-
derived source event/revision, facility revision, package/policy revision,
content digest, declaration digest, and the bound facility/project identity.
The idempotency key remains authority-derived:

```text
construction:facility-transform:
  package_revision:content_digest:facility_ref:
  acquisition_event_id:prior_facility_revision
```

The receipt is the append-derived `GameplayEventStore.append_batch()` receipt.
The project-scoped outbox exposes only the fixed safe facility fields. Full
replay rebuilds the facility projection from committed events. Checkpoint-tail
replay starts from an authority-created checkpoint and applies the committed
tail only after package/digest, source, proof, and revision pins are
revalidated.

### Terminal and zero-write semantics

V1 is terminal and has no reversal, downgrade, retry-as-new-transform,
reopen, compensation, fanout, combined receipt, payment, material, or
production-output vector. `bakery -> bakery_reinforced` remains the closed
INF-1AF row and cannot be admitted through this capability.

Before `GameplayEventStore.append_batch()`, the operation must perform zero
writes for unknown or inactive package/revision, missing or mismatched
canonical digest, unknown kind, missing/ambiguous/stale/private or forged
`facility_acquired` evidence, facility/project binding conflict, source or
stream revision conflict, duplicate or ambiguous declaration, a non-`oven`
source, a prior transform, caller-selected authority coordinates, or any
request that supplies payment, material, permit, technology, output,
compensation, reversal, or target-selection semantics. No default target,
implicit project, implicit policy, or caller-selected digest is permitted.

### Implementation gate (Completed)

The row-specific design is approved and implemented. The complete immutable
manifest is frozen with separately approved equal outer/inner version values,
and its declaration/content digest evidence is recorded in the
[2026-08-19 freeze record](2026-08-19-inf-1ag-industrial-facilities-v1-freeze-record.md).
The exact immutable descriptor/catalog row and read-only binding admission were
subsequently approved. The owner-bound verifier, declaration-validated reducer,
focused RED-to-green tests, independent Harness, and one append-only vertical
were then implemented for this row only. Evidence is `12 passed` in
`backend/tests/test_infra_construction_facility_package_transform.py` and a
green `infra-construction-facility-package-transform` Harness. This closes only
the frozen `oven -> kiln` row; it does not authorize a generic transform,
additional package declaration, or broader August INF completion claim.

## 2026-08-20 Mill v2 Package-Content / Read-Only-Binding Decision

Status: `completed historical authoring decision; frozen v2 record verified`

This table is the complete decision surface for a future immutable
`GameplayPatchManifest` v2 record. It deliberately contains no manifest bytes,
no digest claim, and no implicit empty array. The frozen
`package:industrial-facilities:v1` record is unrelated and must not be changed.

### Fixed outer identity and schema pair

```text
patch_id                    = package:industrial-facilities
patch_revision_id           = package:industrial-facilities:v2
manifest_schema_version     = 2
platform_schema_version     = 1.0
package_id                  = package:industrial-facilities
package_revision            = package:industrial-facilities:v2
```

`patch_version` is a distinct required outer v2 field and exactly equals inner
`package_version`: both are frozen as `2.0.0`.

### Non-admitted manifest decision table

| Manifest path / contract field | Candidate value or fixed contract rule | Source | Freeze status |
| --- | --- | --- | --- |
| `patch_version` / `platform_extension.package_identity.package_version` | `2.0.0` / `2.0.0` | v2 manifest model and platform schema pair | frozen |
| `author_id` | `author:repo` | existing trusted-author policy | frozen |
| `trust_policy_ref` | `trust:repo` | existing package trust policy | frozen |
| `platform_extension.package_definitions[0]` for `mill` | `definition:industrial-facilities-mill@1`, `schema:industrial-facilities-facility@1`, `{"facility_kind":"mill"}` | approved source semantic | frozen |
| `platform_extension.package_definitions[1]` for `mill_reinforced` | `definition:industrial-facilities-mill-reinforced@1`, `schema:industrial-facilities-facility@1`, `{"facility_kind":"mill_reinforced"}` | approved target semantic | frozen |
| `platform_extension.outcome_declarations[0].declaration_ref` | `declaration:industrial-facilities-mill-to-mill-reinforced@1` | approved Owner-Admission Contract | fixed, but needs both definition refs |
| `.outcome_family_ref` | `outcome:construction-facility-mill-reinforcement@1`, the sole schema-valid reference for `construction_facility_mill_reinforcement@1` | approved Owner-Admission Contract | fixed |
| `.definition_refs` | `[definition:industrial-facilities-mill-reinforced@1, definition:industrial-facilities-mill@1]` in canonical author order | declaration schema | frozen |
| `.eligibility_refs` | `[construction:facility-acquired@1]` | approved Owner-Admission Contract | fixed and non-empty |
| `.policy_revision_ref` | `policy:industrial-facilities:mill-to-mill-reinforced@1` | approved Owner-Admission Contract | fixed |
| `.source_package_revision` | `package:industrial-facilities:v2` | approved Owner-Admission Contract | fixed |
| `.declaration_digest` | `sha256:73d3313283bf584254281a2ca1b60d888585f6ba89e6370a30d622e4529b1bc8`; untrusted claim exactly matched adapter derivation | approved platform digest contract | frozen and verified |
| `platform_extension.capability_binding_requests[0].binding_ref` | `binding:industrial-facilities-mill-to-mill-reinforced@1` | approved Owner-Admission Contract | fixed |
| `.capability_ref` / `.declaration_ref` / `.source_package_revision` | `capability:construction-facility-mill-reinforcement@1`; the fixed declaration ref; `package:industrial-facilities:v2` | approved Owner-Admission Contract | fixed |
| `.typed_read_requirements[0]` | `requirement:construction-facility-acquired@1`, `predicate:construction-facility-acquired@1`, `slot:facility-project@1` | approved owner-derived eligibility contract; proof must bind committed `facility_ref` and `project_ref=plot_ref` | fixed; no caller proof |
| `.proposal_effect_types` | `[effect:construction-facility-mill-reinforcement@1]`; this is a package request that must exactly match the future immutable descriptor-owned vector | approved Owner-Admission Contract | fixed, not a new effect authority |
| outer `dependencies` | `[]` | outer manifest schema; no dependency is part of this exact row | frozen |
| `platform_extension.dependency_and_conflict_refs` | `[]` | platform extension schema; no dependency/conflict is part of this exact row | frozen |
| outer `event_schemas`, `state_group_ids`, `state_group_migrations`, `rules`, `requested_capabilities`, `economic_outcomes`, `granted_effect_types`, `verification_profiles` | each is explicitly `[]` | outer manifest schema and the fixed no-extra-domain boundary | frozen |
| `platform_extension.replay_reader_refs` | `[]`; replay authority remains descriptor-owned by `ConstructionProductionAuthority.projector` | replay contract | frozen |
| `platform_extension.verification_profile_refs` | `[]`; the independent Harness is verification evidence, not package-selected authority data | verification contract | frozen |
| outer `content_digest` | `sha256:8deea88c5e49c2aa06f30bbf1bd78ed103e26d8fb31769fe5564dbb7cc279896`; untrusted claim exactly matched normalized-record derivation | approved platform digest contract | frozen and verified |

All package arrays use author-order canonical input. Where an approved list has
more than one item, it must arrive already sorted by the existing schema's
identity key; the adapter neither sorts nor rewrites it. A future author claim
for a missing, malformed, mismatched, or conflicting `declaration_digest` or
`content_digest` is zero-write. Only the adapter-derived digest is retained in
the normalized immutable declaration; only normalized declarations participate
in outer content digest derivation.

### Freeze checklist and gate order (completed)

1. Completed: approved every package-local decision, including explicit `[]`
   values for every unrelated array.
2. Completed: validated both schema-valid, non-authority-shaped facility
   definitions and their ordered `definition_refs`.
3. Completed: assembled one complete, author-ordered v2 manifest with `patch_version ==
   package_version`, the non-empty acquisition eligibility mapping, and the
   fixed binding request. No placeholder or illustrative record is allowed.
4. Completed: the adapter derived and compared declaration digests first,
   normalized declarations, then derived and compared the outer content digest.
   Any failure remains zero-write.
5. Completed: froze the complete bytes and derived pins in the v2 freeze
   record before candidate installation.
6. Completed: admitted the exact immutable
   `descriptor:construction-facility-mill-reinforcement@1` plus
   `inf:construction-facility-mill-reinforcement@1` catalog admission and
   its existing `compose_active_set()/activate()` exact-one binding boundary.
7. Completed: RED tests, the independent Harness, verifier, fixed
   reducer/projector branch, and append vertical now have recorded evidence.

The completed authoring decision created only the exact immutable descriptor/
catalog records and fixed row implementation described above. It does not
admit a generic transform, caller-selected authority coordinate, compensation,
fanout, payment, material semantics, router, registry, writer, settlement
authority, or second runtime.
