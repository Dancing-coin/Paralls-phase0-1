# August INF A-D Contract Pre-Close Implementation Plan

Status: `historical documentation-only plan; INF-1AH subsequently implemented and verified; no generic implementation authorized`

## Work Packages

1. Historical INF-1AH package gate: literals were approved, the distinct
   immutable package was authored and frozen, and descriptor/catalog admission
   completed without touching frozen `package:industrial-facilities:v2`.
2. Historical INF-1 owner contract: the fixed
   `mill_reinforced -> decommissioned` source vector subsequently received its
   separate row-specific runtime approval and verified implementation.
3. INF-2 register: do not reopen owner discovery. Convert only a separately
   approved package-defined economic outcome into a row contract; otherwise
   preserve zero-write.
4. INF-3 register: admit only a committed Ecology source and an existing target
   owner. No consumer registry, fanout, or Ecology-to-owner router.
5. INF-4 register: require committed branch/Production evidence and an existing
   owner consequence. Branch preview remains evidence, never domain truth.
6. Audit sync: update completion audit, remaining-scope matrix, four READMEs,
   blocker taxonomy, and continuation checkpoint with the same dispositions.

## Verification Gates

- document links resolve and no frozen package bytes/digests change;
- `python scripts/verification/harness.py --profile all` is not required for
  this documentation-only phase, but any broad claim must still report the
  existing harness evidence and environment caveats from `docs/harness.md`;
- no runtime, manifest, descriptor, catalog, test, Harness, or event diff is
  present in this change.

## Stop Conditions

Stop each row at the first missing business literal, source-owner fact,
target-owner contract, or admission pin. Record the exact field and the
smallest recommended decision; do not infer a default.
