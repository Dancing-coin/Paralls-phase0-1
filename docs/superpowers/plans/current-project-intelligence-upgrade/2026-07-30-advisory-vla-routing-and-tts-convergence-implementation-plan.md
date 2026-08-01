# Advisory VLA Routing And TTS Convergence Implementation Plan

- Date: `2026-07-30`
- Status: `production-fast-only; godot-runtime-capture-fast-proof-verified; advisory-deep-parked-non-blocking`
- Design: `2026-07-30-advisory-vla-routing-and-tts-convergence-design.md`

## Scope And Truth Relationship

This plan extends the 2026-07-29 VLA real-provider plan with retained two-route
capability but a fast-only production route.
It does not supersede the mainline dialogue streaming or real-TTS provider plans;
those remain the owners of their own contracts and are updated only for
cross-reference and live-proof status.

## Delivered

1. [x] Add `advisory-fast` / `advisory-deep` request/result state, including
   escalation lineage and bridge observability.
2. [x] Add settings for `qwen3.7-flash` (12s) and `qwen3.7-plus` (20s), plus
   the disabled-by-default `VLA_ADVISORY_DEEP_ENABLED` experiment gate and its
   bounded re-admission thresholds.
3. [x] Add a router that fixes production PQFs to `advisory-fast`; PQF
   attention tags, conflict, missing-input, and low-confidence signals remain
   observable metadata. Only an explicit deep experiment can enable one bounded
   escalation decision.
4. [x] Include route/model identity in cache keys and scheduler dedupe; prefer
   fast at equal priority while preserving owner queue isolation.
5. [x] Make the HTTP adapter send the model selected by the routed request.
   `VLA_PROVIDER_JSON_MODE_ENABLED=false` is the compatibility default; the
   adapter still strictly parses JSON and emits only advisory fields. Safe live
   diagnostics retain only status/code/parameter/category, never a secret or
   provider error body.
   Qwen3.7 fast/deep additionally send documented route-specific
   `enable_thinking=false/true`; this is covered by adapter tests.
   The fast proof remains `vla-provider-live-report.*` for readiness; deep proof
   writes `vla-provider-live-deep-report.*` so it cannot overwrite that evidence.
6. [x] Join router, per-owner scheduler, scoped cache, provider adapter, and
   bounded escalation in `VLAAdvisorySlowPath`, with explicit/PQF clock-domain
   handling and no bridge or authority capability.
7. [x] Add explicit TTS live-proof command, retaining stub and WAV validation.
   Add the DashScope two-step JSON-to-temporary-URL-to-WAV adapter while keeping
   the direct-WAV OpenAI-compatible slot available.
8. [x] Add focused pytest coverage for route selection, escalation bounds,
   cache isolation, priority ordering, configuration, VLA adapter, and TTS.
9. [x] Bind the opted-in fast live proof to a fresh Godot viewport capture. The
   command verifies the sampling runtime report's exact capture artifact ref and
   redacts inline image payloads from the proof report.
10. [x] Add an explicit capture-bound replay benchmark. It archives redacted
    per-attempt evidence and reports success, end-to-end latency, grounding, and
    authority-boundary metrics without inventing an accuracy score.
    The 2026-07-30 three-attempt Godot-capture pilot measured fast at `3/3`
    success (`p50=2.271s`, `p95=2.656s`) and deep at `1/3` success (one
    `17.54s` completion and two approximately `20.5s` timeouts). Both routes
    had zero generated entity/affordance grounding refs. This is a limited
    operational observation, not a statistical SLO or semantic-quality score.
11. [x] Close production routing to `qwen3.7-flash` only. Add
    `VLA_ADVISORY_DEEP_ENABLED=false`; deep-tagged PQFs and fast conflicts stay
    fast with an explicit trace reason, while the plus adapter/config remains
    available only for deliberate re-admission experiments.
12. [x] Add a PQF-inherited grounding catalog for known scene entity, collider,
    anchor, and affordance refs. The HTTP adapter exposes that bounded catalog to the
    provider and strips candidate refs outside it; membership remains advisory
    and cannot be used as visual or semantic scoring credit. Benchmark readiness
    now requires 20 distinct annotation samples across at least two scenes, so
    repeated capture replays cannot masquerade as coverage.
    A fresh MainDemo `qwen3.7-flash` live proof returned the catalog entity
    `char_c` and anchor `world_anchor:actor:char_c` with bridge success in
    `2.559s`; this is a one-sample contract proof only.
    The Godot sampling verifier now requires all four catalog kinds in its PQF.
    A subsequent fast proof returned entity/collider/anchor but not affordance;
    it is recorded as resolvable advisory-reference evidence, not visual
    collider recognition or affordance validation.
13. [x] Add a Godot replay-candidate collector that records camera pose, PNG
    hash, runtime report, and per-candidate log while keeping every capture
    `pending_human_review`. The 2026-07-30 collector produced 20 distinct
    candidates across MainDemo and ThroneHallWalkPreview; none are promoted to
    the official annotation manifest automatically.

## Pending External Evidence

1. [x] `qwen3.7-flash` is the sole production VLA provider, with
   `enable_thinking=false`. The fast report promotes provider readiness. On
   2026-07-30 the fast route also passed from a
   fresh Godot viewport capture with a matching six-provider runtime report;
   this proves the bounded probe/capture/live-VLA chain, not general gameplay
   coverage or a latency SLO. `qwen3.7-plus` remains disabled in production:
   its replay pilot reached only `1/3` success and added no grounding refs, so it
   has not met re-admission evidence.
2. [x] Configure the selected DashScope TTS workspace/model/voice mapping and
   run the explicit provider proof. On 2026-07-31 it returned a ready 24 kHz
   mono WAV clip through `dashscope_http`.
3. [x] Run Godot with a real TTS clip. The explicit probe consumed the real
   WebSocket payload in `SpatialVoiceController`, created `AudioStreamWAV`, and
   started the spatial player without a clip rejection or stub fallback. This is
   a runtime consumption proof, not a physical speaker listening test.
4. [ ] Implement sentence/pause clip queueing after the dialogue streaming
   transport exposes stable segment boundaries; do not implement token/audio
   streaming before its jitter and cancellation contract is designed.
5. [ ] Create and review at least 20 distinct multi-scene Godot annotation
   samples with known entity/collider/anchor visibility truth before assigning
   semantic accuracy or quality superiority to either VLA route. Each capture
   must carry its known advisory grounding catalog, but semantic review must
   exclude that catalog, PQF fields, and structured facts from model credit.
   Only then may replay latency percentiles inform a configuration decision.
   A 20-capture, two-scene candidate corpus is now available at
   `.harness/verification/vla-replay-candidate-captures.json`; the remaining
   blocker is human review of visible truth and score policy before promotion.
   A two-scene MainDemo/ThroneHallWalkPreview bootstrap manifest and verifier now
   exist; it is valid but explicitly not coverage-ready, and it excludes
   PQF/structured-fact prompt context from model credit.
   `throne-hall-walk-preview-001` has completed a scoped fast live proof and a
   three-attempt replay (`3/3`; `p50=2.949s`, `p95=3.219s`) with bridge and all
   authority boundaries passing. It still generated zero entity/affordance refs.
   The multi-scene replay command now accepts repeated annotation sample IDs;
   deep and 20-sample coverage remain pending.

## Verification Commands

```powershell
python -m pytest -q backend/tests/test_vla_advisory_routing.py backend/tests/test_vla_provider_backend_adapter.py backend/tests/test_vla_slow_path_scheduler.py backend/tests/test_vla_provider_cache_isolation.py backend/tests/test_vla_percept_bridge.py backend/tests/test_config_runtime_modes.py backend/tests/test_tts_service.py
python scripts/verification/verify_vla_provider_backend.py
python scripts/verification/verify_model_provider_readiness.py
python scripts/verification/verify_godot_sampling_production_grade_providers.py --godot-exe <Godot-console-exe>
python scripts/verification/harness.py --profile vla-provider-backend
python scripts/verification/harness.py --profile model-provider-readiness
python scripts/verification/harness.py --profile docs
```

Explicit external calls, deliberately excluded from normal harness execution:

```powershell
python scripts/verification/verify_vla_provider_live.py --allow-live-call --run-id <run-id>
python scripts/verification/verify_vla_provider_live.py --allow-live-call --use-godot-runtime-capture --run-id <run-id>
python scripts/verification/benchmark_vla_advisory_routes.py --allow-live-call --samples 3
python scripts/verification/benchmark_vla_advisory_routes.py --allow-live-call --route advisory-fast --annotation-sample-id throne-hall-walk-preview-001 --samples 3
python scripts/verification/verify_vla_replay_annotations.py
python scripts/verification/verify_vla_replay_second_scene_capture.py --godot-exe <Godot-console-exe>
python scripts/verification/capture_vla_replay_candidates.py --godot-exe <Godot-console-exe> --variants-per-scene 10
python scripts/verification/verify_vla_provider_live.py --allow-live-call --route advisory-deep --run-id <separate-deep-run-id>
python scripts/verification/verify_tts_provider_live.py --allow-live-call
```
