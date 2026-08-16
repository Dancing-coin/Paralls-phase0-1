# P3A Profile Activation And Population Identity

Status: `implemented-and-verified; bounded profile activation and identity slice`

## Purpose And Contract

An authorized social role can materialize, activate, suspend and requeue while
retaining one existing `CharacterRecord` / `CharacterProfile` identity.
`ActivationProposal` carries `profile_ref`, world/package/policy revisions,
activation reason, scope grant, cadence class and expected revisions. Authority
resolves the profile, validates grants, then commits lifecycle facts through the
existing event store.

## Owners And Boundaries

| Fact | Owner | Restriction |
| --- | --- | --- |
| profile and cognition | Character Core / registry | planner cannot mutate profile |
| active population projection | world-runtime projection | derived from committed facts |
| body, inventory, account, membership | their domain owners | reference only |
| commit and replay | Gameplay authority | `append_batch()` only |

No `NpcState`, synthetic identity, household coordinator, planner writer or
hidden wake-up loop. Test unknown/revoked/stale/duplicate inputs as zero-write,
then prove activation/suspend replay resolves the same profile identity.
