# Harness Engineering Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve the existing Paralls verification Harness into a two-layer system with attributable Core Harness evidence, advisory feedback optimization, and governed Agent Harness proposals.

**Architecture:** Preserve scripts/verification/harness.py as the stable orchestration entry point and keep existing profile scripts as verification authorities. Add focused standard-library modules for schema normalization, suite resolution, process execution, impact selection, history retention, and Agent-facing evolution artifacts. Deliver P0, P1, and P2 in order, with a full verification checkpoint after each phase.

**Tech Stack:** Python 3.13 standard library, pytest, PowerShell, JSON and Markdown manifests under .harness/, GitHub Actions on windows-latest, existing Godot-backed local runtime profiles.

## Global Constraints

- Do not modify Backend, Godot, Siming, ESM, character cognition, or world-truth runtime behavior.
- Add no third-party Python dependency.
- Keep python scripts/verification/harness.py --profile all as the local broad-completion command.
- Hosted CI must execute a versioned non-Godot, non-credential suite.
- Change-aware profile selection is advisory and cannot emit a broad-completion verdict.
- Core facts and Agent hypotheses must use separate files and schemas.
- Agent Harness may create candidate manifests only; it may not apply code, edit Core verifier truth, or promote itself.
- P2 candidate paths are limited to Agent-facing Harness surfaces named in the approved design.
- Existing schema v1 run evidence must remain readable and must not be rewritten.
- Generated evidence stays under .harness/verification/ and remains ignored by Git.
- Use repository-relative artifact references in structured evidence.
- Retry only terminal causes explicitly listed in a profile manifest.
- Run the P0 checkpoint before starting P1 and the P1 checkpoint before starting P2.

---

## File Structure

### New Python Modules

- Create scripts/verification/harness_schema.py for schema v2 constants, normalization, hashes, environment classes, and atomic JSON writes.
- Create scripts/verification/harness_execution.py for one subprocess attempt, timeout handling, process-tree termination, and log capture.
- Create scripts/verification/harness_selection.py for changed-path matching and advisory profile selection.
- Create scripts/verification/suggest_harness_profiles.py as the advisory selection CLI.
- Create scripts/verification/harness_history.py for run indexing, evidence pins, baseline-family discovery, compaction, and retention.
- Create scripts/verification/agent_harness.py for context packs and validated RootCauseHypothesis records.
- Create scripts/verification/evaluate_harness_candidate.py for held-in and held-out evaluation briefs.

### New Versioned Harness Inputs

- Create .harness/suites/local-full.json.
- Create .harness/suites/ci-non-godot.json.
- Create .harness/suites/held-out-canary.json.
- Create .harness/agent/config.json.
- Create .harness/pins/.gitkeep.
- Create .harness/templates/evidence-pin-template.json.
- Create .harness/templates/root-cause-hypothesis-template.json.

### New Tests

- Create scripts/verification/tests/test_harness_schema.py.
- Create scripts/verification/tests/test_harness_suites.py.
- Create scripts/verification/tests/test_harness_execution.py.
- Create scripts/verification/tests/test_harness_selection.py.
- Create scripts/verification/tests/test_harness_history.py.
- Create scripts/verification/tests/test_agent_harness.py.
- Create scripts/verification/tests/test_harness_candidate_evaluation.py.

### Existing Files With Focused Responsibility Changes

- Modify scripts/verification/registry.py:1-70 to load suites and resolve profile filters.
- Modify scripts/verification/evidence.py:1-241 to emit schema v2 manifests, failure facts, compatible diffs, and relative artifact refs.
- Modify scripts/verification/harness.py:1-270 to select suites, execute attempts, record provisional evidence, and invoke index/retention refresh.
- Modify scripts/verification/tests/test_harness_runner.py:1-699 for schema v2 runner behavior.
- Modify scripts/verification/tests/test_harness_registry.py:1-130 for suite registration and new profile metadata.
- Modify scripts/verification/check_release_gate.py:1-106 and scripts/verification/tests/test_formal_profile_checks.py:40-50 for non-Godot hosted CI.
- Modify scripts/verification/check_harness_lifecycle.py:31-140 for operational retention and pin surfaces.
- Modify scripts/verification/evolution.py:1-419 for v2 failure patterns, hypotheses, strict candidate allowlists, and promotion evidence.
- Modify scripts/verification/analyze_harness_evolution.py:1-76 for context, hypothesis, and candidate CLI modes.
- Modify scripts/verification/tests/test_harness_evolution.py for v1 read compatibility and v2 write behavior.
- Modify every .harness/profiles/*.json manifest with explicit execution and selection metadata.
- Modify .harness/templates/profile-template.json with the same metadata contract.
- Modify .harness/retention-policy.json, .harness/evolution/config.json, .harness/evolution/replay-sets/default.json, and .harness/templates/evolution-candidate-template.json.
- Modify .harness/ci/release-gate.json, .harness/ci/local-ci-gate.ps1, .github/workflows/harness.yml, and related rule manifests.
- Modify AGENTS.md, docs/harness.md, docs/harness-architecture.md, docs/harness-reliability.md, docs/ai-engineering-workflow.md, and docs/INDEX.md only where the new command and authority contracts must be discoverable.

---

## P0 — Core Observability

### Task 1: Add Schema V2 And V1 Compatibility

**Files:**
- Create: scripts/verification/harness_schema.py
- Create: scripts/verification/tests/test_harness_schema.py

**Interfaces:**
- Consumes: schema v1 dictionaries already written by evidence.py.
- Produces: RUN_SCHEMA_VERSION, selected_profile_set_hash(profiles), normalize_run_manifest(payload, project_root), baseline_family_payload(manifest), baseline_family_id(manifest), repo_relative(project_root, value), atomic_write_json(path, payload).

- [ ] **Step 1: Write failing schema compatibility tests**

Create scripts/verification/tests/test_harness_schema.py:

~~~python
from __future__ import annotations

from pathlib import Path

from harness_schema import (
    baseline_family_id,
    normalize_run_manifest,
    selected_profile_set_hash,
)


def test_normalize_v1_manifest_preserves_exit_codes_and_marks_unknown_fields(tmp_path: Path) -> None:
    normalized = normalize_run_manifest(
        {
            "schema_version": 1,
            "run_id": "run-v1",
            "overall_harness_passed": False,
            "profile_exit_codes": [{"profile": "docs", "exit_code": 1}],
            "artifacts": {"latest_report_json": str(tmp_path / ".harness" / "verification" / "report.json")},
            "failure_digest_artifacts": [
                str(tmp_path / ".harness" / "verification" / "runs" / "run-v1" / "docs-failure-digest.json")
            ],
        },
        tmp_path,
    )

    assert normalized["schema_version"] == 2
    assert normalized["source_schema_version"] == 1
    assert normalized["suite_id"] == "legacy_unknown"
    assert normalized["profile_results"] == [
        {
            "profile": "docs",
            "exit_code": 1,
            "status": "legacy_unknown",
            "attempts": 0,
            "duration_ms": None,
            "terminal_cause": "legacy_unknown",
            "failure_domain": "legacy_unknown",
        }
    ]
    assert normalized["artifacts"]["latest_report_json"] == ".harness/verification/report.json"
    assert normalized["failure_fact_refs"] == [
        ".harness/verification/runs/run-v1/docs-failure-digest.json"
    ]


def test_baseline_family_is_order_stable_and_environment_sensitive() -> None:
    first = {
        "schema_version": 2,
        "suite_id": "local-full",
        "selected_profile_set_hash": selected_profile_set_hash(["docs", "boundaries"]),
        "environment_class": "local-with-godot",
    }
    reordered = {
        **first,
        "selected_profile_set_hash": selected_profile_set_hash(["boundaries", "docs"]),
    }
    hosted = {**first, "environment_class": "hosted-ci-non-godot"}

    assert baseline_family_id(first) == baseline_family_id(reordered)
    assert baseline_family_id(first) != baseline_family_id(hosted)
~~~

- [ ] **Step 2: Run the tests and verify the module is missing**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_harness_schema.py
~~~

Expected: collection fails with ModuleNotFoundError for harness_schema.

- [ ] **Step 3: Implement the schema helpers**

Create scripts/verification/harness_schema.py with these exact public functions:

~~~python
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


RUN_SCHEMA_VERSION = 2
LEGACY_UNKNOWN = "legacy_unknown"


def selected_profile_set_hash(profiles: list[str]) -> str:
    canonical = json.dumps(sorted(set(profiles)), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def repo_relative(project_root: Path, value: str | Path) -> str:
    path = Path(value)
    if not path.is_absolute():
        return str(path).replace("\\", "/")
    try:
        return str(path.resolve().relative_to(project_root.resolve())).replace("\\", "/")
    except ValueError:
        return f"legacy_external:{path.name}"


def normalize_run_manifest(payload: dict[str, object], project_root: Path) -> dict[str, object]:
    if int(payload.get("schema_version", 0)) == RUN_SCHEMA_VERSION:
        return payload
    profile_results = [
        {
            "profile": str(entry.get("profile", "")),
            "exit_code": int(entry.get("exit_code", 1)),
            "status": LEGACY_UNKNOWN,
            "attempts": 0,
            "duration_ms": None,
            "terminal_cause": LEGACY_UNKNOWN,
            "failure_domain": LEGACY_UNKNOWN,
        }
        for entry in payload.get("profile_exit_codes", [])
        if isinstance(entry, dict)
    ]
    artifacts = {
        str(key): repo_relative(project_root, str(value))
        for key, value in dict(payload.get("artifacts", {})).items()
    }
    return {
        "schema_version": RUN_SCHEMA_VERSION,
        "source_schema_version": int(payload.get("schema_version", 0)),
        "run_id": str(payload.get("run_id", "")),
        "suite_id": LEGACY_UNKNOWN,
        "selection_mode": LEGACY_UNKNOWN,
        "selected_profiles": [entry["profile"] for entry in profile_results],
        "selected_profile_set_hash": selected_profile_set_hash(
            [entry["profile"] for entry in profile_results]
        ),
        "environment_class": LEGACY_UNKNOWN,
        "environment_fingerprint": {"source": LEGACY_UNKNOWN},
        "git_commit": LEGACY_UNKNOWN,
        "git_dirty": LEGACY_UNKNOWN,
        "started_at": LEGACY_UNKNOWN,
        "finished_at": LEGACY_UNKNOWN,
        "duration_ms": None,
        "overall_verdict": "passed" if bool(payload.get("overall_harness_passed", False)) else "failed",
        "overall_harness_passed": bool(payload.get("overall_harness_passed", False)),
        "profile_results": profile_results,
        "artifacts": artifacts,
        "artifact_refs": artifacts,
        "failure_fact_refs": [
            repo_relative(project_root, str(value))
            for value in payload.get("failure_digest_artifacts", [])
        ],
        "active_harness_change_refs": [
            str(change.get("path"))
            for change in payload.get("harness_changes", [])
            if isinstance(change, dict) and isinstance(change.get("path"), str)
        ],
    }


def baseline_family_payload(manifest: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": int(manifest.get("schema_version", 0)),
        "suite_id": str(manifest.get("suite_id", LEGACY_UNKNOWN)),
        "selected_profile_set_hash": str(manifest.get("selected_profile_set_hash", "")),
        "environment_class": str(manifest.get("environment_class", LEGACY_UNKNOWN)),
    }


def baseline_family_id(manifest: dict[str, object]) -> str:
    canonical = json.dumps(baseline_family_payload(manifest), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".tmp-{os.getpid()}")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
~~~

- [ ] **Step 4: Run schema tests**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_harness_schema.py
~~~

Expected: 2 passed.

- [ ] **Step 5: Commit**

~~~powershell
git add scripts/verification/harness_schema.py scripts/verification/tests/test_harness_schema.py
git commit -m "feat: add harness evidence schema v2"
~~~

### Task 2: Add Suite Registry And Profile Capability Metadata

**Files:**
- Create: .harness/suites/local-full.json
- Create: .harness/suites/ci-non-godot.json
- Create: .harness/suites/held-out-canary.json
- Create: scripts/verification/tests/test_harness_suites.py
- Modify: scripts/verification/registry.py:8-70
- Modify: scripts/verification/tests/test_harness_registry.py:13-76
- Modify: .harness/profiles/*.json
- Modify: .harness/templates/profile-template.json

**Interfaces:**
- Consumes: ProfileRegistry from registry.py.
- Produces: SuiteRegistry, load_suite_registry(project_root), resolve_suite_profiles(suite_name, profile_registry, suite_registry).

- [ ] **Step 1: Write failing suite-resolution tests**

Create scripts/verification/tests/test_harness_suites.py:

~~~python
from __future__ import annotations

import json
from pathlib import Path

from registry import load_profile_registry, load_suite_registry, resolve_suite_profiles


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_ci_suite_excludes_godot_credentials_and_explicit_only_profiles(tmp_path: Path) -> None:
    _write(tmp_path / ".harness/profiles/docs.json", {
        "schema_version": 1, "name": "docs", "order": 10,
        "script": "scripts/verification/check_docs.py",
        "requires_godot": False, "requires_live_credentials": False,
    })
    _write(tmp_path / ".harness/profiles/phase0.json", {
        "schema_version": 1, "name": "phase0", "order": 20,
        "script": "scripts/verification/verify_phase0.py",
        "requires_godot": True, "requires_live_credentials": False,
    })
    _write(tmp_path / ".harness/profiles/live.json", {
        "schema_version": 1, "name": "live", "order": 30,
        "script": "scripts/verification/verify_live.py",
        "requires_godot": False, "requires_live_credentials": True,
        "include_in_all": False,
    })
    _write(tmp_path / ".harness/suites/ci-non-godot.json", {
        "schema_version": 1,
        "name": "ci-non-godot",
        "filters": {
            "include_in_all": True,
            "requires_godot": False,
            "requires_live_credentials": False,
        },
    })

    profiles = load_profile_registry(tmp_path)
    suites = load_suite_registry(tmp_path)

    assert resolve_suite_profiles("ci-non-godot", profiles, suites) == ["docs"]
~~~

- [ ] **Step 2: Run the suite test and verify missing APIs**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_harness_suites.py
~~~

Expected: import fails for load_suite_registry or resolve_suite_profiles.

- [ ] **Step 3: Extend registry.py**

Add:

~~~python
@dataclass(frozen=True)
class SuiteRegistry:
    suites: dict[str, dict[str, object]]


def load_suite_registry(project_root: Path) -> SuiteRegistry:
    suite_dir = project_root / ".harness" / "suites"
    suites: dict[str, dict[str, object]] = {}
    for path in sorted(suite_dir.glob("*.json")):
        payload = _read_manifest(path)
        suites[str(payload["name"])] = payload
    return SuiteRegistry(suites=suites)


def _profile_value(profile: dict[str, object], field: str) -> object:
    if field == "include_in_all":
        return bool(profile.get(field, True))
    if field in {"requires_godot", "requires_live_credentials"}:
        return bool(profile.get(field, False))
    return profile.get(field)


def resolve_suite_profiles(
    suite_name: str,
    profile_registry: ProfileRegistry,
    suite_registry: SuiteRegistry,
) -> list[str]:
    suite = suite_registry.suites.get(suite_name)
    if suite is None:
        raise ValueError(f"Unsupported suite: {suite_name}")
    explicit = suite.get("profiles")
    if isinstance(explicit, list):
        return [str(name) for name in explicit]
    filters = dict(suite.get("filters", {}))
    return [
        name
        for name in profile_registry.profile_order
        if all(_profile_value(profile_registry.profiles[name], key) == value for key, value in filters.items())
    ]
~~~

- [ ] **Step 4: Add suite manifests**

Create:

~~~json
{
  "schema_version": 1,
  "name": "local-full",
  "description": "Local broad-completion suite including Godot-backed runtime proof",
  "filters": {
    "include_in_all": true
  }
}
~~~

~~~json
{
  "schema_version": 1,
  "name": "ci-non-godot",
  "description": "Hosted CI suite without Godot or live-provider credentials",
  "filters": {
    "include_in_all": true,
    "requires_godot": false,
    "requires_live_credentials": false
  }
}
~~~

~~~json
{
  "schema_version": 1,
  "name": "held-out-canary",
  "description": "Protected Agent Harness regression suite",
  "protected": true,
  "profiles": [
    "docs",
    "harness-lifecycle",
    "change-lifecycle",
    "harness-reference",
    "harness-evolution"
  ]
}
~~~

- [ ] **Step 5: Add explicit profile execution metadata**

Add these keys to every profile manifest and to profile-template.json:

~~~json
{
  "requires_live_credentials": false,
  "timeout_seconds": 120,
  "retry_on": [],
  "failure_domain": "harness",
  "risk_class": "low",
  "watch_paths": [],
  "depends_on_profiles": []
}
~~~

Use this exact execution policy:

| Profile group | timeout_seconds | failure_domain | risk_class |
| --- | ---: | --- | --- |
| docs, boundaries, drift, release-gate, harness-lifecycle, change-lifecycle, harness-reference, harness-evolution | 120 | harness | low |
| backend-contract, godot-project, model-provider-readiness, vla-provider-backend, actor-scene-knowledge-lifecycle, siming-global-situation-layer, interaction-orchestration-service, non-runtime-production-pipeline, perception-input-alignment, siming-heavenly-graph-foundation | 600 | product | medium |
| character-agent-execution, l1-world-fact-runtime, phase1-slice, godot-sampling-production-grade-providers, embodied-skeletal-debug-replay, esm-physical-channel-world-actuation | 900 | product | high |
| phase0, mainline-unified-runtime | 1200 | product | high |
| siming-backend-chain, script-evolution-proof | 900 | product | high |

Set requires_live_credentials to true only for siming-backend-chain and script-evolution-proof.

Set retry_on to ["timeout", "process_crash"] only for phase0 and mainline-unified-runtime; keep [] for every other profile.

- [ ] **Step 6: Run registry and suite tests**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_harness_registry.py scripts/verification/tests/test_harness_suites.py
~~~

Expected: all tests pass and ci-non-godot resolves no Godot or live-credential profile.

- [ ] **Step 7: Commit**

~~~powershell
git add .harness/profiles .harness/suites .harness/templates/profile-template.json scripts/verification/registry.py scripts/verification/tests/test_harness_registry.py scripts/verification/tests/test_harness_suites.py
git commit -m "feat: add harness suite registry"
~~~

### Task 3: Add Attempt Execution With Timeout And Logs

**Files:**
- Create: scripts/verification/harness_execution.py
- Create: scripts/verification/tests/test_harness_execution.py

**Interfaces:**
- Consumes: command, cwd, stdout path, stderr path, timeout seconds.
- Produces: AttemptOutcome and run_profile_attempt(args, cwd, stdout_path, stderr_path, timeout_seconds).

- [ ] **Step 1: Write failing execution tests**

Create scripts/verification/tests/test_harness_execution.py:

~~~python
from __future__ import annotations

import sys
import subprocess
from pathlib import Path

import harness_execution
from harness_execution import run_profile_attempt


def test_run_profile_attempt_captures_separate_logs(tmp_path: Path) -> None:
    script = tmp_path / "emit.py"
    script.write_text(
        "import sys\nprint('out-line', flush=True)\nprint('err-line', file=sys.stderr, flush=True)\n",
        encoding="utf-8",
    )
    outcome = run_profile_attempt(
        [sys.executable, str(script)],
        tmp_path,
        tmp_path / "stdout.log",
        tmp_path / "stderr.log",
        timeout_seconds=5,
    )

    assert outcome.completion_state == "passed"
    assert outcome.exit_code == 0
    assert "out-line" in (tmp_path / "stdout.log").read_text(encoding="utf-8")
    assert "err-line" in (tmp_path / "stderr.log").read_text(encoding="utf-8")


def test_run_profile_attempt_times_out_and_terminates_process(tmp_path: Path) -> None:
    script = tmp_path / "sleep.py"
    script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")

    outcome = run_profile_attempt(
        [sys.executable, str(script)],
        tmp_path,
        tmp_path / "stdout.log",
        tmp_path / "stderr.log",
        timeout_seconds=0.1,
    )

    assert outcome.completion_state == "timed_out"
    assert outcome.terminal_cause == "timeout"
    assert outcome.duration_ms < 5000


class _FakeProcess:
    pid = 123

    def __init__(self, first_error: BaseException, second_error: BaseException | None = None) -> None:
        self.errors = [first_error, second_error]
        self.wait_calls = 0
        self.killed = False

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        if self.errors:
            error = self.errors.pop(0)
            if error is not None:
                raise error
        return -9

    def kill(self) -> None:
        self.killed = True


def test_run_profile_attempt_preserves_keyboard_interrupt(monkeypatch, tmp_path: Path) -> None:
    process = _FakeProcess(KeyboardInterrupt())
    monkeypatch.setattr(harness_execution.subprocess, "Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(harness_execution, "_terminate_process_tree", lambda _process: None)

    outcome = run_profile_attempt(
        [sys.executable, "unused.py"],
        tmp_path,
        tmp_path / "stdout.log",
        tmp_path / "stderr.log",
        timeout_seconds=1,
    )

    assert outcome.completion_state == "interrupted"
    assert outcome.terminal_cause == "interrupted"


def test_timeout_falls_back_to_kill_when_termination_wait_expires(monkeypatch, tmp_path: Path) -> None:
    process = _FakeProcess(
        subprocess.TimeoutExpired(cmd="unused", timeout=0.1),
        subprocess.TimeoutExpired(cmd="unused", timeout=5),
    )
    monkeypatch.setattr(harness_execution.subprocess, "Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(harness_execution, "_terminate_process_tree", lambda _process: None)

    outcome = run_profile_attempt(
        [sys.executable, "unused.py"],
        tmp_path,
        tmp_path / "stdout.log",
        tmp_path / "stderr.log",
        timeout_seconds=0.1,
    )

    assert outcome.completion_state == "timed_out"
    assert process.killed is True
~~~

- [ ] **Step 2: Run tests and verify the module is missing**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_harness_execution.py
~~~

Expected: collection fails with ModuleNotFoundError for harness_execution.

- [ ] **Step 3: Implement the executor**

Create scripts/verification/harness_execution.py:

~~~python
from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AttemptOutcome:
    completion_state: str
    exit_code: int
    terminal_cause: str
    duration_ms: int


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def _terminate_and_wait(process: subprocess.Popen[str]) -> None:
    _terminate_process_tree(process)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def run_profile_attempt(
    args: list[str],
    cwd: Path,
    stdout_path: Path,
    stderr_path: Path,
    *,
    timeout_seconds: float,
) -> AttemptOutcome:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    popen_kwargs: dict[str, object] = {}
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_handle:
        process = subprocess.Popen(
            args,
            cwd=str(cwd),
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            **popen_kwargs,
        )
        try:
            exit_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            _terminate_and_wait(process)
            return AttemptOutcome(
                completion_state="timed_out",
                exit_code=124,
                terminal_cause="timeout",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        except KeyboardInterrupt:
            _terminate_and_wait(process)
            return AttemptOutcome(
                completion_state="interrupted",
                exit_code=130,
                terminal_cause="interrupted",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
    return AttemptOutcome(
        completion_state="passed" if exit_code == 0 else "failed",
        exit_code=exit_code,
        terminal_cause="none" if exit_code == 0 else "process_crash",
        duration_ms=int((time.monotonic() - start) * 1000),
    )
~~~

- [ ] **Step 4: Run execution tests**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_harness_execution.py
~~~

Expected: 4 passed.

- [ ] **Step 5: Commit**

~~~powershell
git add scripts/verification/harness_execution.py scripts/verification/tests/test_harness_execution.py
git commit -m "feat: record bounded harness attempts"
~~~

### Task 4: Emit V2 Run Manifests, Failure Facts, And Comparable Diffs

**Files:**
- Modify: scripts/verification/evidence.py:1-241
- Modify: scripts/verification/tests/test_harness_runner.py:1-441

**Interfaces:**
- Consumes: normalized attempt records and profile configs.
- Produces: build_run_manifest_v2(...), classify_terminal_cause(...), build_failure_fact(...), archive_profile_artifacts(...), build_run_diff(previous, current), read_compatible_baseline(project_root, manifest), promote_successful_baseline(project_root, manifest).

- [ ] **Step 1: Write failing evidence tests**

Add to test_harness_runner.py:

~~~python
from evidence import build_failure_fact, build_run_diff


def test_run_diff_refuses_incompatible_baseline_families() -> None:
    previous = {
        "schema_version": 2,
        "run_id": "run-docs",
        "suite_id": "explicit:docs",
        "selected_profile_set_hash": "docs-hash",
        "environment_class": "local-without-godot",
        "profile_results": [{"profile": "docs", "exit_code": 0}],
    }
    current = {
        "schema_version": 2,
        "run_id": "run-all",
        "suite_id": "local-full",
        "selected_profile_set_hash": "all-hash",
        "environment_class": "local-with-godot",
        "profile_results": [{"profile": "docs", "exit_code": 0}],
    }

    diff = build_run_diff(previous, current)

    assert diff["comparison_status"] == "no_comparable_baseline"
    assert diff["profile_changes"] == []


def test_failure_fact_distinguishes_missing_and_invalid_reports(tmp_path: Path) -> None:
    missing = build_failure_fact(
        project_root=tmp_path,
        run_id="run-1",
        profile="docs",
        attempt=1,
        exit_code=1,
        completion_state="failed",
        profile_config={"result_artifact": ".harness/verification/docs-report.json", "failure_domain": "harness"},
        attempt_artifact_was_refreshed=False,
    )
    report_path = tmp_path / ".harness/verification/docs-report.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text("{bad-json", encoding="utf-8")
    invalid = build_failure_fact(
        project_root=tmp_path,
        run_id="run-2",
        profile="docs",
        attempt=1,
        exit_code=1,
        completion_state="failed",
        profile_config={"result_artifact": ".harness/verification/docs-report.json", "failure_domain": "harness"},
        attempt_artifact_was_refreshed=True,
    )

    assert missing["terminal_cause"] == "report_missing"
    assert invalid["terminal_cause"] == "report_invalid"


def test_failure_fact_covers_preflight_timeout_crash_and_structured_failure(tmp_path: Path) -> None:
    report_path = tmp_path / ".harness/verification/docs-report.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps({"results": [{"id": "docs_index_paths_exist", "status": "missing"}]}),
        encoding="utf-8",
    )
    common = {
        "project_root": tmp_path,
        "run_id": "run-1",
        "profile": "docs",
        "attempt": 1,
        "exit_code": 1,
    }

    preflight = build_failure_fact(
        **common,
        completion_state="preflight_failed",
        profile_config={"failure_domain": "environment"},
        attempt_artifact_was_refreshed=False,
    )
    timeout = build_failure_fact(
        **common,
        completion_state="timed_out",
        profile_config={"failure_domain": "harness"},
        attempt_artifact_was_refreshed=False,
    )
    crash = build_failure_fact(
        **common,
        completion_state="failed",
        profile_config={"failure_domain": "harness"},
        attempt_artifact_was_refreshed=False,
    )
    structured = build_failure_fact(
        **common,
        completion_state="failed",
        profile_config={
            "result_artifact": ".harness/verification/docs-report.json",
            "failure_domain": "harness",
        },
        attempt_artifact_was_refreshed=True,
    )

    assert preflight["terminal_cause"] == "environment_missing"
    assert timeout["terminal_cause"] == "timeout"
    assert crash["terminal_cause"] == "process_crash"
    assert structured["terminal_cause"] == "structured_check_failed"
    assert structured["failed_check_ids"] == ["docs_index_paths_exist"]
~~~

- [ ] **Step 2: Run the focused tests and verify current behavior fails**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_harness_runner.py -k "incompatible_baseline or missing_and_invalid"
~~~

Expected: tests fail because v1 diff and FailureFact APIs do not exist.

- [ ] **Step 3: Add v2 evidence builders**

Implement these public functions in evidence.py:

~~~python
import shutil

from harness_schema import (
    atomic_write_json,
    baseline_family_id,
    normalize_run_manifest,
    repo_relative,
    selected_profile_set_hash,
)


def build_run_manifest_v2(
    *,
    run_id: str,
    suite_id: str,
    selection_mode: str,
    selected_profiles: list[str],
    environment_fingerprint: dict[str, object],
    environment_class: str,
    started_at: str,
    finished_at: str,
    duration_ms: int,
    overall_passed: bool,
    profile_results: list[dict[str, object]],
    artifacts: dict[str, str],
    git_commit: str,
    git_dirty: bool,
    active_harness_change_refs: list[str] | None = None,
    harness_changes: list[dict[str, object]] | None = None,
    harness_change_errors: list[dict[str, object]] | None = None,
    failure_fact_refs: list[str] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "run_id": run_id,
        "suite_id": suite_id,
        "selection_mode": selection_mode,
        "selected_profiles": selected_profiles,
        "selected_profile_set_hash": selected_profile_set_hash(selected_profiles),
        "environment_fingerprint": environment_fingerprint,
        "environment_class": environment_class,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": duration_ms,
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "overall_verdict": "passed" if overall_passed else "failed",
        "overall_harness_passed": overall_passed,
        "profile_results": profile_results,
        "artifacts": artifacts,
        "artifact_refs": artifacts,
        "active_harness_change_refs": active_harness_change_refs or [],
        "harness_changes": harness_changes or [],
        "harness_change_errors": harness_change_errors or [],
        "failure_fact_refs": failure_fact_refs or [],
    }


def classify_terminal_cause(
    *,
    completion_state: str,
    exit_code: int,
    report_path: Path | None,
    attempt_artifact_was_refreshed: bool,
) -> str:
    if completion_state == "preflight_failed":
        return "environment_missing"
    if completion_state == "timed_out":
        return "timeout"
    if completion_state == "interrupted":
        return "interrupted"
    if report_path is not None and (
        not report_path.exists() or not attempt_artifact_was_refreshed
    ):
        return "report_missing"
    if report_path is not None:
        report = _read_json_object_tolerant(report_path)
        if report is None:
            return "report_invalid"
        if exit_code != 0 or extract_failed_checks(report):
            return "structured_check_failed"
        return "none"
    if exit_code != 0:
        return "process_crash"
    return "none"


def build_failure_fact(
    *,
    project_root: Path,
    run_id: str,
    profile: str,
    attempt: int,
    exit_code: int,
    completion_state: str,
    profile_config: dict[str, object],
    attempt_artifact_was_refreshed: bool,
) -> dict[str, object]:
    artifact = str(profile_config.get("result_artifact", "") or "")
    report_path = project_root / artifact if artifact else None
    terminal_cause = classify_terminal_cause(
        completion_state=completion_state,
        exit_code=exit_code,
        report_path=report_path,
        attempt_artifact_was_refreshed=attempt_artifact_was_refreshed,
    )
    report = _read_json_object_tolerant(report_path) if report_path is not None else None
    failed_checks = extract_failed_checks(report or {})
    if terminal_cause == "environment_missing":
        failure_domain = "environment"
    elif terminal_cause in {"report_missing", "report_invalid"}:
        failure_domain = "evidence"
    else:
        failure_domain = str(profile_config.get("failure_domain", "unknown"))
    return {
        "schema_version": 2,
        "fact_id": f"failure:{run_id}:{profile}:{attempt}",
        "run_id": run_id,
        "profile": profile,
        "attempt": attempt,
        "exit_code": exit_code,
        "completion_state": completion_state,
        "terminal_cause": terminal_cause,
        "failure_domain": failure_domain,
        "failed_check_ids": [str(entry["id"]) for entry in failed_checks],
        "evidence_refs": [str(entry) for entry in _source_artifacts(project_root, report_path)],
        "observed_notes": "",
    }


def _nested_path_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for entry in value for item in _nested_path_values(entry)]
    if isinstance(value, dict):
        return [item for entry in value.values() for item in _nested_path_values(entry)]
    return []


def archive_profile_artifacts(
    project_root: Path,
    run_dir: Path,
    profile: str,
    attempt: int,
    profile_config: dict[str, object],
) -> dict[str, object]:
    artifact = str(profile_config.get("result_artifact", "") or "")
    report_path = project_root / artifact if artifact else None
    candidates: list[Path] = []
    if report_path is not None and report_path.exists():
        candidates.extend([report_path, report_path.with_suffix(".md")])
        report = _read_json_object_tolerant(report_path) or {}
        for value in _nested_path_values(report):
            candidate = Path(value)
            if not candidate.is_absolute():
                candidate = project_root / candidate
            if candidate.suffix.lower() in {".png", ".jpg", ".jpeg", ".ndjson"}:
                candidates.append(candidate)
    trace_path = project_root / ".harness" / "verification" / f"{profile}-runtime-trace.ndjson"
    candidates.append(trace_path)

    archived: dict[Path, str] = {}
    for source in candidates:
        if not source.exists() or not source.resolve().is_relative_to(project_root.resolve()):
            continue
        relative_source = source.resolve().relative_to(project_root.resolve())
        destination = run_dir / "artifacts" / f"{profile}-{attempt}" / relative_source
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        archived[source.resolve()] = repo_relative(project_root, destination)

    structured_report_ref = (
        archived.get(report_path.resolve(), "")
        if report_path is not None and report_path.exists()
        else ""
    )
    trace_refs = [ref for path, ref in archived.items() if path.suffix.lower() == ".ndjson"]
    screenshot_refs = [
        ref for path, ref in archived.items()
        if path.suffix.lower() in {".png", ".jpg", ".jpeg"}
    ]
    source_refs = sorted(set(archived.values()))
    return {
        "structured_report_ref": structured_report_ref,
        "trace_refs": trace_refs,
        "screenshot_refs": screenshot_refs,
        "source_artifact_refs": source_refs,
    }


def result_artifact_snapshot(
    project_root: Path,
    profile_config: dict[str, object],
) -> tuple[int, int] | None:
    artifact = str(profile_config.get("result_artifact", "") or "")
    if artifact == "":
        return None
    path = project_root / artifact
    if not path.exists():
        return None
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


def result_artifact_was_refreshed(
    project_root: Path,
    profile_config: dict[str, object],
    before: tuple[int, int] | None,
) -> bool:
    after = result_artifact_snapshot(project_root, profile_config)
    return after is not None and after != before
~~~

Replace build_run_diff with a family-aware implementation:

~~~python
def _profile_results(manifest: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        str(entry["profile"]): entry
        for entry in manifest.get("profile_results", [])
        if isinstance(entry, dict) and isinstance(entry.get("profile"), str)
    }


def _comparison_projection(entry: dict[str, object]) -> dict[str, object]:
    artifact_refs = [
        str(value)
        for field in (
            "structured_report_ref",
            "trace_refs",
            "screenshot_refs",
            "source_artifact_refs",
        )
        for value in (
            entry.get(field, [])
            if isinstance(entry.get(field), list)
            else [entry.get(field)]
        )
        if isinstance(value, str) and value
    ]
    failed_check_ids = entry.get("failed_check_ids", [])
    return {
        "verdict": str(entry.get("status", "missing")),
        "attempt_count": int(entry.get("attempts") or 0),
        "duration_ms": int(entry.get("duration_ms") or 0),
        "terminal_cause": str(entry.get("terminal_cause", "unknown")),
        "failed_check_ids": sorted(
            str(value) for value in failed_check_ids
        ) if isinstance(failed_check_ids, list) else [],
        "artifact_refs": sorted(set(artifact_refs)),
    }


def build_run_diff(previous: dict[str, object] | None, current: dict[str, object]) -> dict[str, object]:
    if previous is None or baseline_family_id(previous) != baseline_family_id(current):
        return {
            "schema_version": 2,
            "previous_run_id": previous.get("run_id") if previous else None,
            "current_run_id": current["run_id"],
            "comparison_status": "no_comparable_baseline",
            "profile_changes": [],
        }
    previous_profiles = _profile_results(previous)
    current_profiles = _profile_results(current)
    changes: list[dict[str, object]] = []
    for name in sorted(set(previous_profiles) | set(current_profiles)):
        before = _comparison_projection(previous_profiles.get(name, {}))
        after = _comparison_projection(current_profiles.get(name, {}))
        if before == after:
            continue
        changes.append({"profile": name, "previous": before, "current": after})
    return {
        "schema_version": 2,
        "previous_run_id": previous["run_id"],
        "current_run_id": current["run_id"],
        "comparison_status": "comparable",
        "profile_changes": changes,
    }
~~~

- [ ] **Step 4: Add baseline-family storage**

Add these functions:

~~~python
def _family_baseline_path(project_root: Path, manifest: dict[str, object]) -> Path:
    return (
        project_root
        / ".harness"
        / "verification"
        / "baselines"
        / f"{baseline_family_id(manifest)}.json"
    )


def read_compatible_baseline(
    project_root: Path,
    manifest: dict[str, object],
) -> dict[str, object] | None:
    payload = read_json_object(_family_baseline_path(project_root, manifest))
    if payload is None:
        return None
    normalized = normalize_run_manifest(payload, project_root)
    return normalized if baseline_family_id(normalized) == baseline_family_id(manifest) else None


def promote_successful_baseline(
    project_root: Path,
    manifest: dict[str, object],
) -> None:
    if not bool(manifest.get("overall_harness_passed", False)):
        return
    family_path = _family_baseline_path(project_root, manifest)
    atomic_write_json(family_path, manifest)
    atomic_write_json(project_root / ".harness" / "verification" / "baseline.json", manifest)
~~~

Store successful baselines under .harness/verification/baselines/<family-id>.json. Keep baseline.json as the latest successful compatible baseline convenience copy. Do not update either file after a failed run.

- [ ] **Step 5: Run evidence tests**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_harness_runner.py -k "run_diff or failure_fact or failure_digest"
~~~

Expected: focused tests pass.

- [ ] **Step 6: Commit**

~~~powershell
git add scripts/verification/evidence.py scripts/verification/tests/test_harness_runner.py
git commit -m "feat: add attributable harness evidence"
~~~

### Task 5: Integrate Suites, Attempts, Retry Policy, And V2 Reports In The Runner

**Files:**
- Modify: scripts/verification/harness.py:1-270
- Modify: scripts/verification/tests/test_harness_runner.py:442-599

**Interfaces:**
- Consumes: resolve_suite_profiles, run_profile_attempt, schema v2 evidence builders.
- Produces: --suite NAME, provisional attempt files, attempt logs, preflight FailureFacts, flaky_pass profile status, run manifest v2.

- [ ] **Step 1: Write failing runner integration tests**

Add this import and the tests:

~~~python
from harness_execution import AttemptOutcome


def test_harness_runner_records_flaky_pass_and_attempt_artifacts(monkeypatch, tmp_path: Path) -> None:
    registry = SimpleNamespace(
        profiles={
            "phase0": {
                "name": "phase0",
                "script": "scripts/verification/verify_phase0.py",
                "requires_godot": False,
                "max_attempts": 2,
                "retry_on": ["process_crash"],
                "timeout_seconds": 30,
                "failure_domain": "product",
            }
        },
        profile_order=["phase0"],
    )
    outcomes = iter([
        AttemptOutcome("failed", 1, "process_crash", 10),
        AttemptOutcome("passed", 0, "none", 12),
    ])
    monkeypatch.setattr(harness, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(harness, "resolve_python_exe", lambda _value: "python")
    monkeypatch.setattr(harness, "_resolve_godot_exe", lambda _value: None)
    monkeypatch.setattr(harness, "load_profile_registry", lambda _root: registry)
    monkeypatch.setattr(
        harness,
        "load_suite_registry",
        lambda _root: SimpleNamespace(suites={}),
    )
    monkeypatch.setattr(harness, "run_profile_attempt", lambda *args, **kwargs: next(outcomes))
    monkeypatch.setattr(sys, "argv", ["harness.py", "--profile", "phase0"])

    exit_code = harness.main()
    report = json.loads(
        (tmp_path / ".harness/verification/harness-run-report.json").read_text(encoding="utf-8")
    )
    run_id = str(report["run_id"])
    attempt_dir = tmp_path / ".harness" / "verification" / "runs" / run_id / "attempts"
    archived_attempt_1 = json.loads(
        (attempt_dir / "phase0-1.json").read_text(encoding="utf-8")
    )
    archived_attempt_2 = json.loads(
        (attempt_dir / "phase0-2.json").read_text(encoding="utf-8")
    )

    assert exit_code == 0
    assert report["profiles"][0]["status"] == "flaky_pass"
    assert len(report["profiles"][0]["attempt_records"]) == 2
    assert archived_attempt_1["record_state"] == "final"
    assert archived_attempt_2["completion_state"] == "passed"


def test_harness_runner_does_not_retry_terminal_cause_outside_retry_on(monkeypatch, tmp_path: Path) -> None:
    calls = {"count": 0}
    report_path = tmp_path / ".harness" / "verification" / "docs-report.json"
    registry = SimpleNamespace(
        profiles={
            "docs": {
                "name": "docs",
                "script": "scripts/verification/check_docs.py",
                "requires_godot": False,
                "max_attempts": 2,
                "retry_on": ["timeout"],
                "timeout_seconds": 30,
                "failure_domain": "harness",
                "result_artifact": ".harness/verification/docs-report.json",
            }
        },
        profile_order=["docs"],
    )

    def fake_attempt(*_args, **_kwargs) -> AttemptOutcome:
        calls["count"] += 1
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps({
                "results": [
                    {"id": "docs_index_paths_exist", "status": "missing", "evidence": []}
                ]
            }),
            encoding="utf-8",
        )
        return AttemptOutcome("failed", 1, "process_crash", 10)

    monkeypatch.setattr(harness, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(harness, "resolve_python_exe", lambda _value: "python")
    monkeypatch.setattr(harness, "_resolve_godot_exe", lambda _value: None)
    monkeypatch.setattr(harness, "load_profile_registry", lambda _root: registry)
    monkeypatch.setattr(
        harness,
        "load_suite_registry",
        lambda _root: SimpleNamespace(suites={}),
    )
    monkeypatch.setattr(harness, "run_profile_attempt", fake_attempt)
    monkeypatch.setattr(sys, "argv", ["harness.py", "--profile", "docs"])

    exit_code = harness.main()

    assert exit_code == 1
    assert calls["count"] == 1
~~~

Update the existing missing-Godot regression assertions so the preflight is a finalized, non-subprocess attempt rather than attempts=0:

~~~python
assert exit_code == 1
assert calls["count"] == 0
assert report["profiles"][0]["attempts"] == 1
assert report["profiles"][0]["status"] == "preflight_failed"
assert report["profiles"][0]["terminal_cause"] == "environment_missing"
assert report["profiles"][0]["command"] == [
    "python",
    "scripts/verification/verify_phase0.py",
    "--python-exe",
    "python",
]
run_id = str(report["run_id"])
failure_fact = json.loads(
    (tmp_path / ".harness/verification/runs" / run_id / "failures/phase0-1.json").read_text(
        encoding="utf-8"
    )
)
assert failure_fact["terminal_cause"] == "environment_missing"
assert failure_fact["failure_domain"] == "environment"
~~~

Add this redaction regression beside the runner tests:

~~~python
def test_environment_fingerprint_uses_executable_identity_not_user_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(harness, "_bounded_command_output", lambda *_args: "4.6.3.stable")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    fingerprint, environment_class = harness._environment_fingerprint(
        tmp_path,
        str(tmp_path / "venv/Scripts/python.exe"),
        str(tmp_path / "tools/Godot.exe"),
    )

    assert fingerprint["python_executable"] == "python.exe"
    assert fingerprint["godot_version"] == "4.6.3.stable"
    assert str(tmp_path) not in json.dumps(fingerprint)
    assert environment_class == "local-with-godot"
~~~

- [ ] **Step 2: Run focused runner tests**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_harness_runner.py -k "flaky_pass or outside_retry_on"
~~~

Expected: tests fail because the runner still stores one aggregate attempt count.

- [ ] **Step 3: Add mutually exclusive profile and suite selection**

Use:

~~~python
selection = parser.add_mutually_exclusive_group()
selection.add_argument("--profile", choices=PROFILES, default=None)
selection.add_argument("--suite", choices=SUITES, default=None)
profile_selection = args.profile or ("all" if args.suite is None else None)
if args.suite:
    profiles = resolve_suite_profiles(args.suite, registry, suite_registry)
    suite_id = args.suite
    selection_mode = "explicit-suite"
elif profile_selection == "all":
    profiles = resolve_suite_profiles("local-full", registry, suite_registry)
    suite_id = "local-full"
    selection_mode = "legacy-all"
else:
    profiles = [str(profile_selection)]
    suite_id = f"explicit:{profile_selection}"
    selection_mode = "explicit-profile"
~~~

Define the module-level choices from both registries:

~~~python
PROFILE_REGISTRY = load_profile_registry(repo_root())
SUITE_REGISTRY = load_suite_registry(repo_root())
PROFILES = (*PROFILE_REGISTRY.profile_order, "all")
SUITES = tuple(sorted(SUITE_REGISTRY.suites))
~~~

- [ ] **Step 4: Record environment fingerprint**

Add helpers in harness.py that record bounded environment and Git identity without user-directory paths or secret values:

~~~python
import os
import platform
import subprocess
from datetime import datetime, timezone

from harness_execution import AttemptOutcome, run_profile_attempt
from harness_schema import atomic_write_json, repo_relative
from evidence import (
    archive_profile_artifacts,
    build_failure_fact,
    result_artifact_snapshot,
    result_artifact_was_refreshed,
)
from registry import load_profile_registry, load_suite_registry, resolve_suite_profiles


def _bounded_command_output(args: list[str], project_root: Path) -> str:
    try:
        result = subprocess.run(
            args,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    return result.stdout.strip().splitlines()[0] if result.returncode == 0 and result.stdout.strip() else "unavailable"


def _environment_fingerprint(
    project_root: Path,
    python_exe: str,
    godot_exe: str | None,
) -> tuple[dict[str, object], str]:
    hosted_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    fingerprint = {
        "os": platform.system(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "python_executable": Path(python_exe).name,
        "godot_available": godot_exe is not None,
        "godot_version": (
            _bounded_command_output([godot_exe, "--version"], project_root)
            if godot_exe is not None
            else "unavailable"
        ),
        "runner_schema_version": 2,
        "capabilities": {
            "hosted_ci": hosted_ci,
            "godot": godot_exe is not None,
        },
    }
    if hosted_ci:
        environment_class = "hosted-ci-non-godot"
    elif godot_exe is not None:
        environment_class = "local-with-godot"
    else:
        environment_class = "local-without-godot"
    return fingerprint, environment_class


def _git_identity(project_root: Path) -> tuple[str, bool]:
    commit = _bounded_command_output(["git", "rev-parse", "HEAD"], project_root)
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return commit, True
    return commit, bool(status.stdout.strip()) or status.returncode != 0


def _normalized_command(project_root: Path, command: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in command:
        path = Path(value)
        if path.is_absolute():
            relative = repo_relative(project_root, path)
            normalized.append(path.name if Path(relative).is_absolute() else relative)
        else:
            normalized.append(value)
    return normalized
~~~

Pass git_commit, git_dirty, and active_harness_change_refs=[change["path"] for change in harness_changes] into build_run_manifest_v2. Pass every artifacts value through repo_relative before writing either the latest or archived manifest.

- [ ] **Step 5: Execute attempts with provisional evidence**

Add this helper and call it from the main profile loop:

~~~python
def _execute_profile(
    *,
    project_root: Path,
    run_dir: Path,
    run_id: str,
    profile: str,
    profile_config: dict[str, object],
    command: list[str],
    preflight_error: str | None,
) -> tuple[dict[str, object], list[str]]:
    max_attempts = max(1, int(profile_config.get("max_attempts", 1)))
    retry_on = {str(value) for value in profile_config.get("retry_on", [])}
    timeout_seconds = float(profile_config.get("timeout_seconds", 600))
    attempt_records: list[dict[str, object]] = []
    failure_fact_refs: list[str] = []

    for attempt in range(1, max_attempts + 1):
        attempt_path = run_dir / "attempts" / f"{profile}-{attempt}.json"
        stdout_path = run_dir / "attempts" / f"{profile}-{attempt}.stdout.log"
        stderr_path = run_dir / "attempts" / f"{profile}-{attempt}.stderr.log"
        before = result_artifact_snapshot(project_root, profile_config)
        started_at = datetime.now(timezone.utc).isoformat()
        atomic_write_json(
            attempt_path,
            {
                "schema_version": 2,
                "record_state": "provisional",
                "run_id": run_id,
                "profile": profile,
                "attempt": attempt,
                "command": _normalized_command(project_root, command),
                "started_at": started_at,
                "environment_requirements": {
                    "requires_godot": bool(profile_config.get("requires_godot", False)),
                    "requires_live_credentials": bool(
                        profile_config.get("requires_live_credentials", False)
                    ),
                },
                "environment_resolution": {
                    "godot": (
                        "missing" if preflight_error is not None
                        else "resolved" if profile_config.get("requires_godot")
                        else "not_required"
                    ),
                    "live_credentials": (
                        "profile_managed"
                        if profile_config.get("requires_live_credentials")
                        else "not_required"
                    ),
                },
                "stdout_ref": repo_relative(project_root, stdout_path),
                "stderr_ref": repo_relative(project_root, stderr_path),
            },
        )
        if preflight_error is not None:
            stderr_path.parent.mkdir(parents=True, exist_ok=True)
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text(preflight_error + "\n", encoding="utf-8")
            outcome = AttemptOutcome(
                completion_state="preflight_failed",
                exit_code=1,
                terminal_cause="environment_missing",
                duration_ms=0,
            )
        else:
            outcome = run_profile_attempt(
                command,
                project_root,
                stdout_path,
                stderr_path,
                timeout_seconds=timeout_seconds,
            )
        refreshed = result_artifact_was_refreshed(project_root, profile_config, before)
        failure_fact = None
        configured_report = bool(str(profile_config.get("result_artifact", "") or ""))
        if outcome.exit_code != 0 or outcome.completion_state != "passed" or (configured_report and not refreshed):
            failure_fact = build_failure_fact(
                project_root=project_root,
                run_id=run_id,
                profile=profile,
                attempt=attempt,
                exit_code=outcome.exit_code,
                completion_state=outcome.completion_state,
                profile_config=profile_config,
                attempt_artifact_was_refreshed=refreshed,
            )
        terminal_cause = (
            str(failure_fact["terminal_cause"])
            if failure_fact is not None
            else "none"
        )
        archived_artifacts = archive_profile_artifacts(
            project_root,
            run_dir,
            profile,
            attempt,
            profile_config,
        )
        effective_completion_state = outcome.completion_state
        if terminal_cause != "none" and outcome.completion_state == "passed":
            effective_completion_state = "failed"
        if failure_fact is not None:
            failure_fact["evidence_refs"] = sorted(
                {
                    repo_relative(project_root, stdout_path),
                    repo_relative(project_root, stderr_path),
                    *list(archived_artifacts["source_artifact_refs"]),
                }
            )
        final_record = {
            "schema_version": 2,
            "record_state": "final",
            "run_id": run_id,
            "profile": profile,
            "attempt": attempt,
            "command": _normalized_command(project_root, command),
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": outcome.duration_ms,
            "completion_state": effective_completion_state,
            "exit_code": outcome.exit_code,
            "terminal_cause": terminal_cause,
            "failure_domain": (
                str(failure_fact["failure_domain"])
                if failure_fact is not None
                else str(profile_config.get("failure_domain", "unknown"))
            ),
            "environment_requirements": {
                "requires_godot": bool(profile_config.get("requires_godot", False)),
                "requires_live_credentials": bool(
                    profile_config.get("requires_live_credentials", False)
                ),
            },
            "environment_resolution": {
                "godot": (
                    "missing" if preflight_error is not None
                    else "resolved" if profile_config.get("requires_godot")
                    else "not_required"
                ),
                "live_credentials": (
                    "profile_managed"
                    if profile_config.get("requires_live_credentials")
                    else "not_required"
                ),
            },
            "stdout_ref": repo_relative(project_root, stdout_path),
            "stderr_ref": repo_relative(project_root, stderr_path),
            **archived_artifacts,
        }
        atomic_write_json(attempt_path, final_record)
        attempt_records.append(final_record)
        if failure_fact is not None:
            fact_path = run_dir / "failures" / f"{profile}-{attempt}.json"
            atomic_write_json(fact_path, failure_fact)
            failure_fact_refs.append(repo_relative(project_root, fact_path))
        if terminal_cause == "none" or terminal_cause not in retry_on or preflight_error is not None:
            break

    final_attempt = attempt_records[-1]
    final_terminal_cause = str(final_attempt["terminal_cause"])
    process_exit_code = int(final_attempt["exit_code"])
    final_exit_code = process_exit_code if process_exit_code != 0 else (0 if final_terminal_cause == "none" else 1)
    if final_exit_code == 0 and len(attempt_records) == 1:
        status = "passed"
    elif final_exit_code == 0:
        status = "flaky_pass"
    else:
        status = str(attempt_records[-1]["completion_state"])
    return (
        {
            "profile": profile,
            "command": _normalized_command(project_root, command),
            "exit_code": final_exit_code,
            "status": status,
            "attempts": len(attempt_records),
            "max_attempts": max_attempts,
            "duration_ms": sum(int(record["duration_ms"]) for record in attempt_records),
            "terminal_cause": final_terminal_cause,
            "failure_domain": str(final_attempt["failure_domain"]),
            "failed_check_ids": (
                list(failure_fact.get("failed_check_ids", []))
                if failure_fact is not None
                else []
            ),
            "structured_report_ref": str(final_attempt["structured_report_ref"]),
            "trace_refs": list(final_attempt["trace_refs"]),
            "screenshot_refs": list(final_attempt["screenshot_refs"]),
            "source_artifact_refs": list(final_attempt["source_artifact_refs"]),
            "attempt_records": attempt_records,
        },
        failure_fact_refs,
    )
~~~

- [ ] **Step 6: Preserve first-failure stop semantics and record preflight failures**

Extend `_write_harness_report` with keyword-only arguments `suite_id`, `selection_mode`, `selected_profiles`, `environment_fingerprint`, `environment_class`, `started_at`, and `failure_fact_refs`. It builds both latest and archived manifests with `build_run_manifest_v2`, reads the compatible family baseline before diffing, and promotes the new family baseline only after a successful run. Then use the same orchestration path for executable attempts and missing-environment preflight results:

~~~python
run_started_at = datetime.now(timezone.utc)
run_dir = verification_dir(project_root) / "runs" / run_id
environment_fingerprint, environment_class = _environment_fingerprint(
    project_root,
    python_exe,
    godot_exe,
)
stop_exit_code = 0
failure_fact_refs: list[str] = []
for profile in profiles:
    profile_config = registry.profiles[profile]
    command = _profile_command(profile, project_root, python_exe, godot_exe, registry.profiles)
    preflight_error = (
        "Godot executable not found. Set GODOT_EXE or pass --godot-exe."
        if profile_config.get("requires_godot") and godot_exe is None
        else None
    )
    profile_result, profile_failure_refs = _execute_profile(
        project_root=project_root,
        run_dir=run_dir,
        run_id=run_id,
        profile=profile,
        profile_config=profile_config,
        command=command,
        preflight_error=preflight_error,
    )
    profile_results.append(profile_result)
    failure_fact_refs.extend(profile_failure_refs)
    if profile_result["status"] not in {"passed", "flaky_pass"}:
        stop_exit_code = int(profile_result["exit_code"])
        break

report_paths = _write_harness_report(
    project_root,
    profile_results,
    overall_passed=stop_exit_code == 0,
    run_id=run_id,
    profile_configs=registry.profiles,
    suite_id=suite_id,
    selection_mode=selection_mode,
    selected_profiles=profiles,
    environment_fingerprint=environment_fingerprint,
    environment_class=environment_class,
    started_at=run_started_at.isoformat(),
    failure_fact_refs=failure_fact_refs,
)
print(f"harness_report_json={report_paths['json']}")
print(f"harness_report_md={report_paths['markdown']}")
print(f"harness_run_dir={report_paths['run_dir']}")
return stop_exit_code
~~~

`_write_harness_report` must always write the latest and archived JSON/Markdown reports, run manifest, compatible diff, and referenced FailureFacts before returning.

Use this exact manifest/diff section inside `_write_harness_report` after the report files are written:

~~~python
finished_at = datetime.now(timezone.utc)
harness_change_result = collect_harness_changes(project_root)
harness_changes = list(harness_change_result["harness_changes"])
git_commit, git_dirty = _git_identity(project_root)
manifest = build_run_manifest_v2(
    run_id=run_id,
    suite_id=suite_id,
    selection_mode=selection_mode,
    selected_profiles=selected_profiles,
    environment_fingerprint=environment_fingerprint,
    environment_class=environment_class,
    started_at=started_at,
    finished_at=finished_at.isoformat(),
    duration_ms=int(
        (finished_at - datetime.fromisoformat(started_at)).total_seconds() * 1000
    ),
    overall_passed=overall_passed,
    profile_results=profiles,
    artifacts={
        "latest_report_json": repo_relative(project_root, json_path),
        "latest_report_markdown": repo_relative(project_root, markdown_path),
        "archived_report_json": repo_relative(project_root, archived_json_path),
        "archived_report_markdown": repo_relative(project_root, archived_markdown_path),
    },
    git_commit=git_commit,
    git_dirty=git_dirty,
    active_harness_change_refs=[str(change["path"]) for change in harness_changes],
    harness_changes=harness_changes,
    harness_change_errors=list(harness_change_result["harness_change_errors"]),
    failure_fact_refs=failure_fact_refs,
)
previous_baseline = read_compatible_baseline(project_root, manifest)
diff = build_run_diff(previous_baseline, manifest)
atomic_write_json(manifest_path, manifest)
atomic_write_json(archived_manifest_path, manifest)
atomic_write_json(diff_path, diff)
atomic_write_json(archived_diff_path, diff)
promote_successful_baseline(project_root, manifest)
~~~

- [ ] **Step 7: Run the runner tests**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_harness_runner.py scripts/verification/tests/test_harness_execution.py
~~~

Expected: all tests pass, including existing missing-Godot coverage.

- [ ] **Step 8: Commit**

~~~powershell
git add scripts/verification/harness.py scripts/verification/tests/test_harness_runner.py
git commit -m "feat: integrate attributable harness runs"
~~~

### Task 6: Split Hosted CI From Local Full Runtime Proof

**Files:**
- Modify: .github/workflows/harness.yml
- Modify: .harness/ci/release-gate.json
- Modify: .harness/ci/local-ci-gate.ps1
- Modify: .harness/rules/release-gate-rules.json
- Modify: scripts/verification/check_release_gate.py:26-84
- Modify: scripts/verification/tests/test_formal_profile_checks.py:40-50

**Interfaces:**
- Consumes: SuiteRegistry and ci-non-godot manifest.
- Produces: release-gate results ci_runs_non_godot_suite, ci_suite_excludes_godot, ci_suite_excludes_live_credentials, local_full_gate_preserved.

- [ ] **Step 1: Rewrite release-gate expectations first**

Change the formal test to assert:

~~~python
assert statuses["release_gate_metadata_exists"] == "proved"
assert statuses["ci_harness_workflow_exists"] == "proved"
assert statuses["ci_runs_non_godot_suite"] == "proved"
assert statuses["ci_suite_excludes_godot"] == "proved"
assert statuses["ci_suite_excludes_live_credentials"] == "proved"
assert statuses["local_ci_gate_exists"] == "proved"
assert statuses["local_full_gate_preserved"] == "proved"
~~~

- [ ] **Step 2: Run the formal test and verify failure**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_formal_profile_checks.py::test_release_gate_profile_proves_ci_entrypoint
~~~

Expected: FAIL because the old rule IDs and workflow still require all and mainline.

- [ ] **Step 3: Update hosted workflow**

Use this job body:

~~~yaml
jobs:
  harness:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - name: Run non-Godot harness
        run: python scripts/verification/harness.py --suite ci-non-godot
      - name: Upload harness evidence
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: harness-evidence
          path: |
            .harness/verification/harness-run-report.json
            .harness/verification/harness-run-manifest.json
            .harness/verification/harness-run-diff.json
            .harness/verification/run-index.json
            .harness/verification/runs/*/run-manifest.json
            .harness/verification/runs/*/harness-run-diff.json
            .harness/verification/runs/*/failures/*.json
            .harness/verification/runs/*/attempts/*.stdout.log
            .harness/verification/runs/*/attempts/*.stderr.log
~~~

Remove the GODOT_EXE environment variable and the mainline-unified-runtime command.

- [ ] **Step 4: Preserve local full verification without duplication**

Keep:

~~~powershell
python -m pytest -q scripts\verification\tests
python -m compileall -q scripts\verification
python scripts\verification\harness.py --profile all
~~~

Remove the second explicit mainline-unified-runtime invocation because local-full already contains it.

- [ ] **Step 5: Make release-gate resolve suite capabilities**

Load the profile and suite registries in check_release_gate.py. Prove that every resolved ci-non-godot profile has requires_godot=false and requires_live_credentials=false. Validate the workflow command and local full command.

Use:

~~~python
profile_registry = load_profile_registry(project_root)
suite_registry = load_suite_registry(project_root)
ci_profiles = resolve_suite_profiles("ci-non-godot", profile_registry, suite_registry)
ci_configs = [profile_registry.profiles[name] for name in ci_profiles]

results = [
    _result(
        "release_gate_metadata_exists",
        "Release metadata separates hosted and local gates",
        metadata.get("schema_version") == 2
        and metadata.get("required_ci_suite") == "ci-non-godot"
        and metadata.get("required_local_profile") == "all",
        [".harness/ci/release-gate.json"],
    ),
    _result(
        "ci_harness_workflow_exists",
        "CI harness workflow exists",
        workflow_path.exists(),
        [".github/workflows/harness.yml"],
    ),
    _result(
        "ci_runs_non_godot_suite",
        "CI invokes the non-Godot suite",
        "python scripts/verification/harness.py --suite ci-non-godot" in workflow_text,
        [".github/workflows/harness.yml"],
    ),
    _result(
        "ci_suite_excludes_godot",
        "CI suite contains no Godot profile",
        bool(ci_profiles) and all(not bool(config.get("requires_godot", False)) for config in ci_configs),
        [".harness/suites/ci-non-godot.json", ".harness/profiles/"],
    ),
    _result(
        "ci_suite_excludes_live_credentials",
        "CI suite contains no live-credential profile",
        bool(ci_profiles)
        and all(not bool(config.get("requires_live_credentials", False)) for config in ci_configs),
        [".harness/suites/ci-non-godot.json", ".harness/profiles/"],
    ),
    _result(
        "local_ci_gate_exists",
        "Local CI gate exists",
        local_ci_gate_path.exists(),
        [".harness/ci/local-ci-gate.ps1"],
    ),
    _result(
        "local_full_gate_preserved",
        "Local CI gate invokes the full local profile",
        "python scripts\\verification\\harness.py --profile all" in local_ci_gate_text,
        [".harness/ci/local-ci-gate.ps1"],
    ),
]
~~~

- [ ] **Step 6: Update metadata and rule IDs**

Set release-gate.json:

~~~json
{
  "schema_version": 2,
  "name": "release-gate",
  "required_ci_suite": "ci-non-godot",
  "required_local_profile": "all",
  "ci_workflow": ".github/workflows/harness.yml",
  "local_ci_gate": ".harness/ci/local-ci-gate.ps1"
}
~~~

Keep the existing artifact lists after these fields.

- [ ] **Step 7: Run the P0 checkpoint**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_harness_schema.py scripts/verification/tests/test_harness_suites.py scripts/verification/tests/test_harness_execution.py scripts/verification/tests/test_harness_runner.py scripts/verification/tests/test_harness_registry.py scripts/verification/tests/test_formal_profile_checks.py
python -m compileall -q scripts/verification
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile release-gate
python scripts/verification/harness.py --suite ci-non-godot
python scripts/verification/harness.py --profile all
~~~

Expected: all commands exit 0. The hosted suite manifest contains no Godot or credential-backed profile. The local full run includes Godot-backed profiles and writes schema v2 evidence.

- [ ] **Step 8: Commit**

~~~powershell
git add .github/workflows/harness.yml .harness/ci .harness/rules/release-gate-rules.json scripts/verification/check_release_gate.py scripts/verification/tests/test_formal_profile_checks.py
git commit -m "ci: separate hosted and local harness gates"
~~~

Do not start P1 until the complete P0 checkpoint passes.

---

## P1 — Feedback Efficiency

### Task 7: Add Advisory Change-Impact Selection

**Files:**
- Create: scripts/verification/harness_selection.py
- Create: scripts/verification/suggest_harness_profiles.py
- Create: scripts/verification/tests/test_harness_selection.py
- Modify: .harness/profiles/*.json

**Interfaces:**
- Consumes: changed paths, ProfileRegistry watch_paths, depends_on_profiles, and local-full suite.
- Produces: select_profiles(changed_paths, registry, local_full_profiles), git_changed_paths(project_root, base_ref), selection report JSON and Markdown.

- [ ] **Step 1: Write failing selection tests**

Create scripts/verification/tests/test_harness_selection.py:

~~~python
from __future__ import annotations

from types import SimpleNamespace

from harness_selection import select_profiles


def test_selector_adds_transitive_dependencies_and_reasons() -> None:
    registry = SimpleNamespace(
        profile_order=["backend-contract", "phase0"],
        profiles={
            "backend-contract": {
                "watch_paths": ["backend/app/models/**"],
                "depends_on_profiles": [],
            },
            "phase0": {
                "watch_paths": ["scripts/phase0/**"],
                "depends_on_profiles": ["backend-contract"],
            },
        },
    )

    report = select_profiles(["scripts/phase0/MainDemoController.gd"], registry, ["backend-contract", "phase0"])

    assert report["recommended_profiles"] == ["backend-contract", "phase0"]
    assert report["reasons"]["phase0"] == ["watch_path:scripts/phase0/**"]
    assert report["reasons"]["backend-contract"] == ["dependency_of:phase0"]
    assert report["broad_completion_verified"] is False


def test_unknown_path_expands_to_local_full() -> None:
    registry = SimpleNamespace(
        profile_order=["docs", "phase0"],
        profiles={
            "docs": {"watch_paths": ["docs/**"], "depends_on_profiles": []},
            "phase0": {"watch_paths": ["scripts/phase0/**"], "depends_on_profiles": []},
        },
    )

    report = select_profiles(["unmapped/new.file"], registry, ["docs", "phase0"])

    assert report["recommended_profiles"] == ["docs", "phase0"]
    assert report["unknown_paths"] == ["unmapped/new.file"]
    assert report["selection_mode"] == "conservative-local-full"
~~~

- [ ] **Step 2: Run tests and verify the module is missing**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_harness_selection.py
~~~

Expected: collection fails with ModuleNotFoundError for harness_selection.

- [ ] **Step 3: Implement selection**

Use:

~~~python
from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path


def select_profiles(
    changed_paths: list[str],
    registry: object,
    local_full_profiles: list[str],
) -> dict[str, object]:
    normalized = [path.replace("\\", "/") for path in changed_paths]
    selected: set[str] = set()
    reasons: dict[str, list[str]] = {}
    matched_paths: set[str] = set()
    profiles = getattr(registry, "profiles")
    order = list(getattr(registry, "profile_order"))

    for profile in order:
        config = profiles[profile]
        for pattern in config.get("watch_paths", []):
            matching = [path for path in normalized if fnmatch.fnmatch(path, str(pattern))]
            if matching:
                selected.add(profile)
                reasons.setdefault(profile, []).append(f"watch_path:{pattern}")
                matched_paths.update(matching)

    queue = list(selected)
    while queue:
        profile = queue.pop(0)
        for dependency in profiles[profile].get("depends_on_profiles", []):
            name = str(dependency)
            if name not in selected:
                selected.add(name)
                queue.append(name)
            reason = f"dependency_of:{profile}"
            if reason not in reasons.setdefault(name, []):
                reasons[name].append(reason)

    unknown_paths = [path for path in normalized if path not in matched_paths]
    if unknown_paths:
        selected = set(local_full_profiles)
        selection_mode = "conservative-local-full"
        for profile in local_full_profiles:
            reasons.setdefault(profile, []).append("conservative_unknown_path")
    else:
        selection_mode = "advisory"
    selected_profiles = [profile for profile in order if profile in selected]
    return {
        "schema_version": 1,
        "selection_mode": selection_mode,
        "changed_paths": normalized,
        "recommended_profiles": selected_profiles,
        "reasons": reasons,
        "unknown_paths": unknown_paths,
        "broad_completion_verified": False,
        "unverified_scope": ["local-full"],
    }


def git_changed_paths(project_root: Path, base_ref: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or f"git diff failed for {base_ref}")
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]
~~~

- [ ] **Step 4: Add exact watch-path metadata**

Use these mappings:

| Profile | watch_paths |
| --- | --- |
| docs | AGENTS.md; docs/**; openspec/** |
| boundaries | backend/**; scripts/**; scenes/**; project.godot |
| drift | .gitignore; .harness/**; scripts/verification/** |
| backend-contract | backend/app/models/**; backend/app/main.py; backend/tests/** |
| godot-project | project.godot; scenes/**; scripts/**/*.gd; assets/** |
| character-agent-execution | backend/app/character_agent/**; backend/tests/test_character_agent*; scripts/verification/CharacterAgentExecutionProbe.gd |
| release-gate | .github/workflows/harness.yml; .harness/ci/**; .harness/suites/** |
| harness-lifecycle | .harness/**; docs/harness*.md |
| change-lifecycle | AGENTS.md; docs/ai-engineering-workflow.md; docs/superpowers/**; openspec/** |
| harness-reference | .harness/references/**; .harness/templates/**; docs/harness*.md |
| harness-evolution | .harness/evolution/**; scripts/verification/evolution.py; scripts/verification/analyze_harness_evolution.py |
| phase0 | backend/**; scenes/phase0/**; scripts/phase0/**; scripts/autoload/** |
| phase1-slice | backend/app/world_runtime/**; backend/app/services/**; scripts/verification/Phase1SliceRuntimeProbe.gd |
| l1-world-fact-runtime | backend/app/world_runtime/**; backend/tests/test_l1*; scripts/verification/verify_l1_world_fact_runtime.py |
| mainline-unified-runtime | backend/**; scripts/verification/verify_mainline_unified_runtime.py; scripts/verification/*Probe.gd |
| model-provider-readiness | backend/app/services/*provider*; backend/app/config.py; backend/tests/test_*provider* |
| godot-sampling-production-grade-providers | scripts/**; scenes/**; backend/app/services/*provider* |
| embodied-skeletal-debug-replay | scripts/character/**; assets/**; backend/app/services/*skeletal*; scripts/verification/verify_embodied_skeletal_debug_replay_pipeline.py |
| vla-provider-backend | backend/app/**/*vla*; backend/tests/test_vla* |
| actor-scene-knowledge-lifecycle | backend/app/**/*scene_knowledge*; backend/tests/test_actor_scene_knowledge* |
| siming-global-situation-layer | backend/app/**/*siming_global*; backend/tests/test_siming_global* |
| interaction-orchestration-service | backend/app/**/*interaction_orchestration*; backend/tests/test_interaction_orchestration* |
| esm-physical-channel-world-actuation | backend/app/**/*physical*; backend/app/**/*esm*; scripts/**; scenes/** |
| non-runtime-production-pipeline | tools/production/**; backend/app/**/*production*; backend/tests/test_non_runtime_production* |
| perception-input-alignment | backend/app/**/*perception*; backend/app/**/*vla*; backend/tests/test_perception* |
| siming-heavenly-graph-foundation | backend/app/**/*siming_heavenly*; backend/tests/test_siming_heavenly* |
| siming-backend-chain | backend/app/**/*siming*; backend/tests/test_siming* |
| script-evolution-proof | scripts/verification/verify_script_evolution.py; .harness/fixtures/script-evolution/**; backend/app/**/*siming* |

Use these dependencies:

- phase0 depends on backend-contract and godot-project.
- character-agent-execution depends on backend-contract and godot-project.
- phase1-slice depends on backend-contract and godot-project.
- l1-world-fact-runtime depends on backend-contract and godot-project.
- mainline-unified-runtime depends on backend-contract, godot-project, character-agent-execution, and phase1-slice.
- every Harness-owned profile depends on docs when .harness manifests or Harness docs change.

- [ ] **Step 5: Add the advisory CLI**

Create scripts/verification/suggest_harness_profiles.py:

~~~python
from __future__ import annotations

import argparse
from pathlib import Path

from common import repo_root, verification_dir
from harness_schema import atomic_write_json
from harness_selection import git_changed_paths, select_profiles
from registry import load_profile_registry, load_suite_registry, resolve_suite_profiles


def _write_markdown(path: Path, report: dict[str, object]) -> None:
    reasons = report.get("reasons", {})
    lines = [
        "# Harness Selection Report",
        "",
        f"- Selection mode: `{report['selection_mode']}`",
        "- Broad completion verified: `false`",
        "- Unverified broad scope: `local-full`",
        "",
        "## Recommended Profiles",
        "",
    ]
    for profile in report.get("recommended_profiles", []):
        profile_reasons = reasons.get(profile, []) if isinstance(reasons, dict) else []
        lines.append(f"- `{profile}`: {', '.join(str(value) for value in profile_reasons)}")
    lines.extend(["", "## Unknown Paths", ""])
    lines.extend(f"- `{value}`" for value in report.get("unknown_paths", []))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="HEAD~1")
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--project-root", default=None)
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else repo_root()
    try:
        changed_paths = list(args.path) or git_changed_paths(project_root, args.base)
    except ValueError as exc:
        print(f"harness_selection_error={exc}")
        return 1
    registry = load_profile_registry(project_root)
    suites = load_suite_registry(project_root)
    local_full = resolve_suite_profiles("local-full", registry, suites)
    report = select_profiles(changed_paths, registry, local_full)
    output_dir = verification_dir(project_root)
    json_path = output_dir / "harness-selection-report.json"
    markdown_path = output_dir / "harness-selection-report.md"
    atomic_write_json(json_path, report)
    _write_markdown(markdown_path, report)
    print(f"harness_selection_report_json={json_path}")
    print(f"harness_selection_report_md={markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
~~~

- [ ] **Step 6: Run selection tests**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_harness_selection.py scripts/verification/tests/test_harness_registry.py
python scripts/verification/suggest_harness_profiles.py --path scripts/phase0/MainDemoController.gd
~~~

Expected: tests pass; the CLI recommends phase0 plus its dependencies and reports broad_completion_verified=false.

- [ ] **Step 7: Commit**

~~~powershell
git add .harness/profiles scripts/verification/harness_selection.py scripts/verification/suggest_harness_profiles.py scripts/verification/tests/test_harness_selection.py scripts/verification/tests/test_harness_registry.py
git commit -m "feat: suggest change-aware harness profiles"
~~~

### Task 8: Add Run Index, Pins, And Tiered Retention

**Files:**
- Create: scripts/verification/harness_history.py
- Create: scripts/verification/tests/test_harness_history.py
- Create: .harness/pins/.gitkeep
- Create: .harness/templates/evidence-pin-template.json
- Modify: .harness/retention-policy.json
- Modify: scripts/verification/harness.py
- Modify: scripts/verification/check_harness_lifecycle.py:31-140
- Modify: .harness/rules/harness-lifecycle-rules.json

**Interfaces:**
- Consumes: run directories, baseline-family files, candidate manifests, pin manifests, retention policy.
- Produces: refresh_run_index(project_root), query_run_index(project_root, ...), collect_pinned_run_ids(project_root), apply_retention(project_root), .harness/verification/run-index.json.

- [ ] **Step 1: Write failing history tests**

Create scripts/verification/tests/test_harness_history.py with:

~~~python
from __future__ import annotations

import json
from pathlib import Path

from harness_history import apply_retention, query_run_index, refresh_run_index


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _prepare_history_fixture(tmp_path: Path) -> Path:
    _write_json(
        tmp_path / ".harness/retention-policy.json",
        {
            "schema_version": 2,
            "max_full_runs": 2,
            "preserve_latest_successful_baselines": True,
            "archive_root": ".harness/verification/runs/",
            "baseline_root": ".harness/verification/baselines/",
            "pin_root": ".harness/pins/",
            "compact_preserve_globs": [
                "run-manifest.json",
                "harness-run-diff.json",
                "*-failure-digest.json",
                "compact-manifest.json",
            ],
            "compact_remove_globs": ["*.log", "harness-run-report.json", "harness-run-report.md"],
        },
    )
    runs = tmp_path / ".harness/verification/runs"
    for index in range(1, 6):
        run_id = f"run-{index}"
        _write_json(
            runs / run_id / "run-manifest.json",
            {
                "schema_version": 2,
                "run_id": run_id,
                "suite_id": "local-full",
                "environment_class": "local-with-godot",
                "overall_harness_passed": True,
                "failure_fact_refs": [],
            },
        )
        (runs / run_id / "attempt.log").write_text("full log", encoding="utf-8")
    _write_json(
        tmp_path / ".harness/pins/pin-release.json",
        {"schema_version": 1, "id": "pin-release", "run_ids": ["run-1"], "reason": "release"},
    )
    _write_json(
        tmp_path / ".harness/verification/baselines/family.json",
        {
            "schema_version": 2,
            "run_id": "run-2",
            "suite_id": "local-full",
            "environment_class": "local-with-godot",
            "overall_harness_passed": True,
        },
    )
    return runs


def test_retention_preserves_recent_pinned_and_baseline_runs(tmp_path: Path) -> None:
    runs = _prepare_history_fixture(tmp_path)

    result = apply_retention(tmp_path)

    assert result["compacted_run_ids"] == ["run-3"]
    assert (runs / "run-1" / "attempt.log").exists()
    assert (runs / "run-2" / "attempt.log").exists()
    assert not (runs / "run-3" / "attempt.log").exists()
    assert (runs / "run-3" / "compact-manifest.json").exists()
    assert (runs / "run-4" / "attempt.log").exists()
    assert (runs / "run-5" / "attempt.log").exists()


def test_retention_is_idempotent(tmp_path: Path) -> None:
    _prepare_history_fixture(tmp_path)

    first = apply_retention(tmp_path)
    second = apply_retention(tmp_path)

    assert first["errors"] == []
    assert second["errors"] == []
    assert second["compacted_run_ids"] == []


def test_recent_pinned_run_does_not_consume_unpinned_full_run_budget(tmp_path: Path) -> None:
    runs = _prepare_history_fixture(tmp_path)
    _write_json(
        tmp_path / ".harness/pins/pin-recent.json",
        {"schema_version": 1, "id": "pin-recent", "run_ids": ["run-5"], "reason": "QA"},
    )

    result = apply_retention(tmp_path)

    assert result["errors"] == []
    assert result["compacted_run_ids"] == []
    assert (runs / "run-3" / "attempt.log").exists()
    assert (runs / "run-4" / "attempt.log").exists()
    assert (runs / "run-5" / "attempt.log").exists()


def test_invalid_explicit_pin_aborts_compaction(tmp_path: Path) -> None:
    runs = _prepare_history_fixture(tmp_path)
    _write_json(
        tmp_path / ".harness/pins/pin-missing.json",
        {"schema_version": 1, "id": "pin-missing", "run_ids": ["run-404"], "reason": "release"},
    )

    result = apply_retention(tmp_path)

    assert result["compacted_run_ids"] == []
    assert result["errors"] == [".harness/pins/pin-missing.json: unknown run_id run-404"]
    assert (runs / "run-3" / "attempt.log").exists()


def test_run_index_queries_by_baseline_family(tmp_path: Path) -> None:
    _prepare_history_fixture(tmp_path)
    refresh_run_index(tmp_path)

    entries = query_run_index(tmp_path, suite_id="local-full")

    assert [entry["run_id"] for entry in entries] == [
        "run-1", "run-2", "run-3", "run-4", "run-5"
    ]
    assert all(isinstance(entry["baseline_family_id"], str) for entry in entries)
~~~

- [ ] **Step 2: Run tests and verify missing module**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_harness_history.py
~~~

Expected: collection fails with ModuleNotFoundError for harness_history.

- [ ] **Step 3: Define retention policy v2**

Use:

~~~json
{
  "schema_version": 2,
  "max_full_runs": 25,
  "preserve_latest_successful_baselines": true,
  "generated_evidence_root": ".harness/verification/",
  "archive_root": ".harness/verification/runs/",
  "baseline_root": ".harness/verification/baselines/",
  "pin_root": ".harness/pins/",
  "compact_preserve_globs": [
    "run-manifest.json",
    "harness-run-diff.json",
    "*-failure-digest.json",
    "compact-manifest.json"
  ],
  "compact_remove_globs": [
    "*.log",
    "*.png",
    "*.jpg",
    "*.ndjson",
    "harness-run-report.json",
    "harness-run-report.md"
  ]
}
~~~

- [ ] **Step 4: Implement safe two-phase compaction**

Implement the compactor around these functions:

~~~python
from __future__ import annotations

import fnmatch
import json
from pathlib import Path

from harness_schema import atomic_write_json, baseline_family_id


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _extract_run_ids(value: object, known_run_ids: set[str]) -> set[str]:
    found: set[str] = set()
    if isinstance(value, str):
        found.update(run_id for run_id in known_run_ids if run_id in value)
    elif isinstance(value, list):
        for item in value:
            found.update(_extract_run_ids(item, known_run_ids))
    elif isinstance(value, dict):
        for item in value.values():
            found.update(_extract_run_ids(item, known_run_ids))
    return found


def collect_pinned_run_ids(project_root: Path) -> tuple[set[str], list[str]]:
    runs_dir = project_root / ".harness" / "verification" / "runs"
    known = {path.name for path in runs_dir.iterdir() if path.is_dir()} if runs_dir.exists() else set()
    pin_root = project_root / ".harness" / "pins"
    reference_roots = [
        project_root / ".harness" / "evolution" / "candidates",
        project_root / ".harness" / "ci",
    ]
    pinned: set[str] = set()
    errors: list[str] = []
    if pin_root.exists():
        for path in sorted(pin_root.glob("*.json")):
            relative = path.relative_to(project_root).as_posix()
            payload = _read_json(path)
            run_ids = payload.get("run_ids")
            if not isinstance(run_ids, list) or not run_ids or not all(isinstance(value, str) for value in run_ids):
                errors.append(f"{relative}: run_ids must be a non-empty string list")
                continue
            for run_id in run_ids:
                if run_id not in known:
                    errors.append(f"{relative}: unknown run_id {run_id}")
                else:
                    pinned.add(run_id)
    for root in reference_roots:
        if not root.exists():
            continue
        for path in root.rglob("*.json"):
            pinned.update(_extract_run_ids(_read_json(path), known))
    return pinned, errors


def _baseline_run_ids(project_root: Path) -> set[str]:
    baseline_dir = project_root / ".harness" / "verification" / "baselines"
    if not baseline_dir.exists():
        return set()
    return {
        str(payload["run_id"])
        for payload in (_read_json(path) for path in baseline_dir.glob("*.json"))
        if isinstance(payload.get("run_id"), str)
    }


def _matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def apply_retention(project_root: Path) -> dict[str, object]:
    policy = _read_json(project_root / ".harness" / "retention-policy.json")
    runs_dir = project_root / ".harness" / "verification" / "runs"
    if not runs_dir.exists():
        return {"compacted_run_ids": [], "errors": []}
    run_dirs = sorted((path for path in runs_dir.iterdir() if path.is_dir()), reverse=True)
    max_full_runs = int(policy.get("max_full_runs", 25))
    pinned_run_ids, pin_errors = collect_pinned_run_ids(project_root)
    if pin_errors:
        return {"compacted_run_ids": [], "errors": pin_errors}
    protected_run_ids = pinned_run_ids | _baseline_run_ids(project_root)
    unprotected_run_dirs = [path for path in run_dirs if path.name not in protected_run_ids]
    keep_full = {path.name for path in unprotected_run_dirs[:max_full_runs]}
    keep_full.update(protected_run_ids)
    preserve_globs = [str(value) for value in policy.get("compact_preserve_globs", [])]
    remove_globs = [str(value) for value in policy.get("compact_remove_globs", [])]
    compacted: list[str] = []
    errors: list[str] = []

    for run_dir in reversed(run_dirs):
        if run_dir.name in keep_full:
            continue
        try:
            manifest = _read_json(run_dir / "run-manifest.json")
            compact_payload = {
                "schema_version": 1,
                "run_id": run_dir.name,
                "source_manifest": "run-manifest.json",
                "overall_harness_passed": manifest.get("overall_harness_passed"),
                "suite_id": manifest.get("suite_id"),
                "environment_class": manifest.get("environment_class"),
                "duration_ms": manifest.get("duration_ms"),
                "failure_fact_refs": manifest.get("failure_fact_refs", []),
                "storage_tier": "compact",
            }
            compact_path = run_dir / "compact-manifest.json"
            newly_compacted = not compact_path.exists()
            if newly_compacted:
                atomic_write_json(compact_path, compact_payload)
            if _read_json(compact_path).get("run_id") != run_dir.name:
                raise ValueError("compact manifest validation failed")
            for path in sorted(run_dir.rglob("*")):
                if not path.is_file() or path == compact_path:
                    continue
                resolved = path.resolve()
                if not resolved.is_relative_to(run_dir.resolve()):
                    raise ValueError(f"unsafe retention path: {path}")
                relative = path.relative_to(run_dir).as_posix()
                if _matches(relative, preserve_globs):
                    continue
                if _matches(relative, remove_globs):
                    path.unlink()
            if newly_compacted:
                compacted.append(run_dir.name)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{run_dir.name}:{exc}")
    return {"compacted_run_ids": compacted, "errors": errors}
~~~

Use this pin template:

~~~json
{
  "schema_version": 1,
  "id": "pin-example",
  "run_ids": ["run-20260714-000000-000000"],
  "reason": "Release, QA, candidate, or explicit human evidence pin"
}
~~~

- [ ] **Step 5: Build the run index**

Add:

~~~python
def refresh_run_index(project_root: Path) -> dict[str, object]:
    runs_dir = project_root / ".harness" / "verification" / "runs"
    entries: list[dict[str, object]] = []
    if runs_dir.exists():
        for run_dir in sorted(path for path in runs_dir.iterdir() if path.is_dir()):
            manifest = _read_json(run_dir / "run-manifest.json")
            if not manifest:
                continue
            entries.append(
                {
                    "run_id": str(manifest["run_id"]),
                    "schema_version": int(manifest.get("schema_version", 0)),
                    "suite_id": str(manifest.get("suite_id", "legacy_unknown")),
                    "environment_class": str(manifest.get("environment_class", "legacy_unknown")),
                    "overall_harness_passed": bool(manifest.get("overall_harness_passed", False)),
                    "duration_ms": manifest.get("duration_ms"),
                    "failure_fact_refs": list(manifest.get("failure_fact_refs", [])),
                    "baseline_family_id": baseline_family_id(manifest),
                    "storage_tier": (
                        "compact" if (run_dir / "compact-manifest.json").exists() else "full"
                    ),
                }
            )
    payload = {"schema_version": 1, "runs": entries}
    atomic_write_json(
        project_root / ".harness" / "verification" / "run-index.json",
        payload,
    )
    return payload


def query_run_index(
    project_root: Path,
    *,
    suite_id: str | None = None,
    baseline_family: str | None = None,
    overall_passed: bool | None = None,
) -> list[dict[str, object]]:
    payload = _read_json(project_root / ".harness" / "verification" / "run-index.json")
    entries = [entry for entry in payload.get("runs", []) if isinstance(entry, dict)]
    return [
        entry
        for entry in entries
        if (suite_id is None or entry.get("suite_id") == suite_id)
        and (baseline_family is None or entry.get("baseline_family_id") == baseline_family)
        and (overall_passed is None or entry.get("overall_harness_passed") is overall_passed)
    ]
~~~

- [ ] **Step 6: Invoke indexing and retention after finalized reports**

After harness.py finishes writing the archived manifest and diff:

~~~python
retention_result = apply_retention(project_root)
refresh_run_index(project_root)
if retention_result["errors"]:
    print(f"harness_retention_errors={len(retention_result['errors'])}")
~~~

Retention errors remain visible but do not replace the profile verdict.

- [ ] **Step 7: Extend lifecycle checks**

Add these exact results to check_harness_lifecycle.py and mirror their IDs in harness-lifecycle-rules.json and the formal-profile assertion list:

~~~python
_result(
    "lifecycle_run_index_exists",
    "Harness run index exists",
    (project_root / ".harness/verification/run-index.json").exists(),
    [".harness/verification/run-index.json"],
),
_result(
    "lifecycle_evidence_pin_surface_exists",
    "Evidence pin directory and template exist",
    (project_root / ".harness/pins").is_dir()
    and (project_root / ".harness/templates/evidence-pin-template.json").exists(),
    [".harness/pins/", ".harness/templates/evidence-pin-template.json"],
),
_result(
    "lifecycle_retention_is_operational",
    "Retention policy is executable and pin-safe",
    retention_policy.get("schema_version") == 2
    and retention_policy.get("max_full_runs") == 25
    and callable(apply_retention),
    [".harness/retention-policy.json", "scripts/verification/harness_history.py"],
),
~~~

- [ ] **Step 8: Run history and lifecycle tests**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_harness_history.py scripts/verification/tests/test_formal_profile_checks.py
python scripts/verification/harness.py --profile harness-lifecycle
~~~

Expected: tests and profile pass; repeated retention application changes nothing after the first pass.

- [ ] **Step 9: Commit**

~~~powershell
git add .harness/retention-policy.json .harness/pins .harness/templates/evidence-pin-template.json .harness/rules/harness-lifecycle-rules.json scripts/verification/harness_history.py scripts/verification/harness.py scripts/verification/check_harness_lifecycle.py scripts/verification/tests/test_harness_history.py scripts/verification/tests/test_formal_profile_checks.py
git commit -m "feat: enforce tiered harness evidence retention"
~~~

### Task 9: Document And Verify The P1 Contract

**Files:**
- Modify: docs/harness.md
- Modify: docs/harness-architecture.md
- Modify: docs/harness-reliability.md
- Modify: docs/ai-engineering-workflow.md
- Modify: docs/INDEX.md
- Modify: .harness/features.json
- Modify: scripts/verification/tests/test_docs_checks.py

**Interfaces:**
- Consumes: implemented P0 and P1 command surfaces.
- Produces: discoverable docs and feature-ledger evidence.

- [ ] **Step 1: Add docs assertions first**

Add:

~~~python
def test_harness_docs_cover_suite_selection_and_retention() -> None:
    harness_doc = (repo_root() / "docs" / "harness.md").read_text(encoding="utf-8")
    required = [
        "--suite ci-non-godot",
        "harness-selection-report.json",
        "broad_completion_verified",
        "run-index.json",
        ".harness/pins/",
    ]

    assert [value for value in required if value not in harness_doc] == []
~~~

- [ ] **Step 2: Run the docs test and verify failure**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_docs_checks.py
~~~

Expected: FAIL because the P1 command and evidence surfaces are undocumented.

- [ ] **Step 3: Update documentation**

Document:

- local-full versus ci-non-godot
- advisory selection and its non-authoritative status
- schema v2 run, attempt, failure-fact, and baseline-family artifacts
- run index, compact history, and pins
- retry_on and flaky_pass semantics
- exact commands for profile, suite, suggestion, and local broad completion

Add feature-ledger entries:

- attributable-core-harness
- suite-aware-ci
- advisory-impact-selection
- tiered-evidence-retention

- [ ] **Step 4: Run the P1 checkpoint**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests
python -m compileall -q scripts/verification
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile harness-lifecycle
python scripts/verification/harness.py --profile release-gate
python scripts/verification/suggest_harness_profiles.py --path scripts/verification/harness.py
python scripts/verification/harness.py --suite ci-non-godot
python scripts/verification/harness.py --profile all
~~~

Expected: all commands exit 0; the suggestion report explicitly leaves local-full unverified; full local proof still passes.

- [ ] **Step 5: Commit**

~~~powershell
git add docs .harness/features.json scripts/verification/tests/test_docs_checks.py
git commit -m "docs: document attributable harness feedback"
~~~

Do not start P2 until the complete P1 checkpoint passes.

---

## P2 — Governed Agent Harness Evolution

### Task 10: Add Context Packs And Root-Cause Hypotheses

**Files:**
- Create: scripts/verification/agent_harness.py
- Create: scripts/verification/tests/test_agent_harness.py
- Create: .harness/agent/config.json
- Create: .harness/templates/root-cause-hypothesis-template.json
- Modify: scripts/verification/analyze_harness_evolution.py:34-71

**Interfaces:**
- Consumes: run-index.json, FailureFact files, Agent Harness config.
- Produces: build_context_pack(project_root, failure_fact_refs), build_observability_summary(run_manifests, failure_facts), validate_root_cause_hypothesis(project_root, payload), write_root_cause_hypothesis(project_root, payload).

- [ ] **Step 1: Write failing Agent Harness tests**

Create scripts/verification/tests/test_agent_harness.py:

~~~python
from __future__ import annotations

import json
from pathlib import Path

from agent_harness import build_context_pack, write_root_cause_hypothesis


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_agent_config(tmp_path: Path) -> None:
    _write_json(
        tmp_path / ".harness/agent/config.json",
        {
            "schema_version": 1,
            "max_context_runs": 10,
            "max_log_excerpt_chars": 4000,
            "held_out_suite": "held-out-canary",
            "held_out_risk_categories": ["workflow", "documentation", "lifecycle"],
            "allowed_target_components": [
                "context-policy",
                "workflow-instruction",
                "template",
                "memory-policy",
            ],
        },
    )


def test_context_pack_is_bounded_and_excludes_held_out_details(tmp_path: Path) -> None:
    _write_agent_config(tmp_path)
    _write_json(
        tmp_path / ".harness/verification/runs/run-1/failures/docs-1.json",
        {
            "schema_version": 2,
            "fact_id": "failure:run-1:docs:1",
            "run_id": "run-1",
            "profile": "docs",
            "attempt": 1,
            "terminal_cause": "structured_check_failed",
            "failure_domain": "harness",
            "failed_check_ids": ["docs_index_paths_exist"],
            "evidence_refs": [".harness/verification/docs-report.json"],
        },
    )
    _write_json(
        tmp_path / ".harness/verification/runs/run-1/run-manifest.json",
        {
            "schema_version": 2,
            "run_id": "run-1",
            "suite_id": "explicit:docs",
            "selection_mode": "explicit-profile",
            "environment_fingerprint": {"os": "test", "python_version": "3.13"},
            "profile_results": [{"profile": "docs", "attempts": 1, "duration_ms": 25}],
        },
    )
    _write_json(
        tmp_path / ".harness/verification/docs-report.json",
        {"results": [{"id": "docs_index_paths_exist", "status": "missing"}]},
    )
    _write_json(
        tmp_path / ".harness/verification/run-index.json",
        {
            "schema_version": 1,
            "runs": [
                {"run_id": "run-0", "suite_id": "explicit:docs", "overall_harness_passed": True},
                {"run_id": "run-1", "suite_id": "explicit:docs", "overall_harness_passed": False},
            ],
        },
    )
    _write_json(
        tmp_path / ".harness/verification/hypotheses/prior.json",
        {
            "hypothesis_id": "prior",
            "failure_fact_refs": [".harness/verification/runs/run-1/failures/docs-1.json"],
            "confidence": "low",
        },
    )
    _write_json(
        tmp_path / ".harness/evolution/candidates/prior.json",
        {
            "id": "prior",
            "status": "rejected",
            "source_failure_fact_refs": [".harness/verification/runs/run-1/failures/docs-1.json"],
            "evaluation_brief_ref": ".harness/verification/evaluations/prior.json",
        },
    )
    _write_json(
        tmp_path / ".harness/verification/evaluations/prior.json",
        {"candidate_id": "prior", "overall_candidate_evaluation_passed": False},
    )
    log_path = tmp_path / ".harness/verification/runs/run-1/attempts/docs-1.stdout.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("x" * 5000, encoding="utf-8")

    fact_ref = ".harness/verification/runs/run-1/failures/docs-1.json"
    pack = build_context_pack(tmp_path, [fact_ref])

    assert pack["failure_facts"][0]["fact_id"] == "failure:run-1:docs:1"
    assert pack["held_out"] == {
        "suite_id": "held-out-canary",
        "risk_categories": ["workflow", "documentation", "lifecycle"],
    }
    assert "profile_cases" not in pack["held_out"]
    assert len(pack["log_excerpts"][0]["text"]) <= 4000
    assert pack["run_facts"][0]["run_id"] == "run-1"
    assert pack["preserved_passing_behavior"][0]["run_id"] == "run-0"
    assert pack["observability"]["component"]["terminal_causes"] == {
        "structured_check_failed": 1
    }
    assert pack["prior_hypotheses"][0]["hypothesis_id"] == "prior"
    assert pack["candidate_outcomes"][0]["status"] == "rejected"


def test_hypothesis_requires_evidence_confidence_and_contradictions(tmp_path: Path) -> None:
    _write_agent_config(tmp_path)
    _write_json(
        tmp_path / ".harness/verification/runs/run-1/failures/docs-1.json",
        {
            "schema_version": 2,
            "fact_id": "failure:run-1:docs:1",
            "run_id": "run-1",
            "profile": "docs",
            "attempt": 1,
        },
    )
    _write_json(
        tmp_path / ".harness/verification/runs/run-1/run-manifest.json",
        {"schema_version": 2, "run_id": "run-1"},
    )
    payload = {
        "schema_version": 1,
        "hypothesis_id": "hyp-docs-context",
        "failure_fact_refs": [".harness/verification/runs/run-1/failures/docs-1.json"],
        "target_component": "workflow-instruction",
        "causal_mechanism": "The workflow omits the approved suite command.",
        "confidence": "medium",
        "supporting_evidence_refs": [".harness/verification/runs/run-1/run-manifest.json"],
        "contradicting_evidence_refs": [],
        "expected_fix": "Expose the suite command in Agent-facing instructions.",
        "at_risk_regressions": ["Documentation duplication"],
    }
    fact_path = tmp_path / ".harness/verification/runs/run-1/failures/docs-1.json"
    original_fact = fact_path.read_bytes()
    path = write_root_cause_hypothesis(tmp_path, payload)

    assert path.name == "hyp-docs-context.json"
    assert json.loads(path.read_text(encoding="utf-8"))["confidence"] == "medium"
    assert fact_path.read_bytes() == original_fact
~~~

- [ ] **Step 2: Run tests and verify missing module**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_agent_harness.py
~~~

Expected: collection fails with ModuleNotFoundError for agent_harness.

- [ ] **Step 3: Add Agent Harness config**

Use:

~~~json
{
  "schema_version": 1,
  "max_context_runs": 10,
  "max_log_excerpt_chars": 4000,
  "held_out_suite": "held-out-canary",
  "held_out_risk_categories": [
    "workflow",
    "documentation",
    "lifecycle"
  ],
  "allowed_target_components": [
    "context-policy",
    "workflow-instruction",
    "template",
    "memory-policy"
  ]
}
~~~

Create .harness/templates/root-cause-hypothesis-template.json:

~~~json
{
  "schema_version": 1,
  "hypothesis_id": "hyp-example",
  "failure_fact_refs": [
    ".harness/verification/runs/run-example/failures/docs-1.json"
  ],
  "target_component": "workflow-instruction",
  "causal_mechanism": "A falsifiable explanation of the observed failure mechanism.",
  "confidence": "low",
  "supporting_evidence_refs": [
    ".harness/verification/runs/run-example/run-manifest.json"
  ],
  "contradicting_evidence_refs": [],
  "expected_fix": "Expected observable effect after an approved implementation.",
  "at_risk_regressions": [
    "A preserved behavior that could regress"
  ]
}
~~~

- [ ] **Step 4: Implement context and hypothesis validation**

Store generated context packs under .harness/verification/context-packs/ and hypotheses under .harness/verification/hypotheses/. Use atomic_write_json.

Implement:

~~~python
from __future__ import annotations

import json
import hashlib
from pathlib import Path

from harness_schema import atomic_write_json


PROTECTED_CORE_FIELDS = {
    "exit_code",
    "terminal_cause",
    "failure_domain",
    "overall_harness_passed",
    "completion_state",
}


def _project_path(project_root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute():
        raise ValueError(f"absolute evidence reference is not allowed: {relative}")
    resolved = (project_root / path).resolve()
    if not resolved.is_relative_to(project_root.resolve()):
        raise ValueError(f"evidence reference escapes project root: {relative}")
    return resolved


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _config(project_root: Path) -> dict[str, object]:
    return _read_json(project_root / ".harness" / "agent" / "config.json")


def build_observability_summary(
    run_manifests: list[dict[str, object]],
    failure_facts: list[dict[str, object]],
) -> dict[str, object]:
    terminal_causes: dict[str, int] = {}
    failure_domains: dict[str, int] = {}
    for fact in failure_facts:
        cause = str(fact.get("terminal_cause", "unknown"))
        domain = str(fact.get("failure_domain", "unknown"))
        terminal_causes[cause] = terminal_causes.get(cause, 0) + 1
        failure_domains[domain] = failure_domains.get(domain, 0) + 1
    return {
        "component": {
            "terminal_causes": terminal_causes,
            "failure_domains": failure_domains,
        },
        "experience": {
            "run_count": len(run_manifests),
            "duration_ms": sum(int(run.get("duration_ms") or 0) for run in run_manifests),
            "attempt_count": sum(
                int(profile.get("attempts") or 0)
                for run in run_manifests
                for profile in run.get("profile_results", [])
                if isinstance(profile, dict)
            ),
        },
        "decision": {
            "suite_ids": sorted({str(run.get("suite_id", "legacy_unknown")) for run in run_manifests}),
            "selection_modes": sorted({str(run.get("selection_mode", "legacy_unknown")) for run in run_manifests}),
        },
    }


def build_context_pack(project_root: Path, failure_fact_refs: list[str]) -> dict[str, object]:
    config = _config(project_root)
    max_runs = int(config.get("max_context_runs", 10))
    max_chars = int(config.get("max_log_excerpt_chars", 4000))
    selected_refs = failure_fact_refs[:max_runs]
    fact_paths = [_project_path(project_root, ref) for ref in selected_refs]
    missing = [ref for ref, path in zip(selected_refs, fact_paths) if not path.exists()]
    if missing:
        raise ValueError("missing failure facts: " + ", ".join(missing))
    facts = [_read_json(path) for path in fact_paths]
    run_ids = list(dict.fromkeys(str(fact["run_id"]) for fact in facts))
    run_manifests = [
        _read_json(
            project_root
            / ".harness"
            / "verification"
            / "runs"
            / run_id
            / "run-manifest.json"
        )
        for run_id in run_ids
    ]
    run_index_path = project_root / ".harness" / "verification" / "run-index.json"
    run_index = _read_json(run_index_path) if run_index_path.exists() else {"runs": []}
    preserved_passing = [
        entry
        for entry in run_index.get("runs", [])
        if isinstance(entry, dict) and entry.get("overall_harness_passed") is True
    ][:max_runs]
    selected_ref_set = set(selected_refs)
    prior_hypotheses = [
        payload
        for path in sorted((project_root / ".harness/verification/hypotheses").glob("*.json"))
        if (payload := _read_json(path))
        and selected_ref_set.intersection(str(value) for value in payload.get("failure_fact_refs", []))
    ][:max_runs]
    candidate_outcomes = [
        {
            "id": str(payload.get("id", "")),
            "status": str(payload.get("status", "")),
            "lifecycle_stage": str(payload.get("lifecycle_stage", payload.get("status", ""))),
            "evaluation_brief_ref": str(payload.get("evaluation_brief_ref", "")),
        }
        for path in sorted((project_root / ".harness/evolution/candidates").glob("*.json"))
        if (payload := _read_json(path))
        and selected_ref_set.intersection(
            str(value) for value in payload.get("source_failure_fact_refs", [])
        )
    ][:max_runs]
    excerpts: list[dict[str, object]] = []
    for fact in facts:
        run_id = str(fact["run_id"])
        profile = str(fact["profile"])
        attempt = int(fact["attempt"])
        log_path = (
            project_root
            / ".harness"
            / "verification"
            / "runs"
            / run_id
            / "attempts"
            / f"{profile}-{attempt}.stdout.log"
        )
        if log_path.exists():
            excerpts.append(
                {
                    "fact_id": str(fact["fact_id"]),
                    "path": str(log_path.relative_to(project_root)).replace("\\", "/"),
                    "text": log_path.read_text(encoding="utf-8", errors="replace")[:max_chars],
                }
            )
    payload = {
        "schema_version": 1,
        "failure_fact_refs": selected_refs,
        "failure_facts": facts,
        "run_facts": run_manifests,
        "log_excerpts": excerpts,
        "preserved_passing_behavior": preserved_passing,
        "prior_hypotheses": prior_hypotheses,
        "candidate_outcomes": candidate_outcomes,
        "observability": build_observability_summary(run_manifests, facts),
        "held_out": {
            "suite_id": str(config["held_out_suite"]),
            "risk_categories": list(config.get("held_out_risk_categories", [])),
        },
    }
    context_id = hashlib.sha256("\n".join(selected_refs).encode("utf-8")).hexdigest()[:20]
    atomic_write_json(
        project_root / ".harness" / "verification" / "context-packs" / f"{context_id}.json",
        payload,
    )
    return payload


def validate_root_cause_hypothesis(
    project_root: Path,
    payload: dict[str, object],
) -> None:
    config = _config(project_root)
    if payload.get("confidence") not in {"low", "medium", "high"}:
        raise ValueError("confidence must be low, medium, or high")
    if payload.get("target_component") not in set(config.get("allowed_target_components", [])):
        raise ValueError("target_component is not allowed")
    for field in ("failure_fact_refs", "supporting_evidence_refs", "at_risk_regressions"):
        value = payload.get(field)
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
            raise ValueError(f"{field} must be a non-empty string list")
    contradictions = payload.get("contradicting_evidence_refs")
    if not isinstance(contradictions, list) or not all(isinstance(item, str) and item for item in contradictions):
        raise ValueError("contradicting_evidence_refs must be a string list")
    for field in ("hypothesis_id", "causal_mechanism", "expected_fix"):
        if not isinstance(payload.get(field), str) or payload.get(field) == "":
            raise ValueError(f"{field} must be a non-empty string")
    overlap = PROTECTED_CORE_FIELDS.intersection(payload)
    if overlap:
        raise ValueError("hypothesis contains protected Core fields: " + ", ".join(sorted(overlap)))
    evidence_refs = [
        *list(payload["failure_fact_refs"]),
        *list(payload["supporting_evidence_refs"]),
        *list(payload["contradicting_evidence_refs"]),
    ]
    evidence_paths = [_project_path(project_root, str(ref)) for ref in evidence_refs]
    missing = [ref for ref, path in zip(evidence_refs, evidence_paths) if not path.exists()]
    if missing:
        raise ValueError("missing hypothesis evidence: " + ", ".join(str(ref) for ref in missing))


def write_root_cause_hypothesis(
    project_root: Path,
    payload: dict[str, object],
) -> Path:
    validate_root_cause_hypothesis(project_root, payload)
    path = (
        project_root
        / ".harness"
        / "verification"
        / "hypotheses"
        / f"{payload['hypothesis_id']}.json"
    )
    if path.exists():
        raise FileExistsError(path)
    atomic_write_json(path, payload)
    return path
~~~

- [ ] **Step 5: Extend analyzer CLI**

Extend the parser and dispatch:

~~~python
from agent_harness import build_context_pack, write_root_cause_hypothesis


parser.add_argument(
    "--mode",
    choices=["analyze", "prepare-context", "record-hypothesis", "propose"],
    default="analyze",
)
parser.add_argument("--failure-fact-ref", action="append", default=[])
parser.add_argument("--hypothesis-file", default=None)

if args.mode == "prepare-context":
    if not args.failure_fact_ref:
        print("harness_evolution_error=--failure-fact-ref is required")
        return 1
    try:
        pack = build_context_pack(project_root, list(args.failure_fact_ref))
    except ValueError as exc:
        print(f"harness_evolution_error={exc}")
        return 1
    print(f"harness_context_pack_facts={len(pack['failure_facts'])}")
    return 0

if args.mode == "record-hypothesis":
    if not args.hypothesis_file:
        print("harness_evolution_error=--hypothesis-file is required")
        return 1
    try:
        hypothesis = json.loads(Path(args.hypothesis_file).read_text(encoding="utf-8"))
        path = write_root_cause_hypothesis(project_root, hypothesis)
    except (FileExistsError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"harness_evolution_error={exc}")
        return 1
    print(f"harness_root_cause_hypothesis={path}")
    return 0
~~~

The CLI never calls an LLM.

- [ ] **Step 6: Run Agent Harness tests**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_agent_harness.py
python scripts/verification/analyze_harness_evolution.py --mode prepare-context --failure-fact-ref .harness/verification/runs/missing/failures/example.json
~~~

Expected: tests pass. The CLI reports a structured missing-fact error and exits 1 for the nonexistent example rather than writing an invalid pack.

- [ ] **Step 7: Commit**

~~~powershell
git add .harness/agent .harness/templates/root-cause-hypothesis-template.json scripts/verification/agent_harness.py scripts/verification/analyze_harness_evolution.py scripts/verification/tests/test_agent_harness.py
git commit -m "feat: add governed harness analysis artifacts"
~~~

### Task 11: Replace Broad Mutation Scope With Candidate Schema V2

**Files:**
- Modify: scripts/verification/evolution.py:8-355
- Modify: scripts/verification/analyze_harness_evolution.py
- Modify: scripts/verification/tests/test_harness_evolution.py
- Modify: .harness/evolution/config.json
- Modify: .harness/templates/evolution-candidate-template.json

**Interfaces:**
- Consumes: a validated RootCauseHypothesis.
- Produces: build_candidate_from_hypothesis(candidate_id, hypothesis_ref, hypothesis, held_in_cases, config), schema v2 candidate manifests.

- [ ] **Step 1: Replace expected candidate shape in tests**

The v2 expected candidate must be:

~~~python
{
    "schema_version": 2,
    "id": "evo-docs-context",
    "status": "proposed",
    "lifecycle_stage": "proposed",
    "mutation_type": "workflow_instruction",
    "risk_tier": "sandbox-edit",
    "source_failure_fact_refs": [".harness/verification/runs/run-1/failures/docs-1.json"],
    "hypothesis_ref": ".harness/verification/hypotheses/hyp-docs-context.json",
    "proposed_changes": [
        {
            "path": "docs/ai-engineering-workflow.md",
            "summary": "Expose the approved suite command in Agent-facing workflow instructions.",
        }
    ],
    "held_in_cases": [
        {
            "profile": "docs",
            "before_run_id": "run-1",
            "failure_fact_ref": ".harness/verification/runs/run-1/failures/docs-1.json",
        }
    ],
    "held_out_suite": "held-out-canary",
    "expected_fixes": ["Expose the approved suite command in Agent-facing instructions."],
    "at_risk_regressions": ["Documentation duplication"],
    "promotion_checks": ["docs", "harness-lifecycle", "harness-evolution"],
    "requires_human_approval": True,
    "human_approval_artifact": "",
    "qa_review_required": True,
    "qa_review_artifacts": [],
    "evaluation_brief_ref": "",
}
~~~

- [ ] **Step 2: Run focused evolution tests and verify failure**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_harness_evolution.py -k "candidate"
~~~

Expected: FAIL because current candidates target scripts/verification and set requires_human_approval=false.

- [ ] **Step 3: Enforce the initial proposal allowlist**

Use:

~~~python
AGENT_HARNESS_EXACT_PATHS = {
    "AGENTS.md",
    "docs/ai-engineering-workflow.md",
    "docs/harness.md",
    "docs/harness-architecture.md",
    "docs/harness-reliability.md",
}
AGENT_HARNESS_PREFIXES = (
    ".harness/templates/",
    ".harness/agent/",
)
~~~

Reject scripts/verification/, .harness/profiles/, .harness/rules/, .harness/suites/, .harness/ci/, .github/, held-out artifacts, and all product paths.

- [ ] **Step 4: Update evolution config**

Set:

~~~json
{
  "schema_version": 2,
  "max_runs_to_analyze": 20,
  "profiles_in_scope": [
    "docs",
    "harness-lifecycle",
    "change-lifecycle",
    "harness-reference",
    "harness-evolution"
  ],
  "allowed_mutation_types": [
    "context_policy",
    "workflow_instruction",
    "template",
    "memory_policy"
  ],
  "promotion_requires_profiles": [
    "docs",
    "harness-lifecycle",
    "harness-evolution"
  ],
  "held_out_suite": "held-out-canary"
}
~~~

- [ ] **Step 5: Keep v1 candidates readable but write only v2**

First replace symptom-only v1 analysis with FailureFact-family analysis while keeping v1 manifests readable through normalize_run_manifest:

~~~python
from agent_harness import build_observability_summary
from harness_schema import atomic_write_json, normalize_run_manifest


def _normalize_failure_fact(payload: dict[str, object], ref: str) -> dict[str, object]:
    if "fact_id" in payload:
        return payload
    failed_checks = payload.get("failed_checks", [])
    return {
        "schema_version": 2,
        "fact_id": f"legacy:{ref}",
        "run_id": str(payload.get("run_id", "")),
        "profile": str(payload.get("profile", "")),
        "attempt": 1,
        "terminal_cause": "legacy_unknown",
        "failure_domain": "unknown",
        "failed_check_ids": [
            str(check["id"])
            for check in failed_checks
            if isinstance(check, dict) and isinstance(check.get("id"), str)
        ],
        "evidence_refs": [ref],
        "observed_notes": "normalized from schema v1 failure digest",
    }


def analyze_harness_evolution(project_root: Path, config: dict[str, object]) -> dict[str, object]:
    max_runs = int(config.get("max_runs_to_analyze", 20))
    profiles_in_scope = {str(value) for value in config.get("profiles_in_scope", [])}
    manifests = [
        normalize_run_manifest(payload, project_root)
        for payload in _recent_run_manifests(project_root, max_runs)
    ]
    failure_facts: list[dict[str, object]] = []
    telemetry_gaps: list[dict[str, object]] = []
    for manifest in manifests:
        for ref in manifest.get("failure_fact_refs", []):
            path = (project_root / str(ref)).resolve()
            if not path.is_relative_to(project_root.resolve()) or not path.exists():
                telemetry_gaps.append(
                    {"id": "missing_failure_fact_ref", "run_id": manifest.get("run_id"), "path": str(ref)}
                )
                continue
            payload, errors = _project_relative_read_json(project_root, path)
            if errors:
                telemetry_gaps.append(
                    {"id": "invalid_failure_fact_ref", "run_id": manifest.get("run_id"), "path": str(ref)}
                )
                continue
            fact = _normalize_failure_fact(payload, str(ref))
            fact["_source_ref"] = str(ref)
            if not profiles_in_scope or str(fact.get("profile", "")) in profiles_in_scope:
                failure_facts.append(fact)

    families: dict[tuple[str, str, str, tuple[str, ...]], list[dict[str, object]]] = defaultdict(list)
    for fact in failure_facts:
        family = (
            str(fact.get("profile", "")),
            str(fact.get("terminal_cause", "unknown")),
            str(fact.get("failure_domain", "unknown")),
            tuple(sorted(str(value) for value in fact.get("failed_check_ids", []))),
        )
        families[family].append(fact)
    failure_patterns = [
        {
            "id": f"failure_family.{profile}.{terminal_cause}.{failure_domain}",
            "profile": profile,
            "terminal_cause": terminal_cause,
            "failure_domain": failure_domain,
            "failed_check_ids": list(failed_check_ids),
            "failure_count": len(facts),
            "run_ids": sorted({str(fact["run_id"]) for fact in facts}),
            "source_failure_fact_refs": sorted(
                str(fact["_source_ref"])
                for fact in facts
            ),
            "confidence": "medium" if len(facts) >= 2 else "low",
        }
        for (profile, terminal_cause, failure_domain, failed_check_ids), facts in sorted(families.items())
    ]
    return {
        "schema_version": 2,
        "overall_harness_evolution_analyzed": True,
        "history_status": "analyzed" if manifests else "insufficient_history",
        "run_ids_analyzed": [str(manifest.get("run_id", "")) for manifest in manifests],
        "failure_patterns": failure_patterns,
        "telemetry_gaps": telemetry_gaps,
        "observability": build_observability_summary(manifests, failure_facts),
        "candidate_recommendations": [],
        "results": [],
    }
~~~

Then replace candidate loading and creation with these schema-v2 helpers:

~~~python
SUPPORTED_SCHEMA_VERSION = 2


def _is_agent_harness_proposal_path(path: str) -> bool:
    return path in AGENT_HARNESS_EXACT_PATHS or any(
        path.startswith(prefix) for prefix in AGENT_HARNESS_PREFIXES
    )


def _is_repository_relative_ref(value: str) -> bool:
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts


def _candidate_errors(
    relative: str,
    payload: dict[str, object],
    allowed_mutation_types: list[str],
) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        errors.append(f"{relative}: unsupported schema_version {payload.get('schema_version')}")
    for field in (
        "id",
        "status",
        "lifecycle_stage",
        "mutation_type",
        "risk_tier",
        "hypothesis_ref",
        "held_out_suite",
    ):
        if not isinstance(payload.get(field), str) or payload.get(field) == "":
            errors.append(f"{relative}: {field} must be a non-empty string")
    if payload.get("status") not in KNOWN_CANDIDATE_STATUSES:
        errors.append(f"{relative}: invalid status {payload.get('status')}")
    if payload.get("lifecycle_stage") not in KNOWN_CANDIDATE_LIFECYCLE_STAGES:
        errors.append(f"{relative}: invalid lifecycle_stage {payload.get('lifecycle_stage')}")
    if payload.get("risk_tier") not in KNOWN_RISK_TIERS:
        errors.append(f"{relative}: invalid risk_tier {payload.get('risk_tier')}")
    if payload.get("mutation_type") not in allowed_mutation_types:
        errors.append(f"{relative}: unsupported mutation_type {payload.get('mutation_type')}")
    if isinstance(payload.get("hypothesis_ref"), str) and not _is_repository_relative_ref(str(payload["hypothesis_ref"])):
        errors.append(f"{relative}: hypothesis_ref must be repository-relative")
    for field in (
        "source_failure_fact_refs",
        "expected_fixes",
        "at_risk_regressions",
        "promotion_checks",
    ):
        if not _is_non_empty_string_list(payload.get(field)):
            errors.append(f"{relative}: {field} must be a non-empty string list")
    for ref in payload.get("source_failure_fact_refs", []):
        if isinstance(ref, str) and not _is_repository_relative_ref(ref):
            errors.append(f"{relative}: source failure references must be repository-relative")
    held_in_cases = payload.get("held_in_cases")
    if not isinstance(held_in_cases, list) or not held_in_cases:
        errors.append(f"{relative}: held_in_cases must be a non-empty list")
    if payload.get("requires_human_approval") is not True:
        errors.append(f"{relative}: requires_human_approval must be true")
    if payload.get("qa_review_required") is not True:
        errors.append(f"{relative}: qa_review_required must be true")
    if not _is_string_list(payload.get("qa_review_artifacts")):
        errors.append(f"{relative}: qa_review_artifacts must be a string list")
    for field in ("human_approval_artifact", "evaluation_brief_ref"):
        if not isinstance(payload.get(field), str):
            errors.append(f"{relative}: {field} must be a string")

    proposed_changes = payload.get("proposed_changes")
    if not isinstance(proposed_changes, list) or not proposed_changes:
        errors.append(f"{relative}: proposed_changes must be a non-empty list")
    else:
        for index, change in enumerate(proposed_changes):
            if not isinstance(change, dict):
                errors.append(f"{relative}: proposed_changes[{index}] must be an object")
                continue
            path = change.get("path")
            if not isinstance(path, str) or not _is_agent_harness_proposal_path(path):
                errors.append(f"{relative}: proposed_changes[{index}] targets a protected path")
            if not isinstance(change.get("summary"), str) or change.get("summary") == "":
                errors.append(f"{relative}: proposed_changes[{index}].summary must be non-empty")
    for index, case in enumerate(held_in_cases if isinstance(held_in_cases, list) else []):
        if not isinstance(case, dict):
            errors.append(f"{relative}: held_in_cases[{index}] must be an object")
            continue
        for field in ("profile", "before_run_id", "failure_fact_ref"):
            if not isinstance(case.get(field), str) or case.get(field) == "":
                errors.append(f"{relative}: held_in_cases[{index}].{field} must be non-empty")
        failure_ref = case.get("failure_fact_ref")
        if isinstance(failure_ref, str) and not _is_repository_relative_ref(failure_ref):
            errors.append(f"{relative}: held_in_cases[{index}].failure_fact_ref must be repository-relative")
    return errors


COMPONENT_PROPOSAL_TARGETS = {
    "context-policy": ("context_policy", ".harness/agent/config.json"),
    "workflow-instruction": ("workflow_instruction", "docs/ai-engineering-workflow.md"),
    "template": ("template", ".harness/templates/AGENTS.md"),
    "memory-policy": ("memory_policy", ".harness/agent/config.json"),
}


def normalize_candidate_for_history(payload: dict[str, object]) -> dict[str, object]:
    if int(payload.get("schema_version", 0)) == 2:
        return payload
    return {
        "schema_version": 2,
        "source_schema_version": int(payload.get("schema_version", 0)),
        "id": str(payload.get("id", "")),
        "status": str(payload.get("status", "proposed")),
        "lifecycle_stage": str(payload.get("lifecycle_stage", "proposed")),
        "read_only_legacy": True,
        "source_failures": list(payload.get("source_failures", [])),
        "hypothesis_text": str(payload.get("hypothesis", "")),
        "proposed_changes": list(payload.get("proposed_changes", [])),
    }


def load_candidate_manifests(
    project_root: Path,
    *,
    allowed_mutation_types: list[str],
) -> tuple[list[dict[str, object]], list[str]]:
    candidates_dir = project_root / ".harness" / "evolution" / "candidates"
    candidates: list[dict[str, object]] = []
    errors: list[str] = []
    for path in sorted(candidates_dir.glob("*.json")) if candidates_dir.exists() else []:
        relative = _relative_path(project_root, path)
        payload, read_errors = _project_relative_read_json(project_root, path)
        if read_errors:
            errors.extend(read_errors)
            continue
        if int(payload.get("schema_version", 0)) == 1:
            legacy = normalize_candidate_for_history(payload)
            if legacy["lifecycle_stage"] in {"promotion-ready", "promoted"}:
                errors.append(f"{relative}: read-only legacy candidate cannot be promoted")
                continue
            candidates.append(legacy)
            continue
        candidate_errors = _candidate_errors(relative, payload, allowed_mutation_types)
        if candidate_errors:
            errors.extend(candidate_errors)
            continue
        candidates.append(payload)
    return candidates, errors


def build_candidate_from_hypothesis(
    *,
    candidate_id: str,
    hypothesis_ref: str,
    hypothesis: dict[str, object],
    held_in_cases: list[dict[str, object]],
    config: dict[str, object],
) -> dict[str, object]:
    target_component = str(hypothesis["target_component"])
    if target_component not in COMPONENT_PROPOSAL_TARGETS:
        raise ValueError(f"Unsupported target component: {target_component}")
    mutation_type, proposed_path = COMPONENT_PROPOSAL_TARGETS[target_component]
    expected_fix = str(hypothesis["expected_fix"])
    candidate = {
        "schema_version": 2,
        "id": candidate_id,
        "status": "proposed",
        "lifecycle_stage": "proposed",
        "mutation_type": mutation_type,
        "risk_tier": "sandbox-edit",
        "source_failure_fact_refs": list(hypothesis["failure_fact_refs"]),
        "hypothesis_ref": hypothesis_ref,
        "proposed_changes": [{"path": proposed_path, "summary": expected_fix}],
        "held_in_cases": held_in_cases,
        "held_out_suite": str(config["held_out_suite"]),
        "expected_fixes": [expected_fix],
        "at_risk_regressions": list(hypothesis["at_risk_regressions"]),
        "promotion_checks": list(config["promotion_requires_profiles"]),
        "requires_human_approval": True,
        "human_approval_artifact": "",
        "qa_review_required": True,
        "qa_review_artifacts": [],
        "evaluation_brief_ref": "",
    }
    errors = _candidate_errors(
        f".harness/evolution/candidates/{candidate_id}.json",
        candidate,
        list(config["allowed_mutation_types"]),
    )
    if errors:
        raise ValueError("\n".join(errors))
    return candidate


def write_candidate_manifest(project_root: Path, candidate: dict[str, object]) -> Path:
    candidate_id = str(candidate["id"])
    path = project_root / ".harness" / "evolution" / "candidates" / f"{candidate_id}.json"
    if path.exists():
        raise FileExistsError(f"{candidate_id}.json already exists")
    atomic_write_json(path, candidate)
    return path
~~~

When reading schema v1 candidates, expose normalize_candidate_for_history output to analysis only and reject any attempt to move a read_only_legacy record to promotion-ready or promoted. New candidate creation and the template use schema_version=2 and requires_human_approval=true.

Replace .harness/templates/evolution-candidate-template.json with:

~~~json
{
  "schema_version": 2,
  "id": "evo-example",
  "status": "proposed",
  "lifecycle_stage": "proposed",
  "mutation_type": "workflow_instruction",
  "risk_tier": "sandbox-edit",
  "source_failure_fact_refs": [
    ".harness/verification/runs/run-example/failures/docs-1.json"
  ],
  "hypothesis_ref": ".harness/verification/hypotheses/hyp-example.json",
  "proposed_changes": [
    {
      "path": "docs/ai-engineering-workflow.md",
      "summary": "Expose an approved Harness command in Agent-facing workflow instructions."
    }
  ],
  "held_in_cases": [
    {
      "profile": "docs",
      "before_run_id": "run-example",
      "failure_fact_ref": ".harness/verification/runs/run-example/failures/docs-1.json"
    }
  ],
  "held_out_suite": "held-out-canary",
  "expected_fixes": [
    "Expose the approved Harness command."
  ],
  "at_risk_regressions": [
    "Documentation duplication"
  ],
  "promotion_checks": [
    "docs",
    "harness-lifecycle",
    "harness-evolution"
  ],
  "requires_human_approval": true,
  "human_approval_artifact": "",
  "qa_review_required": true,
  "qa_review_artifacts": [],
  "evaluation_brief_ref": ""
}
~~~

- [ ] **Step 6: Make propose mode consume a hypothesis**

Require:

~~~powershell
python scripts/verification/analyze_harness_evolution.py --mode propose --candidate-id <id> --hypothesis-file <path>
~~~

Implement propose mode with repository-relative evidence references and no patch application:

~~~python
from agent_harness import validate_root_cause_hypothesis
from evolution import build_candidate_from_hypothesis


if args.mode == "propose":
    if not args.candidate_id or not args.hypothesis_file:
        print("harness_evolution_error=--candidate-id and --hypothesis-file are required")
        return 1
    try:
        hypothesis_path = Path(args.hypothesis_file).resolve()
        hypothesis_ref = hypothesis_path.relative_to(project_root.resolve()).as_posix()
        hypothesis = json.loads(hypothesis_path.read_text(encoding="utf-8"))
        if not isinstance(hypothesis, dict):
            raise ValueError("hypothesis file must contain a JSON object")
        validate_root_cause_hypothesis(project_root, hypothesis)
        held_in_cases: list[dict[str, object]] = []
        for failure_ref in hypothesis["failure_fact_refs"]:
            failure_path = (project_root / str(failure_ref)).resolve()
            if not failure_path.is_relative_to(project_root.resolve()):
                raise ValueError(f"failure fact escapes project root: {failure_ref}")
            failure = json.loads(failure_path.read_text(encoding="utf-8"))
            held_in_cases.append(
                {
                    "profile": str(failure["profile"]),
                    "before_run_id": str(failure["run_id"]),
                    "failure_fact_ref": str(failure_ref),
                }
            )
        candidate = build_candidate_from_hypothesis(
            candidate_id=args.candidate_id,
            hypothesis_ref=hypothesis_ref,
            hypothesis=hypothesis,
            held_in_cases=held_in_cases,
            config=config,
        )
        candidate_path = write_candidate_manifest(project_root, candidate)
    except (FileExistsError, KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"harness_evolution_error={exc}")
        return 1
    print(f"harness_evolution_candidate={candidate_path}")
    return 0
~~~

- [ ] **Step 7: Run candidate tests**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_harness_evolution.py -k "candidate or scope or approval"
~~~

Expected: all focused tests pass; protected paths and false human-approval values are rejected.

- [ ] **Step 8: Commit**

~~~powershell
git add .harness/evolution/config.json .harness/templates/evolution-candidate-template.json scripts/verification/evolution.py scripts/verification/analyze_harness_evolution.py scripts/verification/tests/test_harness_evolution.py
git commit -m "feat: govern agent harness candidates"
~~~

### Task 12: Add Held-In And Held-Out Evaluation Briefs

**Files:**
- Create: scripts/verification/evaluate_harness_candidate.py
- Create: scripts/verification/tests/test_harness_candidate_evaluation.py
- Modify: scripts/verification/evolution.py
- Modify: scripts/verification/check_harness_evolution.py
- Modify: scripts/verification/tests/test_harness_evolution.py
- Modify: .harness/evolution/replay-sets/default.json
- Modify: .harness/rules/harness-evolution-rules.json

**Interfaces:**
- Consumes: candidate v2, held-in before and after run manifests, held-out before and after run manifests.
- Produces: build_evaluation_brief(...), .harness/verification/evaluations/<candidate-id>.json.

- [ ] **Step 1: Write failing evaluation tests**

Create scripts/verification/tests/test_harness_candidate_evaluation.py:

~~~python
from __future__ import annotations

from evaluate_harness_candidate import build_evaluation_brief


CANDIDATE = {
    "schema_version": 2,
    "id": "evo-docs-context",
    "held_in_cases": [
        {
            "profile": "docs",
            "before_run_id": "run-before",
            "failure_fact_ref": ".harness/verification/runs/run-before/failures/docs-1.json",
        }
    ],
    "expected_fixes": ["Expose the approved suite command."],
    "at_risk_regressions": ["Documentation duplication"],
    "held_out_suite": "held-out-canary",
    "promotion_checks": ["docs", "harness-lifecycle", "harness-evolution"],
}


def manifest(
    run_id: str,
    exit_codes: dict[str, int],
    *,
    suite_id: str = "held-out-canary",
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "run_id": run_id,
        "suite_id": suite_id,
        "profile_results": [
            {
                "profile": profile,
                "exit_code": exit_code,
                "status": "passed" if exit_code == 0 else "failed",
            }
            for profile, exit_code in sorted(exit_codes.items())
        ],
    }


def test_evaluation_requires_held_in_improvement_and_no_held_out_regression() -> None:
    brief = build_evaluation_brief(
        candidate=CANDIDATE,
        held_in_before=manifest("run-before", {"docs": 1}),
        held_in_after=manifest("run-after", {"docs": 0}),
        held_out_before=manifest(
            "canary-before",
            {"docs": 0, "harness-lifecycle": 0, "harness-evolution": 0},
        ),
        held_out_after=manifest(
            "canary-after",
            {"docs": 0, "harness-lifecycle": 0, "harness-evolution": 0},
        ),
    )
    assert brief["held_in_improved"] is True
    assert brief["held_out_regressions"] == []
    assert brief["overall_candidate_evaluation_passed"] is True


def test_evaluation_rejects_held_out_regression() -> None:
    brief = build_evaluation_brief(
        candidate=CANDIDATE,
        held_in_before=manifest("run-before", {"docs": 1}),
        held_in_after=manifest("run-after", {"docs": 0}),
        held_out_before=manifest("canary-before", {"harness-lifecycle": 0}),
        held_out_after=manifest("canary-after", {"harness-lifecycle": 1}),
    )
    assert brief["held_out_regressions"] == ["harness-lifecycle"]
    assert brief["overall_candidate_evaluation_passed"] is False


def test_evaluation_rejects_wrong_held_out_suite_and_missing_held_in_profiles() -> None:
    brief = build_evaluation_brief(
        candidate=CANDIDATE,
        held_in_before=manifest("run-before", {}, suite_id="explicit:docs"),
        held_in_after=manifest("run-after", {}, suite_id="explicit:docs"),
        held_out_before=manifest("canary-before", {"docs": 0}, suite_id="local-full"),
        held_out_after=manifest("canary-after", {"docs": 0}, suite_id="local-full"),
    )

    assert "held-in profile missing: docs" in brief["telemetry_gaps"]
    assert "held-out suite mismatch: expected held-out-canary" in brief["telemetry_gaps"]
    assert brief["overall_candidate_evaluation_passed"] is False
~~~

- [ ] **Step 2: Run tests and verify missing API**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_harness_candidate_evaluation.py
~~~

Expected: collection fails because build_evaluation_brief does not exist.

- [ ] **Step 3: Implement evaluation comparison**

In evaluate_harness_candidate.py:

~~~python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import repo_root
from harness_schema import atomic_write_json, normalize_run_manifest


def _exit_codes(manifest: dict[str, object]) -> dict[str, int]:
    return {
        str(entry["profile"]): int(entry.get("exit_code", 1))
        for entry in manifest.get("profile_results", [])
        if isinstance(entry, dict)
    }


def build_evaluation_brief(
    *,
    candidate: dict[str, object],
    held_in_before: dict[str, object],
    held_in_after: dict[str, object],
    held_out_before: dict[str, object],
    held_out_after: dict[str, object],
) -> dict[str, object]:
    before_in = _exit_codes(held_in_before)
    after_in = _exit_codes(held_in_after)
    held_in_profiles = [str(case["profile"]) for case in candidate.get("held_in_cases", [])]
    telemetry_gaps: list[str] = []
    if not held_in_profiles:
        telemetry_gaps.append("candidate has no held-in profiles")
    expected_before_run_ids = {
        str(case.get("before_run_id", ""))
        for case in candidate.get("held_in_cases", [])
        if isinstance(case, dict)
    }
    if expected_before_run_ids != {str(held_in_before.get("run_id", ""))}:
        telemetry_gaps.append("held-in before run does not cover every candidate case")
    held_in_outcomes: list[dict[str, object]] = []
    for profile in held_in_profiles:
        if profile not in before_in or profile not in after_in:
            telemetry_gaps.append(f"held-in profile missing: {profile}")
            continue
        held_in_outcomes.append(
            {
                "profile": profile,
                "before_exit_code": before_in[profile],
                "after_exit_code": after_in[profile],
                "improved": before_in[profile] != 0 and after_in[profile] == 0,
            }
        )
    improved = bool(held_in_outcomes) and len(held_in_outcomes) == len(held_in_profiles) and all(
        bool(outcome["improved"]) for outcome in held_in_outcomes
    )
    before_out = _exit_codes(held_out_before)
    after_out = _exit_codes(held_out_after)
    expected_held_out_suite = str(candidate.get("held_out_suite", ""))
    if (
        held_out_before.get("suite_id") != expected_held_out_suite
        or held_out_after.get("suite_id") != expected_held_out_suite
    ):
        telemetry_gaps.append(f"held-out suite mismatch: expected {expected_held_out_suite}")
    regressions = sorted(
        name for name, exit_code in before_out.items()
        if exit_code == 0 and after_out.get(name, 1) != 0
    )
    missing_after = sorted(name for name in before_out if name not in after_out)
    telemetry_gaps.extend(f"held-out profile missing after evaluation: {name}" for name in missing_after)
    promotion_checks = [str(value) for value in candidate.get("promotion_checks", [])]
    promotion_check_failures = sorted(
        profile for profile in promotion_checks if after_out.get(profile, 1) != 0
    )
    telemetry_gaps.extend(
        f"promotion check missing or failed: {profile}" for profile in promotion_check_failures
    )
    return {
        "schema_version": 1,
        "candidate_id": str(candidate["id"]),
        "held_in_before_run_id": str(held_in_before["run_id"]),
        "held_in_after_run_id": str(held_in_after["run_id"]),
        "held_out_before_run_id": str(held_out_before["run_id"]),
        "held_out_after_run_id": str(held_out_after["run_id"]),
        "held_in_improved": improved,
        "held_in_outcomes": held_in_outcomes,
        "held_out_regressions": regressions,
        "promotion_check_failures": promotion_check_failures,
        "predicted_effects": {
            "fixes": list(candidate.get("expected_fixes", [])),
            "at_risk_regressions": list(candidate.get("at_risk_regressions", [])),
        },
        "observed_effects": {
            "held_in_outcomes": held_in_outcomes,
            "held_out_regressions": regressions,
        },
        "telemetry_gaps": telemetry_gaps,
        "overall_candidate_evaluation_passed": improved and not regressions and not telemetry_gaps,
    }
~~~

- [ ] **Step 4: Add evaluation CLI**

Complete the CLI with these helpers and arguments:

~~~python
def _load_run_manifest(project_root: Path, run_id: str) -> dict[str, object]:
    path = (
        project_root
        / ".harness"
        / "verification"
        / "runs"
        / run_id
        / "run-manifest.json"
    )
    if not path.exists():
        raise FileNotFoundError(f"run manifest not found: {run_id}")
    return normalize_run_manifest(
        json.loads(path.read_text(encoding="utf-8")),
        project_root,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--held-in-before-run", required=True)
    parser.add_argument("--held-in-after-run", required=True)
    parser.add_argument("--held-out-before-run", required=True)
    parser.add_argument("--held-out-after-run", required=True)
    parser.add_argument("--project-root", default=None)
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve() if args.project_root else repo_root()

    try:
        candidate_path = (
            project_root
            / ".harness"
            / "evolution"
            / "candidates"
            / f"{args.candidate_id}.json"
        )
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        if not isinstance(candidate, dict) or candidate.get("schema_version") != 2:
            raise ValueError("candidate must be a schema v2 JSON object")
        brief = build_evaluation_brief(
            candidate=candidate,
            held_in_before=_load_run_manifest(project_root, args.held_in_before_run),
            held_in_after=_load_run_manifest(project_root, args.held_in_after_run),
            held_out_before=_load_run_manifest(project_root, args.held_out_before_run),
            held_out_after=_load_run_manifest(project_root, args.held_out_after_run),
        )
    except (FileNotFoundError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"harness_candidate_evaluation_error={exc}")
        return 1

    json_path = (
        project_root
        / ".harness"
        / "verification"
        / "evaluations"
        / f"{args.candidate_id}.json"
    )
    atomic_write_json(json_path, brief)
    markdown_path = json_path.with_suffix(".md")
    markdown_path.write_text(
        "\n".join(
            [
                "# Harness Candidate Evaluation",
                "",
                f"- Candidate: `{brief['candidate_id']}`",
                f"- Held-in improved: `{brief['held_in_improved']}`",
                f"- Held-out regressions: `{', '.join(brief['held_out_regressions'])}`",
                f"- Telemetry gaps: `{len(brief['telemetry_gaps'])}`",
                f"- Overall: `{brief['overall_candidate_evaluation_passed']}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"harness_candidate_evaluation_json={json_path}")
    print(f"harness_candidate_evaluation_md={markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
~~~

- [ ] **Step 5: Strengthen promotion-ready validation**

Add a separate evidence-aware validator called from load_candidate_manifests:

~~~python
def _evidence_ref_path(project_root: Path, relative: str) -> Path | None:
    path = Path(relative)
    if path.is_absolute():
        return None
    resolved = (project_root / path).resolve()
    return resolved if resolved.is_relative_to(project_root.resolve()) else None


def _evidence_ref_exists(project_root: Path, relative: str) -> bool:
    path = _evidence_ref_path(project_root, relative)
    return path is not None and path.exists()


def _promotion_evidence_errors(
    project_root: Path,
    relative: str,
    payload: dict[str, object],
) -> list[str]:
    stage = str(payload.get("lifecycle_stage", payload.get("status", "")))
    if stage not in {"promotion-ready", "promoted"}:
        return []
    errors: list[str] = []
    if payload.get("requires_human_approval") is not True:
        errors.append(f"{relative}: promotion requires human approval")
    approval = payload.get("human_approval_artifact")
    if not isinstance(approval, str) or approval == "":
        errors.append(f"{relative}: promotion requires human_approval_artifact")
    elif not _evidence_ref_exists(project_root, approval):
        errors.append(f"{relative}: human_approval_artifact must exist inside the repository")
    qa_artifacts = payload.get("qa_review_artifacts")
    if not isinstance(qa_artifacts, list) or not qa_artifacts:
        errors.append(f"{relative}: promotion requires qa_review_artifacts")
    else:
        missing_qa = [ref for ref in qa_artifacts if not isinstance(ref, str) or not _evidence_ref_exists(project_root, ref)]
        if missing_qa:
            errors.append(f"{relative}: every qa_review_artifact must exist inside the repository")
    brief_ref = payload.get("evaluation_brief_ref")
    if not isinstance(brief_ref, str) or brief_ref == "":
        errors.append(f"{relative}: promotion requires evaluation_brief_ref")
        return errors
    brief_path = _evidence_ref_path(project_root, brief_ref)
    if brief_path is None:
        errors.append(f"{relative}: evaluation_brief_ref must stay inside the repository")
        return errors
    brief, brief_errors = _project_relative_read_json(project_root, brief_path)
    if (
        brief_errors
        or brief.get("candidate_id") != payload.get("id")
        or brief.get("overall_candidate_evaluation_passed") is not True
        or brief.get("held_in_improved") is not True
        or brief.get("held_out_regressions") != []
        or brief.get("promotion_check_failures") != []
        or brief.get("telemetry_gaps") != []
    ):
        errors.append(f"{relative}: evaluation brief must exist and pass")
    return errors
~~~

Keep `_candidate_errors(relative, payload, allowed_mutation_types)` structural; in `load_candidate_manifests`, call `_promotion_evidence_errors(project_root, relative, payload)` only after structural validation succeeds. Neither validator updates the candidate or applies code.

Use this exact v2 branch in `load_candidate_manifests`:

~~~python
candidate_errors = _candidate_errors(relative, payload, allowed_mutation_types)
if not candidate_errors:
    candidate_errors.extend(_promotion_evidence_errors(project_root, relative, payload))
if candidate_errors:
    errors.extend(candidate_errors)
    continue
candidates.append(payload)
~~~

- [ ] **Step 6: Update replay and rules**

Set default replay metadata:

~~~json
{
  "schema_version": 2,
  "id": "default",
  "held_out_suite": "held-out-canary",
  "required_success_profiles": [
    "docs",
    "harness-lifecycle",
    "harness-evolution"
  ],
  "regression_guards": [
    "held_in_failure_resolved",
    "held_out_profile_exit_code_does_not_worsen",
    "core_fact_schema_stable"
  ]
}
~~~

Add rule IDs:

- evolution_hypotheses_governed
- evolution_candidate_scope_protected
- evolution_evaluation_briefs_governed

Replace `load_replay_set` validation so raw held-out case details are not part of proposal-facing replay metadata:

~~~python
errors: list[str] = []
relative = f".harness/evolution/replay-sets/{replay_set_id}.json"
if payload.get("schema_version") != 2:
    errors.append(f"{relative}: unsupported schema_version {payload.get('schema_version')}")
if payload.get("id") != replay_set_id:
    errors.append(f"{relative}: id must match {replay_set_id}")
if not isinstance(payload.get("held_out_suite"), str) or payload.get("held_out_suite") == "":
    errors.append(f"{relative}: held_out_suite must be a non-empty string")
if not _is_non_empty_string_list(payload.get("required_success_profiles")):
    errors.append(f"{relative}: required_success_profiles must be a non-empty string list")
if not _is_non_empty_string_list(payload.get("regression_guards")):
    errors.append(f"{relative}: regression_guards must be a non-empty string list")
return ({}, errors) if errors else (payload, [])
~~~

- [ ] **Step 7: Run evaluation and evolution tests**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_harness_candidate_evaluation.py scripts/verification/tests/test_harness_evolution.py scripts/verification/tests/test_formal_profile_checks.py
python scripts/verification/harness.py --profile harness-evolution
~~~

Expected: all tests and profile pass. A promotion-ready candidate without any required evidence is rejected.

- [ ] **Step 8: Commit**

~~~powershell
git add .harness/evolution/replay-sets/default.json .harness/rules/harness-evolution-rules.json scripts/verification/evaluate_harness_candidate.py scripts/verification/evolution.py scripts/verification/check_harness_evolution.py scripts/verification/tests/test_harness_candidate_evaluation.py scripts/verification/tests/test_harness_evolution.py scripts/verification/tests/test_formal_profile_checks.py
git commit -m "feat: evaluate harness candidates against canaries"
~~~

### Task 13: Complete Documentation, Registry Coverage, And Final Verification

**Files:**
- Modify: AGENTS.md
- Modify: docs/INDEX.md
- Modify: docs/harness.md
- Modify: docs/harness-architecture.md
- Modify: docs/harness-reliability.md
- Modify: docs/ai-engineering-workflow.md
- Modify: .harness/features.json
- Modify: .harness/evaluator-rubric.md
- Modify: .harness/quality-document.md
- Modify: scripts/verification/tests/test_docs_checks.py
- Modify: scripts/verification/tests/test_harness_registry.py

**Interfaces:**
- Consumes: all implemented commands and evidence schemas.
- Produces: final discoverability and acceptance documentation.

- [ ] **Step 1: Add final documentation assertions**

Add to test_docs_checks.py:

~~~python
def test_harness_docs_describe_two_layer_evolution_contract() -> None:
    project_root = repo_root()
    combined = "\n".join(
        [
            (project_root / "AGENTS.md").read_text(encoding="utf-8"),
            (project_root / "docs/harness.md").read_text(encoding="utf-8"),
            (project_root / "docs/harness-architecture.md").read_text(encoding="utf-8"),
            (project_root / "docs/harness-reliability.md").read_text(encoding="utf-8"),
            (project_root / "docs/ai-engineering-workflow.md").read_text(encoding="utf-8"),
        ]
    )
    required = [
        "Core Harness",
        "Agent Harness",
        "FailureFact",
        "RootCauseHypothesis",
        "held-in",
        "held-out-canary",
        "requires_human_approval",
        "evaluation_brief_ref",
        "component observability",
        "experience observability",
        "decision observability",
        "P0",
        "P1",
        "P2",
    ]

    assert [value for value in required if value not in combined] == []
~~~

- [ ] **Step 2: Run docs tests and verify failure**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests/test_docs_checks.py scripts/verification/tests/test_harness_registry.py
~~~

Expected: FAIL until the complete two-layer contract is documented.

- [ ] **Step 3: Update the operating documentation**

Document these authority rules exactly:

- Core facts cannot be overwritten by Agent artifacts.
- Agent hypotheses and candidates are proposals.
- initial candidates target Agent-facing Harness surfaces only.
- held-out suite contents are excluded from generated proposal context.
- human approval, QA evidence, held-in improvement, and held-out non-regression precede promotion-ready.
- hosted CI is non-Godot; local full verification remains the runtime authority.
- component observability summarizes terminal causes and failure domains; experience observability summarizes duration and attempts; decision observability summarizes suite and selection choices.

Update evaluator rubric criteria for attribution, selection honesty, retention, and candidate governance.

Add feature-ledger entries:

- agent-context-packs
- root-cause-hypotheses
- candidate-scope-protection
- held-in-held-out-evaluation

- [ ] **Step 4: Run the complete P2 verification ladder**

Run:

~~~powershell
python -m pytest -q scripts/verification/tests
python -m compileall -q scripts/verification
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile boundaries
python scripts/verification/harness.py --profile drift
python scripts/verification/harness.py --profile release-gate
python scripts/verification/harness.py --profile harness-lifecycle
python scripts/verification/harness.py --profile change-lifecycle
python scripts/verification/harness.py --profile harness-reference
python scripts/verification/harness.py --profile harness-evolution
python scripts/verification/harness.py --suite ci-non-godot
python scripts/verification/harness.py --profile all
~~~

Expected:

- every command exits 0
- full test output contains zero failures
- docs and registry profiles prove every new file and command
- ci-non-godot contains no Godot or credential-backed profile
- local all includes runtime profiles
- latest run manifest uses schema_version=2
- incompatible baseline families report no_comparable_baseline
- selection reports retain broad_completion_verified=false
- retention leaves pinned and baseline runs full
- candidate validator rejects protected paths and missing approval evidence

- [ ] **Step 5: Inspect generated evidence**

Read:

- .harness/verification/harness-run-manifest.json
- .harness/verification/harness-run-diff.json
- .harness/verification/run-index.json
- one archived attempt record
- one FailureFact
- .harness/verification/harness-selection-report.json
- .harness/verification/harness-evolution-report.json

Confirm that all structured paths are repository-relative and that no credential value is present.

- [ ] **Step 6: Inspect the final diff**

Run:

~~~powershell
git status --short
git diff --check
git diff --stat
~~~

Expected: only Harness code, manifests, tests, workflows, and documentation changed. No Backend, Godot scene, Siming, ESM, or product runtime file changed.

- [ ] **Step 7: Commit**

~~~powershell
git add AGENTS.md docs .harness scripts/verification .github/workflows/harness.yml
git commit -m "docs: finalize two-layer harness workflow"
~~~

## Execution Completion Gate

Before claiming the implementation complete:

1. Run the full Task 13 verification ladder again from a clean prompt.
2. Confirm git status is clean.
3. Read the latest run manifest and report the exact run_id.
4. Separate completed and verified, completed but not Godot-verified, blocked, and next step in the handoff.
5. If any Godot-backed profile was not executed successfully, do not claim local-full completion.
