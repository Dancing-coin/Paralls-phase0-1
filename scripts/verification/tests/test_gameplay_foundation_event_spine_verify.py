from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verify_gameplay_foundation_event_spine import _gameplay_bus_publish_is_dispatcher_scoped


def _write_gameplay_module(project_root: Path, name: str, source: str) -> None:
    gameplay_dir = project_root / "backend" / "app" / "gameplay"
    gameplay_dir.mkdir(parents=True, exist_ok=True)
    (gameplay_dir / name).write_text(source, encoding="utf-8")


def test_dispatcher_scope_allows_non_authority_repository_publish(tmp_path: Path) -> None:
    _write_gameplay_module(tmp_path, "dispatcher.py", "self._bus.publish(event)\n")
    _write_gameplay_module(tmp_path, "godot_mirror_delivery.py", "self._repository.publish(view)\n")

    assert _gameplay_bus_publish_is_dispatcher_scoped(tmp_path) is True


def test_dispatcher_scope_rejects_authority_bus_publish_outside_dispatcher(tmp_path: Path) -> None:
    _write_gameplay_module(tmp_path, "dispatcher.py", "self._bus.publish(event)\n")
    _write_gameplay_module(tmp_path, "unauthorized.py", "self._bus.publish(event)\n")

    assert _gameplay_bus_publish_is_dispatcher_scoped(tmp_path) is False
