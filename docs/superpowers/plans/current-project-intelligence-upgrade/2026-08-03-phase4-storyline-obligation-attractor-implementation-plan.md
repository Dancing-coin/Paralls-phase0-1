# Phase 4 Storyline Obligation and Attractor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Manage authored possibilities and runtime story truth as separate graph structures, including terminal player closures, obligation transformations, and reachable narrative attractors.

**Architecture:** Store immutable authored blueprints separately from branch-scoped runtime node instances. Apply lifecycle changes only from validated commands and Authority-confirmed outcomes, then persist obligation and attractor consequences through the Phase 2 six-domain service.

**Tech Stack:** Python `>=3.11`, Pydantic v2, existing Heavenly Graph/six-domain services, pytest, Harness Engineering.

## Global Constraints

- Requires passing Phase 3 `siming-actor-memory-read`.
- Authored possibility is not runtime truth and runtime outcomes never mutate authored blueprints.
- Lifecycle is `latent -> eligible -> selected -> staged -> active -> resolving -> resolved|failed|aborted -> cooldown`.
- A player-closed node is `aborted`, `closure_reason=closed_by_player_choice`, `terminal=true`, and `reopen_policy=never`.
- A terminal node ID is never reactivated; later similar semantics require a new runtime node ID and new causal basis.
- Obligation is causal debt, not a fixed quest; staging or asset availability cannot fulfill it.
- Attractors define acceptable state ranges, not a forced path.
- Hard-order evaluation is fact/player choice, autonomy, feasibility/safety, playability/fairness, obligations, reachable attractors, then resource reuse.
- Standard acceptance uses N1-N5 and O2-to-O6 after Authority confirms `obj_letter=removed_from_surface`.

---

### Task 1: Define Authored and Runtime Story Contracts

**Files:**
- Create: `backend/app/models/siming_story_graph.py`
- Create: `backend/tests/test_siming_story_graph_models.py`

**Interfaces:**
- Consumes: current strict Pydantic conventions and graph IDs.
- Produces: `StoryNodeBlueprint`, `StoryOutcomePort`, `RuntimeStoryNode`, `NarrativeObligation`, `NarrativeAttractor`, and transition commands/results.

- [ ] **Step 1: Write failing terminal-node and outcome-port tests**

```python
def test_terminal_player_closure_requires_never_reopen() -> None:
    with pytest.raises(ValidationError, match="reopen_policy"):
        RuntimeStoryNode(
            node_id="runtime:N4:main", blueprint_id="N4", lifecycle="aborted",
            closure_reason="closed_by_player_choice", terminal=True,
            reopen_policy="new_causal_basis", reachability="unreachable",
        )


def test_outcome_port_requires_authority_predicate() -> None:
    with pytest.raises(ValidationError, match="required_result_type"):
        StoryOutcomePort(
            port_id="player_destroyed_evidence", required_result_type="",
            target_ref="obj_letter", required_state="removed_from_surface",
            outcome_semantic="resolved_with_divergence",
        )
```

- [ ] **Step 2: Run tests and confirm the model module is absent**

Run: `python -m pytest backend/tests/test_siming_story_graph_models.py -v`

Expected: FAIL with `ModuleNotFoundError: app.models.siming_story_graph`.

- [ ] **Step 3: Add exact lifecycle and authored/runtime models**

```python
StoryNodeLifecycle = Literal[
    "latent", "eligible", "selected", "staged", "active", "resolving",
    "resolved", "failed", "aborted", "cooldown",
]

class StoryOutcomeEffect(StrictStoryModel):
    target_blueprint_id: str
    effect: Literal["close_permanently", "mark_unreachable", "make_eligible"]
    reason: str

class StoryOutcomePort(StrictStoryModel):
    port_id: str
    required_result_type: str = Field(min_length=1)
    target_ref: str
    required_state: str
    outcome_semantic: str
    effects: list[StoryOutcomeEffect] = Field(default_factory=list)

class StoryNodeBlueprint(StrictStoryModel):
    blueprint_id: str
    title: str
    prerequisite_fact_refs: list[str] = Field(default_factory=list)
    required_obligation_refs: list[str] = Field(default_factory=list)
    outcome_ports: list[StoryOutcomePort] = Field(default_factory=list)

class RuntimeStoryNode(StrictStoryModel):
    node_id: str
    blueprint_id: str
    lifecycle: StoryNodeLifecycle
    reachability: Literal["reachable", "unreachable", "unreachable_by_ledger"] = "reachable"
    outcome_port: str | None = None
    outcome_semantic: str | None = None
    closure_reason: str | None = None
    terminal: bool = False
    reopen_policy: Literal["same_instance", "new_causal_basis", "never"] = "same_instance"
    causal_basis_refs: list[str] = Field(default_factory=list)
```

Add validators for allowed transition targets, terminal closure tuple, unique port IDs, and non-empty causal basis for any new instance replacing terminal semantics.

- [ ] **Step 4: Define obligation and attractor models**

```python
class NarrativeObligation(StrictStoryModel):
    obligation_id: str
    description: str
    status: Literal["open", "pressured", "partially_satisfied", "fulfilled", "transformed", "waived", "contradicted"]
    pressure: float = Field(ge=0.0, le=1.0)
    source_fact_refs: list[str]
    transformed_to_refs: list[str] = Field(default_factory=list)

class NarrativeAttractor(StrictStoryModel):
    attractor_id: str
    description: str
    required_fact_refs: list[str] = Field(default_factory=list)
    forbidden_terminal_node_refs: list[str] = Field(default_factory=list)
    reachability: Literal["reachable", "blocked", "satisfied"] = "reachable"

class AuthorityStoryOutcome(StrictStoryModel):
    result_type: str
    target_ref: str
    current_state: str
    authority_result_ref: str
    correlation_id: str
    recorded_at: int = Field(ge=0)

class StoryOutcomeApplication(StrictStoryModel):
    authority_result_ref: str
    nodes: dict[str, RuntimeStoryNode]
    graph_transaction_ref: str

class ObligationTransformResult(StrictStoryModel):
    source: NarrativeObligation
    replacement: NarrativeObligation
    graph_transaction_ref: str

class StoryDecisionCandidate(StrictStoryModel):
    candidate_id: str
    runtime_node_ref: str
    confirmed_fact: bool
    player_choice: bool
    actor_autonomy: bool
    world_feasibility: bool
    safety: bool
    playability_fairness: bool
    open_obligation: bool
    reachable_attractor: bool
    narrative_score: float
    resource_score: float = 0.0

class StoryCandidateRejection(StrictStoryModel):
    candidate_id: str
    reason: str

class StoryCandidateRanking(StrictStoryModel):
    eligible: list[StoryDecisionCandidate] = Field(default_factory=list)
    rejected: list[StoryCandidateRejection] = Field(default_factory=list)
```

- [ ] **Step 5: Run model tests and commit**

Run: `python -m pytest backend/tests/test_siming_story_graph_models.py -v`

Expected: PASS.

```powershell
git add backend/app/models/siming_story_graph.py backend/tests/test_siming_story_graph_models.py
git commit -m "feat: define authored and runtime story graph contracts"
```

### Task 2: Implement Runtime Node Lifecycle and Authority Outcome Resolution

**Files:**
- Create: `backend/app/services/siming_story_graph_runtime.py`
- Create: `backend/tests/test_siming_story_graph_runtime.py`

**Interfaces:**
- Consumes: `HeavenlyGraphPort`, `SimingHeavenlyMemoryService`, and Task 1 story contracts.
- Produces: blueprint seed/read, runtime-node instantiate/read/transition, and `apply_authority_outcome(...)`.

- [ ] **Step 1: Write the standard N3/N4/N5 failing scenario**

```python
def test_destroyed_letter_resolves_divergence_and_permanently_closes_path(runtime, scope) -> None:
    seed_n1_to_n5(runtime, scope)
    result = runtime.apply_authority_outcome(scope=scope, outcome=AuthorityStoryOutcome(
        result_type="object_state_result", target_ref="obj_letter",
        current_state="removed_from_surface", authority_result_ref="esm:destroy:1",
        correlation_id="corr:destroy:1", recorded_at=100,
    ))
    assert result.nodes["N3"].lifecycle == "resolved"
    assert result.nodes["N3"].outcome_port == "player_destroyed_evidence"
    assert result.nodes["N3"].outcome_semantic == "resolved_with_divergence"
    assert result.nodes["N4"].model_dump(include={"lifecycle", "closure_reason", "terminal", "reopen_policy"}) == {
        "lifecycle": "aborted", "closure_reason": "closed_by_player_choice",
        "terminal": True, "reopen_policy": "never",
    }
    assert result.nodes["N5"].reachability == "unreachable_by_ledger"
```

- [ ] **Step 2: Write the no-resurrection test**

```python
def test_terminal_node_instance_cannot_be_reactivated(runtime, closed_n4) -> None:
    with pytest.raises(StoryNodeTransitionError, match="terminal"):
        runtime.transition(closed_n4.node_id, expected="aborted", target="eligible", reason="retry")
```

- [ ] **Step 3: Run tests and confirm the runtime service is absent**

Run: `python -m pytest backend/tests/test_siming_story_graph_runtime.py -v`

Expected: FAIL with missing module.

- [ ] **Step 4: Implement graph-backed authored/runtime separation**

```text
SimingStoryGraphRuntime(graph: HeavenlyGraphPort, memory: SimingHeavenlyMemoryService)
seed_blueprint(*, scope, blueprint, provenance, recorded_at) -> HeavenlyGraphWriteResult
instantiate(*, scope, blueprint_id, node_id, causal_basis_refs, recorded_at) -> RuntimeStoryNode
transition(*, scope, node_id, expected, target, reason, recorded_at) -> RuntimeStoryNode
apply_authority_outcome(*, scope, outcome) -> StoryOutcomeApplication
```

Store authored nodes as `authored_story_blueprint` and branch instances as `runtime_story_node`. `apply_authority_outcome` matches `result_type`, `target_ref`, and `required_state`, writes one atomic batch for affected runtime node revisions, and writes a six-domain `storyline_obligation` record referencing the Authority result.

- [ ] **Step 5: Run runtime tests**

Run: `python -m pytest backend/tests/test_siming_story_graph_runtime.py -v`

Expected: PASS for legal transitions, stale expected state, authority predicate matching, N3/N4/N5 outcomes, no resurrection, authored immutability, and idempotent replay.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/services/siming_story_graph_runtime.py backend/tests/test_siming_story_graph_runtime.py
git commit -m "feat: add graph-backed story node lifecycle"
```

### Task 3: Implement Obligation Transformation and Attractor Reachability

**Files:**
- Create: `backend/app/services/siming_story_obligation_runtime.py`
- Create: `backend/app/services/siming_story_node_orchestrator.py`
- Create: `backend/tests/test_siming_story_obligation_runtime.py`
- Create: `backend/tests/test_siming_story_node_orchestrator.py`

**Interfaces:**
- Consumes: runtime node outcomes, actor-memory completeness, confirmed facts, and attractor models.
- Produces: atomic obligation transforms, reachability results, and hard-gated narrative rankings without resource scores.

- [ ] **Step 1: Write the O2-to-O6 atomic transform test**

```python
def test_o2_transforms_to_o6_without_fulfillment(obligations, scope) -> None:
    obligations.seed(scope, obligation_o2())
    result = obligations.transform(
        scope=scope, source_obligation_id="O2", replacement=obligation_o6(),
        authority_result_ref="esm:destroy:1", correlation_id="corr:destroy:1",
    )
    assert result.source.status == "transformed"
    assert result.source.transformed_to_refs == ["O6"]
    assert result.replacement.status == "open"
```

- [ ] **Step 2: Write hard-order orchestrator tests**

```python
def test_resource_value_cannot_rescue_fact_rejected_candidate(orchestrator) -> None:
    rejected = story_candidate("reuse-rich", fact_gate=False, resource_score=1.0)
    accepted = story_candidate("fresh", fact_gate=True, resource_score=0.0)
    result = orchestrator.rank([rejected, accepted])
    assert [item.candidate_id for item in result.eligible] == ["fresh"]
    assert result.rejected[0].reason == "fact_gate_failed"
```

- [ ] **Step 3: Run tests and confirm services are absent**

Run: `python -m pytest backend/tests/test_siming_story_obligation_runtime.py backend/tests/test_siming_story_node_orchestrator.py -v`

Expected: FAIL with missing modules.

- [ ] **Step 4: Implement obligation and attractor operations**

`transform(...)` writes the source revision and replacement node in one graph batch. `evaluate_attractor(...)` marks an attractor blocked when any required route is terminal/unreachable, but allows alternative routes with different node IDs and fresh causal basis. Never infer fulfillment from selection, staging, or resource availability.

```text
SimingStoryObligationRuntime(graph: HeavenlyGraphPort, memory: SimingHeavenlyMemoryService)
seed(*, scope, obligation, provenance, recorded_at) -> HeavenlyGraphWriteResult
transform(*, scope, source_obligation_id, replacement, authority_result_ref, correlation_id) -> ObligationTransformResult
evaluate_attractor(*, scope, attractor_id, valid_at) -> NarrativeAttractor
```

- [ ] **Step 5: Implement the fixed hard-gate order**

```python
class StoryNodeOrchestrator:
    GATE_ORDER = (
        "confirmed_fact", "player_choice", "actor_autonomy",
        "world_feasibility", "safety", "playability_fairness",
        "open_obligation", "reachable_attractor",
    )

    def rank(self, candidates: list[StoryDecisionCandidate]) -> StoryCandidateRanking:
        eligible, rejected = self._apply_gates(candidates)
        return StoryCandidateRanking(
            eligible=sorted(eligible, key=lambda item: (-item.narrative_score, item.candidate_id)),
            rejected=rejected,
        )
```

Resource score is deliberately absent from this phase and enters only after this result in Phase 5.

- [ ] **Step 6: Run tests and commit**

Run: `python -m pytest backend/tests/test_siming_story_obligation_runtime.py backend/tests/test_siming_story_node_orchestrator.py -v`

Expected: PASS.

```powershell
git add backend/app/services/siming_story_obligation_runtime.py backend/app/services/siming_story_node_orchestrator.py backend/tests/test_siming_story_obligation_runtime.py backend/tests/test_siming_story_node_orchestrator.py
git commit -m "feat: manage narrative obligations and attractors"
```

### Task 4: Add the Story Runtime Harness Gate

**Files:**
- Create: `scripts/verification/verify_siming_story_runtime.py`
- Create: `.harness/profiles/siming-story-runtime.json`
- Modify: `docs/harness.md`
- Modify: `docs/INDEX.md`

**Interfaces:**
- Consumes: Tasks 1-3 standard scenario and SQLite graph.
- Produces: `.harness/verification/siming-story-runtime-report.json`.

- [ ] **Step 1: Implement the deterministic story verifier**

Seed N1-N5 and O2, apply the confirmed destruction outcome, close/reopen SQLite, and report `authored_runtime_separation`, `n3_divergence_resolved`, `n4_terminal_closed`, `n5_unreachable`, `o2_transformed_to_o6`, `no_resurrection`, and `attractor_recomputed`.

- [ ] **Step 2: Register the profile**

```json
{
  "schema_version": 1,
  "name": "siming-story-runtime",
  "order": 75,
  "script": "scripts/verification/verify_siming_story_runtime.py",
  "requires_godot": false,
  "max_attempts": 1,
  "result_artifact": ".harness/verification/siming-story-runtime-report.json",
  "description": "Backend proof for branch-scoped story nodes, permanent player closure, obligation transformation, and attractor reachability"
}
```

- [ ] **Step 3: Run the phase gate**

Run: `python scripts/verification/harness.py --profile siming-story-runtime`

Expected: PASS with all seven result IDs proved.

- [ ] **Step 4: Commit**

```powershell
git add scripts/verification/verify_siming_story_runtime.py .harness/profiles/siming-story-runtime.json docs/harness.md docs/INDEX.md
git commit -m "test: prove graph-backed story convergence"
```
