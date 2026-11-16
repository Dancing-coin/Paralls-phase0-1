from dataclasses import dataclass
from threading import RLock
from time import monotonic_ns
from copy import deepcopy

from app.models.feasibility_response import FeasibilityResponse


@dataclass
class ProposalRecord:
    output: object
    submitted_at: int
    status: str = "pending"
    abort_reason: str | None = None
    feasibility_response: FeasibilityResponse | None = None


class SimingProposalTracker:
    def __init__(self, *, now_ts_provider=None) -> None:
        self._proposals: dict[str, ProposalRecord] = {}
        self._lock = RLock()
        self.now_ts = now_ts_provider or (lambda: monotonic_ns() // 1_000_000)

    def register_proposal(self, proposal_id: str, output: object, submitted_at: int | None = None) -> bool:
        with self._lock:
            submitted_at = self.now_ts() if submitted_at is None else submitted_at
            self.cleanup_old_proposals(submitted_at)
            if proposal_id in self._proposals:
                if self._proposals[proposal_id].output != output:
                    raise ValueError("duplicate_environment_proposal")
                return False
            self._proposals[proposal_id] = ProposalRecord(deepcopy(output), submitted_at)
            return True

    def accept_response(self, response: FeasibilityResponse, current_ts: int) -> object | None:
        with self._lock:
            record = self._proposals.get(response.proposal_ref)
            if record is None or record.status != "pending":
                return None
            if current_ts < record.submitted_at or current_ts - record.submitted_at >= 5000:
                record.abort_reason = "window_expired"
            elif not response.feasible:
                record.abort_reason = ",".join(response.constraints) or "infeasible"
            if record.abort_reason:
                record.status = "aborted"
                return None
            record.status = "requested"
            record.feasibility_response = response.model_copy(deep=True)
            return deepcopy(record.output)

    def get(self, proposal_id: str) -> ProposalRecord | None:
        with self._lock:
            return deepcopy(self._proposals.get(proposal_id))

    def abort_proposal(self, proposal_id: str, reason: str) -> None:
        with self._lock:
            record = self._proposals.get(proposal_id)
            if record is not None and record.status in {"pending", "requested"}:
                record.status, record.abort_reason = "aborted", reason

    def claim_execution(self, event) -> bool:
        with self._lock:
            record = self._proposals.get(event.payload.get("proposal_ref"))
            if record is None or record.status != "requested" or record.feasibility_response is None:
                return False
            original, response = record.output, record.feasibility_response
            if (self.now_ts() - record.submitted_at >= 5000
                    or event.payload.get("feasibility_ref") != response.response_id
                    or (event.room_id, event.scene_id, event.zone_id, event.correlation_id) !=
                       (original.room_id, original.scene_id, original.zone_id, original.correlation_id)
                    or any(event.payload.get(key) != value for key, value in original.payload.items())):
                self.abort_proposal(event.payload.get("proposal_ref"), "invalid_or_expired_request")
                return False
            record.status = "executing"
            return True

    def complete_execution(self, proposal_id: str, *, success: bool) -> None:
        with self._lock:
            record = self._proposals.get(proposal_id)
            if record is not None and record.status == "executing":
                record.status = "executed" if success else "aborted"
                record.abort_reason = None if success else "execution_rejected"

    def status(self, proposal_id: str) -> str | None:
        with self._lock:
            record = self._proposals.get(proposal_id)
            return record.status if record else None

    def cleanup_old_proposals(self, current_ts: int | None = None, max_age: int = 60000) -> None:
        with self._lock:
            current_ts = self.now_ts() if current_ts is None else current_ts
            for proposal_id, record in list(self._proposals.items()):
                age = current_ts - record.submitted_at
                if age >= 5000 and record.status in {"pending", "requested"}:
                    record.status, record.abort_reason = "aborted", "window_expired"
                if age > max_age:
                    del self._proposals[proposal_id]
