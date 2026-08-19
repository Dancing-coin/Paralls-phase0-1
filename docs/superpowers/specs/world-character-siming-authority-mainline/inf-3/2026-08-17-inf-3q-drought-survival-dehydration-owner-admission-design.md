# INF-3Q Drought Weather-Front To Survival Dehydration Owner-Admission Design

Status: `implemented narrow vertical; approved 2026-08-17`

## Scope And Decision Boundary

This is the approved and implemented row-specific capability. It evaluates one
exact target edge:

```text
committed Ecology weather-front propagated(weather_ref=weather:drought)
  -> existing SurvivalAuthority
  -> effect:dehydration_exposure -> state:dehydrated
```

The proposal does not consume `gameplay.ecology.drought_process_advanced`.
The Ecology drought process remains an Ecology-owned lifecycle row. A drought
weather-front is admissible only when Ecology has already committed the exact
project-visible weather-front event described below. No caller, branch preview,
LLM proposal, or environmental label may manufacture that relationship.

No new truth owner is added. Ecology remains the source owner and Survival
remains the state/effect owner. The fixed, source-controlled operation lives
only in the existing Survival authority, and the immutable catalog contains
only this exact new consumer row.

## Owned And Non-Owned Facts

| Fact or operation | Owner | Boundary |
| --- | --- | --- |
| Canonical weather-front source and its `weather_ref` | `EcologyHazardAuthority` | project-visible `weather_front.propagated` only |
| Actor-to-region assignment | existing activation/population projection | committed assignment event and its pinned revision; no dossier or client position |
| Dehydration state/effect and scheduled lifecycle | `SurvivalAuthority` | one actor stream and existing dehydration state contract |
| Drought process lifecycle | `EcologyHazardAuthority` | not reinterpreted as a weather-front source |
| Actor identity, general population/social truth, weather routing, fanout, or generic state transition | not admitted | reject before append |

## Proposed Capability And Intent Surface

Proposed capability reference: `capability:ecology-weather-front-survival-dehydration@1`.

The typed intent carries only the logical target request and committed source
references: the authenticated actor envelope, one `weather_event_id`, one
`region_assignment_event_id`, and an idempotency token. The caller cannot set
the owner, target stream, event family, state/effect, privacy scope, revision
vector, receipt, retry, or compensation behavior. `actor_ref` is the
authenticated envelope identity, not a free-form payload selector.

Admission requires all of the following committed evidence:

1. the source event is
   `gameplay.ecology.weather_front.propagated`, is project-visible, and has a
   current Ecology stream head;
2. its payload has exactly `weather_ref=weather:drought` and a non-empty
   `target_region_ref`;
3. the project-visible population/activation assignment event binds the
   authenticated actor to that exact target region, with its stream revision
   pinned; and
4. the current Survival actor stream head equals the command's fixed target
   revision.

The source event's `weather_ref` is the only drought classification. A
`drought_process_advanced` event, a caller-supplied weather value, or an
environment snapshot without the committed front event is insufficient.

## Fixed Event And Revision Contract

| Boundary | Fixed contract |
| --- | --- |
| Source stream/event | existing Ecology stream containing `gameplay.ecology.weather_front.propagated@1`; source event revision and Ecology stream head must match |
| Assignment source | existing project-visible population/activation assignment event; assignment stream and event revision are read-set pins |
| Target stream/events | `gameplay:survival:{actor_ref}` with exactly `gameplay.survival.state_applied` and `gameplay.survival.obligation_opened` for `effect:dehydration_exposure` / `state:dehydrated` |
| Append boundary | one Survival owner fragment through `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()` |
| Revision vector | target Survival expected revision plus source Ecology and assignment read-set revisions; stale any-value rejects before append |
| Catalog row | immutable `inf:weather-front-survival-dehydration@1` ecology-consumer entry owned by `actor_gameplay.survival_domain` |

The target state definition and existing Survival dehydration lifecycle must be
validated before fragment construction. No source event is copied into the
Survival stream as a new Ecology fact.

## Privacy, Idempotency, And Receipt

- Source and target projections are `project` scope. Public, authority-only,
  creator-debug, or caller-selected scopes reject before append.
- The canonical idempotency shape is
  `weather-front-dehydration:{weather_event_id}:{actor_ref}:v1`.
  The request digest also covers the assignment event, source/assignment
  revisions, target revision, and fixed state policy. An exact duplicate
  returns the original Survival append result; a changed duplicate is
  zero-write.
- The receipt is derived only from the one Survival `append_batch()` result.
  It includes the target event IDs/revision, source weather event ID/revision,
  assignment event ID/revision, actor, and an actor-safe projection digest.
  There is no Ecology/Survival cross-stream shared receipt.
- Outbox payload is project-scoped and excludes private assignment details
  beyond the contract's redacted actor/region projection.

## Replay And Lifecycle Semantics

The target projection must be reconstructable by the existing
`GameplayProjectionReplay` reader from the committed Survival events. A full
replay and a checkpoint-plus-tail replay over the same event sequence must
produce the same projection digest and receipt inputs. The Ecology source and
assignment events remain separate read-set evidence; they are not replayed as
Survival-owned facts.

Successful admission opens the existing scheduled dehydration obligation. The
ordinary Survival expiry path is the only admitted terminal transition. This
proposal admits no source-retraction, retry, dispel, compensation, or reopen
operation for the weather-front edge. Consequently, no failed or withdrawn
weather front may silently remove dehydration, and no generic compensation
authority may be introduced. A future compensation extension would require a
separate owner-local contract and approval.

## Required Zero-Write Rejections

- missing, private, stale, or wrong-type source event;
- source `weather_ref` other than exactly `weather:drought`;
- source target region not equal to the committed actor assignment region;
- missing, private, forged, or stale assignment event;
- stale Survival target revision or mismatched state lifecycle definition;
- caller-selected owner, stream, event family, state/effect, privacy, revision,
  receipt, retry, or compensation rule;
- a `drought_process_advanced` event used as a weather-front substitute;
- unknown/unapproved capability or missing future catalog row;
- exact duplicate with a changed request digest; and
- any request that attempts fanout, multiple actors, multiple regions, or a
  generic weather value.

## Approval And Migration Boundary

The approved implementation adds only the fixed catalog entry and
`SurvivalAuthority.apply_weather_front_dehydration_exposure`. Focused RED tests
were written before the runtime path and the independent
`infra-weather-front-survival-dehydration` Harness proves success, zero-write
rejection, privacy, revisions, idempotency, receipt, full replay,
checkpoint-tail replay, and the no-compensation/no-fanout boundary. Existing
cold and heat weather consumers, Ecology drought lifecycle, and every other
unlisted edge remain unchanged.

## Verification Evidence

- `backend/tests/test_infra_weather_front_survival_dehydration.py`: `9 passed`.
- `infra-weather-front-survival-dehydration`: green independent Harness report.
- affected weather-front, Ecology-admission, and catalog regression suite:
  `54 passed`.
