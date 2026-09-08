# Task 7 Report: Runtime Wiring and Generalized Population Harness

## Changed files

- `backend/app/main.py`
  - Preserves the Bakery legacy `owner_executor`.
  - Registers only `population:organization-production-work-contribution:v1` in default runtime `owner_executors`, backed by `OrganizationAuthority` over the shared `GameplayEventStore`.
  - Inventory and public Social remain fail-closed because the production startup has no legal active package binding for either adapter.
- `backend/app/population_continuity/__init__.py`
  - Exports `OrganizationProductionWorkContributionOwnerExecutor` with the existing adapter exports.
- `backend/tests/test_siming_population_domain_owner_runtime.py`
  - Covers the runtime allowlist, legacy Owner preservation, shared store identity, Tax exclusion, Inventory/Social exclusion, and `capability_owner_adapter_missing` zero-write through `SimingRuntime.tick(...)`.
- `scripts/verification/verify_siming_population_domain_owner_adaptation.py`
  - Adds independent domain candidate, selection, privacy, Owner/Character Core order, replay, runtime allowlist, fail-closed and Stormnight exclusion checks.
- `.harness/profiles/siming-population-domain-owner-adaptation.json`
  - Registers the backend-only independent Harness profile.
- `docs/harness.md`
  - Documents the profile and the adapter-verified versus production-runtime-admitted boundary.
- `docs/8月分析/司命与群体世界补充设计/03-群体模拟与角色分级连续性.md`
  - Records the current explicit runtime admission state.
- `docs/8月分析/司命与群体世界补充设计/13-群体模拟生产纵切与推进闭环设计.md`
  - Records Production/Organization admission and Inventory/Social package-activation blockers.

## Verification

TDD RED before runtime wiring:

```text
1 failed, 2 passed, 2 warnings in 5.60s
failure: default runtime owner_executors was empty
```

Focused runtime integration after wiring and fail-closed review:

```powershell
python -m pytest -q backend/tests/test_siming_population_domain_owner_runtime.py
```

```text
6 passed, 2 warnings in 2.98s
```

Full backend suite:

```powershell
python -m pytest -q
```

```text
5212 passed, 8 warnings in 242.82s (0:04:02)
```

Dedicated Harness:

```powershell
python scripts/verification/harness.py --profile siming-population-domain-owner-adaptation
```

```text
overall_siming_population_domain_owner_adaptation_passed=True
harness_exit_code=0
focused domain slice: 25 passed, 2 warnings in 5.21s
```

The first generalized run correctly failed because the ordered three-actor predecessor artifact was missing. No check was weakened. Prerequisites were refreshed in order:

```text
overall_phase3a_profile_activation_passed=True
overall_phase3b_world_mode_continuity_passed=True
overall_phase3c_batch_intent_merge_passed=True
overall_phase3d_bakery_district_population_passed=True
overall_phase3_population_continuity_passed=True
overall_siming_led_population_seed_continuity_passed=True
overall_siming_governed_three_actor_cohort_continuity_v1_passed=True
overall_siming_generalized_population_decision_passed=True
```

Documentation and diff gates:

```powershell
python scripts/verification/check_docs.py
git diff --check
```

```text
overall_docs_passed=True
git diff --check: passed (no output)
```

## Commit

- `bb1f689` (`完成司命群体领域 Owner 适配闭环`)

## Concerns

- Inventory and public Social adapters are implemented and independently verified, but they are not production-runtime-admitted until source-controlled manifests are legally activated with their required Owner dependencies. Default runtime selection therefore requeues them with `capability_owner_adapter_missing` and zero write.
- Tax remains report-only and has no runtime Owner executor. Stormnight realtime action windows remain outside population cadence.
- This Task is backend-only; it makes no Godot runtime verification claim.
- The existing untracked implementation-plan file was intentionally left outside both commits.
