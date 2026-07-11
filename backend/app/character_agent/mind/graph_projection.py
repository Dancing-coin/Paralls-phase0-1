from __future__ import annotations

from typing import Protocol


class GraphMemoryProjectionProvider(Protocol):
    def project_memory_context(
        self,
        *,
        actor_id: str,
        memory_bundle: dict[str, object],
    ) -> dict[str, object]: ...


class NoopGraphMemoryProjectionProvider:
    def project_memory_context(
        self,
        *,
        actor_id: str,
        memory_bundle: dict[str, object],
    ) -> dict[str, object]:
        return {}
