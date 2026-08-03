# Phase 3 Actor Five-Pool Graph Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `char_b` long-term Event, Observation, Knowledge, Social, and Higher-Order memory onto an actor-private durable graph while preserving existing character cognition and keeping Siming access read-only.

**Architecture:** Reuse `CharacterAgentMemoryStore` as the existing validated event-to-record normalizer, persist its typed records into `actor_private:<actor_id>`, and project graph recall back into `CharacterMemoryRecordBundle`. Route only allowlisted heavy actors to the graph-backed store; keep working memory transient and keep `char_a` on the light store.

**Tech Stack:** Python `>=3.11`, Pydantic v2, existing character memory models, `HeavenlyGraphPort`, SQLite adapter, pytest, Harness Engineering.

## Global Constraints

- Requires passing Phase 2 `siming-six-domain-memory`.
- Initial heavy-actor allowlist is exactly `char_b`; `char_a` remains light-store backed.
- Long-term records use namespace `actor_private` with `owner_actor_id` equal to the record actor.
- Existing output validator and `MindWritebackPolicyRouter` remain the only routes into memory writes.
- Working memory stays transient and is not treated as durable graph truth.
- Recall returns the existing `CharacterMemoryRecordBundle`; L2/L3 call sites do not receive a second memory model.
- Siming reads via `ActorMemoryReadGateway` only and receives completeness plus a revision vector.
- `memory_surface_incomplete` is not equivalent to actor ignorance.
- No raw patch, private cache, hidden state, inference history, reasoning draft, or chain-of-thought enters the graph.

---

### Task 1: Implement the Graph-Backed Character Memory Store

**Files:**
- Create: `backend/app/character_agent/storage/graph_memory_store.py`
- Modify: `backend/app/character_agent/storage/memory_store.py`
- Create: `backend/tests/test_character_graph_memory_store.py`

**Interfaces:**
- Consumes: `CharacterAgentMemoryStore`, five existing record models, `CharacterMemoryRecordBundle`, and `HeavenlyGraphPort`.
- Produces: `CharacterMemoryStorePort` and `CharacterGraphMemoryStore` with the existing four-method surface.

- [ ] **Step 1: Define the existing memory-store surface as a protocol**

```python
class CharacterMemoryStorePort(Protocol):
    def write_event(self, event: dict[str, object]) -> None:
        raise NotImplementedError
    def retrieval_bundle(self, actor_id: str) -> dict[str, list[dict[str, object]]]:
        raise NotImplementedError
    def retrieval_record_bundle(
        self, actor_id: str, *, story_branch_id: str | None = None,
        valid_at: int | None = None,
    ) -> CharacterMemoryRecordBundle:
        raise NotImplementedError
    def working_memory_state(
        self, actor_id: str, private_snapshot: dict[str, object] | None = None,
        dynamic_state: dict[str, object] | CharacterDynamicState | None = None,
    ) -> CharacterWorkingMemoryState:
        raise NotImplementedError
```

`CharacterAgentMemoryStore` must satisfy this protocol without changing behavior.

- [ ] **Step 2: Write failing Event/Observation graph tests**

```python
def test_char_b_percept_writes_event_and_observation_nodes(sqlite_graph, scope_resolver) -> None:
    store = CharacterGraphMemoryStore(sqlite_graph, scope_resolver=scope_resolver)
    store.write_event(character_perceived_destroy_event(actor_id="char_b"))
    bundle = store.retrieval_record_bundle("char_b")
    assert bundle.event_memories[0].source_event_id == "authority:letter:destroyed"
    assert bundle.observation_memories[0].observed_entity_id == "obj_letter"
    scope = scope_resolver("char_b")
    assert sqlite_graph.query_nodes(HeavenlyNodeQuery(
        scope=scope, valid_at=100, node_types=["actor_memory:event", "actor_memory:observation"],
    ))
```

- [ ] **Step 3: Run the test and confirm the graph store is absent**

Run: `python -m pytest backend/tests/test_character_graph_memory_store.py -v`

Expected: FAIL with `ModuleNotFoundError: app.character_agent.storage.graph_memory_store`.

- [ ] **Step 4: Implement record normalization and graph deposition**

```python
class CharacterGraphMemoryStore:
    POOLS = (
        ("event", "event_memories"), ("observation", "observation_memories"),
        ("knowledge", "knowledge_memories"), ("social", "social_memories"),
        ("higher_order", "higher_order_memories"),
    )

    def __init__(self, graph: HeavenlyGraphPort, *, scope_resolver: Callable[[str], HeavenlyGraphScope]) -> None:
        self._graph = graph
        self._scope_resolver = scope_resolver
        self._normalizer = CharacterAgentMemoryStore()

    def write_event(self, event: dict[str, object]) -> None:
        actor_id = str(event.get("actor_id", "") or "")
        if not actor_id:
            return
        self._normalizer.write_event(event)
        self._deposit_bundle(actor_id, self._normalizer.retrieval_record_bundle(actor_id), event)
```

Use stable node IDs `actor-memory:<pool>:<memory_id>`, node types `actor_memory:<pool>`, record JSON as attributes, and idempotency key `character-memory:<actor_id>:<source_event_id>`. Create same-scope normalized anchor nodes for referenced actors/objects before relations. A repeated source event must replay, not create a second record.

- [ ] **Step 5: Implement graph recall and transient working memory**

`retrieval_record_bundle(actor_id, *, story_branch_id=None, valid_at=None)` must query five node types at the requested actor-private scope, reject a branch different from the store's scope, use `valid_at` or the latest known event time, parse back into the existing record classes, sort by `(world_ts|producer_ts, memory_id)`, and return `CharacterMemoryRecordBundle`. `CharacterAgentMemoryStore` accepts and ignores the optional filters because it is the current-session light store. `retrieval_bundle` returns `model_dump()` lists plus the existing legacy projection keys. `working_memory_state` delegates to the transient normalizer only.

- [ ] **Step 6: Run store tests**

Run: `python -m pytest backend/tests/test_character_graph_memory_store.py -v`

Expected: PASS for all five pools, idempotent replay, private scope, invalid actor mismatch, bounded recall, and SQLite restart.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/character_agent/storage/graph_memory_store.py backend/app/character_agent/storage/memory_store.py backend/tests/test_character_graph_memory_store.py
git commit -m "feat: add graph-backed character five-pool memory"
```

### Task 2: Route `char_b` Through the Graph Store Without Changing Character Callers

**Files:**
- Create: `backend/app/character_agent/storage/memory_store_router.py`
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/app/config.py`
- Create: `backend/tests/test_character_graph_memory_routing.py`

**Interfaces:**
- Consumes: light and graph stores implementing `CharacterMemoryStorePort`.
- Produces: `CharacterMemoryStoreRouter` and injectable `CharacterAgentRuntime(memory_store=...)`.

- [ ] **Step 1: Write failing routing tests**

```python
def test_router_sends_only_char_b_to_graph(light_store, graph_store) -> None:
    router = CharacterMemoryStoreRouter(
        light_store=light_store, graph_store=graph_store,
        heavy_actor_ids=frozenset({"char_b"}),
    )
    router.write_event(character_perceived_destroy_event(actor_id="char_b"))
    router.write_event(character_perceived_destroy_event(actor_id="char_a"))
    assert graph_store.retrieval_record_bundle("char_b").event_memories
    assert not graph_store.retrieval_record_bundle("char_a").event_memories
    assert light_store.retrieval_record_bundle("char_a").event_memories


def test_runtime_uses_injected_router(router) -> None:
    runtime = CharacterAgentRuntime(memory_store=router)
    runtime.ingest_character_perceived_event(perceived_destroy_event("char_b"))
    assert runtime.get_memory_record_bundle("char_b").observation_memories
```

- [ ] **Step 2: Run tests and confirm injection/routing are absent**

Run: `python -m pytest backend/tests/test_character_graph_memory_routing.py -v`

Expected: FAIL because `CharacterMemoryStoreRouter` and `memory_store` injection do not exist.

- [ ] **Step 3: Implement a four-method router**

```python
class CharacterMemoryStoreRouter:
    def __init__(
        self, *, light_store: CharacterMemoryStorePort,
        graph_store: CharacterMemoryStorePort, heavy_actor_ids: frozenset[str],
    ) -> None:
        self._light = light_store
        self._graph = graph_store
        self._heavy_actor_ids = heavy_actor_ids

    def _store_for(self, actor_id: str) -> CharacterMemoryStorePort:
        return self._graph if actor_id in self._heavy_actor_ids else self._light

    def write_event(self, event: dict[str, object]) -> None:
        self._store_for(str(event.get("actor_id", "") or "")).write_event(event)
```

Delegate the other three methods by their explicit `actor_id`, including the optional branch/time filters on `retrieval_record_bundle`. Do not duplicate write routing at every runtime call site.

- [ ] **Step 4: Add explicit configuration and runtime injection**

Add `heavenly_graph_path: str = ".runtime/siming-heavenly.sqlite3"` and `character_graph_memory_heavy_actor_ids: list[str] = ["char_b"]` to `Settings`; read `PARALLS_HEAVENLY_GRAPH_PATH` and `CHARACTER_GRAPH_MEMORY_HEAVY_ACTORS`; then change the runtime constructor to:

```python
def __init__(
    self, storage_root: str | Path | None = None, *,
    skill_service: CharacterSkillService | None = None,
    memory_store: CharacterMemoryStorePort | None = None,
) -> None:
    self._memory_store = memory_store or CharacterAgentMemoryStore()
```

Keep every existing constructor initialization around this replacement; only replace the current `self._memory_store = CharacterAgentMemoryStore()` assignment.

Extend the runtime read method compatibly:

```python
def get_memory_record_bundle(
    self, actor_id: str, *, story_branch_id: str | None = None,
    valid_at: int | None = None,
) -> CharacterMemoryRecordBundle:
    return self._memory_store.retrieval_record_bundle(
        actor_id, story_branch_id=story_branch_id, valid_at=valid_at,
    )
```

- [ ] **Step 5: Run routing and existing character memory tests**

Run: `python -m pytest backend/tests/test_character_graph_memory_routing.py backend/tests/test_character_agent_memory_writeback.py backend/tests/test_character_agent_runtime_memory_integration.py -v`

Expected: PASS; `char_a` behavior remains unchanged.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/character_agent/storage/memory_store_router.py backend/app/character_agent/runtime/runtime_loop.py backend/app/config.py backend/tests/test_character_graph_memory_routing.py
git commit -m "feat: route heavy actors to graph memory"
```

### Task 3: Add the Siming Read-Only Actor Memory Gateway

**Files:**
- Create: `backend/app/models/siming_actor_memory_read.py`
- Create: `backend/app/services/siming_actor_memory_gateway.py`
- Create: `backend/tests/test_siming_actor_memory_gateway.py`

**Interfaces:**
- Consumes: `CharacterAgentRuntime.get_memory_record_bundle(actor_id)`.
- Produces: `ActorMemoryReadRequest`, `ActorMemoryRevisionVector`, `ActorMemoryReadResult`, and `ActorMemoryReadGateway.read(...)`.

- [ ] **Step 1: Write failing complete/incomplete/read-only tests**

```python
def test_gateway_returns_observation_with_revision_vector(runtime) -> None:
    gateway = ActorMemoryReadGateway(runtime)
    result = gateway.read(ActorMemoryReadRequest(
        actor_id="char_b", story_branch_id="branch:main", valid_at=100,
    ))
    assert result.completeness == "complete"
    assert result.bundle.observation_memories[0].observed_entity_id == "obj_letter"
    assert result.revision_vector.observation != ""


def test_revision_mismatch_is_incomplete_not_ignorance(runtime) -> None:
    gateway = ActorMemoryReadGateway(runtime)
    result = gateway.read(ActorMemoryReadRequest(
        actor_id="char_b", story_branch_id="branch:main", valid_at=100,
        expected_revision_vector=ActorMemoryRevisionVector(observation="stale"),
    ))
    assert result.completeness == "memory_surface_incomplete"
    assert result.reason == "revision_vector_mismatch"
    assert not hasattr(gateway, "write")
```

- [ ] **Step 2: Run tests and confirm the gateway is absent**

Run: `python -m pytest backend/tests/test_siming_actor_memory_gateway.py -v`

Expected: FAIL with missing module.

- [ ] **Step 3: Implement deterministic revision hashing and read-only access**

```python
class ActorMemoryReadGateway:
    def __init__(self, runtime: CharacterAgentRuntime) -> None:
        self._runtime = runtime

    def read(self, request: ActorMemoryReadRequest) -> ActorMemoryReadResult:
        bundle = self._runtime.get_memory_record_bundle(
            request.actor_id, story_branch_id=request.story_branch_id,
            valid_at=request.valid_at,
        )
        vector = ActorMemoryRevisionVector.from_bundle(bundle)
        complete = request.expected_revision_vector in (None, vector)
        return ActorMemoryReadResult(
            actor_id=request.actor_id, story_branch_id=request.story_branch_id,
            valid_at=request.valid_at, revision_vector=vector, bundle=bundle,
            completeness="complete" if complete else "memory_surface_incomplete",
            reason="" if complete else "revision_vector_mismatch",
        )
```

Compute each pool component as SHA-256 of canonical sorted record JSON. Models must expose only the five typed pools and explicitly reject fields named `raw_patch`, `private_cache`, `hidden_state`, `reasoning_draft`, or `chain_of_thought`.

```python
class ActorMemoryRevisionVector(BaseModel):
    event: str = ""
    observation: str = ""
    knowledge: str = ""
    social: str = ""
    higher_order: str = ""

class ActorMemoryReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor_id: str
    story_branch_id: str
    valid_at: int = Field(ge=0)
    expected_revision_vector: ActorMemoryRevisionVector | None = None

class ActorMemoryReadResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor_id: str
    story_branch_id: str
    valid_at: int
    revision_vector: ActorMemoryRevisionVector
    completeness: Literal["complete", "memory_surface_incomplete"]
    reason: str = ""
    bundle: CharacterMemoryRecordBundle
```

- [ ] **Step 4: Run gateway tests**

Run: `python -m pytest backend/tests/test_siming_actor_memory_gateway.py -v`

Expected: PASS for complete reads, expected-vector mismatch, missing actor surface, no write method, and no private artifacts.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/models/siming_actor_memory_read.py backend/app/services/siming_actor_memory_gateway.py backend/tests/test_siming_actor_memory_gateway.py
git commit -m "feat: add Siming read-only actor memory gateway"
```

### Task 4: Compose Durable Character Memory and Add the Phase Gate

**Files:**
- Modify: `backend/app/main.py`
- Create: `scripts/verification/verify_siming_actor_memory_read.py`
- Create: `.harness/profiles/siming-actor-memory-read.json`
- Modify: `docs/harness.md`
- Modify: `docs/INDEX.md`

**Interfaces:**
- Consumes: SQLite adapter, graph store/router, heavy-actor settings, and actor gateway.
- Produces: runtime `char_b` graph memory plus `.harness/verification/siming-actor-memory-read-report.json`.

- [ ] **Step 1: Compose one shared runtime SQLite graph**

In `reset_runtime_state()`, create the SQLite adapter from `PARALLS_HEAVENLY_GRAPH_PATH` (default `.runtime/siming-heavenly.sqlite3`), build a `CharacterGraphMemoryStore` with actor-private scopes, wrap it with `CharacterMemoryStoreRouter`, then construct `CharacterAgentRuntime(memory_store=router)`. Reuse this same graph object in later Siming phases.

```python
heavenly_graph = SQLiteHeavenlyGraphAdapter(settings.heavenly_graph_path)
graph_memory = CharacterGraphMemoryStore(heavenly_graph, scope_resolver=actor_private_scope)
memory_router = CharacterMemoryStoreRouter(
    light_store=CharacterAgentMemoryStore(), graph_store=graph_memory,
    heavy_actor_ids=frozenset(settings.character_graph_memory_heavy_actor_ids),
)
character_agent_runtime = CharacterAgentRuntime(memory_store=memory_router)
```

- [ ] **Step 2: Implement the restart/isolation verifier**

The verifier must ingest a `char_b` perceived event for `obj_letter=removed_from_surface`, prove Event+Observation records, close/reopen SQLite, rebuild the runtime, prove the same bundle/revision vector, prove `char_a` remains light-store backed, query `actor_private:char_a` for the `char_b` node and receive no result, and read `char_b` through `ActorMemoryReadGateway`.

- [ ] **Step 3: Register the profile**

```json
{
  "schema_version": 1,
  "name": "siming-actor-memory-read",
  "order": 74,
  "script": "scripts/verification/verify_siming_actor_memory_read.py",
  "requires_godot": false,
  "max_attempts": 1,
  "result_artifact": ".harness/verification/siming-actor-memory-read-report.json",
  "description": "Backend proof for char_b actor-private five-pool graph memory, restart recall, and Siming read-only isolation"
}
```

- [ ] **Step 4: Run focused and phase verification**

Run: `python -m pytest backend/tests/test_character_graph_memory_store.py backend/tests/test_character_graph_memory_routing.py backend/tests/test_siming_actor_memory_gateway.py -v`

Expected: PASS.

Run: `python scripts/verification/harness.py --profile siming-actor-memory-read`

Expected: PASS with result IDs `char_b_graph_backed`, `event_observation_deposited`, `restart_recall`, `char_a_light_store`, `cross_actor_isolation`, and `siming_read_only`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/main.py scripts/verification/verify_siming_actor_memory_read.py .harness/profiles/siming-actor-memory-read.json docs/harness.md docs/INDEX.md
git commit -m "test: prove actor-private graph memory integration"
```
