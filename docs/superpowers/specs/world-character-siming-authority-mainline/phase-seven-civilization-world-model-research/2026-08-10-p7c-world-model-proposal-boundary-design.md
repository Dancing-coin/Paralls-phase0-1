# P7C World-Model Proposal Boundary

Status: `design-only; implementation not authorized`

## Boundary

A world model receives only approved, scope-filtered snapshots and emits
`PredictionProposal`, content candidate or action recommendation with model
identity, input digest, confidence/calibration version, uncertainty, policy
class, expiry and explanation. It cannot access raw private memory, keys or
canonical writer services, and it cannot declare its output factual.

Any use of an output enters the same human/rules/authority validation route as
other proposals. Generated content is staged in a governed package revision;
action recommendations are revalidated against current state and may be denied.

## Gate

Prove deterministic capture of model inputs, redaction, prompt/output audit,
expired/revoked proposal denial, calibration display and zero world write on
model output. A world model is never sole truth or low-level embodiment control.
