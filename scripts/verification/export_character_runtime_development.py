"""Freeze development-only model/contract associations from an existing trace.

No model calls, authority writes, truth labels or formal split reads occur here.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT))

from app.character_agent.evaluation.runtime_trace_export import export_runtime_trace
from app.character_agent.gateway.laya_provider import LayaSystemOneProvider
from scripts.verification.run_context import run_scope


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--tokenizer-sha256", required=True)
    parser.add_argument("--export-evidence", type=Path, required=True)
    args = parser.parse_args()
    provider = LayaSystemOneProvider(
        endpoint="http://unused.invalid/v1/systemone", tokenizer_path=str(args.tokenizer),
        tokenizer_sha256=args.tokenizer_sha256,
    )
    with run_scope(PROJECT_ROOT, export_to=args.export_evidence) as run:
        result = export_runtime_trace(args.trace, provider=provider)
        (run.evidence_root / "development-source.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        summary = {"run_id": run.run_id, **{key: result[key] for key in (
            "status", "formal_eligible", "accepted_count", "rejections", "source_sha256", "artifact_digest")}}
        (run.evidence_root / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False))
    return 0 if result["accepted_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
