# P7B Branch Replay And Counterfactual Calibration Implementation Plan

Status: `design-only; implementation not authorized`

1. Lock P7A and write branch-descriptor, isolation, seed, expiry and access
   denial tests before a sandbox is connected.
2. Reuse replay/checkpoint readers in read-only mode; branch output is an
   audited report artifact, never an event-stream append target.
3. Add calibration provenance and factual-versus-hypothetical labeling tests.
4. Verify no merge API, no production side effect and no private projection leak.
