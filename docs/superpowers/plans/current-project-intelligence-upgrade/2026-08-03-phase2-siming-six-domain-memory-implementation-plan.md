# Phase 2 Siming Six-Domain Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store and deterministically recall Siming's six heavenly memory domains from the durable graph without treating summaries or state-tree snapshots as canonical memory.

**Architecture:** Add strict domain entry models, a graph-backed write/read service, a bounded context compiler, and compatibility projections into the existing runtime-state types. Domain entries remain immutable graph revisions; every tick context is rebuilt from graph queries and can be reproduced after projection caches are discarded.

**Tech Stack:** Python `>=3.11`, Pydantic v2, existing `HeavenlyGraphPort`, pytest, existing Siming runtime-state models, Harness Engineering.

## Global Constraints

- Requires the passing Phase 1.1 `siming-heavenly-graph-foundation` profile.
- Canonical scope is namespace `siming_heavenly` with no `owner_actor_id`.
- The six domains are `world_fact`, `causal_timeline`, `actor_cognition`, `storyline_obligation`, `intervention_outcome`, and `convergence_strategy`.
- Only Authority-confirmed facts enter `world_fact`; multimodal content is stored as normalized evidence refs, not raw artifacts.
- Actor cognition entries are read-only projections with revision/completeness metadata, not copies of hidden actor state.
- Conflicting propositions remain separate revisions/claims and are never merged into one truth by an LLM.
- Context compilation is bounded and deterministic; compression never deletes graph entities.
- Summary, state tree, read model, and debug output are disposable projections and never write back as canonical memory.

---

### Task 1: Define the Six Typed Memory Domains

**Files:**
- Create: `backend/app/models/siming_heavenly_memory.py`
- Create: `backend/tests/test_siming_heavenly_memory_models.py`

**Interfaces:**
- Consumes: `HeavenlyGraphScope` and existing Pydantic conventions.
- Produces: six strict entry types, `SimingHeavenlyMemoryEntry`, `SimingContextRequest`, and `SimingCompiledContext`.

- [ ] **Step 1: Write failing discriminated-union tests**

```python
def test_world_fact_requires_authority_result_ref() -> None:
    with pytest.raises(ValidationError, match="authority_result_ref"):
        WorldFactMemoryEntry(
            entry_id="fact:letter:removed", world_anchor_id="obj_letter",
            state_key="surface_state", state_value="removed_from_surface",
            evidence_refs=["visual:letter:gone"],
        )


def test_context_request_rejects_actor_private_scope() -> None:
    with pytest.raises(ValidationError, match="siming_heavenly"):
        SimingContextRequest(
            scope=actor_scope("char_b"), valid_at=10, recorded_at=10,
            seed_node_ids=["fact:letter:removed"], relevant_actor_ids=["char_b"],
        )
```

- [ ] **Step 2: Run the model tests and confirm the module is absent**

Run: `python -m pytest backend/tests/test_siming_heavenly_memory_models.py -v`

Expected: FAIL with `ModuleNotFoundError: app.models.siming_heavenly_memory`.

- [ ] **Step 3: Add exact domain models**

```python
class StrictMemoryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

class WorldFactMemoryEntry(StrictMemoryModel):
    domain: Literal["world_fact"] = "world_fact"
    entry_id: str
    world_anchor_id: str
    state_key: str
    state_value: JsonValue
    authority_result_ref: str
    evidence_refs: list[str] = Field(default_factory=list)


class CausalTimelineMemoryEntry(StrictMemoryModel):
    domain: Literal["causal_timeline"] = "causal_timeline"
    entry_id: str
    cause_ref: str
    effect_ref: str
    relation_type: Literal["CAUSED_BY", "ENABLED_BY", "PREVENTED_BY"]
    closes_path_refs: list[str] = Field(default_factory=list)


class ActorCognitionMemoryEntry(StrictMemoryModel):
    domain: Literal["actor_cognition"] = "actor_cognition"
    entry_id: str
    actor_id: str
    revision_vector: dict[str, str]
    completeness: Literal["complete", "memory_surface_incomplete"]
    supporting_memory_refs: list[str] = Field(default_factory=list)


class StorylineObligationMemoryEntry(StrictMemoryModel):
    domain: Literal["storyline_obligation"] = "storyline_obligation"
    entry_id: str
    record_type: Literal["storyline", "story_node", "outcome_port", "obligation", "attractor", "constraint"]
    lifecycle: str
    supporting_fact_refs: list[str] = Field(default_factory=list)


class InterventionOutcomeMemoryEntry(StrictMemoryModel):
    domain: Literal["intervention_outcome"] = "intervention_outcome"
    entry_id: str
    stage: Literal["proposal", "selection", "staging", "dispatch", "authority_result"]
    correlation_id: str
    selected_node_ref: str | None = None
    realization_signature: str | None = None
    authority_result_ref: str | None = None


class ConvergenceStrategyMemoryEntry(StrictMemoryModel):
    domain: Literal["convergence_strategy"] = "convergence_strategy"
    entry_id: str
    reachable_attractor_refs: list[str] = Field(default_factory=list)
    open_obligation_refs: list[str] = Field(default_factory=list)
    permanently_closed_node_refs: list[str] = Field(default_factory=list)
    next_minimal_intervention: str = ""
```

Define `SimingHeavenlyMemoryEntry` as an `Annotated` discriminated union on `domain`. `SimingCompiledContext` must contain one list per domain, selected nodes/relations, `truncated`, and `context_hash`.

```python
SimingHeavenlyMemoryEntry = Annotated[
    WorldFactMemoryEntry | CausalTimelineMemoryEntry | ActorCognitionMemoryEntry |
    StorylineObligationMemoryEntry | InterventionOutcomeMemoryEntry |
    ConvergenceStrategyMemoryEntry,
    Field(discriminator="domain"),
]

class SimingContextRequest(StrictMemoryModel):
    scope: HeavenlyGraphScope
    valid_at: int = Field(ge=0)
    recorded_at: int | None = Field(default=None, ge=0)
    seed_node_ids: list[str]
    relevant_actor_ids: list[str] = Field(default_factory=list)
    relation_types: list[str] = Field(default_factory=list)
    node_limit: int = Field(default=200, ge=1, le=1000)
    relation_limit: int = Field(default=400, ge=1, le=2000)

class SimingCompiledContext(StrictMemoryModel):
    request: SimingContextRequest
    world_facts: list[WorldFactMemoryEntry] = Field(default_factory=list)
    causal_timeline: list[CausalTimelineMemoryEntry] = Field(default_factory=list)
    actor_cognition: list[ActorCognitionMemoryEntry] = Field(default_factory=list)
    storyline_obligations: list[StorylineObligationMemoryEntry] = Field(default_factory=list)
    intervention_outcomes: list[InterventionOutcomeMemoryEntry] = Field(default_factory=list)
    convergence_strategies: list[ConvergenceStrategyMemoryEntry] = Field(default_factory=list)
    selected_node_refs: list[str] = Field(default_factory=list)
    selected_relation_refs: list[str] = Field(default_factory=list)
    truncated: bool
    context_hash: str
```

- [ ] **Step 4: Run model tests**

Run: `python -m pytest backend/tests/test_siming_heavenly_memory_models.py -v`

Expected: PASS for strict fields, domain discrimination, scope validation, and raw/private-artifact rejection.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/models/siming_heavenly_memory.py backend/tests/test_siming_heavenly_memory_models.py
git commit -m "feat: define Siming six-domain memory contracts"
```

### Task 2: Implement Graph-Backed Domain Writes and Reads

**Files:**
- Create: `backend/app/services/siming_heavenly_memory.py`
- Create: `backend/tests/test_siming_six_domain_memory.py`

**Interfaces:**
- Consumes: `HeavenlyGraphPort`, six-domain entries, `GraphValidity`, and `GraphProvenance`.
- Produces: `SimingHeavenlyMemoryService.write_entry(...)`, `get_entry(...)`, and `list_domain(...)`.

- [ ] **Step 1: Write failing six-domain persistence and conflict tests**

```python
def test_service_round_trips_all_six_domains(graph, heavenly_scope, entries) -> None:
    service = SimingHeavenlyMemoryService(graph)
    for index, entry in enumerate(entries):
        service.write_entry(
            scope=heavenly_scope, entry=entry, validity=GraphValidity(valid_from=10),
            recorded_at=10, revision=1, supersedes_revision=None,
            provenance=provenance(entry.entry_id), transaction_id=f"tx:{index}",
            idempotency_key=f"memory:{entry.entry_id}:1",
        )
    assert [len(service.list_domain(heavenly_scope, entry.domain, valid_at=10)) for entry in entries] == [1] * 6


def test_conflicting_claims_are_preserved_as_distinct_entries(graph, heavenly_scope) -> None:
    service = SimingHeavenlyMemoryService(graph)
    write_claim(service, heavenly_scope, "claim:bell:heard", "heard")
    write_claim(service, heavenly_scope, "claim:bell:not-heard", "not_heard")
    assert {entry.entry_id for entry in service.list_domain(heavenly_scope, "world_fact", valid_at=20)} == {
        "claim:bell:heard", "claim:bell:not-heard",
    }
```

- [ ] **Step 2: Run tests and confirm the service is absent**

Run: `python -m pytest backend/tests/test_siming_six_domain_memory.py -v`

Expected: FAIL with `ModuleNotFoundError: app.services.siming_heavenly_memory`.

- [ ] **Step 3: Implement typed graph mapping**

```python
class SimingHeavenlyMemoryService:
    def __init__(self, graph: HeavenlyGraphPort) -> None:
        self._graph = graph

    def write_entry(
        self, *, scope: HeavenlyGraphScope, entry: SimingHeavenlyMemoryEntry,
        validity: GraphValidity, recorded_at: int, revision: int,
        supersedes_revision: int | None, provenance: GraphProvenance,
        transaction_id: str, idempotency_key: str,
    ) -> HeavenlyGraphWriteResult:
        self._require_heavenly_scope(scope)
        node = HeavenlyGraphNode(
            node_id=entry.entry_id, node_type=f"memory:{entry.domain}", scope=scope,
            validity=validity, recorded_at=recorded_at, revision=revision,
            supersedes_revision=supersedes_revision,
            attributes=entry.model_dump(mode="json"), provenance=provenance,
        )
        return self._graph.write_batch(HeavenlyGraphWriteBatch(
            transaction_id=transaction_id, idempotency_key=idempotency_key,
            scope=scope, nodes=[node],
        ))
```

`get_entry(...)` must parse through `TypeAdapter(SimingHeavenlyMemoryEntry)`. `list_domain(...)` must query `node_type=f"memory:{domain}"`, preserve node-ID order, and never return projection nodes.

- [ ] **Step 4: Run service tests against in-memory and SQLite adapters**

Run: `python -m pytest backend/tests/test_siming_six_domain_memory.py -v`

Expected: PASS with six domains, temporal revisions, idempotency, conflict preservation, and restart read coverage.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/siming_heavenly_memory.py backend/tests/test_siming_six_domain_memory.py
git commit -m "feat: persist Siming six-domain memory"
```

### Task 3: Compile Bounded Tick Context and Disposable Projections

**Files:**
- Create: `backend/app/services/siming_context_compiler.py`
- Create: `backend/app/services/siming_story_projection.py`
- Create: `backend/tests/test_siming_context_compiler.py`
- Create: `backend/tests/test_siming_story_projection.py`

**Interfaces:**
- Consumes: `SimingHeavenlyMemoryService`, `HeavenlyGraphPort.query_subgraph(...)`, and current `StateTreeSnapshot`/`NarrativeReadModel` models.
- Produces: `SimingContextCompiler.compile(request) -> SimingCompiledContext` and `SimingStoryProjection.project(context) -> SimingGraphProjectionBundle`.

- [ ] **Step 1: Write the cache-deletion reconstruction test**

```python
def test_compiler_rebuilds_identical_context_without_cached_summary(graph, seeded_scope) -> None:
    compiler = SimingContextCompiler(graph)
    request = SimingContextRequest(
        scope=seeded_scope, valid_at=100, recorded_at=100,
        seed_node_ids=["fact:letter:removed", "obligation:O6"],
        relevant_actor_ids=["char_b"], node_limit=200, relation_limit=400,
    )
    first = compiler.compile(request)
    del compiler
    second = SimingContextCompiler(graph).compile(request)
    assert second == first
    assert second.context_hash == first.context_hash
```

- [ ] **Step 2: Write projection non-authority tests**

```python
def test_projection_contains_graph_basis_and_cannot_write_memory(compiled_context) -> None:
    projection = SimingStoryProjection().project(compiled_context)
    assert projection.read_model.derived_from_snapshot_ref == compiled_context.context_hash
    assert projection.state_tree.storyline.owner_system == "siming"
    assert projection.state_tree.storyline.authority == "editable"
    assert not hasattr(SimingStoryProjection(), "write_entry")
```

- [ ] **Step 3: Run tests and confirm both services are absent**

Run: `python -m pytest backend/tests/test_siming_context_compiler.py backend/tests/test_siming_story_projection.py -v`

Expected: FAIL with missing modules.

- [ ] **Step 4: Implement deterministic compilation**

```python
class SimingContextCompiler:
    def __init__(self, graph: HeavenlyGraphPort) -> None:
        self._graph = graph

    def compile(self, request: SimingContextRequest) -> SimingCompiledContext:
        subgraph = self._graph.query_subgraph(
            scope=request.scope, seed_node_ids=sorted(set(request.seed_node_ids)),
            relation_types=request.relation_types, direction="both", max_depth=4,
            valid_at=request.valid_at, recorded_at=request.recorded_at,
            node_limit=request.node_limit, relation_limit=request.relation_limit,
        )
        return SimingCompiledContext.from_subgraph(request, subgraph)

```

`from_subgraph` must parse only `memory:*` nodes, sort every domain by `entry_id`, compute SHA-256 over canonical JSON (`sort_keys=True`, compact separators), and preserve `truncated`. A fresh compiler instance must reproduce the same result; no retained summary cache is required in this phase.

- [ ] **Step 5: Implement typed compatibility projection**

`SimingGraphProjectionBundle` contains `StateTreeSnapshot`, `StorylineStateSnapshot`, `NarrativeReadModel`, and `debug_summary`. Build all IDs from `context_hash`; mark environment/character branches `authority="mirror"`, and mark the storyline `owner_system="siming"` with the existing editable authority vocabulary. Include graph refs in `derived_from_snapshot_ref`. Do not call the graph write service.

```python
class SimingGraphProjectionBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state_tree: StateTreeSnapshot
    storyline: StorylineStateSnapshot
    read_model: NarrativeReadModel
    debug_summary: dict[str, JsonValue] = Field(default_factory=dict)
```

- [ ] **Step 6: Run compiler/projection tests**

Run: `python -m pytest backend/tests/test_siming_context_compiler.py backend/tests/test_siming_story_projection.py -v`

Expected: PASS with deterministic ordering, hard limits, six-domain bucketing, graph-derived IDs, and projection deletion/rebuild.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/services/siming_context_compiler.py backend/app/services/siming_story_projection.py backend/tests/test_siming_context_compiler.py backend/tests/test_siming_story_projection.py
git commit -m "feat: compile graph-backed Siming context projections"
```

### Task 4: Add the Six-Domain Harness Gate

**Files:**
- Create: `scripts/verification/verify_siming_six_domain_memory.py`
- Create: `.harness/profiles/siming-six-domain-memory.json`
- Modify: `docs/harness.md`
- Modify: `docs/INDEX.md`

**Interfaces:**
- Consumes: Tasks 1-3 focused tests and SQLite adapter.
- Produces: `.harness/verification/siming-six-domain-memory-report.json`.

- [ ] **Step 1: Implement the focused verifier**

The verifier must run all four Phase 2 test files, seed one record in every domain into a temporary SQLite graph, close/reopen it, compile context twice with no retained summary, and emit result IDs `six_domains_present`, `restart_recall`, `summary_free_rebuild`, `conflicts_preserved`, and `projection_not_truth`.

```python
TEST_FILES = [
    "backend/tests/test_siming_heavenly_memory_models.py",
    "backend/tests/test_siming_six_domain_memory.py",
    "backend/tests/test_siming_context_compiler.py",
    "backend/tests/test_siming_story_projection.py",
]
```

- [ ] **Step 2: Register and document the profile**

```json
{
  "schema_version": 1,
  "name": "siming-six-domain-memory",
  "order": 73,
  "script": "scripts/verification/verify_siming_six_domain_memory.py",
  "requires_godot": false,
  "max_attempts": 1,
  "result_artifact": ".harness/verification/siming-six-domain-memory-report.json",
  "description": "Backend proof for durable six-domain Siming memory and summary-free context reconstruction"
}
```

- [ ] **Step 3: Run the phase gate**

Run: `python scripts/verification/harness.py --profile siming-six-domain-memory`

Expected: PASS with all five result IDs proved.

- [ ] **Step 4: Commit**

```powershell
git add scripts/verification/verify_siming_six_domain_memory.py .harness/profiles/siming-six-domain-memory.json docs/harness.md docs/INDEX.md
git commit -m "test: prove Siming six-domain graph memory"
```
