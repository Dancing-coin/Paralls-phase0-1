# Siming Event Bus Final Merge Retrospective

Date: 2026-06-10
Status: completed and verified

## Decision

The final merge used the authority event bus as the Siming mainline. The old direct `SimingService -> siming_output` runtime path was removed from the active backend flow. `siming_output` remains only as a frontend compatibility projection generated from authority events.

## Useful Branch Assets Preserved

- Authority event models and in-memory authority event bus.
- Siming event models, runtime, producer, consumer, pipeline, and audit writer.
- Phase 0 authority event adapter.
- Frontend authority event projector.
- Provenance tests proving projected frontend output is derived from authority events.
- Project harness and OpenSpec assets, merged later as a separate governance layer.

## Rejected Paths

- Directly merging the long-lived `pjm_siming` branch.
- Wholesale merging `codex/siming-bus-integration`.
- Keeping permanent dual paths for Siming output generation.
- Keeping harness, OpenSpec, and workflow assets mixed into the runtime merge commit.

## Final Runtime Chain

```text
Phase 0 input or fact
  -> authority event adapter
  -> authority event bus
  -> Siming event pipeline
  -> Siming runtime
  -> Siming event producer
  -> authority event bus
  -> frontend authority event projector
  -> Godot-compatible frontend envelope
```

## Verification Evidence

- Backend test suite passed after the runtime merge.
- Phase 0 runtime verification passed.
- Phase1-shaped slice verification passed after the harness layer was added.
- The project harness now treats authority bus provenance as a first-class boundary check.

## Follow-Up Rule

Future L2 work should bind to the authority event bus and frontend projection contracts. Do not reintroduce direct Siming runtime calls from websocket handlers or fact handlers.
