# Character Actor Migration Status

This document tracks which parts of the optimized `CharacterActor` architecture are already aligned and which remain transitional.

## Active Architecture Truth

Current active optimization truth:

- `docs/superpowers/specs/2026-06-15-character-actor-architecture-optimization-design.md`

Current active final-convergence planning truth:

- `docs/character/character-actor-final-convergence-target.md`
- `docs/character/character-actor-final-convergence-gap-report.md`
- `docs/superpowers/plans/2026-06-15-character-actor-final-convergence-implementation-plan.md`

Current downstream dependent plan:

- `docs/superpowers/plans/2026-06-15-full-character-agent-runtime-with-llm-implementation-plan.md`

Historical/narrower references still preserved:

- `2026-06-12-character-actor-unification-design.md`
- `2026-06-12-character-actor-runtime-boundary-design.md`
- `2026-06-12-character-actor-control-and-locomotion-design.md`

## Aligned Now

- shared player actor root via `CharacterBase.tscn`
- `CharacterMotor` owns normal world displacement
- player path uses the same visible role stack as the shared actor presentation path
- `KnightCombatModifier` exists as post-animation correction
- shared control terminology is frozen in code:
  - `human_controlled`
  - `agent_controlled`
  - `program_controlled`
- shared locomotion execution terminology is frozen in code:
  - `physics`
  - `root_motion`
  - `hybrid`
- `CharacterPresentationInput` exists as an explicit shared presentation-boundary contract
- `PlayerShell` now owns raw input capture and forwards shell events to the adapter layer
- `Phase0PlayerBridge` no longer owns shell command dispatch; `Phase0PlayerCommandRelay` owns Phase 0 action-map command routing
- current player wrapper scene `CharacterBase.tscn` now also mounts `Phase0PlayerCommandRelay`, so the live `PlayerCharacter` path no longer lags behind the slimmer shell-command ingress surface already present in `PlayerShell.tscn`
- the live player path now also mounts `CharacterMotor` on the `CharacterReplica` lineage instead of keeping that node on the outer `CharacterBase` wrapper, so the motor-owned displacement host is less tied to the player-only shell layer
- `Phase0PlayerBridge` no longer runs parallel raw-input polling loops; it exposes callable adapter methods and actor sync state
- `Phase0PlayerBridge` no longer keeps its program/autotest forcing state inline; that state now lives in a dedicated `Phase0ProgramControlState` helper while the bridge keeps the existing callable surface
- `Phase0PlayerBridge` no longer keeps its locomotion mode state inline; gait/crouch/jump mode logic now lives in a dedicated `Phase0LocomotionControlState` helper while the bridge keeps the existing callable surface
- `Phase0PlayerBridge` no longer performs direct CharacterReplica shell-sync calls inline; those sync calls now live in a dedicated `Phase0CharacterShellSync` helper while the bridge keeps the same public methods
- `Phase0PlayerBridge` no longer keeps its view/anchor/camera-forward resolution logic inline; that logic now lives in a dedicated `Phase0ViewAnchorResolver` helper while the bridge keeps the same public methods
- `CharacterReplica` now pushes focus/attention target and highlight decisions through `CharacterRuntimeState` helpers rather than keeping the little bits of attention-branch logic inline
- `CharacterReplica` now stages player shell pose state through `CharacterRuntimeState` helpers instead of inlining the accept/set/clear sequence directly in the shell
- `CharacterReplica` now reads player-shell velocity/grounded locomotion state back through `CharacterRuntimeState` getters instead of reaching into the raw motion payload for those values
- `CharacterReplica` no longer keeps `player_shell_velocity` as a shell-local ownership field; that velocity now lives in `CharacterRuntimeState` and is only read back where needed
- `CharacterReplica` now reads player-shell stance/gait/jump state back through `CharacterRuntimeState` getters instead of treating that locomotion-mode state as purely shell-local bookkeeping
- `CharacterReplica` now reads `player_gait` back through `CharacterRuntimeState` in its remaining presentation/locomotion assembly sites instead of keeping that gait value as a shell-local fallback source
- `CharacterReplica` now uses a `CharacterRuntimeState` locomotion interpretation helper for the player-shell locomotion decision scaffold, while the outer shell still applies the resulting role-state/profile side effects
- `CharacterReplica` now uses a `CharacterRuntimeState` helper for the final player presentation payload packing (`move_x` / `move_y` / `speed` / `gait`) instead of finishing that contract assembly entirely inline
- `CharacterReplica` now also uses a `CharacterRuntimeState` helper to resolve the player presentation motion fields (`move_local` / `velocity_world`) before final payload packing, further shrinking shell-local presentation assembly
- `CharacterReplica` now reads stance/jump for emitted locomotion status through `CharacterRuntimeState`, so that status reporting no longer treats those values as shell-local source-of-truth
- `CharacterReplica` now also stages agent role-state request candidates through `CharacterRuntimeState`, so the shell no longer separately pulls expression hint and requested action strings before mapping them into local role-state side effects
- `CharacterReplica` now stages agent execution side-effect planning through a single `CharacterRuntimeState` side-effect plan instead of keeping focus lookup, physiology hint, and role-state request assembly spread across the shell branch
- `CharacterRuntimeState` no longer keeps separate agent-side focus/expression/physiology cache fields or getters for this execution path; the active truth now comes from the normalized `CharacterPresentationInput`, and the side-effect plan is built directly from that contract
- `CharacterReplica` now passes its configured `dialogue_role_state` / `interaction_role_state` / `focus_role_state` / `attention_role_state` into the runtime-side execution plan so agent role-state effects respect actor-local configuration instead of falling back to hard-coded default labels
- `CharacterPresentationInput` now owns more of the active actor-side contract surface directly: player runtime payload assembly, agent execution-plan normalization, runtime-state agent-side side-effect reads, and skin-side motion/focus/action/equipment/speech reads have all moved through shared helper methods instead of leaving nested contract reads spread across `CharacterRuntimeState`, `CharacterReplica`, and `KnightRoleSkin`
- the player-shell presentation path is now also thinner at runtime-state scope: `CharacterRuntimeState` no longer keeps a dedicated player-presentation setter layer or cached getter round-trip, and `CharacterReplica.apply_embodied_pose_sync(...)` now pushes the presentation contract returned directly from `stage_player_shell_pose(...)` instead of staging then re-reading that payload through a separate runtime-state cache surface
- player-interact self-body ingress now single-ingests `self_body_perceived_event` before execution emission; the duplicate compat ingest is removed
- `MainDemoController` no longer keeps a direct `CharacterReplica` runtime reference for player-facing forward-vector reads
- visible runtime feedback moved out of `CharacterReplica` into `CharacterRuntimeFeedback`
- `CharacterModelGateway` now carries prompt policy and structured-output validation, `L2/L3` now consume model-backed runtime outputs with local fallback preserved, and dialogue generation is now also routed through the same gateway main path rather than a separate dialogue stub branch
- `CharacterPresentationInput` is preserved at the actor-to-skin boundary while the near-term flat fallback remains available
- `CharacterActorSchema` no longer defines the old flat presentation contract keys, and `CharacterRuntimeState` no longer writes or finalizes that flat motion bridge back into the formal presentation contract
- `CharacterReplica` no longer re-normalizes player presentation input after `CharacterRuntimeState.build_player_presentation_input(...)`; the formal presentation contract now flows more directly from runtime-state host to skin
- `KnightRoleSkin` now builds modifier input and hands it to `KnightCombatModifier`
- asset generalization entry contracts are frozen in code:
  - `CharacterAssetBindingProfile`
  - `CharacterEquipmentBindingProfile`
  - `CharacterActionAssetDescriptor`
- asset lookup remains gated behind explicit readiness criteria
- future root-motion / hybrid work has a motor-owned displacement guard

## Still Transitional

- `Phase0PlayerBridge.gd` still carries demo sync and some autotest-oriented utility methods in addition to pure adaptation, but the program-forcing state, locomotion mode state, CharacterReplica shell-sync calls, and view/anchor resolution logic have now been split into dedicated helpers
- `CharacterReplica.gd` still remains the actor runtime shell, but some of the focus/attention branch logic and player-shell pose staging that used to live inline are now routed through `CharacterRuntimeState`
- `CharacterReplica.gd` still owns the actor runtime shell, but now does so around an extracted `CharacterRuntimeState` host instead of owning all shared runtime state directly
- the new asset contract files are schema-only and are not yet consumed by runtime asset resolution
- asset lookup remains contract-only in this near-term cleanup; do not add `CharacterAssetLibrary.gd` until multiple role skins require real lookup and fallback behavior
- `CharacterPresentationInput` is frozen as a contract, but the current payload is still assembled as a near-term dictionary bridge rather than a typed resource pipeline
- `CharacterLocomotionExecutionMode` is frozen as vocabulary, but near-term runtime remains `physics`-first with selective root-motion consumption routed through actor/motor coordination
- CharacterReplica direct root-motion displacement remains transitional; future root-motion and hybrid work must be motor-owned, and presentation must not become the owner of world displacement
- some debug instrumentation still exists in runtime scripts, but the default bus logging path is now gated behind explicit debug/harness toggles instead of always-on runtime noise
- some migration-only residue has already been trimmed from the shared actor path during Stage 2 closeout: `CharacterReplica` no longer keeps the old `runtime_state_applied:*` diagnostic log or an unused `CharacterPresentationInput` surface preload, `KnightRoleSkin` no longer keeps now-unused `CharacterActorSchema` surface references once helper ownership moved downstream, and `MainDemoController` no longer keeps the unused `last_debug_message` cache or `autotest_capture_delay` export
- `L2` and `L3` now use the model gateway as their runtime consumption path, and `L4` now has a verified first shared-actor execution seam through `character_agent_execution`; broader actor-side convergence is still incomplete
- runtime message emission is execution-only by default; `character_agent_output` remains a static compatibility signal chain rather than a runtime emission path

## Intended Near-Term Cleanup

1. narrow raw input to `PlayerShell`
2. narrow adaptation to bridge/controller adapter layer
3. narrow actor-runtime ownership inside `CharacterReplica`
4. keep final pose/equipment correction in `SkeletonModifier3D`
5. freeze model/skeleton/equipment/action contracts

Status:
- 1 is implemented
- 2 is implemented for shell command dispatch and partially implemented for remaining demo sync helpers
- 3 is implemented for visible runtime feedback and partially implemented for future runtime-state extraction
- 4 is implemented in the current near-term architecture
- 5 is implemented as contract freeze, not full runtime adoption

Near-term cleanup closeout:

- `Phase0PlayerBridge` no longer owns shell command dispatch
- visible runtime feedback moved out of `CharacterReplica`
- `CharacterPresentationInput` is preserved at the actor-to-skin boundary
- the near-term cleanup itself only documented `ControllerPort` as a mid-term target; Stage 2 has since landed the first real `CharacterControllerPort` and adapter-family seam
- asset lookup remains gated behind explicit readiness criteria
- future root-motion / hybrid work remains motor-owned
- remaining work before Phase1-facing mid-term can begin

## Intended Mid-Term Direction

- explicit `ControllerPort`
- explicit `CharacterPresentationInput`
- explicit asset binding profiles
- binder-ready modifier stack
- motor-owned root-motion or hybrid execution mode

`ControllerPort` was intentionally not implemented in the near-term cleanup. That historical constraint remains true for Stage 1, but Stage 2 has now landed the first `CharacterControllerPort` implementation and human / agent / program adapters.

## Final-Convergence Planning Status

Near-term cleanup is not the final actor-substrate convergence stage.

Current planning posture is now:

1. near-term cleanup: completed and recorded
2. final actor-convergence target: now explicitly frozen in docs
3. final actor-convergence planning: now explicitly defined
4. full character-agent convergence: depends on actor final convergence

This means:

- actor-side stage 1 and actor-side stage 2 are distinct
- the full character-agent runtime must not claim final-state `L4` convergence until the actor-side final convergence plan is sufficiently landed

## Stage 2 Audit Status

Stage 2 audit outcome as of `2026-06-15`:

- final-convergence planning artifacts exist
- near-term cleanup artifacts remain valid and should not be re-done
- final-convergence implementation has landed the first shared runtime seams, but the full final convergence is still incomplete

Actor Stage 2 first-batch items now landed in code:

- `CharacterControllerPort` and adapter family
- `CharacterRuntimeState` extraction from the current `CharacterReplica` transition point
- shared ingress unification for human / agent / program control at the first actor ingress seam
- final host choice frozen as `CharacterReplica` lineage, with `CharacterBase` narrowed to wrapper/player-shell status

Current Stage 2 landing status after the first convergence batch:

- `CharacterControllerPort` and the first adapter family are now present in code
- `CharacterRuntimeState` now exists as an extracted runtime-state host for shared actor state
- human / agent / program paths now pass through the adapter family at the actor ingress seam
- final host choice is frozen as: `CharacterReplica` lineage; `CharacterBase` is wrapper and player-shell surface, not long-term actor architecture truth
- `character_agent_execution` has live-smoke verification through `BackendBridge -> LocalPresentationBus -> CharacterReplica`; the current runtime payload now carries agent-side shared-ingress fields (`controller_source`, `control_mode`, `action`) plus a stronger `CharacterPresentationInput`-shaped `presentation_plan` (`focus_state`, `action_state`, `speech_state`) without claiming full Stage B completion
- the shared ingress normalization now preserves a broader explicit `CharacterIntentFrame`-style field set at the `CharacterControllerPort` seam (`look_local`, `stance`, `ttl_ms`, `causation_id`, `correlation_id`) instead of collapsing back to the narrower transitional `move_local/gait/action` subset; player and program ingress now stage those fields explicitly while keeping the bridge surface thin
- actor-side consumers are now also moving off ad-hoc frame-shape assumptions: `CharacterMotor`, `CharacterRuntimeState`, and `Phase0PlayerBridge` now normalize incoming intent-frame dictionaries back through `CharacterControllerPort.normalize_intent_frame(...)` before consuming them, so the shared ingress contract is no longer only explicit at build time
- `CharacterMotor` now also reads normalized `move_local` / `gait` / `action` through thin `CharacterControllerPort` field-read helpers instead of continuing to unpack those actor-side intent fields inline after normalization
- `Phase0PlayerBridge` now also reads normalized `move_local` / `gait` / `action` / `desired_facing_yaw` through thin `CharacterControllerPort` field-read helpers instead of continuing to unpack those bridge-side intent fields inline after normalization
- `CharacterPresentationInput` now also exposes thinner field-read helpers for nested presentation subfields (`focus_target_id`, `requested_action`, `action_gait_hint`, `equipment_gait_hint`, `active_command_type`), and `KnightRoleSkin` / `CharacterRuntimeState` now consume those helpers instead of continuing to unpack presentation sub-dictionaries inline
- `CharacterRuntimeState` now also exposes thinner player-shell locomotion helpers for `motion_fields` / `locomotion_decision`, and `CharacterReplica._update_player_shell_locomotion()` now consumes those helpers instead of continuing to unpack those runtime-side intermediate dictionaries inline
- `CharacterRuntimeState` now also exposes thinner agent execution side-effect helpers for `focus_target_lookup` / `physiology_hint` / `role_state_effects` and the nested `target_lookup` shape, and `CharacterReplica` now consumes those helpers instead of continuing to unpack `execution_side_effect_plan` / `lookup` inline
- `CharacterReplica._on_character_agent_execution_received(...)` now also reads the normalized ingress `action` through a `CharacterRuntimeState` helper instead of directly calling `CharacterControllerPort.get_action_name(frame)` or continuing to fall back to shell-local payload-string access for that shared intent field
- `CharacterRuntimeState` now also exposes a thin `emitter actor_id` sync helper, and `CharacterReplica` now consumes that helper instead of continuing to read `role_state_fact_emitter.get("actor_id")` / `physiology_state_fact_emitter.get("actor_id")` inline
- `CharacterRuntimeState` now also exposes thin payload actor-target helpers (`dialogue`, `siming`, `runtime-state`) plus `command target position` / line-of-sight `collider` helpers, and `CharacterReplica` now consumes those helpers instead of continuing to unpack those payload/runtime-side fields inline
- verification truth is now also aligned with the current shared-actor runtime evidence: the `phase0` audit accepts `backend_message_type:siming_output` as valid proof for the minimal Siming reaction instead of requiring only the older `attention_applied:char_b` log shape
- `verify_l1_runtime_edges.py` is now green against current runtime truth because it hard-passes on backend-connect + initial zone-bootstrap + clean reconnect health, while the older reconnect/privacy/environment probe is explicitly isolated as legacy evidence
- broad `phase0` runtime verification is also green again after removing redundant verifier-side `PHASE0_DEBUG_LOGGING=1` injection; the repo now has current proof for both the narrowed execution slice and the broader demo acceptance path
- `CharacterRuntimeState` now also exposes a thin `line-of-sight hit collider` helper, and `CharacterReplica._has_line_of_sight_to_target()` now consumes that helper instead of continuing to access the physics-ray hit dictionary inline
- `PlayerShell` fallback motion-state publication now also reads the current human intent frame back through `CharacterControllerPort.normalize_intent_frame(...)`, so even the shell-side fallback path no longer needs to assume the narrower transitional frame shape directly
- `CharacterReplica` now also re-normalizes the adapter-built agent ingress frame through `CharacterControllerPort.normalize_intent_frame(...)` before staging active command state and `CharacterPresentationInput`, so the actor host no longer treats the adapter output as an unchecked one-off shape
- `CharacterReplica.apply_embodied_pose_sync(...)` now receives player motion state explicitly from `Phase0CharacterShellSync` instead of backreading `motion_state` from its parent node, so the player-shell pose handoff is less dependent on implicit wrapper state lookup
- `Phase0CharacterShellSync` now routes only through actor-facing alias methods (`apply_embodied_pose_sync`, `begin_embodied_control_frame`, `clear_embodied_control_frame`), so the helper no longer depends on the older player-shell-specific method names
- `Phase0ViewAnchorResolver` now also routes control-anchor / control-forward fallback only through actor-facing embodied-control aliases (`is_embodied_control_active`, `get_embodied_anchor_position`) instead of the older player-shell-specific names
- `Phase0ViewAnchorResolver` now also prefers the actor-facing `CharacterReplica.get_embodied_forward_vector()` before reaching into nested `CharacterReplica/VisualRoot` for no-input look/forward fallback, so view-direction fallback is less coupled to nested scene-node details while the old nested `VisualRoot` fallback still remains available as compat
- `Phase0ViewAnchorResolver` now also prefers the frozen direct wrapper mounts (`CharacterReplica`, `CameraHolder`) and the `PlayerShell.get_camera()` seam before falling back to broader recursive scene search, so wrapper-local camera/actor lookup is less dependent on deep tree walking
- `PlayerShell` now also exposes a thin `get_visual_forward()` alias, and `Phase0ViewAnchorResolver` now prefers that wrapper-facing forward seam before falling back to broader recursive `VisualRoot` search, further reducing resolver dependence on wrapper-internal tree shape
- `CameraOcclusionFader` now reads camera and control-anchor state back through `PlayerShell.get_camera()` / `get_control_anchor_position()` instead of directly querying `Phase0InputBridge`, further narrowing player-wrapper helper coupling
- the remaining normalized human-ingress fallback reads are now also thinner at the wrapper-helper edge: `PlayerShell` fallback motion-state publication now reads `move_local` / `gait` through `CharacterControllerPort.get_move_local(...)` and `get_gait_name(...)`, while `Phase0ViewAnchorResolver` now reads `desired_facing_yaw` / `actor_id` through `CharacterControllerPort.get_desired_facing_yaw(...)` and `get_actor_id(...)` instead of keeping those normalized-frame field names inline
- `PlayerShell` now also exposes thin state-read aliases for wrapper-owned movement state (`get_body_position`, `get_planar_velocity`, `get_vertical_velocity`, `is_grounded_state`, `get_numeric_setting`), and `Phase0PlayerBridge` / `CharacterMotor` now consume those aliases instead of continuing to read wrapper movement state through direct `player.global_position` / `player.velocity` / `player.is_on_floor()` / `body.get(...)` access
- `PlayerShell` now also exposes a thin `get_character_replica()` alias, and `Phase0PlayerBridge` now consumes that alias instead of continuing to tree-query `player.get_node_or_null("CharacterReplica")` directly from the bridge surface
- `docs/scene tree.md` is now synced to the current wrapper truth: `CharacterBase.tscn` no longer mounts `Phase0Embodiment` or a wrapper-level `VisualRoot`, and the old `scripts/player/Phase0PlayerEmbodiment.gd` helper shell has now been removed from the repo surface entirely
- the unused legacy `scripts/player/PlayerController.gd` path has now also been removed from the repo surface; current player-control truth is the shared `PlayerShell` + `Phase0PlayerBridge` + `CharacterMotor` path instead of a parallel controller file
- current demo narration and system summaries now describe the active player truth as `PlayerCharacter / CharacterBase` with an embedded `CharacterReplica(actor_id=char_c)` instead of saying the player directly controls `CharacterC` as a standalone shell
- `CharacterReplica._resolve_player_position()` now falls back directly to its own embodied transform instead of walking the old `CharacterC` / `Player` split, so the actor shell no longer carries that historical scene-shape lookup inside its own runtime path
- the same payload shape is now machine-checked by the `phase0` harness audit as `character_agent_execution_contract=proved`; that broader report now also lists `character_agent_execution_consumer=proved`, while the narrower `character-agent-execution` harness profile backed by a dedicated probe scene remains the more focused runtime proof that the shared actor runtime consumes and applies the contract
- that narrower `character-agent-execution` probe now also directly proves the received runtime payload itself carries the shared contract core (`actor_control_frames` / `presentation_plan` / `action_request_bundle`) instead of relying only on downstream consumption side effects
- `character_agent_output` remains static compatibility only on the bridge/bus side; `CharacterReplica` no longer connects the old output handler
- LocalPresentationBus / MainDemo / verification probes now use explicit debug logging toggles so harness evidence can stay rich without forcing default runtime log noise
- fresh-backend `phase0` verification is green again after tightening startup reconnect behavior: pre-open `backend_closed:-1` remains noise-only for failure semantics, but `MainDemoController` now still schedules a reconnect so strict runtime evidence reaches the shared actor ingress path
- actor-targeted character-agent settlements now carry a shared social-spatial settlement shape (`action_profile`, `source_action_request_type`, `applied_state_changes`) for approach / follow / seek_private_distance / withdraw / break_contact, while settlement authority still belongs to ESM
- current Stage B `L4` runtime remains dual-layer:
  - `CharacterAgentL4Executor` now serves as the execution-plan-first path for five-channel outputs and action-request bundles
  - `CharacterAgentL4Adapter` now behaves as a thin compatibility shell that derives legacy `CharacterGoalCommand` outputs from that plan rather than acting as an independent intent-to-command main path
- backend websocket/runtime glue no longer keeps its own inline fallback execution-plan reconstruction for legacy commands; that thin compatibility reconstruction is now routed back through `CharacterAgentL4Adapter.command_to_execution_payload(...)`
- `CharacterReplica` no longer keeps its own `_payload_string(...)` command/runtime payload unpacking helper; those string reads now route through `CharacterRuntimeState` thin helpers instead
- that compat shell now round-trips more of the execution plan than the earlier fallback layer did:
  - `producer_ts`
  - `causation_id` / `correlation_id`
  - `role_state_hint`
  - speech-class `dialogue_text`
- `CharacterAgentRuntime` now writes `character_agent_execution_request` into session timeline / memory for full-auto actors even while it still returns compatibility goal commands, so the repo must not claim full single-path `L4` convergence yet
- the runtime memory view can now be rehydrated from the session timeline durability path itself; this tightens durability truth around timeline-first recovery without claiming the broader memory closeout is complete
- `char_c` in `player_priority_assisted` mode is now machine-checked on the websocket/raw-fact path to suppress autonomous `character_agent_output` while still emitting `character_agent_suggestion`, and that assisted-path `character_agent_suggestion_packet` is now also written into session timeline / memory, so the current species/control-mode split is no longer just a local runtime assumption

Actor Stage 2 items still incomplete:

- stronger direct use of `CharacterIntentFrame` and `CharacterPresentationInput` as the active actor contracts across all actor-side consumers beyond the now-landed `character_agent_execution` ingress seam
- final shared actor scene/runtime convergence beyond the documented first host choice
- removal or explicit debug-gating of remaining migration diagnostics

Character-agent Stage B hard preconditions that still depend on full Stage 2 closeout:

- no final `L4` claim before shared actor ingress is unified
- no final `L4` claim before runtime-state extraction lands
- no final `L4` claim before the player-only wrapper split stops defining the actor architecture

## Debugging Note

Current debug additions still exist to prove actor/control/presentation boundaries under active migration.

The repo now has the first explicit debug/harness toggle layer:

- `LocalPresentationBus` only prints debug events when debug logging is enabled
- `MainDemoController` enables that path explicitly for autotest / focus-autotest / `PHASE0_DEBUG_LOGGING=1`
- runtime probes enable it explicitly before collecting verification evidence

Remaining work is to keep shrinking the amount of actor/runtime code that depends on debug-only surfaces, not to restore default always-on log noise.

## Task 7 Closeout Status

As of `2026-06-17`, the repo now has enough actor-side planning truth and prerequisite convergence work landed to let the full character-agent plan continue Stage B tasks honestly, with the following boundaries kept explicit:

- Stage A / actor-side final-convergence planning truth is present and linked in-repo
- the first real shared actor ingress family is landed in code and machine-checked
- `CharacterRuntimeState` extraction and wrapper-host narrowing are landed far enough that Stage B can keep converging against the shared actor substrate instead of treating it as undefined background work
- `Phase 0` runtime proof remains green after the current Stage 2 seam-tightening passes

This does **not** mean:

- Actor Stage 2 is fully complete
- shared actor scene/runtime convergence is fully closed
- Stage B may claim final single-path `L4 -> CharacterActor` convergence

The honest current handoff is:

- Stage B may continue on already-spec-backed tasks
- Stage B must keep using thin compatibility where necessary
- Stage B must not describe the runtime as fully converged while the remaining Stage 2 closeout items above are still open
