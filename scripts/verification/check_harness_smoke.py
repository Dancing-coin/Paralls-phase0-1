from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


# 固定少量离线用例，避免收集会再次调用本入口的完整测试集。
SMOKE_TESTS = [
    "scripts/verification/tests/test_harness_suites.py::test_suite_selection_preserves_order_and_deduplicates",
    "scripts/verification/tests/test_harness_suites.py::test_all_preserves_legacy_profile_order_and_exclusions",
    "scripts/verification/tests/test_harness_suites.py::test_invalid_suite_manifest_is_rejected",
    "scripts/verification/tests/test_harness_suites.py::test_duplicate_profile_names_are_rejected",
    "scripts/verification/tests/test_harness_suites.py::test_invalid_profile_script_is_rejected",
    "scripts/verification/tests/test_harness_suites.py::test_invalid_timeout_is_rejected",
    "scripts/verification/tests/test_run_context.py",
    "scripts/verification/tests/test_harness_execution.py",
]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="harness-smoke-") as test_root:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--basetemp", test_root, *SMOKE_TESTS],
            cwd=Path(__file__).resolve().parents[2],
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            check=False,
            timeout=110,
        )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
