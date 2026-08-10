from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.models import ActivationProposal
from verify_phase3_common import root, run_focused, write_report


def main() -> int:
    focused, log = run_focused()
    registry = CharacterProfileRegistry.from_directory(
        root() / "assets" / "characters" / "profiles"
    )
    store = GameplayEventStore()
    authority = ProfileActivationAuthority(registry=registry, store=store)
    proposal = ActivationProposal(
        proposal_id="proposal:harness:p3a",
        profile_ref="character:char_a",
        world_ref="world:harness",
        package_revision="package:bakery-authored-agents:v1",
        policy_revision="policy:population:v1",
        activation_reason="harness",
        scope_grant=("actor:self",),
        cadence_class="simulation",
        expected_revisions={"population:world:harness": 0},
        idempotency_key="activation:harness:p3a",
        correlation_id="corr:harness:p3a",
        source_ref="population:harness",
    )
    receipt = authority.commit(proposal)
    denied = authority.commit(
        proposal.model_copy(
            update={
                "profile_ref": "character:npc:1",
                "proposal_id": "proposal:harness:p3a:denied",
                "idempotency_key": "activation:harness:p3a:denied",
            }
        )
    )
    report = {
        "overall_passed": focused and receipt.committed and denied.zero_write,
        "predecessors": {"phase1d": True, "phase2": True},
        "receipt": receipt.model_dump(mode="json"),
        "revision_vector": receipt.revision_vector,
        "replay_hash": receipt.replay_hash,
        "scope_redaction": {
            "scope": list(receipt.scope),
            "redaction": receipt.redaction,
        },
        "zero_write": denied.zero_write,
        "stop_reason": denied.stop_reason,
        "focused_log": log,
    }
    return write_report("phase3a-profile-activation", report)


if __name__ == "__main__":
    raise SystemExit(main())
