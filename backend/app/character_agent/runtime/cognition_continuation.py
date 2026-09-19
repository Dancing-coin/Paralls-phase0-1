"""跨 worker 的请求只含不可变数据；续执行与结束钩子只留在 owner。"""

from collections.abc import Callable, Generator
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class PreparedCognitionJob:
    job_id: str
    turn_id: str
    stage: int
    task_kind: str
    actor_id: str
    request_json: bytes
    generation: int
    source_revision_vector: tuple[tuple[str, str], ...]
    read_set_digest: str
    idempotency_key: str
    activation_lock_ref: str
    activation_token: str
    deadline_monotonic: float
    token: str


@dataclass(frozen=True)
class CognitionAdvance:
    status: Literal['pending', 'completed', 'requeued', 'zero_write']
    next_job: PreparedCognitionJob | None = None
    result: object = None
    reason: str = ''
    # 重复回执中的 next_job 已交付，调度器不得再次发起该 job 的 provider 调用。
    replayed: bool = False


@dataclass(frozen=True)
class CognitionRequest:
    task_kind: str
    request_json: bytes
    policy_id: str = ''


@dataclass
class PendingCognitionTurn:
    turn_id: str
    actor_id: str
    producer_ts: int
    source_kind: str
    steps: Generator[CognitionRequest, dict[str, object], object]
    deadline_monotonic: float
    activation_lock_ref: str
    activation_token: str
    activation_is_current: Callable[[str, str], bool] | None
    on_finished: Callable[[str, str], None] | None
    owner_thread: int
    stage: int = 0
    job: PreparedCognitionJob | None = None
    policy_id: str = ''
