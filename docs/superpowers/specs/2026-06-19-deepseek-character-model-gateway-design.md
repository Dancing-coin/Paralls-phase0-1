# DeepSeek Character Model Gateway Design

Date: `2026-06-19`

## Purpose

This spec defines how the repository should connect the character-agent runtime to DeepSeek as the first live online model provider without freezing the current single-provider stopgap as long-term architecture truth.

It exists because the repository already has:

- `CharacterModelGateway`
- `CharacterModelRouter`
- `CharacterModelProvider`
- `CharacterContextBuilder`
- `CharacterPromptPolicy`
- `CharacterStructuredOutputValidator`

but the current provider surface is still only a thin generic HTTP POST seam with offline fallback, not a real provider-aware runtime boundary.

The goal of this change is to:

1. make DeepSeek the first real online provider for `L2`, `L3`, and dialogue generation
2. preserve the current local fallback path
3. make the gateway/provider/router stack router-ready for future online providers
4. avoid over-expanding into a full multi-provider runtime before the first live provider is proven

## Problem

The current `CharacterModelProvider` does not speak a real model-provider protocol.

It currently:

- accepts the full gateway request object
- posts it directly to `CHARACTER_MODEL_ENDPOINT`
- assumes a raw JSON object or `{ "output": ... }` response
- falls back offline on failure

That is enough for placeholder integration, but it is not enough for a standard live provider integration because:

- DeepSeek expects an OpenAI-compatible chat-completions request shape
- the current provider seam does not clearly separate:
  - route selection
  - provider identity
  - provider request translation
  - provider response normalization
- the current env contract is too generic to be a stable provider-facing runtime boundary

If DeepSeek is wired into this seam without redesigning the boundary, the repository will end up with:

- provider-specific behavior hidden inside a generic endpoint string
- no clean basis for future routing work
- more migration debt inside the model path

## Goal

Implement a router-ready online model boundary that makes DeepSeek the first real live provider for the current character-agent runtime.

This first integration must cover:

- `CharacterAgent L2`
- `CharacterAgent L3`
- dialogue generation

through the existing:

- `CharacterModelGateway`
- `CharacterModelRouter`
- `CharacterModelProvider`

without changing the character business logic entry points that already consume the gateway.

## Non-Goals

This change does not attempt to ship:

- a full provider registry for multiple live vendors
- provider-specific prompt policy trees
- model-choice UI
- long-horizon model cost management
- streaming response support
- tool calling
- a complete rewrite of the current `L2/L3` runtime contracts

## Existing Source Of Truth

This design must remain aligned with:

- `docs/superpowers/specs/2026-06-15-full-character-agent-runtime-with-llm-design.md`
- `docs/superpowers/plans/2026-06-15-full-character-agent-runtime-with-llm-implementation-plan.md`
- current gateway code under `backend/app/character_agent/gateway/`

The important architectural truth already frozen in the full-runtime spec is:

- provider abstraction is required
- the default path is online-first
- local and hybrid-ready fallbacks must remain possible
- character business logic must not be tied directly to one vendor API

## Design Decision

The repository should implement **one live provider now, but in a router-ready shape**.

That means:

- **yes** to DeepSeek as the current online provider
- **yes** to explicit provider identity in routing/config
- **yes** to provider-specific request/response translation
- **yes** to local fallback preservation
- **no** to a broad multi-provider runtime rollout in this pass

## Considered Approaches

### Approach A: Keep the current generic endpoint seam and point it at DeepSeek

Implementation idea:

- set `CHARACTER_MODEL_ENDPOINT=https://api.deepseek.com/...`
- keep sending the current raw gateway request body
- adapt as little code as possible

Pros:

- smallest diff
- fast to wire

Cons:

- not a standards-compliant DeepSeek integration
- request translation remains implicit and brittle
- future router work would still start from the wrong seam
- contradicts the full-runtime design direction

Decision:

- rejected

### Approach B: Full multi-provider runtime now

Implementation idea:

- provider registry
- multiple online provider adapters
- route policy expansion
- env/config surface for multiple vendors

Pros:

- most future-facing

Cons:

- scope too broad for the current need
- delays first proven live provider integration
- creates unnecessary configuration and verification burden

Decision:

- rejected for this pass

### Approach C: DeepSeek-first provider-aware integration with router-ready contracts

Implementation idea:

- keep the current gateway entry points
- upgrade router output to explicit provider identity
- upgrade provider into a provider-aware adapter layer
- add DeepSeek chat-completions translation
- normalize DeepSeek output back into current structured task outputs
- preserve offline fallback

Pros:

- standard DeepSeek integration
- aligned with the full-runtime LLM plan
- smallest architecture that still scales correctly
- does not force premature multi-provider complexity

Cons:

- larger than a pure endpoint-string swap
- requires careful structured-output handling

Decision:

- recommended and selected

## Target Runtime Shape

The resulting boundary should look like:

```text
CharacterAgent L2 / L3 / Dialogue
-> CharacterModelGateway
-> CharacterModelRouter
-> CharacterModelProvider
-> DeepSeek adapter path or local fallback path
```

The gateway remains the only business-facing entry point.

The router decides:

- route mode
- provider kind

The provider decides:

- whether to call a live provider
- how to translate the request
- how to normalize the response
- when to fall back locally

## Router Design

`CharacterModelRouter` should stop returning only:

- `online`
- `local`
- `hybrid`

as abstract ideas.

It should return explicit route metadata such as:

- `route_mode`
- `provider_kind`

For this pass, the stable provider kinds should be:

- `deepseek`
- `local`
- `hybrid`

Recommended behavior:

- default route:
  - `route_mode=online_default`
  - `provider_kind=deepseek`
- explicit local override:
  - `route_mode=local_only`
  - `provider_kind=local`
- explicit hybrid override:
  - `route_mode=hybrid_ready`
  - `provider_kind=hybrid`

`hybrid` in this pass does not require a second live provider.

It only means:

- try DeepSeek first
- preserve local fallback behavior on provider failure or invalid output

## Provider Design

`CharacterModelProvider` should become a provider-aware adapter layer.

For this pass it needs three behaviors:

1. `local`
   - do not make a network call
   - use existing offline output generation

2. `deepseek`
   - build an OpenAI-compatible chat-completions request
   - call DeepSeek over HTTPS
   - parse the response
   - extract structured JSON content

3. `hybrid`
   - attempt the DeepSeek path
   - fall back to local output on network, parse, schema, or provider failure

The provider must not expose the user’s raw secret in logs, exceptions, or repo files.

## DeepSeek Request Contract

The provider should translate the current gateway request into a DeepSeek chat-completions request with:

- `model`
- `messages`
- optional `temperature`
- structured system instruction from `prompt["system_instruction"]`
- compact user payload built from:
  - `prompt["user_instruction"]`
  - `prompt["required_output_keys"]`
  - task kind
  - structured context summary when needed

The implementation should prefer a constrained response format that asks the model to return one JSON object matching the task contract.

The provider must not send the entire internal gateway request as the raw vendor payload.

## DeepSeek Response Normalization

The provider should normalize DeepSeek output back into the current task-shaped dictionaries expected by:

- `CharacterStructuredOutputValidator`
- `CharacterAgentL2Service`
- `CharacterAgentL3Service`
- `DialogueService`

This means the provider must:

- extract the assistant content
- parse JSON safely
- reject non-object outputs
- let the validator remain the authoritative task-level schema gate

If the provider returns malformed JSON or missing keys:

- local fallback is allowed in `hybrid`
- local fallback is not required in explicit strict-online mode because that mode does not exist in this pass

## Environment Contract

The repository should move from the old generic env seam toward a provider-aware contract.

For this pass, the runtime env surface should be:

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_MODEL`
- optional `DEEPSEEK_BASE_URL`

Compatibility may be preserved for the older generic envs if useful:

- `CHARACTER_MODEL_API_KEY`
- `CHARACTER_MODEL_ENDPOINT`

But the new provider-aware env names should become the preferred runtime truth.

Secrets must be stored only in local environment configuration, never committed.

## Security Rule

The DeepSeek key must:

- not be written into tracked files
- not be echoed back in logs or responses
- not be copied into docs/specs/plans/tests

After the implementation is proven, rotating the currently shared key is strongly recommended because it has already been exposed in-thread.

## Testing Requirements

The change must add or update focused tests for:

- router provider-kind selection
- provider request translation for DeepSeek
- provider response normalization from DeepSeek-shaped responses
- hybrid fallback behavior on HTTP or JSON failure
- gateway compatibility for:
  - `l2_reasoning`
  - `l3_planning`
  - `dialogue_generation`

The tests should not require live network access.

They should use recorded/mock provider payload and response fixtures at the provider seam.

## Verification Requirements

Minimum verification for the implementation pass:

- focused gateway/provider/router pytest
- broader character-agent gateway tests
- `python -m pytest -v` in `backend/`
- relevant harness profiles if touched docs or runtime verification expectations change

This pass does not need Godot runtime proof unless the integration changes runtime actor behavior outside the backend gateway path.

## Acceptance Criteria

This DeepSeek integration is complete when all are true:

1. `CharacterModelGateway` remains the only business-facing model entry point
2. `CharacterModelRouter` returns explicit DeepSeek-aware provider metadata
3. `CharacterModelProvider` can translate current gateway requests into DeepSeek chat-completions requests
4. `L2`, `L3`, and dialogue generation can all use the DeepSeek path through the existing gateway
5. local fallback still works
6. no secret is written into tracked repo files
7. the resulting seam is router-ready for future providers without requiring a redesign
8. the implementation does not expand into an unnecessary multi-provider runtime rollout

## Summary

The correct next step is not a generic endpoint swap and not a full provider-platform rollout.

It is:

- DeepSeek as the first real online provider
- router-ready provider-aware contracts
- local fallback preserved
- no change to the business-facing character-agent gateway surface
