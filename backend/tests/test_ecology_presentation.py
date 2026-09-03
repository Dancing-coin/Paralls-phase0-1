import pytest

from app.gameplay.ecology_platform_runtime import EcologyPlatformProjection
from app.gameplay.ecology_presentation import EcologyPresentationError, project_ecology_for_godot


def test_ecology_projection_is_read_only_godot_safe():
    projection = EcologyPlatformProjection(
        regions={}, cells={}, environments={}, resources={}, crops={}, species={}, closes={}, source_revision_vector={}
    )
    view = project_ecology_for_godot(projection)
    assert view["projection_kind"] == "ecology.generic.godot.v1"
    assert view["state"]["regions"] == {}


def test_ecology_projection_rejects_non_godot_consumer():
    projection = EcologyPlatformProjection(
        regions={}, cells={}, environments={}, resources={}, crops={}, species={}, closes={}, source_revision_vector={}
    )
    with pytest.raises(EcologyPresentationError, match="ecology_presentation_consumer_invalid"):
        project_ecology_for_godot(projection, consumer="backend-writer")
