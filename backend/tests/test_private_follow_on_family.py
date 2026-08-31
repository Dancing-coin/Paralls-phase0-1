from __future__ import annotations

import pytest

from app.gameplay.closed_generic_gameplay_families import CLOSED_GAMEPLAY_FAMILIES, PRIVATE_FOLLOW_ON_BLOCKER, PrivateFollowOnIntent
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry
from app.gameplay.p5.social_knowledge import SocialFactAuthority
from test_inf4ao_public_milling_social_ack import _notice, _social_registry
from test_inf4ah_public_workshop_notice import _activity as workshop_activity, _request as workshop_notice_request
from test_inf2ag_public_workshop_service_exchange import _setup as workshop_setup
from app.gameplay.organization_government_runtime import GovernmentAuthority


FAMILY_MANIFEST_DIR = (
    __import__("pathlib").Path(__file__).resolve().parents[2]
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "closed-generic"
    / "private-follow-on"
)
FAMILY_MANIFEST_PATHS = (
    FAMILY_MANIFEST_DIR / "package-private-follow-on-public-milling-v1.manifest.json",
    FAMILY_MANIFEST_DIR / "package-private-follow-on-public-workshop-v1.manifest.json",
)



def test_private_follow_on_derives_two_actor_private_targets_from_notice() -> None:
    store, notice = _notice()
    authority = SocialFactAuthority(store=store, registry=_social_registry())

    result = authority.settle_private_follow_on(
        intent=PrivateFollowOnIntent(
            notice_event_id=notice.event_id,
            expected_notice_revision=notice.stream_revision,
            command_id="command:private-follow-on",
            correlation_id="corr:private-follow-on",
        )
    )

    assert result.receipt is not None
    events = [event for event in store.read_events() if event.event_id in set(result.receipt.committed_event_ids)]
    assert len(events) == 2
    assert {event.visibility_policy for event in events} == {
        "actor:organization:district-milling-cooperative",
        "actor:org:mill:1",
    }
    assert all(event.payload["family_ref"] == "private_follow_on@1" for event in events)


def test_private_follow_on_rejects_caller_participants_and_privacy() -> None:
    with pytest.raises(Exception):
        PrivateFollowOnIntent.model_validate(
            {
                "notice_event_id": "event:notice",
                "expected_notice_revision": 1,
                "command_id": "command:follow-on",
                "correlation_id": "corr:follow-on",
                "participant_refs": ["caller"],
                "privacy_scope": "project",
            }
        )


def test_private_follow_on_genericity_has_two_admitted_notice_source_manifests() -> None:
    assert [path.name for path in FAMILY_MANIFEST_PATHS] == [
        "package-private-follow-on-public-milling-v1.manifest.json",
        "package-private-follow-on-public-workshop-v1.manifest.json",
    ]
    manifests = [
        GameplayPatchManifest.model_validate_json(path.read_text(encoding="utf-8"))
        for path in FAMILY_MANIFEST_PATHS
    ]
    assert all(manifest.content_digest == manifest.expected_content_digest() for manifest in manifests)
    assert {
        definition.typed_content["source_fact_family_ref"]
        for manifest in manifests
        for definition in manifest.platform_extension.package_definitions
    } == {
        "fact:government-public-milling-notice@1",
        "fact:government-public-workshop-notice@1",
    }


def test_private_follow_on_historical_blocker_is_not_in_active_genericity_matrix() -> None:
    assert PRIVATE_FOLLOW_ON_BLOCKER.family_ref == "private_follow_on@1"
    assert PRIVATE_FOLLOW_ON_BLOCKER.status == "blocked"
    assert all(item.family_ref != "private_follow_on@1" for item in __import__(
        "app.gameplay.closed_generic_gameplay_families",
        fromlist=["CLOSED_FAMILY_GENERICITY_BLOCKERS"],
    ).CLOSED_FAMILY_GENERICITY_BLOCKERS)


def test_private_follow_on_replays_duplicate_and_matches_each_participant_tail() -> None:
    store, notice = _notice()
    authority = SocialFactAuthority(store=store, registry=_social_registry())
    intent = PrivateFollowOnIntent(
        notice_event_id=notice.event_id,
        expected_notice_revision=notice.stream_revision,
        command_id="command:private-follow-on",
        correlation_id="corr:private-follow-on",
    )
    first = authority.settle_private_follow_on(intent=intent)
    before = tuple(store.read_events())
    duplicate = authority.settle_private_follow_on(intent=intent)
    changed = authority.settle_private_follow_on(intent=intent.model_copy(update={"correlation_id": "corr:changed"}))

    assert duplicate.receipt is not None
    assert duplicate.receipt.committed_event_ids == first.receipt.committed_event_ids
    assert not changed.receipt
    assert tuple(store.read_events()) == before
    for participant in ("organization:district-milling-cooperative", "org:mill:1"):
        full = authority.public_milling_notice_social_acknowledgment_view_for(participant_ref=participant)
        tail = authority.public_milling_notice_social_acknowledgment_view_for(participant_ref=participant, checkpoint_at=notice.global_sequence)
        assert full == tail


def test_private_follow_on_stays_bounded_to_the_exact_notice_chain() -> None:
    family = next(item for item in CLOSED_GAMEPLAY_FAMILIES if item.family_ref == "private_follow_on@1")
    assert family.status == "generic_implemented"
    assert family.owner_ref == "authority:p5:social"
    assert family.stream_pattern == "gameplay:social:public-milling-notice-acknowledgment:{participant_ref}"

    store, notice = _notice()
    authority = SocialFactAuthority(registry=_social_registry(), store=store)
    accepted = authority.record_public_milling_notice_social_acknowledgment(
        **{
            "notice_event_id": notice.event_id,
            "expected_notice_revision": notice.stream_revision,
            "expected_target_revisions": (0, 0),
            "command_id": "inf4ao:ack:bounded",
            "idempotency_key": f"social:public-milling-notice-ack:{notice.event_id}:{notice.stream_revision}:0:0:v1",
            "causation_id": notice.event_id,
            "correlation_id": "corr:inf4ao:ack:bounded",
        }
    )
    assert accepted.resolution.result_kind == "committed_success"
    forged = notice.model_copy(
        update={"payload": {**notice.payload, "organization_ref": "organization:forged"}},
        deep=True,
    )
    store._events_by_id[notice.event_id] = forged
    store._events = [forged if item.event_id == notice.event_id else item for item in store._events]
    before = store.export_snapshot()

    result = authority.settle_private_follow_on(
        intent=PrivateFollowOnIntent(
            notice_event_id=notice.event_id,
            expected_notice_revision=notice.stream_revision,
            command_id="command:private-follow-on:bounded",
            correlation_id="corr:private-follow-on:bounded",
        )
    )

    assert not result.receipt
    assert result.resolution.failure_code == "private_follow_on_source_conflict"
    assert store.export_snapshot() == before


def _workshop_notice() -> tuple[object, object]:
    store, _economy = workshop_setup()
    activity = workshop_activity(store)
    result = GovernmentAuthority(store=store).record_public_workshop_notice(
        **workshop_notice_request(store, activity)
    )
    assert result.committed, result.failure
    return store, store.get_event(result.committed_event_ids[0])


def _family_authority(store: object) -> tuple[SocialFactAuthority, GameplayPatchRegistry]:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    manifests = tuple(
        GameplayPatchManifest.model_validate_json(path.read_text(encoding="utf-8"))
        for path in FAMILY_MANIFEST_PATHS
    )
    registry.install_many(manifests)
    active = registry.activate(tuple(manifest.patch_revision_id for manifest in manifests))
    authority = SocialFactAuthority(
        store=store,
        registry=_social_registry(),
        package_registry=registry,
    )
    assert active.capability_bindings
    return authority, registry


def test_private_follow_on_supports_milling_and_workshop_contents_through_one_adapter() -> None:
    milling_store, milling_notice = _notice()
    milling_authority, milling_registry = _family_authority(milling_store)
    milling = milling_authority.settle_private_follow_on(
        intent=PrivateFollowOnIntent(
            notice_event_id=milling_notice.event_id,
            expected_notice_revision=milling_notice.stream_revision,
            command_id="command:private-follow-on:milling",
            correlation_id="corr:private-follow-on:milling",
        )
    )
    assert milling.receipt is not None
    milling_events = [
        milling_store.get_event(event_id) for event_id in milling.receipt.committed_event_ids
    ]
    assert {event.payload["source_fact_family_ref"] for event in milling_events} == {
        "fact:government-public-milling-notice@1"
    }
    assert {
        event.payload["participant_ref"] for event in milling_events
    } == {"organization:district-milling-cooperative", "org:mill:1"}
    assert all(
        event.payload["content_digest"]
        == next(
            manifest.content_digest
            for manifest in milling_registry.active_manifests(
                milling_registry.active_patch_set.active_patch_set_revision
            )
            if manifest.patch_revision_id == "package:private-follow-on:public-milling@1"
        )
        for event in milling_events
    )

    workshop_store, workshop_notice = _workshop_notice()
    workshop_authority, workshop_registry = _family_authority(workshop_store)
    workshop = workshop_authority.settle_private_follow_on(
        intent=PrivateFollowOnIntent(
            notice_event_id=workshop_notice.event_id,
            expected_notice_revision=workshop_notice.stream_revision,
            command_id="command:private-follow-on:workshop",
            correlation_id="corr:private-follow-on:workshop",
        )
    )
    assert workshop.receipt is not None
    workshop_events = [
        workshop_store.get_event(event_id) for event_id in workshop.receipt.committed_event_ids
    ]
    assert {event.payload["source_fact_family_ref"] for event in workshop_events} == {
        "fact:government-public-workshop-notice@1"
    }
    assert {event.payload["participant_ref"] for event in workshop_events} == {
        "organization:municipal-assessment-office",
        "organization:mill",
    }
    assert all(
        event.payload["content_digest"]
        == next(
            manifest.content_digest
            for manifest in workshop_registry.active_manifests(
                workshop_registry.active_patch_set.active_patch_set_revision
            )
            if manifest.patch_revision_id == "package:private-follow-on:public-workshop@1"
        )
        for event in workshop_events
    )


def test_private_follow_on_generic_contents_replay_and_changed_duplicate_are_zero_write() -> None:
    store, notice = _workshop_notice()
    authority, _registry = _family_authority(store)
    intent = PrivateFollowOnIntent(
        notice_event_id=notice.event_id,
        expected_notice_revision=notice.stream_revision,
        command_id="command:private-follow-on:generic-replay",
        correlation_id="corr:private-follow-on:generic-replay",
    )
    first = authority.settle_private_follow_on(intent=intent)
    assert first.receipt is not None
    before = store.export_snapshot()
    duplicate = authority.settle_private_follow_on(intent=intent)
    changed = authority.settle_private_follow_on(
        intent=intent.model_copy(update={"correlation_id": "corr:private-follow-on:changed"})
    )
    assert duplicate.receipt is not None
    assert duplicate.receipt.idempotency_status == "duplicate_replayed"
    assert duplicate.receipt.committed_event_ids == first.receipt.committed_event_ids
    assert changed.resolution.failure_code == "private_follow_on_idempotency_key_reused"
    assert changed.receipt is None
    assert store.export_snapshot() == before
    for participant in ("organization:municipal-assessment-office", "organization:mill"):
        full = authority.public_milling_notice_social_acknowledgment_view_for(
            participant_ref=participant
        )
        tail = authority.public_milling_notice_social_acknowledgment_view_for(
            participant_ref=participant,
            checkpoint_at=notice.global_sequence,
        )
        assert full == tail
        assert len(full.acknowledgments) == 1


def test_private_follow_on_activation_rejects_changed_manifest_digest_before_active_set() -> None:
    manifests = tuple(
        GameplayPatchManifest.model_validate_json(path.read_text(encoding="utf-8"))
        for path in FAMILY_MANIFEST_PATHS
    )
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    tampered = manifests[1].model_copy(
        update={"content_digest": "sha256:" + "f" * 64}
    )
    with pytest.raises(Exception, match="patch_digest_mismatch"):
        registry.install(tampered)
    assert registry.active_patch_set is None
