# Phase 5 Resource Capability and Staging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let eligible story nodes reuse existing scene, actor, object, environment, dialogue, and embodiment capabilities without allowing asset availability to override facts, autonomy, or Authority.

**Architecture:** Build a backend semantic capability index over existing resource contracts, calculate exact realization signatures and fatigue, then stage selected nodes through explicit Godot/Character/ESM acknowledgements. Staging changes only node readiness; actual Authority outcomes remain the sole resolution source.

**Tech Stack:** Python `>=3.11`, Pydantic v2, existing character skill `realization_keys`, existing Godot `CharacterEmbodimentAssetRegistry`, existing ESM capabilities, pytest, Harness Engineering.

## Global Constraints

- Requires passing Phase 4 `siming-story-runtime`.
- Add no art and assume no resources beyond `MainDemo.tscn`, throne room, `char_b`, `char_c`, `obj_letter`, `env_lamp`, current dialogue/voice path, camera, and registered realization keys.
- Do not build a second Godot action asset registry; consume existing registry/feasibility acknowledgements.
- Resource scoring runs only after fact, player choice, autonomy, Authority, ESM, safety, playability, fairness, obligation, and attractor gates pass.
- Exact realization signature is asset bundle + actor binding + camera pattern + semantic purpose + location state.
- Repeating only a scene or actor is not fatigue; penalize the complete signature within a bounded recent window.
- Preload/staging success is not story resolution or obligation fulfillment.
- Resource failure, actor refusal, or player divergence produces `aborted_before_activation`/`aborted` and leaves the obligation open.

---

### Task 1: Define Capability, Signature, and Staging Contracts

**Files:**
- Create: `backend/app/models/siming_resource_capability.py`
- Create: `backend/tests/test_siming_resource_capability_models.py`

**Interfaces:**
- Consumes: story node IDs and existing realization-key strings.
- Produces: `ResourceCapabilityPackage`, `ResourceRealizationRequest`, `RealizationSignature`, `StagingRequest`, `StagingAck`, and `StagingResult`.

- [ ] **Step 1: Write failing stable-signature tests**

```python
def test_signature_changes_with_semantic_purpose() -> None:
    first = realization_request(semantic_purpose="evidence_reveal").signature("main_demo_throne_room")
    second = realization_request(semantic_purpose="private_confrontation").signature("main_demo_throne_room")
    assert first != second


def test_staging_result_cannot_claim_story_resolution() -> None:
    with pytest.raises(ValidationError, match="story"):
        StagingResult(
            node_id="runtime:bridge:1", status="staged",
            realization_signature="sig:1", story_resolved=True,
        )
```

- [ ] **Step 2: Run tests and confirm the module is absent**

Run: `python -m pytest backend/tests/test_siming_resource_capability_models.py -v`

Expected: FAIL with missing module.

- [ ] **Step 3: Add strict models and canonical signature**

```python
class ResourceCapabilityPackage(StrictResourceModel):
    capability_id: str
    asset_bundle: str
    scene_refs: list[str]
    actor_ids: list[str]
    object_ids: list[str]
    environment_ids: list[str]
    realization_keys: list[str]
    semantic_purposes: list[str]
    load_cost: float = Field(ge=0.0)
    loaded: bool
    cooldown_until: int = Field(ge=0)

class ResourceRealizationRequest(StrictResourceModel):
    node_id: str
    actor_bindings: dict[str, str]
    target_object_id: str | None = None
    target_environment_id: str | None = None
    required_realization_keys: list[str]
    camera_pattern: str
    semantic_purpose: str
    location_state: str

    def signature(self, asset_bundle: str) -> str:
        payload = [asset_bundle, sorted(self.actor_bindings.items()), self.camera_pattern,
                   self.semantic_purpose, self.location_state]
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
```

`StagingAck` source is exactly `godot`, `character`, or `esm`; `StagingResult.status` is `staged`, `aborted_before_activation`, or `cancelled` and has no story-resolution field.

```python
class ResourceMatch(StrictResourceModel):
    accepted: bool
    reason: str = ""
    capability: ResourceCapabilityPackage | None = None
    realization_signature: str = ""
    fatigue_penalty: float = Field(default=0.0, ge=0.0)

class StagingAck(StrictResourceModel):
    source: Literal["godot", "character", "esm"]
    correlation_id: str
    accepted: bool
    reason: str = ""

class StagingRequest(StrictResourceModel):
    node_id: str
    correlation_id: str
    obligation_id: str
    resource_match: ResourceMatch

class StagingResult(StrictResourceModel):
    node_id: str
    correlation_id: str
    status: Literal["staged", "aborted_before_activation", "cancelled"]
    story_node_lifecycle: Literal["staged", "aborted"]
    obligation_status: Literal["open", "pressured", "partially_satisfied"]
    realization_signature: str
    reason: str = ""
```

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest backend/tests/test_siming_resource_capability_models.py -v`

Expected: PASS.

```powershell
git add backend/app/models/siming_resource_capability.py backend/tests/test_siming_resource_capability_models.py
git commit -m "feat: define resource capability and staging contracts"
```

### Task 2: Index Existing Capabilities and Rank Reuse/Fatigue

**Files:**
- Create: `backend/app/services/siming_resource_capability_registry.py`
- Create: `backend/tests/test_siming_resource_capability_registry.py`

**Interfaces:**
- Consumes: Task 1 models, current skill realization keys, and repo-local ESM capability snapshot.
- Produces: `ResourceCapabilityRegistry.register(...)`, `match(...)`, and `record_realization(...)`.

- [ ] **Step 1: Write current-scene coverage and fatigue tests**

```python
def test_main_demo_package_covers_private_confrontation(registry) -> None:
    match = registry.match(realization_request(
        actor_bindings={"speaker": "char_b", "listener": "char_c"},
        target_object_id="obj_letter", required_realization_keys=["look_at_target", "focus_attention"],
        semantic_purpose="private_confrontation",
    ), world_ts=100)
    assert match.accepted is True
    assert match.capability.asset_bundle == "main_demo_throne_room"


def test_only_exact_recent_signature_receives_fatigue_penalty(registry) -> None:
    reveal = realization_request(semantic_purpose="evidence_reveal")
    confrontation = realization_request(semantic_purpose="private_confrontation")
    registry.record_realization(reveal, "main_demo_throne_room", world_ts=90)
    assert registry.match(reveal, world_ts=100).fatigue_penalty > 0
    assert registry.match(confrontation, world_ts=100).fatigue_penalty == 0
```

- [ ] **Step 2: Run tests and confirm the registry is absent**

Run: `python -m pytest backend/tests/test_siming_resource_capability_registry.py -v`

Expected: FAIL with missing module.

- [ ] **Step 3: Implement the semantic index and final-stage score**

```python
class ResourceCapabilityRegistry:
    FATIGUE_WINDOW = 5

    def match(self, request: ResourceRealizationRequest, *, world_ts: int) -> ResourceMatch:
        covered = [item for item in self._packages.values() if self._covers(item, request, world_ts)]
        ranked = sorted(covered, key=lambda item: (
            self._fatigue(item, request), item.load_cost,
            0 if item.loaded else 1, item.capability_id,
        ))
        if not ranked:
            return ResourceMatch(accepted=False, reason="resource_unavailable")
        selected = ranked[0]
        return ResourceMatch(
            accepted=True, capability=selected,
            realization_signature=request.signature(selected.asset_bundle),
            fatigue_penalty=self._fatigue(selected, request),
        )
```

Seed `main_demo_throne_room` from explicit repo-local constants. Coverage checks scene, actors, object/environment, semantic purpose, and all realization keys. It does not check story facts or autonomy because those have already been hard-gated upstream.

- [ ] **Step 4: Run registry tests and commit**

Run: `python -m pytest backend/tests/test_siming_resource_capability_registry.py -v`

Expected: PASS for coverage, unavailable resources, load/cooldown, deterministic ordering, signature fatigue, and natural reuse.

```powershell
git add backend/app/services/siming_resource_capability_registry.py backend/tests/test_siming_resource_capability_registry.py
git commit -m "feat: index and rank existing story capabilities"
```

### Task 3: Implement Staging Acknowledgement and Cancellation

**Files:**
- Create: `backend/app/services/siming_story_node_staging.py`
- Create: `backend/tests/test_siming_story_node_staging.py`

**Interfaces:**
- Consumes: eligible story candidate, accepted resource match, and Godot/Character/ESM `StagingAck`s.
- Produces: staged or aborted node transition plus an intervention-outcome memory record.

- [ ] **Step 1: Write all-ack, refusal, and divergence tests**

```python
def test_node_stages_only_after_all_required_acks(stager, request) -> None:
    result = stager.complete(request, acks=[
        ack("godot", True), ack("character", True), ack("esm", True),
    ])
    assert result.status == "staged"
    assert result.story_node_lifecycle == "staged"


def test_character_refusal_aborts_before_activation_and_keeps_obligation_open(stager, request) -> None:
    result = stager.complete(request, acks=[ack("godot", True), ack("character", False, "actor_refused"), ack("esm", True)])
    assert result.status == "aborted_before_activation"
    assert result.obligation_status == "open"


def test_player_divergence_cancels_staged_node(stager, staged_request) -> None:
    result = stager.cancel(staged_request.node_id, reason="player_diverged", correlation_id="corr:2")
    assert result.status == "cancelled"
```

- [ ] **Step 2: Run tests and confirm the stager is absent**

Run: `python -m pytest backend/tests/test_siming_story_node_staging.py -v`

Expected: FAIL with missing module.

- [ ] **Step 3: Implement correlation-safe staging**

```python
class SimingStoryNodeStaging:
    REQUIRED_ACK_SOURCES = frozenset({"godot", "character", "esm"})

    def complete(self, request: StagingRequest, *, acks: list[StagingAck]) -> StagingResult:
        by_source = {ack.source: ack for ack in acks if ack.correlation_id == request.correlation_id}
        if set(by_source) != self.REQUIRED_ACK_SOURCES:
            return self._abort(request, "missing_staging_ack")
        rejected = sorted(ack.reason for ack in by_source.values() if not ack.accepted)
        return self._abort(request, rejected[0]) if rejected else self._stage(request)
```

Every result writes an `intervention_outcome` six-domain entry. `_stage` transitions only `selected -> staged`; `_abort` transitions `selected|staged -> aborted` with `aborted_before_activation` semantics and never changes obligation to fulfilled.

- [ ] **Step 4: Run stager tests and commit**

Run: `python -m pytest backend/tests/test_siming_story_node_staging.py -v`

Expected: PASS for missing/duplicate/wrong-correlation acks, actor refusal, ESM rejection, Godot preload failure, cancellation, and idempotent replay.

```powershell
git add backend/app/services/siming_story_node_staging.py backend/tests/test_siming_story_node_staging.py
git commit -m "feat: stage story nodes through runtime acknowledgements"
```

### Task 4: Add the Resource Staging Harness Gate

**Files:**
- Create: `scripts/verification/verify_siming_resource_staging.py`
- Create: `.harness/profiles/siming-resource-staging.json`
- Modify: `docs/harness.md`
- Modify: `docs/INDEX.md`

**Interfaces:**
- Consumes: Tasks 1-3 plus Phase 4 hard-gated candidate output.
- Produces: `.harness/verification/siming-resource-staging-report.json`.

- [ ] **Step 1: Implement the repo-resource verifier**

The verifier must statically confirm the named scene/resources/realization keys exist, then run backend capability and staging cases. Emit `existing_resource_package`, `hard_gate_precedes_resource_score`, `semantic_reuse`, `exact_signature_fatigue`, `all_ack_staged`, `refusal_aborted`, and `obligation_remains_open`.

- [ ] **Step 2: Register the profile**

```json
{
  "schema_version": 1,
  "name": "siming-resource-staging",
  "order": 76,
  "script": "scripts/verification/verify_siming_resource_staging.py",
  "requires_godot": false,
  "max_attempts": 1,
  "result_artifact": ".harness/verification/siming-resource-staging-report.json",
  "description": "Backend and repo-static proof for resource-aware story ranking, semantic reuse, fatigue, and truthful staging"
}
```

- [ ] **Step 3: Run the phase gate**

Run: `python scripts/verification/harness.py --profile siming-resource-staging`

Expected: PASS with all seven results proved.

- [ ] **Step 4: Commit**

```powershell
git add scripts/verification/verify_siming_resource_staging.py .harness/profiles/siming-resource-staging.json docs/harness.md docs/INDEX.md
git commit -m "test: prove resource-aware story staging"
```
