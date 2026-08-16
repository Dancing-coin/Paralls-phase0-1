# INF-3J Weather-Front Economy Quote Edge

Status: `implemented bounded and verified`

One project-visible existing weather-front event may be consumed by the
existing Economy quote owner to publish the next version of one existing quote.
Ecology emits no Economy event and selects no price; it supplies only an opaque,
one-use admission over a complete canonical source vector. Economy validates the
source event, stream, revision, target region, project privacy and current quote,
applies the fixed owner policy `weather_front_price_multiplier`, then uses its
existing formal quote append spine.

| Concern | Closed contract |
| --- | --- |
| Source owner | existing `EcologyHazardAuthority`; only a committed `gameplay.ecology.weather_front.propagated` event at `project` visibility can issue the opaque admission |
| Target owner | existing `EconomyAuthorityService` / `actor_gameplay.economy_domain` |
| Target stream/event | `gameplay:economy` / existing `gameplay.economy.dynamic_quote_published` |
| Source pin | immutable `weather_event_id`, `ecology_stream_id`, `ecology_revision`, `region_ref`, and `quote_ref`, persisted as `ecology_weather_source` on the target event |
| Revision and idempotency | source stream must still equal its admitted head; exact source-bound duplicate replays, while changed source, quote, revision, region or idempotency input rejects before append |
| Privacy/outbox | source and target are project-scoped; Economy emits only the existing redacted project quote outbox, and authority-only weather evidence cannot be admitted |
| Receipt/replay | success is the target's sole `GameplayEventStore.append_batch()` result; every pre-append denial returns an owner-local structured zero-write `AppendBatchResult`; `EconomyProjector` supplies full/checkpoint-tail replay |

Unknown quote, source, scope, stale revisions, forged admission, cross-quote
reuse, changed source under the same idempotency key and a caller-selected
multiplier are zero-write.

This is one fixed consumer edge, not generic pricing, market truth, fanout or
an Ecology writer.
