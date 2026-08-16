# INF-4R Population World-Mode And Civilization-Interface Expansion Plan

Status: `INF-4R bounded social-input admission verified; later inputs remain blocked`

Date: `2026-08-12`

## Preconditions

- Retain CharacterProfile identity and INF-4 branch isolation as invariants.
- The sole first source is `SocialFactAuthority.view_for`; freeze its recipient
  scope, source revision vector, and observation time in planner input.
- Household/organization schedules and civilization capability are `blocked`:
  no current revisioned source projection or civilization owner exists. Reject
  them as unsupported and stop if the work proposes a truth store.

## Work sequence

1. Add failing contract tests for world-mode/cadence policy, SocialFactAuthority
   source provenance/scope/vector, deterministic digest/order, and unsupported
   household/organization/capability input rejection.
2. Implement pure plan construction from fixed projection inputs and existing
   activation lock state; ensure mode selection does not tick or mutate state.
3. Add one owner-scoped daily plan and one long-cycle plan from the named social
   input. Each must produce
   only existing owner intents/fragments and independently prove zero-write
   rejection, duplicate, revision conflict, defer, and release.
4. Assert civilization capability input is unsupported with zero writes; do not
   add a capability authoring path or an implied future source.
5. Extend branch preview and scoped reports with SocialFactAuthority redaction.
   Prove branch/production isolation, full/checkpoint-tail production replay,
   branch replay, and requeue. Reader migration and compensation are blocked
   until a later package names their owner event maps.
6. Add `infra-population-world-mode`, its evidence report, and an August status
   update that lists supported plans rather than claiming full simulation.

## INF-4R evidence

- [x] `FrozenSocialPlanningInput` pins the recipient, observation time,
  SocialFactAuthority projection digest, and source revision vector.
- [x] `PopulationPlanner` admits only that frozen input and preserves its
  digest in the plan; stale vectors and out-of-scope recipients are zero-write.
- [x] Household, organization, and civilization capability inputs remain
  unsupported zero-write rejections.
- [x] Independent profile: `infra-population-world-mode`, evidence at
  `.harness/verification/infra-population-world-mode-report.json`.
- [x] The profile separately proves that the retired generic
  `PopulationBatchPlan` merge remains zero-write for frozen social proposals;
  social-source replay does not imply an append authority.

## Required verification

```powershell
python -m pytest backend/tests/test_infra_population_world_mode.py -q
python scripts/verification/harness.py --profile infra-population-world-mode
python -m pytest -q
git diff --check
```
