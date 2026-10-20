from __future__ import annotations

import copy
import hashlib
import json
from typing import Iterable


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_digest_excluding(value: object, excluded: Iterable[str] = ()) -> str:
    excluded_set = set(excluded)
    if isinstance(value, dict):
        value = {k: canonical_digest_excluding(v, ()) for k, v in value.items() if k not in excluded_set}
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def canonical_records_digest(records: list[dict]) -> str:
    """Historical archive contract: records array only, all record fields included."""
    return "sha256:" + hashlib.sha256(_canonical(records)).hexdigest()


def build_run_envelope(records: list[dict], metadata: dict, run_status: dict) -> dict:
    required_metadata = {
        "input_digest", "provider_revision", "tokenizer_sha256", "device",
        "max_len", "head_max_len", "before_health", "after_health",
        "preflight", "execution_identity",
    }
    missing = sorted(required_metadata - metadata.keys())
    if missing:
        raise ValueError(f"run envelope metadata missing: {', '.join(missing)}")
    envelope = {
        "schema_version": "calibration_run_envelope.v1",
        "records": copy.deepcopy(records),
        "records_digest": canonical_records_digest(records),
        "metadata": copy.deepcopy(metadata),
        "run_status": copy.deepcopy(run_status),
    }
    envelope["envelope_digest"] = canonical_digest_excluding(envelope, {"envelope_digest"})
    return envelope


def _invalid(record: dict) -> str | None:
    usage = record.get("usage")
    if not isinstance(usage, dict):
        return "usage_missing"
    if (usage.get("truncated") is not False or type(usage.get("state_tokens_dropped")) is not int
            or usage["state_tokens_dropped"] != 0):
        return "usage_unverifiable" if usage.get("truncated") is not True else "truncated"
    if record.get("input_valid") is False:
        return "input_invalid"
    if record.get("invalid_category"):
        return str(record["invalid_category"])
    response = record.get("response")
    if not isinstance(response, dict) or not isinstance(response.get("choice"), str):
        return "response_invalid"
    request = record.get("request")
    questions = request.get("questions") if isinstance(request, dict) else None
    question = questions.get("choice") if isinstance(questions, dict) else None
    criteria = question.get("criteria") if isinstance(question, dict) else None
    if not isinstance(criteria, dict) or not criteria:
        return "request_candidates_missing"
    if response["choice"] not in criteria:
        return "choice_out_of_set"
    return None


def _accepted_labels(value: object) -> set[str]:
    """Normalize the frozen review representation without changing its meaning."""
    if not isinstance(value, list):
        return set()
    labels: set[str] = set()
    for item in value:
        if isinstance(item, str):
            labels.add(item)
        elif isinstance(item, dict):
            for key in ("label", "wire_label", "candidate_id"):
                candidate = item.get(key)
                if isinstance(candidate, str) and candidate:
                    labels.add(candidate)
    return labels


def score_calibration_records(records: list[dict], truth: dict[str, dict], *,
                             formal_denominators: dict[str, int],
                             minimum_valid: dict[str, int]) -> dict:
    tracks: dict[str, dict] = {}
    for track, denominator in formal_denominators.items():
        tracks[track] = {"hits": 0, "valid_samples": 0, "formal_denominator": denominator,
                         "invalid": {}}
    for record in records:
        track = record.get("track")
        if track not in tracks:
            continue
        invalid = _invalid(record)
        if invalid:
            tracks[track]["invalid"][invalid] = tracks[track]["invalid"].get(invalid, 0) + 1
            continue
        qid = record.get("question_id")
        label = record["response"]["choice"]
        accepted = _accepted_labels(truth.get(qid, {}).get("acceptable_action_set"))
        if not accepted:
            tracks[track]["invalid"]["truth_missing"] = tracks[track]["invalid"].get("truth_missing", 0) + 1
            continue
        tracks[track]["valid_samples"] += 1
        if label in accepted:
            tracks[track]["hits"] += 1
    blocked = [track for track, minimum in minimum_valid.items()
               if tracks.get(track, {}).get("valid_samples", 0) < minimum]
    return {"schema_version": "calibration_score.v2", "tracks": tracks,
            "status": "blocked_minimum_valid_samples" if blocked else "scored",
            "blocked_tracks": blocked, "invalid_handling": "fail_closed"}
