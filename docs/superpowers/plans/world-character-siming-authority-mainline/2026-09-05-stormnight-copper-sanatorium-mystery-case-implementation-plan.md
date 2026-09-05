# Stormnight Copper Sanatorium Mystery Case Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver one complete, original, fact-backed 3D smart-agent mystery case that exercises the existing Character, P5, ActionWindow, Inventory and Godot seams without adding a second runtime.

**Architecture:** Add a strict package-local case-content/admission layer and an additive P5 case adapter. Reuse existing QuestEvidenceAuthority, SocialFactAuthority, CharacterAgentRuntime, ActionGraph/ActionWindow, Inventory custody, event replay and Godot mirror paths. Case content fills typed slots; existing owners continue to decide all canonical facts.

**Tech Stack:** Python/Pydantic, existing GameplayPatchManifest v3/platform 2.0 adapter, GameplayEventStore, P5 authorities, Character Agent runtime, pytest, Harness, Godot 4.6.3 GDScript.

**Spec:** `docs/superpowers/specs/world-character-siming-authority-mainline/2026-09-05-stormnight-copper-sanatorium-mystery-case-design.md`

## Global Constraints

- Stay on `main`; preserve all frozen packages, existing narrow rows, and user changes.
- Do not add a second runtime, store, bus, clock, scheduler, generic writer, router, coordinator or settlement authority.
- Use existing `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()` for every durable case fact.
- Character/LLM/Godot/Siming output is intent or proposal, never canonical truth.
- Keep project-visible case facts separate from actor-private knowledge and impressions.
- Do not vendor or copy source-story text, names, dialogue, images or modern adaptations.
- August INF A-D remains `not complete`; this case is a separate product vertical.

---

### Task 1: Case content models and provenance

**Files:**
- Create: `backend/app/gameplay/p5/scripted_mystery_content.py`
- Create: `backend/tests/test_scripted_mystery_content.py`
- Create: `docs/superpowers/specs/world-character-siming-authority-mainline/2026-09-05-stormnight-copper-sanatorium-mystery-case-provenance.md`

**Interfaces:**
- Produces `ScriptedMysteryCaseContent`, `CaseTruthFact`, `PrivateKnowledgeSet`, `ClueDefinition`, `StatementDefinition`, `CasePhaseDefinition`, `CaseOutcomeDefinition`, and `CaseContentAdmissionResult`.
- Consumes existing `StrictGameplayModel`, package refs and registered predicate/action-graph refs.

- [ ] **Step 1: Write the failing tests** for strict extra-field rejection, namespace+revision refs, canonical author order, duplicate refs, private-truth leakage, arbitrary expression rejection, missing policy rejection, and source provenance metadata.
- [ ] **Step 2: Run `pytest backend/tests/test_scripted_mystery_content.py -q`** and confirm failure because the models and admission function do not exist.
- [ ] **Step 3: Implement immutable models** with `ConfigDict(extra="forbid", frozen=True)`, tuple arrays, typed truth kinds, registered predicate refs, and `CaseContentAdmissionResult.admit(content, *, admitted_action_graph_refs, admitted_predicate_refs)`.
- [ ] **Step 4: Add the original Stormnight content fixture** with four actors, four rooms, 10–15 clues, four private knowledge sets, three phases and four outcomes. Do not include source prose or original names.
- [ ] **Step 5: Run focused tests and `python -m compileall -q backend`**; both must pass.
- [ ] **Step 6: Commit** the content/provenance slice with a Lore-format message.

### Task 2: Immutable package and descriptor admission

**Files:**
- Create: `backend/app/gameplay/p5/scripted_mystery_case_package.py`
- Create: `backend/tests/test_scripted_mystery_case_package.py`
- Create: `docs/superpowers/specs/world-character-siming-authority-mainline/2026-09-05-stormnight-copper-sanatorium-package-freeze-record.md`
- Modify: existing v3/2.0 package adapter and governed catalog modules only for additive registration.

**Interfaces:**
- Produces `StormnightCasePackage`, `CasePackageBinding`, and `load_stormnight_case_package()`.
- Consumes `ScriptedMysteryCaseContent`, the existing manifest adapter, immutable candidate/active binding and exact-one descriptor resolution.

- [ ] **Step 1: Write RED tests** for v3/2.0 pairing, declaration/content digest derivation, untrusted digest claims, exact-one binding, unknown/multiple binding, revision pin retention and frozen-content immutability.
- [ ] **Step 2: Run the package test file** and verify it fails before registration.
- [ ] **Step 3: Register one immutable Stormnight package revision** through the existing adapter; derive canonical bytes and digests from normalized content and reject differing caller claims.
- [ ] **Step 4: Register one exact P5 case descriptor/catalog row** with fixed owner, case stream grammar, event family set, project/private scopes, replay reader and policy pins; do not add a generic case descriptor.
- [ ] **Step 5: Run package, patch-runtime and catalog regression suites** and verify frozen v1/v2/v3 packages remain unchanged.
- [ ] **Step 6: Commit** the admission slice separately from runtime behavior.

### Task 3: Case truth seed and projection

**Files:**
- Create: `backend/app/gameplay/p5/scripted_mystery_case_runtime.py`
- Create: `backend/tests/test_scripted_mystery_case_runtime.py`
- Modify: existing P5 event-schema registration only for additive case events.

**Interfaces:**
- Produces `CaseOpenIntent`, `CaseProjection`, `CasePhaseResult`, `CaseOutcomeResult`, `ScriptedMysteryCaseAuthority.open_case()`, `advance_phase()`, and `resolve_outcome()`.
- Consumes `StormnightCasePackage`, `GameplayCommandEnvelope`, existing registry/store/replay helpers.

- [ ] **Step 1: Write RED tests** for case opening, phase order, truth-fact provenance, project privacy, duplicate/changed duplicate, stale revision and zero-write append behavior.
- [ ] **Step 2: Implement only four additive case events**: `case_opened@1`, `statement_recorded@1`, `accusation_submitted@1`, and `case_outcome_resolved@1`, using the existing envelope, settlement plan and append batch.
- [ ] **Step 3: Implement `CaseProjector`** to reconstruct phase, public truth references, committed clue refs, accusation status and terminal outcome; reject forged package/policy/source pins during replay.
- [ ] **Step 4: Add full/checkpoint-tail replay tests** and prove the case runtime does not write Body, Inventory, Economy, Organization or Social stores directly.
- [ ] **Step 5: Run focused case-runtime and P5 replay suites**, then commit.

### Task 4: Statements, private knowledge and evidence graph

**Files:**
- Create: `backend/app/gameplay/p5/scripted_mystery_evidence.py`
- Create: `backend/tests/test_scripted_mystery_evidence.py`
- Modify: `backend/app/gameplay/p5/quest_evidence.py` and `backend/app/gameplay/p5/social_knowledge.py` only through additive adapters.

**Interfaces:**
- Produces `CaseTurnContext`, `StatementIntent`, `EvidenceDiscoveryIntent`, `AccusationIntent`, `CaseEvidenceProjection`, and `ScriptedMysteryEvidenceAdapter`.
- Consumes existing QuestEvidenceAuthority, SocialFactAuthority, Inventory custody API and `CaseProjection`.

- [ ] **Step 1: Write RED tests** for public/private statement visibility, actor knowledge filtering, clue predicate evaluation, collection custody, evidence provenance, contradictory statements and accusation threshold.
- [ ] **Step 2: Implement `build_turn_context(case_projection, recipient_ref)`** so each actor receives only public facts plus its admitted private knowledge set.
- [ ] **Step 3: Implement statement/evidence/accusation adapters** that call existing owners; no adapter may directly append another owner’s event.
- [ ] **Step 4: Add tampering, private leakage, stale-source, duplicate and changed-duplicate tests** with event-store length assertions proving zero-write rejection.
- [ ] **Step 5: Run P5 quest/social, Inventory custody and new evidence suites**, then commit.

### Task 5: Character Agent case-turn integration

**Files:**
- Create: `backend/app/services/scripted_mystery_agent_turns.py`
- Create: `backend/tests/test_scripted_mystery_agent_turns.py`
- Modify: `backend/app/services/character_agent_runtime.py`, `backend/app/services/character_agent_l3.py`, and `backend/app/services/character_agent_l4_adapter.py` only for additive case-turn interfaces.

**Interfaces:**
- Produces `CaseAgentContext`, `CaseTurnProposal`, `CaseTurnDecision`, and `ScriptedMysteryAgentTurnService.propose_turn()`.
- Consumes `CaseTurnContext`, existing Character profile/memory/goal layers and returns only typed dialogue/action proposals.

- [ ] **Step 1: Write RED tests** proving an agent can propose investigate/question/hide/pursue actions from its filtered context, cannot see another actor’s private clue, and cannot commit directly.
- [ ] **Step 2: Implement context conversion** from committed case projection, actor-private Social knowledge and current ActionWindow snapshot.
- [ ] **Step 3: Implement deterministic proposal normalization** with stable turn id, source revision vector, policy pins and owner route; reject free-form event vectors and truth assertions.
- [ ] **Step 4: Add two agent policies**: investigator evidence-seeking and guardian concealment/pursuit, using the same service and typed slots.
- [ ] **Step 5: Run Character Agent, knowledge, action-request and new turn suites**, then commit.

### Task 6: ActionWindow/P5 case loop integration

**Files:**
- Create: `backend/tests/test_stormnight_action_loop.py`
- Modify: `backend/app/gameplay/p5/investigation_conflict.py` only through additive case calls.

**Interfaces:**
- Consumes `CaseTurnProposal`, `ActionGraphDefinition`, `ActionWindowIntent`, and `SpatialSnapshotRef`.
- Produces committed movement/visibility/sound/control/capture/escape facts through the existing P5 facade and `CaseOutcomeResult` through the case authority.

- [ ] **Step 1: Write RED tests** for inspect, collect, hide, pursuit, control, escape, capture and terminal outcome across all three phases.
- [ ] **Step 2: Bind the Stormnight graph to existing registered primitives**; do not add arbitrary graph nodes or a second controller.
- [ ] **Step 3: Route every action proposal through source-fenced `ActionWindow` validation and the existing P5 conflict facade.**
- [ ] **Step 4: Connect successful clue collection to the Inventory evidence-custody adapter and successful accusation to Quest/Social evidence adapters.**
- [ ] **Step 5: Add four deterministic outcome fixtures** and run action/P5/Inventory/Quest/Social regression suites before committing.

### Task 7: Godot case scene, UI and voice

**Files:**
- Create: `scenes/phase0/StormnightCopperSanatorium.tscn`
- Create: `scripts/verification/StormnightCopperSanatoriumProbe.gd`
- Create: `scripts/verification/StormnightCopperSanatoriumView.gd`
- Create: `backend/tests/test_stormnight_godot_contract_static.py`
- Create: `.harness/profiles/stormnight-copper-sanatorium.json`
- Create: `scripts/verification/verify_stormnight_copper_sanatorium.py`

**Interfaces:**
- Consumes committed `CaseProjection` mirror data and filtered actor view.
- Produces presentation state, voice-template selection, speculative rollback and verification artifacts only.

- [ ] **Step 1: Write RED static tests** for four rooms, two hide spots, two occluders, two sound zones, locked door, evidence table, committed-only projection and absence of `append_batch`/direct world writes.
- [ ] **Step 2: Build the scene entirely from Godot PrimitiveMesh, built-in materials, labels and state overlays.**
- [ ] **Step 3: Implement read-only panels** for phase, clues, private knowledge, pursuit, accusation and terminal outcome; rejection clears speculative state and restores the last committed snapshot.
- [ ] **Step 4: Add revisioned voice templates** for preparing, clue-found, statement-conflict, detected, captured, escaped, solved and returned states.
- [ ] **Step 5: Run Godot 4.6.3 headless and desktop probes**, write Harness artifacts, and commit.

### Task 8: Full case verification and template extraction

**Files:**
- Create: `backend/tests/test_stormnight_copper_sanatorium_full_replay.py`
- Create: `backend/tests/test_stormnight_case_template_genericity.py`
- Modify: mainline spec/plan README, P5 README, completion audit and continuation checkpoint.

**Interfaces:**
- Consumes all prior case/package/agent/action/presentation adapters.
- Produces the `stormnight-copper-sanatorium` Harness report, completion audit and a second content-only package variant loaded by the same case adapter.

- [x] **Step 1: Write RED replay tests** covering case lifecycle, owner handoff, one action window, one statement, one evidence collection, one accusation, all four declared outcomes and tampered checkpoint rejection.
- [ ] **Step 2: Add tamper tests** for package bytes, declaration/content digest, role knowledge, clue visibility, spatial snapshot, statement payload, event payload and checkpoint state.
- [ ] **Step 3: Add a second content-only variant** with different room names, cast names, clue text and motive while retaining the same typed slots and adapters; prove no owner/runtime code changes are required.
- [ ] **Step 4: Run focused suites, `python -m pytest -q`, `python -m compileall -q backend`, `git diff --check`, action/P5/Character/Godot/docs Harness profiles and the full Harness.
- [ ] **Step 5: Update the completion audit** to distinguish `complete reference game`, `reusable case template`, and future Creator Skill/Siming Director work. Keep August INF A-D `not complete`.
- [ ] **Step 6: Commit and push each verified slice directly to `main`** using Lore-format messages.

## Rollout gates

1. Content/admission before case truth runtime.
2. Case truth/replay before statements/evidence.
3. Statements/evidence before Character Agent turns.
4. Agent turns before action-loop integration.
5. Action loop before Godot case delivery.
6. Godot delivery before full-case/template closure.

Any failed focused test, Harness, privacy check, replay check or Godot probe
blocks the next gate. Existing narrow rows remain read-only compatible.

## Completion definition

The plan is complete only when all four outcomes are playable and reproducible,
all durable facts are owner-bound, every rejection is zero-write, full/tail
replay is equal, Godot headless and desktop probes pass, and a second content
variant loads through the same typed case adapter. This does not complete the
general Creator Skill, Siming Director, full combat or August INF A-D.
