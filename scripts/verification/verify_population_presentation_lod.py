"""记录 Godot 表现准入证据；后端绿色不能代替帧时间和可见结果。"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from common import artifact_path, resolve_godot_exe


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    report = {
        "stage": 5, "godot_status": "godot_unverified", "overall_passed": False,
        "presentation_implementation": "not_admitted_without_runtime_evidence",
        "near_character_count": None, "far_instance_count": None, "invisible_population_count": None,
        "frame_p95_ms": None, "gpu_ms": None, "network_bytes": None,
        "required_checks": [
            "真实后端 presentation 增量到达场景并产生可见变化",
            "近景、远景、不可见三组切换前后 Owner receipts、角色 revision、replay hash 相同",
            "记录 CPU/GPU 帧时间、网络消息、资源加载和各组数量",
            "仅在重复远景实例确为热点时采用 MultiMesh；记录整组可见性限制",
        ],
    }
    try:
        executable = resolve_godot_exe(args.godot_exe)
    except FileNotFoundError as exc:
        report["blocked_reason"] = str(exc)
    else:
        command = [str(executable), "--headless", "--path", str(root), "--editor", "--quit"]
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=180)
        report["editor_import"] = {"command": command, "exit_code": result.returncode,
                                   "output": result.stdout + result.stderr}
        report["blocked_reason"] = "编辑器导入不能证明100/1,000人两档表现成本和真实可见结果，仍需运行时采样"
    target = artifact_path(root, ".harness/verification/population-presentation-lod-report.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("population_presentation_lod_status=godot_unverified")
    return 2


if __name__ == "__main__":
    from pathlib import Path
    from run_context import run_scope

    with run_scope(Path(__file__).resolve().parents[2]):
        raise SystemExit(main())
