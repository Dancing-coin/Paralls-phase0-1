# INF-3W Weather Rain To Crop Recovery Owner-Admission Contract

Status: `implemented narrow vertical; generic crop recovery remains blocked`

## Exact Row

```text
committed project-visible gameplay.ecology.weather_front.propagated@1
  weather_ref = weather:rain
+ the owner-derived unique CropRecord in target_region_ref
  health = 0..99
-> existing EcologyHazardAuthority
-> one project-visible gameplay.ecology.crop.recorded@1 recovery partition
```

The selector is fixed: zero or multiple damaged crops reject. The fixed policy
adds exactly `5` health, capped at `100`; it does not infer an inverse drought
operation and never reads `drought_process_advanced` as source evidence.

## Fixed Contract

| Field | Rule |
| --- | --- |
| capability / outcome | `capability:ecology-weather-rain-crop-recovery@1` / `outcome:ecology-weather-rain-crop-recovered@1` |
| owner | existing `EcologyHazardAuthority` |
| source | exact project-visible `weather_front.propagated` with `weather:rain`; target region is read from the event |
| eligibility | exactly one committed target-region crop with `0 <= health < 100` |
| target | `gameplay:ecology:{target_region_ref}` / existing `gameplay.ecology.crop.recorded@1` family, partitioned by immutable `row_ref` and source provenance |
| privacy | project |
| idempotency | owner-derived `weather_event_id + crop_ref + crop_revision + v1` |
| receipt / replay | append-derived receipt; existing regional full/checkpoint-tail replay |
| lifecycle | one recovery per source event and crop revision; exact duplicate replays, changed duplicate rejects; no reversal, compensation, fanout, or retry-as-new |

The event payload fixes weather/crop before-and-after revisions and health,
policy, predicate, descriptor and catalog pins. Caller-supplied crop identity
is ignored; the envelope source ref must exactly equal the committed weather
event id, and its causation id is pinned to that same event. Unknown, private,
stale, ambiguous, healthy, duplicate, forged or
wrong-weather source rejects before append.
Malformed or non-project privacy input is also converted to the fixed owner
zero-write result; it never escapes as an unhandled validation exception.

The existing regional reader recognizes this immutable `row_ref` partition and
revalidates the weather event, prior and next crop state, causal parent, policy,
predicate and catalog pins before projecting it. Forged replay provenance fails
closed; ordinary seasonal and drought `crop.recorded` rows remain unchanged.

Both full and checkpoint-tail `regional_replay()` paths invoke this existing
authority-scope regional validation before producing their replay result. A
forged canonical recovery event therefore fails closed on either replay path;
this is an exact INF-3W provenance fence, not a new generic replay runtime.

Exact duplicate replay additionally requires the original weather id, target
region, causation and correlation binding. Reusing the same key with changed
region or command context is zero-write.
