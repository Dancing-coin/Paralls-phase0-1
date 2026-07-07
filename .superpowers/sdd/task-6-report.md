# Task 6 Report: Siming Narrative Core Boundary Verification

## Files Changed

- `backend/tests/test_siming_llm_boundary_static.py`
- `backend/tests/test_siming_event_pipeline.py`

## Commands And Results

1. Focused regression slice

```powershell
python -m pytest backend/tests/test_siming_narrative_core.py backend/tests/test_siming_quality_monitor.py backend/tests/test_siming_intervention_guardrails.py backend/tests/test_siming_read_facade.py backend/tests/test_siming_agent_loop_runtime.py backend/tests/test_siming_event_pipeline.py backend/tests/test_siming_llm_boundary_static.py -v
```

Result:
- `36 passed`
- `2 warnings`
- runtime: `2.30s`

2. Broader Siming and websocket regression slice

```powershell
python -m pytest backend/tests/test_siming_llm_runtime.py backend/tests/test_visual_fact_pipeline.py backend/tests/test_ws_protocol.py backend/tests/test_verification_audit.py -k "siming or visual_fact or observatory or read_model or checkpoint" -v
```

Result:
- `50 passed`
- `1 failed`
- `83 deselected`
- `2 warnings`
- runtime: `2.36s`

Failure:
- `backend/tests/test_siming_llm_runtime.py::test_runtime_shares_feature_registry_between_fairness_snapshot_and_policy`
- assertion did not find `policy_rejected` audit reason containing `resource_pressure_policy_rejected`

3. Full backend suite

```powershell
python -m pytest -v
```

Result:
- collection interrupted
- `1134 items / 1 error`
- `7 warnings`
- runtime: `2.95s`

Collection error:
- `tests/test_non_runtime_production_pipeline.py`
- `ModuleNotFoundError: No module named 'tools'`

## Commit

- `Verify Siming narrative core boundaries`

## Concerns

- The scoped Task 6 boundary assertions pass.
- The broader regression slice is not fully green because of an existing failure in `backend/tests/test_siming_llm_runtime.py`.
- The full backend suite is not currently runnable in this checkout because `tests/test_non_runtime_production_pipeline.py` cannot import `tools.production`.
- No production code was changed for Task 6.

## Fix: Restore Registry Dimensions In Siming Quality Monitor

### Root Cause

Task 5 moved fact-accepted fairness snapshot ownership from `SimingFairnessAuditEngine.build_snapshot(...)` to `SimingQualityMonitor.evaluate(...).snapshot`. The quality monitor kept the five deterministic required dimensions, but it no longer merged dynamically registered `SimingFeatureRegistry.fairness_dimensions()` into `snapshot.dimensions`. As a result, the shared registry's custom `resource_pressure` policy mapping never appeared in the fairness snapshot, and `SimingInterventionPolicy.evaluate(...)` had no dimension to match against `resource_pressure_sensitive`.

### Files Changed

- `backend/app/services/siming_quality_monitor.py`
- `backend/app/services/siming_runtime.py`
- `backend/tests/test_siming_quality_monitor.py`

### Commands And Results

1. Confirmed RED regression before changes

```powershell
python -m pytest backend/tests/test_siming_llm_runtime.py::test_runtime_shares_feature_registry_between_fairness_snapshot_and_policy -vv
```

Result:
- `1 failed`
- failure assertion did not find `policy_rejected` audit reason containing `resource_pressure_policy_rejected`

2. Verified focused runtime regression after fix

```powershell
python -m pytest backend/tests/test_siming_llm_runtime.py::test_runtime_shares_feature_registry_between_fairness_snapshot_and_policy -v
```

Result:
- `1 passed`
- `1 warning`

3. Verified quality monitor unit slice after fix

```powershell
python -m pytest backend/tests/test_siming_quality_monitor.py -v
```

Result:
- `3 passed`

4. Verified broader Task 6 regression slice after fix

```powershell
python -m pytest backend/tests/test_siming_llm_runtime.py backend/tests/test_visual_fact_pipeline.py backend/tests/test_ws_protocol.py backend/tests/test_verification_audit.py -k "siming or visual_fact or observatory or read_model or checkpoint" -v
```

Result:
- `51 passed`
- `83 deselected`
- `2 warnings`

### Commit

- `dab2633 Restore registry dimensions in Siming quality monitor`

### Concerns

- The required regression and broader slice are green after the fix.
- The command outputs still include the pre-existing Pydantic `model_id` namespace warning and Starlette `httpx` deprecation warning.
- This report preserves the earlier Task 6 full-suite concern; I did not rerun `python -m pytest -v` for this scoped regression fix.
