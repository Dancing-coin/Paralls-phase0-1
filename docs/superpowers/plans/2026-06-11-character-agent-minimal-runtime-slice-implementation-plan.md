# Character Agent Minimal Runtime Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal character-agent runtime slice for `CharacterA` and `CharacterB` that explicitly implements the `CharacterAgent L1` perception layer first, then interprets it, selects one minimal intent, and emits observable Godot-facing outputs without bypassing `ESM` or `System L1`.

**Architecture:** Align to the main-project `L1` perception chain: upstream `Raw Fact Producers` and candidate compilation stay in current `System L1`, while this repo hardens the `Per-Character Perception Filter` and implements the `Private World Snapshot`, then layers `L2`, `L3`, `L4`, and websocket/Godot integration on top.

**Tech Stack:** FastAPI websocket backend, Pydantic models, pytest, existing debug stream, Godot GDScript presentation scripts, existing harness verification.

---

### Task 1: Runtime Models And Backend Contract Tests

**Files:**
- Create: `backend/app/models/character_agent_runtime.py`
- Create: `backend/tests/test_character_agent_runtime_models.py`

- [ ] **Step 1: Write the failing model tests**

Add tests that instantiate and serialize the four new types: `CharacterPrivateWorldSnapshot`, `CharacterInterpretation`, `CharacterIntentDecision`, and `CharacterPresentationCommand`.
The snapshot model must reflect the main-project `L1` design rather than only the smaller local draft.

```python
from app.models.character_agent_runtime import (
    CharacterIntentDecision,
    CharacterInterpretation,
    CharacterPresentationCommand,
    CharacterPrivateWorldSnapshot,
)


def test_character_private_world_snapshot_defaults() -> None:
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id="char_a",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=100,
        updated_at=100,
    )

    assert snapshot.visible_entities == []
    assert snapshot.body_state_hints == []
    assert snapshot.unresolved_signals == []
    assert snapshot.active_anomalies == []


def test_character_presentation_command_shape() -> None:
    command = CharacterPresentationCommand(
        actor_id="char_b",
        output_type="attention_shift",
        producer_ts=120,
        causation_id="character_agent:120",
        correlation_id="character_agent:120",
        target_actor_id="char_c",
    )

    payload = command.model_dump(exclude_none=True)

    assert payload["output_type"] == "attention_shift"
    assert payload["target_actor_id"] == "char_c"
```

- [ ] **Step 2: Run the model tests to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_agent_runtime_models.py
```

Expected before implementation: fail with `ModuleNotFoundError` or missing model names from `app.models.character_agent_runtime`.

- [ ] **Step 3: Implement the runtime model module**

Add a focused model file with the four runtime types and the frozen minimal fields from the spec.

```python
from pydantic import BaseModel, Field


class CharacterPrivateWorldSnapshot(BaseModel):
    actor_id: str
    room_id: str
    scene_id: str
    zone_id: str
    producer_ts: int
    visible_entities: list[str] = Field(default_factory=list)
    audible_entities: list[str] = Field(default_factory=list)
    unresolved_signals: list[str] = Field(default_factory=list)
    active_anomalies: list[str] = Field(default_factory=list)
    attention_targets: list[str] = Field(default_factory=list)
    short_horizon_social_presence: list[str] = Field(default_factory=list)
    local_spatial_confidence_map: dict[str, float] = Field(default_factory=dict)
    recent_world_changes: list[str] = Field(default_factory=list)
    recent_constraint_results: list[str] = Field(default_factory=list)
    body_state_hints: list[str] = Field(default_factory=list)
    last_siming_catalyst: str | None = None
    clarity_score: float = 1.0
    certainty_score: float = 1.0
    updated_at: int
```

- [ ] **Step 4: Re-run the model tests**

Run:

```powershell
python -m pytest -q backend\tests\test_character_agent_runtime_models.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/character_agent_runtime.py backend/tests/test_character_agent_runtime_models.py
git commit -m "Define the minimal character-agent runtime contracts"
```

### Task 2: Harden The `Per-Character Perception Filter`

**Files:**
- Modify: `backend/app/services/per_character_percept_filter.py`
- Modify: `backend/tests/test_per_character_percept_filter.py`
- Modify: `backend/tests/test_visual_fact_pipeline.py`

- [ ] **Step 1: Write failing filter tests**

Add tests that prove the filter is no longer just target-id gating and starts matching the main-project `L1` design dimensions:

- distance
- orientation
- attention focus
- minimum clarity / certainty outputs

```python
def test_filter_returns_private_event_with_quality_scores() -> None:
    candidate = CandidatePerceptEvent(
        percept_channel="visual",
        source_fact_family="visual_fact",
        source_fact_type="fixed_gaze_on_target",
        producer_ts=610,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source_actor_id="char_c",
        target_actor_id="char_a",
        audience_scope="candidate",
        observability={"visual": True},
        causation_id="vf:610",
        correlation_id="vf:610",
    )

    perceived = filter_candidate_for_actor(
        candidate,
        actor_id="char_a",
        context={"is_facing_target": True, "distance_m": 2.0, "attention_focus": "char_c"},
    )

    assert perceived is not None
    assert "clarity_score" in perceived.model_dump()
    assert "certainty_score" in perceived.model_dump()
```

- [ ] **Step 2: Run the filter tests to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_per_character_percept_filter.py backend\tests\test_visual_fact_pipeline.py
```

Expected before implementation: fail because the filter does not yet emit the required quality/boundary behavior.

- [ ] **Step 3: Implement the filter hardening**

Update the filter so it stays deterministic but starts honoring the main-project `L1` shape.

```python
def filter_candidate_for_actor(...):
    ...
    clarity_score = 1.0 if is_facing_target else 0.4
    certainty_score = 1.0 if distance_m <= 3.0 else 0.6
    ...
```

- [ ] **Step 4: Re-run the filter tests**

Run:

```powershell
python -m pytest -q backend\tests\test_per_character_percept_filter.py backend\tests\test_visual_fact_pipeline.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/per_character_percept_filter.py backend/tests/test_per_character_percept_filter.py backend/tests/test_visual_fact_pipeline.py
git commit -m "Harden the character-agent L1 private perception filter"
```

### Task 3: `CharacterAgent L1` Perception Layer

**Files:**
- Create: `backend/app/services/character_agent_l1.py`
- Modify: `backend/app/services/character_agent_runtime.py`
- Create: `backend/tests/test_character_agent_l1.py`

- [ ] **Step 1: Write the failing L1 snapshot tests**

Add tests that prove `CharacterAgent L1` is a real perception layer: it ingests filtered/private inputs, updates a per-actor snapshot, preserves perception-quality state, and exposes that state as the only downstream boundary for `L2`.

```python
from app.models.character_perceived import CharacterPerceivedEvent
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from app.services.character_agent_l1 import CharacterAgentL1Service


def test_character_agent_l1_tracks_latest_private_snapshot() -> None:
    service = CharacterAgentL1Service()
    perceived = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=200,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:200:char_a",
    )

    snapshot = service.apply_character_perceived_event(perceived)

    assert snapshot.actor_id == "char_a"
    assert snapshot.visible_entities == ["visual_fact/fixed_gaze_on_target"]
    assert snapshot.clarity_score == 1.0
    assert snapshot.certainty_score == 1.0


def test_character_agent_l1_tracks_self_body_hint() -> None:
    service = CharacterAgentL1Service()
    event = SelfBodyPerceivedEvent(
        actor_id="char_a",
        body_state_class="interaction_strain",
        producer_ts=220,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="body_state_result/interaction_strain=engaged",
        source_body_result_id="body_result:char_a:220",
    )

    snapshot = service.apply_self_body_perceived_event(event)

    assert snapshot.body_state_hints == ["interaction_strain:body_state_result/interaction_strain=engaged"]
```

- [ ] **Step 2: Run the L1 tests to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_agent_l1.py
```

Expected before implementation: fail because the `CharacterAgentL1Service` module does not exist.

- [ ] **Step 3: Implement the `CharacterAgent L1` perception service**

The service should do one thing well: implement the actor-private perception layer from filtered inputs. It should not interpret, select intent, or emit Godot commands.

```python
class CharacterAgentL1Service:
    def apply_character_perceived_event(self, event: CharacterPerceivedEvent) -> CharacterPrivateWorldSnapshot:
        ...

    def apply_self_body_perceived_event(self, event: SelfBodyPerceivedEvent) -> CharacterPrivateWorldSnapshot:
        ...

    def apply_siming_output(self, payload: dict[str, object]) -> CharacterPrivateWorldSnapshot:
        ...
```

The implementation should also expose a read API:

```python
    def get_snapshot(self, actor_id: str) -> CharacterPrivateWorldSnapshot | None:
        ...
```

- [ ] **Step 4: Re-run the L1 tests**

Run:

```powershell
python -m pytest -q backend\tests\test_character_agent_l1.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/character_agent_l1.py backend/app/services/character_agent_runtime.py backend/tests/test_character_agent_l1.py
git commit -m "Implement the character-agent L1 private world snapshot"
```

### Task 4: `L2`, `L3`, `L4`, And Runtime Orchestration

**Files:**
- Create: `backend/app/services/character_agent_l2.py`
- Create: `backend/app/services/character_agent_l3.py`
- Create: `backend/app/services/character_agent_l4_adapter.py`
- Create: `backend/app/services/character_agent_runtime.py`
- Create: `backend/tests/test_character_agent_runtime.py`

- [ ] **Step 1: Write failing orchestration tests**

Add unit tests that prove:

- `L2` interprets a private event into a structured interpretation
- `L3` chooses one intent from the allowed intent set
- `L4` converts the intent into one or more presentation commands
- `CharacterAgentRuntime` only handles `char_a` and `char_b`

```python
from app.models.character_perceived import CharacterPerceivedEvent
from app.services.character_agent_runtime import CharacterAgentRuntime


def test_character_agent_runtime_turns_perceived_event_into_output() -> None:
    runtime = CharacterAgentRuntime()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=300,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:300:char_a",
    )

    commands = runtime.ingest_character_perceived_event(event)

    assert commands
    assert commands[0].actor_id == "char_a"
    assert commands[0].output_type in {
        "attention_shift",
        "brief_dialogue_response",
        "reposition_step",
        "role_state_hint",
        "physiology_hint",
    }
```

- [ ] **Step 2: Run the orchestration tests to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_agent_runtime.py
```

Expected before implementation: fail because the runtime service and subservices do not exist.

- [ ] **Step 3: Implement `CharacterAgentL2Service`**

Keep it deterministic. It should inspect the latest event and snapshot, then emit a small `CharacterInterpretation`.

```python
class CharacterAgentL2Service:
    def interpret_perceived_event(self, snapshot, event) -> CharacterInterpretation:
        summary = event.perceived_summary
        interpretation_type = "opportunity" if "visual_fact" in summary else "state_change"
        return CharacterInterpretation(
            actor_id=event.actor_id,
            interpreted_summary=summary,
            interpretation_type=interpretation_type,
            salience_score=0.7,
            ambiguity_level="low",
            risk_level="low",
            opportunity_level="medium" if interpretation_type == "opportunity" else "low",
            attention_target=snapshot.attention_targets[0] if snapshot.attention_targets else None,
            inner_prompt_candidate=f"{event.actor_id}:{summary}",
        )
```

- [ ] **Step 4: Implement `CharacterAgentL3Service`**

Keep the first-pass selector simple and auditable.

```python
class CharacterAgentL3Service:
    def select_intent(self, interpretation: CharacterInterpretation) -> CharacterIntentDecision:
        output_type = "observe_target"
        if interpretation.opportunity_level in {"medium", "high"}:
            output_type = "speak_brief_response"
        elif interpretation.risk_level in {"medium", "high"}:
            output_type = "reposition"
        return CharacterIntentDecision(
            actor_id=interpretation.actor_id,
            selected_intent=output_type,
            persona_passed=True,
            logic_passed=True,
            gain_loss_passed=True,
            rationale=interpretation.interpreted_summary,
        )
```

- [ ] **Step 5: Implement `CharacterAgentL4Adapter` and orchestration runtime**

The adapter should translate decisions into `CharacterPresentationCommand` objects, and the runtime should own `L1 -> L2 -> L3 -> L4` orchestration. `L1` stays a private snapshot layer, not a duplicated world-fact pipeline.

```python
class CharacterAgentRuntime:
    SUPPORTED_ACTORS = {"char_a", "char_b"}

    def ingest_character_perceived_event(self, event: CharacterPerceivedEvent) -> list[CharacterPresentationCommand]:
        if event.actor_id not in self.SUPPORTED_ACTORS:
            return []
        snapshot = self._l1.apply_character_perceived_event(event)
        interpretation = self._l2.interpret_perceived_event(snapshot, event)
        decision = self._l3.select_intent(interpretation)
        return self._l4.build_commands(snapshot, interpretation, decision)
```

- [ ] **Step 6: Re-run the orchestration tests**

Run:

```powershell
python -m pytest -q backend\tests\test_character_agent_runtime.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/character_agent_l2.py backend/app/services/character_agent_l3.py backend/app/services/character_agent_l4_adapter.py backend/app/services/character_agent_runtime.py backend/tests/test_character_agent_runtime.py
git commit -m "Add the minimal character-agent runtime slice services"
```

### Task 5: Backend WebSocket Integration And Runtime Ingress Wiring

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_visual_fact_pipeline.py`
- Modify: `backend/tests/test_ws_protocol.py`

- [ ] **Step 1: Write failing integration tests**

Extend websocket coverage so a private character input can trigger a `character_agent_output` envelope for `char_a` or `char_b`.

```python
def test_raw_visual_fact_for_char_a_emits_character_agent_output() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "raw_fact_event",
                "payload": {
                    "fact_family": "visual_fact",
                    "fact_type": "fixed_gaze_on_target",
                    "relation_type": "actor_looks_at_actor",
                    "producer_ts": 900,
                    "room_id": "room_demo",
                    "scene_id": "scene_demo",
                    "zone_id": "zone_focus",
                    "source": {"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
                    "targets": {"actor_id": "char_a"},
                },
            }
        )

        messages = [websocket.receive_json() for _ in range(2)]

    assert any(message["message_type"] == "character_agent_output" for message in messages)
```

- [ ] **Step 2: Run the integration tests to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_visual_fact_pipeline.py backend\tests\test_ws_protocol.py
```

Expected before implementation: fail because `character_agent_output` is never emitted.

- [ ] **Step 3: Wire runtime creation into `reset_runtime_state()`**

Instantiate the runtime beside the other process-owned backend services.

```python
global character_agent_runtime
character_agent_runtime = CharacterAgentRuntime()
```

- [ ] **Step 4: Feed the runtime from existing private-input seams**

When `CharacterPerceivedEvent` or `SelfBodyPerceivedEvent` is produced, immediately pass it through the runtime and append any returned `character_agent_output` envelopes.

```python
commands = character_agent_runtime.ingest_character_perceived_event(perceived)
messages.extend(_as_character_agent_output_envelopes(commands))
```

Also add a pass that scans outbound `siming_output` messages targeted at `char_a` or `char_b` and routes them through `character_agent_runtime.ingest_siming_output(...)`.

- [ ] **Step 5: Add envelope conversion helper**

Add a dedicated helper in `backend/app/main.py`.

```python
def _as_character_agent_output_envelopes(commands: list[CharacterPresentationCommand]) -> list[dict[str, object]]:
    return [
        {
            "message_type": "character_agent_output",
            "payload": command.model_dump(exclude_none=True),
        }
        for command in commands
    ]
```

- [ ] **Step 6: Re-run the websocket and pipeline tests**

Run:

```powershell
python -m pytest -q backend\tests\test_visual_fact_pipeline.py backend\tests\test_ws_protocol.py
```

Expected: PASS, with at least one assertion proving `character_agent_output` is emitted for `char_a` or `char_b`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/main.py backend/tests/test_visual_fact_pipeline.py backend/tests/test_ws_protocol.py
git commit -m "Wire the character-agent runtime into the backend websocket flow"
```

### Task 6: Godot Presentation Bus And Character Replica Consumption

**Files:**
- Modify: `scripts/autoload/LocalPresentationBus.gd`
- Modify: `scripts/autoload/BackendBridge.gd`
- Modify: `scripts/character/CharacterReplica.gd`
- Modify: `backend/tests/test_verification_audit.py`

- [ ] **Step 1: Add a failing static verification test**

Add assertions that the bus exposes a new `character_agent_output_received` signal and the bridge dispatches the new message type.

```python
def test_backend_bridge_exposes_character_agent_output_signal_chain() -> None:
    project_root = Path(__file__).resolve().parents[2]
    bus_source = (project_root / "scripts" / "autoload" / "LocalPresentationBus.gd").read_text(encoding="utf-8")
    bridge_source = (project_root / "scripts" / "autoload" / "BackendBridge.gd").read_text(encoding="utf-8")

    assert 'signal character_agent_output_received(payload)' in bus_source
    assert 'character_agent_output' in bridge_source
```

- [ ] **Step 2: Run the audit/static test to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_verification_audit.py
```

Expected before implementation: fail because the new signal chain does not exist.

- [ ] **Step 3: Add the new bus signal and bridge dispatch**

```gdscript
signal character_agent_output_received(payload)
```

```gdscript
"character_agent_output":
    _bus_log("character_agent_output:%s" % JSON.stringify(payload))
    _bus_emit("character_agent_output_received", [payload])
```

- [ ] **Step 4: Teach `CharacterReplica.gd` to consume the command**

Connect the new signal in `_ready()` and add one method that fans out to existing helpers instead of duplicating pose/motion logic.

```gdscript
func _on_character_agent_output_received(payload: Dictionary) -> void:
    if str(payload.get("actor_id", "")) != actor_id:
        return
    match str(payload.get("output_type", "")):
        "attention_shift":
            apply_attention(payload)
        "brief_dialogue_response":
            apply_dialogue(payload)
        "reposition_step":
            var target := payload.get("move_target", null)
            if target is Array and target.size() == 3:
                set_move_target(Vector3(target[0], target[1], target[2]))
```

- [ ] **Step 5: Re-run the static verification test**

Run:

```powershell
python -m pytest -q backend\tests\test_verification_audit.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/autoload/LocalPresentationBus.gd scripts/autoload/BackendBridge.gd scripts/character/CharacterReplica.gd backend/tests/test_verification_audit.py
git commit -m "Expose character-agent presentation commands to Godot"
```

### Task 7: Boundary Audit And End-To-End Verification

**Files:**
- Create: `backend/tests/test_character_agent_boundary_audit.py`
- Modify: `scripts/verification/verify_phase0.py` only if fresh evidence shows a real verification gap
- Modify: `scripts/verification/harness.py` only if profile wiring is actually missing

- [ ] **Step 1: Write a failing boundary audit test**

The audit must prove that the runtime only accepts filtered/private inputs and is not imported into raw-fact compilation or authority-bus settlement paths as a truth source.

```python
from pathlib import Path


def test_character_agent_runtime_is_not_used_as_world_truth_authority() -> None:
    project_root = Path(__file__).resolve().parents[2]
    runtime_source = (project_root / "backend" / "app" / "services" / "character_agent_runtime.py").read_text(encoding="utf-8")
    esm_source = (project_root / "backend" / "app" / "services" / "esm_service.py").read_text(encoding="utf-8")

    assert "RawFactEvent" not in runtime_source
    assert "AuthorityEvent" not in runtime_source
    assert "CharacterAgentRuntime" not in esm_source
```

- [ ] **Step 2: Run the boundary audit to verify failure or gap**

Run:

```powershell
python -m pytest -q backend\tests\test_character_agent_boundary_audit.py
```

Expected before implementation: fail until the runtime file exists and the audit is aligned to the actual implementation.

- [ ] **Step 3: Finalize the audit and run focused backend tests**

Run:

```powershell
python -m pytest -q backend\tests\test_character_agent_runtime_models.py backend\tests\test_character_agent_runtime.py backend\tests\test_character_agent_boundary_audit.py backend\tests\test_visual_fact_pipeline.py backend\tests\test_ws_protocol.py
```

Expected: PASS.

- [ ] **Step 4: Run project verification**

Run:

```powershell
python -m pytest -v
python scripts/verification/harness.py --profile phase0
python scripts/verification/harness.py --profile phase1-slice
python scripts/verification/harness.py --profile all
```

Expected:

- repository pytest suite passes
- `phase0` stays green
- `phase1-slice` stays green
- `all` remains green without boundary regression

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_character_agent_boundary_audit.py scripts/verification/verify_phase0.py scripts/verification/harness.py
git commit -m "Verify the character-agent slice without relaxing phase0 boundaries"
```
