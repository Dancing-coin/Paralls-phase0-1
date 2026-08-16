# INF-2N Activation-Released Fatigue Expiry Design

Status: `implemented bounded and verified 2026-08-15`

INF-2N adds only `state:fatigued` to the existing closed
`survival_state_expiry` activation-obligation binding. It keeps the existing
Survival owner, `gameplay:survival:{profile_ref}` stream, project privacy,
exact released-lock admission, owner fragment, append-derived receipt and
replay. It does not open generic activation binding or create a scheduler.
