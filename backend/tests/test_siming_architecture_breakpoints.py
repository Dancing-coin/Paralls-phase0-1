import pytest

from app.gameplay import event_schema_registry
from app.models.fact_type import FACT_TYPE_REGISTRY
from app.services.authority_graph_projector import HeavenlyAuthorityEventProjector
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter


def test_s3_projector_startup_rejects_unmapped_gameplay_schema(monkeypatch):
    existing = event_schema_registry.gameplay_schema_event_types()
    monkeypatch.setattr(event_schema_registry, "gameplay_schema_event_types",
                        lambda: (*existing, "gameplay.new_owner.unmapped@1"))
    with pytest.raises(RuntimeError, match="gameplay.new_owner.unmapped@1"):
        HeavenlyAuthorityEventProjector(InMemoryHeavenlyGraphAdapter(), scope_resolver=lambda _: None)


def test_s3_registry_covers_current_schemas_and_preserves_declared_domain():
    FACT_TYPE_REGISTRY.validate_event_type_coverage()
    assert HeavenlyAuthorityEventProjector._domain_for("gameplay.survival.body_changed") == "survival_body"
    assert HeavenlyAuthorityEventProjector._domain_for("gameplay.survival.undeclared") is None
