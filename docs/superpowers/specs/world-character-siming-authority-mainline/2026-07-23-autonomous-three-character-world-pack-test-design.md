# Autonomous Three-Character World Pack Test Design

Status: `awaiting-user-review`

Date: `2026-07-23`

## Purpose

Define a repeatable, no-human-input 30-minute autonomous character test that proves the current world-character-Siming-authority direction across two distinct world packs:

- World A: `neon-night-apartment`, based on the supplied three-bedroom apartment art package.
- World B: `candlelit-throne-hall`, based on the existing throne hall runtime surface.

Each world contains three independent agent-controlled characters. The shared test harness injects objective pressure events but never specifies dialogue, alliances, actions, or endings. Characters must act through their profile/dossier, private perception, memory, relationship and ability projections, authority constraints, and Godot embodiment.

This is a test design, not a claim that the complete embodied action runtime, relationship graph runtime, ability graph runtime, live model providers, or VLA providers already exist.

## Goals

1. Run one 30-minute session per world with no player input.
2. Exercise three autonomous characters per world, with complete authored identity, goals, private truth, relationship seeds, and capability seeds.
3. Prove open-ended social outcomes under fixed world pressures: cooperation, refusal, concealment, negotiation, avoidance, escalation, recovery, or unresolved coexistence are all valid outcomes.
4. Prove authority and embodiment boundaries: language and strategy stay open-ended, while object, spatial, physical, relationship, and world changes remain structured and verified.
5. Produce replayable evidence: event traces, model decisions, authority results, private-safe projections, screenshots, and final world/actor state.

## Non-goals

- No scripted final dialogue or mandatory single ending.
- No claim that an LLM, VLA, animation, or Godot client can write world truth directly.
- No full combat, economy, production relationship graph, or production VLA implementation.
- No requirement for a complete action library before the first closure.
- No replacement of the existing mainline, character mind core, authority settlement, or Godot local-presentation boundaries.

## Shared Autonomous Scenario Harness

### Run Contract

Each run creates:

```text
run_id
world_pack_id
fixed_seed
authority_tick_clock
three actor dossiers and profile revisions
world state revision
event/decision/settlement trace
Godot screenshot and replay references
provider readiness/degrade records
```

The harness accepts no player input after start. It may inject only declared objective world events at scheduled windows. It must not select an actor's dialogue content, target, action, acceptance, refusal, alliance, or ending.

### Shared Data Flow

```text
world pack definitions + actor dossier/profile
-> bootstrap authority facts, private relationship seeds, ability seeds
-> actor-private perception and memory
-> L2 interpretation -> L3 planning -> L4 semantic execution
-> ability affordance projection and authority settlement
-> local Godot embodiment / physical observation
-> world, memory, relationship, and trace writeback
-> replay and acceptance evidence
```

### Safety and Degrade Rules

- Model provider timeout, VLA low confidence, invalid output, path failure, contact failure, and target refusal produce typed observations and a bounded replan/abort path.
- Same action plus same blocking reason may not repeat more than twice without a changed plan, changed target, or explicit withdrawal.
- Cost, latency, error, and event-volume budgets must be recorded. A breached budget triggers a visible controlled-degrade state and evidence flush.
- Private relationship graph state, secret content, and raw private memory never enter public Godot views or Siming raw inputs.
- All world/physical effects require authority settlement and post-action observation; animation completion is never proof of success.

## Relationship and Ability Graph Alignment

### Relationship Graphs

The design follows the two-layer contract:

```text
AuthorityRelationshipGraph
  objective roles, occupancy, mandates, duties, contracts, and commitments

ActorPrivateRelationshipGraph
  trust, hostility, fear, respect, intimacy, obligation_felt, suspicion,
  labels, beliefs, known-secret references, misunderstandings, evidence refs
```

Objective facts are created only by bootstrap authority events or authority settlement. Private relationship state belongs to its owner actor and changes only through visible percepts, memory, disclosed communication, or internal interpretation events with evidence references.

Legacy dossier seed fields `initial_trust`, `initial_affinity`, `initial_obligation`, and `initial_tension` are bootstrap inputs only. This pack's materialization policy maps `initial_affinity` to `intimacy`, and maps `initial_tension` to sourced `hostility` and/or `suspicion`; no direct, source-free relation score writes are allowed.

### Ability Graphs

The design separates:

```text
stable ability graph
  learned abilities, authored grants, restrictions, skill-action paths

momentary AbilityAffordanceProjection
  stable abilities + body + resources + equipment + distance + permissions
  + target/world facts + authority policy
```

An actor may permanently possess a skill while an action is currently blocked by privacy, distance, missing tool, target state, body state, or authority policy. Affordance queries never write learned ability state or settle world effects.

## World A: Neon Night Apartment

### Source Asset Reality

The source project is `Apartment_Godot_Project_PortableFixed_20260720_152626`. Its scene metadata identifies:

- `Floor_RoomA_Living_Room___Open_Kitchen`
- `Floor_HallD_Quiet_Buffer_Hallway`
- `Floor_RoomB_Lin_Mo_Bedroom`
- `Floor_RoomC_Su_Xiao_Bedroom`
- `Floor_RoomD_Chen_Yuan_Bedroom`
- beds, desk, sofa, table, lamps, night-city window assets, and three NPC scenes (`CH01`, `CH22`, `CH31`).

The supplied package has automatic collision and static furniture, but its chair/desk set is currently static collision. It is not evidence that a chair can already be kicked over. A dynamic chair adapter is required.

### Premise

Three tenants have maintained a fragile, low-interference cohabitation arrangement. On a night when the apartment is lit by city neon, an unsigned residence-adjustment proposal appears on the shared table. It accurately reflects shared expenses and private schedules. Its appearance makes ordinary domestic objects, distances, rooms, and privacy boundaries socially meaningful.

### Objective Authority Facts

```text
actor:lin_mo  --residence_occupancy--> space:room_b_lin_mo
actor:su_xiao --residence_occupancy--> space:room_c_su_xiao
actor:chen_yuan --residence_occupancy--> space:room_d_chen_yuan
household:neon_apartment --shared_cost_obligation--> account:utilities:current_period
```

No debt, blame, authorship, or interpersonal emotion is objective fact at bootstrap.

### Character Dossiers

#### Lin Mo / CH01

- Public identity: 29-year-old remote interaction designer; primary lease contact.
- Values: order, fairness, personal boundary, explainable rules.
- Personality: high conscientiousness, low impulsivity, medium openness, low extraversion.
- Need priority: safety/stability, control, fair treatment, belonging.
- Long goal: preserve a sustainable household without carrying every common responsibility alone.
- Private truth: Lin wrote the unsigned residence-adjustment proposal to observe the others' unguarded response.
- Skills/grants: `skill:apartment.document_review`, `skill:household.coordination`, `skill:social.deescalation`.
- Supported paths: inspect proposal, compare shared expense record, request a household meeting, propose a rule.
- Restrictions: cannot enter private rooms, inspect private devices, or enforce a rule without authority/consent.
- Expression: measured speech, evidence before emotion, contained hand movement, withdrawal under shame.
- Initial private perspectives: trusts Su more than Chen; respects Chen's ability but suspects avoidance of household responsibility.

#### Su Xiao / CH22

- Public identity: 27-year-old freelance sound editor working late hours.
- Values: relational warmth, being heard, honest expression, livable flexibility.
- Personality: empathic, open, socially initiating, sensitive to prolonged coldness.
- Need priority: belonging, understanding, autonomy, safety.
- Long goal: turn cohabitation into genuine cooperation rather than silent rule compliance.
- Private truth: Su retained a night recording that can corroborate abnormal device noise, but disclosure may violate privacy.
- Skills/grants: `skill:apartment.acoustic_observation`, `skill:social.mediation`, `skill:household.hospitality`.
- Supported paths: inspect audio evidence, invite discussion, mediate speaking turns, prepare/hand over a drink.
- Restrictions: cannot treat emotional inference as fact or disclose private recording without a policy-allowed choice.
- Expression: open questions, relational reframing, directness after repeated dismissal.
- Initial private perspectives: sees Lin as reliable but controlling; values Chen's openness but is increasingly hurt by night noise.

#### Chen Yuan / CH31

- Public identity: 31-year-old robotics simulation engineer under delivery pressure.
- Values: autonomy, efficiency, technical competence, result-oriented repair.
- Personality: high confidence and openness, moderate conscientiousness, low warmth of expression.
- Need priority: competence proof, autonomy, resource continuity, belonging.
- Long goal: finish the current project without being forced from the apartment.
- Private truth: Chen's unannounced high-load simulation work caused most of the utility anomaly; stopping it immediately risks a work loss.
- Skills/grants: `skill:apartment.equipment_diagnostics`, `skill:household.cost_estimation`, `skill:physical.object_handling`.
- Supported paths: inspect own equipment, estimate compensation, propose cost split, move a light object when physically feasible.
- Restrictions: cannot alter common wiring, enter private rooms, or claim payment that authority has not settled.
- Expression: technical framing, rapid solution proposals, defensive irony under pressure.
- Initial private perspectives: considers Lin useful but intrusive; trusts Su's goodwill and may depend on her mediation.

### Required Scene Entities

```text
document:residence_adjustment_proposal  inspect/share/conceal/place
evidence:utility_statement              inspect/compare/share
evidence:night_recording                inspect/disclose_with_policy
item:cup_01                              take/place/hand_over
chair:dynamic_01                         sit/push/kick/move; RigidBody3D
light:apartment_common                   stable/low_light/restored
door:room_b|room_c|room_d                open/closed/locked; privacy policy
zones: living_kitchen, quiet_hall, room_b, room_c, room_d
```

### Scheduled Pressure Windows

| Time | Objective event |
| --- | --- |
| 0-5 min | Night routine; actors begin in declared rooms or shared zone. |
| 5-10 min | Common light enters `low_light`; proposal becomes visible on table. |
| 10-16 min | Utility anomaly and equipment timeline become inspectable facts. |
| 16-22 min | Recording/document clues enter permitted perception range. |
| 22-27 min | Hallway, doors, and dynamic chair create spatial/physical pressure. |
| 27-30 min | Light restores; household settlement window opens. |

Valid outcomes include shared rule agreement, compensation proposal, private coalition, concealment, withdrawal, ongoing conflict, or unresolved coexistence.

## World B: Candlelit Throne Hall

### Premise

On the eve of a regency meeting, an unsigned border warning alleges that the north gate guard has been compromised. A sealed letter, seal record, fading eternal lamp, and side-door signal support different explanations. The meeting starts in 30 minutes; the characters must decide whether to investigate, lock down, report, delay, or preserve ceremony.

### Objective Authority Facts

```text
actor:ysara  --royal_guard_command--> organization:royal_guard
actor:thomas --record_keeping_duty--> organization:regency_court
actor:mare    --envoy_mandate--> organization:border_council
actor:ysara  --security_custody--> space:throne_hall
actor:thomas --evidence_custody--> evidence:sealed_letter|seal_record
```

### Character Dossiers

#### Ysara

- Public identity: royal guard captain.
- Values: safety, responsibility, defensible order.
- Private truth: once ignored Mare's retreat recommendation in a border action and now carries concealed guilt.
- Skills/grants: `skill:guard.command_basics`, `skill:guard.threat_assessment`, `skill:guard.access_control`.
- Paths: inspect threat signal, secure entry, request evidence, escort person.
- Private perspectives: respects Mare's field ability but distrusts her urgency; trusts Thomas's procedure but suspects hesitation under danger.
- Restriction: cannot enact an irreversible lockdown or force without authority, feasible access, and policy conditions.

#### Thomas

- Public identity: court recorder and procedure keeper.
- Values: evidence integrity, reversible decisions, procedural justice.
- Private truth: an old seal record has a process flaw caused by his earlier shortcut; it is embarrassing but not treason.
- Skills/grants: `skill:archive.document_verification`, `skill:court.procedure`, `skill:public_recording`.
- Paths: inspect seal, compare record, record decision, issue procedural warning.
- Private perspectives: regards Ysara as reliable but potentially over-security-focused; sees Mare as informed but pressuring.
- Restriction: cannot declare treason or grant sealed access from suspicion alone.

#### Mare

- Public identity: border envoy.
- Values: practical risk response, speed, responsibility to frontline lives.
- Private truth: part of the warning comes from an unverified oral source she believes is reliable.
- Skills/grants: `skill:frontier.observation`, `skill:envoy.negotiation`, `skill:threat_reporting`.
- Paths: present field report, request limited lockdown, inspect entry, seek private conference.
- Private perspectives: respects Ysara but believes she hides behind procedure; distrusts Thomas's bureaucracy.
- Restriction: cannot independently command a formal lockdown or assert unverified report as settled fact.

### Required Scene Entities

```text
evidence:sealed_letter       inspect/present/secure
evidence:seal_record         inspect/compare/secure
object:map_table             inspect/place_document
environment:eternal_lamp     stable/dim/restored
door:side_entry              open/closed/secured; access policy
device:alarm_bell            inspect/raise_alarm_with_policy
zones: throne_dais, evidence_table, side_entry, guard_lane
```

### Scheduled Pressure Windows

| Time | Objective event |
| --- | --- |
| 0-5 min | Pre-meeting duties and ordinary hall state. |
| 5-10 min | Eternal lamp dims; sealed letter becomes available at evidence table. |
| 10-15 min | Letter and seal record present a verified inconsistency. |
| 15-21 min | Side-entry anomaly enters visual/auditory perception. |
| 21-26 min | Regency command requests ceremonial continuity with incomplete information. |
| 26-30 min | Meeting deadline creates settlement/decision pressure. |

Valid outcomes include limited investigation, formal lockdown, procedural delay, temporary alliance, hidden evidence, public disagreement, or unresolved risk.

## Embodiment and Asset Requirements

### Shared Character Requirements

```text
Skeleton3D binding profile
head, left/right hand, and foot anchors
AnimationTree/locomotion: idle, walk, run, turn, stop, backstep
semantic atoms: look_at, talk, listen, point, reach, grip, release,
sit/stand, generic kick/push
IK: head/torso, hands, feet
motion warping and root-motion ownership policy
spatial audio source and TTS/stub path
```

High-value dual-character clips such as handshake, embrace, support, or struggle are P1 assets. They require an `InteractionSession` and do not replace approach, alignment, consent, interruption, or outcome verification.

### Scene Affordance Registry

Every interactive entity must expose:

```yaml
entity_id: chair:dynamic_01
semantic_type: chair
scene_node_path: res://...
state_machine: [upright, tipped, blocked]
affordances: [sit, push, kick, move]
anchors: [sit_anchor, push_anchor, kick_contact_anchor]
physics: {mass, friction, rigid_body, tipping_threshold}
authority_policy: {allowed_actions, force_limits, privacy_scope}
perception_tags: [furniture, movable, obstruction]
```

## Embodied Action and Interaction Contracts

### EmbodiedActionController

The local Godot controller must realize an already authorized semantic request through:

```text
AcquireTarget -> PlanApproach -> Navigate -> Align -> Prepare
-> ExecuteContact -> Verify -> Recover
                         |          |
                         +-> Abort -+
```

It runs at local frame/physics cadence. LLMs and VLAs choose goals, strategy, interpretation, or replan direction; they do not send high-frequency bone transforms or direct rigid-body impulses.

### InteractionSession

Two-character interactions require a session with participants, action semantic, acceptance/refusal, relative stance slots, timing, realization profile, interruption policy, authority request, observation, and settlement. It is required for handoff, handshake, embrace, support, and other coordinated interactions.

### VLA and Scene Truth

Known Godot scene entities provide exact position, collider, mass, state, anchor, and navigation truth. VLA is an advisory slow path used to recognize unknown assets, visual state, or affordance candidates; VLA results carry confidence and must be fused to a scene entity before action planning. VLA never writes world truth or controls physics directly.

## 30-Minute Acceptance Matrix

Each world run must prove:

1. All three actors independently produce perception, interpretation, planning, and at least one action attempt.
2. At least two content-bearing dialogue exchanges are received and written to the listener's private memory path.
3. At least one actor-private relationship projection changes with evidence references and no private leakage.
4. At least one ability affordance is available and at least one is blocked by a typed condition.
5. At least one character-object or character-environment action settles through authority.
6. At least one path, contact, target movement, privacy, permission, or refusal failure causes recover/retry/abort behavior.
7. At least one non-scripted narrative branch emerges from actor choices.
8. Final evidence includes screenshots, trace, authority settlements, actor-safe final state, relationship/ability explanations, and replay identifiers.

The run fails if it has authority bypasses, unobserved physical success claims, private data leakage, same-blocker action loops, unrecorded provider failure, or missing replay evidence.

## Delivery Sequence

1. Build scene adapters, entity affordance definitions, zones, and source-art dependency repair.
2. Materialize six dossiers into bootstrap authority/private relationship/ability events.
3. Enable and verify live character model provider with explicit fallback behavior.
4. Implement one closed embodied loop: approach, align, kick/push dynamic chair, observe, settle, and recover.
5. Implement document/cup pickup-handoff with hand IK, attachment, and refusal.
6. Implement InteractionSession and verify handshake before embrace.
7. Integrate VLA advisory fusion only after scene truth and local embodiment are reliable.
8. Run 30-minute world-pack profiles, retain replay artifacts, and compare branches across seeds.

## Verification Commands and Artifacts

Existing baseline profiles remain required:

```powershell
python scripts/verification/harness.py --profile phase0
python scripts/verification/harness.py --profile mainline-unified-runtime
```

Planned profiles for this design:

```text
autonomous-world-pack-contract
embodied-action-controller
scene-affordance-registry
interaction-session-runtime
neon-night-apartment-30m
candlelit-throne-hall-30m
autonomous-world-pack-all
```

All generated reports, trace files, screenshots, replay seeds, provider/degrade records, and failure digests must live under `.harness/verification/` and be retained by run ID.

## Acceptance Definition

The design is ready to move into implementation planning only when the user approves this document. Runtime completion is claimed only after the planned profiles and broad repository verification provide fresh evidence.
