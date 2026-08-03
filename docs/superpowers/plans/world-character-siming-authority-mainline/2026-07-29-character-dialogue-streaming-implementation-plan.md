# Character Dialogue Streaming Implementation Plan

Status: `completed`

## Goal

Deliver streamed character dialogue text through the existing model gateway
chain while retaining a completed validated `dialogue_response` as the sole
memory/audit result.

## Tasks

- [x] Add a dialogue-only provider/gateway streaming operation and preserve
  the synchronous L2/L3 path.
- [x] Add provider SSE parsing, local chunk fallback, cooperative cancellation,
  and terminal error/fallback semantics.
- [x] Add WebSocket stream families and optional dialogue request correlation.
- [x] Write the completed response only after successful validation.
- [x] Add Godot bridge/bus signals for start, delta, and terminal stream state.
- [x] Cover gateway/provider, WebSocket ordering, cancellation/failure policy,
  and Godot signal routing with tests.
- [x] Run focused backend tests, backend-contract harness, and the required
  broad harness profile.

## Verification Commands

```powershell
python -m pytest -q backend/tests/test_character_model_gateway.py backend/tests/test_character_model_provider.py backend/tests/test_character_dialogue_mind_core_integration.py backend/tests/test_ws_protocol.py backend/tests/test_character_actor_bridge_static.py
python scripts/verification/harness.py --profile backend-contract
python scripts/verification/harness.py --profile all
```

## Constraints

- No new dependency or second character model entry point.
- No streamed L2/L3 results.
- Partial text is not memory, audit, authority, or TTS input.
- The final `DialogueResponse` must remain backwards-compatible.
