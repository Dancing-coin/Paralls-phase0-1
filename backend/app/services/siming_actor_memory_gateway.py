import json

from app.models.siming_actor_memory_read import (
    ActorMemoryReadRequest,
    ActorMemoryReadResult,
    ActorMemoryRevisionVector,
)
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.services.siming_continuation import digest


class ActorMemoryReadGateway:
    _MAX_DIGEST_CACHE_KEY_CHARS = 4096

    def __init__(self, runtime: CharacterAgentRuntime) -> None:
        self._runtime = runtime
        self._digest_cache: tuple[tuple[str, object], str] | None = None

    def read_digest(self, request: ActorMemoryReadRequest) -> str:
        reader = getattr(self._runtime, 'memory_record_read_token', None)
        token = reader(request.actor_id) if callable(reader) else None
        key = None if token is None else (json.dumps(request.model_dump(mode='json'),
            ensure_ascii=True, sort_keys=True, separators=(',', ':')), token)
        cached = self._digest_cache
        if key is not None and cached is not None and key == cached[0] and reader(request.actor_id) == token:
            return cached[1]
        value = digest(self.read(request).model_dump(mode='json'))
        # 只留一个有界请求键和原完整摘要；版本在计算中变化时不能保存。
        if (key is not None and len(key[0]) <= self._MAX_DIGEST_CACHE_KEY_CHARS
                and reader(request.actor_id) == token):
            self._digest_cache = key, value
        return value

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
