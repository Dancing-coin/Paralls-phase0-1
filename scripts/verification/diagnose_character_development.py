"""Bounded, development-only character provider diagnosis.

This runner deliberately consumes a frozen package and never opens calibration,
final, or independent-holdout material.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from time import monotonic
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.character_agent.gateway.laya_provider import LayaSystemOneProvider
from app.character_agent.planning.l3_planner import CandidateCompiler

EXPECTED_PACKAGE_DIGEST = "b579d06613831eaf97ae0faab3e280e67bf4d8b041abe34c5a02ddcb0e09d1a8"
PROVIDER_REVISION = LayaSystemOneProvider.PROVIDER_REVISION
def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def ordered_digest(value: Any) -> str:
    """Digest insertion order recursively; unlike digest, dict order is material."""
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _summary_without_identity(value: str) -> str:
    return "; ".join(part for part in value.split("; ") if not part.startswith(("character_id=", "canonical_name=")))


def _frozen_description(record: dict[str, Any]) -> str:
    description = record.get("description")
    if isinstance(description, str) and description:
        return description
    # Synthetic unit-test rows are normalized through the same compiler rule;
    # production packages always carry the compiler-generated field.
    return CandidateCompiler._semantic_description(record)


def build_variants(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        for variant in ("baseline-repeat", "descriptions", "anonymous-summary"):
            changed = copy.deepcopy(row)
            changed["variant"] = variant
            context = changed["provider_request"]["context"]
            if variant == "descriptions":
                mapping = context["candidate_mapping"]
                changed["wire_request"]["questions"]["choice"]["criteria"] = {
                        label: _frozen_description(record) for label, record in mapping.items()
                }
            elif variant == "anonymous-summary":
                context["effective_profile_summary"] = _summary_without_identity(context.get("effective_profile_summary", ""))
            output.append({"variant": variant, "row": changed})
        if (row.get("scenario_id"), row.get("actor_id")) in {
            ("archive-scratches", "char_b"), ("guard-order", "char_a"),
            ("upset-witness", "char_b"), ("unavailable-key", "char_a")
        }:
            changed = copy.deepcopy(row); changed["variant"] = "reversed-order"
            context = changed["provider_request"]["context"]
            labels = list(context["candidate_intents"])[::-1]
            context["candidate_intents"] = labels
            context["candidate_mapping"] = {label: context["candidate_mapping"][label] for label in labels}
            context["frozen_candidates"] = list(reversed(context["frozen_candidates"]))
            changed["wire_request"]["questions"]["choice"]["criteria"] = {label: label for label in labels}
            output.append({"variant": "reversed-order", "row": changed})
    return output


def validate_variant(row: dict[str, Any], variant: str) -> None:
    if variant not in {"baseline-repeat", "descriptions", "anonymous-summary", "reversed-order"}:
        raise ValueError("unknown_variant")
    if row.get("split") != "development":
        raise ValueError("unknown_split")
    context = row.get("provider_request", {}).get("context", {})
    mapping = context.get("candidate_mapping")
    if not isinstance(mapping, dict):
        raise ValueError("candidate_mapping_missing")
    labels = list(mapping)
    if context.get("candidate_intents") != labels:
        raise ValueError("candidate_mapping_order_mismatch")
    if variant in {"baseline-repeat", "anonymous-summary", "reversed-order"}:
        if row.get("wire_request", {}).get("questions", {}).get("choice", {}).get("criteria", {}) != {label: label for label in labels}:
            raise ValueError("wire_input_tampered")
    if variant == "descriptions":
        criteria = row.get("wire_request", {}).get("questions", {}).get("choice", {}).get("criteria", {})
        expected = {label: _frozen_description(record) for label, record in mapping.items()}
        if criteria != expected:
            raise ValueError("description_variant_not_single_variable")


def _load_package(path: Path) -> dict[str, Any]:
    package = json.loads(path.read_text(encoding="utf-8"))
    if digest(package) != EXPECTED_PACKAGE_DIGEST:
        raise ValueError("baseline_digest_mismatch")
    if package.get("final_labels_read") is not False or package.get("preflight", {}).get("development_ready") is not True:
        raise ValueError("development_only_contract_defect")
    if len(package.get("records", [])) != 16 or any(row.get("split") != "development" for row in package["records"]):
        raise ValueError("development_requires_16_rows")
    return package


def run(package: dict[str, Any], output_dir: Path, endpoint: str, timeout: float = 120.0, freeze_only: bool = False,
        baseline_path: Path | None = None) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output_destination_must_be_empty")
    if ROOT.resolve() in output_dir.resolve().parents or output_dir.resolve() == ROOT.resolve():
        raise ValueError("output_must_be_external")
    output_dir.mkdir(parents=True, exist_ok=True)
    if baseline_path is not None:
        shutil.copyfile(baseline_path, output_dir / "frozen-development-package.json")
    else:
        (output_dir / "frozen-development-package.json").write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    matrix = build_variants(package["records"])
    (output_dir / "matrix.json").write_text(json.dumps({"variants": [{"variant": item["variant"], "scenario_id": item["row"]["scenario_id"], "actor_id": item["row"]["actor_id"], "input_digest": digest(item["row"]["provider_request"]), "ordered_input_digest": ordered_digest(item["row"]["provider_request"])} for item in matrix]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if freeze_only:
        return {"status": "frozen", "package_digest": EXPECTED_PACKAGE_DIGEST}
    provider = LayaSystemOneProvider(endpoint=endpoint, timeout_seconds=timeout)
    results: list[dict[str, Any]] = []
    variants = build_variants(package["records"])
    with (output_dir / "results.jsonl").open("x", encoding="utf-8") as stream:
        for item in variants:
            row, variant = item["row"], item["variant"]
            validate_variant(row, variant)
            started = monotonic(); error = None; response = None
            wire = None
            try:
                wire = provider.build_wire_request(row["provider_request"])
                if variant == "descriptions":
                    wire["questions"]["choice"]["criteria"] = {
                        label: _frozen_description(record)
                        for label, record in row["provider_request"]["context"]["candidate_mapping"].items()
                    }
                if variant not in {"descriptions", "reversed-order"} and wire != row["wire_request"]:
                    raise ValueError("wire_input_tampered")
                response = provider._post(wire)
            except Exception as exc:  # preserve provider errors as evidence
                error = f"{exc.__class__.__name__}:{exc}"
            call = provider.last_call or {}
            result = {"scenario_id": row["scenario_id"], "actor_id": row["actor_id"], "split": "development",
                      "variant": variant, "ordered_input_digest": ordered_digest(row["provider_request"]),
                      "ordered_wire_digest": ordered_digest(wire if 'wire' in locals() else row.get("wire_request")),
                      "input_digest": row.get("input_digest"), "wire_request_digest": row.get("wire_request_digest"),
                      "provider_revision": PROVIDER_REVISION, "provider_request": row["provider_request"], "wire_request": row["wire_request"],
                      "actual_wire_request": call.get("request", wire), "raw_response": response,
                      "mapping": row["provider_request"]["context"]["candidate_mapping"], "latency_ms": round((monotonic() - started) * 1000, 3),
                      "error": error}
            stream.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n"); stream.flush(); os.fsync(stream.fileno()); results.append(result)
    by_variant = {}
    for result in results:
        bucket = by_variant.setdefault(result["variant"], {"calls": 0, "responses": 0, "errors": 0, "ordered_digests": []})
        bucket["calls"] += 1
        bucket["responses"] += result["raw_response"] is not None
        bucket["errors"] += result["error"] is not None
        bucket["ordered_digests"].append(result["ordered_wire_digest"])
    summary = {"status": "development_completed", "package_digest": EXPECTED_PACKAGE_DIGEST,
               "rows": len(results), "expected_rows": 52, "provider_revision": PROVIDER_REVISION,
               "variants": by_variant}
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--endpoint", required=False, default="")
    parser.add_argument("--freeze-only", action="store_true")
    args = parser.parse_args()
    package = _load_package(args.baseline_dir / "frozen-development-package.json")
    print(json.dumps(run(package, args.output_dir, args.endpoint, freeze_only=args.freeze_only,
                         baseline_path=args.baseline_dir / "frozen-development-package.json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
