"""Create the metadata-only transport/input manifest for the repaired run."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

FORMAL_PREFIXES = ("indicator_gap", "reply_slips", "muted_bell", "message_channel", "shared_reminder")

def digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--prepared", type=Path, required=True); p.add_argument("--output", type=Path, required=True)
    p.add_argument("--old-wire-digest", required=True); p.add_argument("--threshold-digest", required=True)
    p.add_argument("--tokenizer-sha256", required=True); p.add_argument("--device", default="cpu")
    a = p.parse_args(); doc = json.loads(a.prepared.read_text(encoding="utf-8")); records = doc["prepared_records"]
    formal = [r for r in records if any(f"_{prefix}_" in r["question_id"] for prefix in FORMAL_PREFIXES)
              or "_timeline_check_participant_01_" in r["question_id"]
              or "_timeline_check_participant_02_" in r["question_id"]]
    if len(formal) != 22: raise SystemExit(f"expected 22 formal records, got {len(formal)}")
    entries = []
    for r in formal:
        budget = r.get("input_budget") or {}
        entries.append({"question_id": r["question_id"], "split": r["split"], "track": r["track"],
                        "wire_digest": r["wire_digest"], "max_len": budget.get("max_len"),
                        "head_max_len": budget.get("head_max_len"), "required_tokens": budget.get("required_tokens"),
                        "state_tokens": budget.get("state_tokens"), "head_tokens": budget.get("head_tokens"),
                        "candidate_order": list((r["wire"]["questions"]["choice"]["criteria"]).keys()),
                        "input_valid": budget.get("truncated") is False})
    manifest = {"schema_version": "calibration_transport_manifest.v1", "run_kind": "repair_diagnostic_rerun",
                "formal_question_ids": [e["question_id"] for e in entries], "device": a.device,
                "max_len": 2091, "head_max_len": 256, "old_wire_digest": a.old_wire_digest,
                "new_input_digest": doc.get("inputs_digest"), "provider_revision": "laya:68804629e8ccd9d616d48a40e87de9fabbeae069:1720e3e3357cfe1e281542e223f8273b0890ca34",
                "tokenizer_sha256": a.tokenizer_sha256, "threshold_digest": a.threshold_digest,
                "truth_included": False, "acceptable_sets_included": False, "reviewer_rationale_included": False,
                "records": entries}
    a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"); return 0
if __name__ == "__main__": raise SystemExit(main())
