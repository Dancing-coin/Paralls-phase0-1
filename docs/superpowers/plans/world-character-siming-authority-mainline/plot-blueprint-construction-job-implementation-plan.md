# Plot/Blueprint/Job Implementation Plan

Add typed content validation and deterministic grid projection around existing
models. Write RED tests for malformed content, overlap, orientation, stale
plot/permit proof, duplicate and replay equivalence; implement the smallest
owner methods and Harness profile; retain legacy readers unchanged. Gate:
content admission and headless job replay green. Rollback: disable new binding
without altering old events.

ConstructionJob replay now validates occupied-cell shape and canonical order;
malformed coordinates fail closed with a stable domain error.

Job-start replay now validates project privacy and canonical plot stream
identity before accepting occupancy state.

Completion and failure replay now reject wrong plot streams or private events
with stable source-conflict errors.
Existing plot/blueprint identity conflict errors remain unchanged for payload
identity tampering.
