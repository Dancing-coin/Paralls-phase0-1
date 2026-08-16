# INF-1T Survival Fatigue State Action Design

Status: `implemented bounded and verified 2026-08-15`

INF-1T adds the already-admitted `state:fatigued` row to the existing closed
Survival dispel and fixed recovery-transform action route. Owner, stream,
event family, projection scope, receipt and replay remain unchanged:
`authority:semantic -> SurvivalAuthority fragment -> ObligationSettlementCoordinator
-> SettlementPlan -> GameplayEventStore.append_batch()`.

The route accepts only `state:fatigued`, project scope, the existing Survival
stream and fixed transform target `state:recovering`. Generic action, state,
owner and replacement-target registration remains unsupported-input zero-write.
