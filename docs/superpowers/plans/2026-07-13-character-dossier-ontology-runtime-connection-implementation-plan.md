# Character Dossier Ontology Runtime Connection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `CharacterDossier` wrapper and runtime projection path so
authored dossier truth can be edited, filtered, and fed into the existing
mind-frame pipeline without overwriting runtime state.

**Architecture:** Keep the current `CharacterProfile` as the long-term
psychological/behavior baseline nested inside a new dossier model. Add focused
dossier models, visibility filtering, projection summaries, and shadow
`CharacterMindFrame` cards. Relationship graph, ability graph, and body
runtime production systems remain follow-up specs; this plan creates the
contracts and safe initialization surfaces.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, existing
`backend/app/character_agent/profile` and `backend/app/character_agent/mind`
patterns. No new dependencies.

---

## Scope Boundary

This plan implements the design in:

- `docs/superpowers/specs/2026-07-13-character-dossier-ontology-runtime-connection-design.md`

Included:

- `CharacterDossier` schema wrapper around existing `CharacterProfile`.
- Dossier layer metadata and layer-level hot reload invalidation contract.
- Full multi-identity profile model.
- Static `EmbodimentProfile` model and explicit separation from future
  `BodyRuntimeState`.
- `AuthorityProfile`, `PrivateTruthProfile`, `RelationshipSeedProfile`, and
  `CapabilitySeedProfile` contracts.
- Layer-level visibility policy plus field-level private-truth projection
  limits.
- Dossier loader compatibility for legacy profile YAML and new dossier YAML.
- Shadow dossier projection summaries for `CharacterMindFrame`.
- Documentation/status updates and verification.

Excluded:

- Full relationship graph storage and graph algorithms.
- Full ability graph storage and graph algorithms.
- Full `BodyRuntimeState` physics/body simulation.
- Full `CharacterSkillSystem` implementation.
- Behavior-changing L2/L3/L4 prompt or scoring changes.
- Authoring UI/editor tooling.
- Runtime hot reload service or file watcher.

---

## File Structure

- `backend/app/character_agent/profile/dossier_models.py`
  - New Pydantic models for `CharacterDossier`, dossier metadata, visibility,
    identity, embodiment, authority, private truth, relationship seeds, and
    capability seeds.
- `backend/app/character_agent/profile/dossier_loader.py`
  - Loader that accepts both wrapped dossier YAML and legacy profile YAML.
- `backend/app/character_agent/profile/dossier_projection.py`
  - Visibility-filtered projection builder for dossier summaries.
- `backend/app/character_agent/profile/dossier_seed_projection.py`
  - Candidate bundle helpers for relationship seeds and capability seeds.
- `backend/app/character_agent/profile/dossier_hot_reload.py`
  - Layer replacement and invalidation contract helper.
- `backend/app/character_agent/profile/__init__.py`
  - Export dossier models, loader, and projection helpers.
- `backend/app/character_agent/mind/view_builder.py`
  - Add L2/L3/L4 consumption of filtered dossier projection cards.
- `backend/app/character_agent/mind/projectors.py`
  - Add dossier projection cards in enduring truth and affordance-friendly
    summaries.
- `backend/app/character_agent/mind/frame_builder.py`
  - Accept optional `dossier_projection` input and place cards without changing
    existing behavior.
- `backend/app/character_agent/models/mind_frame.py`
  - Register new factor types such as `identity_context`,
    `embodiment_context`, `authority_context`, `private_truth_context`, and
    `dossier_hot_reload`.
- `backend/tests/test_character_dossier_models.py`
  - Schema tests for dossier layers and visibility.
- `backend/tests/test_character_dossier_loader.py`
  - Compatibility and wrapped YAML loader tests.
- `backend/tests/test_character_dossier_projection.py`
  - Visibility filtering and projection tests.
- `backend/tests/test_character_mind_frame_builder.py`
  - Shadow mind-frame integration tests.
- `backend/tests/test_character_mind_projectors.py`
  - Projector card tests.
- `docs/架构/运行时/模块/角色智能体.md`
  - Add dossier/runtime boundary summary.
- `docs/character/character-mind-core-status.md`
  - Update implementation status after code lands.

---

## Phase 1: Dossier Schema Foundation

### Task 1: Add CharacterDossier Models

**Files:**
- Create: `backend/app/character_agent/profile/dossier_models.py`
- Modify: `backend/app/character_agent/profile/__init__.py`
- Create: `backend/tests/test_character_dossier_models.py`

- [x] **Step 1: Write failing schema tests**

Create `backend/tests/test_character_dossier_models.py` with tests covering:

```python
import pytest
from pydantic import ValidationError

from app.character_agent.profile import CharacterDossier, CharacterProfile


def _minimal_character_profile_payload() -> dict[str, object]:
    return {
        "identity_core": {
            "character_id": "char_test",
            "canonical_name": "Test Character",
            "aliases": ["Tester"],
            "occupation_role": "archive attendant",
        },
        "origin_seed": {
            "homeland": "test quarter",
            "formative_context": "trained in archives",
            "current_scene_function": "test anchor",
        },
        "life_memory_backbone": {
            "defining_memories": ["kept a record safe"],
            "unresolved_knots": ["fears procedural failure"],
        },
        "virtue_value_layer": {
            "value_priorities": ["care", "order"],
            "red_lines": ["casually expose private records"],
            "forbidden_behaviors": ["fabricate authority"],
        },
        "trait_vector_layer": {
            "courage": 0.6,
            "scheming": 0.2,
            "empathy": 0.8,
            "rationality": 0.7,
            "sociability": 0.5,
        },
        "capability_constraint_layer": {
            "skills": ["mediation"],
            "knowledge_domains": ["archive routine"],
            "physical_constraints": ["low sprint stamina"],
            "psychological_constraints": ["avoids escalation"],
            "social_constraints": ["cannot authorize sealed access alone"],
        },
        "style_expression_bias_layer": {
            "speech_style": "measured",
            "silence_pattern": "pauses before sensitive answers",
            "gesture_bias": "contained",
            "posture_bias": "upright",
        },
        "conversation_personality_layer": {
            "social_openness": 0.5,
            "privacy_sensitivity": 0.7,
            "talk_initiative": 0.4,
            "deception_control": 0.9,
            "trust_threshold_for_private_talk": 0.7,
        },
        "need_hierarchy_layer": {
            "base_weights": {
                "physiological": 0.2,
                "safety": 0.7,
                "belonging": 0.8,
                "esteem": 0.5,
                "self_actualization": 0.4,
            },
            "deprivation_sensitivity": {
                "physiological": 0.3,
                "safety": 0.8,
                "belonging": 0.8,
                "esteem": 0.5,
                "self_actualization": 0.4,
            },
            "satisfaction_sensitivity": {
                "physiological": 0.3,
                "safety": 0.7,
                "belonging": 0.8,
                "esteem": 0.6,
                "self_actualization": 0.5,
            },
            "dominant_drives": ["preserve trust"],
        },
        "temperament_response_layer": {
            "baseline_temperament": {
                "caution": 0.7,
                "dominance": 0.3,
                "attachment": 0.7,
                "emotional_reactivity": 0.4,
                "recovery_speed": 0.6,
                "impulse_control": 0.8,
            },
            "conflict_style": {
                "confrontation_tendency": 0.2,
                "avoidance_tendency": 0.4,
                "mediation_tendency": 0.8,
                "escalation_threshold": 0.7,
            },
            "defense_patterns": {
                "under_pressure": ["procedural control"],
                "under_shame": ["withdrawal"],
                "under_threat": ["vigilance"],
                "under_loss": ["private grief"],
            },
            "trust_dynamics": {
                "initial_trust_bias": 0.5,
                "betrayal_memory_weight": 0.7,
                "forgiveness_threshold": 0.6,
                "loyalty_lock_in": 0.8,
            },
            "expression_bias": {
                "outward_warmth": 0.6,
                "emotional_transparency": 0.5,
                "facial_control": 0.7,
                "verbal_indirection": 0.6,
            },
        },
    }


def _minimal_dossier_payload() -> dict[str, object]:
    return {
        "dossier_id": "dossier:char_test",
        "actor_id": "char_test",
        "schema_version": "character_dossier.v1",
        "identity_profile": {
            "actor_id": "char_test",
            "canonical_name": "Test Character",
            "aliases": ["Tester"],
            "demographic_identity": {
                "age_band": "young_adult",
                "gender_identity": "female",
            },
            "role_identities": {
                "occupational_role": "archive_attendant",
                "scene_role": "test_anchor",
                "authority_role": "archive_procedure_keeper",
            },
        },
        "embodiment_profile": {
            "body_schema": {
                "body_type": "slight",
                "height_band": "average",
                "dominant_hand": "right",
            },
            "sensory_baseline": {"vision": "normal", "hearing": "attentive"},
            "motor_baseline": {
                "sprint_capacity": "low",
                "fine_motor_control": "high",
                "load_bearing": "low",
            },
            "voice_baseline": {"volume": "low", "tone": "soft"},
        },
        "authority_profile": {
            "responsibilities": ["maintain_archive_order"],
            "allowed_actions": ["explain_public_procedure"],
            "forbidden_actions": ["grant_sealed_access_alone"],
            "escalation_targets": ["senior_archivist"],
        },
        "private_truth_profile": {
            "secrets": [
                {
                    "truth_id": "secret:char_test:omission_fear",
                    "content": "fears one omission could damage trust",
                    "known_by": ["author", "char_test"],
                    "unknown_to": ["public"],
                    "allowed_projection": {
                        "l2": "summarized",
                        "l3": "constraint_only",
                        "player": "hidden",
                    },
                }
            ]
        },
        "relationship_seed_profile": {
            "relationships": [
                {
                    "target_actor_id": "char_b",
                    "relation_tags": ["trusted_colleague"],
                    "initial_trust": 0.68,
                    "initial_affinity": 0.56,
                    "initial_obligation": 0.34,
                    "initial_tension": 0.18,
                    "evidence_seeds": [
                        {
                            "event_id": "rel_seed:char_test:char_b:kept_confidence",
                            "summary": "char_b kept a sensitive archive matter private",
                            "effect": {"trust": 0.18},
                        }
                    ],
                }
            ]
        },
        "capability_seed_profile": {
            "skill_seeds": [
                {
                    "skill_id": "social.mediation",
                    "source": "authored",
                    "rank": "trained",
                    "proficiency": 0.74,
                    "confidence": 0.81,
                    "supports": [{"action_family": "social_deescalation"}],
                    "requires": [{"condition": "has_speaking_turn"}],
                    "blocked_by": ["public_humiliation"],
                }
            ],
            "knowledge_domains": ["archive_routine"],
            "constraints": {
                "physical": ["low_sprint_stamina"],
                "social": ["cannot_authorize_sealed_access_alone"],
            },
        },
        "character_profile": _minimal_character_profile_payload(),
    }


def test_character_dossier_wraps_existing_character_profile() -> None:
    dossier = CharacterDossier.model_validate(_minimal_dossier_payload())

    assert dossier.actor_id == "char_test"
    assert isinstance(dossier.character_profile, CharacterProfile)
    assert dossier.character_profile.identity_core.character_id == "char_test"
    assert dossier.identity_profile.role_identities.occupational_role == "archive_attendant"


def test_character_dossier_rejects_actor_mismatch() -> None:
    payload = _minimal_dossier_payload()
    payload["character_profile"]["identity_core"]["character_id"] = "other_actor"

    with pytest.raises(ValidationError, match="actor_id"):
        CharacterDossier.model_validate(payload)


def test_character_dossier_rejects_invalid_scalar_skill_seed() -> None:
    payload = _minimal_dossier_payload()
    payload["capability_seed_profile"]["skill_seeds"][0]["proficiency"] = 1.5

    with pytest.raises(ValidationError):
        CharacterDossier.model_validate(payload)


def test_private_truth_projection_policy_rejects_unknown_value() -> None:
    payload = _minimal_dossier_payload()
    payload["private_truth_profile"]["secrets"][0]["allowed_projection"]["l2"] = "omniscient"

    with pytest.raises(ValidationError):
        CharacterDossier.model_validate(payload)
```

- [x] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest backend/tests/test_character_dossier_models.py -v
```

Expected: FAIL with import error for `CharacterDossier`.

- [x] **Step 3: Implement dossier models**

Create `backend/app/character_agent/profile/dossier_models.py` with focused
Pydantic models. Use `extra="forbid"` and scalar bounds on proficiency and
confidence.

Required model names:

- `DossierVisibilityPolicy`
- `DossierLayerMetadata`
- `DossierMetadata`
- `DemographicIdentity`
- `RoleIdentities`
- `AffiliationIdentities`
- `SocialIdentities`
- `IdentityProfile`
- `EmbodimentProfile`
- `AuthorityProfile`
- `PrivateTruthProfile`
- `RelationshipSeedProfile`
- `CapabilitySeedProfile`
- `CharacterDossier`

Also add compatibility alias fields for current `CharacterProfile` layers:

- `origin_profile`
- `life_history_profile`
- `value_profile`
- `personality_profile`
- `need_profile`
- `expression_profile`

These may be lightweight optional dictionaries or typed compatibility models in
the first pass. Their purpose is to reserve the dossier layer names and let the
projection builder map current `character_profile.origin_seed`,
`life_memory_backbone`, `virtue_value_layer`, `personality_layer`,
`need_hierarchy_layer`, and `style_expression_bias_layer` into dossier-shaped
summaries without moving all profile data immediately.

Implementation requirements:

- `CharacterDossier.character_profile` type is `CharacterProfile`.
- `CharacterDossier.actor_id` must equal
  `character_profile.identity_core.character_id`.
- Default optional dossier layers to empty-but-valid models where practical.
- `allowed_projection` values must be restricted to `visible`, `summarized`,
  `partial`, `belief_only`, `constraint_only`, `action_relevant_only`, and
  `hidden`.
- Optional compatibility layer fields must not make legacy profile YAML fail.
- `origin_profile`, `life_history_profile`, `value_profile`,
  `personality_profile`, `need_profile`, and `expression_profile` should be
  absent from required YAML until the migration phase.

- [x] **Step 4: Export public models**

Modify `backend/app/character_agent/profile/__init__.py` to export:

```python
from app.character_agent.profile.dossier_models import CharacterDossier
```

Also export any helper models needed by tests or downstream code.

- [x] **Step 5: Run schema tests**

Run:

```bash
python -m pytest backend/tests/test_character_dossier_models.py -v
```

Expected: PASS.

---

## Phase 2: Dossier Loader Compatibility

### Task 2: Add Dossier Loader For Wrapped And Legacy YAML

**Files:**
- Create: `backend/app/character_agent/profile/dossier_loader.py`
- Modify: `backend/app/character_agent/profile/__init__.py`
- Create: `backend/tests/test_character_dossier_loader.py`

- [x] **Step 1: Write failing loader tests**

Create `backend/tests/test_character_dossier_loader.py` with tests that:

- load a wrapped dossier YAML from a temporary directory
- adapt a legacy profile YAML into a dossier
- reject actor ID mismatch
- preserve the nested `CharacterProfile`

Use `yaml.safe_dump` to write temporary files, following the existing profile
loader test pattern.

- [x] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest backend/tests/test_character_dossier_loader.py -v
```

Expected: FAIL with import error for `CharacterDossierLoader`.

- [x] **Step 3: Implement loader**

Create `CharacterDossierLoader` with:

```python
class CharacterDossierLoader:
    def __init__(self, root: Path | str | None = None) -> None: ...
    def load(self, actor_id: str) -> CharacterDossier: ...
```

Loader behavior:

- If YAML top-level contains `character_dossier`, unwrap it.
- If YAML top-level contains `schema_version: character_dossier.v1`, treat it
  as a dossier payload.
- Otherwise treat YAML as legacy `CharacterProfile` payload and create a
  compatibility dossier with:
  - `dossier_id=f"dossier:{actor_id}"`
  - `schema_version="character_dossier.v1"`
  - `identity_profile` derived from `identity_core`
  - `character_profile` set to the legacy payload
- Reject if resolved dossier actor ID does not equal requested `actor_id`.

- [x] **Step 4: Export loader**

Modify `backend/app/character_agent/profile/__init__.py` to export:

```python
from app.character_agent.profile.dossier_loader import CharacterDossierLoader
```

- [x] **Step 5: Run loader and existing profile tests**

Run:

```bash
python -m pytest backend/tests/test_character_dossier_loader.py backend/tests/test_character_profile_loader.py -v
```

Expected: PASS.

---

## Phase 3: Visibility And Dossier Projection

### Task 3: Add Visibility-Filtered Dossier Projection

**Files:**
- Create: `backend/app/character_agent/profile/dossier_projection.py`
- Modify: `backend/app/character_agent/profile/__init__.py`
- Create: `backend/tests/test_character_dossier_projection.py`

- [x] **Step 1: Write failing projection tests**

Create `backend/tests/test_character_dossier_projection.py` with tests proving:

- `build_dossier_projection(dossier, audience="l2")` includes identity,
  authority, embodiment summary, and self-known private truth summary.
- author-only private truth is hidden from `l2`.
- `audience="l3"` receives private truth as constraints only, not raw content.
- `audience="player"` hides player-hidden secrets.
- projection output contains no `character_profile` raw payload.

- [x] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest backend/tests/test_character_dossier_projection.py -v
```

Expected: FAIL with import error for `build_dossier_projection`.

- [x] **Step 3: Implement projection builder**

Create:

```python
Audience = Literal["author", "self", "player", "l2", "l3", "l4"]

def build_dossier_projection(
    dossier: CharacterDossier,
    *,
    audience: Audience,
) -> dict[str, object]:
    ...
```

Projection shape:

```python
{
    "actor_id": "...",
    "identity": {...},
    "embodiment": {...},
    "authority": {...},
    "private_truth": {...},
    "relationship_seeds": {...},
    "capability_seeds": {...},
    "source_refs": ["dossier:char_a", "dossier_layer:identity_profile:1"],
}
```

Rules:

- Do not include raw `character_profile`.
- For `l2`, include only secrets where `known_by` contains the actor ID or
  `self`; return summaries, not raw author-only content.
- For `l3`, include only `constraint_only` summaries and counts.
- For `l4`, include only action-relevant authority, embodiment, and expression
  hints.
- For `player`, hide secrets whose projection is `hidden`.

- [x] **Step 4: Export projection helper**

Modify `backend/app/character_agent/profile/__init__.py`:

```python
from app.character_agent.profile.dossier_projection import build_dossier_projection
```

- [x] **Step 5: Run projection tests**

Run:

```bash
python -m pytest backend/tests/test_character_dossier_projection.py -v
```

Expected: PASS.

---

## Phase 4: MindFrame Shadow Integration

### Task 4: Add Dossier Projection Cards To CharacterMindFrame

**Files:**
- Modify: `backend/app/character_agent/models/mind_frame.py`
- Modify: `backend/app/character_agent/mind/projectors.py`
- Modify: `backend/app/character_agent/mind/frame_builder.py`
- Modify: `backend/tests/test_character_mind_projectors.py`
- Modify: `backend/tests/test_character_mind_frame_builder.py`

- [x] **Step 1: Write failing mind-frame tests**

Add tests proving:

- `CharacterMindFrameBuilder.build_frame(..., dossier_projection=...)` accepts
  a projection mapping.
- enduring truth contains `identity_context`, `embodiment_context`,
  `authority_context`, and `private_truth_context` cards when supplied.
- affordance layer contains capability seed hints only as a summary, not a full
  ability graph.
- existing calls without `dossier_projection` still pass unchanged.

- [x] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest backend/tests/test_character_mind_projectors.py backend/tests/test_character_mind_frame_builder.py -v
```

Expected: FAIL because factor types or `dossier_projection` parameter do not
exist.

- [x] **Step 3: Register factor types**

Modify `backend/app/character_agent/models/mind_frame.py` factor ownership:

```python
"identity_context": "enduring_truth",
"embodiment_context": "enduring_truth",
"authority_context": "enduring_truth",
"private_truth_context": "enduring_truth",
"dossier_hot_reload": "enduring_truth",
"capability_seed_affordance": "affordance",
"relationship_seed_context": "memory_evidence",
```

- [x] **Step 4: Add DossierProjectionProjector**

Modify `backend/app/character_agent/mind/projectors.py` to add a small
projector class:

```python
class DossierProjectionProjector:
    def project_enduring_truth(self, projection: dict[str, object]) -> list[MentalFactorProjectionCard]:
        ...

    def project_memory_evidence(self, projection: dict[str, object]) -> list[MentalFactorProjectionCard]:
        ...

    def project_affordances(self, projection: dict[str, object]) -> list[MentalFactorProjectionCard]:
        ...
```

Rules:

- Copy nested dictionaries before storing them in cards.
- `private_truth_context` summary must be count/constraint oriented.
- `capability_seed_affordance` must not claim skill evaluation.
- `relationship_seed_context` must state that seeds initialize memory and are
  not live relationship truth.

- [x] **Step 5: Wire builder parameter**

Modify `CharacterMindFrameBuilder.build_frame` to accept:

```python
dossier_projection: dict[str, object] | None = None
```

Add dossier cards to:

- `enduring_truth`
- `memory_evidence`
- `affordances`

Do not alter existing card behavior when the parameter is omitted.

- [x] **Step 6: Run mind-frame tests**

Run:

```bash
python -m pytest backend/tests/test_character_mind_projectors.py backend/tests/test_character_mind_frame_builder.py backend/tests/test_character_mind_frame_models.py -v
```

Expected: PASS.

### Task 4.5: Add Layer View Consumption Of Dossier Cards

**Files:**
- Modify: `backend/app/character_agent/mind/view_builder.py`
- Modify: `backend/app/character_agent/models/mind_frame.py`
- Modify: `backend/tests/test_character_mind_context_views.py`

- [x] **Step 1: Write failing L2/L3/L4 view tests**

Add tests proving:

- `L2InterpretationView` includes a `dossier_context_summary` or equivalent
  payload containing identity, embodiment, authority, and private-truth
  summaries.
- `L3PlanningView` includes dossier-derived hard constraints, authority
  constraints, relationship seed context, and capability seed affordance summary
  only as summaries.
- `L4ExecutionView` includes action-relevant embodiment and authority
  constraints as presentation or execution constraints.
- None of the views includes raw `character_profile` or raw secret content.

- [x] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest backend/tests/test_character_mind_context_views.py -v
```

Expected: FAIL because the view models and builder do not yet expose dossier
summaries.

- [x] **Step 3: Extend view models conservatively**

Modify `backend/app/character_agent/models/mind_frame.py`:

```python
class L2InterpretationView(StrictMindFrameModel):
    ...
    dossier_context_summary: dict[str, object] = Field(default_factory=dict)


class L3PlanningView(StrictMindFrameModel):
    ...
    dossier_planning_summary: dict[str, object] = Field(default_factory=dict)


class L4ExecutionView(StrictMindFrameModel):
    ...
    dossier_execution_constraints: dict[str, object] = Field(default_factory=dict)
```

Do not remove existing fields.

- [x] **Step 4: Populate view summaries from cards**

Modify `LayerContextViewBuilder`:

- L2 pulls from `identity_context`, `embodiment_context`,
  `authority_context`, and `private_truth_context`.
- L3 pulls from `authority_context`, `relationship_seed_context`, and
  `capability_seed_affordance`.
- L4 pulls from `embodiment_context` and `authority_context` only.

Use deep copies and default to `{}` when cards are absent.

- [x] **Step 5: Run view tests**

Run:

```bash
python -m pytest backend/tests/test_character_mind_context_views.py backend/tests/test_character_mind_frame_builder.py -v
```

Expected: PASS.

---

## Phase 5: Seed Initialization Contracts

### Task 5: Add Relationship And Capability Seed Conversion Helpers

**Files:**
- Create: `backend/app/character_agent/profile/dossier_seed_projection.py`
- Modify: `backend/app/character_agent/profile/__init__.py`
- Create: `backend/tests/test_character_dossier_seed_projection.py`

- [x] **Step 1: Write failing seed projection tests**

Create tests proving:

- relationship seed records become social-memory candidate dictionaries with
  evidence refs.
- capability skill seeds become character-skill-state candidate dictionaries.
- `build_dossier_seed_initialization_bundle(dossier)` returns both candidate
  lists plus source refs in one stable envelope.
- conversion helpers do not mutate the dossier.
- generated dictionaries are explicit candidates, not committed runtime state.

- [x] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest backend/tests/test_character_dossier_seed_projection.py -v
```

Expected: FAIL with import errors.

- [x] **Step 3: Implement seed helper module**

Create:

```python
def relationship_seed_candidates(dossier: CharacterDossier) -> list[dict[str, object]]:
    ...

def capability_seed_candidates(dossier: CharacterDossier) -> list[dict[str, object]]:
    ...

def build_dossier_seed_initialization_bundle(dossier: CharacterDossier) -> dict[str, object]:
    ...
```

Relationship candidate fields:

- `candidate_type="relationship_seed"`
- `actor_id`
- `target_actor_id`
- `relation_tags`
- `initial_trust`
- `initial_affinity`
- `initial_obligation`
- `initial_tension`
- `evidence_seeds`
- `source_ref`

Capability candidate fields:

- `candidate_type="capability_seed"`
- `actor_id`
- `skill_id`
- `source`
- `rank`
- `proficiency`
- `confidence`
- `supports`
- `requires`
- `blocked_by`
- `source_ref`

Bundle shape:

```python
{
    "actor_id": "char_a",
    "relationship_seed_candidates": [...],
    "capability_seed_candidates": [...],
    "candidate_only": True,
    "does_not_persist": True,
    "source_refs": ["dossier:char_a"],
}
```

The bundle is the stable handoff to future social-memory initialization and
skill-state initialization. It must not directly write stores.

- [x] **Step 4: Export helpers**

Modify `backend/app/character_agent/profile/__init__.py` to export both helper
functions and `build_dossier_seed_initialization_bundle`.

- [x] **Step 5: Run seed projection tests**

Run:

```bash
python -m pytest backend/tests/test_character_dossier_seed_projection.py -v
```

Expected: PASS.

---

## Phase 6: Layer Hot Reload Contract

### Task 6: Add Layer Hot Reload Invalidation Contract

**Files:**
- Modify: `backend/app/character_agent/profile/dossier_models.py`
- Create: `backend/app/character_agent/profile/dossier_hot_reload.py`
- Create: `backend/tests/test_character_dossier_hot_reload.py`

- [x] **Step 1: Write failing hot reload tests**

Create tests proving:

- replacing `embodiment_profile` returns invalidations for
  `embodiment_projection`, `physical_feasibility_projection`, and
  `skill_affordance_projection`.
- replacing `identity_profile` invalidates `identity_projection` and
  `effective_profile_projection`.
- hot reload result contains `does_not_mutate` entries for runtime stores.
- helper returns a new dossier instance and does not mutate the original.

- [x] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest backend/tests/test_character_dossier_hot_reload.py -v
```

Expected: FAIL with import error for `replace_dossier_layer`.

- [x] **Step 3: Implement hot reload helper**

Create:

```python
class DossierHotReloadResult(BaseModel):
    actor_id: str
    layer_id: str
    previous_layer_version: int
    next_layer_version: int
    invalidates: list[str]
    does_not_mutate: list[str]
    dossier: CharacterDossier


def replace_dossier_layer(
    dossier: CharacterDossier,
    *,
    layer_id: str,
    layer_payload: dict[str, object],
) -> DossierHotReloadResult:
    ...
```

Required `does_not_mutate` values:

- `need_tension_state`
- `dynamic_state`
- `body_runtime_state`
- `current_goal_state`
- `memory_store`
- `relationship_graph`
- `character_skill_state`

This helper is a contract and test utility. It is not a file watcher or live
runtime reload service.

- [x] **Step 4: Run hot reload tests**

Run:

```bash
python -m pytest backend/tests/test_character_dossier_hot_reload.py -v
```

Expected: PASS.

---

## Phase 7: Example Dossier Fixture

### Task 7: Add One Example Dossier Without Migrating All Profiles

**Files:**
- Create: `assets/characters/dossiers/char_a.yaml`
- Modify: `backend/tests/test_character_dossier_loader.py`

- [x] **Step 1: Add fixture test**

Extend loader tests to load:

```text
assets/characters/dossiers/char_a.yaml
```

Assert:

- actor ID is `char_a`
- nested character profile canonical name remains `Lin Yue`
- identity profile contains multi-identity fields
- embodiment profile contains static motor baseline
- relationship seed profile contains evidence seeds
- capability seed profile contains `social.mediation`

- [x] **Step 2: Create example dossier YAML**

Create `assets/characters/dossiers/char_a.yaml` as a wrapped dossier using the
current `char_a` profile data as the nested `character_profile`. Keep it as an
example fixture; do not migrate `assets/characters/profiles/char_a.yaml` in
this task.

- [x] **Step 3: Run fixture tests**

Run:

```bash
python -m pytest backend/tests/test_character_dossier_loader.py -v
```

Expected: PASS.

---

## Phase 8: Documentation And Status

### Task 8: Update Architecture Docs

**Files:**
- Modify: `docs/架构/运行时/模块/角色智能体.md`
- Modify: `docs/character/character-mind-core-status.md`

- [x] **Step 1: Document Dossier boundary**

In `docs/架构/运行时/模块/角色智能体.md`, add a concise section explaining:

```text
CharacterDossier = editable authored truth.
CharacterProfile = long-term psychological/behavior baseline inside Dossier.
Runtime stores own lived state.
Dossier projections enter CharacterMindFrame only after visibility filtering.
```

- [x] **Step 2: Document static/dynamic body split**

State:

```text
EmbodimentProfile is static or semi-static.
BodyRuntimeState is mutable and must be updated by runtime/settlement systems.
Dossier hot reload does not clear injury, fatigue, pain, or other runtime body state.
```

- [x] **Step 3: Document graph and skill boundaries**

State:

```text
RelationshipSeedProfile initializes social memory and relationship evidence.
RelationshipGraph is a future evidence-backed read model.
CapabilitySeedProfile initializes skill-state candidates.
AbilityGraph is a future read model consumed by CharacterSkillService.
L3 consumes summaries, not raw graphs.
```

- [x] **Step 4: Update status doc**

In `docs/character/character-mind-core-status.md`, add status entries:

- dossier schema wrapper
- visibility-filtered dossier projection
- shadow mind-frame dossier cards
- relationship/capability seed contracts
- known remaining follow-ups

- [x] **Step 5: Run docs harness**

Run:

```bash
python scripts/verification/harness.py --profile docs
```

Expected: `overall_docs_passed=True`.

---

## Final Verification

Run the focused test suite:

```bash
python -m pytest \
  backend/tests/test_character_dossier_models.py \
  backend/tests/test_character_dossier_loader.py \
  backend/tests/test_character_dossier_projection.py \
  backend/tests/test_character_dossier_seed_projection.py \
  backend/tests/test_character_dossier_hot_reload.py \
  backend/tests/test_character_profile_models.py \
  backend/tests/test_character_profile_loader.py \
  backend/tests/test_character_mind_frame_models.py \
  backend/tests/test_character_mind_projectors.py \
  backend/tests/test_character_mind_frame_builder.py \
  backend/tests/test_character_mind_context_views.py -v
```

Run docs harness:

```bash
python scripts/verification/harness.py --profile docs
```

For broad completion claims, run:

```bash
python scripts/verification/harness.py --profile all
```

---

## Rollback Strategy

- Phase 1-4 are additive and shadow-mode. Rollback is deleting dossier models,
  loader, projection helpers, tests, and dossier cards.
- Phase 5 only creates candidate conversion helpers. It does not persist social
  memory or skill state.
- Phase 6 only defines the hot reload contract. It does not start a file
  watcher or mutate runtime stores.
- Phase 7 adds one example fixture and can be removed independently.
- Documentation changes should be reverted with the code if dossier contracts
  are removed.

---

## Commit Guidance

Use Lore-style commit messages. Suggested split:

1. `Separate authored dossier truth from profile baseline`
2. `Project dossier layers through visibility filters`
3. `Expose dossier summaries in mind frames`
4. `Convert dossier seeds into runtime initialization candidates`
5. `Define dossier layer hot reload invalidation`
6. `Add an example character dossier fixture`
7. `Document dossier runtime boundaries`

Keep graph, body-runtime, and skill-system production work in later commits and
later specs.
