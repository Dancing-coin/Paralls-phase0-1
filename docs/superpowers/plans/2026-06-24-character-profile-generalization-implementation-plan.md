# Character Profile And Generalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hardcoded role support with a structured-file-first `CharacterProfile` system and generalized role registration so the runtime can handle arbitrary roles rather than `char_a / char_b / char_c` as architecture truth.

**Architecture:** Introduce a backend profile package that loads YAML profiles into normalized Pydantic runtime objects and exposes a registry/lookup seam for the existing `CharacterAgentRuntime`. Keep current control-mode defaults and known role IDs working through profile metadata rather than runtime hardcoding.

**Tech Stack:** Python, Pydantic, YAML profile assets, existing `CharacterAgentRuntime`, pytest.

---

### Task 1: Add profile asset directory and normalized profile models

**Files:**
- Create: `assets/characters/profiles/README.md`
- Create: `assets/characters/profiles/char_a.yaml`
- Create: `assets/characters/profiles/char_b.yaml`
- Create: `assets/characters/profiles/char_c.yaml`
- Create: `backend/app/character_agent/profile/__init__.py`
- Create: `backend/app/character_agent/profile/models.py`
- Test: `backend/tests/test_character_profile_models.py`

- [ ] **Step 1: Write the failing model test**

```python
from app.character_agent.profile.models import CharacterProfile


def test_character_profile_requires_stage2_identity_and_trait_fields() -> None:
    profile = CharacterProfile.model_validate(
        {
            "identity_core": {
                "character_id": "char_test",
                "canonical_name": "Test Role",
                "aliases": [],
                "occupation_role": "witness",
            },
            "origin_seed": {},
            "life_memory_backbone": {},
            "virtue_value_layer": {"value_priorities": ["safety", "loyalty"]},
            "trait_vector_layer": {
                "courage": 0.4,
                "scheming": 0.2,
                "empathy": 0.7,
                "rationality": 0.5,
                "sociability": 0.3,
            },
            "capability_constraint_layer": {"skills": [], "knowledge_domains": []},
            "style_expression_bias_layer": {"speech_style": "direct", "silence_pattern": "guarded"},
            "conversation_personality_layer": {
                "social_openness": 0.3,
                "privacy_sensitivity": 0.8,
                "talk_initiative": 0.2,
                "deception_control": 0.4,
                "trust_threshold_for_private_talk": 0.75,
            },
        }
    )

    assert profile.identity_core.character_id == "char_test"
    assert profile.trait_vector_layer.empathy == 0.7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_character_profile_models.py::test_character_profile_requires_stage2_identity_and_trait_fields -v`
Expected: FAIL with `ModuleNotFoundError` or missing `CharacterProfile`.

- [ ] **Step 3: Add normalized profile models**

```python
from pydantic import BaseModel, Field


class IdentityCore(BaseModel):
    character_id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    occupation_role: str


class TraitVectorLayer(BaseModel):
    courage: float
    scheming: float
    empathy: float
    rationality: float
    sociability: float


class ConversationPersonalityLayer(BaseModel):
    social_openness: float
    privacy_sensitivity: float
    talk_initiative: float
    deception_control: float
    trust_threshold_for_private_talk: float


class CharacterProfile(BaseModel):
    identity_core: IdentityCore
    origin_seed: dict[str, object] = Field(default_factory=dict)
    life_memory_backbone: dict[str, object] = Field(default_factory=dict)
    virtue_value_layer: dict[str, object] = Field(default_factory=dict)
    trait_vector_layer: TraitVectorLayer
    capability_constraint_layer: dict[str, object] = Field(default_factory=dict)
    style_expression_bias_layer: dict[str, object] = Field(default_factory=dict)
    conversation_personality_layer: ConversationPersonalityLayer
```

- [ ] **Step 4: Add initial structured profiles**

```yaml
# assets/characters/profiles/char_a.yaml
identity_core:
  character_id: char_a
  canonical_name: Character A
  aliases: []
  occupation_role: court_figure
origin_seed: {}
life_memory_backbone: {}
virtue_value_layer:
  value_priorities: [authority, stability]
trait_vector_layer:
  courage: 0.62
  scheming: 0.58
  empathy: 0.32
  rationality: 0.71
  sociability: 0.44
capability_constraint_layer:
  skills: [observation, rhetoric]
  knowledge_domains: [court, ritual]
style_expression_bias_layer:
  speech_style: formal
  silence_pattern: strategic
conversation_personality_layer:
  social_openness: 0.31
  privacy_sensitivity: 0.77
  talk_initiative: 0.46
  deception_control: 0.69
  trust_threshold_for_private_talk: 0.82
```

- [ ] **Step 5: Run model test**

Run: `pytest backend/tests/test_character_profile_models.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add assets/characters/profiles backend/app/character_agent/profile backend/tests/test_character_profile_models.py
git commit -m "Ground character runtime in structured profile models

Constraint: Stage 2 requires structured-file-first profile truth before generalized runtime support
Rejected: Keep role identity in runtime constants | blocks arbitrary-role support
Confidence: high
Scope-risk: moderate
Directive: Do not let runtime layers read ad-hoc role identity from scattered constants after this point
Tested: pytest backend/tests/test_character_profile_models.py -v
Not-tested: runtime integration with profile loading"
```

### Task 2: Add profile loader, read-only views, and registry

**Files:**
- Create: `backend/app/character_agent/profile/loader.py`
- Create: `backend/app/character_agent/profile/views.py`
- Create: `backend/app/character_agent/profile/registry.py`
- Test: `backend/tests/test_character_profile_loader.py`

- [ ] **Step 1: Write failing loader/registry tests**

```python
from app.character_agent.profile.loader import CharacterProfileLoader
from app.character_agent.profile.registry import CharacterProfileRegistry


def test_profile_loader_reads_yaml_profile() -> None:
    loader = CharacterProfileLoader("assets/characters/profiles")
    profile = loader.load("char_a")
    assert profile.identity_core.character_id == "char_a"


def test_profile_registry_lists_available_roles() -> None:
    registry = CharacterProfileRegistry.from_directory("assets/characters/profiles")
    assert "char_a" in registry.actor_ids()
    assert registry.get("char_b").identity_core.canonical_name == "Character B"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest backend/tests/test_character_profile_loader.py -v`
Expected: FAIL because loader/registry do not exist.

- [ ] **Step 3: Implement loader and registry**

```python
import yaml
from pathlib import Path

from app.character_agent.profile.models import CharacterProfile


class CharacterProfileLoader:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def load(self, actor_id: str) -> CharacterProfile:
        path = self._root / f"{actor_id}.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        return CharacterProfile.model_validate(payload)


class CharacterProfileRegistry:
    def __init__(self, profiles: dict[str, CharacterProfile]) -> None:
        self._profiles = profiles

    @classmethod
    def from_directory(cls, root: str | Path) -> "CharacterProfileRegistry":
        loader = CharacterProfileLoader(root)
        profiles = {
            path.stem: loader.load(path.stem)
            for path in sorted(Path(root).glob("*.yaml"))
        }
        return cls(profiles)

    def actor_ids(self) -> list[str]:
        return sorted(self._profiles.keys())

    def get(self, actor_id: str) -> CharacterProfile:
        return self._profiles[actor_id]
```

- [ ] **Step 4: Add read-only views**

```python
from dataclasses import dataclass

from app.character_agent.profile.models import CharacterProfile


@dataclass(frozen=True)
class ProfileIdentityView:
    character_id: str
    canonical_name: str
    occupation_role: str


def build_identity_view(profile: CharacterProfile) -> ProfileIdentityView:
    return ProfileIdentityView(
        character_id=profile.identity_core.character_id,
        canonical_name=profile.identity_core.canonical_name,
        occupation_role=profile.identity_core.occupation_role,
    )
```

- [ ] **Step 5: Run loader tests**

Run: `pytest backend/tests/test_character_profile_loader.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/character_agent/profile backend/tests/test_character_profile_loader.py
git commit -m "Add profile loader and registry for generalized role support

Constraint: Runtime must discover roles from structured profile assets instead of hardcoded actor lists
Rejected: Lazy inline YAML parsing inside runtime loop | mixes IO and cognition flow
Confidence: high
Scope-risk: moderate
Directive: Keep profile loading and profile consumption separate via read-only views
Tested: pytest backend/tests/test_character_profile_loader.py -v
Not-tested: runtime actor registration switch-over"
```

### Task 3: Replace hardcoded actor support in runtime and dispatch paths

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/app/services/siming_character_dispatch_adapter.py`
- Test: `backend/tests/test_character_agent_runtime_generalization.py`
- Test: `backend/tests/test_siming_character_dispatch_adapter.py`

- [ ] **Step 1: Write the failing runtime generalization test**

```python
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime


def test_runtime_supports_registered_actor_not_runtime_constant() -> None:
    runtime = CharacterAgentRuntime()
    assert runtime.supports_actor("char_a")
    assert not hasattr(runtime, "SUPPORTED_ACTORS")
```

- [ ] **Step 2: Run the focused failing test**

Run: `pytest backend/tests/test_character_agent_runtime_generalization.py::test_runtime_supports_registered_actor_not_runtime_constant -v`
Expected: FAIL because `SUPPORTED_ACTORS` still exists.

- [ ] **Step 3: Switch runtime actor discovery to registry-backed state**

```python
from app.character_agent.profile.registry import CharacterProfileRegistry


class CharacterAgentRuntime:
    def __init__(self, storage_root: str | Path | None = None) -> None:
        self._profile_registry = CharacterProfileRegistry.from_directory("assets/characters/profiles")
        self._supported_actor_ids = set(self._profile_registry.actor_ids())
        self._control_modes = self._default_control_modes()

    def _default_control_modes(self) -> dict[str, str]:
        defaults = {actor_id: "agent_full_auto" for actor_id in self._supported_actor_ids}
        if "char_c" in defaults:
            defaults["char_c"] = "player_priority_assisted"
        return defaults

    def supports_actor(self, actor_id: str) -> bool:
        return actor_id in self._supported_actor_ids
```

- [ ] **Step 4: Update adapter tests to assert registry-backed support still works**

```python
def test_dispatch_marks_unknown_actor_target_unavailable() -> None:
    runtime = CharacterAgentRuntime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime)
    # existing event fixture keeps a bogus target_id; expected status remains target_unavailable
```

- [ ] **Step 5: Run runtime and dispatch tests**

Run: `pytest backend/tests/test_character_agent_runtime_generalization.py backend/tests/test_siming_character_dispatch_adapter.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/character_agent/runtime/runtime_loop.py backend/app/services/siming_character_dispatch_adapter.py backend/tests/test_character_agent_runtime_generalization.py backend/tests/test_siming_character_dispatch_adapter.py
git commit -m "Generalize runtime actor support through profile registry

Constraint: Stage 2 must support arbitrary registered roles rather than freezing char_a/char_b/char_c as architecture truth
Rejected: Keep SUPPORTED_ACTORS and add one more allowlist seam | preserves the wrong runtime boundary
Confidence: medium
Scope-risk: broad
Directive: Any new role support should begin with profile registration, not runtime hardcoding
Tested: pytest backend/tests/test_character_agent_runtime_generalization.py backend/tests/test_siming_character_dispatch_adapter.py -v
Not-tested: full phase0 runtime after registry expansion"
```
