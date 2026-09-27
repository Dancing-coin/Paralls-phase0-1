# Task 8 report — advisory character embodied episodes

## Completed

- Added `CandidateActionObservation`, closed `EpisodeFailureClass`, and immutable actor-private `EmbodiedEpisodeRecord` in `backend/app/character_agent/models/embodied_episode.py`.
- Added pure `EmbodiedEpisodeService.begin`/`complete` in `backend/app/character_agent/services/embodied_episode_service.py`. Confirmed success requires an accepted authority result, authority reference, post-capture reference, and matching expected observation. Recoverable outcomes carry a typed recovery candidate.
- Added `VLAAdvisoryCandidateAdapter` in `backend/app/world_runtime/vla_percept_bridge.py`. It validates request/capture provenance, grounding catalog identity, and reviewed registry availability; it rejects stale/scope-mismatched and body/control/world-bearing provider candidates.
- Added fixed fact precedence and `record_percept_conflict` to `backend/app/character_agent/reasoning/actor_scene_knowledge.py`. It retains the higher-priority fact, records both refs, marks the entry contested, and requests fresh observation.
- Added actor-private runtime begin/complete/get episode methods in `backend/app/character_agent/runtime/runtime_loop.py`. Completion records recovery candidates and explicit re-observation requests locally; it does not write settlement/ESM/Gameplay/Godot state.
- Added/updated focused tests in `backend/tests/test_embodied_episode_service.py`, `backend/tests/test_vla_percept_bridge.py`, and `backend/tests/test_vla_runtime_consumption.py`.

## Interfaces

- `EmbodiedEpisodeService.begin(turn, candidate, pre_capture_ref)`
- `EmbodiedEpisodeService.complete(episode, authority_result, post_capture_ref, observed_state)`
- `VLAAdvisoryCandidateAdapter.to_candidate_action(result)`
- `CharacterAgentRuntime.begin_embodied_episode(...)` / `complete_embodied_episode(...)`

## Verification

- Red phase: `python -m pytest tests/test_embodied_episode_service.py -v` failed at collection with `ModuleNotFoundError: app.character_agent.models.embodied_episode`, as expected before implementation.
- Focused verification: `python -m pytest backend/tests/test_embodied_episode_service.py backend/tests/test_vla_percept_bridge.py backend/tests/test_vla_runtime_consumption.py backend/tests/test_character_behavior_evaluation.py -v` — **27 passed**.
- Adjacent regression verification: ASK, affordance registry, and execution contract suites — **25 passed** (four existing FastAPI deprecation warnings).
- `python -m compileall -q` on all Task 8 production files — passed.
- `git diff --check` — passed.
- Required full backend suite: `python -m pytest -v` was blocked during collection by 10 unrelated import-path errors (`ModuleNotFoundError` for `backend`, `tools`, and `scripts.verification` from the backend working directory); no Task 8 test failure was reported.

## Commit

- `a78dc0b1 feat: add advisory character embodied episodes`

## Concerns / next step

- This task intentionally records evidence and recovery only. The later archive-door vertical must supply the real execution/authority/post-capture sequence; no VLA result can dispatch it or settle world truth.

## Fix round 1 (review retry)

- Added stable completion idempotency (`episode_ref + authority result ref + post-capture ref`), equivalent replay return, conflicting replay rejection, persisted begin ownership checks, and explicit non-empty observation requirement for success.
- Enforced `committed authority > structured percept > provider advisory > model inference` in ASK admission; lower-priority disagreement records `percept_conflict` and requests fresh observation.
- VLA candidate admission now validates subject, target, world anchor, capture root/id, source lineage, source frame index, clock/tick, and request provenance against the PQF envelope.
- Normalized HTTP VLA `candidate_entity_refs`, `candidate_affordance_refs`, and `evidence_artifact_refs` into the reviewed semantic candidate without adding control/world fields.

### Fix-round verification

- Focus + adjacent suite: `python -m pytest backend/tests/test_embodied_episode_service.py backend/tests/test_vla_percept_bridge.py backend/tests/test_vla_runtime_consumption.py backend/tests/test_character_behavior_evaluation.py backend/tests/test_actor_scene_knowledge_runtime.py backend/tests/test_scene_affordance_registry.py backend/tests/test_character_execution_contract.py -v` — **57 passed**, 4 existing FastAPI deprecation warnings.
- `python -m compileall -q` on all Task 8 production files — passed.
- `git diff --check` — passed.

### Fix-round commit

- `d3e99d54 fix: harden advisory embodied episode replay`

## Fix round 2 (precedence promotion closure)

- Lower-priority admissions now retain the existing higher-priority source,
  world-truth marker, summary, confidence, and claim even when the incoming
  claim is equivalent but has higher confidence. Evidence refs and lineage are
  still appended; disagreements continue through `percept_conflict`.
- Added regression coverage for committed-authority followed by equal-claim
  provider advisory input.

### Fix-round 2 verification

- Focus + adjacent suite — **58 passed**, 4 existing FastAPI deprecation warnings.
- `python -m compileall -q` on Task 8 production files — passed.
- `git diff --check` — passed.
