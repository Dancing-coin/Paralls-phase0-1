# Phase 0 Correlated ACK and Backpressure Stabilization Design

Date: 2026-07-11

Status: approved for implementation planning

## 1. Problem

The Heavenly Graph Foundation completion ladder is blocked by an existing Phase 0 runtime proof failure. The Godot autotest sends the far-move request and the expected failed interaction, but the final interaction is not settled before the test times out and shuts down.

The failure is caused by two coupled behaviors:

1. `MainDemoController.gd` treats any ACK with route `local_motion` or `esm_service` as the ACK for the request currently being awaited. ACKs do not carry a request identity, so an older delayed ACK can advance a newer test stage.
2. The main websocket processes one inbound envelope and synchronously sends its complete outbound message list before receiving the next envelope. Multimodal fact handling can generate a large outbound burst, so later player inputs can remain queued beyond the autotest's fixed timeout.

The observed failure happens before ESM produces a constraint result. It is not evidence that ESM accepted an invalid interaction.

## 2. Goals

- Give every Godot-generated player input a stable request identity.
- Echo that identity in the backend ACK without breaking old clients.
- Make the Phase 0 autotest wait for the ACK belonging to the exact request it sent.
- Match the expected failed-interaction result to the current interaction through the existing world-result correlation contract.
- Stop new autotest sampling traffic while the final authoritative failure proof is being produced.
- Replace silent timeout continuation with explicit stage failure evidence.
- Preserve the current ESM authority boundary and websocket architecture.

## 3. Non-goals

- No rewrite of the websocket into independent reader and writer tasks.
- No queue broker, external transport, retry service, or priority scheduler.
- No change to ESM interaction acceptance or constraint rules.
- No change to Siming, Heavenly Graph, character memory, story orchestration, or Godot presentation ownership.
- No general production telemetry redesign.

## 4. Considered approaches

### 4.1 Chosen: correlated ACK plus bounded quiescence

Add a backward-compatible `request_id` to player inputs, echo it in ACKs, and make the autotest wait for exact identities. After the successful interaction proof is complete, pause further sampling and wait for a bounded quiet window before sending the final move and failed interaction.

This is the smallest approach that fixes both false ACK attribution and deterministic test starvation while improving the real protocol.

### 4.2 Rejected: timeout-only Harness stabilization

Increasing timeouts or reducing log volume may make the current run pass, but route-only ACK matching remains incorrect. A delayed ACK could still advance the wrong request.

### 4.3 Deferred: concurrent websocket read/write queues

Separating reads and writes would address transport head-of-line blocking more generally, but it changes lifecycle, ordering, backpressure, and shutdown behavior. That redesign is outside this repair.

## 5. Protocol contract

### 5.1 Player input request identity

`PlayerInputBase` gains:

```python
request_id: str = ""
```

The empty default preserves compatibility with existing tests, scripts, and clients.

`PlayerIntentMapper.gd` generates a non-empty ID for every emitted player input using:

```text
player_input:<actor_id>:<intent_type>:<producer_ts>:<sequence>
```

`producer_ts` is captured once per input and reused in both the request ID and payload. `sequence` is a mapper-local monotonically increasing integer, preventing collisions when multiple requests are emitted in one millisecond.

### 5.2 ACK echo

For a valid `player_input`, the backend ACK payload includes:

```json
{
  "accepted": true,
  "source_type": "player_input",
  "route": "local_motion",
  "request_id": "player_input:char_c:move_intent:1234:8",
  "intent_type": "move_intent",
  "producer_ts": 1234
}
```

The route remains present for compatibility and observability. Old clients that omit `request_id` receive the same ACK shape with an empty request ID.

Invalid-payload ACK behavior remains unchanged because no valid `PlayerInputBase` instance exists from which to echo identity.

### 5.3 World-result correlation

ESM remains unchanged. Interaction world results continue to use the current correlation form:

```text
interact:<producer_ts>
```

The Godot autotest records the failed interaction's `producer_ts` and accepts `constraint_state_result` only when its `correlation_id` matches that interaction.

## 6. Godot controller state

The route-only booleans are removed:

- `pending_failed_move_ack_seen`
- `pending_failed_interaction_ack_seen`
- uncorrelated `pending_failed_interaction_result_seen`

They are replaced by request-scoped state:

```text
acknowledged_request_ids: Dictionary
pending_failed_interaction_correlation_id: String
matched_failed_interaction_result: bool
last_backend_activity_ms: int
autotest_transport_quiescent: bool
```

`_on_backend_ack_received` records only non-empty `request_id` values. It does not infer request completion from `route`.

`_on_world_result_received` updates `last_backend_activity_ms` and marks the failed-interaction result only when both result type and correlation ID match.

The input emitters return a small request descriptor containing `request_id` and `producer_ts`. Callers that do not need correlation may ignore the return value.

## 7. Autotest execution flow

The final Phase 0 sequence becomes:

1. Submit dialogue and wait using existing evidence behavior.
2. Send the near move and successful interaction.
3. Wait until the successful interaction has produced its ACK and required authoritative result evidence.
4. Enter transport quiescence:
   - stop periodic near-object and spatial-access sampling;
   - prevent new derivative autotest-only multimodal emissions after the already observed successful settlement;
   - wait for a 500 ms interval with no backend activity, bounded by 10 seconds.
5. Send the far move and wait up to 10 seconds for the ACK whose `request_id` matches that move.
6. Send the interaction without a near-object fact and wait up to 10 seconds for its matching ACK.
7. Wait up to 10 seconds for `constraint_state_result` whose correlation ID is `interact:<failed-interaction-producer_ts>`.
8. Only after that match, log `phase0_autotest_stage:failed_interaction_resolved`, capture the screenshot, and complete shutdown.

The quiet-window barrier does not assert that the websocket has no kernel-level queued bytes. It provides a bounded application-level condition: no new backend message has reached Godot for 500 ms after sampling has been paused.

## 8. Failure behavior

Each bounded wait returns success or failure. On failure, the controller logs exactly one marker:

```text
phase0_autotest_failure:<stage>:<request_id>
```

Valid stages are:

- `transport_not_quiet`
- `far_move_ack_timeout`
- `failed_interaction_ack_timeout`
- `failed_interaction_result_timeout`

After logging the marker, the autotest captures available evidence and shuts down without logging `phase0_autotest_stage:failed_interaction_resolved` or `phase0_autotest_complete`.

The verifier continues to require the real `constraint_state_result`. It must not accept the failure marker as proof of an authoritative failed interaction.

## 9. Backward compatibility

- Existing Python constructors remain valid because `request_id` defaults to an empty string.
- Existing clients may continue using route-based ACK information for display, but the Phase 0 autotest no longer uses it for synchronization.
- Existing world-result schemas and ESM correlation remain unchanged.
- Existing successful interaction, multimodal evidence, character-agent execution, Siming, and observatory proofs remain required.

## 10. Verification design

Implementation follows red-green-refactor:

1. Add a failing backend contract test proving a player-input ACK echoes `request_id`, `intent_type`, and `producer_ts`.
2. Add a failing compatibility test proving an input without `request_id` is still accepted and produces an empty echoed ID.
3. Add a failing Godot source-contract test proving request IDs are generated with a collision-safe sequence and the controller no longer uses route-only pending flags.
4. Add a failing controller source-contract test proving all final-stage waits are request/correlation scoped and timeout paths do not log the success marker.
5. Implement the minimal protocol and controller changes.
6. Run focused backend and verification-script tests.
7. Run full `python -m pytest -v`.
8. Run `python scripts/verification/harness.py --profile phase0` and require all strict checks to pass.
9. Run `python scripts/verification/harness.py --profile all` and require `overall_harness_passed=True`.

## 11. Expected implementation scope

Expected files are limited to:

- `backend/app/models/player_input.py`
- `backend/app/main.py`
- `backend/tests/` tests covering player-input routing and ACK compatibility
- `scripts/player/PlayerIntentMapper.gd`
- `scripts/phase0/MainDemoController.gd`
- `scripts/verification/tests/` source-contract tests for the Godot synchronization flow
- the supplemental implementation plan for this design

No Heavenly Graph foundation file is modified by this repair.

## 12. Completion criteria

The repair is complete only when:

- every Godot-emitted player input carries a non-empty collision-safe request ID;
- backend player-input ACKs echo request identity and timing fields;
- legacy requests without an ID remain valid;
- the Phase 0 autotest uses request-scoped ACK waits and correlation-scoped constraint waits;
- timeout paths produce failure evidence and never produce the success marker;
- focused tests, full pytest, `phase0`, and broad `all` Harness all pass;
- the final branch diff still preserves the Heavenly Graph architectural boundaries.
