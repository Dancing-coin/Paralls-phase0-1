from app.models.siming_actor_memory_read import (
    ActorMemoryReadRequest,
    ActorMemoryReadResult,
    ActorMemoryRevisionVector,
)
from app.services.character_agent_runtime import CharacterAgentRuntime


class ActorMemoryReadGateway:
    def __init__(self, runtime: CharacterAgentRuntime) -> None:
        self._runtime = runtime

    def read(self, request: ActorMemoryReadRequest) -> ActorMemoryReadResult:
        bundle = self._runtime.get_memory_record_bundle(
            request.actor_id,
            story_branch_id=request.story_branch_id,
            valid_at=request.valid_at,
        )
        vector = ActorMemoryRevisionVector.from_bundle(bundle)
        complete = request.expected_revision_vector in (None, vector)
        return ActorMemoryReadResult(
            actor_id=request.actor_id,
            story_branch_id=request.story_branch_id,
            valid_at=request.valid_at,
            revision_vector=vector,
            bundle=bundle,
            completeness="complete" if complete else "memory_surface_incomplete",
            reason="" if complete else "revision_vector_mismatch",
        )
