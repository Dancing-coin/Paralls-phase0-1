# Task 4 — Durable actor-private behavior-policy lifecycle

## Completed

- Added a strict `BehaviorPolicyRecord` and `BehaviorPolicyConsumption` contract
  with the closed lifecycle statuses: `candidate`, `accepted`, `applied`,
  `expired`, `superseded`, `rolled_back`, and `rejected`.
- Added an append-only `BehaviorPolicyStore` backed by the existing
  actor-scoped `CharacterAgentSessionStore`; it adds no world-truth writer or
  independent database. It restores state from the same durable session event
  history and exposes a compact actor-private continuity projection.
- Enforced actor isolation, idempotent proposal/reconciliation/consumption,
  changed-payload idempotency-key rejection, expiration, consumption limits,
  supersession, and rollback-on-success.
- Replaced L3's process-local `_consumed_behavior_policy_ids` and working
  memory scan with a runtime-supplied actor-private policy snapshot. L3 only
  admits an evidence-backed `accepted` record.
- Recovery policies exclude only the failed candidate for the eligible L3
  pass. Recall policies raise bounded memory recall limits (at most 16 entries
  per pool and 2400 tokens) without changing profile truth, authority state,
  world facts, or past settlement.
- Runtime evaluation now writes candidate and reconciliation session events,
  passes accepted policy state to L3, consumes it against the canonical turn
  only after a model decision, and carries policy state in the existing graph
  continuity snapshot.

## Evaluator-candidate gate changes

`backend/app/character_agent/services/character_behavior_evaluation.py` is a
required Task 4 change, not Task 5/6 scope: it is the producer of the policy
candidate that the lifecycle store validates. Its policy type values now match
the closed durable record vocabulary (`recovery`, `recall`,
`skill_calibration`, `cadence`) and its initial status is `candidate` rather
than the obsolete `candidate_only`. Without that alignment, runtime could not
form the strict record or evidence-gate it into `accepted` for L3.

The corresponding evaluator test changes verify those producer values and the
runtime's session-event `candidate` → evidence-qualified `accepted` sequence.

## Test-first evidence

- RED observed: `python -m pytest backend/tests/test_behavior_policy_lifecycle.py -v`
  initially failed during collection with
  `ModuleNotFoundError: app.character_agent.models.behavior_policy`, before
  the durable model/store existed.
- Focused lifecycle/planner/evaluation suite: 61 passed.
- Continuity, turn-recovery, and memory-recall regressions: 28 passed (four
  pre-existing FastAPI deprecation warnings only).
- Full backend run from repository root was attempted with
  `python -m pytest backend -v`. The execution host returned after 30 seconds
  while the process had reached 12% of 5,389 collected tests with no reported
  failures; it did not yield a final result, so this is **not** a full-suite
  pass claim.

## Boundaries and remaining risk

- Policy records stay actor-private and only influence L3 candidate selection
  or bounded recall context. They do not write world truth or alter authored
  profile data.
- No Godot files changed; no runtime/editor proof is claimed.

## Fix round 1

Addressed all seven review findings:

1. Evidence admission now requires explicit qualified/complete evidence,
   confidence >= 0.8, failure domains, and at least two lineage refs.
2. Records/events carry and validate branch, valid-time, causation,
   correlation, source revision, idempotency, policy revision, and transition
   revision metadata.
3. Lifecycle transitions use a closed transition table; terminal states cannot
   reopen and each transition increments `transition_revision`.
4. Consumption stores exact turn/causation/correlation links; successful
   settlement rolls back only an exact matching link.
5. Restore/load fails closed on malformed policy state and accepts only newer
   transition revisions; equal conflicting revisions are rejected.
6. Compatible failures within `failure_window` merge and increment durable
   `failure_count`.
7. Policy consumption is recorded for fallback/continuity-floor turns too, so
   an ineligible use cannot leak into a later turn.

Settlement linkage is intentionally strict: a legacy settlement without exact
canonical `turn_id`, `branch_id`, `causation_id`, and `correlation_id` does not
create or alter a durable policy. This avoids unsafe inference across
interleaved turns.

Verification command:

```text
python -m pytest backend/tests/test_behavior_policy_lifecycle.py backend/tests/test_character_behavior_evaluation.py backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_turn_recovery.py backend/tests/test_character_graph_continuity_store.py backend/tests/test_character_memory_recall_policy.py -v
```

Result: **93 passed, 4 pre-existing FastAPI deprecation warnings**.

## Fix round 2

Addressed the rereview findings:

1. Evidence now carries explicit settlement/context/evidence-ref fields. Runtime admission verifies refs against the actor timeline, requires non-empty substantive payloads, a canonical settlement ref/status, context hash, complete/qualified evidence, confidence >= 0.8, and distinct lineage refs before accepting or exposing a policy to L3.
2. Policy identity fields use bounded non-empty shape validation. Runtime checks canonical branch, valid-at, causation, correlation, and source revision against the settlement/timeline context before writing a policy.
3. Consumption/rollback links include branch ID and require exact branch/turn/causation/correlation matching; missing or mismatched branch data is policy-inert.
4. Continuity restore and event replay reject higher-revision status regressions or reopenings unless the status is unchanged or a legal successor under the closed transition table.
5. Compatible failure merges persist every contributing proposal idempotency key plus its proposal digest; replaying an exact merged proposal is deduplicated without incrementing `failure_count`, while altered payloads conflict. Out-of-order older proposals do not merge, and consumption without complete linkage is policy-inert.

Verification command:

```text
python -m pytest backend/tests/test_behavior_policy_lifecycle.py backend/tests/test_character_behavior_evaluation.py backend/tests/test_character_agent_l3_planning.py -q
```

Result: **69 passed in 1.80s**.

Additional covering command:

```text
python -m pytest backend/tests/test_behavior_policy_lifecycle.py backend/tests/test_character_behavior_evaluation.py backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_turn_recovery.py backend/tests/test_character_graph_continuity_store.py backend/tests/test_character_memory_recall_policy.py -v
```

Result: **97 passed, 4 pre-existing FastAPI deprecation warnings in 4.18s**.

## Fix round 3

Addressed the final rereview issues:

1. Policy `source_revision` now comes exclusively from the persisted settlement event's positive canonical `event_index`. A supplied settlement `source_revision` must match exactly; omitted/invalid event index and mismatches are rejected without policy admission. The regression suite verifies the valid pre-evaluation event index and both mismatch and missing-index cases.
2. Duplicate consumption replay now compares supplied branch, causation, and correlation IDs with the durable consumption link. Exact linkage returns an idempotent replay; missing or mismatched linkage returns a policy-inert conflict without writing.

Verification command:

```text
python -m pytest backend/tests/test_behavior_policy_lifecycle.py backend/tests/test_character_behavior_evaluation.py backend/tests/test_character_agent_l3_planning.py -q
```

Result: **72 passed in 1.98s**.

Additional covering command:

```text
python -m pytest backend/tests/test_behavior_policy_lifecycle.py backend/tests/test_character_behavior_evaluation.py backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_turn_recovery.py backend/tests/test_character_graph_continuity_store.py backend/tests/test_character_memory_recall_policy.py -q
```

Result: **100 passed, 4 pre-existing FastAPI deprecation warnings in 4.35s**.
