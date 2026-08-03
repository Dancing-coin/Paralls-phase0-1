# Advisory VLA Routing And TTS Convergence Design

- Date: `2026-07-30`
- Status: `production-fast-only; godot-capture-fast-live-proof-verified; advisory-deep-parked-non-blocking`
- Parent: `current-project-intelligence-upgrade`
- Extends: `2026-07-29-vla-real-provider-adapter-live-proof-design.md`
- Coordinates with: `world-character-siming-authority-mainline/2026-07-29-character-dialogue-streaming-design.md` and `2026-07-29-real-tts-provider-presentation-design.md`

## Canonical Ownership

This is the single convergence document for the next provider route. It extends,
but does not replace, the VLA HTTP/live-proof design. The mainline dialogue
streaming design remains the canonical text-stream contract and the mainline TTS
design remains the canonical audio-presentation contract. The 2026-07-23/24
Kimi documents are historical analysis only.

## Fixed Boundaries

```text
PQF + artifact refs + structured scene/entity/collider/anchor refs
  -> VLAProviderRequest (production: advisory-fast)
  -> VLAAdvisorySlowPath (scoped cache / per-owner scheduler / provider adapter)
  -> VLAProviderResult
  -> ModalityInterpretationResult
  -> CrossModalUnderstandingResult
  -> CanonicalPerceptBundle advisory uncertainty and hypotheses
```

VLA is never a controller. It cannot write world truth, L1 projected facts, ESM
authority, settlement, transforms, physics, bones, rigid bodies, or actor
controls. Known Godot scene/entity/collider/anchor data remains the first source
for known facts; VLA estimates only supplement unresolved perception.

`CharacterModelGateway -> CharacterModelProvider ->
CharacterStructuredOutputValidator` remains the sole character-model path.
`SimingRuntime.tick() -> SimingEventProducer -> AuthorityEventBus` remains the
sole Siming event path. Neither consumes a partial VLA/TTS result as authority.

## Production Fast-Only Route

| Route | Default model | Timeout | Entry rule | Scheduler/cache rule |
| --- | --- | --- | --- | --- |
| `advisory-fast` | `qwen3.7-flash` | 12 seconds | every eligible production PQF, including conflict/high-uncertainty tags | sole production route; cache key includes route, model, version, owner scope, capture and refs |
| `advisory-deep` | `qwen3.7-plus` | 20 seconds | parked, non-blocking, and disabled in production; explicit benchmark/re-admission experiment only | retained separate cache/fingerprint identity; never auto-enqueued while disabled |

Production fast explicitly sends the documented non-standard
`enable_thinking=false` capability. The retained deep experiment sends
`enable_thinking=true` only when an operator deliberately re-enables it. Neither
thinking content nor partial reasoning enters the advisory result or bridge.

The adapter also normalizes a schema-valid provider JSON response whose
`findings` is a single string or `string[]` into restricted advisory finding
objects. This compatibility projection attaches only the request artifact refs
and top-level confidence; it rejects all non-list/non-string findings and never
projects an action or authority field.

The legacy `VLA_PROVIDER_MODEL*` setting remains a compatibility surface for
direct adapter callers. New slow-path work reads `VLA_ADVISORY_FAST_*` and
`VLA_ADVISORY_DEEP_*`; `VLA_ADVISORY_DEEP_ENABLED=false` is the production
default. Both candidates share the configured provider endpoint and API key, but
only fast is scheduled in production.

`VLA_PROVIDER_JSON_MODE_ENABLED` is an explicit transport-capability switch.
It defaults to `false` for the DashScope-compatible route: the adapter continues
to prompt for JSON and strictly validates the resulting advisory schema, but
only sends OpenAI `response_format=json_object` after the target endpoint has
confirmed support. This flag does not loosen output validation or authority
boundaries.

The 12-second fast budget remains bounded slow-path work and must not block a
simulation tick. The retained 20-second deep budget is experimental only; it is
not a production latency allowance.

### Escalation, Conflict, And Degradation

1. Production always chooses fast. Conflict/high-uncertainty tags preserve their
   meaning in metadata but resolve with `deep_route_disabled_use_fast`.
2. A completed fast result never auto-enqueues deep while
   `VLA_ADVISORY_DEEP_ENABLED=false`; consumers record uncertainty/conflict and
   retain structured facts.
3. If deep is explicitly re-enabled for an experiment, it may make one bounded
   escalation only. A deep result never recurses, and timeout/error still emits
   advisory late/degraded output.
4. A VLA/structured-fact disagreement is recorded in `conflict_refs`, not used
   to overwrite a scene fact. A consumer may request another advisory window or
   surface uncertainty, but authority remains elsewhere.
5. Opaque artifact refs never become provider URLs. A real HTTP request needs an
   explicit provider-supported visual source; otherwise it fails closed. The
   adapter accepts `https://` and `data:image/` candidates, but an operator must
   use a provider-accessible HTTPS artifact if that provider rejects inline data.

Both route identity and escalation lineage survive into provider result, modality
findings, and `CanonicalPerceptBundle.uncertainty`; they are observability only.
`VLASlowPath` reads the explicit caller time or the PQF `wall_clock_ts`, never a
different implicit clock domain, when it checks staleness or cache lifetime.

## TTS And Dialogue Streaming

TTS is presentation for already completed dialogue text, not a language-model
replacement and not an authority input. `DialogueAudio` remains an optional
`DialogueResponse.audio` attachment; its failure falls back to stub and cannot
change dialogue text, planning, execution, ESM, world truth, or Siming.

The first latency upgrade is sentence/pause segmentation after ordered dialogue
text deltas: synthesize and queue complete WAV clips with ordered sequence
metadata, then preserve the same validated terminal `dialogue_response` for
memory and audit. True audio-byte streaming is deferred until a separate
chunk/jitter/cancellation/lip-sync transport exists. It must not use partial
text as a character cognition or authority result.

`TTS_MODE=stub` remains supported. `openai_compatible` remains available for a
direct-WAV provider. The selected `dashscope_http` slot sends Qwen Audio TTS
JSON, consumes the temporary provider URL only inside the backend, and requires
the downloaded clip to pass the same mono PCM S16LE WAV validation at the
configured sample rate. An explicit-only `verify_tts_provider_live.py` report is
live proof; configuration, a unit-test fake, or fallback output is not.

## Proof States

- `configured` / `readiness` means endpoint, model, and secret surface can be
  evaluated; it is not a network invocation.
- VLA `real_provider_verified` requires the existing opted-in VLA command, an
  eligible visual artifact, schema-valid advisory result, bridge success, and
  matching redacted run metadata.
- Fast proof is stored at `vla-provider-live-report.*` and is the only VLA
  evidence eligible for fast-route readiness promotion. An explicit deep proof
  is stored separately at `vla-provider-live-deep-report.*`; both passed on
  2026-07-30 with repository-local artifacts, but neither proves Godot capture
  production or scene-runtime latency.
- A Godot viewport proof is a stronger, separate evidence chain: run
  `verify_godot_sampling_production_grade_providers.py`, then run the VLA command
  with `--use-godot-runtime-capture`. The live command requires the current
  runtime report to declare the exact viewport PNG artifact reference, and
  rejects stale captures (five-minute default). Its report preserves the Godot
  runtime report and camera-frame references without storing the image payload.
  The 2026-07-30 `advisory-fast` Godot-capture call passed. The corresponding
  `advisory-deep` call timed out at its configured 20-second budget; it is a
  typed advisory degradation, not deep-route runtime proof or an excuse to
  change the bounded timeout without separate latency evidence.

## Replay Benchmark

`benchmark_vla_advisory_routes.py` is the canonical explicit-only replay tool.
Every attempt delegates to the normal capture-bound live-proof command, archives
only its already redacted report, and records end-to-end wall-clock latency,
provider success, bridge success, grounded-finding ratio, and authority-boundary
compliance per route. The timing includes local image encoding and bridge work;
it is not provider-only latency.

The benchmark requires at least 20 samples before its output is statistically
descriptive, and those must be 20 distinct annotation sample IDs spanning at
least two scenes. Repeating one capture measures retry stability only; it cannot
promote statistical readiness. The benchmark never emits a semantic accuracy
score without a separately reviewed annotation manifest tied to
scene/entity/collider/anchor truth. This prevents a model from receiving credit
for merely repeating prompt context or labels.

The tracked bootstrap manifest is
`docs/verification/vla-advisory-replay-annotation-manifest.json`. It currently
contains two human-reviewed Godot captures (MainDemo and ThroneHallWalkPreview)
and intentionally reports
`bootstrap_valid_not_coverage_ready`. It is a schema and review-control surface,
not an accuracy claim. The verifier rejects a sample that gives model credit for
PQF subject/target fields, structured facts, or the advisory grounding catalog.

`capture_vla_replay_candidates.py` can collect distinct MainDemo and ThroneHall
runtime captures into a separate `pending_human_review` corpus. It checks PNG
hashes and retains camera/report/log evidence, but never changes the official
annotation manifest or semantic-scoring readiness. Promotion remains a human
review decision tied to visible scene truth.

### Grounding Catalog

`PerceptionInputFrame` and `PerceptionQueryFrame` carry a read-only grounding
catalog of known scene entity refs, collider refs, anchor refs, and bounded
affordance refs.
The PQF derives entity/anchor entries from its subject, target, attention, and
anchor identities; L1/Godot scene bindings may add known affordance refs. A
`VLAProviderRequest` must inherit this catalog exactly. The adapter supplies it
as an allowed-reference list and filters every provider candidate ref against
it. Empty catalogs remain valid and result in ungrounded advisory output rather
than an invented ID. Catalog membership only makes a reference resolvable; it is
not visual evidence and never grants world-truth or semantic-score credit.

The 2026-07-30 fresh MainDemo fast proof returned the exact catalog entity
`char_c` and anchor `world_anchor:actor:char_c` after the strict JSON-shape
instruction was added. This proves one catalog-constrained provider result and
the advisory bridge, not collider/affordance recognition, semantic accuracy, or
coverage beyond that single reviewed capture.

A subsequent fresh Godot probe verified that the runtime PQF itself supplied
entity, collider, anchor, and affordance catalog entries. Its fast live proof
returned the catalog entity, collider, and anchor but no affordance. The provider
reported structured-fact support for the identity/collider linkage, so this is a
resolvable advisory-reference proof, not evidence that the collider was visually
recognized or that an affordance is usable.

Live proof may select a reviewed sample with
`--annotation-sample-id <id>`. Its PQF scope is derived from that sample rather
than MainDemo defaults, and its report records the selected scope. On 2026-07-30
the `throne-hall-walk-preview-001` fast proof passed using
`room_throne_hall/throne_hall_walk_preview/central_hall/char_c`; this is a
second-scene transport/bridge proof, not a semantic score.
- TTS `real_provider_verified` requires the opted-in command to return a ready
  complete WAV clip. On 2026-07-31 the selected DashScope adapter passed this
  proof, then a separate Godot probe consumed the real WebSocket payload as an
  `AudioStreamWAV` without clip rejection or stub fallback. This proves local
  player consumption, not physical speaker output.
- Neither proof claims Godot audible playback, long-running quality, latency
  SLOs, or provider safety beyond the proven request.
- `qwen3.7-flash` / `qwen3.7-plus` are the operator-mandated VLA routes. The
  2026-07-30 DashScope probes are recorded as evidence only: the tiny inline
  image was rejected and a repository artifact exceeded a 20-second flash
  probe. A `qwen3-vl-plus` compatibility probe accepted the repository Base64
  artifact, proving that an external image host is not a prerequisite for this
  adapter, but it is not a route replacement or Qwen3.7 live proof.

## Acceptance Criteria

1. Fast/deep requests preserve PQF capture, owner, artifact, and structured
   fact scope while selecting their own model/timeout.
2. Cache and scheduler cannot treat fast/deep work as the same request.
3. Conflict/uncertainty escalation remains one-way, bounded, and advisory.
4. The existing bridge emits route metadata without modifying world truth.
5. Stub TTS, complete-clip TTS, dialogue streaming, and explicit live proof
   remain distinguishable in code and documentation.
