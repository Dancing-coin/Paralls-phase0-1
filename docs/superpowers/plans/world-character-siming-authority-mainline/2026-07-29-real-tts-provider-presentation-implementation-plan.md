# Real TTS Provider Presentation Implementation Plan

Status: `real-provider-and-godot-consumption-verified`

Date: `2026-07-29`

## Scope

Implement the v1 provider-agnostic TTS presentation contract described by
`2026-07-29-real-tts-provider-presentation-design.md`. Keep stub behavior and
the existing dialogue, character execution, ESM, and Siming contracts stable.

## Delivered Steps

1. Add `DialogueAudio` as an optional `DialogueResponse.audio` attachment.
2. Replace discarded `TTSService.synthesize()` return values at every dialogue
   construction site with the attached audio contract.
3. Add a `TTSProvider` boundary, retain the direct-WAV `openai_compatible`
   slot, and add the selected `dashscope_http` adapter. The adapter submits the
   Qwen Audio TTS JSON request, validates its returned HTTPS audio URL, then
   downloads the WAV before it enters the v1 contract.
4. Add explicit environment configuration, deterministic actor voice mapping,
   PCM WAV validation, a `1,000,000` byte encoded-payload limit below Godot's
   `1 MiB` receive buffer, and failure-to-stub fallback.
5. Decode the complete base64 WAV payload in `SpatialVoiceController` into
   `AudioStreamWAV`, preserve spatial playback and auditory facts, and retain the
   legacy stub log path. Treat a DashScope streaming-size `data` header as the
   complete bytes available at EOF while rejecting every other truncated chunk.
6. Add unit coverage for audio contract, voice mapping, provider fallback, WAV
   validation, and dialogue attachment. Run backend and static verification.

## Deferred Work

- Sentence/pause segmentation and clip queueing after streamed dialogue text has
  an ordered delta contract.
- Provider byte-stream transport, jitter buffering, retry/cancellation semantics,
  and lip-sync timing.
- Sentence/pause segmentation and clip queueing after dialogue streaming exposes
  stable segment boundaries. Do not replace the bounded v1 clip with unbounded
  token/audio streaming before its jitter and cancellation contract exists.

The explicit verification commands are:

```powershell
python scripts/verification/verify_tts_provider_live.py --allow-live-call
python scripts/verification/verify_tts_godot_playback.py --allow-live-call
```

They are not normal harness profiles. On 2026-07-31 both passed: the selected
DashScope adapter produced a ready clip and Godot consumed it through the real
WebSocket path. The latter proves player consumption, not a human listening test.

## Verification Commands

```powershell
python -m pytest -v backend/tests/test_tts_service.py backend/tests/test_character_service.py backend/tests/test_ws_protocol.py backend/tests/test_config_runtime_modes.py
python -m pytest -v
python scripts/verification/verify_phase0.py
python scripts/verification/harness.py --profile all
```
