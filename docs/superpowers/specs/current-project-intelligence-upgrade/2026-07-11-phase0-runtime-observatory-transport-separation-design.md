# Phase 0 Runtime and Observatory Transport Separation Design

Date: 2026-07-11

Status: approved for written-spec review

## 1. Problem

The correlated-ACK repair now proves the successful interaction and visible world-state change, but the strict Phase 0 run still fails before it can submit the expected failed interaction.

The latest run, `run-20260711-203120-764566`, established this ordering:

1. request `player_input:char_c:interact_intent:40044:7` receives its exact accepted ACK;
2. the correlated action, object, and environment results all arrive;
3. Godot emits the required settlement-derived visual, tactile, thermal, olfactory, physiology, and role-state facts;
4. the backend expands those facts into authority, character, Siming, and observatory projections;
5. the post-success quiet barrier times out before the far move or failed interaction is submitted.

Between the environment result and the timeout, the main websocket delivered 140 messages, including 63 `character_agent_debug_event` messages and 30 `character_agent_debug_snapshot` messages. The main `/ws` endpoint reads one inbound envelope, builds its complete outbound list, sends that list sequentially, and only then reads the next inbound envelope. Runtime/control traffic and observatory/debug projections therefore share one head-of-line blocking lane.

The remaining failure is not an ESM, character-memory, Siming, Heavenly Graph, or multimodal-perception correctness failure. It is a transport projection and drain-proof failure.

## 2. Goals

- Preserve every authority, character, Siming, Heavenly Graph, and multimodal computation.
- Prevent observatory/debug projections from starving gameplay ACKs and authoritative world results on the strict Phase 0 connection.
- Add an exact ordered barrier proving that all earlier client envelopes have been processed before the next proof stage begins.
- Keep the existing single-reader/single-writer websocket lifecycle in this repair.
- Preserve default behavior for existing clients.
- Retain the existing 500 ms quiet window and 10000 ms bounded waits.

## 3. Non-goals

- No concurrent websocket reader/writer task redesign.
- No broker, external queue, priority scheduler, or retry service.
- No deletion or suppression of multimodal facts inside the runtime.
- No change to ESM settlement, world-truth ownership, character cognition, Siming authority, Heavenly Graph, or character memory.
- No general observatory UI rewrite or second Godot websocket client in this repair.
- No timeout increase beyond 10000 ms.

## 4. Considered approaches

### 4.1 Chosen: connection-scoped runtime projection plus ordered barrier

The websocket URL gains a connection-scoped `stream_mode` query parameter. Existing clients default to `full`. The strict Phase 0 autotest connects with `stream_mode=runtime_only`.

`runtime_only` removes observatory-only projections from the main websocket response while retaining all runtime/control messages. The backend still computes the observatory projections and publishes their debug-stream equivalents; only the per-connection main-socket projection is filtered.

The client then sends a correlated `transport_barrier` envelope after pausing autonomous fact producers. Because the current endpoint processes inbound envelopes in FIFO order and finishes sending one envelope's outbound list before reading the next, the exact barrier ACK proves that all earlier envelopes and their retained runtime responses have crossed the main connection boundary. A 500 ms quiet window after the ACK detects any producer that starts new traffic after the fence.

This is the smallest approach that addresses the actual head-of-line cause without discarding multimodal evidence or replacing the websocket architecture.

### 4.2 Rejected: ordered barrier without projection filtering

A barrier by itself would queue behind the same large observatory bursts. The latest run delivered only the first derived-fact responses before the existing 10000 ms bound expired, so a barrier-only repair would not satisfy the approved timeout contract.

### 4.3 Deferred: independent priority writer lanes

A full production transport could use independent gameplay and observatory sockets or priority queues with concurrent reader/writer tasks. That is a larger lifecycle and ordering redesign. The existing `/debug/ws` endpoint provides the future observatory lane, but wiring a second Godot connection is not required to unblock this proof.

## 5. Connection-scoped stream contract

The main endpoint accepts:

```text
/ws
/ws?stream_mode=full
/ws?stream_mode=runtime_only
```

Rules:

- missing `stream_mode` means `full`;
- `full` preserves the current outbound behavior;
- `runtime_only` filters only the observatory-only message types listed below;
- an unknown value is normalized to `full` and recorded in the debug stream, preserving compatibility rather than silently dropping messages.

The observatory-only set is exactly:

```text
character_agent_debug_event
character_agent_debug_snapshot
siming_debug_event
siming_debug_snapshot
world_outcome_trace
scheduling_round_trace
script_beat_event
```

The following remain on `runtime_only` because they participate in gameplay, authority, or visible execution:

```text
ack
dialogue_response
action_request
focus_state
world_result
state_machine_transition
character_runtime_state_snapshot
character_runtime_state_delta
character_agent_output
character_agent_execution
character_agent_suggestion
siming_output
self_body_perceived_event
conversation_candidate_event
```

Any unlisted future message type is retained by default. New observatory-only families must be explicitly added to the filter set with tests.

Filtering happens in `websocket_endpoint` after `_handle_envelope` and `_finalize_outbound_messages` complete but before `websocket.send_json`. This preserves runtime side effects, authority publication, observatory projection generation, and `_emit_debug_from_messages` publication to `/debug/ws`.

## 6. Ordered transport barrier contract

Godot may send:

```json
{
  "message_type": "transport_barrier",
  "payload": {
    "request_id": "transport_barrier:40102:1",
    "producer_ts": 40102
  }
}
```

The backend returns exactly one ACK:

```json
{
  "message_type": "ack",
  "payload": {
    "accepted": true,
    "source_type": "transport_barrier",
    "route": "transport_barrier",
    "request_id": "transport_barrier:40102:1",
    "producer_ts": 40102
  }
}
```

`request_id` must be non-empty and `producer_ts` must be an integer. Invalid payloads use the existing negative invalid-payload ACK path.

The barrier has no domain side effects. It does not publish authority events, mutate world truth, tick Siming, update character memory, or write Heavenly Graph state.

The backend does not claim global system idleness. The ACK means only: for this websocket connection, every envelope received before this barrier has completed normal handling and all retained main-socket messages produced by those envelopes were sent before the barrier ACK.

## 7. Godot connection and barrier behavior

`MainDemoController` resolves its connection URL after reading `PHASE0_AUTOTEST` and `PHASE0_FOCUS_AUTOTEST`:

- strict main autotest: append `stream_mode=runtime_only`;
- focus autotest and normal interactive runs: preserve the configured URL and therefore default to `full`;
- an existing query string is preserved by appending with `&` instead of `?`.

`BackendBridge` owns barrier request generation because the barrier is a transport concern, not a player intent. It maintains a connection-local sequence and generates:

```text
transport_barrier:<producer_ts>:<sequence>
```

`send_transport_barrier()` returns the same small descriptor shape used by player-input synchronization:

```text
request_id: String
producer_ts: int
```

The existing `acknowledged_request_ids` map and `_wait_for_request_ack` helper consume the barrier ACK. No route-only flag is introduced.

## 8. Revised Phase 0 drain flow

The strict main autotest uses the barrier at both bounded drain points:

1. disable controller periodic sampling and actor-local perception before probes;
2. before the near move, send a barrier and wait up to 10000 ms for its exact ACK;
3. require a 500 ms quiet interval after the barrier ACK;
4. run the near move and successful interaction using exact request and result correlation;
5. after all three successful world results arrive, enter full autotest quiescence;
6. send a second barrier and wait up to 10000 ms for its exact ACK;
7. require a 500 ms quiet interval after that ACK;
8. submit the far move and failed interaction;
9. wait for the exact failed-interaction ACK and `constraint_state_result` correlation;
10. complete only after the authoritative constraint result is observed.

The two barrier failure stages are:

```text
pre_interaction_barrier_ack_timeout
post_success_barrier_ack_timeout
```

The existing `transport_not_quiet` stage remains for a failed 500 ms post-barrier quiet check. Every failure continues to use:

```text
phase0_autotest_failure:<stage>:<request_id>
```

## 9. Backward compatibility

- Existing `/ws` clients receive `full` mode without changing their URL.
- Existing outbound message order within retained messages is unchanged.
- No existing player-input or ACK contract is removed.
- Normal Godot observatory panels continue receiving the current full stream.
- Strict Phase 0 intentionally omits observatory-only messages from its main socket but still executes the same runtime logic and can inspect the debug-stream evidence generated by that logic.
- Unknown future message types remain visible in `runtime_only` unless explicitly classified as observatory-only.

## 10. Testing strategy

Implementation follows red-green-refactor:

1. backend unit tests prove `full` retains and `runtime_only` removes exactly the seven observatory-only families;
2. websocket tests prove missing/unknown modes remain backward-compatible;
3. websocket tests prove a correlated barrier ACK is delivered after earlier request responses and has no runtime side effects;
4. Godot source-contract tests prove strict autotest URL selection and connection-local barrier ID generation;
5. controller source-contract tests prove both drain points use exact barrier ACKs followed by the 500 ms quiet window;
6. focused backend and Godot contract suites pass;
7. marker-aware Godot parsing reports no script load errors;
8. strict Phase 0 proves both successful and failed interaction paths;
9. Heavenly Graph focused tests and profile remain green;
10. full pytest and `harness.py --profile all` pass before branch completion.

## 11. Expected implementation scope

Expected tracked files:

- `backend/app/main.py`
- `backend/app/models/transport.py`
- `backend/app/transport_projection.py`
- `backend/tests/test_ws_protocol.py`
- `backend/tests/test_transport_projection.py`
- `scripts/autoload/BackendBridge.gd`
- `scripts/phase0/MainDemoController.gd`
- `scripts/verification/tests/test_phase0_correlated_ack_contract.py`
- this design and its implementation plan

No ESM, Siming runtime, Heavenly Graph implementation, character-memory, fact-emitter, or authority-event file is modified.

## 12. Completion criteria

The repair is complete only when:

- strict Phase 0 connects with `stream_mode=runtime_only`;
- normal clients remain in backward-compatible `full` mode;
- the seven observatory-only message families are omitted only from the runtime-only main-socket projection;
- observatory/debug generation still executes and remains available through the debug stream;
- both Phase 0 drain points use exact correlated barrier ACKs and the 500 ms quiet check;
- the failed interaction produces a real correlated `constraint_state_result`;
- focused tests, full pytest, `phase0`, the Heavenly Graph profile, and broad `all` Harness all pass;
- final review finds no open Critical or Important issue.
