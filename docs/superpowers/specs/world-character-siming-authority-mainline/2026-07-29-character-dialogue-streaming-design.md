# Character Dialogue Streaming Design

Date: `2026-07-29`

Status: `implemented`

## Purpose

This design upgrades character `dialogue_generation` from a single completed
payload to streamed display text without creating a second character-model
entry point or changing the authority status of a dialogue result.

## Current Facts

- `DialogueService` already calls `CharacterModelGateway.run_task(...)`.
- The gateway prepares the request, invokes `CharacterModelProvider`, and
  validates the completed result with `CharacterStructuredOutputValidator`.
- The WebSocket endpoint currently waits for that completed result and emits
  only `dialogue_response`.
- A live provider call is conditional: `DIALOGUE_MODE=online`, a non-local
  route, and provider credentials/configuration are required. The default
  stub mode and several unconfigured dialogue routes intentionally use the
  local fallback; they are not evidence of a real provider call.

## Scope

Only `task_kind="dialogue_generation"` gains streaming.

`l2_reasoning` and `l3_planning` remain completed structured requests. Their
outputs keep their current provider, validator, and runtime-consumption
semantics. A partial dialogue token is presentation data, never an L2 belief,
an L3 plan, a world result, or an authority event.

## Main Path

```text
DialogueService
-> CharacterModelGateway.stream_dialogue_task
-> CharacterModelProvider.stream_dialogue
-> provider SSE or local fallback chunks
-> CharacterStructuredOutputValidator (completed output only)
-> websocket presentation frames
-> completed DialogueResponse
-> memory, timeline, observatory, and audit writeback
```

The existing synchronous `run_task` path remains the main path for L2/L3 and
for existing non-stream callers. The dialogue stream method is an additional
operation on the same gateway/provider/validator instances, not a separate
model entry point.

## WebSocket Contract

The existing inbound `player_input` / `dialogue_submit` accepts an optional
`request_id`. When absent, the backend generates one. The server emits:

| Family | Direction | Required payload fields | Meaning |
| --- | --- | --- | --- |
| `dialogue_stream_start` | outbound | `request_id`, `actor_id`, `target_actor_id` | display stream accepted |
| `dialogue_stream_delta` | outbound | `request_id`, `sequence`, `delta`, `accumulated_chars` | non-authoritative display text |
| `dialogue_response` | outbound | current `DialogueResponse` fields plus `request_id` | completed, validated authority-facing result |
| `dialogue_stream_end` | outbound | `request_id`, `status`, `partial_chars`, `fallback_used` | terminal stream state |
| `dialogue_stream_cancel` | inbound | `request_id` | cooperative cancellation request |

`dialogue_response` remains compatible with old clients. `request_id` is
optional on the model so older producers and consumers remain valid.

## Completion, Cancellation, Timeout, And Fallback

- Only a completed provider output is passed to
  `CharacterStructuredOutputValidator` and emitted as `dialogue_response`.
- Only that final response is synthesized by TTS and written to
  `CharacterAgentRuntime` memory, timeline, observatory, and audit surfaces.
- `dialogue_stream_cancel` sets a cooperative cancellation signal. The server
  emits `dialogue_stream_end(status="cancelled")`, stops forwarding chunks,
  and does not persist or synthesize the partial output. A blocking urllib
  read may finish at its configured timeout, but its output is discarded.
- A provider timeout/failure after any delta emits
  `dialogue_stream_end(status="timed_out"|"failed")`; the client must discard
  its partial display and no final result is persisted.
- A local route, an unconfigured permissive dialogue route, or a hybrid
  provider failure before the first delta emits local fallback chunks and a
  normal validated `dialogue_response`, with `fallback_used=true` in the end
  frame. A strict online provider failure is reported rather than silently
  splicing a different answer after visible provider text.

## Provider Streaming Format

The current compatible chat-completions providers are called with
`stream=true` for dialogue only. The stream prompt requests spoken text, not
the old JSON envelope. Provider SSE `choices[0].delta.content` values become
display deltas. After `[DONE]`, the provider creates the existing dialogue
shape with the accumulated content and the current neutral stream tone; the
gateway validates it before completion. Rich streamed tone metadata is a
separate future protocol addition.

## Acceptance Criteria

1. A local dialogue submission emits start, ordered deltas, final
   `dialogue_response`, then a completed end frame.
2. The final response remains the only dialogue memory/audit writeback.
3. Cancellation and post-delta failure do not create a final response or
   writeback.
4. Local and safe pre-first-delta fallback complete through the same validator.
5. Tests prove L2/L3 do not receive a streaming API.
6. Godot routes stream frames through explicit presentation-bus signals while
   retaining the existing `dialogue_received` terminal path.
