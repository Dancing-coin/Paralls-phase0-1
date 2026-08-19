# Package Content And Cross-Domain Binding Matrix Plan

Status: `design documentation in progress; no runtime implementation authorized`

## Goal

Document the extensible gameplay-package content boundary and its typed
bindings to Siming, character-agent mind models, ESM/physics, and existing
domain owners without creating a second runtime or generic authority.

## Sequence

1. Inventory executable `GameplayPatchManifest` fields, registry lifecycle,
   package-defined economic outcomes, Rule IR, capability requests, and
   verification metadata.
2. Inventory the reference `GameplayPackageManifest` and record its relationship
   to the executable patch model; do not extend both independently.
3. Classify package fields as content declarations, typed evidence references,
   proposal/binding requests, engine control-plane fields, existing-owner facts,
   or prohibited authority inputs.
4. Define versioned package definitions and outcome declarations with immutable
   revision/digest pins and no owner/stream/event/privacy/receipt/fragment
   selection.
5. Define cross-domain read/proposal/settlement boundaries for Siming,
   character mind, ESM/physics, Construction, Inventory/Ownership, and
   Economy/Contract.
6. Record package lifecycle, conflict, disable, migration, and historical replay
   obligations.
7. Keep the package schema, eligibility resolver, capability catalog row, and
   owner reducer as separate later approval gates.

## Verification

- Docs Harness finds this design and plan pair.
- `git diff --check` passes.
- No RED tests, Harness profile, catalog entry, resolver, package schema field,
  or runtime code is added by this plan.

## Out Of Scope

- implementing facility-transform declarations;
- implementing a generic eligibility resolver;
- creating a package registry or new owner;
- changing `GameplayPatchManifest` or `GameplayPackageManifest` code;
- approving any concrete facility pair;
- generic routing, settlement, compensation, market, or cross-domain writer.
