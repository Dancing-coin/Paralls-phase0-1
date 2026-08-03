# Phase 7 Full Siming Heavenly Runtime Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the complete player-destroys-evidence scenario through durable graph memory, `char_b` private recall, real online LLM proposal, deterministic validation, one `SimingRuntime.tick(...)` decision, Authority settlement, and visible Godot reaction.

**Architecture:** Compose one SQLite graph into the backend and provide graph context/candidates to the existing tick through a non-publishing support service. Activate ownership by event family, write every decision/outcome idempotently, and prove the loop in the existing MainDemo scene with a real backend restart, nonblank screenshots, online provider audit, and archived Harness evidence.

**Tech Stack:** Python `>=3.11`, FastAPI, Pydantic v2, SQLite, existing System L6/Siming/Character/ESM services, existing Godot 4 project, existing online Siming LLM provider routes, pytest, Harness Engineering.

## Global Constraints

- Requires passing Phase 6 `siming-adaptive-bridge`.
- `SimingRuntime.tick(...)` remains the only decision entry and catalyst publisher path.
- `SimingHeavenlyRuntimeSupport` may ingest, compile, validate, stage, and record but has no `tick` or publish method.
- Modes are `off`, `shadow`, and `active`; shadow evidence cannot affect policy, feasibility, selection, staging, or publication.
- Active ownership transfers by event family, not by whichever path returns first.
- One correlation ID has at most one selected decision and one dispatch family.
- Graph failure in active mode yields `graph_degraded` and no new graph-dependent node activation; state tree is not fallback truth.
- LLM failure/invalid output yields `llm_unavailable`/`proposal_rejected` and no action; fake/disabled fallback fails live acceptance.
- Only ESM/World Authority can confirm `removed_from_surface`; Godot hides the object only after the applied Authority result.
- `char_b` must actually observe destruction, persist Event+Observation, survive backend restart, and be read through the Siming gateway.
- Use existing art/resources only and save before-destruction, after-destruction, and `char_b` reaction proof.
- Do not claim completion from hosted `ci-non-godot`; real Godot plus online LLM local evidence is mandatory.

---

### Task 1: Compose the Graph Runtime and Explicit Ownership Modes

**Files:**
- Create: `backend/app/services/siming_heavenly_runtime_support.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_siming_heavenly_runtime_composition.py`
- Modify: `backend/tests/test_config_runtime_modes.py`

**Interfaces:**
- Consumes: all Phase 1.1-6 graph, memory, story, resource, bridge, provider, and actor gateway services.
- Produces: `SimingHeavenlyRuntimeSupport`, `PreparedHeavenlyDecision`, and configured `off|shadow|active` composition.

- [ ] **Step 1: Write failing mode/configuration tests**

```python
def test_heavenly_mode_defaults_off(monkeypatch) -> None:
    monkeypatch.delenv("SIMING_HEAVENLY_MODE", raising=False)
    assert reload_settings().siming_heavenly_mode == "off"


def test_active_mode_composes_shared_sqlite_graph(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SIMING_HEAVENLY_MODE", "active")
    monkeypatch.setenv("PARALLS_HEAVENLY_GRAPH_PATH", str(tmp_path / "runtime.sqlite3"))
    state = build_runtime_state(reload_settings())
    assert state.siming_runtime.heavenly_support.mode == "active"
    assert state.heavenly_graph is state.character_graph_memory.graph
```

- [ ] **Step 2: Run tests and confirm mode/support are absent**

Run: `python -m pytest backend/tests/test_config_runtime_modes.py backend/tests/test_siming_heavenly_runtime_composition.py -v`

Expected: FAIL because `siming_heavenly_mode` and support composition do not exist.

- [ ] **Step 3: Add exact settings**

```python
SimingHeavenlyMode = Literal["off", "shadow", "active"]
siming_heavenly_mode: SimingHeavenlyMode = "off"
```

Read `SIMING_HEAVENLY_MODE`; reuse Phase 3 `heavenly_graph_path` and `character_graph_memory_heavy_actor_ids`. Reject an empty graph path or heavy-actor IDs outside the runtime profile registry.

- [ ] **Step 4: Implement a non-publishing support service**

```python
class PreparedHeavenlyDecision(BaseModel):
    mode: SimingHeavenlyMode
    event_family: str
    owns_event_family: bool
    correlation_id: str
    context_hash: str
    eligible_node_refs: list[str] = Field(default_factory=list)
    validation_audit_refs: list[str] = Field(default_factory=list)
    degraded_reason: str = ""
```

```text
SimingHeavenlyRuntimeSupport.GRAPH_OWNED_EVENT_FAMILIES = {evidence_destruction_consequence}
SimingHeavenlyRuntimeSupport(mode, memory, compiler, actor_memory, story, obligations, resources, staging, bridges, llm_provider)
prepare(siming_input: SimingInput) -> PreparedHeavenlyDecision
record_selection(prepared: PreparedHeavenlyDecision, selected_node_ref: str) -> str
record_dispatch(*, correlation_id: str, dispatch_event_id: str) -> str
record_authority_outcome(event: AuthorityEvent) -> str | None
```

Do not add `tick`, `publish`, or actor-memory write methods. `prepare` returns typed eligible bridge/story candidates and audit refs; it cannot activate or dispatch them.

- [ ] **Step 5: Compose one SQLite adapter and all dependent services**

Refactor `reset_runtime_state()` only enough to create one `SQLiteHeavenlyGraphAdapter`, pass it to character graph memory and Siming graph services, then inject the support into `SimingRuntime`. In `off`, Siming graph support is absent but `char_b` graph memory remains available; in `shadow`, support writes/compiles evidence but marks candidates advisory; in `active`, the owned family may enter selection.

- [ ] **Step 6: Run composition tests and commit**

Run: `python -m pytest backend/tests/test_config_runtime_modes.py backend/tests/test_siming_heavenly_runtime_composition.py -v`

Expected: PASS for all modes, shared adapter identity, invalid config, and absence of publisher methods.

```powershell
git add backend/app/services/siming_heavenly_runtime_support.py backend/app/config.py backend/app/main.py backend/tests/test_siming_heavenly_runtime_composition.py backend/tests/test_config_runtime_modes.py
git commit -m "feat: compose Siming heavenly graph runtime modes"
```

### Task 2: Integrate Graph Candidates Into the Single Tick and Recovery Ledger

**Files:**
- Modify: `backend/app/services/siming_runtime.py`
- Modify: `backend/app/services/siming_event_pipeline.py`
- Modify: `backend/app/services/siming_event_consumer.py`
- Modify: `backend/app/models/siming_event.py`
- Create: `backend/tests/test_siming_heavenly_runtime_tick.py`
- Create: `backend/tests/test_siming_heavenly_runtime_recovery.py`

**Interfaces:**
- Consumes: `PreparedHeavenlyDecision` from Task 1 and existing policy/feasibility/producer path.
- Produces: one selected graph-backed decision in active mode, evidence-only shadow mode, and idempotent unsent/sent-unconfirmed/authority-confirmed recovery.

- [ ] **Step 1: Write off/shadow/active ownership tests**

```python
def test_shadow_candidate_never_changes_selection(shadow_runtime, input_event) -> None:
    result = shadow_runtime.tick([input_event])
    assert selected_decision_ids(result) == legacy_decision_ids(input_event)
    assert any(a.status == "shadow_recorded" for a in result.audit_records)


def test_active_owned_family_stages_then_dispatches_once(active_runtime, destruction_input) -> None:
    selected = active_runtime.tick([destruction_input])
    assert selected_decision_ids(selected) == ["decision:runtime:bridge:proposal:private-confrontation:1"]
    assert [item.output_type for item in selected.outputs].count("staging_request") == 1
    assert [item.output_type for item in selected.outputs].count("dispatch_intent") == 0
    dispatched = active_runtime.tick([all_staging_acks_input("corr:destroy:1")])
    dispatches = [item for item in dispatched.outputs if item.output_type == "dispatch_intent"]
    assert len(dispatches) == 1
    assert dispatches[0].correlation_id == "corr:destroy:1"
```

- [ ] **Step 2: Write crash-recovery tests**

```python
@pytest.mark.parametrize("state,expected_dispatches", [
    ("unsent", 1), ("sent_unconfirmed", 0), ("authority_confirmed", 0),
])
def test_recovery_never_double_dispatches(runtime_factory, state, expected_dispatches) -> None:
    runtime = runtime_factory(seed_dispatch_state=state)
    result = runtime.tick([recovery_input("corr:destroy:1")])
    assert len([o for o in result.outputs if o.output_type == "dispatch_intent"]) == expected_dispatches
```

- [ ] **Step 3: Run tests and confirm the legacy tick does not consume graph preparation**

Run: `python -m pytest backend/tests/test_siming_heavenly_runtime_tick.py backend/tests/test_siming_heavenly_runtime_recovery.py -v`

Expected: FAIL because active ownership and recovery records are absent.

- [ ] **Step 4: Add graph preparation inside the existing tick loop**

```python
prepared = self._heavenly_support.prepare(siming_input) if self._heavenly_support else None
if prepared is not None and prepared.mode == "active" and prepared.owns_event_family:
    outputs, audits = self._process_graph_owned_event(event, prepared)
    result.outputs.extend(outputs)
    result.audit_records.extend(audits)
    continue
```

`_process_graph_owned_event` stays a private helper of `SimingRuntime`; it applies existing policy/feasibility plus story/resource validators and records exactly one selection. On selection it emits one typed `staging_request` output and no catalyst dispatch. `SimingEventConsumer` accepts correlation-matched `siming_staging_ack` inputs from Godot, Character, and ESM; after all three are persisted, a later tick uses existing `_candidate_output`, `_decision_output`, and `_dispatch_output` to publish exactly once. It must return no action on graph degraded, incomplete memory, LLM unavailable, rejected proposal, staging failure, or a sent-unconfirmed ledger state.

```python
SimingInputType = Literal[
    "world_fact_event", "visual_fact_event", "esm_result_event",
    "character_behavior_event", "conversation_resolution_event",
    "constraint_state_event", "siming_staging_ack",
]

SimingOutputType = Literal[
    "fairness_snapshot", "intervention_candidate", "intervention_decision",
    "staging_request", "dispatch_intent", "audit_record", "no_action",
]
```

- [ ] **Step 5: Record publication and Authority confirmation in the event pipeline**

Before tick, call the support's `record_authority_outcome(event)` through a non-decision runtime method. After `SimingEventProducer.publish_outputs`, record only actual published dispatch event IDs. Add a correlation-local duplicate check before publishing; a second dispatch family for the same correlation raises `SimingDuplicateDispatchError` and fails the event instead of silently publishing.

- [ ] **Step 6: Demote compatibility projections**

In active owned-family processing, build state tree/read model/checkpoints from `SimingStoryProjection.project(compiled_context)`. Keep legacy projections in off/shadow and unrelated event families. Never read state-tree fields to reconstruct a missing story node or obligation.

- [ ] **Step 7: Run tick, pipeline, and recovery tests**

Run: `python -m pytest backend/tests/test_siming_heavenly_runtime_tick.py backend/tests/test_siming_heavenly_runtime_recovery.py backend/tests/test_siming_runtime.py backend/tests/test_siming_event_pipeline.py -v`

Expected: PASS for one owner, one dispatch, all failure modes, projection basis, and all three recovery states.

- [ ] **Step 8: Commit**

```powershell
git add backend/app/services/siming_runtime.py backend/app/services/siming_event_pipeline.py backend/app/services/siming_event_consumer.py backend/app/models/siming_event.py backend/tests/test_siming_heavenly_runtime_tick.py backend/tests/test_siming_heavenly_runtime_recovery.py
git commit -m "feat: route heavenly graph decisions through Siming tick"
```

### Task 3: Make Evidence Destruction and `char_b` Reaction Visible in MainDemo

**Files:**
- Modify: `backend/app/services/esm_service.py`
- Modify: `backend/tests/test_esm_service.py`
- Modify: `scripts/object/InteractiveObject.gd`
- Modify: `scripts/phase0/MainDemoController.gd`
- Create: `scripts/verification/SimingHeavenlyRuntimeProbe.gd`
- Modify: `scenes/phase0/MainDemo.tscn`
- Create: `backend/tests/test_siming_heavenly_godot_static.py`

**Interfaces:**
- Consumes: structured `InteractIntent(interaction_type="destroy")`, applied object-state result, current LocalPresentationBus, current character dispatch/dialogue path.
- Produces: `removed_from_surface` Authority result, hidden/collision-disabled object, real `char_b` observation, and three Godot captures/markers.

- [ ] **Step 1: Write the Authority transition test**

```python
def test_visible_letter_can_be_destroyed_by_authority() -> None:
    esm = ESMService()
    esm.commit_interaction_state(
        room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
        target_object_id="obj_letter", current_state="visible",
    )
    policy = esm.interaction_policy_for(
        "obj_letter", "destroy", room_id="room_demo", scene_id="scene_demo",
        zone_id="zone_focus", actor_id="char_c",
    )
    assert policy["current_state"] == "removed_from_surface"
```

- [ ] **Step 2: Write static Godot behavior tests**

```python
def test_removed_letter_hides_visual_label_and_collision() -> None:
    source = Path("scripts/object/InteractiveObject.gd").read_text(encoding="utf-8")
    assert 'current_state == "removed_from_surface"' in source
    assert "visual_root.visible = not removed" in source
    assert "collision_shape.disabled = removed" in source


def test_main_demo_contains_heavenly_runtime_probe() -> None:
    scene = Path("scenes/phase0/MainDemo.tscn").read_text(encoding="utf-8")
    assert "SimingHeavenlyRuntimeProbe.gd" in scene
```

- [ ] **Step 3: Run tests and confirm destruction/presentation are missing**

Run: `python -m pytest backend/tests/test_esm_service.py backend/tests/test_siming_heavenly_godot_static.py -v`

Expected: FAIL because `destroy` is not allowed and the object never hides.

- [ ] **Step 4: Add the stateful Authority transition**

Keep current inspect/read behavior and add a `destroy` transition from `visible` to `removed_from_surface` for `obj_letter`. The existing orchestration must emit the applied `object_state_result`; do not synthesize success in Godot.

```python
"obj_letter": {
    "allowed_interactions": {"inspect", "read", "destroy"},
    "machine_id": "visibility", "initial_state": "partially_visible",
    "stateful": True,
    "transitions": {
        "inspect": {"previous_state": "partially_visible", "current_state": "visible"},
        "read": {"previous_state": "partially_visible", "current_state": "visible"},
        "destroy": {"previous_state": "visible", "current_state": "removed_from_surface"},
    },
    "affordances": ["inspect", "read", "destroy"],
    "environment_transition": "alert_lamp",
}
```

- [ ] **Step 5: Apply the Authority result visibly**

Add `@onready var visual_root = $VisualRoot` and `@onready var collision_shape = $InteractionCollider/CollisionShape3D`. In `_apply_visual_state`, set `removed := current_state == "removed_from_surface"`, then `visual_root.visible = not removed`, `label_3d.visible = not removed`, and `collision_shape.disabled = removed`. Continue emitting the normalized state-transition fact after the result so the character perception path can record the observation.

- [ ] **Step 6: Add an opt-in real runtime probe to MainDemo**

The probe exits immediately unless `SIMING_HEAVENLY_AUTOTEST=1`. It first proves `char_b` has actor-local line of sight to `obj_letter` through the existing perception sampler, waits for backend connection, captures `siming-heavenly-before-destruction.png`, submits structured inspect then destroy through the existing controller request method, waits for the applied world result and hidden visual/collision state, captures `siming-heavenly-after-destruction.png`, and logs `siming_heavenly_restart_ready`. After backend reconnect, it submits a normal structured dialogue/focus input to provide a tick opportunity, answers the received `staging_request` with a Godot feasibility ack while backend Character/ESM produce their own acks, waits for the next tick's single `char_b` dispatch and visible reaction/dialogue, captures `siming-heavenly-char-b-reaction.png`, runs the existing sampled-pixel meaningful-image check, then logs `siming_heavenly_godot_complete`. The verifier must reject evidence unless the persisted observation names `actor_id=char_b`, `observed_entity_id=obj_letter`, and the destruction Authority result ref.

- [ ] **Step 7: Run static/backend tests and a scene-load check**

Run: `python -m pytest backend/tests/test_esm_service.py backend/tests/test_siming_heavenly_godot_static.py -v`

Expected: PASS.

Run: `& $env:GODOT_EXE --path . --scene res://scenes/phase0/MainDemo.tscn --quit-after 120 --render-thread safe`

Expected: exit 0 with no parse/resource errors. If `GODOT_EXE` is unavailable, report the Godot portion as written but unverified and do not pass Phase 7.

- [ ] **Step 8: Commit**

```powershell
git add backend/app/services/esm_service.py backend/tests/test_esm_service.py scripts/object/InteractiveObject.gd scripts/phase0/MainDemoController.gd scripts/verification/SimingHeavenlyRuntimeProbe.gd scenes/phase0/MainDemo.tscn backend/tests/test_siming_heavenly_godot_static.py
git commit -m "feat: realize evidence destruction and Siming reaction"
```

### Task 4: Build the Real Online LLM and Godot Verification Profile

**Files:**
- Create: `scripts/verification/verify_siming_heavenly_runtime.py`
- Create: `scripts/verification/tests/test_siming_heavenly_runtime_verify.py`
- Create: `.harness/profiles/siming-heavenly-runtime.json`
- Modify: `docs/harness.md`
- Modify: `docs/INDEX.md`

**Interfaces:**
- Consumes: live Siming LLM environment, SQLite path, backend process helpers, Godot executable, probe markers, and graph/audit reports.
- Produces: `.harness/verification/siming-heavenly-runtime-report.json`, logs, traces, three screenshots, and archived Harness evidence.

- [ ] **Step 1: Write preflight and fake-rejection verifier tests**

```python
def test_preflight_rejects_disabled_or_fake_provider(monkeypatch) -> None:
    monkeypatch.setenv("SIMING_LLM_MODE", "disabled")
    result = live_preflight(project_root())
    assert result.ok is False
    assert "online_siming_llm_required" in result.reasons


def test_report_requires_all_three_nonblank_captures(tmp_path) -> None:
    evidence = valid_live_evidence(tmp_path)
    evidence.reaction_capture.unlink()
    assert evaluate_live_evidence(evidence).overall is False
```

- [ ] **Step 2: Run tests and confirm the verifier is absent**

Run: `python -m pytest scripts/verification/tests/test_siming_heavenly_runtime_verify.py -v`

Expected: FAIL with missing verifier module.

- [ ] **Step 3: Implement strict secret-safe preflight**

`--preflight` must resolve `GODOT_EXE`, require `SIMING_HEAVENLY_MODE=active`, `SIMING_LLM_MODE=http`, at least one enabled non-disabled HTTP route, non-empty endpoint/model/API key, writable SQLite parent directory, and must print only presence booleans/route IDs/models. It must never print keys or route config containing keys.

- [ ] **Step 4: Implement the live process sequence**

1. Delete only the verifier-owned temporary database path under `.harness/verification/siming-heavenly-runtime/` after resolving it inside that directory.
2. Start a fresh backend with active graph mode and real online provider environment.
3. Start MainDemo with `SIMING_HEAVENLY_AUTOTEST=1` and capture stdout asynchronously.
4. Wait for `siming_heavenly_restart_ready` while keeping Godot alive.
5. Confirm the graph contains N3/N4/N5, O2/O6, and `char_b` Event+Observation; stop the backend.
6. Start a fresh backend process against the same SQLite file; wait for Godot reconnect and `siming_heavenly_godot_complete`.
7. Stop child processes in `finally`, wait for port release, and parse the report/audit/graph state.

Use existing `ensure_backend`, `stop_backend`, `wait_for_backend_release`, and command/evidence helpers. Do not downgrade to fake candidates after provider failure.

- [ ] **Step 5: Evaluate exact live evidence**

Require result IDs `preflight_live_ready`, `authority_removed_from_surface`, `godot_object_disappeared`, `char_b_observed`, `char_b_restart_recalled`, `cross_actor_isolated`, `summary_free_context_rebuilt`, `n3_divergence`, `n4_terminal`, `n5_unreachable`, `o2_to_o6`, `online_private_confrontation`, `validator_accepted`, `resource_signature_recorded`, `single_dispatch`, `char_b_visible_reaction`, and `outcome_written_back`. Provider audit must have non-empty provider/route/model/request ID and must not equal `disabled` or `fake`.

- [ ] **Step 6: Register the Godot-required profile**

```json
{
  "schema_version": 1,
  "name": "siming-heavenly-runtime",
  "order": 78,
  "script": "scripts/verification/verify_siming_heavenly_runtime.py",
  "requires_godot": true,
  "max_attempts": 1,
  "result_artifact": ".harness/verification/siming-heavenly-runtime-report.json",
  "description": "Live online-LLM, SQLite, Authority, character-memory, and Godot proof for the complete Siming heavenly runtime"
}
```

- [ ] **Step 7: Run verifier tests and live phase gate**

Run: `python -m pytest scripts/verification/tests/test_siming_heavenly_runtime_verify.py -v`

Expected: PASS.

Run: `python scripts/verification/verify_siming_heavenly_runtime.py --preflight`

Expected: PASS without exposing secrets.

Run: `python scripts/verification/harness.py --profile siming-heavenly-runtime`

Expected: PASS with all 17 result IDs, three meaningful screenshots, matching online audit, and restart-restored memory.

- [ ] **Step 8: Commit**

```powershell
git add scripts/verification/verify_siming_heavenly_runtime.py scripts/verification/tests/test_siming_heavenly_runtime_verify.py .harness/profiles/siming-heavenly-runtime.json docs/harness.md docs/INDEX.md
git commit -m "test: prove live Siming heavenly runtime"
```

### Task 5: Run Full Regression and Confirm Archived Evidence

**Files:**
- Verify: `.harness/verification/`
- Modify only if enforced commands changed: `docs/harness.md`, `docs/INDEX.md`

**Interfaces:**
- Consumes: all seven dedicated phase profiles and live artifacts.
- Produces: broad completion evidence with matching archived run/suite identity.

- [ ] **Step 1: Run all graph phase gates in dependency order**

```powershell
python scripts/verification/harness.py --profile siming-heavenly-graph-foundation
python scripts/verification/harness.py --profile siming-six-domain-memory
python scripts/verification/harness.py --profile siming-actor-memory-read
python scripts/verification/harness.py --profile siming-story-runtime
python scripts/verification/harness.py --profile siming-resource-staging
python scripts/verification/harness.py --profile siming-adaptive-bridge
python scripts/verification/harness.py --profile siming-heavenly-runtime
```

Expected: all PASS.

- [ ] **Step 2: Run backend and mainline regression**

Run: `python -m pytest -v`

Expected: PASS.

Run: `python scripts/verification/harness.py --profile mainline-unified-runtime`

Expected: PASS.

- [ ] **Step 3: Run broad local completion proof**

Run: `python scripts/verification/harness.py --profile all`

Expected: PASS. Confirm the archived manifest and report agree on `run_id` and `suite_id`, all child processes exited, and the three Phase 7 screenshots are non-empty/meaningful.

- [ ] **Step 4: Commit any command-document synchronization**

```powershell
git add docs/harness.md docs/INDEX.md
git commit -m "docs: document Siming heavenly runtime verification"
```
