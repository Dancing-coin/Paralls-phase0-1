# Package Contract Closure And Manifest Adapter Plan

Status: `design-only; implementation gated`

## Goal

Close the formal package-content contract so future gameplay packages and mods
can add typed definitions and proposal rules without creating a second
runtime, registry, or domain truth owner.

## Scope

This plan covers only documentation and approval boundaries for:

- canonical `GameplayPatchManifest` package sections;
- immutable package identity, revision, schema, and digest pins;
- `PackageDefinition`, `PackageOutcomeDeclaration`, and `BindingRequest`;
- owner-derived `EligibilityProof` and row-specific evidence validation;
- package lifecycle, disable/upgrade, full replay, and checkpoint-tail replay;
- reconciliation with the reference `GameplayPackageManifest` model.

## Sequence

1. Record `GameplayPatchManifest` as the sole executable package admission
   path and keep `GameplayPackageManifest` reference-only.
2. Freeze the logical package record shapes and revision/digest invariants.
3. Freeze the owner-derived eligibility proof shape and the rule that each
   admitted owner capability enumerates its accepted evidence kinds.
4. Reconcile the package matrix, domain-extension catalog, Rule IR design,
   foundation READMEs, and INF-1AG design with this contract.
5. For each future row, create a separate Owner-Admission Contract that fixes
   owner, command, stream/event family, privacy, idempotency, receipt,
   replay, and compensation semantics.
6. Only after row approval, write RED tests, an independent Harness profile,
   and the narrow runtime vertical.

## Explicit Non-Goals

- no runtime package schema or adapter implementation;
- no generic eligibility resolver or package registry;
- no new owner, router, coordinator, writer, settlement authority, or
  second runtime/store/bus/clock/scheduler;
- no approval of a facility pair, economic outcome, payment, transfer,
  treasury, market, or compensation policy;
- no RED tests, Harness profile, catalog entry, or runtime code for INF-1AG.

## Verification

- documentation references resolve to the new design and plan;
- the package matrix and legacy catalog no longer imply that packages choose
  owner privacy, replay, receipt, or compensation semantics;
- `GameplayPatchManifest` and `GameplayPackageManifest` are not described as
  parallel executable models;
- `git diff --check` passes;
- Docs Harness passes;
- no runtime files, package schema code, or catalog entries are changed by
  this plan.
