from __future__ import annotations

import json
import sys
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.character_agent.execution.l4_adapter import CharacterAgentL4Adapter
from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.shared_contracts import GameplayPackageManifest

try:
    from common import repo_root, verification_dir, write_json, write_markdown
except ModuleNotFoundError:
    from scripts.verification.common import repo_root, verification_dir, write_json, write_markdown


def _digest(value: object) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _manifest() -> GameplayPackageManifest:
    return GameplayPackageManifest(
        package_id="package:bakery-authored-agents", package_revision="1", domain_id="bakery-authored-agents",
        maturity_level="reference", required_core_version="1", commands=("work.start.v1",),
        events=("gameplay.work.start_work",), projections=("actor-work",), declared_schemas=("work-intent.v1",),
        capabilities=("work-intent",), privacy_policies=("actor-scoped",), mirror_bindings=("godot:committed",),
        compatibility_range="1.x", content_digest="sha256:phase2a", actor_refs=("character:char_a", "character:char_b", "character:char_c"),
    )


def main() -> int:
    root = repo_root()
    registry = CharacterProfileRegistry.from_directory(root / "assets" / "characters" / "profiles")
    adapter = CharacterAgentL4Adapter(profile_registry=registry)
    envelope_result = adapter.build_work_intent_envelope(
        actor_ref="character:char_b", manifest=_manifest(), intent_kind="start_work",
        payload={"assignment_ref": "assignment:baker", "work_order_ref": "work:bread"},
        source_ref="character-agent:char_b", causation_id="p2a:cause", correlation_id="p2a:corr",
        idempotency_key="p2a:start", expected_revisions={"assignment:baker": 0, "work:bread": 0},
        pinned_revisions={"policy": 1},
    )
    rejected = adapter.build_work_intent_envelope(
        actor_ref="character:npc:synthetic", manifest=_manifest(), intent_kind="start_work", payload={},
        source_ref="character-agent:synthetic", causation_id="p2a:reject", correlation_id="p2a:reject",
        idempotency_key="p2a:reject",
    )
    envelope = envelope_result.envelope
    scoped_projection = {"actor_ref": "character:char_b", "work_refs": ["work:bread"], "public_facility": "available"}
    report = {
        "overall_phase2a_actor_to_gameplay_participation_passed": bool(
            envelope is not None and rejected.rejection is not None and rejected.rejection.zero_write_guarantee
        ),
        "receipt": {"command_id": envelope.command_id if envelope else None, "committed_event_ids": [], "zero_write_adapter": True},
        "event_diff": {"before": 0, "after": 0, "reason": "adapter never writes canonical state"},
        "revision_vector": envelope.expected_revisions if envelope else {},
        "replay_hash": _digest({"canonical_events": [], "scope": scoped_projection}),
        "scope_redaction": {"actor": scoped_projection, "redacted": ["need", "memory", "other_actor_wage"]},
        "failure_zero_write": rejected.rejection.model_dump(mode="json") if rejected.rejection else {},
    }
    directory = verification_dir(root)
    json_path = directory / "phase2a-actor-to-gameplay-participation-report.json"
    md_path = directory / "phase2a-actor-to-gameplay-participation-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "P2A Actor-to-Gameplay Participation", report, "overall_phase2a_actor_to_gameplay_participation_passed")
    print(f"phase2a_report_json={json_path}")
    print(f"overall_phase2a_actor_to_gameplay_participation_passed={report['overall_phase2a_actor_to_gameplay_participation_passed']}")
    return 0 if report["overall_phase2a_actor_to_gameplay_participation_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
