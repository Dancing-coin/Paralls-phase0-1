"""Capture a G0 pytest baseline without changing the runtime repository."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True, encoding="utf-8").strip()


def normalize(stack: str, root: Path) -> str:
    stack = stack.replace("\\", "/")
    for path, token in [(str(root), "<REPO>"), (sys.prefix, "<PYTHON>"), (os.environ.get("TEMP", ""), "<TEMP>")]:
        if path:
            stack = re.sub(re.escape(path.replace("\\", "/")), token, stack, flags=re.I)
    stack = re.sub(r"pytest-\d+", "pytest-N", stack)
    stack = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", stack)
    stack = re.sub(r"\b\d{4}-\d{2}-\d{2}[T ][0-9:.]+(?:Z|[+-]\d{2}:\d{2})?", "<TIME>", stack)
    return stack


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--freeze", action="store_true", help="Freeze all backend/tests/test_*.py files before running")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument("--test", action="append", help="Explicit smoke/diagnostic node IDs; not the full baseline")
    options = parser.parse_args()
    root = options.repo.resolve()
    backend = root / "backend"
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    head = git(root, "rev-parse", "HEAD")
    manifest_path = options.manifest.resolve() if options.manifest else output / "test-files.json"
    if options.freeze:
        files = sorted(p.relative_to(backend).as_posix() for p in (backend / "tests").rglob("test_*.py"))
        write_json(manifest_path, {"head": head, "files": [{"path": f, "sha256": digest((backend / f).read_bytes())} for f in files]})
    elif options.test:
        files = options.test
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["head"] != head:
            raise SystemExit("HEAD differs from frozen manifest")
        files = [item["path"] for item in manifest["files"]]
        for item in manifest["files"]:
            if digest((backend / item["path"]).read_bytes()) != item["sha256"]:
                raise SystemExit(f"Test changed: {item['path']}")
    packages = sorted([{"name": d.metadata["Name"], "version": d.version} for d in importlib.metadata.distributions()], key=lambda d: (d["name"] or "").lower())
    source_hashes = {p.relative_to(root).as_posix(): digest(p.read_bytes()) for p in sorted((backend / "app").rglob("*.py"))}
    environment = {
        "head": head, "git_status_before": git(root, "status", "--porcelain"),
        "commit": git(root, "log", "-1", "--format=%H %ai %s"), "repo": str(root),
        "python": sys.version, "executable": sys.executable, "os": platform.platform(),
        "packages": packages, "packages_sha256": digest(json.dumps(packages, sort_keys=True).encode()),
        "source_hashes": source_hashes, "file_count": len(files),
        "manifest_sha256": digest(manifest_path.read_bytes()) if manifest_path.exists() else None,
        "dependency_files": {name: digest((backend / name).read_bytes()) for name in ["pyproject.toml", "ci-constraints.txt"]},
        "pytest_env": {key: os.environ.get(key) for key in ["PYTHONHASHSEED", "PYTHONPATH", "PYTEST_ADDOPTS", "PYTEST_DISABLE_PLUGIN_AUTOLOAD"]},
    }
    write_json(output / "environment.json", environment)
    os.chdir(backend)
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(backend))
    import pytest

    class Capture:
        def __init__(self) -> None:
            self.tests: dict[str, dict] = {}
            self.failures: list[dict] = []
            self.collection_errors: list[dict] = []
            self.nodeids: list[str] = []
            self.started = datetime.now(timezone.utc).isoformat()

        def pytest_collection_finish(self, session):
            self.nodeids = [item.nodeid for item in session.items]
            write_json(output / "collected-nodeids.json", self.nodeids)

        def pytest_collectreport(self, report):
            if report.failed:
                self.collection_errors.append({"test_name": report.nodeid, "stack": str(report.longrepr)})

        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_makereport(self, item, call):
            result = yield
            report = result.get_result()
            if report.failed and call.excinfo:
                report.g0_error_type = call.excinfo.type.__name__
                report.g0_frames = [{"file": str(entry.path), "line": entry.lineno + 1, "function": entry.name} for entry in call.excinfo.traceback]

        def pytest_runtest_logreport(self, report):
            test = self.tests.setdefault(report.nodeid, {"test_name": report.nodeid, "phases": {}})
            test["phases"][report.when] = report.outcome
            if report.failed:
                stack = str(report.longrepr)
                normalized = normalize(stack, root)
                failure = {"test_name": report.nodeid, "phase": report.when,
                           "error_type": getattr(report, "g0_error_type", "Unknown"),
                           "message": str(getattr(getattr(report.longrepr, "reprcrash", None), "message", "")),
                           "stack_hash": digest(normalized.encode()), "stack": stack,
                           "normalized_stack": normalized, "frames": getattr(report, "g0_frames", [])}
                self.failures.append(failure)
                with (output / "failures.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(failure, ensure_ascii=False) + "\n")

        def pytest_sessionfinish(self, session, exitstatus):
            for test in self.tests.values():
                phases = test["phases"]
                test["outcome"] = ("error" if any(phases.get(p) == "failed" for p in ["setup", "teardown"]) else
                                   "failed" if phases.get("call") == "failed" else
                                   "skipped" if "skipped" in phases.values() else
                                   "passed" if phases.get("call") == "passed" else "incomplete")
            counts = dict(Counter(t["outcome"] for t in self.tests.values()))
            write_json(output / "results.json", {"head": head, "started": self.started,
                       "finished": datetime.now(timezone.utc).isoformat(), "exit_code": int(exitstatus),
                       "collected_count": len(self.nodeids), "counts": counts,
                       "collection_errors": self.collection_errors, "tests": list(self.tests.values()),
                       "failures": self.failures})

    if not options.test:
        actual = sorted(p.relative_to(backend).as_posix() for p in (backend / "tests").rglob("test_*.py"))
        if actual != files:
            raise SystemExit("Test file inventory differs from frozen manifest")
    # Directory collection avoids pytest's quadratic work for 1,000 explicit file arguments.
    args = [*(files if options.test else ["tests"]), "-v", "--tb=short", "-p", "no:cacheprovider", f"--junitxml={output / 'junit.xml'}"]
    if options.collect_only:
        args.append("--collect-only")
    write_json(output / "invocation.json", {"cwd": str(backend), "sys_path_prepend": [str(backend), str(root)], "pytest_args": args, "runner_argv": sys.argv})
    capture = Capture()
    status = pytest.main(args, plugins=[capture])
    environment["git_status_after"] = git(root, "status", "--porcelain")
    environment["head_after"] = git(root, "rev-parse", "HEAD")
    environment["source_unchanged"] = all((root / path).exists() and digest((root / path).read_bytes()) == sha for path, sha in source_hashes.items())
    write_json(output / "environment.json", environment)
    return int(status)


if __name__ == "__main__":
    raise SystemExit(main())
