# Character Animation Asset Qualification And Concurrent Realization Sub-Specification

Date: `2026-09-14`

Status: `final child specification of the unified character action foundation`

Parent:
`2026-09-14-unified-character-action-foundation-and-inf-tag-contract-design.md`

## Purpose And Boundary

This specification defines how externally authored character models and
animations become qualified action assets for the shared actor runtime. It
focuses on the practical case where an external provider supplies full-body
clips while the runtime also needs locomotion and other actions to coexist.

It adds an asset qualification and realization layer. It does not create a
second action scheduler, body controller, physics authority, or animation
authoring system.

The project continues to consume externally authored animation content. The
qualification pipeline may map bones, extract root motion, create a filtered
presentation variant, and package a report, but it does not invent new motion
semantics or author replacement keyframes.

## Ownership And Source Of Truth

| Concern | Owner | Boundary |
| --- | --- | --- |
| Animation content and timing intent | External asset provider | Source clips and timing sheet |
| Skeleton mapping and asset qualification | Asset qualification pipeline | Mapping, track analysis, derived variants, report |
| Semantic action identity | Action asset manifest | `action:*` descriptor and realization profiles |
| Concurrent action admission | `ActorActionArbiter` | Claims, locomotion relation, cancellation, fallback |
| Physical motion and collision | `CharacterMotor` | `MotionContribution` and `PhysicsMotionCommand` |
| Physical evidence | Motor and sensors | Provisional `PhysicsContactEvidence` |
| World/gameplay consequence | ESM / Gameplay | `ActionAttempt` settlement and authority results |
| Local visual realization | `RolePresentationAdapter` | AnimationTree, masks, IK, VFX, SFX |

An animation marker is not a physical fact. A mask-qualified animation is not
permission to bypass resource claims. A qualification report is not an
authority result.

## Asset Qualification Pipeline

Every external character package follows this path before runtime admission:

```text
GLB / qualified FBX intake
    -> canonical skeleton mapping
    -> rest-pose, unit, slot, and clip discovery
    -> animation track and root-motion analysis
    -> optional build-time derived realization
    -> visual/physics claim review
    -> locomotion compatibility qualification
    -> qualification report and manifest
    -> runtime asset registry
```

The runtime must consume only registered realization profiles. It must not
inspect arbitrary tracks and decide at play time that a full-body clip is safe
to use as an upper-body action.

The package should retain provenance for every derived result:

```text
source_clip_ref
derived_clip_ref?
derived_from_clip_ref?
qualification_report_ref
package_digest
```

## Realization Modes For External Clips

The same semantic action may expose more than one qualified presentation
realization.

### Native upper-body realization

The external provider supplies a clip authored for upper-body coexistence.
This is the preferred result for actions such as aim, fire, reload, pickup,
and a one-handed interaction.

### Build-time derived upper-body realization

The pipeline filters a full-body source clip into an upper-body variant only
when track analysis and visual qualification prove that the result is safe.
The derivation is mechanical packaging, not new authored motion. The derived
clip must retain the source timing and typed markers, and its report must
record the canonical mask and any removed root or lower-body tracks.

### Full-body exclusive realization

The original clip is retained when it requires coordinated lower-body and
upper-body motion, changes pelvis/root support, or fails the upper-body
qualification checks. The action replaces or suspends locomotion according to
its descriptor and remains a valid action; it simply does not advertise
locomotion coexistence.

### Locomotion-driving realization

Some actions, such as a lunge or a committed charge, intentionally include
leg and root motion. They may coexist with a control lease only through the
`drive_locomotion` relation. Their root delta becomes a `MotionContribution`
and is collision-resolved by Motor; it is not applied by the presentation
layer.

### Additive realization

An additive clip must declare its reference pose, affected canonical bones,
constraint policy, and visual claims. Additive blending does not mean that the
clip occupies no resources.

## Qualification Rules For Full-Body Sources

The folder name or high-level category does not determine concurrency. The
pipeline evaluates the actual clip and manifest claims.

An upper-body concurrent candidate must satisfy all of the following:

- its canonical bone impact is limited to the declared mask and any explicitly
  allowed transition bones;
- root and pelvis translation obey the skeleton profile; unexpected translation
  rejects the candidate;
- lower-body tracks are absent, masked, or proven to be rest-pose tracks;
- the root motion profile is either absent or explicitly converted into a
  locomotion contribution;
- the upper/lower seam remains within the package's qualification thresholds;
- foot support remains compatible with the selected locomotion profile;
- hand, weapon, and interaction anchors remain within their declared envelope;
- the clip's physical claims are compatible with the intended concurrent
  action; and
- all required markers, cancel windows, and authority route metadata remain
  valid after derivation.

If any required check fails, the asset is not silently downgraded to an
upper-body action. It becomes full-body exclusive, remains queued until a
compatible realization is available, or is rejected according to its explicit
fallback policy.

## Canonical Skeleton And Mask Contract

External bone names are package input, not runtime resource IDs. Each package
provides a versioned mapping:

```text
package bone name -> canonical bone ID
```

The package also declares a mask profile. The profile defines the cut point,
pelvis policy, transition bones, and allowed root/pelvis channels. A generic
rule such as "Spine and above" is not sufficient for every skeleton.

The qualification report records both the declared mask and the actual curve
impact after import. A clip fails qualification if it writes undeclared
canonical bones above the configured tolerance or if a masked root/pelvis
track leaves unaccounted-for motion.

The runtime contract uses canonical IDs such as:

```text
pelvis
upper_body
left_arm
right_arm
left_hand
right_hand
left_leg
right_leg
head
root_translation
facing
```

Raw bone names remain in the package mapping and report for diagnostics.

## Root Motion And Locomotion Relation

Root motion is qualified independently of visual masking.

The descriptor must specify:

```text
locomotion_compatibility
  coexist | drive_locomotion | replace_locomotion | suspend

root_motion_policy
  hold | bounded_continue | reversible_continue

root_motion_profile_ref?
root_motion_required
```

For an upper-body derived clip, root and pelvis translation is normally
removed from the presentation clip. If the action intentionally drives a
lunge or charge, the action must use `drive_locomotion` and expose a qualified
root-motion profile instead of pretending to be upper-body-only.

No asset or presentation node may write the actor transform directly. Root
motion is sampled as a `MotionContribution`, composed with other contributions,
and consumed by `CharacterMotor`.

## Marker, Evidence, And Authority Contract

The asset stores typed marker timing, not physical truth:

```text
timing_marker {
  marker_id
  time_seconds
  marker_kind
  emits_attempt
  evidence_requirement
}
```

Examples of `marker_kind` include `footstep_expected`,
`hand_reach_candidate`, `weapon_contact_candidate`, and
`landing_expected`.

The runtime path is:

```text
animation marker observation at physics tick T
    -> Motor / sensor PhysicsContactEvidence(T)
    -> same-tick ActionAttempt(T) join when evidence is required
    -> ESM / Gameplay revalidation
    -> AuthorityResult
```

Footstep and VFX/SFX markers may remain local presentation events. A weapon
contact or interaction marker can create an `ActionAttempt`, but the marker
cannot settle damage, pickup, occupancy, or object state. The existing ESM
sub-specification remains the authority for target revision, spatial range,
occupancy, idempotency, and settlement.

The presentation marker is never itself a contact confirmation. A marker that
requires physical evidence waits for Motor evidence from the same tick; a
marker that declares no evidence requirement may emit after observation. This
ordering is part of the asset qualification report and the runtime contract.

## Realization Profile Contract

The active action descriptor may expose multiple qualified realization
profiles:

```text
CharacterActionAssetDescriptor {
  semantic_action_id
  source_clip_ref
  realization_profiles[]
  canonical_skeleton_mapping_ref
  canonical_bone_mask_ref?
  resource_claims[]
  physics_claims[]
  physics_profile_ref
  authority_route_ref       # esm | gameplay | composite (Phase 1)
  required_clips[]
  optional_clips[]
  locomotion_compatibility
  cancel_windows[]
  timing_markers[]
  root_motion_profile_ref?
  root_motion_policy
  root_motion_required
  fallback_policy
  presentation_tags[]
  required_slots[]
  qualification_report_ref
  atomic_sequence: []
}
```

```text
realization_profile {
  profile_id
  mode
    # native_upper_body | derived_upper_body |
    # full_body_exclusive | drive_locomotion | additive
  clip_ref
  derived_from_clip_ref?
  bone_mask_ref?
  locomotion_compatibility
  root_motion_policy
  qualification_status
  fallback_rank
}
```

The semantic action ID remains stable across realization profiles. Agents,
INF, and network messages request the semantic action; they do not select raw
clip names or send bone poses. Profile selection is a local qualified-asset
decision, optionally correlated with a package digest in connected mode.

`atomic_sequence` remains empty in Phase 1. Future atom expansion occurs
before ordinary resource arbitration and cannot bypass qualification or
physical claims.

## Runtime Selection And Fallback

When an action request arrives, the runtime performs this sequence:

```text
semantic action request
    -> resolve qualified profiles
    -> filter by current locomotion, claims, and physics profile
    -> select the highest-ranked compatible profile
    -> admit, queue, or reject through ActorActionArbiter
```

Fallback is explicit:

```text
fallback_policy
  exclusive
  queue_until_compatible
  reject
  presentation_only
```

The runtime must not silently convert a rejected upper-body derivation into a
different physical action. If no concurrent profile is qualified, the action
may be admitted as full-body exclusive only when that fallback is declared.

Visual profile selection does not change physical claims. An upper-body clip
can still conflict on `physics_body`, `support_contact`,
`weapon_hit_volume:<id>`, `interaction_reach`, or `target_occupancy:<id>`.

## Qualification Report

Each package produces a machine-readable report with at least:

- package and source clip digest;
- Godot/importer and qualification profile identity;
- canonical skeleton mapping result;
- rest pose, unit, scale, root, and attachment-slot result;
- actual canonical bone curve impact;
- root/pelvis translation and rotation audit;
- derived mask and removed-track summary;
- marker and timing validation;
- visual seam, support, hand/weapon envelope, and locomotion compatibility
  results;
- visual and physical resource claims;
- selected realization profiles and fallback policy; and
- final status: `qualified`, `qualified_with_fallback`, or `rejected`.

The report is a build/import artifact. Runtime does not infer missing claims
from animation curves.

## Phase 1 External Delivery Contract

For each of at least two external characters, the qualification package must
provide:

- a complete canonical skeleton mapping and stable rest pose;
- qualified Idle/Walk/Run/Jump/Turn locomotion;
- one external attack or interaction action with phase timing, cancellation,
  markers, authority route, and recovery policy;
- either a native or qualified derived concurrent realization when movement and
  the action must coexist;
- a qualified full-body fallback for actions that cannot coexist;
- declared root-motion and physics profiles;
- equipment and interaction attachment slots; and
- a qualification report that can be inspected by the animation debugger.

At least one Phase 1 package must additionally provide one qualified held-item
slot/hand anchor and a phase-marked melee action whose semantic ID, claims,
marker, and authority route can reach the standard `ActionAttempt` path. A
hitscan action family may be represented by a semantic request/route fixture
without requiring projectile or ammunition animation assets in this phase.

The first milestone must demonstrate all of these cases where the package
supports them:

```text
Idle + action
Walk/Run + qualified concurrent action
full-body exclusive action
rejected or unsupported concurrent action with explicit recovery
```

If a provider supplies only a full-body clip and no safe derived profile, the
runtime reports that the action does not support locomotion coexistence. This
is an asset qualification result, not a hidden runtime failure.

## Normative Phase 1 Asset Delivery Rules

The following rules are the external handoff contract. `MUST` means the
package cannot enter the Phase 1 runtime registry without it. `SHOULD` means
the package remains admissible only with an explicit qualification note or
fallback. `MAY` describes an optional extension.

### Package and model rules

1. The package **MUST** contain a runtime-ready `.glb` model. FBX **MAY** be
   supplied as source, but it **MUST** be converted and qualification-tested
   before runtime use.
2. The model **MUST** declare metres, applied object transforms, a stable rest
   pose, a declared root bone, and the canonical forward/up convention.
3. The package **MUST** provide a versioned external-bone-to-canonical-bone
   mapping. Exact external bone names are not required; unmapped required
   canonical bones are a qualification failure.
4. Required equipment and interaction attachment slots **MUST** be declared
   when the package contains combat or interaction actions.
5. A fixed character height range is **NOT** a contract requirement. Unit,
   scale, profile, and mapping validation are required instead.

### Locomotion rules

6. Each Phase 1 character **MUST** provide qualified `idle`, `walk_forward`,
   `run_forward`, `jump_start`, `jump_loop` or `fall`, `jump_land`, and left
   and right turn realizations.
7. Source frame rate **MUST** be declared and recorded. A project-recommended
   rate of 60 FPS does not make other time-valid source rates invalid.
8. Locomotion clips **MUST** declare whether they are in-place or root-motion
   driven. Root deltas **MUST** be consumed through Motor; an animation clip
   never writes the actor transform.
9. Strafe, backward, crouch, and multi-direction variants are **MAY** assets
   for Phase 1 and become required only when a scenario explicitly tests them.

### Action and concurrency rules

10. Each Phase 1 character **MUST** provide at least one external attack or
    interaction action with duration, phase markers, cancellation or recovery
    timing, resource claims, physics profile, and authority route metadata.
11. An action intended to coexist with Walk/Run **MUST** provide either a
    qualified native upper-body realization or a qualification-approved
    build-time derived upper-body realization.
12. A full-body-only action **MUST** be registered as
    `full_body_exclusive`, `drive_locomotion`, `queue_until_compatible`, or
    `reject`. It **MUST NOT** be labelled upper-body concurrent by folder name,
    clip name, or manual override without a report.
13. Roll, knockdown, death, climb, mount, and coordinated lunge actions
    **SHOULD** remain full-body or locomotion-driving unless a dedicated
    concurrent realization passes the same qualification rules.
14. A semantic action **MUST** have a stable action ID independent of its clip
    filename. Multiple qualified realization profiles are allowed for one
    semantic action.

### Timing, evidence, and authority rules

15. Every action that can create an authority attempt **MUST** provide typed
    marker IDs and times. Markers **MUST** be time-based, not inferred from a
    fixed frame number at runtime.
16. A marker **MUST NOT** be treated as proof of physical contact. Motor or
    sensor evidence and ESM/Gameplay revalidation remain mandatory.
17. The package **MUST NOT** contain damage, hit outcome, inventory mutation,
    status application, ownership transfer, or other world-truth values.
18. `atomic_sequence` **MUST** remain `[]` for every Phase 1 asset.

### Physics and qualification rules

19. The package **MUST** declare the physical profile required by its action:
    grounded/airborne mode, support requirements, root-motion envelope, and
    relevant physical claims.
20. Weapon, interaction, and target occupancy claims **MUST** use canonical
    resource IDs. A boolean such as `claims_weapon = true` is insufficient.
21. A derived upper-body profile **MUST** retain source timing and marker
    provenance, record removed tracks, and pass mask, pelvis/root, seam,
    support, hand/weapon, and locomotion compatibility checks.
22. Every registered profile **MUST** have a machine-readable qualification
    report with status `qualified`, `qualified_with_fallback`, or `rejected`.
23. `rejected` profiles **MUST NOT** enter the runtime registry. A
    `qualified_with_fallback` package **MUST** expose its explicit fallback to
    the Arbiter and debug overlay.
24. Runtime code **MUST NOT** perform ad hoc track deletion, infer physical
    claims from curves, or silently switch a failed concurrent action into a
    different physical action.

### Accepted delivery levels

| Delivery level | Required contents | Supported result |
| --- | --- | --- |
| Minimum movement package | Model, mapping, rest pose, Phase 1 locomotion, report | Shared locomotion only |
| Full-body action package | Minimum package plus one full-body action and timing sheet | Action works as explicit full-body/drive-locomotion fallback |
| Concurrent action package | Full-body source plus native or qualified derived upper-body realization | Action may coexist with Walk/Run |
| Presentation extension | Additive/reaction clips with reference pose and claims | Local presentation only unless separately qualified |

### First milestone acceptance for external packages

For two characters to count as qualified shared assets, both packages **MUST**
pass the common movement contract and each **MUST** complete one of these
tested action paths:

```text
Idle + action
Walk/Run + qualified concurrent action
full-body exclusive action with explicit recovery
```

If a provider delivers only full-body clips, the package can still pass the
movement and full-body action portions. It cannot claim Walk/Run plus action
coexistence until a native or derived concurrent profile is qualified.

## Verification Requirements

Required verification covers:

1. canonical mapping, rest pose, units, root, and required slots;
2. source-rate and marker preservation using time-based validation;
3. upper-body derivation rejecting undeclared pelvis/root/lower-body motion;
4. full-body fallback remaining playable without a second body writer;
5. root motion becoming a Motor contribution rather than a Transform write;
6. locomotion plus upper-body playback through AnimationTree/mask previews;
7. physics claims remaining separate from visual claims;
8. marker-only local contact producing no world consequence without settlement;
9. semantic action requests selecting profiles without exposing clip names to
   CharacterAgent, INF, or network peers; and
10. qualification report failure preventing unqualified profiles from runtime
    registration.

## Relation To Other Specifications

- The unified action foundation owns semantic action identity, claims,
  arbitration, and the single actor ingress.
- The physics sub-specification owns root-motion contribution, Motor command,
  collision execution, and physical evidence.
- The ESM settlement sub-specification owns ActionAttempt validation,
  occupancy, revision, idempotency, and world consequences.
- The connected-action sub-specification owns intent transport, package/runtime
  identity, prediction, and the separation from future physical body streams.
- The character action asset interface remains the compact field index; this
  document owns qualification and realization detail.

## Explicit Deferrals

- no authored replacement animation content;
- no automatic quality acceptance based only on folder names or clip names;
- no runtime track surgery or runtime inference of physical claims;
- no generic procedural retargeting that fabricates action semantics;
- no raw-pose networking;
- no server-authoritative rigid-body simulation; and
- no Phase 1 atomic-action expansion.
