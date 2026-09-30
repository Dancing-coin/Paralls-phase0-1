import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_phase0


def test_phase0_stub_probe_overrides_online_tts_without_changing_production_default():
    project_root = Path(__file__).resolve().parents[3]
    env = dict(os.environ, TTS_MODE="dashscope_http", PYTHONPATH=str(project_root / "backend"))
    env.update(verify_phase0.PHASE0_VERIFY_ENV)

    result = subprocess.run(
        [sys.executable, "-c", "from app.config import settings; print(settings.tts_mode)"],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "stub"
