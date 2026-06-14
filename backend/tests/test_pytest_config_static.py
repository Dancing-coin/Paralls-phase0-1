from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_pytest_asyncio_loop_scope_is_explicit() -> None:
    pyproject_source = (ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")

    assert 'asyncio_default_fixture_loop_scope = "function"' in pyproject_source
