# Phase 1.1 Durable Heavenly Graph Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing Heavenly Graph contract namespace-safe, owner-isolated, traversable with hard bounds, and durable across process restarts through SQLite.

**Architecture:** Extend the existing Pydantic schema and `HeavenlyGraphPort`, implement the same behavior in the current in-memory adapter and a new standard-library SQLite adapter, and bind both to one reusable contract suite. Keep SQLite path injection explicit and preserve existing checkpoint semantics.

**Tech Stack:** Python `>=3.11`, Pydantic v2, standard-library `sqlite3`, pytest, existing Harness Engineering.

## Global Constraints

- Source design: `docs/superpowers/specs/current-project-intelligence-upgrade/2026-08-03-current-project-siming-durable-heavenly-graph-phase2-7-integration-design.md` sections 3 and 5.
- Valid namespaces are exactly `siming_heavenly`, `actor_private`, and `resource_capability`.
- `actor_private` requires `owner_actor_id`; the other namespaces forbid it.
- Scope identity includes world, session, story branch, room, scene, namespace, and owner.
- `GraphProvenance.actor_id` is provenance, not ownership or access control.
- Traversal is deterministic, bi-temporal, scope-local, and bounded by depth/node/relation caps.
- `HeavenlySubgraphResult` is a query result, not a checkpoint or snapshot.
- SQLite uses foreign keys, WAL, one transaction per `HeavenlyGraphWriteBatch`, and versioned schema migration.
- In-memory and SQLite adapters must expose identical conflict and replay behavior.
- Use no external database package and do not silently rebuild a database on migration failure.

---

### Task 1: Extend Scope and Add Bounded Subgraph Contracts

**Files:**
- Modify: `backend/app/models/siming_heavenly_graph.py`
- Modify: `backend/app/services/siming_heavenly_graph_port.py`
- Modify: `backend/tests/test_siming_heavenly_graph_models.py`

**Interfaces:**
- Consumes: existing `HeavenlyGraphScope`, node/relation query models, and `HeavenlyGraphPort`.
- Produces: `GraphNamespace`, `HeavenlySubgraphDirection`, `HeavenlySubgraphResult`, and `HeavenlyGraphPort.query_subgraph(...)`.

- [ ] **Step 1: Write failing scope validation tests**

```python
def test_actor_private_scope_requires_owner() -> None:
    with pytest.raises(ValidationError, match="owner_actor_id"):
        HeavenlyGraphScope(
            world_id="world:demo", session_id="session:demo",
            story_branch_id="branch:main", graph_namespace="actor_private",
        )


def test_heavenly_scope_forbids_owner() -> None:
    with pytest.raises(ValidationError, match="owner_actor_id"):
        HeavenlyGraphScope(
            world_id="world:demo", session_id="session:demo",
            story_branch_id="branch:main", graph_namespace="siming_heavenly",
            owner_actor_id="char_b",
        )
```

- [ ] **Step 2: Run tests and confirm the old scope accepts invalid ownership**

Run: `python -m pytest backend/tests/test_siming_heavenly_graph_models.py -v`

Expected: FAIL because `graph_namespace` and `owner_actor_id` do not exist.

- [ ] **Step 3: Add the exact scope and query-result models**

```python
GraphNamespace = Literal["siming_heavenly", "actor_private", "resource_capability"]
HeavenlySubgraphDirection = Literal["outgoing", "incoming", "both"]


class HeavenlyGraphScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    world_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    story_branch_id: str = Field(min_length=1)
    room_id: str | None = Field(default=None, min_length=1)
    scene_id: str | None = Field(default=None, min_length=1)
    graph_namespace: GraphNamespace = "siming_heavenly"
    owner_actor_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_owner_boundary(self) -> "HeavenlyGraphScope":
        if self.graph_namespace == "actor_private" and self.owner_actor_id is None:
            raise ValueError("actor_private scope requires owner_actor_id")
        if self.graph_namespace != "actor_private" and self.owner_actor_id is not None:
            raise ValueError("owner_actor_id is only valid for actor_private scope")
        return self


class HeavenlySubgraphResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: HeavenlyGraphScope
    seed_node_ids: list[str]
    valid_at: int = Field(ge=0)
    recorded_at: int | None = Field(default=None, ge=0)
    nodes: list[HeavenlyGraphNode] = Field(default_factory=list)
    relations: list[HeavenlyGraphRelation] = Field(default_factory=list)
    truncated: bool = False
```

- [ ] **Step 4: Add the exact port method**

```python
def query_subgraph(
    self, *, scope: HeavenlyGraphScope, seed_node_ids: list[str],
    relation_types: list[str], direction: HeavenlySubgraphDirection,
    max_depth: int, valid_at: int, recorded_at: int | None,
    node_limit: int, relation_limit: int,
) -> HeavenlySubgraphResult:
    raise NotImplementedError
```

Implementations must reject `max_depth` outside `0..8`, `node_limit` outside `1..1000`, and `relation_limit` outside `1..2000` with `ValueError`.

- [ ] **Step 5: Run model tests**

Run: `python -m pytest backend/tests/test_siming_heavenly_graph_models.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/models/siming_heavenly_graph.py backend/app/services/siming_heavenly_graph_port.py backend/tests/test_siming_heavenly_graph_models.py
git commit -m "feat: extend heavenly graph scope and traversal contract"
```

### Task 2: Implement Deterministic In-Memory Traversal and Expand the Shared Contract

**Files:**
- Modify: `backend/app/services/in_memory_heavenly_graph.py`
- Modify: `backend/tests/heavenly_graph_contract.py`
- Modify: `backend/tests/test_siming_heavenly_graph_contract.py`

**Interfaces:**
- Consumes: Task 1 `query_subgraph(...)` and full seven-field scope identity.
- Produces: deterministic breadth-first traversal and adapter-independent isolation/limit assertions.

- [ ] **Step 1: Add failing reusable contract cases**

```python
def assert_bounded_subgraph_contract(adapter: HeavenlyGraphPort) -> None:
    scope = actor_scope("char_b")
    seed_chain(adapter, scope, length=4)
    result = adapter.query_subgraph(
        scope=scope, seed_node_ids=["n0"], relation_types=["CAUSED_BY"],
        direction="outgoing", max_depth=2, valid_at=20, recorded_at=20,
        node_limit=10, relation_limit=10,
    )
    assert [node.node_id for node in result.nodes] == ["n0", "n1", "n2"]
    assert [rel.relation_id for rel in result.relations] == ["r0", "r1"]
    assert result.truncated is True


def assert_owner_isolation_contract(adapter: HeavenlyGraphPort) -> None:
    seed_private_fact(adapter, actor_scope("char_b"), "memory:observed-destruction")
    result = adapter.query_subgraph(
        scope=actor_scope("char_a"), seed_node_ids=["memory:observed-destruction"],
        relation_types=[], direction="both", max_depth=1, valid_at=20,
        recorded_at=20, node_limit=10, relation_limit=10,
    )
    assert result.nodes == []
    assert result.relations == []
```

- [ ] **Step 2: Run the in-memory contract and confirm traversal is missing**

Run: `python -m pytest backend/tests/test_siming_heavenly_graph_contract.py -v`

Expected: FAIL with `AttributeError` for `query_subgraph`.

- [ ] **Step 3: Extend `ScopeKey` and implement bounded breadth-first traversal**

```python
ScopeKey = tuple[str, str, str, str | None, str | None, str, str | None]

def _scope_key(self, scope: HeavenlyGraphScope) -> ScopeKey:
    return (
        scope.world_id, scope.session_id, scope.story_branch_id,
        scope.room_id, scope.scene_id, scope.graph_namespace,
        scope.owner_actor_id,
    )
```

`query_subgraph(...)` must load only effective revisions through `query_nodes`/`query_relations`, sort each frontier by node ID, sort accepted relations by relation ID, stop at all three bounds, include a present seed node at depth zero, and set `truncated=True` whenever an unseen reachable entity is excluded by depth or size limits.

- [ ] **Step 4: Run the shared in-memory contract**

Run: `python -m pytest backend/tests/test_siming_heavenly_graph_contract.py -v`

Expected: PASS for the old contract plus namespace, owner, direction, bi-temporal, deterministic-order, and truncation cases.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/in_memory_heavenly_graph.py backend/tests/heavenly_graph_contract.py backend/tests/test_siming_heavenly_graph_contract.py
git commit -m "feat: add bounded heavenly graph traversal"
```

### Task 3: Add the SQLite Adapter and Restart Contract

**Files:**
- Create: `backend/app/services/sqlite_heavenly_graph.py`
- Create: `backend/tests/test_sqlite_heavenly_graph_contract.py`
- Modify: `backend/tests/heavenly_graph_contract.py`

**Interfaces:**
- Consumes: complete `HeavenlyGraphPort` and shared adapter contract.
- Produces: `SQLiteHeavenlyGraphAdapter(database_path: str | Path)` with `close()` and persistent contract parity.

- [ ] **Step 1: Bind the shared contract to a missing SQLite adapter**

```python
@pytest.fixture
def adapter(tmp_path: Path):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / "heavenly.sqlite3")
    yield graph
    graph.close()


def test_sqlite_adapter_contract(adapter: SQLiteHeavenlyGraphAdapter) -> None:
    assert_complete_heavenly_graph_contract(adapter)
```

- [ ] **Step 2: Add an explicit restart test**

```python
def test_sqlite_restart_restores_revisions_checkpoint_and_audit_refs(tmp_path: Path) -> None:
    path = tmp_path / "heavenly.sqlite3"
    first = SQLiteHeavenlyGraphAdapter(path)
    scope, checkpoint_ref = seed_restart_case(first)
    first.close()
    reopened = SQLiteHeavenlyGraphAdapter(path)
    assert reopened.get_node(node_id="fact:letter", scope=scope, valid_at=50).revision == 2
    assert reopened.read_checkpoint(checkpoint_ref).nodes[0].revision == 1
    assert reopened.get_node(node_id="fact:letter", scope=scope, valid_at=50).provenance.evidence_refs == ["authority:destroy:1"]
    reopened.close()
```

- [ ] **Step 3: Run tests and confirm the adapter is absent**

Run: `python -m pytest backend/tests/test_sqlite_heavenly_graph_contract.py -v`

Expected: FAIL with `ModuleNotFoundError: app.services.sqlite_heavenly_graph`.

- [ ] **Step 4: Implement the minimal durable schema**

Use `sqlite3.connect(str(database_path))`, `PRAGMA foreign_keys = ON`, `PRAGMA journal_mode = WAL`, and a `schema_version(version INTEGER PRIMARY KEY)` table. Store immutable node/relation revisions as canonical JSON plus indexed scope/entity/revision/time columns; store idempotency payload hashes/results, transaction IDs, checkpoint metadata, and checkpoint entity refs. Execute one `BEGIN IMMEDIATE`/commit per write batch and rollback on every exception.

```python
class SQLiteHeavenlyGraphAdapter:
    SCHEMA_VERSION = 1

    def __init__(self, database_path: str | Path) -> None:
        self._connection = sqlite3.connect(str(database_path))
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._migrate()

    def close(self) -> None:
        self._connection.close()
```

Reuse the shared scope-key serialization and the existing error types. Unknown future schema versions must raise `HeavenlyGraphError`; no table drop or implicit rebuild is allowed.

- [ ] **Step 5: Run both adapter bindings**

Run: `python -m pytest backend/tests/test_siming_heavenly_graph_contract.py backend/tests/test_sqlite_heavenly_graph_contract.py -v`

Expected: PASS with identical revision, idempotency, referential-integrity, checkpoint, temporal, isolation, and traversal behavior.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/services/sqlite_heavenly_graph.py backend/tests/heavenly_graph_contract.py backend/tests/test_sqlite_heavenly_graph_contract.py
git commit -m "feat: add durable SQLite heavenly graph adapter"
```

### Task 4: Extend Focused Verification and Documentation

**Files:**
- Modify: `scripts/verification/verify_siming_heavenly_graph_foundation.py`
- Modify: `.harness/profiles/siming-heavenly-graph-foundation.json`
- Modify: `docs/harness.md`
- Modify: `docs/INDEX.md`

**Interfaces:**
- Consumes: both adapter bindings and restart test from Task 3.
- Produces: one dedicated report proving the durable Phase 1.1 exit gate.

- [ ] **Step 1: Extend the verifier test file list and runtime trace**

```python
TEST_FILES = [
    "backend/tests/test_siming_heavenly_graph_models.py",
    "backend/tests/test_siming_heavenly_graph_contract.py",
    "backend/tests/test_sqlite_heavenly_graph_contract.py",
]
```

The verifier must create a temporary SQLite file under `.harness/verification/`, write `actor_private:char_b` data and a checkpoint, close/reopen the adapter, query a bounded subgraph, and report `namespace_owner_isolation`, `bounded_subgraph`, `sqlite_restart`, and `adapter_contract_parity` results.

- [ ] **Step 2: Update the profile description and docs command**

Set the profile description to `Backend proof for namespace-safe, owner-isolated, bi-temporal, bounded, restart-durable Heavenly Graph adapters` and document:

```powershell
python scripts/verification/harness.py --profile siming-heavenly-graph-foundation
```

- [ ] **Step 3: Run focused and dedicated verification**

Run: `python -m pytest backend/tests/test_siming_heavenly_graph_models.py backend/tests/test_siming_heavenly_graph_contract.py backend/tests/test_sqlite_heavenly_graph_contract.py -v`

Expected: PASS.

Run: `python scripts/verification/harness.py --profile siming-heavenly-graph-foundation`

Expected: PASS and a report at `.harness/verification/siming-heavenly-graph-foundation-report.json` containing all four new result IDs.

- [ ] **Step 4: Commit**

```powershell
git add scripts/verification/verify_siming_heavenly_graph_foundation.py .harness/profiles/siming-heavenly-graph-foundation.json docs/harness.md docs/INDEX.md
git commit -m "test: prove durable heavenly graph foundation"
```
