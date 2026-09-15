# Character Animation Asset Qualification And Concurrent Realization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn externally authored character GLB packages into machine-qualified presentation profiles that can safely support locomotion, full-body actions, and explicit concurrency fallbacks.

**Architecture:** The importer/qualification layer owns skeleton mapping, track analysis, derived presentation packaging, and reports. The runtime consumes only registered profiles; it never edits tracks or infers physical claims at play time. `CharacterMotor` remains the only transform writer and the arbiter remains the only admission authority.

**Tech Stack:** Godot 4.6 GDScript, GLB/glTF, existing `AnimationPlayer`/`AnimationTree`, Python manifest tooling, pytest, and headless Godot qualification scenes.

**Spec:** `docs/superpowers/specs/2026-09-14-character-animation-asset-qualification-and-concurrent-realization-subspec.md`

**Execution status:** Task-level reference for Task 6-8 of
`docs/superpowers/plans/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-implementation-plan.md`.
The unified plan is the only implementation order; this file does not define
an alternate runtime path or release gate.

## Global Constraints

- External animation content is imported; this plan does not author replacement keyframes.
- A full-body source clip is never labelled upper-body concurrent without a qualification report.
- Root motion is sampled into `MotionContribution`; no presentation node writes an actor transform.
- Semantic action IDs, not raw clip names, cross the CharacterAgent, INF, Siming, or network boundaries.
- `atomic_sequence` remains `[]` for every Phase 1 asset.
- Phase 1 requires one qualified equipment slot/hand anchor and one
  phase-marked melee action in at least one accepted package. Hitscan is a
  semantic route fixture, not a requirement for projectile or ammo assets.
- Rejected profiles never enter the runtime registry.
- Structural GLB validation is not a substitute for Godot visual qualification.

### Task 1: Define the package manifest and report schema

**Files:**
- Modify: `scripts/character/CharacterActionAssetDescriptor.gd`
- Create: `scripts/character/CharacterAssetQualification.gd`
- Create: `assets/validation/schemas/character-action-asset-manifest.v1.json`
- Create: `assets/validation/schemas/character-qualification-report.v1.json`
- Test: `backend/tests/test_character_asset_manifest_contract_static.py`

**Interfaces:**
- `CharacterAssetQualification.validate_binding(Dictionary) -> Dictionary`
- `CharacterAssetQualification.validate_profile(Dictionary) -> Dictionary`
- `CharacterActionAssetDescriptor.validate() -> Dictionary`

- [ ] Add fields for `source_clip_ref`, `derived_clip_ref`, `canonical_skeleton_mapping_ref`, `bone_mask_ref`, `resource_claims`, `physics_claims`, `physics_profile_ref`, `locomotion_compatibility`, `root_motion_policy`, `root_motion_required`, `timing_markers`, `cancel_windows`, `fallback_policy`, `qualification_report_ref`, and `atomic_sequence`.
- [ ] Add `action_family` (`melee` or `hitscan`) and `weapon_ref?` as semantic
  profile metadata; reject damage, hit, ammo, and transform fields.
- [ ] Make `atomic_sequence` default to an empty `Array[StringName]` and reject non-empty values in Phase 1 validation.
- [ ] Encode report status as exactly `qualified`, `qualified_with_fallback`, or `rejected`.
- [ ] Add static tests for stable semantic IDs, provenance fields, and rejection of authoritative damage/effect fields.
- [ ] Run `python -m pytest backend/tests/test_character_asset_manifest_contract_static.py -v` and verify the new schema tests fail before implementation.
- [ ] Implement the minimum validator and rerun the focused test until it passes.

### Task 2: Implement canonical skeleton and attachment mapping

**Files:**
- Create: `scripts/character/CharacterCanonicalRigProfile.gd`
- Create: `assets/validation/profiles/paralls_humanoid_v1.json`
- Modify: `assets/validation/manifests/character-qualification.example.json`
- Test: `backend/tests/test_character_canonical_rig_mapping_static.py`

**Interfaces:**
- `CharacterCanonicalRigProfile.resolve_external_bone(String, Dictionary) -> StringName`
- `CharacterCanonicalRigProfile.validate_required_groups(Skeleton3D, Dictionary) -> Dictionary`

- [ ] Define canonical slots for root, `pelvis`, `upper_body`, clavicles,
  `left_arm`/`right_arm`, hands, legs, feet, neck, and `head`; package-specific
  bone names remain only in the mapping profile.
- [ ] Support explicit external mappings and candidate lists without runtime name guessing.
- [ ] Validate hand attachment anchors and record unmapped optional finger/facial bones separately from required body failures.
- [ ] Require at least one declared hand/weapon attachment anchor for the
  Phase 1 melee package and record its canonical `weapon_slot:<id>` claim.
- [ ] Add mappings for the existing Bip001 knight and Mixamo-style candidate skeletons in test fixtures.
- [ ] Run the focused mapping test and the existing asset qualification contract tests.

### Task 3: Add clip track-impact and root-motion analysis

**Files:**
- Create: `scripts/qualification/AnimationTrackImpactAnalyzer.gd`
- Create: `scripts/qualification/RootMotionAudit.gd`
- Modify: `scripts/qualification/CharacterAssetQualificationRunner.gd`
- Test: `backend/tests/test_character_animation_track_impact_static.py`

**Interfaces:**
- `AnimationTrackImpactAnalyzer.inspect(Animation, Dictionary) -> Dictionary`
- `RootMotionAudit.inspect(Animation, StringName) -> Dictionary`
- `CharacterAssetQualification.validate_clip_impact(Dictionary) -> Dictionary`

- [ ] Report actual canonical bone impact, transform channels, root/pelvis displacement, and unexpected undeclared tracks.
- [ ] Distinguish rest-pose tracks from meaningful lower-body motion using a configured tolerance.
- [ ] Mark locomotion clips as `in_place` or `root_motion` and retain source frame rate and duration.
- [ ] Add fixtures proving the knight and NPC candidate clips are full-body and cannot be silently admitted as upper-body clips.
- [ ] Run `python -m pytest backend/tests/test_character_animation_track_impact_static.py -v`.

### Task 4: Build qualified realization profiles

**Files:**
- Create: `scripts/qualification/UpperBodyRealizationBuilder.gd`
- Create: `scripts/qualification/CharacterQualificationReportWriter.gd`
- Modify: `scripts/qualification/CharacterAssetQualificationRunner.gd`
- Create: `assets/validation/fixtures/qualified-realization-profiles.json`
- Test: `backend/tests/test_character_realization_profile_static.py`

**Interfaces:**
- `UpperBodyRealizationBuilder.build(Animation, Dictionary) -> Dictionary`
- `CharacterQualificationReportWriter.write(Dictionary, String) -> void`

- [ ] Implement native upper-body registration when the package supplies a declared mask-qualified clip.
- [ ] Implement build-time filtered variants only when track impact, seam, support, and root/pelvis checks pass.
- [ ] Retain original clips as `full_body_exclusive` or `drive_locomotion` when lower-body coordination is required.
- [ ] Preserve marker timing and provenance in derived profiles; record removed tracks and mask identity.
- [ ] Preserve `weapon_hit_volume:<id>` and action-family metadata when a
  qualified weapon action is native or build-time derived.
- [ ] Emit explicit fallback rank and policy for every semantic action.
- [ ] Run the focused test and inspect a generated report for a passing and rejected profile.

### Task 5: Repair and stage existing repository assets

**Files:**
- Create: `assets/validation/manifests/crusader-knight-qualified-candidate.json`
- Create: `assets/validation/manifests/npc-ch31-qualified-candidate.json`
- Create: `assets/validation/manifests/female-trio-0.4-qualified-candidate.json`
- Modify: `scenes/active/crusader_knight/KnightRoleSkin.tscn`
- Modify: `assets/active/crusader_knight/crusader_knight.glb.import`
- Create: `scenes/active/apartment_test/NpcCh31RoleSkin.tscn`
- Test: `backend/tests/test_character_asset_staging_static.py`

**Interfaces:**
- Each candidate manifest exposes `qualification_status`, package digest, canonical mapping, clip map, and fallback policy.

- [ ] Remove old `assets/characters/shared/...` and `assets/artpacks/...` references from staged wrappers by using self-contained active copies.
- [ ] Keep archive sources untouched and do not promote a candidate to `approved` before headless qualification and visual review.
- [ ] Stage one per-role female-trio GLB only as an opt-in candidate; do not stage the rejected visual 0.4.0 result as approved.
- [ ] Verify the active knight and staged NPC wrappers load their embedded or co-located textures without external project paths.
- [ ] Run `python -m pytest backend/tests/test_character_asset_staging_static.py -v`.

### Task 6: Integrate registry selection with the runtime presentation adapter

**Files:**
- Create: `scripts/character/CharacterEmbodimentAssetRegistry.gd`
- Modify: `scripts/character/KnightRoleSkin.gd`
- Modify: `scripts/character/GenericRoleSkin.gd`
- Modify: `scripts/character/CharacterPresentationAssetResolver.gd`
- Test: `backend/tests/test_character_asset_registry_static.py`

**Interfaces:**
- `CharacterEmbodimentAssetRegistry.register(Dictionary) -> Dictionary`
- `CharacterEmbodimentAssetRegistry.resolve(StringName, Dictionary) -> Dictionary`
- `CharacterPresentationAssetResolver.resolve_profile(StringName, Dictionary) -> Dictionary`

- [ ] Register only reports with accepted status and complete provenance.
- [ ] Select profiles by semantic action, current locomotion, resource claims, and fallback policy.
- [ ] Forbid raw clip selection from Agent/INF/network payloads.
- [ ] Keep animation preview and runtime simulation separate; preview cannot emit attempts or root-motion commands.
- [ ] Run the focused registry test and existing presentation resolver tests.

### Task 7: Qualification evidence and gate closure

**Files:**
- Modify: `scenes/qualification/CharacterAssetQualification.tscn`
- Modify: `scripts/qualification/CharacterAssetQualificationRunner.gd`
- Create: `scripts/verification/verify_character_asset_qualification.py`
- Test: `backend/tests/test_character_asset_qualification_profile.py`

- [ ] Run the knight, NPC, and one female-trio candidate through headless Godot qualification.
- [ ] Record separate results for model import, skeleton mapping, locomotion, action timing, concurrency, physics claims, and visual review.
- [ ] Prove that a full-body-only action is reported as exclusive/queued/rejected rather than concurrent.
- [ ] Prove `atomic_sequence=[]` and absence of world-truth fields in every accepted manifest.
- [ ] Prove one accepted package reaches the melee marker/claim handoff and a
  hitscan semantic profile can be resolved without selecting a raw clip.
- [ ] Run `python -m pytest backend/tests/test_character_asset_qualification_profile.py -v`.
- [ ] Run `python scripts/verification/harness.py --profile godot-project` and retain the report paths.

## Completion Criteria

- [ ] At least two character packages have complete canonical mapping and machine-readable qualification reports.
- [ ] One package demonstrates a qualified concurrent upper-body action; another demonstrates explicit full-body fallback or rejection.
- [ ] One accepted package demonstrates a qualified held-item slot and
  phase-marked melee action; hitscan remains a semantic request/authority
  fixture without client-side damage or ballistic truth.
- [ ] Runtime selection uses semantic IDs and registered profiles only.
- [ ] No package or presentation adapter writes gameplay consequences or actor transforms.
- [ ] Candidate assets remain visibly classified as candidate until Godot evidence and review pass.
