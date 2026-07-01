# Actor-Local Perception And Fact Production Design

Status: `execution-active`

Date: `2026-06-29`

Parent:

- [2026-06-29-world-character-siming-authority-mainline-master-design.md](</d:/Users/User/Documents/paralls-phase-0-demo/docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-world-character-siming-authority-mainline-master-design.md>)

## Scope

Define how actors continuously sample the world and emit structured facts without depending on demo-controller ownership.

## Required Outcomes

1. actor-local visual / auditory / embodied / environmental sampling ownership
2. reusable cone/range/LOS semantics
3. fact emission through standard emitters and canonical fact fabric
4. support for actor->actor, actor->object, and actor->environment noticing

## Execution Truth

This design now has direct implementation evidence in the repository.

Current implementation/proof anchors include:

- `scripts/character/ActorPerceptionSampler.gd`
- `scripts/character/ActorPerceptionTargetResolver.gd`
- `scripts/character/CharacterReplica.gd`
- `backend/tests/test_relationship_overlay_static.py`
- `backend/tests/test_visual_fact_pipeline.py`
- `backend/tests/test_character_actor_reacquisition_runtime.py`
- `python scripts/verification/verify_actor_local_perception.py`
