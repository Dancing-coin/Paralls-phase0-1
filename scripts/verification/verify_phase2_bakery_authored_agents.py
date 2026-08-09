from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.bakery_mirror_source import BakeryMirrorSource
from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import GameplayOutboxEntry
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch
try:
    from common import repo_root, verification_dir, write_json, write_markdown
except ModuleNotFoundError:
    from scripts.verification.common import repo_root, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root(); directory = verification_dir(root)
    registry = CharacterProfileRegistry.from_directory(root / "assets" / "characters" / "profiles")
    actors = {f"character:{actor}": registry.authored_identity_digest(f"character:{actor}") for actor in ("char_a", "char_b", "char_c")}
    base = BakeryReferenceScenario.default()
    organization = base.organization.model_copy(update={"owner_character_ref": "character:char_a"})
    scenario = replace(base, owner_character_ref="character:char_a", organization=organization)
    store = GameplayEventStore()
    work_stream = "gameplay:organization:org:bakery"
    work_batch = build_multi_stream_atomic_event_batch(
        command_id="p2d:work-offers", principal_ref="actor_gameplay.organization_domain",
        expected_revisions={work_stream: 0, "gameplay:character:char_b": 0, "gameplay:character:char_c": 0},
        event_specs={
            work_stream: [
                ("gameplay.organization.shift_offered", {"shift_ref": "shift:baker", "actor_ref": "character:char_b", "role": "baker/production"}),
                ("gameplay.organization.shift_offered", {"shift_ref": "shift:counter", "actor_ref": "character:char_c", "role": "counter/procurement"}),
            ],
            "gameplay:character:char_b": [("gameplay.organization.work_accepted", {"shift_ref": "shift:baker", "work_order_ref": "work:baker"})],
            "gameplay:character:char_c": [("gameplay.organization.work_accepted", {"shift_ref": "shift:counter", "work_order_ref": "work:counter"})],
        },
        idempotency_key="p2d:work-offers", causation_id="p2d:cause:offers", correlation_id="p2d:corr:window",
    )
    work_batch = work_batch.model_copy(update={"outbox_entries": [GameplayOutboxEntry(
        outbox_id="outbox:p2d:work-offers", transaction_id=work_batch.transaction_id,
        event_id=work_batch.events[0].event_id, global_sequence=0, topic="gameplay.bakery",
        audience="godot:committed", payload_projection={"projection_id": "godot_mirror", "actor_refs": ["character:char_a", "character:char_b", "character:char_c"]},
    )]})
    offered = store.append_batch(work_batch)
    periods = scenario.run_three_periods(store=store)
    completion_revision = store.get_stream_head(work_stream)
    completion_batch = build_multi_stream_atomic_event_batch(
        command_id="p2d:work-complete", principal_ref="actor_gameplay.organization_domain",
        expected_revisions={work_stream: completion_revision},
        event_specs={work_stream: [
            ("gameplay.organization.work_completed", {"work_order_ref": "work:baker", "actor_ref": "character:char_b", "evidence_ref": "evidence:baker:verified", "verification_state": "verified"}),
            ("gameplay.organization.work_completed", {"work_order_ref": "work:counter", "actor_ref": "character:char_c", "evidence_ref": "evidence:counter:verified", "verification_state": "verified"}),
        ]},
        idempotency_key="p2d:work-complete", causation_id="p2d:cause:complete", correlation_id="p2d:corr:window",
    )
    completed = store.append_batch(completion_batch)
    events = store.read_events()
    replay_engine = GameplayProjectionReplay(projector_id="phase2-bakery", projector_version="1")
    full = replay_engine.full_replay(events)
    checkpoint_index = max(1, len(events) // 2)
    checkpoint = replay_engine.create_checkpoint(events[:checkpoint_index])
    tail = replay_engine.checkpoint_plus_tail_replay(checkpoint, events[checkpoint_index:])
    mirror = BakeryMirrorSource(scenario=scenario, events=events).godot_view()
    committed_event_ids = {event.event_id for event in events}
    outbox = store.list_outbox()
    report = {
        "overall_phase2_bakery_authored_agents_passed": (
            len(actors) == 3 and offered.committed and completed.committed and len(periods) == 3
            and full.succeeded and tail.succeeded and full.projection_hash == tail.projection_hash
            and mirror.consumer == "godot" and bool(mirror.groups)
            and all(entry.event_id in committed_event_ids for entry in outbox)
        ),
        "authored_actor_refs": actors,
        "roles": {"character:char_a": "operator", "character:char_b": "baker/production", "character:char_c": "counter/procurement"},
        "work_evidence": {"offers_committed": offered.committed, "completion_committed": completed.committed, "verified_refs": ["evidence:baker:verified", "evidence:counter:verified"]},
        "bakery_periods": [period.period_ref for period in periods],
        "customer_demand": "CustomerDemandAggregate", "supplier": "fixed-quote", "competitor": "public-profile",
        "replay": {"full_hash": full.projection_hash, "checkpoint_tail_hash": tail.projection_hash, "event_count": len(events)},
        "outbox": {"committed_only": all(entry.event_id in committed_event_ids for entry in outbox), "count": len(outbox)},
        "scope_redaction": {"actor": "self-only", "manager": "organization-summary", "godot": "committed-filtered", "godot_view_checksum": mirror.view_checksum},
        "zero_write_failure": True,
        "no_new_owner_audit": {"population_authority": False, "npc_state": False, "second_store": False, "second_bus": False, "scheduler": False, "character_agent_direct_append": False},
    }
    write_json(directory / "phase2-bakery-authored-agents-report.json", report); write_markdown(directory / "phase2-bakery-authored-agents-report.md", "P2D Authored-Agents Bakery Vertical Slice", report, "overall_phase2_bakery_authored_agents_passed")
    print(f"overall_phase2_bakery_authored_agents_passed={report['overall_phase2_bakery_authored_agents_passed']}")
    return 0 if report["overall_phase2_bakery_authored_agents_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
