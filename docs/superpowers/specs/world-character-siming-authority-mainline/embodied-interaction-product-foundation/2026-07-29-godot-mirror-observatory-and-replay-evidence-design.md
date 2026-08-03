# Godot Mirror, Observatory, And Replay Evidence Design

Status: `implemented-foundation; broader-mirror-and-replay-coverage-planned`

Date: `2026-07-29`

Revision: `2026-07-31` (review remediation)

## Purpose

Define the evidence/read-model boundary for embodied actions. It extends the
existing BackendBridge, LocalPresentationBus, Observatory, AuthorityEvent, and
skeletal debug replay surfaces with a correlated, privacy-filtered interaction
attempt ledger. It does not replace the planned generic gameplay mirror.

The correlated attempt ledger, filtered observatory rows, replay validation,
and bounded Godot presentation paths are now implemented for the verified
embodied slices. This does not replace the broader gameplay mirror or prove
scene-wide live delivery beyond those reviewed slices.

## Evidence Ledger

```text
EmbodiedInteractionEvidence
  interaction_attempt_id, session_id?
  request_ref, registry_binding_ref, controller_phase_events[]
  terminal_local_observation_ref, settlement_ref, authority_event_refs[]
  final_presentation_ref, causation_id, correlation_id
  scene_revision, policy_revision, settlement_writer_kind
  visibility_scope, retention_policy

EmbodiedEvidenceEvent
  attempt_id, event_kind, emitter_kind, emitter_id, emitter_epoch
  source_sequence, server_ledger_sequence, payload_digest
  occurred_at, recorded_at, projection_policy_ref
```

The backend is the ledger's durable source. Godot may retain a bounded local
debug cache and write approved debug artifacts, but cannot reconstruct or
alter authority truth from it. Full bone snapshots remain separate
`debug_replay_only` artifacts and are referenced, never placed in the normal
interaction transport.

`server_ledger_sequence` is a strictly continuous, backend-assigned sequence
per attempt and is the sole replay order. `source_sequence` is continuous per
emitter epoch. Phase events are accepted only at the next expected source
sequence; an exact duplicate digest receives the earlier acknowledgement and a
different duplicate or a gap is rejected/resynced. A reconnect creates a new
emitter epoch, revokes old grants, and requires authority-issued resumption
before any new phase event. Once authority records cancellation, terminal
outcome, rejection, or commit, later phase/outcome traffic is retained only as
rejected audit evidence (`late_after_terminal`) and can never change settlement.
Concurrent cancel/outcome races are ordered by the authority-assigned ledger
sequence, not client timestamps.

## Godot Read Models

The interaction layer provides a typed, read-only per-attempt mirror for
animation/UI/debug consumers:

```text
attempt_id, phase, local_status, settlement_status, retry_directive,
presentation_directive, visible_evidence_refs, sync_status
```

It composes with the future `CharacterGameplayStateMirrorComponent`; it does
not duplicate resource/inventory/relationship state. Pending local realization
is visibly distinct from committed authority result. A local terminal outcome
must never render as a confirmed world change before a settlement projection.

## Observatory

The existing Observatory gains filtered rows for:

- semantic request and selected affordance summary;
- current controller phase and a safe terminal failure reason;
- observed contact/object/environment summary;
- authority commit/reject, retry directive, and resulting public world effect;
- post-settlement character/Siming reactions as downstream entries, never as
  causes of the physical result.

Private participant terms, raw private memory, unfiltered VLA prompt/context,
and full skeletal artifacts remain excluded from normal Observatory views.

## Replay Validation

The verifier reads `server_ledger_sequence` in causal order and requires:

```text
authorized request
 -> registry binding revision
 -> legal controller phases
 -> one terminal local observation
 -> exactly one settlement
 -> zero or more routed authority/presentation projections
```

It rejects orphan observations, duplicate settlement, mismatched revisions,
gaps/reordered source sequence, stale emitter epoch, late-after-terminal
mutation, presentation-before-commit success claims, and privacy-ineligible
payloads. Projection validation uses the field-level allowlist in the session
and settlement design, not a coarse record visibility label.
Replay validates evidence consistency, not deterministic reproduction of every
floating-point physics frame.

## Acceptance Criteria

1. Every chair attempt has a single correlated ledger that links request,
   phases, observation, settlement, authority event, and final presentation.
2. Observatory distinguishes `local_observed`, `settling`, `committed`, and
   `rejected`; it cannot mislabel animation completion as committed.
3. The replay verifier rejects a missing terminal observation, duplicate
   settlement, bad causal ID, stale binding revision, and unfiltered private
   field fixture.
4. Debug skeletal replay is opt-in and references the existing
   `debug_replay_only` policy; no full-bone payload enters authority or normal
   observatory transport.
5. A Godot runtime probe produces visible state plus a trace artifact and
   screenshot/log evidence for success and at least one failure path.
6. Replay fixtures prove duplicate-with-same-digest acknowledgement,
   duplicate-with-different-digest rejection, source-sequence gap resync,
   reconnect epoch invalidation, and cancellation/outcome race ordering.

## Dependencies

- Existing Observatory state/models, AuthorityEvent frontend projection,
  BackendBridge/LocalPresentationBus, and skeletal debug replay pipeline.
- Session/settlement design in this tree.
- Future generic gameplay mirror only for shared synchronization primitives.
