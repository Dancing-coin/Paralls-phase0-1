from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

from test_infra_ecology_weather_front_wave_fanout import WAVES, _authority, _propagate

from app.gameplay.ecology_runtime import (
    EcologyWeatherFrontEventPlannerPolicy,
    EcologyWeatherFrontWaveFanoutPolicy,
)
from app.gameplay.models import OwnerAuthorizedFragment
from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch_from_fragments
from app.gameplay.shared_contracts import GameplayCommandEnvelope

_VERIFICATION_DIR = Path(__file__).resolve().parents[2] / "scripts" / "verification"
if str(_VERIFICATION_DIR) not in sys.path:
    sys.path.insert(0, str(_VERIFICATION_DIR))
_VERIFICATION_SPEC = importlib.util.spec_from_file_location(
    "verify_infra_ecology_weather_front_event_derived_planner",
    _VERIFICATION_DIR / "verify_infra_ecology_weather_front_event_derived_planner.py",
)
assert _VERIFICATION_SPEC is not None and _VERIFICATION_SPEC.loader is not None
verification_script = importlib.util.module_from_spec(_VERIFICATION_SPEC)
_VERIFICATION_SPEC.loader.exec_module(verification_script)

PARTIAL_WAVES = (WAVES[0], WAVES[1][:1])

def _source_event(store):
    return next(
        event
        for event in store.read_events()
        if event.event_type == "gameplay.ecology.weather_front.propagated"
        and event.payload.get("target_region_ref") == "region:wave:a"
    )


def _seed_weather_source(store, authority, *, stream_id, visibility_policy, key, chain_depth=0):
    fragment = OwnerAuthorizedFragment(
        fragment_id=f"fragment:{key}",
        owner_principal_ref="authority:ecology",
        source_rule_ref="test:seed-weather-source",
        expected_revisions={stream_id: store.get_stream_head(stream_id)},
        pinned_revisions={stream_id: 1},
        event_specs={
            stream_id: (
                (
                    "gameplay.ecology.weather_front.propagated",
                    {
                        "source_region_ref": "region:wave:root",
                        "target_region_ref": "region:wave:a",
                        "weather_ref": "weather:rain",
                        "tick": 7,
                        "chain_depth": chain_depth,
                    },
                ),
            )
        },
        event_visibility_policies={stream_id: (visibility_policy,)},
    )
    batch = build_multi_stream_atomic_event_batch_from_fragments(
        command_id=f"command:{key}",
        idempotency_principal_ref="authority:ecology",
        idempotency_key=key,
        causation_id=f"cause:{key}",
        correlation_id=f"corr:{key}",
        fragments=(fragment,),
    )
    result = store.append_batch(batch)
    assert result.committed
    return next(event for event in store.read_events() if event.event_id in result.committed_event_ids)


def _plan_command(authority, store, plan, *, key="ecology:derived:commit", scope="project", revisions=None):
    refs = {plan.root_region_ref, plan.prior_source_region_ref}
    refs.update(region for wave in plan.waves for edge in wave for region in edge)
    expected = {
        authority.ecology_stream_id(region_ref=region): store.get_stream_head(
            authority.ecology_stream_id(region_ref=region)
        )
        for region in sorted(refs)
    }
    return GameplayCommandEnvelope(
        command_id=f"command:{key}",
        command_type="gameplay.ecology.weather_front.event_derived_plan",
        command_version=1,
        principal_ref="authority:ecology",
        idempotency_key=key,
        expected_revisions=expected if revisions is None else revisions,
        causation_id=f"cause:{key}",
        correlation_id=f"corr:{key}",
        source_ref="authority:ecology",
        submitted_at="2026-08-16T00:00:00Z",
        payload={
            "visibility_scope": scope,
            "source_weather_event_id": plan.source_weather_event_id,
            "planner_digest": plan.planner_digest,
        },
    )


def _plan_bound_to_source(authority, store, source, template_plan):
    policy = EcologyWeatherFrontEventPlannerPolicy()
    source_stream_revision = store.get_stream_head(source.stream_id)
    return template_plan.model_copy(
        update={
            "source_weather_event_id": source.event_id,
            "source_weather_event_revision": source.stream_revision,
            "source_ecology_stream_id": source.stream_id,
            "source_ecology_stream_revision": source_stream_revision,
            "prior_source_region_ref": source.payload["source_region_ref"],
            "root_region_ref": source.payload["target_region_ref"],
            "weather_ref": source.payload["weather_ref"],
            "tick": source.payload["tick"],
            "planner_digest": authority._weather_front_event_planner_digest(
                source_weather_event_id=source.event_id,
                source_weather_event_revision=source.stream_revision,
                source_ecology_stream_id=source.stream_id,
                source_ecology_stream_revision=source_stream_revision,
                root_region_ref=source.payload["target_region_ref"],
                prior_source_region_ref=source.payload["source_region_ref"],
                weather_ref=source.payload["weather_ref"],
                tick=source.payload["tick"],
                policy=policy,
                waves=template_plan.waves,
            ),
        },
        deep=True,
    )


def test_event_derived_planner_is_deterministic_and_does_not_accept_edges():
    store, authority = _authority()
    assert _propagate(authority, store, waves=PARTIAL_WAVES).committed
    source = _source_event(store)

    plan, error = authority.propose_weather_front_wave_plan_from_event(
        source_weather_event_id=source.event_id,
        policy=EcologyWeatherFrontEventPlannerPolicy(),
    )
    repeat, repeat_error = authority.propose_weather_front_wave_plan_from_event(
        source_weather_event_id=source.event_id,
        policy=EcologyWeatherFrontEventPlannerPolicy(),
    )

    assert error is None and repeat_error is None and plan == repeat
    assert plan is not None
    assert plan.waves == ((("region:wave:a", "region:wave:d"),),)
    assert all(source.event_id == plan.source_weather_event_id for _ in [0])


def test_event_derived_planner_rejects_missing_source_without_write():
    store, authority = _authority()
    before = store.read_events()

    missing, missing_error = authority.propose_weather_front_wave_plan_from_event(
        source_weather_event_id="event:missing",
        policy=EcologyWeatherFrontEventPlannerPolicy(),
    )

    assert missing is None and missing_error == "weather_front_source_missing"
    assert store.read_events() == before


def test_event_derived_planner_rejects_private_source_without_write():
    store, authority = _authority()
    source = _seed_weather_source(
        store,
        authority,
        stream_id=authority.ecology_stream_id(region_ref="region:wave:root"),
        visibility_policy="authority_only",
        key="ecology:derived:private-source",
    )
    before = store.read_events()

    plan, error = authority.propose_weather_front_wave_plan_from_event(
        source_weather_event_id=source.event_id,
        policy=EcologyWeatherFrontEventPlannerPolicy(),
    )

    assert plan is None and error == "weather_front_source_privacy_denied"
    assert store.read_events() == before


def test_event_derived_planner_rejects_foreign_stream_source_without_write():
    store, authority = _authority()
    source = _seed_weather_source(
        store,
        authority,
        stream_id="gameplay:foreign:region:wave:root",
        visibility_policy="project",
        key="ecology:derived:foreign-source",
    )
    before = store.read_events()

    plan, error = authority.propose_weather_front_wave_plan_from_event(
        source_weather_event_id=source.event_id,
        policy=EcologyWeatherFrontEventPlannerPolicy(),
    )

    assert plan is None and error == "weather_front_source_invalid"
    assert store.read_events() == before


def test_event_derived_planner_rejects_malformed_negative_depth_source_without_write():
    store, authority = _authority()
    source = _seed_weather_source(
        store,
        authority,
        stream_id=authority.ecology_stream_id(region_ref="region:wave:root"),
        visibility_policy="project",
        key="ecology:derived:negative-depth-source",
        chain_depth=-1,
    )
    before = store.read_events()

    plan, error = authority.propose_weather_front_wave_plan_from_event(
        source_weather_event_id=source.event_id,
        policy=EcologyWeatherFrontEventPlannerPolicy(),
    )

    assert plan is None and error == "weather_front_source_invalid"
    assert store.read_events() == before


def test_event_derived_planner_rejects_exhausted_frontier_without_write():
    store, authority = _authority()
    assert _propagate(authority, store).committed
    exhausted_source = next(
        event
        for event in store.read_events()
        if event.event_type == "gameplay.ecology.weather_front.propagated"
        and event.payload.get("target_region_ref") == "region:wave:e"
    )
    before = store.read_events()

    plan, error = authority.propose_weather_front_wave_plan_from_event(
        source_weather_event_id=exhausted_source.event_id,
        policy=EcologyWeatherFrontEventPlannerPolicy(),
    )

    assert plan is None and error == "weather_front_no_eligible_targets"
    assert store.read_events() == before


def test_event_derived_planner_commits_via_existing_ecology_batch():
    store, authority = _authority()
    assert _propagate(authority, store, waves=PARTIAL_WAVES).committed
    source = _source_event(store)
    plan, error = authority.propose_weather_front_wave_plan_from_event(
        source_weather_event_id=source.event_id,
        policy=EcologyWeatherFrontEventPlannerPolicy(),
    )
    assert error is None and plan is not None
    before = len(store.read_events())

    result = authority.propagate_weather_front_wave_plan(
        envelope=_plan_command(authority, store, plan),
        policy=EcologyWeatherFrontWaveFanoutPolicy(),
        plan=plan,
    )

    assert result.committed
    assert len(store.read_events()) == before + 2
    assert all(event.stream_id.startswith("gameplay:ecology:") for event in store.read_events()[before:])


def test_event_derived_planner_commit_rejects_negative_depth_source_without_write():
    store, authority = _authority()
    assert _propagate(authority, store, waves=PARTIAL_WAVES).committed
    source = _source_event(store)
    template_plan, error = authority.propose_weather_front_wave_plan_from_event(
        source_weather_event_id=source.event_id,
        policy=EcologyWeatherFrontEventPlannerPolicy(),
    )
    assert error is None and template_plan is not None
    negative_source = _seed_weather_source(
        store,
        authority,
        stream_id=authority.ecology_stream_id(region_ref="region:wave:root"),
        visibility_policy="project",
        key="ecology:derived:negative-depth-source",
        chain_depth=-1,
    )
    negative_plan = _plan_bound_to_source(authority, store, negative_source, template_plan)
    before = store.read_events()

    result = authority.propagate_weather_front_wave_plan(
        envelope=_plan_command(authority, store, negative_plan, key="ecology:derived:negative-depth-commit"),
        policy=EcologyWeatherFrontWaveFanoutPolicy(),
        plan=negative_plan,
    )

    assert result.failure is not None and result.failure.error_code == "weather_front_source_invalid"
    assert store.read_events() == before


def test_event_derived_planner_commit_rejects_exhausted_depth_source_without_write():
    store, authority = _authority()
    assert _propagate(authority, store, waves=PARTIAL_WAVES).committed
    source = _source_event(store)
    template_plan, error = authority.propose_weather_front_wave_plan_from_event(
        source_weather_event_id=source.event_id,
        policy=EcologyWeatherFrontEventPlannerPolicy(),
    )
    assert error is None and template_plan is not None
    exhausted_source = _seed_weather_source(
        store,
        authority,
        stream_id=authority.ecology_stream_id(region_ref="region:wave:root"),
        visibility_policy="project",
        key="ecology:derived:exhausted-depth-source",
        chain_depth=EcologyWeatherFrontEventPlannerPolicy().max_chain_depth,
    )
    exhausted_plan = _plan_bound_to_source(authority, store, exhausted_source, template_plan)
    before = store.read_events()

    result = authority.propagate_weather_front_wave_plan(
        envelope=_plan_command(authority, store, exhausted_plan, key="ecology:derived:exhausted-depth-commit"),
        policy=EcologyWeatherFrontWaveFanoutPolicy(),
        plan=exhausted_plan,
    )

    assert result.failure is not None and result.failure.error_code == "weather_front_no_eligible_targets"
    assert store.read_events() == before


def test_event_derived_planner_exact_duplicate_and_changed_duplicate_are_zero_write():
    store, authority = _authority()
    assert _propagate(authority, store, waves=PARTIAL_WAVES).committed
    source = _source_event(store)
    plan, error = authority.propose_weather_front_wave_plan_from_event(
        source_weather_event_id=source.event_id,
        policy=EcologyWeatherFrontEventPlannerPolicy(),
    )
    assert error is None and plan is not None
    command = _plan_command(authority, store, plan)
    first = authority.propagate_weather_front_wave_plan(
        envelope=command, policy=EcologyWeatherFrontWaveFanoutPolicy(), plan=plan
    )
    duplicate = authority.propagate_weather_front_wave_plan(
        envelope=command, policy=EcologyWeatherFrontWaveFanoutPolicy(), plan=plan
    )
    tampered = authority.propagate_weather_front_wave_plan(
        envelope=command,
        policy=EcologyWeatherFrontWaveFanoutPolicy(),
        plan=plan.model_copy(update={"planner_digest": "sha256:tampered"}),
    )

    assert first.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert tampered.failure is not None and tampered.failure.error_code == "weather_front_planner_digest_invalid"
    assert len(store.read_events()) == 38


def test_event_derived_planner_rejects_revision_conflict_without_write():
    store, authority = _authority()
    assert _propagate(authority, store, waves=PARTIAL_WAVES).committed
    source = _source_event(store)
    plan, error = authority.propose_weather_front_wave_plan_from_event(
        source_weather_event_id=source.event_id,
        policy=EcologyWeatherFrontEventPlannerPolicy(),
    )
    assert error is None and plan is not None
    command = _plan_command(authority, store, plan)
    stale = {**command.expected_revisions, next(iter(command.expected_revisions)): 0}
    before = store.read_events()

    result = authority.propagate_weather_front_wave_plan(
        envelope=command.model_copy(update={"expected_revisions": stale}),
        policy=EcologyWeatherFrontWaveFanoutPolicy(),
        plan=plan,
    )

    assert result.failure is not None and result.failure.error_code == "revision_conflict"
    assert store.read_events() == before


def test_event_derived_planner_rejects_nonproject_scope_without_write():
    store, authority = _authority()
    assert _propagate(authority, store, waves=PARTIAL_WAVES).committed
    source = _source_event(store)
    plan, error = authority.propose_weather_front_wave_plan_from_event(
        source_weather_event_id=source.event_id,
        policy=EcologyWeatherFrontEventPlannerPolicy(),
    )
    assert error is None and plan is not None
    before = store.read_events()

    result = authority.propagate_weather_front_wave_plan(
        envelope=_plan_command(authority, store, plan, scope="authority_only"),
        policy=EcologyWeatherFrontWaveFanoutPolicy(),
        plan=plan,
    )

    assert result.failure is not None and result.failure.error_code == "ecology_front_privacy_scope_denied"
    assert store.read_events() == before


def test_event_derived_planner_outbox_and_checkpoint_tail_replay_are_scoped():
    store, authority = _authority()
    assert _propagate(authority, store, waves=PARTIAL_WAVES).committed
    source = _source_event(store)
    plan, error = authority.propose_weather_front_wave_plan_from_event(
        source_weather_event_id=source.event_id,
        policy=EcologyWeatherFrontEventPlannerPolicy(),
    )
    assert error is None and plan is not None
    assert authority.propagate_weather_front_wave_plan(
        envelope=_plan_command(authority, store, plan, key="ecology:derived:scope"),
        policy=EcologyWeatherFrontWaveFanoutPolicy(),
        plan=plan,
    ).committed

    outbox = store.list_outbox()[-2:]
    assert {entry.audience for entry in outbox} == {"project"}
    assert all(set(entry.payload_projection) == {"region_ref", "event_type"} for entry in outbox)
    assert authority.regional_replay().projection_hash == authority.regional_replay(checkpoint_at=30).projection_hash


def test_event_derived_planner_predecessor_gate_requires_fresh_harness_identity(tmp_path, monkeypatch):
    verification_root = tmp_path / ".harness" / "verification"
    verification_root.mkdir(parents=True)
    predecessor_payload = {
        "profile": "infra-regional-ecology-truth",
        "overall_passed": True,
        "commit": "rev-current",
    }
    (verification_root / "infra-regional-ecology-truth-report.json").write_text(
        json.dumps(predecessor_payload),
        encoding="utf-8",
    )
    (verification_root / "infra-ecology-weather-front-wave-fanout-report.json").write_text(
        json.dumps(
            {
                **predecessor_payload,
                "profile": "infra-ecology-weather-front-wave-fanout",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(verification_script, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(verification_script, "evidence_revision", lambda _root: "rev-current")
    monkeypatch.setattr(
        verification_script,
        "run_command",
        lambda *args, **kwargs: SimpleNamespace(returncode=0),
    )

    assert verification_script.main() == 1
    report = json.loads(
        (verification_root / "infra-ecology-weather-front-event-derived-planner-report.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["checks"]["predecessor_regional_truth_report"] is False
