# 司命 Agent Loop 运行时骨架 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把现有窄版 `SimingRuntime` 扩展成真实可运行的司命 Agent Loop 主骨架，并为故事线状态、状态树、群体模拟桥、公平主维度扩展和投影能力预留稳定接入口。

**Architecture:** 保留已经落地的 `SimingEventConsumer -> SimingRuntime.tick() -> SimingEventProducer -> AuthorityEventBus` 权威路径，把 `tick()` 内部固定为 `observe -> fact -> state tree -> fairness -> storyline -> candidate -> decision -> dispatch -> audit -> read model`。新增能力全部通过端口和注册表进入主循环，`InterventionCandidate -> InterventionDecision -> Dispatch` 仍是唯一收敛面。

**Tech Stack:** Python 3.11+, Pydantic v2, FastAPI backend, existing in-memory authority bus, pytest, harness profiles `docs`, `backend-contract`, `boundaries`, and focused backend Siming tests.

---

## File Structure

- Create: `backend/app/models/siming_runtime_state.py`
  - 承载司命 Agent Loop 内部运行态模型：`ObservedSimingEvent`、`StateTreeSnapshot`、`StorylineStateSnapshot`、`NarrativeObligationLedgerSnapshot`、`FairnessDimensionSnapshot`、`SimingCheckpoint`、`NarrativeReadModel`、projection/group bridge stub 模型。
- Modify: `backend/app/models/siming_event.py`
  - 扩展 `FairnessStateSnapshot`，允许注册式顶层公平维度进入 snapshot；扩展 `SimingTickResult`，让 tick 返回内部状态引用但不发布为总线真值。
- Create: `backend/app/services/siming_observe.py`
  - 统一总线事件到司命可观察输入，拒绝非法信封和无权消费事件。
- Create: `backend/app/services/siming_fact_core.py`
  - 维护单 tick 事实校验结果和 fact veto，不让 LLM 或 projection 绕过 locked fact。
- Create: `backend/app/services/siming_state_tree.py`
  - 从 observed events 维护当前态查询面，包含 environment、character、storyline、knowledge、group_simulation 分支形状。
- Create: `backend/app/services/siming_storyline.py`
  - 维护司命自有 `StorylineStateSnapshot` 和薄 `NarrativeObligationLedgerSnapshot`。
- Create: `backend/app/services/siming_feature_registry.py`
  - 注册 auditor、fairness dimension、policy mapping、projection strategy、group bridge mode 等扩展点。
- Create: `backend/app/services/siming_fairness_audit.py`
  - 生成带维度状态的 `FairnessStateSnapshot`，并支持 auditor 降级。
- Create: `backend/app/services/siming_projection.py`
  - 提供 `StorylineProjectionPort` 和 `GroupSimulationBridgePort` 的稳定 stub / read-only 接口。
- Create: `backend/app/services/siming_read_model.py`
  - 生成 `SimingCheckpoint` 和 `NarrativeReadModel`，只解释 loop，不反向写事实。
- Modify: `backend/app/services/siming_runtime.py`
  - 注入新端口，重排 `tick()` 内部主链，保留现有 deterministic / LLM-assisted 输出行为。
- Modify: `backend/app/services/siming_policy.py`
  - 让 policy 只解释已激活的 fairness 维度；未映射维度只能进入 audit/read model。
- Modify: `backend/app/services/siming_event_pipeline.py`
  - 保持管线顺序不变，增加对 tick read model/checkpoint 的 audit 写入。
- Modify: `backend/app/services/siming_audit_writer.py`
  - 存储 checkpoint/read model 引用查询，支持 replay 测试。
- Create: `backend/tests/test_siming_agent_loop_models.py`
- Create: `backend/tests/test_siming_observe_state_tree.py`
- Create: `backend/tests/test_siming_storyline_obligations.py`
- Create: `backend/tests/test_siming_fairness_registry.py`
- Create: `backend/tests/test_siming_projection_group_bridge.py`
- Create: `backend/tests/test_siming_agent_loop_runtime.py`
- Modify: `backend/tests/test_siming_event_pipeline.py`
- Modify: `scripts/verification/verify_phase1_slice.py`

## Implementation Rules

- 不新增第二条决策主链；所有干预仍必须经过 `InterventionCandidate -> InterventionDecision -> Dispatch`。
- `StateTreeSnapshot` 是当前态查询面，不是历史真源，不替代事件总线和 audit。
- `StorylineStateSnapshot` 与 `NarrativeObligationLedgerSnapshot` 属于司命自有 runtime state，必须在第一阶段可用。
- `GroupSimulationBridgePort` 只提供上游统计态摘要和 state tree 分支，不能直接产出 decision 或发布 `siming.*`。
- 新增公平顶层维度必须两步生效：先注册进 snapshot，再单独注册 policy / urgency / candidate mapping。
- `StorylineProjectionPort` 只能增强候选生成、排序或解释，不能绕过 policy、feasibility、audit。
- 高层干预 `band` 维持小闭集，优先扩展 `reason_tags`、`payload`、`goal_ref`、`required_downstream_path`。
- LLM provider router 已存在，本计划只把它接入更完整的上下文，不新增 LLM 旁路。

---

### Task 1: Freeze Agent Loop Runtime State Models

**Files:**
- Create: `backend/app/models/siming_runtime_state.py`
- Modify: `backend/app/models/siming_event.py`
- Create: `backend/tests/test_siming_agent_loop_models.py`

- [ ] **Step 1: Write the failing model tests**

Create `backend/tests/test_siming_agent_loop_models.py`:

```python
from app.models.authority_event import AuthorityEvent
from app.models.siming_event import FairnessStateSnapshot, SimingTickResult
from app.models.siming_runtime_state import (
    FairnessDimensionSnapshot,
    GroupSimulationBranchSnapshot,
    NarrativeObligation,
    NarrativeObligationLedgerSnapshot,
    NarrativeReadModel,
    ObservedSimingEvent,
    SimingCheckpoint,
    StateTreeNode,
    StateTreeSnapshot,
    StorylineMarker,
    StorylineStateSnapshot,
)


def make_event() -> AuthorityEvent:
    return AuthorityEvent.model_validate(
        {
            "event_id": "visual_fact:300:char_c:light_level_drop",
            "event_type": "visual_fact_event",
            "producer_ts": 300,
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "source": {"layer": "L1", "system": "visual_fact", "actor_id": "char_c"},
            "routing": {"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["siming"]},
            "priority": "p2",
            "ttl": 5000,
            "durability": "replayable",
            "causation_id": "visual_fact:300",
            "correlation_id": "visual_fact:300",
            "payload": {
                "fact_type": "light_level_drop",
                "established_fact_id": "visual_fact:300:char_c:light_level_drop",
                "target_environment_id": "env_lamp",
            },
        }
    )


def test_observed_event_keeps_bus_event_separate_from_siming_domain_state() -> None:
    event = make_event()
    observed = ObservedSimingEvent.from_authority_event(event)

    assert observed.source_event_id == event.event_id
    assert observed.event_type == "visual_fact_event"
    assert observed.payload["established_fact_id"] == "visual_fact:300:char_c:light_level_drop"
    assert observed.authority_event is event


def test_state_tree_snapshot_has_authority_separated_branches() -> None:
    snapshot = StateTreeSnapshot(
        snapshot_id="state_tree:room_demo:1",
        schema_version=1,
        producer_system="siming.state_tree",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        world_ts=300,
        sim_tick_ts=301,
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        environment=StateTreeNode(
            node_id="environment:env_lamp",
            owner_system="L1/ESM",
            authority="mirror",
            status="fresh",
            summary={"light_level": "low"},
        ),
        character=StateTreeNode(
            node_id="character:char_b",
            owner_system="character_agent",
            authority="mirror",
            status="partial",
            summary={"available": True},
        ),
        storyline=StateTreeNode(
            node_id="storyline:main",
            owner_system="siming",
            authority="editable",
            status="fresh",
            summary={"phase": "rising"},
        ),
        group_simulation=GroupSimulationBranchSnapshot(status="unavailable", summary={}),
    )

    assert snapshot.environment.authority == "mirror"
    assert snapshot.character.authority == "mirror"
    assert snapshot.storyline.authority == "editable"
    assert snapshot.group_simulation.status == "unavailable"


def test_storyline_and_obligation_models_are_siming_owned() -> None:
    storyline = StorylineStateSnapshot(
        snapshot_id="storyline:room_demo:1",
        schema_version=1,
        producer_system="siming.storyline",
        room_id="room_demo",
        world_ts=300,
        sim_tick_ts=301,
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        active_phase="rising",
        markers=[
            StorylineMarker(
                marker_id="marker:light_drop",
                marker_type="tension",
                status="active",
                entity_refs=["env_lamp"],
                reason="Established light drop should affect participation.",
            )
        ],
    )
    ledger = NarrativeObligationLedgerSnapshot(
        ledger_id="obligation:room_demo:1",
        schema_version=1,
        producer_system="siming.obligation",
        room_id="room_demo",
        world_ts=300,
        sim_tick_ts=301,
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        obligations=[
            NarrativeObligation(
                obligation_id="obl:reveal_light_drop",
                source_ref="marker:light_drop",
                obligation_type="unresolved_reveal",
                status="open",
                reason="char_b is eligible but has not received the established fact.",
            )
        ],
    )

    assert storyline.markers[0].status == "active"
    assert ledger.obligations[0].status == "open"


def test_fairness_snapshot_can_record_unmapped_top_level_dimension() -> None:
    snapshot = FairnessStateSnapshot(
        snapshot_id="fairness:visual_fact:300",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        known_fact_ids=["visual_fact:300:char_c:light_level_drop"],
        eligible_actor_ids=["char_b"],
        blocked_actor_ids=[],
        recent_intervention_ids=[],
        dimensions={
            "resource_pressure": FairnessDimensionSnapshot(
                dimension_id="resource_pressure",
                status="fresh",
                score=0.65,
                reason="Resource imbalance is observed but no policy mapping is active.",
                mapped_to_policy=False,
            )
        },
    )

    assert snapshot.dimensions["resource_pressure"].mapped_to_policy is False


def test_tick_result_can_return_runtime_state_without_publishing_truth() -> None:
    read_model = NarrativeReadModel(
        read_model_id="read:room_demo:1",
        schema_version=1,
        producer_system="siming.read_model",
        room_id="room_demo",
        scene_scope="scene_demo/zone_focus",
        world_ts=300,
        sim_tick_ts=301,
        current_state={"imbalance_type": "information_visibility"},
        focus_entities=["env_lamp", "char_b"],
        derived_from_snapshot_ref="fairness:visual_fact:300",
    )
    checkpoint = SimingCheckpoint(
        checkpoint_id="checkpoint:room_demo:1",
        schema_version=1,
        room_id="room_demo",
        world_ts=300,
        sim_tick_ts=301,
        checkpoint_type="fairness_after",
        fairness_snapshot_ref="fairness:visual_fact:300",
        state_tree_snapshot_ref="state_tree:room_demo:1",
        storyline_snapshot_ref="storyline:room_demo:1",
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
    )
    result = SimingTickResult(read_model=read_model, checkpoints=[checkpoint])

    assert result.read_model.current_state["imbalance_type"] == "information_visibility"
    assert result.checkpoints[0].checkpoint_type == "fairness_after"
```

- [ ] **Step 2: Run the model tests to verify they fail**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_agent_loop_models.py
```

Expected: FAIL because `app.models.siming_runtime_state` and the expanded `FairnessStateSnapshot.dimensions` / `SimingTickResult.read_model` fields do not exist.

- [ ] **Step 3: Add the runtime state model module**

Create `backend/app/models/siming_runtime_state.py`:

```python
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.authority_event import AuthorityEvent


StateAuthority = Literal["mirror", "editable", "read_only"]
NodeStatus = Literal["fresh", "partial", "stale", "unavailable"]
StorylineMarkerStatus = Literal["active", "stalled", "overheated", "resolved"]
ObligationStatus = Literal["open", "closed", "reopened"]
CheckpointType = Literal["fairness_before", "fairness_after"]


class ObservedSimingEvent(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    source_event_id: str
    event_type: str
    room_id: str
    scene_id: str
    zone_id: str
    producer_ts: int
    causation_id: str
    correlation_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    authority_event: AuthorityEvent

    @classmethod
    def from_authority_event(cls, event: AuthorityEvent) -> "ObservedSimingEvent":
        return cls(
            source_event_id=event.event_id,
            event_type=event.event_type,
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            producer_ts=event.producer_ts,
            causation_id=event.causation_id,
            correlation_id=event.correlation_id,
            payload=dict(event.payload),
            authority_event=event,
        )


class StateTreeNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    owner_system: str
    authority: StateAuthority
    status: NodeStatus
    summary: dict[str, Any] = Field(default_factory=dict)
    child_refs: list[str] = Field(default_factory=list)


class GroupSimulationBranchSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: NodeStatus
    summary: dict[str, Any] = Field(default_factory=dict)
    aggregate_refs: list[str] = Field(default_factory=list)


class StateTreeSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    schema_version: int
    producer_system: str
    room_id: str
    scene_id: str
    zone_id: str
    world_ts: int
    sim_tick_ts: int
    causation_id: str
    correlation_id: str
    environment: StateTreeNode
    character: StateTreeNode
    storyline: StateTreeNode
    knowledge: StateTreeNode | None = None
    group_simulation: GroupSimulationBranchSnapshot = Field(
        default_factory=lambda: GroupSimulationBranchSnapshot(status="unavailable", summary={})
    )


class StorylineMarker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marker_id: str
    marker_type: str
    status: StorylineMarkerStatus
    entity_refs: list[str] = Field(default_factory=list)
    reason: str


class StorylineStateSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    schema_version: int
    producer_system: str
    room_id: str
    world_ts: int
    sim_tick_ts: int
    causation_id: str
    correlation_id: str
    active_phase: str
    markers: list[StorylineMarker] = Field(default_factory=list)


class NarrativeObligation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obligation_id: str
    source_ref: str
    obligation_type: str
    status: ObligationStatus
    reason: str


class NarrativeObligationLedgerSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ledger_id: str
    schema_version: int
    producer_system: str
    room_id: str
    world_ts: int
    sim_tick_ts: int
    causation_id: str
    correlation_id: str
    obligations: list[NarrativeObligation] = Field(default_factory=list)


class FairnessDimensionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension_id: str
    status: NodeStatus
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str
    mapped_to_policy: bool = False


class ProjectionRunSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projection_id: str
    status: NodeStatus
    basis_state_tree_ref: str
    basis_fairness_snapshot_ref: str
    candidate_hints: list[dict[str, Any]] = Field(default_factory=list)


class SimingCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checkpoint_id: str
    schema_version: int
    room_id: str
    world_ts: int
    sim_tick_ts: int
    checkpoint_type: CheckpointType
    fairness_snapshot_ref: str
    state_tree_snapshot_ref: str
    storyline_snapshot_ref: str
    causation_id: str
    correlation_id: str


class NarrativeReadModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    read_model_id: str
    schema_version: int
    producer_system: str
    room_id: str
    scene_scope: str
    world_ts: int
    sim_tick_ts: int
    current_state: dict[str, Any] = Field(default_factory=dict)
    focus_entities: list[str] = Field(default_factory=list)
    conversation_surface: dict[str, Any] = Field(default_factory=dict)
    evidence_surface: dict[str, Any] = Field(default_factory=dict)
    intervention_surface: dict[str, Any] = Field(default_factory=dict)
    narrative_surface: dict[str, Any] = Field(default_factory=dict)
    summary_text: str = ""
    derived_from_snapshot_ref: str
```

- [ ] **Step 4: Extend existing Siming models**

Modify `backend/app/models/siming_event.py`:

```python
from app.models.siming_runtime_state import FairnessDimensionSnapshot, NarrativeReadModel, SimingCheckpoint
```

Add this field to `FairnessStateSnapshot`:

```python
    dimensions: dict[str, FairnessDimensionSnapshot] = Field(default_factory=dict)
```

Replace `SimingTickResult` with:

```python
class SimingTickResult(BaseModel):
    outputs: list[SimingOutput] = Field(default_factory=list)
    audit_records: list[SimingAuditRecord] = Field(default_factory=list)
    checkpoints: list[SimingCheckpoint] = Field(default_factory=list)
    read_model: NarrativeReadModel | None = None
```

- [ ] **Step 5: Run the model tests to verify they pass**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_agent_loop_models.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/models/siming_runtime_state.py backend/app/models/siming_event.py backend/tests/test_siming_agent_loop_models.py
git commit -m "Establish Siming agent loop runtime state models"
```

---

### Task 2: Add ObservePipeline And StateTreePort

**Files:**
- Create: `backend/app/services/siming_observe.py`
- Create: `backend/app/services/siming_state_tree.py`
- Create: `backend/tests/test_siming_observe_state_tree.py`

- [ ] **Step 1: Write the failing observe/state tree tests**

Create `backend/tests/test_siming_observe_state_tree.py`:

```python
from app.models.authority_event import AuthorityEvent
from app.services.siming_observe import SimingObservePipeline
from app.services.siming_state_tree import InMemorySimingStateTree


def make_event(event_type: str = "visual_fact_event", **payload_overrides: object) -> AuthorityEvent:
    payload = {
        "event_id": f"{event_type}:300",
        "event_type": event_type,
        "producer_ts": 300,
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "source": {"layer": "L1", "system": "visual_fact", "actor_id": "char_c"},
        "routing": {"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["siming"]},
        "priority": "p2",
        "ttl": 5000,
        "durability": "replayable",
        "causation_id": "visual_fact:300",
        "correlation_id": "visual_fact:300",
        "payload": {
            "fact_type": "light_level_drop",
            "established_fact_id": "visual_fact:300:char_c:light_level_drop",
            "target_environment_id": "env_lamp",
            "target_actor_id": "char_b",
        },
    }
    payload["payload"].update(payload_overrides)  # type: ignore[index, union-attr]
    return AuthorityEvent.model_validate(payload)


def test_observe_pipeline_accepts_allowed_authority_events_only() -> None:
    pipeline = SimingObservePipeline()

    observed = pipeline.observe([make_event()])
    ignored = pipeline.observe([make_event("presentation_event")])

    assert len(observed) == 1
    assert observed[0].source_event_id == "visual_fact_event:300"
    assert ignored == []


def test_state_tree_mirrors_environment_and_character_without_taking_authority() -> None:
    observed = SimingObservePipeline().observe([make_event()])
    tree = InMemorySimingStateTree()

    snapshot = tree.update_from_observed(observed, sim_tick_ts=301)

    assert snapshot.environment.node_id == "environment:env_lamp"
    assert snapshot.environment.owner_system == "L1/ESM"
    assert snapshot.environment.authority == "mirror"
    assert snapshot.environment.summary["established_fact_id"] == "visual_fact:300:char_c:light_level_drop"
    assert snapshot.character.node_id == "character:char_b"
    assert snapshot.character.authority == "mirror"
    assert snapshot.storyline.authority == "editable"
    assert snapshot.group_simulation.status == "unavailable"


def test_state_tree_keeps_missing_branches_explicitly_stale_or_unavailable() -> None:
    observed = SimingObservePipeline().observe([make_event(target_environment_id=None, target_actor_id=None)])
    snapshot = InMemorySimingStateTree().update_from_observed(observed, sim_tick_ts=301)

    assert snapshot.environment.status == "partial"
    assert snapshot.character.status == "partial"
    assert snapshot.group_simulation.status == "unavailable"
```

- [ ] **Step 2: Run the tests to verify failure**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_observe_state_tree.py
```

Expected: FAIL because observe/state tree services do not exist.

- [ ] **Step 3: Implement ObservePipeline**

Create `backend/app/services/siming_observe.py`:

```python
from app.models.authority_event import AuthorityEvent
from app.models.siming_runtime_state import ObservedSimingEvent


class SimingObservePipeline:
    ALLOWED_EVENT_TYPES = {
        "world_fact_event",
        "visual_fact_event",
        "esm_result_event",
        "character_behavior_event",
        "conversation_resolution_event",
        "constraint_state_event",
    }

    def observe(self, events: list[AuthorityEvent]) -> list[ObservedSimingEvent]:
        observed: list[ObservedSimingEvent] = []
        for event in events:
            if event.event_type not in self.ALLOWED_EVENT_TYPES:
                continue
            observed.append(ObservedSimingEvent.from_authority_event(event))
        return observed
```

- [ ] **Step 4: Implement StateTreePort**

Create `backend/app/services/siming_state_tree.py`:

```python
from app.models.siming_runtime_state import ObservedSimingEvent, StateTreeNode, StateTreeSnapshot


class InMemorySimingStateTree:
    def update_from_observed(
        self,
        observed_events: list[ObservedSimingEvent],
        *,
        sim_tick_ts: int,
    ) -> StateTreeSnapshot:
        event = observed_events[-1]
        environment_id = event.payload.get("target_environment_id")
        actor_id = event.payload.get("target_actor_id")
        established_fact_id = event.payload.get("established_fact_id")

        environment_status = "fresh" if environment_id else "partial"
        character_status = "fresh" if actor_id else "partial"

        return StateTreeSnapshot(
            snapshot_id=f"state_tree:{event.room_id}:{sim_tick_ts}:{event.source_event_id}",
            schema_version=1,
            producer_system="siming.state_tree",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            world_ts=event.producer_ts,
            sim_tick_ts=sim_tick_ts,
            causation_id=event.causation_id,
            correlation_id=event.correlation_id,
            environment=StateTreeNode(
                node_id=f"environment:{environment_id or 'unknown'}",
                owner_system="L1/ESM",
                authority="mirror",
                status=environment_status,
                summary={
                    "target_environment_id": environment_id,
                    "established_fact_id": established_fact_id,
                },
            ),
            character=StateTreeNode(
                node_id=f"character:{actor_id or 'unknown'}",
                owner_system="character_agent",
                authority="mirror",
                status=character_status,
                summary={"target_actor_id": actor_id},
            ),
            storyline=StateTreeNode(
                node_id=f"storyline:{event.room_id}:main",
                owner_system="siming",
                authority="editable",
                status="fresh",
                summary={"active_phase": "rising"},
            ),
            knowledge=StateTreeNode(
                node_id=f"knowledge:{event.room_id}:collective",
                owner_system="siming.knowledge_graph",
                authority="editable",
                status="partial",
                summary={"known_fact_ids": [established_fact_id] if established_fact_id else []},
            ),
        )
```

- [ ] **Step 5: Run the observe/state tree tests**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_observe_state_tree.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/services/siming_observe.py backend/app/services/siming_state_tree.py backend/tests/test_siming_observe_state_tree.py
git commit -m "Add Siming observe pipeline and state tree port"
```

---

### Task 3: Add FactCorePort

**Files:**
- Create: `backend/app/services/siming_fact_core.py`
- Create: `backend/tests/test_siming_fact_core.py`

- [ ] **Step 1: Write the failing fact core tests**

Create `backend/tests/test_siming_fact_core.py`:

```python
from app.models.authority_event import AuthorityEvent
from app.services.siming_fact_core import SimingFactCore
from app.services.siming_observe import SimingObservePipeline


def make_event(**payload_overrides: object) -> AuthorityEvent:
    payload = {
        "event_id": "visual_fact:300:char_c:light_level_drop",
        "event_type": "visual_fact_event",
        "producer_ts": 300,
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "source": {"layer": "L1", "system": "visual_fact", "actor_id": "char_c"},
        "routing": {"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["siming"]},
        "priority": "p2",
        "ttl": 5000,
        "durability": "replayable",
        "causation_id": "visual_fact:300",
        "correlation_id": "visual_fact:300",
        "payload": {
            "fact_type": "light_level_drop",
            "established_fact_id": "visual_fact:300:char_c:light_level_drop",
            "target_environment_id": "env_lamp",
        },
    }
    payload["payload"].update(payload_overrides)  # type: ignore[index, union-attr]
    return AuthorityEvent.model_validate(payload)


def test_fact_core_extracts_known_facts_from_observed_events() -> None:
    observed = SimingObservePipeline().observe([make_event()])

    result = SimingFactCore().evaluate(observed)

    assert result.accepted is True
    assert result.known_fact_ids == ["visual_fact:300:char_c:light_level_drop"]
    assert result.veto_reason is None


def test_fact_core_vetoes_locked_fact_conflicts_before_llm_or_projection() -> None:
    observed = SimingObservePipeline().observe([make_event(locked_fact_conflict=True)])

    result = SimingFactCore().evaluate(observed)

    assert result.accepted is False
    assert result.veto_reason == "locked_fact_conflict"
    assert result.known_fact_ids == []
```

- [ ] **Step 2: Run fact core tests to verify failure**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_fact_core.py
```

Expected: FAIL because `siming_fact_core.py` does not exist.

- [ ] **Step 3: Implement FactCorePort**

Create `backend/app/services/siming_fact_core.py`:

```python
from dataclasses import dataclass

from app.models.siming_runtime_state import ObservedSimingEvent


@dataclass(frozen=True)
class SimingFactCoreResult:
    accepted: bool
    known_fact_ids: list[str]
    veto_reason: str | None = None


class SimingFactCore:
    def evaluate(self, observed_events: list[ObservedSimingEvent]) -> SimingFactCoreResult:
        known_fact_ids: list[str] = []
        for event in observed_events:
            if event.payload.get("locked_fact_conflict") is True:
                return SimingFactCoreResult(
                    accepted=False,
                    known_fact_ids=[],
                    veto_reason="locked_fact_conflict",
                )
            established_fact_id = event.payload.get("established_fact_id")
            if established_fact_id:
                known_fact_ids.append(str(established_fact_id))

        return SimingFactCoreResult(
            accepted=True,
            known_fact_ids=known_fact_ids,
            veto_reason=None,
        )
```

- [ ] **Step 4: Run fact core tests**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_fact_core.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/siming_fact_core.py backend/tests/test_siming_fact_core.py
git commit -m "Add Siming fact core guard"
```

---

### Task 4: Add StorylineStatePort And NarrativeObligationLedger

**Files:**
- Create: `backend/app/services/siming_storyline.py`
- Create: `backend/tests/test_siming_storyline_obligations.py`

- [ ] **Step 1: Write the failing storyline tests**

Create `backend/tests/test_siming_storyline_obligations.py`:

```python
from app.models.siming_runtime_state import StateTreeNode, StateTreeSnapshot
from app.services.siming_storyline import InMemoryNarrativeObligationLedger, InMemoryStorylineState


def make_state_tree() -> StateTreeSnapshot:
    return StateTreeSnapshot(
        snapshot_id="state_tree:room_demo:1",
        schema_version=1,
        producer_system="siming.state_tree",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        world_ts=300,
        sim_tick_ts=301,
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        environment=StateTreeNode(
            node_id="environment:env_lamp",
            owner_system="L1/ESM",
            authority="mirror",
            status="fresh",
            summary={"established_fact_id": "visual_fact:300:char_c:light_level_drop"},
        ),
        character=StateTreeNode(
            node_id="character:char_b",
            owner_system="character_agent",
            authority="mirror",
            status="fresh",
            summary={"target_actor_id": "char_b"},
        ),
        storyline=StateTreeNode(
            node_id="storyline:room_demo:main",
            owner_system="siming",
            authority="editable",
            status="fresh",
            summary={"active_phase": "rising"},
        ),
    )


def test_storyline_state_builds_runtime_markers_from_state_tree() -> None:
    state_tree = make_state_tree()
    storyline = InMemoryStorylineState().update_from_state_tree(state_tree)

    assert storyline.active_phase == "rising"
    assert storyline.markers[0].marker_type == "information_visibility"
    assert storyline.markers[0].entity_refs == ["environment:env_lamp", "character:char_b"]


def test_obligation_ledger_turns_storyline_markers_into_trackable_debt() -> None:
    state_tree = make_state_tree()
    storyline = InMemoryStorylineState().update_from_state_tree(state_tree)
    ledger = InMemoryNarrativeObligationLedger().update_from_storyline(storyline)

    assert ledger.obligations[0].obligation_type == "unresolved_reveal"
    assert ledger.obligations[0].status == "open"
    assert ledger.obligations[0].source_ref == storyline.markers[0].marker_id
```

- [ ] **Step 2: Run the tests to verify failure**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_storyline_obligations.py
```

Expected: FAIL because `siming_storyline.py` does not exist.

- [ ] **Step 3: Implement storyline and obligation services**

Create `backend/app/services/siming_storyline.py`:

```python
from app.models.siming_runtime_state import (
    NarrativeObligation,
    NarrativeObligationLedgerSnapshot,
    StateTreeSnapshot,
    StorylineMarker,
    StorylineStateSnapshot,
)


class InMemoryStorylineState:
    def update_from_state_tree(self, state_tree: StateTreeSnapshot) -> StorylineStateSnapshot:
        marker = StorylineMarker(
            marker_id=f"marker:{state_tree.snapshot_id}:information_visibility",
            marker_type="information_visibility",
            status="active",
            entity_refs=[state_tree.environment.node_id, state_tree.character.node_id],
            reason="Established environment state has an eligible character visibility surface.",
        )
        return StorylineStateSnapshot(
            snapshot_id=f"storyline:{state_tree.room_id}:{state_tree.sim_tick_ts}",
            schema_version=1,
            producer_system="siming.storyline",
            room_id=state_tree.room_id,
            world_ts=state_tree.world_ts,
            sim_tick_ts=state_tree.sim_tick_ts,
            causation_id=state_tree.causation_id,
            correlation_id=state_tree.correlation_id,
            active_phase=str(state_tree.storyline.summary.get("active_phase", "rising")),
            markers=[marker],
        )


class InMemoryNarrativeObligationLedger:
    def update_from_storyline(self, storyline: StorylineStateSnapshot) -> NarrativeObligationLedgerSnapshot:
        obligations = [
            NarrativeObligation(
                obligation_id=f"obligation:{marker.marker_id}",
                source_ref=marker.marker_id,
                obligation_type="unresolved_reveal",
                status="open",
                reason=marker.reason,
            )
            for marker in storyline.markers
            if marker.status in {"active", "stalled"}
        ]
        return NarrativeObligationLedgerSnapshot(
            ledger_id=f"obligation:{storyline.room_id}:{storyline.sim_tick_ts}",
            schema_version=1,
            producer_system="siming.obligation",
            room_id=storyline.room_id,
            world_ts=storyline.world_ts,
            sim_tick_ts=storyline.sim_tick_ts,
            causation_id=storyline.causation_id,
            correlation_id=storyline.correlation_id,
            obligations=obligations,
        )
```

- [ ] **Step 4: Run the storyline tests**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_storyline_obligations.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/siming_storyline.py backend/tests/test_siming_storyline_obligations.py
git commit -m "Add Siming storyline state and obligation ledger"
```

---

### Task 5: Add FeatureRegistry And Fairness Dimension Activation

**Files:**
- Create: `backend/app/services/siming_feature_registry.py`
- Create: `backend/app/services/siming_fairness_audit.py`
- Modify: `backend/app/services/siming_policy.py`
- Create: `backend/tests/test_siming_fairness_registry.py`

- [ ] **Step 1: Write the failing registry and fairness tests**

Create `backend/tests/test_siming_fairness_registry.py`:

```python
from app.models.siming_event import InterventionCandidate
from app.models.siming_runtime_state import StateTreeNode, StateTreeSnapshot
from app.services.siming_fairness_audit import SimingFairnessAuditEngine
from app.services.siming_feature_registry import SimingFeatureRegistry
from app.services.siming_policy import SimingInterventionPolicy


def make_state_tree() -> StateTreeSnapshot:
    return StateTreeSnapshot(
        snapshot_id="state_tree:room_demo:1",
        schema_version=1,
        producer_system="siming.state_tree",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        world_ts=300,
        sim_tick_ts=301,
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        environment=StateTreeNode(
            node_id="environment:env_lamp",
            owner_system="L1/ESM",
            authority="mirror",
            status="fresh",
            summary={"established_fact_id": "visual_fact:300:char_c:light_level_drop"},
        ),
        character=StateTreeNode(
            node_id="character:char_b",
            owner_system="character_agent",
            authority="mirror",
            status="fresh",
            summary={"target_actor_id": "char_b"},
        ),
        storyline=StateTreeNode(
            node_id="storyline:room_demo:main",
            owner_system="siming",
            authority="editable",
            status="fresh",
            summary={"active_phase": "rising"},
        ),
    )


def make_candidate() -> InterventionCandidate:
    return InterventionCandidate(
        candidate_id="cand:1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        proposed_band="fact_reveal",
        target_actor_id="char_b",
        established_fact_ids=["visual_fact:300:char_c:light_level_drop"],
        reason_tags=["resource_pressure_sensitive"],
        source="rule",
    )


def test_registered_dimension_enters_snapshot_without_policy_mapping() -> None:
    registry = SimingFeatureRegistry()
    registry.register_fairness_dimension("resource_pressure", required=False)

    snapshot = SimingFairnessAuditEngine(registry).build_snapshot(make_state_tree())

    assert "resource_pressure" in snapshot.dimensions
    assert snapshot.dimensions["resource_pressure"].mapped_to_policy is False
    assert snapshot.dimensions["resource_pressure"].status == "fresh"


def test_unmapped_dimension_does_not_change_policy_decision() -> None:
    registry = SimingFeatureRegistry()
    registry.register_fairness_dimension("resource_pressure", required=False)
    snapshot = SimingFairnessAuditEngine(registry).build_snapshot(make_state_tree())

    result = SimingInterventionPolicy(feature_registry=registry).evaluate(make_candidate(), snapshot=snapshot)

    assert result.accepted is True
    assert "resource_pressure_policy_rejected" not in result.reasons


def test_dimension_affects_policy_only_after_mapping_is_registered() -> None:
    registry = SimingFeatureRegistry()
    registry.register_fairness_dimension("resource_pressure", required=False)
    registry.register_policy_mapping(
        dimension_id="resource_pressure",
        reject_reason_tag="resource_pressure_sensitive",
        rejection_reason="resource_pressure_policy_rejected",
    )
    snapshot = SimingFairnessAuditEngine(registry).build_snapshot(make_state_tree())

    result = SimingInterventionPolicy(feature_registry=registry).evaluate(make_candidate(), snapshot=snapshot)

    assert result.accepted is False
    assert "resource_pressure_policy_rejected" in result.reasons
    assert snapshot.dimensions["resource_pressure"].mapped_to_policy is True
```

- [ ] **Step 2: Run the tests to verify failure**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_fairness_registry.py
```

Expected: FAIL because feature registry and fairness audit engine do not exist.

- [ ] **Step 3: Implement FeatureRegistry**

Create `backend/app/services/siming_feature_registry.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class FairnessDimensionRegistration:
    dimension_id: str
    required: bool = False


@dataclass(frozen=True)
class PolicyMappingRegistration:
    dimension_id: str
    reject_reason_tag: str
    rejection_reason: str


class SimingFeatureRegistry:
    def __init__(self) -> None:
        self._fairness_dimensions: dict[str, FairnessDimensionRegistration] = {}
        self._policy_mappings: dict[str, PolicyMappingRegistration] = {}

    def register_fairness_dimension(self, dimension_id: str, *, required: bool) -> None:
        self._fairness_dimensions[dimension_id] = FairnessDimensionRegistration(
            dimension_id=dimension_id,
            required=required,
        )

    def register_policy_mapping(
        self,
        *,
        dimension_id: str,
        reject_reason_tag: str,
        rejection_reason: str,
    ) -> None:
        if dimension_id not in self._fairness_dimensions:
            self.register_fairness_dimension(dimension_id, required=False)
        self._policy_mappings[dimension_id] = PolicyMappingRegistration(
            dimension_id=dimension_id,
            reject_reason_tag=reject_reason_tag,
            rejection_reason=rejection_reason,
        )

    def fairness_dimensions(self) -> list[FairnessDimensionRegistration]:
        return list(self._fairness_dimensions.values())

    def policy_mapping_for(self, dimension_id: str) -> PolicyMappingRegistration | None:
        return self._policy_mappings.get(dimension_id)
```

- [ ] **Step 4: Implement FairnessAuditEngine**

Create `backend/app/services/siming_fairness_audit.py`:

```python
from app.models.siming_event import FairnessStateSnapshot
from app.models.siming_runtime_state import FairnessDimensionSnapshot, StateTreeSnapshot
from app.services.siming_feature_registry import SimingFeatureRegistry


class SimingFairnessAuditEngine:
    DEFAULT_DIMENSIONS = (
        "information_distribution",
        "participation_distribution",
        "conversation_access_fairness",
        "suspicion_heat_distribution",
        "evidence_visibility_distribution",
    )

    def __init__(self, feature_registry: SimingFeatureRegistry | None = None) -> None:
        self._feature_registry = feature_registry or SimingFeatureRegistry()

    def build_snapshot(self, state_tree: StateTreeSnapshot) -> FairnessStateSnapshot:
        known_fact_id = state_tree.environment.summary.get("established_fact_id")
        target_actor_id = state_tree.character.summary.get("target_actor_id")
        dimensions: dict[str, FairnessDimensionSnapshot] = {}

        for dimension_id in self.DEFAULT_DIMENSIONS:
            dimensions[dimension_id] = FairnessDimensionSnapshot(
                dimension_id=dimension_id,
                status="fresh",
                score=0.5,
                reason="Default Phase 1 fairness dimension is present.",
                mapped_to_policy=True,
            )

        for registration in self._feature_registry.fairness_dimensions():
            mapping = self._feature_registry.policy_mapping_for(registration.dimension_id)
            dimensions[registration.dimension_id] = FairnessDimensionSnapshot(
                dimension_id=registration.dimension_id,
                status="fresh",
                score=0.5,
                reason="Registered fairness dimension is observable.",
                mapped_to_policy=mapping is not None,
            )

        return FairnessStateSnapshot(
            snapshot_id=f"fairness:{state_tree.snapshot_id}",
            room_id=state_tree.room_id,
            scene_id=state_tree.scene_id,
            zone_id=state_tree.zone_id,
            causation_id=state_tree.causation_id,
            correlation_id=state_tree.correlation_id,
            known_fact_ids=[str(known_fact_id)] if known_fact_id else [],
            eligible_actor_ids=[str(target_actor_id)] if target_actor_id else [],
            blocked_actor_ids=[],
            recent_intervention_ids=[],
            dimensions=dimensions,
        )
```

- [ ] **Step 5: Wire policy to interpret only mapped dimensions**

Modify `backend/app/services/siming_policy.py`:

```python
from dataclasses import dataclass

from app.models.siming_event import FairnessStateSnapshot, InterventionCandidate
from app.services.siming_feature_registry import SimingFeatureRegistry


@dataclass(frozen=True)
class SimingPolicyResult:
    accepted: bool
    reasons: list[str]


class SimingInterventionPolicy:
    UNSAFE_REASON_TAGS = {
        "locked_truth_rewrite",
        "skip_role_autonomy",
        "skip_esm",
        "phase2_projection_required",
    }

    def __init__(self, feature_registry: SimingFeatureRegistry | None = None) -> None:
        self._feature_registry = feature_registry or SimingFeatureRegistry()

    def evaluate(
        self, candidate: InterventionCandidate, *, snapshot: FairnessStateSnapshot
    ) -> SimingPolicyResult:
        reasons: list[str] = []

        unknown_facts = [
            fact_id
            for fact_id in candidate.established_fact_ids
            if fact_id not in snapshot.known_fact_ids
        ]
        if unknown_facts:
            reasons.append("unknown_fact_reference")

        if candidate.target_actor_id:
            if candidate.target_actor_id in snapshot.blocked_actor_ids:
                reasons.append("actor_not_eligible")
            elif candidate.target_actor_id not in snapshot.eligible_actor_ids:
                reasons.append("actor_not_eligible")

        for tag in candidate.reason_tags:
            if tag in self.UNSAFE_REASON_TAGS:
                reasons.append(tag)

        if (
            candidate.proposed_band == "environment_request"
            and "esm_validated_request" not in candidate.reason_tags
        ):
            reasons.append("environment_request_requires_esm_path")

        for dimension_id, dimension in snapshot.dimensions.items():
            if not dimension.mapped_to_policy:
                continue
            mapping = self._feature_registry.policy_mapping_for(dimension_id)
            if mapping is not None and mapping.reject_reason_tag in candidate.reason_tags:
                reasons.append(mapping.rejection_reason)

        if reasons:
            return SimingPolicyResult(accepted=False, reasons=reasons)
        return SimingPolicyResult(accepted=True, reasons=["established_fact_visible"])
```

- [ ] **Step 6: Run registry/fairness tests and existing policy tests**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_fairness_registry.py tests/test_siming_llm_policy.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/services/siming_feature_registry.py backend/app/services/siming_fairness_audit.py backend/app/services/siming_policy.py backend/tests/test_siming_fairness_registry.py
git commit -m "Add Siming fairness feature registry"
```

---

### Task 6: Add Projection And Group Simulation Bridge Stubs

**Files:**
- Create: `backend/app/services/siming_projection.py`
- Create: `backend/tests/test_siming_projection_group_bridge.py`

- [ ] **Step 1: Write the failing projection/group bridge tests**

Create `backend/tests/test_siming_projection_group_bridge.py`:

```python
from app.models.siming_event import FairnessStateSnapshot
from app.models.siming_runtime_state import (
    GroupSimulationBranchSnapshot,
    NarrativeObligation,
    NarrativeObligationLedgerSnapshot,
    StateTreeNode,
    StateTreeSnapshot,
    StorylineStateSnapshot,
)
from app.services.siming_projection import StubGroupSimulationBridge, StubStorylineProjection


def make_state_tree() -> StateTreeSnapshot:
    return StateTreeSnapshot(
        snapshot_id="state_tree:room_demo:1",
        schema_version=1,
        producer_system="siming.state_tree",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        world_ts=300,
        sim_tick_ts=301,
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        environment=StateTreeNode(
            node_id="environment:env_lamp",
            owner_system="L1/ESM",
            authority="mirror",
            status="fresh",
            summary={},
        ),
        character=StateTreeNode(
            node_id="character:char_b",
            owner_system="character_agent",
            authority="mirror",
            status="fresh",
            summary={},
        ),
        storyline=StateTreeNode(
            node_id="storyline:room_demo:main",
            owner_system="siming",
            authority="editable",
            status="fresh",
            summary={},
        ),
        group_simulation=GroupSimulationBranchSnapshot(status="unavailable", summary={}),
    )


def test_group_bridge_returns_read_only_unavailable_branch_by_default() -> None:
    branch = StubGroupSimulationBridge().summarize(room_id="room_demo")

    assert branch.status == "unavailable"
    assert branch.summary["mode"] == "shape_only"


def test_storyline_projection_returns_candidate_hints_only() -> None:
    state_tree = make_state_tree()
    fairness = FairnessStateSnapshot(
        snapshot_id="fairness:1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        known_fact_ids=["visual_fact:300:char_c:light_level_drop"],
        eligible_actor_ids=["char_b"],
        blocked_actor_ids=[],
        recent_intervention_ids=[],
    )
    storyline = StorylineStateSnapshot(
        snapshot_id="storyline:1",
        schema_version=1,
        producer_system="siming.storyline",
        room_id="room_demo",
        world_ts=300,
        sim_tick_ts=301,
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        active_phase="rising",
    )
    ledger = NarrativeObligationLedgerSnapshot(
        ledger_id="obligation:1",
        schema_version=1,
        producer_system="siming.obligation",
        room_id="room_demo",
        world_ts=300,
        sim_tick_ts=301,
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        obligations=[
            NarrativeObligation(
                obligation_id="obl:1",
                source_ref="marker:1",
                obligation_type="unresolved_reveal",
                status="open",
                reason="Reveal an established fact.",
            )
        ],
    )

    projection = StubStorylineProjection().project(
        state_tree=state_tree,
        fairness=fairness,
        storyline=storyline,
        ledger=ledger,
    )

    assert projection.status == "fresh"
    assert projection.basis_state_tree_ref == "state_tree:room_demo:1"
    assert projection.basis_fairness_snapshot_ref == "fairness:1"
    assert projection.candidate_hints[0]["obligation_id"] == "obl:1"
    assert "decision_id" not in projection.candidate_hints[0]
```

- [ ] **Step 2: Run the tests to verify failure**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_projection_group_bridge.py
```

Expected: FAIL because projection service does not exist.

- [ ] **Step 3: Implement projection and group bridge stubs**

Create `backend/app/services/siming_projection.py`:

```python
from app.models.siming_event import FairnessStateSnapshot
from app.models.siming_runtime_state import (
    GroupSimulationBranchSnapshot,
    NarrativeObligationLedgerSnapshot,
    ProjectionRunSnapshot,
    StateTreeSnapshot,
    StorylineStateSnapshot,
)


class StubGroupSimulationBridge:
    def summarize(self, *, room_id: str) -> GroupSimulationBranchSnapshot:
        return GroupSimulationBranchSnapshot(
            status="unavailable",
            summary={"mode": "shape_only", "room_id": room_id},
        )


class StubStorylineProjection:
    def project(
        self,
        *,
        state_tree: StateTreeSnapshot,
        fairness: FairnessStateSnapshot,
        storyline: StorylineStateSnapshot,
        ledger: NarrativeObligationLedgerSnapshot,
    ) -> ProjectionRunSnapshot:
        hints = [
            {
                "obligation_id": obligation.obligation_id,
                "reason": obligation.reason,
                "suggested_band": "fact_reveal",
            }
            for obligation in ledger.obligations
            if obligation.status == "open"
        ]
        return ProjectionRunSnapshot(
            projection_id=f"projection:{state_tree.room_id}:{state_tree.sim_tick_ts}",
            status="fresh",
            basis_state_tree_ref=state_tree.snapshot_id,
            basis_fairness_snapshot_ref=fairness.snapshot_id,
            candidate_hints=hints,
        )
```

- [ ] **Step 4: Run projection/group bridge tests**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_projection_group_bridge.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/siming_projection.py backend/tests/test_siming_projection_group_bridge.py
git commit -m "Add Siming projection and group bridge stubs"
```

---

### Task 7: Refactor SimingRuntime Tick Into The Fixed Agent Loop Chain

**Files:**
- Modify: `backend/app/services/siming_runtime.py`
- Create: `backend/tests/test_siming_agent_loop_runtime.py`

- [ ] **Step 1: Write the failing runtime chain tests**

Create `backend/tests/test_siming_agent_loop_runtime.py`:

```python
from app.models.authority_event import AuthorityEvent
from app.models.siming_event import SimingInput
from app.services.siming_runtime import SimingRuntime


def make_visual_fact_event(**payload_overrides: object) -> AuthorityEvent:
    payload = {
        "event_id": "visual_fact:300:char_c:light_level_drop",
        "event_type": "visual_fact_event",
        "producer_ts": 300,
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "source": {"layer": "L1", "system": "visual_fact", "actor_id": "char_c"},
        "routing": {"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["siming"]},
        "priority": "p2",
        "ttl": 5000,
        "durability": "replayable",
        "causation_id": "visual_fact:300",
        "correlation_id": "visual_fact:300",
        "payload": {
            "fact_type": "light_level_drop",
            "established_fact_id": "visual_fact:300:char_c:light_level_drop",
            "target_environment_id": "env_lamp",
            "target_actor_id": "char_b",
        },
    }
    payload["payload"].update(payload_overrides)  # type: ignore[index, union-attr]
    return AuthorityEvent.model_validate(payload)


def test_tick_returns_state_tree_storyline_checkpoint_and_read_model() -> None:
    runtime = SimingRuntime()

    result = runtime.tick([SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event())])

    assert result.checkpoints
    assert result.read_model is not None
    assert result.read_model.derived_from_snapshot_ref.startswith("fairness:")
    assert any(output.output_type == "fairness_snapshot" for output in result.outputs)
    assert any(output.output_type == "intervention_candidate" for output in result.outputs)
    assert any(output.output_type == "intervention_decision" for output in result.outputs)
    assert any(output.output_type == "dispatch_intent" for output in result.outputs)


def test_tick_falls_back_to_minimum_fairness_chain_when_projection_is_stubbed() -> None:
    runtime = SimingRuntime()

    result = runtime.tick([SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event())])

    assert result.read_model is not None
    assert result.read_model.narrative_surface["projection_status"] == "fresh"
    assert any(audit.status == "recorded" for audit in result.audit_records)


def test_no_action_still_has_audit_checkpoint_and_read_model() -> None:
    runtime = SimingRuntime()
    event = make_visual_fact_event(
        event_id="world:1",
        event_type="world_fact_event",
        payload={"fact_type": "unrelated"},
    )

    result = runtime.tick([SimingInput(input_type="world_fact_event", source_event=event)])

    assert any(output.output_type == "no_action" for output in result.outputs)
    assert any(audit.status == "no_action" for audit in result.audit_records)
    assert result.checkpoints
    assert result.read_model is not None
```

- [ ] **Step 2: Run runtime chain tests to verify failure**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_agent_loop_runtime.py
```

Expected: FAIL because `SimingRuntime.tick()` does not yet populate checkpoints/read model and does not use the new ports.

- [ ] **Step 3: Add runtime collaborators without changing public constructor callers**

Modify `backend/app/services/siming_runtime.py` imports:

```python
from app.services.siming_fairness_audit import SimingFairnessAuditEngine
from app.services.siming_fact_core import SimingFactCore
from app.services.siming_observe import SimingObservePipeline
from app.services.siming_projection import StubGroupSimulationBridge, StubStorylineProjection
from app.services.siming_read_model import SimingReadModelBuilder
from app.services.siming_state_tree import InMemorySimingStateTree
from app.services.siming_storyline import InMemoryNarrativeObligationLedger, InMemoryStorylineState
```

Extend `SimingRuntime.__init__`:

```python
        observe_pipeline: SimingObservePipeline | None = None,
        fact_core: SimingFactCore | None = None,
        state_tree: InMemorySimingStateTree | None = None,
        fairness_audit: SimingFairnessAuditEngine | None = None,
        storyline_state: InMemoryStorylineState | None = None,
        obligation_ledger: InMemoryNarrativeObligationLedger | None = None,
        storyline_projection: StubStorylineProjection | None = None,
        group_bridge: StubGroupSimulationBridge | None = None,
        read_model_builder: SimingReadModelBuilder | None = None,
```

Inside `__init__`, add:

```python
        self._observe_pipeline = observe_pipeline or SimingObservePipeline()
        self._fact_core = fact_core or SimingFactCore()
        self._state_tree = state_tree or InMemorySimingStateTree()
        self._fairness_audit = fairness_audit or SimingFairnessAuditEngine()
        self._storyline_state = storyline_state or InMemoryStorylineState()
        self._obligation_ledger = obligation_ledger or InMemoryNarrativeObligationLedger()
        self._storyline_projection = storyline_projection or StubStorylineProjection()
        self._group_bridge = group_bridge or StubGroupSimulationBridge()
        self._read_model_builder = read_model_builder or SimingReadModelBuilder()
```

- [ ] **Step 4: Implement read model builder used by runtime**

Create `backend/app/services/siming_read_model.py`:

```python
from app.models.siming_event import FairnessStateSnapshot, SimingAuditRecord
from app.models.siming_runtime_state import (
    NarrativeReadModel,
    ProjectionRunSnapshot,
    SimingCheckpoint,
    StateTreeSnapshot,
    StorylineStateSnapshot,
)


class SimingReadModelBuilder:
    def build_checkpoint(
        self,
        *,
        state_tree: StateTreeSnapshot,
        fairness: FairnessStateSnapshot,
        storyline: StorylineStateSnapshot,
    ) -> SimingCheckpoint:
        return SimingCheckpoint(
            checkpoint_id=f"checkpoint:{state_tree.room_id}:{state_tree.sim_tick_ts}:{fairness.snapshot_id}",
            schema_version=1,
            room_id=state_tree.room_id,
            world_ts=state_tree.world_ts,
            sim_tick_ts=state_tree.sim_tick_ts,
            checkpoint_type="fairness_after",
            fairness_snapshot_ref=fairness.snapshot_id,
            state_tree_snapshot_ref=state_tree.snapshot_id,
            storyline_snapshot_ref=storyline.snapshot_id,
            causation_id=state_tree.causation_id,
            correlation_id=state_tree.correlation_id,
        )

    def build_read_model(
        self,
        *,
        state_tree: StateTreeSnapshot,
        fairness: FairnessStateSnapshot,
        storyline: StorylineStateSnapshot,
        projection: ProjectionRunSnapshot,
        audit_records: list[SimingAuditRecord],
    ) -> NarrativeReadModel:
        return NarrativeReadModel(
            read_model_id=f"read:{state_tree.room_id}:{state_tree.sim_tick_ts}",
            schema_version=1,
            producer_system="siming.read_model",
            room_id=state_tree.room_id,
            scene_scope=f"{state_tree.scene_id}/{state_tree.zone_id}",
            world_ts=state_tree.world_ts,
            sim_tick_ts=state_tree.sim_tick_ts,
            current_state={
                "imbalance_type": "information_visibility",
                "intervention_urgency": "normal",
                "active_phase_marker": storyline.active_phase,
            },
            focus_entities=[state_tree.environment.node_id, state_tree.character.node_id],
            intervention_surface={
                "audit_statuses": [audit.status for audit in audit_records],
            },
            narrative_surface={
                "projection_status": projection.status,
                "candidate_hint_count": len(projection.candidate_hints),
            },
            derived_from_snapshot_ref=fairness.snapshot_id,
        )
```

- [ ] **Step 5: Refactor tick to build internal loop state before existing outputs**

In `backend/app/services/siming_runtime.py`, replace the start of `tick()` with this pattern while keeping the existing per-event output branches:

```python
    def tick(self, inputs: list[SimingInput]) -> SimingTickResult:
        result = SimingTickResult()
        for siming_input in inputs:
            event = siming_input.source_event
            observed = self._observe_pipeline.observe([event])
            if not observed:
                continue
            fact_result = self._fact_core.evaluate(observed)
            if not fact_result.accepted:
                result.outputs.append(self._no_action(event))
                result.audit_records.append(
                    self._audit(
                        event,
                        status="no_action",
                        reason=f"fact_veto:{fact_result.veto_reason}",
                    )
                )
                continue

            state_tree = self._state_tree.update_from_observed(
                observed,
                sim_tick_ts=event.producer_ts + 1,
            )
            state_tree.group_simulation = self._group_bridge.summarize(room_id=event.room_id)
            fairness_snapshot = self._fairness_audit.build_snapshot(state_tree)
            storyline = self._storyline_state.update_from_state_tree(state_tree)
            ledger = self._obligation_ledger.update_from_storyline(storyline)
            projection = self._storyline_projection.project(
                state_tree=state_tree,
                fairness=fairness_snapshot,
                storyline=storyline,
                ledger=ledger,
            )

            result.outputs.append(self._fairness_snapshot(event))

            # Keep the existing candidate/decision/dispatch behavior below this line.
```

At each branch before `continue`, append:

```python
                result.checkpoints.append(
                    self._read_model_builder.build_checkpoint(
                        state_tree=state_tree,
                        fairness=fairness_snapshot,
                        storyline=storyline,
                    )
                )
                result.read_model = self._read_model_builder.build_read_model(
                    state_tree=state_tree,
                    fairness=fairness_snapshot,
                    storyline=storyline,
                    projection=projection,
                    audit_records=result.audit_records,
                )
```

Use a small private helper to avoid duplication:

```python
    def _finalize_tick_state(
        self,
        result: SimingTickResult,
        *,
        state_tree: StateTreeSnapshot,
        fairness_snapshot: FairnessStateSnapshot,
        storyline: StorylineStateSnapshot,
        projection: ProjectionRunSnapshot,
    ) -> None:
        result.checkpoints.append(
            self._read_model_builder.build_checkpoint(
                state_tree=state_tree,
                fairness=fairness_snapshot,
                storyline=storyline,
            )
        )
        result.read_model = self._read_model_builder.build_read_model(
            state_tree=state_tree,
            fairness=fairness_snapshot,
            storyline=storyline,
            projection=projection,
            audit_records=result.audit_records,
        )
```

- [ ] **Step 6: Run runtime chain and existing Siming runtime tests**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_agent_loop_runtime.py tests/test_siming_llm_runtime.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/services/siming_runtime.py backend/app/services/siming_read_model.py backend/tests/test_siming_agent_loop_runtime.py
git commit -m "Refactor Siming runtime into agent loop chain"
```

---

### Task 8: Persist Checkpoint And Read Model Evidence Through The Pipeline

**Files:**
- Modify: `backend/app/services/siming_audit_writer.py`
- Modify: `backend/app/services/siming_event_pipeline.py`
- Modify: `backend/tests/test_siming_event_pipeline.py`

- [ ] **Step 1: Add failing pipeline evidence tests**

Append to `backend/tests/test_siming_event_pipeline.py`:

```python
def test_pipeline_records_checkpoint_and_read_model_for_runtime_tick() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    pipeline = make_pipeline(bus, audit_writer)
    bus.subscribe("visual_fact_event", pipeline.handle_event)

    bus.publish(make_visual_fact_event())

    checkpoints = audit_writer.list_checkpoints(room_id="room_demo")
    read_models = audit_writer.list_read_models(room_id="room_demo")
    assert checkpoints
    assert checkpoints[0].fairness_snapshot_ref.startswith("fairness:")
    assert read_models
    assert read_models[0].derived_from_snapshot_ref.startswith("fairness:")
```

- [ ] **Step 2: Run the pipeline test to verify failure**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_event_pipeline.py::test_pipeline_records_checkpoint_and_read_model_for_runtime_tick
```

Expected: FAIL because `SimingAuditWriter` does not store checkpoints/read models.

- [ ] **Step 3: Extend audit writer storage**

Modify `backend/app/services/siming_audit_writer.py`:

```python
from app.models.siming_event import SimingAuditCorrection, SimingAuditRecord
from app.models.siming_runtime_state import NarrativeReadModel, SimingCheckpoint


class SimingAuditWriter:
    def __init__(self) -> None:
        self._records_by_id: dict[str, SimingAuditRecord] = {}
        self._checkpoints_by_id: dict[str, SimingCheckpoint] = {}
        self._read_models_by_id: dict[str, NarrativeReadModel] = {}
        self.duplicate_count = 0

    def record(self, audit: SimingAuditRecord) -> None:
        if audit.audit_id in self._records_by_id:
            self.duplicate_count += 1
            return
        self._records_by_id[audit.audit_id] = audit.model_copy(deep=True)

    def record_checkpoint(self, checkpoint: SimingCheckpoint) -> None:
        self._checkpoints_by_id[checkpoint.checkpoint_id] = checkpoint.model_copy(deep=True)

    def record_read_model(self, read_model: NarrativeReadModel) -> None:
        self._read_models_by_id[read_model.read_model_id] = read_model.model_copy(deep=True)

    def list_checkpoints(self, *, room_id: str) -> list[SimingCheckpoint]:
        return [
            checkpoint.model_copy(deep=True)
            for checkpoint in self._checkpoints_by_id.values()
            if checkpoint.room_id == room_id
        ]

    def list_read_models(self, *, room_id: str) -> list[NarrativeReadModel]:
        return [
            read_model.model_copy(deep=True)
            for read_model in self._read_models_by_id.values()
            if read_model.room_id == room_id
        ]
```

Keep the existing `append_correction`, `find_by_correlation`, and `find_by_causation` methods unchanged below this block.

- [ ] **Step 4: Record checkpoint/read model in pipeline**

Modify `backend/app/services/siming_event_pipeline.py`:

```python
        result = self._runtime.tick(inputs)
        for audit in result.audit_records:
            self._audit_writer.record(audit)
        for checkpoint in result.checkpoints:
            self._audit_writer.record_checkpoint(checkpoint)
        if result.read_model is not None:
            self._audit_writer.record_read_model(result.read_model)
        self._producer.publish_outputs(result.outputs)
```

- [ ] **Step 5: Run the pipeline tests**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_event_pipeline.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/services/siming_audit_writer.py backend/app/services/siming_event_pipeline.py backend/tests/test_siming_event_pipeline.py
git commit -m "Persist Siming loop checkpoint evidence"
```

---

### Task 9: Wire Verification And Run The Focused Gate

**Files:**
- Modify: `scripts/verification/verify_phase1_slice.py`
- Optional Modify: `docs/superpowers/plans/2026-06-17-siming-agent-loop-architecture-implementation-plan.md`

- [ ] **Step 1: Add the new tests to the phase1 slice pytest list**

Modify `scripts/verification/verify_phase1_slice.py` and add these entries after the existing Siming LLM tests:

```python
                "tests/test_siming_agent_loop_models.py",
                "tests/test_siming_observe_state_tree.py",
                "tests/test_siming_fact_core.py",
                "tests/test_siming_storyline_obligations.py",
                "tests/test_siming_fairness_registry.py",
                "tests/test_siming_projection_group_bridge.py",
                "tests/test_siming_agent_loop_runtime.py",
```

- [ ] **Step 2: Run focused backend tests**

Run:

```powershell
cd backend
python -m pytest -q `
  tests/test_siming_agent_loop_models.py `
  tests/test_siming_observe_state_tree.py `
  tests/test_siming_fact_core.py `
  tests/test_siming_storyline_obligations.py `
  tests/test_siming_fairness_registry.py `
  tests/test_siming_projection_group_bridge.py `
  tests/test_siming_agent_loop_runtime.py `
  tests/test_siming_llm_models.py `
  tests/test_siming_llm_provider.py `
  tests/test_siming_llm_policy.py `
  tests/test_siming_llm_feasibility.py `
  tests/test_siming_llm_runtime.py `
  tests/test_siming_event_pipeline.py
```

Expected: PASS.

- [ ] **Step 3: Run contract and boundary harness profiles**

Run:

```powershell
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile backend-contract
python scripts/verification/harness.py --profile boundaries
```

Expected: all three profiles PASS. `docs` must confirm the approved `2026-06-17-siming-agent-loop-architecture-design.md` spec has this matching implementation plan.

- [ ] **Step 4: Run phase1 slice if Godot is available**

Run:

```powershell
python scripts/verification/harness.py --profile phase1-slice
```

Expected: PASS when the local Godot executable is available. If Godot is unavailable, record the exact harness error in the final report and keep the backend-focused evidence from Step 2 and Step 3.

- [ ] **Step 5: Commit**

```powershell
git add scripts/verification/verify_phase1_slice.py
git commit -m "Add Siming agent loop tests to phase1 verification"
```

---

## Self-Review

- Spec coverage:
  - Agent Loop 主链由 Task 7 落地。
  - 状态树由 Task 1 和 Task 2 落地。
  - FactCorePort 由 Task 3 落地。
  - 故事线状态和薄义务账本由 Task 4 落地。
  - 公平顶层维度两步生效由 Task 5 落地。
  - Projection 和 group simulation bridge 稳定接入口由 Task 6 落地。
  - Checkpoint、audit、read model 证据链由 Task 7 和 Task 8 落地。
  - 验收和 harness 由 Task 9 落地。
- Boundary coverage:
  - LLM 仍只返回 `InterventionCandidate`，现有 provider router 不被替换。
  - `StateTreeSnapshot` 只作为查询面；环境和角色分支保持 mirror authority。
  - `GroupSimulationBridgePort` 只产生 read-only / unavailable 分支，不产出 decision。
  - 未映射公平维度只进入 snapshot/read model，不影响 policy。
- Deferred by design:
  - 完整群体模拟引擎、复杂故事线搜索、跨局长期演化、真实多 auditor 并发调度不在这份第一阶段执行计划内。
