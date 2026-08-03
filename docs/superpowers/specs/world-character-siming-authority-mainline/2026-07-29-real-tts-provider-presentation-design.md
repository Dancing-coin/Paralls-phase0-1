# Real TTS Provider Presentation Design

Status: `real-provider-and-godot-consumption-verified`

Date: `2026-07-29`

Cross-route convergence, including the explicit TTS live-proof status, is
tracked by `current-project-intelligence-upgrade/2026-07-30-advisory-vla-routing-and-tts-convergence-design.md`.

## Purpose And Boundary

This design upgrades dialogue's local audible presentation from a stub marker to
an optionally real, playable audio clip. TTS consumes already-produced dialogue
text. It is not a text-model alternative and does not create, edit, validate, or
settle character intent, Siming output, ESM results, or world truth.

The response remains a complete `dialogue_response`; `audio` is an optional
presentation attachment. A TTS failure cannot alter dialogue text, authority
results, character execution, or Siming routing.

## Contract: `tts_audio.v1`

`DialogueResponse.audio` is either absent or a `DialogueAudio` payload:

| Field | Clip value | Stub/fallback value |
| --- | --- | --- |
| `contract` | `tts_audio.v1` | `tts_audio.v1` |
| `mode` | `clip` | `stub` |
| `status` | `ready` | `stub` or `fallback` |
| `provider` | adapter identity | `stub` |
| `voice_id` | resolved character voice | resolved character voice |
| `content_type` | `audio/wav` | absent |
| `encoding` | `base64` | absent |
| `payload` | complete base64 WAV bytes | absent |
| `sample_format` | `pcm_s16le` | absent |
| `sample_rate_hz` | configured rate, default `24000` | absent |
| `channels` | `1` | absent |
| `sequence`, `is_final` | `0`, `true` | `0`, `true` |

The v1 contract accepts only complete mono PCM signed-16-bit WAV clips. The
backend validates container, PCM encoding, channel count, sample rate, byte rate,
and truncation before the clip reaches the WebSocket. Godot strips the WAV header
and loads the PCM data into `AudioStreamWAV` for 3D playback.

Payloads are deliberately attached to the dialogue envelope rather than emitted
as world events. `TTS_MAX_ENCODED_PAYLOAD_BYTES` defaults to `1,000,000`; Godot
sets its `WebSocketPeer.inbound_buffer_size` to `1 MiB`, leaving frame-envelope
headroom. An over-budget clip becomes a normal stub fallback. Payloads are not
persistent authority records.

## Provider Boundary And Voice Mapping

`TTSProvider.synthesize(content, voice_id) -> bytes` is the provider-neutral
backend interface. `openai_compatible` remains available for providers that
return direct WAV bytes. `dashscope_http` is the selected Alibaba Cloud Model
Studio adapter: it POSTs the Qwen Audio TTS request (`model`, `input.text`,
`input.voice`, `input.format=wav`, and `input.sample_rate`), extracts the
temporary audio URL from the JSON response, and downloads the WAV inside the
backend. If DashScope returns its documented `http` `*.aliyuncs.com` temporary
URL, the adapter upgrades it to HTTPS before download; all other HTTP URLs are
rejected. Provider-specific response schemas and temporary URLs never leak into
Godot.

Voice resolution is deterministic: `TTS_VOICE_MAP_JSON[actor_id]`, otherwise
`TTS_DEFAULT_VOICE`. The JSON map contains provider voice IDs, for example:

```json
{"char_a":"alloy", "char_b":"nova", "char_c":"echo"}
```

Configuration for the selected slot is `TTS_MODE=dashscope_http`,
`TTS_PROVIDER_ENDPOINT=https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer`,
`TTS_PROVIDER_API_KEY`, `TTS_PROVIDER_MODEL`, `TTS_PROVIDER_TIMEOUT_SECONDS`,
and `TTS_OUTPUT_SAMPLE_RATE_HZ`. `{WorkspaceId}` is an operator-supplied Model
Studio workspace identifier, not an API key and not inferable from the DashScope
compatible-mode endpoint. The live verifier rejects the placeholder before any
network request. Missing, unreachable, or invalid provider output produces a
stub fallback and preserves the dialogue response.

## Buffering And Streaming Decision

The initial real path uses one complete bounded dialogue clip, decoded and played
immediately by `SpatialVoiceController`. It needs no client jitter buffer and
keeps retry/fallback and dialogue ordering straightforward.

For the next latency step, choose sentence/pause segmented TTS, not token-level
audio streaming: each segment keeps `sequence` ordering and has `is_final=false`
until the last segment. Godot should queue a next complete clip before the
current clip reaches a configurable low-water mark. This works with the current
text-complete dialogue response and makes failure recovery observable.

True provider audio streaming remains deferred. It requires a separate
`dialogue_audio_chunk` transport, `AudioStreamGenerator`/ring-buffer playback,
sequence-gap handling, jitter thresholds, cancellation, and synchronized
subtitle/lip state. It should be considered only after dialogue text itself has
an ordered streaming contract. It must still terminate in the same complete
`dialogue_response` for audit and memory.

The explicit provider proof command requires an operator-approved opaque run ID
and one `--actor-id` for each final binding, for example
`python scripts/verification/verify_tts_provider_live.py --allow-live-call --evidence-run-id <opaque-run-id> --actor-id <approved-actor-id>`.
The separate Godot consumption proof uses the same run ID and actor set:
`python scripts/verification/verify_tts_godot_playback.py --allow-live-call --evidence-run-id <opaque-run-id> --actor-id <approved-actor-id>`.
The first proves a ready complete provider clip; the second proves that the real
dialogue payload becomes `AudioStreamWAV` and starts the spatial player. Neither
configuration, a unit-test fake, a stub fallback, nor physical speaker output is
treated as the other proof.

## Acceptance Criteria

1. `TTS_MODE=stub` retains audible-fact and `voice_stub_played` behavior.
2. A configured DashScope provider produces `mode=clip`, base64 `audio/wav`,
   mapped voice ID, 24 kHz mono PCM metadata, and a playable Godot stream.
3. Invalid or unavailable provider output falls back to stub without changing the
   dialogue, execution, interaction, or Siming paths.
4. No TTS data becomes ESM/world truth or a Siming input/output contract.
5. The 2026-07-31 explicit proofs returned a ready DashScope 24 kHz mono WAV
   clip and consumed it in Godot without a clip rejection or stub fallback.
