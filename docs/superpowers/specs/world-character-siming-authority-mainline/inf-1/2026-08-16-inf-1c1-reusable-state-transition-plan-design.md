# INF-1C1 Reusable State Transition Plan

Status: `implemented and independently verified as a pure reusable proposal layer; broader INF-1 remains incomplete`

## Contract

`EffectLifecycleEvaluator.plan_apply()`, `plan_dispel()` and `plan_transform()`
return a frozen `StateTransitionPlan`. The plan carries only the decision,
stack transition, effective magnitude, target state and optional expiry
proposal. It cannot select an owner, append an event, create an obligation in
the store, or execute a script/expression.

The existing `resolve*()` methods remain compatibility projections for current
owner code. The same pure plan shape is accepted for existing Survival,
Construction and Ecology definitions from the closed semantic registry.

## Evidence

Focused tests: `backend/tests/test_infra_reusable_state_transition_plan.py`.
Harness: `.harness/verification/infra-reusable-state-transition-plan-report.json`.

This package does not claim generic owner routing, new state registration,
event-derived expiry settlement, or any new domain writer.
