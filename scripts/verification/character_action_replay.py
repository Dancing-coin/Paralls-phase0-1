from __future__ import annotations

from hashlib import sha256
import json
from copy import deepcopy


class CharacterActionReplayTrace:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def append(self, tick: int, proposal: dict[str, object], admission: dict[str, object], command: dict[str, object], evidence: list[dict[str, object]], authority: dict[str, object]) -> None:
        self.records.append({
            "tick": tick, "proposal": deepcopy(proposal), "admission": deepcopy(admission),
            "command": deepcopy(command), "evidence": deepcopy(evidence), "authority": deepcopy(authority),
        })

    def replay(self) -> dict[str, object]:
        normalized = json.dumps(self.records, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        digest = "sha256:" + sha256(normalized.encode()).hexdigest()
        authority = json.dumps([r["authority"] for r in self.records], sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return {
            "record_count": len(self.records),
            "trace_digest": digest,
            "authority_digest": "sha256:" + sha256(authority.encode()).hexdigest(),
            "dynamic_rigidbody_bitwise_determinism": False,
        }
