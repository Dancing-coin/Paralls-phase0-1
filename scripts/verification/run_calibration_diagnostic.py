"""Run frozen calibration inputs without loading review truth.

This process accepts only prepared requests and a metadata-only manifest. Truth,
acceptable sets, and reviewer rationale are intentionally not command inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.character_agent.gateway.laya_provider import LayaSystemOneProvider
from app.character_agent.evaluation.calibration_contracts import build_run_envelope


def _digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _post(endpoint: str, payload: dict, timeout: float) -> tuple[dict | None, bytes | None, str | None]:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    try:
        with urlopen(Request(endpoint, data=body, headers={"Content-Type": "application/json"}, method="POST"), timeout=timeout) as response:
            raw = response.read()
        decoded = json.loads(raw.decode("utf-8"))
        return decoded if isinstance(decoded, dict) else None, raw, None
    except Exception as exc:  # preserve the exact failure in the archive
        return None, None, f"{type(exc).__name__}: {exc}"


def _health(endpoint: str, timeout: float) -> dict:
    try:
        with urlopen(endpoint.rstrip("/") + "/health", timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
        return value if isinstance(value, dict) else {"error": "health_not_object"}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def preflight_admits_formal_run(health: dict, preflight: dict) -> bool:
    usage = preflight.get("usage")
    return (health.get("status") == "ok"
            and health.get("loaded") == ["multilingual"]
            and health.get("revisions", {}).get("multilingual") == LayaSystemOneProvider.CHECKPOINT_REVISION
            and health.get("device") == "cpu"
            and health.get("checkpoint_devices", {}).get("multilingual") == "cpu"
            and preflight.get("accepted") is True
            and isinstance(usage, dict)
            and usage.get("truncated") is False
            and type(usage.get("state_tokens_dropped")) is int
            and usage["state_tokens_dropped"] == 0)


def _choice(response: object) -> str | None:
    answers = response.get("answers") if isinstance(response, dict) else None
    answer = answers.get("choice") if isinstance(answers, dict) else None
    selected = answer.get("choice") if isinstance(answer, dict) else None
    return selected if isinstance(selected, str) else None


def _preflight(provider: LayaSystemOneProvider, endpoint: str, timeout: float) -> dict:
    request = {"task_kind": "l3_planning", "context": {
        "laya_state": "synthetic budget preflight; no formal calibration content",
        "candidate_intents": ["C1", "C2"],
        "max_len": 2091, "head_max_len": 256, "input_budget_required": True,
    }}
    payload = provider.build_wire_request(request)
    response, raw, error = _post(endpoint, payload, timeout)
    return {"request_digest": _digest(payload), "response_digest": _digest(json.loads(raw.decode("utf-8"))) if raw else None,
            "accepted": error is None and _choice(response) in payload["questions"]["choice"]["criteria"], "error": error,
            "input_budget": provider.last_input_budget, "usage": response.get("usage") if isinstance(response, dict) else None,
            "synthetic": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:18765")
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--tokenizer-sha256", required=True)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()

    if args.output.exists():
        raise SystemExit("output must be a new directory; sealed evidence cannot be overwritten")
    started_unix = time.time()

    prepared = _read_json(args.inputs)
    read_events = [{"sequence": 1, "path": str(args.inputs.resolve()), "purpose": "approved_inputs"}]
    manifest = _read_json(args.manifest)
    read_events.append({"sequence": 2, "path": str(args.manifest.resolve()), "purpose": "metadata_only_manifest"})
    if not isinstance(prepared, dict) or not isinstance(prepared.get("prepared_records"), list):
        raise SystemExit("prepared inputs are invalid")
    if not isinstance(manifest, dict) or not isinstance(manifest.get("formal_question_ids"), list):
        raise SystemExit("metadata-only manifest is invalid")
    ids = manifest["formal_question_ids"]
    if not ids or any(not isinstance(qid, str) or not qid.strip() for qid in ids) or len(set(ids)) != len(ids):
        raise SystemExit("manifest question ids must be nonempty and unique")
    selected = set(ids)
    records = [r for r in prepared["prepared_records"] if isinstance(r, dict) and r.get("question_id") in selected]
    if len(records) != len(ids) or {r["question_id"] for r in records} != selected:
        raise SystemExit("manifest/input question coverage mismatch")
    by_id = {r["question_id"]: r for r in records}
    records = [by_id[qid] for qid in ids]
    provider = LayaSystemOneProvider(endpoint=args.endpoint, tokenizer_path=str(args.tokenizer),
                                     tokenizer_sha256=args.tokenizer_sha256,
                                     require_option_token_validation=False)
    args.output.mkdir(parents=True, exist_ok=False)
    before_health = _health(args.endpoint, args.timeout)
    preflight = _preflight(provider, args.endpoint.rstrip("/") + "/v1/systemone", args.timeout)
    executed: list[dict] = []
    stopped = not preflight_admits_formal_run(before_health, preflight)
    for prepared_record in ([] if stopped else records):
        request = prepared_record.get("prepared_request")
        if not isinstance(request, dict):
            executed.append({"question_id": prepared_record.get("question_id"), "invalid_category": "request_missing"})
            stopped = True
            break
        try:
            payload = provider.build_wire_request(request)
        except Exception as exc:
            executed.append({"question_id": prepared_record.get("question_id"), "input_valid": False,
                              "invalid_category": "input_budget", "error": f"{type(exc).__name__}: {exc}"})
            stopped = True
            break
        started = time.time()
        response, raw_response, error = _post(provider.endpoint, payload, args.timeout)
        usage = response.get("usage") if isinstance(response, dict) else None
        if not isinstance(usage, dict):
            usage = {"truncated": None, "usage_missing": True}
        selected_choice = _choice(response)
        record = {"question_id": prepared_record["question_id"], "track": prepared_record.get("track"),
                  "split": prepared_record.get("split"), "request": payload,
                  "request_digest": _digest(payload), "response": {"choice": selected_choice} if selected_choice is not None else None,
                  "response_body": response,
                  "response_digest": _digest(response) if response is not None else None,
                  "usage": usage, "input_budget": provider.last_input_budget,
                  "input_valid": True, "elapsed_ms": round((time.time() - started) * 1000, 3),
                  "error": error}
        executed.append(record)
        if (usage.get("truncated") is not False or type(usage.get("state_tokens_dropped")) is not int
                or usage["state_tokens_dropped"] != 0):
            record["invalid_category"] = "truncated" if usage.get("truncated") is True else "usage_unverifiable"
            stopped = True
            break
        if error:
            # Preserve the exception and stop; no retry or answer-dependent retry is allowed.
            stopped = True
            break
        if selected_choice not in payload["questions"]["choice"]["criteria"]:
            record["invalid_category"] = "choice_out_of_set" if selected_choice is not None else "response_invalid"
            stopped = True
            break
    after_health = _health(args.endpoint, args.timeout)
    if after_health != before_health:
        stopped = True
    metadata = {"schema_version": "calibration_transport_manifest.v1", "endpoint": args.endpoint,
                "manifest_digest": _digest(manifest), "input_digest": prepared.get("inputs_digest"),
                "provider_revision": provider.PROVIDER_REVISION, "tokenizer_sha256": args.tokenizer_sha256,
                "device": manifest.get("device", "unknown"), "max_len": manifest.get("max_len"),
                "head_max_len": manifest.get("head_max_len"), "parameters": manifest.get("parameters", {}),
                "preflight": preflight,
                "before_health": before_health, "after_health": after_health,
                "execution_identity": {"pid": os.getpid(), "script": str(Path(__file__).resolve()),
                                       "script_sha256": "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                       "python": sys.version, "started_unix": started_unix},
                "truth_loaded": False, "labels_read": False}
    envelope = build_run_envelope(executed, metadata, {"status": "stopped_on_invalid_or_error" if stopped else "sealed",
                                                       "executed_count": len(executed), "formal_count": len(records),
                                                       "stopped": stopped})
    (args.output / "run-envelope.json").write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "runner-read-log.json").write_text(json.dumps({"schema_version": "calibration_runner_read_log.v1",
        "execution_identity": metadata["execution_identity"], "events": read_events,
        "truth_loaded": False, "labels_read": False}, indent=2), encoding="utf-8")
    return 0 if not stopped and len(executed) == len(records) else 2


if __name__ == "__main__":
    raise SystemExit(main())
