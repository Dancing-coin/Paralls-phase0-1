# Embodied Interaction Boundary And Acceptance Matrix

Status: `awaiting-user-review`

Date: `2026-07-29`

## Invariants

1. Godot is a realization and observation host, never world authority.
2. Backend settlement alone commits world/relationship/body/object state.
3. LLM and VLA output semantics/advisories, never frame-level bones, physics,
   impulses, or final state declarations.
4. Known scene truth comes from the reviewed registry and local engine
   bindings; VLA is optional and lower authority.
5. One controller-scoped, attested attempt produces at most one settlement and
   one terminal local outcome.
6. Presentation success is not authority success.
7. Session privacy and actor-private mind data remain filtered at the backend.
8. TTS/streaming dialogue are outside this implementation plan.

## Verification Matrix

| Area | Success evidence | Required failure evidence |
| --- | --- | --- |
| Registry | `chair_01` resolves catalog-backed anchors/collider/policy at pinned revision | unknown, stale, missing local binding/occupancy, VLA conflict or invented ID |
| Transport / attestation | authenticated controller consumes one grant on its current epoch | spoofed attempt ID, nonce reuse, stale epoch, revoked grant, unknown message |
| Controller | actor reaches stance, aligns, records contact and recovers on one selected route | no path, target moved, slot occupied, timeout, cancellation, miss, legacy/controller double start |
| Local physics | contact/final state observation is structured and bounded | animation only, wrong collider, fixed chair, raw stream rejected |
| Authority | validated observation commits once through its recorded writer | duplicate, stale, fabricated, denied, revision conflict, writer cutover misuse have zero mutation |
| Session | participants reserve slots and settle/cancel coherently | refusal, target loss, interruption, private data leakage |
| Mirror/Observatory | pending/settling/committed/rejected remain distinct and field-filtered | false local success, revision gap, per-field privacy payload rejection |
| Replay | causal ledger is complete and server-ordered | orphan observation, duplicate settlement, mismatched IDs/revisions, sequence gap, epoch/late-message violation |
| VLA | advisory result may enrich a reviewed binding path | disabled/stale/conflicting advisory cannot block/overwrite known truth |

## Evidence Levels

- Unit/contract tests prove schema, identity, policy, privacy, and authority
  failure behavior.
- Backend integration tests prove request-to-settlement and event projection.
- Godot headless/runtime probes prove a real scene/controller/collider path.
- Screenshot/log/trace artifacts prove visible result and causal linkage.
- The aggregate profile proves ordering only after predecessor profiles pass.

## Release Criteria

The first closure may be called complete only after all planned focused profiles
and `embodied-interaction-foundation-all` exist and pass, all predecessor
profiles remain green, `python scripts/verification/harness.py --profile all`
passes, and fresh artifacts are retained under `.harness/verification/`.
