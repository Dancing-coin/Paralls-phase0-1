from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = PROJECT_ROOT / "scripts" / "verification" / "verify_script_evolution.py"
SCRIPT_FIXTURE_PATH = PROJECT_ROOT / ".harness" / "fixtures" / "script-evolution" / "demo-script.md"
CHOICES_FIXTURE_PATH = PROJECT_ROOT / ".harness" / "fixtures" / "script-evolution" / "demo-choices.txt"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_script_evolution", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_fixture_baseline_normalizes_from_natural_language_text() -> None:
    module = load_module()

    script_text = SCRIPT_FIXTURE_PATH.read_text(encoding="utf-8")
    baseline = module.normalize_baseline_fixture(script_text)

    assert baseline == module.fixture_baseline_model()
    assert baseline["script_id"] == "lamp_letter"
    assert baseline["objects"][0]["object_id"] == "obj_letter"
    assert baseline["objects"][0]["state"]["interaction_state"] == "unopened"
    assert {fact["fact_id"] for fact in baseline["locked_facts"]} == {
        "fact_letter_exists",
        "fact_char_b_does_not_know_letter_content",
    }


def test_fixture_choices_normalize_from_natural_language_text() -> None:
    module = load_module()

    choices_text = CHOICES_FIXTURE_PATH.read_text(encoding="utf-8")
    choices = module.normalize_candidate_choices_fixture(choices_text)

    assert choices == module.fixture_candidate_choices()
    assert [choice["choice_id"] for choice in choices] == ["A", "B", "C"]
    assert choices[0]["interaction_type"] == "inspect"
    assert choices[1]["interaction_type"] == "leave"
    assert choices[2]["interaction_type"] == "handoff"
    assert choices[2]["secondary_target_ref"] == "char_b"


def test_baseline_normalizer_requires_mainline_fragments() -> None:
    module = load_module()
    script_text = """# 灯下信件

深夜，书房里只有一盏台灯亮着。
角色 A 站在书桌旁。
角色 B 在门外，并不知道信里的内容。
"""

    try:
        module.normalize_baseline_fixture(script_text)
    except ValueError as exc:
        assert "old letter exists on desk" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing desk-letter fragment")


def test_choice_normalizer_maps_by_body_semantics_not_choice_label() -> None:
    module = load_module()

    choices_text = "\n".join(
        [
            "A. 玩家直接离开书房。",
            "B. 玩家拿起旧信仔细查看。",
            "C. 玩家把信交给门外的角色 B。",
        ]
    )

    choices = module.normalize_candidate_choices_fixture(choices_text)

    assert choices[0]["choice_id"] == "A"
    assert choices[0]["interaction_type"] == "leave"
    assert choices[1]["choice_id"] == "B"
    assert choices[1]["interaction_type"] == "inspect"


def test_choice_normalizer_marks_unrecognized_choice_as_normalization_failed() -> None:
    module = load_module()

    choices_text = "\n".join(
        [
            "A. 玩家拿起旧信仔细查看。",
            "B. 玩家开始哼歌等待。",
            "C. 玩家把信交给门外的角色 B。",
        ]
    )

    choices = module.normalize_candidate_choices_fixture(choices_text)
    failed = choices[1]

    assert failed["choice_id"] == "B"
    assert failed["source_text"] == "玩家开始哼歌等待。"
    assert failed["event_type"] == "normalization_failed"
    assert failed["confidence"] == 0.0
    assert "unrecognized choice body" in failed["notes"]


def test_classify_choice_before_backend_execution() -> None:
    module = load_module()
    baseline = module.fixture_baseline_model()
    choices = module.fixture_candidate_choices()

    result_a = module.classify_choice(baseline, choices[0])
    result_b = module.classify_choice(baseline, choices[1])
    result_c = module.classify_choice(baseline, choices[2])

    assert result_a.classification == "PENDING_AUTHORITY_EXECUTION"
    assert result_a.matched_deviation_id == "player_inspects_letter"
    assert result_b.classification == "EVOLVABLE_NO_IMPACT"
    assert result_c.classification == "NEEDS_PRIOR_EVENT"
    assert "obj_letter.possession" in result_c.notes


def test_classify_choice_skips_prior_event_when_requirement_is_already_satisfied() -> None:
    module = load_module()
    baseline = module.fixture_baseline_model()
    baseline["objects"][0]["state"]["possession"] = "char_a"
    choice_c = module.fixture_candidate_choices()[2]

    result_c = module.classify_choice(baseline, choice_c)

    assert result_c.classification != "NEEDS_PRIOR_EVENT"
    assert result_c.classification == "PENDING_AUTHORITY_EXECUTION"
    assert "prior requirement satisfied; authority execution required" in result_c.notes


def test_execute_choice_branch_produces_authority_esm_and_diff() -> None:
    module = load_module()
    baseline = module.fixture_baseline_model()
    candidate = module.fixture_candidate_choices()[0]

    result = module.execute_choice_branch(baseline, candidate)

    assert result.classification in {"MAINLINE_IMPACT_DETECTED", "PENDING_SIMING_OBSERVATION"}
    assert result.matched_deviation_id == "player_inspects_letter"
    assert any(event["event_type"] == "player.interaction.requested" for event in result.authority_events)
    assert any(event["event_type"] == "esm_result_event" for event in result.authority_events)
    assert any(event["event_type"] == "world.object_state.changed" for event in result.authority_events)
    assert any(item["result_type"] == "action_resolution_result" for item in result.esm_results)
    expected_branch_diff = {
        (diff["path"], diff["from"], diff["to"])
        for diff in result.branch_diff
    }
    assert expected_branch_diff == {
        ("objects.obj_letter.visibility_state", "partially_visible", "visible"),
        ("objects.obj_letter.interaction_state", "unopened", "inspected"),
    }
    esm_events = [event for event in result.authority_events if event["event_type"] == "esm_result_event"]
    assert all("state_path" in event["payload"] for event in esm_events)
    assert {event["payload"]["state_path"] for event in esm_events} == {
        diff_path for diff_path, _, _ in expected_branch_diff
    }
    assert {
        event["payload"]["state_path"]: (
            event["payload"]["machine_id"],
            event["payload"]["change_summary"],
        )
        for event in esm_events
    } == {
        "objects.obj_letter.visibility_state": ("visibility", "obj_letter visibility_state changed from partially_visible to visible"),
        "objects.obj_letter.interaction_state": ("interaction", "obj_letter interaction_state changed from unopened to inspected"),
    }


def test_execute_choice_branch_skips_branch_artifacts_when_interaction_is_rejected() -> None:
    module = load_module()
    baseline = module.fixture_baseline_model()
    candidate = module.fixture_candidate_choices()[0]

    result = module.execute_choice_branch(baseline, candidate, is_in_range=False)

    assert result.classification not in {
        "PENDING_AUTHORITY_EXECUTION",
        "PENDING_SIMING_OBSERVATION",
        "MAINLINE_IMPACT_DETECTED",
    }
    assert result.matched_deviation_id == "player_inspects_letter"
    assert any(event["event_type"] == "player.interaction.requested" for event in result.authority_events)
    assert not any(event["event_type"] == "esm_result_event" for event in result.authority_events)
    assert not any(event["event_type"] == "world.object_state.changed" for event in result.authority_events)
    assert any(item["result_type"] == "constraint_state_result" for item in result.esm_results)
    assert not any(item["result_type"] == "object_state_result" for item in result.esm_results)


def test_execute_choice_branch_returns_no_impact_when_authority_accepts_without_branch_diff() -> None:
    module = load_module()
    baseline = module.fixture_baseline_model()
    baseline["objects"][0]["state"]["possession"] = "char_a"
    candidate = module.fixture_candidate_choices()[2]

    result = module.execute_choice_branch(baseline, candidate)

    assert result.classification == "EVOLVABLE_NO_IMPACT"
    assert result.branch_diff == []
    assert result.matched_deviation_id == ""
    assert "no allowed branch diff" in result.notes
    assert any(event["event_type"] == "player.interaction.requested" for event in result.authority_events)
    assert not any(event["event_type"] == "esm_result_event" for event in result.authority_events)
    assert not any(event["event_type"] == "world.object_state.changed" for event in result.authority_events)
    assert any(item["result_type"] == "action_resolution_result" for item in result.esm_results)
    assert not any(item["result_type"] == "object_state_result" for item in result.esm_results)


def test_run_choice_pipeline_requires_siming_observation_for_mainline_impact() -> None:
    module = load_module()
    baseline = module.fixture_baseline_model()
    candidate = module.fixture_candidate_choices()[0]

    result = module.run_choice_pipeline(baseline, candidate)

    assert result.classification in {"MAINLINE_IMPACT_DETECTED", "SIMING_INTERVENTION_PROPOSED"}
    assert result.siming_evidence["observed"] is True
    assert int(result.siming_evidence["output_count"]) >= 1
    assert int(result.siming_evidence["audit_count"]) >= 1
    assert int(result.siming_evidence["observation_evidence_count"]) >= 1


def test_run_choice_pipeline_uses_all_branch_esm_result_events_for_siming() -> None:
    module = load_module()
    baseline = module.fixture_baseline_model()
    candidate = module.fixture_candidate_choices()[0]
    executed = module.execute_choice_branch(baseline, candidate)
    esm_events = [event for event in executed.authority_events if event["event_type"] == "esm_result_event"]
    captured_source_event_ids: list[str] = []

    class FakeOutput:
        def __init__(self, source_event_id: str) -> None:
            self.output_type = "visual_fact_dispatch"
            self.selected_path = "visual_fact_path"
            self.intervention_band = "fact_reveal"
            self._source_event_id = source_event_id

        def model_dump(self) -> dict[str, object]:
            return {
                "output_type": self.output_type,
                "selected_path": self.selected_path,
                "intervention_band": self.intervention_band,
                "source_event_id": self._source_event_id,
            }

    class FakeAuditRecord:
        def __init__(self, source_event_id: str) -> None:
            self._source_event_id = source_event_id

        def model_dump(self) -> dict[str, object]:
            return {
                "status": "recorded",
                "reason": "captured all branch esm result events",
                "source_event_id": self._source_event_id,
            }

    class FakeRuntime:
        def tick(self, inputs: list[object]) -> SimpleNamespace:
            nonlocal captured_source_event_ids
            captured_source_event_ids = [siming_input.source_event.event_id for siming_input in inputs]
            return SimpleNamespace(
                outputs=[FakeOutput(source_event_id) for source_event_id in captured_source_event_ids],
                audit_records=[FakeAuditRecord(source_event_id) for source_event_id in captured_source_event_ids],
            )

    module.SimingRuntime = FakeRuntime

    result = module.run_choice_pipeline(baseline, candidate)

    assert len(executed.branch_diff) == 2
    assert len(esm_events) == 2
    assert captured_source_event_ids == [event["event_id"] for event in esm_events]
    assert result.classification in {"MAINLINE_IMPACT_DETECTED", "SIMING_INTERVENTION_PROPOSED"}
    assert int(result.siming_evidence["source_event_count"]) == 2
    assert result.siming_evidence["source_event_ids"] == captured_source_event_ids


def test_run_choice_pipeline_keeps_no_impact_and_prior_event_classifications() -> None:
    module = load_module()
    baseline = module.fixture_baseline_model()
    choices = module.fixture_candidate_choices()

    result_b = module.run_choice_pipeline(baseline, choices[1])
    result_c = module.run_choice_pipeline(baseline, choices[2])

    assert result_b.classification == "EVOLVABLE_NO_IMPACT"
    assert result_b.siming_evidence == {}
    assert result_c.classification == "NEEDS_PRIOR_EVENT"
    assert result_c.siming_evidence == {}


def test_attach_siming_evidence_marks_missing_source_event_as_explicit_observation_failure() -> None:
    module = load_module()
    pending = module.ChoiceResult(
        choice_id="A",
        source_text="inspect the letter",
        classification="PENDING_SIMING_OBSERVATION",
        branch_diff=[{"path": "objects.obj_letter.visibility_state", "from": "partially_visible", "to": "visible"}],
        authority_events=[{"event_type": "player.interaction.requested", "payload": {"choice_id": "A"}}],
        esm_results=[{"result_type": "object_state_result"}],
    )

    result = module.attach_siming_evidence(pending)

    assert result.classification == "SIMING_OBSERVATION_MISSING"
    assert "missing authority event" in result.notes
    assert result.siming_evidence == {}


def test_attach_siming_evidence_does_not_treat_fairness_snapshot_only_as_observed_impact() -> None:
    module = load_module()

    class FakeOutput:
        def __init__(self, *, output_type: str, selected_path: str, intervention_band: str) -> None:
            self.output_type = output_type
            self.selected_path = selected_path
            self.intervention_band = intervention_band

        def model_dump(self) -> dict[str, object]:
            return {
                "output_type": self.output_type,
                "selected_path": self.selected_path,
                "intervention_band": self.intervention_band,
            }

    class FakeRuntime:
        def tick(self, _inputs: list[object]) -> SimpleNamespace:
            return SimpleNamespace(
                outputs=[
                    FakeOutput(
                        output_type="fairness_snapshot",
                        selected_path="no_action",
                        intervention_band="none",
                    )
                ],
                audit_records=[],
            )

    module.SimingRuntime = FakeRuntime
    baseline = module.fixture_baseline_model()
    candidate = module.fixture_candidate_choices()[0]

    result = module.run_choice_pipeline(baseline, candidate)

    assert result.classification == "PENDING_SIMING_OBSERVATION"
    assert result.siming_evidence["observed"] is False
    assert int(result.siming_evidence["output_count"]) == 1
    assert int(result.siming_evidence["observed_output_count"]) == 0
    assert int(result.siming_evidence["observation_evidence_count"]) == 0


def test_cli_component_mode_writes_bilingual_reports() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/verification/verify_script_evolution.py",
            "--component-only",
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0
    assert "自然语言剧本选择演化证明 / Natural Language Script Choice Evolution Proof" in result.stdout
    assert "剧本路径(script_path)=" in result.stdout
    assert "选择输入路径(choices_path)=" in result.stdout
    assert "剧本归一化(script_normalize)=fixture" in result.stdout
    assert "[选项 A / CHOICE A]" in result.stdout
    assert "判定(result)=主线影响已检测 / MAINLINE_IMPACT_DETECTED" in result.stdout or (
        "判定(result)=司命已提出干预 / SIMING_INTERVENTION_PROPOSED" in result.stdout
    )
    assert "判定(result)=可演化但未影响主线 / EVOLVABLE_NO_IMPACT" in result.stdout
    assert "判定(result)=需要前置事件 / NEEDS_PRIOR_EVENT" in result.stdout
    assert "主线可演化(mainline_evolvable)=True" in result.stdout
    assert "结果=通过 / result=PASS" in result.stdout
    assert "[CHOICE A]" not in result.stdout
    assert "MAINLINE_IMPACT_DETECTED" in result.stdout or "SIMING_INTERVENTION_PROPOSED" in result.stdout
    assert "EVOLVABLE_NO_IMPACT" in result.stdout
    assert "NEEDS_PRIOR_EVENT" in result.stdout

    report_path = PROJECT_ROOT / ".harness" / "verification" / "script-evolution-proof-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overall_script_evolution_passed"] is True
    assert report["mainline_evolvable"] is True
    assert report["summary_zh"] == "通过：至少一个玩家选择触发了可观察的主线影响，证明主线可以演化。"
    assert len(report["choices"]) == 3
    assert report["choices"][0]["classification_zh"] in {"主线影响已检测", "司命已提出干预"}
    assert report["choices"][1]["classification_zh"] == "可演化但未影响主线"
    assert report["choices"][2]["classification_zh"] == "需要前置事件"

    markdown_path = PROJECT_ROOT / ".harness" / "verification" / "script-evolution-proof-report.md"
    markdown = markdown_path.read_text(encoding="utf-8")
    assert markdown.startswith("# 自然语言剧本选择演化证明 / Natural Language Script Choice Evolution Proof")
    assert "- 总体结果(Overall): `True`" in markdown
    assert "- 主线可演化(Mainline Evolvable): `True`" in markdown
    assert "| 选项 Choice | 判定 Classification | 中文判定 | 说明 Notes |" in markdown
    assert "主线影响已检测" in markdown or "司命已提出干预" in markdown
    assert "可演化但未影响主线" in markdown
    assert "需要前置事件" in markdown


def test_cli_no_args_uses_default_fixtures_and_fails_without_api_key() -> None:
    env = dict(os.environ)
    env["SIMING_LLM_API_KEY"] = ""
    env["SIMING_LLM_ENDPOINT"] = "https://api.deepseek.com/chat/completions"
    env["SIMING_LLM_MODEL"] = "deepseek-chat"
    report_path = PROJECT_ROOT / ".harness" / "verification" / "script-evolution-proof-report.json"
    if report_path.exists():
        report_path.unlink()

    result = subprocess.run(
        [
            sys.executable,
            "scripts/verification/verify_script_evolution.py",
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )

    assert result.returncode == 1
    assert "DEEPSEEK_UNAVAILABLE" in result.stdout
    assert str(SCRIPT_FIXTURE_PATH) in result.stdout
    assert str(CHOICES_FIXTURE_PATH) in result.stdout

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overall_script_evolution_passed"] is False
    assert report["script_path"] == str(SCRIPT_FIXTURE_PATH)
    assert report["choices_path"] == str(CHOICES_FIXTURE_PATH)
    assert report["normalization"]["live_deepseek"] is True
    assert report["normalization"]["script_normalize"] == "deepseek_chat"
    assert report["normalization"]["choices_normalize"] == "deepseek_chat"
    assert "SIMING_LLM_API_KEY" in report["normalization"]["error"]


def test_cli_component_mode_uses_supplied_input_files(tmp_path: Path) -> None:
    module = load_module()
    script_path = tmp_path / "custom-script.md"
    choices_path = tmp_path / "custom-choices.txt"
    first_choice_body = module.fixture_candidate_choices()[0]["source_text"]
    script_path.write_text(
        SCRIPT_FIXTURE_PATH.read_text(encoding="utf-8") + "\nCustom proof variant line.\n",
        encoding="utf-8",
    )
    choices_path.write_text(f"A. {first_choice_body}", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/verification/verify_script_evolution.py",
            "--script",
            str(script_path),
            "--choices",
            str(choices_path),
            "--component-only",
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert "Natural Language Script Choice Evolution Proof" in result.stdout
    report_path = PROJECT_ROOT / ".harness" / "verification" / "script-evolution-proof-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["script_path"] == str(script_path)
    assert report["choices_path"] == str(choices_path)
    assert len(report["candidate_choices"]) == 1
    candidate_choice = report["candidate_choices"][0]
    assert candidate_choice["choice_id"] == "A"
    assert candidate_choice["source_text"] == first_choice_body
    assert candidate_choice["event_type"] == "player_interaction"
    assert candidate_choice["interaction_type"] == "inspect"
    assert candidate_choice["actor_ref"] == "char_a"


def test_cli_component_mode_rejects_supplied_script_validation_failure(tmp_path: Path) -> None:
    script_path = tmp_path / "invalid-script.md"
    choices_path = tmp_path / "custom-choices.txt"
    report_path = PROJECT_ROOT / ".harness" / "verification" / "script-evolution-proof-report.json"
    if report_path.exists():
        report_path.unlink()
    script_path.write_text(
        "\n".join(
            [
                "# Invalid proof script",
                "",
                "Only one line is present, so the required fragments are missing.",
            ]
        ),
        encoding="utf-8",
    )
    choices_path.write_text("A. Inspect the old letter.", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/verification/verify_script_evolution.py",
            "--script",
            str(script_path),
            "--choices",
            str(choices_path),
            "--component-only",
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode != 0
    assert "Traceback" not in result.stdout
    assert "自然语言剧本选择演化证明 / Natural Language Script Choice Evolution Proof" in result.stdout
    assert str(script_path) in result.stdout
    assert str(choices_path) in result.stdout
    assert "missing fragment: old letter exists on desk" in result.stdout

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overall_script_evolution_passed"] is False
    assert report["mainline_evolvable"] is False
    assert report["script_path"] == str(script_path)
    assert report["choices_path"] == str(choices_path)
    assert report["normalization"]["error"] == "baseline normalization failed: missing fragment: old letter exists on desk"


def test_cli_component_mode_rejects_missing_supplied_script_file(tmp_path: Path) -> None:
    script_path = tmp_path / "missing-script.md"
    choices_path = tmp_path / "custom-choices.txt"
    report_path = PROJECT_ROOT / ".harness" / "verification" / "script-evolution-proof-report.json"
    if report_path.exists():
        report_path.unlink()
    choices_path.write_text("A. Inspect the old letter.", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/verification/verify_script_evolution.py",
            "--script",
            str(script_path),
            "--choices",
            str(choices_path),
            "--component-only",
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode != 0
    assert "Traceback" not in result.stdout
    assert "自然语言剧本选择演化证明 / Natural Language Script Choice Evolution Proof" in result.stdout
    assert str(script_path) in result.stdout
    assert str(choices_path) in result.stdout
    assert "No such file" in result.stdout or "cannot find the file" in result.stdout.lower()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overall_script_evolution_passed"] is False
    assert report["mainline_evolvable"] is False
    assert report["script_path"] == str(script_path)
    assert report["choices_path"] == str(choices_path)
    assert "file" in report["normalization"]["error"].lower()


def test_live_deepseek_without_key_fails_bilingually() -> None:
    env = dict(os.environ)
    env["SIMING_LLM_API_KEY"] = ""
    env["SIMING_LLM_ENDPOINT"] = "https://api.deepseek.com/chat/completions"
    env["SIMING_LLM_MODEL"] = "deepseek-chat"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/verification/verify_script_evolution.py",
            "--script",
            ".harness/fixtures/script-evolution/demo-script.md",
            "--choices",
            ".harness/fixtures/script-evolution/demo-choices.txt",
            "--live-deepseek",
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )

    assert result.returncode == 1
    assert "DEEPSEEK_UNAVAILABLE" in result.stdout
    report_path = PROJECT_ROOT / ".harness" / "verification" / "script-evolution-proof-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overall_script_evolution_passed"] is False
    assert "SIMING_LLM_API_KEY" in report["normalization"]["error"]


def test_deepseek_request_uses_backend_config_when_process_env_is_unset(monkeypatch) -> None:
    module = load_module()
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback) -> None:
            return None

        def read(self) -> bytes:
            return b'{"choices":[]}'

    def fake_urlopen(request, timeout: float):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.delenv("SIMING_LLM_API_KEY", raising=False)
    monkeypatch.delenv("SIMING_LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("SIMING_LLM_MODEL", raising=False)
    monkeypatch.delenv("SIMING_LLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setattr(
        module,
        "backend_settings",
        SimpleNamespace(
            siming_llm_api_key="config-key",
            siming_llm_endpoint="https://api.deepseek.com/chat/completions",
            siming_llm_model="deepseek-chat",
            siming_llm_timeout_seconds=7.0,
        ),
        raising=False,
    )
    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    response = module._deepseek_request([{"role": "user", "content": "ping"}])

    assert response == {"choices": []}
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer config-key"
    assert captured["payload"]["model"] == "deepseek-chat"
    assert captured["timeout"] == 7.0


def test_normalize_with_deepseek_sends_expected_choice_ids_to_model(monkeypatch) -> None:
    module = load_module()
    script_text = SCRIPT_FIXTURE_PATH.read_text(encoding="utf-8")
    choices_text = CHOICES_FIXTURE_PATH.read_text(encoding="utf-8")
    baseline = module.fixture_baseline_model()
    valid_choices = module.fixture_candidate_choices()
    captured_messages: list[list[dict[str, str]]] = []
    responses = iter(
        [
            {"choices": [{"message": {"content": json.dumps(baseline, ensure_ascii=False)}}]},
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"choices": valid_choices}, ensure_ascii=False)
                        }
                    }
                ]
            },
        ]
    )

    def fake_deepseek_request(messages: list[dict[str, str]]) -> dict[str, object]:
        captured_messages.append(messages)
        return next(responses)

    monkeypatch.setattr(module, "_deepseek_request", fake_deepseek_request)

    module.normalize_with_deepseek(script_text, choices_text)

    choice_request = captured_messages[1]
    system_prompt = choice_request[0]["content"]
    user_payload = json.loads(choice_request[1]["content"])
    assert "choice_id" in system_prompt
    assert "event_type" in system_prompt
    assert "actor_ref" in system_prompt
    assert "target_ref" in system_prompt
    assert "interaction_type" in system_prompt
    assert "normalization_notes" in system_prompt
    assert "A, B, C" in system_prompt
    assert user_payload["expected_choice_ids"] == ["A", "B", "C"]


def test_normalize_with_deepseek_sends_stable_baseline_schema_to_model(monkeypatch) -> None:
    module = load_module()
    script_text = SCRIPT_FIXTURE_PATH.read_text(encoding="utf-8")
    choices_text = CHOICES_FIXTURE_PATH.read_text(encoding="utf-8")
    baseline = module.fixture_baseline_model()
    valid_choices = module.fixture_candidate_choices()
    captured_messages: list[list[dict[str, str]]] = []
    responses = iter(
        [
            {"choices": [{"message": {"content": json.dumps(baseline, ensure_ascii=False)}}]},
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"choices": valid_choices}, ensure_ascii=False)
                        }
                    }
                ]
            },
        ]
    )

    def fake_deepseek_request(messages: list[dict[str, str]]) -> dict[str, object]:
        captured_messages.append(messages)
        return next(responses)

    monkeypatch.setattr(module, "_deepseek_request", fake_deepseek_request)

    module.normalize_with_deepseek(script_text, choices_text)

    script_prompt = captured_messages[0][0]["content"]
    assert "actor_id" in script_prompt
    assert "char_a" in script_prompt
    assert "char_b" in script_prompt
    assert "object_id" in script_prompt
    assert "obj_letter" in script_prompt
    assert "visibility_state" in script_prompt
    assert "interaction_state" in script_prompt
    assert "allowed_deviations" in script_prompt
    assert "prior_event_requirements" in script_prompt


def test_chapter_mode_auto_choices_writes_full_chain_logs(tmp_path: Path, monkeypatch, capsys) -> None:
    module = load_module()
    script_path = tmp_path / "chapter.txt"
    choices_path = tmp_path / "unused-choices.txt"
    script_path.write_text(
        "刘世民醒在成都宫中，读到街亭军报，决定亲自改变北伐走向。",
        encoding="utf-8",
    )
    baseline = {
        "script_id": "liushimin_jigu_chapter",
        "mainline_summary": "刘世民意识到街亭将败，准备改变北伐主线。",
        "actors": [
            {"id": "liu_shimin", "name": "刘世民", "title": "占据刘禅身体的李世民。"},
            {"id": "guan_xing", "name": "关兴", "title": "年轻侍中，被皇帝的气势推动。"},
        ],
        "objects": [
            {
                "object_id": "node_jigu_campaign",
                "summary": "箕谷疑兵是否被改造成主攻方向。",
                "state": {
                    "command_state": "undecided",
                    "morale_state": "uncertain",
                },
            },
            {
                "object_id": "node_court_stability",
                "summary": "成都朝廷是否接受皇帝突然亲征。",
                "state": {
                    "coordination_state": "unprepared",
                },
            },
        ],
        "locked_facts": [
            {"fact_id": "street_pavilion_is_urgent", "summary": "街亭危机已经迫近。"}
        ],
        "allowed_deviations": [
            {
                "deviation_id": "imperial_redirect_to_jigu",
                "trigger_family": "player_strategy",
                "target_object_id": "node_jigu_campaign",
                "interaction_type": "redirect_campaign",
                "may_change": [
                    {
                        "path": "objects.node_jigu_campaign.command_state",
                        "from": "undecided",
                        "to": "imperial_redirect",
                    },
                    {
                        "path": "objects.node_jigu_campaign.morale_state",
                        "from": "uncertain",
                        "to": "rising",
                    },
                ],
                "must_preserve_locked_facts": ["street_pavilion_is_urgent"],
            },
            {
                "deviation_id": "stabilize_court_before_departure",
                "trigger_family": "player_strategy",
                "target_object_id": "node_court_stability",
                "interaction_type": "summon_ministers",
                "may_change": [
                    {
                        "path": "objects.node_court_stability.coordination_state",
                        "from": "unprepared",
                        "to": "delegated",
                    }
                ],
                "must_preserve_locked_facts": ["street_pavilion_is_urgent"],
            },
        ],
        "prior_event_requirements": [
            {
                "requirement_id": "must_redirect_before_rescue_jieting",
                "summary": "必须先确立箕谷改向，才能立刻改写街亭救援。",
                "interaction_type": "rescue_jieting",
                "target_object_id": "node_jigu_campaign",
                "required_state": {
                    "objects.node_jigu_campaign.command_state": "imperial_redirect"
                },
            }
        ],
    }
    choices = [
        {
            "choice_id": "A",
            "source_text": "玩家命刘世民立刻赶赴箕谷，把疑兵改造成主攻。",
            "event_type": "player_strategy",
            "actor_ref": "liu_shimin",
            "intent_type": "interact_intent",
            "target_ref": "guan_xing",
            "interaction_type": "command",
            "confidence": 0.93,
            "evidence": ["箕谷", "疑兵也是主力"],
            "normalization_notes": "directly targets the chapter's military turning point",
        },
        {
            "choice_id": "B",
            "source_text": "玩家让关兴召集郭攸之、董允、向宠稳定成都政务。",
            "event_type": "player_strategy",
            "actor_ref": "guan_xing",
            "intent_type": "interact_intent",
            "target_ref": "node_court_stability",
            "interaction_type": "summon_ministers",
            "confidence": 0.88,
            "evidence": ["这些人交给你了"],
            "normalization_notes": "delegates court stabilization before departure",
        },
        {
            "choice_id": "C",
            "source_text": "玩家要求马上改写街亭救援命令。",
            "event_type": "player_strategy",
            "actor_ref": "liu_shimin",
            "intent_type": "interact_intent",
            "target_ref": "node_jigu_campaign",
            "interaction_type": "rescue_jieting",
            "confidence": 0.81,
            "evidence": ["街亭一战，马谡必败"],
            "normalization_notes": "requires a prior campaign redirect in the backend state",
        },
    ]
    responses = iter(
        [
            {"choices": [{"message": {"content": json.dumps(baseline, ensure_ascii=False)}}]},
            {"choices": [{"message": {"content": json.dumps({"choices": choices}, ensure_ascii=False)}}]},
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "projections": [
                                        {
                                            "choice_id": "A",
                                            "impacted_mainline_node": "箕谷疑兵转为主动牵制",
                                            "original_mainline_direction": "赵云疑兵仍是牵制，街亭危机继续逼近。",
                                            "evolved_mainline_direction": "刘世民亲赴箕谷后，疑兵士气上升并形成主动牵制。",
                                            "followup_nodes": [
                                                "曹真需要重新判断箕谷兵力性质",
                                                "街亭方向获得更长反应窗口",
                                                "诸葛亮主力可以调整北伐节奏",
                                            ],
                                            "locked_fact_constraints": ["街亭危机已经迫近。"],
                                            "evolvable": True,
                                            "projection_notes": "Projection consumes backend branch_diff and does not decide proof status.",
                                        },
                                        {
                                            "choice_id": "B",
                                            "impacted_mainline_node": "成都后方协调",
                                            "original_mainline_direction": "成都政务尚未准备承接皇帝突然亲征。",
                                            "evolved_mainline_direction": "关兴承担联络任务，后方协调状态改为 delegated。",
                                            "followup_nodes": [
                                                "郭攸之、董允、向宠接管后方秩序",
                                                "御驾亲征的政治阻力下降",
                                            ],
                                            "locked_fact_constraints": ["街亭危机已经迫近。"],
                                            "evolvable": True,
                                            "projection_notes": "Support branch still changes the mainline support conditions.",
                                        },
                                    ]
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        ]
    )

    monkeypatch.setattr(module, "_deepseek_request", lambda _messages: next(responses))

    report = module.run_proof(
        script_path,
        choices_path,
        live_deepseek=True,
        chapter_mode=True,
        auto_choices=True,
        full_chain_log=True,
    )

    assert report["mode"] == "chapter"
    assert report["choices_source"] == "deepseek_auto"
    assert report["overall_script_evolution_passed"] is True
    assert report["summary_zh"].startswith("通过：")
    assert report["normalization"]["script_normalize"] == "deepseek_chapter"
    assert report["normalization"]["choices_normalize"] == "deepseek_auto_choices"
    assert {actor["actor_id"] for actor in report["baseline_model"]["actors"]} == {"liu_shimin", "guan_xing"}
    assert report["candidate_choices"][0]["target_ref"] == "node_jigu_campaign"
    assert report["candidate_choices"][0]["interaction_type"] == "redirect_campaign"
    assert report["candidate_choices"][0]["contract_alignment"]["aligned"] is True
    assert len(report["chain_trace"]) >= 7
    assert len(report["choices"]) == 3
    assert report["choices"][0]["classification"] in {
        "MAINLINE_IMPACT_DETECTED",
        "SIMING_INTERVENTION_PROPOSED",
    }
    assert report["choices"][0]["full_chain"]["authority_event_count"] >= 3
    assert report["choices"][0]["full_chain"]["esm_result_count"] >= 2
    assert report["choices"][0]["full_chain"]["branch_diff_count"] >= 1
    assert report["choices"][0]["full_chain"]["siming_observed"] is True
    assert report["choices"][0]["mainline_projection"]["impacted_mainline_node"] == "箕谷疑兵转为主动牵制"
    assert "街亭方向获得更长反应窗口" in report["choices"][0]["mainline_projection"]["followup_nodes"]
    assert report["choices"][0]["mainline_projection"]["evolvable"] is True
    assert report["choices"][1]["mainline_projection"]["impacted_mainline_node"] == "成都后方协调"
    assert report["choices"][2]["classification"] == "NEEDS_PRIOR_EVENT"
    assert report["choices"][2]["mainline_projection"]["evolvable"] is False

    report_md = PROJECT_ROOT / ".harness" / "verification" / "chapter-evolution-full-chain-report.md"
    events_jsonl = PROJECT_ROOT / ".harness" / "verification" / "chapter-evolution-events.jsonl"
    assert report_md.exists()
    assert events_jsonl.exists()
    markdown = report_md.read_text(encoding="utf-8")
    assert "# 章节级主线演化完整链路证明 / Chapter Evolution Full Chain Proof" in markdown
    assert "完整链路阶段" in markdown
    assert "DeepSeek 章节归一化" in markdown
    assert "后端权威事件" in markdown
    assert "ESM 结果" in markdown
    assert "司命观察" in markdown
    assert "后续主线演化" in markdown
    assert "箕谷疑兵转为主动牵制" in markdown
    assert "街亭方向获得更长反应窗口" in markdown
    assert "world.object_state.changed" in markdown
    assert "action_resolution_result" in markdown
    assert "objects.node_jigu_campaign.command_state: undecided -> imperial_redirect" in markdown

    events = [json.loads(line) for line in events_jsonl.read_text(encoding="utf-8").splitlines()]
    stages = {event["stage"] for event in events}
    assert {
        "input_loaded",
        "deepseek_chapter_normalized",
        "deepseek_auto_choices_generated",
        "choice_backend_classified",
        "choice_authority_events",
        "choice_esm_results",
        "choice_branch_diff",
        "choice_siming_evidence",
        "choice_mainline_projected",
        "proof_completed",
    }.issubset(stages)
    authority_event = next(
        event for event in events if event["stage"] == "choice_authority_events" and event["payload"]["choice_id"] == "A"
    )
    esm_event = next(
        event for event in events if event["stage"] == "choice_esm_results" and event["payload"]["choice_id"] == "A"
    )
    diff_event = next(
        event for event in events if event["stage"] == "choice_branch_diff" and event["payload"]["choice_id"] == "A"
    )
    siming_event = next(
        event for event in events if event["stage"] == "choice_siming_evidence" and event["payload"]["choice_id"] == "A"
    )
    projection_event = next(
        event for event in events if event["stage"] == "choice_mainline_projected" and event["payload"]["choice_id"] == "A"
    )
    assert len(authority_event["payload"]["authority_events"]) >= 3
    assert any(item["event_type"] == "world.object_state.changed" for item in authority_event["payload"]["authority_events"])
    assert len(esm_event["payload"]["esm_results"]) >= 2
    assert any(item["result_type"] == "action_resolution_result" for item in esm_event["payload"]["esm_results"])
    assert diff_event["payload"]["branch_diff"] == report["choices"][0]["branch_diff"]
    assert siming_event["payload"]["siming_evidence"]["observed"] is True
    assert projection_event["payload"]["mainline_projection"]["impacted_mainline_node"] == "箕谷疑兵转为主动牵制"

    module._print_console(report)
    console = capsys.readouterr().out
    assert "后续主线演化(mainline_projection):" in console
    assert "Branch Diff:" in console
    assert "objects.node_jigu_campaign.command_state: undecided -> imperial_redirect" in console
    assert "影响主线节点=箕谷疑兵转为主动牵制" in console
    assert "新主线走向=刘世民亲赴箕谷后，疑兵士气上升并形成主动牵制。" in console
    assert "后续剧情节点=" in console


def test_deepseek_content_accepts_top_level_json_array_as_choices_payload() -> None:
    module = load_module()
    choices = module.fixture_candidate_choices()
    payload = {"choices": [{"message": {"content": json.dumps(choices, ensure_ascii=False)}}]}

    parsed = module._deepseek_content(payload)

    assert parsed == {"choices": choices}


def test_normalize_with_deepseek_accepts_label_keyed_choice_object(monkeypatch) -> None:
    module = load_module()
    script_text = SCRIPT_FIXTURE_PATH.read_text(encoding="utf-8")
    choices_text = CHOICES_FIXTURE_PATH.read_text(encoding="utf-8")
    baseline = module.fixture_baseline_model()
    choices_by_label = {choice["choice_id"]: choice for choice in module.fixture_candidate_choices()}
    responses = iter(
        [
            {"choices": [{"message": {"content": json.dumps(baseline, ensure_ascii=False)}}]},
            {"choices": [{"message": {"content": json.dumps(choices_by_label, ensure_ascii=False)}}]},
        ]
    )

    monkeypatch.setattr(module, "_deepseek_request", lambda _messages: next(responses))

    _baseline, choices, _meta = module.normalize_with_deepseek(script_text, choices_text)

    assert [choice["choice_id"] for choice in choices] == ["A", "B", "C"]


def test_live_baseline_normalization_canonicalizes_backend_contract_shape() -> None:
    module = load_module()
    raw_baseline = {
        "script_id": "staging_letter",
        "mainline_summary": "角色A在书桌上发现一封旧信，尚未检查或带走。",
        "actors": [
            {"actor_id": "char_a", "summary": "角色A"},
            {"actor_id": "char_b", "summary": "角色B"},
        ],
        "objects": [
            {
                "object_id": "obj_letter",
                "summary": "旧信",
                "state": {
                    "location": "desk",
                    "visibility_state": "partially_visible",
                    "interaction_state": "unopened",
                    "possession": "desk",
                },
            }
        ],
        "locked_facts": [{"fact_id": "letter_unread", "summary": "旧信尚未被阅读"}],
        "allowed_deviations": [
            {"interaction_type": "inspect", "target_object_id": "obj_letter"},
            {"interaction_type": "take", "target_object_id": "obj_letter"},
        ],
        "prior_event_requirements": [
            "objects.obj_letter.possession == char_a before interaction_type=handoff to obj_letter"
        ],
    }

    baseline = module.canonicalize_live_baseline(raw_baseline)

    assert baseline["script_id"] == "staging_letter"
    assert {actor["actor_id"] for actor in baseline["actors"]} == {"char_a", "char_b"}
    assert baseline["objects"][0]["object_id"] == "obj_letter"
    deviations = {deviation["deviation_id"]: deviation for deviation in baseline["allowed_deviations"]}
    assert deviations["player_inspects_letter"]["may_change"] == [
        {
            "path": "objects.obj_letter.visibility_state",
            "from": "partially_visible",
            "to": "visible",
        },
        {
            "path": "objects.obj_letter.interaction_state",
            "from": "unopened",
            "to": "inspected",
        },
    ]
    assert deviations["player_takes_letter"]["may_change"] == [
        {
            "path": "objects.obj_letter.possession",
            "from": "desk",
            "to": "char_a",
        }
    ]
    assert baseline["prior_event_requirements"] == [
        {
            "requirement_id": "letter_must_be_held_before_handing_to_b",
            "summary": "角色 A must hold obj_letter before handing it to char_b.",
            "interaction_type": "handoff",
            "target_object_id": "obj_letter",
            "required_state": {"objects.obj_letter.possession": "char_a"},
        }
    ]


def test_normalize_with_deepseek_rejects_partial_or_reordered_choice_lists(monkeypatch) -> None:
    module = load_module()
    script_text = SCRIPT_FIXTURE_PATH.read_text(encoding="utf-8")
    choices_text = CHOICES_FIXTURE_PATH.read_text(encoding="utf-8")
    baseline = module.fixture_baseline_model()
    valid_choices = module.fixture_candidate_choices()

    invalid_payloads = [
        valid_choices[:2],
        [valid_choices[0], valid_choices[0], valid_choices[2]],
        [valid_choices[1], valid_choices[0], valid_choices[2]],
        valid_choices + [{**valid_choices[0], "choice_id": "D"}],
    ]

    for invalid_choices in invalid_payloads:
        responses = iter(
            [
                {"choices": [{"message": {"content": json.dumps(baseline, ensure_ascii=False)}}]},
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps({"choices": invalid_choices}, ensure_ascii=False)
                            }
                        }
                    ]
                },
            ]
        )

        monkeypatch.setattr(module, "_deepseek_request", lambda _messages, _responses=responses: next(_responses))

        with pytest.raises(RuntimeError, match="CHOICES_NORMALIZE_FAILED"):
            module.normalize_with_deepseek(script_text, choices_text)


def test_run_proof_live_deepseek_fails_when_deepseek_omits_choice_labels(monkeypatch) -> None:
    module = load_module()
    baseline = module.fixture_baseline_model()
    valid_choices = module.fixture_candidate_choices()
    responses = iter(
        [
            {"choices": [{"message": {"content": json.dumps(baseline, ensure_ascii=False)}}]},
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"choices": valid_choices[:2]}, ensure_ascii=False)
                        }
                    }
                ]
            },
        ]
    )

    monkeypatch.setattr(module, "_deepseek_request", lambda _messages: next(responses))

    with pytest.raises(RuntimeError, match="CHOICES_NORMALIZE_FAILED"):
        module.run_proof(SCRIPT_FIXTURE_PATH, CHOICES_FIXTURE_PATH, live_deepseek=True)


def test_script_evolution_profile_is_registered() -> None:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "verification"))
    import harness
    from registry import load_profile_registry

    registry = load_profile_registry(PROJECT_ROOT)

    assert "script-evolution-proof" in registry.profiles
    profile = registry.profiles["script-evolution-proof"]
    assert profile["script"] == "scripts/verification/verify_script_evolution.py"
    assert profile["requires_godot"] is False
    assert profile["include_in_all"] is False
    assert profile["result_artifact"] == ".harness/verification/script-evolution-proof-report.json"
    assert "script-evolution-proof" not in harness._profiles_for_selection("all", registry)
    assert harness._profiles_for_selection("script-evolution-proof", registry) == ["script-evolution-proof"]
