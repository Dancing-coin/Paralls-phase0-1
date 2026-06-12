# Repository Plan Status Register

## Purpose

This file is the repository-wide execution register for plan truth.

It exists to answer three questions without rereading every historical plan:

- which plans are currently active
- which plans are already completed and verified
- which plans were replaced by later plans and should no longer be treated as open work

## Status Vocabulary

- `completed_verified`: implementation target is satisfied on the current worktree and supported by current tests and/or runtime verification
- `superseded`: an older plan was replaced by a newer controlling plan; it is not open work anymore
- `metadata_only_open`: code may already be done, but the source plan itself still lacks explicit close-out metadata and needs truth-sync

## Current Register

| Plan | Status | Notes |
| --- | --- | --- |
| `2026-06-08-system-l1-full-phase1-implementation-plan.md` | `completed_verified` | Parent `System L1` plan; child-plan matrix and full verification gate are green. |
| `2026-06-08-system-l1-client-interaction-implementation-plan.md` | `completed_verified` | `move_intent` / `focus_target_change` / `interact` proof chain is verified. |
| `2026-06-08-system-l1-visual-fact-system-implementation-plan.md` | `completed_verified` | emitter family plus `evidence_projection` runtime proof is verified. |
| `2026-06-08-system-l1-esm-full-domain-implementation-plan.md` | `completed_verified` | settlement matrix, capability/workbench surface, request-lineage, and thermal-field proof are verified. |
| `2026-06-08-system-l1-spatial-audio-auditory-facts-implementation-plan.md` | `completed_verified` | explicit auditory taxonomy and `L1-only` candidate policy already have verified status metadata. |
| `2026-06-08-system-l1-remaining-emitter-implementation-plan.md` | `completed_verified` | remaining emitter shell plan already marked executed; runtime wiring also landed. |
| `2026-06-08-system-l1-runtime-wired-remaining-emitters-implementation-plan.md` | `completed_verified` | runtime proof for tactile / thermal / olfactory / physiology / role-state emitters is verified. |
| `2026-06-08-system-l1-to-l2-interface-implementation-plan.md` | `completed_verified` | candidate / perceived / self-body seams are verified. |
| `2026-06-08-system-l1-debug-replay-verification-implementation-plan.md` | `completed_verified` | verification triad and audit surfaces are verified. |
| `2026-06-08-system-l1-auditory-domain-completion-implementation-plan.md` | `completed_verified` | follow-on auditory completion plan already marked executed and verified. |
| `2026-06-08-system-l1-verification-truth-sync-implementation-plan.md` | `completed_verified` | checklist + proof fixtures + verification triad are now aligned. |
| `2026-06-08-system-l1-esm-implementation-plan.md` | `superseded` | replaced by the later `system-l1-esm-full-domain` plan. |
| `2026-06-08-l1-main-project-alignment-migration-implementation-plan.md` | `completed_verified` | candidate percept, per-character filter, and character-perceived event chain are explicitly verified. |
| `2026-06-08-stage-b-per-character-filtering-implementation-plan.md` | `completed_verified` | actor-context-aware filtering and character-facing perceived-event storage are explicitly verified. |
| `2026-06-07-l1-ttl-nearby-actor-expiry-implementation-plan.md` | `completed_verified` | TTL expiry and refresh semantics are explicitly verified. |
| `2026-06-07-l1-state-projection-hardening-implementation-plan.md` | `completed_verified` | shared effect semantics, reseed behavior, and runtime-edge recovery are explicitly verified. |
| `2026-06-05-player-root-motion-locomotion-implementation-plan.md` | `completed_verified` | locomotion/root-motion audit proof, jump probes, and forward-direction probes are explicitly verified. |
| `2026-06-02-phase05-runtime-alignment-implementation-plan.md` | `completed_verified` | backend runtime state, relation compilation, Siming, health identity, and websocket runtime messages are explicitly verified. |
| `2026-06-02-phase05-character-scene-upgrade-implementation-plan.md` | `completed_verified` | `CharacterC`, driver-spec/docs, homebuilder notes, and scene-zone docs are explicitly verified; the mixabridge note remains as an offline asset-tool reference rather than a runtime dependency. |
| `2026-06-02-phase0-open-scene-camera-implementation-plan.md` | `completed_verified` | open-field scene, camera tuning, and sample-scene docs are explicitly verified. |
| `2026-06-06-l1-raw-fact-emitter-implementation.md` | `completed_verified` | document already self-registers as implemented for the minimal slice and is covered by current raw-fact tests. |

## Current Meaning

At the time of this register:

- no active `System L1` execution plan remains unfinished
- no repository plan in this register still remains `metadata_only_open`
- all registered plans are now either `completed_verified` or `superseded`
