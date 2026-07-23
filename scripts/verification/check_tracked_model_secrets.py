from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


SECRET_ENV_NAMES = ("CHARACTER_MODEL_API_KEY", "SIMING_LLM_API_KEY")


def _configured_secret_values(env: dict[str, str]) -> list[bytes]:
    values: list[str] = []
    for name in SECRET_ENV_NAMES:
        value = str(env.get(name, "") or "").strip()
        if value:
            values.append(value)
    raw_routes = str(env.get("SIMING_LLM_ROUTES_JSON", "") or "").strip()
    if raw_routes:
        try:
            parsed = json.loads(raw_routes)
        except json.JSONDecodeError:
            parsed = []
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    value = str(item.get("api_key", "") or "").strip()
                    if value:
                        values.append(value)
    return [value.encode("utf-8") for value in dict.fromkeys(values)]


def _tracked_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git ls-files failed")
    return [root / line for line in result.stdout.splitlines() if line.strip()]


def scan(root: Path, env: dict[str, str] | None = None) -> list[str]:
    secret_values = _configured_secret_values(env or os.environ)
    if not secret_values:
        return []
    offenders: list[str] = []
    for path in _tracked_files(root):
        try:
            content = path.read_bytes()
        except (OSError, UnicodeDecodeError):
            continue
        if any(secret in content for secret in secret_values):
            offenders.append(str(path.relative_to(root)).replace("\\", "/"))
    return offenders


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    offenders = scan(root)
    for path in offenders:
        print(f"tracked_model_secret_path={path}")
    print(f"tracked_model_secret_offender_count={len(offenders)}")
    return 1 if offenders else 0


if __name__ == "__main__":
    raise SystemExit(main())
