Status: DONE_WITH_CONCERNS

Task 3 implemented with TDD.

Red:
- Added `backend/tests/test_siming_intervention_guardrails.py` exactly from the brief.
- Ran `python -m pytest backend/tests/test_siming_intervention_guardrails.py -v`.
- Observed expected failure: `ModuleNotFoundError: No module named 'app.services.siming_intervention_guardrails'`.

Green:
- Added `backend/app/services/siming_intervention_guardrails.py`.
- Reran `python -m pytest backend/tests/test_siming_intervention_guardrails.py -v`.
- Result: `3 passed`.

Behavior delivered:
- Rejects blocked risk tags including `phase2_projection_required`.
- Rejects unknown fact references not present in `FairnessStateSnapshot.known_fact_ids`.
- Rejects ineligible actor targets.
- Rejects `environment_request` seeds that do not carry `esm_validated_request`.
- Converts accepted seeds into `InterventionCandidate` values with `guardrail_checked`.

Concern:
- The repo's current interfaces are slightly inconsistent: `InterventionSeed.source` defaults to `narrative_core`, while `InterventionCandidate.source` only accepts `rule | llm | fallback`.
- To keep Task 3 self-contained and passing without widening model changes, the new guardrail service normalizes `narrative_core` to `rule` when building a candidate.

Files changed:
- `backend/app/services/siming_intervention_guardrails.py`
- `backend/tests/test_siming_intervention_guardrails.py`

Fix section:
- Files changed: `backend/tests/test_siming_intervention_guardrails.py`
- Test command: `python -m pytest backend/tests/test_siming_intervention_guardrails.py -v`
- Result: `5 passed`
