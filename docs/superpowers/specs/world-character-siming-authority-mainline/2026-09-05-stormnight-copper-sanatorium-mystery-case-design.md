# Stormnight Copper Sanatorium: Smart-Agent Mystery Case Design

Status: `approved case direction; design ready for implementation planning`

## Purpose

Build the first complete, fact-backed 3D scripted-mystery case on the existing
world-character-Siming runtime. The case is an original adaptation inspired by
the public-domain locked-room structure of *The Adventure of the Speckled
Band* (Project Gutenberg eBook #1661). No original names, text, artwork,
dialogue or modern adaptation material is copied into the repository. The
source is retained only as provenance for structural inspiration; distribution
jurisdictions still require independent legal review.

The case must prove that real Character Agents can perceive, remember,
question, deceive, investigate and act in a 3D scene while every durable fact
is written by its existing owner and can be replayed exactly.

## Case scope

Working title: `Stormnight Copper Sanatorium`.

- one player investigator and four Character Agents;
- one isolated sanatorium with four rooms, two hide spots, two occluders,
  two sound zones, one locked door and one evidence table;
- three explicit phases: `arrival`, `investigation`, `storm_night`;
- 10–15 authored clues, 4 private knowledge sets and 4 terminal outcomes:
  `case_solved`, `false_accusation`, `culprit_escaped`, `investigator_captured`;
- movement, inspect, collect, question, reveal, hide, pursuit, control and
  escape actions;
- no automatic persistent character death. A case-death result remains an
  encounter fact and requires the existing explicit world-death confirmation
  boundary for persistence.

The cast is original and package-local: an investigator, a threatened heir,
an estate guardian, a physician and a night attendant. Their names and
dialogue are content, not runtime constants.

## Package and truth model

The case uses the existing `GameplayPatchManifest v3` with
`platform_schema_version="2.0"`; no manifest schema is added. A strict,
immutable `ScriptedMysteryCaseContent` model contains:

```text
case_ref / case_revision / package_ref / package_revision
location_ref / actor_refs / role_assignments
truth_facts / private_knowledge_sets / clue_definitions
statement_definitions / objective_definitions / phase_definitions
action_graph_refs / outcome_definitions / presentation_refs / policy_refs
```

All refs include namespace and revision. Arrays are author-ordered canonical
input; duplicates, undeclared refs, actor-private truth leakage, arbitrary
expressions and missing policy are rejected before append. Truth facts are
typed as scene, identity, causal, possession, timeline or relationship facts.
Clue visibility uses registered predicates only. The author cannot select an
owner, stream, event family, receipt or arbitrary consequence fragment.

## Owner and event boundary

`InvestigationConflictAuthority` remains the P5 conflict owner and is extended
only additively. `QuestEvidenceAuthority` owns evidence registration and
objective transitions. `SocialFactAuthority` owns shared statements and
actor-private knowledge. `CharacterAgentRuntime` owns agent cognition and
memory proposals. `ActionGraphDefinition`, `ActionWindowIntent` and the
existing `EmbodiedActionController` own action admission and local playback.
Inventory owns evidence custody when a clue is physically collected.

The case adapter may add only these P5 case events:

```text
gameplay.p5.mystery.case_opened@1
gameplay.p5.mystery.statement_recorded@1
gameplay.p5.mystery.accusation_submitted@1
gameplay.p5.mystery.case_outcome_resolved@1
```

They use the existing envelope → settlement plan → `append_batch()` spine.
Case state is project-visible; private knowledge and private impressions stay
actor-private. No case adapter writes body, inventory, account, ownership,
production, population or government facts directly.

## Agent turn contract

Every agent turn follows:

```text
committed public case projection
 + actor-private knowledge projection
 + current embodied/spatial snapshot
→ CharacterAgent proposal (dialogue or action intent)
→ P5 / Quest / Social / Action owner validation
→ committed event(s)
→ filtered projection
→ actor memory update
```

An LLM or heuristic may propose wording, belief and intent, but cannot assert
that a clue is true, a statement is believed, a target is captured or the case
is solved. Those facts come from committed owner events.

## Case outcomes and privacy

The player can inspect only project-visible facts and their own private facts.
Each AI receives only the knowledge set admitted for its actor. Statements
record whether they are public, private, truthful-by-world-fact, misleading or
withheld; credibility is a Social/P5 projection, never a client flag.

An accusation is valid only when its evidence refs and target actor are
committed, visible to the investigator and satisfy the package predicate. A
failed accusation is a terminal case outcome, not a rewrite of world truth.
Capture/escape uses the existing action-window conflict surface. World death
remains an explicit, separate confirmation.

## Presentation and creator seam

Godot uses PrimitiveMesh, built-in materials, labels and state overlays. It
renders the committed case projection, current phase, clue ledger, private
knowledge panel, pursuit status and terminal result. Rejected intents clear
speculative state. Voice templates are revisioned package content and never
create truth.

The case package is also the first creator-template source. A later Creator
Skill may fill its typed slots, but this case does not implement arbitrary code
execution, automatic publishing or Siming rule mutation. Siming may later
select an admitted phase/variant through a proposal; it cannot alter frozen
truth facts.

## Acceptance gates

The case is complete only when:

1. the immutable package, digest, descriptor and exact-one binding validate;
2. all four agents run turns from their filtered public/private context;
3. investigation, statement, evidence custody, accusation and action windows
   produce committed owner events;
4. all four outcomes are reproducible and privacy-correct;
5. zero-write, stale, tampered, duplicate and changed-duplicate paths reject;
6. full and checkpoint-tail replay produce identical case, knowledge, evidence,
   action and outcome projections;
7. Godot headless and desktop probes show committed projection and rejection
   rollback;
8. the extracted template can load a second content variant through the same
   adapter without adding an owner or runtime.

This case is a complete reference game, not a claim of a complete social-
deduction platform, combat engine or arbitrary one-command game generator.
August INF A-D remains `not complete`.

## Source provenance

- Structural inspiration: [Project Gutenberg eBook #1661](https://www.gutenberg.org/ebooks/1661)
- Original publication identified by the source as 1892.
- Repository implementation uses new names, new dialogue, new art-free scene
  content and new typed facts; the source text is not vendored.
