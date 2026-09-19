"""混合基准的合法领域输入；只能在既有 RuntimeExecution owner 中调用。"""
from pathlib import Path

from app.gameplay.econ1_economy_runtime import OperatingWindow
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.gameplay.patch_runtime import GameplayPatchManifest


RECIPE = "mixed-owner-fixture:v1:regular28:peak100:b1limit32"


def install_conflict_fixture_package(registry):
    """仅在基准启动、world/continuation pins 建立前装配，不改生产默认包集。"""
    path = Path(__file__).resolve().parents[2] / "backend/assets/verification/population-social-conflict.manifest.json"
    manifest = GameplayPatchManifest.model_validate_json(path.read_text(encoding="utf-8"))
    existing = registry.active_patch_set.patch_revision_ids if registry.active_patch_set else ()
    registry.install(manifest)
    registry.activate(tuple(dict.fromkeys((*existing, manifest.patch_revision_id))))
    return manifest.patch_revision_id


def prepare_conflict_fixture(*, store, packages, policy_registry, profiles, actors, key):
    from app.gameplay.organization_government_social_platform_runtime import OGS_SOCIAL_PRINCIPAL_REF, SocialNormConflictIntent
    from app.gameplay.p5.social_knowledge import SocialFactAuthority
    from app.population_continuity.activation_policy import ActivationPolicy
    from app.population_continuity.conflict_activation import prepare_conflict_activation

    authored = tuple(actor for actor in actors if profiles.contains(actor))
    if not authored or len(authored) > 4 or len(set(authored)) != len(authored):
        raise ValueError("mixed_fixture_authored_cohort_invalid")
    intent = SocialNormConflictIntent(case_ref="case:" + key + "@1",
        subject_refs=tuple("character:" + actor for actor in authored), conflict_state="opened",
        provenance_ref="provenance:" + key + "@1", source_revision_pin=0)
    command = "conflict:" + key
    prior = store.get_by_idempotency(OGS_SOCIAL_PRINCIPAL_REF, command)
    if prior is None:
        result = SocialFactAuthority(registry=policy_registry, store=store, package_registry=packages).record_admitted_platform_social_conflict(
            intent=intent, binding_ref="binding:social-conflict@1", command_id=command,
            idempotency_key=command, causation_id=key, correlation_id=key, expected_revision=0)
        if result.receipt is None or not result.receipt.committed_event_ids:
            raise ValueError("mixed_fixture_conflict_commit_failed")
        event_id = result.receipt.committed_event_ids[0]
    else:
        if not prior.committed or len(prior.committed_event_ids) != 1:
            raise ValueError("mixed_fixture_conflict_source_changed")
        event_id = prior.committed_event_ids[0]
    event = store.get_event(event_id)
    expected = intent.model_dump(mode="json", exclude_none=True)
    if any(event.payload.get(name) != value for name, value in expected.items()):
        raise ValueError("mixed_fixture_conflict_source_changed")
    return tuple(prepare_conflict_activation(store=store, package_registry=packages, profiles=profiles,
        policy=ActivationPolicy(), source_event_id=event_id, actor_id=actor, budget=4) for actor in authored)


def prepare_due_fixture(*, store, actors: tuple[str, ...], event) -> list[dict]:
    if event.kind not in {"regular_due", "due_peak"} or type(event.window_index) is not int or event.window_index < 1:
        raise ValueError("mixed_fixture_due_event_invalid")
    indices = event.actor_indices[:28] if event.kind == "regular_due" else event.actor_indices
    if (len(set(indices)) != len(indices) or any(type(i) is not int or not 0 <= i < len(actors) for i in indices)
            or not indices or len(indices) > 100):
        raise ValueError("mixed_fixture_actor_selection_invalid")
    owner, rows = OrganizationAuthority(store=store), []
    for index in indices:
        key = f"{event.transaction_id}:actor-slot:{index}"
        window_ref, organization = "window:" + key, f"org:mixed:{index % 2}"
        command = "schedule:" + key
        payload = dict(organization_ref=organization, recipient_ref="character:" + actors[index],
            membership_ref="membership:" + key, assignment_ref="assignment:" + key, role="worker",
            shift_ref="shift:" + key, operating_window_ref=window_ref, work_order_ref="work:" + key,
            effective_from="1970-01-01T00:00:00Z", effective_to=None, visibility_scope="organization:summary")
        prior = store.get_by_idempotency(owner._PRINCIPAL, "idempotency:" + command)
        if prior is None:
            prior = owner.record_schedule(command_id=command, **payload)
        if not prior.committed or len(prior.committed_event_ids) != 4:
            raise ValueError("mixed_fixture_schedule_failed")
        # record_schedule 使用当前 stream head；恢复时必须核对原已提交输入，不能重签同 key。
        scheduled = [store.get_event(event_id) for event_id in prior.committed_event_ids]
        if (any(row.payload != payload or row.visibility_policy != "organization:summary"
                or row.stream_id != "gameplay:organization:" + organization for row in scheduled)
                or scheduled[-1].event_type != "gameplay.organization.work_order_recorded"):
            raise ValueError("mixed_fixture_schedule_conflict")
        common = dict(causation_id=key, correlation_id=key, visibility_scope="project")
        opened = owner.open_operating_window(command_id="open:" + key, idempotency_key="open:" + key,
            window=OperatingWindow(window_ref=window_ref, organization_ref=organization,
                opens_at_tick=0, closes_at_tick=event.window_index,
                policy_revision=RECIPE, source_revision=scheduled[-1].event_id), **common)
        if not opened.committed:
            raise ValueError("mixed_fixture_open_failed")
        closed = owner.close_operating_window(command_id="close:" + key, idempotency_key="close:" + key,
            organization_ref=organization, window_ref=window_ref, expected_stream_revision=1, **common)
        if not closed.committed:
            raise ValueError("mixed_fixture_close_failed")
        rows.append(dict(key=key, actor_id=actors[index], window_ref=window_ref,
            due_tick=event.window_index, schedule_event_id=scheduled[-1].event_id,
            closed_event_id=closed.committed_event_ids[0]))
    return rows
