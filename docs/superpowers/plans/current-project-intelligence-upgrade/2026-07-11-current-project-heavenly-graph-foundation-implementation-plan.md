# Heavenly Graph Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the typed, bi-temporal, branch-aware, deterministic graph foundation that later Siming memory and story phases can use without adding a second runtime decision path.

**Architecture:** Introduce a Pydantic graph envelope, a stable `HeavenlyGraphPort`, and an in-memory adapter with atomic revision writes, idempotency, branch isolation, temporal reads, immutable provenance, and stable checkpoints. Bind those semantics to a reusable adapter contract suite and a dedicated backend-only Harness profile. This phase is storage foundation only: it does not wire the graph into `SimingRuntime.tick(...)`.

**Tech Stack:** Python `>=3.11`, Python 3.13 local runtime, Pydantic v2, pytest, hashlib/json from the standard library, existing Harness Engineering scripts.

## Global Constraints

- Follow `docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-11-current-project-siming-heavenly-knowledge-graph-and-story-node-design.md`.
- Preserve `SimingRuntime.tick(inputs: list[SimingInput]) -> SimingTickResult` as the only decision path.
- Do not modify `backend/app/services/siming_runtime.py`, `siming_event_pipeline.py`, `backend/app/main.py`, character memory stores, ESM, Godot, or System L6 in this phase.
- Do not add a production graph-database dependency to `backend/pyproject.toml`.
- The graph is not world authority. Phase 1 stores typed revisions and provenance but does not infer or confirm facts.
- Every node and relation revision must carry world/session/story-branch scope, valid time, recorded time, and provenance.
- Temporal intervals are half-open: `[valid_from, valid_to)`; `valid_to=None` means open-ended.
- Recorded-time queries return only revisions known at or before the requested recorded time.
- A write batch is single-scope and atomic.
- Reusing an idempotency key with identical payload returns a replay result; reusing it with different payload raises a conflict.
- A revision is immutable after write. New state is represented by the next sequential revision with `supersedes_revision`.
- Relations may reference only nodes available in the same graph scope.
- The adapter returns deep copies so callers cannot mutate stored history.
- Checkpoints are immutable snapshots and do not change after later graph writes.
- There is no delete API and no active forgetting engine in this phase.
- Domain-specific six-memory schemas, actor five-pool reads, story nodes, obligations, resources, and bridge nodes are prohibited in this phase.
- Every task ends with focused tests and a task-level commit.
- Keep new Harness profile, verification script, registry test, `docs/harness.md`, and `docs/INDEX.md` synchronized.

---

## File Structure

- `backend/app/models/siming_heavenly_graph.py`: graph scope, temporal validity, provenance, immutable node/relation revisions, write batches/results, queries, and checkpoint models.
- `backend/app/services/siming_heavenly_graph_port.py`: storage protocol and stable graph error classes.
- `backend/app/services/in_memory_heavenly_graph.py`: deterministic in-memory implementation of the port.
- `backend/tests/test_siming_heavenly_graph_models.py`: Pydantic validation and envelope tests.
- `backend/tests/heavenly_graph_contract.py`: reusable adapter contract inherited by in-memory and future production-adapter tests.
- `backend/tests/test_siming_heavenly_graph_contract.py`: concrete in-memory adapter binding.
- `scripts/verification/verify_siming_heavenly_graph_foundation.py`: focused tests plus deterministic runtime probe and structured evidence.
- `.harness/profiles/siming-heavenly-graph-foundation.json`: backend-only profile at order `72`.
- `scripts/verification/tests/test_harness_registry.py`: profile ordering and dispatch registration.
- `docs/harness.md`: command, proof surface, artifacts, and `all` ordering.
- `docs/INDEX.md`: profile and verification-script discoverability.

---

### Task 1: Define the Typed Graph Envelope

**Files:**
- Create: `backend/app/models/siming_heavenly_graph.py`
- Create: `backend/tests/test_siming_heavenly_graph_models.py`

**Interfaces:**
- Produces: `HeavenlyGraphScope`
- Produces: `GraphValidity`
- Produces: `GraphProvenance`
- Produces: `HeavenlyGraphNode` and `HeavenlyGraphRelation`
- Produces: `HeavenlyGraphWriteBatch` and `HeavenlyGraphWriteResult`
- Produces: `HeavenlyNodeQuery` and `HeavenlyRelationQuery`
- Produces: `HeavenlyGraphCheckpointRef` and `HeavenlyGraphSnapshot`
- Consumed by: Tasks 2-6.

- [ ] **Step 1: Write failing graph-model validation tests**

Create `backend/tests/test_siming_heavenly_graph_models.py`:

```python
import pytest
from pydantic import ValidationError

from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
)


def make_scope(*, branch_id: str = "branch:main") -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:demo",
        session_id="session:demo",
        story_branch_id=branch_id,
        room_id="room_demo",
        scene_id="scene_demo",
    )


def make_provenance(*, source_ref: str = "authority:event:1") -> GraphProvenance:
    return GraphProvenance(
        source_kind="authority_event",
        source_ref=source_ref,
        causation_id="cause:1",
        correlation_id="corr:1",
        producer_system="system_l6",
    )


def make_node(
    *,
    node_id: str = "fact:lamp",
    revision: int = 1,
    supersedes_revision: int | None = None,
    branch_id: str = "branch:main",
) -> HeavenlyGraphNode:
    return HeavenlyGraphNode(
        node_id=node_id,
        node_type="world_fact",
        scope=make_scope(branch_id=branch_id),
        validity=GraphValidity(valid_from=10),
        recorded_at=12,
        revision=revision,
        supersedes_revision=supersedes_revision,
        attributes={"state": "dim"},
        provenance=make_provenance(),
    )


def test_graph_validity_rejects_empty_half_open_interval() -> None:
    with pytest.raises(ValidationError, match="valid_to must be greater"):
        GraphValidity(valid_from=10, valid_to=10)


def test_first_revision_rejects_supersedes_revision() -> None:
    with pytest.raises(ValidationError, match="revision 1 cannot supersede"):
        make_node(revision=1, supersedes_revision=1)


def test_later_revision_requires_immediate_predecessor() -> None:
    with pytest.raises(ValidationError, match="immediate predecessor"):
        make_node(revision=3, supersedes_revision=1)


def test_write_batch_rejects_cross_scope_entities() -> None:
    with pytest.raises(ValidationError, match="batch scope"):
        HeavenlyGraphWriteBatch(
            transaction_id="graph_tx:1",
            idempotency_key="authority:event:1",
            scope=make_scope(branch_id="branch:main"),
            nodes=[make_node(branch_id="branch:other")],
        )


def test_write_batch_rejects_duplicate_entity_revisions() -> None:
    node = make_node()

    with pytest.raises(ValidationError, match="duplicate node revision"):
        HeavenlyGraphWriteBatch(
            transaction_id="graph_tx:1",
            idempotency_key="authority:event:1",
            scope=make_scope(),
            nodes=[node, node.model_copy(deep=True)],
        )
```

- [ ] **Step 2: Run model tests and verify the module is missing**

Run:

```powershell
python -m pytest backend/tests/test_siming_heavenly_graph_models.py -v
```

Expected: collection FAILS with `ModuleNotFoundError: No module named 'app.models.siming_heavenly_graph'`.

- [ ] **Step 3: Implement the complete typed graph envelope**

Create `backend/app/models/siming_heavenly_graph.py`:

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


GraphSourceKind = Literal[
    "authority_event",
    "world_result",
    "esm_result",
    "character_memory",
    "siming_projection",
    "runtime_outcome",
    "authored_seed",
]


class HeavenlyGraphScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    world_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    story_branch_id: str = Field(min_length=1)
    room_id: str | None = Field(default=None, min_length=1)
    scene_id: str | None = Field(default=None, min_length=1)


class GraphValidity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    valid_from: int = Field(ge=0)
    valid_to: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_half_open_interval(self) -> "GraphValidity":
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be greater than valid_from")
        return self

    def contains(self, valid_at: int) -> bool:
        return self.valid_from <= valid_at and (
            self.valid_to is None or valid_at < self.valid_to
        )


class GraphProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_kind: GraphSourceKind
    source_ref: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    producer_system: str = Field(min_length=1)
    actor_id: str | None = Field(default=None, min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)


class HeavenlyGraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(min_length=1)
    node_type: str = Field(min_length=1)
    scope: HeavenlyGraphScope
    validity: GraphValidity
    recorded_at: int = Field(ge=0)
    revision: int = Field(ge=1)
    supersedes_revision: int | None = Field(default=None, ge=1)
    attributes: dict[str, JsonValue] = Field(default_factory=dict)
    provenance: GraphProvenance

    @model_validator(mode="after")
    def validate_revision_chain(self) -> "HeavenlyGraphNode":
        if self.revision == 1 and self.supersedes_revision is not None:
            raise ValueError("revision 1 cannot supersede another revision")
        if self.revision > 1 and self.supersedes_revision != self.revision - 1:
            raise ValueError("revision must supersede its immediate predecessor")
        return self


class HeavenlyGraphRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation_id: str = Field(min_length=1)
    relation_type: str = Field(min_length=1)
    source_node_id: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    scope: HeavenlyGraphScope
    validity: GraphValidity
    recorded_at: int = Field(ge=0)
    revision: int = Field(ge=1)
    supersedes_revision: int | None = Field(default=None, ge=1)
    attributes: dict[str, JsonValue] = Field(default_factory=dict)
    provenance: GraphProvenance

    @model_validator(mode="after")
    def validate_revision_chain(self) -> "HeavenlyGraphRelation":
        if self.revision == 1 and self.supersedes_revision is not None:
            raise ValueError("revision 1 cannot supersede another revision")
        if self.revision > 1 and self.supersedes_revision != self.revision - 1:
            raise ValueError("revision must supersede its immediate predecessor")
        return self


class HeavenlyGraphWriteBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    scope: HeavenlyGraphScope
    nodes: list[HeavenlyGraphNode] = Field(default_factory=list)
    relations: list[HeavenlyGraphRelation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_batch(self) -> "HeavenlyGraphWriteBatch":
        if not self.nodes and not self.relations:
            raise ValueError("write batch must contain at least one entity")
        for entity in [*self.nodes, *self.relations]:
            if entity.scope != self.scope:
                raise ValueError("every entity must match the batch scope")
        node_revisions = [(node.node_id, node.revision) for node in self.nodes]
        if len(node_revisions) != len(set(node_revisions)):
            raise ValueError("duplicate node revision in write batch")
        relation_revisions = [
            (relation.relation_id, relation.revision) for relation in self.relations
        ]
        if len(relation_revisions) != len(set(relation_revisions)):
            raise ValueError("duplicate relation revision in write batch")
        return self


class HeavenlyGraphWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str
    idempotency_key: str
    applied: bool
    replayed: bool = False
    node_refs: list[str] = Field(default_factory=list)
    relation_refs: list[str] = Field(default_factory=list)


class HeavenlyNodeQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: HeavenlyGraphScope
    valid_at: int = Field(ge=0)
    recorded_at: int | None = Field(default=None, ge=0)
    node_ids: list[str] = Field(default_factory=list)
    node_types: list[str] = Field(default_factory=list)
    limit: int | None = Field(default=100, ge=1, le=1000)


class HeavenlyRelationQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: HeavenlyGraphScope
    valid_at: int = Field(ge=0)
    recorded_at: int | None = Field(default=None, ge=0)
    relation_ids: list[str] = Field(default_factory=list)
    relation_types: list[str] = Field(default_factory=list)
    source_node_ids: list[str] = Field(default_factory=list)
    target_node_ids: list[str] = Field(default_factory=list)
    limit: int | None = Field(default=100, ge=1, le=1000)


class HeavenlyGraphCheckpointRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    checkpoint_ref: str = Field(min_length=1)
    checkpoint_id: str = Field(min_length=1)
    scope: HeavenlyGraphScope
    valid_at: int = Field(ge=0)
    recorded_at: int = Field(ge=0)


class HeavenlyGraphSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checkpoint: HeavenlyGraphCheckpointRef
    nodes: list[HeavenlyGraphNode] = Field(default_factory=list)
    relations: list[HeavenlyGraphRelation] = Field(default_factory=list)
```

- [ ] **Step 4: Run model tests**

Run:

```powershell
python -m pytest backend/tests/test_siming_heavenly_graph_models.py -v
```

Expected: `5 passed`.

- [ ] **Step 5: Commit Task 1**

```powershell
git add backend/app/models/siming_heavenly_graph.py backend/tests/test_siming_heavenly_graph_models.py
git commit -m "feat: define Siming heavenly graph models"
```

---

### Task 2: Define the Port and Basic Deterministic Adapter

**Files:**
- Create: `backend/app/services/siming_heavenly_graph_port.py`
- Create: `backend/app/services/in_memory_heavenly_graph.py`
- Create: `backend/tests/heavenly_graph_contract.py`
- Create: `backend/tests/test_siming_heavenly_graph_contract.py`

**Interfaces:**
- Consumes: all Task 1 models.
- Produces: `HeavenlyGraphPort.write_batch(batch) -> HeavenlyGraphWriteResult`.
- Produces: `get_node(...)`, `get_relation(...)`, `query_nodes(...)`, and `query_relations(...)`.
- Produces: stable `HeavenlyGraphError` subclasses.

- [ ] **Step 1: Write the reusable basic adapter contract**

Create `backend/tests/heavenly_graph_contract.py`:

```python
from abc import ABC, abstractmethod

import pytest

from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphRelation,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
    HeavenlyNodeQuery,
    HeavenlyRelationQuery,
)
from app.services.siming_heavenly_graph_port import (
    HeavenlyGraphPort,
    HeavenlyGraphReferentialIntegrityError,
)


def graph_scope(*, branch_id: str = "branch:main") -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:demo",
        session_id="session:demo",
        story_branch_id=branch_id,
        room_id="room_demo",
        scene_id="scene_demo",
    )


def graph_provenance(*, source_ref: str = "authority:event:1") -> GraphProvenance:
    return GraphProvenance(
        source_kind="authority_event",
        source_ref=source_ref,
        causation_id="cause:1",
        correlation_id="corr:1",
        producer_system="system_l6",
        evidence_refs=[source_ref],
    )


def graph_node(
    *,
    node_id: str,
    branch_id: str = "branch:main",
    state: str = "dim",
    valid_from: int = 10,
    valid_to: int | None = None,
    recorded_at: int = 12,
    revision: int = 1,
    supersedes_revision: int | None = None,
    source_ref: str = "authority:event:1",
) -> HeavenlyGraphNode:
    return HeavenlyGraphNode(
        node_id=node_id,
        node_type="world_fact",
        scope=graph_scope(branch_id=branch_id),
        validity=GraphValidity(valid_from=valid_from, valid_to=valid_to),
        recorded_at=recorded_at,
        revision=revision,
        supersedes_revision=supersedes_revision,
        attributes={"state": state},
        provenance=graph_provenance(source_ref=source_ref),
    )


def graph_relation(
    *,
    relation_id: str,
    source_node_id: str,
    target_node_id: str,
    branch_id: str = "branch:main",
    valid_from: int = 10,
    recorded_at: int = 12,
    revision: int = 1,
    supersedes_revision: int | None = None,
) -> HeavenlyGraphRelation:
    return HeavenlyGraphRelation(
        relation_id=relation_id,
        relation_type="caused_by",
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        scope=graph_scope(branch_id=branch_id),
        validity=GraphValidity(valid_from=valid_from),
        recorded_at=recorded_at,
        revision=revision,
        supersedes_revision=supersedes_revision,
        attributes={},
        provenance=graph_provenance(source_ref=f"authority:{relation_id}"),
    )


class HeavenlyGraphContract(ABC):
    @abstractmethod
    def make_graph(self) -> HeavenlyGraphPort:
        raise NotImplementedError

    def test_basic_write_read_returns_deep_copies(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        node = graph_node(node_id="fact:lamp")

        result = graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:basic",
                idempotency_key="authority:event:basic",
                scope=scope,
                nodes=[node],
            )
        )
        loaded = graph.get_node(node_id="fact:lamp", scope=scope, valid_at=20)

        assert result.applied is True
        assert result.replayed is False
        assert loaded is not None
        assert loaded.attributes["state"] == "dim"

        loaded.attributes["state"] = "mutated_by_caller"
        reloaded = graph.get_node(node_id="fact:lamp", scope=scope, valid_at=20)
        assert reloaded is not None
        assert reloaded.attributes["state"] == "dim"

    def test_same_node_id_is_isolated_by_story_branch(self) -> None:
        graph = self.make_graph()
        main_scope = graph_scope(branch_id="branch:main")
        other_scope = graph_scope(branch_id="branch:other")

        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:main",
                idempotency_key="authority:event:main",
                scope=main_scope,
                nodes=[graph_node(node_id="fact:lamp", state="dim")],
            )
        )
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:other",
                idempotency_key="authority:event:other",
                scope=other_scope,
                nodes=[
                    graph_node(
                        node_id="fact:lamp",
                        branch_id="branch:other",
                        state="destroyed",
                    )
                ],
            )
        )

        main = graph.get_node(node_id="fact:lamp", scope=main_scope, valid_at=20)
        other = graph.get_node(node_id="fact:lamp", scope=other_scope, valid_at=20)

        assert main is not None and main.attributes["state"] == "dim"
        assert other is not None and other.attributes["state"] == "destroyed"

    def test_relation_query_is_deterministic(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        nodes = [
            graph_node(node_id="fact:cause"),
            graph_node(node_id="fact:effect"),
        ]
        relations = [
            graph_relation(
                relation_id="relation:z",
                source_node_id="fact:effect",
                target_node_id="fact:cause",
            ),
            graph_relation(
                relation_id="relation:a",
                source_node_id="fact:cause",
                target_node_id="fact:effect",
            ),
        ]

        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:relations",
                idempotency_key="authority:event:relations",
                scope=scope,
                nodes=nodes,
                relations=relations,
            )
        )

        loaded = graph.query_relations(
            HeavenlyRelationQuery(scope=scope, valid_at=20)
        )

        assert [relation.relation_id for relation in loaded] == [
            "relation:a",
            "relation:z",
        ]

    def test_node_query_filters_type_and_limit(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:query",
                idempotency_key="authority:event:query",
                scope=scope,
                nodes=[
                    graph_node(node_id="fact:b"),
                    graph_node(node_id="fact:a"),
                ],
            )
        )

        loaded = graph.query_nodes(
            HeavenlyNodeQuery(
                scope=scope,
                valid_at=20,
                node_types=["world_fact"],
                limit=1,
            )
        )

        assert [node.node_id for node in loaded] == ["fact:a"]
```

Create `backend/tests/test_siming_heavenly_graph_contract.py`:

```python
from heavenly_graph_contract import HeavenlyGraphContract

from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.siming_heavenly_graph_port import HeavenlyGraphPort


class TestInMemoryHeavenlyGraphContract(HeavenlyGraphContract):
    def make_graph(self) -> HeavenlyGraphPort:
        return InMemoryHeavenlyGraphAdapter()
```

- [ ] **Step 2: Run the contract and verify service modules are missing**

Run:

```powershell
python -m pytest backend/tests/test_siming_heavenly_graph_contract.py -v
```

Expected: collection FAILS because `app.services.siming_heavenly_graph_port` and `app.services.in_memory_heavenly_graph` do not exist.

- [ ] **Step 3: Define the stable graph port and errors**

Create `backend/app/services/siming_heavenly_graph_port.py`:

```python
from typing import Protocol

from app.models.siming_heavenly_graph import (
    HeavenlyGraphNode,
    HeavenlyGraphRelation,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
    HeavenlyGraphWriteResult,
    HeavenlyNodeQuery,
    HeavenlyRelationQuery,
)


class HeavenlyGraphError(RuntimeError):
    pass


class HeavenlyGraphRevisionConflict(HeavenlyGraphError):
    pass


class HeavenlyGraphIdempotencyConflict(HeavenlyGraphError):
    pass


class HeavenlyGraphReferentialIntegrityError(HeavenlyGraphError):
    pass


class HeavenlyGraphCheckpointConflict(HeavenlyGraphError):
    pass


class HeavenlyGraphCheckpointNotFound(HeavenlyGraphError):
    pass


class HeavenlyGraphPort(Protocol):
    def write_batch(
        self,
        batch: HeavenlyGraphWriteBatch,
    ) -> HeavenlyGraphWriteResult:
        raise NotImplementedError

    def get_node(
        self,
        *,
        node_id: str,
        scope: HeavenlyGraphScope,
        valid_at: int,
        recorded_at: int | None = None,
    ) -> HeavenlyGraphNode | None:
        raise NotImplementedError

    def get_relation(
        self,
        *,
        relation_id: str,
        scope: HeavenlyGraphScope,
        valid_at: int,
        recorded_at: int | None = None,
    ) -> HeavenlyGraphRelation | None:
        raise NotImplementedError

    def query_nodes(
        self,
        query: HeavenlyNodeQuery,
    ) -> list[HeavenlyGraphNode]:
        raise NotImplementedError

    def query_relations(
        self,
        query: HeavenlyRelationQuery,
    ) -> list[HeavenlyGraphRelation]:
        raise NotImplementedError

```

- [ ] **Step 4: Implement basic deterministic in-memory write/read**

Create `backend/app/services/in_memory_heavenly_graph.py`:

```python
from collections.abc import Sequence

from app.models.siming_heavenly_graph import (
    HeavenlyGraphNode,
    HeavenlyGraphRelation,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
    HeavenlyGraphWriteResult,
    HeavenlyNodeQuery,
    HeavenlyRelationQuery,
)
from app.services.siming_heavenly_graph_port import (
    HeavenlyGraphReferentialIntegrityError,
    HeavenlyGraphRevisionConflict,
)


ScopeKey = tuple[str, str, str, str | None, str | None]


class InMemoryHeavenlyGraphAdapter:
    def __init__(self) -> None:
        self._nodes: dict[
            tuple[ScopeKey, str],
            list[HeavenlyGraphNode],
        ] = {}
        self._relations: dict[
            tuple[ScopeKey, str],
            list[HeavenlyGraphRelation],
        ] = {}

    def write_batch(
        self,
        batch: HeavenlyGraphWriteBatch,
    ) -> HeavenlyGraphWriteResult:
        self._validate_batch_revisions(batch)
        self._validate_relation_endpoints(batch)

        for node in batch.nodes:
            key = (self._scope_key(node.scope), node.node_id)
            self._nodes.setdefault(key, []).append(node.model_copy(deep=True))
        for relation in batch.relations:
            key = (self._scope_key(relation.scope), relation.relation_id)
            self._relations.setdefault(key, []).append(
                relation.model_copy(deep=True)
            )

        return HeavenlyGraphWriteResult(
            transaction_id=batch.transaction_id,
            idempotency_key=batch.idempotency_key,
            applied=True,
            replayed=False,
            node_refs=[
                self._entity_ref("node", node.scope, node.node_id, node.revision)
                for node in batch.nodes
            ],
            relation_refs=[
                self._entity_ref(
                    "relation",
                    relation.scope,
                    relation.relation_id,
                    relation.revision,
                )
                for relation in batch.relations
            ],
        )

    def get_node(
        self,
        *,
        node_id: str,
        scope: HeavenlyGraphScope,
        valid_at: int,
        recorded_at: int | None = None,
    ) -> HeavenlyGraphNode | None:
        nodes = self.query_nodes(
            HeavenlyNodeQuery(
                scope=scope,
                valid_at=valid_at,
                recorded_at=recorded_at,
                node_ids=[node_id],
                limit=1,
            )
        )
        return nodes[0] if nodes else None

    def get_relation(
        self,
        *,
        relation_id: str,
        scope: HeavenlyGraphScope,
        valid_at: int,
        recorded_at: int | None = None,
    ) -> HeavenlyGraphRelation | None:
        relations = self.query_relations(
            HeavenlyRelationQuery(
                scope=scope,
                valid_at=valid_at,
                recorded_at=recorded_at,
                relation_ids=[relation_id],
                limit=1,
            )
        )
        return relations[0] if relations else None

    def query_nodes(
        self,
        query: HeavenlyNodeQuery,
    ) -> list[HeavenlyGraphNode]:
        scope_key = self._scope_key(query.scope)
        node_id_filter = set(query.node_ids)
        node_type_filter = set(query.node_types)
        selected: list[HeavenlyGraphNode] = []
        for (stored_scope, node_id), versions in self._nodes.items():
            if stored_scope != scope_key:
                continue
            if node_id_filter and node_id not in node_id_filter:
                continue
            node = self._latest_entity(versions)
            if node_type_filter and node.node_type not in node_type_filter:
                continue
            selected.append(node.model_copy(deep=True))
        ordered = sorted(selected, key=lambda node: node.node_id)
        return ordered if query.limit is None else ordered[: query.limit]

    def query_relations(
        self,
        query: HeavenlyRelationQuery,
    ) -> list[HeavenlyGraphRelation]:
        scope_key = self._scope_key(query.scope)
        relation_id_filter = set(query.relation_ids)
        relation_type_filter = set(query.relation_types)
        source_filter = set(query.source_node_ids)
        target_filter = set(query.target_node_ids)
        selected: list[HeavenlyGraphRelation] = []
        for (stored_scope, relation_id), versions in self._relations.items():
            if stored_scope != scope_key:
                continue
            if relation_id_filter and relation_id not in relation_id_filter:
                continue
            relation = self._latest_entity(versions)
            if (
                relation_type_filter
                and relation.relation_type not in relation_type_filter
            ):
                continue
            if source_filter and relation.source_node_id not in source_filter:
                continue
            if target_filter and relation.target_node_id not in target_filter:
                continue
            selected.append(relation.model_copy(deep=True))
        ordered = sorted(
            selected,
            key=lambda relation: relation.relation_id,
        )
        return ordered if query.limit is None else ordered[: query.limit]

    def _validate_batch_revisions(
        self,
        batch: HeavenlyGraphWriteBatch,
    ) -> None:
        for node in batch.nodes:
            versions = self._nodes.get(
                (self._scope_key(node.scope), node.node_id),
                [],
            )
            self._validate_revision(
                entity_kind="node",
                entity_id=node.node_id,
                revision=node.revision,
                supersedes_revision=node.supersedes_revision,
                existing_revisions=[item.revision for item in versions],
            )
        for relation in batch.relations:
            versions = self._relations.get(
                (self._scope_key(relation.scope), relation.relation_id),
                [],
            )
            self._validate_revision(
                entity_kind="relation",
                entity_id=relation.relation_id,
                revision=relation.revision,
                supersedes_revision=relation.supersedes_revision,
                existing_revisions=[item.revision for item in versions],
            )

    def _validate_relation_endpoints(
        self,
        batch: HeavenlyGraphWriteBatch,
    ) -> None:
        batch_node_ids = {node.node_id for node in batch.nodes}
        scope_key = self._scope_key(batch.scope)
        for relation in batch.relations:
            for endpoint in [
                relation.source_node_id,
                relation.target_node_id,
            ]:
                exists = endpoint in batch_node_ids or bool(
                    self._nodes.get((scope_key, endpoint))
                )
                if not exists:
                    raise HeavenlyGraphReferentialIntegrityError(
                        f"relation endpoint {endpoint!r} is missing in batch scope"
                    )

    def _validate_revision(
        self,
        *,
        entity_kind: str,
        entity_id: str,
        revision: int,
        supersedes_revision: int | None,
        existing_revisions: list[int],
    ) -> None:
        expected = max(existing_revisions, default=0) + 1
        expected_supersedes = expected - 1 if expected > 1 else None
        if (
            revision != expected
            or supersedes_revision != expected_supersedes
        ):
            raise HeavenlyGraphRevisionConflict(
                f"{entity_kind} {entity_id!r} expected revision {expected} "
                f"superseding {expected_supersedes!r}"
            )

    def _latest_entity(
        self,
        versions: Sequence[HeavenlyGraphNode]
        | Sequence[HeavenlyGraphRelation],
    ) -> HeavenlyGraphNode | HeavenlyGraphRelation:
        return max(versions, key=lambda item: item.revision)

    def _scope_key(self, scope: HeavenlyGraphScope) -> ScopeKey:
        return (
            scope.world_id,
            scope.session_id,
            scope.story_branch_id,
            scope.room_id,
            scope.scene_id,
        )

    def _entity_ref(
        self,
        entity_kind: str,
        scope: HeavenlyGraphScope,
        entity_id: str,
        revision: int,
    ) -> str:
        return f"{entity_kind}:{self._scope_ref(scope)}:{entity_id}@{revision}"

    def _scope_ref(self, scope: HeavenlyGraphScope) -> str:
        return ":".join(
            [
                scope.world_id,
                scope.session_id,
                scope.story_branch_id,
                scope.room_id or "_",
                scope.scene_id or "_",
            ]
        )
```

- [ ] **Step 5: Run the basic adapter contract**

Run:

```powershell
python -m pytest backend/tests/test_siming_heavenly_graph_contract.py -v
```

Expected: `4 passed`.

- [ ] **Step 6: Run model and contract tests together**

Run:

```powershell
python -m pytest backend/tests/test_siming_heavenly_graph_models.py backend/tests/test_siming_heavenly_graph_contract.py -v
```

Expected: `9 passed`.

- [ ] **Step 7: Commit Task 2**

```powershell
git add backend/app/services/siming_heavenly_graph_port.py backend/app/services/in_memory_heavenly_graph.py backend/tests/heavenly_graph_contract.py backend/tests/test_siming_heavenly_graph_contract.py
git commit -m "feat: add heavenly graph port and in-memory adapter"
```

---

### Task 3: Implement Bi-Temporal Revision Queries

**Files:**
- Modify: `backend/tests/heavenly_graph_contract.py`
- Modify: `backend/app/services/siming_heavenly_graph_port.py`
- Modify: `backend/app/services/in_memory_heavenly_graph.py`

**Interfaces:**
- Consumes: Task 2 query methods.
- Produces: half-open valid-time selection for nodes and relations.
- Produces: recorded-time “known as of” selection for nodes and relations.
- Preserves: one effective revision per entity ID, sorted deterministically.

- [ ] **Step 1: Add failing node, relation, and endpoint temporal contract tests**

Append these methods to `HeavenlyGraphContract` in `backend/tests/heavenly_graph_contract.py`:

```python
    def test_node_query_respects_valid_and_recorded_time(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:node:v1",
                idempotency_key="authority:event:node:v1",
                scope=scope,
                nodes=[
                    graph_node(
                        node_id="fact:lamp",
                        state="dim",
                        valid_from=0,
                        recorded_at=10,
                    )
                ],
            )
        )
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:node:v2",
                idempotency_key="authority:event:node:v2",
                scope=scope,
                nodes=[
                    graph_node(
                        node_id="fact:lamp",
                        state="destroyed",
                        valid_from=50,
                        recorded_at=60,
                        revision=2,
                        supersedes_revision=1,
                        source_ref="authority:event:node:v2",
                    )
                ],
            )
        )

        before_valid_change = graph.get_node(
            node_id="fact:lamp",
            scope=scope,
            valid_at=40,
            recorded_at=100,
        )
        before_recording = graph.get_node(
            node_id="fact:lamp",
            scope=scope,
            valid_at=70,
            recorded_at=59,
        )
        after_recording = graph.get_node(
            node_id="fact:lamp",
            scope=scope,
            valid_at=70,
            recorded_at=60,
        )

        assert before_valid_change is not None
        assert before_valid_change.revision == 1
        assert before_recording is not None
        assert before_recording.revision == 1
        assert after_recording is not None
        assert after_recording.revision == 2

    def test_relation_query_respects_valid_and_recorded_time(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:relation:v1",
                idempotency_key="authority:event:relation:v1",
                scope=scope,
                nodes=[
                    graph_node(node_id="fact:cause", valid_from=0),
                    graph_node(node_id="fact:effect", valid_from=0),
                ],
                relations=[
                    graph_relation(
                        relation_id="relation:cause",
                        source_node_id="fact:effect",
                        target_node_id="fact:cause",
                        valid_from=0,
                        recorded_at=10,
                    )
                ],
            )
        )
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:relation:v2",
                idempotency_key="authority:event:relation:v2",
                scope=scope,
                relations=[
                    graph_relation(
                        relation_id="relation:cause",
                        source_node_id="fact:effect",
                        target_node_id="fact:cause",
                        valid_from=50,
                        recorded_at=60,
                        revision=2,
                        supersedes_revision=1,
                    )
                ],
            )
        )

        before = graph.get_relation(
            relation_id="relation:cause",
            scope=scope,
            valid_at=70,
            recorded_at=59,
        )
        after = graph.get_relation(
            relation_id="relation:cause",
            scope=scope,
            valid_at=70,
            recorded_at=60,
        )

        assert before is not None and before.revision == 1
        assert after is not None and after.revision == 2

    def test_relation_requires_endpoints_effective_at_relation_start(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()

        with pytest.raises(
            HeavenlyGraphReferentialIntegrityError,
            match="missing in batch scope",
        ):
            graph.write_batch(
                HeavenlyGraphWriteBatch(
                    transaction_id="graph_tx:future-endpoint",
                    idempotency_key="authority:event:future-endpoint",
                    scope=scope,
                    nodes=[
                        graph_node(
                            node_id="fact:future",
                            valid_from=50,
                            recorded_at=10,
                        ),
                        graph_node(
                            node_id="fact:present",
                            valid_from=0,
                            recorded_at=10,
                        ),
                    ],
                    relations=[
                        graph_relation(
                            relation_id="relation:too-early",
                            source_node_id="fact:future",
                            target_node_id="fact:present",
                            valid_from=10,
                            recorded_at=12,
                        )
                    ],
                )
            )
```

- [ ] **Step 2: Run the temporal tests and verify latest-revision behavior is wrong**

Run:

```powershell
python -m pytest backend/tests/test_siming_heavenly_graph_contract.py -k "valid_and_recorded_time or endpoints_effective" -v
```

Expected: all three tests FAIL because Task 2 always returns the highest revision and checks only endpoint identity, not endpoint temporal availability.

- [ ] **Step 3: Route queries through effective-revision selection**

In `query_nodes(...)` replace:

```python
            node = self._latest_entity(versions)
```

with:

```python
            node = self._effective_entity(
                versions,
                valid_at=query.valid_at,
                recorded_at=query.recorded_at,
            )
            if node is None:
                continue
```

In `query_relations(...)` replace:

```python
            relation = self._latest_entity(versions)
```

with:

```python
            relation = self._effective_entity(
                versions,
                valid_at=query.valid_at,
                recorded_at=query.recorded_at,
            )
            if relation is None:
                continue
```

- [ ] **Step 4: Replace latest-only selection with bi-temporal selection**

Replace `_latest_entity(...)` with:

```python
    def _effective_entity(
        self,
        versions: Sequence[HeavenlyGraphNode]
        | Sequence[HeavenlyGraphRelation],
        *,
        valid_at: int,
        recorded_at: int | None,
    ) -> HeavenlyGraphNode | HeavenlyGraphRelation | None:
        candidates = [
            item
            for item in versions
            if item.validity.contains(valid_at)
            and (recorded_at is None or item.recorded_at <= recorded_at)
        ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda item: (item.recorded_at, item.revision),
        )
```

The selection order is recorded time first, revision second. This preserves the historical view when a correction is recorded after its valid-time start.

- [ ] **Step 5: Validate relation endpoints at relation valid/recorded time**

Replace `_validate_relation_endpoints(...)` with:

```python
    def _validate_relation_endpoints(
        self,
        batch: HeavenlyGraphWriteBatch,
    ) -> None:
        batch_nodes = {node.node_id: node for node in batch.nodes}
        scope_key = self._scope_key(batch.scope)
        for relation in batch.relations:
            for endpoint in [
                relation.source_node_id,
                relation.target_node_id,
            ]:
                batch_node = batch_nodes.get(endpoint)
                if batch_node is not None:
                    exists = (
                        batch_node.validity.contains(
                            relation.validity.valid_from
                        )
                        and batch_node.recorded_at <= relation.recorded_at
                    )
                else:
                    versions = self._nodes.get((scope_key, endpoint), [])
                    exists = (
                        self._effective_entity(
                            versions,
                            valid_at=relation.validity.valid_from,
                            recorded_at=relation.recorded_at,
                        )
                        is not None
                    )
                if not exists:
                    raise HeavenlyGraphReferentialIntegrityError(
                        f"relation endpoint {endpoint!r} is missing in batch scope "
                        "at the relation valid/recorded time"
                    )
```

- [ ] **Step 6: Run the full adapter contract**

Run:

```powershell
python -m pytest backend/tests/test_siming_heavenly_graph_contract.py -v
```

Expected: `7 passed`.

- [ ] **Step 7: Commit Task 3**

```powershell
git add backend/app/services/in_memory_heavenly_graph.py backend/tests/heavenly_graph_contract.py
git commit -m "feat: add heavenly graph temporal queries"
```

---

### Task 4: Enforce Idempotency, Atomicity, and Immutable Revision History

**Files:**
- Modify: `backend/tests/heavenly_graph_contract.py`
- Modify: `backend/app/services/in_memory_heavenly_graph.py`

**Interfaces:**
- Consumes: `HeavenlyGraphWriteBatch.idempotency_key`.
- Produces: identical replay result without a second write.
- Produces: `HeavenlyGraphIdempotencyConflict` for key reuse with different payload.
- Preserves: all-or-nothing mutation and immutable older revisions.

- [ ] **Step 1: Extend graph write error imports in the contract suite**

Replace the port import with:

```python
from app.services.siming_heavenly_graph_port import (
    HeavenlyGraphIdempotencyConflict,
    HeavenlyGraphPort,
    HeavenlyGraphReferentialIntegrityError,
)
```

- [ ] **Step 2: Add failing idempotency and integrity contract tests**

Append to `HeavenlyGraphContract`:

```python
    def test_identical_idempotency_replay_does_not_write_twice(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        batch = HeavenlyGraphWriteBatch(
            transaction_id="graph_tx:idempotent",
            idempotency_key="authority:event:idempotent",
            scope=scope,
            nodes=[graph_node(node_id="fact:lamp")],
        )

        first = graph.write_batch(batch)
        second = graph.write_batch(batch.model_copy(deep=True))
        loaded = graph.query_nodes(
            HeavenlyNodeQuery(scope=scope, valid_at=20)
        )

        assert first.applied is True and first.replayed is False
        assert second.applied is False and second.replayed is True
        assert [node.revision for node in loaded] == [1]

    def test_idempotency_key_reuse_with_different_payload_is_rejected(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:original",
                idempotency_key="authority:event:shared",
                scope=scope,
                nodes=[graph_node(node_id="fact:lamp", state="dim")],
            )
        )

        with pytest.raises(
            HeavenlyGraphIdempotencyConflict,
            match="different payload",
        ):
            graph.write_batch(
                HeavenlyGraphWriteBatch(
                    transaction_id="graph_tx:conflict",
                    idempotency_key="authority:event:shared",
                    scope=scope,
                    nodes=[
                        graph_node(
                            node_id="fact:other",
                            state="destroyed",
                        )
                    ],
                )
            )

    def test_invalid_relation_rolls_back_entire_batch(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()

        with pytest.raises(
            HeavenlyGraphReferentialIntegrityError,
            match="missing in batch scope",
        ):
            graph.write_batch(
                HeavenlyGraphWriteBatch(
                    transaction_id="graph_tx:atomic",
                    idempotency_key="authority:event:atomic",
                    scope=scope,
                    nodes=[graph_node(node_id="fact:new")],
                    relations=[
                        graph_relation(
                            relation_id="relation:invalid",
                            source_node_id="fact:new",
                            target_node_id="fact:missing",
                        )
                    ],
                )
            )

        assert graph.get_node(
            node_id="fact:new",
            scope=scope,
            valid_at=20,
        ) is None

    def test_new_revision_does_not_mutate_old_provenance(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:provenance:v1",
                idempotency_key="authority:event:provenance:v1",
                scope=scope,
                nodes=[
                    graph_node(
                        node_id="fact:lamp",
                        valid_from=0,
                        recorded_at=10,
                        source_ref="authority:event:old",
                    )
                ],
            )
        )
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:provenance:v2",
                idempotency_key="authority:event:provenance:v2",
                scope=scope,
                nodes=[
                    graph_node(
                        node_id="fact:lamp",
                        state="destroyed",
                        valid_from=50,
                        recorded_at=60,
                        revision=2,
                        supersedes_revision=1,
                        source_ref="authority:event:new",
                    )
                ],
            )
        )

        old = graph.get_node(
            node_id="fact:lamp",
            scope=scope,
            valid_at=20,
            recorded_at=100,
        )
        new = graph.get_node(
            node_id="fact:lamp",
            scope=scope,
            valid_at=70,
            recorded_at=100,
        )

        assert old is not None
        assert old.provenance.source_ref == "authority:event:old"
        assert new is not None
        assert new.provenance.source_ref == "authority:event:new"

    def test_idempotency_keys_are_scoped_by_graph_scope(self) -> None:
        graph = self.make_graph()
        main_scope = graph_scope(branch_id="branch:main")
        other_scope = graph_scope(branch_id="branch:other")

        main = graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:scope:main",
                idempotency_key="authority:event:shared-id",
                scope=main_scope,
                nodes=[graph_node(node_id="fact:lamp", state="dim")],
            )
        )
        other = graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:scope:other",
                idempotency_key="authority:event:shared-id",
                scope=other_scope,
                nodes=[
                    graph_node(
                        node_id="fact:lamp",
                        branch_id="branch:other",
                        state="destroyed",
                    )
                ],
            )
        )

        assert main.applied is True
        assert other.applied is True
```

- [ ] **Step 3: Run the new contract tests**

Run:

```powershell
python -m pytest backend/tests/test_siming_heavenly_graph_contract.py -k "idempotency or invalid_relation or old_provenance" -v
```

Expected: the idempotency tests FAIL. Atomic rollback and provenance history may already pass and remain regression coverage.

- [ ] **Step 4: Add canonical batch hashing and idempotency storage**

At the top of `backend/app/services/in_memory_heavenly_graph.py` add:

```python
import hashlib
import json
```

Extend the port imports:

```python
from app.services.siming_heavenly_graph_port import (
    HeavenlyGraphIdempotencyConflict,
    HeavenlyGraphReferentialIntegrityError,
    HeavenlyGraphRevisionConflict,
)
```

In `__init__` add:

```python
        self._idempotency: dict[
            tuple[ScopeKey, str],
            tuple[str, HeavenlyGraphWriteResult],
        ] = {}
```

- [ ] **Step 5: Check idempotency before revision validation**

At the beginning of `write_batch(...)` add:

```python
        payload_hash = self._batch_hash(batch)
        scoped_idempotency_key = (
            self._scope_key(batch.scope),
            batch.idempotency_key,
        )
        prior = self._idempotency.get(scoped_idempotency_key)
        if prior is not None:
            prior_hash, prior_result = prior
            if prior_hash != payload_hash:
                raise HeavenlyGraphIdempotencyConflict(
                    f"idempotency key {batch.idempotency_key!r} "
                    "was reused with different payload"
                )
            return prior_result.model_copy(
                update={"applied": False, "replayed": True},
                deep=True,
            )
```

Replace the direct `return HeavenlyGraphWriteResult(...)` with:

```python
        result = HeavenlyGraphWriteResult(
            transaction_id=batch.transaction_id,
            idempotency_key=batch.idempotency_key,
            applied=True,
            replayed=False,
            node_refs=[
                self._entity_ref("node", node.scope, node.node_id, node.revision)
                for node in batch.nodes
            ],
            relation_refs=[
                self._entity_ref(
                    "relation",
                    relation.scope,
                    relation.relation_id,
                    relation.revision,
                )
                for relation in batch.relations
            ],
        )
        self._idempotency[scoped_idempotency_key] = (
            payload_hash,
            result.model_copy(deep=True),
        )
        return result
```

- [ ] **Step 6: Add deterministic canonical hashing**

Add:

```python
    def _batch_hash(self, batch: HeavenlyGraphWriteBatch) -> str:
        canonical = json.dumps(
            batch.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

- [ ] **Step 7: Run the full adapter contract**

Run:

```powershell
python -m pytest backend/tests/test_siming_heavenly_graph_contract.py -v
```

Expected: `12 passed`.

- [ ] **Step 8: Commit Task 4**

```powershell
git add backend/app/services/in_memory_heavenly_graph.py backend/tests/heavenly_graph_contract.py
git commit -m "feat: enforce heavenly graph transaction integrity"
```

---

### Task 5: Add Immutable Checkpoint Snapshots

**Files:**
- Modify: `backend/tests/heavenly_graph_contract.py`
- Modify: `backend/app/services/in_memory_heavenly_graph.py`

**Interfaces:**
- Consumes: bi-temporal node/relation queries.
- Produces: `create_checkpoint(...) -> HeavenlyGraphCheckpointRef`.
- Produces: `read_checkpoint(checkpoint_ref) -> HeavenlyGraphSnapshot`.
- Produces: immutable snapshot content after later writes.

- [ ] **Step 1: Import checkpoint errors in the contract suite**

Extend the port import in `backend/tests/heavenly_graph_contract.py`:

```python
from app.services.siming_heavenly_graph_port import (
    HeavenlyGraphCheckpointConflict,
    HeavenlyGraphCheckpointNotFound,
    HeavenlyGraphIdempotencyConflict,
    HeavenlyGraphPort,
    HeavenlyGraphReferentialIntegrityError,
)
```

- [ ] **Step 2: Add failing checkpoint contract tests**

Append to `HeavenlyGraphContract`:

```python
    def test_checkpoint_is_immutable_after_later_writes(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:checkpoint:v1",
                idempotency_key="authority:event:checkpoint:v1",
                scope=scope,
                nodes=[
                    graph_node(
                        node_id="fact:lamp",
                        state="dim",
                        valid_from=0,
                        recorded_at=10,
                    )
                ],
            )
        )
        checkpoint = graph.create_checkpoint(
            checkpoint_id="checkpoint:before-destruction",
            scope=scope,
            valid_at=20,
            recorded_at=20,
        )
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:checkpoint:v2",
                idempotency_key="authority:event:checkpoint:v2",
                scope=scope,
                nodes=[
                    graph_node(
                        node_id="fact:lamp",
                        state="destroyed",
                        valid_from=0,
                        recorded_at=30,
                        revision=2,
                        supersedes_revision=1,
                        source_ref="authority:event:checkpoint:v2",
                    )
                ],
            )
        )

        snapshot = graph.read_checkpoint(checkpoint.checkpoint_ref)
        current = graph.get_node(
            node_id="fact:lamp",
            scope=scope,
            valid_at=20,
            recorded_at=40,
        )

        assert snapshot.nodes[0].revision == 1
        assert snapshot.nodes[0].attributes["state"] == "dim"
        assert current is not None and current.revision == 2

    def test_checkpoint_creation_is_idempotent_for_same_coordinates(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:checkpoint:idempotent",
                idempotency_key="authority:event:checkpoint:idempotent",
                scope=scope,
                nodes=[graph_node(node_id="fact:lamp")],
            )
        )

        first = graph.create_checkpoint(
            checkpoint_id="checkpoint:stable",
            scope=scope,
            valid_at=20,
            recorded_at=20,
        )
        second = graph.create_checkpoint(
            checkpoint_id="checkpoint:stable",
            scope=scope,
            valid_at=20,
            recorded_at=20,
        )

        assert first == second

    def test_checkpoint_id_reuse_with_different_coordinates_is_rejected(self) -> None:
        graph = self.make_graph()
        scope = graph_scope()
        graph.create_checkpoint(
            checkpoint_id="checkpoint:conflict",
            scope=scope,
            valid_at=20,
            recorded_at=20,
        )

        with pytest.raises(
            HeavenlyGraphCheckpointConflict,
            match="different coordinates",
        ):
            graph.create_checkpoint(
                checkpoint_id="checkpoint:conflict",
                scope=scope,
                valid_at=21,
                recorded_at=20,
            )

    def test_unknown_checkpoint_ref_is_rejected(self) -> None:
        graph = self.make_graph()

        with pytest.raises(
            HeavenlyGraphCheckpointNotFound,
            match="was not found",
        ):
            graph.read_checkpoint("heavenly_graph_checkpoint:missing")
```

- [ ] **Step 3: Run checkpoint tests and verify methods are absent**

Run:

```powershell
python -m pytest backend/tests/test_siming_heavenly_graph_contract.py -k "checkpoint" -v
```

Expected: checkpoint tests FAIL because `HeavenlyGraphPort` and `InMemoryHeavenlyGraphAdapter` do not yet expose checkpoint methods.

- [ ] **Step 4: Extend the port with checkpoint methods**

In `backend/app/services/siming_heavenly_graph_port.py` use this model import:

```python
from app.models.siming_heavenly_graph import (
    HeavenlyGraphCheckpointRef,
    HeavenlyGraphNode,
    HeavenlyGraphRelation,
    HeavenlyGraphScope,
    HeavenlyGraphSnapshot,
    HeavenlyGraphWriteBatch,
    HeavenlyGraphWriteResult,
    HeavenlyNodeQuery,
    HeavenlyRelationQuery,
)
```

Then append these methods to `HeavenlyGraphPort`:

```python
    def create_checkpoint(
        self,
        *,
        checkpoint_id: str,
        scope: HeavenlyGraphScope,
        valid_at: int,
        recorded_at: int,
    ) -> HeavenlyGraphCheckpointRef:
        raise NotImplementedError

    def read_checkpoint(
        self,
        checkpoint_ref: str,
    ) -> HeavenlyGraphSnapshot:
        raise NotImplementedError
```

- [ ] **Step 5: Add checkpoint storage and imports**

In `backend/app/services/in_memory_heavenly_graph.py` use this model import:

```python
from app.models.siming_heavenly_graph import (
    HeavenlyGraphCheckpointRef,
    HeavenlyGraphNode,
    HeavenlyGraphRelation,
    HeavenlyGraphScope,
    HeavenlyGraphSnapshot,
    HeavenlyGraphWriteBatch,
    HeavenlyGraphWriteResult,
    HeavenlyNodeQuery,
    HeavenlyRelationQuery,
)
```

Extend the port imports:

```python
from app.services.siming_heavenly_graph_port import (
    HeavenlyGraphCheckpointConflict,
    HeavenlyGraphCheckpointNotFound,
    HeavenlyGraphIdempotencyConflict,
    HeavenlyGraphReferentialIntegrityError,
    HeavenlyGraphRevisionConflict,
)
```

In `__init__` add:

```python
        self._checkpoints: dict[str, HeavenlyGraphSnapshot] = {}
```

- [ ] **Step 6: Implement checkpoint creation and reads**

Add:

```python
    def create_checkpoint(
        self,
        *,
        checkpoint_id: str,
        scope: HeavenlyGraphScope,
        valid_at: int,
        recorded_at: int,
    ) -> HeavenlyGraphCheckpointRef:
        checkpoint_ref = self._checkpoint_ref(checkpoint_id, scope)
        checkpoint = HeavenlyGraphCheckpointRef(
            checkpoint_ref=checkpoint_ref,
            checkpoint_id=checkpoint_id,
            scope=scope,
            valid_at=valid_at,
            recorded_at=recorded_at,
        )
        existing = self._checkpoints.get(checkpoint_ref)
        if existing is not None:
            if existing.checkpoint != checkpoint:
                raise HeavenlyGraphCheckpointConflict(
                    f"checkpoint {checkpoint_id!r} was reused "
                    "with different coordinates"
                )
            return existing.checkpoint.model_copy(deep=True)

        snapshot = HeavenlyGraphSnapshot(
            checkpoint=checkpoint,
            nodes=self.query_nodes(
                HeavenlyNodeQuery(
                    scope=scope,
                    valid_at=valid_at,
                    recorded_at=recorded_at,
                    limit=None,
                )
            ),
            relations=self.query_relations(
                HeavenlyRelationQuery(
                    scope=scope,
                    valid_at=valid_at,
                    recorded_at=recorded_at,
                    limit=None,
                )
            ),
        )
        self._checkpoints[checkpoint_ref] = snapshot.model_copy(deep=True)
        return checkpoint.model_copy(deep=True)

    def read_checkpoint(
        self,
        checkpoint_ref: str,
    ) -> HeavenlyGraphSnapshot:
        snapshot = self._checkpoints.get(checkpoint_ref)
        if snapshot is None:
            raise HeavenlyGraphCheckpointNotFound(
                f"checkpoint ref {checkpoint_ref!r} was not found"
            )
        return snapshot.model_copy(deep=True)
```

Add:

```python
    def _checkpoint_ref(
        self,
        checkpoint_id: str,
        scope: HeavenlyGraphScope,
    ) -> str:
        return (
            f"heavenly_graph_checkpoint:{self._scope_ref(scope)}:"
            f"{checkpoint_id}"
        )
```

- [ ] **Step 7: Run model and complete contract suites**

Run:

```powershell
python -m pytest backend/tests/test_siming_heavenly_graph_models.py backend/tests/test_siming_heavenly_graph_contract.py -v
```

Expected: `21 passed`.

- [ ] **Step 8: Commit Task 5**

```powershell
git add backend/app/services/siming_heavenly_graph_port.py backend/app/services/in_memory_heavenly_graph.py backend/tests/heavenly_graph_contract.py
git commit -m "feat: add heavenly graph checkpoints"
```

---

### Task 6: Add the Dedicated Harness Proof

**Files:**
- Create: `scripts/verification/verify_siming_heavenly_graph_foundation.py`
- Create: `.harness/profiles/siming-heavenly-graph-foundation.json`
- Modify: `scripts/verification/tests/test_harness_registry.py`
- Modify: `docs/harness.md`
- Modify: `docs/INDEX.md`

**Interfaces:**
- Consumes: Task 1-5 model and adapter contracts.
- Produces: `siming-heavenly-graph-foundation` profile at order `72`.
- Produces: `.harness/verification/siming-heavenly-graph-foundation-report.json`.
- Produces: `.harness/verification/siming-heavenly-graph-foundation-report.md`.
- Produces: `.harness/verification/siming-heavenly-graph-foundation-trace.json`.

- [ ] **Step 1: Add the profile to the failing registry test**

In `scripts/verification/tests/test_harness_registry.py` append `"siming-heavenly-graph-foundation"` after `"perception-input-alignment"` in `registry.profile_order`:

```python
        "perception-input-alignment",
        "siming-heavenly-graph-foundation",
```

Add:

```python
    assert registry.profiles["siming-heavenly-graph-foundation"]["script"] == (
        "scripts/verification/verify_siming_heavenly_graph_foundation.py"
    )
    assert registry.profiles["siming-heavenly-graph-foundation"]["requires_godot"] is False
```

- [ ] **Step 2: Run the registry test and verify the profile is missing**

Run:

```powershell
python -m pytest scripts/verification/tests/test_harness_registry.py::test_load_profile_registry_reads_project_profiles -v
```

Expected: FAIL because `siming-heavenly-graph-foundation` is absent from the loaded registry.

- [ ] **Step 3: Create the Harness profile**

Create `.harness/profiles/siming-heavenly-graph-foundation.json`:

```json
{
  "schema_version": 1,
  "name": "siming-heavenly-graph-foundation",
  "order": 72,
  "script": "scripts/verification/verify_siming_heavenly_graph_foundation.py",
  "requires_godot": false,
  "max_attempts": 1,
  "result_artifact": ".harness/verification/siming-heavenly-graph-foundation-report.json",
  "description": "Backend proof for the typed, bi-temporal, branch-isolated, idempotent Siming heavenly graph port and deterministic in-memory adapter"
}
```

- [ ] **Step 4: Create the focused verifier**

Create `scripts/verification/verify_siming_heavenly_graph_foundation.py`:

```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
)
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from common import (
    repo_root,
    resolve_python_exe,
    run_command,
    verification_dir,
    write_json,
    write_markdown,
)


TEST_FILES = [
    "backend/tests/test_siming_heavenly_graph_models.py",
    "backend/tests/test_siming_heavenly_graph_contract.py",
]


def _result(
    result_id: str,
    title: str,
    proved: bool,
    evidence: list[str],
    notes: str = "",
) -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def _scope(branch_id: str) -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:demo",
        session_id="session:demo",
        story_branch_id=branch_id,
        room_id="room_demo",
        scene_id="scene_demo",
    )


def _node(
    *,
    branch_id: str,
    state: str,
    revision: int,
    supersedes_revision: int | None,
    valid_from: int,
    recorded_at: int,
    source_ref: str,
) -> HeavenlyGraphNode:
    return HeavenlyGraphNode(
        node_id="fact:lamp",
        node_type="world_fact",
        scope=_scope(branch_id),
        validity=GraphValidity(valid_from=valid_from),
        recorded_at=recorded_at,
        revision=revision,
        supersedes_revision=supersedes_revision,
        attributes={"state": state},
        provenance=GraphProvenance(
            source_kind="authority_event",
            source_ref=source_ref,
            causation_id=source_ref,
            correlation_id="corr:heavenly-graph-proof",
            producer_system="system_l6",
            evidence_refs=[source_ref],
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    pytest_log = log_dir / "siming-heavenly-graph-foundation-pytest.log"
    pytest_result = run_command(
        [python_exe, "-m", "pytest", "-q", *TEST_FILES],
        project_root,
        pytest_log,
    )

    graph = InMemoryHeavenlyGraphAdapter()
    main_scope = _scope("branch:main")
    other_scope = _scope("branch:other")
    main_v1_batch = HeavenlyGraphWriteBatch(
        transaction_id="graph_tx:main:v1",
        idempotency_key="authority:event:main:v1",
        scope=main_scope,
        nodes=[
            _node(
                branch_id="branch:main",
                state="dim",
                revision=1,
                supersedes_revision=None,
                valid_from=0,
                recorded_at=10,
                source_ref="authority:event:main:v1",
            )
        ],
    )
    first_write = graph.write_batch(main_v1_batch)
    replay_write = graph.write_batch(main_v1_batch.model_copy(deep=True))
    checkpoint = graph.create_checkpoint(
        checkpoint_id="checkpoint:before-destruction",
        scope=main_scope,
        valid_at=20,
        recorded_at=20,
    )
    graph.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id="graph_tx:other:v1",
            idempotency_key="authority:event:other:v1",
            scope=other_scope,
            nodes=[
                _node(
                    branch_id="branch:other",
                    state="intact",
                    revision=1,
                    supersedes_revision=None,
                    valid_from=0,
                    recorded_at=10,
                    source_ref="authority:event:other:v1",
                )
            ],
        )
    )
    graph.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id="graph_tx:main:v2",
            idempotency_key="authority:event:main:v2",
            scope=main_scope,
            nodes=[
                _node(
                    branch_id="branch:main",
                    state="destroyed",
                    revision=2,
                    supersedes_revision=1,
                    valid_from=50,
                    recorded_at=60,
                    source_ref="authority:event:main:v2",
                )
            ],
        )
    )

    main_before_valid = graph.get_node(
        node_id="fact:lamp",
        scope=main_scope,
        valid_at=40,
        recorded_at=100,
    )
    main_before_recorded = graph.get_node(
        node_id="fact:lamp",
        scope=main_scope,
        valid_at=70,
        recorded_at=59,
    )
    main_after_recorded = graph.get_node(
        node_id="fact:lamp",
        scope=main_scope,
        valid_at=70,
        recorded_at=60,
    )
    other_branch = graph.get_node(
        node_id="fact:lamp",
        scope=other_scope,
        valid_at=70,
        recorded_at=100,
    )
    snapshot = graph.read_checkpoint(checkpoint.checkpoint_ref)

    trace_path = log_dir / "siming-heavenly-graph-foundation-trace.json"
    write_json(
        trace_path,
        {
            "first_write": first_write.model_dump(mode="json"),
            "replay_write": replay_write.model_dump(mode="json"),
            "main_before_valid": (
                main_before_valid.model_dump(mode="json")
                if main_before_valid is not None
                else None
            ),
            "main_before_recorded": (
                main_before_recorded.model_dump(mode="json")
                if main_before_recorded is not None
                else None
            ),
            "main_after_recorded": (
                main_after_recorded.model_dump(mode="json")
                if main_after_recorded is not None
                else None
            ),
            "other_branch": (
                other_branch.model_dump(mode="json")
                if other_branch is not None
                else None
            ),
            "checkpoint": snapshot.model_dump(mode="json"),
        },
    )

    temporal_ok = (
        main_before_valid is not None
        and main_before_valid.revision == 1
        and main_before_recorded is not None
        and main_before_recorded.revision == 1
        and main_after_recorded is not None
        and main_after_recorded.revision == 2
    )
    branch_ok = (
        other_branch is not None
        and other_branch.attributes["state"] == "intact"
        and main_after_recorded is not None
        and main_after_recorded.attributes["state"] == "destroyed"
    )
    idempotency_ok = (
        first_write.applied is True
        and replay_write.applied is False
        and replay_write.replayed is True
    )
    checkpoint_ok = (
        len(snapshot.nodes) == 1
        and snapshot.nodes[0].revision == 1
        and snapshot.nodes[0].attributes["state"] == "dim"
    )
    results = [
        _result(
            "focused-pytest-pass",
            "Heavenly graph focused pytest suites pass",
            pytest_result.returncode == 0,
            [str(pytest_log)],
        ),
        _result(
            "bi-temporal-query",
            "Valid-time and recorded-time queries select the correct revision",
            temporal_ok,
            [str(trace_path)],
        ),
        _result(
            "branch-isolation",
            "Identical entity IDs remain isolated by story branch",
            branch_ok,
            [str(trace_path)],
        ),
        _result(
            "idempotent-write",
            "Identical idempotency replay does not apply a second revision",
            idempotency_ok,
            [str(trace_path)],
        ),
        _result(
            "immutable-checkpoint",
            "Checkpoint content remains stable after later writes",
            checkpoint_ok,
            [str(trace_path)],
        ),
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_siming_heavenly_graph_foundation_passed": overall,
        "results": results,
        "artifacts": {
            "pytest_log": str(pytest_log),
            "trace": str(trace_path),
        },
    }
    json_path = log_dir / "siming-heavenly-graph-foundation-report.json"
    md_path = log_dir / "siming-heavenly-graph-foundation-report.md"
    write_json(json_path, report)
    write_markdown(
        md_path,
        "Siming Heavenly Graph Foundation Verification Report",
        report,
        "overall_siming_heavenly_graph_foundation_passed",
    )
    print(f"siming_heavenly_graph_foundation_report_json={json_path}")
    print(f"siming_heavenly_graph_foundation_report_md={md_path}")
    print(
        "overall_siming_heavenly_graph_foundation_passed="
        f"{overall}"
    )
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Update Harness documentation**

In the `docs/harness.md` command surface, add:

```powershell
python scripts/verification/harness.py --profile siming-heavenly-graph-foundation
```

After the `perception-input-alignment` section and before `all`, add:

```markdown
### `siming-heavenly-graph-foundation`

Backend verification for the typed Siming heavenly graph storage foundation.

Current proof includes:

- bi-temporal node and relation revision queries
- strict world/session/story-branch isolation
- immutable provenance and sequential revisions
- atomic relation endpoint validation
- idempotency replay and conflict detection
- immutable deterministic checkpoint snapshots

This profile does not prove `SimingRuntime.tick(...)` integration, actor five-pool reads, story-node orchestration, resource staging, AdaptiveBridgeNode behavior, or a production graph database.

Output:

- `.harness/verification/siming-heavenly-graph-foundation-report.json`
- `.harness/verification/siming-heavenly-graph-foundation-report.md`
- `.harness/verification/siming-heavenly-graph-foundation-trace.json`
```

Append `siming-heavenly-graph-foundation` to the ordered profile list in the `all` section.

- [ ] **Step 6: Update the documentation index**

In `docs/INDEX.md` under “验证配置” add:

```markdown
- `siming-heavenly-graph-foundation`：后端证明，覆盖司命天道图谱基础的时态查询、分支隔离、不可变来源、幂等事务和 checkpoint；不代表已接入 `SimingRuntime.tick(...)`。
```

In the verification-script list add:

```markdown
- `python scripts/verification/verify_siming_heavenly_graph_foundation.py`
```

- [ ] **Step 7: Run registry and docs tests**

Run:

```powershell
python -m pytest scripts/verification/tests/test_harness_registry.py scripts/verification/tests/test_docs_checks.py -v
```

Expected: PASS.

- [ ] **Step 8: Run the new profile**

Run:

```powershell
python scripts/verification/harness.py --profile siming-heavenly-graph-foundation
```

Expected:

```text
overall_siming_heavenly_graph_foundation_passed=True
harness_exit_code=0
```

- [ ] **Step 9: Run the docs profile**

Run:

```powershell
python scripts/verification/harness.py --profile docs
```

Expected: `overall_docs_passed=True`.

- [ ] **Step 10: Commit Task 6**

```powershell
git add .harness/profiles/siming-heavenly-graph-foundation.json scripts/verification/verify_siming_heavenly_graph_foundation.py scripts/verification/tests/test_harness_registry.py docs/harness.md docs/INDEX.md
git commit -m "test: add heavenly graph foundation harness"
```

---

### Task 7: Run the Phase 1 Completion Verification Ladder

**Files:**
- No planned source edits.
- Generated evidence remains under `.harness/verification/` and is not committed unless repository policy explicitly tracks it.

**Interfaces:**
- Consumes: Tasks 1-6.
- Produces: fresh evidence that the foundation is complete without claiming runtime integration.

- [ ] **Step 1: Check patch formatting**

Run:

```powershell
git diff --check
```

Expected: no output and exit code `0`.

- [ ] **Step 2: Run all Heavenly Graph focused tests**

Run:

```powershell
python -m pytest backend/tests/test_siming_heavenly_graph_models.py backend/tests/test_siming_heavenly_graph_contract.py -v
```

Expected: `21 passed`.

- [ ] **Step 3: Run the full backend test suite**

Run:

```powershell
python -m pytest -v
```

Expected: PASS with no failed tests.

- [ ] **Step 4: Run the dedicated profile again**

Run:

```powershell
python scripts/verification/harness.py --profile siming-heavenly-graph-foundation
```

Expected: `overall_siming_heavenly_graph_foundation_passed=True`.

- [ ] **Step 5: Run backend contract and boundaries profiles**

Run:

```powershell
python scripts/verification/harness.py --profile backend-contract
python scripts/verification/harness.py --profile boundaries
```

Expected:

```text
overall_backend_contract_passed=True
overall_boundaries_passed=True
```

- [ ] **Step 6: Run documentation verification**

Run:

```powershell
python scripts/verification/harness.py --profile docs
```

Expected: `overall_docs_passed=True`.

- [ ] **Step 7: Run broad repository verification**

Run:

```powershell
python scripts/verification/harness.py --profile all
```

Expected: `overall_harness_passed=True`. If a Godot-dependent profile cannot execute, report that exact profile as blocked and do not describe broad runtime verification as complete.

- [ ] **Step 8: Confirm the implementation stayed within Phase 1**

Run:

```powershell
git status --short
git diff --name-only HEAD~6..HEAD
```

Expected source scope:

```text
backend/app/models/siming_heavenly_graph.py
backend/app/services/siming_heavenly_graph_port.py
backend/app/services/in_memory_heavenly_graph.py
backend/tests/test_siming_heavenly_graph_models.py
backend/tests/heavenly_graph_contract.py
backend/tests/test_siming_heavenly_graph_contract.py
scripts/verification/verify_siming_heavenly_graph_foundation.py
.harness/profiles/siming-heavenly-graph-foundation.json
scripts/verification/tests/test_harness_registry.py
docs/harness.md
docs/INDEX.md
```

`backend/app/services/siming_runtime.py`, `backend/app/services/siming_event_pipeline.py`, `backend/app/main.py`, character memory stores, ESM, and Godot files must not appear.

---

## Self-Review

**Spec coverage:** Tasks 1-5 cover the Phase 1 design slice: typed graph model, temporal semantics, branch scope, immutable provenance, production-facing port, deterministic in-memory adapter, transactional writes, idempotency, and checkpoint snapshots. Task 6 adds the independent Harness proof required by design section 20.5.

**Adapter contract growth:** `HeavenlyGraphContract` is intentionally reusable. Later phases extend the same contract suite with story node lifecycle, obligation transform, outcome-port resolution, and graph-to-projection checks after those domain types exist.

**Intentional exclusions:** This plan contains no six-domain schemas, context compiler, actor-memory gateway, story-node orchestrator, resource registry, adaptive bridge, production database vendor, or runtime composition changes. Those are assigned to Phases 2-7 in the program plan.

**Authority boundary:** The graph stores typed revisions and references only. It does not confirm world facts, write character memory, perform ESM settlement, control Godot, or publish Siming catalysts.

**Open-marker scan:** Every code-editing step contains exact files, code, commands, and expected outcomes. No open implementation marker is used.

**Type consistency:** `HeavenlyGraphScope`, `GraphValidity`, `GraphProvenance`, node/relation revision fields, query fields, write result flags, checkpoint types, port signatures, adapter methods, tests, and verifier use the same names throughout.

**Test count consistency:** Task 1 adds 5 model tests. Task 2 starts with 4 adapter contract tests. Task 3 adds 3, Task 4 adds 5, and Task 5 adds 4, yielding 16 adapter contract tests and 21 focused tests total.

---

## Execution Handoff

After this plan is approved, choose one execution mode:

1. **Subagent-Driven (recommended):** use `superpowers:subagent-driven-development`, one fresh implementer per task with review between tasks.
2. **Inline Execution:** use `superpowers:executing-plans` in this session with batch checkpoints.
