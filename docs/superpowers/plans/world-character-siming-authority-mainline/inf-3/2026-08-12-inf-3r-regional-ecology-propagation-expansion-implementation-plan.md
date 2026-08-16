# INF-3R Regional Ecology Propagation Expansion Plan

Status: `implemented and verified for the fixed frost-to-due-production-finish edge`

Date: `2026-08-12`

## Preconditions

- Retain frost/crop as the compatibility baseline.
- Freeze the sole edge: `EcologyHazardAuthority.settle_frost` to
  `ConstructionProductionAuthority.build_due_finish_fragment`.
- Record crop and `gameplay:construction_production:{facility_ref}` stream
  revisions, fan-out one, no delay obligation, visibility, and explicit
  `compensation_not_supported` rejection before code is changed.
- INF-3R-A has verified a committed frost source event, an explicit production
  run/facility selection contract, exact source/target revision vectors, and a
  scoped target projection. It deliberately does not supply the full `Recipe`
  required by `ConstructionProductionAuthority.build_due_finish_fragment`.
- INF-3R-B has verified the existing construction owner, committed run-started
  recipe snapshot, authority-only revisioned reader, privacy/replay behavior,
  and zero-write failures. Do not introduce a bridge, new owner, stream,
  scheduler, or projection; ecology and the coordinator cannot manufacture a
  recipe.

## Work sequence

1. Add failing tests for the committed frost-source proposal and the existing
   construction owner's one-fragment, one-append settlement; the proposal must
   carry no target decision or recipe.
2. Make `ConstructionProductionAuthority` validate the committed source,
   select its own one due run, retrieve its own revisioned recipe snapshot, and
   append the named finish fragment once. Do not add a second writer.
3. Assert stale/missing target, source revision, privacy, duplicate,
   nonempty retry, and nonempty compensation are zero-write failures.
4. Extend only the construction scoped projection/outbox payload; prove public
   redaction, authority provenance, full/checkpoint-tail replay, and legacy
   reader rejection.
5. Add `infra-regional-ecology` with one assertion per named edge property and
   update the August status/report with only the proven coverage.

## Required verification

```powershell
python -m pytest backend/tests/test_infra_regional_ecology.py -q
python scripts/verification/harness.py --profile infra-regional-ecology
python -m pytest -q
git diff --check
```

## Completion record

The focused suite passed 38 tests; `infra-regional-ecology` passed 13
independent assertions; full pytest passed `2569 passed`; and `git diff --check`
passed on 2026-08-13. The completed write is one construction-owner finish
fragment from one committed frost source. Retry and compensation remain
zero-write rejected, and INF-3X/INF-3Y remain separate packages.
