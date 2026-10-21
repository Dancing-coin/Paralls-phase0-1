from dataclasses import replace

from app.world_runtime.adapter_admission import AdapterDescriptor, AdapterRequirement, admit_adapters


def _descriptor():
    return AdapterDescriptor(
        adapter_ref="backend:event_projection", revision="1", clock_mapping_refs=("legacy-map@1",),
        evidence_types=("owner_event",), snapshot_scope=("event_projection",),
        determinism="replay_deterministic", max_lateness=0, replay_supported=True,
        entity_binding_ref="existing:event-stream", rollback_horizon=0,
        invalidation_policy_ref="stop_confirmation")


def _requirement():
    return AdapterRequirement(clock_mapping_refs=("legacy-map@1",), evidence_types=("owner_event",),
                              snapshot_scope=("event_projection",), determinism="replay_deterministic",
                              max_lateness=0, replay_required=True, rollback_horizon=0)


def test_admission_computes_intersection_without_inventing_snapshot_support():
    descriptor = _descriptor()
    result = admit_adapters((descriptor,), requirement=_requirement())
    assert result.can_confirm((descriptor,))
    missing = admit_adapters((descriptor,), requirement=replace(_requirement(), snapshot_scope=("physics",)))
    assert not missing.admitted
    assert "adapter_snapshot_scope_missing" in missing.diagnostics


def test_missing_mapping_or_late_horizon_is_not_silently_downgraded():
    result = admit_adapters((_descriptor(),), requirement=replace(
        _requirement(), clock_mapping_refs=("new-map@1",), max_lateness=1))
    assert not result.admitted
    assert "adapter_clock_mapping_missing" in result.diagnostics
    assert "adapter_lateness_unsupported" in result.diagnostics


def test_runtime_loss_blocks_confirmation_and_recovery_requires_new_revision_and_mapping():
    descriptor = _descriptor()
    admitted = admit_adapters((descriptor,), requirement=_requirement())
    fault = admitted.invalidate(adapter_ref=descriptor.adapter_ref, reason="capability_lost")
    assert not fault.can_confirm((descriptor,))
    assert "capability_lost" in fault.diagnostics
    assert not fault.recover((descriptor,), requirement=_requirement()).admitted
    revision_only = replace(descriptor, revision="2")
    assert not fault.recover((revision_only,), requirement=_requirement()).admitted
    restored = replace(revision_only, clock_mapping_refs=("legacy-map@2",))
    requirement = replace(_requirement(), clock_mapping_refs=("legacy-map@2",))
    assert fault.recover((restored,), requirement=requirement).can_confirm((restored,))


def test_stale_or_empty_adapter_set_cannot_confirm():
    descriptor = _descriptor()
    admitted = admit_adapters((descriptor,), requirement=_requirement())
    assert not admitted.can_confirm(())
    assert not admitted.can_confirm((replace(descriptor, revision="2"),))
    assert not admit_adapters((), requirement=_requirement()).admitted
