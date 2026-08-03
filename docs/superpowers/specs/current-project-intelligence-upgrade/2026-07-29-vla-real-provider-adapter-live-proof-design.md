# VLA Real Provider Adapter And Live-Proof Design

- Date: `2026-07-29`
- Status: `implemented-live-proof-blocked`
- Parent: `current-project-intelligence-upgrade` incremental spec tree
- Extended by: `2026-07-30-advisory-vla-routing-and-tts-convergence-design.md`
- Evidence baseline: reviewed `vla_provider.py`, scheduler, cache, percept bridge, PQF contracts, model-provider readiness, and the VLA runtime module document on `2026-07-29`.

## Goal

Close the remaining real-provider gap in the existing VLA advisory slow path. The
first supported transport is an OpenAI-compatible multimodal chat-completions
endpoint, suitable for a configured Qwen3-VL-compatible service. This is an
adapter integration, not a new VLA runtime or an action-control feature.

## Existing Boundary To Preserve

```text
PerceptionQueryFrame + artifact refs + structured fact refs
  -> VLAProviderRequest
  -> per-owner slow-path scheduler / scoped cache
  -> HTTP advisory adapter
  -> VLAProviderResult
  -> ModalityInterpretationResult
  -> CrossModalUnderstandingResult
  -> CanonicalPerceptBundle uncertainty / hypotheses
```

`VLAProviderResult.advisory` is always true. It must never write world truth,
L1 projected facts, ESM authority, settlement, physics, or actor controls.
Known Godot scene/entity/collider/anchor information stays in structured facts
and takes precedence over VLA estimates. A conflicting VLA result is recorded
as an advisory conflict rather than applied as a correction.

## Real HTTP Contract

The adapter sends one non-streaming request to an OpenAI-compatible
`/chat/completions` endpoint. The request contains a JSON-only advisory schema
instruction and PQF identity, owner scope, capture identifiers, artifact refs,
structured fact refs, and attention/spatial context. Image content is sent only
for visual inputs whose `stable_source_ref` is an explicit `https://` URL or
`data:image/...` URL.

Opaque ref IDs stay in the structured input but are never guessed as URLs or
resolved by reading Godot. Without an eligible visual artifact, the adapter
returns `blocked_missing_artifacts` without network I/O.

Provider JSON is projected into a small advisory finding vocabulary: summary,
confidence, candidate entity/affordance refs, uncertainty, conflicts, and
evidence artifact refs. Action, authority, world-state, force, transform,
velocity, bone, collider mutation, and settlement fields are discarded before
constructing `VLAProviderResult`.

## Configuration

```env
VLA_PROVIDER_MODE=http
VLA_PROVIDER_KIND=openai_compatible
VLA_PROVIDER_ENDPOINT=https://dashscope.aliyuncs.com/compatible-mode/v1
VLA_PROVIDER_API_KEY=<secret-not-committed>
VLA_PROVIDER_MODEL=qwen3-vl-plus
VLA_PROVIDER_MODEL_VERSION=<provider-version-or-configured-unverified>
VLA_PROVIDER_TIMEOUT_SECONDS=8.0
VLA_PROVIDER_REQUIRED_ARTIFACT_REFS=<opaque-runtime-ref-marker>
VLA_PROVIDER_LIVE_PROOF_RUN_ID=<fresh-explicit-proof-run-id>
```

`disabled`, `blocked`, and `local` remain valid degraded modes. Secrets never
enter reports, fixtures, or documentation.

## Live-Proof Definition

`real_provider_verified` requires an explicit live invocation, not a unit-test
HTTP stub and not readiness configuration alone. The proof must show an opted-in
call with endpoint/key/model, a non-empty run ID, a PQF with an eligible image
artifact, a schema-valid advisory result, bridge conversion to the canonical
bundle, and redacted evidence. Readiness only promotes this result when its run
ID, provider ID, model ID, endpoint host, runtime artifact marker, and bridge
status match the current configuration. It must also retain timeout/error
advisory degradation.

The live proof is explicit-only and excluded from `harness --profile all`.
Without credentials or an eligible artifact it reports the corresponding
blocked status; that is not a completion claim.

## Acceptance Criteria

1. A compatible endpoint receives a PQF-derived multimodal request and returns
   a `REAL_PROVIDER_VERIFIED` advisory result.
2. Owner context/cache namespace, capture clock, artifact refs, and structured
   fact refs are retained end to end.
3. Missing artifacts, malformed JSON, timeout, and transport errors produce
   typed non-authoritative degradation.
4. Provider output cannot inject action/control/authority/world-state fields
   into the canonical percept bundle.
5. Existing scheduler, cache, bridge, runtime-consumption, and readiness tests
   stay green.

## Non-Goals

- streaming VLA output, model-weight deployment, or new dependencies;
- artifact storage, signed-URL generation, or Godot rescan;
- direct scene binding, action planning, physics, ESM settlement, or world
truth writes.

The route split is now owned by the 2026-07-30 convergence design: default
`advisory-fast` and bounded `advisory-deep` use this same adapter, input
boundary, and proof standard. This document remains the canonical HTTP
transport and VLA live-proof contract.
