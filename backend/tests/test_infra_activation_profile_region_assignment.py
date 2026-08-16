from __future__ import annotations

from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.ecology_runtime import (
    CropRecord,
    EcologyHazardAuthority,
    EnvironmentalState,
    EnvironmentRegion,
    HazardRecord,
    ResourceNode,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.models import ActivationProposal


PROFILE_DIR = Path(__file__).resolve().parents[2] / "assets" / "characters" / "profiles"
WORLD_REF = "world:region-assignment"
PROFILE_REF = "character:char_a"
REGION_REF = "region:region-assignment"


def _region_evidence(*, visibility_scope: str = "project") -> tuple[GameplayEventStore, str]:
    store = GameplayEventStore()
    ecology = EcologyHazardAuthority(store=store)
    region = EnvironmentRegion(
        region_ref=REGION_REF,
        climate_profile_ref="climate:temperate",
        biome_tags=("biome:field",),
        jurisdiction_ref="jurisdiction:region-assignment",
        revision=0,
    )
    result = ecology.record_region_bundle(
        envelope=GameplayCommandEnvelope(
            command_id="command:region-assignment:seed",
            command_type="gameplay.ecology.region_bundle.record",
            command_version=1,
            principal_ref="authority:ecology",
            idempotency_key="region-assignment:seed",
            expected_revisions={f"gameplay:ecology:{REGION_REF}": 0},
            causation_id="cause:region-assignment:seed",
            correlation_id="corr:region-assignment:seed",
            source_ref="authority:ecology",
            submitted_at="2026-08-16T00:00:00Z",
            payload={"visibility_scope": visibility_scope},
        ),
        region=region,
        environment=EnvironmentalState(region_ref=REGION_REF, temperature_centi_c=175, moisture_basis_points=4_000, weather_ref="weather:clear", revision=0),
        resource=ResourceNode(node_ref="resource:region-assignment:water", region_ref=REGION_REF, substance_ref="substance:water", quantity=90, regeneration_per_tick=2, revision=0),
        crop=CropRecord(crop_ref="crop:region-assignment:wheat", region_ref=REGION_REF, plot_ref="plot:region-assignment:1", health=100, growth_basis_points=5_000, revision=0, owner_ref="authority:crop"),
        hazard=HazardRecord(hazard_ref="hazard:region-assignment:frost", region_ref=REGION_REF, effect_ref="effect:frost", severity_basis_points=5_000, due_tick=3, duration_ticks=1, semantic_revision="semantic:1", rule_revision="rule:1", policy_revision="policy:1", idempotency_key="region-assignment:seed"),
    )
    assert result.committed
    return store, result.committed_event_ids[0]


def _activation(*, store: GameplayEventStore) -> ProfileActivationAuthority:
    authority = ProfileActivationAuthority(
        registry=CharacterProfileRegistry.from_directory(PROFILE_DIR), store=store
    )
    result = authority.commit(
        ActivationProposal(
            proposal_id="proposal:region-assignment:activate",
            profile_ref=PROFILE_REF,
            world_ref=WORLD_REF,
            package_revision="package:region-assignment:1",
            policy_revision="policy:region-assignment:1",
            activation_reason="fixture",
            scope_grant=("project",),
            cadence_class="daily",
            expected_revisions={f"population:{WORLD_REF}": 0},
            idempotency_key="region-assignment:activate",
            correlation_id="corr:region-assignment:activate",
            source_ref="world_runtime.activation_authority",
        )
    )
    assert result.committed
    return authority


def _command(*, expected_revision: int = 1, ecology_revision: int = 5, key: str = "region-assignment:assign", region_ref: str = REGION_REF) -> GameplayCommandEnvelope:
    return GameplayCommandEnvelope(
        command_id=f"command:{key}",
        command_type="population.activation.assign_region",
        command_version=1,
        principal_ref="world_runtime.activation_authority",
        actor_ref=PROFILE_REF,
        project_ref="project:region-assignment",
        idempotency_key=key,
        expected_revisions={f"population:{WORLD_REF}": expected_revision},
        read_set_revisions={f"gameplay:ecology:{region_ref}": ecology_revision},
        causation_id="cause:region-assignment",
        correlation_id="corr:region-assignment",
        source_ref="world_runtime.activation_authority",
        submitted_at="2026-08-16T00:00:00Z",
        payload={"region_ref": region_ref, "visibility_scope": "project"},
    )


def test_profile_region_assignment_commits_only_activation_fragment_from_project_ecology_evidence() -> None:
    store, evidence_event_id = _region_evidence()
    activation = _activation(store=store)

    result = activation.assign_profile_region(
        command=_command(),
        world_ref=WORLD_REF,
        profile_ref=PROFILE_REF,
        region_ref=REGION_REF,
        region_evidence_event_id=evidence_event_id,
    )

    assert result.committed
    assert result.committed_event_ids
    assert result.revision_vector == {f"population:{WORLD_REF}": 2}
    assert store.read_stream(f"population:{WORLD_REF}")[-1].event_type == "population.activation.region_assigned"
    batch = store.read_transactions()[-1]
    assert batch.read_stream_revisions == {f"gameplay:ecology:{REGION_REF}": 5}
    assert len(store.list_outbox()) == 6
    assert activation.profile_region_view_for(world_ref=WORLD_REF, reader_scope="project") == {
        PROFILE_REF: {"region_ref": REGION_REF, "source_event_id": evidence_event_id}
    }


def test_profile_region_assignment_rejects_forged_ecology_evidence_without_write() -> None:
    store, evidence_event_id = _region_evidence()
    activation = _activation(store=store)
    before = len(store.read_events())

    forged = activation.assign_profile_region(
        command=_command(), world_ref=WORLD_REF, profile_ref=PROFILE_REF,
        region_ref=REGION_REF, region_evidence_event_id="event:missing",
    )

    assert forged.zero_write
    assert len(store.read_events()) == before


def test_profile_region_assignment_rejects_private_ecology_evidence_without_write() -> None:
    private_store, private_evidence_event_id = _region_evidence(visibility_scope="authority_only")
    private_activation = _activation(store=private_store)
    before = len(private_store.read_events())
    private = private_activation.assign_profile_region(
        command=_command(), world_ref=WORLD_REF, profile_ref=PROFILE_REF,
        region_ref=REGION_REF, region_evidence_event_id=private_evidence_event_id,
    )

    assert private.zero_write
    assert len(private_store.read_events()) == before


def test_profile_region_assignment_rejects_inactive_profile_without_write() -> None:
    store, evidence_event_id = _region_evidence()
    activation = _activation(store=store)
    before = len(store.read_events())
    inactive = activation.assign_profile_region(
        command=_command(key="region-assignment:inactive"), world_ref=WORLD_REF,
        profile_ref="character:char_b", region_ref=REGION_REF,
        region_evidence_event_id=evidence_event_id,
    )

    assert inactive.zero_write
    assert len(store.read_events()) == before


def test_profile_region_assignment_exact_duplicate_replays_without_second_write() -> None:
    store, evidence_event_id = _region_evidence()
    activation = _activation(store=store)
    first = activation.assign_profile_region(command=_command(), world_ref=WORLD_REF, profile_ref=PROFILE_REF, region_ref=REGION_REF, region_evidence_event_id=evidence_event_id)
    before = len(store.read_events())
    duplicate = activation.assign_profile_region(command=_command(), world_ref=WORLD_REF, profile_ref=PROFILE_REF, region_ref=REGION_REF, region_evidence_event_id=evidence_event_id)

    assert first.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == before


def test_profile_region_assignment_rejects_stale_activation_revision_without_write() -> None:
    store, evidence_event_id = _region_evidence()
    activation = _activation(store=store)
    assert activation.assign_profile_region(command=_command(), world_ref=WORLD_REF, profile_ref=PROFILE_REF, region_ref=REGION_REF, region_evidence_event_id=evidence_event_id).committed
    before = len(store.read_events())

    result = activation.assign_profile_region(command=_command(key="region-assignment:stale", expected_revision=1), world_ref=WORLD_REF, profile_ref=PROFILE_REF, region_ref=REGION_REF, region_evidence_event_id=evidence_event_id)

    assert result.zero_write
    assert len(store.read_events()) == before


def test_profile_region_assignment_rejects_stale_ecology_source_revision_without_write() -> None:
    store, evidence_event_id = _region_evidence()
    activation = _activation(store=store)
    assert activation.assign_profile_region(command=_command(), world_ref=WORLD_REF, profile_ref=PROFILE_REF, region_ref=REGION_REF, region_evidence_event_id=evidence_event_id).committed
    before = len(store.read_events())

    result = activation.assign_profile_region(command=_command(key="region-assignment:stale-source", expected_revision=2, ecology_revision=4), world_ref=WORLD_REF, profile_ref=PROFILE_REF, region_ref=REGION_REF, region_evidence_event_id=evidence_event_id)

    assert result.zero_write
    assert len(store.read_events()) == before


def test_profile_region_assignment_rejects_changed_idempotency_reuse_without_write() -> None:
    store, evidence_event_id = _region_evidence()
    activation = _activation(store=store)
    assert activation.assign_profile_region(command=_command(), world_ref=WORLD_REF, profile_ref=PROFILE_REF, region_ref=REGION_REF, region_evidence_event_id=evidence_event_id).committed
    before = len(store.read_events())

    result = activation.assign_profile_region(command=_command(region_ref="region:forged"), world_ref=WORLD_REF, profile_ref=PROFILE_REF, region_ref="region:forged", region_evidence_event_id=evidence_event_id)

    assert result.zero_write
    assert len(store.read_events()) == before


def test_profile_region_assignment_rejects_nonproject_reader() -> None:
    store, evidence_event_id = _region_evidence()
    activation = _activation(store=store)
    assert activation.assign_profile_region(command=_command(), world_ref=WORLD_REF, profile_ref=PROFILE_REF, region_ref=REGION_REF, region_evidence_event_id=evidence_event_id).committed

    assert activation.profile_region_view_for(world_ref=WORLD_REF, reader_scope="actor:character:char_a") == {}


def test_profile_region_assignment_checkpoint_tail_replay_matches_full() -> None:
    store, evidence_event_id = _region_evidence()
    activation = _activation(store=store)
    assert activation.assign_profile_region(command=_command(), world_ref=WORLD_REF, profile_ref=PROFILE_REF, region_ref=REGION_REF, region_evidence_event_id=evidence_event_id).committed
    events = store.read_stream(f"population:{WORLD_REF}")
    checkpoint = activation.profile_region_projection_from_events(events[:-1])
    full = activation.profile_region_projection_from_events(events)
    tail = activation.profile_region_projection_from_events(
        events[-1:], checkpoint_state=checkpoint
    )

    assert full == tail == activation.profile_region_projection(WORLD_REF)
