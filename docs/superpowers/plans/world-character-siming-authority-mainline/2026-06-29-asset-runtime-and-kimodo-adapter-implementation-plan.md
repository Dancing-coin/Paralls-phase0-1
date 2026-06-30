# Asset Runtime And Kimodo Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define and then implement the final-target realization backend for asset indexing, preload, fallback, and Kimodo integration.

**Architecture:** Treat the asset runtime as the future embodiment-realization host below execution semantics. Start by introducing interface and registry contracts without forcing immediate heavy runtime adoption. Keep the current local presentation host alive while adding a clean adapter seam for Kimodo and asset-library-backed realization.

**Tech Stack:** GDScript, repository asset docs, future adapter interfaces, pytest static tests, docs verification.

**Progress Snapshot (`2026-06-30`):**
- Tasks `1-4` now have direct repository evidence.
- Current proof chain covers:
  - `CharacterEmbodimentAssetRuntime.gd` registry and preload API
  - `KimodoActionRequest` semantic/target metadata contract
  - `KimodoRealizationPlan` generated-motion plus local-fallback composition contract
  - `compose_realization_plan(...)` realization planning surface with
    - `generated_motion_allowed`
    - `local_fallback_asset_refs`
    - `missing_semantic_keys`
  - unified mainline verifier result `asset_runtime_kimodo_contracts=proved`
- Current direct evidence:
  - `pytest backend/tests/test_character_asset_runtime_static.py backend/tests/test_kimodo_adapter_contract.py -v`
  - `python scripts/verification/harness.py --profile docs`
  - `python scripts/verification/verify_mainline_unified_runtime.py`
  - `python scripts/verification/harness.py --profile mainline-unified-runtime`

**Direct Evidence Audit (`2026-06-30`):**
- Required outcome `1. explicit asset indexing and capability binding model`
  - Direct evidence:
    - `backend/tests/test_character_asset_runtime_static.py::test_character_asset_runtime_declares_registry_and_preload_api`
    - `scripts/character/CharacterEmbodimentAssetRuntime.gd` now defines `register_motion_asset(...)`
- Required outcome `2. on-demand preload policy`
  - Direct evidence:
    - `backend/tests/test_character_asset_runtime_static.py::test_character_asset_runtime_declares_registry_and_preload_api`
    - `scripts/character/CharacterEmbodimentAssetRuntime.gd` now defines `preload_assets_for_semantics(...)`
- Required outcome `3. Kimodo adapter contract`
  - Direct evidence:
    - `backend/tests/test_kimodo_adapter_contract.py::test_kimodo_action_request_carries_semantic_and_target_metadata`
    - `backend/app/character_agent/execution/kimodo_adapter_contract.py` now defines `KimodoActionRequest`
- Required outcome `4. generated-motion plus local-asset fallback composition rules`
  - Direct evidence:
    - `backend/tests/test_kimodo_adapter_contract.py::test_kimodo_realization_plan_carries_generated_motion_and_local_fallback_assets`
    - `backend/tests/test_character_asset_runtime_static.py::test_character_asset_runtime_declares_realization_plan_api`
    - `backend/app/character_agent/execution/kimodo_adapter_contract.py` now defines `KimodoRealizationPlan`
    - `scripts/character/CharacterEmbodimentAssetRuntime.gd` now defines `compose_realization_plan(...)`
- Unified proof status:
  - `.harness/verification/mainline-unified-runtime-report.json` currently records:
    - `asset_runtime_kimodo_contracts=proved`

**Completion Audit Conclusion (`2026-06-30`):**
- Within the current contract-first scope of this plan, the four required outcomes now have direct repository evidence.
- The plan is intentionally closed at the seam/contract layer:
  - asset indexing and preload surfaces are defined
  - Kimodo request and realization contracts are defined
  - generated-motion plus local-fallback composition is defined
  - unified verifier coverage records these contracts as `asset_runtime_kimodo_contracts=proved`
- Remaining non-goals for this plan:
  - no live Kimodo runtime integration
  - no production asset cache/eviction runtime
  - no heavy local preload daemon or streaming pipeline

---

### Task 1: Define asset-runtime registry and preload contracts

**Files:**
- Create: `scripts/character/CharacterEmbodimentAssetRuntime.gd`
- Modify: `docs/character/character-asset-integration.md`
- Test: `backend/tests/test_character_asset_runtime_static.py`

- [x] **Step 1: Write the failing static contract test**

```python
from pathlib import Path


def test_character_asset_runtime_declares_registry_and_preload_api() -> None:
    text = Path("scripts/character/CharacterEmbodimentAssetRuntime.gd").read_text(encoding="utf-8")
    assert "register_motion_asset" in text
    assert "preload_assets_for_semantics" in text
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_character_asset_runtime_static.py -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```gdscript
extends RefCounted

class_name CharacterEmbodimentAssetRuntime

var _motion_assets: Dictionary = {}

func register_motion_asset(semantic_key: String, asset_ref: String) -> void:
	_motion_assets[semantic_key] = asset_ref

func preload_assets_for_semantics(semantic_keys: Array[String]) -> Array[String]:
	var queued: Array[String] = []
	for key in semantic_keys:
		if _motion_assets.has(key):
			queued.append(str(_motion_assets[key]))
	return queued
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_character_asset_runtime_static.py -v`
Expected: `PASS`

- [x] **Step 5: Commit**

```bash
git add scripts/character/CharacterEmbodimentAssetRuntime.gd docs/character/character-asset-integration.md backend/tests/test_character_asset_runtime_static.py
git commit -m "Define initial embodiment asset runtime registry contracts

Constraint: Future heavy realization must run through a formal asset-runtime layer rather than one-off scene wiring
Rejected: Leave asset and preload semantics implicit until Kimodo lands | makes the adapter contract too vague
Confidence: medium
Scope-risk: moderate
Directive: Execution semantics must map to registrable asset-runtime keys before backend-generated realization is attempted
Tested: pytest backend/tests/test_character_asset_runtime_static.py -v
Not-tested: live preload behavior"
```

### Task 2: Define Kimodo adapter interface without forcing immediate runtime coupling

**Files:**
- Create: `backend/app/character_agent/execution/kimodo_adapter_contract.py`
- Test: `backend/tests/test_kimodo_adapter_contract.py`

- [x] **Step 1: Write the failing adapter contract test**

```python
from app.character_agent.execution.kimodo_adapter_contract import KimodoActionRequest


def test_kimodo_action_request_carries_semantic_and_target_metadata() -> None:
    request = KimodoActionRequest(
        actor_id="char_a",
        semantic_keys=["approach", "greeting_nod"],
        target_actor_id="char_c",
        execution_mode="skeletal_animation",
    )
    assert request.semantic_keys == ["approach", "greeting_nod"]
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_kimodo_adapter_contract.py -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
from pydantic import BaseModel, ConfigDict, Field


class KimodoActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    semantic_keys: list[str] = Field(default_factory=list)
    target_actor_id: str | None = None
    target_object_id: str | None = None
    execution_mode: str
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_kimodo_adapter_contract.py -v`
Expected: `PASS`

- [x] **Step 5: Commit**

```bash
git add backend/app/character_agent/execution/kimodo_adapter_contract.py backend/tests/test_kimodo_adapter_contract.py
git commit -m "Define Kimodo adapter contract from execution semantics

Constraint: Kimodo integration must consume stable semantics rather than scene-specific action strings
Rejected: Bind Kimodo directly to current CharacterReplica internals | too coupled to the temporary local host
Confidence: high
Scope-risk: narrow
Directive: Any future Kimodo integration must accept semantic requests that remain valid even if the local presentation host changes
Tested: pytest backend/tests/test_kimodo_adapter_contract.py -v
Not-tested: real Kimodo runtime"
```

### Task 3: Add unified verifier coverage for asset-runtime and Kimodo contracts

**Files:**
- Modify: `scripts/verification/verify_mainline_unified_runtime.py`
- Modify: `scripts/verification/tests/test_mainline_unified_runtime_verify.py`

- [x] **Step 1: Write the failing verifier coverage test**

```python
def test_mainline_unified_runtime_verifier_includes_asset_runtime_and_kimodo_contract_evidence() -> None:
    # assert the unified verifier runs:
    # backend/tests/test_character_asset_runtime_static.py
    # backend/tests/test_kimodo_adapter_contract.py
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k asset_runtime_and_kimodo -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
# in verify_mainline_unified_runtime.py, add a focused pytest profile for:
# - backend/tests/test_character_asset_runtime_static.py
# - backend/tests/test_kimodo_adapter_contract.py
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest scripts/verification/tests/test_mainline_unified_runtime_verify.py -k asset_runtime_and_kimodo -v`
Expected: `PASS`

- [x] **Step 5: Re-run unified proof**

Run: `python scripts/verification/verify_mainline_unified_runtime.py`
Expected: `PASS`

### Task 4: Add generated-motion plus local-asset fallback composition contracts

**Files:**
- Modify: `backend/app/character_agent/execution/kimodo_adapter_contract.py`
- Modify: `backend/tests/test_kimodo_adapter_contract.py`
- Modify: `scripts/character/CharacterEmbodimentAssetRuntime.gd`
- Modify: `backend/tests/test_character_asset_runtime_static.py`
- Modify: `docs/character/character-asset-integration.md`

- [x] **Step 1: Write the failing focused tests**

```python
from app.character_agent.execution.kimodo_adapter_contract import KimodoRealizationPlan


def test_kimodo_realization_plan_carries_generated_motion_and_local_fallback_assets() -> None:
    plan = KimodoRealizationPlan(
        actor_id="char_a",
        semantic_keys=["approach", "greeting_nod"],
        execution_mode="skeletal_animation",
        generated_motion_allowed=True,
        local_fallback_asset_refs=["res://motions/approach.anim"],
        missing_semantic_keys=["greeting_nod"],
    )
    assert plan.generated_motion_allowed is True
```
```

```python
from pathlib import Path


def test_character_asset_runtime_declares_realization_plan_api() -> None:
    text = Path("scripts/character/CharacterEmbodimentAssetRuntime.gd").read_text(encoding="utf-8")
    assert "compose_realization_plan" in text
```
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_kimodo_adapter_contract.py backend/tests/test_character_asset_runtime_static.py -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
class KimodoRealizationPlan(BaseModel):
    actor_id: str
    semantic_keys: list[str]
    execution_mode: str
    generated_motion_allowed: bool = False
    local_fallback_asset_refs: list[str] = Field(default_factory=list)
    missing_semantic_keys: list[str] = Field(default_factory=list)
```

```gdscript
func compose_realization_plan(semantic_keys: Array[String], generated_motion_allowed: bool) -> Dictionary:
	var resolved_assets := preload_assets_for_semantics(semantic_keys)
	var missing_semantic_keys: Array[String] = []
	for semantic_key: String in semantic_keys:
		if not _motion_assets.has(semantic_key):
			missing_semantic_keys.append(semantic_key)
	return {
		"semantic_keys": semantic_keys,
		"generated_motion_allowed": generated_motion_allowed,
		"local_fallback_asset_refs": resolved_assets,
		"missing_semantic_keys": missing_semantic_keys,
	}
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_kimodo_adapter_contract.py backend/tests/test_character_asset_runtime_static.py -v`
Expected: `PASS`

- [x] **Step 5: Re-run docs and unified proof**

Run: `python scripts/verification/harness.py --profile docs`
Expected: `PASS`

Run: `python scripts/verification/verify_mainline_unified_runtime.py`
Expected: `PASS`
