# INF-2R Multi-Domain Obligation Policy Expansion Plan

Status: `INF-2R construction due-completion policy implemented and verified; unsupported paths remain fenced`

Date: `2026-08-12`

## Preconditions

- Freeze the sole first policy: construction production completion, owned by
  `ConstructionProductionAuthority.build_due_finish_fragment` on
  `gameplay:construction_production:{facility_ref}`.
- Record its stream revision, existing `run_finished` event family, visibility
  class, and explicit obligation lifecycle payload fields. Ecology is blocked:
  `EcologyHazardAuthority` has no owner-fragment builder.
- Stop if a policy requires polling, a second scheduler, or direct mutation.

## Work sequence

1. Add failing construction-policy tests for due selection, no background mutation,
   insufficient authority/resource zero-write, duplicate, stale revision, and
   closed/cancelled lifecycle rejection.
2. Add typed production policy references and use the existing owner fragment builder without
   widening the coordinator's authority.
3. Integrate activation lock/pending-change behavior where an owner has an
   interactive surface; test held revision and stale release independently.
4. Assert unsupported retry/compensation is rejected with zero writes. Do not
   implement either before a later plan names their owner event families.
5. Extend scoped receipt/projection readers and prove full/checkpoint-tail
   replay plus compatible event-reader migration.
6. Add independent profile `infra-multi-domain-obligation`, report, and August
   status only after every capability maps to a distinct assertion.

## Delivered scope

- [x] Added the closed `ConstructionDueCompletionPolicy` using the existing
  production stream and owner fragment builder.
- [x] Kept clock advancement caller-driven; the coordinator only assembles the
  owner fragment and appends through the existing event spine.
- [x] Reject non-empty retry and compensation policy input before append until
  INF-2X supplies registered owner event families.
- [x] Added distinct focused assertions and the
  `infra-multi-domain-obligation` Harness report.

## Required verification

```powershell
python -m pytest backend/tests/test_infra_multi_domain_obligation.py -q
python scripts/verification/harness.py --profile infra-multi-domain-obligation
python -m pytest -q
git diff --check
```
