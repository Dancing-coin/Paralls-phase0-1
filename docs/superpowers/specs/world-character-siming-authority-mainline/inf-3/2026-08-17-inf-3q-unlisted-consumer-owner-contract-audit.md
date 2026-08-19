# INF-3Q Unlisted Consumer Owner-Contract Audit

Status: `audit disposition superseded for this exact row: implemented narrow vertical; other unlisted consumers remain owner-contract blocked`

The next INF-3 row is any weather/ecology consumer beyond the fixed
Construction, Organization, Economy, and Survival rows admitted through C4.
Ecology owns source records and bounded propagation, while each target owner
must build its own fragment. No further target owner has a complete approved
source/target contract.

Missing for every unlisted edge: target authority and stream, event family and
revision, privacy scopes, idempotency key, owner receipt/replay reader, and
retry/compensation semantics. C4 is read-only and cannot register a consumer
or construct a target fragment.

Unlisted source/target combinations therefore reject before any target
`GameplayEventStore.append_batch()` call. No generic registry or fanout writer
is authorized.

## Bounded Candidate Reviewed: Drought Weather Front To Survival Dehydration

This audit evaluated exactly one high-value candidate, without reopening the
terminal general existing-owner search:
`gameplay.ecology.weather_front.propagated(weather_ref=weather:drought)` to
the existing `SurvivalAuthority` state pair
`effect:dehydration_exposure -> state:dehydrated`.

The candidate has only partial reusable evidence:

- Ecology already commits a project-visible weather-front event containing
  `source_region_ref`, `target_region_ref`, `weather_ref`, `tick`, and its
  stream/event revision. C4 can validate that fixed source event and the
  Ecology read-set revision.
- Survival already owns the dehydration state lifecycle, and the two admitted
  cold/heat weather rows show that a target actor can be bound to an exact
  project-visible population profile-region assignment with target-stream and
  population revisions pinned.

At the time of this audit, it was not an executable existing contract. The
immutable catalog then contained only `inf:weather-front-survival-cold@1` and
`inf:weather-front-survival-heat@1`, and `SurvivalAuthority` had no fixed
dehydration weather-front command or admission recipe. A generic weather-front
event accepts arbitrary
`weather_ref`, while the committed Ecology drought process emits
`drought_process_advanced`, not an admitted drought weather-front source.
Neither source-selection relationship is currently fixed. Finally, no
weather-drought-specific terminal, retry, reversal, or compensation/reopen
rule exists for a previously applied dehydration state.

The following fields are therefore missing and must be stated without
placeholders in a future row-specific target-edge Owner-Admission Contract:

1. one committed source kind and exact `weather:drought` production rule;
2. the canonical project-visible actor-to-target-region assignment event and
   its stream/event revision pins;
3. one fixed Survival command, stream/event family, revision vector, scoped
   projection, idempotency key and append-derived receipt;
4. full and checkpoint-tail replay readers for that exact edge; and
5. terminal, retry, source retraction, and compensation/reopen semantics.

This disposition created no new owner, target fragment, catalog row, or
runtime path. The existing dehydration lifecycle and the cold/heat rows
remained unchanged; neither implied admission for `weather:drought`.

Work resumed only after the separate row-specific target-edge Owner-Admission
Contract was explicitly approved. It extended the existing Survival owner only
and added no generic consumer registry, fanout writer, or Ecology-to-Survival
router.

## Disposition Update: Implemented Narrow Vertical

The approved contract is now implemented as exactly
`inf:weather-front-survival-dehydration@1` and
`SurvivalAuthority.apply_weather_front_dehydration_exposure`. It accepts only
the committed project-visible `weather_front.propagated` source with exact
`weather:drought`, an active project-visible matching profile-region assignment,
and exact Ecology, population, and Survival revision pins. It writes only the
existing Survival `state_applied` / `obligation_opened` pair. The drought
process remains an invalid source, and compensation, retry, reopen, fanout,
generic routing, and any other unlisted consumer remain unadmitted.

Evidence: `9 passed` focused tests, green
`infra-weather-front-survival-dehydration` Harness, and `54 passed` affected
regressions. This audit remains durable evidence of why a row-specific
admission was required; it was not a failed implementation attempt.
