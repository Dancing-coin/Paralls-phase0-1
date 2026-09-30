from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from common import ensure_backend, repo_root, resolve_godot_exe, resolve_python_exe, run_command_until_markers, stop_backend, verification_dir


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    godot = resolve_godot_exe(args.godot_exe)
    python = resolve_python_exe(args.python_exe)
    env = {"PARALLS_HEAVENLY_GRAPH_PATH": ":memory:", "PARALLS_BACKEND_WS_URL": "ws://127.0.0.1:8000/ws", "PARALLS_STREET_PROBE": "2"}
    backend = None
    result = None
    error = ""
    try:
        _, backend = ensure_backend(ROOT, python, prefer_fresh_backend=True, env=env)
        result = run_command_until_markers(
            [str(godot), "--headless", "--path", str(ROOT), "--scene", "res://scenes/phase0/StreetCombatDemo.tscn", "--quit-after", "2400", "--render-thread", "safe", "--rendering-method", "gl_compatibility"],
            ROOT,
            verification_dir(ROOT) / "street-combat-godot.log",
            success_markers=[
                "street_combat_probe:backend_connected=true",
                "street_combat_probe:player_hit=true",
                "street_combat_probe:agent_hit=true",
                "street_combat_probe:duplicate_replayed=true",
                "street_combat_probe:stale_rejected=true",
                "street_combat_probe:recovery_committed=true",
                "street_combat_probe:duplicate_stale_recovery=true",
                "street_combat_probe:imported_attack_playback=true",
                "street_combat_probe:skeletons=3",
                "street_combat_probe:environment=true:collision=true:navigation=true",
                "street_combat_probe:hud_observed=true",
            ],
            timeout_seconds=60,
            env=env,
            require_all_markers=True,
        )
    except Exception as exc:
        error = f"{type(exc).__name__}:{exc}"
    finally:
        stop_backend(backend)
    runtime = {
        "status": "fresh-street-combat-runtime",
        "fresh_backend": True,
        "environment_loaded": bool(result and "street_combat_probe:environment=true" in result.stdout),
        "collision_loaded": bool(result and "street_combat_probe:environment=true:collision=true:navigation=true" in result.stdout),
        "navigation_loaded": bool(result and "street_combat_probe:environment=true:collision=true:navigation=true" in result.stdout),
        "skeleton_bindings": 3 if result and "street_combat_probe:skeletons=3" in result.stdout else 0,
        "player_authority_hit": bool(result and "street_combat_probe:player_hit=true" in result.stdout),
        "agent_authority_hit": bool(result and "street_combat_probe:agent_hit=true" in result.stdout),
        "duplicate_replayed": bool(result and "street_combat_probe:duplicate_replayed=true" in result.stdout),
        "stale_rejected": bool(result and "street_combat_probe:stale_rejected=true" in result.stdout),
        "recovery_committed": bool(result and "street_combat_probe:recovery_committed=true" in result.stdout),
        "hud_observed": bool(result and "street_combat_probe:hud_observed=true" in result.stdout),
        "godot_exit_code": getattr(result, "returncode", None),
        "marker_found": bool(result and result.marker_found),
        "error": error,
    }
    runtime["valid"] = bool(
        runtime["marker_found"]
        and runtime["environment_loaded"]
        and runtime["collision_loaded"]
        and runtime["navigation_loaded"]
        and runtime["skeleton_bindings"] == 3
        and runtime["player_authority_hit"]
        and runtime["agent_authority_hit"]
        and runtime["duplicate_replayed"]
        and runtime["stale_rejected"]
        and runtime["recovery_committed"]
        and runtime["hud_observed"]
    )
    evidence = verification_dir(ROOT) / "street-combat-runtime.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(runtime, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(runtime, sort_keys=True))
    return 0 if runtime["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
