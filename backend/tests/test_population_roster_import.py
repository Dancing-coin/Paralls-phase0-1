from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from urllib.error import HTTPError, URLError

import pytest

from app.config import Settings
from app.gameplay.p5.scripted_mystery_content import stormnight_case_content
from app.population_continuity.roster import load_population_roster
from tools.production import population_roster as tool


def test_import_stormnight_preserves_all_versioned_actor_ids_without_private_truth():
    payload = stormnight_case_content().model_dump(mode="json")
    payload["truth_facts"] = [{"subject_refs": ["character:must-not-import@1"]}]
    payload["private_knowledge_sets"] = object()
    assert tool.import_roster(payload).actor_ids == (
        "stormnight-guardian@1", "stormnight-heir@1",
        "stormnight-investigator@1", "stormnight-physician@1",
    )


@pytest.mark.parametrize("payload", [
    {"actor_ids": ["alice", "bob@1"]},
    {"characters": [
        {"actor_id": "alice", "name": "爱丽丝", "aliases": ["小爱"]},
        {"actor_id": "bob@1", "name": "鲍勃", "aliases": []},
    ]},
])
def test_import_explicit_roster_and_character_table(payload):
    assert tool.import_roster(payload).actor_ids == ("alice", "bob@1")


@pytest.mark.parametrize("payload", [
    {"actor_refs": "character:alice"},
    {"actor_refs": ["object:alice"]},
    {"actor_refs": ["alice"]},
    {"actor_refs": ["character:alice", "character:alice"]},
    {"characters": []},
    {"characters": [{"actor_id": "../alice", "name": "爱丽丝"}]},
    {"actor_ids": ["alice"], "characters": []},
    {"truth_facts": [{"actor_id": "alice"}]},
])
def test_import_rejects_invalid_or_ambiguous_tables(payload):
    with pytest.raises(ValueError):
        tool.import_roster(payload)


def model_settings(**overrides):
    values = dict(
        non_runtime_model_mode="http",
        non_runtime_model_endpoint="https://example.invalid/v1/chat/completions",
        non_runtime_model_api_key="test-secret-do-not-print",
        non_runtime_model_model="test-roster-model",
        non_runtime_model_timeout_seconds=3,
    )
    return Settings(**(values | overrides))


def model_characters():
    return {"characters": [
        {"actor_id": "alice@1", "name": "爱丽丝", "aliases": ["小爱"],
         "evidence": ["爱丽丝，又称小爱，是镇上的医生。"]},
        {"actor_id": "bob", "name": "鲍勃", "aliases": [],
         "evidence": ["鲍勃是铁匠。"]},
    ]}


def write_script(tmp_path):
    source = tmp_path / "剧本.txt"
    source.write_text("爱丽丝，又称小爱，是镇上的医生。\n鲍勃是铁匠。", encoding="utf-8")
    return source


def fake_response(monkeypatch, payload):
    response = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(payload, ensure_ascii=False)}}]}
    monkeypatch.setattr(tool, "urlopen", lambda *args, **kwargs: BytesIO(json.dumps(response).encode()))


def test_analyze_and_explicit_approve_round_trip(tmp_path, monkeypatch):
    source = write_script(tmp_path)

    def transport(request, timeout):
        body = json.loads(request.data)
        assert request.full_url == "https://example.invalid/v1/chat/completions"
        assert request.get_header("Authorization") == "Bearer test-secret-do-not-print"
        assert body["model"] == "test-roster-model"
        assert body["messages"][-1]["content"] == source.read_bytes().decode("utf-8")
        assert timeout == 3
        return BytesIO(json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(model_characters())}}]}).encode())

    monkeypatch.setattr(tool, "urlopen", transport)
    monkeypatch.setattr(tool, "settings", model_settings())
    draft_path, output = tmp_path / "draft.json", tmp_path / "roster.json"
    assert tool.main(["analyze", str(source), "--output", str(draft_path)]) == 0
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    assert draft["kind"] == "population_roster_draft"
    assert draft["source_sha256"] == sha256(source.read_bytes()).hexdigest()
    assert draft["characters"] == model_characters()["characters"]
    with pytest.raises(ValueError):
        load_population_roster(draft_path)
    with pytest.raises(ValueError):
        tool.import_roster(draft)
    with pytest.raises(ValueError):
        tool.import_roster({key: value for key, value in draft.items() if key != "characters"} | {"actor_ids": ["alice"]})
    assert tool.main(["approve", str(draft_path), "--source", str(source), "--output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8")) == {"actor_ids": ["alice@1", "bob"]}
    assert load_population_roster(output).actor_ids == ("alice@1", "bob")


@pytest.mark.parametrize("override", [
    {"non_runtime_model_mode": "disabled"},
    {"non_runtime_model_mode": "local"},
    {"non_runtime_model_api_key": None},
    {"non_runtime_model_endpoint": "file:///tmp/model"},
    {"non_runtime_model_model": " "},
])
def test_analyze_requires_configured_http_provider(tmp_path, monkeypatch, override):
    def forbidden(*args, **kwargs):
        pytest.fail("未配置模型时不应发起网络请求")
    monkeypatch.setattr(tool, "urlopen", forbidden)
    with pytest.raises(ValueError, match="NON_RUNTIME_MODEL"):
        tool.analyze_script(write_script(tmp_path), model_settings(**override))


@pytest.mark.parametrize("payload", [
    {"characters": []},
    {"characters": [{"actor_id": "alice", "name": "爱丽丝", "aliases": [], "evidence": ["不存在的原文"]}]},
    {"characters": [{"actor_id": "alice", "name": "爱丽丝", "aliases": [], "evidence": [" "]}]},
    {"characters": [model_characters()["characters"][0]] * 2},
    {"characters": [{"actor_id": "alice", "name": "爱丽丝", "aliases": []}]},
    {"characters": model_characters()["characters"], "truth_facts": ["不能输出剧情真相"]},
])
def test_model_payload_requires_schema_unique_ids_and_verbatim_evidence(tmp_path, monkeypatch, payload):
    fake_response(monkeypatch, payload)
    with pytest.raises(ValueError):
        tool.analyze_script(write_script(tmp_path), model_settings())


@pytest.mark.parametrize("response", [b"not-json", b'{"choices":[]}', b'{"choices":[{"finish_reason":"stop","message":{"content":"not-json"}}]}'])
def test_invalid_provider_response_is_rejected(tmp_path, monkeypatch, response):
    monkeypatch.setattr(tool, "urlopen", lambda *args, **kwargs: BytesIO(response))
    with pytest.raises(ValueError, match="模型响应"):
        tool.analyze_script(write_script(tmp_path), model_settings())


@pytest.mark.parametrize("finish_reason", ["length", "content_filter", "tool_calls", None])
def test_incomplete_provider_response_cannot_become_a_draft(tmp_path, monkeypatch, finish_reason):
    response = {"choices": [{"finish_reason": finish_reason, "message": {"content": json.dumps(model_characters())}}]}
    monkeypatch.setattr(tool, "urlopen", lambda *args, **kwargs: BytesIO(json.dumps(response).encode()))
    with pytest.raises(ValueError, match="模型响应"):
        tool.analyze_script(write_script(tmp_path), model_settings())


@pytest.mark.parametrize("error", [
    HTTPError("https://example.invalid/test-secret-do-not-print", 401, "test-secret-do-not-print", {}, None),
    URLError("test-secret-do-not-print"),
])
def test_provider_error_does_not_leak_key_or_write_output(tmp_path, monkeypatch, capsys, error):
    def transport(*args, **kwargs):
        raise error
    monkeypatch.setattr(tool, "urlopen", transport)
    monkeypatch.setattr(tool, "settings", model_settings())
    output = tmp_path / "draft.json"
    with pytest.raises(SystemExit) as failure:
        tool.main(["analyze", str(write_script(tmp_path)), "--output", str(output)])
    assert failure.value.code == 2
    assert "test-secret-do-not-print" not in capsys.readouterr().err
    assert not output.exists()


def test_approve_rechecks_source_hash_and_edited_evidence(tmp_path, monkeypatch):
    source = write_script(tmp_path)
    fake_response(monkeypatch, model_characters())
    draft = tool.analyze_script(source, model_settings()).model_dump(mode="json")
    draft["characters"][0]["evidence"] = ["不在原文里的引用"]
    with pytest.raises(ValueError, match="原文"):
        tool.approve_draft(draft, source)
    draft["characters"][0]["evidence"] = model_characters()["characters"][0]["evidence"]
    source.write_text("已修改剧本", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA256"):
        tool.approve_draft(draft, source)


def test_cli_import_never_overwrites_source_or_existing_output(tmp_path):
    source = tmp_path / "characters.json"
    original = json.dumps({"characters": [{"actor_id": "alice", "name": "爱丽丝"}]})
    source.write_text(original, encoding="utf-8")
    output = tmp_path / "roster.json"
    assert tool.main(["import", str(source), "--output", str(output)]) == 0
    assert load_population_roster(output).actor_ids == ("alice",)
    for target in (source, output):
        before = target.read_bytes()
        with pytest.raises(SystemExit) as failure:
            tool.main(["import", str(source), "--output", str(target)])
        assert failure.value.code == 2
        assert target.read_bytes() == before
    assert source.read_text(encoding="utf-8") == original
