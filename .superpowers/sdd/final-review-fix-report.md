# Final Review Fix Report

## 2026-07-07 Final Review Fix

Findings addressed:
- Critical 1: `SimingRuntime.ingest_canonical_percept_bundle(...)` no longer emits `intervention_candidate`, `intervention_decision`, or `dispatch_intent`; the helper remains a canonical bundle read-model/debug consumption path and cannot bypass `tick(...)` for orchestrator decisions.
- Critical 2: rejected narrative guardrails now block the fallback visual-fact candidate/decision/dispatch path, emit `no_action`, audit the rejection reason, and expose guardrail rejection details in the read model.
- Important 1: `InterventionSeed` now separates `basis_fact_refs` from `basis_obligation_refs`; guardrails validate fact refs and candidate conversion uses fact refs for `established_fact_ids`.
- Important 2: the read facade narrative summary now includes bounded obligation and intervention-seed summaries.
- Minor: removed the avoidable `# type: ignore[no-untyped-def]` on the runtime narrative summary helper by typing it with `NarrativeCoreResult`.

Files changed:
- `backend/app/models/siming_narrative.py`
- `backend/app/services/siming_narrative_core.py`
- `backend/app/services/siming_intervention_guardrails.py`
- `backend/app/services/siming_quality_monitor.py`
- `backend/app/services/siming_runtime.py`
- `backend/tests/test_siming_intervention_guardrails.py`
- `backend/tests/test_siming_agent_loop_runtime.py`
- `backend/tests/test_siming_event_pipeline.py`
- `backend/tests/test_l1_perception_frame_runtime.py`

Verification:
- Red checks before production changes:
- `python -m pytest backend/tests/test_siming_intervention_guardrails.py -v` failed: 6 failed because `basis_fact_refs` was not accepted by `InterventionSeed`.
- `python -m pytest backend/tests/test_siming_agent_loop_runtime.py -v` failed: 2 failed because read-model obligation summaries were missing and rejected guardrails still allowed candidate/decision/dispatch outputs.
- `python -m pytest backend/tests/test_siming_event_pipeline.py::test_pipeline_canonical_bundle_ingestion_records_read_model_without_decision_outputs backend/tests/test_l1_perception_frame_runtime.py::test_siming_runtime_consumes_global_bundle_without_sharing_character_context -v` failed: 2 failed because canonical bundle ingestion still emitted an `intervention_candidate`.
- Focused checks after fixes:
- `python -m pytest backend/tests/test_siming_intervention_guardrails.py -v` passed: 6 passed.
- `python -m pytest backend/tests/test_siming_agent_loop_runtime.py -v` passed: 8 passed, 1 warning.
- `python -m pytest backend/tests/test_siming_event_pipeline.py -v` passed: 13 passed, 1 warning.
- `python -m pytest backend/tests/test_l1_perception_frame_runtime.py -v` passed: 14 passed, 1 warning.
- Broader Task 6 slice:
- `python -m pytest backend/tests/test_siming_llm_runtime.py backend/tests/test_visual_fact_pipeline.py backend/tests/test_ws_protocol.py backend/tests/test_verification_audit.py -k "siming or visual_fact or observatory or read_model or checkpoint" -v` passed: 51 passed, 83 deselected, 2 warnings.
- Post-type-edit sanity:
- `python -m pytest backend/tests/test_siming_agent_loop_runtime.py -v` passed: 8 passed, 1 warning.
- `python -m pytest backend/tests/test_siming_intervention_guardrails.py -v` passed: 6 passed.

Commit:
- `6b12b58` - `Fix Siming narrative core final review findings`

Concerns:
- Existing warnings remain unrelated to this change: Pydantic protected namespace warning for `Scene3DSpaceModel.model_id`, and the broader slice also reports a Starlette/FastAPI TestClient deprecation warning.
- Godot/editor runtime verification was not run because this fix is backend Siming/runtime behavior and the requested verification set was pytest-based.
