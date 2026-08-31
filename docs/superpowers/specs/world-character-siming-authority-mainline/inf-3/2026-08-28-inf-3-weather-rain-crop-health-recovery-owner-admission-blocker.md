# INF-3 Weather Rain To Crop Health Recovery Owner-Admission Blocker

Status: `historical blocker; superseded by implemented INF-3W exact unique-crop recovery row`

## Reviewed Shape

The reviewed candidate is intentionally narrow:

```text
committed project-visible
gameplay.ecology.weather_front.propagated@1
  weather_ref = weather:rain
  target_region_ref = one committed target region
+ one exact current damaged CropRecord in that region
-> existing EcologyHazardAuthority
-> one Ecology-owned crop health recovery record
```

This is not an approval for a generic crop recovery operation. It does not
consume `gameplay.ecology.drought_process_advanced`, does not create a crop
recovery registry, and does not add fanout, inventory, production, payment, or
cross-domain semantics.

## Existing Facts

| Boundary | Existing committed fact | Reusable fence |
| --- | --- | --- |
| Source owner | `EcologyHazardAuthority` | Existing project-visible Ecology stream |
| Source event | `gameplay.ecology.weather_front.propagated` | Payload currently carries `source_region_ref`, `target_region_ref`, `weather_ref`, `tick`, policy data, and region/environment revision pins |
| Source classification | `weather_ref = weather:rain` | Must be read from the committed event; caller weather values and drought process events are invalid |
| Crop projection | `CropRecord` with `crop_ref`, `region_ref`, optional `plot_ref`, `health`, `growth_basis_points`, `revision`, and `owner_ref` | Existing Ecology regional projection; project view removes authority-only provenance |
| Existing write family | `gameplay.ecology.crop.recorded` | Existing Ecology owner event, currently used for initial records and seasonal/drought process updates |
| Target stream | `gameplay:ecology:{target_region_ref}` | Existing Ecology stream pattern |
| Privacy | `project` | Source, crop evidence, target event, and outbox must remain project-scoped |
| Append/replay spine | `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()` and `EcologyHazardAuthority.regional_replay()` | Full and checkpoint-tail replay already exist for the regional record stream |

## Exact Blocker

The current facts do not form a semantically complete

```text
one committed source event/state -> one exact target record
```

tuple. The following boundaries are absent and cannot be inferred from
`weather:rain`, a `facility_kind`-style string, a numeric health value, or a
caller request:

1. **Crop identity binding.** The weather-front event identifies a target
   region, not a `crop_ref`, `plot_ref`, or crop revision. A target region may
   contain zero, one, or multiple project-visible crops. Selecting the last
   crop, first crop, sorted crop, or all crops would be an implicit selector or
   fanout.
2. **Damaged predicate.** `CropRecord` has no lifecycle/status or damage
   evidence. `health < 100` is a possible predicate, but it is not an
   approved `predicate_ref` and does not distinguish damage from any other
   gameplay cause.
3. **Recovery policy.** No committed policy fixes whether recovery adds a
   bounded amount, restores a fixed value, or uses another deterministic rule.
   The drought process's `5` health decrement is not a rain recovery policy and
   cannot be mirrored or inverted.
4. **Provenance payload.** The existing `crop.recorded` payload has generic
   `record`, `source_revision`, and `causal_parent_refs` fields. It does not
   require the weather event id/revision, crop-before revision/health,
   recovery policy revision, or an exact row identifier. Reusing it without
   those fixed fields would make replay unable to prove that the record came
   from this row rather than a seasonal process or another crop write.
5. **Lifecycle contract.** There is no approved terminal/repeat/reversal rule
   for rain recovery. A second rain front could be a new recovery, a duplicate,
   or a zero-write condition; that choice affects idempotency and projection
   semantics.

These gaps were resolved under the approved autonomous row-resolution mandate
by an explicit row-local product decision: target regions use an owner-derived
unique damaged crop selector; damaged means `0 <= health < 100`; recovery is
fixed at `+5` capped at `100`; and `crop.recorded` carries an immutable
row-specific provenance partition. The implemented INF-3W contract is the
operative record. This packet remains historical evidence and does not admit
generic crop recovery.

## Minimum Business Decisions

The following table is the smallest set of choices needed to reopen the row.
The candidate values are examples for decision support only; none is current
fact or frozen content.

| Required decision | Candidate values | Business impact | Recommended decision |
| --- | --- | --- | --- |
| Exact crop selector | `source-event-bound-crop@1` with committed `crop_ref` in the weather event; `unique-project-crop-in-target-region@1` with zero-write on zero/multiple; `plot-bound-crop@1` if a committed source also binds `plot_ref` | Determines whether one crop is provably selected without caller choice or fanout; the first/third require an upstream committed binding fact | Prefer `unique-project-crop-in-target-region@1` only if the product intentionally defines one-crop target regions; otherwise approve a committed source binding |
| Damaged predicate | `predicate:crop-health-below-max@1` meaning `0 <= health < 100`; a committed damage event/projection predicate; another explicitly named owner-derived predicate | Defines which crop states are eligible; a numeric heuristic may conflate unrelated causes | Prefer a named owner-derived predicate, with `health < 100` acceptable only if product confirms it is the complete damage definition |
| Recovery policy | `policy:weather-rain-crop-recovery@1` with fixed delta; fixed restore-to-maximum; another bounded immutable policy revision | Defines the resulting health and prevents hidden balancing behavior | Prefer an explicit fixed policy revision and fixed delta or target value; do not derive it from drought loss |
| Exact outcome/event payload | Reuse `crop.recorded` only after adding fixed provenance fields in the row contract; or a separately admitted exact event family | Determines whether replay can distinguish this row from ordinary crop writes | Prefer the existing `crop.recorded` family only if the payload contract pins source event id/revision, prior/current crop revision, policy revision, and row identity |
| Lifecycle | One recovery per `(weather_event, crop)`; repeat recovery allowed for a later source event; terminal row; no reversal/compensation | Determines duplicate behavior and whether health can be changed repeatedly | Prefer one append per distinct committed weather event and crop revision, with exact duplicate replay and no reversal/compensation |

No recommendation above is an implicit approval. Until these decisions are
made, the row must remain `owner-contract blocked`.

## Future Contract Shape After Approval

Once the minimum decisions are explicit, the row-specific contract can pin:

- capability and outcome identifiers for this rain-to-crop row only;
- `EcologyHazardAuthority` as both existing source/target owner;
- source event type, exact `weather:rain`, source event revision, Ecology stream
  head, target region, and project visibility;
- one owner-derived crop selector and the committed crop's current revision;
- one named damage predicate and one immutable recovery policy revision;
- target stream `gameplay:ecology:{target_region_ref}`;
- one fixed `gameplay.ecology.crop.recorded` payload vector whose provenance
  binds weather event id/revision, crop-before revision/health,
  crop-after revision/health, policy revision, and row identity;
- authority-derived idempotency including source event id, crop ref, source
  crop revision, and fixed policy/contract revision;
- append-derived receipt and the existing Ecology full/checkpoint-tail replay;
- zero-write for unknown/wrong/private/stale source, zero/multiple crop match,
  non-damaged crop, policy/predicate mismatch, privacy or binding conflict,
  revision conflict, duplicate with changed payload, drought-process
  substitution, and any fanout or caller-selected target.

This future shape remains an exact owner-local row. It must not become an
arbitrary `weather -> crop` resolver or generic crop recovery API.

## Verification Disposition

The existing Ecology/weather regression baseline remains green:

```text
16 passed
```

The baseline covers existing regional records, weather propagation, drought
process behavior, and the already admitted Survival rain row. It does not prove
this unadmitted crop-recovery candidate. No implementation was attempted, so
there is no RED-to-green evidence, Harness, catalog admission, or runtime
vertical to report for this candidate.
