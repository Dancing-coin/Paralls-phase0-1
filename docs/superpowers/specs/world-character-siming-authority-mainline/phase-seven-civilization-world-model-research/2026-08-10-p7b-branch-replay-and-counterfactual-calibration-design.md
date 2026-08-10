# P7B Branch Replay And Counterfactual Calibration

Status: `design-only; implementation not authorized`

## Contract

A branch is an immutable replay descriptor: parent checkpoint/tail range,
revision/package set, allowed perturbation manifest, seed, policy mode,
classification and expiry. It produces a labeled `CounterfactualReport` with
inputs, assumptions, calibration metric, uncertainty and result digest. It is
not a fork of production truth and cannot merge facts back.

Calibration compares predicted/branch outcomes with later committed observations
through declared metrics and access-controlled data. It must distinguish
historical replay, hypothetical execution and model inference.

## Gate

Test branch isolation, prohibited merge, deterministic seed, stale dependency,
private-data denial, report provenance and retention deletion. No mutable
parallel event store or invisible simulation facts are permitted.
