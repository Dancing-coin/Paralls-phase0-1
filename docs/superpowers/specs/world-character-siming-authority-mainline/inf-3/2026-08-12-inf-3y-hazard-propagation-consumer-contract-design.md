# INF-3Y Hazard Propagation Consumer Contract Design

Status: `one exact frost -> construction consumer contract admitted for test-first implementation; no other INF-3Y edge is enabled`

## Purpose and inherited baseline

INF-3Y defines a governed edge catalog after a source and a consumer row are
independently admitted. The existing INF-3R frost-to-production row is not
inherited evidence or an INF-3Y enabled baseline: it reads a committed
`semantic.effect.settled` crop source, not the canonical INF-3X ecology hazard
stream. INF-3Y inherits hazard causal evidence, semantic snapshots, INF-1X rule
evaluation and INF-2X delayed settlement. It does not turn hazards into a
global writer or infer that a consumer exists because its model class exists.

## Edge ownership and registration

The ecology owner supplies an immutable `HazardPropagationProposal`; each
consumer owns acceptance and its domain event fragment. The catalog row is
`edge_ref`, source hazard/effect selector, source/target scope, threshold,
attenuation, cadence, chain budget, source and consumer revisions, target
authority/stream/event family, privacy mapping and compensation policy. Each
row is disabled by default. No hazard-to-consumer row is currently enabled. The
candidate frost -> `ConstructionProductionAuthority` row is now admitted as the
sole test-first row: `ecology-hazard:frost-to-construction-finish:v1`. Its
source is project-visible canonical `gameplay.ecology.hazard.recorded` and
`gameplay.ecology.crop.recorded` events on the same
`gameplay:ecology:{region_ref}` stream. The immutable proposal pins both event
ids/revisions and the ecology stream head; it contains hazard/crop/plot/region
refs, effect, due tick, causal parents and project visibility. The hazard record
pins `source_crop_ref`; proposal admission resolves that exact active crop event
and never infers a target from the set of regional crops. The construction
owner alone accepts `CanonicalFrostProductionFinishCommand`, verifies that
exact source vector, selects one due run for the proposal plot, obtains the
construction stream head itself, and builds its existing `run_finished`
fragment. Its target is the existing
`gameplay:construction_production:{facility_ref}` stream and event family
`gameplay.construction_production.run_finished`; the consumer-selected target
head is the construction revision vector. The prior
`ConstructionFrostFinishCommand` semantic crop path remains a separate INF-3R
contract and is not adapted or reused as this source reader. Market,
survival/body, inventory, social, population and civilization rows remain
blocked until their named builder and projection source are accepted.

```text
ecology fact/hazard -> frozen semantic/effect proposal -> registered edge
-> target OwnerAuthorizedFragment -> append_batch -> causal/outbox/replay
```

The coordinator may assemble accepted fragments but cannot calculate price,
health, inventory, relationship or population outcomes. Clients, Godot, LLM,
Siming and creator tools cannot invoke an edge or write a consumer directly.

## Contract, failure and privacy

### 2026-08-13 admission audit

INF-3X now independently proves canonical hazard records on
`gameplay:ecology:{region_ref}`, while INF-3R independently proves an older
semantic crop source -> construction finish narrow edge. Do not bridge these
contracts by passing a canonical hazard event into the semantic command or by
allowing ecology to invoke construction directly. This row instead names the
new construction-owned consumer command above. Direct caller construction
invocation, unknown/disabled edges, missing or stale source vector, altered
duplicate proposal, non-project source visibility, missing/ambiguous/not-due
target, fragment overlap, retry and compensation reject before append with zero
writes. Ecology only returns a proposal; it does not invoke construction.
Retired canonical hazard or crop records are excluded by event-derived active
record reconstruction and reject before proposal creation with zero writes.
The consumer entrypoint also requires the matching transient
`CanonicalHazardConsumerAdmission` emitted by ecology in the same trusted
process. It is deliberately not a `StrictGameplayModel`, not serializable in a
wire command, and not reconstructed from a caller-controlled authority string.
Construction internally registers only the exact object it issues to the
ecology authority call path; a same-process caller that imports the real class
and copies its public fields is still rejected with zero writes, and cannot
call the internal issuer through the supported module API. This is a backend
trust boundary for client/Godot/LLM/Siming/creator inputs, not a claim that
arbitrary trusted Python code using reflection or monkey-patching inside the
authority process is sandboxed.

`HazardPropagationProposal` contains hazard/region refs, effect and resistance
digests, source revision vector, target selector digest, severity, effective/
due tick, causal chain/parents, idempotency key and visibility. The consumer
returns accepted/deferred/rejected fragment and its expected stream revision.
Delayed rows create an INF-2X obligation; immediate rows still use the single
append batch. A row cannot fan out beyond its explicit budget and fixed,
deterministic target order.

Unknown/disabled row, missing ecology owner, stale source or consumer revision,
out-of-scope target, budget/cycle exhaustion, altered duplicate input,
incompatible visibility, consumer refusal or overlapping fragment causes a
structured zero-write rejection. Authority traces retain evidence; public,
actor and creator views expose only allowed region/hazard/consumer summaries.

## Replay, rollback, Harness and completion

Full and checkpoint-tail replay must reconstruct the registered edge decision,
consumer events, causal ancestry and redacted view. Event/edge readers have
versioned migrations; rollback retires future rows, cancels future obligations,
or uses a named consumer compensation event. `infra-hazard-propagation` needs
independent success/rejection/idempotency/revision/privacy/replay assertions per
enabled edge. Non-goals: automatic all-domain fanout, generic market/body
owner, ambient background propagation, P6/P7. Completion is a list of proven
rows, never “hazards affect the world generally.”
