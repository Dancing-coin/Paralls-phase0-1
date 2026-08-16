# INF-1B Semantic Survival State Bridge Design

Status: `implemented and verified for two registered Survival state rows; August INF-1 closure remains incomplete`

## Scope

This package admits two closed semantic proposal bridges. It does not give the
semantic registry or evaluator domain write authority. `SemanticSettlementAuthority`
validates a proposal then invokes the existing `SurvivalAuthority`; Survival alone
creates its state and `ScheduledObligation` facts through the existing append spine.

| Concern | Contract |
| --- | --- |
| Proposal principal | `authority:semantic` only |
| Target owner | existing `actor_gameplay.survival_domain` / `SurvivalAuthority` |
| State/effect | `state:cold@1` / `effect:cold_exposure`; `state:overheated@1` / `effect:heat_exposure` only |
| Stream | `gameplay:survival:{actor_ref}` |
| Events | `gameplay.survival.state_applied`, `gameplay.survival.obligation_opened` |
| Privacy | `project` only; authority-only/private proposals reject before write |
| Revision/idempotency | exact survival stream revision; existing Survival idempotency receipt |
| Replay | existing survival projection and checkpoint-tail replay |

The bridge converts a validated immutable semantic snapshot into a
`GameplayCommandEnvelope` with the Survival principal and delegates to
`SurvivalAuthority.apply_effect_state()`. It pins only the semantic snapshot
revision vector and uses `semantic_registry` as source provenance. It does not
accept a caller-selected stream, owner, event type, fragment, or lifecycle row.

## Non-goals

No generic effect-owner mapping, generic state lifecycle, direct semantic event
write, new obligation store, scheduler, NPC/population/social owner, or P6/P7
work is authorized. The pure evaluator's expiry dictionary remains a proposal
outside these named rows.

## Evidence

`infra-semantic-survival-state-bridge` independently asserts cold-row success,
overheated-row owner submission, duplicate replay, altered-idempotency-payload
zero-write, target revision zero-write, privacy/unmapped-owner zero-write, and
checkpoint-tail replay. Evidence is stored at
`.harness/verification/infra-semantic-survival-state-bridge-report.json`.
