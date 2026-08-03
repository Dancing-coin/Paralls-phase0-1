from __future__ import annotations

import pytest

from app.gameplay.patch_runtime import (
    CapabilityRegistry,
    CapabilityResult,
    EffectProposal,
    GameplayPatchManifest,
    GameplayPatchRegistry,
    GameplayPatchRegistrySnapshotError,
    GameplayPatchRuntimeError,
    GameplayRuleEvaluator,
    PatchDependency,
    PatchEventSchema,
    RegisteredCapability,
    RequestedCapability,
    RuleCapabilityCall,
    RuleCondition,
    RuleDefinition,
    RuleEffectTemplate,
    RuleEvaluationRequest,
)


def _manifest(
    *,
    patch_id: str = "patch:combat",
    version: str = "0.1.0",
    revision: str = "patch:combat@0.1.0",
    dependencies: tuple[PatchDependency, ...] = (),
    schemas: tuple[PatchEventSchema, ...] = (),
    rules: tuple[RuleDefinition, ...] = (),
    capabilities: tuple[RequestedCapability, ...] = (),
    effects: tuple[str, ...] = ("resource.consume",),
    author: str = "author:repo",
) -> GameplayPatchManifest:
    manifest = GameplayPatchManifest(
        manifest_schema_version=1,
        patch_id=patch_id,
        patch_version=version,
        patch_revision_id=revision,
        content_digest="pending",
        author_id=author,
        trust_policy_ref="trust:repo",
        dependencies=dependencies,
        event_schemas=schemas,
        rules=rules,
        requested_capabilities=capabilities,
        granted_effect_types=effects,
        verification_profiles=("gameplay-patch-runtime",),
    )
    return manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})


def _activate(registry: GameplayPatchRegistry, manifest: GameplayPatchManifest) -> None:
    registry.install(manifest)
    registry.activate((manifest.patch_revision_id,))


def _request(registry: GameplayPatchRegistry, *, trigger: str = "action.attempt", inputs: dict[str, object] | None = None) -> RuleEvaluationRequest:
    active = registry.active_patch_set
    assert active is not None
    return RuleEvaluationRequest(
        evaluation_id="eval:1",
        trigger=trigger,
        authority_tick=10,
        pinned_registry_revision=active.registry_revision,
        pinned_active_patch_set_revision=active.active_patch_set_revision,
        projection_inputs=inputs or {"actor": {"stamina": 20}},
    )


def test_trusted_manifest_is_immutable_candidate_until_explicit_activation() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    manifest = _manifest()

    installed = registry.install(manifest)

    assert installed.patch_revision_id == manifest.patch_revision_id
    assert registry.active_patch_set is None
    active = registry.activate((manifest.patch_revision_id,))
    assert active.patch_revision_ids == (manifest.patch_revision_id,)
    with pytest.raises(GameplayPatchRuntimeError, match="patch_candidate_duplicate"):
        registry.install(manifest)


def test_untrusted_or_digest_tampered_manifest_cannot_install() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    with pytest.raises(GameplayPatchRuntimeError, match="patch_author_untrusted"):
        registry.install(_manifest(author="author:unknown"))
    tampered = _manifest().model_copy(update={"content_digest": "sha256:wrong"})
    with pytest.raises(GameplayPatchRuntimeError, match="patch_digest_mismatch"):
        registry.install(tampered)


def test_missing_dependency_and_schema_collision_reject_without_partial_install() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    missing = _manifest(dependencies=(PatchDependency(dependency_kind="patch", target_ref="patch:missing", reason="required"),))
    with pytest.raises(GameplayPatchRuntimeError, match="patch_dependency_missing"):
        registry.install(missing)

    first = _manifest(schemas=(PatchEventSchema(event_type="patch.event", schema_version=1, schema_digest="sha256:one"),))
    conflict = _manifest(patch_id="patch:other", revision="patch:other@0.1.0", schemas=(PatchEventSchema(event_type="patch.event", schema_version=1, schema_digest="sha256:two"),))
    registry.install(first)
    with pytest.raises(GameplayPatchRuntimeError, match="patch_schema_collision"):
        registry.install(conflict)
    assert registry.active_patch_set is None


def test_batch_install_rejects_dependency_cycle_atomically() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    a = _manifest(
        patch_id="patch:a",
        revision="patch:a@0.1.0",
        dependencies=(PatchDependency(dependency_kind="patch", target_ref="patch:b", reason="b"),),
    )
    b = _manifest(
        patch_id="patch:b",
        revision="patch:b@0.1.0",
        dependencies=(PatchDependency(dependency_kind="patch", target_ref="patch:a", reason="a"),),
    )

    with pytest.raises(GameplayPatchRuntimeError, match="patch_dependency_cycle"):
        registry.install_many((a, b))
    with pytest.raises(GameplayPatchRuntimeError, match="patch_candidate_not_installed"):
        registry.activate((a.patch_revision_id,))


def test_dependency_version_ranges_require_one_compatible_candidate() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    base = _manifest(patch_id="patch:base", version="1.2.0", revision="patch:base@1.2.0")
    dependent = _manifest(
        patch_id="patch:dependent",
        revision="patch:dependent@0.1.0",
        dependencies=(PatchDependency(dependency_kind="patch", target_ref="patch:base", version_range=">=1.0,<2.0", reason="base"),),
    )
    registry.install_many((base, dependent))
    active = registry.activate((base.patch_revision_id, dependent.patch_revision_id))

    assert active.patch_revision_ids == (base.patch_revision_id, dependent.patch_revision_id)


def test_data_only_rule_evaluation_returns_deterministic_proposals() -> None:
    rule = RuleDefinition(
        rule_id="rule:swing-cost",
        rule_version="1",
        trigger="action.attempt",
        conditions=(RuleCondition(path=("actor", "stamina"), operator="equals", expected_value=20),),
        effect_templates=(RuleEffectTemplate(effect_type="resource.consume", payload={"amount": 15}),),
    )
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    _activate(registry, _manifest(rules=(rule,)))
    evaluator = GameplayRuleEvaluator(patch_registry=registry, capability_registry=CapabilityRegistry())

    first = evaluator.evaluate(_request(registry))
    second = evaluator.evaluate(_request(registry))

    assert first.status == "proposed"
    assert first.effect_proposals[0].effect_type == "resource.consume"
    assert first.output_digest == second.output_digest


def test_rule_budget_and_unauthorized_effect_fail_before_any_settlement() -> None:
    budget_rule = RuleDefinition(
        rule_id="rule:too-many-effects",
        rule_version="1",
        trigger="action.attempt",
        effect_templates=(
            RuleEffectTemplate(effect_type="resource.consume", payload={"amount": 1}),
            RuleEffectTemplate(effect_type="resource.consume", payload={"amount": 2}),
        ),
    )
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    _activate(registry, _manifest(rules=(budget_rule,)))
    with pytest.raises(GameplayPatchRuntimeError, match="rule_budget_exceeded"):
        GameplayRuleEvaluator(patch_registry=registry, capability_registry=CapabilityRegistry(), max_effect_proposals=1).evaluate(_request(registry))

    unauthorized_rule = RuleDefinition(
        rule_id="rule:unauthorized",
        rule_version="1",
        trigger="action.attempt",
        effect_templates=(RuleEffectTemplate(effect_type="ownership.transfer", payload={}),),
    )
    other_registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    _activate(other_registry, _manifest(revision="patch:other@0.1.0", rules=(unauthorized_rule,)))
    with pytest.raises(GameplayPatchRuntimeError, match="effect_type_unauthorized"):
        GameplayRuleEvaluator(patch_registry=other_registry, capability_registry=CapabilityRegistry()).evaluate(_request(other_registry))


def test_capability_must_be_manifest_authorized_and_only_returns_allowed_proposals() -> None:
    requested = RequestedCapability(
        capability_id="capability:combat",
        capability_version="1",
        call_sites=("rule:capability",),
        requested_effect_types=("resource.consume",),
        reason="cost calculation",
    )
    rule = RuleDefinition(
        rule_id="rule:capability",
        rule_version="1",
        trigger="action.attempt",
        capability_calls=(RuleCapabilityCall(capability_id="capability:combat", capability_version="1", input_paths={"stamina": ("actor", "stamina")}),),
    )
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    _activate(registry, _manifest(rules=(rule,), capabilities=(requested,)))
    capabilities = CapabilityRegistry()
    capabilities.register(
        RegisteredCapability(
            capability_id="capability:combat",
            capability_version="1",
            handler_code_digest="sha256:handler",
            owner="owner:combat",
            allowed_callers=frozenset({"author:repo"}),
            allowed_effect_types=frozenset({"resource.consume"}),
            deterministic=True,
            side_effect_free=True,
            network_access=False,
            filesystem_access=False,
            handler=lambda values, _context: CapabilityResult(
                "proposed",
                (EffectProposal("resource.consume", {"amount": values["stamina"]}, "capability:combat"),),
            ),
        )
    )

    result = GameplayRuleEvaluator(patch_registry=registry, capability_registry=capabilities).evaluate(_request(registry))

    assert result.effect_proposals == (EffectProposal("resource.consume", {"amount": 20}, "capability:combat"),)


def test_unsafe_or_failing_capability_cannot_reach_authority_settlement() -> None:
    capabilities = CapabilityRegistry()
    with pytest.raises(GameplayPatchRuntimeError, match="capability_authority_unsafe"):
        capabilities.register(
            RegisteredCapability(
                capability_id="capability:unsafe",
                capability_version="1",
                handler_code_digest="sha256:unsafe",
                owner="owner:unsafe",
                allowed_callers=frozenset({"author:repo"}),
                allowed_effect_types=frozenset(),
                deterministic=True,
                side_effect_free=True,
                network_access=True,
                filesystem_access=False,
                handler=lambda _values, _context: CapabilityResult("no_op"),
            )
        )

    requested = RequestedCapability(
        capability_id="capability:failing",
        capability_version="1",
        call_sites=("rule:failing",),
        requested_effect_types=("resource.consume",),
        reason="failure fixture",
    )
    rule = RuleDefinition(
        rule_id="rule:failing",
        rule_version="1",
        trigger="action.attempt",
        capability_calls=(RuleCapabilityCall(capability_id="capability:failing", capability_version="1"),),
    )
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    _activate(registry, _manifest(revision="patch:failing@0.1.0", rules=(rule,), capabilities=(requested,)))

    def fail_handler(_values, _context):
        raise RuntimeError("handler failure")

    capabilities.register(
        RegisteredCapability(
            capability_id="capability:failing",
            capability_version="1",
            handler_code_digest="sha256:failing",
            owner="owner:failing",
            allowed_callers=frozenset({"author:repo"}),
            allowed_effect_types=frozenset({"resource.consume"}),
            deterministic=True,
            side_effect_free=True,
            network_access=False,
            filesystem_access=False,
            handler=fail_handler,
        )
    )
    with pytest.raises(GameplayPatchRuntimeError, match="capability_handler_failed"):
        GameplayRuleEvaluator(patch_registry=registry, capability_registry=capabilities).evaluate(_request(registry))


def test_registry_snapshot_round_trip_recovers_immutable_candidates_and_active_set(tmp_path) -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    base = _manifest(patch_id="patch:base", revision="patch:base@1.0.0", version="1.0.0")
    extension = _manifest(
        patch_id="patch:extension",
        revision="patch:extension@0.1.0",
        dependencies=(PatchDependency(dependency_kind="patch", target_ref="patch:base", version_range="==1.0.0", reason="base"),),
    )
    registry.install_many((base, extension))
    active = registry.activate((base.patch_revision_id, extension.patch_revision_id))
    path = tmp_path / "patch-registry.json"
    registry.save_snapshot(path)

    restored = GameplayPatchRegistry.load_snapshot(path, trusted_authors=frozenset({"author:repo"}))

    assert restored.active_patch_set == active
    assert [manifest.patch_revision_id for manifest in restored.active_manifests(active.active_patch_set_revision)] == list(active.patch_revision_ids)


def test_tampered_candidate_or_active_set_snapshot_fails_closed() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    manifest = _manifest()
    _activate(registry, manifest)
    snapshot = registry.export_snapshot()
    candidates = snapshot["candidates"]
    assert isinstance(candidates, list)
    candidates[0]["content_digest"] = "sha256:tampered"
    with pytest.raises(GameplayPatchRegistrySnapshotError, match="patch_registry_snapshot_invalid"):
        GameplayPatchRegistry.from_snapshot(snapshot, trusted_authors=frozenset({"author:repo"}))

    pristine = registry.export_snapshot()
    active = pristine["active_patch_set"]
    assert isinstance(active, dict)
    active["active_patch_set_revision"] = "sha256:tampered"
    with pytest.raises(GameplayPatchRegistrySnapshotError, match="patch_registry_snapshot_active_set_mismatch"):
        GameplayPatchRegistry.from_snapshot(pristine, trusted_authors=frozenset({"author:repo"}))
