# INF-1AG Industrial Facilities V2 Mill Freeze Record

Status: `package frozen and digest-verified; exact descriptor/binding admission and Construction narrow vertical implemented and verified`

Date: `2026-08-20`

## Frozen Bytes And Derived Pins

The exact canonical UTF-8 bytes are stored in
[package-industrial-facilities-v2.manifest.json](package-industrial-facilities-v2.manifest.json).
There is no trailing newline. This is the only immutable content for
`package:industrial-facilities:v2`; it must not be edited in place.

```text
manifest pair      = (2, "1.0")
patch version      = 2.0.0
package version    = 2.0.0
declaration digest = sha256:73d3313283bf584254281a2ca1b60d888585f6ba89e6370a30d622e4529b1bc8
content digest     = sha256:8deea88c5e49c2aa06f30bbf1bd78ed103e26d8fb31769fe5564dbb7cc279896
```

The author input carried both digest claims. The adapter excluded only
`declaration_digest` to derive and exactly compare the declaration claim, then
stored the derived value in the normalized declaration. It then excluded only
outer `content_digest` from the complete normalized record, derived and exactly
compared the content claim. Missing, malformed, mismatched, or conflicting
claims are fail-closed and non-mutating.

The frozen package contains exactly the following non-owner content:

```text
definition:industrial-facilities-mill@1
definition:industrial-facilities-mill-reinforced@1
declaration:industrial-facilities-mill-to-mill-reinforced@1
binding:industrial-facilities-mill-to-mill-reinforced@1
```

Both definitions use `schema:industrial-facilities-facility@1` and typed
content limited to their respective `facility_kind`. All outer and extension
arrays that are unrelated to this narrow row are explicitly frozen as `[]`.
They do not grant package authority over events, replay readers, receipt,
privacy, compensation, or settlement fragments.

## Read-Only Admission And Runtime Boundary

Activation resolves exactly one immutable descriptor:

```text
descriptor:construction-facility-mill-reinforcement@1
inf:construction-facility-mill-reinforcement@1
```

The existing registry retains package/content/declaration/descriptor/active-set
pins. `ConstructionProductionAuthority.reinforce_mill_from_package()` rereads
those pins and the committed project-visible `facility_acquired@1` proof before
using `GameplayCommandEnvelope -> SettlementPlan ->
GameplayEventStore.append_batch()` to append one project-scoped
`facility_transformed@1` event. The fixed projector accepts only the pinned
`mill -> mill_reinforced` vector and advances the facility revision once.

The row is terminal and has no reversal, downgrade, compensation, fanout,
payment, material, production-output, weather, maintenance, recipe, permit,
technology, inventory, or generic transform semantics. The frozen v1 oven row
is unchanged.

## Evidence

- `backend/tests/test_infra_construction_mill_reinforcement.py`: digest claim,
  exact-one binding, success, zero-write rejection, privacy, revision,
  idempotency, append-derived receipt, and full/checkpoint-tail replay.
- `.harness/profiles/infra-construction-mill-reinforcement.json`: independent
  Harness with seven selectors, all green.
- Relevant patch/runtime, v1 regression, catalog, and mill suites: `53 passed`
  with a writable repository-local `--basetemp`.
- Full pytest probe: `916 passed` before the unrelated host permission denial
  when `test_config_runtime_modes` attempted to write the workspace-parent
  `D:\Users\User\Documents\.env`. This is an environment limitation, not a
  mill-row failure or a full-suite pass claim.

This record admits only the exact frozen mill row. It does not complete August
INF A-D or reopen another INF row.
