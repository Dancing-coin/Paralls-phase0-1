# Government Policy, Permit And Inspection State

Status: `implementation-authorized`

Date: `2026-09-03`

Government owns policy, permit and inspection state. The state machine is
`draft -> published -> effective -> superseded -> revoked`. Inspection and
permit flows remain exact, typed and owner-bound.

Writes use `gameplay.government.policy`. Cross-owner actions are precompiled
recipes only; stale, missing, duplicated or unauthorized claims fail closed.
No generic legal router, policy registry or second government runtime is
introduced.

