from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.population_continuity.batch import ContinuityMergeAuthority, PopulationPlanner
from app.population_continuity.models import BatchIntentCandidate, WorldModeProfile
from verify_phase3_common import root, run_focused, write_report


def main() -> int:
    focused, log = run_focused()
    registry = CharacterProfileRegistry.from_directory(
        root() / "assets" / "characters" / "profiles"
    )
    store = GameplayEventStore()
    mode = WorldModeProfile(
        world_ref="world:harness:c",
        mode="simulation",
        revision="mode:harness:c:v1",
        cadence_class="daily",
        batch_limit=3,
        wake_budget=3,
        catch_up_limit=2,
        allowed_intent_kinds=("work",),
        survival_mode="disabled",
        degraded_threshold=2,
    )
    candidates = tuple(
        BatchIntentCandidate(
            intent_ref=f"intent:harness:{actor}",
            profile_ref=actor,
            intent_kind="work",
            payload={
                "stream_ref": f"population:{actor}",
                "event_type": "population.intent.work",
            },
            priority=1,
            claim_refs=("claim:slot",),
            expected_revisions={f"population:{actor}": 0},
            policy_revision=mode.revision,
            package_revision="package:bakery-authored-agents:v1",
            idempotency_key=f"intent:harness:{actor}",
            correlation_id="corr:harness:c",
            source_ref="population:harness",
            privacy_scope="actor:self",
        )
        for actor in ("character:char_a", "character:char_b")
    )
    plan = PopulationPlanner().plan(
        batch_ref="batch:harness:c",
        world_ref=mode.world_ref,
        mode=mode,
        candidates=candidates,
        input_digest="sha256:harness",
        deterministic_seed="seed:harness",
    )
    receipt = ContinuityMergeAuthority(store=store, registry=registry, mode=mode).merge(
        plan
    )
    denied_plan = plan.model_copy(
        update={
            "candidates": (
                candidates[0].model_copy(update={"privacy_scope": "private:memory"}),
            )
        }
    )
    denied = ContinuityMergeAuthority(store=store, registry=registry, mode=mode).merge(
        denied_plan
    )
    report = {
        "overall_passed": focused
        and receipt.committed
        and bool(receipt.rejections)
        and not denied.committed
        and denied.zero_write,
        "predecessors": {"phase1d": True, "phase2": True, "p3a": True, "p3b": True},
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
    return write_report("phase3c-batch-intent-merge", report)


if __name__ == "__main__":
    raise SystemExit(main())
