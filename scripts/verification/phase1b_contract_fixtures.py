"""Pure, deterministic P1B fixture builders using the shared Gameplay contracts."""

from __future__ import annotations

from dataclasses import dataclass

from app.gameplay.shared_contracts import GameplayCommandEnvelope, SemanticSnapshot


@dataclass(frozen=True)
class ContractFixture:
    fixture_id: str
    command: GameplayCommandEnvelope
    semantic_snapshot: SemanticSnapshot
    evidence_refs: tuple[str, ...]
    owner_map: dict[str, str]
    expected_projection: dict[str, object]


def _fixture(fixture_id: str, *, stream_ref: str, event_type: str, owner: str, payload: dict[str, object]) -> ContractFixture:
    command = GameplayCommandEnvelope(
        command_id=f"command:p1b:{fixture_id}",
        command_type=f"p1b.{fixture_id}.apply",
        command_version=1,
        principal_ref="principal:p1b",
        actor_ref="actor:p1b",
        project_ref="project:p1b",
        transaction_id=f"transaction:p1b:{fixture_id}",
        idempotency_key=f"idempotency:p1b:{fixture_id}",
        expected_revisions={stream_ref: 0},
        causation_id=f"cause:p1b:{fixture_id}",
        correlation_id=f"correlation:p1b:{fixture_id}",
        source_ref="source:p1b:fixture",
        submitted_at="2026-08-07T00:00:00Z",
        pinned_revisions={"policy": 1, "world": 1},
        payload={"stream_ref": stream_ref, "event_type": event_type, **payload},
    )
    snapshot = SemanticSnapshot(
        entity_ref=f"entity:p1b:{fixture_id}",
        component_refs=(f"component:{fixture_id}",),
        resolved_tags=(f"tag:{fixture_id}",),
        policy_context_ref="policy:p1b:v1",
        source_revision_vector={"semantic:p1b": 1},
        digest=f"sha256:p1b:{fixture_id}",
    )
    return ContractFixture(
        fixture_id=fixture_id,
        command=command,
        semantic_snapshot=snapshot,
        evidence_refs=(f"evidence:p1b:{fixture_id}",),
        owner_map={stream_ref: owner},
        expected_projection={"fixture_id": fixture_id, "scope": "public"},
    )


def build_effect_resistance_fixture() -> ContractFixture:
    return _fixture(
        "effect-resistance",
        stream_ref="stream:p1b:crop",
        event_type="p1b.effect_resistance_evaluated",
        owner="effect_owner",
        payload={"effect_ref": "effect:frost", "resistance": 0.5},
    )


def build_object_ownership_fixture() -> ContractFixture:
    return _fixture(
        "object-ownership",
        stream_ref="stream:p1b:object",
        event_type="p1b.object_ownership_settled",
        owner="ownership_owner",
        payload={"object_ref": "object:shared:1", "ownership_ref": "owner:p1b"},
    )


__all__ = ["ContractFixture", "build_effect_resistance_fixture", "build_object_ownership_fixture"]
