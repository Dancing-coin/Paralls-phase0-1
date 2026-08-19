# SGC-2 Derived Cognitive Graph Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task after the contract is approved.

**Goal:** Build one scoped, replayable derived graph projection without promoting graph output to truth.

**Spec:** `docs/superpowers/specs/world-character-siming-authority-mainline/siming-group-world-formalization/02-sgc-2-derived-cognitive-graph-contract.md`

**Prerequisite:** One approved authority-event projection reader and its privacy scope.

### Task 0: Source-reader admission gate

**Files:** `backend/app/services/siming_heavenly_graph_port.py`, `docs/superpowers/specs/world-character-siming-authority-mainline/siming-group-world-formalization/02-sgc-2-derived-cognitive-graph-contract.md`, `.harness/verification/`

- [ ] Name the allowlisted authority event/projection, reader principal, scope and policy revision.
- [ ] Confirm the source is already committed and replayable; otherwise record `owner-contract blocked` and stop before graph model changes.
- [ ] Record the source vector and graph contract revision in the package checkpoint.

### Task 1: Define source and query fixtures

**Files:** `backend/app/models/siming_heavenly_graph.py`, `backend/app/services/siming_heavenly_graph_port.py`, `backend/tests/test_siming_scoped_graph_correction.py`

- [ ] Extend the existing frozen graph models with only the missing source-vector, policy and redaction fields; preserve `HeavenlyGraphScope`, `GraphValidity`, revision-chain and batch idempotency validators.
- [ ] Add fixtures for source event vector, policy revision, dual-time query and visibility scope.
- [ ] Write RED tests for unlisted event family, widened scope, privacy redaction and invalid source revision.
- [ ] Run the focused file and record RED output.

### Task 2: Implement append-only derived correction

**Files:** `backend/app/services/in_memory_heavenly_graph.py`, `backend/app/services/siming_heavenly_graph_port.py`

- [ ] Persist only derived fields with provenance, validity, revision and redaction state.
- [ ] Append superseding/retracted/redacted derivations for source correction; never mutate or delete source facts.
- [ ] Invalidate dependent cache/checkpoint keys on source, policy or scope change.
- [ ] Add a read-only character summary adapter that cannot mutate five-pool memory.

### Task 3: Replay and Harness evidence

**Files:** `backend/tests/test_siming_scoped_graph_correction.py`, `scripts/verification/harness.py`, `scripts/verification/registry.py`, `.harness/profiles/sgc-2-derived-cognitive-graph.json`, `.harness/rules/sgc-2-derived-cognitive-graph.json`, `docs/harness.md`

- [ ] Add tests for full/tail graph equivalence, branch isolation and consumed-summary non-mutation.
- [ ] Register and run the selector named `sgc-2-derived-cognitive-graph` after focused pytest.
- [ ] Save graph full/tail digests, redaction evidence and checkpoint invalidation evidence under `.harness/verification/sgc-2/`.
- [ ] Synchronize graph spec, August status and checkpoint with evidence or blocked disposition.
