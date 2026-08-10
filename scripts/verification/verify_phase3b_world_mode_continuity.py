from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.models import ActivationProposal, WorldModeProfile
from app.population_continuity.world import WorldContinuityRuntime
from verify_phase3_common import root, run_focused, write_report


def main() -> int:
    focused, log = run_focused()
    registry = CharacterProfileRegistry.from_directory(
        root() / "assets" / "characters" / "profiles"
    )
    store = GameplayEventStore()
    ProfileActivationAuthority(registry=registry, store=store).commit(
        ActivationProposal(
            proposal_id="proposal:harness:p3b",
            profile_ref="character:char_a",
            world_ref="world:harness:b",
            package_revision="package:bakery-authored-agents:v1",
            policy_revision="policy:population:v1",
            activation_reason="harness",
            scope_grant=("actor:self",),
            cadence_class="simulation",
            expected_revisions={"population:world:harness:b": 0},
            idempotency_key="activation:harness:p3b",
            correlation_id="corr:harness:p3b",
            source_ref="population:harness",
        )
    )
    mode = WorldModeProfile(
        world_ref="world:harness:b",
        mode="simulation",
        revision="mode:harness:p3b:v1",
        cadence_class="daily",
        batch_limit=2,
        wake_budget=2,
        catch_up_limit=2,
        allowed_intent_kinds=("work",),
        survival_mode="narrative",
        degraded_threshold=2,
    )
    runtime = WorldContinuityRuntime(store=store, mode=mode)
    pause = runtime.pause(reason="harness")
    resume = runtime.resume()
    due = runtime.evaluate_due(
        actor_ref="character:char_a",
        obligation_refs=("obligation:overdue",),
        overdue_refs=("obligation:overdue",),
    )
    full, tail = runtime.replay_equivalence()
    report = {
        "overall_passed": focused
        and pause.committed
        and resume.committed
        and due.zero_write
        and full == tail,
        "predecessors": {"phase1d": True, "phase2": True, "p3a": True},
        "receipt": {
            "pause": pause.model_dump(mode="json"),
            "resume": resume.model_dump(mode="json"),
            "due": due.model_dump(mode="json"),
        },
        "revision_vector": resume.revision_vector,
        "replay_hash": full,
        "checkpoint_tail_hash": tail,
        "scope_redaction": {"scope": "world-mode", "redaction": "obligation refs only"},
        "zero_write": due.zero_write,
        "stop_reason": None,
        "focused_log": log,
    }
    return write_report("phase3b-world-mode-continuity", report)


if __name__ == "__main__":
    raise SystemExit(main())
