from __future__ import annotations

import pytest
from pydantic import ValidationError


def _load_p5_symbols() -> dict[str, object]:
    try:
        from app.gameplay.p5.contracts import (
            P5ProposedEvent,
            P5ResolutionRequest,
            P5ResolutionResult,
            P5SchemaPin,
            QuestObjectiveDefinition,
            QuestPackageDefinition,
            build_directed_relationship_ref,
        )
        from app.gameplay.p5.registry import (
            OwnerAdapterAllowance,
            P5EventCatalogEntry,
            P5EventNamespace,
            P5PolicyRegistry,
            P5StreamGrammar,
            TrustedEvidenceProvider,
        )
    except Exception as exc:  # pragma: no cover - explicit RED guard
        pytest.fail(f"production break: p5 typed contracts or registry module missing: {exc}")

    return {
        "OwnerAdapterAllowance": OwnerAdapterAllowance,
        "P5EventCatalogEntry": P5EventCatalogEntry,
        "P5EventNamespace": P5EventNamespace,
        "P5PolicyRegistry": P5PolicyRegistry,
        "P5ProposedEvent": P5ProposedEvent,
        "P5ResolutionRequest": P5ResolutionRequest,
        "P5ResolutionResult": P5ResolutionResult,
        "P5SchemaPin": P5SchemaPin,
        "P5StreamGrammar": P5StreamGrammar,
        "QuestObjectiveDefinition": QuestObjectiveDefinition,
        "QuestPackageDefinition": QuestPackageDefinition,
        "TrustedEvidenceProvider": TrustedEvidenceProvider,
        "build_directed_relationship_ref": build_directed_relationship_ref,
    }


def _digest(hex_digit: str) -> str:
    return f"sha256:{hex_digit * 64}"


def _sample_registry(symbols: dict[str, object], *, reverse_order: bool = False) -> object:
    TrustedEvidenceProvider = symbols["TrustedEvidenceProvider"]
    OwnerAdapterAllowance = symbols["OwnerAdapterAllowance"]
    QuestObjectiveDefinition = symbols["QuestObjectiveDefinition"]
    QuestPackageDefinition = symbols["QuestPackageDefinition"]
    P5SchemaPin = symbols["P5SchemaPin"]
    P5EventCatalogEntry = symbols["P5EventCatalogEntry"]
    P5EventNamespace = symbols["P5EventNamespace"]
    P5StreamGrammar = symbols["P5StreamGrammar"]
    P5PolicyRegistry = symbols["P5PolicyRegistry"]

    providers = [
        TrustedEvidenceProvider(
            provider_ref="provider:evidence:clerk-ledger",
            provider_revision="provider-rev:clerk-ledger:v1",
            provider_digest=_digest("1"),
            allowed_evidence_kinds=("evidence:receipt",),
        ),
        TrustedEvidenceProvider(
            provider_ref="provider:evidence:guard-report",
            provider_revision="provider-rev:guard-report:v1",
            provider_digest=_digest("2"),
            allowed_evidence_kinds=("evidence:observation",),
        ),
    ]
    owners = [
        OwnerAdapterAllowance(
            owner_ref="owner:status-authority",
            allowed_event_names=("gameplay.status_tag.applied",),
            allowed_stream_grammar_refs=("grammar:p5:relationship",),
        ),
        OwnerAdapterAllowance(
            owner_ref="owner:quest-authority",
            allowed_event_names=("gameplay.quest.evidence_registered",),
            allowed_stream_grammar_refs=("grammar:p5:quest",),
        ),
    ]
    objectives = [
        QuestObjectiveDefinition(
            objective_ref="objective:bakery-theft:collect-ledger",
            prerequisite_fact_refs=("fact:case:opened",),
            accepted_evidence_kind_refs=("evidence:receipt",),
            visibility="authority_only",
            expiry_policy_ref="expiry:never",
        ),
        QuestObjectiveDefinition(
            objective_ref="objective:bakery-theft:report-suspect",
            prerequisite_fact_refs=("fact:ledger:validated",),
            accepted_evidence_kind_refs=("evidence:observation",),
            visibility="public",
            expiry_policy_ref="expiry:never",
        ),
    ]
    package = QuestPackageDefinition(
        package_ref="package:p5:bakery-theft",
        package_revision="package-rev:p5:bakery-theft:v1",
        package_digest=_digest("3"),
        ruleset_revision="ruleset:p5d:v1",
        objectives=tuple(reversed(objectives) if reverse_order else objectives),
    )
    schema_pins = [
        P5SchemaPin(
            schema_ref="schema:p5:quest:evidence-registered",
            schema_version=1,
            schema_digest=_digest("4"),
        ),
        P5SchemaPin(
            schema_ref="schema:p5:social:relationship-recorded",
            schema_version=1,
            schema_digest=_digest("5"),
        ),
    ]
    grammars = [
        P5StreamGrammar(grammar_ref="grammar:p5:quest", pattern=r"^gameplay:quest:[^:]+$"),
        P5StreamGrammar(grammar_ref="grammar:p5:relationship", pattern=r"^gameplay:relationship:[^:]+$"),
        P5StreamGrammar(grammar_ref="grammar:p5:evidence", pattern=r"^gameplay:evidence:[^:]+$"),
    ]
    namespaces = [
        P5EventNamespace(
            namespace_ref="namespace:p5:quest",
            event_name_prefix="gameplay.quest.",
            allowed_event_names=("gameplay.quest.evidence_registered",),
        ),
        P5EventNamespace(
            namespace_ref="namespace:p5:social",
            event_name_prefix="gameplay.social.",
            allowed_event_names=("gameplay.social.relationship_fact_recorded",),
        ),
    ]
    events = [
        P5EventCatalogEntry(
            event_name="gameplay.quest.evidence_registered",
            namespace_ref="namespace:p5:quest",
            schema_ref="schema:p5:quest:evidence-registered",
            schema_version=1,
            stream_grammar_ref="grammar:p5:quest",
        ),
        P5EventCatalogEntry(
            event_name="gameplay.social.relationship_fact_recorded",
            namespace_ref="namespace:p5:social",
            schema_ref="schema:p5:social:relationship-recorded",
            schema_version=1,
            stream_grammar_ref="grammar:p5:relationship",
        ),
    ]

    if reverse_order:
        providers.reverse()
        owners.reverse()
        schema_pins.reverse()
        grammars.reverse()
        namespaces.reverse()
        events.reverse()

    return P5PolicyRegistry.build(
        registry_ref="policy-registry:p5",
        registry_revision="policy-registry:p5:v1",
        trusted_evidence_providers=tuple(providers),
        owner_adapter_allowlist=tuple(owners),
        quest_packages=(package,),
        ruleset_revisions=("ruleset:p5d:v1",),
        schema_pins=tuple(schema_pins),
        event_namespaces=tuple(namespaces),
        event_catalog=tuple(events),
        stream_grammars=tuple(grammars),
    )


def test_registry_break_requires_pinned_digest_and_stable_digest_inputs() -> None:
    symbols = _load_p5_symbols()
    registry_a = _sample_registry(symbols)
    registry_b = _sample_registry(symbols, reverse_order=True)

    assert registry_a.registry_digest == registry_b.registry_digest

    P5PolicyRegistry = symbols["P5PolicyRegistry"]
    with pytest.raises(ValidationError, match="p5_policy_registry_digest_mismatch"):
        P5PolicyRegistry(
            registry_ref=registry_a.registry_ref,
            registry_revision=registry_a.registry_revision,
            registry_digest=_digest("f"),
            trusted_evidence_providers=registry_a.trusted_evidence_providers,
            owner_adapter_allowlist=registry_a.owner_adapter_allowlist,
            quest_packages=registry_a.quest_packages,
            ruleset_revisions=registry_a.ruleset_revisions,
            schema_pins=registry_a.schema_pins,
            event_namespaces=registry_a.event_namespaces,
            event_catalog=registry_a.event_catalog,
            stream_grammars=registry_a.stream_grammars,
        )


def test_registry_break_fails_closed_for_unknown_provider_owner_package_ruleset_schema_event_and_stream_grammar() -> None:
    symbols = _load_p5_symbols()
    registry = _sample_registry(symbols)
    P5ProposedEvent = symbols["P5ProposedEvent"]
    P5ResolutionRequest = symbols["P5ResolutionRequest"]

    relationship_ref = symbols["build_directed_relationship_ref"](
        source_ref="character:guard:alpha",
        relation_kind="suspects",
        target_ref="character:baker:beta",
    )
    request = P5ResolutionRequest(
        request_ref="request:p5:bakery-theft",
        registry_ref=registry.registry_ref,
        registry_revision=registry.registry_revision,
        registry_digest=registry.registry_digest,
        package_ref="package:p5:bakery-theft",
        package_revision="package-rev:p5:bakery-theft:v1",
        ruleset_revision="ruleset:p5d:v1",
        evidence_provider_ref="provider:evidence:clerk-ledger",
        owner_adapter_ref="owner:quest-authority",
        provenance_source_ref="source:evidence:ledger",
        subject_scope_ref="actor:investigator",
        expected_revisions={"gameplay:quest:quest-instance-1": 0},
        read_set_revisions={"gameplay:evidence:evidence-1": 4},
        required_schema_pins=(
            symbols["P5SchemaPin"](
                schema_ref="schema:p5:quest:evidence-registered",
                schema_version=1,
                schema_digest=_digest("4"),
            ),
        ),
        relationship_ref=relationship_ref,
        proposed_events=(
            P5ProposedEvent(
                event_name="gameplay.quest.evidence_registered",
                schema_version=1,
                stream_ref="gameplay:quest:quest-instance-1",
                visibility="authority_only",
            ),
        ),
    )

    validated = registry.validate_request(request)
    assert validated.registry_digest == registry.registry_digest

    with pytest.raises(ValueError, match="p5_provider_untrusted"):
        registry.validate_request(request.model_copy(update={"evidence_provider_ref": "provider:evidence:unknown"}))
    with pytest.raises(ValueError, match="p5_owner_adapter_unregistered"):
        registry.validate_request(request.model_copy(update={"owner_adapter_ref": "owner:unknown"}))
    with pytest.raises(ValueError, match="p5_package_revision_unregistered"):
        registry.validate_request(request.model_copy(update={"package_revision": "package-rev:p5:bakery-theft:v999"}))
    with pytest.raises(ValueError, match="p5_ruleset_revision_unregistered"):
        registry.validate_request(request.model_copy(update={"ruleset_revision": "ruleset:p5d:v999"}))
    with pytest.raises(ValueError, match="p5_event_schema_unregistered"):
        registry.validate_request(
            request.model_copy(
                update={
                    "proposed_events": (
                        P5ProposedEvent(
                            event_name="gameplay.quest.evidence_registered",
                            schema_version=2,
                            stream_ref="gameplay:quest:quest-instance-1",
                            visibility="authority_only",
                        ),
                    )
                }
            )
        )
    with pytest.raises(ValueError, match="p5_event_unregistered"):
        registry.validate_request(
            request.model_copy(
                update={
                    "proposed_events": (
                        P5ProposedEvent(
                            event_name="gameplay.quest.unknown_event",
                            schema_version=1,
                            stream_ref="gameplay:quest:quest-instance-1",
                            visibility="authority_only",
                        ),
                    )
                }
            )
        )
    with pytest.raises(ValueError, match="p5_stream_grammar_mismatch"):
        registry.validate_request(
            request.model_copy(
                update={
                    "proposed_events": (
                        P5ProposedEvent(
                            event_name="gameplay.quest.evidence_registered",
                            schema_version=1,
                            stream_ref="gameplay:relationship:not-a-quest-stream",
                            visibility="authority_only",
                        ),
                    )
                }
            )
        )
    with pytest.raises(ValueError, match="p5_schema_unregistered"):
        registry.validate_request(
            request.model_copy(
                update={
                    "required_schema_pins": (
                        symbols["P5SchemaPin"](
                            schema_ref="schema:p5:quest:evidence-registered",
                            schema_version=1,
                            schema_digest=_digest("4"),
                        ),
                        symbols["P5SchemaPin"](
                            schema_ref="schema:p5:quest:missing",
                            schema_version=1,
                            schema_digest=_digest("6"),
                        ),
                    )
                }
            )
        )
    with pytest.raises(ValueError, match="p5_stream_grammar_unregistered"):
        registry.validate_request(
            request.model_copy(
                update={
                    "read_set_revisions": {"stream:foreign:unsupported": 7},
                }
            )
        )


def test_request_break_requires_explicit_visibility_and_registered_namespace_allowlist() -> None:
    symbols = _load_p5_symbols()
    P5EventCatalogEntry = symbols["P5EventCatalogEntry"]
    P5EventNamespace = symbols["P5EventNamespace"]
    P5PolicyRegistry = symbols["P5PolicyRegistry"]
    P5ProposedEvent = symbols["P5ProposedEvent"]

    registry = _sample_registry(symbols)

    valid_event = P5ProposedEvent(
        event_name="gameplay.quest.evidence_registered",
        schema_version=1,
        stream_ref="gameplay:quest:quest-instance-1",
        visibility="actor:investigator",
    )
    assert valid_event.visibility == "actor:investigator"

    with pytest.raises(ValidationError, match="visibility"):
        P5ProposedEvent(
            event_name="gameplay.quest.evidence_registered",
            schema_version=1,
            stream_ref="gameplay:quest:quest-instance-1",
            visibility="project",
        )

    with pytest.raises(ValidationError, match="p5_event_namespace_event_mismatch"):
        P5PolicyRegistry(
            registry_ref=registry.registry_ref,
            registry_revision=registry.registry_revision,
            registry_digest=registry.registry_digest,
            trusted_evidence_providers=registry.trusted_evidence_providers,
            owner_adapter_allowlist=registry.owner_adapter_allowlist,
            quest_packages=registry.quest_packages,
            ruleset_revisions=registry.ruleset_revisions,
            schema_pins=registry.schema_pins,
            event_namespaces=(
                P5EventNamespace(
                    namespace_ref="namespace:p5:quest",
                    event_name_prefix="gameplay.quest.",
                    allowed_event_names=("gameplay.quest.evidence_registered",),
                ),
            ),
            event_catalog=(
                P5EventCatalogEntry(
                    event_name="gameplay.social.relationship_fact_recorded",
                    namespace_ref="namespace:p5:quest",
                    schema_ref="schema:p5:social:relationship-recorded",
                    schema_version=1,
                    stream_grammar_ref="grammar:p5:relationship",
                ),
            ),
            stream_grammars=registry.stream_grammars,
        )


def test_relationship_ref_break_uses_opaque_canonical_identity_without_colon_join_ambiguity() -> None:
    symbols = _load_p5_symbols()
    build_directed_relationship_ref = symbols["build_directed_relationship_ref"]

    first = build_directed_relationship_ref(
        source_ref="character:guard:alpha",
        relation_kind="suspects",
        target_ref="character:baker:beta",
    )
    second = build_directed_relationship_ref(
        source_ref="character:guard:alpha",
        relation_kind="suspects",
        target_ref="character:baker:beta",
    )
    reversed_direction = build_directed_relationship_ref(
        source_ref="character:baker:beta",
        relation_kind="suspects",
        target_ref="character:guard:alpha",
    )

    assert first == second
    assert first != reversed_direction
    assert first.startswith("gameplay:relationship:")
    assert "character:guard:alpha" not in first
    assert "character:baker:beta" not in first


def test_resolution_result_break_allows_only_zero_write_success_and_adverse_outcome_kinds() -> None:
    symbols = _load_p5_symbols()
    P5ResolutionResult = symbols["P5ResolutionResult"]

    rejected = P5ResolutionResult(
        result_kind="rejected_zero_write",
        registry_ref="policy-registry:p5",
        registry_revision="policy-registry:p5:v1",
        registry_digest=_digest("9"),
        committed_event_refs=(),
        failure_code="p5_provider_untrusted",
    )
    success = P5ResolutionResult(
        result_kind="committed_success",
        registry_ref="policy-registry:p5",
        registry_revision="policy-registry:p5:v1",
        registry_digest=_digest("9"),
        committed_event_refs=("event:p5:quest:1",),
        failure_code=None,
    )
    adverse = P5ResolutionResult(
        result_kind="committed_adverse_outcome",
        registry_ref="policy-registry:p5",
        registry_revision="policy-registry:p5:v1",
        registry_digest=_digest("9"),
        committed_event_refs=("event:p5:alarm:1",),
        failure_code=None,
    )

    assert rejected.result_kind == "rejected_zero_write"
    assert rejected.committed_event_refs == ()
    assert success.result_kind == "committed_success"
    assert adverse.result_kind == "committed_adverse_outcome"

    with pytest.raises(ValidationError):
        P5ResolutionResult(
            result_kind="committed_partial",
            registry_ref="policy-registry:p5",
            registry_revision="policy-registry:p5:v1",
            registry_digest=_digest("9"),
            committed_event_refs=(),
            failure_code=None,
        )
