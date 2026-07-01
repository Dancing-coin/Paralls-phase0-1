# World-Character-Siming-Authority Mainline Closure Matrix

Status: `audited`

Date: `2026-06-30`

## Scope

This document is a stricter closeout audit for the dedicated mainline plan tree under:

- `docs/superpowers/plans/world-character-siming-authority-mainline/`

It does not claim that the entire repository is globally perfect.
It claims that the dedicated mainline plan tree has been executed with direct evidence,
and maps each plan to:

1. planned closure scope
2. landed implementation files
3. direct verification evidence
4. remaining risk at the plan-local level

## Aggregate Verification Baseline

Fresh evidence used for this audit:

- `python scripts/verification/harness.py --profile docs`
- `python scripts/verification/harness.py --profile mainline-unified-runtime`
- `.harness/verification/mainline-unified-runtime-report.md`

Current aggregate proof status:

- `overall_docs_passed=True`
- `overall_mainline_unified_runtime_passed=True`

## Closure Matrix

### 1. World Runtime Foundation

- Plan file:
  - `docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-world-runtime-foundation-implementation-plan.md`
- Planned closure scope:
  - Canonical outer-world runtime models, fact-family routing seam, authority-facing projection helpers, and top-level docs entrypoint exposure.
- Landed implementation files:
  - `backend/app/world_runtime/models.py`
  - `backend/app/world_runtime/fact_registry.py`
  - `backend/app/world_runtime/projection.py`
  - `backend/app/services/fact_router.py`
  - `backend/app/main.py`
- Direct verification evidence:
  - `backend/tests/test_world_runtime_models.py`
  - `backend/tests/test_world_runtime_fact_registry.py`
  - `backend/tests/test_world_runtime_projection.py`
  - `backend/tests/test_documentation_entrypoints.py::test_docs_index_mentions_world_runtime_mainline`
  - `python scripts/verification/harness.py --profile docs`
- Remaining risk:
  - 未发现该 plan 范围内的直接剩余风险；仅保留仓库级宽口径风险。

### 2. Actor-Local Perception And Fact Production

- Plan file:
  - `docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-actor-local-perception-and-fact-production-implementation-plan.md`
- Planned closure scope:
  - Actor-owned target resolution, local perception sampling, standard fact-emitter routing, `CharacterReplica` runtime ownership, and dedicated verifier coverage.
- Landed implementation files:
  - `scripts/character/ActorPerceptionSampler.gd`
  - `scripts/character/ActorPerceptionTargetResolver.gd`
  - `scripts/character/CharacterReplica.gd`
  - `scenes/phase0/CharacterReplica.tscn`
  - `scripts/verification/verify_actor_local_perception.py`
- Direct verification evidence:
  - `backend/tests/test_relationship_overlay_static.py::test_actor_perception_sampler_declares_cone_range_and_los_hooks`
  - `backend/tests/test_visual_fact_pipeline.py::test_actor_local_sampling_emits_standard_visual_fact_shape`
  - `backend/tests/test_character_actor_reacquisition_runtime.py::test_character_replica_wires_actor_perception_sampler`
  - `.harness/verification/actor-local-perception-report.json`
  - unified result `actor_local_perception=proved`
- Remaining risk:
  - 未发现该 plan 范围内的直接剩余风险；仅保留仓库级宽口径风险。

### 3. Autonomous Social Contact And Exchange

- Plan file:
  - `docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-autonomous-social-contact-and-exchange-implementation-plan.md`
- Planned closure scope:
  - Role-owned utterance initiation, contact lifecycle semantics, arrival-driven continuity, and dedicated end-to-end contact verification.
- Landed implementation files:
  - `backend/app/services/dialogue_service.py`
  - `backend/app/services/character_service.py`
  - `backend/app/character_agent/execution/l4_executor.py`
  - `scripts/character/CharacterRuntimeState.gd`
  - `scripts/character/KnightRoleSkin.gd`
  - `scripts/verification/verify_autonomous_social_contact.py`
- Direct verification evidence:
  - `backend/tests/test_character_service.py::test_agent_initiated_utterance_preserves_speaking_actor`
  - `backend/tests/test_character_agent_runtime.py -k greeting -v`
  - `backend/tests/test_ws_protocol.py -k arrival_fact -v`
  - `.harness/verification/autonomous-social-contact-report.json`
  - unified result `autonomous_social_contact=proved`
- Remaining risk:
  - 未发现该 plan 范围内的直接剩余风险；仅保留仓库级宽口径风险。

### 4. Authority And Settlement Runtime Closure

- Plan file:
  - `docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-authority-and-settlement-runtime-closure-implementation-plan.md`
- Planned closure scope:
  - Structured settlement semantics for social-spatial requests and explicit runtime-facing settlement writeback.
- Landed implementation files:
  - `backend/app/main.py`
  - `backend/app/models/world_result.py`
  - `backend/app/services/frontend_authority_event_projection.py`
- Direct verification evidence:
  - `backend/tests/test_ws_protocol.py::test_approach_settlement_result_preserves_action_profile_and_target_actor`
  - `backend/tests/test_character_agent_action_request_routing.py::test_actor_target_settlements_carry_structured_social_spatial_metadata`
  - `backend/tests/test_visual_fact_pipeline.py::test_social_spatial_settlement_result_is_projected_back_into_runtime_outputs`
  - unified result `authority_settlement_writeback=proved`
- Remaining risk:
  - 未发现该 plan 范围内的直接剩余风险；仅保留仓库级宽口径风险。

### 5. Execution Semantics And Realization Runtime

- Plan file:
  - `docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-execution-semantics-and-realization-runtime-implementation-plan.md`
- Planned closure scope:
  - Stable execution-semantic vocabulary below `L4` and explicit transitional-local-host consumption of those semantics.
- Landed implementation files:
  - `backend/app/character_agent/execution/l4_executor.py`
  - `scripts/character/CharacterPresentationInput.gd`
  - `scripts/character/CharacterRuntimeState.gd`
  - `scripts/character/CharacterReplica.gd`
  - `docs/character/character-agent-runtime-architecture.md`
- Direct verification evidence:
  - `backend/tests/test_character_agent_runtime.py::test_execution_plan_carries_contact_and_realization_semantic_keys`
  - `backend/tests/test_character_actor_boundary_audit.py::test_character_replica_still_behaves_as_local_realization_host_not_semantics_owner`
- Remaining risk:
  - This plan is closed at the semantics-freeze plus transitional-host boundary.
  - Direct remaining plan-local limits:
    - no fully replaced local realization host yet
    - no final skeletal or bone-space production backend here

### 6. Asset Runtime And Kimodo Adapter

- Plan file:
  - `docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-asset-runtime-and-kimodo-adapter-implementation-plan.md`
- Planned closure scope:
  - Asset registry/preload contracts, Kimodo request/realization seam, and generated-motion plus local-fallback composition rules.
- Landed implementation files:
  - `scripts/character/CharacterEmbodimentAssetRegistry.gd`
  - `backend/app/character_agent/execution/kimodo_adapter_contract.py`
  - `scripts/verification/verify_mainline_unified_runtime.py`
  - `docs/character/character-asset-integration.md`
- Direct verification evidence:
  - `backend/tests/test_character_asset_registry_static.py`
  - `backend/tests/test_kimodo_adapter_contract.py`
  - `scripts/verification/tests/test_mainline_unified_runtime_verify.py`
  - unified result `asset_runtime_kimodo_contracts=proved`
- Remaining risk:
  - This plan is intentionally closed at the seam and contract layer.
  - Direct remaining plan-local limits:
    - no live Kimodo runtime integration
    - no production asset cache or eviction runtime
    - no heavy local preload daemon or streaming pipeline

### 7. World Runtime Scheduling And Continuity

- Plan file:
  - `docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-world-runtime-scheduling-and-continuity-implementation-plan.md`
- Planned closure scope:
  - Cadence/wake-up/cooldown/recovery policies, multi-actor selection semantics, unified scheduling state, round observability, replay surfaces, websocket delivery, and frontend signal/state chain proof.
- Landed implementation files:
  - `backend/app/world_runtime/scheduling.py`
  - `backend/app/world_runtime/continuity.py`
  - `backend/app/character_agent/runtime/runtime_loop.py`
  - `backend/app/main.py`
  - `backend/app/models/observatory.py`
  - `backend/app/services/character_agent_debug_projection.py`
  - `scripts/autoload/BackendBridge.gd`
  - `scripts/autoload/LocalPresentationBus.gd`
  - `scripts/ui/CharacterDirectorState.gd`
  - `scripts/verification/verify_mainline_unified_runtime.py`
- Direct verification evidence:
  - `backend/tests/test_world_runtime_scheduling.py`
  - `backend/tests/test_world_runtime_continuity.py`
  - `backend/tests/test_character_agent_runtime_memory_integration.py`
  - `backend/tests/test_character_agent_action_request_routing.py::test_character_agent_execution_route_emits_scheduling_round_trace`
  - `backend/tests/test_debug_panel.py`
  - `backend/tests/test_observatory_message_delivery_static.py`
  - `backend/tests/test_character_director_state_static.py`
  - `backend/tests/test_ws_protocol.py::test_websocket_character_agent_execution_emits_scheduling_round_trace`
  - `backend/tests/test_ws_protocol.py::test_websocket_interact_intent_emits_scheduling_round_trace_after_character_agent_execution`
  - `scripts/verification/tests/test_mainline_unified_runtime_verify.py`
  - unified results:
    - `mainline_world_runtime_suite=proved`
    - `runtime_cadence_continuity_observatory=proved`
    - `continuity_recovery_runtime=proved`
- Remaining risk:
  - This plan is closed within the current replay-friendly first-pass scheduler scope.
  - Direct remaining plan-local limits:
    - no heavy global scheduler implementation
    - no production-scale population benchmark
    - no cross-process replay service beyond current observability and replay surfaces

### 8. Mainline Docs Truth Rewrite

- Plan file:
  - `docs/superpowers/plans/world-character-siming-authority-mainline/2026-06-29-mainline-docs-truth-rewrite-implementation-plan.md`
- Planned closure scope:
  - Promote the dedicated mainline tree into repository entry docs and demote older `Phase 0` mission framing to compatibility/historical status.
- Landed implementation files:
  - `docs/INDEX.md`
  - `docs/ai-engineering-workflow.md`
  - `docs/character/character-agent-runtime-architecture.md`
  - `docs/character/character-actor-migration-status.md`
  - `AGENTS.md`
  - `PHASE0_README.md`
  - `docs/demo-script.md`
  - `docs/harness.md`
- Direct verification evidence:
  - `backend/tests/test_documentation_entrypoints.py::test_mainline_docs_entrypoints_promote_world_character_siming_authority_tree`
  - `backend/tests/test_documentation_entrypoints.py::test_phase0_mission_docs_are_marked_as_compatibility_surfaces`
  - `python scripts/verification/harness.py --profile docs`
- Remaining risk:
  - 未发现该 plan 范围内的直接剩余风险；仅保留仓库级宽口径风险。

## Audit Conclusion

- The dedicated plan tree is executed with direct implementation and verification evidence for all eight plans.
- I do not see remaining open tasks inside this dedicated plan tree.
- The conservative residual statement is:
  - dedicated mainline plan-tree scope: closed
  - wider repository scope: not re-audited here beyond the focused proof surfaces above
