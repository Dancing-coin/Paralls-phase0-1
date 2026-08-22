# Phase 6 Adaptive Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an online LLM propose one local causal bridge after player divergence while deterministic validators retain all authority over facts, actor knowledge, terminal nodes, resources, autonomy, and graph commits.

**Architecture:** Extend the existing Siming LLM provider transport with a typed adaptive-bridge proposal operation and safe request audit metadata. Validate proposals against compiled graph context, actor-memory reads, story state, and resource matches; only accepted proposals become new runtime story nodes, while dispatch remains deferred to `SimingRuntime.tick(...)` in Phase 7.

**Tech Stack:** Python `>=3.11`, Pydantic v2, existing `httpx` Siming provider, existing graph/story/resource services, pytest, Harness Engineering.

## Global Constraints

- Requires passing Phase 5 `siming-resource-staging`.
- Allowed patterns are exactly `private_confrontation`, `consequence_reveal`, `relationship_shift`, `alternative_opportunity`, `delayed_payoff`, and `aftermath`.
- A bridge fills one local causal gap; it cannot invent world facts, resurrect terminal nodes, write actor memory, require absent resources, or override actor refusal.
- LLM output remains a proposal and never directly writes graph state, activates nodes, stages resources, or publishes catalysts.
- `private_confrontation` requires a complete `char_b` memory surface and actual Event/Observation evidence that `char_b` observed the destruction.
- Existing `SimingLlmCandidateProvider` routes and failover are reused; do not add a second HTTP stack.
- Audit records provider, route ID, model, request ID, correlation ID, latency, response artifact hash/safe ref, proposal ID, validation result, graph transaction ref, and selected node ref.
- Audit excludes API keys, raw private caches, hidden state, and chain-of-thought.

---

### Task 1: Define Typed Bridge Proposal and Validation Contracts

**Files:**
- Create: `backend/app/models/siming_adaptive_bridge.py`
- Create: `backend/tests/test_siming_adaptive_bridge_models.py`

**Interfaces:**
- Consumes: resource realization request and story/actor reference IDs.
- Produces: `AdaptiveBridgeNodeProposal`, `GeneratedAdaptiveBridgeProposalBatch`, `AdaptiveBridgeValidationResult`, and safe provider audit metadata.

- [ ] **Step 1: Write failing pattern and forbidden-field tests**

```python
def test_bridge_rejects_unapproved_pattern() -> None:
    with pytest.raises(ValidationError, match="pattern"):
        AdaptiveBridgeNodeProposal(**proposal_payload(pattern="time_travel_reset"))


@pytest.mark.parametrize("field", ["world_fact_write", "actor_memory_write", "catalyst", "chain_of_thought"])
def test_bridge_rejects_authority_fields(field: str) -> None:
    payload = proposal_payload(pattern="private_confrontation")
    payload[field] = "forbidden"
    with pytest.raises(ValidationError):
        AdaptiveBridgeNodeProposal(**payload)
```

- [ ] **Step 2: Run tests and confirm the module is absent**

Run: `python -m pytest backend/tests/test_siming_adaptive_bridge_models.py -v`

Expected: FAIL with missing module.

- [ ] **Step 3: Add exact strict proposal models**

```python
AdaptiveBridgePattern = Literal[
    "private_confrontation", "consequence_reveal", "relationship_shift",
    "alternative_opportunity", "delayed_payoff", "aftermath",
]

class StrictBridgeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class AdaptiveBridgeNodeProposal(StrictBridgeModel):
    proposal_id: str
    pattern: AdaptiveBridgePattern
    correlation_id: str
    causal_gap_ref: str
    title: str
    target_actor_id: str | None = None
    supporting_fact_refs: list[str]
    required_actor_memory_refs: list[str] = Field(default_factory=list)
    obligation_refs: list[str] = Field(default_factory=list)
    attractor_refs: list[str] = Field(default_factory=list)
    realization_request: ResourceRealizationRequest
    autonomy_reason: str

class SimingLlmProposalAudit(StrictBridgeModel):
    provider: str
    route_id: str
    model: str
    request_id: str
    correlation_id: str
    latency_ms: int = Field(ge=0)
    response_artifact_hash: str

class GeneratedAdaptiveBridgeProposalBatch(StrictBridgeModel):
    proposals: list[AdaptiveBridgeNodeProposal]
    audit: SimingLlmProposalAudit

class AdaptiveBridgeValidationResult(StrictBridgeModel):
    accepted: bool
    proposal_id: str
    reason_codes: list[str] = Field(default_factory=list)
    graph_transaction_ref: str | None = None
    runtime_node_ref: str | None = None
```

`AdaptiveBridgeValidationResult` contains `accepted`, ordered `reason_codes`, `proposal_id`, optional `graph_transaction_ref`, and optional `runtime_node_ref`.

- [ ] **Step 4: Run model tests and commit**

Run: `python -m pytest backend/tests/test_siming_adaptive_bridge_models.py -v`

Expected: PASS.

```powershell
git add backend/app/models/siming_adaptive_bridge.py backend/tests/test_siming_adaptive_bridge_models.py
git commit -m "feat: define adaptive bridge proposal contracts"
```

### Task 2: Extend the Existing Online Provider With Typed Story Proposals

**Files:**
- Modify: `backend/app/services/siming_llm_provider.py`
- Modify: `backend/tests/test_siming_llm_provider.py`
- Create: `backend/tests/test_siming_llm_adaptive_bridge_provider.py`

**Interfaces:**
- Consumes: current provider routes, request functions, and Task 1 models.
- Produces: `generate_adaptive_bridge_proposals(*, compiled_context, correlation_id)` on disabled, router, HTTP, and fake providers.

- [ ] **Step 1: Write failing HTTP parsing and audit tests**

```python
def test_http_provider_returns_typed_bridge_batch(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response_with_bridge(private_confrontation_payload()))
    provider = HttpSimingLlmCandidateProvider(
        api_key="secret", endpoint="https://example.test/v1/responses",
        model="model-live", timeout_seconds=8, route_id="route-live",
    )
    batch = provider.generate_adaptive_bridge_proposals(
        compiled_context=compiled_context_payload(), correlation_id="corr:destroy:1",
    )
    assert batch.proposals[0].pattern == "private_confrontation"
    assert batch.audit.route_id == "route-live"
    assert batch.audit.model == "model-live"
    assert "secret" not in batch.model_dump_json()
```

- [ ] **Step 2: Run provider tests and confirm the method is absent**

Run: `python -m pytest backend/tests/test_siming_llm_provider.py backend/tests/test_siming_llm_adaptive_bridge_provider.py -v`

Expected: FAIL with `AttributeError: generate_adaptive_bridge_proposals`.

- [ ] **Step 3: Factor one shared HTTP request helper**

```python
def _post_json(self, payload: dict[str, object]) -> tuple[dict[str, object], str, int, str]:
    started = time.monotonic()
    response = httpx.post(self._endpoint, headers={"Authorization": f"Bearer {self._api_key}"}, json=payload, timeout=self._timeout_seconds)
    response.raise_for_status()
    raw = response.content
    return response.json(), response.headers.get("x-request-id", ""), int((time.monotonic() - started) * 1000), hashlib.sha256(raw).hexdigest()
```

Refactor existing `generate_candidates` to use this helper without changing its public return type.

- [ ] **Step 4: Implement typed bridge request/response on all providers**

```python
def generate_adaptive_bridge_proposals(
    self, *, compiled_context: dict[str, object], correlation_id: str,
) -> GeneratedAdaptiveBridgeProposalBatch:
    data, request_id, latency_ms, artifact_hash = self._post_json(
        self._adaptive_bridge_payload(compiled_context, correlation_id)
    )
    proposals = [AdaptiveBridgeNodeProposal.model_validate(item) for item in self._bridge_items(data)]
    return GeneratedAdaptiveBridgeProposalBatch(
        proposals=proposals,
        audit=SimingLlmProposalAudit(
            provider=self._provider_name, route_id=self._route_id, model=self._model,
            request_id=request_id, correlation_id=correlation_id,
            latency_ms=latency_ms, response_artifact_hash=artifact_hash,
        ),
    )
```

Disabled returns an empty proposal list with `provider="disabled"`; Router failover returns the first non-empty valid batch and raises the last provider error when all routes fail; Fake accepts explicit proposal batches for unit tests only.

- [ ] **Step 5: Run all provider tests and commit**

Run: `python -m pytest backend/tests/test_siming_llm_provider.py backend/tests/test_siming_llm_adaptive_bridge_provider.py -v`

Expected: PASS for OpenAI Responses/chat-compatible parsing, router failover, invalid schema, timeout, safe audit, disabled, and fake behavior.

```powershell
git add backend/app/services/siming_llm_provider.py backend/tests/test_siming_llm_provider.py backend/tests/test_siming_llm_adaptive_bridge_provider.py
git commit -m "feat: generate typed adaptive bridge proposals"
```

### Task 3: Validate and Commit New Runtime Bridge Nodes

**Files:**
- Create: `backend/app/services/siming_adaptive_bridge.py`
- Create: `backend/tests/test_siming_adaptive_bridge.py`

**Interfaces:**
- Consumes: compiled context, `ActorMemoryReadGateway`, story runtime, obligation runtime, resource registry, and typed provider batch.
- Produces: deterministic validation audit and a new latent runtime node for accepted proposals.

- [ ] **Step 1: Write the accepted private-confrontation test**

```python
def test_private_confrontation_commits_new_node_when_all_gates_pass(bridge, valid_batch) -> None:
    result = bridge.validate_and_commit(valid_batch.proposals[0], provider_audit=valid_batch.audit)
    assert result.accepted is True
    assert result.runtime_node_ref == "runtime:bridge:proposal:private-confrontation:1"
    assert result.graph_transaction_ref
    assert bridge.story_runtime.read_node(result.runtime_node_ref).lifecycle == "latent"
```

- [ ] **Step 2: Write rejection matrix tests**

```python
@pytest.mark.parametrize("fixture_name,reason", [
    ("missing_fact", "supporting_fact_missing"),
    ("terminal_reuse", "terminal_node_resurrection"),
    ("incomplete_memory", "memory_surface_incomplete"),
    ("no_observation", "actor_did_not_observe"),
    ("closed_obligation", "obligation_not_open"),
    ("missing_resource", "resource_unavailable"),
    ("actor_refusal", "actor_autonomy_rejected"),
])
def test_bridge_rejection_matrix(request, bridge, fixture_name, reason) -> None:
    result = bridge.validate_and_commit(request.getfixturevalue(fixture_name))
    assert result.accepted is False
    assert reason in result.reason_codes
    assert result.runtime_node_ref is None
```

- [ ] **Step 3: Run tests and confirm the service is absent**

Run: `python -m pytest backend/tests/test_siming_adaptive_bridge.py -v`

Expected: FAIL with missing module.

- [ ] **Step 4: Implement fixed-order validation**

```python
class SimingAdaptiveBridge:
    def validate_and_commit(
        self, proposal: AdaptiveBridgeNodeProposal,
        *, provider_audit: SimingLlmProposalAudit,
    ) -> AdaptiveBridgeValidationResult:
        checks = (
            self._validate_schema_and_pattern,
            self._validate_existing_facts,
            self._validate_no_terminal_resurrection,
            self._validate_actor_memory,
            self._validate_open_obligations,
            self._validate_autonomy,
            self._validate_resource_match,
        )
        reasons = [reason for check in checks for reason in check(proposal)]
        if reasons:
            return self._record_rejection(proposal, provider_audit, reasons)
        return self._commit_new_runtime_node(proposal, provider_audit)
```

For `private_confrontation`, `_validate_actor_memory` reads `char_b`, requires completeness `complete`, and requires both an Event and Observation ref matching the confirmed destruction source. `_commit_new_runtime_node` uses ID `runtime:bridge:<proposal_id>`, lifecycle `latent`, and causal basis refs from validated facts/obligations. It must not call any actor memory write or event producer.

- [ ] **Step 5: Run bridge tests and commit**

Run: `python -m pytest backend/tests/test_siming_adaptive_bridge.py -v`

Expected: PASS for the full rejection matrix, idempotent proposal replay, audit completeness, new node IDs, and absence of dispatch/memory writes.

```powershell
git add backend/app/services/siming_adaptive_bridge.py backend/tests/test_siming_adaptive_bridge.py
git commit -m "feat: validate adaptive bridge story nodes"
```

### Task 4: Add the Adaptive Bridge Harness Gate

**Files:**
- Create: `scripts/verification/verify_siming_adaptive_bridge.py`
- Create: `.harness/profiles/siming-adaptive-bridge.json`
- Modify: `docs/harness.md`
- Modify: `docs/INDEX.md`

**Interfaces:**
- Consumes: Tasks 1-3 with fake provider input only for deterministic phase proof.
- Produces: `.harness/verification/siming-adaptive-bridge-report.json`; live provider proof remains Phase 7.

- [ ] **Step 1: Implement deterministic proposal/validator verification**

Seed the post-destruction graph and `char_b` observation, pass a typed fake `private_confrontation` proposal through the real validators, and emit `typed_proposal`, `existing_fact_only`, `char_b_observation_gate`, `open_o6_gate`, `resource_gate`, `no_terminal_resurrection`, `no_actor_memory_write`, and `new_runtime_node_committed`.

- [ ] **Step 2: Register the profile**

```json
{
  "schema_version": 1,
  "name": "siming-adaptive-bridge",
  "order": 77,
  "script": "scripts/verification/verify_siming_adaptive_bridge.py",
  "requires_godot": false,
  "max_attempts": 1,
  "result_artifact": ".harness/verification/siming-adaptive-bridge-report.json",
  "description": "Backend proof for typed adaptive bridge proposals, deterministic validation, and authority-safe runtime node commit"
}
```

- [ ] **Step 3: Run the phase gate**

Run: `python scripts/verification/harness.py --profile siming-adaptive-bridge`

Expected: PASS with all eight result IDs proved; this phase does not claim a live LLM call.

- [ ] **Step 4: Commit**

```powershell
git add scripts/verification/verify_siming_adaptive_bridge.py .harness/profiles/siming-adaptive-bridge.json docs/harness.md docs/INDEX.md
git commit -m "test: prove adaptive bridge validation"
```
