import argparse
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import sys
from typing import Literal
import urllib.error
import urllib.request


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings as backend_settings
from app.models.authority_event import AuthorityEvent
from app.models.player_input import InteractIntent
from app.models.siming_event import SimingInput
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.esm_service import ESMService
from app.services.phase0_authority_event_adapter import Phase0AuthorityEventAdapter
from app.services.siming_runtime import SimingRuntime
from common import repo_root, verification_dir, write_json


ChoiceClassification = Literal[
    "PENDING_AUTHORITY_EXECUTION",
    "PENDING_SIMING_OBSERVATION",
    "SIMING_OBSERVATION_MISSING",
    "CONSTRAINT_REJECTED",
    "SIMING_INTERVENTION_PROPOSED",
    "MAINLINE_IMPACT_DETECTED",
    "EVOLVABLE_NO_IMPACT",
    "REJECTED_BY_BASELINE",
    "NEEDS_PRIOR_EVENT",
    "NORMALIZATION_FAILED",
]


@dataclass
class BaselineModel:
    script_id: str
    mainline_summary: str
    actors: list[dict[str, object]]
    objects: list[dict[str, object]]
    locked_facts: list[dict[str, object]]
    allowed_deviations: list[dict[str, object]]
    prior_event_requirements: list[dict[str, object]]


@dataclass
class CandidateChoice:
    choice_id: str
    source_text: str
    event_type: str
    actor_ref: str
    intent_type: str
    target_ref: str
    interaction_type: str
    confidence: float
    evidence: list[str]
    normalization_notes: str
    secondary_target_ref: str = ""


@dataclass
class ChoiceResult:
    choice_id: str
    source_text: str
    classification: ChoiceClassification
    matched_deviation_id: str = ""
    notes: str = ""
    branch_diff: list[dict[str, object]] = field(default_factory=list)
    authority_events: list[dict[str, object]] = field(default_factory=list)
    esm_results: list[dict[str, object]] = field(default_factory=list)
    siming_evidence: dict[str, object] = field(default_factory=dict)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_FIXTURE_PATH = PROJECT_ROOT / ".harness" / "fixtures" / "script-evolution" / "demo-script.md"
CHOICES_FIXTURE_PATH = PROJECT_ROOT / ".harness" / "fixtures" / "script-evolution" / "demo-choices.txt"
REPORT_JSON = "script-evolution-proof-report.json"
REPORT_MD = "script-evolution-proof-report.md"
CHAPTER_REPORT_JSON = "chapter-evolution-full-chain-report.json"
CHAPTER_REPORT_MD = "chapter-evolution-full-chain-report.md"
CHAPTER_EVENTS_JSONL = "chapter-evolution-events.jsonl"
CLASSIFICATION_ZH: dict[str, str] = {
    "PENDING_AUTHORITY_EXECUTION": "等待后端权威执行",
    "PENDING_SIMING_OBSERVATION": "等待司命观察",
    "SIMING_OBSERVATION_MISSING": "司命观察缺失",
    "CONSTRAINT_REJECTED": "约束拒绝",
    "SIMING_INTERVENTION_PROPOSED": "司命已提出干预",
    "MAINLINE_IMPACT_DETECTED": "主线影响已检测",
    "EVOLVABLE_NO_IMPACT": "可演化但未影响主线",
    "REJECTED_BY_BASELINE": "被基线拒绝",
    "NEEDS_PRIOR_EVENT": "需要前置事件",
    "NORMALIZATION_FAILED": "归一化失败",
}
NOTES_ZH_BY_CLASSIFICATION: dict[str, str] = {
    "PENDING_AUTHORITY_EXECUTION": "玩家选择已通过基线检查，等待后端权威链路执行。",
    "PENDING_SIMING_OBSERVATION": "后端已产生世界分歧，等待司命观察或审计证据。",
    "SIMING_OBSERVATION_MISSING": "后端产生了世界分歧，但缺少可交给司命观察的权威事件。",
    "CONSTRAINT_REJECTED": "后端权威链路拒绝了该交互，没有应用世界分支变化。",
    "SIMING_INTERVENTION_PROPOSED": "世界分歧已被司命观察，并产生了类似干预的输出。",
    "MAINLINE_IMPACT_DETECTED": "世界分歧已被司命观察或审计，主线影响成立。",
    "EVOLVABLE_NO_IMPACT": "该选择可被后端处理，但没有触发允许的主线分支变化。",
    "REJECTED_BY_BASELINE": "该选择不符合剧本基线或允许偏移范围。",
    "NEEDS_PRIOR_EVENT": "该选择需要先发生前置事件，当前基线状态不足。",
    "NORMALIZATION_FAILED": "自然语言输入无法归一化为后端可执行事件。",
}

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def _non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _contains_any(text: str, fragments: list[str]) -> bool:
    return any(fragment in text for fragment in fragments)


def _require_semantic_fragment(text: str, fragments: list[str], message: str) -> None:
    if not _contains_any(text, fragments):
        raise ValueError(f"baseline normalization failed: {message}")


def _extract_mainline_summary(lines: list[str]) -> str:
    for line in lines:
        if line.startswith("当前主线中"):
            return line
    raise ValueError("baseline normalization failed: missing current mainline summary")


def normalize_baseline_fixture(script_text: str) -> dict[str, object]:
    lines = _non_empty_lines(script_text)
    normalized_text = " ".join(lines)

    _require_semantic_fragment(
        normalized_text,
        ["桌上放着一封旧信", "桌上有一封信", "桌上有一封旧信"],
        "missing fragment: old letter exists on desk",
    )
    _require_semantic_fragment(
        normalized_text,
        ["角色 A 站在书桌旁", "角色 A 只是看见了旧信", "已经注意到桌上有一封信"],
        "missing fragment: char_a sees or knows the letter exists",
    )
    _require_semantic_fragment(
        normalized_text,
        ["还没有打开", "尚未检查", "尚未打开", "尚未检查、打开或带走它", "没有打开"],
        "missing fragment: char_a has not opened or checked the letter",
    )
    _require_semantic_fragment(
        normalized_text,
        ["尚未检查、打开或带走它", "还没有带走", "未带走"],
        "missing fragment: char_a has not taken the letter",
    )
    _require_semantic_fragment(
        normalized_text,
        ["角色 B 在门外", "门外的角色 B", "角色 B 在门外，并不知道信里的内容"],
        "missing fragment: char_b is outside",
    )
    _require_semantic_fragment(
        normalized_text,
        ["并不知道信里的内容", "不知道信里的内容", "不知道信件内容"],
        "missing fragment: char_b does not know the letter content",
    )

    return {
        "script_id": "lamp_letter",
        "mainline_summary": _extract_mainline_summary(lines),
        "actors": [
            {"actor_id": "char_a", "summary": "站在书桌旁，知道旧信存在。"},
            {"actor_id": "char_b", "summary": "在门外，不知道信件内容。"},
        ],
        "objects": [
            {
                "object_id": "obj_letter",
                "summary": "桌上的旧信，半压在黑色笔记本下。",
                "state": {
                    "location": "desk",
                    "visibility_state": "partially_visible",
                    "interaction_state": "unopened",
                    "possession": "desk",
                },
            }
        ],
        "locked_facts": [
            {"fact_id": "fact_letter_exists", "summary": "桌上存在一封旧信。"},
            {
                "fact_id": "fact_char_b_does_not_know_letter_content",
                "summary": "角色 B 尚不知道信件内容。",
            },
        ],
        "allowed_deviations": [
            {
                "deviation_id": "player_inspects_letter",
                "trigger_family": "player_interaction",
                "target_object_id": "obj_letter",
                "interaction_type": "inspect",
                "may_change": [
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
                ],
                "must_preserve_locked_facts": [
                    "fact_letter_exists",
                    "fact_char_b_does_not_know_letter_content",
                ],
            },
            {
                "deviation_id": "player_takes_letter",
                "trigger_family": "player_interaction",
                "target_object_id": "obj_letter",
                "interaction_type": "take",
                "may_change": [
                    {
                        "path": "objects.obj_letter.possession",
                        "from": "desk",
                        "to": "char_a",
                    }
                ],
                "must_preserve_locked_facts": [
                    "fact_letter_exists",
                    "fact_char_b_does_not_know_letter_content",
                ],
            },
        ],
        "prior_event_requirements": [
            {
                "requirement_id": "letter_must_be_held_before_handing_to_b",
                "summary": "角色 A 必须先拿起旧信，才能把旧信交给角色 B。",
                "interaction_type": "handoff",
                "target_object_id": "obj_letter",
                "required_state": {"objects.obj_letter.possession": "char_a"},
            }
        ],
    }


def _normalized_failure_candidate(choice_id: str, body: str, notes: str) -> dict[str, object]:
    return {
        "choice_id": choice_id,
        "source_text": body,
        "event_type": "normalization_failed",
        "actor_ref": "",
        "intent_type": "",
        "target_ref": "",
        "interaction_type": "normalization_failed",
        "confidence": 0.0,
        "evidence": [],
        "normalization_notes": notes,
        "notes": notes,
    }


def _normalize_choice(choice_id: str, body: str) -> dict[str, object]:
    normalized_body = body.strip()

    if "旧信" in normalized_body and _contains_any(normalized_body, ["查看", "检查", "inspect", "看信"]):
        return {
            "choice_id": choice_id,
            "source_text": normalized_body,
            "event_type": "player_interaction",
            "actor_ref": "char_a",
            "intent_type": "interact_intent",
            "target_ref": "obj_letter",
            "interaction_type": "inspect",
            "confidence": 0.91,
            "evidence": ["旧信", "查看/检查"],
            "normalization_notes": "choice body indicates inspecting the old letter",
        }

    if _contains_any(normalized_body, ["离开书房", "离开", "走出书房", "退出书房"]):
        return {
            "choice_id": choice_id,
            "source_text": normalized_body,
            "event_type": "player_navigation",
            "actor_ref": "char_a",
            "intent_type": "move_intent",
            "target_ref": "room_exit",
            "interaction_type": "leave",
            "confidence": 0.86,
            "evidence": ["离开书房"],
            "normalization_notes": "choice body indicates leaving the study",
        }

    if (
        _contains_any(normalized_body, ["给", "交给", "递给", "hand"])
        and "信" in normalized_body
        and _contains_any(normalized_body, ["角色 B", "char_b", "门外"])
    ):
        return {
            "choice_id": choice_id,
            "source_text": normalized_body,
            "event_type": "player_interaction",
            "actor_ref": "char_a",
            "intent_type": "interact_intent",
            "target_ref": "obj_letter",
            "secondary_target_ref": "char_b",
            "interaction_type": "handoff",
            "confidence": 0.88,
            "evidence": ["信", "交给/递给", "角色 B"],
            "normalization_notes": "choice body indicates handing the letter to char_b",
        }

    return _normalized_failure_candidate(choice_id, normalized_body, "unrecognized choice body semantics")


def normalize_candidate_choices_fixture(choices_text: str) -> list[dict[str, object]]:
    compact_text = " ".join(_non_empty_lines(choices_text))
    matches = re.findall(r"([A-Z])\.\s*(.*?)(?=(?:[A-Z]\.\s)|$)", compact_text)
    expected_labels = [chr(ord("A") + index) for index in range(len(matches))]
    if [label for label, _ in matches] != expected_labels:
        raise ValueError("fixture choices must contain consecutively labeled options starting at A")

    return [_normalize_choice(label, body) for label, body in matches]


def _expected_choice_labels_from_text(choices_text: str) -> list[str]:
    compact_text = " ".join(_non_empty_lines(choices_text))
    matches = re.findall(r"([A-Z])\.\s*(.*?)(?=(?:[A-Z]\.\s)|$)", compact_text)
    labels = [label for label, _ in matches]
    expected_labels = [chr(ord("A") + index) for index in range(len(labels))]
    if not labels or labels != expected_labels:
        raise RuntimeError(
            "CHOICES_NORMALIZE_FAILED: supplied natural-language choices must use consecutive labels starting at A"
        )
    return labels


def fixture_baseline_model() -> dict[str, object]:
    return normalize_baseline_fixture(SCRIPT_FIXTURE_PATH.read_text(encoding="utf-8"))


def fixture_candidate_choices() -> list[dict[str, object]]:
    return normalize_candidate_choices_fixture(CHOICES_FIXTURE_PATH.read_text(encoding="utf-8"))


def canonicalize_live_baseline(baseline: dict[str, object]) -> dict[str, object]:
    canonical = dict(baseline)
    canonical["actors"] = _canonical_live_actors(baseline)
    canonical["objects"] = _canonical_live_objects(baseline)
    canonical["locked_facts"] = _canonical_live_locked_facts(baseline)
    canonical["allowed_deviations"] = _canonical_letter_deviations()
    canonical["prior_event_requirements"] = [_canonical_handoff_requirement()]
    return canonical


def _canonical_live_actors(baseline: dict[str, object]) -> list[dict[str, object]]:
    raw_actors = baseline.get("actors", [])
    actors = [actor for actor in raw_actors if isinstance(actor, dict)] if isinstance(raw_actors, list) else []
    by_id = {str(actor.get("actor_id", "")): actor for actor in actors}
    return [
        {
            "actor_id": "char_a",
            "summary": str(by_id.get("char_a", {}).get("summary", "Role A near the study desk.")),
        },
        {
            "actor_id": "char_b",
            "summary": str(by_id.get("char_b", {}).get("summary", "Role B outside the study.")),
        },
    ]


def _canonical_live_objects(baseline: dict[str, object]) -> list[dict[str, object]]:
    raw_objects = baseline.get("objects", [])
    objects = [item for item in raw_objects if isinstance(item, dict)] if isinstance(raw_objects, list) else []
    by_id = {str(item.get("object_id", "")): item for item in objects}
    letter = by_id.get("obj_letter", {})
    raw_state = letter.get("state", {}) if isinstance(letter, dict) else {}
    state = raw_state if isinstance(raw_state, dict) else {}
    return [
        {
            "object_id": "obj_letter",
            "summary": str(letter.get("summary", "Old letter on the desk.")) if isinstance(letter, dict) else "Old letter on the desk.",
            "state": {
                "location": str(state.get("location", "desk")),
                "visibility_state": str(state.get("visibility_state", "partially_visible")),
                "interaction_state": str(state.get("interaction_state", "unopened")),
                "possession": str(state.get("possession", "desk")),
            },
        }
    ]


def _canonical_live_locked_facts(baseline: dict[str, object]) -> list[dict[str, object]]:
    raw_facts = baseline.get("locked_facts", [])
    facts = [fact for fact in raw_facts if isinstance(fact, dict)] if isinstance(raw_facts, list) else []
    if facts:
        return facts
    return [
        {"fact_id": "fact_letter_exists", "summary": "The old letter exists on the desk."},
        {
            "fact_id": "fact_char_b_does_not_know_letter_content",
            "summary": "Character B does not know the letter content.",
        },
    ]


def _canonical_letter_deviations() -> list[dict[str, object]]:
    return [
        {
            "deviation_id": "player_inspects_letter",
            "trigger_family": "player_interaction",
            "target_object_id": "obj_letter",
            "interaction_type": "inspect",
            "may_change": [
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
            ],
            "must_preserve_locked_facts": [
                "fact_letter_exists",
                "fact_char_b_does_not_know_letter_content",
            ],
        },
        {
            "deviation_id": "player_takes_letter",
            "trigger_family": "player_interaction",
            "target_object_id": "obj_letter",
            "interaction_type": "take",
            "may_change": [
                {
                    "path": "objects.obj_letter.possession",
                    "from": "desk",
                    "to": "char_a",
                }
            ],
            "must_preserve_locked_facts": [
                "fact_letter_exists",
                "fact_char_b_does_not_know_letter_content",
            ],
        },
    ]


def _canonical_handoff_requirement() -> dict[str, object]:
    return {
        "requirement_id": "letter_must_be_held_before_handing_to_b",
        "summary": "角色 A must hold obj_letter before handing it to char_b.",
        "interaction_type": "handoff",
        "target_object_id": "obj_letter",
        "required_state": {"objects.obj_letter.possession": "char_a"},
    }


def _object_ids(baseline: dict[str, object]) -> set[str]:
    objects = baseline.get("objects", [])
    if not isinstance(objects, list):
        return set()
    return {str(item.get("object_id")) for item in objects if isinstance(item, dict)}


def _actor_ids(baseline: dict[str, object]) -> set[str]:
    actors = baseline.get("actors", [])
    if not isinstance(actors, list):
        return set()
    return {str(item.get("actor_id")) for item in actors if isinstance(item, dict)}


def _allowed_deviations(baseline: dict[str, object]) -> list[dict[str, object]]:
    deviations = baseline.get("allowed_deviations", [])
    return [item for item in deviations if isinstance(item, dict)] if isinstance(deviations, list) else []


def _prior_requirements(baseline: dict[str, object]) -> list[dict[str, object]]:
    requirements = baseline.get("prior_event_requirements", [])
    return [item for item in requirements if isinstance(item, dict)] if isinstance(requirements, list) else []


def _deviation_by_id(baseline: dict[str, object], deviation_id: str) -> dict[str, object] | None:
    for deviation in _allowed_deviations(baseline):
        if str(deviation.get("deviation_id")) == deviation_id:
            return deviation
    return None


def _lookup_state_path(baseline: dict[str, object], path: str) -> object | None:
    current: object = baseline
    for segment in path.split("."):
        if isinstance(current, dict):
            if segment in current:
                current = current[segment]
                continue
            state = current.get("state")
            if isinstance(state, dict) and segment in state:
                current = state[segment]
                continue
            return None

        if isinstance(current, list):
            matched_item = None
            for item in current:
                if not isinstance(item, dict):
                    continue
                if item.get("object_id") == segment or item.get("actor_id") == segment or item.get("fact_id") == segment:
                    matched_item = item
                    break
            if matched_item is None:
                return None
            current = matched_item
            continue

        return None

    return current


def _required_state_is_satisfied(baseline: dict[str, object], required_state: object) -> bool:
    if not isinstance(required_state, dict):
        return False
    for path, expected_value in required_state.items():
        if _lookup_state_path(baseline, str(path)) != expected_value:
            return False
    return True


def apply_deviation_diff(baseline: dict[str, object], deviation_id: str) -> list[dict[str, object]]:
    deviation = _deviation_by_id(baseline, deviation_id)
    if deviation is None:
        return []
    changes = deviation.get("may_change", [])
    if not isinstance(changes, list):
        return []
    diff: list[dict[str, object]] = []
    for item in changes:
        if not isinstance(item, dict):
            continue
        diff.append(
            {
                "path": str(item.get("path", "")),
                "from": item.get("from"),
                "to": item.get("to"),
            }
        )
    return diff


def _state_path_machine_id(path: str) -> str:
    state_dimension = path.rsplit(".", 1)[-1]
    if state_dimension.endswith("_state"):
        return state_dimension[: -len("_state")]
    return state_dimension


def _change_summary(target_object_id: str, state_path: str, previous_state: object, current_state: object) -> str:
    state_dimension = state_path.rsplit(".", 1)[-1]
    return f"{target_object_id} {state_dimension} changed from {previous_state} to {current_state}"


def _authority_event(
    *,
    event_id: str,
    event_type: str,
    producer_ts: int,
    actor_id: str,
    payload: dict[str, object],
    causation_id: str,
    correlation_id: str,
) -> AuthorityEvent:
    return AuthorityEvent(
        event_id=event_id,
        event_type=event_type,
        producer_ts=producer_ts,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L1", "system": "script_evolution_proof", "actor_id": actor_id},
        routing={"audience_mode": "room", "routing_mode": "broadcast", "target_ids": []},
        priority="p1",
        durability="replayable",
        causation_id=causation_id,
        correlation_id=correlation_id,
        payload=payload,
    )


def _candidate_to_interact_intent(candidate: dict[str, object], producer_ts: int) -> InteractIntent:
    return InteractIntent(
        player_id="player_demo",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id=str(candidate["actor_ref"]),
        intent_type=str(candidate.get("intent_type", "interact_intent")),
        target_object_id=str(candidate["target_ref"]),
        interaction_type=str(candidate["interaction_type"]),
        producer_ts=producer_ts,
    )


def classify_choice(baseline: dict[str, object], candidate: dict[str, object]) -> ChoiceResult:
    choice_id = str(candidate.get("choice_id", ""))
    source_text = str(candidate.get("source_text", ""))
    actor_ref = str(candidate.get("actor_ref", ""))
    target_ref = str(candidate.get("target_ref", ""))
    interaction_type = str(candidate.get("interaction_type", ""))
    event_type = str(candidate.get("event_type", ""))

    if event_type == "normalization_failed" or interaction_type == "normalization_failed":
        return ChoiceResult(
            choice_id,
            source_text,
            "NORMALIZATION_FAILED",
            notes=str(candidate.get("notes") or candidate.get("normalization_notes") or "normalization failed"),
        )

    if actor_ref and actor_ref not in _actor_ids(baseline):
        return ChoiceResult(choice_id, source_text, "NORMALIZATION_FAILED", notes=f"unknown actor_ref={actor_ref}")

    prior_requirement_satisfied = False
    for requirement in _prior_requirements(baseline):
        if (
            str(requirement.get("interaction_type")) == interaction_type
            and str(requirement.get("target_object_id")) == target_ref
        ):
            required_state = requirement.get("required_state", {})
            if not _required_state_is_satisfied(baseline, required_state):
                return ChoiceResult(
                    choice_id,
                    source_text,
                    "NEEDS_PRIOR_EVENT",
                    notes=f"requires prior state {required_state}",
                )
            prior_requirement_satisfied = True

    if target_ref not in _object_ids(baseline):
        return ChoiceResult(choice_id, source_text, "EVOLVABLE_NO_IMPACT", notes=f"non-mainline target={target_ref}")

    for deviation in _allowed_deviations(baseline):
        if (
            str(deviation.get("target_object_id")) == target_ref
            and str(deviation.get("interaction_type")) == interaction_type
        ):
            return ChoiceResult(
                choice_id,
                source_text,
                "PENDING_AUTHORITY_EXECUTION",
                matched_deviation_id=str(deviation.get("deviation_id", "")),
                notes="matched allowed deviation; authority execution required",
            )

    if prior_requirement_satisfied:
        return ChoiceResult(
            choice_id,
            source_text,
            "PENDING_AUTHORITY_EXECUTION",
            notes="prior requirement satisfied; authority execution required",
        )

    return ChoiceResult(choice_id, source_text, "REJECTED_BY_BASELINE", notes="no allowed deviation matched")


def execute_choice_branch(
    baseline: dict[str, object],
    candidate: dict[str, object],
    *,
    is_in_range: bool | None = True,
) -> ChoiceResult:
    classified = classify_choice(baseline, candidate)
    if classified.classification != "PENDING_AUTHORITY_EXECUTION":
        return classified

    bus = InMemoryAuthorityEventBus()
    esm = ESMService()
    adapter = Phase0AuthorityEventAdapter()
    choice_id = str(candidate["choice_id"])
    actor_ref = str(candidate["actor_ref"])
    target_ref = str(candidate["target_ref"])
    producer_ts = 100 + ord(choice_id[0])
    causation_id = f"choice:{choice_id}"
    correlation_id = f"script-evolution:{choice_id}"

    incoming = _authority_event(
        event_id=f"choice:{choice_id}:player_interaction",
        event_type="player.interaction.requested",
        producer_ts=producer_ts,
        actor_id=actor_ref,
        causation_id=causation_id,
        correlation_id=correlation_id,
        payload={"choice": candidate},
    )
    bus.publish(incoming)

    intent = _candidate_to_interact_intent(candidate, producer_ts)
    resolution = esm.resolve_interaction(intent, is_in_range=is_in_range)
    esm_results = [resolution.model_dump()]

    if resolution.result_type != "action_resolution_result":
        bus.publish(adapter.world_result_event(resolution, source_event=intent))
        return ChoiceResult(
            choice_id=choice_id,
            source_text=str(candidate["source_text"]),
            classification="CONSTRAINT_REJECTED",
            matched_deviation_id=classified.matched_deviation_id,
            notes="authority rejected interaction; no branch diff applied",
            authority_events=[event.model_dump() for event in bus.list_events()],
            esm_results=esm_results,
        )

    branch_diff = apply_deviation_diff(baseline, classified.matched_deviation_id)
    if not branch_diff:
        return ChoiceResult(
            choice_id=choice_id,
            source_text=str(candidate["source_text"]),
            classification="EVOLVABLE_NO_IMPACT",
            matched_deviation_id=classified.matched_deviation_id,
            notes="authority accepted but no allowed branch diff was produced",
            branch_diff=[],
            authority_events=[event.model_dump() for event in bus.list_events()],
            esm_results=esm_results,
        )

    for index, diff in enumerate(branch_diff, start=1):
        state_path = str(diff["path"])
        object_result = esm.emit_object_state_result(
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            actor_id=actor_ref,
            target_object_id=target_ref,
            previous_state=str(diff["from"]),
            current_state=str(diff["to"]),
            producer_ts=producer_ts + index,
            request_ref=getattr(resolution, "request_ref", None),
            causation_id=causation_id,
            correlation_id=correlation_id,
        )
        object_result = object_result.model_copy(
            update={
                "machine_id": _state_path_machine_id(state_path),
                "change_summary": _change_summary(target_ref, state_path, diff["from"], diff["to"]),
            }
        )
        esm_results.append(object_result.model_dump())
        siming_event = adapter.world_result_event(object_result, source_event=intent)
        siming_event.payload["state_path"] = state_path
        bus.publish(siming_event)
        bus.publish(
            _authority_event(
                event_id=f"choice:{choice_id}:world_change:{index}",
                event_type="world.object_state.changed",
                producer_ts=producer_ts + index,
                actor_id=actor_ref,
                causation_id=causation_id,
                correlation_id=correlation_id,
                payload={
                    "choice_id": choice_id,
                    "target_object_id": target_ref,
                    "path": state_path,
                    "from": diff["from"],
                    "to": diff["to"],
                    "esm_result": object_result.model_dump(),
                    "siming_observable_event_id": siming_event.event_id,
                },
            )
        )

    return ChoiceResult(
        choice_id=choice_id,
        source_text=str(candidate["source_text"]),
        classification="PENDING_SIMING_OBSERVATION",
        matched_deviation_id=classified.matched_deviation_id,
        notes="authority and ESM produced branch diff; Siming observation required",
        branch_diff=branch_diff,
        authority_events=[event.model_dump() for event in bus.list_events()],
        esm_results=esm_results,
    )


def _siming_source_events(result: ChoiceResult) -> list[AuthorityEvent]:
    source_events: list[AuthorityEvent] = []
    for event_payload in result.authority_events:
        if event_payload.get("event_type") == "esm_result_event":
            source_events.append(AuthorityEvent.model_validate(event_payload))
    return source_events


def _is_intervention_like(output: object) -> bool:
    output_type = str(getattr(output, "output_type", "") or "")
    selected_path = str(getattr(output, "selected_path", "") or "")
    intervention_band = str(getattr(output, "intervention_band", "") or "")
    return any(
        token in " ".join([output_type, selected_path, intervention_band]).lower()
        for token in ["candidate", "decision", "dispatch", "catalyst", "intervention", "fact_reveal"]
    )


def _is_bookkeeping_only_output(output: object) -> bool:
    output_type = str(getattr(output, "output_type", "") or "")
    selected_path = str(getattr(output, "selected_path", "") or "")
    return output_type in {"fairness_snapshot", "no_action"} or selected_path == "no_action"


def _model_dump_or_value(item: object) -> object:
    model_dump = getattr(item, "model_dump", None)
    if callable(model_dump):
        return model_dump()
    return item


def attach_siming_evidence(result: ChoiceResult) -> ChoiceResult:
    if result.classification != "PENDING_SIMING_OBSERVATION":
        return result

    source_events = _siming_source_events(result)
    if not source_events:
        result.classification = "SIMING_OBSERVATION_MISSING"
        result.notes = "world divergence missing authority event for Siming"
        return result

    runtime = SimingRuntime()
    tick_result = runtime.tick(
        [SimingInput(input_type=source_event.event_type, source_event=source_event) for source_event in source_events]
    )
    outputs = list(tick_result.outputs)
    audit_records = list(tick_result.audit_records)
    observed_outputs = [output for output in outputs if not _is_bookkeeping_only_output(output)]
    output_count = len(outputs)
    observed_output_count = len(observed_outputs)
    audit_count = len(audit_records)
    observation_evidence_count = observed_output_count + audit_count
    intervention_count = sum(1 for output in observed_outputs if _is_intervention_like(output))
    result.siming_evidence = {
        "observed": observation_evidence_count > 0,
        "source_event_count": len(source_events),
        "source_event_ids": [source_event.event_id for source_event in source_events],
        "output_count": output_count,
        "observed_output_count": observed_output_count,
        "audit_count": audit_count,
        "observation_evidence_count": observation_evidence_count,
        "intervention_like_output_count": intervention_count,
        "outputs": [_model_dump_or_value(output) for output in outputs],
        "audit_records": [_model_dump_or_value(record) for record in audit_records],
    }

    if intervention_count > 0:
        result.classification = "SIMING_INTERVENTION_PROPOSED"
        result.notes = "world divergence observed by Siming with intervention-like output"
    elif observation_evidence_count > 0:
        result.classification = "MAINLINE_IMPACT_DETECTED"
        result.notes = "world divergence observed or audited by Siming"
    else:
        result.classification = "PENDING_SIMING_OBSERVATION"
        result.notes = "world divergence produced but Siming returned bookkeeping-only evidence"
    return result


def run_choice_pipeline(baseline: dict[str, object], candidate: dict[str, object]) -> ChoiceResult:
    return attach_siming_evidence(execute_choice_branch(baseline, candidate))


def _choice_full_chain(result: ChoiceResult) -> dict[str, object]:
    authority_event_types = [
        str(event.get("event_type", "unknown"))
        for event in result.authority_events
        if isinstance(event, dict)
    ]
    esm_result_types = [
        str(item.get("result_type", "unknown"))
        for item in result.esm_results
        if isinstance(item, dict)
    ]
    siming_evidence = result.siming_evidence if isinstance(result.siming_evidence, dict) else {}
    return {
        "classification": result.classification,
        "classification_zh": CLASSIFICATION_ZH.get(result.classification, "未知判定"),
        "authority_event_count": len(result.authority_events),
        "authority_event_types": authority_event_types,
        "esm_result_count": len(result.esm_results),
        "esm_result_types": esm_result_types,
        "branch_diff_count": len(result.branch_diff),
        "siming_observed": bool(siming_evidence.get("observed", False)),
        "siming_source_event_count": int(siming_evidence.get("source_event_count", 0) or 0),
        "siming_output_count": int(siming_evidence.get("output_count", 0) or 0),
        "siming_audit_count": int(siming_evidence.get("audit_count", 0) or 0),
        "siming_observation_evidence_count": int(
            siming_evidence.get("observation_evidence_count", 0) or 0
        ),
    }


def _empty_mainline_projection(choice_id: str, reason_zh: str) -> dict[str, object]:
    return {
        "choice_id": choice_id,
        "impacted_mainline_node": "",
        "original_mainline_direction": "",
        "evolved_mainline_direction": "",
        "followup_nodes": [],
        "locked_fact_constraints": [],
        "evolvable": False,
        "projection_notes": reason_zh,
    }


def _coerce_string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _coerce_mainline_projection(payload: dict[str, object], choice_id: str) -> dict[str, object]:
    return {
        "choice_id": choice_id,
        "impacted_mainline_node": str(payload.get("impacted_mainline_node", "") or ""),
        "original_mainline_direction": str(payload.get("original_mainline_direction", "") or ""),
        "evolved_mainline_direction": str(payload.get("evolved_mainline_direction", "") or ""),
        "followup_nodes": _coerce_string_list(payload.get("followup_nodes", [])),
        "locked_fact_constraints": _coerce_string_list(payload.get("locked_fact_constraints", [])),
        "evolvable": bool(payload.get("evolvable", False)),
        "projection_notes": str(payload.get("projection_notes", "") or ""),
    }


def _coerce_projection_payload(payload: dict[str, object], expected_choice_ids: list[str]) -> list[dict[str, object]]:
    raw_projections = payload.get("projections")
    if not isinstance(raw_projections, list):
        raw_projections = payload.get("mainline_projections")
    if not isinstance(raw_projections, list):
        raw_projections = payload.get("choices")
    if isinstance(raw_projections, list):
        projections: list[dict[str, object]] = []
        for item in raw_projections:
            if isinstance(item, dict):
                projections.append(dict(item))
        return projections
    if all(choice_id in payload for choice_id in expected_choice_ids):
        projections = []
        for choice_id in expected_choice_ids:
            item = payload.get(choice_id)
            if isinstance(item, dict):
                next_item = dict(item)
                next_item.setdefault("choice_id", choice_id)
                projections.append(next_item)
        return projections
    return []


def _choice_to_report(result: ChoiceResult) -> dict[str, object]:
    return {
        "choice_id": result.choice_id,
        "source_text": result.source_text,
        "classification": result.classification,
        "classification_zh": CLASSIFICATION_ZH.get(result.classification, "未知判定"),
        "matched_deviation_id": result.matched_deviation_id,
        "notes": result.notes,
        "notes_zh": NOTES_ZH_BY_CLASSIFICATION.get(result.classification, "没有中文说明。"),
        "branch_diff": result.branch_diff,
        "authority_events": result.authority_events,
        "esm_results": result.esm_results,
        "siming_evidence": result.siming_evidence,
        "full_chain": _choice_full_chain(result),
    }


def _write_script_evolution_markdown(path: Path, report: dict[str, object]) -> None:
    lines = ["# 自然语言剧本选择演化证明 / Natural Language Script Choice Evolution Proof", ""]
    lines.append(f"- 总体结果(Overall): `{report['overall_script_evolution_passed']}`")
    lines.append(f"- 主线可演化(Mainline Evolvable): `{report['mainline_evolvable']}`")
    summary_zh = report.get("summary_zh")
    if summary_zh:
        lines.append(f"- 中文结论: {summary_zh}")
    lines.append("")
    lines.append("| 选项 Choice | 判定 Classification | 中文判定 | 说明 Notes |")
    lines.append("| --- | --- | --- | --- |")
    for choice in report["choices"]:
        notes_zh = str(choice.get("notes_zh", "")).replace("\n", " ")
        notes_en = str(choice.get("notes", "")).replace("\n", " ")
        notes = f"{notes_zh} / {notes_en}" if notes_en else notes_zh
        lines.append(
            f"| `{choice['choice_id']}` | `{choice['classification']}` | {choice.get('classification_zh', '')} | {notes} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_chapter_evolution_markdown(path: Path, report: dict[str, object]) -> None:
    lines = ["# 章节级主线演化完整链路证明 / Chapter Evolution Full Chain Proof", ""]
    lines.append(f"- 总体结果(Overall): `{report['overall_script_evolution_passed']}`")
    lines.append(f"- 主线可演化(Mainline Evolvable): `{report['mainline_evolvable']}`")
    lines.append(f"- 中文结论: {report.get('summary_zh', '')}")
    lines.append(f"- 剧本路径(script_path): `{report.get('script_path', '')}`")
    lines.append(f"- 选择来源(choices_source): `{report.get('choices_source', '')}`")
    normalization = report.get("normalization", {})
    if isinstance(normalization, dict):
        lines.append(f"- 剧本归一化(script_normalize): `{normalization.get('script_normalize', 'unknown')}`")
        lines.append(f"- 选择归一化(choices_normalize): `{normalization.get('choices_normalize', 'unknown')}`")
    lines.append("")
    lines.append("## 自动玩家选择 / Auto Player Choices")
    lines.append("")
    lines.append("| 选项 Choice | 玩家选择 | 判定 Classification | 中文判定 | 执行状态 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for choice in report.get("choices", []):
        full_chain = choice.get("full_chain", {}) if isinstance(choice, dict) else {}
        execution_status = "已执行后端链路" if int(full_chain.get("authority_event_count", 0) or 0) else "未进入后端执行"
        lines.append(
            "| `{choice_id}` | {source_text} | `{classification}` | {classification_zh} | {execution_status} |".format(
                choice_id=choice.get("choice_id", ""),
                source_text=str(choice.get("source_text", "")).replace("\n", " "),
                classification=choice.get("classification", ""),
                classification_zh=choice.get("classification_zh", ""),
                execution_status=execution_status,
            )
        )
    lines.append("")
    lines.append("## 完整链路阶段 / Full Chain Stages")
    lines.append("")
    lines.append("| 阶段 Stage | 中文说明 | 关键计数 |")
    lines.append("| --- | --- | --- |")
    for event in report.get("chain_trace", []):
        if not isinstance(event, dict):
            continue
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        count_summary = ", ".join(
            f"{key}={value}"
            for key, value in payload.items()
            if key.endswith("_count") or key in {"choice_id", "classification"}
        )
        lines.append(f"| `{event.get('stage', '')}` | {event.get('summary_zh', '')} | {count_summary} |")
    lines.append("")
    lines.append("## 逐选项后端链路 / Per-Choice Backend Chain")
    lines.append("")
    lines.append("| 选项 Choice | 后端权威事件 | ESM 结果 | Branch Diff | 司命观察 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for choice in report.get("choices", []):
        if not isinstance(choice, dict):
            continue
        full_chain = choice.get("full_chain", {})
        if not isinstance(full_chain, dict):
            full_chain = {}
        lines.append(
            "| `{choice_id}` | {authority} | {esm} | {diff} | {siming} |".format(
                choice_id=choice.get("choice_id", ""),
                authority=full_chain.get("authority_event_count", 0),
                esm=full_chain.get("esm_result_count", 0),
                diff=full_chain.get("branch_diff_count", 0),
                siming="已观察" if full_chain.get("siming_observed") else "未观察/不需要",
            )
        )
    lines.append("")
    lines.append("## 逐选项执行明细 / Per-Choice Execution Details")
    for choice in report.get("choices", []):
        if not isinstance(choice, dict):
            continue
        choice_id = choice.get("choice_id", "")
        full_chain = choice.get("full_chain", {})
        if not isinstance(full_chain, dict):
            full_chain = {}
        authority_event_types = full_chain.get("authority_event_types", [])
        esm_result_types = full_chain.get("esm_result_types", [])
        branch_diff = choice.get("branch_diff", [])
        siming_evidence = choice.get("siming_evidence", {})
        lines.append("")
        lines.append(f"### 选项 {choice_id} / Choice {choice_id}")
        lines.append("")
        lines.append(f"- 玩家选择: {str(choice.get('source_text', '')).replace(chr(10), ' ')}")
        lines.append(f"- 判定: {choice.get('classification_zh', '')} / `{choice.get('classification', '')}`")
        lines.append(
            "- 后端权威事件类型: "
            + (", ".join(f"`{item}`" for item in authority_event_types) if authority_event_types else "无")
        )
        lines.append(
            "- ESM 结果类型: "
            + (", ".join(f"`{item}`" for item in esm_result_types) if esm_result_types else "无")
        )
        if isinstance(branch_diff, list) and branch_diff:
            lines.append("- Branch Diff:")
            for diff in branch_diff:
                if not isinstance(diff, dict):
                    continue
                lines.append(f"  - {diff.get('path', '')}: {diff.get('from', '')} -> {diff.get('to', '')}")
        else:
            lines.append("- Branch Diff: 无")
        if isinstance(siming_evidence, dict) and siming_evidence:
            lines.append(
                "- 司命观察: observed={observed}, outputs={outputs}, audits={audits}, evidence={evidence}".format(
                    observed=siming_evidence.get("observed", False),
                    outputs=siming_evidence.get("output_count", 0),
                    audits=siming_evidence.get("audit_count", 0),
                    evidence=siming_evidence.get("observation_evidence_count", 0),
                )
            )
        else:
            lines.append("- 司命观察: 无")
        projection = choice.get("mainline_projection", {})
        if isinstance(projection, dict) and projection:
            lines.append("- 后续主线演化:")
            lines.append(f"  - 影响主线节点: {projection.get('impacted_mainline_node', '') or '无'}")
            lines.append(f"  - 原主线走向: {projection.get('original_mainline_direction', '') or '无'}")
            lines.append(f"  - 新主线走向: {projection.get('evolved_mainline_direction', '') or '无'}")
            followup_nodes = projection.get("followup_nodes", [])
            if isinstance(followup_nodes, list) and followup_nodes:
                lines.append("  - 后续剧情节点:")
                for node in followup_nodes:
                    lines.append(f"    - {node}")
            else:
                lines.append("  - 后续剧情节点: 无")
            locked_constraints = projection.get("locked_fact_constraints", [])
            if isinstance(locked_constraints, list) and locked_constraints:
                lines.append("  - 仍受锁定事实约束:")
                for constraint in locked_constraints:
                    lines.append(f"    - {constraint}")
            else:
                lines.append("  - 仍受锁定事实约束: 无")
            lines.append(f"  - 可继续演化: {projection.get('evolvable', False)}")
            notes = str(projection.get("projection_notes", "") or "")
            if notes:
                lines.append(f"  - 投影说明: {notes}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, events: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(event, ensure_ascii=False, sort_keys=True) for event in events)
    path.write_text(payload + ("\n" if payload else ""), encoding="utf-8")


def _print_console(report: dict[str, object]) -> None:
    if report.get("mode") == "chapter":
        print("章节级主线演化完整链路证明 / Chapter Evolution Full Chain Proof")
        script_path = report.get("script_path")
        if script_path:
            print(f"剧本路径(script_path)={script_path}")
        print(f"选择来源(choices_source)={report.get('choices_source', '')}")
        normalization = report.get("normalization", {})
        if isinstance(normalization, dict):
            print(f"剧本归一化(script_normalize)={normalization.get('script_normalize', 'unknown')}")
            print(f"选择归一化(choices_normalize)={normalization.get('choices_normalize', 'unknown')}")
            error = normalization.get("error")
            if error:
                print(f"错误(error)={error}")
        for choice in report.get("choices", []):
            if not isinstance(choice, dict):
                continue
            full_chain = choice.get("full_chain", {}) if isinstance(choice, dict) else {}
            if not isinstance(full_chain, dict):
                full_chain = {}
            print(f"[选项 {choice['choice_id']} / CHOICE {choice['choice_id']}] {choice['source_text']}")
            print(f"判定(result)={choice.get('classification_zh', '未知判定')} / {choice['classification']}")
            print(
                "链路(full_chain)="
                f"authority_events={full_chain.get('authority_event_count', 0)}, "
                f"esm_results={full_chain.get('esm_result_count', 0)}, "
                f"branch_diff={full_chain.get('branch_diff_count', 0)}, "
                f"siming_observed={full_chain.get('siming_observed', False)}"
            )
            print(f"说明(notes)={choice.get('notes_zh', '')} / {choice['notes']}")
            branch_diff = choice.get("branch_diff", [])
            if isinstance(branch_diff, list) and branch_diff:
                print("Branch Diff:")
                for diff in branch_diff:
                    if isinstance(diff, dict):
                        print(f"  - {diff.get('path', '')}: {diff.get('from', '')} -> {diff.get('to', '')}")
            else:
                print("Branch Diff: 无")
            projection = choice.get("mainline_projection", {})
            if isinstance(projection, dict) and projection:
                print("后续主线演化(mainline_projection):")
                print(f"  影响主线节点={projection.get('impacted_mainline_node', '') or '无'}")
                print(f"  原主线走向={projection.get('original_mainline_direction', '') or '无'}")
                print(f"  新主线走向={projection.get('evolved_mainline_direction', '') or '无'}")
                followup_nodes = projection.get("followup_nodes", [])
                if isinstance(followup_nodes, list) and followup_nodes:
                    print("  后续剧情节点=" + " | ".join(str(node) for node in followup_nodes))
                else:
                    print("  后续剧情节点=无")
                locked_constraints = projection.get("locked_fact_constraints", [])
                if isinstance(locked_constraints, list) and locked_constraints:
                    print("  锁定事实约束=" + " | ".join(str(item) for item in locked_constraints))
                else:
                    print("  锁定事实约束=无")
                print(f"  可继续演化={projection.get('evolvable', False)}")
                notes = str(projection.get("projection_notes", "") or "")
                if notes:
                    print(f"  投影说明={notes}")
        print(f"主线可演化(mainline_evolvable)={report.get('mainline_evolvable', False)}")
        print(f"中文结论(summary_zh)={report.get('summary_zh', '')}")
        passed = bool(report.get("overall_script_evolution_passed"))
        print("总体验证=通过 / overall=PASS" if passed else "总体验证=失败 / overall=FAIL")
        return
    print("自然语言剧本选择演化证明 / Natural Language Script Choice Evolution Proof")
    script_path = report.get("script_path")
    if script_path:
        print(f"剧本路径(script_path)={script_path}")
    choices_path = report.get("choices_path")
    if choices_path:
        print(f"选择输入路径(choices_path)={choices_path}")
    normalization = report.get("normalization", {})
    if isinstance(normalization, dict):
        print(f"剧本归一化(script_normalize)={normalization.get('script_normalize', 'unknown')}")
        print(f"选择归一化(choices_normalize)={normalization.get('choices_normalize', 'unknown')}")
        error = normalization.get("error")
        if error:
            print(f"错误(error)={error}")
    for choice in report.get("choices", []):
        print(f"[选项 {choice['choice_id']} / CHOICE {choice['choice_id']}] {choice['source_text']}")
        print(f"判定(result)={choice.get('classification_zh', '未知判定')} / {choice['classification']}")
        print(f"说明(notes)={choice.get('notes_zh', '')} / {choice['notes']}")
    print(f"主线可演化(mainline_evolvable)={report.get('mainline_evolvable', False)}")
    passed = bool(report.get("overall_script_evolution_passed"))
    print("结果=通过 / result=PASS" if passed else "结果=失败 / result=FAIL")


def _write_report(report: dict[str, object]) -> None:
    project_root = repo_root()
    log_dir = verification_dir(project_root)
    if report.get("mode") == "chapter":
        write_json(log_dir / CHAPTER_REPORT_JSON, report)
        _write_chapter_evolution_markdown(log_dir / CHAPTER_REPORT_MD, report)
        events = report.get("chain_trace", [])
        _write_jsonl(log_dir / CHAPTER_EVENTS_JSONL, events if isinstance(events, list) else [])
        return
    write_json(log_dir / REPORT_JSON, report)
    _write_script_evolution_markdown(log_dir / REPORT_MD, report)


def _configured_deepseek_endpoint() -> str:
    return str(backend_settings.siming_llm_endpoint or "https://api.deepseek.com/chat/completions").strip()


def _configured_deepseek_model() -> str:
    return str(backend_settings.siming_llm_model or "deepseek-chat").strip()


def _configured_deepseek_timeout() -> float:
    return float(backend_settings.siming_llm_timeout_seconds or 8.0)


def _deepseek_request(messages: list[dict[str, str]]) -> dict[str, object]:
    api_key = str(backend_settings.siming_llm_api_key or "").strip()
    endpoint = _configured_deepseek_endpoint()
    model = _configured_deepseek_model()
    timeout = _configured_deepseek_timeout()
    if not api_key:
        raise RuntimeError("DEEPSEEK_UNAVAILABLE: missing SIMING_LLM_API_KEY")
    payload = {
        "model": model,
        "messages": messages,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"DEEPSEEK_UNAVAILABLE: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("DEEPSEEK_UNAVAILABLE: response JSON is not an object")
    return data


def _deepseek_content(data: dict[str, object]) -> dict[str, object]:
    choices = data.get("choices")
    if not isinstance(choices, list):
        raise RuntimeError("CHOICES_NORMALIZE_FAILED: DeepSeek response missing choices")
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"CHOICES_NORMALIZE_FAILED: invalid JSON content: {exc}") from exc
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"choices": parsed}
    raise RuntimeError("CHOICES_NORMALIZE_FAILED: DeepSeek response missing JSON content")


def _coerce_live_choices_payload(payload: dict[str, object], expected_labels: list[str]) -> list[object]:
    raw_choices = payload.get("choices")
    if isinstance(raw_choices, list):
        return raw_choices
    if all(label in payload for label in expected_labels) and set(payload.keys()) == set(expected_labels):
        return [payload[label] for label in expected_labels]
    raise RuntimeError("CHOICES_NORMALIZE_FAILED: normalized choices missing choices list")


def normalize_with_deepseek(
    script_text: str, choices_text: str
) -> tuple[dict[str, object], list[dict[str, object]], dict[str, object]]:
    expected_labels = _expected_choice_labels_from_text(choices_text)
    script_response = _deepseek_request(
        [
            {
                "role": "system",
                "content": (
                    "Return only JSON. Normalize the script into the exact keys: "
                    "script_id, mainline_summary, actors, objects, locked_facts, "
                    "allowed_deviations, prior_event_requirements. Do not create events from the script. "
                    "Use the stable backend proof schema, not prose arrays. actors must be objects with "
                    "actor_id and summary, using actor_id char_a for role A and char_b for role B. objects "
                    "must be objects with object_id, summary, and state; use object_id obj_letter for the old "
                    "letter, with state keys location, visibility_state, interaction_state, and possession. "
                    "Use visibility_state=partially_visible, interaction_state=unopened, possession=desk for "
                    "the baseline old letter. locked_facts must be objects with fact_id and summary. "
                    "allowed_deviations must include object-state deviations for inspecting the letter "
                    "(interaction_type=inspect, target_object_id=obj_letter) and taking the letter "
                    "(interaction_type=take, target_object_id=obj_letter). prior_event_requirements must "
                    "include the handoff prerequisite requiring objects.obj_letter.possession == char_a before "
                    "interaction_type=handoff to obj_letter."
                ),
            },
            {"role": "user", "content": script_text},
        ]
    )
    baseline = canonicalize_live_baseline(_deepseek_content(script_response))
    choices_response = _deepseek_request(
        [
            {
                "role": "system",
                "content": (
                    "Return only JSON with top-level key choices. Normalize each supplied player choice "
                    "against the supplied baseline. Do not claim world mutation. Return exactly one object "
                    "per expected choice_id, in this exact order: "
                    f"{', '.join(expected_labels)}. Every returned object must explicitly include choice_id "
                    "using the matching expected label. Each choice object must use this candidate event schema: "
                    "choice_id, source_text, event_type, actor_ref, intent_type, target_ref, interaction_type, "
                    "confidence, evidence, normalization_notes, and optional secondary_target_ref. Use only these "
                    "stable ids from the baseline proof contract: actor_ref char_a or char_b; target_ref obj_letter "
                    "for letter interactions or room_exit for leaving. Map inspecting/checking the old letter to "
                    "event_type=player_interaction, intent_type=interact_intent, interaction_type=inspect, "
                    "actor_ref=char_a, target_ref=obj_letter. Map leaving the study to event_type=player_navigation, "
                    "intent_type=move_intent, interaction_type=leave, actor_ref=char_a, target_ref=room_exit. Map "
                    "handing the letter to character B to event_type=player_interaction, intent_type=interact_intent, "
                    "interaction_type=handoff, actor_ref=char_a, target_ref=obj_letter, secondary_target_ref=char_b."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "script": script_text,
                        "baseline_model": baseline,
                        "choices": choices_text,
                        "expected_choice_ids": expected_labels,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
    )
    choices_payload = _deepseek_content(choices_response)
    raw_choices = _coerce_live_choices_payload(choices_payload, expected_labels)
    if not all(isinstance(choice, dict) for choice in raw_choices):
        raise RuntimeError("CHOICES_NORMALIZE_FAILED: normalized choices must contain only objects")
    candidate_choices = [choice for choice in raw_choices if isinstance(choice, dict)]
    actual_labels = [str(choice.get("choice_id", "")).strip() for choice in candidate_choices]
    if actual_labels != expected_labels:
        raise RuntimeError(
            "CHOICES_NORMALIZE_FAILED: normalized choice_ids must match supplied labels exactly once and in order "
            f"(expected={expected_labels}, actual={actual_labels})"
        )
    endpoint = _configured_deepseek_endpoint()
    endpoint_host = endpoint.split("/")[2] if "://" in endpoint and len(endpoint.split("/")) > 2 else endpoint
    return baseline, candidate_choices, {
        "script_normalize": "deepseek_chat",
        "choices_normalize": "deepseek_chat",
        "deepseek_model": _configured_deepseek_model(),
        "deepseek_endpoint_host": endpoint_host,
    }


def canonicalize_chapter_baseline(baseline: dict[str, object]) -> dict[str, object]:
    def _list_of_dicts(value: object) -> list[dict[str, object]]:
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    script_id = str(baseline.get("script_id", "chapter_evolution")).strip() or "chapter_evolution"
    mainline_summary = str(baseline.get("mainline_summary", "")).strip()
    raw_actors = _list_of_dicts(baseline.get("actors", []))
    actors = []
    for actor in raw_actors:
        actor_id = str(actor.get("actor_id") or actor.get("id") or "").strip()
        if not actor_id:
            continue
        summary = str(actor.get("summary") or " ".join(
            str(actor.get(key, "")).strip()
            for key in ("name", "title")
            if str(actor.get(key, "")).strip()
        )).strip()
        next_actor = dict(actor)
        next_actor["actor_id"] = actor_id
        next_actor["summary"] = summary or actor_id
        actors.append(next_actor)
    raw_objects = _list_of_dicts(baseline.get("objects", []))
    objects = []
    for item in raw_objects:
        object_id = str(item.get("object_id") or item.get("id") or "").strip()
        if not object_id:
            continue
        next_item = dict(item)
        next_item["object_id"] = object_id
        next_item["summary"] = str(item.get("summary") or item.get("name") or object_id)
        objects.append(next_item)
    raw_locked_facts = _list_of_dicts(baseline.get("locked_facts", []))
    locked_facts = []
    for fact in raw_locked_facts:
        fact_id = str(fact.get("fact_id") or fact.get("id") or "").strip()
        if not fact_id:
            continue
        next_fact = dict(fact)
        next_fact["fact_id"] = fact_id
        next_fact["summary"] = str(fact.get("summary") or fact.get("description") or fact_id)
        locked_facts.append(next_fact)
    allowed_deviations = _list_of_dicts(baseline.get("allowed_deviations", []))
    prior_event_requirements = _list_of_dicts(baseline.get("prior_event_requirements", []))
    if not actors:
        raise RuntimeError("CHAPTER_NORMALIZE_FAILED: normalized chapter missing actors")
    if not objects:
        raise RuntimeError("CHAPTER_NORMALIZE_FAILED: normalized chapter missing narrative objects")
    if not allowed_deviations:
        raise RuntimeError("CHAPTER_NORMALIZE_FAILED: normalized chapter missing allowed_deviations")
    return {
        "script_id": script_id,
        "mainline_summary": mainline_summary,
        "actors": actors,
        "objects": objects,
        "locked_facts": locked_facts,
        "allowed_deviations": allowed_deviations,
        "prior_event_requirements": prior_event_requirements,
    }


def _validate_candidate_choice_labels(candidate_choices: list[dict[str, object]], expected_labels: list[str]) -> None:
    actual_labels = [str(choice.get("choice_id", "")).strip() for choice in candidate_choices]
    if actual_labels != expected_labels:
        raise RuntimeError(
            "CHOICES_NORMALIZE_FAILED: normalized choice_ids must match supplied labels exactly once and in order "
            f"(expected={expected_labels}, actual={actual_labels})"
        )


def _choice_alignment_text(choice: dict[str, object]) -> str:
    evidence = choice.get("evidence", [])
    if isinstance(evidence, list):
        evidence_text = " ".join(str(item) for item in evidence)
    else:
        evidence_text = str(evidence)
    return " ".join(
        [
            str(choice.get("source_text", "")),
            evidence_text,
            str(choice.get("normalization_notes", "")),
            str(choice.get("target_ref", "")),
            str(choice.get("interaction_type", "")),
        ]
    ).lower()


def _alignment_tokens(text: str) -> set[str]:
    normalized = re.sub(r"[\s_\-，。！？、；：,.!?;:]+", " ", text.lower())
    tokens = {token for token in normalized.split(" ") if len(token) >= 2}
    compact = re.sub(r"\s+", "", normalized)
    for size in (2, 3, 4):
        for index in range(0, max(len(compact) - size + 1, 0)):
            token = compact[index : index + size]
            if token:
                tokens.add(token)
    return tokens


def _deviation_alignment_score(
    choice: dict[str, object],
    deviation: dict[str, object],
    objects_by_id: dict[str, dict[str, object]],
) -> int:
    score = 0
    target_object_id = str(deviation.get("target_object_id", ""))
    interaction_type = str(deviation.get("interaction_type", ""))
    if str(choice.get("target_ref", "")) == target_object_id:
        score += 100
    if str(choice.get("interaction_type", "")) == interaction_type:
        score += 40
    object_summary = str(objects_by_id.get(target_object_id, {}).get("summary", ""))
    searchable = _choice_alignment_text(choice)
    target_text = " ".join(
        [
            target_object_id,
            str(deviation.get("deviation_id", "")),
            str(deviation.get("trigger_family", "")),
            interaction_type,
            object_summary,
        ]
    )
    for token in _alignment_tokens(target_text):
        if token and token in searchable:
            score += min(len(token), 4)
    return score


def align_auto_choices_to_allowed_deviations(
    baseline: dict[str, object],
    candidate_choices: list[dict[str, object]],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    deviations = _allowed_deviations(baseline)
    objects = baseline.get("objects", [])
    objects_by_id = {
        str(item.get("object_id", "")): item
        for item in objects
        if isinstance(item, dict) and str(item.get("object_id", ""))
    } if isinstance(objects, list) else {}
    actors = _actor_ids(baseline)
    fallback_actor = sorted(actors)[0] if actors else ""
    aligned_choices: list[dict[str, object]] = []
    aligned_count = 0
    for index, choice in enumerate(candidate_choices):
        next_choice = dict(choice)
        prior_match = next(
            (
                requirement
                for requirement in _prior_requirements(baseline)
                if str(requirement.get("target_object_id", "")) == str(next_choice.get("target_ref", ""))
                and str(requirement.get("interaction_type", "")) == str(next_choice.get("interaction_type", ""))
            ),
            None,
        )
        if prior_match is not None:
            next_choice["contract_alignment"] = {
                "aligned": False,
                "reason": "matches prior_event_requirement",
                "requirement_id": str(prior_match.get("requirement_id", "")),
            }
            aligned_choices.append(next_choice)
            continue
        exact_match = next(
            (
                deviation
                for deviation in deviations
                if str(deviation.get("target_object_id", "")) == str(next_choice.get("target_ref", ""))
                and str(deviation.get("interaction_type", "")) == str(next_choice.get("interaction_type", ""))
            ),
            None,
        )
        selected_deviation = exact_match
        if selected_deviation is None and deviations:
            scored = sorted(
                (
                    (
                        _deviation_alignment_score(next_choice, deviation, objects_by_id),
                        order,
                        deviation,
                    )
                    for order, deviation in enumerate(deviations)
                ),
                key=lambda item: (item[0], -item[1]),
                reverse=True,
            )
            best_score, _order, best_deviation = scored[0]
            if best_score > 0:
                selected_deviation = best_deviation
            elif index < len(deviations):
                selected_deviation = deviations[index]

        if selected_deviation is None:
            next_choice["contract_alignment"] = {
                "aligned": False,
                "reason": "no allowed deviation available",
            }
            aligned_choices.append(next_choice)
            continue

        original_target_ref = str(next_choice.get("target_ref", ""))
        original_interaction_type = str(next_choice.get("interaction_type", ""))
        target_object_id = str(selected_deviation.get("target_object_id", ""))
        interaction_type = str(selected_deviation.get("interaction_type", ""))
        was_aligned = exact_match is None or original_target_ref != target_object_id or original_interaction_type != interaction_type
        if was_aligned:
            aligned_count += 1
            next_choice["target_ref"] = target_object_id
            next_choice["interaction_type"] = interaction_type
            next_choice["intent_type"] = "interact_intent"
            if str(next_choice.get("actor_ref", "")) not in actors and fallback_actor:
                next_choice["actor_ref"] = fallback_actor
            next_choice["normalization_notes"] = (
                f"{next_choice.get('normalization_notes', '')} "
                f"[backend contract aligned to deviation {selected_deviation.get('deviation_id', '')}]"
            ).strip()
        next_choice["contract_alignment"] = {
            "aligned": was_aligned,
            "from_target_ref": original_target_ref,
            "from_interaction_type": original_interaction_type,
            "to_target_ref": target_object_id,
            "to_interaction_type": interaction_type,
            "deviation_id": str(selected_deviation.get("deviation_id", "")),
        }
        aligned_choices.append(next_choice)
    return aligned_choices, {
        "aligned_choice_count": aligned_count,
        "allowed_deviation_count": len(deviations),
    }


def normalize_chapter_with_deepseek(
    script_text: str,
) -> tuple[dict[str, object], list[dict[str, object]], dict[str, object], list[dict[str, object]]]:
    expected_labels = ["A", "B", "C"]
    trace: list[dict[str, object]] = []
    script_response = _deepseek_request(
        [
            {
                "role": "system",
                "content": (
                    "Return only JSON. Normalize the supplied Chinese fiction chapter into the backend proof schema. "
                    "Do not decide whether evolution passes. Create a baseline with exact keys: script_id, "
                    "mainline_summary, actors, objects, locked_facts, allowed_deviations, prior_event_requirements. "
                    "For this proof, objects may be narrative or strategic state nodes, not only physical objects. "
                    "Every object must have object_id, summary, and state. Use stable ASCII ids. "
                    "allowed_deviations must contain backend-executable branch changes with deviation_id, "
                    "trigger_family, target_object_id, interaction_type, may_change, and must_preserve_locked_facts. "
                    "Each may_change entry must use a path like objects.<object_id>.<state_key>, with from and to. "
                    "At least one allowed deviation must represent a player choice that can visibly change the mainline. "
                    "Use may_change directions that are consistent with the chapter situation: from the current baseline "
                    "state to the changed state caused by the player-like operation. Do not invert a protagonist action "
                    "into the opposite outcome unless the deviation explicitly represents refusing that action. "
                    "prior_event_requirements may be empty, or may describe a choice that requires an earlier state."
                ),
            },
            {"role": "user", "content": script_text},
        ]
    )
    baseline = canonicalize_chapter_baseline(_deepseek_content(script_response))
    trace.append(
        _trace_event(
            "deepseek_chapter_normalized",
            "DeepSeek 章节归一化：生成后端可执行的角色、叙事节点、锁定事实和允许偏移。",
            actor_count=len(baseline["actors"]),
            object_count=len(baseline["objects"]),
            allowed_deviation_count=len(baseline["allowed_deviations"]),
            prior_requirement_count=len(baseline["prior_event_requirements"]),
        )
    )
    choices_response = _deepseek_request(
        [
            {
                "role": "system",
                "content": (
                    "Return only JSON with top-level key choices. Generate exactly three player-like choices from the "
                    "chapter baseline. Do not copy chapter prose as the choice text; write each source_text as a player "
                    "operation, for example '玩家命令刘世民立刻...' or '玩家选择让关兴...'. Use these choice ids in order: A, B, C. "
                    "Each choice must include choice_id, "
                    "source_text, event_type, actor_ref, intent_type, target_ref, interaction_type, confidence, "
                    "evidence, normalization_notes, and optional secondary_target_ref. actor_ref must match one actor_id "
                    "from baseline. target_ref and interaction_type should use one pair from baseline.allowed_deviations "
                    "whenever the player choice is intended to be executable; copy target_ref from target_object_id and "
                    "copy interaction_type exactly from the selected allowed_deviation. Prefer: A as a high-impact "
                    "mainline intervention, B as a support or limited-impact choice, C as a blocked or "
                    "prerequisite-dependent choice when the baseline supports it. Do not claim success; only normalize "
                    "candidate choices for backend execution."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "chapter": script_text,
                        "baseline_model": baseline,
                        "expected_choice_ids": expected_labels,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
    )
    choices_payload = _deepseek_content(choices_response)
    raw_choices = _coerce_live_choices_payload(choices_payload, expected_labels)
    if not all(isinstance(choice, dict) for choice in raw_choices):
        raise RuntimeError("CHOICES_NORMALIZE_FAILED: normalized choices must contain only objects")
    candidate_choices = [choice for choice in raw_choices if isinstance(choice, dict)]
    _validate_candidate_choice_labels(candidate_choices, expected_labels)
    candidate_choices, alignment_meta = align_auto_choices_to_allowed_deviations(baseline, candidate_choices)
    trace.append(
        _trace_event(
            "deepseek_auto_choices_generated",
            "DeepSeek 自动生成玩家选择：生成 3 个候选事件，等待后端逐个裁判。",
            choice_count=len(candidate_choices),
        )
    )
    trace.append(
        _trace_event(
            "deepseek_auto_choices_aligned",
            "后端合同对齐：将自动生成的选择映射到 allowed_deviations 的 target_ref/interaction_type。",
            **alignment_meta,
        )
    )
    endpoint = _configured_deepseek_endpoint()
    endpoint_host = endpoint.split("/")[2] if "://" in endpoint and len(endpoint.split("/")) > 2 else endpoint
    return baseline, candidate_choices, {
        "script_normalize": "deepseek_chapter",
        "choices_normalize": "deepseek_auto_choices",
        "deepseek_model": _configured_deepseek_model(),
        "deepseek_endpoint_host": endpoint_host,
    }, trace


def project_mainline_with_deepseek(
    script_text: str,
    baseline: dict[str, object],
    choices_report: list[dict[str, object]],
) -> list[dict[str, object]]:
    impact_classifications = {"MAINLINE_IMPACT_DETECTED", "SIMING_INTERVENTION_PROPOSED"}
    impacted_choices = [
        choice
        for choice in choices_report
        if choice.get("classification") in impact_classifications and choice.get("branch_diff")
    ]
    if not impacted_choices:
        return [
            {
                **choice,
                "mainline_projection": _empty_mainline_projection(
                    str(choice.get("choice_id", "")),
                    "该选择没有产生后端确认的主线分歧，因此不投影后续主线。",
                ),
            }
            for choice in choices_report
        ]

    projection_request_choices = []
    for choice in impacted_choices:
        full_chain = choice.get("full_chain", {})
        if not isinstance(full_chain, dict):
            full_chain = {}
        projection_request_choices.append(
            {
                "choice_id": choice.get("choice_id"),
                "source_text": choice.get("source_text"),
                "classification": choice.get("classification"),
                "branch_diff": choice.get("branch_diff", []),
                "authority_event_types": full_chain.get("authority_event_types", []),
                "esm_result_types": full_chain.get("esm_result_types", []),
                "siming_evidence_summary": {
                    "observed": full_chain.get("siming_observed", False),
                    "output_count": full_chain.get("siming_output_count", 0),
                    "audit_count": full_chain.get("siming_audit_count", 0),
                    "observation_evidence_count": full_chain.get("siming_observation_evidence_count", 0),
                },
            }
        )
    payload = {
        "chapter": script_text,
        "baseline_mainline_summary": baseline.get("mainline_summary", ""),
        "locked_facts": baseline.get("locked_facts", []),
        "choices_with_backend_evidence": projection_request_choices,
    }
    response = _deepseek_request(
        [
            {
                "role": "system",
                "content": (
                    "Return only JSON with top-level key projections. You are not the proof judge. The backend has "
                    "already decided which choices changed world/mainline state. Your job is to narratively project "
                    "what those confirmed branch_diff values mean for the next mainline. For each supplied choice_id, "
                    "return exactly one projection object with keys: choice_id, impacted_mainline_node, "
                    "original_mainline_direction, evolved_mainline_direction, followup_nodes, locked_fact_constraints, "
                    "evolvable, projection_notes. followup_nodes must be 3 to 5 concrete subsequent plot nodes. "
                    "locked_fact_constraints must list facts that still cannot be contradicted. Do not invent proof "
                    "status and do not ignore branch_diff."
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
    )
    parsed = _deepseek_content(response)
    expected_choice_ids = [str(choice.get("choice_id", "") or "") for choice in impacted_choices]
    raw_projections = _coerce_projection_payload(parsed, expected_choice_ids)
    if not raw_projections:
        raise RuntimeError("MAINLINE_PROJECTION_FAILED: DeepSeek response missing projection objects")
    projection_by_choice_id: dict[str, dict[str, object]] = {}
    for item in raw_projections:
        if not isinstance(item, dict):
            continue
        choice_id = str(item.get("choice_id", "") or "")
        if choice_id:
            projection_by_choice_id[choice_id] = _coerce_mainline_projection(item, choice_id)

    enriched: list[dict[str, object]] = []
    for choice in choices_report:
        choice_id = str(choice.get("choice_id", "") or "")
        if choice.get("classification") in impact_classifications and choice.get("branch_diff"):
            projection = projection_by_choice_id.get(
                choice_id,
                _empty_mainline_projection(choice_id, "DeepSeek 未返回该选项的主线投影。"),
            )
        else:
            projection = _empty_mainline_projection(choice_id, "该选择未产生后端确认的主线分歧。")
        enriched.append({**choice, "mainline_projection": projection})
    return enriched


def _trace_event(stage: str, summary_zh: str, **payload: object) -> dict[str, object]:
    return {
        "stage": stage,
        "summary_zh": summary_zh,
        "payload": payload,
    }


def _choice_trace_events(choice: dict[str, object]) -> list[dict[str, object]]:
    choice_id = str(choice.get("choice_id", ""))
    classification = str(choice.get("classification", ""))
    full_chain = choice.get("full_chain", {})
    if not isinstance(full_chain, dict):
        full_chain = {}
    return [
        _trace_event(
            "choice_backend_classified",
            "后端基线裁判：判定选择是否能进入权威执行、是否需要前置事件或是否不影响主线。",
            choice_id=choice_id,
            classification=classification,
        ),
        _trace_event(
            "choice_authority_events",
            "后端权威事件：记录玩家输入、ESM 结果和世界状态变化事件。",
            choice_id=choice_id,
            authority_event_count=full_chain.get("authority_event_count", 0),
            authority_event_types=full_chain.get("authority_event_types", []),
            authority_events=choice.get("authority_events", []),
        ),
        _trace_event(
            "choice_esm_results",
            "ESM 结果：记录交互是否被接受，以及对象/叙事节点状态变化。",
            choice_id=choice_id,
            esm_result_count=full_chain.get("esm_result_count", 0),
            esm_result_types=full_chain.get("esm_result_types", []),
            esm_results=choice.get("esm_results", []),
        ),
        _trace_event(
            "choice_branch_diff",
            "Branch Diff：记录该选择相对同一基线造成的世界/主线状态差异。",
            choice_id=choice_id,
            branch_diff_count=full_chain.get("branch_diff_count", 0),
            branch_diff=choice.get("branch_diff", []),
        ),
        _trace_event(
            "choice_siming_evidence",
            "司命观察：记录司命是否看到分歧，以及 audit/output 证据数量。",
            choice_id=choice_id,
            siming_observed=full_chain.get("siming_observed", False),
            siming_output_count=full_chain.get("siming_output_count", 0),
            siming_audit_count=full_chain.get("siming_audit_count", 0),
            siming_evidence=choice.get("siming_evidence", {}),
        ),
        _trace_event(
            "choice_mainline_projected",
            "主线演化投影：基于后端已确认的 branch diff 推演后续主线走向。",
            choice_id=choice_id,
            mainline_projection=choice.get(
                "mainline_projection",
                _empty_mainline_projection(choice_id, "该选择没有主线投影。"),
            ),
        ),
    ]


def run_proof(
    script_path: Path,
    choices_path: Path,
    live_deepseek: bool,
    *,
    chapter_mode: bool = False,
    auto_choices: bool = False,
    full_chain_log: bool = False,
) -> dict[str, object]:
    script_text = script_path.read_text(encoding="utf-8")
    choices_text = "" if auto_choices else choices_path.read_text(encoding="utf-8")
    chain_trace: list[dict[str, object]] = [
        _trace_event(
            "input_loaded",
            "输入已读取：自然语言剧本进入后端证明流程。",
            script_path=str(script_path),
            choices_path=str(choices_path) if not auto_choices else "",
            script_char_count=len(script_text),
            auto_choices=auto_choices,
            chapter_mode=chapter_mode,
        )
    ]
    normalization_meta: dict[str, object] = {
        "script_normalize": "fixture",
        "choices_normalize": "fixture",
        "live_deepseek": live_deepseek,
    }
    if chapter_mode:
        if not live_deepseek:
            raise RuntimeError("CHAPTER_MODE_REQUIRES_DEEPSEEK: chapter mode requires live DeepSeek")
        if not auto_choices:
            raise RuntimeError("CHAPTER_MODE_REQUIRES_AUTO_CHOICES: chapter mode currently requires --auto-choices")
        baseline, choices, deepseek_meta, deepseek_trace = normalize_chapter_with_deepseek(script_text)
        normalization_meta.update(deepseek_meta)
        chain_trace.extend(deepseek_trace)
    elif live_deepseek:
        baseline, choices, deepseek_meta = normalize_with_deepseek(script_text, choices_text)
        normalization_meta.update(deepseek_meta)
    else:
        baseline = normalize_baseline_fixture(script_text)
        choices = normalize_candidate_choices_fixture(choices_text)

    results = [run_choice_pipeline(baseline, candidate) for candidate in choices]
    impact_classifications = {"MAINLINE_IMPACT_DETECTED", "SIMING_INTERVENTION_PROPOSED"}
    mainline_evolvable = any(result.classification in impact_classifications for result in results)
    choices_report = [_choice_to_report(result) for result in results]
    if chapter_mode:
        choices_report = project_mainline_with_deepseek(script_text, baseline, choices_report)
    if full_chain_log or chapter_mode:
        for choice_report in choices_report:
            chain_trace.extend(_choice_trace_events(choice_report))
        chain_trace.append(
            _trace_event(
                "proof_completed",
                "证明完成：总体验证结果与每个选择的执行状态已写入报告。",
                choice_count=len(choices_report),
                impact_choice_count=sum(
                    1 for choice in choices_report if choice.get("classification") in impact_classifications
                ),
                mainline_evolvable=mainline_evolvable,
            )
        )
    report: dict[str, object] = {
        "mode": "chapter" if chapter_mode else "script",
        "overall_script_evolution_passed": mainline_evolvable,
        "mainline_evolvable": mainline_evolvable,
        "summary_zh": (
            "通过：至少一个玩家选择触发了可观察的主线影响，证明主线可以演化。"
            if mainline_evolvable
            else "失败：没有玩家选择触发可观察的主线影响，尚不能证明主线可以演化。"
        ),
        "script_path": str(script_path),
        "choices_path": str(choices_path) if not auto_choices else "",
        "choices_source": "deepseek_auto" if auto_choices else "input_file",
        "normalization": normalization_meta,
        "baseline_model": baseline,
        "candidate_choices": choices,
        "choices": choices_report,
        "chain_trace": chain_trace if (full_chain_log or chapter_mode) else [],
        "artifacts": {
            "json": ".harness/verification/chapter-evolution-full-chain-report.json"
            if chapter_mode
            else ".harness/verification/script-evolution-proof-report.json",
            "markdown": ".harness/verification/chapter-evolution-full-chain-report.md"
            if chapter_mode
            else ".harness/verification/script-evolution-proof-report.md",
            "events_jsonl": ".harness/verification/chapter-evolution-events.jsonl" if chapter_mode else "",
        },
    }
    _write_report(report)
    return report


def _build_failure_report(
    script_path: Path,
    choices_path: Path,
    live_deepseek: bool,
    error: Exception,
    *,
    chapter_mode: bool = False,
    auto_choices: bool = False,
    full_chain_log: bool = False,
) -> dict[str, object]:
    chain_trace = [
        _trace_event(
            "proof_failed",
            "证明失败：流程在完成前中断，详见 normalization.error。",
            script_path=str(script_path),
            choices_path=str(choices_path) if not auto_choices else "",
            chapter_mode=chapter_mode,
            auto_choices=auto_choices,
            error=str(error),
        )
    ] if (chapter_mode or full_chain_log) else []
    return {
        "mode": "chapter" if chapter_mode else "script",
        "overall_script_evolution_passed": False,
        "mainline_evolvable": False,
        "summary_zh": "失败：验证过程中断，尚不能证明主线可以演化。",
        "script_path": str(script_path),
        "choices_path": str(choices_path) if not auto_choices else "",
        "choices_source": "deepseek_auto" if auto_choices else "input_file",
        "normalization": {
            "script_normalize": "deepseek_chapter"
            if chapter_mode and live_deepseek
            else ("deepseek_chat" if live_deepseek else "fixture"),
            "choices_normalize": "deepseek_auto_choices"
            if chapter_mode and auto_choices
            else ("deepseek_chat" if live_deepseek else "fixture"),
            "live_deepseek": live_deepseek,
            "error": str(error),
        },
        "choices": [],
        "chain_trace": chain_trace,
        "artifacts": {
            "json": ".harness/verification/chapter-evolution-full-chain-report.json"
            if chapter_mode
            else ".harness/verification/script-evolution-proof-report.json",
            "markdown": ".harness/verification/chapter-evolution-full-chain-report.md"
            if chapter_mode
            else ".harness/verification/script-evolution-proof-report.md",
            "events_jsonl": ".harness/verification/chapter-evolution-events.jsonl" if chapter_mode else "",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    project_root = repo_root()
    parser.add_argument(
        "--script",
        default=str(project_root / ".harness" / "fixtures" / "script-evolution" / "demo-script.md"),
    )
    parser.add_argument(
        "--choices",
        default=str(project_root / ".harness" / "fixtures" / "script-evolution" / "demo-choices.txt"),
    )
    parser.add_argument("--live-deepseek", action="store_true")
    parser.add_argument("--component-only", action="store_true")
    parser.add_argument("--chapter-mode", action="store_true")
    parser.add_argument("--auto-choices", action="store_true")
    parser.add_argument("--full-chain-log", action="store_true")
    args = parser.parse_args()

    try:
        report = run_proof(
            Path(args.script),
            Path(args.choices),
            live_deepseek=bool(args.live_deepseek or not args.component_only),
            chapter_mode=bool(args.chapter_mode),
            auto_choices=bool(args.auto_choices),
            full_chain_log=bool(args.full_chain_log),
        )
    except (RuntimeError, ValueError, OSError) as exc:
        report = _build_failure_report(
            Path(args.script),
            Path(args.choices),
            bool(args.live_deepseek or not args.component_only),
            exc,
            chapter_mode=bool(args.chapter_mode),
            auto_choices=bool(args.auto_choices),
            full_chain_log=bool(args.full_chain_log),
        )
        _write_report(report)
        _print_console(report)
        return 1

    _print_console(report)
    return 0 if report["overall_script_evolution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
