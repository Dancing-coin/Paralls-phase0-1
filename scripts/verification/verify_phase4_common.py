from __future__ import annotations

import subprocess
import sys

from common import repo_root, verification_dir


def run_focused(*tests: str) -> tuple[bool, str]:
    root = repo_root()
    result = subprocess.run([sys.executable, "-m", "pytest", *tests, "-q"], cwd=root, capture_output=True, text=True, check=False)
    return result.returncode == 0, result.stdout + result.stderr


def write_report(name: str, report: dict[str, object]) -> int:
    directory = verification_dir(repo_root())
    directory.mkdir(parents=True, exist_ok=True)
    import json
    path = directory / f"{name}-report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{name.replace('-', '_')}_report_json={path}")
    print(f"overall_{name.replace('-', '_')}_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


def replay_evidence(events):
    """Return real full/checkpoint-tail replay evidence for one stage only."""
    from app.gameplay.replay import GameplayProjectionReplay

    replay = GameplayProjectionReplay(projector_id="verification:phase4", projector_version="v1")
    full = replay.full_replay(events)
    split_at = max(1, len(events) // 2)
    checkpoint = replay.create_checkpoint(events[:split_at])
    checkpoint_tail = replay.checkpoint_plus_tail_replay(checkpoint, events[split_at:])
    return full, checkpoint_tail
